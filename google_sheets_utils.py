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

    if not raw_data or len(raw_data) < 2:
        raise ValueError("Sheet is empty or does not have enough rows.")

    header = [col.strip().lower() for col in raw_data[0]]
    data_rows = raw_data[1:]

    df = pd.DataFrame(data_rows, columns=header)

    if "username" not in df.columns:
        raise ValueError(f"Column 'username' not found. Columns: {df.columns.tolist()}")

    df = df[df["username"] == username]

    # Optional: Convert numeric column(s)
    if "amount" in df.columns:
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)

    # Add row numbers (for Google Sheets indexing)
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
        if row["username"] == username:
            ws.update(f"B{idx}", [[float(amount)]])
            return
    # If not found, append new row
    ws.append_row([username, float(amount)])


def get_budget(sheet: gspread.Spreadsheet, username: str) -> float:
    ws = get_budget_worksheet(sheet)
    data = ws.get_all_records()
    for row in data:
        if row["username"] == username:
            try:
                return float(row["Budget"])
            except ValueError:
                return 0.0
    return 0.0  # default if not foun
def add_expense_with_trip(sheet, username, date, category, description, amount, location, trip="General", shared_with=None):
    ws = sheet.worksheet(SHEET_NAME)

    if shared_with:
        shared_str = ",".join(shared_with)
        total_people = len(shared_with) + 1  # including payer
        split_amt = round(float(amount) / total_people, 2)
    else:
        shared_str = ""
        split_amt = float(amount)

    ws.append_row([
        username,
        date,
        category,
        description,
        float(amount),
        location,
        trip,
        shared_str,
        split_amt
    ])


def load_expense_with_trip(sheet, username, trip=None):
    ws = sheet.worksheet(SHEET_NAME)
    raw_data = ws.get_all_values()
    header = [col.strip().lower() for col in raw_data[0]]
    data_rows = raw_data[1:]
    df = pd.DataFrame(data_rows, columns=header)
    df = df[df["username"] == username]
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    df["Row"] = list(range(2, 2 + len(df)))
    if trip:
        df = df[df["trip"] == trip]
    return df

def update_expense_with_trip(sheet, row_number, date, category, description, amount, location, trip="General"):
    ws = sheet.worksheet(SHEET_NAME)
    ws.update(f"B{row_number}:F{row_number}", [[date, category, description, float(amount), location]])
    ws.update(f"G{row_number}", [[trip]])  # Note the double brackets here

    
def get_user_trips(sheet, username):
    try:
        df = load_ex_gsheet(sheet, username)
        if not df.empty and "trip" in df.columns:
            trips = df["trip"].dropna().unique().tolist()
            return sorted(list(set(trips)))
    except Exception as e:
        print("Error in get_user_trips:", e)
    return ["General"]



