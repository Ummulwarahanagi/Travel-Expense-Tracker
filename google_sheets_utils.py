import gspread
import pandas as pd
import logging
import streamlit as st
import requests
import json
import os
import datetime
from oauth2client.service_account import ServiceAccountCredentials

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
SHEET_NAME = "Sheet1"
BUDGET_SHEET = "Budget"
BASE_CURRENCY = "INR"  # Set your base currency here

CACHE_FILE = "currency_rates.json"


def get_secrets():
    sheet_key = st.secrets["sheet_key"]
    service_account_info = st.secrets["gcp_service_account"]
    return sheet_key, service_account_info


def connect_sheet():
    sheet_key, service_account_info = get_secrets()
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
    client = gspread.authorize(creds)
    logger.info("Successfully connected to the Google Sheet.")
    return client.open_by_key(sheet_key)


def load_ex_gsheet(sheet: gspread.Spreadsheet, username: str) -> pd.DataFrame:
    ws = sheet.worksheet(SHEET_NAME)
    data = ws.get_all_records()
    df = pd.DataFrame(data)

    if df.empty:
        logger.warning("Google Sheet data is empty.")
        return df

    if len(df.columns) > 0 and all(isinstance(col, str) for col in df.columns):
        df.columns = df.columns.str.strip()
        logger.info("Columns in DataFrame: %s", df.columns.tolist())

    column_name = "username"
    if column_name not in df.columns:
        raise KeyError(f"Column '{column_name}' not found in Google Sheet")

    df = df[df[column_name] == username].reset_index(drop=True)
    df["Row"] = list(range(2, 2 + len(df)))
    return df


def get_user_budget(sheet: gspread.Spreadsheet, username: str) -> float:
    ws = sheet.worksheet(BUDGET_SHEET)
    records = ws.get_all_records()
    df = pd.DataFrame(records)

    col_username = "Username"
    col_budget = "Budget"

    if df.empty or col_username not in df.columns or col_budget not in df.columns:
        return 0.0

    user_budget_row = df[df[col_username] == username]
    if not user_budget_row.empty:
        return float(user_budget_row[col_budget].values[0])
    return 0.0


def add_ex_gsheet(sheet: gspread.Spreadsheet, username: str, date: str, category: str, description: str,
                  amount: float, location: str, trip: str, currency: str, inr_amount: float) -> None:
    ws = sheet.worksheet(SHEET_NAME)
    ws.append_row([username, date, category, description, float(amount), location, trip, currency, float(inr_amount)])
    logger.info(
        "Expense added for '%s': %s | %s | %.2f %s | %s | %s | %.2f INR",
        username, date, category, amount, currency, location, trip, inr_amount
    )


def delete_expense(sheet: gspread.Spreadsheet, row_number: int) -> None:
    try:
        ws = sheet.worksheet(SHEET_NAME)
        ws.delete_rows(row_number)
        logger.info("Deleted row %d.", row_number)
    except gspread.exceptions.APIError as e:
        logger.error("Failed to delete row %d: %s", row_number, e)


def update_expense(sheet: gspread.Spreadsheet, row_number: int, username: str, date: str, category: str,
                   description: str, amount: float, location: str, trip: str, currency: str, inr_amount: float) -> None:
    try:
        ws = sheet.worksheet(SHEET_NAME)
        ws.update(f"A{row_number}:I{row_number}",
                  [[username, date, category, description, float(amount), location, trip, currency, float(inr_amount)]])
        logger.info("Updated row %d for user '%s'.", row_number, username)
    except gspread.exceptions.APIError as e:
        logger.error("Failed to update row %d: %s", row_number, e)


def get_budget_worksheet(sheet: gspread.Spreadsheet) -> gspread.Worksheet:
    try:
        return sheet.worksheet(BUDGET_SHEET)
    except gspread.exceptions.WorksheetNotFound:
        logger.warning("Budget sheet not found. Creating new one.")
        return sheet.add_worksheet(title=BUDGET_SHEET, rows="1", cols="2")


def set_budget(sheet: gspread.Spreadsheet, username: str, amount: float) -> None:
    ws = get_budget_worksheet(sheet)
    records = ws.get_all_records()
    df = pd.DataFrame(records)

    column_name = "Username"

    if df.empty or column_name not in df.columns:
        ws.append_row([username, float(amount)])
        logger.info("Set budget for new user '%s' to %.2f.", username, amount)
        return

    if username in df[column_name].values:
        row_idx = df[df[column_name] == username].index[0] + 2
        ws.update(f"A{row_idx}:B{row_idx}", [[username, float(amount)]])
        logger.info("Updated budget for '%s' to %.2f.", username, amount)
    else:
        ws.append_row([username, float(amount)])
        logger.info("Set budget for new user '%s' to %.2f.", username, amount)


def get_budget(sheet: gspread.Spreadsheet, username: str) -> float:
    ws = get_budget_worksheet(sheet)
    records = ws.get_all_records()
    df = pd.DataFrame(records)

    try:
        return float(df[df['Username'] == username]["Budget"].values[0])
    except (IndexError, ValueError, KeyError) as e:
        logger.warning("No budget for '%s': %s. Defaulting to 0.0.", username, e)
        return 0.0


# Currency conversion functions
def get_exchange_rates(base=BASE_CURRENCY):
    """
    Fetches latest currency rates with respect to base currency (INR).
    Uses local caching in a JSON file per day to limit API calls.
    """
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            cache = json.load(f)
            if cache.get("date") == str(datetime.date.today()):
                logger.info("Using cached exchange rates.")
                return cache["rates"]

    url = f"https://api.exchangerate-api.com/v4/latest/{base}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        rates = data.get("rates", {})
        with open(CACHE_FILE, "w") as f:
            json.dump({"date": str(datetime.date.today()), "rates": rates}, f)
        logger.info("Fetched and cached latest exchange rates.")
        return rates
    except requests.RequestException as e:
        logger.error(f"Failed to fetch exchange rates: {e}")
        # Fallback to cached if exists, else empty dict
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r") as f:
                cache = json.load(f)
                return cache.get("rates", {})
        return {}


