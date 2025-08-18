import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime

# ===== CONFIG =====
SHEET_NAME = "Premium_Tracking"
WORKSHEET_NAME = "Policies"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",  # Required to open by title
]
CREDS_FILE = "credentials.json"  # Path relative to where you run the app

HEADERS = [
    "insured_name",        # col 1
    "policy_number",       # col 2
    "carrier",             # col 3
    "premium_mode",        # col 4 (kept for compatibility with UI)
    "premium_schedule",    # col 5 (JSON string of 12 monthly amounts)
    "wire_reference",      # col 6
    "wiring_instructions", # col 7
    "is_tracking",         # col 8 ("1"/"0")
    "created_at",          # col 9 (UTC ISO)
    "due_day"              # col 10 (1..28 recommended)
]
# ==================


def _client():
    creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
    return gspread.authorize(creds)


def _worksheet():
    client = _client()
    sheet = client.open(SHEET_NAME)
    ws = sheet.worksheet(WORKSHEET_NAME)
    # Bootstrap/repair header row (idempotent; no API version issues)
    values = ws.get_all_values()
    # Write headers into row 1 always (safe even if row 1 already has headers)
    ws.update(f"A1:J1", [HEADERS])
    # If sheet was empty before, ensure row 1 exists now (update created it)
    return ws


def add_policy(
    insured_name: str,
    policy_number: str,
    carrier: str,
    premium_mode: str,
    premium_schedule,  # list of 12 numbers/strings
    wire_reference: str,
    wiring_instructions: str,
    is_tracking: bool = True,
    due_day: int = 15,
):
    """Append a new policy row."""
    ws = _worksheet()
    row = [
        (insured_name or "").strip(),
        (policy_number or "").strip(),
        (carrier or "").strip(),
        (premium_mode or "").strip(),
        json.dumps(premium_schedule or []),
        (wire_reference or "").strip(),
        (wiring_instructions or "").strip(),
        "1" if is_tracking else "0",
        datetime.utcnow().isoformat(timespec="seconds"),
        str(int(due_day) if str(due_day).strip().isdigit() else 15),
    ]
    ws.append_row(row, value_input_option="RAW")


def get_policies():
    """Return list[dict] of policies (empty list if none)."""
    ws = _worksheet()
    data = ws.get_all_values()
    if len(data) <= 1:
        return []

    out = []
    for row in data[1:]:
        if not row or all(not c for c in row):
            continue
        row = (row + [""] * len(HEADERS))[:len(HEADERS)]
        try:
            schedule = json.loads(row[4] or "[]")
            if not isinstance(schedule, list):
                schedule = []
        except Exception:
            schedule = []
        out.append({
            "insured_name": row[0],
            "policy_number": row[1],
            "carrier": row[2],
            "premium_mode": row[3],
            "premium_schedule": schedule,
            "wire_reference": row[5],
            "wiring_instructions": row[6],
            "is_tracking": row[7],
            "created_at": row[8],
            "due_day": row[9],
        })
    return out


def update_policy_tracking(policy_number: str, is_tracking: bool):
    """Set is_tracking to '1' or '0' for the given policy_number."""
    ws = _worksheet()
    data = ws.get_all_values()
    for idx, row in enumerate(data[1:], start=2):
        if len(row) > 1 and row[1] == policy_number:
            ws.update_cell(idx, 8, str(int(bool(is_tracking))))
            return True
    return False


def delete_policy(policy_number: str) -> bool:
    """Delete the row matching policy_number. Returns True if deleted."""
    ws = _worksheet()
    data = ws.get_all_values()
    for idx, row in enumerate(data[1:], start=2):
        if len(row) > 1 and row[1] == policy_number:
            # gspread v6 uses delete_rows; older versions used delete_row
            if hasattr(ws, "delete_rows"):
                ws.delete_rows(idx)
            else:
                ws.delete_row(idx)  # fallback for older gspread
            return True
    return False
