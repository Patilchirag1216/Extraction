"""Full UI workflow test through Streamlit's AppTest framework.

Processes the built-in sample cards, then checks the review and export pages.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from streamlit.testing.v1 import AppTest  # noqa: E402

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")


def by_label(widgets, label):
    for w in widgets:
        if getattr(w, "label", None) == label:
            return w
    raise AssertionError(f"widget not found: {label}")


def main():
    at = AppTest.from_file(APP, default_timeout=600)
    at.session_state["nav"] = "Process Cards"
    at.run()
    assert not at.exception, at.exception

    # Enable the built-in samples and run extraction.
    by_label(at.checkbox, "Use built-in sample cards instead").set_value(True)
    at.run()
    by_label(at.button, "Start extraction").click()
    at.run()
    if at.exception:
        print("[FAIL] processing", [e.value for e in at.exception])
        return
    print("[ OK ] processing via UI; batch:", at.session_state.get("last_batch_id"))

    # Review page.
    at.session_state["nav"] = "Review & Edit"
    at.run()
    if at.exception:
        print("[FAIL] review", [e.value for e in at.exception])
        return
    names = [t.value for t in at.text_input if t.label == "Doctor Name"]
    print("[ OK ] review page; doctor name field:", names[:1])

    # Export page.
    at.session_state["nav"] = "Export to Excel"
    at.run()
    by_label(at.button, "Generate Excel file").click()
    at.run()
    if at.exception:
        print("[FAIL] export", [e.value for e in at.exception])
        return
    print("[ OK ] export page; download buttons:", len(at.download_button))
    print("DONE")


if __name__ == "__main__":
    main()
