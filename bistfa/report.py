"""Rapor çıktıları: Excel çalışma kitabı (tablolar, oranlar, bulgular, veri kalitesi, kaynak) ve yazdırılabilir HTML."""
from __future__ import annotations

import datetime as _dt
import html
import io

import pandas as pd

from . import findings as FD
from . import metrics as M
from . import risk, statements
from .periods import Period
from .source import SOURCE_NAME, SOURCE_NOTE

KEY = ["revenue", "gross_margin", "ebit_margin", "ebitda", "ebitda_margin", "net_income", "net_margin", "ocf", "fcf",
       "net_debt", "nd_ebitda", "roe", "roa", "current_ratio", "quick_ratio", "fin_debt_to_equity", "int_cov_ebit",
       "ocf_to_ebitda", "ccc"]


def fmt(r: M.Result, scale: float = 1e6) -> str:
    if r.value is None:
        return "hesaplanamadı"
    v = r.value
    s = {"TL": f"{v / scale:,.1f}", "pct": f"%{v * 100:.1f}", "x": f"{v:.2f}x", "days": f"{v:.1f} gün", "ratio": f"{v:.2f}"}[r.unit]
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def metrics_frame(co, periods: list[Period]) -> pd.DataFrame:
    rows = []
    for d in M.DEFS:
        rec = {"Grup": d.group, "Metrik": d.name, "Birim": {"TL": "TL", "pct": "%", "x": "x", "days": "gün", "ratio": "oran"}[d.unit],
               "Formül": d.formula}
        for p in periods:
            r = co.metric(d.id, p)
            rec[p.label] = r.value if r.value is not None else f"hesaplanamadı: {r.reason}"
        rec["Bakiye bazı / not"] = co.metric(d.id, periods[-1]).basis
        rows.append(rec)
    return pd.DataFrame(rows)


def excel(co, P: Period, periods: list[Period]) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        info = pd.DataFrame({
            "Alan": ["Şirket", "Seçili dönem", "Dönem niteliği", "Fiyat bazı", "Kaynak", "Kaynak notu", "Veri alınma",
                     "Kapsam", "Para birimi / ölçek", "Rapor oluşturma"],
            "Değer": [f"{co.name} ({co.ticker})", P.label, P.kind, P.price_basis, SOURCE_NAME, SOURCE_NOTE,
                      f"{co.raw.fetched_at:%d.%m.%Y %H:%M} ({co.raw.origin})", co.facts["scope"].iloc[0], "TRY, TL (birim)",
                      _dt.datetime.now().strftime("%d.%m.%Y %H:%M")]})
        info.to_excel(xw, sheet_name="Kaynak", index=False)
        for stmt, sheet in [("IS", "Gelir tablosu"), ("BS", "Bilanço"), ("CF", "Nakit akış"), ("MEMO", "Dipnot")]:
            t, _ = statements.build(co, stmt, periods, "Tutar", hide_empty=True)
            t.to_excel(xw, sheet_name=sheet, index=False)
        bal, mv = statements.equity_statement(co, [p for p in periods if p.is_annual] or periods)
        bal.to_excel(xw, sheet_name="Özkaynak", index=False)
        mv.to_excel(xw, sheet_name="Özkaynak", index=False, startrow=len(bal) + 3)
        metrics_frame(co, periods).to_excel(xw, sheet_name="Oranlar", index=False)
        fs = FD.evaluate(co, P)
        pd.DataFrame([{"Tür": f.kind, "Başlık": f.title, "Açıklama": f.text, "Kural": f.rule,
                       "Dayanak": "; ".join(f"{a} {b}: {c}" for a, b, c in f.evidence)} for f in fs]
                     ).to_excel(xw, sheet_name="Bulgular", index=False)
        co.checks.to_excel(xw, sheet_name="Veri kalitesi", index=False)
        pd.DataFrame(sorted(co.issues.items()), columns=["Dönem", "Kaynak uyarısı"]).to_excel(xw, sheet_name="Kaynak uyarıları", index=False)
        co.facts.to_excel(xw, sheet_name="Veri modeli (uzun)", index=False)
    return buf.getvalue()


