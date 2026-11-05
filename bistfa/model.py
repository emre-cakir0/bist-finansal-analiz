"""
İç veri modeli: uzun formatlı fact tablosu. Her değer şu köken bilgileriyle tutulur:
şirket, kaynak kalem kodu ve adı, standart anahtar, tablo, dönem başı/sonu veya bilanço tarihi, dönem niteliği
(YTD akış / bilanço tarihi), kapsam, para birimi ve ölçek, kaynak ve alınma zamanı, raporlama çerçevesi,
TMS 29 / fiyat bazı, raporlanan mı türetilmiş mi.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import catalog as C
from .periods import Period, parse
from .source import RawData, SOURCE_NAME, period_cols

SCOPE = "Kaynakta belirtilmemiş (İş Yatırım yayımlıyorsa konsolide); tek seri kullanılır, solo/konsolide karışmaz"
FRAMEWORK = "TFRS, KGK finansal tablo örnekleri (XI_29 formatı)"
CURRENCY, SCALE = "TRY", "TL (birim)"


def build(raw: RawData) -> tuple[pd.DataFrame, pd.DataFrame, list[Period], list[str]]:
    """Döner: (facts uzun tablo, wide: kod x dönem, mevcut dönemler, kaynakta boş/eksik dönemler)"""
    df = raw.frame.copy()
    df["FINANCIAL_ITEM_CODE"] = df["FINANCIAL_ITEM_CODE"].astype(str)
    df = df.drop_duplicates("FINANCIAL_ITEM_CODE").set_index("FINANCIAL_ITEM_CODE")
    pcs = period_cols(df.reset_index())
    wide = df[pcs].apply(pd.to_numeric, errors="coerce")
    names = df["FINANCIAL_ITEM_NAME_TR"].to_dict()

    # tamamen boş dönemleri (açıklanmamış ya da çekilemeyen) ayır
    has = [p for p in pcs if wide.loc[wide.index.intersection(["1BL", "3C"]), p].notna().any()]
    periods = sorted((parse(p) for p in has), key=lambda p: p.key)
    wide = wide[[p.label for p in periods]] if periods else wide.iloc[:, :0]
    gaps = _gaps(periods)

    # türetilmiş satırlar
    g = lambda c: wide.loc[c] if c in wide.index else pd.Series(np.nan, index=wide.columns)  # noqa: E731
    der = {
        "D_TOTAL_LIAB": g("2A") + g("2B"),
        "D_EQ_RESID": g("2O") - wide.reindex(C.DERIVED["D_EQ_RESID"][1][1:]).fillna(0).sum(),
        "D_EBITDA": g("3H") + g("4CAB"),
        "D_FCF": g("4C") + g("4CAI"),
    }
    der_df = pd.DataFrame(der).T
    der_df.loc["D_EQ_RESID"] = der_df.loc["D_EQ_RESID"].where(der_df.loc["D_EQ_RESID"].abs() > 1000, 0.0)
    full = pd.concat([wide, der_df])

    # uzun fact tablosu
    rows = []
    fetched = raw.fetched_at.strftime("%d.%m.%Y %H:%M")
    for code in full.index:
        derived = code.startswith("D_")
        stmt = {"D_TOTAL_LIAB": "BS", "D_EQ_RESID": "BS", "D_EBITDA": "IS",
                "D_FCF": "CF"}.get(code) if derived else C.statement_of(code)
        flow = (stmt in ("IS", "CF")) if derived else C.is_flow(code)
        for p in periods:
            v = full.at[code, p.label]
            if pd.isna(v):
                continue
            rows.append((raw.ticker, code, C.CODE_STD.get(code), C.LABEL.get(code, names.get(code, code)),
                         None if derived else names.get(code), stmt, p.label, p.start if flow else None, p.end,
                         p.months if flow else 0, "YTD akış" if flow else "bilanço tarihi", SCOPE, CURRENCY, SCALE,
                         SOURCE_NAME if not derived else "Hesaplanan: " + C.DERIVED[code][0], fetched, FRAMEWORK,
                         p.price_basis, "türetilmiş" if derived else "raporlanan", float(v)))
    facts = pd.DataFrame(rows, columns=[
        "ticker", "code", "std_key", "item", "item_source", "statement", "period", "period_start", "period_end",
        "months", "basis", "scope", "currency", "scale", "source", "fetched_at", "framework", "price_basis",
        "value_type", "value"])
    return facts, full, periods, gaps


def _gaps(periods: list[Period]) -> list[str]:
    if not periods:
        return []
    have = {p.key for p in periods}
    out, y, m = [], periods[0].year, periods[0].month
    while y * 100 + m <= periods[-1].key:
        if y * 100 + m not in have:
            out.append(f"{y}/{m}")
        m += 3
        if m > 12:
            y, m = y + 1, 3
    return out
