# BIST Finansal Analiz uygulaması v2: denetim, kararlar ve doğrulama

Son güncelleme: 2026-11-13

Bu belge, uygulamayı tam bir mali tablo analiz aracına dönüştürme isteğinin (8 sayfa, köken bilgili veri modeli, kural tabanlı yorum) nasıl ele alındığını kaydeder: mevcut kodun denetimi, tut / yeniden düzenle / yeniden yaz kararları, veri kuralları, bilinçli tanım farkları ve testler.

## 1. Mevcut kodun denetimi ve kararlar

| Parça | Karar | Gerekçe |
|---|---|---|
| Veri bağlantısı (`isyatirimhisse`, yıl yıl yeniden deneme, önbellek) | **Tutuldu**, `bistfa/source.py`'ye taşındı | Çalışıyordu ve eksik yıl sorununu çözüyordu. Önbellek yoksa önce SQL projesinin ham CSV'leri okunur (aynı kaynak, aynı biçim). |
| Baz kırılması tespiti, kalite testleri | **Tutuldu**, `bistfa/quality.py` | SQL testleriyle aynı sonucu veriyordu. Kaynak verisinde doğrulanan 20 toplam kimliği her dönem test edilir. |
| Oran mantığı (`rf_core.py`) | **Yeniden düzenlendi** → `bistfa/metrics.py` | 43 metrik tek bir kayıtta tanımlandı: her sonuç değer, birim, formül, kullanılan kalemler, bakiye bazı ve hesaplanamadıysa nedenini taşır. Ortalama bakiye kuralı eklendi. |
| Veri modeli | **Yeni**: `bistfa/model.py` | İstenen köken alanları için uzun formatlı fact tablosu (aşağıda). |
| Arayüz (`app.py` v1, 5 sekme) | **Yeniden yazıldı**: `app/app.py`, `app/ui.py`, `app/views.py` | 8 sayfa, formül açıklama katmanı ve metrik yanında uyarı gereksinimleri tek sayfalı tasarıma sığmıyordu. |
| v1 dosyaları | Geliştirme klasöründe saklandı, bu depoya alınmadı | Çalışan hesaplamalar silinmez kuralı; v1 hesapları bistfa'ya taşındı. |

Paket katmanları: `source` (ham veri) → `model` (fact tablosu, türetilmiş satırlar) → `quality` (testler, baz kırılması) → `metrics` (oran kaydı) → `company` (tek şirket görünümü, karşılaştırma yöntemi) → `statements`, `findings`, `risk`, `peers`, `report` (sunum için hazır çıktılar). Arayüz hesaplama yapmaz.

## 2. Veri modeli

Her değer (`Company.facts`) şu alanlarla tutulur: şirket kodu, kaynak kalem kodu ve adı, standart anahtar, tablo (IS/BS/CF), dönem, dönem başı ve sonu (bilanço kalemlerinde yalnız tarih), ay sayısı, nitelik (YTD akış / bilanço tarihi), kapsam, para birimi, ölçek, kaynak, alınma zamanı, raporlama çerçevesi, fiyat bazı (TMS 29 öncesi nominal / dönem sonu satın alma gücü) ve raporlanan / türetilmiş ayrımı. Excel çıktısındaki "Veri modeli (uzun)" sayfası ve CSV indirmesi bu tablodur.

Kaynakta olmayan bilgiler açıkça belirtilir, uydurulmaz:
- **Kapsam (solo/konsolide):** kaynak belirtmiyor; tek seri kullanılır, karıştırılmaz.
- **KAP bildirim tarihi:** yok; alınma zamanı gösterilir. KAP bağlantısı genel sorgu sayfasına gider.
- **Sektör:** yok; benzer şirket grupları elle hazırlanmıştır ve arayüzde böyle etiketlenir.
- **Özkaynak değişim tablosu:** kaynakta yok. Bilanço bileşenleri + dönem kârı + temettü + sermaye artırımından **kurulur**. "Diğer hareketler" kalan farktır ve türetilmiş olarak işaretlenir.

## 3. Veri kuralları

