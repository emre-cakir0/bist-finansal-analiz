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

# --- tema (koyu lacivert; Power BI ve HTML dashboard ile aynı palet) --------------------------------
BG, SIDE, CARD, LINE, INK, MUTE = "#0C1636", "#101C42", "#15234C", "#26386B", "#EDF2FC", "#A3B2D1"
BLUE, TEAL, ORANGE, PINK, YELLOW, RED, GREEN = "#5B9BFF", "#3DD6C3", "#FFA94D", "#E0569A", "#FFD166", "#FF8A8A", "#4ADE80"
SERIES = [BLUE, ORANGE, TEAL, PINK, YELLOW, "#93C5FD", "#86EFAC", "#C4B5FD"]
GRID = "#1E2D5A"

SCALES = {"Milyon TL": 1e6, "Milyar TL": 1e9, "Bin TL": 1e3}
PER_SHARE = {"3ZD"}   # hisse başına tutarlar ölçeklenmez
UNIT_TXT = {"pct": "%", "x": "x", "days": "gün", "ratio": "oran"}

CSS = f"""
<style>
.stApp {{ background:{BG}; }}
section[data-testid="stSidebar"] {{ background:{SIDE}; border-right:1px solid {LINE}; }}
header[data-testid="stHeader"] {{ background:transparent; }}
.block-container {{ padding-top:2.6rem; padding-bottom:2rem; max-width:1480px; }}
h1,h2,h3,h4 {{ color:{INK}; }}
.bf-head {{ display:flex; justify-content:space-between; align-items:flex-end; gap:14px; flex-wrap:wrap; margin-bottom:6px; }}
.bf-title {{ font-size:26px; font-weight:700; color:{INK}; line-height:1.15; }}
.bf-sub {{ font-size:13px; color:{MUTE}; margin-top:4px; }}
.bf-chips {{ display:flex; gap:6px; flex-wrap:wrap; }}
.bf-chip {{ font-size:12px; padding:4px 9px; border-radius:7px; border:1px solid {LINE}; color:{INK}; background:{CARD}; white-space:nowrap; }}
.bf-chip.warn {{ border-color:#8A5A1F; color:#FFC58A; background:#2A2112; }}
.bf-chip.bad {{ border-color:#8A3B3B; color:#FFB4B4; background:#2E1820; }}
.bf-chip.info {{ border-color:#2F4F8F; color:#BFD4FF; background:#14254F; }}
.bf-kpi {{ background:{CARD}; border:1px solid {LINE}; border-radius:12px; padding:11px 13px 0; height:178px;
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
.bf-sec {{ font-size:16px; font-weight:650; color:{INK}; margin:14px 0 2px; }}
.bf-secsub {{ font-size:12.5px; color:{MUTE}; margin-bottom:6px; }}
.bf-tbl-wrap {{ overflow-x:auto; border:1px solid {LINE}; border-radius:10px; background:{CARD}; max-height:640px; overflow-y:auto; }}
table.bf-tbl {{ border-collapse:separate; border-spacing:0; width:100%; font-size:13px; color:{INK}; }}
table.bf-tbl th {{ position:sticky; top:0; background:#1A2A5A; color:{INK}; font-weight:600; text-align:right; padding:7px 10px;
                   border-bottom:1px solid {LINE}; white-space:nowrap; z-index:2; }}
table.bf-tbl th:first-child {{ text-align:left; left:0; z-index:3; }}
table.bf-tbl td {{ padding:5px 10px; border-bottom:1px solid #1D2C59; text-align:right; white-space:nowrap;
                   font-variant-numeric:tabular-nums; }}
table.bf-tbl td:first-child {{ text-align:left; position:sticky; left:0; background:{CARD}; white-space:normal; min-width:240px; max-width:380px; }}
table.bf-tbl tr.total td {{ font-weight:700; background:#182A58; }}
table.bf-tbl tr.total td:first-child {{ background:#182A58; }}
table.bf-tbl tr.sub td {{ font-weight:600; }}
table.bf-tbl tr.header td {{ font-weight:700; color:{MUTE}; letter-spacing:.04em; font-size:12px; background:#111E47; }}
table.bf-tbl tr.header td:first-child {{ background:#111E47; }}
table.bf-tbl tr.derived td {{ font-style:italic; color:#CFE0FF; }}
table.bf-tbl tr:hover td {{ background:#1C3068; }}
table.bf-tbl td.neg {{ color:#FFB4B4; }}
.bf-tag {{ font-size:10.5px; font-style:normal; border:1px solid #2F4F8F; color:#BFD4FF; border-radius:5px; padding:0 5px; margin-left:6px; }}
.bf-code {{ color:{MUTE}; font-size:11px; margin-left:6px; }}
.bf-foot {{ font-size:11.5px; color:{MUTE}; margin-top:18px; line-height:1.55; border-top:1px solid {LINE}; padding-top:10px; }}
div[data-testid="stTabs"] button p {{ font-size:14px; }}
@media (max-width: 700px) {{
  .block-container {{ padding-left:1rem; padding-right:1rem; }}
  .bf-title {{ font-size:21px; }}
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
    chips = [(f"{P.label} · {P.kind}", ""), (P.price_basis, "info" if P.tms29 else "")]
    if P.label in co.issues:
        chips.append(("⚠ Kaynak veri uyarısı", "warn"))
    chips += extra_chips or []
    ch = "".join(f'<span class="bf-chip {k}">{esc(t)}</span>' for t, k in chips)
    st.markdown(f'<div class="bf-head"><div><div class="bf-title">{esc(title)}</div>'
                f'<div class="bf-sub">{esc(co.name)} ({esc(co.ticker)}) · dönem sonu {P.end:%d.%m.%Y}</div></div>'
                f'<div class="bf-chips">{ch}</div></div>', unsafe_allow_html=True)
    if P.label in co.issues:
        st.warning(f"**{P.label} için kaynak veri uyarısı:** {co.issues[P.label]}. Bu dönemde TL tutar karşılaştırmaları "
                   "gösterilmez; aynı kolon içi oranlar kullanılabilir.", icon="⚠️")


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
        w.append("Kaynak baz uyarısı: TL tutar karşılaştırılamaz")
    if r.id in ("ebitda", "ebitda_margin", "nd_ebitda", "int_cov_ebitda", "ocf_to_ebitda") and r.value is not None:
        w.append("FAVÖK hesaplanmıştır (3H + 4CAB)")
    return w


def metric_card(co, mid: str, P: Period, scale: float, trend: list[Period], color=BLUE, show_trend=True):
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
    elif cmp["comp"] == "BASE_BREAK" and r.unit == "TL":
        dtxt = "baz kırılması: karşılaştırılmaz"
    dline = (f'<div class="d" style="color:{col}">{arrow} {esc(dtxt)}'
             + (f' · {esc(word)}' if word and cmp["delta"] is not None else "") + '</div>')
    cline = f'<div class="c">vs {esc(cmp["prev_period"])} · birim: {esc(unit_lbl)}</div>'
    ws = metric_warnings(co, r, P, cmp_said=cmp["comp"] == "BASE_BREAK")
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
                      plot_bgcolor=CARD, font=dict(color=MUTE, family="Segoe UI, system-ui, sans-serif", size=12),
                      legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0, font=dict(color=INK)),
                      showlegend=legend, hoverlabel=dict(bgcolor=SIDE, font_color=INK), bargap=0.25,
                      separators=",.")
    fig.update_xaxes(showgrid=False, linecolor=LINE, tickfont=dict(color=MUTE), type="category")
    fig.update_yaxes(gridcolor=GRID, zerolinecolor="#4A5E95", tickfont=dict(color=MUTE))
    if yfmt:
        fig.update_yaxes(tickformat=yfmt)
    return fig


def mark_periods(fig, labels: list[str], co):
    """TMS 29 dönemini gölgeler; kaynak uyarılı dönemleri işaretler (renk tek başına anlam taşımaz: metin etiketi var)."""
    # Kategori ekseninin aralığı sabitlenir: açıklama metinleri autorange'i genişletip boşluk bırakmasın
    fig.update_xaxes(range=[-0.5, len(labels) - 0.5])
    tms = [l for l in labels if int(l.split("/")[0]) * 100 + int(l.split("/")[1]) >= 202312]
    if tms:
        i0 = labels.index(tms[0])
        fig.add_vrect(x0=i0 - 0.5, x1=len(labels) - 0.5, fillcolor="#3DD6C3", opacity=0.07, line_width=0, layer="below")
        fig.add_annotation(x=i0 - 0.45, y=0.99, yref="paper", text="TMS 29", showarrow=False, xanchor="left",
                           yanchor="top", font=dict(size=10.5, color=TEAL))
    for l in labels:
        if l in co.issues:
            fig.add_annotation(x=l, y=0, yref="paper", text="⚠ baz", showarrow=False, yanchor="bottom",
                               font=dict(size=10.5, color="#FFC58A"))
    return fig


def show(fig):
    try:
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    except TypeError:  # eski Streamlit
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


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
    mark_periods(fig, labels, co)
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
    mark_periods(fig, labels, co)
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
                tds.append("<td></td>" if kind == "header" else '<td style="color:#5F6F96">—</td>')
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