# --- Streamlit UI ---

st.set_page_config(page_title="Travel Expense Tracker", layout="wide")

gsheet = connect_sheet()
query_params = st.experimental_get_query_params()
username_list = query_params.get("username")
username = username_list[0] if username_list else None

if not username:
    st.error("Logged Out - No username provided")
    st.stop()

st.title(f"Welcome {username}")

if st.sidebar.button("Logout"):
    st.experimental_set_query_params()
    st.experimental_rerun()

# Sidebar - Budget section
st.sidebar.header("Set Your Budget")
curr_budget = get_budget(gsheet, username) or 0.0
budget_input = st.sidebar.number_input("Budget (INR):", min_value=0.0, value=curr_budget, step=100.0, format="%.2f")
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
    currency = st.selectbox("Currency", ["INR", "USD", "EUR", "AED", "JPY", "GBP"])
    location = st.text_input("Location")
    trip = st.text_input("Trip Name")

    if st.form_submit_button("Add"):
        rates = get_exchange_rates()
        if not rates:
            st.error("Failed to fetch currency exchange rates. Try again later.")
        else:
            # Convert from selected currency to INR
            rate_to_inr = rates.get(currency)
            if rate_to_inr is None:
                st.error(f"Exchange rate for {currency} not found.")
            else:
                # Since rates are relative to base currency (INR), and base=INR,
                # rates[currency] = how much 1 INR equals currency units,
                # but exchangerate-api returns rates as 1 base currency = x target currency.
                # Actually, for base=INR, rates["USD"] means 1 INR = x USD.
                # We want the inverse: 1 USD = ? INR
                # So invert the rate to get currency -> INR:
                # Example: rates['USD'] = 0.012, then 1 USD = 1 / 0.012 INR
                if currency == BASE_CURRENCY:
                    inr_equiv = amount
                else:
                    inr_equiv = round(amount / rate_to_inr, 2)

                add_ex_gsheet(gsheet, username, str(date), category, description, amount, location, trip, currency,
                              inr_equiv)
                st.success(f"Expense added! (₹{inr_equiv} INR equivalent)")

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
    # Use INR Amount for calculations
    total_spent = df["INR Amount"].sum()
    budget = get_budget(gsheet, username)
    remaining = budget - total_spent

    st.metric(label="Budget (INR)", value=f"₹{budget:,.2f}")
    st.metric(label="Total Spent (INR)", value=f"₹{total_spent:,.2f}")
    st.metric(label="Remaining Budget (INR)", value=f"₹{remaining:,.2f}")

    # Bar chart by category (sum INR Amount)
    cat_df = df.groupby("Category")["INR Amount"].sum().reset_index()
    st.bar_chart(data=cat_df.set_index("Category"))

    # Table of expenses
    st.markdown("### Expense Details")
    st.dataframe(df[["Date", "Category", "Description", "Amount", "Currency", "INR Amount", "Location", "Trip"]])

else:
    st.info("No expenses found. Please add some expenses.")

# Editing Expenses Section
if not df.empty:
    st.markdown("## Edit or Delete Expense")

    with st.form("select_expense_form"):
        row_options = df.apply(lambda x: f'{x["Date"].strftime("%Y-%m-%d")} | {x["Category"]} | {x["Description"]} | ₹{x["INR Amount"]:.2f}', axis=1)
        selected_expense = st.selectbox("Select expense to edit/delete:", options=row_options)
        if st.form_submit_button("Select"):
            idx = row_options[row_options == selected_expense].index[0]
            selected_row = df.loc[idx]

            with st.form("edit_expense_form"):
                new_date = st.date_input("Date", selected_row["Date"])
                new_category = st.selectbox("Category", ["Flights", "Hotels", "Food", "Transport", "Miscellaneous"], index=["Flights", "Hotels", "Food", "Transport", "Miscellaneous"].index(selected_row["Category"]))
                new_description = st.text_input("Description", selected_row["Description"])
                new_amount = st.number_input("Amount", min_value=0.0, value=float(selected_row["Amount"]), format="%.2f")
                new_currency = st.selectbox("Currency", ["INR", "USD", "EUR", "AED", "JPY", "GBP"], index=["INR", "USD", "EUR", "AED", "JPY", "GBP"].index(selected_row["Currency"]))
                new_location = st.text_input("Location", selected_row["Location"])
                new_trip = st.text_input("Trip", selected_row["Trip"])

                if st.form_submit_button("Update Expense"):
                    rates = get_exchange_rates()
                    rate_to_inr = rates.get(new_currency)
                    if rate_to_inr is None:
                        st.error(f"Exchange rate for {new_currency} not found.")
                    else:
                        if new_currency == BASE_CURRENCY:
                            new_inr = new_amount
                        else:
                            new_inr = round(new_amount / rate_to_inr, 2)

                        update_expense(gsheet, selected_row["Row"], username, str(new_date), new_category,
                                       new_description, new_amount, new_location, new_trip, new_currency, new_inr)
                        st.success("Expense updated!")
                        st.experimental_rerun()

                if st.form_submit_button("Delete Expense"):
                    delete_expense(gsheet, selected_row["Row"])
                    st.success("Expense deleted!")
                    st.experimental_rerun()
else:
    st.info("No expenses available to edit or delete.")
