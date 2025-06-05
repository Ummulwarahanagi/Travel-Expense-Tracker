import streamlit as st
import pandas as pd
import requests
import random
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

# ------------------------- Streamlit Setup ---------------------------- #
st.set_page_config(page_title="Travel Expense Tracker", layout="wide")
params = st.query_params
username = params.get("username", None)

if not username:
    st.error("⚠️ You are logged out. Please log in.")
    st.stop()

# ------------------------- Google Sheets ---------------------------- #
gsheet = connect_sheet()

# ------------------------- Personalized Avatar AI Assistant ---------------------------- #
def ai_suggestion(df, category, amount):
    if df.empty:
        return "You're just getting started! 👍 Spend wisely."
    cat_exp = df[df["category"] == category]["amount"].sum()
    avg_cat_exp = cat_exp / max(len(df[df["category"] == category]), 1)
    if amount > avg_cat_exp * 1.5:
        return f"⚠️ This expense is quite high compared to your usual `{category}` spending."
    elif amount < avg_cat_exp * 0.5:
        return f"✅ Smart choice! You're spending less than your average on `{category}`."
    else:
        return f"👌 This is in line with your past spending on `{category}`."

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/4712/4712102.png", width=80)
    st.markdown(f"## 👋 Hi **{username}**!")
    st.markdown("I'm your AI assistant. I’ll suggest tips based on your spending history! 💡")

# ------------------------- Sidebar - Trip Manager ---------------------------- #
st.sidebar.title("📂 Travel Expense Tracker")
st.sidebar.markdown("---")

with st.sidebar.expander("🗂 Trip Manager", expanded=True):
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
        if st.button("🔄 Return to Active Trip"):
            st.session_state.viewing_trip = active_trip
            st.rerun()
    else:
        st.markdown(f"### 🗺️ Active Trip: `{active_trip}`")

st.sidebar.markdown("---")

# ------------------------- Budget ---------------------------- #
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

st.sidebar.markdown("---")

# ------------------------- Location Input ---------------------------- #
location_input = st.text_input("📍 Location (start typing... hit enter)", key="live_loc_input")
selected_location = location_input
suggestions = []

if len(location_input.strip()) >= 3:
    query = f"{location_input}, {active_trip}"
    results = nominatim_search(query)
    suggestions = [res['display_name'] for res in results]
    if suggestions:
        selected_location = st.selectbox("🔽 Suggestions", suggestions, key="location_suggestions")
    else:
        st.info("No matching locations found.")

# ------------------------- Expense Input ---------------------------- #
st.text("Add Expenses")
with st.form("add_expense_form", clear_on_submit=True):
    date = st.date_input("Date")
    category = st.selectbox("Category", ["Flights", "Hotels", "Food", "Transport", "Miscellaneous", "Shopping", "Entertainment", "Fuel", "Medical", "Groceries", "Sightseeing"])
    description = st.text_input("Description")
    st.text(f"📍 Selected Location: {selected_location}")
    amount = st.number_input("Amount (₹)", min_value=0.0, format="%.2f")
    submitted = st.form_submit_button("Add Expense")
    if submitted:
        add_expense_with_trip(gsheet, username, str(date), category, description, amount, selected_location, trip=active_trip)
        st.success(f"✅ Expense added to `{active_trip}`!")

        # Load for AI Suggestion
        df_temp = load_expense_with_trip(gsheet, username, trip=active_trip)
        ai_msg = ai_suggestion(df_temp, category, amount)
        st.info(f"🤖 AI Suggestion: {ai_msg}")

# ------------------------- Remaining UI - Summary ---------------------------- #
trip_to_display = st.session_state.viewing_trip
df = load_expense_with_trip(gsheet, username, trip=trip_to_display)

st.markdown("---")
st.markdown(f"<h2 style='color:#34495E;'>📊 Expense Summary for <span style='color:#E67E22;'>{trip_to_display}</span></h2>", unsafe_allow_html=True)

if df.empty:
    st.info(f"No expenses found for `{trip_to_display}`.")
else:
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    total_spent = df["amount"].sum()
    remaining = float(curr_budget) - total_spent

    col1, col2, col3 = st.columns(3)
    col1.metric("🌟 Budget", f"₹{curr_budget:,.2f}")
    col2.metric("💸 Total Spent", f"₹{total_spent:,.2f}")
    col3.metric("🎁 Remaining", f"₹{max(remaining, 0):,.2f}")

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
                        update_expense_with_trip(gsheet, int(update_row), str(u_date), u_cat, u_desc, u_amt, u_loc, trip=active_trip)
                        st.success(f"Updated expense row {int(update_row)}.")

# ------------------------- Logout ---------------------------- #
st.sidebar.markdown("---")
if st.sidebar.button("🚪 Logout"):
    st.query_params.clear()
    st.rerun()

