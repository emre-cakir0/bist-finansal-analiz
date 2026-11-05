"""
Uygulamanın 8 sayfası. Her sayfa yalnız bistfa çıktısını gösterir; hesaplama ve kurallar bistfa'dadır.
Sayfa fonksiyonları app.py'nin doldurduğu CTX sözlüğünü kullanır.
"""
from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import ui
from bistfa import findings as FD
from bistfa import metrics as M
from bistfa import peers, report, risk, statements
from bistfa.periods import COMP_TEXT, COMPARABLE_AMOUNTS, comparability, safe_change
from bistfa.source import SOURCE_NAME, SOURCE_NOTE, kap_url

CTX: dict = {}


def _c():
    return CTX["co"], CTX["P"], CTX["scale"], CTX["trend"]


def _v(co, code, label):
    return co.value(code, label)


# =================================================================================================
# 1. Yönetici özeti
# =================================================================================================
def page_summary():
    co, P, scale, trend = _c()
    ui.page_head("Yönetici özeti", co, P)
    prev = P.prior_comparable()
    ui.note(f"Karşılaştırma dönemi: <b>{prev.label}</b> (aynı uzunlukta önceki dönem). Oranlarda fark puan/kat olarak, "
            f"TL büyüklüklerde nominal yüzde olarak verilir; TMS 29 döneminde tutar değişimi reel büyüme değildir. "
            f"Tutarlar {ui.scale_name(scale)}. Her kartın altındaki <i>Nasıl hesaplandı?</i> formülü ve kaynak kalemleri gösterir.")
    ui.kpi_row(co, ["revenue", "ebitda", "net_income", "fcf"], P, scale, trend)
    ui.kpi_row(co, ["ebitda_margin", "net_margin", "roe", "nd_ebitda"], P, scale, trend)

    fs = FD.evaluate(co, P)
    c1, c2 = st.columns(2)
    with c1:
        ui.section("Öne çıkan olumlu noktalar", "En fazla 3; kural ve dayanak dönemiyle")
        ui.finding_list(FD.top(fs, "olumlu", 3), "+", ui.GREEN)
    with c2:
        ui.section("Başlıca riskler / izlenecekler", "En fazla 3; eşikler sektör bağlamı olmadan kesin hüküm değildir")
        ui.finding_list(FD.top(fs, "izlenecek", 3), "!", ui.RED)
    info = FD.top(fs, "bilgi", 3)
    if info:
        ui.finding_list(info, "i", ui.BLUE)

    c1, c2 = st.columns([3, 2])
    with c1:
        ui.section("Hasılat ve net kâr", f"{'Yıllık' if P.is_annual else f'{P.months} aylık YTD'} dönemler · {ui.scale_name(scale)} · nominal")
        ui.show(ui.bar_chart(co, ["revenue", "net_income"], trend, scale, [ui.BLUE, ui.ORANGE]))
    with c2:
        ui.section("Marjlar", "Aynı kolon içi oranlar: TMS 29 fiyat bazından etkilenmez")
        ui.show(ui.line_chart(co, ["gross_margin", "ebitda_margin", "net_margin"], trend, colors=[ui.TEAL, ui.BLUE, ui.ORANGE]))
    ui.na_note(co, ["revenue", "net_income", "gross_margin", "ebitda_margin", "net_margin"], trend)
    footer()


# =================================================================================================
# 2. Finansal durum / bilanço
# =================================================================================================
ASSET_GROUPS = [("Nakit ve finansal yatırımlar", ["1AA", "1AB"]), ("Ticari alacaklar", ["1AC"]), ("Stoklar", ["1AF"]),
                ("Diğer dönen varlıklar", "rest:1A:1AA,1AB,1AC,1AF"),
                ("Maddi duran varlıklar + kullanım hakkı", ["1BG", "1BFAA"]),
                ("Diğer duran varlıklar", "rest:1AK:1BG,1BFAA")]
LIAB_GROUPS = [("KV finansal borç", ["2AA"]), ("Ticari borçlar", ["2AAGAA"]), ("Diğer KV yükümlülükler", "rest:2A:2AA,2AAGAA"),
               ("UV finansal borç", ["2BA"]), ("Diğer UV yükümlülükler", "rest:2B:2BA"), ("Özkaynaklar", ["2N"])]


def _group_val(co, spec, label):
    if isinstance(spec, str):
        _, tot, minus = spec.split(":")
        t = _v(co, tot, label)
        if t is None:
            return None
        return t - sum(_v(co, k, label) or 0 for k in minus.split(","))
    vals = [_v(co, k, label) for k in spec]
    return None if all(v is None for v in vals) else sum(v or 0 for v in vals)


def _composition_fig(co, groups, periods, base_code):
    labels = [p.label for p in periods]
    fig = go.Figure()
    for i, (name, spec) in enumerate(groups):
        ys = []
        for l in labels:
            b, v = _v(co, base_code, l), _group_val(co, spec, l)
            ys.append(None if not b or v is None else v / b)
        fig.add_bar(x=labels, y=ys, name=name, marker_color=ui.SERIES[i % 8],
                    hovertemplate=f"{name}<br>%{{x}}: %{{y:.1%}}<extra></extra>")
    fig.update_layout(barmode="relative")
    return ui.style_fig(fig, 340, yfmt=".0%")


