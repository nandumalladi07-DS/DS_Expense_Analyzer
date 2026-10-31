# Test files: bank statements to upload

Three fake statements in different real-world formats. Upload them in the app's sidebar (**Bank statement CSV**) or pass them to `analyze.py`.

| File | Format it imitates | Tick "DD/MM/YYYY"? | What you should see |
|---|---|---|---|
| `hdfc_style_statement.csv` | Indian bank export: `Txn Date`, `Narration`, separate `Withdrawal Amt.` / `Deposit Amt.` columns, `1,234.00` style numbers | **Yes** | 3 months (Jul–Sep 2026), salary deposits ignored, **₹79,900 iPhone** and **₹5,400 party order** flagged as unusual |
| `negative_amounts_statement.csv` | Card/app export where spending is negative and income positive | No | 4 months, salary and the Myntra refund ignored, **₹2,600 airport cab** flagged |
| `with_own_categories.csv` | A CSV with your own `category` column, some left blank | No | Your labels (Gifts, Donations, Electronics…) kept; blank ones filled automatically |

From the terminal:
```bash
python analyze.py test_files/hdfc_style_statement.csv --dayfirst
python analyze.py test_files/negative_amounts_statement.csv
python analyze.py test_files/with_own_categories.csv
```