- **Dönem uzunluğu:** akışlar YTD'dir. Yatay analiz ve karşılaştırmalar yalnız aynı uzunluktaki önceki dönemle yapılır (2025/9 ↔ 2024/9). Trend grafikleri aynı ay sonlu dönemlerle kurulur.
- **Yıllıklandırma:** getiri, devir hızı ve gün oranlarında ara dönem akışları × 12/ay ile yıllıklandırılır ve kartta belirtilir; mevsimsellik yok sayılır.
- **TMS 29 ve fiyat düzeyi:** kaynak kolonları farklı fiyat düzeylerindedir; `pricebasis` her kolonun düzeyini belirler ve TÜFE ile ortak fiyata (son yıl sonu) ya da yayımlandığı hâle çevirir. Ortak fiyat görünümünde TL değişimleri reeldir. Ayrıntı ve kanıt: bölüm 10.
- **Ortalama bakiye:** ROE, ROA, devir hızı ve gün hesaplarında (açılış + kapanış) / 2, iki bakiye aynı fiyat düzeyindeyse (ortak fiyat görünümünde düzeltilmiş dönemler ya da ikisi de nominal). Aksi halde dönem sonu kullanılır ve sonuçta yazılır. Dönem sonu özkaynak negatifse ROE hesaplanmaz.
- **Yanıltıcı yüzde yok:** sıfır baz, işaret değişimi ve negatif bazda yüzde değişim üretilmez; nedeni gösterilir.
- **Sessiz sıfır yok:** hesaplanamayan her metrik "hesaplanamadı" ve nedeniyle gösterilir; grafiklerde boş noktaların nedeni listelenir.
- **FAVÖK** kaynakta yok; net faaliyet kârı (3H) + amortisman (4CAB) olarak hesaplanır ve her yerde "hesaplanan" etiketi taşır. Hasılatın %1'inden küçükse FAVÖK bazlı oranlar hesaplanmaz.
- **Net borç** yalnız açıkça finansal olan borçlarla (2AA + 2BA) hesaplanır; ticari borçlar ve diğer finansal yükümlülükler katılmaz. Finansal borç/özkaynak ile toplam yükümlülük/özkaynak ayrı gösterilir.
- **Finans sektörü:** banka/sigorta formatındaki şirketler yüklenmez (anlaşılır mesaj). Karşılaştırmada finans sektörü kalemi raporlayan şirketler dışlanır.

## 4. Kaynak verisinde bulunan iki önemli nokta

**3HC işaretli net tutardır.** Kaynakta "finansal giderler" adıyla gelen 3HC satırı aslında net finansman gelir/gideridir: vergi öncesi kâr = EBIT (3HACA) + finansal gelirler (3HB) + 3HC. Bu eşitlik dört perakende şirketinin 112 dönem-şirketinde birebir tutuyor. Negatif değer net gideri gösterir. TMS 29 döneminde parasal kazançlar satırı pozitife çevirebilir: BİM, Migros ve Şok'ta 2025/12'de net gelir. Sonuçlar:
- Saf faiz gideri bu kaynaktan ayrıştırılamaz. Faiz karşılama oranları "net finansman gideri" paydasıyla ve yalnız net gider varken hesaplanır; aksi halde neden yazılır.
- SQL projesi "pozitif = gider" varsaymıştı. `05_analytics.sql` (`ebitda_to_finance_expense`) ve `04_standardize.sql` notu düzeltildi, view'lar yeniden kuruldu. Power BI'daki "EBITDA to Finance Expense" ölçüsü bir sonraki yenilemede doğru değeri alır.

**3HCA ayrı bir kalem değildir.** "Vergi öncesi diğer gelir ve giderler" satırı (3HCA), BİM, Migros ve Şok'ta yatırım faaliyeti gelir/giderlerinin (3HA + 3HAA) birebir tekrarıdır ve zaten EBIT'in içindedir. CarrefourSA'da bu kalemlerin toplamıyla da tutmaz. Tabloda bilgi satırı olarak gösterilir, toplamlara katılmaz. Önceki taslakta "ayrıştırılmamış fark" görünen tutar bu çift saymanın sonucuydu.

## 5. Bilinçli tanım farkları (SQL hattına göre)

| Metrik | SQL hattı | Uygulama | Neden |
|---|---|---|---|
| ROE, DuPont net marj ve özkaynak çarpanı | 3L / 2N | 3Z / 2O (ana ortaklık) | Pay ve payda aynı sahiplik tabanında olmalı |
| ROE, ROA, devir hızı, gün oranları | dönem sonu bakiye | ortalama bakiye (TMS 29 öncesi) | Akış / stok uyumu |
| Faaliyet marjı | esas faaliyet kârı (3DF) | EBIT (3HACA) marjı ayrıca, net faaliyet marjı (3H) ayrıca | Kalem adları ve kapsamı açık |
| Nakit oranı | (nakit + KV finansal yatırım) / KVY | nakit / KVY | İstenen tanım: yalnız nakit |

## 6. Bulgular, risk skoru ve sağlık puanı

