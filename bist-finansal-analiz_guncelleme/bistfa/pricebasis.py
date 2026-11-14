"""
Fiyat düzeyi (satın alma gücü) dönüşümü.

BULGU (şirket raporlarıyla doğrulandı, bkz. docs/APP_AUDIT.md bölüm 10): İş Yatırım kaynağındaki bir dönem kolonu,
o dönemin ilk yayımlanan rakamı değil, o dönemi KARŞILAŞTIRMA olarak içeren en son TMS 29 raporundaki rakamdır:

- Yıllık kolon Y/12  → (Y+1) yılında yayımlanmış en son raporun dönem sonu fiyatıyla
  (ör. 2024/12 kolonu Aralık 2025 fiyatıyla; 2025/12 kolonu, veri çekildiğinde son rapor 2026/6 ise Haziran 2026 fiyatıyla).
- Ara dönem kolonu Y/m → (Y+1)/m raporu yayımlandıysa onun dönem sonu fiyatıyla; yayımlanmadıysa kendi dönem sonu fiyatıyla.
- TMS 29 öncesi olup sonradan yeniden düzenlenmemiş kolonlar (yıllık ≤ 2021, ara dönem ≤ 2022/9) nominal TL'dir.

Bu modül her kolonun kaynak fiyat düzeyini belirler ve TÜFE ile iki görünüme çevirir:
- "common"    : TMS 29 kapsamındaki tüm kolonlar tek bir hedef tarihin (son yıl sonu) fiyatıyla → dönemler karşılaştırılabilir,
                büyüme REEL.
- "published" : her dönem kendi dönem sonu fiyatıyla (şirketin o dönem açıkladığı rakam).
- "source"    : kaynaktan geldiği gibi (SQL hattıyla birebirlik testi için).
"""
from __future__ import annotations

import datetime as _dt

from .periods import Period, TMS29_START, parse

# TÜİK TÜFE aylık % değişim (kaynak: TCMB "Tüketici Fiyatları" tablosu). Yeni aylar açıklandıkça buraya eklenir.
MONTHLY = {
    (2023, 1): 6.65, (2023, 2): 3.15, (2023, 3): 2.29, (2023, 4): 2.39, (2023, 5): 0.04, (2023, 6): 3.92,
    (2023, 7): 9.49, (2023, 8): 9.09, (2023, 9): 4.75, (2023, 10): 3.43, (2023, 11): 3.28, (2023, 12): 2.93,
    (2024, 1): 6.70, (2024, 2): 4.53, (2024, 3): 3.16, (2024, 4): 3.18, (2024, 5): 3.37, (2024, 6): 1.64,
    (2024, 7): 3.23, (2024, 8): 2.47, (2024, 9): 2.97, (2024, 10): 2.88, (2024, 11): 2.24, (2024, 12): 1.03,
    (2025, 1): 5.03, (2025, 2): 2.27, (2025, 3): 2.46, (2025, 4): 3.00, (2025, 5): 1.53, (2025, 6): 1.37,
    (2025, 7): 2.06, (2025, 8): 2.04, (2025, 9): 3.23, (2025, 10): 2.55, (2025, 11): 0.87, (2025, 12): 0.89,
    (2026, 1): 4.84, (2026, 2): 2.96, (2026, 3): 1.94, (2026, 4): 4.18, (2026, 5): 1.71, (2026, 6): 0.99,
    (2026, 7): 1.78, (2026, 8): 1.84, (2026, 9): 1.84, (2026, 10): 2.58,
}
# Aralık ayı yıllık % değişim: aylık oranların yuvarlama birikimini düzeltmek için çıpa
ANNUAL_DEC = {2023: 64.77, 2024: 44.38, 2025: 30.89}

# SQL projesinin ham CSV'leri 2025/12'de biter; çekildikleri tarihte (05.11.2026) yayımlanmış son rapor.
# Kanıt: kaynak 2025/12 hasılatı / açıklanan 2025 hasılatı = TÜFE(son rapor) / TÜFE(Ara 2025)
#   BİM 849,1/721,0 = Migros 486,1/412,7 = Şok 328,3/278,8 = 1,1777 (Haz 2026); CarrefourSA 103,9/83,6 = 1,2432 (Eyl 2026).
SNAPSHOT_LATEST = {"BIMAS": "2026/6", "MGROS": "2026/6", "SOKM": "2026/6", "CRFSA": "2026/9"}


def _build_index() -> dict:
    idx = {(2022, 12): 100.0}
    for y in sorted({k[0] for k in MONTHLY}):
        months = [m for m in range(1, 13) if (y, m) in MONTHLY]
        chain, level = [], 1.0
        for m in months:
            level *= 1 + MONTHLY[(y, m)] / 100
            chain.append(level)
        adj = 1.0
        if len(months) == 12 and y in ANNUAL_DEC:      # yıl sonunu yıllık orana oturt, farkı aylara eşit dağıt
            adj = ((1 + ANNUAL_DEC[y] / 100) / chain[-1]) ** (1 / 12)
        base = idx[(y - 1, 12)]
        for i, m in enumerate(months):
            idx[(y, m)] = base * chain[i] * adj ** (i + 1)
        if (y, 12) not in idx:
            break
    return idx


