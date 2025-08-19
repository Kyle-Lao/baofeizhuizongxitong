import streamlit as st
from datetime import date, timedelta  # for 7-day reminder
import calendar
from dateutil.relativedelta import relativedelta  # pip install python-dateutil

from sheets_db import (
    add_policy,
    get_policies,
    update_policy_tracking,
    delete_policy,
)

st.set_page_config(page_title="Premium Tracker (Sheets)", layout="wide")


# ===== Helpers =====
def _coerce_amount(x):
    try:
        return float(str(x).replace(",", "").replace("$", "").strip())
    except Exception:
        return 0.0


def find_next_premium(premium_schedule, due_day):
    """
    premium_schedule: list of 12 amounts for months 0..11 from 'this month'
    due_day: 1..28 recommended to avoid month-end pitfalls
    Returns: (date, amount) or (None, 0.0)
    """
    today = date.today()
    try:
        due_day = int(str(due_day).strip() or "15")
    except Exception:
        due_day = 15
    due_day = max(1, min(28, due_day))

    schedule = [_coerce_amount(a) for a in (premium_schedule or [])]
    schedule += [0.0] * (12 - len(schedule))
    schedule = schedule[:12]

    for m in range(12):
        cycle_month = today.replace(day=1) + relativedelta(months=+m)
        y, mo = cycle_month.year, cycle_month.month
        last_dom = calendar.monthrange(y, mo)[1]
        due_dt = date(y, mo, min(due_day, last_dom))
        amt = schedule[m]
        if amt > 0 and due_dt >= today:
            return due_dt, amt

    return None, 0.0


def _policy_row_display(p):
    due_dt, amt = find_next_premium(p.get("premium_schedule"), p.get("due_day"))
    next_due = due_dt.strftime("%Y-%m-%d") if due_dt else "—"
    reminder_dt = (due_dt - timedelta(days=7)) if due_dt else None
    reminder_str = reminder_dt.strftime("%Y-%m-%d") if reminder_dt else "—"
    next_amt = f"${amt:,.2f}" if amt else "—"

    # No "Mode" column anymore
    col1, col2, col3, col4, col5, col6 = st.columns([2, 1.6, 1.2, 1.2, 1, 1])
    col1.write(f"**{p['policy_number']}** — {p['insured_name']} ({p['carrier']})")
    col2.write(f"Next Due: {next_due}  \nReminder: {reminder_str}")
    col3.write(f"Amount: {next_amt}")
    tracking = (str(p.get("is_tracking", "1")) == "1")
    col4.write("Tracking: ✅" if tracking else "Tracking: ⛔️")

    # Toggle tracking
    with col5:
        toggle_label = "Disable" if tracking else "Enable"
        if st.button(toggle_label, key=f"toggle_{p['policy_number']}"):
            update_policy_tracking(p["policy_number"], not tracking)
            st.rerun()

    # Delete
    with col6:
        if st.button("Delete", key=f"delete_{p['policy_number']}"):
            delete_policy(p["policy_number"])
            st.rerun()

    with st.expander("Wiring details"):
        st.text(f"Wire Reference:\n{p.get('wire_reference') or ''}")
        st.text(f"Wiring Instructions:\n{p.get('wiring_instructions') or ''}")


# ===== Sidebar: Add Policy =====
st.sidebar.header("Add Policy")
with st.sidebar.form("add_policy_form", clear_on_submit=False):
    insured_name = st.text_input("Insured Name")
    policy_number = st.text_input("Policy Number")
    carrier = st.text_input("Carrier")
    due_day = st.number_input("Due Day (1–28 recommended)", min_value=1, max_value=31, value=15, step=1)

    # === Option A: show month-name labels ===
    st.write("**Monthly Premiums (starting from the current month)**")
    start = date.today().replace(day=1)
    labels = [(start + relativedelta(months=i)).strftime("%b %Y") for i in range(12)]

    paste_mode = st.checkbox("Paste comma-separated amounts instead", value=False)

    if paste_mode:
        st.caption("Order: " + " → ".join(labels))
        pasted = st.text_area(
            "Comma-separated (12 values). Example: 100,0,0,100,0,0,100,0,0,100,0,0",
            value="",
            height=100,
        )
        schedule = []
        if pasted.strip():
            schedule = [_coerce_amount(x) for x in pasted.split(",")]
        # normalize
        schedule += [0.0] * (12 - len(schedule))
        schedule = schedule[:12]
    else:
        cols = st.columns(3)
        schedule = []
        for i, label in enumerate(labels):
            with cols[i % 3]:
                amt = st.number_input(label, min_value=0.0, step=1.0, key=f"m{i+1}")
                schedule.append(amt)

    wire_reference = st.text_input("Wire Reference")
    wiring_instructions = st.text_area("Wiring Instructions", height=120)
    is_tracking = st.checkbox("Enable Tracking", value=True)

    submitted = st.form_submit_button("Add Policy")
    if submitted:
        add_policy(
            insured_name=insured_name,
            policy_number=policy_number,
            carrier=carrier,
            premium_mode="Monthly",  # default; column kept for sheet compatibility
            premium_schedule=schedule,
            wire_reference=wire_reference,
            wiring_instructions=wiring_instructions,
            is_tracking=is_tracking,
            due_day=due_day,
        )
        st.success(f"Policy {policy_number} added.")
        st.rerun()


# ===== Main: Tracked Policies =====
st.title("Premium Tracker (Google Sheets)")
policies = get_policies()

if not policies:
    st.info("No policies yet. Add one from the sidebar.")
else:
    st.subheader("Tracked Policies")
    for p in policies:
        _policy_row_display(p)
        st.divider()


# ===== Footnote =====
with st.expander("Notes"):
    st.markdown(
        """
- The schedule represents **12 months starting from the current month** and is labeled by month.
- For reliability across different month lengths, the app uses true month arithmetic for due dates.
- Recommended **Due Day** is 1–28.
- Reminder dates are shown at **7 days prior** to the next due date.
"""
    )
