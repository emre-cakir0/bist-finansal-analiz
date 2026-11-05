"""
bistfa - BIST Finansal Analiz çekirdeği

Katmanlar (bağımlılık yönü yukarıdan aşağıya):
    source.py     veri sağlayıcı (İş Yatırım / isyatirimhisse), önbellek, eksik yıl yeniden denemesi
    catalog.py    147 kaynak kalemin kataloğu: tablo, hiyerarşi, standart anahtar, işaret kuralı
    model.py      uzun formatlı fact modeli (her değer köken bilgisiyle)
    periods.py    dönem kavramları ve karşılaştırılabilirlik (YTD/yıllık, TMS 29, baz kırılması)
    statements.py gelir tablosu, bilanço, nakit akış, özkaynak değişim tablosu + yatay/dikey analiz
    metrics.py    tek yerde tanımlı oran/metrik kaydı (formül, bileşen, durum ve neden)
    quality.py    veri kalitesi testleri ve kaynak sorunu tespiti
    risk.py       Altman Z'' (uygunluk kontrollü) ve risk göstergeleri
    peers.py      benzer şirket grupları ve karşılaştırma uyumluluğu
    findings.py   kurala dayalı bulgular (olumlu gelişmeler / izlenecek konular) ve dayanakları
    report.py     Excel ve HTML (yazdırılabilir) rapor çıktısı
    company.py    hepsini birleştiren Company nesnesi
"""
__version__ = "2.0.0"
