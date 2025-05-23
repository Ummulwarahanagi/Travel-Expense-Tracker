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

#Budget Input Sidebar
st.sidebar.header("💰Set A Budget")
curr_budget = get_budget(gsheet)
input = st.sidebar.number_input("Budget :", min_value=0.0, value=curr_budget, step=100.0, format="%.2f")

if st.sidebar.button("Update Budget"):
    set_budget(gsheet, input)
    st.sidebar.success("Budget updated successfully")

#Expense Add Form Sidebar
st.sidebar.header("➕ Add Expense")
with st.sidebar.form("add_expense"):
    date = st.date_input("Date")
    category = st.selectbox("Category", ["Flights", "Hotels", "Food", "Transport", "Miscellaneous"])
    description = st.text_input("Description")
    amount = st.number_input("Amount", min_value=0.0, format="%.2f")
    location = st.text_input("Location")
    if st.form_submit_button("Add"):
        add_ex_gsheet(gsheet, str(date), category, description, amount, location)
        st.success("Expense added!")

#Load Expense Data
df = load_ex_gsheet(gsheet)
params = st.experimental_get_query_params()
user = params.get("user", ["Guest"])[0]

st.title(f"Welcome {user} 👋")
st.markdown("📊 Budget Overview")

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
        st.markdown("""
            <a href="https://docs.google.com/spreadsheets/d/13cvRo8lk91PWI_cnr7MoGmuabcWmwZqDIEj2-6JXldw/edit?gid=0#gid=0" target="_blank">
                <button style="background-color:#4CAF50; color:white; padding:10px 30px; border:none; border-radius:8px; cursor:pointer;">
                     See Google Sheet
                </button>
            </a>
        """, unsafe_allow_html=True)
        st.dataframe(df)

    with tabs[1]:
        st.subheader("📌 Category Breakdown")
        summary = df.groupby("Category")["Amount"].sum().reset_index()
        st.bar_chart(summary, x="Category", y="Amount")

        summary["% Used"] = (summary["Amount"] / curr_budget * 100).round(2)
        summary["Status"] = summary["% Used"].apply(lambda x: " OK" if x <= 30 else "High")# shorthand lambda function
        st.dataframe(summary[["Category", "Amount", "% Used", "Status"]])

    with tabs[2]:
        st.subheader("🗑️ Delete Expense")
        with st.expander("Delete a expense enter the row"):
            delete_row = st.number_input("Row Number", min_value=2, max_value=int(df["Row"].max()), step=1)
            if st.button("Delete"):
                delete_expense(gsheet, int(delete_row))
                st.success(f"Deleted row is {int(delete_row)}.")

        st.subheader("✏️ Update Expense")
        with st.expander("Update a expense"):
            update_row = st.number_input("Row to Update", min_value=2, max_value=int(df["Row"].max()), step=1)
            with st.form("update_expense"):
                u_date = st.date_input("Date", key="u_date")
                u_cat = st.selectbox("Category", ["Flights", "Hotels", "Food", "Transport", "Miscellaneous"], key="u_cat")
                u_desc = st.text_input("Description", key="u_desc")
                u_amt = st.number_input("Amount", min_value=0.0, format="%.2f", key="u_amt")
                u_loc = st.text_input("Location", key="u_loc")
                if st.form_submit_button("Update"):
                    update_expense(gsheet, int(update_row), str(u_date), u_cat, u_desc, u_amt, u_loc)
                    st.success(f"Updated expense {int(update_row)}.")

else:
    st.info("No expenses added. Use the sidebar to track your expense.")
