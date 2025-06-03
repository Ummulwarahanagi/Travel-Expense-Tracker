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
username_list = query_params.get("username")
username = username_list[0] if username_list else None

if not username:
    st.error("Logged Out")
    st.stop()

st.title(f"Welcome {username}")

if st.sidebar.button("Logout"):
    st.query_params
    st.rerun()

# Sidebar - Budget section
st.sidebar.header("Set Your Budget")
curr_budget = get_budget(gsheet, username) or 0.0
budget_input = st.sidebar.number_input("Budget :", min_value=0.0, value=curr_budget, step=100.0, format="%.2f")
if st.sidebar.button("Update Budget"):
    set_budget(gsheet, username, budget_input)
    st.sidebar.success("Budget updated!")

# Sidebar - Add Expense Form
st.sidebar.header("Add Expense")
with st.sidebar.form("add_expense"):
    date = st.date_input("Date")
    category = st.selectbox("Category", ["Flights", "Hotels", "Food", "Transport", "Miscellaneous"])
    description = st.text_input("Description")
    amount = st.number_input("Amount", min_value=0.0, format="%.2f")
    location = st.text_input("Location")
    trip = st.text_input("Trip Name")  # ✅ NEW FIELD

    if st.form_submit_button("Add"):
        add_ex_gsheet(gsheet, username, str(date), category, description, amount, location, trip)
        st.success("Expense added!")

# Load Data
df = load_ex_gsheet(gsheet, username)

# Sidebar - Filter by Trip & Date
if not df.empty:
    st.sidebar.markdown("### 🔍 Filter Expenses")
    
    trip_names = df["Trip"].dropna().unique().tolist()
    selected_trip = st.sidebar.selectbox("Select Trip", ["All"] + trip_names)
    
    df["Date"] = pd.to_datetime(df["Date"])
    min_date, max_date = df["Date"].min(), df["Date"].max()
    date_range = st.sidebar.date_input("Date Range", [min_date, max_date])

    if selected_trip != "All":
        df = df[df["Trip"] == selected_trip]

    df = df[(df["Date"] >= pd.to_datetime(date_range[0])) & (df["Date"] <= pd.to_datetime(date_range[1]))]

# Budget Overview Section
st.markdown("## Budget Overview")

if not df.empty:
    total_spend = df["Amount"].sum()
    remained_budget = curr_budget - total_spend

    if selected_trip != "All":
        st.markdown(f"### 📌 Viewing Trip: `{selected_trip}`")

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Budget", f"₹{curr_budget:,.2f}")
    col2.metric("Total Spend", f"₹{total_spend:,.2f}", delta_color="inverse" if total_spend > curr_budget else "normal")
    col3.metric("Remaining Amount", f"₹{remained_budget:,.2f}", delta_color="inverse" if remained_budget < curr_budget * 0.2 else "normal")

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
            if "Row" in df.columns:
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
            if "Row" in df.columns:
                update_row = st.number_input("Row to Update", min_value=2, max_value=int(df["Row"].max()), step=1)
                with st.form("update_expense"):
                    u_date = st.date_input("Date", key="u_date")
                    u_cat = st.selectbox("Category", ["Flights", "Hotels", "Food", "Transport", "Miscellaneous"], key="u_cat")
                    u_desc = st.text_input("Description", key="u_desc")
                    u_amt = st.number_input("Amount", min_value=0.0, format="%.2f", key="u_amt")
                    u_loc = st.text_input("Location", key="u_loc")
                    u_trip = st.text_input("Trip Name", key="u_trip")  # ✅ Add to update logic
                    if st.form_submit_button("Update"):
                        update_expense(gsheet, int(update_row), username, str(u_date), u_cat, u_desc, u_amt, u_loc, u_trip)
                        st.success(f"Updated expense in row {int(update_row)}")
                        st.rerun()
            else:
                st.warning("No data available to update.")

    # Smart Spend Insights Section
    st.markdown("---")
    st.subheader("💡 Smart Spend Insights")

    def generate_insights(df, budget):
        insights = []
        if df.empty:
            return [("No insights available. Add some expenses first.", "info")]

        total_spent = df["Amount"].sum()
        daily_avg = df.groupby("Date")["Amount"].sum().mean()

        if total_spent > budget:
            insights.append(("🚨 You’ve exceeded your total budget. Consider reviewing high-expense categories.", "danger"))
        elif budget - total_spent < budget * 0.2:
            insights.append(("⚠️ You're close to exhausting your budget. Plan remaining days carefully.", "warning"))

        food_exp = df[df["Category"] == "Food"]["Amount"].sum()
        if food_exp > total_spent * 0.3:
            insights.append(("🍽️ High food expenses — try exploring cheaper local dining options.", "warning"))

        hotel_exp = df[df["Category"] == "Hotels"]["Amount"].sum()
        if hotel_exp > total_spent * 0.4:
            insights.append(("🏨 Hotels are taking a big chunk — check for cheaper stays next time.", "warning"))

        transport_exp = df[df["Category"] == "Transport"]["Amount"].sum()
        if transport_exp < total_spent * 0.1:
            insights.append(("🚗 Nice! You’re saving on transport. Keep it up!", "success"))

        if daily_avg > budget / 10:
            insights.append((f"📈 Your average daily spend is ₹{daily_avg:.2f} — adjust to stay on track.", "warning"))

        return insights

    def styled_message(message, style_type):
        styles = {
            "danger": "background-color:#ffdddd; color:#a70000; border-left:6px solid #a70000; padding:10px; margin-bottom:10px; border-radius:5px;",
            "warning": "background-color:#fff4e5; color:#8a6d3b; border-left:6px solid #ffa500; padding:10px; margin-bottom:10px; border-radius:5px;",
            "success": "background-color:#ddffdd; color:#207520; border-left:6px solid #207520; padding:10px; margin-bottom:10px; border-radius:5px;",
            "info": "background-color:#e7f3fe; color:#31708f; border-left:6px solid #31708f; padding:10px; margin-bottom:10px; border-radius:5px;",
        }
        return f'<div style="{styles.get(style_type, styles["info"])}">{message}</div>'

    insights = generate_insights(df, curr_budget)
    for message, style_type in insights:
        st.markdown(styled_message(message, style_type), unsafe_allow_html=True)

else:
    st.info("No expenses added yet. Use the sidebar to start tracking your expenses.")
    st.markdown("---")
    st.subheader("💡 Smart Spend Insights")
    st.info("No insights available yet. Add some expenses to see tips here.")
