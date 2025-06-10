# db_init.py

import sqlite3
import os

# ----------------------------------------------------------------------------
# We assume `events.db` lives one level above this file (in the project root).
# __file__ refers to "…/campus_event_assistant/agents/db_init.py".
# So we construct the path to "events.db" as two dots up + "/events.db".
# ----------------------------------------------------------------------------
BASE_DIR = os.path.dirname(__file__)              # …/campus_event_assistant/agents
DB_PATH = os.path.abspath(os.path.join(BASE_DIR, "..", "events.db"))
# Now DB_PATH is ".../campus_event_assistant/events.db"

def init_db():
    """
    Connect to the SQLite database (creates events.db if it doesn't exist),
    then create the three tables if they do not already exist:

      1) raw_events  : holds every parsed event from Instagram, even duplicates.
      2) events      : final, deduplicated events with categories attached.
      3) users       : each student's username and their preferred categories.

    Returns:
        conn : sqlite3.Connection
        c    : sqlite3.Cursor
    """
    # 1) Ensure the directory for the DB exists (optional, but safe)
    db_dir = os.path.dirname(DB_PATH)
    os.makedirs(db_dir, exist_ok=True)

    # 2) Open a connection to events.db (will create the file if missing)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 3) Create the raw_events table
    c.execute("""
    CREATE TABLE IF NOT EXISTS raw_events (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        title       TEXT    NOT NULL,
        datetime    TEXT    NOT NULL,  -- ISO8601 string (e.g., "2025-06-04T15:00:00")
        location    TEXT,
        description TEXT,
        source      TEXT    NOT NULL,  -- e.g., "dept_compsci_official"
        ingested_at TEXT    DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 4) Create the final events table
    c.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id          INTEGER PRIMARY KEY,
        title       TEXT    NOT NULL,
        datetime    TEXT    NOT NULL,
        location    TEXT,
        description TEXT,
        source      TEXT    NOT NULL,
        category    TEXT,             -- e.g., "technical", "cultural", etc.
        deduped     INTEGER DEFAULT 0 -- 0 = not yet processed, 1 = deduplicated/ready
    );
    """)

    # 5) Create the users table for storing preferences
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username   TEXT PRIMARY KEY,  -- e.g., "alice", "bob"
        categories TEXT                -- JSON-encoded list, e.g. '["technical","sports"]'
    );
    """)

    # 6) Commit the schema changes and return the connection+cursor
    conn.commit()
    return conn, c
