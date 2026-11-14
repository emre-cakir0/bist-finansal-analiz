"""
Kaynak kalem kataloğu ve tablo düzenleri.

İş Yatırım kalem kodları düzgün bir ağaç DEĞİLDİR (ör. 2AAGAA 'Ticari Borçlar' kısa vadeli yükümlülüklerin
doğrudan alt kalemidir, 2AA 'Finansal Borçlar'ın değil). Bu yüzden hiyerarşi burada elle ve açıkça tanımlanır.
Toplam kimlikleri (ör. 1A = alt kalemler toplamı) quality.py'de her dönem için test edilir.

Satır biçimi: (kod, düzey, tür, etiket)
  tür: "total" (ana toplam), "sub" (ara toplam), "line" (kalem), "header" (başlık, değersiz),
       "derived" (kaynakta olmayan, burada hesaplanan satır), "memo" (dipnot bilgisi)
İşaret: kaynakta giderler negatiftir. 3HC '(Esas faaliyet dışı) finansal giderler (−)' adını taşısa da İŞARETLİ
bir NET tutardır: vergi öncesi kâr = EBIT (3HACA) + 3HB + 3HC (tüm dönemlerde birebir doğrulandı; 3HCA yatırım
faaliyetlerinin bilgi amaçlı alt toplamıdır ve zaten EBIT içindedir). Negatif = net finansman
gideri; TMS 29 döneminde net parasal pozisyon kazançları nedeniyle pozitif (net gelir) olabilir. Bu yüzden saf
faiz gideri bu kaynaktan ayrıştırılamaz. (Önceki SQL projesinde 'pozitif = gider' varsayılmıştı; yanlıştır.)
"""
from __future__ import annotations

# standart anahtar -> kaynak kodu (metrikler bu anahtarlarla çalışır)
STD = {
    "current_assets": "1A", "cash": "1AA", "st_fin_investments": "1AB", "trade_receivables": "1AC",
    "other_receivables": "1AE", "inventories": "1AF", "bio_assets_st": "1AG", "other_current_assets": "1AH",
    "held_for_sale": "1AJ", "non_current_assets": "1AK", "ppe": "1BG", "rou_assets": "1BFAA", "goodwill": "1BGA",
    "intangibles": "1BH", "total_assets": "1BL",
    "current_liabilities": "2A", "st_fin_debt": "2AA", "st_other_fin_liab": "2AAG", "trade_payables": "2AAGAA",
    "non_current_liabilities": "2B", "lt_fin_debt": "2BA", "lt_other_fin_liab": "2BB",
    "total_equity": "2N", "parent_equity": "2O", "paid_in_capital": "2OA", "retained_earnings": "2OCE",
    "current_year_profit_bs": "2OCF", "minority_equity": "2ODA", "total_liab_equity": "2ODB",
    "revenue": "3C", "cogs": "3CA", "gross_profit": "3D", "selling_expenses": "3DA", "admin_expenses": "3DB",
    "rnd_expenses": "3DC", "core_operating_profit": "3H", "other_op_income": "3DD", "other_op_expense": "3DE",
    "operating_profit": "3DF", "ebit": "3HACA", "finance_income": "3HB", "finance_expense": "3HC",
    "profit_before_tax": "3I", "tax_expense": "3IA", "profit_continuing": "3J", "net_income": "3L",
    "minority_income": "3LB", "net_income_parent": "3Z", "eps": "3ZD",
    "da_memo": "4B", "finance_expense_memo": "4BB", "domestic_sales": "4BC", "export_sales": "4BD",
    "net_fx_position": "4BE",
    "operating_cash_flow": "4C", "da_cf": "4CAB", "wc_change": "4CAF", "capex": "4CAI",
    "investing_cash_flow": "4CAK", "fcf_source": "4CB", "fin_debt_change": "4CBA", "dividends_paid": "4CBB",
    "capital_increase": "4CBC", "financing_cash_flow": "4CBE", "cash_change": "4CBI",
    "cash_begin": "4CBK", "cash_end": "4CBL",
}
CODE_STD = {v: k for k, v in STD.items()}

