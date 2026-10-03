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
