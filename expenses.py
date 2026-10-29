"""Core analysis: load a bank-statement CSV, categorise spending, summarise, flag anomalies."""

from __future__ import annotations

import io
import re
from pathlib import Path

import numpy as np
import pandas as pd

# Column names that different banks use for the same thing (lower-case).
COLUMN_ALIASES = {
    "date": ["date", "transaction date", "txn date", "value date", "posting date"],
    "description": ["description", "narration", "details", "merchant", "particulars",
                    "name", "remarks", "transaction details"],
    "amount": ["amount", "debit", "withdrawal", "withdrawal amt.", "debit amount", "value"],
    "category": ["category"],
}

# Keyword rules: the first category whose keyword appears in the description wins.
CATEGORY_KEYWORDS = {
    "Food & Dining": ["swiggy", "zomato", "restaurant", "cafe", "coffee", "starbucks", "domino",
                      "pizza", "mcdonald", "kfc", "burger", "dining", "bakery"],
    "Groceries": ["bigbasket", "blinkit", "zepto", "dmart", "grocery", "supermarket",
                  "reliance fresh", "walmart", "instamart"],
    "Fuel": ["fuel", "petrol", "diesel", "hp pump", "indian oil", "bharat petroleum", "shell"],
    "Transport": ["uber", "ola", "rapido", "metro", "irctc", "railway", "parking", "toll", "lyft"],
    "Shopping": ["amazon", "flipkart", "myntra", "ajio", "nykaa", "mall", "store", "meesho"],
    "Bills & Utilities": ["electricity", "water bill", "gas bill", "broadband", "airtel", "jio",
                          "vodafone", "mobile recharge", "internet", "dth", "bescom"],
    "Rent & Housing": ["rent", "maintenance", "society", "landlord"],
    "Entertainment": ["netflix", "spotify", "prime video", "hotstar", "bookmyshow", "movie",
                      "pvr", "inox", "youtube premium", "steam"],
    "Health": ["pharmacy", "apollo", "medplus", "hospital", "clinic", "doctor", "1mg",
               "pharmeasy", "gym", "cult.fit"],
    "Travel": ["makemytrip", "goibibo", "airline", "indigo", "air india", "hotel", "oyo",
               "airbnb", "booking.com", "cleartrip"],
    "Education": ["udemy", "coursera", "course", "school", "college", "tuition", "books"],
    "Transfers": ["upi transfer", "neft", "imps", "atm", "cash withdrawal"],
}


def _find_column(columns: list[str], wanted: str) -> str | None:
    lower = {c.strip().lower(): c for c in columns}
    for alias in COLUMN_ALIASES[wanted]:
        if alias in lower:
            return lower[alias]
    return None


# Keywords must start at a word boundary, so "ola" matches "OLA CABS" but not "coca cola".
_CATEGORY_PATTERNS = {
    cat: re.compile("|".join(r"\b" + re.escape(k) for k in kws))
    for cat, kws in CATEGORY_KEYWORDS.items()
}


def categorize(description: str) -> str:
    text = str(description).lower()
    for category, pattern in _CATEGORY_PATTERNS.items():
        if pattern.search(text):
            return category
    return "Other"


def load_transactions(source, dayfirst: bool = False) -> pd.DataFrame:
    """Read a CSV (path, file object or text) into columns: date, description, amount, category.

    - Common bank column names are recognised (e.g. "Narration", "Withdrawal Amt.").
    - If most amounts are negative (debits shown as minus), signs are flipped so spending is positive.
    - Rows with amount <= 0 after that are income / refunds and are dropped from spending.
    - If the CSV already has a "category" column it is kept; otherwise keyword rules fill it.
    """
    if isinstance(source, str) and not Path(source).exists() and "\n" in source:
        source = io.StringIO(source)
    raw = pd.read_csv(source)

    cols = {k: _find_column(list(raw.columns), k) for k in COLUMN_ALIASES}
    missing = [k for k in ("date", "description", "amount") if cols[k] is None]
    if missing:
        raise ValueError(f"Could not find column(s) {missing}. Found: {list(raw.columns)}")

    df = pd.DataFrame({
        "date": pd.to_datetime(raw[cols["date"]], errors="coerce", dayfirst=dayfirst),
        "description": raw[cols["description"]].astype(str).str.strip(),
        "amount": pd.to_numeric(
            raw[cols["amount"]].astype(str).str.replace(r"[^\d.\-]", "", regex=True),
            errors="coerce"),
    })
    if cols["category"]:
        df["category"] = raw[cols["category"]].fillna("").astype(str).str.strip()
    else:
        df["category"] = ""

    df = df.dropna(subset=["date", "amount"])
    if (df["amount"] < 0).mean() > 0.5:
        df["amount"] = -df["amount"]
    df = df[df["amount"] > 0].copy()

    needs_cat = df["category"].eq("")
    df.loc[needs_cat, "category"] = df.loc[needs_cat, "description"].map(categorize)
    df["month"] = df["date"].dt.to_period("M").astype(str)
    return df.sort_values("date").reset_index(drop=True)


