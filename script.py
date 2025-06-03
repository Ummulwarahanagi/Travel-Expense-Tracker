import streamlit as st
import pandas as pd
from google_sheets_utils import (
    connect_sheet,
    add_ex_gsheet,
    load_ex_gsheet,
    delete_expense,
    update_expense,
    set_budget,
    get_budget
)
import requests

# --- Streamlit Page Config ---
st.set_page_config(page_title="Travel Expense Tracker", layout="wide")

# --- Connect to Google Sheet ---
gsheet = connect_sheet()

# --- Get Username from Query Params ---
query_params = st.query_params
username = query_params.get("username", None)

if not username:
    st.error("Logged Out")
    st.stop()

st.title(f"Welcome {username}")

# --- Logout Button ---
if st.sidebar.button("Logout"):
    st.query_params.clear()
    st.rerun()

# --- Budget Sidebar ---
st.sidebar.header("💰 Set Your Budget")

curr_budget = get_budget(gsheet, username)
if curr_budget is None or not isinstance(curr_budget, (int, float)):
    curr_budget = 0.0

budget_input = st.sidebar.number_input("Budget :", min_value=0.0, value=curr_budget, step=100.0, format="%.2f")

if st.sidebar.button("Update Budget"):
    set_budget(gsheet, username, budget_input)
    st.sidebar.success("Budget updated successfully")

# --- Add Expense Sidebar ---
st.sidebar.header("➕ Add Expense")
with st.sidebar.form("add_expense"):
    date = st.date_input("Date")
    category = st.selectbox("Category", ["Flights", "Hotels", "Food", "Transport", "Miscellaneous"])
    description = st.text_input("Description")
    amount = st.number_input("Amount", min_value=0.0, format="%.2f")
    location = st.text_input("Location")

    if st.form_submit_button("Add"):
        add_ex_gsheet(gsheet, username, str(date), category, description, amount, location)
        st.success("Expense added!")

# --- Currency Converter Sidebar ---
st.sidebar.header("Currency Converter")
currencies = ["USD", "EUR", "INR", "GBP", "JPY", "AUD", "CAD", "CNY"]

from_currency = st.sidebar.selectbox("From", currencies, index=2)
to_currency = st.sidebar.selectbox("To", currencies, index=0)
conv_amount = st.sidebar.number_input("Amount", min_value=0.0, value=1.0, step=0.1, format="%.2f")

if st.sidebar.button("Convert"):
    example_rates = {
        ("INR", "USD"): 0.012, ("INR", "EUR"): 0.011, ("INR", "GBP"): 0.0098,
        ("INR", "JPY"): 1.57, ("INR", "AUD"): 0.018, ("INR", "CAD"): 0.016, ("INR", "CNY"): 0.083,
        ("USD", "INR"): 82.5, ("EUR", "INR"): 88.5, ("GBP", "INR"): 102.0,
        ("JPY", "INR"): 0.64, ("AUD", "INR"): 56.0, ("CAD", "INR"): 61.5, ("CNY", "INR"): 12.0,
        ("EUR", "USD"): 1.1, ("USD", "EUR"): 0.91, ("GBP", "USD"): 1.3,
        ("USD", "GBP"): 0.77, ("JPY", "USD"): 0.007, ("USD", "JPY"): 140,
        ("AUD", "USD"): 0.67, ("USD", "AUD"): 1.5, ("CAD", "USD"): 0.74,
        ("USD", "CAD"): 1.35, ("CNY", "USD"): 0.14, ("USD", "CNY"): 7.1,
    }

    rate = example_rates.get((from_currency, to_currency), None)
    if rate:
        converted = conv_amount * rate
        st.sidebar.success(f"{conv_amount:.2f} {from_currency} = {converted:.2f} {to_currency}")
    else:
        st.sidebar.error("Currency pair not supported yet.")

# --- Load User Expenses ---
df = load_ex_gsheet(gsheet, username)

# --- Budget Overview Section ---
st.markdown("📊 **Budget Overview**")

