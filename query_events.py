# agents/query_events.py

import sqlite3
import argparse
from datetime import datetime, timedelta

DB_PATH = "../events.db"

def print_events(rows):
    if not rows:
        print("No events found for this query.")
        return

    header = f"{'ID':<3} {'Date & Time':<20} {'Category':<12} {'Title':<40} {'Location':<25} {'Sources'}"
    print(header)
    print("-" * len(header))
    for eid, dt, cat, title, loc, src in rows:
        print(f"{eid:<3} {dt:<20} {cat:<12} {title[:37]:<40} {loc[:23]:<25} {src}")

def get_all_events():
    """
    Fetch every event (no date filtering), ordered by datetime.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        SELECT id, datetime, category, title, location, sources
        FROM events
        ORDER BY datetime;
        """
    )
    rows = c.fetchall()
    conn.close()
    return rows

def get_past_events():
    """
    Fetch events with date(datetime) < today, ordered by datetime.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    today_str = datetime.today().date().isoformat()
    c.execute(
        """
        SELECT id, datetime, category, title, location, sources
        FROM events
        WHERE date(datetime) < ?
        ORDER BY datetime;
        """,
        (today_str,)
    )
    rows = c.fetchall()
    conn.close()
    return rows

def get_upcoming_events():
    """
    Fetch events with date(datetime) >= today, ordered by datetime.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    today_str = datetime.today().date().isoformat()
    c.execute(
        """
        SELECT id, datetime, category, title, location, sources
        FROM events
        WHERE date(datetime) >= ?
        ORDER BY datetime;
        """,
        (today_str,)
    )
    rows = c.fetchall()
    conn.close()
    return rows

def get_events_between(start_offset, end_offset):
    """
    Fetch events whose date(datetime) is between today+start_offset and today+end_offset (inclusive).
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    start_date = (datetime.today() + timedelta(days=start_offset)).date().isoformat()
    end_date   = (datetime.today() + timedelta(days=end_offset)).date().isoformat()

    c.execute(
        """
        SELECT id, datetime, category, title, location, sources
        FROM events
        WHERE date(datetime) BETWEEN ? AND ?
        ORDER BY datetime;
        """,
        (start_date, end_date)
    )
    rows = c.fetchall()
    conn.close()
    return rows

def get_events_category(cat):
    """
    Fetch events with category exactly = cat.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        SELECT id, datetime, category, title, location, sources
        FROM events
        WHERE category = ?
        ORDER BY datetime;
        """,
        (cat,)
    )
    rows = c.fetchall()
    conn.close()
    return rows

def get_events_keyword(kw):
    """
    Fetch events where title LIKE '%kw%' OR description LIKE '%kw%'.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    like = f"%{kw}%"
    c.execute(
        """
        SELECT id, datetime, category, title, location, sources
        FROM events
        WHERE title LIKE ? OR description LIKE ?
        ORDER BY datetime;
        """,
        (like, like)
    )
    rows = c.fetchall()
    conn.close()
    return rows

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query campus events (no login required).")
    group = parser.add_mutually_exclusive_group()

    # Date‐based flags:
    group.add_argument("--past",      action="store_true", help="Show events date < today")
    group.add_argument("--upcoming",  action="store_true", help="Show events date ≥ today")
    group.add_argument("--today",     action="store_true", help="Show events happening today")
    group.add_argument("--tomorrow",  action="store_true", help="Show events happening tomorrow")
    group.add_argument("--this-week", action="store_true", help="Show events happening in the next 7 days")

    # Category / keyword:
    group.add_argument("--category", type=str, help="Filter by category (exact match)")
    group.add_argument("--keyword",  type=str, help="Filter by keyword (in title or description)")

    args = parser.parse_args()

    # 1) If --past, show only past events
    if args.past:
        rows = get_past_events()
        print_events(rows)

    # 2) If --upcoming, show only future events
    elif args.upcoming:
        rows = get_upcoming_events()
        print_events(rows)

    # 3) If --today, show events where date(datetime) == today
    elif args.today:
        rows = get_events_between(0, 0)
        print_events(rows)

    # 4) If --tomorrow, show date(datetime) == today+1
    elif args.tomorrow:
        rows = get_events_between(1, 1)
        print_events(rows)

    # 5) If --this-week, show date(datetime) BETWEEN today and today+6
    elif args.this_week:
        rows = get_events_between(0, 6)
        print_events(rows)

    # 6) If --category, filter by category
    elif args.category:
        rows = get_events_category(args.category)
        print_events(rows)

    # 7) If --keyword, filter by keyword substring
    elif args.keyword:
        rows = get_events_keyword(args.keyword)
        print_events(rows)

    # 8) No flags: show ALL events (past + future)
    else:
        rows = get_all_events()
        print_events(rows)
