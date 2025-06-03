import streamlit as st
import pandas as pd
import requests
import json
import os
import datetime

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

# ------------------ Currency Conversion ------------------
CACHE_FILE = "currency_rates.json"
BASE_CURRENCY = "INR"

def get_exchange_rates(base=BASE_CURRENCY):
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            cache = json.load(f)
            if cache["date"] == str(datetime.date.today()):
                return cache["rates"]
    url = f"https://api.exchangerate-api.com/v4/latest/{base}"
    response = requests.get(url)
    if response.status_code != 200:
        return None
    data = response.json()
    with open(CACHE_FILE, "w") as f:
        json.dump({"date": str(datetime.date.today()), "rates": data["rates"]}, f)
    return data["rates"]

# ---------------------------------------------------------

gsheet = connect_sheet()
query_params = st.experimental_get_query_params()
username_list = query_params.get("username")
username = username_list[0] if username_list else None

if not username:
    st.error("Logged Out - No username provided")
    st.stop()

st.title(f"Welcome {username}")

if st.sidebar.button("Logout"):
    st.experimental_set_query_params()  # Clear query params
    st.experimental_rerun()

st.sidebar.header("Set Your Budget")

# Fetch budget on first load or if not in session state
if "curr_budget" not in st.session_state:
    st.session_state.curr_budget = get_budget(gsheet, username) or 0.0

budget_input = st.sidebar.number_input(
    "Budget (INR):",
    min_value=0.0,
    value=st.session_state.curr_budget,
    step=100.0,
    format="%.2f"
)

if st.sidebar.button("Update Budget"):
    set_budget(gsheet, username, budget_input)
    # Immediately fetch the updated budget again
    st.session_state.curr_budget = get_budget(gsheet, username) or budget_input
    st.success(f"Budget updated to ₹{st.session_state.curr_budget:,.2f}")

# Use this updated budget throughout the app
curr_budget = st.session_state.curr_budget

# Sidebar - Add Expense Form
st.sidebar.header("Add Expense")
with st.sidebar.form("add_expense"):
    date = st.date_input("Date")
    category = st.selectbox("Category", ["Flights", "Hotels", "Food", "Transport", "Miscellaneous"])
    description = st.text_input("Description")
    amount = st.number_input("Amount", min_value=0.0, format="%.2f")
    currency = st.selectbox("Currency", ["INR", "USD", "EUR", "AED", "JPY", "GBP"])
    location = st.text_input("Location")

    if st.form_submit_button("Add"):
        rates = get_exchange_rates()
        if not rates:
            st.error("Failed to fetch currency exchange rates. Try again later.")
        else:
            rate_to_inr = rates.get(currency)
            if rate_to_inr is None:
                st.error(f"Exchange rate for {currency} not found.")
            else:
                if currency == BASE_CURRENCY:
                    inr_equiv = amount
                else:
                    inr_equiv = round(amount / rate_to_inr, 2)

                add_ex_gsheet(gsheet, username, str(date), category, description, amount, location, currency,
                              inr_equiv)
                st.success(f"Expense added! (₹{inr_equiv} INR equivalent)")

# Load Data
df = load_ex_gsheet(gsheet, username)


