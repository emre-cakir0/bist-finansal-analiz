"""
Kurala dayalı bulgular. Her bulgu: tür (olumlu / izlenecek / bilgi), başlık, açıklama, kural, dayanak (metrik,
dönem, değer). Eşikler genel kabul görmüş başlangıç değerleridir; sektör bağlamı olmadan kesin hüküm değildir ve
arayüzde kuralıyla birlikte gösterilir. Tek bir "sağlık puanı" ÜRETİLMEZ: sektör duyarlı eşikler ve yeterli
karşılaştırma verisi olmadan ağırlıklı bir puan açıklanabilir olmaz.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .periods import Period


def _d(x, n=1):
    return f"{x:.{n}f}".replace(".", ",")


@dataclass
class Finding:
    kind: str          # "olumlu" | "izlenecek" | "bilgi"
    severity: int      # sıralama için (yüksek önce)
    title: str
    text: str
    rule: str
    evidence: list = field(default_factory=list)   # (metrik adı, dönem, değer metni)


def _fmt(r):
    if r.value is None:
        return "hesaplanamadı"
    return {"pct": f"%{r.value * 100:.1f}", "x": f"{r.value:.2f}x", "days": f"{r.value:.1f} gün",
            "ratio": f"{r.value:.2f}", "TL": f"{r.value / 1e9:,.2f} mlr TL"}[r.unit].replace(",", "X").replace(".", ",").replace("X", ".")


def evaluate(co, P: Period) -> list[Finding]:
    F = []
    m = lambda k, p=P: co.metric(k, p)  # noqa: E731
    prev = P.prior_comparable()

    def ev(*keys, p=P):
        return [(m(k, p).name, p.label, _fmt(m(k, p))) for k in keys]

    # kârlılık trendi (aynı kolon içi oranlar: TMS 29'dan etkilenmez)
    for k, label in [("ebitda_margin", "FAVÖK marjı"), ("net_margin", "Net kâr marjı")]:
        a, b = m(k), m(k, prev)
        if a.value is not None and b.value is not None:
            dpp = (a.value - b.value) * 100
            if dpp >= 1:
                F.append(Finding("olumlu", 3, f"{label} yükseldi", f"{label} {prev.label} dönemine göre {_d(dpp)} puan arttı.",
                                 "Aynı uzunluktaki önceki döneme göre ≥ 1 puan artış", ev(k) + ev(k, p=prev)))
            elif dpp <= -1:
                F.append(Finding("izlenecek", 3, f"{label} geriledi", f"{label} {prev.label} dönemine göre {_d(-dpp)} puan azaldı.",
                                 "Aynı uzunluktaki önceki döneme göre ≥ 1 puan düşüş", ev(k) + ev(k, p=prev)))
    ni = m("net_income")
    if ni.value is not None and ni.value < 0:
        F.append(Finding("izlenecek", 5, "Net zarar", "Dönem net zararla kapandı.", "Dönem kârı (3L) < 0", ev("net_income")))
    # nakit üretimi
    oc = m("ocf_to_ebitda")
    if oc.value is not None:
        if oc.value >= 1:
            F.append(Finding("olumlu", 2, "Güçlü nakit dönüşümü", "İşletme nakdi FAVÖK'ü karşılıyor.",
                             "FNA / FAVÖK ≥ 1,0", ev("ocf_to_ebitda")))
        elif oc.value < 0.7:
            F.append(Finding("izlenecek", 3, "Zayıf nakit dönüşümü", "Faaliyet kârının önemli kısmı nakde dönmüyor.",
                             "FNA / FAVÖK < 0,7", ev("ocf_to_ebitda")))
    fcf = m("fcf")
    if fcf.value is not None and fcf.value < 0:
        F.append(Finding("izlenecek", 3, "Negatif serbest nakit akışı",
                         "İşletme nakdi sabit sermaye yatırımlarını karşılamadı.", "İşletme nakdi + CapEx < 0", ev("fcf", "ocf", "capex")))
    # borçluluk
    nd = m("nd_ebitda")
    if nd.value is not None:
        if nd.value < 0:
            F.append(Finding("olumlu", 3, "Net nakit pozisyonu", "Nakit ve finansal yatırımlar finansal borcu aşıyor.",
                             "Net finansal borç < 0", ev("net_debt", "nd_ebitda")))
        elif nd.value > 3:
            F.append(Finding("izlenecek", 4, "Yüksek kaldıraç", "Net finansal borç yıllık FAVÖK'ün 3 katını aşıyor.",
                             "Net borç / FAVÖK > 3,0 (genel başlangıç eşiği; sektöre göre değişir)", ev("nd_ebitda")))
    elif "FAVÖK" in nd.reason:
        F.append(Finding("izlenecek", 4, "FAVÖK çok düşük", "Borç servis kapasitesi FAVÖK ile ölçülemiyor.",
                         "FAVÖK ≤ hasılatın %1'i", ev("ebitda", "revenue")))
    ic = m("int_cov_ebit")
    if ic.value is not None:
        if ic.value < 1.5:
            F.append(Finding("izlenecek", 4, "Düşük faiz karşılama", "EBIT net finansman giderini sınırlı karşılıyor.",
                             "EBIT / net finansman gideri < 1,5 (gider kur farkı içerebilir)", ev("int_cov_ebit")))
        elif ic.value > 5:
            F.append(Finding("olumlu", 1, "Rahat faiz karşılama", "EBIT net finansman giderinin 5 katından fazla.",
                             "EBIT / net finansman gideri > 5", ev("int_cov_ebit")))
    eq = m("total_equity")
    if eq.value is not None and eq.value <= 0:
        F.append(Finding("izlenecek", 6, "Negatif özkaynak", "Birikmiş zararlar sermayeyi aşmış; ROE ve borç/özkaynak hesaplanmaz.",
                         "Özkaynaklar (2N) ≤ 0", ev("total_equity")))
    # likidite: perakende gibi negatif nakit döngülü modellerde cari oran < 1 olağandır
    cr, ccc = m("current_ratio"), m("ccc")
    if cr.value is not None and cr.value < 1:
        if ccc.value is not None and ccc.value < 0:
            F.append(Finding("bilgi", 1, "Cari oran 1'in altında, işletme sermayesi tedarikçi finanslı",
                             "Nakit dönüşüm döngüsü negatif; bu yapı perakende gibi sektörlerde olağandır.",
                             "Cari oran < 1 ve nakit dönüşüm döngüsü < 0", ev("current_ratio", "ccc")))
        else:
            F.append(Finding("izlenecek", 3, "Likidite baskısı", "Kısa vadeli yükümlülükler dönen varlıkları aşıyor.",
                             "Cari oran < 1 ve nakit dönüşüm döngüsü ≥ 0 (sektör bağlamı gerekir)", ev("current_ratio", "ccc")))
    sd = m("st_debt_share")
    if sd.value is not None and sd.value > 0.6 and (m("fin_debt").value or 0) > 0:
        F.append(Finding("izlenecek", 2, "Kısa vadeli borç yoğunluğu", "Finansal borcun çoğu bir yıl içinde vadesi gelen borç.",
                         "KV finansal borç / finansal borç > %60", ev("st_debt_share")))
    roe, roep = m("roe"), m("roe", prev)
    if roe.value is not None and roep.value is not None and roe.value - roep.value >= 0.03:
        F.append(Finding("olumlu", 2, "ROE arttı", f"ROE {prev.label} dönemine göre {_d(100 * (roe.value - roep.value))} puan yükseldi.",
                         "≥ 3 puan artış", ev("roe") + ev("roe", p=prev)))
    if roe.value is not None and roep.value is not None and roep.value - roe.value >= 0.03:
        F.append(Finding("izlenecek", 3, "ROE geriledi", f"ROE {prev.label} dönemine göre {_d(100 * (roep.value - roe.value))} puan düştü.",
                         "≥ 3 puan düşüş (bakiye bazı karşılaştırma dönemleri arasında farklı olabilir)", ev("roe") + ev("roe", p=prev)))
    # veri
    if P.label in co.issues:
        F.append(Finding("bilgi", 2, "Kaynak veri uyarısı", co.issues[P.label],
                         "Kaynakta baz kırılması: TL tutar karşılaştırmaları gösterilmez", []))
    return F


def top(findings: list[Finding], kind: str, n: int = 3) -> list[Finding]:
    return sorted([f for f in findings if f.kind == kind], key=lambda f: -f.severity)[:n]
