---
title: Personal Expense Analyzer
emoji: 💸
colorFrom: green
colorTo: blue
sdk: docker
app_port: 8501
pinned: false
---

# 💸 Personal Expense Analyzer

Upload a bank-statement CSV and get a dashboard. It sorts every transaction into a category, shows where your money goes each month, and flags transactions that are unusually large for their category.

Works with your own bank export (column names like `Narration` / `Withdrawal Amt.` are recognised) or with the bundled sample data.

## What it shows

- **Data cleaning:** auto-detects date/description/amount columns across bank formats, strips `₹` and `,` from amounts, handles debits shown as negative numbers, and drops income/refunds.
- **Feature engineering:** keyword-based categorisation (Food, Transport, Fuel, Bills, Shopping…) with word-boundary matching, so `OLA CABS` → Transport but `COCA COLA` is not.
- **Exploratory analysis:** totals, share per category, monthly trend stacked by category.
- **Anomaly detection:** a robust **modified z-score** (median and MAD instead of mean and standard deviation), computed per category. A transaction is flagged only if it is statistically extreme **and** at least 3× the typical amount. On the sample data it finds exactly the 3 planted anomalies (a ₹72,000 laptop, a ₹6,800 party order and a ₹3,900 airport cab) with no false alarms.
- **Tests:** 18 tests for parsing, categorisation, summaries and anomaly detection, plus headless tests of the dashboard.

## Example output (`python analyze.py`)

```
347 spending transactions, 01 Apr 2026 – 30 Sep 2026

== Unusual transactions ==
      date               description      category  amount  typical_amount
2026-08-29         AMAZON PAY LAPTOP      Shopping 72000.0         1427.71
2026-05-11 ZOMATO ONLINE PARTY ORDER Food & Dining  6800.0          445.38
2026-07-05         UBER TRIP AIRPORT     Transport  3900.0          291.33
```

## Project structure

```
DS_Expense_Analyzer/
├── expenses.py                  # load + clean CSV, categorise, summaries, anomaly detection, sample generator
├── analyze.py                   # command-line report
├── app.py                       # Streamlit dashboard
├── data/sample_transactions.csv # 6 months of realistic fake transactions
├── tests/
│   ├── test_expenses.py         # analysis tests
│   └── test_app.py              # dashboard smoke tests (no browser needed)
├── requirements.txt
└── Dockerfile                   # to run anywhere with Docker
```

## How to run (step by step)

You need **Python 3.10 or newer**. Check with `python --version` (on Windows you may need `py --version`).

### 1. Get the code

```bash
git clone https://github.com/<your-username>/DS_Expense_Analyzer.git
cd DS_Expense_Analyzer
```

### 2. Create a virtual environment and install packages

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
If PowerShell blocks the activate script, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then try again.

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Run the tests

```bash
python -m pytest -v
```
Expected: `18 passed` (about 2 seconds).

### 4. Command-line report

```bash
python analyze.py                          # sample data
python analyze.py path/to/statement.csv    # your own file
python analyze.py statement.csv --dayfirst # if dates look like 31/01/2026
```

### 5. Start the dashboard

```bash
streamlit run app.py
```
Open http://localhost:8501. It starts with the sample data. Upload your own CSV from the sidebar, and use the **sensitivity** slider to flag more or fewer anomalies.

## Your CSV format

You need three columns, in any order. Any of these names work (capitalisation doesn't matter):

| Needed | Accepted column names |
|---|---|
| date | `date`, `transaction date`, `txn date`, `value date`, `posting date` |
| description | `description`, `narration`, `details`, `merchant`, `particulars`, `remarks` |
| amount | `amount`, `debit`, `withdrawal`, `withdrawal amt.`, `debit amount` |
| category *(optional)* | `category`. If present, your own labels are kept. |

> `.gitignore` ignores every `*.csv` except the sample, so your real statements never get committed by accident.

To teach it new merchants, add keywords to `CATEGORY_KEYWORDS` in `expenses.py`.

## Deploy free on Streamlit Community Cloud

1. Sign in at https://share.streamlit.io with your GitHub account.
2. Click **Create app → Deploy a public app from GitHub**.
3. Fill in **Repository** `<your-username>/DS_Expense_Analyzer`, **Branch** `main` and **Main file path** `app.py`.
4. Click **Deploy**.

After a few minutes the app is live at a public `https://<name>.streamlit.app` link. Apps with no visitors for 12 hours go to sleep; the next visitor wakes them with one click.

## Run with Docker (optional)

```bash
docker build -t expense-analyzer .
docker run -p 8501:8501 expense-analyzer
```

## Tech stack

Python · pandas · NumPy · Streamlit · pytest · Docker
