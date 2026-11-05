"""
Benzer şirket grupları ve karşılaştırma uyumluluğu.

Kaynak (isyatirimhisse) sektör sınıflandırması VERMEZ. Aşağıdaki gruplar elle hazırlanmıştır, resmî bir
sınıflandırma değildir ve eksik olabilir; kullanıcı arayüzde grubu değiştirebilir veya kod ekleyebilir.
Banka, sigorta ve diğer finansal kuruluşlar bu uygulamanın veri formatında (XI_29) bulunmaz ve
reel sektör oranlarıyla karşılaştırılmaz.
"""
from __future__ import annotations

NAMES = {
    "BIMAS": "BİM", "MGROS": "Migros", "SOKM": "Şok Marketler", "CRFSA": "CarrefourSA",
    "ULKER": "Ülker", "TATGD": "Tat Gıda", "PNSUT": "Pınar Süt", "BANVT": "Banvit", "KNFRT": "Konfrut Gıda",
    "AEFES": "Anadolu Efes", "CCOLA": "Coca-Cola İçecek",
    "FROTO": "Ford Otosan", "TOASO": "Tofaş", "DOAS": "Doğuş Otomotiv",
    "EREGL": "Ereğli Demir Çelik", "KRDMD": "Kardemir (D)", "ISDMR": "İskenderun Demir Çelik",
    "ARCLK": "Arçelik", "VESBE": "Vestel Beyaz Eşya",
    "TCELL": "Turkcell", "TTKOM": "Türk Telekom",
    "THYAO": "Türk Hava Yolları", "PGSUS": "Pegasus",
    "TUPRS": "Tüpraş", "PETKM": "Petkim", "SISE": "Şişecam", "ASELS": "Aselsan",
}

GROUPS = {
    "Gıda perakendesi": ["BIMAS", "MGROS", "SOKM", "CRFSA"],
    "Gıda üretimi": ["ULKER", "TATGD", "PNSUT", "BANVT"],
    "İçecek": ["AEFES", "CCOLA"],
    "Otomotiv": ["FROTO", "TOASO", "DOAS"],
    "Demir-çelik": ["EREGL", "KRDMD", "ISDMR"],
    "Dayanıklı tüketim": ["ARCLK", "VESBE"],
    "Telekomünikasyon": ["TCELL", "TTKOM"],
    "Havayolu": ["THYAO", "PGSUS"],
}


def name(t: str) -> str:
    return NAMES.get(t, t)


def group_of(t: str) -> str | None:
    return next((g for g, ts in GROUPS.items() if t in ts), None)


def compatibility(base, other, period_label: str) -> tuple[bool, list[str]]:
    """Karşılaştırma koşulları: aynı dönem mevcut, aynı dönem uzunluğu, aynı çerçeve ve fiyat bazı, finansal kuruluş değil."""
    issues = []
    if period_label not in other.period_labels:
        issues.append(f"{period_label} dönemi yok (son dönem {other.period_labels[-1]})")
    if other.financial_sector_flags(other.period(period_label) if period_label in other.period_labels else other.periods[-1]):
        issues.append("finans sektörü kalemleri raporlanmış; reel sektör oranlarıyla karşılaştırılmaz")
    if period_label in base.issues or period_label in other.issues:
        issues.append("kaynakta baz kırılması: TL tutarlar karşılaştırılamaz, oranlar karşılaştırılabilir")
    ok = not any(x.startswith((period_label + " dönemi yok", "finans")) for x in issues)
    return ok, issues