STATEMENT_OF = {"1": "BS", "2": "BS", "3": "IS"}


def statement_of(code: str) -> str:
    if code.startswith("4C"):
        return "CF"
    if code.startswith("4B"):
        return "MEMO"
    return STATEMENT_OF.get(code[0], "OTHER")


def is_flow(code: str) -> bool:
    """Gelir tablosu, nakit akışı ve dipnot akışları yılbaşından itibaren kümülatiftir (YTD)."""
    return statement_of(code) in ("IS", "CF") or code in ("4B", "4BA", "4BB", "4BC", "4BD")


DISPLAY_SIGN: dict = {}  # tüm kalemler kaynaktaki işaretle gösterilir

BS = [
    (None, 0, "header", "VARLIKLAR"),
    ("1A", 0, "total", "Dönen varlıklar"),
    ("1AA", 1, "line", "Nakit ve nakit benzerleri"), ("1AB", 1, "line", "Finansal yatırımlar"),
    ("1AC", 1, "line", "Ticari alacaklar"), ("1AD", 1, "line", "Finans sektörü faaliyetlerinden alacaklar"),
    ("1AE", 1, "line", "Diğer alacaklar"), ("1AEA", 1, "line", "Müşteri sözleşmelerinden doğan varlıklar"),
    ("1AF", 1, "line", "Stoklar"), ("1AG", 1, "line", "Canlı varlıklar"), ("1AH", 1, "line", "Diğer dönen varlıklar"),
    ("1AJ", 1, "line", "Satış amacıyla elde tutulan duran varlıklar"),
    ("1AK", 0, "total", "Duran varlıklar"),
    ("1B", 1, "line", "Ticari alacaklar"), ("1BA", 1, "line", "Finans sektörü faaliyetlerinden alacaklar"),
    ("1BB", 1, "line", "Diğer alacaklar"), ("1BBA", 1, "line", "Müşteri sözleşmelerinden doğan varlıklar"),
    ("1BC", 1, "line", "Finansal yatırımlar"), ("1BD", 1, "line", "Özkaynak yöntemiyle değerlenen yatırımlar"),
    ("1BE", 1, "line", "Canlı varlıklar"), ("1BF", 1, "line", "Yatırım amaçlı gayrimenkuller"),
    ("1BFA", 1, "line", "Stoklar"), ("1BFAA", 1, "line", "Kullanım hakkı varlıkları"),
    ("1BG", 1, "line", "Maddi duran varlıklar"), ("1BGA", 1, "line", "Şerefiye"),
    ("1BH", 1, "line", "Maddi olmayan duran varlıklar"), ("1BJ", 1, "line", "Ertelenmiş vergi varlığı"),
    ("1BK", 1, "line", "Diğer duran varlıklar"),
    ("1BL", 0, "total", "TOPLAM VARLIKLAR"),
    (None, 0, "header", "KAYNAKLAR"),
    ("2A", 0, "total", "Kısa vadeli yükümlülükler"),
    ("2AA", 1, "line", "Finansal borçlar"), ("2AAG", 1, "line", "Diğer finansal yükümlülükler"),
    ("2AAGAA", 1, "line", "Ticari borçlar"), ("2AAGAB", 1, "line", "Diğer borçlar"),
    ("2AAGAC", 1, "line", "Müşteri sözleşmelerinden doğan yükümlülükler"),
    ("2AAGB", 1, "line", "Finans sektörü faaliyetlerinden borçlar"), ("2AAGC", 1, "line", "Devlet teşvik ve yardımları"),
    ("2AAGCA", 1, "line", "Ertelenmiş gelirler"), ("2AAGD", 1, "line", "Dönem kârı vergi yükümlülüğü"),
    ("2AAGE", 1, "line", "Borç karşılıkları"), ("2AAGF", 1, "line", "Diğer kısa vadeli yükümlülükler"),
    ("2AAGH", 1, "line", "Satış amaçlı varlıklara ilişkin yükümlülükler"),
    ("2B", 0, "total", "Uzun vadeli yükümlülükler"),
    ("2BA", 1, "line", "Finansal borçlar"), ("2BB", 1, "line", "Diğer finansal yükümlülükler"),
    ("2BBA", 1, "line", "Ticari borçlar"), ("2BBB", 1, "line", "Diğer borçlar"),
    ("2BBBA", 1, "line", "Müşteri sözleşmelerinden doğan yükümlülükler"),
    ("2BC", 1, "line", "Finans sektörü faaliyetlerinden borçlar"), ("2BD", 1, "line", "Devlet teşvik ve yardımları"),
    ("2BDA", 1, "line", "Ertelenmiş gelirler"), ("2BE", 1, "line", "Uzun vadeli karşılıklar"),
    ("2BF", 1, "line", "Çalışanlara sağlanan faydalara ilişkin karşılıklar"),
    ("2BG", 1, "line", "Ertelenmiş vergi yükümlülüğü"), ("2BH", 1, "line", "Diğer uzun vadeli yükümlülükler"),
    ("D_TOTAL_LIAB", 0, "derived", "Toplam yükümlülükler"),
    ("2N", 0, "total", "Özkaynaklar"),
    ("2O", 1, "sub", "Ana ortaklığa ait özkaynaklar"),
    ("2OA", 2, "line", "Ödenmiş sermaye"), ("2OC", 2, "line", "Karşılıklı iştirak sermayesi düzeltmesi (−)"),
    ("2OCA", 2, "line", "Hisse senedi ihraç primleri"), ("2OCB", 2, "line", "Değer artış fonları"),
    ("2OCC", 2, "line", "Yabancı para çevrim farkları"), ("2OCD", 2, "line", "Kârdan ayrılan kısıtlanmış yedekler"),
    ("2OCE", 2, "line", "Geçmiş yıllar kâr/zararları"), ("2OCF", 2, "line", "Dönem net kâr/zararı"),
    ("2OD", 2, "line", "Diğer özsermaye kalemleri"),
    ("D_EQ_RESID", 2, "derived", "Kaynakta ayrıştırılmamış fark"),
    ("2ODA", 1, "line", "Azınlık payları"),
    ("2ODB", 0, "total", "TOPLAM KAYNAKLAR"),
]

