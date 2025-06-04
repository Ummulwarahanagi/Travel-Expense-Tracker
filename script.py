import streamlit as st
import pandas as pd
from google_sheets_utils import (
    connect_sheet,
    add_expense_with_trip,
    load_expense_with_trip,
    get_user_trips,
    get_budget,
    set_budget,
)

st.set_page_config(page_title="Travel Expense Tracker", layout="wide")

# --- Get Username from query params ---
query_params = st.experimental_get_query_params()
username = query_params.get("username", [None])[0]

if not username:
    st.error("Logged Out")
    st.stop()

gsheet = connect_sheet()

st.title(f"Welcome {username}")
st.sidebar.header("🎒 Trip Manager")

# Fetch trips
user_trips = get_user_trips(gsheet, username)
default_trips = ["General"]
all_trips = sorted(list(set(user_trips + default_trips)))

# Input for NEW trip
trip_input = st.sidebar.text_input("➕ Start a New Trip", key="new_trip")
# Select from EXISTING trips
existing_trip = st.sidebar.selectbox("📜 Or Select Existing Trip", options=all_trips, key="existing_trip")

# Logic: if new trip is entered, prioritize that
current_trip = trip_input.strip() if trip_input.strip() else existing_trip
st.sidebar.success(f"You're working on: `{current_trip}`")

# Logout
if st.sidebar.button("Logout"):
    st.experimental_set_query_params()
    st.experimental_rerun()

# Budget
st.sidebar.header("💰 Set Budget")
curr_budget = get_budget(gsheet, username)
try:
    curr_budget = float(curr_budget)
except (TypeError, ValueError):
    curr_budget = 0.0

budget_input = st.sidebar.number_input("Budget:", min_value=0.0, value=curr_budget, step=100.0)
if st.sidebar.button("Update Budget"):
    set_budget(gsheet, username, budget_input)
    st.sidebar.success("✅ Budget updated")

# Add Expense
st.sidebar.header("➕ Add Expense")
with st.sidebar.form("add_expense"):
    date = st.date_input("Date")
    category = st.selectbox("Category", ["Flights", "Hotels", "Food", "Transport", "Miscellaneous"])
    description = st.text_input("Description")
    amount = st.number_input("Amount", min_value=0.0, format="%.2f")
    location = st.text_input("Location")
    if st.form_submit_button("Add"):
        add_expense_with_trip(
            gsheet,
            username,
            str(date),
            category,
            description,
            amount,
            location,
            trip=current_trip
        )
        st.success(f"✅ Expense added to `{current_trip}`!")

# View Trip History
st.header(f"📂 Expense History for: `{current_trip}`")
df_expenses = load_expense_with_trip(gsheet, username, trip=current_trip)

if df_expenses.empty:
    st.warning("No expenses found for this trip.")
else:
    st.dataframe(df_expenses)

    # Optional: Total Expense Summary
    if "amount" in df_expenses.columns:
        total = df_expenses["amount"].sum()
        st.success(f"Total spent on `{current_trip}`: ₹{total:.2f}")


if df_expenses.empty:
    st.info("No expenses found for this trip.")
else:
    st.dataframe(df_expenses)


st.sidebar.header("Currency Converter")
currencies = ["USD", "EUR", "INR", "GBP", "JPY", "AUD", "CAD", "CNY"]

from_currency = st.sidebar.selectbox("From", currencies, index=2)
to_currency = st.sidebar.selectbox("To", currencies, index=0)
conv_amount = st.sidebar.number_input(
    "Amount", min_value=0.0, value=1.0, step=0.1, format="%.2f"
)

