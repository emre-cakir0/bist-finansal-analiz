"""
BIST Finansal Analiz — Streamlit uygulaması (v2)
Çalıştırma (proje klasöründen):  streamlit run app/app.py   ya da  app\\run_app.bat
Bir BIST kodu yazın: mali tablolar İş Yatırım'dan çekilir (önbellek / SQL projesi ham verisi önce), bistfa veri
modeline dönüştürülür; tablolar, oranlar, bulgular ve veri kalitesi 8 sayfada gösterilir.
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import ui  # noqa: E402
import views  # noqa: E402
from bistfa import company, peers  # noqa: E402
from bistfa.source import FetchError, SOURCE_NAME, SOURCE_NOTE, isyatirim_url, kap_url  # noqa: E402

st.set_page_config(page_title="BIST Finansal Analiz", page_icon="📊", layout="wide", initial_sidebar_state="expanded")
st.markdown(ui.CSS, unsafe_allow_html=True)


@st.cache_resource(show_spinner=False, max_entries=40)
def load_company(ticker: str, token: int):
    return company.load(ticker, token)


ss = st.session_state
ss.setdefault("refresh", {})

PAGES = [
    st.Page(views.page_summary, title="Yönetici özeti", icon="🧭", url_path="ozet", default=True),
    st.Page(views.page_balance, title="Finansal durum", icon="🏦", url_path="bilanco"),
    st.Page(views.page_performance, title="Performans ve kârlılık", icon="📈", url_path="performans"),
    st.Page(views.page_cash, title="Nakit akışı ve işletme sermayesi", icon="💧", url_path="nakit"),
    st.Page(views.page_risk, title="Likidite, borçluluk ve risk", icon="🛡️", url_path="risk"),
    st.Page(views.page_peers, title="Sektör karşılaştırması", icon="🏷️", url_path="sektor"),
    st.Page(views.page_statements, title="Finansal tablolar", icon="📑", url_path="tablolar"),
    st.Page(views.page_checkup, title="Check-up ve veri kalitesi", icon="✅", url_path="checkup"),
]
nav = st.navigation(PAGES, position="sidebar")

# --- kenar çubuğu: şirket ve dönem seçimi -------------------------------------------------------
with st.sidebar:
    st.markdown(f'<div style="font-size:19px;font-weight:700;color:{ui.INK}">BIST Finansal Analiz</div>'
                f'<div style="font-size:12px;color:{ui.MUTE};margin-bottom:8px">Mali tablo analizi · reel sektör</div>',
                unsafe_allow_html=True)
    opts = [f"{t} — {n}" for t, n in peers.NAMES.items()]
    pick = st.selectbox("Şirket (kod yazıp Enter)", opts, index=opts.index(ss.get("pick", opts[0])) if ss.get("pick") in opts else 0,
                        accept_new_options=True, help="Listede olmayan bir BIST kodunu yazıp Enter'a basabilirsiniz.")
    ss["pick"] = pick
    ticker = pick.split("—")[0].strip().upper()

    token = ss["refresh"].get(ticker, 0)
    try:
        with st.spinner(f"{ticker} yükleniyor…"):
            co = load_company(ticker, token)
    except FetchError as e:
        st.error(str(e))
        st.stop()
    except Exception as e:  # noqa: BLE001
        st.error(f"{ticker} yüklenemedi: {type(e).__name__}: {e}")
        st.stop()

    ptype = st.radio("Dönem türü", ["Yıllık", "Ara dönem (YTD)"], horizontal=True,
                     help="Ara dönem kolonları yıl başından itibaren birikimlidir (3, 6, 9 ay). Getiri ve gün oranları "
                          "yıllıklandırılır; trendler aynı uzunluktaki dönemlerle kurulur.")
    pool = co.annual_periods() if ptype == "Yıllık" else [p for p in co.periods if not p.is_annual]
    if not pool:
        pool = co.periods
        st.caption("Bu türde dönem yok; tüm dönemler listelendi.")
    labels = [p.label for p in pool][::-1]
    plabel = st.selectbox("Dönem", labels, index=0,
                          format_func=lambda l: l + ("  ⚠" if l in co.issues else ""))
    P = co.period(plabel)
    scale_lbl = st.selectbox("Tutar ölçeği", list(ui.SCALES), index=0)
    trend_n = st.slider("Trend uzunluğu (dönem)", 3, 8, 7)

    st.markdown(f'<div style="font-size:12px;color:{ui.MUTE};line-height:1.5;margin-top:6px">'
                f'<b>Veri:</b> {co.raw.origin}, {co.raw.fetched_at:%d.%m.%Y %H:%M}<br>'
                f'<b>Dönemler:</b> {co.period_labels[0]} – {co.period_labels[-1]} ({len(co.periods)})<br>'
                f'<b>Kapsam:</b> kaynakta belirtilmemiş, tek seri<br><b>Para birimi:</b> TRY</div>', unsafe_allow_html=True)
    if st.button("Veriyi kaynaktan yenile",
                 help="İş Yatırım'dan yeniden çeker ve önbelleği günceller (internet gerekir)."):
        ss["refresh"][ticker] = token + 1
        st.rerun()
    st.markdown(f'<div style="font-size:12px;margin-top:4px"><a href="{kap_url(ticker)}" target="_blank">KAP bildirim sorgu</a> · '
                f'<a href="{isyatirim_url(ticker)}" target="_blank">İş Yatırım şirket kartı</a></div>', unsafe_allow_html=True)
    st.caption(SOURCE_NOTE)

trend = [p for p in co.periods if p.month == P.month and p.key <= P.key][-trend_n:]
views.CTX.update(co=co, P=P, scale=ui.SCALES[scale_lbl], trend=trend, load=lambda t: load_company(t, ss["refresh"].get(t, 0)))
nav.run()