IS = [
    ("3C", 0, "total", "Hasılat"),
    ("3CA", 1, "line", "Satışların maliyeti (−)"),
    ("3CAA", 1, "line", "Ticari faaliyetlerden diğer kâr/zarar"),
    ("3CAC", 1, "line", "Faiz, ücret, prim, komisyon gelirleri (finans sektörü)"),
    ("3CAD", 1, "line", "Faiz, ücret, prim, komisyon giderleri (finans sektörü)"),
    ("3CAE", 1, "line", "Finans sektörü faaliyetlerinden diğer kâr/zarar"),
    ("3CB", 1, "line", "Diğer gelir ve giderler"),
    ("3D", 0, "sub", "BRÜT KÂR"),
    ("3DA", 1, "line", "Pazarlama, satış ve dağıtım giderleri (−)"), ("3DB", 1, "line", "Genel yönetim giderleri (−)"),
    ("3DC", 1, "line", "Araştırma ve geliştirme giderleri (−)"),
    ("3H", 0, "sub", "Net faaliyet kârı (diğer faaliyet gelir/giderleri hariç)"),
    ("3DD", 1, "line", "Esas faaliyetlerden diğer gelirler"), ("3DE", 1, "line", "Esas faaliyetlerden diğer giderler (−)"),
    ("3DEA", 1, "line", "Faaliyet kârı öncesi diğer gelir ve giderler"),
    ("3DF", 0, "sub", "ESAS FAALİYET KÂRI"),
    ("3HA", 1, "line", "Yatırım faaliyetlerinden gelirler"), ("3HAA", 1, "line", "Yatırım faaliyetlerinden giderler (−)"),
    ("3HAB", 1, "line", "Diğer gelir ve giderler"),
    ("3HAC", 1, "line", "Özkaynak yöntemiyle değerlenen yatırımların kâr/zarar payları"),
    ("3HCA", 2, "memo", "Bilgi: yatırım faaliyetleri, net (EBIT içinde; toplama ayrıca katılmaz)"),
    ("3HACA", 0, "sub", "FİNANSMAN GİDERİ ÖNCESİ FAALİYET KÂRI (EBIT)"),
    ("3HB", 1, "line", "Finansal gelirler"),
    ("3HC", 1, "line", "Finansman gelir/gideri, net (negatif = gider; TMS 29 parasal kazanç içerebilir)"),
    ("3I", 0, "sub", "VERGİ ÖNCESİ KÂR"),
    ("3IA", 1, "line", "Vergi gelir/gideri"),
    ("3IB", 2, "line", "Dönem vergi gelir/gideri"), ("3IC", 2, "line", "Ertelenmiş vergi gelir/gideri"),
    ("3ID", 2, "line", "Diğer vergi gelir/gideri"),
    ("3J", 0, "sub", "Sürdürülen faaliyetler dönem kârı"),
    ("3KA", 1, "line", "Durdurulan faaliyetler dönem kârı"),
    ("3L", 0, "total", "DÖNEM KÂRI (ZARARI)"),
    ("3LB", 1, "line", "Azınlık payları"), ("3Z", 1, "line", "Ana ortaklık payları"),
    ("3ZD", 1, "memo", "Hisse başına kazanç (TL)"),
    (None, 0, "header", "HESAPLANAN GÖSTERGELER"),
    ("D_EBITDA", 0, "derived", "FAVÖK (hesaplanan) = net faaliyet kârı + amortisman"),
]

