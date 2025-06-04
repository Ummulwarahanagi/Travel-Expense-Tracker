import streamlit as st
import pandas as pd
import requests
from google_sheets_utils import (
    connect_sheet,
    add_expense_with_trip,
    load_expense_with_trip,
    get_user_trips,
    get_budget,
    set_budget,
    update_expense_with_trip,
    delete_expense
)

def nominatim_search(query, limit=5):
    import time
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": query,
        "format": "json",
        "addressdetails": 1,
        "limit": limit,
        "accept-language": "en",
    }
    headers = {
        "User-Agent": "travel-expense-tracker-app (ummulwarahanagi@gmail.com)"
    }
    try:
        time.sleep(1)
        resp = requests.get(url, params=params, headers=headers)
        if resp.status_code == 200:
            return resp.json()
        else:
            st.warning(f"Nominatim API error: {resp.status_code}")
    except Exception as e:
        st.error(f"API error: {e}")
    return []

st.set_page_config(page_title="Travel Expense Tracker", layout="wide")

params = st.query_params
username = params.get("username", None)
if not username:
    st.error("\u26a0\ufe0f You are logged out. Please log in.")
    st.stop()

gsheet = connect_sheet()

st.markdown(f"<h1 style='text-align:center; color:#2E86C1;'>👋 Welcome, <span style='color:#F39C12;'>{username}</span>!</h1>", unsafe_allow_html=True)

st.sidebar.title("🗂 Travel Expense Tracker")
st.sidebar.markdown("---")

with st.sidebar.expander("💼 Trip Manager", expanded=True):
    user_trips = get_user_trips(gsheet, username)
    default_trips = ["General"]
    all_trips = sorted(set(user_trips + default_trips))

    trip_input = st.text_input("➕ Start New Trip:", key="trip_input")
    existing_trip = st.selectbox("📂 View Previous Trips:", options=all_trips, key="trip_select")

    if "active_trip" not in st.session_state:
        st.session_state.active_trip = trip_input.strip() or sorted(user_trips)[-1] if user_trips else "General"

    if trip_input.strip() and trip_input.strip() != st.session_state.get("active_trip", ""):
        st.session_state.active_trip = trip_input.strip()
        st.rerun()

    active_trip = st.session_state.active_trip

    if "viewing_trip" not in st.session_state:
        st.session_state.viewing_trip = active_trip

    if existing_trip != st.session_state.active_trip:
        if st.button("📖 View Selected Trip History"):
            st.session_state.viewing_trip = existing_trip

    if st.session_state.viewing_trip != active_trip:
        st.markdown(f"### 📂 Viewing Trip: `{st.session_state.viewing_trip}`")
        if st.button("🔁 Return to Active Trip"):
            st.session_state.viewing_trip = active_trip
            st.rerun()
    else:
        st.markdown(f"### 🧳️ Active Trip: `{active_trip}`")

st.sidebar.markdown("---")

with st.sidebar.expander("💰 Budget & Expenses", expanded=True):
    curr_budget = get_budget(gsheet, username)
    try:
        curr_budget = float(curr_budget)
    except:
        curr_budget = 0.0

    st.subheader("Set Budget")
    budget_input = st.number_input("Budget (₹):", min_value=0.0, value=curr_budget, step=100.0, format="%.2f")
    if st.button("Update Budget"):
        set_budget(gsheet, username, budget_input)
        st.success("✅ Budget updated")

    st.markdown("---")
    # Location input OUTSIDE the form for live suggestion
location_input = st.text_input("📍 Location (start typing...)", key="live_loc_input")
selected_location = location_input
suggestions = []

if len(location_input.strip()) >= 3:
    query = f"{location_input}, {active_trip}"
    st.write("Search for:", query)  # Debug
    results = nominatim_search(query)
    suggestions = [res['display_name'] for res in results]
    if suggestions:
        selected_location = st.selectbox("🔽 Suggestions", suggestions, key="location_suggestions")
    else:
        st.info("No matching locations found.")