if st.sidebar.button("Convert"):
    example_rates = {
        ("INR", "USD"): 0.012,
        ("INR", "EUR"): 0.011,
        ("INR", "GBP"): 0.0098,
        ("INR", "JPY"): 1.57,
        ("INR", "AUD"): 0.018,
        ("INR", "CAD"): 0.016,
        ("INR", "CNY"): 0.083,
        ("USD", "INR"): 82.5,
        ("EUR", "INR"): 88.5,
        ("GBP", "INR"): 102.0,
        ("JPY", "INR"): 0.64,
        ("AUD", "INR"): 56.0,
        ("CAD", "INR"): 61.5,
        ("CNY", "INR"): 12.0,
        ("EUR", "USD"): 1.1,
        ("USD", "EUR"): 0.91,
        ("GBP", "USD"): 1.3,
        ("USD", "GBP"): 0.77,
        ("JPY", "USD"): 0.007,
        ("USD", "JPY"): 140,
        ("AUD", "USD"): 0.67,
        ("USD", "AUD"): 1.5,
        ("CAD", "USD"): 0.74,
        ("USD", "CAD"): 1.35,
        ("CNY", "USD"): 0.14,
        ("USD", "CNY"): 7.1,
    }

    rate = example_rates.get((from_currency, to_currency), None)
    if rate:
        converted = conv_amount * rate
        st.sidebar.success(
            f"{conv_amount:.2f} {from_currency} = {converted:.2f} {to_currency}"
        )
    else:
        st.sidebar.error("Currency pair not supported yet.")


# Load Expense Data
df = load_expense_with_trip(gsheet, username,trip=current_trip)


params = st.query_params
user = params.get("username", ["Guest"])[0]


st.markdown("Budget Overview")

if not df.empty:
    # Convert 'Amount' column to numeric, replace invalid with 0
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)

    total_spend = df["amount"].sum()
    curr_budget = float(curr_budget)  # ensure curr_budget is float

    remained_budget = curr_budget - total_spend

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Budget", f"₹{curr_budget:,.2f}")
    col2.metric("Total Spend", f"₹{total_spend:,.2f}")
    col3.metric("Remaining Amount", f"₹{remained_budget:,.2f}")

    tabs = st.tabs(["All Expenses", "Category Breakdown", "Manage Expense"])

    with tabs[0]:
        st.subheader("All Expenses")
        st.dataframe(df)

    with tabs[1]:
        st.subheader("Category Breakdown")
        summary = df.groupby("category")["amount"].sum().reset_index()
        st.bar_chart(summary, x="category", y="amount")

        summary["% Used"] = (summary["amount"] / curr_budget * 100).round(2)
        summary["Status"] = summary["% Used"].apply(
            lambda x: " OK" if x <= 30 else "High"
        )  # shorthand lambda function
        st.dataframe(summary[["category", "amount", "% Used", "Status"]])

    with tabs[2]:
        st.subheader("Delete Expense")
        with st.expander("Delete a expense enter the row"):
            delete_row = st.number_input(
                "Row Number", min_value=2, max_value=int(df["Row"].max()), step=1
            )
            if st.button("Delete"):
                delete_expense(gsheet, int(delete_row))
                st.success(f"Deleted row is {int(delete_row)}.")

        st.subheader("Update Expense")
        with st.expander("Update a expense"):
            update_row = st.number_input(
                "Row to Update", min_value=2, max_value=int(df["Row"].max()), step=1
            )
            with st.form("update_expense"):
                u_date = st.date_input("Date", key="u_date")
                u_cat = st.selectbox(
                    "Category",
                    ["Flights", "Hotels", "Food", "Transport", "Miscellaneous"],
                    key="u_cat",
                )
                u_desc = st.text_input("Description", key="u_desc")
                u_amt = st.number_input(
                    "Amount", min_value=0.0, format="%.2f", key="u_amt"
                )
                u_loc = st.text_input("Location", key="u_loc")
                if st.form_submit_button("Update"):
                    update_expense_with_trip(
                        gsheet,
                        int(update_row),
                        str(u_date),
                        u_cat,
                        u_desc,
                        u_amt,
                        u_loc,
                        trip=current_trip
                    )
                    st.success(f"Updated expense {int(update_row)}.")

else:
    st.info("No expenses added. Use the sidebar to track your expense.")