def page_balance():
    co, P, scale, trend = _c()
    ui.page_head("Finansal durum (bilanço)", co, P)
    ui.kpi_row(co, ["total_assets", "total_equity", "nwc", "net_debt"], P, scale, trend)
    c1, c2 = st.columns(2)
    with c1:
        ui.section("Varlık yapısı (dikey analiz)", "Her kalem / toplam varlıklar, aynı bilanço tarihi")
        ui.show(_composition_fig(co, ASSET_GROUPS, trend, "1BL"))
    with c2:
        ui.section("Kaynak yapısı (dikey analiz)", "Yükümlülükler ve özkaynak / toplam kaynaklar")
        ui.show(_composition_fig(co, LIAB_GROUPS, trend, "1BL"))
    ui.note("Negatif 'diğer' dilimi, alt kalemlerin toplamı aşan kalemleri (ör. düzeltme hesapları) gösterir. "
            "Finansal borçlara kiralama yükümlülükleri dahil olabilir (kaynak ayrıştırmıyor).")

    ui.section("Yatay analiz: önemli bilanço kalemleri",
               f"{P.label} ile {P.prior_comparable().label} (aynı uzunlukta önceki dönem) ve önceki yıl sonu karşılaştırması")
    _horizontal_table(co, P, scale, ["1A", "1AA", "1AC", "1AF", "1AK", "1BG", "1BFAA", "1BL", "2A", "2AA", "2AAGAA", "2B",
                                     "2BA", "D_TOTAL_LIAB", "2N"])

    ui.section("Net işletme sermayesi", "Dönen varlıklar − kısa vadeli yükümlülükler; negatif değer KV yükümlülüklerin dönen varlıkları aştığını gösterir")
    ui.show(ui.bar_chart(co, ["nwc"], trend, scale, [ui.TEAL], height=260))
    footer()


def _horizontal_table(co, P, scale, codes):
    from bistfa import catalog as C
    rows = []
    refs = [x for x in dict.fromkeys([P.prior_comparable().label, P.prior_year_end().label]) if x in co.period_labels]
    for code in codes:
        cur = _v(co, code, P.label)
        if cur is None:
            continue
        rec = {"Kalem": C.LABEL.get(code, code), "_tip": f"{code}", P.label: cur,
               "_cls": "total" if code in ("1BL", "2N", "D_TOTAL_LIAB") else ""}
        for rl in refs:
            prevv = _v(co, code, rl)
            comp = comparability(P, co.period(rl), co.issues, set(co.period_labels))
            diff, pc, why = safe_change(cur, prevv)
            ok = comp in COMPARABLE_AMOUNTS
            rec[rl] = prevv
            rec[f"Δ vs {rl}"] = diff if ok else None
            rec[f"% vs {rl}"] = (pc if ok else None, why if ok else COMP_TEXT[comp])
        rows.append(rec)
    if not rows:
        st.info("Seçili dönemde bilanço kalemi bulunamadı.")
        return
    df = pd.DataFrame(rows)
    cols = [P.label] + [c for rl in refs for c in (rl, f"Δ vs {rl}", f"% vs {rl}")]

    def fmt(v, r):
        if isinstance(v, tuple):
            pc, why = v
            if pc is None:
                return f'<span title="{ui.esc(why)}" style="color:#8C9AC0">n.a.</span>', False
            return ("−%" if pc < 0 else "+%") + ui.num(abs(pc) * 100, 1), pc < 0
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return '<span style="color:#5F6F96">—</span>', False
        return ui.num(v / scale, 1), v < 0
    st.markdown(ui.simple_table_html(df, "Kalem", cols, fmt), unsafe_allow_html=True)
    notes = {rl: COMP_TEXT[comparability(P, co.period(rl), co.issues, set(co.period_labels))] for rl in refs}
    ui.note(f"Tutarlar {ui.scale_name(scale)}. " + " · ".join(f"<b>{k}</b>: {ui.esc(v)}" for k, v in notes.items())
            + ". 'n.a.' üzerine gelince neden gösterilmediği görünür (sıfır baz, işaret değişimi, baz kırılması).")


# =================================================================================================
# 3. Performans / kârlılık
# =================================================================================================
def page_performance():
    co, P, scale, trend = _c()
    ui.page_head("Performans ve kârlılık", co, P)
    ui.kpi_row(co, ["gross_margin", "ebit_margin", "roe", "roa"], P, scale, trend)
    c1, c2 = st.columns(2)
    with c1:
        ui.section("Gelir tablosu trendi", f"{ui.scale_name(scale)} · nominal; TMS 29 döneminde yıllar arası reel karşılaştırma değildir")
        ui.show(ui.bar_chart(co, ["revenue", "gross_profit", "ebit", "net_income"], trend, scale))
    with c2:
        ui.section("Marj trendi", "Kâr kalemi / hasılat, aynı dönem kolonu")
        ui.show(ui.line_chart(co, ["gross_margin", "core_op_margin", "ebit_margin", "ebitda_margin", "net_margin"], trend))
    c1, c2 = st.columns(2)
    with c1:
        ui.section("ROE ve ROA", "Getiriler ara dönemde yıllıklandırılır; ortalama bakiye kuralı kart açıklamasında")
        ui.show(ui.line_chart(co, ["roe", "roa"], trend, colors=[ui.BLUE, ui.TEAL]))
    with c2:
        ui.section("DuPont ayrıştırması", "ROE = net kâr marjı × varlık devir hızı × özkaynak çarpanı")
        _dupont(co, P, trend)
    ui.na_note(co, ["gross_margin", "ebit_margin", "ebitda_margin", "net_margin", "roe", "roa"], trend)
    footer()