INDEX = _build_index()


def cpi(d: _dt.date):
    return INDEX.get((d.year, d.month))


def applies_tms29(total_assets: dict) -> bool:
    """Şirket enflasyon muhasebesi uyguluyor mu? Uygulayanlarda kaynak 2022/12 kolonu yeniden düzenlenmiştir ve toplam
    varlık 2022/9'a göre ~2 katına çıkar; uygulamayanlarda (ör. işlevsel para birimi USD/EUR olanlar) sıçrama olmaz.
    2022 dönemleri yoksa uyguladığı varsayılır."""
    a, b = total_assets.get("2022/9"), total_assets.get("2022/12")
    if a and b and a > 0 and b > 0:
        return b / a > 1.5
    return True


def source_basis(P: Period, latest_key: int, stock: bool = False):
    """Kaynak kolonunun ifade edildiği fiyat düzeyi tarihi; None = nominal (yeniden düzenlenmemiş).
    stock=True bilanço kalemleri içindir: ara dönem raporları karşılaştırma bilançosu olarak yalnız önceki yıl sonunu
    verdiğinden ara dönem bilanço kolonları yeniden düzenlenmez (kendi dönem sonu fiyatında kalır)."""
    if P.is_annual:
        cands = [parse(f"{P.year + 1}/{m}") for m in (3, 6, 9, 12)]
        cands = [r for r in cands if r.key <= latest_key and r.end >= TMS29_START]
        if cands:
            return cands[-1].end
    elif not stock:
        r = parse(f"{P.year + 1}/{P.month}")
        if r.key <= latest_key and r.end >= TMS29_START:
            return r.end
    return P.end if P.end >= TMS29_START else None


MONTHS_TR = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]


def month_label(d: _dt.date) -> str:
    return f"{MONTHS_TR[d.month]} {d.year}"


def _one(p: Period, b, basis: str, target):
    """(çarpan, tür, açıklama, eksik mi) tek bir kolon ve tablo türü için."""
    if b is None:
        return 1.0, "nominal", "TMS 29 öncesi: nominal TL", False
    if basis == "source":
        return 1.0, "own", f"Kaynak kolonu: {month_label(b)} fiyatıyla", False
    want = target if basis == "common" else (p.end if p.end >= TMS29_START else b)
    if cpi(b) is None or cpi(want) is None:
        return 1.0, "own", f"Kaynak kolonu: {month_label(b)} fiyatıyla (TÜFE tablosunda bu ay yok; çevrilemedi)", True
    f = cpi(want) / cpi(b)
    if basis == "common":
        return f, "real", f"{month_label(want)} fiyatıyla", False
    if p.end >= TMS29_START:
        return f, "own", f"Yayımlandığı gibi: {month_label(want)} fiyatıyla", False
    return f, "next", f"Sonraki raporda yeniden düzenlenmiş hâli: {month_label(b)} fiyatıyla (ilk yayımlanan nominal rakam kaynakta yok)", False


def plan(ticker: str, periods: list[Period], basis: str = "common", applies: bool = True) -> dict:
    """Her dönem için akış (gelir tablosu, nakit akışı) ve bilanço çarpanları, tür ve açıklama.
    tür: 'real' (ortak fiyat), 'own' (kendi dönem sonu fiyatı), 'next' (sonraki rapordaki hâli), 'nominal'."""
    assert basis in ("common", "published", "source")
    latest_key = max([p.key for p in periods] + ([parse(SNAPSHOT_LATEST[ticker]).key] if ticker in SNAPSHOT_LATEST else []))
    annual = [p for p in periods if p.is_annual and p.end >= TMS29_START]
    target = (annual[-1] if annual else periods[-1]).end
    out = {"basis": basis, "target": target, "applies": applies, "latest_key": latest_key, "missing": [],
           "factors": {}, "kinds": {}, "text": {}, "factors_bs": {}, "kinds_bs": {}, "text_bs": {}, "source_basis": {}}
    for p in periods:
        if not applies:
            for k in ("factors", "factors_bs"):
                out[k][p.label] = 1.0
            for k in ("kinds", "kinds_bs"):
                out[k][p.label] = "nominal"
            for k in ("text", "text_bs"):
                out[k][p.label] = "Enflasyon muhasebesi uygulanmıyor: nominal TL"
            continue
        bf, bs = source_basis(p, latest_key), source_basis(p, latest_key, stock=True)
        out["source_basis"][p.label] = bf
        f, k, t, m1 = _one(p, bf, basis, target)
        out["factors"][p.label], out["kinds"][p.label], out["text"][p.label] = f, k, t
        f, k, t, m2 = _one(p, bs, basis, target)
        out["factors_bs"][p.label], out["kinds_bs"][p.label], out["text_bs"][p.label] = f, k, t
        if m1 or m2:
            out["missing"].append(p.label)
    return out
