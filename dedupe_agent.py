# agents/dedupe_agent.py

import sqlite3
from datetime import datetime, timedelta

# ----------------------------------------------------------------------------
# Connect to the same SQLite database and ensure `events` table exists.
# ----------------------------------------------------------------------------
def init_events_table(conn):
    """
    Create the `events` table if it doesn't already exist. Columns:

      id          INTEGER PRIMARY KEY AUTOINCREMENT
      title       TEXT    NOT NULL
      datetime    TEXT    NOT NULL       -- ISO 8601 string
      location    TEXT
      description TEXT
      sources     TEXT    NOT NULL       -- comma-separated list of source handles

    A UNIQUE constraint on (title, datetime, location) will help avoid
    exact duplicates.
    """
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT    NOT NULL,
            datetime    TEXT    NOT NULL,
            location    TEXT,
            description TEXT,
            sources     TEXT    NOT NULL,
            UNIQUE(title, datetime, location)
        );
    """)
    conn.commit()

# ----------------------------------------------------------------------------
# Helper to parse an ISO datetime string into a Python datetime object.
# ----------------------------------------------------------------------------
def parse_iso_datetime(dt_str):
    try:
        return datetime.fromisoformat(dt_str)
    except ValueError:
        return None

# ----------------------------------------------------------------------------
# Find a matching event within ±5 minutes of (title, datetime, location)
# ----------------------------------------------------------------------------
def find_matching_event(cursor, title, dt_obj, location):
    """
    Query the `events` table for rows with the same title & location,
    and whose datetime is within ±5 minutes of dt_obj.

    Returns:
      (event_id:int, existing_datetime_str:str, existing_sources:str, existing_description:str)
      or None if no match.
    """
    # First, fetch any event rows with the same title and location
    cursor.execute(
        """
        SELECT id, datetime, sources, description
        FROM events
        WHERE title = ? AND location = ?
        """,
        (title, location)
    )
    candidates = cursor.fetchall()  # list of (id, datetime_str, sources, description)

    # Check time proximity
    for event_id, existing_dt_str, sources, desc in candidates:
        existing_dt = parse_iso_datetime(existing_dt_str)
        if existing_dt is None:
            continue
        diff = abs((existing_dt - dt_obj).total_seconds())
        if diff <= 5 * 60:  # within 5 minutes
            return (event_id, existing_dt_str, sources, desc)

    return None

# ----------------------------------------------------------------------------
# Main deduplication logic
# ----------------------------------------------------------------------------
def dedupe_raw_events():
    """
    1) Connect to events.db and initialize tables.
    2) For each row in raw_events:
         a) Attempt to find a matching event in events (±5 min, same title & location).
         b) If found: update that row's sources+description.
            Else: insert a new row into events.
    3) Print a summary at the end.
    """
    # 1) Connect/create the database
    conn = sqlite3.connect("../events.db")
    c = conn.cursor()

    # Ensure events table exists
    init_events_table(conn)

    # 2) Fetch all rows from raw_events
    c.execute("SELECT id, title, datetime, location, description, source FROM raw_events")
    raw_rows = c.fetchall()  # list of tuples

    inserted_count = 0
    updated_count = 0

    for raw_id, title, dt_str, location, description, source in raw_rows:
        dt_obj = parse_iso_datetime(dt_str)
        if dt_obj is None:
            # Skip any malformed datetime
            continue

        # 3a) Attempt to find an existing event that matches
        match = find_matching_event(c, title, dt_obj, location or "")
        if match:
            event_id, existing_dt_str, existing_sources, existing_desc = match

            # Build updated sources list (comma-separated, unique)
            source_list = [s.strip() for s in existing_sources.split(",") if s.strip()]
            if source not in source_list:
                source_list.append(source)
            new_sources = ",".join(source_list)

            # Build updated description (append if new)
            desc_list = [line.strip() for line in existing_desc.split("\n---\n") if line.strip()]
            if description.strip() and description.strip() not in desc_list:
                desc_list.append(description.strip())
            new_description = "\n---\n".join(desc_list)

            # Update the existing row
            c.execute(
                """
                UPDATE events
                SET sources = ?, description = ?
                WHERE id = ?
                """,
                (new_sources, new_description, event_id)
            )
            updated_count += 1
        else:
            # 3b) No existing match: insert new event
            c.execute(
                """
                INSERT INTO events (title, datetime, location, description, sources, source)
                VALUES (?, ?, ?, ?, ?, '')
                """,
                (title, dt_str, location, description, source)
            )
            inserted_count += 1

        conn.commit()

    conn.close()

    print(f"[Deduper] Inserted {inserted_count} new event(s).")
    print(f"[Deduper] Updated {updated_count} existing event(s).")

# ----------------------------------------------------------------------------
# Script entry point
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    dedupe_raw_events()