def _dupont(co, P, trend):
    keys = [("dupont_margin", "pct"), ("asset_turnover", "x"), ("equity_multiplier", "x"), ("roe", "pct")]
    rows = []
    for k, u in keys:
        r = co.metric(k, P)
        rec = {"Bileşen": r.name, "_tip": r.formula}
        for p in trend[-5:]:
            rec[p.label] = co.metric(k, p).value
        rec["_u"] = u
        rows.append(rec)
    df = pd.DataFrame(rows)
    cols = [p.label for p in trend[-5:]]

    def fmt(v, r):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return "—", False
        return ui.fmt_value(v, r["_u"]), v < 0
    st.markdown(ui.simple_table_html(df, "Bileşen", cols, fmt), unsafe_allow_html=True)
    prev = P.prior_comparable()
    a = [co.metric(k, P).value for k, _ in keys[:3]]
    b = [co.metric(k, prev).value for k, _ in keys[:3]]
    if None in a or None in b or min(a + b) <= 0:
        ui.note("Sürücü analizi yapılamadı: bileşenlerden biri eksik ya da pozitif değil (log ayrıştırması pozitif değer ister).")
    else:
        contrib = [math.log(x / y) for x, y in zip(a, b)]
        tot = sum(contrib)
        names = ["net kâr marjı", "varlık devir hızı", "özkaynak çarpanı"]
        i = max(range(3), key=lambda j: abs(contrib[j]))
        share = abs(contrib[i]) / sum(abs(c) for c in contrib) if any(contrib) else 0
        ui.note(f"<b>Sürücü:</b> {prev.label} → {P.label} ROE değişiminin (log ayrıştırma) en büyük katkısı "
                f"<b>{names[i]}</b> ({'+' if contrib[i] > 0 else '−'}; mutlak katkıların %{share * 100:.0f}'i). "
                + " · ".join(f"{n}: {'+' if c >= 0 else '−'}{ui.num(abs(c), 2)}" for n, c in zip(names, contrib))
                + f" (toplam {'+' if tot >= 0 else '−'}{ui.num(abs(tot), 2)} = ln(ROE cari / ROE önceki)). "
                "Net kâr marjı DuPont'ta ana ortaklık kârı (3Z) ile hesaplanır.")
    basis = co.metric("roe", P).basis
    if basis:
        ui.note("Bakiye bazı: " + ui.esc(basis))


# =================================================================================================
# 4. Nakit akışı ve işletme sermayesi
# =================================================================================================
def page_cash():
    co, P, scale, trend = _c()
    ui.page_head("Nakit akışı ve işletme sermayesi", co, P)
    ui.kpi_row(co, ["ocf", "capex", "fcf", "ocf_to_ebitda"], P, scale, trend)
    c1, c2 = st.columns(2)
    with c1:
        ui.section("İşletme nakdi, yatırım ve serbest nakit", f"{ui.scale_name(scale)} · YTD akışlar")
        ui.show(ui.bar_chart(co, ["ocf", "capex", "fcf"], trend, scale, [ui.BLUE, ui.ORANGE, ui.TEAL]))
    with c2:
        ui.section("Nakit dönüşümü", "İşletme nakdi / FAVÖK ve işletme nakdi / net kâr (1,0 = kârın tamamı nakde döndü)")
        ui.show(ui.line_chart(co, ["ocf_to_ebitda", "ocf_to_net_income"], trend, pct=False, colors=[ui.BLUE, ui.ORANGE]))
    c1, c2 = st.columns(2)
    with c1:
        ui.section("İşletme sermayesi günleri", "Stok + alacak − borç günü = nakit dönüşüm döngüsü")
        ui.show(ui.line_chart(co, ["dio", "dso", "dpo", "ccc"], trend, pct=False,
                              colors=[ui.ORANGE, ui.TEAL, ui.PINK, ui.BLUE], dash_ids=("ccc",)))
    with c2:
        ui.section("Yatırım yoğunluğu", "CapEx / hasılat ve CapEx / amortisman")
        ui.show(ui.line_chart(co, ["capex_to_revenue", "fcf_margin"], trend, colors=[ui.ORANGE, ui.TEAL]))
    ui.section("Yorum", "Değerlerden kurala dayalı üretilir")
    for t in _cash_story(co, P):
        st.markdown("- " + t)
    ui.na_note(co, ["ocf", "fcf", "ocf_to_ebitda", "ocf_to_net_income", "dio", "dso", "dpo", "ccc"], trend)
    footer()