if not df.empty:
    total_spend = df["Amount"].sum()
    remained_budget = curr_budget - total_spend

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Budget", f"₹{curr_budget:,.2f}")
    col2.metric("Total Spend", f"₹{total_spend:,.2f}")
    col3.metric("Remaining Amount", f"₹{remained_budget:,.2f}")

    tabs = st.tabs(["📋 All Expenses", "📌 Category Breakdown", "🛠️ Manage Expense"])

    with tabs[0]:
        st.subheader("📋 All Expenses")
        st.dataframe(df)

    with tabs[1]:
        st.subheader("📌 Category Breakdown")
        summary = df.groupby("Category")["Amount"].sum().reset_index()
        st.bar_chart(summary, x="Category", y="Amount")

        summary["% Used"] = (summary["Amount"] / curr_budget * 100).round(2)
        summary["Status"] = summary["% Used"].apply(lambda x: "✅ OK" if x <= 30 else "⚠️ High")
        st.dataframe(summary[["Category", "Amount", "% Used", "Status"]])

    with tabs[2]:
        st.subheader("🛠️ Manage Expense")

        st.markdown("### 🗑️ Delete Expense")
        with st.expander("Delete an expense (enter the row number):"):
            if not df.empty and "Row" in df.columns:
                max_row = int(df["Row"].max())
                delete_row = st.number_input("Row Number", min_value=2, max_value=max_row, step=1)
                if st.button("Delete"):
                    delete_expense(gsheet, int(delete_row))
                    st.success(f"Deleted row: {int(delete_row)}")
                    st.rerun()
            else:
                st.warning("No data available to delete.")

        st.markdown("### ✏️ Update Expense")
        with st.expander("Update an expense"):
            if not df.empty and "Row" in df.columns:
                update_row = st.number_input("Row to Update", min_value=2, max_value=int(df["Row"].max()), step=1)
                with st.form("update_expense"):
                    u_date = st.date_input("Date", key="u_date")
                    u_cat = st.selectbox("Category", ["Flights", "Hotels", "Food", "Transport", "Miscellaneous"], key="u_cat")
                    u_desc = st.text_input("Description", key="u_desc")
                    u_amt = st.number_input("Amount", min_value=0.0, format="%.2f", key="u_amt")
                    u_loc = st.text_input("Location", key="u_loc")
                    if st.form_submit_button("Update"):
                        update_expense(gsheet, int(update_row), username, str(u_date), u_cat, u_desc, u_amt, u_loc)
                        st.success(f"Updated expense in row {int(update_row)}")
                        st.experimental_rerun()
            else:
                st.warning("No data available to update.")

    # --- Smart Spend Insights ---
    st.markdown("---")
    st.subheader("💡 Smart Spend Insights")

    def generate_insights(df, budget):
        insights = []

        if df.empty:
            return ["No insights available. Add some expenses first."]

        total_spent = df["Amount"].sum()
        daily_avg = df.groupby("Date")["Amount"].sum().mean()

        if total_spent > budget:
            insights.append("🚨 You’ve exceeded your total budget. Consider reviewing high-expense categories.")
        elif budget - total_spent < budget * 0.2:
            insights.append("⚠️ You're close to exhausting your budget. Plan remaining days carefully.")

        food_exp = df[df["Category"] == "Food"]["Amount"].sum()
        if food_exp > total_spent * 0.3:
            insights.append("🍽️ High food expenses — try exploring cheaper local dining options.")

        hotel_exp = df[df["Category"] == "Hotels"]["Amount"].sum()
        if hotel_exp > total_spent * 0.4:
            insights.append("🏨 Hotels are taking a big chunk — check for cheaper stays next time.")

        transport_exp = df[df["Category"] == "Transport"]["Amount"].sum()
        if transport_exp < total_spent * 0.1:
            insights.append("🚗 Nice! You’re saving on transport. Keep it up!")

        if daily_avg > budget / 10:
            insights.append(f"📈 Your average daily spend is ₹{daily_avg:.2f} — adjust to stay on track.")

        return insights

    insights = generate_insights(df, curr_budget)
    if insights:
        for tip in insights:
            st.info(tip)
    else:
        st.info("No insights available yet. Add some expenses.")

else:
    st.info("No expenses added yet. Use the sidebar to start tracking your expenses.")
    st.markdown("---")
    st.subheader("💡 Smart Spend Insights")
    st.info("No insights available yet. Add some expenses to see tips here.")
