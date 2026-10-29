"""Streamlit dashboard.  Run:  streamlit run app.py"""

from pathlib import Path

import streamlit as st

import expenses as ex

SAMPLE = Path(__file__).parent / "data" / "sample_transactions.csv"

st.set_page_config(page_title="Expense Analyzer", page_icon="💸", layout="wide")
st.title("💸 Personal Expense Analyzer")
st.caption("Upload a bank-statement CSV (needs date, description and amount columns) "
           "or explore the sample data.")

with st.sidebar:
    st.header("Data")
    uploaded = st.file_uploader("Bank statement CSV", type="csv")
    dayfirst = st.checkbox("Dates are DD/MM/YYYY", value=False)
    threshold = st.slider("Anomaly sensitivity (lower = more flags)", 2.0, 6.0, 3.5, 0.5)
    st.markdown("Your file is processed in memory and never stored.")

try:
    if uploaded is not None:
        df = ex.load_transactions(uploaded, dayfirst=dayfirst)
        st.success(f"Loaded **{uploaded.name}**")
    else:
        if not SAMPLE.exists():
            SAMPLE.parent.mkdir(exist_ok=True)
            ex.generate_sample_data().to_csv(SAMPLE, index=False)
        df = ex.load_transactions(SAMPLE)
        st.info("Showing **sample data**. Upload your own CSV in the sidebar.")
except ValueError as e:
    st.error(str(e))
    st.stop()

if df.empty:
    st.warning("No spending transactions found in this file.")
    st.stop()

# Filters
categories = sorted(df["category"].unique())
picked = st.multiselect("Categories", categories, default=categories)
view = df[df["category"].isin(picked)]
if view.empty:
    st.warning("Pick at least one category.")
    st.stop()

# KPIs
months = view["month"].nunique()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total spent", f"₹{view['amount'].sum():,.0f}")
c2.metric("Avg per month", f"₹{view['amount'].sum() / months:,.0f}")
c3.metric("Transactions", f"{len(view):,}")
c4.metric("Top category", ex.category_summary(view).index[0])

left, right = st.columns(2)
with left:
    st.subheader("Spending by category")
    summary = ex.category_summary(view)
    st.bar_chart(summary["total"], horizontal=True)
    st.dataframe(summary, width="stretch")
with right:
    st.subheader("Monthly trend")
    st.bar_chart(ex.monthly_summary(view))
    st.caption("Stacked by category")

st.subheader("🚨 Unusual transactions")
anomalies = ex.detect_anomalies(view, threshold=threshold)
if anomalies.empty:
    st.write("Nothing unusual at this sensitivity.")
else:
    st.write(f"{len(anomalies)} transaction(s) are far above what you usually spend in that category:")
    st.dataframe(
        anomalies[["date", "description", "category", "amount", "typical_amount", "score"]]
        .assign(date=lambda d: d["date"].dt.date),
        hide_index=True, width="stretch")

with st.expander("All transactions"):
    st.dataframe(view.assign(date=view["date"].dt.date), hide_index=True, width="stretch")
    st.download_button("Download categorised CSV", view.to_csv(index=False),
                       file_name="categorised_transactions.csv")
