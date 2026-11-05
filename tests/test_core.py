"""
Çekirdek birim testleri (SQL gerektirmez). Çalıştırma: python -m pytest tests  ya da  python tests/test_core.py
İlk çalıştırmada dört perakende şirketinin tabloları kaynaktan çekilir (internet gerekir) ve app/.cache'e yazılır.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bistfa import company, statements, risk  # noqa: E402
from bistfa.periods import parse, safe_change, comparability  # noqa: E402

P = parse("2025/12")


def test_safe_change_rules():
    assert safe_change(110, 100)[1] == 0.1
    assert safe_change(10, 0)[1] is None and "sıfır baz" in safe_change(10, 0)[2]
    assert safe_change(5, -5)[1] is None and "işaret" in safe_change(5, -5)[2]
    assert safe_change(-3, -5)[1] is None


def test_comparability_codes():
    co = company.load("BIMAS")
    labels = set(co.period_labels)
    assert comparability(parse("2021/12"), parse("2020/12"), co.issues, labels) == "NOMINAL"
    assert comparability(parse("2022/12"), parse("2021/12"), co.issues, labels) == "BASE_BREAK"
    assert comparability(parse("2024/12"), parse("2023/12"), co.issues, labels) == "NOMINAL_TMS29"
    assert comparability(parse("2023/9"), parse("2022/9"), co.issues, labels) == "NOMINAL"


def test_identities_pass():
    for t in ["BIMAS", "MGROS", "SOKM"]:
        c = company.load(t).checks
        assert (c[c["grup"] == "Toplam kimliği"]["sonuç"] != "FAIL").sum() >= 500


def test_dupont_identity():
    co = company.load("BIMAS")
    for y in ["2020/12", "2024/12", "2025/12"]:
        p = parse(y)
        m = [co.metric(k, p).value for k in ("dupont_margin", "asset_turnover", "equity_multiplier", "roe")]
        assert math.isclose(m[0] * m[1] * m[2], m[3], rel_tol=1e-9)


def test_average_balance_rule():
    co = company.load("BIMAS")
    assert "ortalama bakiye" in co.metric("roe", parse("2021/12")).basis
    assert "TMS 29" in co.metric("roe", P).basis
    assert "açılış bakiyesi yok" in co.metric("roe", parse("2019/12")).basis


def test_na_reasons():
    cr = company.load("CRFSA")
    assert cr.metric("roe", P).value is None and "negatif" in cr.metric("roe", P).reason
    so = company.load("SOKM")
    r = so.metric("nd_ebitda", parse("2024/12"))
    assert r.value is None and "FAVÖK" in r.reason
    bi = company.load("BIMAS")
    assert bi.metric("int_cov_ebit", P).value is None  # TMS 29: net finansman satırı gelir


def test_tl_change_blocked_on_base_break():
    co = company.load("BIMAS")
    c = co.comparison("revenue", P)
    assert c["comp"] == "BASE_BREAK" and c["delta"] is None
    c = co.comparison("gross_margin", P)
    assert c["delta"] is not None   # oranlar aynı kolon içi: karşılaştırılabilir


def test_statements_and_equity():
    co = company.load("BIMAS")
    t, _ = statements.build(co, "BS", [parse("2024/12"), P])
    assert {"1A", "1BL", "2N"} <= set(t["Kod"])
    t, notes = statements.build(co, "IS", [parse("2022/12")], "Yatay (%)")
    assert notes["2022/12"] == "BASE_BREAK" and t.loc[t.Kod == "3C", "2022/12"].iloc[0] is None
    bal, mv = statements.equity_statement(co, [parse("2024/12"), P])
    col = mv[P.label]
    assert math.isclose(sum(col[:5]), col[5], rel_tol=1e-9)


def test_altman_eligibility():
    co = company.load("BIMAS")
    assert risk.altman_z2(co, P).shown
    assert not risk.altman_z2(co, parse("2025/9")).shown


if __name__ == "__main__":
    n = 0
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f(); n += 1; print("OK", k)
    print(f"{n} test geçti")