CF = [
    ("4C", 0, "total", "İşletme faaliyetlerinden net nakit"),
    ("4CA", 1, "line", "Düzeltme öncesi kâr"),
    ("4CAB", 2, "line", "Amortisman ve itfa payları"), ("4CAC", 2, "line", "Karşılıklardaki değişim"),
    ("4CAD", 2, "line", "Diğer gelir/gider düzeltmeleri"),
    ("4CAE", 1, "sub", "İşletme sermayesi değişimi öncesi faaliyet kârı"),
    ("4CAF", 1, "line", "İşletme sermayesindeki değişim"),
    ("4CAG", 1, "sub", "Esas faaliyetten oluşan nakit"), ("4CAH", 1, "line", "Diğer işletme faaliyetlerinden nakit"),
    ("4CAK", 0, "total", "Yatırım faaliyetlerinden nakit"),
    ("4CAI", 1, "line", "Sabit sermaye yatırımları (CapEx)"), ("4CAJ", 1, "line", "Diğer yatırım faaliyetlerinden nakit"),
    ("4CB", 0, "sub", "Serbest nakit akımı (kaynak tanımı: işletme + tüm yatırım faaliyetleri)"),
    ("4CBE", 0, "total", "Finansman faaliyetlerinden nakit"),
    ("4CBA", 1, "line", "Finansal borçlardaki değişim"), ("4CBB", 1, "line", "Temettü ödemeleri"),
    ("4CBC", 1, "line", "Sermaye artırımı"), ("4CBD", 1, "line", "Diğer finansman faaliyetlerinden nakit"),
    ("4CBI", 0, "sub", "Nakit ve benzerlerindeki değişim"),
    ("4CBG", 1, "line", "Yabancı para çevrim farklarının etkisi"), ("4CBH", 1, "line", "Diğer nakit giriş/çıkışı"),
    ("4CBK", 1, "line", "Dönem başı nakit"), ("4CBJ", 1, "line", "Diğer nakit benzerleri değişimi"),
    ("4CBL", 0, "total", "Dönem sonu nakit"),
    (None, 0, "header", "HESAPLANAN GÖSTERGELER"),
    ("D_FCF", 0, "derived", "Serbest nakit akışı (hesaplanan) = işletme nakdi + sabit sermaye yatırımları"),
]

