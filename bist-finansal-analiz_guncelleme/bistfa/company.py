"""Company: kaynak verisi + model + dönemler + kaynak sorunları + metrikler (tek giriş noktası)."""
from __future__ import annotations

from functools import lru_cache

from . import metrics as M
from . import model, quality, source
from .peers import name as peer_name
from .periods import Period, comparability, parse, safe_change, COMP_TEXT, COMPARABLE_AMOUNTS

STOCK_METRICS = {"total_assets", "total_equity", "nwc", "net_debt", "fin_debt"}   # bilanço tarihli TL metrikleri
FIN_SECTOR_CODES = ["1AD", "1BA", "2AAGB", "2BC", "3CAC", "3CAD", "3CAE"]


class Company:
    def __init__(self, raw: source.RawData, basis: str = "common"):
        self.raw = raw
        self.basis = basis
        self.ticker = raw.ticker
        self.name = peer_name(raw.ticker)
        self.facts, self.wide, self.periods, self.gaps, self.price = model.build(raw, basis)
        self.kinds, self.kinds_bs = self.price["kinds"], self.price["kinds_bs"]
        if not self.periods:
            raise source.FetchError(f"{self.ticker}: kaynakta okunabilir dönem bulunamadı.")
        if "3C" not in self.wide.index or self.wide.loc["3C"].notna().sum() == 0:
            raise source.FetchError(f"{self.ticker}: gelir tablosu kalemleri bulunamadı; şirket reel sektör (XI_29) "
                                    "formatında raporlamıyor olabilir.")
        self.period_labels = [p.label for p in self.periods]
        self.issues = quality.detect_issues(self.ticker, self.wide, self.periods, self.kinds, self.kinds_bs, legacy=basis == "source")
        for lbl in self.price.get("missing", []):
            self.issues.setdefault(lbl, "TÜFE tablosunda bu dönemin fiyat düzeyi yok; kolon kaynak fiyatıyla bırakıldı")
        self.checks = quality.run_checks(self.ticker, self.wide, self.periods, self.issues, self.gaps,
                                         wide_source=self.price["wide_source"],
                                         kinds=None if basis == "source" else self.kinds)
        self._cache = {}

    # --- erişim ---
    def period(self, label: str) -> Period:
        return parse(label)

    def comp(self, cur: Period, prev: Period, stock: bool = False) -> str:
        """Karşılaştırılabilirlik kodu. stock=True bilanço kalemleri içindir (ara dönem bilançoları yeniden düzenlenmez)."""
        return comparability(cur, prev, self.issues, set(self.period_labels),
                             None if self.basis == "source" else (self.kinds_bs if stock else self.kinds))

    def basis_text(self, P: Period, stock: bool = False) -> str:
        return self.price["text_bs" if stock else "text"].get(P.label, P.price_basis)

    @property
    def basis_name(self) -> str:
        from .pricebasis import month_label
        if not self.price.get("applies", True):
            return "nominal TL (enflasyon muhasebesi uygulanmıyor)"
        return {"common": f"{month_label(self.price['target'])} fiyatıyla", "published": "yayımlandığı gibi",
                "source": "kaynak kolonları"}[self.basis]

    def annual_periods(self) -> list[Period]:
        return [p for p in self.periods if p.is_annual]

    def value(self, code: str, label: str):
        if code in self.wide.index and label in self.wide.columns:
            v = self.wide.at[code, label]
            return None if v != v else float(v)
        return None

    def financial_sector_flags(self, P: Period) -> list[str]:
        return [c for c in FIN_SECTOR_CODES if (self.value(c, P.label) or 0) != 0]

    # --- metrikler ---
    def metric(self, mid: str, P: Period, force_end: bool = False) -> M.Result:
        k = (mid, P.label, force_end)
        if k not in self._cache:
            self._cache[k] = M.compute(self, P, mid, force_end) if P.label in self.period_labels else \
                M.Result(mid, M.BY_ID[mid].name, M.BY_ID[mid].group, M.BY_ID[mid].unit, P.label, None, "na",
                         f"{P.label} dönemi kaynakta yok", M.BY_ID[mid].formula)
        return self._cache[k]

    def comparison(self, mid: str, P: Period) -> dict:
        """Cari dönemi aynı uzunluktaki önceki dönemle karşılaştırır ve yöntemi açıklar."""
        cur = self.metric(mid, P)
        prevP = P.prior_comparable()
        prev = self.metric(mid, prevP)
        comp = self.comp(P, prevP, stock=mid in STOCK_METRICS)
        out = {"cur": cur, "prev": prev, "prev_period": prevP.label, "comp": comp, "comp_text": COMP_TEXT[comp],
               "delta": None, "delta_text": "", "method": ""}
        if comp == "NA" or cur.value is None or prev.value is None:
            out["delta_text"] = "Karşılaştırılamadı: " + (COMP_TEXT[comp] if comp == "NA" else
                                                         (cur.reason or prev.reason or "değer yok"))
            return out
        if cur.unit == "TL":
            diff, pc, note = safe_change(cur.value, prev.value)
            if comp not in COMPARABLE_AMOUNTS:
                out["delta_text"] = COMP_TEXT[comp]
                out["method"] = "TL tutar değişimi gösterilmez"
                return out
            out["delta"] = pc
            word = "reel" if comp == "REAL" else "nominal"
            out["delta_text"] = (f"%{_tr(pc * 100, 1)} {word}".replace("%+", "+%").replace("%−", "−%") if pc is not None else note)
            out["method"] = f"({P.label} − {prevP.label}) / |{prevP.label}|; {COMP_TEXT[comp]}"
        else:
            diff = cur.value - prev.value
            out["delta"] = diff
            unit = {"pct": "puan", "x": "x", "days": "gün", "ratio": ""}[cur.unit]
            shown = diff * 100 if cur.unit == "pct" else diff
            out["delta_text"] = f"{_tr(shown, 1)} {unit}".strip() if cur.unit in ("pct", "days") else f"{_tr(shown, 2)}{unit}"
            out["method"] = (f"{P.label} − {prevP.label} farkı; oranlar her dönemin kendi kolonunda hesaplandığından "
                             "fiyat düzeyinden etkilenmez")
            if comp == "BASE_BREAK":
                out["method"] += ". Not: kaynakta baz kırılması işaretli dönem"
        return out


def _tr(x: float, d: int, sign=True) -> str:
    """Türkçe sayı biçimi: ondalık virgül, binlik nokta, eksi işareti (−)."""
    s = f"{abs(x):,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("−" if x < 0 else ("+" if sign and x > 0 else "")) + s


@lru_cache(maxsize=64)
def _load(ticker: str, refresh_token: int, basis: str) -> Company:
    return Company(source.load(ticker, refresh=refresh_token > 0), basis)


def load(ticker: str, refresh_token: int = 0, basis: str = "common") -> Company:
    """basis: "common" (ortak fiyat, reel karşılaştırma), "published" (yayımlandığı gibi), "source" (kaynak kolonları)."""
    return _load(ticker.strip().upper(), refresh_token, basis)
