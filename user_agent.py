# agents/user_agent.py

import sqlite3

DB_PATH = "../events.db"  # relative to this script

# ----------------------------------------------------------------------------
# 1) Ensure the `users` table exists
# ----------------------------------------------------------------------------
def init_users_table():
    """
    Creates the `users` table if it doesn't already exist. Columns:
      • username (TEXT PRIMARY KEY)
      • categories (TEXT)  — comma-separated category names
      • keywords   (TEXT)  — comma-separated custom keywords
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username   TEXT PRIMARY KEY,
            categories TEXT,
            keywords   TEXT
        );
    """)
    conn.commit()
    conn.close()

# ----------------------------------------------------------------------------
# 2) Add or update a user’s preferences
# ----------------------------------------------------------------------------
def set_user_preferences(username, categories_list, keywords_list):
    """
    Inserts or updates a user in `users`, storing:
      • username           — unique user identifier (string)
      • categories_list    — list of categories (e.g. ["Technical","Sports"])
      • keywords_list      — list of extra keywords (e.g. ["robotics","hackathon"])
    """
    init_users_table()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Join lists into comma-separated strings (empty string if list is empty)
    cat_str = ",".join(categories_list) if categories_list else ""
    key_str = ",".join(keywords_list)   if keywords_list   else ""

    # Use INSERT OR REPLACE so that if the username already exists, we overwrite
    c.execute(
        """
        INSERT OR REPLACE INTO users (username, categories, keywords)
        VALUES (?, ?, ?)
        """,
        (username, cat_str, key_str)
    )
    conn.commit()
    conn.close()

# ----------------------------------------------------------------------------
# 3) Fetch a user’s preferences
# ----------------------------------------------------------------------------
def get_user_preferences(username):
    """
    Returns a tuple (categories_list, keywords_list) for the given username.
    If the user does not exist, returns ([], []).
    """
    init_users_table()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT categories, keywords FROM users WHERE username = ?",
        (username,)
    )
    row = c.fetchone()
    conn.close()

    if not row:
        return [], []

    cat_str, key_str = row
    categories_list = [s for s in cat_str.split(",") if s] if cat_str else []
    keywords_list   = [s for s in key_str.split(",") if s] if key_str else []
    return categories_list, keywords_list

# ----------------------------------------------------------------------------
# 4) Delete a user’s profile (optional)
# ----------------------------------------------------------------------------
def delete_user(username):
    """
    Removes a user and their preferences from the `users` table.
    """
    init_users_table()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE username = ?", (username,))
    conn.commit()
    conn.close()

# ----------------------------------------------------------------------------
# 5) List all users (for debugging or admin purposes)
# ----------------------------------------------------------------------------
def list_all_users():
    """
    Returns a list of (username, categories_list, keywords_list) for every user in `users`.
    """
    init_users_table()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username, categories, keywords FROM users")
    rows = c.fetchall()
    conn.close()

    result = []
    for username, cat_str, key_str in rows:
        categories_list = [s for s in cat_str.split(",") if s] if cat_str else []
        keywords_list   = [s for s in key_str.split(",") if s] if key_str else []
        result.append((username, categories_list, keywords_list))
    return result

# ----------------------------------------------------------------------------
# 6) Simple command‐line interface (for testing)
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    """
    Usage examples (run from campus_event_assistant/agents):

      # 1) Create or update user “alice” with categories “Technical, Sports” 
      #    and keywords “robotics,ai”:
      python user_agent.py set alice Technical Sports --keywords robotics ai

      # 2) Fetch preferences for “alice”:
      python user_agent.py get alice

      # 3) List all users:
      python user_agent.py list

      # 4) Delete user “alice”:
      python user_agent.py delete alice
    """

    import argparse

    parser = argparse.ArgumentParser(
        description="Manage user preference profiles (categories + keywords)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # set <username> <categories> [--keywords <kw1> <kw2> ...]
    p_set = subparsers.add_parser("set", help="Set or update a user’s preferences")
    p_set.add_argument("username", type=str, help="Unique username")
    p_set.add_argument("categories", nargs="+", type=str,
                       help="List of categories (e.g. Technical Sports Cultural)")
    p_set.add_argument("--keywords", nargs="*", default=[],
                       help="Optional list of extra keywords")

    # get <username>
    p_get = subparsers.add_parser("get", help="Retrieve a user’s preferences")
    p_get.add_argument("username", type=str, help="Unique username")

    # delete <username>
    p_del = subparsers.add_parser("delete", help="Delete a user’s profile")
    p_del.add_argument("username", type=str, help="Unique username")

    # list
    p_list = subparsers.add_parser("list", help="List all user profiles")

    args = parser.parse_args()

    if args.command == "set":
        set_user_preferences(args.username, args.categories, args.keywords)
        print(f"[UserAgent] Set preferences for '{args.username}':")
        print(f"  Categories: {args.categories}")
        print(f"  Keywords:   {args.keywords}")

    elif args.command == "get":
        cats, kws = get_user_preferences(args.username)
        if not cats and not kws:
            print(f"[UserAgent] No profile found for '{args.username}'.")
        else:
            print(f"[UserAgent] Preferences for '{args.username}':")
            print(f"  Categories: {cats}")
            print(f"  Keywords:   {kws}")

    elif args.command == "delete":
        delete_user(args.username)
        print(f"[UserAgent] Deleted profile for '{args.username}' (if it existed).")

    elif args.command == "list":
        all_users = list_all_users()
        if not all_users:
            print("[UserAgent] No users in the database.")
        else:
            print("[UserAgent] All user profiles:")
            for uname, cats, kws in all_users:
                print(f"  - {uname}: Categories={cats}, Keywords={kws}")
