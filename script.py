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

st.set_page_config(page_title="Travel Expense Tracker", layout="wide")

gsheet = connect_sheet()
query_params = st.experimental_get_query_params()
username = query_params.get("username", [None])[0]

if not username:
    st.error("Logged Out")
    st.stop()

st.title(f"Welcome {username}")

if st.sidebar.button("Logout"):
    st.experimental_set_query_params()
    st.experimental_rerun()

st.sidebar.header("Set Your Budget")
curr_budget = get_budget(gsheet, username) or 0.0
budget_input = st.sidebar.number_input("Budget :", min_value=0.0, value=curr_budget, step=100.0, format="%.2f")
if st.sidebar.button("Update Budget"):
    set_budget(gsheet, username, budget_input)
    st.sidebar.success("Budget updated!")

st.sidebar.header("Add Expense")
with st.sidebar.form("add_expense"):
    date = st.date_input("Date")
    category = st.selectbox("Category", ["Flights", "Hotels", "Food", "Transport", "Miscellaneous"])
    description = st.text_input("Description")
    amount = st.number_input("Amount", min_value=0.0, format="%.2f")
    location = st.text_input("Location")
    if st.form_submit_button("Add"):
        add_ex_gsheet(gsheet, username, str(date), category, description, amount, location)
        st.success("Expense added!")

df = load_ex_gsheet(gsheet, username)

st.markdown("## Budget Overview")
if not df.empty:
    total_spend = df["Amount"].sum()
    remained_budget = curr_budget - total_spend
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Budget", f"₹{curr_budget:,.2f}")
    col2.metric("Total Spend", f"₹{total_spend:,.2f}")
    col3.metric("Remaining Amount", f"₹{remained_budget:,.2f}")

    st.subheader("Category Breakdown")
    summary = df.groupby("Category")["Amount"].sum()
    st.bar_chart(summary)

    st.markdown("---")
    st.subheader("Smart Spend Insights")

    def generate_insights(df, budget):
        insights = []
        if df.empty:
            return ["No expenses yet. Add some to get insights."]
        total_spent = df["Amount"].sum()
        if total_spent > budget:
            insights.append("You’ve exceeded your total budget. Review your high-expense categories!")
        elif budget - total_spent < budget * 0.2:
            insights.append("You're close to exhausting your budget. Plan carefully!")
        food_exp = df[df["Category"] == "Food"]["Amount"].sum()
        if food_exp > total_spent * 0.3:
            insights.append("High food expenses — try exploring cheaper local dining.")
        hotel_exp = df[df["Category"] == "Hotels"]["Amount"].sum()
        if hotel_exp > total_spent * 0.4:
            insights.append("Hotels are a big chunk — check for budget stays.")
        return insights

    insights = generate_insights(df, curr_budget)
    for tip in insights:
        st.write(f"- {tip}")
else:
    st.info("No expenses added yet. Use the sidebar to start tracking your expenses.")
