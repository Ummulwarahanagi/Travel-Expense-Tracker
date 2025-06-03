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
    data = ws.get_all_records()
    df = pd.DataFrame(data)

    if df.empty:
        logger.warning("Google Sheet data is empty.")
        return df

    if len(df.columns) > 0 and all(isinstance(col, str) for col in df.columns):
        df.columns = df.columns.str.strip()
        logger.info("Columns in DataFrame: %s", df.columns.tolist())

    column_name = "username"  # Match your sheet exactly
    if column_name not in df.columns:
        raise KeyError(f"Column '{column_name}' not found in Google Sheet")

    df = df[df[column_name] == username].reset_index(drop=True)
    df["Row"] = list(range(2, 2 + len(df)))
    return df

def get_user_budget(sheet: gspread.Spreadsheet, username: str) -> float:
    ws = sheet.worksheet("Budget")
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

def add_ex_gsheet(sheet: gspread.Spreadsheet, username: str, date: str, category: str, description: str, amount: float, location: str, trip: str) -> None:
    ws = sheet.worksheet(SHEET_NAME)
    ws.append_row([username, date, category, description, float(amount), location, trip])
    logger.info("Expense added for '%s': %s | %s | %.2f | %s | %s", username, date, category, amount, location, trip)

def delete_expense(sheet: gspread.Spreadsheet, row_number: int) -> None:
    try:
        ws = sheet.worksheet(SHEET_NAME)
        ws.delete_rows(row_number)
        logger.info("Deleted row %d.", row_number)
    except gspread.exceptions.APIError as e:
        logger.error("Failed to delete row %d: %s", row_number, e)

def update_expense(sheet: gspread.Spreadsheet, row_number: int, username: str, date: str, category: str, description: str, amount: float, location: str, trip: str) -> None:
    try:
        ws = sheet.worksheet(SHEET_NAME)
        ws.update(f"A{row_number}:H{row_number}", [[username, date, category, description, float(amount), location, trip]])
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

    logger.info("Budget sheet columns: %s", df.columns.tolist())

    column_name = "username"  # Match your sheet's exact column header

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
        return float(df[df['username'] == username]["Budget"].values[0])
    except (IndexError, ValueError, KeyError) as e:
        logger.warning("No budget for '%s': %s. Defaulting to 0.0.", username, e)
        return 0.0
