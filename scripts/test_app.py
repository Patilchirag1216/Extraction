"""Run the Streamlit app with AppTest to catch runtime errors on every page."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from streamlit.testing.v1 import AppTest  # noqa: E402

PAGES = ["Dashboard", "Process Cards", "Review & Edit", "Export to Excel", "History & Resume"]
APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")


def main():
    for page in PAGES:
        at = AppTest.from_file(APP, default_timeout=120)
        at.session_state["nav"] = page
        at.run()
        if at.exception:
            print(f"[FAIL] {page}")
            for exc in at.exception:
                print("   ", exc.value)
        else:
            print(f"[ OK ] {page}")


if __name__ == "__main__":
    main()
