"""
Veri sağlayıcı: İş Yatırım mali tabloları, isyatirimhisse kütüphanesi üzerinden.

Kapsam ve koşullar (README'de ayrıntılı):
- Resmî kaynak değildir; KAP finansal raporları birincil kaynaktır. İş Yatırım verisi kişisel kullanım içindir,
  yeniden dağıtılmamalıdır. Uygulama yalnız localhost'ta çalışır, veri yerel önbellekte tutulur.
- financial_group="1": XI_29 (TFRS, reel sektör) formatı. Banka/sigorta formatları kapsam dışıdır.
- Konsolide/solo bilgisi kaynakta belirtilmez; bir şirket için tek seri çekildiğinden seriler karışmaz.
- Kaynak, zaman aşımında bazı yılları sessizce atlayabilir: eksik yıllar tek tek yeniden istenir,
  hâlâ eksik dönem varsa modele "gap" olarak işlenir ve arayüzde gösterilir.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "app" / ".cache"
LEGACY_RAW = ROOT / "data" / "raw"          # SQL hattının ham CSV'leri (aynı kaynak, aynı biçim)
START_YEAR = 2019
FIN_GROUP = "1"
META = ["FINANCIAL_ITEM_CODE", "FINANCIAL_ITEM_NAME_TR", "FINANCIAL_ITEM_NAME_EN", "SYMBOL"]

SOURCE_NAME = "İş Yatırım mali tabloları (isyatirimhisse 5.0.1, XI_29 formatı)"
SOURCE_NOTE = ("Resmî kaynak değildir. Birincil kaynak KAP finansal raporlarıdır; kritik rakamları KAP'ta doğrulayın. "
               "Kişisel kullanım içindir.")


class FetchError(Exception):
    pass


@dataclass
class RawData:
    ticker: str
    frame: pd.DataFrame        # geniş: kalem x dönem
    fetched_at: _dt.datetime   # önbellek dosyasının yazıldığı an
    origin: str                # "önbellek", "SQL projesi ham verisi" ya da "canlı"


def kap_url(ticker: str) -> str:
    return "https://www.kap.org.tr/tr/bildirim-sorgu"


def isyatirim_url(ticker: str) -> str:
    return f"https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/sirket-karti.aspx?hisse={ticker}"


def period_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c not in META and "/" in str(c)]


def _sort_cols(df: pd.DataFrame) -> pd.DataFrame:
    pcs = sorted(period_cols(df), key=lambda c: tuple(map(int, str(c).split("/"))))
    return df[[c for c in df.columns if c in META] + pcs]


def _validate_ticker(ticker: str) -> str:
    t = (ticker or "").strip().upper()
    if not t.isalnum() or not 3 <= len(t) <= 6:
        raise FetchError("Geçerli bir BIST kodu girin (ör. BIMAS, ULKER).")
    return t


def load(ticker: str, refresh: bool = False, end_year: int | None = None) -> RawData:
    t = _validate_ticker(ticker)
    cache = CACHE_DIR / f"{t}.csv"
    if not refresh:
        for p, origin in ((cache, "önbellek"), (LEGACY_RAW / f"{t}.csv", "SQL projesi ham verisi")):
            if p.exists():
                return RawData(t, _sort_cols(pd.read_csv(p, encoding="utf-8-sig")),
                               _dt.datetime.fromtimestamp(p.stat().st_mtime), origin)
    df = _fetch_live(t, end_year or _dt.date.today().year)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(cache, index=False, encoding="utf-8-sig")
    return RawData(t, df, _dt.datetime.now(), "canlı")


def _fetch_live(t: str, end_year: int) -> pd.DataFrame:
    try:
        from isyatirimhisse import fetch_financials
    except ImportError as e:  # pragma: no cover
        raise FetchError("isyatirimhisse kurulu değil: pip install -r requirements.txt") from e

    def get(y0, y1):
        try:
            d = fetch_financials(symbols=t, start_year=y0, end_year=y1, exchange="TRY", financial_group=FIN_GROUP)
        except ValueError:      # kütüphane: "No financial data was fetched for any symbol"
            return None
        except Exception as e:  # ağ hatası
            raise FetchError(f"{t} için veri çekilemedi ({type(e).__name__}). Bağlantıyı kontrol edip tekrar deneyin.") from e
        return d if d is not None and len(d) else None

    df = get(START_YEAR, end_year)
    if df is None:
        raise FetchError(f"{t} için XI_29 formatında mali tablo bulunamadı. Kod yanlış olabilir ya da şirket banka, "
                         "sigorta veya diğer finansal kuruluş formatında raporluyor; bu uygulama reel sektör "
                         "şirketleri için tasarlandı.")
    for _ in range(3):  # eksik yılları tek tek yeniden dene
        cols = period_cols(df)
        counts = {}
        for c in cols:
            y = int(str(c).split("/")[0])
            counts[y] = counts.get(y, 0) + 1
        missing = [y for y in range(START_YEAR, end_year) if counts.get(y, 0) < 4]
        if end_year not in counts:
            missing.append(end_year)
        if not missing:
            break
        for y in missing:
            part = get(y, y)
            if part is None:
                continue
            new = [c for c in period_cols(part) if c not in df.columns]
            if new:
                df = df.merge(part[["FINANCIAL_ITEM_CODE"] + new], on="FINANCIAL_ITEM_CODE", how="left")
    return _sort_cols(df)
