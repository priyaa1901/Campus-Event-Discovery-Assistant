# agents/notify_agent.py

import sqlite3
from datetime import datetime, timedelta

DB_PATH = "../events.db"

def get_tomorrows_events():
    """
    Fetch events whose date(datetime) is exactly tomorrow's date (local).
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    tomorrow_str = (datetime.today() + timedelta(days=1)).date().isoformat()
    c.execute(
        """
        SELECT id, datetime, category, title, location, sources
        FROM events
        WHERE date(datetime) = ?
        ORDER BY datetime;
        """,
        (tomorrow_str,)
    )
    rows = c.fetchall()
    conn.close()
    return rows

def format_event_row(row):
    """
    Given a row tuple (id, datetime, category, title, location, sources),
    return a single‐line string summary.
    """
    eid, dt, cat, title, loc, src = row
    # Show “HH:MM” part of dt for brevity
    time_part = dt.split("T")[1]
    return f"[{time_part}] ({cat}) {title} — {loc or 'No location'} [{src}]"

if __name__ == "__main__":
    tomorrow_str = (datetime.today() + timedelta(days=1)).date().isoformat()
    print(f"\n📣  Notifications for {tomorrow_str}:\n")

    events = get_tomorrows_events()
    if not events:
        print("No events scheduled for tomorrow.\n")
    else:
        for ev in events:
            print(" • " + format_event_row(ev))
        print()

    # (Optional) Return an exit code or write to a file, etc.
