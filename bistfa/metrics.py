"""
Metrik kaydı: tüm oran ve göstergeler TEK yerde tanımlıdır. Her sonuç; değer, birim, dönem, formül, kullanılan
kaynak kalemler (kod, dönem, değer), bakiye bazı, yıllıklandırma ve hesaplanamadıysa NEDEN taşır.

Genel kurallar
- Oranın payı ve paydası aynı dönem kolonundan alınır (TMS 29 fiyat bazı farkını dışlamak için).
- Ortalama bakiye: (dönem başı + dönem sonu) / 2. Dönem başı = önceki yıl sonu bilançosu. Yalnız iki bakiye aynı
  fiyat bazındaysa (ikisi de TMS 29 öncesi) kullanılır; TMS 29 döneminde kaynakta açılış bakiyesi yeniden ifade
  edilmediği için DÖNEM SONU bakiyesi kullanılır ve sonuçta belirtilir. İlk dönemde açılış bakiyesi yoksa dönem sonu.
- Yıllıklandırma: getiri, devir hızı ve gün hesaplarında ara dönem (YTD) akışları × 12 / ay sayısı. Yıllık
  dönemlerde yıllıklandırma yapılmaz. Mevsimsellik göz ardı edilir.
- FAVÖK kaynakta raporlanmaz; HESAPLANIR: net faaliyet kârı (3H) + nakit akış tablosundaki amortisman (4CAB).
- FAVÖK hasılatın %1'inden küçükse (sıfır/negatif dahil) FAVÖK bazlı oranlar hesaplanmaz.
- Özkaynak (ortalama) sıfır veya negatifse ROE, özkaynak çarpanı ve borç/özkaynak hesaplanmaz.
- Net finansal borç yalnız açıkça finansal borç olan kalemleri kullanır (2AA + 2BA); ticari borçlar katılmaz.
  'Diğer finansal yükümlülükler' (2AAG, 2BB) dahil edilmez. Kiralama yükümlülükleri kaynakta finansal borçlar
  içinde raporlanıyor olabilir.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import catalog as C
from .periods import Period, parse


def _d(x, n=1):
    return f"{x:.{n}f}".replace(".", ",")


class NA(Exception):
    pass


@dataclass
class Result:
    id: str
    name: str
    group: str
    unit: str                 # "TL", "pct", "x", "days", "ratio"
    period: str
    value: float | None
    status: str               # "ok" | "na"
    reason: str
    formula: str
    inputs: list = field(default_factory=list)   # (açıklama, kod, dönem, değer)
    basis: str = ""
    annualized: bool = False
    better: str | None = None  # "up" | "down" | None
    note: str = ""


@dataclass
class Def:
    id: str
    name: str
    group: str
    unit: str
    formula: str
    fn: object
    better: str | None = None
    note: str = ""


class Ctx:
    def __init__(self, co, P: Period, force_end: bool = False):
        self.co, self.P, self.force_end = co, P, force_end
        self.inputs, self.basis, self.annualized = [], [], False

    def raw(self, code, P=None):
        P = P or self.P
        w = self.co.wide
        if code in w.index and P.label in w.columns:
            v = w.at[code, P.label]
            return None if v != v else float(v)
        return None

    def v(self, code, P=None, label=None, optional=False):
        P = P or self.P
        x = self.raw(code, P)
        if x is None:
            if optional:
                self.inputs.append((label or C.LABEL.get(code, code), code, P.label, 0.0))
                return 0.0
            raise NA(f"{label or C.LABEL.get(code, code)} ({code}) {P.label} döneminde kaynakta yok")
        self.inputs.append((label or C.LABEL.get(code, code), code, P.label, x))
        return x

    def flow(self, code, label=None, annualize=False, optional=False):
        x = self.v(code, label=label, optional=optional)
        if annualize and self.P.months != 12:
            self.annualized = True
            return x * 12 / self.P.months
        return x

    def avg(self, code, label=None):
        end = self.v(code, label=label)
        if self.force_end:
            self._b("dönem sonu bakiyesi")
            return end
        op = self.P.prior_year_end()
        if self.P.tms29:
            self._b("dönem sonu bakiyesi (TMS 29: açılış bakiyesi aynı fiyat bazında değil)")
            return end
        start = self.raw(code, op)
        if start is None or op.label not in self.co.period_labels:
            self._b("dönem sonu bakiyesi (açılış bakiyesi yok)")
            return end
        if op.tms29 != self.P.tms29:
            self._b("dönem sonu bakiyesi (açılış farklı fiyat bazında)")
            return end
        self.inputs.append((f"{label or C.LABEL.get(code, code)} (açılış)", code, op.label, start))
        self._b(f"ortalama bakiye ({op.label} ve {self.P.label})")
        return (start + end) / 2

    def _b(self, t):
        if t not in self.basis:
            self.basis.append(t)

    # ortak bileşenler
    def ebitda(self, annualize=False):
        return self.flow("3H", annualize=annualize) + self.flow("4CAB", annualize=annualize)

    def ebitda_ok(self):
        e, r = self.ebitda(), self.flow("3C")
        if r <= 0:
            raise NA("Hasılat sıfır veya negatif")
        if e <= 0.01 * r:
            raise NA(f"FAVÖK hasılatın %1'inden küçük (%{_d(e / r * 100)}); FAVÖK bazlı oran anlamsız")
        return e

    def fin_debt(self):
        return self.v("2AA") + self.v("2BA")

    def net_debt(self):
        return self.fin_debt() - self.v("1AA") - self.v("1AB", optional=True)

    def pos(self, x, what):
        if x <= 0:
            raise NA(f"{what} sıfır veya negatif; oran anlamsız")
        return x


def _div(a, b, what="Payda"):
    if b == 0:
        raise NA(f"{what} sıfır")
    return a / b


DEFS: list[Def] = []


def d(id, name, group, unit, formula, better=None, note=""):
    def wrap(fn):
        DEFS.append(Def(id, name, group, unit, formula, fn, better, note))
        return fn
    return wrap


# --- Büyüklükler (TL, YTD akış veya bilanço tarihi) -----------------------------------------------
@d("revenue", "Hasılat", "Büyüklük", "TL", "Satış gelirleri (3C)", "up")
def _(c): return c.flow("3C")
@d("gross_profit", "Brüt kâr", "Büyüklük", "TL", "Brüt kâr (3D)", "up")
def _(c): return c.flow("3D")
@d("ebit", "Faaliyet kârı (EBIT)", "Büyüklük", "TL", "Finansman gideri öncesi faaliyet kârı (3HACA)", "up",
   "Esas faaliyet kârı + yatırım faaliyetleri gelir/giderleri + iştirak payları")
def _(c): return c.flow("3HACA")
@d("ebitda", "FAVÖK (hesaplanan)", "Büyüklük", "TL", "Net faaliyet kârı (3H) + amortisman ve itfa payları (4CAB)", "up",
   "Kaynakta raporlanmaz; diğer faaliyet gelir/giderleri hariç tutulur")
def _(c): return c.ebitda()
@d("net_income", "Net dönem kârı", "Büyüklük", "TL", "Dönem kârı/zararı (3L), azınlık payları dahil", "up")
def _(c): return c.flow("3L")
@d("net_income_parent", "Ana ortaklık net kârı", "Büyüklük", "TL", "Ana ortaklık payları (3Z)", "up")
def _(c): return c.flow("3Z")
@d("ocf", "İşletme faaliyetlerinden nakit", "Büyüklük", "TL", "İşletme faaliyetlerinden net nakit (4C)", "up")
def _(c): return c.flow("4C")
@d("capex", "Sabit sermaye yatırımları", "Büyüklük", "TL", "Sabit sermaye yatırımları (4CAI, nakit çıkışı negatif)")
def _(c): return c.flow("4CAI")
@d("fcf", "Serbest nakit akışı (hesaplanan)", "Büyüklük", "TL",
   "İşletme faaliyetlerinden nakit (4C) + sabit sermaye yatırımları (4CAI)", "up",
   "Kaynağın 'serbest nakit akımı' (4CB) tüm yatırım faaliyetlerini düşer; bu tanım yalnız CapEx'i düşer")
def _(c): return c.flow("4C") + c.flow("4CAI")
@d("fin_debt", "Finansal borç", "Büyüklük", "TL", "KV finansal borçlar (2AA) + UV finansal borçlar (2BA)", "down")
def _(c): return c.fin_debt()
@d("net_debt", "Net finansal borç", "Büyüklük", "TL",
   "Finansal borç (2AA + 2BA) − nakit (1AA) − KV finansal yatırımlar (1AB)", "down", "Negatif değer net nakit pozisyonudur")
def _(c): return c.net_debt()
@d("nwc", "Net işletme sermayesi", "Büyüklük", "TL", "Dönen varlıklar (1A) − kısa vadeli yükümlülükler (2A)")
def _(c): return c.v("1A") - c.v("2A")
@d("total_assets", "Toplam varlıklar", "Büyüklük", "TL", "Toplam varlıklar (1BL)")
def _(c): return c.v("1BL")
@d("total_equity", "Özkaynaklar", "Büyüklük", "TL", "Özkaynaklar (2N), azınlık payları dahil", "up")
def _(c): return c.v("2N")


# --- Kârlılık (aynı dönem kolonu içinde) ---------------------------------------------------------
def margin(code):
    return lambda c: _div(c.flow(code), c.pos(c.flow("3C"), "Hasılat"), "Hasılat")


d("gross_margin", "Brüt kâr marjı", "Kârlılık", "pct", "Brüt kâr (3D) / hasılat (3C)", "up")(margin("3D"))
d("ebit_margin", "Faaliyet kârı (EBIT) marjı", "Kârlılık", "pct", "EBIT (3HACA) / hasılat (3C)", "up")(margin("3HACA"))
d("core_op_margin", "Net faaliyet kâr marjı", "Kârlılık", "pct",
  "Net faaliyet kârı (3H: brüt kâr − pazarlama − genel yönetim − Ar-Ge) / hasılat", "up")(margin("3H"))


@d("ebitda_margin", "FAVÖK marjı", "Kârlılık", "pct", "FAVÖK (3H + 4CAB) / hasılat (3C)", "up")
def _(c): return _div(c.ebitda(), c.pos(c.flow("3C"), "Hasılat"))


d("net_margin", "Net kâr marjı", "Kârlılık", "pct", "Dönem kârı (3L) / hasılat (3C)", "up")(margin("3L"))


# --- Getiri ve DuPont -------------------------------------------------------------------------------
@d("roe", "ROE (özkaynak kârlılığı)", "Getiri", "pct",
   "Ana ortaklık net kârı (3Z, yıllıklandırılmış) / ana ortaklık özkaynakları (2O, ortalama)", "up")
def _(c):
    return _div(c.flow("3Z", annualize=True), c.pos(c.avg("2O"), "Ana ortaklık özkaynağı"))


@d("roa", "ROA (aktif kârlılığı)", "Getiri", "pct", "Net dönem kârı (3L, yıllıklandırılmış) / toplam varlıklar (1BL, ortalama)", "up")
def _(c): return _div(c.flow("3L", annualize=True), c.pos(c.avg("1BL"), "Toplam varlıklar"))


@d("dupont_margin", "DuPont: net kâr marjı", "Getiri", "pct", "Ana ortaklık net kârı (3Z) / hasılat (3C)", "up")
def _(c): return _div(c.flow("3Z"), c.pos(c.flow("3C"), "Hasılat"))


@d("asset_turnover", "Varlık devir hızı", "Getiri", "x", "Hasılat (3C, yıllıklandırılmış) / toplam varlıklar (1BL, ortalama)", "up")
def _(c): return _div(c.flow("3C", annualize=True), c.pos(c.avg("1BL"), "Toplam varlıklar"))


@d("equity_multiplier", "Özkaynak çarpanı", "Getiri", "x",
   "Toplam varlıklar (1BL, ortalama) / ana ortaklık özkaynakları (2O, ortalama)", None, "Yüksek değer yüksek kaldıraç demektir")
def _(c): return _div(c.avg("1BL"), c.pos(c.avg("2O"), "Ana ortaklık özkaynağı"))


# --- Likidite ---------------------------------------------------------------------------------------
@d("current_ratio", "Cari oran", "Likidite", "ratio", "Dönen varlıklar (1A) / kısa vadeli yükümlülükler (2A)", "up")
def _(c): return _div(c.v("1A"), c.pos(c.v("2A"), "Kısa vadeli yükümlülükler"))


@d("quick_ratio", "Asit-test oranı", "Likidite", "ratio",
   "(Dönen varlıklar (1A) − stoklar (1AF)) / kısa vadeli yükümlülükler (2A)", "up",
   "Tanım: stoklar düşülür; peşin ödenmiş giderler ve diğer dönen varlıklar düşülmez")
def _(c): return _div(c.v("1A") - c.v("1AF"), c.pos(c.v("2A"), "Kısa vadeli yükümlülükler"))


@d("cash_ratio", "Nakit oranı", "Likidite", "ratio", "Nakit ve nakit benzerleri (1AA) / kısa vadeli yükümlülükler (2A)", "up")
def _(c): return _div(c.v("1AA"), c.pos(c.v("2A"), "Kısa vadeli yükümlülükler"))


# --- Borçluluk ve faiz karşılama --------------------------------------------------------------------
@d("nd_ebitda", "Net finansal borç / FAVÖK", "Borçluluk", "x",
   "Net finansal borç / FAVÖK (ara dönemde yıllıklandırılmış)", "down")
def _(c):
    c.ebitda_ok()
    return _div(c.net_debt(), c.ebitda(annualize=True))


@d("fin_debt_to_equity", "Finansal borç / özkaynak", "Borçluluk", "x", "Finansal borç (2AA + 2BA) / özkaynaklar (2N)", "down")
def _(c): return _div(c.fin_debt(), c.pos(c.v("2N"), "Özkaynak"))


@d("liab_to_equity", "Toplam yükümlülük / özkaynak", "Borçluluk", "x",
   "(Kısa vadeli (2A) + uzun vadeli yükümlülükler (2B)) / özkaynaklar (2N)", "down",
   "Ticari borçlar dahil tüm yükümlülükler; finansal borç/özkaynaktan farklıdır")
def _(c): return _div(c.v("2A") + c.v("2B"), c.pos(c.v("2N"), "Özkaynak"))


@d("liab_to_assets", "Yükümlülük / toplam varlık", "Borçluluk", "pct", "(2A + 2B) / toplam varlıklar (1BL)", "down")
def _(c): return _div(c.v("2A") + c.v("2B"), c.pos(c.v("1BL"), "Toplam varlıklar"))


@d("st_debt_share", "Kısa vadeli finansal borç payı", "Borçluluk", "pct", "KV finansal borçlar (2AA) / finansal borç (2AA + 2BA)", "down",
   "Borç vade yapısı: yüksek pay yeniden finansman ihtiyacını artırır")
def _(c): return _div(c.v("2AA"), c.pos(c.fin_debt(), "Finansal borç"))


def _net_fin_expense(c):
    fe = c.flow("3HC", label="Finansman gelir/gideri (net)")
    if fe >= 0:
        raise NA("Finansman satırı (3HC) net GELİR veya sıfır; kaynakta faiz gideri ayrıştırılamadığından faiz karşılama "
                 "hesaplanmadı (TMS 29 döneminde parasal kazançlar bu satırı pozitife çevirebilir)")
    return -fe


@d("int_cov_ebit", "Faiz karşılama (EBIT)", "Borçluluk", "x",
   "EBIT (3HACA) / net finansman gideri (−3HC, yalnız 3HC < 0 iken)", "up",
   "Net finansman gideri; kur farkı ve TMS 29 etkilerini içerebilir, saf faiz gideri değildir")
def _(c): return c.flow("3HACA") / _net_fin_expense(c)


@d("int_cov_ebitda", "Faiz karşılama (FAVÖK)", "Borçluluk", "x",
   "FAVÖK (3H + 4CAB) / net finansman gideri (−3HC, yalnız 3HC < 0 iken)", "up",
   "Net finansman gideri; kur farkı ve TMS 29 etkilerini içerebilir")
def _(c): return c.ebitda() / _net_fin_expense(c)


# --- Nakit üretimi ------------------------------------------------------------------------------------
@d("ocf_to_ebitda", "Nakit dönüşümü (FNA / FAVÖK)", "Nakit", "ratio", "İşletme faaliyetlerinden nakit (4C) / FAVÖK", "up")
def _(c): return c.flow("4C") / c.ebitda_ok()


@d("ocf_to_net_income", "FNA / net kâr", "Nakit", "ratio", "İşletme faaliyetlerinden nakit (4C) / dönem kârı (3L)", "up")
def _(c): return c.flow("4C") / c.pos(c.flow("3L"), "Dönem kârı")


@d("fcf_margin", "Serbest nakit akışı marjı", "Nakit", "pct", "(4C + 4CAI) / hasılat (3C)", "up")
def _(c): return _div(c.flow("4C") + c.flow("4CAI"), c.pos(c.flow("3C"), "Hasılat"))


@d("capex_to_revenue", "CapEx / hasılat", "Nakit", "pct", "−Sabit sermaye yatırımları (4CAI) / hasılat (3C)")
def _(c): return _div(-c.flow("4CAI"), c.pos(c.flow("3C"), "Hasılat"))


@d("capex_to_da", "CapEx / amortisman", "Nakit", "x", "−4CAI / amortisman ve itfa payları (4CAB)", None,
   "1'in üstü varlık tabanının amortismandan hızlı büyüdüğünü gösterir")
def _(c): return _div(-c.flow("4CAI"), c.pos(c.flow("4CAB"), "Amortisman"))


# --- İşletme sermayesi (gün) ---------------------------------------------------------------------------
def _cogs(c):
    x = c.flow("3CA", annualize=True)
    if x >= 0:
        raise NA("Satışların maliyeti negatif (gider) olarak raporlanmamış")
    return -x


@d("dio", "Stok gün sayısı", "İşletme sermayesi", "days", "Stoklar (1AF) / satışların maliyeti (yıllık) × 365", "down")
def _(c): return c.avg("1AF") / _cogs(c) * 365


@d("dso", "Alacak gün sayısı", "İşletme sermayesi", "days", "KV ticari alacaklar (1AC) / hasılat (yıllık) × 365", "down")
def _(c): return c.avg("1AC") / c.pos(c.flow("3C", annualize=True), "Hasılat") * 365


@d("dpo", "Borç gün sayısı", "İşletme sermayesi", "days", "KV ticari borçlar (2AAGAA) / satışların maliyeti (yıllık) × 365", None)
def _(c): return c.avg("2AAGAA") / _cogs(c) * 365


@d("ccc", "Nakit dönüşüm döngüsü", "İşletme sermayesi", "days", "Stok günü + alacak günü − borç günü", "down",
   "Negatif değer işletme sermayesinin tedarikçilerce finanse edildiğini gösterir")
def _(c):
    i = c.avg("1AF") / _cogs(c) * 365
    r = c.avg("1AC") / c.pos(c.flow("3C", annualize=True), "Hasılat") * 365
    p = c.avg("2AAGAA") / _cogs(c) * 365
    return i + r - p


BY_ID = {x.id: x for x in DEFS}
GROUPS = list(dict.fromkeys(x.group for x in DEFS))


def compute(co, P: Period, mid: str, force_end: bool = False) -> Result:
    m = BY_ID[mid]
    c = Ctx(co, P, force_end)
    try:
        v = m.fn(c)
        status, reason = "ok", ""
    except NA as e:
        v, status, reason = None, "na", str(e)
    except ZeroDivisionError:
        v, status, reason = None, "na", "Payda sıfır"
    basis = "; ".join(c.basis) if c.basis else ("akış ve bakiye aynı dönem kolonundan" if m.unit != "TL" else "")
    if c.annualized:
        basis = (basis + "; " if basis else "") + f"akışlar × 12/{P.months} ile yıllıklandırıldı"
    seen, inputs = set(), []
    for x in c.inputs:  # aynı kalem birden çok kez okunmuş olabilir
        if (x[1], x[2], x[0]) not in seen:
            seen.add((x[1], x[2], x[0]))
            inputs.append(x)
    return Result(m.id, m.name, m.group, m.unit, P.label, v, status, reason, m.formula, inputs, basis,
                  c.annualized, m.better, m.note)


def compute_all(co, P: Period, force_end: bool = False) -> dict[str, Result]:
    return {m.id: compute(co, P, m.id, force_end) for m in DEFS}


def series(co, mid: str, periods: list[Period]) -> list[Result]:
    return [compute(co, p, mid) for p in periods]