- **Bulgular** (`bistfa/findings.py`) kurala dayalıdır. Her biri kuralını ve dayanak dönemi/değerini taşır. Eşikler genel başlangıç değerleridir. Örneğin cari oran < 1, nakit döngüsü negatifse "izlenecek" değil "bilgi" olarak verilir (perakende yapısı).
- **Altman Z''** (gelişmekte olan piyasa / imalat dışı varyant) yalnız yıllık dönemde ve finans dışı şirkette gösterilir. Bileşenleri, katsayıları ve şu uyarılar yanında verilir: TMS 29'da X2 sınırlı; eşikler Türkiye için kalibre edilmemiş; iflas olasılığı değildir.
- **Sağlık puanı üretilmez:** sektöre duyarlı eşikler ve yeterli karşılaştırma verisi olmadan ağırlıklı tek puan açıklanabilir olmaz.

## 7. Sayfalar

1. Yönetici özeti: 8 KPI (dönem, birim, karşılaştırma dönemi ve yöntemi, uyarı, trend), en fazla 3 olumlu ve 3 risk, hasılat/kâr ve marj trendi.
2. Finansal durum: varlık ve kaynak yapısı (dikey analiz), yatay analiz tablosu (önceki aynı uzunlukta dönem ve önceki yıl sonu), net işletme sermayesi.
3. Performans: gelir tablosu ve marj trendi, ROE/ROA, DuPont tablosu ve log ayrıştırmayla sürücü açıklaması.
4. Nakit akışı: işletme nakdi, CapEx, serbest nakit akışı, nakit dönüşümü, stok/alacak/borç günleri ve nakit döngüsü, kurala dayalı yorum.
5. Likidite ve risk: cari, asit-test (tanımıyla), nakit oranı, NİS; finansal borç ve toplam yükümlülük ayrı; net borç/FAVÖK; EBIT ve FAVÖK bazlı faiz karşılama; vade uyarısı; Altman Z''.
6. Sektör karşılaştırması: varsayılan aynı grup, kapsam tablosu (dahil/dışlandı ve nedeni), yalnız aynı dönem ve oranlar, grup medyanı.
7. Finansal tablolar: gelir, bilanço, nakit akış, özkaynak değişimi, dipnot sekmeleri. Görünümler: tutar, yatay (tutar ve %), dikey. Satır üzerinde formül/kaynak kodu gösterilir; satır ayrıntısında alt kalemler ve köken; CSV indirme.
8. Check-up ve veri kalitesi: özet, güçlü yönler, izlenecekler (kural ve dayanakla), temel metrikler, hesaplanamayanlar, veri uyarıları, test sonuçları. İndirmeler: Excel, HTML rapor (tarayıcıdan PDF), oran CSV, veri modeli CSV.

## 8. Testler

| Test | Komut | Sonuç |
|---|---|---|
| Çekirdek birim testleri | `python tests/test_core.py` | 11/11 (2026-11-13): güvenli % değişim, üç fiyat görünümünde karşılaştırılabilirlik kodları, yayımlanan 10 rakamla fiyat çevirme mutabakatı, enflasyon muhasebesi uygulamayan şirket tespiti, toplam kimlikleri, DuPont = ROE, ortalama bakiye kuralı, hesaplanamama nedenleri, reel ve geçiş dönemi TL değişimi, tablolar ve özkaynak mutabakatı, Altman uygunluğu |
| SQL ile birebirlik | `python tests/test_parity.py` | Kaynak görünümüyle çalışır. Son çalıştırma 2026-11-05: 28 metrik × 4 şirket × 28 dönem, 3.136 değer, **0 fark**. Fiyat düzeyi modülünden sonra yeniden çalıştırılmadı (bkz. bölüm 10). |
| Arayüz duman testi | `python tests/test_app_pages.py` | 8 sayfa × 8 senaryo (2026-11-13): yıllık, ara dönem, negatif özkaynak, geçiş yılı 2022/12, TMS 29 öncesi, karma fiyatlı 2023/9, "yayımlandığı gibi" görünümü; 0 hata |
| Kaynak veri kimlikleri | uygulama içi | BİM 581 PASS, 0 FAIL. CarrefourSA'da dönem sonu nakit mutabakatı (4CBL) 11 dönemde tutmuyor, Migros ve Şok'ta 1'er dönem: kaynak tutarsızlığı, FAIL olarak gösterilir. |
| Diğer şirketler | ULKER, THYAO, EREGL, FROTO, ASELS, PNSUT | ULKER 539 test, 0 FAIL. THYAO ve EREGL enflasyon muhasebesi uygulamıyor olarak tanındı, nominal bırakıldı. AKBNK anlaşılır mesajla reddediliyor. |

