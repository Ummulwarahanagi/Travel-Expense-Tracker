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

# --- Location API ---
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
        "User-Agent": "travel-expense-tracker-app (your-email@example.com)"
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

# --- AI Suggestion Logic ---
def ai_suggestion(df, category, amount, total_spent, budget):
    def color_wrap(text):
        return f"<span style='color:white;'>{text}</span>"

    if budget <= 0:
        starters = [
            "You're just getting started! 👍 Spend wisely.",
            "Let's kick off this journey with smart spending! 🚀",
            "Beginner's luck! Keep tracking those expenses. 💼",
            "Every rupee counts—let's make them work! 💪"
        ]
        return color_wrap(random.choice(starters)), False

    # Budget maxed out
    if total_spent >= budget:
        limits = [
            f"🚫 Budget maxed out at ₹{budget:,.2f}! No more spending allowed.",
            f"⛔ You've hit your budget ceiling of ₹{budget:,.2f}. Time to pause spending.",
            f"⚠️ Budget exhausted! ₹{budget:,.2f} is your limit. Review your expenses.",
            f"🛑 Hold on! You reached the budget limit of ₹{budget:,.2f}."
        ]
        return color_wrap(random.choice(limits)), True  # True = critical alert

    # Near budget warning (90% spent)
    if total_spent >= 0.9 * budget:
        warnings = [
            f"⚠️ Heads up! You're nearly at your budget with ₹{budget - total_spent:,.2f} left.",
            f"🔥 Almost there! Only ₹{budget - total_spent:,.2f} remaining in your budget.",
            f"⏳ Watch out! Your budget's almost full, ₹{budget - total_spent:,.2f} left to spend.",
            f"⚡ You're close to your budget limit—just ₹{budget - total_spent:,.2f} remains!"
        ]
        return color_wrap(random.choice(warnings)), True

    # Normal spending suggestions
    cat_exp = df[df["category"] == category]["amount"].sum()
    avg_cat_exp = cat_exp / max(len(df[df["category"] == category]), 1)

    if amount > avg_cat_exp * 1.5:
        suggestion = random.choice([
            f"🚀 Wow! That's a big spend on `{category}` compared to usual. Keep an eye!",
            f"⚠️ High expense alert for `{category}`! Make sure it's worth it.",
            f"🔥 `{category}` spending spike detected. Budget wisely!",
            f"💡 You splurged on `{category}` today. Monitor those costs!"
        ])
    elif amount < avg_cat_exp * 0.5:
        suggestion = random.choice([
            f"🎉 Nice! You're spending less than usual on `{category}`—smart move.",
            f"✅ Keeping `{category}` costs low, great job!",
            f"👍 Low spending on `{category}` is always welcome.",
            f"🌱 Being frugal on `{category}` pays off!"
        ])
    else:
        suggestion = random.choice([
            f"👌 This `{category}` expense aligns well with your past spending.",
            f"💼 `{category}` costs seem steady. Keep it up!",
            f"📝 `{category}` spending is consistent with your habits.",
            f"📊 `{category}` expense fits your budget pattern."
        ])

    return color_wrap(suggestion), False

    if amount > avg_cat_exp * 1.5:
        return random.choice(high_spend_msgs), False
    elif amount < avg_cat_exp * 0.5:
        return random.choice(low_spend_msgs), False
    else:
        return random.choice(normal_spend_msgs), False

# --- Sound beep helper ---
def play_beep():
    st.markdown(
        """
        <audio autoplay>
        <source src="https://actions.google.com/sounds/v1/alarms/beep_short.ogg" type="audio/ogg">
        </audio>
        """,
        unsafe_allow_html=True,
    )

# --- Streamlit Setup ---
st.set_page_config(page_title="Travel Expense Tracker", layout="wide")
params = st.query_params
username = params.get("username",None)

if not username:
    st.error("⚠️ You are logged out. Please log in.")
    st.stop()

# --- Connect Google Sheet ---
gsheet = connect_sheet()

# --- Session State initialization ---
if "active_trip" not in st.session_state:
    st.session_state.active_trip = None
if "viewing_trip" not in st.session_state:
    st.session_state.viewing_trip = None
if "last_ai_msg" not in st.session_state:
    st.session_state.last_ai_msg = ""

