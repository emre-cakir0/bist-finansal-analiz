"""
Arayüz yardımcıları: tema, sayı biçimleri, metrik kartları (formül açıklama katmanıyla), grafik stili ve
finansal tablo HTML'i. Hesaplama yapmaz; tüm değerler bistfa'dan gelir.
"""
from __future__ import annotations

import html
import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from bistfa import catalog as C
from bistfa.periods import COMP_TEXT, Period

# --- tema (koyu gri zemin, beyaz metin, lime vurgu; HTML dashboard ile aynı palet) ------------------
BG, SIDE, CARD, LINE, INK, MUTE = "#0F100F", "#131413", "#1B1C1B", "#2B2D2A", "#FFFFFF", "#9A9E96"
ACCENT, ON_ACCENT = "#C8FF32", "#10110F"
# Seri renkleri sabit sırayla atanır: C1 lime (birincil), C2 mavi, C3 gri, C4 pembe, C5 amber
C1, C2, C3, C4, C5 = "#C8FF32", "#3987E5", "#A4A8A0", "#D55181", "#C98500"
RED, GREEN = "#FF7F7F", "#C8FF32"
SERIES = [C1, C2, C3, C4, C5, "#7FB2F0", "#E6A0BC", "#D9B45A"]
GRID = "#262825"

SCALES = {"Milyon TL": 1e6, "Milyar TL": 1e9, "Bin TL": 1e3}
PER_SHARE = {"3ZD"}   # hisse başına tutarlar ölçeklenmez
UNIT_TXT = {"pct": "%", "x": "x", "days": "gün", "ratio": "oran"}

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Instrument+Serif:ital@0;1&display=swap');
.stApp {{ background:radial-gradient(ellipse 1000px 420px at 60% -120px, rgba(200,255,50,.12), transparent 70%) no-repeat fixed, {BG}; }}
.stApp, .stApp p, .stApp label, .stApp li, .stApp td, .stApp th, .stApp input, .stApp textarea, .stApp button,
.stApp [data-baseweb="select"] {{ font-family:Inter,"Segoe UI",system-ui,sans-serif; }}
.bf-navh {{ font-size:10.5px; letter-spacing:.12em; font-weight:700; color:{MUTE}; margin:14px 0 2px; padding-top:14px; border-top:1px solid {LINE}; }}
.bf-navsep {{ border-top:1px solid {LINE}; margin:10px 0 6px; }}
.bf-navcur {{ background:{ACCENT}; color:{ON_ACCENT}; font-weight:600; font-size:14.5px; border-radius:10px; padding:8px 10px; margin:0 0 8px; }}
section[data-testid="stSidebar"] [data-testid="stPageLink"] {{ margin:-6px 0; }}
section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] {{ border-radius:10px; padding:7px 10px; }}
section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover {{ background:rgba(255,255,255,.07); }}
.bf-lead {{ display:flex; gap:24px; align-items:center; flex-wrap:wrap; background:rgba(255,255,255,.045); border:1px solid rgba(255,255,255,.09);
           border-left:3px solid {ACCENT}; border-radius:14px; padding:18px 20px; margin:4px 0 14px; }}
