"""
Altman Z''-skoru (Altman 1995, gelişmekte olan piyasalar / imalat dışı şirketler varyantı, defter değeriyle).

    Z'' = 6,56·X1 + 3,26·X2 + 6,72·X3 + 1,05·X4
    X1 = net işletme sermayesi / toplam varlıklar
    X2 = birikmiş kârlar / toplam varlıklar     (geçmiş yıllar kâr/zararları 2OCE + dönem net kârı 2OCF)
    X3 = EBIT / toplam varlıklar                 (EBIT = finansman gideri öncesi faaliyet kârı 3HACA, yıllık)
    X4 = özkaynakların defter değeri / toplam yükümlülükler
    Altman'ın özgün bölgeleri: Z'' > 2,60 "güvenli", 1,10–2,60 "gri", < 1,10 "sıkıntı".

UYGUNLUK: yalnız finansal olmayan şirketler (XI_29 formatı), yıllık (12 aylık) dönem, gereken tüm kalemler mevcut.
SINIRLAR: Türkiye ve TMS 29 için yeniden kalibre edilmemiştir; TMS 29 döneminde 'geçmiş yıllar kâr/zararları'
yeniden ifade farklarını içerir. Bir iflas olasılığı ya da yatırım sinyali DEĞİLDİR; finansal yapıyı özetleyen
tarihsel bir göstergedir.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .periods import Period

COEF = {"X1": 6.56, "X2": 3.26, "X3": 6.72, "X4": 1.05}


@dataclass
class Altman:
    shown: bool
    reason: str
    z: float | None = None
    zone: str | None = None
    parts: dict = field(default_factory=dict)
    caveats: list = field(default_factory=list)


def altman_z2(co, P: Period) -> Altman:
    if not P.is_annual:
        return Altman(False, "Yalnız yıllık (12 aylık) dönemlerde hesaplanır; seçili dönem ara dönem.")
    if co.financial_sector_flags(P):
        return Altman(False, "Finans sektörü faaliyet kalemleri raporlanmış; model finansal kuruluşlara uygun değil.")
    need = {"1A": "Dönen varlıklar", "2A": "KV yükümlülükler", "1BL": "Toplam varlıklar", "2OCE": "Geçmiş yıllar kâr/zararları",
            "3HACA": "EBIT", "2N": "Özkaynaklar", "2B": "UV yükümlülükler"}
    v = {}
    for k, name in need.items():
        x = co.value(k, P.label)
        if x is None:
            return Altman(False, f"Gerekli kalem eksik: {name} ({k}).")
        v[k] = x
    cy = co.value("2OCF", P.label) or 0.0
    ta, tl = v["1BL"], v["2A"] + v["2B"]
    if ta <= 0 or tl <= 0:
        return Altman(False, "Toplam varlık ya da toplam yükümlülük sıfır.")
    X = {"X1": (v["1A"] - v["2A"]) / ta, "X2": (v["2OCE"] + cy) / ta, "X3": v["3HACA"] / ta, "X4": v["2N"] / tl}
    z = sum(COEF[k] * X[k] for k in X)
    zone = "güvenli bölge (> 2,60)" if z > 2.6 else ("gri bölge (1,10–2,60)" if z >= 1.1 else "sıkıntı bölgesi (< 1,10)")
    cav = ["Türkiye ve TMS 29 için yeniden kalibre edilmemiş özgün eşikler kullanıldı.",
           "İflas olasılığı ya da yatırım sinyali değildir."]
    if P.tms29:
        cav.insert(0, "TMS 29 döneminde birikmiş kârlar (X2) yeniden ifade farklarını içerir; X2 yorumu sınırlıdır.")
    parts = {k: {"değer": X[k], "katsayı": COEF[k], "katkı": COEF[k] * X[k]} for k in X}
    return Altman(True, "", z, zone, parts, cav)