## 9. Sınırlar

- Kaynak resmî değildir; kritik rakamlar KAP'ta doğrulanmalıdır.
- 2022 öncesi dönemler bu kaynaktan ortak fiyata çevrilemez; nominal kalır.
- Kiralama yükümlülükleri finansal borç içinde olabilir; kaynak ayırmıyor.
- Ara dönem yıllıklandırması mevsimselliği yok sayar.
- PDF, HTML raporun tarayıcıdan yazdırılmasıyla alınır (ek kütüphane kurulmadı).

## 10. Kaynak kolonlarının fiyat düzeyi ve reel karşılaştırma (2026-11-13)

**Sorun.** Uygulama 2022/12 ve 2025/12 gibi dönemlerde "kaynak veri uyarısı" gösteriyor, TL karşılaştırmalarını kapatıyordu. Neden bilinmiyordu; yalnız belirtisi (toplam varlıkta sıçrama, açıklanan rakamın 1,18 katı hasılat) kaydedilmişti.

**Bulgu.** Kaynaktaki bir dönem kolonu, o dönemin ilk yayımlanan rakamı değil, o dönemi karşılaştırma olarak içeren sonraki rapordaki (enflasyona göre yeniden düzenlenmiş) rakamdır:

| Kolon | Fiyat düzeyi |
|---|---|
| Yıllık Y/12, gelir tablosu ve bilanço | (Y+1) yılında yayımlanmış en son raporun dönem sonu |
| Ara dönem Y/m, gelir tablosu ve nakit akışı | (Y+1)/m raporu yayımlandıysa onun dönem sonu; yoksa kendi dönem sonu |
| Ara dönem Y/m, bilanço | Kendi dönem sonu (ara dönem raporları karşılaştırma bilançosu olarak yalnız önceki yıl sonunu verir) |
| TMS 29 öncesi, sonradan düzenlenmemiş (yıllık ≤ 2021, ara dönem ≤ 2022/9; 2023 ara dönem bilançoları) | Nominal TL |

**Kanıt.**
- BİM 2023 raporu: 2023 hasılatı 328.441.924 bin TL, 2022 karşılaştırması 279.252.910 bin TL. Kaynakta 2022/12 = 279.252.910 (birebir), 2023/12 = 474.200 mn = 328.442 × 1,4438 (Aralık 2024 yıllık TÜFE %44,38).
- 2024/12 kolonu / açıklanan 2024: BİM 680,1 / 519,6, Migros 384,5 / 293,8, Şok 264,6 / 202,2 = 1,309 (Aralık 2025 yıllık TÜFE %30,89).
- 2025/12 kolonu / açıklanan 2025: BİM, Migros, Şok 1,1777 = TÜFE(Haziran 2026) / TÜFE(Aralık 2025); CarrefourSA 1,2432 = TÜFE(Eylül 2026) / TÜFE(Aralık 2025). Veri 05.11.2026'da çekildi; o tarihte CarrefourSA 9 aylık raporunu yayımlamıştı, diğer üçü yayımlamamıştı.
- Çevirmeden sonra türetilen çeyreklik hasılatlar düzgün bir seri verir (BİM 2025: 175,7 / 171,9 / 187,5 / 186,0 milyar TL, Aralık 2025 fiyatıyla); önceki "çeyrek makullüğü" hataları kaybolur.

**Çözüm.** `bistfa/pricebasis.py`:
- TÜİK aylık TÜFE değişimlerinden endeks kurar (kaynak: TCMB tüketici fiyatları tablosu; Aralık ayları yıllık orana oturtulur).
- Her kolonun kaynak fiyat düzeyini yukarıdaki kuralla, akış ve bilanço için ayrı ayrı belirler.
- Üç görünüm üretir: **ortak fiyat** (varsayılan; düzeltilmiş tüm dönemler son yıl sonu fiyatıyla, büyüme reel), **yayımlandığı gibi** (her dönem kendi dönem sonu fiyatıyla) ve **kaynak** (dokunulmamış; SQL birebirlik testi için).
- Enflasyon muhasebesi uygulamayan şirketleri (ör. işlevsel para birimi USD olanlar) tanır: 2022/12 toplam varlığı 2022/9'a göre sıçramıyorsa kolonlar nominal bırakılır (THYAO 1,03 ve EREGL 1,00; uygulayanlarda 1,9 ile 2,9 arası).
- SQL projesinin 2025/12'de biten ham dosyaları için çekim anındaki son rapor dönemi elle kaydedilmiştir (`SNAPSHOT_LATEST`). Uygulamanın kendi çektiği veride bu, mevcut dönemlerden otomatik bulunur.

