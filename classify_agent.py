# agents/classify_agent.py

import sqlite3
import re

# ----------------------------------------------------------------------------
# 1) Ensure `category` column exists in `events` table
# ----------------------------------------------------------------------------
def init_category_column(conn):
    """
    Adds a 'category' column to the `events` table if it doesn't already exist.
    """
    cursor = conn.cursor()
    # Check current columns
    cursor.execute("PRAGMA table_info(events);")
    columns = [row[1] for row in cursor.fetchall()]  # row[1] is the column name
    if "category" not in columns:
        cursor.execute("ALTER TABLE events ADD COLUMN category TEXT DEFAULT 'Other';")
        conn.commit()

# ----------------------------------------------------------------------------
# 2) Define keyword‐to‐category mappings
# ----------------------------------------------------------------------------
CATEGORY_KEYWORDS = {
    "Technical": [
        "hackathon", "workshop", "coding", "tech", "developer", "programming", "algorithm", "data science", "ai", "ml"
    ],
    "Cultural": [
        "concert", "music", "dance", "drama", "theatre", "fest", "cultural", "band", "choir", "art", "creative"
    ],
    "Sports": [
        "tournament", "match", "game", "league", "cricket", "football", "basketball", "volleyball", "athletics", "race", "sport"
    ],
    "Career": [
        "career", "internship", "job", "placement", "seminar", "technical talk", "tech talk", "recruitment", "dpi", "resume", "workshop" 
        # note: "workshop" also appears under Technical, but Career‐context workshops are rare; we'll prefer the first hit.
    ],
    "Social": [
        "social", "networking", "meetup", "mixer", "party", "get-together", "gathering", "alumni"
    ]
}

# Pre‐compile lowercase keyword patterns for efficiency
COMPILED_KEYWORD_PATTERNS = {
    category: [re.compile(r"\b" + re.escape(keyword) + r"\b", flags=re.IGNORECASE)
               for keyword in keywords]
    for category, keywords in CATEGORY_KEYWORDS.items()
}

# ----------------------------------------------------------------------------
# 3) Classification logic
# ----------------------------------------------------------------------------
def classify_text(text):
    """
    Given a text blob (title + description), return the best matching category:
      - Search each category’s keywords in order of CATEGORY_KEYWORDS dict.
      - First category whose ANY keyword matches → return that category.
      - If no keywords match, return "Other".
    """
    for category, patterns in COMPILED_KEYWORD_PATTERNS.items():
        for pat in patterns:
            if pat.search(text):
                return category
    return "Other"

# ----------------------------------------------------------------------------
# 4) Main classification routine
# ----------------------------------------------------------------------------
def classify_events():
    """
    1) Connect to events.db, ensure `category` column exists.
    2) For each row in `events` (id, title, description), run classifier.
       • Update the `category` column accordingly.
    3) Print a summary of counts per category.
    """
    conn = sqlite3.connect("../events.db")
    c = conn.cursor()

    # 1) Ensure category column exists
    init_category_column(conn)

    # 2) Fetch all events (id, title, description)
    c.execute("SELECT id, title, description FROM events")
    rows = c.fetchall()  # list of (id, title, description)

    category_counts = {}

    for event_id, title, description in rows:
        # Combine title + description into one string, lowercase it 
        text_blob = f"{title}\n{description}".lower()

        # Run classifier
        assigned_category = classify_text(text_blob)

        # Update the events table
        c.execute(
            """
            UPDATE events
            SET category = ?
            WHERE id = ?
            """,
            (assigned_category, event_id)
        )
        conn.commit()

        # Tally for summary
        category_counts.setdefault(assigned_category, 0)
        category_counts[assigned_category] += 1

    conn.close()

    # 3) Print summary
    print("[Classifier] Assigned categories as follows:")
    for cat, count in sorted(category_counts.items()):
        print(f"  • {cat}: {count} event(s)")

# ----------------------------------------------------------------------------
# Script entry point
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    classify_events()
