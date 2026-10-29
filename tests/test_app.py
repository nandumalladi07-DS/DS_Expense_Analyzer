"""Smoke tests: the Streamlit dashboard runs end-to-end without a browser."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def test_dashboard_loads_with_sample_data():
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert any("sample data" in i.value for i in at.info)
    assert [m.label for m in at.metric] == ["Total spent", "Avg per month", "Transactions", "Top category"]


def test_lower_sensitivity_flags_more():
    at = AppTest.from_file(APP, default_timeout=60).run()
    strict = len(at.dataframe[-2].value) if len(at.dataframe) >= 3 else 0
    at.slider[0].set_value(2.0).run()
    assert not at.exception
    assert len(at.dataframe[-2].value) >= strict