# Budget Overview Section
st.markdown("## Budget Overview")
if not df.empty:
    # Use INR Amount for calculations
    total_spent = df["INR Amount"].sum()
    remaining = curr_budget - total_spent

    st.metric(label="Budget (INR)", value=f"₹{curr_budget:,.2f}")
    st.metric(label="Total Spent (INR)", value=f"₹{total_spent:,.2f}")
    st.metric(label="Remaining Budget (INR)", value=f"₹{remaining:,.2f}")

    tabs = st.tabs(["📋 All Expenses", "📌 Category Breakdown", "🛠️ Manage Expense"])

    with tabs[0]:
        st.subheader("📋 All Expenses")
        st.dataframe(df[["Date", "Category", "Description", "Amount", "Currency", "INR Amount", "Location", "Trip","Row"]])

    with tabs[1]:
       st.subheader("📌 Category Breakdown")
       cat_df = df.groupby("Category")["INR Amount"].sum().reset_index()
       st.bar_chart(cat_df.set_index("Category"))

       if curr_budget > 0:
          cat_df["% of Budget Used"] = (cat_df["INR Amount"] / curr_budget * 100).round(2)
       else:
          cat_df["% of Budget Used"] = 0
          st.warning("⚠️ Budget is zero or not set. Percentage calculations are disabled.")

       cat_df["Status"] = cat_df["% of Budget Used"].apply(lambda x: "✅ OK" if x <= 30 else "⚠️ High")
       st.dataframe(cat_df[["Category", "INR Amount", "% of Budget Used", "Status"]])

    with tabs[2]:
        st.subheader("🛠️ Manage Expenses")
        with st.expander("Delete an expense by Row number"):
            if "Row" in df.columns:
                max_row = int(df["Row"].max())
                del_row = st.number_input("Row Number to Delete", min_value=2, max_value=max_row, step=1)
                if st.button("Delete Expense"):
                    delete_expense(gsheet, int(del_row))
                    st.success(f"Deleted row {int(del_row)}")
                    st.rerun()
            else:
                st.info("No expense data available to delete.")

        with st.expander("Update an expense by Row number"):
            if "Row" in df.columns:
                upd_row = st.number_input("Row Number to Update", min_value=2, max_value=int(df["Row"].max()), step=1)
                # Find expense data for upd_row
                upd_expense = df[df["Row"] == upd_row]
                if not upd_expense.empty:
                    upd_expense = upd_expense.iloc[0]
                    with st.form("update_expense_form"):
                        u_date = st.date_input("Date", value=upd_expense["Date"])
                        u_cat = st.selectbox("Category", ["Flights", "Hotels", "Food", "Transport", "Miscellaneous"],
                                             index=["Flights", "Hotels", "Food", "Transport", "Miscellaneous"].index(upd_expense["Category"]))
                        u_desc = st.text_input("Description", value=upd_expense["Description"])
                        u_amt = st.number_input("Amount", min_value=0.0, value=float(upd_expense["Amount"]), format="%.2f")
                        u_curr = st.selectbox("Currency", ["INR", "USD", "EUR", "AED", "JPY", "GBP"],
                                              index=["INR", "USD", "EUR", "AED", "JPY", "GBP"].index(upd_expense["Currency"]))
                        u_loc = st.text_input("Location", value=upd_expense["Location"])
                        u_trip = st.text_input("Trip Name", value=upd_expense["Trip"])

                        if st.form_submit_button("Update Expense"):
                            rates = get_exchange_rates()
                            if not rates or u_curr not in rates:
                                st.error("Exchange rates not available. Try again later.")
                            else:
                                if u_curr == BASE_CURRENCY:
                                    u_inr = u_amt
                                else:
                                    u_inr = round(u_amt / rates[u_curr], 2)
                                update_expense(gsheet, upd_row, username, str(u_date), u_cat, u_desc, u_amt, u_loc, u_trip, u_curr, u_inr)
                                st.success(f"Expense in row {upd_row} updated!")
                                st.experimental_rerun()
                else:
                    st.info("Selected row not found in data.")
            else:
                st.info("No expense data available to update.")

    # Smart Spend Insights Section
    st.markdown("---")
    st.subheader("💡 Smart Spend Insights")

    def generate_insights(df, budget):
        insights = []
        if df.empty:
            return [("No insights available. Add some expenses first.", "info")]

        total_spent = df["INR Amount"].sum()
        daily_avg = df.groupby("Date")["INR Amount"].sum().mean()

        if total_spent > budget:
            insights.append(("🚨 You’ve exceeded your total budget. Consider reviewing high-expense categories.", "danger"))
        elif budget - total_spent < budget * 0.2:
            insights.append(("⚠️ You're close to exhausting your budget. Plan remaining days carefully.", "warning"))

        food_exp = df[df["Category"] == "Food"]["INR Amount"].sum()
        if food_exp > total_spent * 0.3:
            insights.append(("🍽️ High food expenses — try exploring cheaper local dining options.", "warning"))

        hotel_exp = df[df["Category"] == "Hotels"]["INR Amount"].sum()
        if hotel_exp > total_spent * 0.4:
            insights.append(("🏨 Hotels are taking a big chunk — check for cheaper stays next time.", "warning"))

        transport_exp = df[df["Category"] == "Transport"]["INR Amount"].sum()
        if transport_exp < total_spent * 0.1:
            insights.append(("🚗 Nice! You’re saving on transport. Keep it up!", "success"))

        if daily_avg > budget / 10:
            insights.append((f"📈 Your average daily spend is ₹{daily_avg:.2f} — adjust to stay on track.", "warning"))

        return insights

    def styled_message(message, style_type):
        styles = {
            "danger": "background-color:#ffdddd; color:#a70000; padding:10px; border-radius:5px;",
            "warning": "background-color:#fff4cc; color:#665c00; padding:10px; border-radius:5px;",
            "success": "background-color:#ddffdd; color:#1a6f1a; padding:10px; border-radius:5px;",
            "info": "background-color:#d9edf7; color:#31708f; padding:10px; border-radius:5px;"
        }
        style = styles.get(style_type, styles["info"])
        return f"<div style='{style}'>{message}</div>"

    insights = generate_insights(df, curr_budget)
    for msg, stype in insights:
        st.markdown(styled_message(msg, stype), unsafe_allow_html=True)

else:
    st.info("No expense data found. Please add expenses using the form on the left sidebar.")
