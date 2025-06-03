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

# --- Advanced CSS for vivid colors and animations ---
st.markdown("""
<style>
    /* Gradient background for whole page */
    .main {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        min-height: 100vh;
        padding: 20px 30px;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }

    /* Budget Metrics with gradient text and shadow */
    .budget-metric {
        background: white;
        border-radius: 14px;
        padding: 20px 15px;
        box-shadow: 0 8px 20px rgba(0,0,0,0.12);
        text-align: center;
        transition: transform 0.3s ease;
        cursor: default;
        user-select: none;
    }
    .budget-metric:hover {
        transform: translateY(-8px);
        box-shadow: 0 12px 30px rgba(0,0,0,0.2);
    }
    .budget-metric h3 {
        font-weight: 700;
        color: #222222;
        margin-bottom: 8px;
    }
    .budget-value {
        font-size: 2.6rem;
        font-weight: 900;
        background: linear-gradient(90deg, #00c6ff, #0072ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        user-select: text;
    }

    /* Insight Boxes with stronger colored borders & glowing effect */
    .insight-box {
        background: white;
        border-left: 8px solid;
        border-radius: 14px;
        padding: 18px 24px;
        margin-bottom: 14px;
        font-weight: 700;
        font-size: 1.1rem;
        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        display: flex;
        align-items: center;
        gap: 12px;
        user-select: none;
        transition: box-shadow 0.4s ease;
    }
    .insight-box:hover {
        box-shadow: 0 8px 25px rgba(0,0,0,0.18);
    }
    .insight-icon {
        font-size: 1.8rem;
        flex-shrink: 0;
    }

    /* Colored borders & glowing shadows for categories */
    .insight-high {
        border-color: #e63946;
        box-shadow: 0 0 12px #e63946aa;
        color: #e63946;
    }
    .insight-warning {
        border-color: #f4a261;
        box-shadow: 0 0 12px #f4a261aa;
        color: #f4a261;
    }
    .insight-info {
        border-color: #2a9d8f;
        box-shadow: 0 0 12px #2a9d8faa;
        color: #2a9d8f;
    }
    .insight-success {
        border-color: #43a047;
        box-shadow: 0 0 12px #43a047aa;
        color: #43a047;
    }
    .insight-neutral {
        border-color: #264653;
        box-shadow: 0 0 12px #264653aa;
        color: #264653;
    }

    /* Category badges for breakdown table */
    .category-badge {
        padding: 6px 14px;
        border-radius: 16px;
        color: white;
        font-weight: 700;
        font-size: 0.9rem;
        text-align: center;
        display: inline-block;
        user-select: none;
    }
    .badge-Flights { background-color: #0077b6; }
    .badge-Hotels { background-color: #0096c7; }
    .badge-Food { background-color: #f77f00; }
    .badge-Transport { background-color: #2a9d8f; }
    .badge-Miscellaneous { background-color: #6a4c93; }

</style>
""", unsafe_allow_html=True)

gsheet = connect_sheet()
query_params = st.query_params
username = query_params.get("username", [None])[0]

if not username:
    st.error("Logged Out")
    st.stop()

st.markdown('<div class="main">', unsafe_allow_html=True)
st.title(f"👋 Welcome {username}")

if st.sidebar.button("Logout"):
    st.query_params
    st.experimental_rerun()

# Budget Sidebar
st.sidebar.header("💰 Set Your Budget")
curr_budget = get_budget(gsheet, username) or 0.0
budget_input = st.sidebar.number_input("Budget :", min_value=0.0, value=curr_budget, step=100.0, format="%.2f")
if st.sidebar.button("Update Budget"):
    set_budget(gsheet, username, budget_input)
    st.sidebar.success("Budget updated!")

# Add Expense Sidebar
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

df = load_ex_gsheet(gsheet, username)

# Budget Overview
st.markdown("📊 **Budget Overview**")
if not df.empty:
    total_spend = df["Amount"].sum()
    remained_budget = curr_budget - total_spend
    col1, col2, col3 = st.columns(3)
    col1.markdown(f'<div class="budget-metric"><h3>Total Budget</h3><div class="budget-value">₹{curr_budget:,.2f}</div></div>', unsafe_allow_html=True)
    col2.markdown(f'<div class="budget-metric"><h3>Total Spend</h3><div class="budget-value" style="background: linear-gradient(90deg, #ff416c, #ff4b2b);">₹{total_spend:,.2f}</div></div>', unsafe_allow_html=True)
    col3.markdown(f'<div class="budget-metric"><h3>Remaining Amount</h3><div class="budget-value" style="background: linear-gradient(90deg, #43cea2, #185a9d);">₹{remained_budget:,.2f}</div></div>', unsafe_allow_html=True)

    # Category Breakdown with badges
    st.subheader("📌 Category Breakdown")
    summary = df.groupby("Category")["Amount"].sum().reset_index()
    summary["Badge"] = summary["Category"].apply(lambda x: f'<span class="category-badge badge-{x}">{x}</span>')
    st.markdown(summary.to_html(escape=False, columns=["Badge", "Amount"], index=False), unsafe_allow_html=True)
    st.bar_chart(summary.set_index("Category")["Amount"])

    # Smart Spend Insights
    st.markdown("---")
    st.subheader("💡 Smart Spend Insights")

    def generate_insights(df, budget):
        insights = []
        if df.empty:
            return [("ℹ️", "No expenses yet. Add some to get insights.", "insight-neutral")]

        total_spent = df["Amount"].sum()
        daily_avg = df.groupby("Date")["Amount"].sum().mean()

        if total_spent > budget:
            insights.append(("🚨", "You’ve exceeded your total budget. Review your high-expense categories!", "insight-high"))
        elif budget - total_spent < budget * 0.2:
            insights.append(("⚠️", "You're close to exhausting your budget. Plan carefully!", "insight-warning"))

        food_exp = df[df["Category"] == "Food"]["Amount"].sum()
        if food_exp > total_spent * 0.3:
            insights.append(("🍽️", "High food expenses — try exploring cheaper local dining.", "insight-warning"))

        hotel_exp = df[df["Category"] == "Hotels"]["Amount"].sum()
        if hotel_exp > total_spent * 0.4:
            insights.append(("🏨", "Hotels are a big chunk — check for budget stays.", "insight-high"))

        transport_exp = df[df["Category"] == "Transport"]["Amount"].sum()
        if transport_exp < total_spent * 0.1:
            insights.append(("🚗", "Great! Saving on transport expenses.", "insight-success"))

        if daily_avg > budget / 10:
            insights.append(("📈", f"Average daily spend ₹{daily_avg:.2f} — adjust to stay on track.", "insight-info"))

        return insights

    insights = generate_insights(df, curr_budget)
    for icon, tip, style in insights:
        st.markdown(f'<div class="insight-box {style}"><span class="insight-icon">{icon}</span>{tip}</div>', unsafe_allow_html=True)
else:
    st.info("No expenses added yet. Use the sidebar to start tracking your expenses.")
    st.markdown("---")
    st.subheader("💡 Smart Spend Insights")
    st.info("No insights available yet. Add some expenses to see tips here.")

st.markdown("</div>", unsafe_allow_html=True)
