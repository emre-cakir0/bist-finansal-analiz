"""
Finansal tablolar: satırlar kalemler, sütunlar dönemler.

Görünümler
- "Tutar": raporlandığı gibi (giderler negatif; finansal giderler tabloda negatif gösterilir).
- "Yatay (tutar)" / "Yatay (%)": aynı uzunluktaki önceki dönemle (yıllık↔yıllık, 9 aylık↔9 aylık) fark.
  Karşılaştırılabilirlik kodu sütun başlığına eklenir; baz kırılmasında yüzde hesaplanmaz.
  Sıfır baz ve kâr↔zarar işaret değişiminde yüzde gösterilmez (periods.safe_change).
- "Dikey (%)": gelir tablosu ve nakit akışında hasılata, bilançoda toplam varlıklara oran (aynı kolon).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import catalog as C
from .periods import Period, comparability, safe_change, COMPARABLE_AMOUNTS, BASE_BREAK, TMS29_TRANSITION

MODES = ["Tutar", "Yatay (tutar)", "Yatay (%)", "Dikey (%)"]
NAMES = {"IS": "Kâr veya zarar tablosu", "BS": "Finansal durum tablosu (bilanço)", "CF": "Nakit akış tablosu",
         "MEMO": "Dipnot bilgileri", "EQ": "Özkaynak değişim tablosu"}


def _val(co, code, label):
    w = co.wide
    if code in w.index and label in w.columns:
        v = w.at[code, label]
        if v == v:
            return float(v) * C.DISPLAY_SIGN.get(code, 1)
    return None


def build(co, stmt: str, periods: list[Period], mode: str = "Tutar", hide_empty: bool = True,
          max_level: int = 9) -> tuple[pd.DataFrame, dict]:
    """Döner: (tablo, sütun notları). Tablo: Kod, Kalem, Düzey, Tür + dönem sütunları (float ya da None)."""
    layout = C.LAYOUTS[stmt]
    labels = [p.label for p in periods]
    notes = {}
    if mode.startswith("Yatay"):
        for p in periods:
            notes[p.label] = comparability(p, p.prior_comparable(), co.issues, set(co.period_labels))
    base_code = "1BL" if stmt == "BS" else "3C"
    rows = []
    for code, level, kind, label in layout:
        if level > max_level:
            continue
        rec = {"Kod": code or "", "Kalem": label, "Düzey": level, "Tür": kind}
        vals = []
        for p in periods:
            if code is None:
                v = None
            elif mode == "Tutar":
                v = _val(co, code, p.label)
            elif mode == "Dikey (%)":
                if stmt == "MEMO":
                    v = None
                else:
                    a, b = _val(co, code, p.label), _val(co, base_code, p.label)
                    v = a / b if a is not None and b not in (None, 0) else None
            else:
                prev = p.prior_comparable()
                a, b = _val(co, code, p.label), _val(co, code, prev.label)
                diff, pc, _ = safe_change(a, b)
                comp = notes[p.label]
                if mode == "Yatay (tutar)":
                    v = diff if comp in COMPARABLE_AMOUNTS else None
                else:
                    v = pc if comp in COMPARABLE_AMOUNTS else None
            rec[p.label] = v
            vals.append(v)
        if hide_empty and kind in ("line", "memo") and all(x in (None, 0) or x != x for x in vals):
            continue
        rows.append(rec)
    return pd.DataFrame(rows), notes


def row_detail(co, code: str, periods: list[Period]) -> dict:
    """Satır ayrıntısı: kaynak adı, standart anahtar, formül/kimlik, alt kalemler ve dönem değerleri (köken bilgisiyle)."""
    f = co.facts[co.facts["code"] == code]
    out = {
        "kod": code, "etiket": C.LABEL.get(code, code),
        "kaynak_adı": None if f.empty else f["item_source"].iloc[0],
        "standart_anahtar": C.CODE_STD.get(code),
        "tür": "türetilmiş" if code.startswith("D_") else "raporlanan",
        "formül": C.DERIVED[code][0] if code in C.DERIVED else (
            f"{C.LABEL.get(code, code)} = " + " + ".join(f"{C.LABEL.get(k, k)} ({k})" for k in C.IDENTITIES[code])
            if code in C.IDENTITIES else "Kaynakta raporlanan değer"),
        "işaret": "Kaynakta pozitif = gider; tabloda negatif gösterilir" if code in C.DISPLAY_SIGN else
                  "Kaynaktaki işaretle (giderler negatif)",
        "alt_kalemler": C.IDENTITIES.get(code) or C.CHILDREN.get(code, []),
    }
    keep = ["period", "value", "basis", "price_basis", "value_type", "source", "fetched_at", "scope"]
    out["değerler"] = f[f["period"].isin([p.label for p in periods])][keep].reset_index(drop=True)
    return out


def equity_statement(co, years: list[Period]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Özkaynak değişim tablosu (kaynakta doğrudan raporlanmaz; bilanço bileşenleri ve nakit akışından KURULUR).
    1) Bileşen bakiyeleri: yıl sonları itibarıyla özkaynak kalemleri.
    2) Hareket mutabakatı: açılış (önceki yıl sonu 2N) + dönem kârı (3L) + temettü ödemeleri (4CBB)
       + sermaye artırımı (4CBC) + diğer hareketler (TÜRETİLMİŞ: kalan fark) = kapanış (2N).
       'Diğer' satırı; diğer kapsamlı gelir, azınlık işlemleri, geri alınan paylar ve TMS 29 döneminde açılış
       bakiyesinin farklı fiyat bazında olmasından doğan yeniden ifade farkını içerir.
    """
    comp_rows = [c for c, lvl, kind, _ in C.BS if c and c.startswith(("2O", "2N", "D_EQ"))] + ["2N"]
    comp_rows = list(dict.fromkeys(["2OA", "2OC", "2OCA", "2OCB", "2OCC", "2OCD", "2OCE", "2OCF", "2OD", "D_EQ_RESID",
                                    "2O", "2ODA", "2N"]))
    bal = pd.DataFrame({"Kalem": [C.LABEL.get(c, c) for c in comp_rows], "Kod": comp_rows})
    for p in years:
        bal[p.label] = [_val(co, c, p.label) for c in comp_rows]
    bal = bal[~((bal["Kod"].str.startswith(("2OC", "2OD", "D_EQ"))) & (bal[[p.label for p in years]].fillna(0) == 0).all(axis=1))]

    mv = {"Kalem": ["Açılış özkaynakları (önceki yıl sonu)", "Dönem kârı / zararı (3L)", "Temettü ödemeleri (4CBB)",
                    "Sermaye artırımı (4CBC)", "Diğer hareketler (türetilmiş fark)", "Kapanış özkaynakları (2N)"]}
    for p in years:
        op = _val(co, "2N", p.prior_year_end().label) if p.prior_year_end().label in co.period_labels else None
        cl, ni = _val(co, "2N", p.label), _val(co, "3L", p.label)
        dv, ci = _val(co, "4CBB", p.label) or 0.0, _val(co, "4CBC", p.label) or 0.0
        other = None if None in (op, cl, ni) else cl - op - ni - dv - ci
        mv[p.label] = [op, ni, dv, ci, other, cl]
    return bal, pd.DataFrame(mv)