**Sonuçlar ve sınırlar.**
- Yayımlanan rakamlarla mutabakat `tests/test_core.py` içinde: 10 rakam, %0,3 tolerans.
- 2023 ara dönemlerinde gelir tablosu düzeltilmiş, bilanço nominaldir. İkisini birleştiren oranlar (ROE, devir hızı, gün oranları, net borç / FAVÖK) bu dönemlerde hesaplanmaz ve nedeni gösterilir. Kaynak görünümünde bu tutarsızlık 2024 ve sonrasındaki ara dönemlerde de vardı (akış bir yıl sonraki fiyatla, bilanço kendi fiyatıyla); ortak fiyat görünümü bunu giderir.
- 2022/12 ve 2023 ara dönem gelir tablolarının ilk yayımlanan (nominal) hâli kaynakta yoktur; "yayımlandığı gibi" görünümünde bu kolonlar sonraki rapordaki hâliyle kalır ve böyle etiketlenir.
- TÜFE tablosu Ekim 2026'ya kadar doludur. Daha yeni bir fiyat düzeyi gerektiren kolon kaynak fiyatıyla bırakılır ve dönem notu düşülür; tablo elle güncellenir.
- Çeyrek makullüğü testi artık karşılaştırmaları kapatmaz; aralık dışı çeyrekler (ör. ASELSAN'ın dördüncü çeyrek mevsimselliği) "INFO" olarak listelenir.
- SQL birebirlik testi kaynak görünümüyle çalışır. Bu değişiklikten sonra SQL Server'a erişilemediği için yeniden çalıştırılmadı; kaynak görünümü önceki davranışı korur.

## 11. Eksik veri çekimi ve fiyat düzeyi (2026-11-14)

**Bulgu.** Canlı uygulamada (Streamlit Cloud) BİM 2025 hasılatı 761,3 milyar TL ve reel büyüme %11,9 göründü; doğrusu 721,1 ve %6,0. Neden: kaynak (isyatirimhisse) her yıl için tek istek atar, 10 sn'lik sabit zaman aşımında yalnız uyarı yazıp o yılı atlar. Bulut sunucusundaki çekimde 2022 ve 2026/9 sütunları gelmemişti. 2026/9 raporu yayımlandığı için kaynak 2025 yıllığını Eylül 2026 fiyatıyla verirken, 2026/9 sütunu eksik olduğundan `pricebasis` kolonu Haziran 2026 fiyatında saydı: 896,4 / 1,1775 = 761,3 (doğrusu 896,4 / 1,2430 = 721,2). Formül değil, veri tamlığı hatası.

**Düzeltme (`bistfa/source.py`).**
- Yıllar tek tek çekilir; kütüphanenin uyarı çıktısı yakalanır, zaman aşımına düşen yıl beklemeyle 4 kez yeniden denenir. Yine alınamazsa yükleme durur ve "tekrar deneyin" mesajı verilir; kısmi veri döndürülmez, önbelleğe yazılmaz.
- Kütüphane modülündeki istek zaman aşımı 30 sn'ye çıkarıldı (yalnız o modülde). Ölçüm: yanıtlar ya ~0,3 sn ya ~10,2 sn sürüyor; 10 sn sınırı ikinci grubu kesiyordu.
- Eksiksiz çekimden sonra `app/.cache/<KOD>.meta.json` yazılır. Bu dosyası olmayan önbellek güvenilmez sayılıp yeniden çekilir; eksiksiz önbellek 7 günden eskiyse yenilenir, yenilenemezse eski kopya "önbellek (yenilenemedi)" etiketiyle kullanılır.
- İstekler hatasız döndükten sonra kalan boşluklar kaynağın kendi boşluklarıdır ve eskisi gibi modelde "gap" olarak gösterilir.

**Doğrulama.** Yeni testler: zaman aşımı sonrası yeniden deneme, kalıcı zaman aşımında kısmi veri reddi, işaretsiz önbelleğe güvenmeme, eski önbellek davranışı (test_core: 13/13). Taze çekim (14.11.2026, son sütun 2026/9): 2025 hasılatı BİM 721,2 (açıklanan 721,0), Migros 412,8 (413,0), Şok 278,9 (278,8) milyar TL. Testler `BISTFA_OFFLINE=1` ile ağa çıkmadan önbellekten çalışır.
