import gspread
import pandas as pd
import logging
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants

SHEET_NAME = "Sheet1"
BUDGET_SHEET = "Budget"
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
    raw_data = ws.get_all_values()

    import streamlit as st
    st.write("🧪 Raw data from sheet:", raw_data)

    if not raw_data or len(raw_data) < 2:
        raise ValueError("Sheet is empty or does not have enough rows.")

    # Extract header and data
    header = [h.strip().lower() for h in raw_data[0]]
    st.write("🧪 Extracted header:", header)

    data_rows = raw_data[1:]
    df = pd.DataFrame(data_rows, columns=header)
    st.write("🧪 DataFrame preview:", df.head())

    if "username" not in df.columns:
        raise ValueError(f"❌ Could not find a 'username' column. Found: {df.columns.tolist()}")

    df = df[df["username"] == username]
    df["Row"] = list(range(2, 2 + len(df)))

    return df





def add_ex_gsheet(sheet: gspread.Spreadsheet, username: str, date: str, category: str, description: str, amount: float, location: str) -> None:
    ws = sheet.worksheet(SHEET_NAME)
    ws.append_row([username, date, category, description, float(amount), location])
    logger.info("Expense added for user %s: %s | %s | %s | %.2f | %s", username, date, category, description, amount, location)



def delete_expense(sheet: gspread.Spreadsheet, row_number: int) -> None:
    try:
        ws = sheet.worksheet(SHEET_NAME)
        ws.delete_rows(row_number)
        logger.info("Deleted row %d.", row_number)
    except gspread.exceptions.APIError as e:
        logger.error("Failed to delete row %d: %s", row_number, e)

def update_expense(sheet: gspread.Spreadsheet, row_number: int, date: str, category: str, description: str, amount: float, location: str) -> None:
    try:
        ws = sheet.worksheet(SHEET_NAME)
        ws.update(f"A{row_number}", [[date, category, description, float(amount), location]])
        logger.info("Updated row %d.", row_number)
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
    data = ws.get_all_records()
    for idx, row in enumerate(data, start=2):
        if row["Username"] == username:
            ws.update(f"B{idx}", [[float(amount)]])
            return
    # If not found, append new row
    ws.append_row([username, float(amount)])


def get_budget(sheet: gspread.Spreadsheet, username: str) -> float:
    ws = get_budget_worksheet(sheet)
    data = ws.get_all_records()
    for row in data:
        if row["Username"] == username:
            try:
                return float(row["Budget"])
            except ValueError:
                return 0.0
    return 0.0  # default if not found
 
