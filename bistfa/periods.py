"""
Dönem kavramları ve karşılaştırılabilirlik.

- Bilanço kalemleri bir TARİHTEKİ durumdur; gelir tablosu ve nakit akışı yılbaşından o tarihe kadarki AKIŞTIR (YTD).
- Karşılaştırma yalnız aynı uzunluktaki dönemler arasında yapılır: 2025/9 (9 aylık) ancak 2024/9 ile karşılaştırılır.
- TMS 29 (SPK 28.12.2023, 81/1820): 31.12.2023 ve sonrasında biten dönemlerde her kolon kendi dönem sonu satın alma
  gücüyle ifade edilir. Kaynak verideki önceki kolonlar yeniden ifade edilmediği için dönemler arası TL değişimi
  NOMİNALDİR, reel büyüme değildir.
"""
from __future__ import annotations

import calendar
import datetime as _dt
from dataclasses import dataclass

TMS29_START = _dt.date(2023, 12, 31)


@dataclass(frozen=True)
class Period:
    label: str          # "2025/12"
    year: int
    month: int          # dönem sonu ayı = YTD ay sayısı (takvim yılı sonu varsayımı)

    @property
    def end(self) -> _dt.date:
        return _dt.date(self.year, self.month, calendar.monthrange(self.year, self.month)[1])

    @property
    def start(self) -> _dt.date:
        return _dt.date(self.year, 1, 1)

    @property
    def months(self) -> int:
        return self.month

    @property
    def is_annual(self) -> bool:
        return self.month == 12

    @property
    def tms29(self) -> bool:
        return self.end >= TMS29_START

    @property
    def key(self) -> int:
        return self.year * 100 + self.month

    @property
    def kind(self) -> str:
        return "yıllık (12 ay)" if self.is_annual else f"{self.month} aylık (YTD)"

    @property
    def price_basis(self) -> str:
        return (f"TMS 29: {self.end:%d.%m.%Y} satın alma gücü" if self.tms29 else "TMS 29 öncesi: nominal TL")

    def prior_comparable(self) -> "Period":
        return Period(f"{self.year - 1}/{self.month}", self.year - 1, self.month)

    def prior_year_end(self) -> "Period":
        return Period(f"{self.year - 1}/12", self.year - 1, 12)

    def __str__(self):
        return self.label


def parse(label: str) -> Period:
    y, m = map(int, str(label).split("/"))
    return Period(f"{y}/{m}", y, m)


# Karşılaştırılabilirlik kodları
NA, OK_NOMINAL, NOMINAL_TMS29, TMS29_TRANSITION, BASE_BREAK = "NA", "NOMINAL", "NOMINAL_TMS29", "TMS29_GECIS", "BASE_BREAK"
COMP_TEXT = {
    NA: "Karşılaştırma dönemi yok",
    OK_NOMINAL: "Nominal karşılaştırma (TMS 29 öncesi)",
    NOMINAL_TMS29: "Nominal: her kolon kendi dönem sonu fiyatıyla; reel değişim değildir",
    TMS29_TRANSITION: "TMS 29 geçişi: önceki dönem nominal, cari dönem enflasyona göre düzeltilmiş; karşılaştırılamaz",
    BASE_BREAK: "Kaynakta baz kırılması: karşılaştırılamaz",
}
COMPARABLE_AMOUNTS = {OK_NOMINAL, NOMINAL_TMS29}   # TL tutar değişimi gösterilebilir (nominal etiketiyle)


def comparability(cur: Period, prev: Period | None, issues: dict, available: set) -> str:
    if prev is None or prev.label not in available:
        return NA
    if cur.label in issues or prev.label in issues:
        return BASE_BREAK
    if cur.tms29 and not prev.tms29:
        return TMS29_TRANSITION
    return NOMINAL_TMS29 if cur.tms29 else OK_NOMINAL


def safe_change(cur, prev):
    """(tutar değişimi, yüzde değişim, not). Yanıltıcı yüzde üretmez."""
    if cur is None or prev is None or cur != cur or prev != prev:
        return None, None, "veri yok"
    diff = cur - prev
    if prev == 0:
        return diff, None, "sıfır baz: yüzde anlamsız"
    if (prev < 0 < cur) or (prev > 0 > cur):
        return diff, None, "işaret değişti (kâr↔zarar): yüzde anlamsız"
    if prev < 0 and cur < 0:
        return diff, None, ("negatif tutar küçüldü" if cur > prev else "negatif tutar büyüdü") + ": yüzde anlamsız"
    return diff, diff / abs(prev), ""