def _cash_story(co, P):
    m = lambda k: co.metric(k, P)  # noqa: E731
    out = []
    ccc, dpo, dio = m("ccc").value, m("dpo").value, m("dio").value
    if ccc is not None:
        if ccc < 0:
            out.append(f"Nakit dönüşüm döngüsü **{ui.num(ccc, 0)} gün**: tedarikçilere ödeme süresi ({ui.num(dpo, 0)} gün) "
                       f"stok ve alacakların nakde dönme süresinden uzun; işletme sermayesi tedarikçilerce finanse ediliyor. "
                       "Bu yapı büyüme döneminde nakit yaratır, satışlar yavaşlarsa tersine dönebilir.")
        else:
            out.append(f"Nakit dönüşüm döngüsü **{ui.num(ccc, 0)} gün**: stok ({ui.num(dio, 0)} gün) ve alacaklar ödeme "
                       "süresinden uzun; büyüme ek işletme sermayesi finansmanı gerektirir.")
    oe, on = m("ocf_to_ebitda").value, m("ocf_to_net_income").value
    if oe is not None:
        out.append(f"İşletme nakdi FAVÖK'ün **{ui.num(oe, 2)} katı**" + (
            "; faaliyet kârı nakde dönüyor." if oe >= 1 else "; kârın bir bölümü işletme sermayesine ya da vergiye gidiyor."))
    if on is not None and on < 0:
        out.append("Net kâr ile işletme nakdi zıt işaretli; kâr kalitesi ve tahakkuklar incelenmeli.")
    f, ce = m("fcf").value, m("capex_to_da").value
    if f is not None:
        out.append(("Serbest nakit akışı **pozitif**: işletme nakdi sabit sermaye yatırımlarını karşıladı." if f >= 0 else
                    "Serbest nakit akışı **negatif**: yatırımlar işletme nakdini aştı; fark borç, nakit veya özkaynakla finanse edildi."))
    if ce is not None:
        out.append(f"CapEx amortismanın **{ui.num(ce, 2)} katı**" + (" (kapasite büyütme yönünde)." if ce > 1.2 else
                                                                      " (ağırlıkla yenileme düzeyinde)." if ce >= 0.8 else
                                                                      " (amortismanın altında yatırım)."))
    if P.tms29:
        out.append("TMS 29 döneminde nakit akış kalemleri de dönem sonu fiyatıyla ifade edilir; oranlar aynı kolon içinde tutarlıdır.")
    return out or ["Yorum için yeterli veri yok."]


# =================================================================================================
# 5. Likidite, borçluluk ve risk
# =================================================================================================
def page_risk():
    co, P, scale, trend = _c()
    ui.page_head("Likidite, borçluluk ve risk", co, P)
    ui.note("Eşikler sektörden bağımsız kesin ölçüt değildir: örneğin gıda perakendesinde negatif nakit döngüsü nedeniyle "
            "cari oranın 1'in altında olması olağandır. Değerleri sektör karşılaştırması sayfasıyla birlikte okuyun.")
    ui.section("Likidite")
    ui.kpi_row(co, ["current_ratio", "quick_ratio", "cash_ratio", "nwc"], P, scale, trend)
    ui.note("<b>Asit-test oranı</b> tanımı: (dönen varlıklar − stoklar) / kısa vadeli yükümlülükler. Peşin ödenmiş giderler "
            "kaynakta ayrı verilmediği için düşülmez. <b>Nakit oranı</b>: yalnız nakit ve nakit benzerleri.")
    ui.section("Borçluluk", "Finansal borç (faizli) ile toplam yükümlülükler ayrı gösterilir")
    ui.kpi_row(co, ["fin_debt_to_equity", "liab_to_equity", "nd_ebitda", "liab_to_assets"], P, scale, trend)
    ui.section("Faiz karşılama ve vade yapısı")
    ui.kpi_row(co, ["int_cov_ebit", "int_cov_ebitda", "st_debt_share", "fin_debt"], P, scale, trend)
    ui.note("Faiz karşılama paydası kaynaktaki <b>net</b> finansman gelir/gideridir (3HC); kur farkı ve TMS 29 parasal "
            "kazanç/kayıplarını içerebilir, saf faiz gideri değildir. Satır net gelir gösteriyorsa oran hesaplanmaz. "
            "EBIT = finansman gideri öncesi faaliyet kârı (3HACA); FAVÖK = net faaliyet kârı + amortisman (hesaplanan).")
    sd = co.metric("st_debt_share", P).value
    if sd is not None and sd > 0.6:
        st.warning(f"Vade uyarısı: finansal borcun %{sd * 100:.0f}'ı kısa vadeli (12 ay içinde). Yeniden finansman ve faiz "
                   "riski açısından izlenmeli.", icon="⚠️")
    c1, c2 = st.columns(2)
    with c1:
        ui.section("Likidite trendi")
        ui.show(ui.line_chart(co, ["current_ratio", "quick_ratio", "cash_ratio"], trend, pct=False,
                              colors=[ui.BLUE, ui.TEAL, ui.ORANGE]))
    with c2:
        ui.section("Kaldıraç trendi", "Negatif net borç / FAVÖK = net nakit")
        ui.show(ui.line_chart(co, ["nd_ebitda", "fin_debt_to_equity", "liab_to_equity"], trend, pct=False,
                              colors=[ui.PINK, ui.BLUE, ui.YELLOW]))
    ui.na_note(co, ["current_ratio", "nd_ebitda", "fin_debt_to_equity", "int_cov_ebit"], trend)
    _altman(co, P)
    footer()