# ✅ FORM starts here (use selected_location)
with st.form("add_expense_form", clear_on_submit=True):
    date = st.date_input("Date")
    category = st.selectbox("Category", ["Flights", "Hotels", "Food", "Transport", "Miscellaneous"])
    description = st.text_input("Description")
    
    # Just show the selected location inside the form
    st.text(f"📍 Selected Location: {selected_location}")
    
    amount = st.number_input("Amount (₹)", min_value=0.0, format="%.2f")
    submitted = st.form_submit_button("Add Expense")

    if submitted:
        add_expense_with_trip(
            gsheet,
            username,
            str(date),
            category,
            description,
            amount,
            selected_location,
            trip=active_trip
        )
        st.success(f"✅ Expense added to `{active_trip}`!")


st.sidebar.markdown("---")

with st.sidebar.expander("💱 Currency Converter", expanded=False):
    currencies = ["USD", "EUR", "INR", "GBP", "JPY", "AUD", "CAD", "CNY"]
    from_currency = st.selectbox("From", currencies, index=2)
    to_currency = st.selectbox("To", currencies, index=0)
    conv_amount = st.number_input("Amount", min_value=0.0, value=1.0, step=0.1, format="%.2f")

    if st.button("Convert"):
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
        rate = example_rates.get((from_currency, to_currency))
        if rate:
            converted = conv_amount * rate
            st.success(f"{conv_amount:.2f} {from_currency} = {converted:.2f} {to_currency}")
        else:
            st.error("Currency pair not supported yet.")

st.sidebar.markdown("---")

if st.sidebar.button("🚪 Logout"):
    st.query_params.clear()
    st.rerun()

trip_to_display = st.session_state.viewing_trip
df = load_expense_with_trip(gsheet, username, trip=trip_to_display)

st.markdown("---")
st.markdown(f"<h2 style='color:#34495E;'>📊 Expense Summary for <span style='color:#E67E22;'>{trip_to_display}</span></h2>", unsafe_allow_html=True)

if df.empty:
    st.info(f"No expenses found for `{trip_to_display}`. Use the sidebar to add expenses.")
else:
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    total_spent = df["amount"].sum()
    remaining = float(curr_budget) - total_spent

    col1, col2, col3 = st.columns(3)
    col1.metric("🎯 Budget", f"₹{curr_budget:,.2f}")
    col2.metric("💸 Total Spent", f"₹{total_spent:,.2f}")
    col3.metric("🛁 Remaining", f"₹{max(remaining, 0):,.2f}")

    tabs = st.tabs(["All Expenses", "Category Breakdown", "Manage Expenses"])

    with tabs[0]:
        st.subheader("All Expenses")
        st.dataframe(df, height=400)

    with tabs[1]:
        st.subheader("Category Breakdown")
        summary = df.groupby("category")["amount"].sum().reset_index()
        st.bar_chart(summary.rename(columns={"amount": "Amount"}).set_index("category"))
        summary["% Used"] = (summary["amount"] / curr_budget * 100).round(2)
        summary["Status"] = summary["% Used"].apply(lambda x: "OK ✅" if x <= 30 else "High ⚠️")
        st.dataframe(summary[["category", "amount", "% Used", "Status"]])

    with tabs[2]:
        st.subheader("Delete Expense")
        with st.expander("Delete an Expense"):
            if not df.empty:
                delete_row = st.number_input("Row Number", min_value=2, max_value=int(df["Row"].max()), step=1)
                if st.button("Delete"):
                    delete_expense(gsheet, int(delete_row))
                    st.success(f"Deleted row: {int(delete_row)}")
            else:
                st.info("No data to delete.")

        st.subheader("Update Expense")
        with st.expander("Update an Expense"):
            if not df.empty:
                update_row = st.number_input("Row to Update", min_value=2, max_value=int(df["Row"].max()), step=1)
                with st.form("update_expense_form"):
                    u_date = st.date_input("Date", key="u_date")
                    u_cat = st.selectbox("Category", ["Flights", "Hotels", "Food", "Transport", "Miscellaneous"], key="u_cat")
                    u_desc = st.text_input("Description", key="u_desc")
                    u_amt = st.number_input("Amount", min_value=0.0, format="%.2f", key="u_amt")
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
                            trip=active_trip
                        )
                        st.success(f"Updated expense row {int(update_row)}.")
            else:
                st.info("No data to update.")
