"""
bistfa çekirdeği ile SQL hattının (dw.vw_ratios) aynı veriden aynı sonucu verdiğini doğrular.
Çalıştırma (proje klasöründen, SQL Server açıkken):  python tests/test_parity.py

SQL hattı bakiyelerde DÖNEM SONU kullanır; karşılaştırma bistfa'da force_end=True ile yapılır. bistfa'nın bilinçli
olarak hesaplamadığı durumlar (ör. FAVÖK ≤ hasılatın %1'i, negatif özkaynak) "kural farkı" olarak ayrı sayılır.
ebitda_to_finance_expense: SQL'deki 3HC işaret varsayımı 05.11.2026'da düzeltildi (bkz. docs/APP_AUDIT.md) ve artık karşılaştırılır.
"""
import sys
from pathlib import Path

import pandas as pd
import pyodbc

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bistfa import company  # noqa: E402

MAP = {"revenue": "revenue", "ebitda": "ebitda", "net_debt": "net_debt", "fcf": "fcf", "gross_margin": "gross_margin",
       "ebitda_margin": "ebitda_margin", "core_operating_margin": "core_op_margin", "operating_margin": "ebit_margin",
       "net_margin": "net_margin", "current_ratio": "current_ratio", "quick_ratio": "quick_ratio", "cash_ratio": "cash_ratio",
       "net_debt_to_ebitda": "nd_ebitda", "fin_debt_to_equity": "fin_debt_to_equity",
       "liabilities_to_assets": "liab_to_assets", "dio": "dio", "dso": "dso", "dpo": "dpo",
       "cash_conversion_cycle": "ccc", "ocf_to_ebitda": "ocf_to_ebitda", "fcf_margin": "fcf_margin",
       "capex_to_revenue": "capex_to_revenue", "dupont_net_margin": "dupont_margin",
       "dupont_asset_turnover": "asset_turnover", "dupont_equity_multiplier": "equity_multiplier",
       "roe_annualized": "roe", "roa_annualized": "roa", "ebitda_to_finance_expense": "int_cov_ebitda"}
REL_TOL = 1e-6

# Bilinçli TANIM farkları: bu sütunlar bistfa metriğiyle değil, SQL tanımı kaynak kalemlerden yeniden kurularak
# karşılaştırılır (verinin aynı olduğunu kanıtlar); bistfa'nın tanımı ve gerekçesi docs/APP_AUDIT.md'dedir.
def _x(co, P, *codes):
    vals = [co.value(c, P.label) for c in codes]
    return None if any(v is None for v in vals) else vals


def _alt(f):
    def g(co, P):
        try:
            return f(co, P)
        except (TypeError, ZeroDivisionError):
            return None
    return g


ANN = lambda P: 12 / P.months  # noqa: E731
DEFINITION_DIFF = {
    "operating_margin": ("SQL: esas faaliyet kârı (3DF) / hasılat; bistfa EBIT marjı: 3HACA / hasılat",
                         _alt(lambda co, P: (lambda v: v[0] / v[1])(_x(co, P, "3DF", "3C")))),
    "cash_ratio": ("SQL: (nakit + KV finansal yatırım) / KVY; bistfa nakit oranı yalnız nakit (1AA) kullanır",
                   _alt(lambda co, P: (lambda v: (v[0] + v[1]) / v[2])(_x(co, P, "1AA", "1AB", "2A")))),
    "dupont_net_margin": ("SQL: 3L / hasılat; bistfa ana ortaklık kârı 3Z / hasılat (ROE paydası ana ortaklık özkaynağı)",
                          _alt(lambda co, P: (lambda v: v[0] / v[1])(_x(co, P, "3L", "3C")))),
    "dupont_equity_multiplier": ("SQL: toplam varlık / toplam özkaynak (2N); bistfa / ana ortaklık özkaynağı (2O)",
                                 _alt(lambda co, P: (lambda v: v[0] / v[1] if v[1] > 0 else None)(_x(co, P, "1BL", "2N")))),
    "roe_annualized": ("SQL: 3L / 2N; bistfa 3Z / 2O (pay ve payda aynı sahiplik tabanında)",
                       _alt(lambda co, P: (lambda v: v[0] * ANN(P) / v[1] if v[1] > 0 else None)(_x(co, P, "3L", "2N")))),
}


def main() -> int:
    drv = sorted(d for d in pyodbc.drivers() if d.startswith("ODBC Driver"))[-1]
    cn = pyodbc.connect(f"DRIVER={{{drv}}};SERVER=localhost\\SQLEXPRESS;DATABASE=RetailFinance;"
                        "Trusted_Connection=yes;TrustServerCertificate=yes;")
    sql = pd.read_sql("SELECT ticker, period_label, " + ", ".join(MAP) + " FROM dw.vw_ratios", cn)
    stats = {"eşit": 0, "ikisi de boş": 0, "kural farkı (bistfa boş)": 0, "SQL boş": 0, "FARK": 0}
    diffs = {}
    for t in sorted(sql["ticker"].unique()):
        co = company.load(t)
        for _, row in sql[sql.ticker == t].iterrows():
            P = co.period(row.period_label)
            for col, mid in MAP.items():
                x = row[col]
                x = None if pd.isna(x) else float(x)
                r = co.metric(mid, P, force_end=True)
                y = r.value
                if col in DEFINITION_DIFF:
                    y = DEFINITION_DIFF[col][1](co, P)
                if x is None and y is None:
                    stats["ikisi de boş"] += 1
                elif y is None:
                    stats["kural farkı (bistfa boş)"] += 1
                elif x is None:
                    stats["SQL boş"] += 1
                elif abs(x - y) <= max(REL_TOL * abs(x), 1e-6 if r.unit != "TL" else 1.0):
                    if col in DEFINITION_DIFF:
                        stats["eşit (SQL tanımıyla yeniden kuruldu)"] = stats.get("eşit (SQL tanımıyla yeniden kuruldu)", 0) + 1
                        continue
                    stats["eşit"] += 1
                else:
                    stats["FARK"] += 1
                    diffs.setdefault(col, []).append((t, row.period_label, x, y))
    for col, xs in diffs.items():
        print(f"FARK {col}: {len(xs)} değer, örn. " + "; ".join(f"{a} {b} sql={c:.6g} app={d:.6g}" for a, b, c, d in xs[:3]))
    print(stats)
    print("\nTanım farkları (bilinçli):")
    for col, (txt, _) in DEFINITION_DIFF.items():
        print(f"  {col}: {txt}")
    return 1 if stats["FARK"] else 0


if __name__ == "__main__":
    sys.exit(main())
