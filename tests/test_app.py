"""Smoke test: the dashboard runs end to end for every chemistry."""
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = str(Path(__file__).resolve().parents[1] / "app.py")


@pytest.mark.parametrize("chemistry", ["NMC", "LFP", "NCA", "Na-ion"])
def test_app_runs(chemistry):
    at = AppTest.from_file(APP, default_timeout=300)
    at.run()
    at.selectbox[0].set_value(chemistry).run()
    at.button[0].click().run()
    assert not at.exception
    assert len(at.metric) >= 4
    # Summary and the Economics second life show the same capacity leaving the car
    left = [m.value for m in at.metric if m.label == "Capacity leaving the car"]
    assert len(left) == 2 and left[0] == left[1]
    assert 50 < float(left[0].rstrip(" %")) < 100


def test_cooling_options_and_sources_tab():
    at = AppTest.from_file(APP, default_timeout=300)
    at.run()
    cooling = [s for s in at.selectbox if s.label == "Battery cooling"][0]
    cooling.set_value("Immersion cooling").run()
    assert any("Pre-conditioning" in w.value for w in at.sidebar.warning)
    at.button[0].click().run()
    assert not at.exception
    assert any(t.label == "Sources" for t in at.tabs)
