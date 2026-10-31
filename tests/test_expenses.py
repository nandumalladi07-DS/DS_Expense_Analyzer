import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import expenses as ex  # noqa: E402


@pytest.fixture(scope="module")
def sample_df(tmp_path_factory):
    path = tmp_path_factory.mktemp("data") / "sample.csv"
    ex.generate_sample_data().to_csv(path, index=False)
    return ex.load_transactions(str(path))


@pytest.mark.parametrize("description, expected", [
    ("SWIGGY ORDER #123", "Food & Dining"),
    ("Uber trip help.uber.com", "Transport"),
    ("NETFLIX.COM", "Entertainment"),
    ("BESCOM ELECTRICITY BILL", "Bills & Utilities"),
    ("DOMINOS PIZZA", "Food & Dining"),
    ("COCA COLA VENDING", "Other"),          # "ola" must not match inside "cola"
    ("HP PETROL PUMP", "Fuel"),
    ("Random shop xyz", "Other"),
])
def test_categorize(description, expected):
    assert ex.categorize(description) == expected


def test_bank_style_columns_and_negative_debits():
    csv = (
        "Txn Date,Narration,Withdrawal Amt.\n"
        "31/01/2026,ZOMATO ORDER,-450.50\n"
        "01/02/2026,UBER TRIP,-300\n"
        "02/02/2026,SALARY CREDIT,50000\n"
    )
    df = ex.load_transactions(csv, dayfirst=True)
    assert list(df["description"]) == ["ZOMATO ORDER", "UBER TRIP"]  # salary dropped
    assert df["amount"].tolist() == [450.50, 300.0]                  # signs flipped
    assert df["date"].iloc[0] == pd.Timestamp("2026-01-31")
    assert df["category"].tolist() == ["Food & Dining", "Transport"]


def test_existing_category_column_is_kept():
    csv = "date,description,amount,category\n2026-01-01,Mystery,100,Gifts\n2026-01-02,SWIGGY,200,\n"
    df = ex.load_transactions(csv)
    assert df["category"].tolist() == ["Gifts", "Food & Dining"]


def test_currency_symbols_and_commas_are_parsed():
    csv = 'date,description,amount\n2026-01-01,AMAZON,"₹1,299.00"\n'
    assert ex.load_transactions(csv)["amount"].iloc[0] == 1299.0


def test_missing_column_gives_clear_error():
    with pytest.raises(ValueError, match="amount"):
        ex.load_transactions("date,description\n2026-01-01,foo\n")


def test_summaries_add_up(sample_df):
    total = sample_df["amount"].sum()
    assert ex.category_summary(sample_df)["total"].sum() == pytest.approx(total, abs=1)
    assert ex.category_summary(sample_df)["share_%"].sum() == pytest.approx(100, abs=0.1)
    assert ex.monthly_summary(sample_df).to_numpy().sum() == pytest.approx(total, abs=1)
    assert len(ex.monthly_summary(sample_df)) == 6


def test_planted_anomalies_are_found(sample_df):
    found = set(ex.detect_anomalies(sample_df)["description"])
    assert {"ZOMATO ONLINE PARTY ORDER", "UBER TRIP AIRPORT", "AMAZON PAY LAPTOP"} <= found


def test_no_false_alarms_on_regular_bills(sample_df):
    flagged = ex.detect_anomalies(sample_df)
    assert not flagged["description"].str.contains("RENT|NETFLIX|SPOTIFY").any()


def test_anomalies_empty_when_too_little_history():
    csv = "date,description,amount\n2026-01-01,SWIGGY,100\n2026-01-02,SWIGGY,9000\n"
    assert ex.detect_anomalies(ex.load_transactions(csv)).empty


TEST_FILES = Path(__file__).resolve().parents[1] / "test_files"


def test_hdfc_style_test_file():
    df = ex.load_transactions(str(TEST_FILES / "hdfc_style_statement.csv"), dayfirst=True)
    assert not df["description"].str.contains("SALARY").any()  # deposits ignored
    assert df["month"].unique().tolist() == ["2026-07", "2026-08", "2026-09"]
    flagged = set(ex.detect_anomalies(df)["description"])
    assert {"POS AMAZON PAY INDIA-IPHONE", "UPI-SWIGGY-SWIGGY8@ICICI-Party order"} <= flagged


def test_negative_amounts_test_file():
    df = ex.load_transactions(str(TEST_FILES / "negative_amounts_statement.csv"))
    assert (df["amount"] > 0).all()
    assert not df["description"].isin(["Salary credit", "Myntra refund"]).any()
    assert "Ola Cabs ride airport" in set(ex.detect_anomalies(df)["description"])


def test_own_categories_test_file():
    df = ex.load_transactions(str(TEST_FILES / "with_own_categories.csv"))
    cats = dict(zip(df["description"], df["category"]))
    assert cats["Mom birthday gift"] == "Gifts"
    assert cats["Swiggy dinner"] == "Food & Dining"  # blank → auto-categorised