def _altman(co, P):
    ui.section("Altman Z''-skoru (gelişmekte olan piyasalar / imalat dışı varyantı)",
               "Z'' = 6,56·X1 + 3,26·X2 + 6,72·X3 + 1,05·X4 · yalnız yıllık dönem ve finans dışı şirketler")
    a = risk.altman_z2(co, P)
    if not a.shown:
        st.info("Gösterilmiyor: " + a.reason)
        return
    c1, c2 = st.columns([1, 2])
    with c1:
        st.markdown(f'<div class="bf-kpi" style="min-height:120px"><div class="l">Z\'\' skoru · {P.label}</div>'
                    f'<div class="v">{ui.num(a.z, 2)}</div><div class="c">{ui.esc(a.zone)}</div></div>',
                    unsafe_allow_html=True)
    with c2:
        names = {"X1": "Net işletme sermayesi / toplam varlıklar", "X2": "Birikmiş kârlar (geçmiş yıllar + dönem) / toplam varlıklar",
                 "X3": "EBIT / toplam varlıklar", "X4": "Özkaynaklar / toplam yükümlülükler"}
        df = pd.DataFrame([{"Bileşen": f"{k} · {names[k]}", "Oran": ui.num(v["değer"], 3), "Katsayı": ui.num(v["katsayı"], 2),
                            "Katkı": ui.num(v["katkı"], 2)} for k, v in a.parts.items()])
        ui.table(df)
    for c in a.caveats:
        ui.note("• " + ui.esc(c))


# =================================================================================================
# 6. Sektör karşılaştırması
# =================================================================================================
CMP_METRICS = ["gross_margin", "ebitda_margin", "net_margin", "roe", "roa", "asset_turnover", "current_ratio",
               "nd_ebitda", "fin_debt_to_equity", "ocf_to_ebitda", "ccc", "capex_to_revenue"]


