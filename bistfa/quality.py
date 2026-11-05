"""
Veri kalitesi: toplam kimlikleri, bilanço dengesi, dönem bütünlüğü ve kaynak baz kırılması tespiti.
(Önceki uygulamanın rf_core kuralları buraya taşındı; perakende şirketlerinde SQL testleriyle aynı sonucu verir.)
"""
from __future__ import annotations

import pandas as pd

from . import catalog as C
from .periods import Period


def _d(x, n=1):
    return f"{x:.{n}f}".replace(".", ",")

TOL = 1000  # kaynak değerler bin TL'ye yuvarlanmış

# SQL projesinde KAP/yayımlanmış rakamlarla doğrulanan sorunlar (dw.known_data_issues)
KNOWN_ISSUES = {
    **{(t, "2022/12"): "2022/12 kolonu TMS 29 ile yeniden ifade edilmiş karşılaştırma değerleri taşıyor "
                       "(toplam varlıklar 2022/9'a göre ~2,6 kat)" for t in ("BIMAS", "MGROS", "SOKM", "CRFSA")},
    **{(t, p): "2025/12 kolonu 2025/9'a göre farklı fiyat bazında (BİM ve Migros yıllık hasılatı resmî rakamın ~1,18 katı)"
       for t in ("BIMAS", "MGROS", "SOKM") for p in ("2025/9", "2025/12")},
    ("BIMAS", "2025/6"): "Şüpheli: 2025/6 YTD hasılatı resmî çeyreklik rakamlarla uyuşmuyor",
}


def quarterly_revenue(wide: pd.DataFrame, periods: list[Period]) -> pd.Series:
    """Bağımsız çeyrek hasılatı = YTD(t) − YTD(t−1) aynı yıl içinde; Q1 = YTD. Önceki çeyrek yoksa türetilmez."""
    out = {}
    have = {p.label for p in periods}
    for p in periods:
        v = wide.at["3C", p.label] if "3C" in wide.index else None
        if p.month == 3:
            out[p.label] = v
        else:
            prev = f"{p.year}/{p.month - 3}"
            out[p.label] = v - wide.at["3C", prev] if prev in have else None
    return pd.Series(out, dtype=float)


def detect_issues(ticker: str, wide: pd.DataFrame, periods: list[Period]) -> dict[str, str]:
    out = {p: txt for (t, p), txt in KNOWN_ISSUES.items() if t == ticker}
    labels = [p.label for p in periods]
    if "1BL" in wide.index:
        ta = wide.loc["1BL", labels]
        for i in range(1, len(labels) - 1):
            a, b, c = ta.iloc[i - 1], ta.iloc[i], ta.iloc[i + 1]
            if a > 0 and b > 0 and c > 0 and b / a > 1.8 and c / b < 0.75:
                out.setdefault(labels[i], f"Otomatik tespit: toplam varlıklar önceki döneme göre {_d(b / a)} kat, sonraki "
                                          f"dönemde {_d(c / b, 2)} katına dönüyor (yeniden ifade / baz farkı şüphesi)")
    q = quarterly_revenue(wide, periods)
    prev = None
    for p in periods:
        v = q.get(p.label)
        if p.month > 3 and v is not None and prev is not None and prev > 0 and v == v:
            ratio = v / prev
            if not 0.5 <= ratio <= 2.0:
                out.setdefault(p.label, f"Otomatik tespit: türetilen çeyreklik hasılat önceki çeyreğin {_d(ratio, 2)} katı "
                                        f"(beklenen 0,5–2,0); YTD kolonları farklı fiyat bazında olabilir")
        if v is not None and v == v and v <= 0 and p.month > 3:
            out.setdefault(p.label, "Otomatik tespit: türetilen çeyreklik hasılat sıfır veya negatif")
        prev = v
    return out


def run_checks(ticker: str, wide: pd.DataFrame, periods: list[Period], issues: dict, gaps: list[str]) -> pd.DataFrame:
    rows = []
    for total, kids in C.IDENTITIES.items():
        if total not in wide.index:
            continue
        for p in periods:
            t = wide.at[total, p.label]
            if pd.isna(t):
                continue
            s = wide.reindex(kids)[p.label].fillna(0).sum()
            diff = abs(t - s)
            ok = diff <= TOL
            name = f"{C.LABEL.get(total, total)} = alt kalemler"
            res = "PASS" if ok else ("EXPLAINED" if p.label in issues else "FAIL")
            rows.append(("Toplam kimliği", name, p.label, res,
                         f"{total} − ({' + '.join(kids)}) = {diff:,.0f} TL".replace(",", ".")))
    q = quarterly_revenue(wide, periods)
    prev = None
    for p in periods:
        v = q.get(p.label)
        if p.month > 3 and v == v and v is not None and prev:
            ok = v > 0 and 0.5 <= v / prev <= 2.0
            res = "PASS" if ok else ("EXPLAINED" if p.label in issues else "FAIL")
            rows.append(("Çeyrek makullüğü", "Türetilen çeyreklik hasılat 0,5–2,0 x önceki çeyrek", p.label, res,
                         f"oran {v / prev:.2f}".replace(".", ",")))
        prev = v
    rows.append(("Dönem bütünlüğü", "İlk ve son dönem arasında eksik çeyrek yok", None,
                 "PASS" if not gaps else "FAIL", "eksik: " + ", ".join(gaps) if gaps else f"{len(periods)} dönem"))
    df = pd.DataFrame(rows, columns=["grup", "test", "dönem", "sonuç", "ayrıntı"])
    df.insert(0, "şirket", ticker)
    return df