.bf-lead .m {{ flex:1; min-width:280px; }}
.bf-lead .t {{ font-size:10.5px; letter-spacing:.12em; font-weight:700; color:{MUTE}; }}
.bf-lead h2 {{ margin:4px 0 4px; padding:0; font-family:'Instrument Serif',Georgia,serif; font-size:29px; font-weight:400; line-height:1.2; color:{INK}; }}
.bf-lead h2 em {{ color:{ACCENT}; font-style:italic; }}
.bf-lead .s {{ font-size:13px; color:{MUTE}; }}
.bf-lead .k {{ display:flex; gap:30px; border-left:1px solid {LINE}; padding-left:24px; flex-wrap:wrap; }}
.bf-lead .k b {{ font-size:21px; font-weight:650; color:{INK}; font-variant-numeric:tabular-nums; }}
.bf-lead .k span {{ font-size:12.5px; margin-left:8px; font-weight:500; white-space:nowrap; }}
.bf-lead .k .t {{ display:block; margin-bottom:2px; }}
.stApp a {{ color:{ACCENT}; }}
.bf-read {{ display:flex; gap:10px; align-items:flex-start; border:1px solid {LINE}; border-left:3px solid {MUTE}; border-radius:10px;
           background:rgba(255,255,255,.03); padding:9px 14px; margin:6px 0 12px; font-size:13px; color:#CBCEC7; line-height:1.5; }}
.bf-read b {{ color:{INK}; font-weight:600; }}
.bf-read .t {{ font-size:10.5px; letter-spacing:.1em; font-weight:700; color:{MUTE}; display:block; }}
section[data-testid="stSidebar"] {{ background:{SIDE}; border-right:1px solid {LINE}; }}
header[data-testid="stHeader"] {{ background:transparent; }}
.block-container {{ padding-top:2.6rem; padding-bottom:2rem; max-width:1480px; }}
h1,h2,h3,h4 {{ color:{INK}; }}
.bf-head {{ display:flex; justify-content:space-between; align-items:flex-end; gap:14px; flex-wrap:wrap; margin-bottom:6px; }}
.bf-title {{ font-family:'Instrument Serif',Georgia,serif; font-size:40px; font-weight:400; color:{INK}; line-height:1.1; }}
.bf-sub {{ font-size:13px; color:{MUTE}; margin-top:4px; }}
.bf-chips {{ display:flex; gap:6px; flex-wrap:wrap; }}
.bf-chip {{ font-size:12px; padding:4px 9px; border-radius:7px; border:1px solid {LINE}; color:{INK}; background:{CARD}; white-space:nowrap; }}
.bf-chip.warn {{ border-color:#8A5A1F; color:#FFC58A; background:#2A2112; }}
.bf-chip.bad {{ border-color:#8A3B3B; color:#FFB4B4; background:#2E1820; }}
.bf-chip.info {{ border-color:#3A3D38; color:#D6DAD0; background:#1E201D; }}
.bf-kpi {{ background:rgba(255,255,255,.045); border:1px solid rgba(255,255,255,.09); border-radius:16px; padding:11px 13px 0; height:178px;
          position:relative; overflow:hidden; }}
.bf-kpi .l {{ font-size:12.5px; color:{MUTE}; }}
.bf-kpi .v {{ font-size:25px; font-weight:700; color:{INK}; margin-top:2px; font-variant-numeric:tabular-nums; }}
.bf-kpi .v.na {{ font-size:16px; color:{MUTE}; font-weight:600; margin-top:8px; }}
.bf-kpi .d {{ font-size:12px; margin-top:2px; }}
.bf-kpi .c {{ font-size:11px; color:{MUTE}; margin-top:2px; }}
.bf-kpi .w {{ font-size:11px; color:#FFC58A; margin-top:3px; line-height:1.35; }}
.bf-kpi svg {{ position:absolute; left:0; right:0; bottom:0; width:100%; height:30px; }}
.bf-kpi .sp {{ height:34px; }}
.bf-card {{ background:{CARD}; border:1px solid {LINE}; border-radius:12px; padding:12px 16px; margin-bottom:10px; }}
.bf-find {{ display:flex; gap:10px; margin:8px 0; font-size:13.5px; line-height:1.5; color:{INK}; }}
.bf-find .ic {{ font-weight:700; width:18px; flex-shrink:0; text-align:center; }}
.bf-find .r {{ font-size:12px; color:{MUTE}; }}
.bf-note {{ font-size:12px; color:{MUTE}; line-height:1.5; margin:4px 0 10px; }}
.bf-sec {{ font-size:17px; font-weight:650; color:{INK}; margin:14px 0 2px; }}
.bf-secsub {{ font-size:12.5px; color:{MUTE}; margin-bottom:6px; }}
.bf-tbl-wrap {{ overflow-x:auto; border:1px solid {LINE}; border-radius:10px; background:{CARD}; max-height:640px; overflow-y:auto; }}
table.bf-tbl {{ border-collapse:separate; border-spacing:0; width:100%; font-size:13px; color:{INK}; }}
table.bf-tbl th {{ position:sticky; top:0; background:#232523; color:{INK}; font-weight:600; text-align:right; padding:7px 10px;
                   border-bottom:1px solid {LINE}; white-space:nowrap; z-index:2; }}
table.bf-tbl th:first-child {{ text-align:left; left:0; z-index:3; }}
table.bf-tbl td {{ padding:5px 10px; border-bottom:1px solid #262825; text-align:right; white-space:nowrap;
                   font-variant-numeric:tabular-nums; }}
table.bf-tbl td:first-child {{ text-align:left; position:sticky; left:0; background:{CARD}; white-space:normal; min-width:240px; max-width:380px; }}
table.bf-tbl tr.total td {{ font-weight:700; background:#222422; }}
table.bf-tbl tr.total td:first-child {{ background:#222422; }}
table.bf-tbl tr.sub td {{ font-weight:600; }}
table.bf-tbl tr.header td {{ font-weight:700; color:{MUTE}; letter-spacing:.04em; font-size:12px; background:#171817; }}
table.bf-tbl tr.header td:first-child {{ background:#171817; }}
table.bf-tbl tr.derived td {{ font-style:italic; color:#D9DDD3; }}
table.bf-tbl tr:hover td {{ background:#2A2D29; }}
table.bf-tbl td.neg {{ color:#FFB4B4; }}
.bf-tag {{ font-size:10.5px; font-style:normal; border:1px solid #3A3D38; color:#D6DAD0; border-radius:5px; padding:0 5px; margin-left:6px; }}
.bf-code {{ color:{MUTE}; font-size:11px; margin-left:6px; }}
.bf-foot {{ font-size:11.5px; color:{MUTE}; margin-top:18px; line-height:1.55; border-top:1px solid {LINE}; padding-top:10px; }}
div[data-testid="stTabs"] button p {{ font-size:14px; }}
@media (max-width: 700px) {{
  .block-container {{ padding-left:1rem; padding-right:1rem; }}
  .bf-title {{ font-size:30px; }}
  .bf-kpi .v {{ font-size:21px; }}
}}
</style>"""


# --- biçimler --------------------------------------------------------------------------------------
def num(v, d=1):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    s = f"{abs(v):,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("−" if v < 0 else "") + s


def fmt_value(v, unit: str, scale: float = 1e6, short=False) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    if unit == "TL":
        return num(v / scale, 1)
    if unit == "pct":
        return ("−%" if v < 0 else "%") + num(abs(v) * 100, 1)
    if unit == "x":
        return num(v, 2) + "x"
    if unit == "days":
        return num(v, 1) + ("" if short else " gün")
    return num(v, 2)


def scale_name(scale: float) -> str:
    return {1e6: "milyon TL", 1e9: "milyar TL", 1e3: "bin TL"}[scale]


def esc(x) -> str:
    return html.escape(str(x), quote=True)


# --- yerleşim parçaları ----------------------------------------------------------------------------
def page_head(title: str, co, P: Period, extra_chips: list[tuple[str, str]] | None = None):
    chips = [(f"{P.label} · {P.kind}", ""), (co.basis_text(P).split(" (")[0], "info")]
    chips += extra_chips or []
    ch = "".join(f'<span class="bf-chip {k}">{esc(t)}</span>' for t, k in chips)
    st.markdown(f'<div class="bf-head"><div><div class="bf-title">{esc(title)}</div>'
                f'<div class="bf-sub">{esc(co.name)} ({esc(co.ticker)}) · dönem sonu {P.end:%d.%m.%Y}</div></div>'
                f'<div class="bf-chips">{ch}</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="bf-read"><div><span class="t">NASIL OKUNUR</span>{reading_note(co, P)}</div></div>',
                unsafe_allow_html=True)


def lead(co, P: Period):
    """Dönemin özeti: sayfanın en önemli bulgusu tek cümlede, yanında üç gösterge. Değerlerden kurala dayalı üretilir."""
    rev, gm, nm = co.comparison("revenue", P), co.comparison("gross_margin", P), co.comparison("net_margin", P)
    g, dg, dn = rev["delta"], gm["delta"], nm["delta"]
    gmv, nmv = gm["cur"].value, nm["cur"].value
    a = None
    if g is not None and rev["comp"] in ("REAL", "NOMINAL", "NOMINAL_TMS29"):
        word = "reel olarak" if rev["comp"] == "REAL" else "nominal"
        a = f"Hasılat {word} <em>%{num(abs(g) * 100, 1)} {'büyüdü' if g >= 0 else 'daraldı'}</em>"
    if dg is None:
        b = f"brüt marj {fmt_value(gmv, 'pct')}" if gmv is not None else ""
    else:
        b = "brüt marj yatay" if abs(dg) < 0.003 else ("brüt marj güçlendi" if dg > 0 else "brüt marj geriledi")
    if nmv is None:
        c = ""
    elif nmv < 0:
        c = "dönem zararla kapandı"
    elif dn is None:
        c = f"net marj {fmt_value(nmv, 'pct')}"
    else:
        c = "net marj yatay" if abs(dn) < 0.003 else ("net marj iyileşti" if dn > 0 else "net marj daraldı")
    parts = [x for x in ([a, b] if a else [b, c]) if x]
    if a and nmv is not None and nmv < 0:
        parts = [a, c]
    msg = "; ".join(parts) + "." if parts else "Bu dönem için özet üretilemedi."
    msg = msg[0].upper() + msg[1:]

    def mini(label, value, delta=None, unit="pct"):
        if value is None:
            return f'<div><span class="t">{label}</span><b>—</b></div>'
        d = ""
        if delta is not None:
            z = abs(delta) < 0.0005
            col = MUTE if z else (GREEN if delta > 0 else RED)
            d = f'<span style="color:{col}">{"■" if z else ("▲" if delta > 0 else "▼")} {num(abs(delta) * 100, 1)} puan</span>'
        return f'<div><span class="t">{label}</span><b>{value}</b>{d}</div>'
    minis = ""
    if a:
        minis += mini("REEL BÜYÜME" if rev["comp"] == "REAL" else "NOMİNAL BÜYÜME", ("+" if g >= 0 else "−") + "%" + num(abs(g) * 100, 1))
    minis += mini("BRÜT MARJ", fmt_value(gmv, "pct") if gmv is not None else None, dg)
    minis += mini("NET MARJ", fmt_value(nmv, "pct") if nmv is not None else None, dn)
    st.markdown(f'<div class="bf-lead"><div class="m"><span class="t">DÖNEMİN ÖZETİ · {esc(P.label)}</span><h2>{msg}</h2>'
                f'<div class="s">{esc(co.name)} · {esc(P.kind)} · {esc(rev["prev_period"])} dönemine göre</div></div>'
                f'<div class="k">{minis}</div></div>', unsafe_allow_html=True)


def reading_note(co, P: Period) -> str:
    """Tutarların fiyat düzeyini tek cümleyle açıklar (uyarı değil, okuma kılavuzu)."""
    if not co.price.get("applies", True):
        txt = ("Bu şirket enflasyon muhasebesi uygulamıyor; tutarlar <b>nominal TL</b>'dir ve yıllar arası değişimler nominaldir.")
    elif co.basis == "common":
        txt = (f"Enflasyon muhasebesi dönemindeki tutarlar <b>{esc(co.basis_name)}</b> gösterilir; bu dönemlerdeki büyümeler "
               "<b>reeldir</b> (enflasyondan arındırılmış). Daha eski dönemler nominal TL'dir. Şirketin açıkladığı rakamlar için "
               "sol menüden <b>Yayımlandığı gibi</b> seçin; oranlar iki görünümde aynıdır.")
    elif co.basis == "published":
        txt = ("Tutarlar <b>şirketin açıkladığı gibidir</b>; her dönem kendi rapor tarihinin fiyat düzeyindedir, bu yüzden TL "
               "değişimleri nominaldir. Reel karşılaştırma için sol menüden <b>ortak fiyat</b> görünümünü seçin.")
    else:
        txt = "Tutarlar <b>kaynak kolonlarındaki</b> hâliyledir (dönemler farklı fiyat düzeylerinde); yalnız denetim amaçlıdır."
    if P.label in co.issues:
        txt += f" <b>Veri notu ({esc(P.label)}):</b> {esc(co.issues[P.label])}."
    if co.kinds.get(P.label) != co.kinds_bs.get(P.label):
        txt += (" Bu ara dönemde gelir tablosu sonraki raporda enflasyona göre düzeltilmiş, bilanço düzeltilmemiştir; "
                "ikisini birleştiren oranlar hesaplanmaz.")
    return txt


def section(title: str, sub: str | None = None):
    st.markdown(f'<div class="bf-sec">{esc(title)}</div>' + (f'<div class="bf-secsub">{esc(sub)}</div>' if sub else ""),
                unsafe_allow_html=True)


def note(text: str):
    st.markdown(f'<div class="bf-note">{text}</div>', unsafe_allow_html=True)


def spark_svg(vals, color):
    pts_in = [(i, x) for i, x in enumerate(vals) if x is not None and not (isinstance(x, float) and math.isnan(x))]
    if len(pts_in) < 2:
        return '<div class="sp"></div>'
    lo, hi = min(x for _, x in pts_in), max(x for _, x in pts_in)
    pad = (hi - lo) * 0.15 or abs(hi) * 0.1 or 1
    lo, hi = lo - pad, hi + pad
    n = max(len(vals) - 1, 1)
    pts = [(i / n * 100, 100 - (x - lo) / (hi - lo) * 100) for i, x in pts_in]
    line = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)
    area = line + f" L{pts[-1][0]:.1f} 100 L{pts[0][0]:.1f} 100 Z"
    return (f'<div class="sp"></div><svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">'
            f'<path d="{area}" fill="{color}" fill-opacity="0.13"></path>'
            f'<path d="{line}" fill="none" stroke="{color}" stroke-width="2" vector-effect="non-scaling-stroke"></path></svg>')


EPS = {"pct": 0.0005, "x": 0.005, "ratio": 0.005, "days": 0.05, "TL": 0.0005}   # gösterim hassasiyetinin yarısı


def tone_of(delta, better, unit="ratio"):
    if delta is not None and abs(delta) < EPS.get(unit, 1e-12):
        return MUTE, "■", "değişim yok"
    if delta is None or better is None:
        return MUTE, "■", "değişim yok" if delta is not None and abs(delta) < 1e-12 else ""
    good = (delta > 0) == (better == "up")
    return (GREEN if good else RED), ("▲" if delta > 0 else "▼"), ("olumlu yön" if good else "olumsuz yön")


def metric_warnings(co, r, P: Period, cmp_said: bool = False) -> list[str]:
    w = []
    if r.value is None:
        w.append("Hesaplanamadı: " + r.reason)
    if "dönem sonu" in (r.basis or ""):
        w.append("Ortalama yerine dönem sonu bakiyesi")
    if r.annualized:
        w.append(f"Ara dönem: × 12/{P.months} yıllıklandırıldı")
    if r.unit == "TL" and P.label in co.issues and not cmp_said:
        w.append("Veri notu: TL tutar karşılaştırması yapılmaz")
    if r.id in ("ebitda", "ebitda_margin", "nd_ebitda", "int_cov_ebitda", "ocf_to_ebitda") and r.value is not None:
        w.append("FAVÖK hesaplanmıştır (3H + 4CAB)")
    return w


def metric_card(co, mid: str, P: Period, scale: float, trend: list[Period], color=C1, show_trend=True):
    """Metrik kartı: değer, karşılaştırma (dönem ve yöntem), uyarılar, trend; altında 'Nasıl hesaplandı?' katmanı."""
    r = co.metric(mid, P)
    cmp = co.comparison(mid, P)
    unit_lbl = scale_name(scale) if r.unit == "TL" else UNIT_TXT[r.unit]
    if r.value is None:
        val = '<div class="v na">Hesaplanamadı</div>'
    else:
        val = f'<div class="v">{esc(fmt_value(r.value, r.unit, scale))}</div>'
    col, arrow, word = tone_of(cmp["delta"], r.better, r.unit)
    dtxt = cmp["delta_text"] or "—"
    if r.value is None:   # neden aşağıdaki uyarı satırında; tekrar etme
        dtxt, word = "karşılaştırma yok", ""
    elif cmp["comp"] in ("BASE_BREAK", "TMS29_GECIS") and r.unit == "TL":
        dtxt = "geçiş dönemi: önceki dönem nominal" if cmp["comp"] == "TMS29_GECIS" else "veri notu: karşılaştırılmaz"
    dline = (f'<div class="d" style="color:{col}">{arrow} {esc(dtxt)}'
             + (f' · {esc(word)}' if word and cmp["delta"] is not None else "") + '</div>')
    cline = f'<div class="c">vs {esc(cmp["prev_period"])} · birim: {esc(unit_lbl)}</div>'
    ws = metric_warnings(co, r, P, cmp_said=cmp["comp"] in ("BASE_BREAK", "TMS29_GECIS"))
    wl = "".join(f'<div class="w">⚠ {esc(x)}</div>' for x in ws[:2])
    if ws and ws[0].startswith("Hesaplanamadı") and len(ws[0]) > 60:
        wl = f'<div class="w" title="{esc(ws[0])}">⚠ {esc(ws[0][:55].rsplit(" ", 1)[0])}… (ayrıntı: Nasıl hesaplandı?)</div>'
    vals = [co.metric(mid, p).value for p in trend] if show_trend else []
    st.markdown(f'<div class="bf-kpi" title="{esc(r.formula)}"><div class="l">{esc(r.name)}</div>{val}{dline}{cline}{wl}'
                f'{spark_svg(vals, color)}</div>', unsafe_allow_html=True)
    with popover("Nasıl hesaplandı?"):
        explain(co, r, cmp, scale)


def explain(co, r, cmp=None, scale=1e6):
    st.markdown(f"**{r.name}** · {r.period}")
    st.markdown(f"**Formül:** {r.formula}")
    if r.basis:
        st.markdown(f"**Bakiye / dönem bazı:** {r.basis}")
    if r.note:
        st.markdown(f"**Not:** {r.note}")
    if r.value is None:
        st.markdown(f"**Neden hesaplanamadı:** {r.reason}")
    if r.inputs:
        df = pd.DataFrame([{"Kalem": a, "Kod": k, "Dönem": p, f"Değer ({scale_name(scale)})": num(v / scale, 1)}
                           for a, k, p, v in r.inputs])
        table(df)
    if cmp:
        st.markdown(f"**Karşılaştırma:** {cmp['prev_period']} ile. {cmp['comp_text']}.")
        if cmp["method"]:
            st.caption("Yöntem: " + cmp["method"])
    st.caption("Kaynak kalem kodları İş Yatırım XI_29 formatındadır; değerler raporlanan YTD/bilanço tarihi tutarlarıdır.")


def kpi_row(co, mids, P, scale, trend, colors=None, cols=4):
    rows = [mids[i:i + cols] for i in range(0, len(mids), cols)]
    k = 0
    for row in rows:
        cs = st.columns(cols)
        for c, mid in zip(cs, row):
            with c:
                metric_card(co, mid, P, scale, trend, (colors or SERIES)[k % len(colors or SERIES)])
            k += 1


def finding_list(fs, icon, color):
    if not fs:
        st.markdown(f'<div class="bf-note">Bu dönem için kural eşiğini geçen bulgu yok.</div>', unsafe_allow_html=True)
        return
    for f in fs:
        evid = "; ".join(f"{a} {b}: {c}" for a, b, c in f.evidence)
        st.markdown(f'<div class="bf-find"><div class="ic" style="color:{color}">{icon}</div><div><b>{esc(f.title)}</b> — '
                    f'{esc(f.text)}<div class="r">Kural: {esc(f.rule)}' + (f' · Dayanak: {esc(evid)}' if evid else "")
                    + '</div></div></div>', unsafe_allow_html=True)


# --- grafikler -------------------------------------------------------------------------------------
def style_fig(fig, height=320, legend=True, yfmt=None):
    fig.update_layout(height=height, margin=dict(l=6, r=6, t=44 if legend else 10, b=6), paper_bgcolor=CARD,
                      plot_bgcolor=CARD, font=dict(color=MUTE, family="Inter, Segoe UI, system-ui, sans-serif", size=12.5),
                      legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0, font=dict(color=INK)),
                      showlegend=legend, hoverlabel=dict(bgcolor=CARD, bordercolor=LINE, font_color=INK), bargap=0.25,
                      separators=",.")
    fig.update_xaxes(showgrid=False, linecolor=LINE, tickfont=dict(color=MUTE), type="category")
    fig.update_yaxes(gridcolor=GRID, zerolinecolor="#4A4D47", tickfont=dict(color=MUTE))
    if yfmt:
        fig.update_yaxes(tickformat=yfmt)
    return fig


def mark_periods(fig, labels: list[str], co, stock: bool = False):
    """Nominal dönemlerle enflasyona göre düzeltilmiş dönemleri ince bir ayraçla ayırır (uyarı değil, okuma yardımı)."""
    fig.update_xaxes(range=[-0.5, len(labels) - 0.5])   # açıklama metinleri autorange'i genişletmesin
    kinds = co.kinds_bs if stock else co.kinds
    ks = [kinds.get(l, "nominal") for l in labels]
    if "nominal" in ks and any(k != "nominal" for k in ks):
        i0 = next(i for i, k in enumerate(ks) if k != "nominal")
        if i0 > 0:
            fig.add_vline(x=i0 - 0.5, line_width=1, line_dash="dot", line_color="#4A4D47")
            right = (co.basis_name + " →") if co.basis == "common" else "enflasyona göre düzeltilmiş →"
            fig.add_annotation(x=i0 - 0.56, y=1.0, yref="paper", text="nominal TL", showarrow=False, xanchor="right",
                               yanchor="top", font=dict(size=10.5, color=MUTE))
            fig.add_annotation(x=i0 - 0.44, y=1.0, yref="paper", text=right, showarrow=False, xanchor="left",
                               yanchor="top", font=dict(size=10.5, color=MUTE))
    return fig


def show(fig, key=None):
    try:
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=key)
    except TypeError:  # eski Streamlit
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key=key)


def table(df, **kw):
    try:
        st.dataframe(df, hide_index=True, width="stretch", **kw)
    except TypeError:
        st.dataframe(df, hide_index=True, use_container_width=True, **kw)


def popover(label):
    try:
        return st.popover(label, width="stretch")
    except TypeError:
        return st.popover(label, use_container_width=True)


def series_vals(co, mid, periods, scale=1.0):
    out = []
    for p in periods:
        v = co.metric(mid, p).value
        out.append(None if v is None else (v / scale if co.metric(mid, p).unit == "TL" else v))
    return out


def bar_chart(co, mids, periods, scale, colors=None, height=320, relative=False):
    labels = [p.label for p in periods]
    fig = go.Figure()
    for i, mid in enumerate(mids):
        vals = series_vals(co, mid, periods, scale)
        name = co.metric(mid, periods[-1]).name
        fig.add_bar(x=labels, y=vals, name=name, marker_color=(colors or SERIES)[i % 8],
                    hovertemplate=f"{name}<br>%{{x}}: %{{y:,.1f}} {scale_name(scale)}<extra></extra>")
    if relative:
        fig.update_layout(barmode="relative")
    style_fig(fig, height)
    mark_periods(fig, labels, co, stock=all(m in ("total_assets", "total_equity", "nwc", "net_debt", "fin_debt") for m in mids))
    return fig


def line_chart(co, mids, periods, height=300, colors=None, pct=True, dash_ids=()):
    labels = [p.label for p in periods]
    fig = go.Figure()
    for i, mid in enumerate(mids):
        vals = series_vals(co, mid, periods)
        r = co.metric(mid, periods[-1])
        hover = "%{y:.1%}" if pct else ("%{y:.1f} gün" if r.unit == "days" else "%{y:.2f}")
        fig.add_scatter(x=labels, y=vals, name=r.name, mode="lines+markers", connectgaps=False,
                        line=dict(color=(colors or SERIES)[i % 8], width=2.4, dash="dot" if mid in dash_ids else None),
                        marker=dict(size=6), hovertemplate=f"{r.name}<br>%{{x}}: {hover}<extra></extra>")
    style_fig(fig, height, yfmt=".0%" if pct else None)
    fig.update_xaxes(range=[-0.5, len(labels) - 0.5])
    return fig


def na_note(co, mids, periods):
    """Grafikte boş kalan noktaların nedenleri (sessiz sıfır yok)."""
    out = []
    for mid in mids:
        for p in periods:
            r = co.metric(mid, p)
            if r.value is None:
                out.append(f"{r.name} {p.label}: {r.reason}")
    if out:
        with st.expander(f"Grafikte boş kalan {len(out)} nokta ve nedeni"):
            for x in out:
                st.markdown("- " + esc(x))


# --- tablolar --------------------------------------------------------------------------------------
def statement_html(df: pd.DataFrame, labels: list[str], mode: str, scale: float, col_notes: dict | None = None,
                   titles: dict | None = None) -> str:
    col_notes = col_notes or {}
    head = "<th>Kalem</th>"
    for l in labels:
        cn = col_notes.get(l)
        mark = " ⚠" if cn and cn not in ("NOMINAL", "NOMINAL_TMS29") else ""
        tip = COMP_TEXT.get(cn, "") if cn else ""
        head += f'<th title="{esc(tip)}">{esc(l)}{mark}</th>'
    body = []
    for _, r in df.iterrows():
        code, kind, lvl = r.get("Kod", ""), r.get("Tür", "line"), int(r.get("Düzey", 0) or 0)
        tip = (titles or {}).get(code, "")
        tag = '<span class="bf-tag">türetilmiş</span>' if kind == "derived" else ""
        codehtml = f'<span class="bf-code">{esc(code)}</span>' if code and not code.startswith("D_") else ""
        label = f'<span style="padding-left:{lvl * 16}px">{esc(r["Kalem"])}</span>{tag}{codehtml}'
        tds = [f'<td title="{esc(tip)}">{label}</td>']
        for l in labels:
            v = r.get(l)
            if kind == "header" or v is None or (isinstance(v, float) and math.isnan(v)):
                tds.append("<td></td>" if kind == "header" else '<td style="color:#6E726A">—</td>')
                continue
            if mode in ("Yatay (%)", "Dikey (%)"):
                s = ("−%" if v < 0 else "%") + num(abs(v) * 100, 1)
            elif code in PER_SHARE:
                s = num(v, 2) + " TL"
            else:
                s = num(v / scale, 1)
            tds.append(f'<td class="{"neg" if v < 0 else ""}">{s}</td>')
        body.append(f'<tr class="{esc(kind)}">' + "".join(tds) + "</tr>")
    return (f'<div class="bf-tbl-wrap"><table class="bf-tbl"><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


def simple_table_html(df: pd.DataFrame, first: str, cols: list[str], fmt) -> str:
    head = f"<th>{esc(first)}</th>" + "".join(f"<th>{esc(c)}</th>" for c in cols)
    rows = []
    for _, r in df.iterrows():
        cls = r.get("_cls", "")
        tds = [f'<td title="{esc(r.get("_tip", ""))}">{esc(r[first])}</td>']
        for c in cols:
            v = r.get(c)
            s, neg = fmt(v, r)
            tds.append(f'<td class="{"neg" if neg else ""}">{s}</td>')
        rows.append(f'<tr class="{esc(cls)}">' + "".join(tds) + "</tr>")
    return f'<div class="bf-tbl-wrap"><table class="bf-tbl"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def row_titles(stmt: str) -> dict:
    """Satır üzerine gelince gösterilen açıklama: formül/kimlik ve kaynak kodu."""
    out = {}
    for code, _, _, label in C.LAYOUTS.get(stmt, []):
        if not code:
            continue
        if code in C.DERIVED:
            out[code] = "Hesaplanan: " + C.DERIVED[code][0]
        elif code in C.IDENTITIES:
            out[code] = f"{label} ({code}) = " + " + ".join(C.LABEL.get(k, k) for k in C.IDENTITIES[code])
        else:
            out[code] = f"Kaynakta raporlanan kalem ({code})"
    return out
