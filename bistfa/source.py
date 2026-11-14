"""
Veri sağlayıcı: İş Yatırım mali tabloları, isyatirimhisse kütüphanesi üzerinden.

Kapsam ve koşullar (README'de ayrıntılı):
- Resmî kaynak değildir; KAP finansal raporları birincil kaynaktır. İş Yatırım verisi kişisel kullanım içindir,
  yeniden dağıtılmamalıdır. Uygulama yalnız localhost'ta çalışır, veri yerel önbellekte tutulur.
- financial_group="1": XI_29 (TFRS, reel sektör) formatı. Banka/sigorta formatları kapsam dışıdır.
- Konsolide/solo bilgisi kaynakta belirtilmez; bir şirket için tek seri çekildiğinden seriler karışmaz.
- Kütüphane her yıl için tek istek atar ve zaman aşımında yalnız uyarı yazıp o yılı atlar. Kaynakta her kolon bir
  sonraki raporun fiyat düzeyindedir (bkz. pricebasis.py), bu yüzden eksik bir çeyrek yalnız boşluk değil, önceki
  kolonların fiyat düzeyinin yanlış belirlenmesi demektir. Bu nedenle yıllar tek tek çekilir, uyarı yakalanır ve
  yeniden denenir; yine alınamayan yıl varsa yükleme durdurulur ve eksik veri önbelleğe yazılmaz.
- Önbellek: eksiksiz çekimden sonra yanına <KOD>.meta.json yazılır. Bu dosyası olmayan (eski sürüm ya da eksik)
  önbellek yeniden çekilir; eksiksiz önbellek MAX_AGE'den eskiyse yenilenir, yenileme başarısızsa eski eksiksiz
  kopya kullanılır. BISTFA_OFFLINE=1 iken (testler) önbellek olduğu gibi okunur, ağa çıkılmaz.
"""
from __future__ import annotations

import contextlib
import datetime as _dt
import io
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "app" / ".cache"
LEGACY_RAW = ROOT / "data" / "raw"          # SQL hattının ham CSV'leri (aynı kaynak, aynı biçim)
START_YEAR = 2019
FIN_GROUP = "1"
CACHE_VERSION = 2
MAX_AGE = _dt.timedelta(days=7)
RETRIES = 4
TIMEOUT = 30          # sn; kütüphanenin sabit 10 sn'si, ~10,2 sn'de gelen (bu sunucuda sık görülen) yanıtları kesiyor
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


def _meta_path(t: str) -> Path:
    return CACHE_DIR / f"{t}.meta.json"


def _read_meta(t: str) -> dict | None:
    try:
        m = json.loads(_meta_path(t).read_text(encoding="utf-8"))
        return m if m.get("version") == CACHE_VERSION and m.get("complete") else None
    except (OSError, ValueError):
        return None


def load(ticker: str, refresh: bool = False, end_year: int | None = None) -> RawData:
    t = _validate_ticker(ticker)
    cache = CACHE_DIR / f"{t}.csv"
    cached = None
    if cache.exists():
        meta = _read_meta(t)
        when = (_dt.datetime.fromisoformat(meta["fetched_at"]) if meta
                else _dt.datetime.fromtimestamp(cache.stat().st_mtime))
        cached = RawData(t, _sort_cols(pd.read_csv(cache, encoding="utf-8-sig")), when, "önbellek")
        if os.environ.get("BISTFA_OFFLINE") == "1":
            return cached
        if meta and not refresh and _dt.datetime.now() - when < MAX_AGE:
            return cached
        if not meta:
            cached = None          # eski sürüm ya da eksik çekim: güvenilmez, yeniden çek
    elif not refresh and (LEGACY_RAW / f"{t}.csv").exists():
        p = LEGACY_RAW / f"{t}.csv"
        return RawData(t, _sort_cols(pd.read_csv(p, encoding="utf-8-sig")),
                       _dt.datetime.fromtimestamp(p.stat().st_mtime), "SQL projesi ham verisi")
    try:
        df = _fetch_live(t, end_year or _dt.date.today().year)
    except FetchError:
        if cached is not None and not refresh:
            cached.origin = "önbellek (yenilenemedi)"
            return cached
        raise
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(cache, index=False, encoding="utf-8-sig")
    now = _dt.datetime.now()
    _meta_path(t).write_text(json.dumps({"version": CACHE_VERSION, "complete": True, "fetched_at": now.isoformat(
        timespec="seconds"), "columns": period_cols(df)}, ensure_ascii=False), encoding="utf-8")
    return RawData(t, df, now, "canlı")


def _fetch_year(t: str, y: int, fetch, sleep=time.sleep):
    """Tek yıl (4 çeyrek, tek istek). None = o yıl için kaynakta veri yok. Zaman aşımı/ağ hatası yeniden denenir;
    kütüphane hatayı yalnız ekrana yazdığından çıktısı yakalanır."""
    for attempt in range(RETRIES):
        buf, d, err = io.StringIO(), None, None
        with contextlib.redirect_stdout(buf):
            try:
                d = fetch(symbols=t, start_year=y, end_year=y, exchange="TRY", financial_group=FIN_GROUP)
            except ValueError:      # kütüphane: "No financial data was fetched for any symbol"
                d = None
            except Exception as e:  # ağ hatası
                err = e
        if err is None and "Could not fetch" not in buf.getvalue():
            return d if d is not None and len(d) else None
        if attempt < RETRIES - 1:
            sleep(1.5 * (attempt + 1))
    raise FetchError(f"İş Yatırım {t} için {y} yılı verisine yanıt vermedi (zaman aşımı). Eksik veriyle yanlış "
                     "rakam göstermemek için yükleme durduruldu; birkaç dakika sonra tekrar deneyin.")


def _library_fetch():
    """isyatirimhisse.fetch_financials; kütüphane modülünün içindeki requests.get çağrısına daha uzun zaman aşımı verilir
    (yalnız o modülde; uygulamanın geri kalanı etkilenmez)."""
    import importlib
    import types
    try:
        ff = importlib.import_module("isyatirimhisse.FetchFinancials")
    except ImportError as e:  # pragma: no cover
        raise FetchError("isyatirimhisse kurulu değil: pip install -r requirements.txt") from e
    if not getattr(ff.requests, "_bistfa_patched", False):
        real = ff.requests

        def get(url, *args, timeout=None, **kw):
            return real.get(url, *args, timeout=max(timeout or 0, TIMEOUT), **kw)
        ff.requests = types.SimpleNamespace(get=get, _bistfa_patched=True)
    return ff.fetch_financials


def _fetch_live(t: str, end_year: int, fetch=None, sleep=time.sleep) -> pd.DataFrame:
    if fetch is None:
        fetch = _library_fetch()
    df = None
    for y in range(START_YEAR, end_year + 1):
        part = _fetch_year(t, y, fetch, sleep)
        if part is None:
            continue
        if df is None:
            df = part
            continue
        new = [c for c in period_cols(part) if c not in df.columns]
        if new:
            df = df.merge(part[["FINANCIAL_ITEM_CODE"] + new], on="FINANCIAL_ITEM_CODE", how="left")
    if df is None:
        raise FetchError(f"{t} için XI_29 formatında mali tablo bulunamadı. Kod yanlış olabilir ya da şirket banka, "
                         "sigorta veya diğer finansal kuruluş formatında raporluyor; bu uygulama reel sektör "
                         "şirketleri için tasarlandı.")
    return _sort_cols(df)   # istekler hatasız döndükten sonra kalan boşluklar kaynağındır; model "gap" olarak işler
