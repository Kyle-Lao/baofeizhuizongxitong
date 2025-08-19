import os
import smtplib
from email.mime.text import MIMEText
from datetime import date, timedelta
import calendar
from dateutil.relativedelta import relativedelta  # pip install python-dateutil
from dotenv import load_dotenv  # pip install python-dotenv

from sheets_db import get_policies

load_dotenv()

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
EMAIL_SENDER = os.getenv("EMAIL_SENDER")         # full email address
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")     # App Password (if Gmail + 2FA)
EMAIL_RECIPIENTS = [e.strip() for e in os.getenv("EMAIL_RECIPIENTS", "").split(",") if e.strip()]


def _coerce_amount(x):
    try:
        return float(str(x).replace(",", "").replace("$", "").strip())
    except Exception:
        return 0.0


def _next_due_for_policy(policy):
    """Return (due_date, amount) for the first non-zero monthly entry >= today."""
    schedule = [_coerce_amount(a) for a in (policy.get("premium_schedule") or [])]
    schedule += [0.0] * (12 - len(schedule))
    schedule = schedule[:12]

    try:
        due_day = int(str(policy.get("due_day") or "15").strip())
    except Exception:
        due_day = 15
    due_day = max(1, min(28, due_day))

    today = date.today()
    for m in range(12):
        base = today.replace(day=1) + relativedelta(months=+m)
        y, mo = base.year, base.month
        last_dom = calendar.monthrange(y, mo)[1]
        due_dt = date(y, mo, min(due_day, last_dom))
        amt = schedule[m]
        if amt > 0 and due_dt >= today:
            return due_dt, amt
    return None, 0.0


def _send_email(subject, body, recipients):
    if not recipients:
        return
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = ", ".join(recipients)
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)


def check_due_premiums():
    """Send reminders exactly 7 days before the next due date."""
    today = date.today()
    for p in (get_policies() or []):
        if str(p.get("is_tracking", "1")) != "1":
            continue
        due, amt = _next_due_for_policy(p)
        if not (due and amt > 0):
            continue
        reminder_dt = due - timedelta(days=7)
        if reminder_dt == today:
            subject = f"[Premium Due Soon] Policy {p['policy_number']} ({p['insured_name']})"
            body = f"""Policy Number: {p['policy_number']}
Insured Name: {p['insured_name']}
Carrier: {p['carrier']}

Due Date: {due.strftime('%B %d, %Y')}
Amount: ${amt:,.2f}

Wiring Instructions:
{p.get('wiring_instructions') or ''}

Wire Reference:
{p.get('wire_reference') or ''}

(Automated reminder sent 7 days before due date)
"""
            _send_email(subject, body, EMAIL_RECIPIENTS)


if __name__ == "__main__":
    check_due_premiums()
