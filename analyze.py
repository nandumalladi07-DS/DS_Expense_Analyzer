"""Command-line report.

Usage:
    python analyze.py                       # analyse the bundled sample data
    python analyze.py my_statement.csv      # analyse your own CSV
    python analyze.py my.csv --dayfirst     # dates like 31/01/2026
    python analyze.py --make-sample         # (re)create data/sample_transactions.csv
"""

import argparse
from pathlib import Path

import pandas as pd

import expenses as ex

SAMPLE = Path(__file__).parent / "data" / "sample_transactions.csv"


def main():
    parser = argparse.ArgumentParser(description="Personal expense analyzer")
    parser.add_argument("csv", nargs="?", default=str(SAMPLE))
    parser.add_argument("--dayfirst", action="store_true", help="dates are DD/MM/YYYY")
    parser.add_argument("--make-sample", action="store_true", help="write the sample CSV and exit")
    args = parser.parse_args()

    if args.make_sample:
        SAMPLE.parent.mkdir(exist_ok=True)
        ex.generate_sample_data().to_csv(SAMPLE, index=False)
        print(f"Wrote {SAMPLE}")
        return

    df = ex.load_transactions(args.csv, dayfirst=args.dayfirst)
    pd.set_option("display.width", 120)
    print(f"{len(df)} spending transactions, {df['date'].min():%d %b %Y} – {df['date'].max():%d %b %Y}")
    print(f"Total spent: {df['amount'].sum():,.2f}\n")
    print("== By category ==")
    print(ex.category_summary(df).to_string())
    print("\n== Monthly totals ==")
    print(df.groupby("month")["amount"].sum().round(2).to_string())
    print("\n== Unusual transactions ==")
    anomalies = ex.detect_anomalies(df)
    if anomalies.empty:
        print("None found.")
    else:
        print(anomalies[["date", "description", "category", "amount", "typical_amount"]]
              .to_string(index=False))


if __name__ == "__main__":
    main()