# --- Sidebar: Trip Manager and Budget ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/4712/4712102.png", width=80)
    st.text(f"Hello {username}!")
    # Pop-up style greeting in chat area, so skip sidebar greeting here.

    st.title("📂 Travel Expense Tracker")
    st.markdown("---")

    # Trip manager
    user_trips = get_user_trips(gsheet, username)
    default_trips = ["General"]
    all_trips = sorted(set(user_trips + default_trips))

    trip_input = st.text_input("➕ Start New Trip:", key="trip_input")
    existing_trip = st.selectbox("📂 View Previous Trips:", options=all_trips, key="trip_select")

    # Initialize active trip if None
    if st.session_state.active_trip is None:
        if trip_input.strip():
            st.session_state.active_trip = trip_input.strip()
        elif user_trips:
            st.session_state.active_trip = sorted(user_trips)[-1]
        else:
            st.session_state.active_trip = "General"

    # If user inputs new trip, update active trip and rerun
    if trip_input.strip() and trip_input.strip() != st.session_state.active_trip:
        st.session_state.active_trip = trip_input.strip()
        st.rerun()

    active_trip = st.session_state.active_trip

    # Viewing trip selector
    if st.session_state.viewing_trip is None:
        st.session_state.viewing_trip = active_trip

    if existing_trip != active_trip:
        if st.button("📖 View Selected Trip History"):
            st.session_state.viewing_trip = existing_trip

    if st.session_state.viewing_trip != active_trip:
        st.markdown(f"### 📂 Viewing Trip: `{st.session_state.viewing_trip}`")
        if st.button("🔄 Return to Active Trip"):
            st.session_state.viewing_trip = active_trip
            st.rerun()
    else:
        st.markdown(f"### 🗺️ Active Trip: `{active_trip}`")

    st.markdown("---")

    # Budget management
    curr_budget = get_budget(gsheet, username)
    try:
        curr_budget = float(curr_budget)
    except:
        curr_budget = 0.0

    st.subheader("💰 Add Budget")
    budget_input = st.number_input("Set Budget (₹):", min_value=0.0, value=curr_budget, step=100.0, format="%.2f")
    if st.button("Update Budget"):
        set_budget(gsheet, username, budget_input)
        st.success("✅ Budget updated")

    st.markdown("---")
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

       rate = example_rates.get((from_currency, to_currency), None)  # <-- Move this inside
       if rate:
          converted = conv_amount * rate
          st.sidebar.success(f"{conv_amount:.2f} {from_currency} = {converted:.2f} {to_currency}")
       else:
          st.sidebar.error("Currency pair not supported yet.")

      
       st.sidebar.markdown("---")
if st.sidebar.button("🚪 Logout"):
   st.query_params.clear()
   st.rerun()

# --- Pop-up AI Greeting & Message in Chat ---

def ai_chat_message(msg, is_critical=False, avatar="🤖"):
    # Color styling for critical messages
    color = "white" if is_critical else "#34495E"
    with st.chat_message(avatar):
        st.markdown(f"<span style='color:{color}; font-weight:bold;'>{msg}</span>", unsafe_allow_html=True)

# Show greeting once per session
if not st.session_state.get("greeted", False):
    ai_chat_message(" <span style='color:white;'>👋 I'm your AI travel expense assistant. I'll help you stay on budget and give spending tips.")
    st.session_state.greeted = True

# --- Location input ---
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

# --- Load expense DataFrame for active trip ---
df = load_expense_with_trip(gsheet, username, trip=active_trip)
df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
total_spent = df["amount"].sum()
remaining_budget = curr_budget - total_spent

# --- Expense input form ---
# Step 1: Let user choose sharing option BEFORE the form
share_option = st.selectbox("Do you want to split this expense?", ["No", "Yes"])

# Step 2: Capture sharing input accordingly
shared_raw = ""
if share_option == "Yes":
    shared_raw = st.text_input("Enter usernames/emails (comma-separated)", key="share_input")

# Step 3: Actual form for expense entry
with st.form("add_expense_form", clear_on_submit=True):
    date = st.date_input("Date")
    category = st.selectbox("Category", [
        "Flights", "Hotels", "Food", "Transport", "Miscellaneous",
        "Shopping", "Entertainment", "Fuel", "Medical", "Groceries", "Sightseeing"
    ])
    description = st.text_input("Description", key="desc_input")
    st.text(f"📍 Selected Location: {selected_location}")
    amount = st.number_input("Amount (₹)", min_value=0.0, format="%.2f")
    submitted = st.form_submit_button("Add Expense")