def page_peers():
    co, P, scale, trend = _c()
    ui.page_head("Sektör karşılaştırması", co, P)
    grp = peers.group_of(co.ticker)
    gnames = list(peers.GROUPS)
    c1, c2 = st.columns([1, 2])
    with c1:
        g = st.selectbox("Benzer şirket grubu", gnames + ["(Özel liste)"],
                         index=gnames.index(grp) if grp in gnames else len(gnames))
    default = [t for t in peers.GROUPS.get(g, []) if t != co.ticker]
    with c2:
        extra = st.text_input("Ek BIST kodları (virgülle)", "", help="Gruba eklenecek kodlar. Banka/sigorta formatındaki "
                                                                       "şirketler otomatik dışlanır.")
    tickers = [co.ticker] + default + [t.strip().upper() for t in extra.split(",") if t.strip()]
    tickers = list(dict.fromkeys(tickers))
    ui.note("Gruplar elle hazırlanmıştır; resmî sektör sınıflandırması değildir (kaynak sektör bilgisi vermez). "
            "Varsayılan olarak seçili şirketin grubu kullanılır. Yalnız aynı dönemi (aynı uzunluk ve tarih) olan reel sektör "
            "şirketleri karşılaştırılır; TL büyüklükler karşılaştırılmaz, oranlar kullanılır.")
    loaded, cov = {}, []
    load = CTX["load"]
    with st.spinner("Benzer şirket verileri yükleniyor…"):
        for t in tickers:
            try:
                o = load(t)
            except Exception as e:  # noqa: BLE001
                cov.append({"Şirket": t, "Durum": "Dışlandı", "Son dönem": "—", "Not": str(e)[:160]})
                continue
            ok, iss = peers.compatibility(co, o, P.label)
            cov.append({"Şirket": f"{o.name} ({t})", "Durum": "Karşılaştırmada" if ok else "Dışlandı",
                        "Son dönem": o.period_labels[-1], "Not": "; ".join(iss) or "uyumlu"})
            if ok:
                loaded[t] = o
    ui.section("Kapsam", f"{P.label} dönemi için {len(loaded)} / {len(tickers)} şirket karşılaştırmada")
    ui.table(pd.DataFrame(cov))
    if len(loaded) < 2:
        st.info("Karşılaştırma için aynı dönemi olan en az iki şirket gerekir. Ek kod girin ya da başka bir dönem seçin.")
        footer()
        return
    sel = st.multiselect("Gösterilecek oranlar", CMP_METRICS, default=CMP_METRICS[:6],
                         format_func=lambda k: M.BY_ID[k].name)
    names = [o.name for o in loaded.values()]
    rows = []
    for k in sel:
        rec = {"Oran": M.BY_ID[k].name, "_tip": M.BY_ID[k].formula}
        vals = []
        for t, o in loaded.items():
            r = o.metric(k, P)
            rec[o.name] = (r.value, r.unit, r.reason)
            if r.value is not None:
                vals.append(r.value)
        med = sorted(vals)[len(vals) // 2] if len(vals) % 2 else (sum(sorted(vals)[len(vals) // 2 - 1:len(vals) // 2 + 1]) / 2 if vals else None)
        rec["Grup medyanı"] = (med, M.BY_ID[k].unit, "") if vals else (None, M.BY_ID[k].unit, "değer yok")
        rows.append(rec)

    def fmt(v, r):
        val, unit, why = v
        if val is None:
            return f'<span title="{ui.esc(why)}" style="color:#8C9AC0">n.a.</span>', False
        return ui.fmt_value(val, unit), val < 0
    ui.section("Oran tablosu", f"{P.label} · n.a. üzerine gelince neden hesaplanamadığı görünür")
    st.markdown(ui.simple_table_html(pd.DataFrame(rows), "Oran", names + ["Grup medyanı"], fmt), unsafe_allow_html=True)

    cols = st.columns(2)
    for i, k in enumerate(sel):
        unit = M.BY_ID[k].unit
        xs, ys, cs, tx = [], [], [], []
        for t, o in loaded.items():
            v = o.metric(k, P).value
            xs.append(o.name)
            ys.append(v)
            cs.append(ui.BLUE if t == co.ticker else "#5A6C9C")
            tx.append(ui.fmt_value(v, unit) if v is not None else "n.a.")
        fig = go.Figure(go.Bar(x=xs, y=ys, marker_color=cs, text=tx, textposition="outside",
                               hovertemplate="%{x}: %{text}<extra></extra>"))
        med = rows[i]["Grup medyanı"][0]
        if med is not None:
            fig.add_hline(y=med, line_dash="dot", line_color=ui.YELLOW, annotation_text="medyan",
                          annotation_font_color=ui.YELLOW)
        ui.style_fig(fig, 260, legend=False, yfmt=".0%" if unit == "pct" else None)
        with cols[i % 2]:
            ui.section(M.BY_ID[k].name, f"{co.name} mavi; diğerleri gri (etiketli)")
            ui.show(fig)
    footer()


# =================================================================================================
# 7. Finansal tablolar
# =================================================================================================
def page_statements():
    co, P, scale, trend = _c()
    ui.page_head("Finansal tablolar", co, P)
    allp = [p for p in co.periods if p.key <= P.key]
    c1, c2, c3, c4 = st.columns([2, 1.4, 1, 1])
    with c1:
        kind = st.radio("Dönem seti", ["Yıllık", "Aynı çeyrek (YTD)", "Ardışık çeyrekler"], horizontal=True,
                        help="Akış tablolarında farklı uzunluktaki YTD dönemleri yan yana yorumlanmamalıdır.")
    if kind == "Yıllık":
        pool = [p for p in allp if p.is_annual]
    elif kind == "Aynı çeyrek (YTD)":
        pool = [p for p in allp if p.month == P.month]
    else:
        pool = allp
    pool = pool or allp
    with c2:
        mode = st.selectbox("Görünüm", statements.MODES,
                            help="Yatay: önceki aynı uzunluktaki döneme göre değişim. Dikey: gelir tablosunda hasılata, "
                                 "bilançoda toplam varlıklara oran.")
    with c3:
        n = st.number_input("Dönem sayısı", 2, 12, 5)
    with c4:
        lvl = st.selectbox("Ayrıntı", ["Tüm kalemler", "Ana kalemler"], index=0)
    periods = pool[-int(n):]
    labels = [p.label for p in periods]
    hide = st.toggle("Boş satırları gizle", True)
    if kind == "Ardışık çeyrekler":
        ui.note("⚠ Gelir ve nakit akış tablosu kolonları YTD (yıl başından itibaren birikimli) tutarlardır; farklı uzunluktaki "
                "kolonlar karşılaştırılmaz. Yatay analiz her zaman aynı uzunluktaki önceki döneme göre yapılır.")
    tabs = st.tabs(["Gelir tablosu", "Bilanço", "Nakit akış", "Özkaynak değişimi", "Dipnot bilgileri"])
    for tab, stmt in zip(tabs, ["IS", "BS", "CF", "EQ", "MEMO"]):
        with tab:
            if stmt == "EQ":
                _equity_tab(co, periods, scale)
                continue
            m = mode if not (stmt == "MEMO" and mode == "Dikey (%)") else "Tutar"
            if stmt == "CF" and mode == "Dikey (%)":
                ui.note("Nakit akış tablosunda dikey analiz hasılata oran olarak verilir.")
            df, notes = statements.build(co, stmt, periods, m, hide_empty=hide, max_level=9 if lvl == "Tüm kalemler" else 0)
            unit = "%" if m in ("Yatay (%)", "Dikey (%)") else ui.scale_name(scale)
            ui.note(f"<b>{statements.NAMES[stmt]}</b> · {m} · birim: {unit} · para birimi TRY · "
                    f"{'bilanço tarihi itibarıyla' if stmt == 'BS' else 'YTD akış'} · kaynak: {ui.esc(SOURCE_NAME)}. "
                    "Kalem adının üzerine gelince formül/kaynak kodu görünür; ⚠ işaretli kolon başlıkları karşılaştırma uyarısı taşır.")
            st.markdown(ui.statement_html(df, labels, m, scale, notes, ui.row_titles(stmt)), unsafe_allow_html=True)
            if notes:
                bad = {k: v for k, v in notes.items() if v not in COMPARABLE_AMOUNTS}
                if bad:
                    ui.note("Yatay analizde boş bırakılan kolonlar: " + "; ".join(f"{k}: {COMP_TEXT[v]}" for k, v in bad.items()))
            _drill(co, df, periods, scale, stmt)
            st.download_button("Bu tabloyu CSV indir", df.drop(columns=["Tür"]).to_csv(index=False).encode("utf-8-sig"),
                               f"{co.ticker}_{stmt}_{m}.csv".replace(" ", "_").replace("(", "").replace(")", "").replace("%", "yuzde"),
                               "text/csv", key=f"dl_{stmt}")
    footer()


def _drill(co, df, periods, scale, stmt):
    codes = [c for c in df["Kod"] if c]
    if not codes:
        return
    lab = dict(zip(df["Kod"], df["Kalem"]))
    code = st.selectbox("Satır ayrıntısı (formül, alt kalemler, köken)", ["—"] + codes,
                        format_func=lambda c: c if c == "—" else f"{lab.get(c, c)} ({c})", key=f"drill_{stmt}")
    if code == "—":
        return
    d = statements.row_detail(co, code, periods)
    with st.container(border=True):
        st.markdown(f"**{d['etiket']}** · kod `{d['kod']}` · {d['tür']}")
        st.markdown(f"**Formül / kimlik:** {d['formül']}")
        st.markdown(f"**Kaynak kalem adı:** {d['kaynak_adı'] or '—'} · **Standart anahtar:** {d['standart_anahtar'] or '—'}")
        st.caption(d["işaret"])
        if d["alt_kalemler"]:
            from bistfa import catalog as C
            sub = pd.DataFrame([{"Alt kalem": f"{C.LABEL.get(k, k)} ({k})",
                                 **{p.label: ui.num(v / scale, 1) if (v := co.value(k, p.label)) is not None else "—"
                                    for p in periods}} for k in d["alt_kalemler"]])
            st.markdown(f"Alt kalemler ({ui.scale_name(scale)}):")
            ui.table(sub)
        v = d["değerler"].copy()
        if len(v):
            v["value"] = v["value"].map(lambda x: ui.num(x / scale, 1))
            v.columns = ["Dönem", f"Değer ({ui.scale_name(scale)})", "Nitelik", "Fiyat bazı", "Tür", "Kaynak", "Alınma", "Kapsam"]
            ui.table(v)


def _equity_tab(co, periods, scale):
    years = [p for p in periods if p.is_annual] or periods
    bal, mv = statements.equity_statement(co, years)
    labels = [p.label for p in years]
    ui.note("Kaynak özkaynak değişim tablosu yayımlamaz. Aşağıdaki tablo <b>kurulmuştur</b>: bileşen bakiyeleri bilançodan, "
            "hareketler gelir tablosu (dönem kârı) ve nakit akış tablosundan (temettü, sermaye artırımı) alınır; "
            "'Diğer hareketler' kalan farktır (diğer kapsamlı gelir, azınlık işlemleri, geri alınan paylar ve TMS 29 "
            "döneminde açılış bakiyesinin farklı fiyat bazında olmasından doğan yeniden ifade farkı).")
    ui.section("Özkaynak bileşenleri", f"Bilanço tarihi itibarıyla · {ui.scale_name(scale)}")
    b = bal.assign(Tür=lambda d: d["Kod"].map(lambda c: "total" if c in ("2N", "2O") else ("derived" if c.startswith("D_") else "line")),
                   Düzey=lambda d: d["Kod"].map(lambda c: 0 if c in ("2N",) else (1 if c in ("2O", "2ODA") else 2)))
    st.markdown(ui.statement_html(b, labels, "Tutar", scale, titles=ui.row_titles("BS")), unsafe_allow_html=True)
    ui.section("Hareket mutabakatı", "Açılış + dönem kârı + temettü + sermaye artırımı + diğer = kapanış")
    m = mv.assign(Kod="", Düzey=0, Tür=["total", "line", "line", "line", "derived", "total"])
    st.markdown(ui.statement_html(m, labels, "Tutar", scale), unsafe_allow_html=True)
    if any(p.tms29 for p in years):
        ui.note("TMS 29 yıllarında açılış bakiyesi kaynakta önceki yıl sonu fiyatıyla durduğundan 'Diğer hareketler' "
                "satırı enflasyon düzeltmesi farkını da taşır ve büyük görünebilir.")


# =================================================================================================
# 8. Check-up raporu ve veri kalitesi
# =================================================================================================
def page_checkup():
    co, P, scale, trend = _c()
    ui.page_head("Check-up raporu ve veri kalitesi", co, P)
    fs = FD.evaluate(co, P)
    pos, neg = [f for f in fs if f.kind == "olumlu"], [f for f in fs if f.kind == "izlenecek"]
    na = [co.metric(d.id, P) for d in M.DEFS if co.metric(d.id, P).value is None]
    ui.section("Özet")
    st.markdown(f"{co.name}, {P.label} ({P.kind}) itibarıyla **{len(pos)} olumlu** ve **{len(neg)} izlenecek** bulgu üretti; "
                f"{len(M.DEFS)} metrikten **{len(na)}** tanesi hesaplanamadı. Kaynak: {SOURCE_NAME}; veri "
                f"{co.raw.fetched_at:%d.%m.%Y %H:%M} ({co.raw.origin}). Bulgular kurala dayalıdır; tek bir sağlık puanı "
                "üretilmez çünkü sektör duyarlı eşikler olmadan ağırlıklı puan açıklanabilir olmaz.")
    c1, c2 = st.columns(2)
    with c1:
        ui.section("Güçlü yönler")
        ui.finding_list(sorted(pos, key=lambda f: -f.severity), "+", ui.GREEN)
    with c2:
        ui.section("İzlenmesi gereken konular")
        ui.finding_list(sorted(neg, key=lambda f: -f.severity), "!", ui.RED)

    ui.section("Temel metrikler", f"{P.label} · önceki karşılaştırılabilir döneme göre")
    rows = []
    for k in report.KEY:
        r, c = co.metric(k, P), co.comparison(k, P)
        rows.append({"Metrik": r.name, "Değer": ui.fmt_value(r.value, r.unit, scale) if r.value is not None else "hesaplanamadı",
                     "Birim": ui.scale_name(scale) if r.unit == "TL" else ui.UNIT_TXT[r.unit],
                     "Karşılaştırma": f"{c['delta_text']} (vs {c['prev_period']})", "Uyarı": "; ".join(ui.metric_warnings(co, r, P)),
                     "Formül": r.formula})
    ui.table(pd.DataFrame(rows))

    ui.section("Hesaplanamayan metrikler", "Sessiz sıfır yok: her boş değerin nedeni")
    if na:
        ui.table(pd.DataFrame([{"Metrik": r.name, "Neden": r.reason} for r in na]))
    else:
        st.markdown("Yok.")

    ui.section("Veri uyarıları")
    w = [{"Dönem": p, "Uyarı": t} for p, t in sorted(co.issues.items(), key=lambda x: co.period(x[0]).key)]
    w += [{"Dönem": g, "Uyarı": "Kaynakta bu dönem yok ya da çekilemedi (eksik dönem)"} for g in co.gaps]
    if w:
        ui.table(pd.DataFrame(w))
    else:
        st.markdown("Kayıtlı uyarı yok.")

    ui.section("Veri kalitesi testleri", "Toplam kimlikleri, çeyrek makullüğü ve dönem bütünlüğü")
    ch = co.checks
    summ = ch.groupby(["grup", "sonuç"]).size().unstack(fill_value=0).reset_index()
    ui.table(summ)
    show = st.multiselect("Gösterilecek sonuçlar", sorted(ch["sonuç"].unique()),
                          default=[x for x in ["FAIL", "EXPLAINED"] if x in set(ch["sonuç"])])
    ui.table(ch[ch["sonuç"].isin(show)].drop(columns=["şirket"]))
    ui.note("PASS: kimlik ±1.000 TL içinde tutuyor. EXPLAINED: dönem kayıtlı kaynak uyarısı taşıyor. FAIL: kaynakta "
            "açıklanmamış tutarsızlık (ör. bazı şirketlerde dönem sonu nakit mutabakatı).")

    ui.section("İndir")
    annual = [p for p in co.periods if p.is_annual and p.key <= P.key][-6:]
    plist = list(dict.fromkeys(annual + ([P] if not P.is_annual else [])))
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.download_button("Excel çalışma kitabı", report.excel(co, P, plist), f"{co.ticker}_{P.label.replace('/', '-')}_analiz.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with c2:
        st.download_button("Check-up raporu (HTML → PDF)", report.html_report(co, P).encode("utf-8"),
                           f"{co.ticker}_{P.label.replace('/', '-')}_checkup.html", "text/html",
                           help="Tarayıcıda açıp Yazdır → PDF olarak kaydet ile PDF alınır.")
    with c3:
        st.download_button("Oranlar (CSV)", report.metrics_frame(co, plist).to_csv(index=False).encode("utf-8-sig"),
                           f"{co.ticker}_oranlar.csv", "text/csv")
    with c4:
        st.download_button("Veri modeli (CSV, uzun)", co.facts.to_csv(index=False).encode("utf-8-sig"),
                           f"{co.ticker}_veri_modeli.csv", "text/csv")
    footer()


def footer():
    co = CTX["co"]
    st.markdown(f'<div class="bf-foot"><b>Kaynak:</b> {ui.esc(SOURCE_NAME)} · veri {co.raw.fetched_at:%d.%m.%Y %H:%M} '
                f'({ui.esc(co.raw.origin)}) · <a href="{kap_url(co.ticker)}" target="_blank">KAP bildirim sorgu</a><br>'
                f'{ui.esc(SOURCE_NOTE)} Kapsam: kaynakta belirtilmemiş (tek seri; solo/konsolide karıştırılmaz). '
                'TMS 29 döneminde (2023/12 ve sonrası) her kolon kendi dönem sonu satın alma gücüyle ifade edilir; '
                'yıllar arası TL değişimleri nominaldir, reel büyüme gösterilmez. Yatırım tavsiyesi değildir.</div>',
                unsafe_allow_html=True)