MEMO = [
    ("4B", 0, "memo", "Amortisman giderleri"), ("4BA", 0, "memo", "Kıdem tazminatı"),
    ("4BB", 0, "memo", "Finansman gelir/gideri, net (3HC ile aynı)"), ("4BC", 0, "memo", "Yurt içi satışlar"),
    ("4BD", 0, "memo", "Yurt dışı satışlar"), ("4BE", 0, "memo", "Net yabancı para pozisyonu"),
    ("4BEA", 1, "memo", "Parasal net yabancı para varlık/(yükümlülük) pozisyonu"),
    ("4BEB", 1, "memo", "Net YP pozisyonu (hedge dahil)"),
]

LAYOUTS = {"IS": IS, "BS": BS, "CF": CF, "MEMO": MEMO}
LABEL = {code: label for lay in LAYOUTS.values() for code, _, _, label in lay if code}

# Türetilen satırların tanımı (formül metni + hesap). Değerler model.py'de 'derived' olarak üretilir.
DERIVED = {
    "D_TOTAL_LIAB": ("Kısa vadeli yükümlülükler + uzun vadeli yükümlülükler", ["2A", "2B"]),
    "D_EQ_RESID": ("Ana ortaklık özkaynakları − kaynakta listelenen bileşenlerin toplamı",
                   ["2O", "2OA", "2OC", "2OCA", "2OCB", "2OCC", "2OCD", "2OCE", "2OCF", "2OD"]),
    "D_EBITDA": ("Net faaliyet kârı (3H) + nakit akış tablosundaki amortisman ve itfa payları (4CAB)", ["3H", "4CAB"]),
    "D_FCF": ("İşletme faaliyetlerinden net nakit (4C) + sabit sermaye yatırımları (4CAI, negatif)", ["4C", "4CAI"]),
}

# Ana toplamlar ve alt kalemleri (kalite testleri ve "alt kalemleri aç" görünümü için)
CHILDREN = {}
for lay in (BS, IS, CF):
    stack: list[tuple[int, str]] = []
    for code, level, kind, _ in lay:
        if code is None or kind == "header":
            stack = []
            continue
        while stack and stack[-1][0] >= level:
            stack.pop()
        if stack and kind in ("line", "sub", "derived", "memo"):
            CHILDREN.setdefault(stack[-1][1], []).append(code)
        if kind in ("total", "sub"):
            stack.append((level, code))

IDENTITIES = {  # toplam = alt kalemler (kaynak verisinde doğrulandı; her dönem test edilir)
    "1A": ["1AA", "1AB", "1AC", "1AD", "1AE", "1AEA", "1AF", "1AG", "1AH", "1AJ"],
    "1AK": ["1B", "1BA", "1BB", "1BBA", "1BC", "1BD", "1BE", "1BF", "1BFA", "1BFAA", "1BG", "1BGA", "1BH", "1BJ", "1BK"],
    "1BL": ["1A", "1AK"],
    "2A": ["2AA", "2AAG", "2AAGAA", "2AAGAB", "2AAGAC", "2AAGB", "2AAGC", "2AAGCA", "2AAGD", "2AAGE", "2AAGF", "2AAGH"],
    "2B": ["2BA", "2BB", "2BBA", "2BBB", "2BBBA", "2BC", "2BD", "2BDA", "2BE", "2BF", "2BG", "2BH"],
    "2N": ["2O", "2ODA"],
    "2ODB": ["2A", "2B", "2N"],
    "3D": ["3C", "3CA"],
    "3H": ["3D", "3DA", "3DB", "3DC"],
    "3DF": ["3H", "3DD", "3DE", "3DEA"],
    "3HACA": ["3DF", "3HA", "3HAA", "3HAB", "3HAC"],
    "3I": ["3HACA", "3HB", "3HC"],
    "3J": ["3I", "3IA"],
    "3L": ["3J", "3KA"],
    "4C": ["4CAG", "4CAH"],
    "4CAG": ["4CAE", "4CAF"],
    "4CAK": ["4CAI", "4CAJ"],
    "4CB": ["4C", "4CAK"],
    "4CBE": ["4CBA", "4CBB", "4CBC", "4CBD"],
    "4CBL": ["4CBK", "4CBI", "4CBJ"],
}
