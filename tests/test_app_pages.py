"""
Arayüz duman testi: 8 sayfanın her biri birkaç şirket/dönem için başsız (headless) çalıştırılır ve istisna
olmadığı doğrulanır. Çalıştırma (proje klasöründen):  python tests/test_app_pages.py
"""
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
PAGES = ["page_summary", "page_balance", "page_performance", "page_cash", "page_risk", "page_peers",
         "page_statements", "page_checkup"]
CASES = [("BIMAS", "2025/12"), ("CRFSA", "2025/12"), ("MGROS", "2022/12"), ("SOKM", "2025/9"), ("BIMAS", "2021/12")]

SCRIPT = """
import sys
sys.path.insert(0, r"{app}"); sys.path.insert(0, r"{root}")
import streamlit as st
import ui, views
from bistfa import company
st.markdown(ui.CSS, unsafe_allow_html=True)
co = company.load("{t}")
P = co.period("{p}")
views.CTX.update(co=co, P=P, scale=1e6, trend=[x for x in co.periods if x.month == P.month and x.key <= P.key][-7:],
                 load=company.load)
views.{fn}()
"""


def main() -> int:
    bad = 0
    for t, p in CASES:
        for fn in PAGES:
            at = AppTest.from_string(SCRIPT.format(app=ROOT / "app", root=ROOT, t=t, p=p, fn=fn), default_timeout=120)
            at.run()
            if at.exception:
                bad += 1
                print(f"HATA {t} {p} {fn}: {at.exception[0].value}")
            else:
                print(f"ok   {t} {p} {fn}")
    at = AppTest.from_file(str(ROOT / "app" / "app.py"), default_timeout=120)
    at.run()
    print("app.py giriş:", "HATA " + str(at.exception[0].value) if at.exception else "ok")
    bad += bool(at.exception)
    print(f"\n{bad} hata")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