# Step 4: Process the form data
if submitted:
    shared_with = [s.strip() for s in shared_raw.split(",") if s.strip()] if share_option == "Yes" else None

    errors = []
    if curr_budget < 1000:
        errors.append("⚠️ Please set a valid budget of at least ₹1000 before adding expenses.")
    if not description.strip():
        errors.append("⚠️ Description cannot be empty.")
    if amount <= 0:
        errors.append("⚠️ Enter a valid amount greater than ₹0.")
    if not selected_location or selected_location.strip() == "":
        errors.append("⚠️ Please select a valid location.")

    if errors:
        for err in errors:
            st.warning(err)
        play_beep()
    else:
        if total_spent + amount > curr_budget:
            ai_chat_message(f"🚫 Cannot add expense! This would exceed your budget of ₹{curr_budget:,.2f}.", is_critical=True)
            play_beep()
        else:
            add_expense_with_trip(
                gsheet, username, str(date), category, description,
                amount, selected_location, trip=active_trip, shared_with=shared_with
            )
            st.success(f"✅ Expense added to `{active_trip}`!")
            suggestion_msg, is_critical = ai_suggestion(df, category, amount, total_spent + amount, curr_budget)
            ai_chat_message(suggestion_msg, is_critical=is_critical)

                # Reload and reprocess
            df = load_expense_with_trip(gsheet, username, trip=active_trip)
            df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
            df["split_amount"] = pd.to_numeric(df.get("Split Amount", df["amount"]), errors="coerce").fillna(0)
            df["shared_with"] = df.get("shared_with").fillna("")
            df["is_shared"] = df["shared_with"].apply(lambda x: "✅" if str(x).strip() else "❌")

            view_mode = st.radio("View Mode", ["All Expenses", "My Share Only"])
            if view_mode == "My Share Only":
                df = df[df["username"] == username]
                df["amount"] = df["split_amount"]

                total_spent = df["split_amount"].sum()
                remaining_budget = curr_budget - total_spent

                # AI suggestion
                ai_msg, critical = ai_suggestion(df, category, amount, total_spent, curr_budget)
                ai_chat_message(ai_msg, is_critical=critical)
                if critical:
                   play_beep()


# --- Expense summary and management ---
st.markdown("---")
trip_to_display = st.session_state.viewing_trip or active_trip
st.markdown(f"<h2 style='color:#34495E;'>📊 Expense Summary for <span style='color:#E67E22;'>{trip_to_display}</span></h2>", unsafe_allow_html=True)

df_view = load_expense_with_trip(gsheet, username, trip=trip_to_display)
if df_view.empty:
    st.info(f"No expenses found for `{trip_to_display}`.")
else:
    df_view["amount"] = pd.to_numeric(df_view["amount"], errors="coerce").fillna(0)
    total_spent_view = df_view["amount"].sum()
    remaining_view = float(curr_budget) - total_spent_view

    col1, col2, col3 = st.columns(3)
    col1.metric("🌟 Budget", f"₹{curr_budget:,.2f}")
    col2.metric("💸 Total Spent", f"₹{total_spent_view:,.2f}")
    col3.metric("🎁 Remaining", f"₹{max(remaining_view, 0):,.2f}")

    tabs = st.tabs(["All Expenses", "Category Breakdown", "Manage Expenses"])

    with tabs[0]:
        st.subheader("All Expenses")
        st.dataframe(df_view, height=400)

    with tabs[1]:
         st.subheader("📊 Category Breakdown (Overall)")
    
         # Overall category-wise breakdown
         summary = df_view.groupby("category")["amount"].sum().reset_index()
         st.bar_chart(summary.rename(columns={"amount": "Amount"}).set_index("category"))

         summary["% Used"] = (summary["amount"] / curr_budget * 100).round(2)
         summary["Status"] = summary["% Used"].apply(lambda x: "OK ✅" if x <= 30 else "High ⚠️")
         st.dataframe(summary[["category", "amount", "% Used", "Status"]])

         st.markdown("---")
         st.subheader("📅 Daily Category Breakdown")

         # Convert date column to datetime
         df_view["date"] = pd.to_datetime(df_view["date"], errors="coerce")

         # Group by date and category
         daily_breakdown = df_view.groupby(["date", "category"])["amount"].sum().reset_index()

         # Pivot to get categories as columns for grouped bar chart
         pivot_table = daily_breakdown.pivot(index="date", columns="category", values="amount").fillna(0)

         st.bar_chart(pivot_table)
         st.subheader("📈 Total Daily Spend Trend")
         daily_total = df_view.groupby("date")["amount"].sum()
         st.line_chart(daily_total)


    with tabs[2]:
        st.subheader("Delete Expense")
        with st.expander("Delete an Expense"):
            if not df_view.empty:
                delete_row = st.number_input("Row Number", min_value=2, max_value=int(df_view["Row"].max()), step=1)
                if st.button("Delete"):
                    delete_expense(gsheet, int(delete_row))
                    st.success(f"Deleted row: {int(delete_row)}")

        st.subheader("Update Expense")
        with st.expander("Update an Expense"):
            if not df_view.empty:
                update_row = st.number_input("Row to Update", min_value=2, max_value=int(df_view["Row"].max()), step=1)
                with st.form("update_expense_form"):
                    u_date = st.date_input("Date", key="u_date")
                    u_cat = st.selectbox("Category", ["Flights", "Hotels", "Food", "Transport", "Miscellaneous"], key="u_cat")
                    u_desc = st.text_input("Description", key="u_desc")
                    u_amt = st.number_input("Amount", min_value=0.0, format="%.2f", key="u_amt")
                    u_loc = st.text_input("Location", key="u_loc")
                    if st.form_submit_button("Update"):
                        update_expense_with_trip(gsheet, int(update_row), str(u_date), u_cat, u_desc, u_amt, u_loc, trip=active_trip)
                        st.success(f"Updated expense row {int(update_row)}.")

