"""
Çekirdek birim testleri (SQL gerektirmez). Çalıştırma: python -m pytest tests  ya da  python tests/test_core.py
Perakende şirketlerinin ham CSV'leri data/raw içinde olmalıdır (SQL projesiyle aynı veri).
"""
import os
os.environ.setdefault("BISTFA_OFFLINE", "1")   # önbellek olduğu gibi okunur; testler ağa çıkmaz
import datetime as dt
import json
import math
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bistfa import company, statements, risk, source  # noqa: E402
from bistfa.periods import parse, safe_change  # noqa: E402

P = parse("2025/12")


def test_safe_change_rules():
    assert safe_change(110, 100)[1] == 0.1
    assert safe_change(10, 0)[1] is None and "sıfır baz" in safe_change(10, 0)[2]
    assert safe_change(5, -5)[1] is None and "işaret" in safe_change(5, -5)[2]
    assert safe_change(-3, -5)[1] is None


def test_comparability_codes():
    co = company.load("BIMAS")                       # varsayılan: ortak fiyat (Aralık 2025)
    assert co.comp(parse("2021/12"), parse("2020/12")) == "NOMINAL"
    assert co.comp(parse("2022/12"), parse("2021/12")) == "TMS29_GECIS"
    assert co.comp(parse("2024/12"), parse("2023/12")) == "REAL"
    assert co.comp(parse("2025/12"), parse("2024/12")) == "REAL"
    assert co.comp(parse("2024/9"), parse("2023/9")) == "REAL"                   # akışlar: 2023/9 sonraki raporda düzeltilmiş
    assert co.comp(parse("2024/9"), parse("2023/9"), stock=True) == "TMS29_GECIS"  # ara dönem bilançosu düzeltilmez
    pub = company.load("BIMAS", basis="published")
    assert pub.comp(parse("2025/12"), parse("2024/12")) == "NOMINAL_TMS29"
    src = company.load("BIMAS", basis="source")
    assert src.comp(parse("2025/12"), parse("2024/12")) == "BASE_BREAK"


def test_price_basis_matches_published_figures():
    """Yayımlanan rakamlar (milyar TL): BİM 2023 raporu, Migros 4Ç24 özeti, QNB (Şok), Investing (CarrefourSA)."""
    exp = [("BIMAS", "3C", "2023/12", 328.44), ("BIMAS", "3C", "2025/12", 721.0), ("BIMAS", "3L", "2023/12", 15.445),
           ("MGROS", "3C", "2024/12", 293.78), ("MGROS", "3Z", "2024/12", 6.34), ("MGROS", "1BL", "2024/12", 150.059),
           ("SOKM", "3C", "2024/12", 202.174), ("SOKM", "3C", "2025/12", 278.8), ("CRFSA", "3C", "2025/12", 83.61),
           ("CRFSA", "3L", "2025/12", -6.539)]
    for t, code, lbl, pub in exp:
        v = company.load(t, basis="published").value(code, lbl) / 1e9
        assert abs(v - pub) / abs(pub) < 0.003, (t, code, lbl, v, pub)
    co = company.load("BIMAS")
    assert co.issues == {} and abs(co.comparison("revenue", P)["delta"] - 0.060) < 0.002      # BİM 2025: reel +%6
    assert math.isclose(co.value("3C", "2024/12"), company.load("BIMAS", basis="source").value("3C", "2024/12"))


def test_non_applier_is_left_nominal():
    from bistfa import pricebasis
    assert pricebasis.applies_tms29({"2022/9": 100.0, "2022/12": 103.0}) is False
    assert pricebasis.applies_tms29({"2022/9": 100.0, "2022/12": 250.0}) is True
    pl = pricebasis.plan("XXXXX", [parse("2024/12"), parse("2025/12")], "common", applies=False)
    assert set(pl["factors"].values()) == {1.0} and set(pl["kinds"].values()) == {"nominal"}


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
    assert "aynı fiyat düzeyinde" in co.metric("roe", P).basis               # ortak fiyat: açılış ve kapanış karşılaştırılabilir
    assert "TMS 29" in company.load("BIMAS", basis="source").metric("roe", P).basis
    assert co.metric("roe", parse("2023/9")).value is None                   # akış düzeltilmiş, ara dönem bilançosu nominal
    assert "açılış bakiyesi yok" in co.metric("roe", parse("2019/12")).basis


def test_na_reasons():
    cr = company.load("CRFSA")
    assert cr.metric("roe", P).value is None and "negatif" in cr.metric("roe", P).reason
    so = company.load("SOKM")
    r = so.metric("nd_ebitda", parse("2024/12"))
    assert r.value is None and "FAVÖK" in r.reason
    bi = company.load("BIMAS")
    assert bi.metric("int_cov_ebit", P).value is None  # TMS 29: net finansman satırı gelir