def category_summary(df: pd.DataFrame) -> pd.DataFrame:
    out = (df.groupby("category")["amount"]
             .agg(total="sum", transactions="count", average="mean")
             .sort_values("total", ascending=False))
    out["share_%"] = 100 * out["total"] / out["total"].sum()
    return out.round(2)


def monthly_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Months as rows, categories as columns, values = total spend."""
    return df.pivot_table(index="month", columns="category", values="amount",
                          aggfunc="sum", fill_value=0).round(2)


def detect_anomalies(df: pd.DataFrame, threshold: float = 3.5, min_count: int = 5,
                     min_ratio: float = 3.0) -> pd.DataFrame:
    """Flag unusually large transactions within their own category.

    A transaction is flagged when BOTH hold:
      1. its robust "modified z-score" (Iglewicz & Hoaglin), 0.6745 * (x - median) / MAD,
         is above `threshold`. Unlike mean/std, median/MAD aren't dragged up by the very
         outliers we want to catch;
      2. it is at least `min_ratio` times the category's typical (median) amount, so small
         wobbles like a slightly higher electricity bill aren't reported.
    Categories with fewer than `min_count` transactions are skipped (not enough history).
    """
    flagged = []
    for _, group in df.groupby("category"):
        if len(group) < min_count:
            continue
        median = group["amount"].median()
        mad = (group["amount"] - median).abs().median()
        if mad == 0:
            continue
        score = 0.6745 * (group["amount"] - median) / mad
        mask = (score > threshold) & (group["amount"] >= min_ratio * median)
        hits = group[mask].copy()
        hits["typical_amount"] = round(median, 2)
        hits["score"] = score[mask].round(1)
        flagged.append(hits)
    if not flagged:
        return df.iloc[0:0].assign(typical_amount=[], score=[])
    return pd.concat(flagged).sort_values("score", ascending=False)


def generate_sample_data(months: int = 6, seed: int = 7, end: str = "2026-09-30") -> pd.DataFrame:
    """Realistic fake statement (INR) with a few planted anomalies, for demos and tests."""
    rng = np.random.default_rng(seed)
    end_ts = pd.Timestamp(end)
    start = (end_ts.to_period("M") - (months - 1)).start_time
    days = pd.date_range(start, end_ts, freq="D")

    # (description, typical amount, spread, expected transactions per day)
    patterns = [
        ("SWIGGY ORDER", 450, 150, 0.35), ("ZOMATO ONLINE", 520, 180, 0.25),
        ("STARBUCKS COFFEE", 380, 60, 0.12), ("BLINKIT GROCERY", 900, 300, 0.2),
        ("BIGBASKET", 1800, 500, 0.06), ("UBER TRIP", 320, 120, 0.3),
        ("OLA CABS", 280, 100, 0.15), ("HP PETROL PUMP FUEL", 2000, 400, 0.05),
        ("AMAZON PAY", 1500, 900, 0.1), ("MYNTRA FASHION", 2200, 900, 0.03),
        ("APOLLO PHARMACY", 650, 250, 0.04), ("BOOKMYSHOW MOVIE", 700, 200, 0.04),
        ("UDEMY COURSE", 499, 50, 0.01),
    ]
    rows = []
    for day in days:
        for desc, mu, sd, rate in patterns:
            for _ in range(rng.poisson(rate)):
                rows.append((day, desc, max(50, round(rng.normal(mu, sd), 2))))
        if day.day == 1:
            rows.append((day, "RENT TO LANDLORD", 22000.0))
            rows.append((day, "NETFLIX SUBSCRIPTION", 649.0))
            rows.append((day, "SPOTIFY PREMIUM", 119.0))
        if day.day == 5:
            rows.append((day, "BESCOM ELECTRICITY BILL", round(rng.normal(1400, 250), 2)))
            rows.append((day, "AIRTEL BROADBAND", 999.0))
        if day.day == 1:
            rows.append((day, "SALARY CREDIT ACME CORP", -85000.0))  # income, gets dropped

    # Planted anomalies: unusually large spends in otherwise regular categories
    rows += [
        (days[40], "ZOMATO ONLINE PARTY ORDER", 6800.0),
        (days[95], "UBER TRIP AIRPORT", 3900.0),
        (days[150], "AMAZON PAY LAPTOP", 72000.0),
    ]
    df = pd.DataFrame(rows, columns=["Date", "Description", "Amount"]).sort_values("Date")
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
    return df.reset_index(drop=True)