def html_report(co, P: Period) -> str:
    e = html.escape
    fs = FD.evaluate(co, P)
    pos, neg = FD.top(fs, "olumlu", 5), FD.top(fs, "izlenecek", 5)
    rows = "".join(
        f"<tr><td>{e(co.metric(k, P).name)}</td><td class=n>{e(fmt(co.metric(k, P)))}</td>"
        f"<td>{e(co.comparison(k, P)['delta_text'])}</td><td class=s>{e(co.metric(k, P).formula)}</td></tr>" for k in KEY)
    na = [co.metric(d.id, P) for d in M.DEFS if co.metric(d.id, P).status == "na"]
    alt = risk.altman_z2(co, P)
    alt_html = (f"<p>Z'' = <b>{str(round(alt.z, 2)).replace('.', ',')}</b> ({e(alt.zone)}). " + " ".join(e(c) for c in alt.caveats) + "</p>") if alt.shown \
        else f"<p>Gösterilmiyor: {e(alt.reason)}</p>"

    def flist(xs):
        return "".join(f"<li><b>{e(f.title)}</b>: {e(f.text)}<br><span class=s>Kural: {e(f.rule)}. Dayanak: "
                       f"{e('; '.join(f'{a} {b}: {c}' for a, b, c in f.evidence))}</span></li>" for f in xs) or "<li>Yok</li>"
    warn = "".join(f"<li>{e(p)}: {e(t)}</li>" for p, t in sorted(co.issues.items()))
    return f"""<!doctype html><html lang="tr"><head><meta charset="utf-8"><title>{e(co.ticker)} finansal check-up {e(P.label)}</title>
<style>body{{font-family:Segoe UI,system-ui,sans-serif;color:#14213D;max-width:960px;margin:24px auto;padding:0 16px;line-height:1.5}}
h1{{font-size:24px;margin:0}}h2{{font-size:17px;border-bottom:1px solid #DCE3F1;padding-bottom:4px;margin-top:26px}}
table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{border-bottom:1px solid #E8EDF7;padding:5px 6px;text-align:left;vertical-align:top}}
.n{{text-align:right;white-space:nowrap}}.s{{color:#56658A;font-size:12px}}.box{{background:#F6F8FD;border:1px solid #DCE3F1;border-radius:8px;padding:10px 14px}}
@media print{{body{{margin:0}}}}</style></head><body>
<h1>{e(co.name)} ({e(co.ticker)}) · Finansal check-up</h1>
<p class=s>Dönem {e(P.label)} ({e(P.kind)}) · {e(P.price_basis)} · Kaynak: {e(SOURCE_NAME)} · Veri alınma {co.raw.fetched_at:%d.%m.%Y %H:%M}
· Rapor {_dt.datetime.now():%d.%m.%Y %H:%M}</p>
<div class=box>{e(SOURCE_NOTE)} Bu rapor yatırım tavsiyesi ya da fiyat tahmini değildir.</div>
<h2>Temel göstergeler</h2><table><tr><th>Metrik</th><th class=n>Değer (TL: milyon)</th><th>Önceki karşılaştırılabilir döneme göre</th><th>Formül</th></tr>{rows}</table>
<h2>Güçlü yönler</h2><ul>{flist(pos)}</ul><h2>İzlenmesi gereken konular</h2><ul>{flist(neg)}</ul>
<h2>Altman Z''-skoru</h2>{alt_html}
<h2>Hesaplanamayan metrikler</h2><ul>{''.join(f'<li>{e(r.name)}: {e(r.reason)}</li>' for r in na) or '<li>Yok</li>'}</ul>
<h2>Veri uyarıları</h2><ul>{warn or '<li>Kayıtlı uyarı yok</li>'}{''.join(f'<li>Eksik dönem: {e(g)}</li>' for g in co.gaps)}</ul>
<p class=s>Yöntem: oranlar aynı dönem kolonu içinde hesaplanır; TMS 29 döneminde TL tutar değişimleri nominaldir. FAVÖK hesaplanmıştır
(net faaliyet kârı + amortisman). Tarayıcıda Yazdır → PDF olarak kaydet ile PDF alınabilir.</p></body></html>"""