def test_tl_change_real_and_transition():
    co = company.load("BIMAS")
    c = co.comparison("revenue", P)
    assert c["comp"] == "REAL" and "reel" in c["delta_text"]
    c = co.comparison("revenue", parse("2022/12"))
    assert c["comp"] == "TMS29_GECIS" and c["delta"] is None          # 2021 nominal, 2022 düzeltilmiş
    assert co.comparison("gross_margin", parse("2022/12"))["delta"] is not None


def test_statements_and_equity():
    co = company.load("BIMAS")
    t, _ = statements.build(co, "BS", [parse("2024/12"), P])
    assert {"1A", "1BL", "2N"} <= set(t["Kod"])
    t, notes = statements.build(co, "IS", [parse("2022/12")], "Yatay (%)")
    assert notes["2022/12"] == "TMS29_GECIS" and t.loc[t.Kod == "3C", "2022/12"].iloc[0] is None
    bal, mv = statements.equity_statement(co, [parse("2024/12"), P])
    col = mv[P.label]
    assert math.isclose(sum(col[:5]), col[5], rel_tol=1e-9)


def test_altman_eligibility():
    co = company.load("BIMAS")
    assert risk.altman_z2(co, P).shown
    assert not risk.altman_z2(co, parse("2025/9")).shown


def _frame(year, quarters):
    import pandas as pd
    d = {"FINANCIAL_ITEM_CODE": ["3C"], "FINANCIAL_ITEM_NAME_TR": ["Hasılat"], "FINANCIAL_ITEM_NAME_EN": ["Revenue"],
         "SYMBOL": ["TEST"]}
    d.update({f"{year}/{m}": [1.0] for m in quarters})
    return pd.DataFrame(d)


def test_fetch_retries_timeouts_and_never_returns_partial_data():
    calls = {}

    def flaky(symbols, start_year, end_year, **kw):        # 2026: ilk istek zaman aşımı, ikincisi gelir
        calls[start_year] = calls.get(start_year, 0) + 1
        if start_year == 2026 and calls[start_year] == 1:
            print(f"[Warning] Could not fetch data for '{symbols}' in one period: Read timed out.")
            raise ValueError("No financial data was fetched for any symbol.")
        return _frame(start_year, (3, 6, 9) if start_year == 2026 else (3, 6, 9, 12))

    old = source.START_YEAR
    source.START_YEAR = 2025
    try:
        df = source._fetch_live("TEST", 2026, fetch=flaky, sleep=lambda s: None)
        assert source.period_cols(df) == ["2025/3", "2025/6", "2025/9", "2025/12", "2026/3", "2026/6", "2026/9"]
        assert calls[2026] == 2

        def dead(symbols, start_year, end_year, **kw):     # 2026 hiç gelmiyor: kısmi veri döndürülmemeli
            if start_year == 2026:
                print("[Warning] Could not fetch data for 'TEST' in one period: Read timed out.")
                raise ValueError("No financial data was fetched for any symbol.")
            return _frame(start_year, (3, 6, 9, 12))
        try:
            source._fetch_live("TEST", 2026, fetch=dead, sleep=lambda s: None)
            raise AssertionError("kısmi veri kabul edildi")
        except source.FetchError as e:
            assert "2026" in str(e)
    finally:
        source.START_YEAR = old


def test_cache_without_completeness_marker_is_not_trusted():
    old_dir, old_fetch, old_env = source.CACHE_DIR, source._fetch_live, source.os.environ.pop("BISTFA_OFFLINE", None)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            source.CACHE_DIR = Path(tmp)
            _frame(2025, (3, 6, 9, 12)).to_csv(Path(tmp) / "TEST.csv", index=False, encoding="utf-8-sig")

            def down(t, y, **kw):
                raise source.FetchError("ağ yok")
            source._fetch_live = down
            try:                                              # işaretsiz (eski/eksik) önbellek: kullanılmaz
                source.load("TEST")
                raise AssertionError("işaretsiz önbellek kullanıldı")
            except source.FetchError:
                pass
            stale = (dt.datetime.now() - dt.timedelta(days=30)).isoformat(timespec="seconds")
            (Path(tmp) / "TEST.meta.json").write_text(json.dumps({"version": source.CACHE_VERSION, "complete": True,
                                                                  "fetched_at": stale}), encoding="utf-8")
            r = source.load("TEST")                           # eksiksiz ama eski: yenilenemezse eski kopya
            assert r.origin == "önbellek (yenilenemedi)" and source.period_cols(r.frame)[-1] == "2025/12"
            source._fetch_live = lambda t, y, **kw: _frame(2026, (3, 6, 9))
            r = source.load("TEST")                           # yenilenebiliyorsa yeni veri ve işaret yazılır
            assert r.origin == "canlı" and source._read_meta("TEST")["complete"]
    finally:
        source.CACHE_DIR, source._fetch_live = old_dir, old_fetch
        if old_env is not None:
            source.os.environ["BISTFA_OFFLINE"] = old_env


if __name__ == "__main__":
    n = 0
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f(); n += 1; print("OK", k)
    print(f"{n} test geçti")
