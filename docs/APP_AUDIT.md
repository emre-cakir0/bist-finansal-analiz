# BIST Finansal Analiz uygulaması v2: denetim, kararlar ve doğrulama

Son güncelleme: 2026-11-05

Bu belge, uygulamayı tam bir mali tablo analiz aracına dönüştürme isteğinin (8 sayfa, köken bilgili veri modeli, kural tabanlı yorum) nasıl ele alındığını kaydeder: mevcut kodun denetimi, tut / yeniden düzenle / yeniden yaz kararları, veri kuralları, bilinçli tanım farkları ve testler.

## 1. Mevcut kodun denetimi ve kararlar

| Parça | Karar | Gerekçe |
|---|---|---|
| Veri bağlantısı (`isyatirimhisse`, yıl yıl yeniden deneme, önbellek) | **Tutuldu**, `bistfa/source.py`'ye taşındı | Çalışıyordu ve eksik yıl sorununu çözüyordu. Önbellek yoksa önce SQL projesinin ham CSV'leri okunur (aynı kaynak, aynı biçim). |
| Baz kırılması tespiti, kalite testleri | **Tutuldu**, `bistfa/quality.py` | SQL testleriyle aynı sonucu veriyordu. Kaynak verisinde doğrulanan 20 toplam kimliği her dönem test edilir. |
| Oran mantığı (`rf_core.py`) | **Yeniden düzenlendi** → `bistfa/metrics.py` | 43 metrik tek bir kayıtta tanımlandı: her sonuç değer, birim, formül, kullanılan kalemler, bakiye bazı ve hesaplanamadıysa nedenini taşır. Ortalama bakiye kuralı eklendi. |
| Veri modeli | **Yeni**: `bistfa/model.py` | İstenen köken alanları için uzun formatlı fact tablosu (aşağıda). |
| Arayüz (`app.py` v1, 5 sekme) | **Yeniden yazıldı**: `app/app.py`, `app/ui.py`, `app/views.py` | 8 sayfa, formül açıklama katmanı ve metrik yanında uyarı gereksinimleri tek sayfalı tasarıma sığmıyordu. |
| v1 dosyaları | **Silinmedi**: `app/legacy_v1/` | Çalışan hesaplamalar silinmez kuralı. |

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
- **TMS 29:** 2023/12 ve sonrasında her kolon kendi dönem sonu fiyatıyla ifade edilir. Oranlar aynı kolon içinde hesaplanır. TL değişimleri "nominal" etiketiyle gösterilir; reel büyüme gösterilmez. Kaynakta baz kırılması olan dönemlerde TL değişimi hiç gösterilmez.
- **Ortalama bakiye:** ROE, ROA, devir hızı ve gün hesaplarında (açılış + kapanış) / 2, yalnız iki bakiye de TMS 29 öncesiyse. Aksi halde dönem sonu kullanılır ve sonuçta yazılır.
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

| Test | Komut | Sonuç (2026-11-05) |
|---|---|---|
| Çekirdek birim testleri | `python tests/test_core.py` | 9/9: güvenli % değişim, karşılaştırılabilirlik kodları, toplam kimlikleri, DuPont = ROE, ortalama bakiye kuralı, hesaplanamama nedenleri, baz kırılmasında TL değişimi engeli, tablolar ve özkaynak mutabakatı, Altman uygunluğu |
| SQL ile birebirlik | `python tests/test_parity.py` | 28 metrik × 4 şirket × 28 dönem: 3.136 değer, **0 fark**. 20 değer uygulamanın bilinçli olarak hesaplamadığı durum. 5 tanım farkı (bölüm 5) SQL tanımıyla kaynak kalemlerden yeniden kurularak doğrulandı (520 değer). |
| Arayüz duman testi | `python tests/test_app_pages.py` | 8 sayfa × 5 senaryo (BİM 2025/12 ve 2021/12, CarrefourSA negatif özkaynak, Migros 2022/12 baz kırılması, Şok 2025/9 ara dönem) + giriş sayfası: 0 hata |
| Kaynak veri kimlikleri | uygulama içi | BİM 579 PASS, 3 EXPLAINED. CarrefourSA'da dönem sonu nakit mutabakatı (4CBL) 11 dönemde tutmuyor, Migros ve Şok'ta 1'er dönem: kaynak tutarsızlığı, FAIL olarak gösterilir. |
| Perakende dışı şirket | ULKER | 540 test, 0 FAIL. 2022/12, 2025/9, 2025/12 baz kırılması otomatik tespit edildi. AKBNK anlaşılır mesajla reddedildi. |

Tarayıcıda (localhost:8501) yönetici özeti, performans, risk, sektör, tablolar ve check-up sayfaları açılıp metinleri kontrol edildi. Görülen hatalar düzeltildi: ondalık noktalar, sıfır değişimin "olumsuz" görünmesi, hisse başına kazancın ölçeklenmesi, ROE düşüşü kuralının eksikliği.

## 9. Sınırlar

- Kaynak resmî değildir; kritik rakamlar KAP'ta doğrulanmalıdır.
- Reel büyüme için TÜFE serisi gerekir (yapılmadı).
- Kiralama yükümlülükleri finansal borç içinde olabilir; kaynak ayırmıyor.
- Ara dönem yıllıklandırması mevsimselliği yok sayar.
- PDF, HTML raporun tarayıcıdan yazdırılmasıyla alınır (ek kütüphane kurulmadı).
