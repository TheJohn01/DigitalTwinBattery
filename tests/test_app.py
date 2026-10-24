"""Smoke test: the dashboard runs end to end for every chemistry."""
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from battery_twin.chemistry import PROJECTION_CYCLES  # noqa: E402

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
    # sodium-ion shows a range on the Summary (fastest-fading to median cell); its upper end
    # is the value the Economics tab uses
    assert len(left) == 2 and left[0].split("–")[-1] == left[1]
    assert 50 < float(left[1].rstrip(" %")) < 100


def test_cooling_options_and_sources_tab():
    at = AppTest.from_file(APP, default_timeout=300)
    at.run()
    cooling = [s for s in at.selectbox if s.label == "Battery cooling"][0]
    cooling.set_value("Immersion cooling").run()
    assert any("Pre-conditioning" in w.value for w in at.sidebar.warning)
    at.button[0].click().run()
    assert not at.exception
    assert any(t.label == "Sources" for t in at.tabs)


def test_storage_depth_of_discharge():
    at = AppTest.from_file(APP, default_timeout=300)
    at.run()
    at.button[0].click().run()
    npv = lambda: [m.value for m in at.metric if m.label == "Second-life NPV"][0]
    before = npv()
    [s for s in at.slider if s.label.startswith("Storage depth")][0].set_value(50).run()
    assert not at.exception
    assert npv() != before


def test_battery_test_length_follows_cycles_per_year():
    at = AppTest.from_file(APP, default_timeout=300)
    at.run()
    [n for n in at.number_input if n.label == "Cycles per year"][0].set_value(200).run()
    at.button[0].click().run()
    assert not at.exception
    assert at.session_state["inputs"][4] == 200 * 8          # cycles a year x years in the car
    assert any("field factors" in c.value for c in at.caption)


def test_battery_test_longer_than_the_ageing_curve_is_capped():
    # 3,000 cycles a year for 8 years is past the 20,000-cycle curve: capped, no crash
    at = AppTest.from_file(APP, default_timeout=300)
    at.run()
    [n for n in at.number_input if n.label == "Cycles per year"][0].set_value(3000).run()
    at.button[0].click().run()
    assert not at.exception and "error" not in at.session_state
    assert at.session_state["inputs"][4] == PROJECTION_CYCLES
