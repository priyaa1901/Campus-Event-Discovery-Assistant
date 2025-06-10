# agents/ingest_agent.py

import re
import sqlite3
import time
import random
import requests
import json
from datetime import datetime, timedelta
from db_init import init_db
from bs4 import BeautifulSoup
import getpass
from typing import List

# ----------------------------------------------------------------------------
# CONFIGURATION
# ----------------------------------------------------------------------------

DB_PATH = "../events.db"
INSTAGRAM_HANDLES = [
    "dsync_bmsce",
    "csbs_bmsce",
    "rotaract_bmsce",
    "codeio_bmsce",
    "varaince_bmsce",
    "gradient.aiml",
    "bmsce_ieeecs",
    "protocol_bmsce",
    "bmsce_acm",
    "abc_bmsce"
]
MAX_POSTS_PER_PROFILE = 3       # Fetch up to 3 recent posts per handle
DELAY_BETWEEN_PROFILES = 5      # Seconds to wait between each handle

# ----------------------------------------------------------------------------
# 1) Caption Parsing Helpers (same as before)
# ----------------------------------------------------------------------------

def parse_caption(caption_text):
    """
    Heuristic parser for Instagram captions. Returns (title, datetime_obj, location, description).
    """
    if not caption_text or not caption_text.strip():
        return "", None, "", ""

    raw_lines = [ln.strip() for ln in caption_text.splitlines()]
    lines = [L for L in raw_lines if L]
    if not lines:
        return "", None, "", ""

    greeting_pattern = re.compile(r"^(Greetings|Warm|Hello|Hi|Get ready|Are you ready|Think you|Join us)", flags=re.IGNORECASE)
    filler_pattern = re.compile(r"^(Event\s*Details:?|Details:?|What are you waiting for|Here's what|Save the date)", flags=re.IGNORECASE)
    emoji_strip_pattern = re.compile(r'^[🎉✨🚀💫🌟🔥⚡📅🕒📍💰🏆👥]+')

    candidates = []
    for ln in lines:
        if not greeting_pattern.match(ln) and not filler_pattern.match(ln) and len(ln) > 5:
            clean_ln = emoji_strip_pattern.sub("", ln).strip()
            if clean_ln:
                candidates.append(clean_ln)
    if not candidates:
        candidates = [emoji_strip_pattern.sub("", ln).strip() for ln in lines if emoji_strip_pattern.sub("", ln).strip()]

    title = None
    date_obj = None
    event_time_str = ""
    location = ""
    description_parts = []
    date_line_idx = None

    date_patterns = [
        re.compile(r"^(?:📅\s*)?Date\s*[:：]\s*(.+)$", flags=re.IGNORECASE),
        re.compile(r"^📅\s*(.+)$"),
        re.compile(r"^Date\s*[:：]\s*(.+)$", flags=re.IGNORECASE),
    ]
    time_patterns = [
        re.compile(r"^(?:🕒|🕚|⏰|🕝|🕓|🕑)\s*Time\s*[:：]\s*(.+)$", flags=re.IGNORECASE),
        re.compile(r"^Time\s*[:：]\s*(.+)$", flags=re.IGNORECASE),
        re.compile(r"^(?:🕒|🕚|⏰|🕝|🕓|🕑)\s*(.+)$"),
    ]
    venue_patterns = [
        re.compile(r"^(?:📍\s*)?Venue\s*[:：]\s*(.+)$", flags=re.IGNORECASE),
        re.compile(r"^📍\s*(.+)$"),
    ]

    # 1) Find any "Date:" line and record its index
    for i, ln in enumerate(lines):
        for dp in date_patterns:
            m = dp.match(ln)
            if m and date_obj is None:
                raw_date = m.group(1).strip()
                date_obj = parse_date_string(raw_date)
                if date_obj:
                    date_line_idx = i
                break
        if date_line_idx is not None:
            break

    # 2) If date_line_idx exists, pick title from the line above it
    if date_line_idx is not None and date_line_idx > 0:
        candidate = lines[date_line_idx - 1]
        clean_candidate = emoji_strip_pattern.sub("", candidate).strip()
        if (
            len(clean_candidate) > 3
            and not greeting_pattern.match(candidate)
            and not filler_pattern.match(candidate)
        ):
            title = clean_candidate

    # 3) If no title yet, look for "presents", "invite you to", etc.
    if not title:
        event_patterns = [
            re.compile(r"presents\s+(.+?)(?:\s+at|\s*!|\s*‼|\s*$)", flags=re.IGNORECASE),
            re.compile(r"invite you to\s+(.+?)(?:\s*!|\s*‼|\s*$)", flags=re.IGNORECASE),
            re.compile(r"Think you can\s+(.+?)\?", flags=re.IGNORECASE),
            re.compile(r"Get ready for\s+(.+?)(?:\s*!|\s*‼|\s*$)", flags=re.IGNORECASE),
            re.compile(r"Join us for\s+(.+?)(?:\s*!|\s*‼|\s*$)", flags=re.IGNORECASE),
            re.compile(r"presents:\s+(.+?)(?:\s+at|\s*!|\s*‼|\s*$)", flags=re.IGNORECASE),
        ]
        for ln in lines:
            for ep in event_patterns:
                m = ep.search(ln)
                if m:
                    title = m.group(1).strip()
                    title = re.sub(
                        r"\s+(challenge|competition|workshop|event)$",
                        r" \1",
                        title,
                        flags=re.IGNORECASE,
                    )
                    break
            if title:
                break

    # 4) If still no title, pick the first candidate under 60 chars
    if not title and candidates:
        for ln in candidates:
            if 3 <= len(ln) < 60:
                title = ln
                break

    # 5) Fallback: first non‐greeting line
    if not title:
        for ln in lines:
            clean_ln = emoji_strip_pattern.sub("", ln).strip()
            if clean_ln and len(clean_ln) > 3 and not greeting_pattern.match(ln):
                title = clean_ln
                break

    # 6) Gather time, venue, and description
    for i, ln in enumerate(lines):
        # skip the "title-above-date" line if used
        if date_line_idx is not None and i == date_line_idx - 1 and title == lines[i]:
            continue

        # a) Time
        for tp in time_patterns:
            m = tp.match(ln)
            if m and not event_time_str:
                times_text = m.group(1).strip()
                start_time = re.split(r"\s+to\s+|\s*-\s*", times_text, flags=re.IGNORECASE)[0].strip()
                event_time_str = start_time
                break
        if event_time_str:
            continue

        # b) Venue
        for vp in venue_patterns:
            m = vp.match(ln)
            if m and not location:
                location = m.group(1).strip()
                break
        if location:
            continue

        # c) Otherwise, add to description_parts (unless it's the title-above-date line)
        description_parts.append(ln)

    # 7) If no date was found, try a free-form regex
    if date_obj is None:
        date_obj = extract_date_from_text(caption_text)

    # 8) If no time found, try a free-form regex
    if not event_time_str:
        event_time_str = extract_time_from_text(caption_text)

    # 9) Combine date_obj + event_time_str
    datetime_obj = None
    if date_obj and event_time_str:
        datetime_obj = combine_date_time(date_obj, event_time_str)
    elif date_obj:
        # default to 10 AM
        datetime_obj = datetime.combine(date_obj, datetime.min.time().replace(hour=10))

    description = (
        " ".join(description_parts)
        if description_parts
        else (caption_text[:200] + "..." if len(caption_text) > 200 else caption_text)
    )

    return title or "Event", datetime_obj, location, description


def parse_date_string(date_str):
    """
    Try a variety of formats (e.g. '16th February 2024', '2nd March'), append current year if missing.
    """
    if not date_str:
        return None
    s = date_str.strip()
    if not re.search(r"\b\d{4}\b", s):
        s = f"{s} {datetime.now().year}"
    s = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", s)
    formats = [
        "%d %B %Y", "%d %B, %Y", "%d %b %Y", "%d %b, %Y",
        "%B %d %Y", "%B %d, %Y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def extract_date_from_text(text):
    """
    Regex match "16th February, 2024" or "2nd March" in free text.
    """
    pattern = re.compile(
        r"\b(\d{1,2}(?:st|nd|rd|th)?\s+"
        r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
        r"(?:,?\s*\d{4})?)\b",
        flags=re.IGNORECASE
    )
    m = pattern.search(text)
    if m:
        return parse_date_string(m.group(1))
    return None


def extract_time_from_text(text):
    """
    Regex match "10:30 AM", "14:00" etc. in free text.
    """
    patterns = [
        re.compile(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\s*(AM|PM)\b", flags=re.IGNORECASE),
        re.compile(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b"),
        re.compile(r"\b(1[0-2]|[1-9])\s*(AM|PM)\b", flags=re.IGNORECASE),
    ]
    for pat in patterns:
        m = pat.search(text)
        if m:
            return m.group(0)
    return ""


def combine_date_time(date_obj, time_str):
    """
    Combine date + time into a datetime. Default 10:00 AM if parsing fails.
    """
    tstr = time_str.strip()
    formats = ["%I:%M %p", "%H:%M", "%I %p", "%I.%M %p", "%H.%M"]
    for fmt in formats:
        try:
            t = datetime.strptime(tstr, fmt).time()
            return datetime.combine(date_obj, t)
        except ValueError:
            continue
    return datetime.combine(date_obj, datetime.min.time().replace(hour=10))


# ----------------------------------------------------------------------------
# 2) Fetch via i.instagram.com/api/v1/users/web_profile_info/
# ----------------------------------------------------------------------------

def fetch_posts_via_api(handle, sessionid, max_posts=MAX_POSTS_PER_PROFILE):
    """
    Use Instagram's `web_profile_info` endpoint to fetch up to `max_posts`
    recent posts for @handle. Requires a valid `sessionid` cookie.
    Returns a list of dicts: { 'shortcode','caption','timestamp','edge_liked_by','edge_media_to_comment' }.
    """
    url = f"https://i.instagram.com/api/v1/users/web_profile_info/?username={handle}"
    headers = {
        "User-Agent": "Instagram 280.0.0.15.127 Android",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "X-IG-App-ID": "936619743392459",
        "Connection": "keep-alive",
        "Cookie": f"sessionid={sessionid};"
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        print(f"    [DEBUG] @{handle} status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"    [DEBUG] Response content: {resp.text[:500]}")
        resp.raise_for_status()
        try:
            data = resp.json()
            print(f"    [DEBUG] JSON keys: {list(data.keys())}")
            print(f"    [DEBUG] JSON (truncated): {str(data)[:1000]}")
        except Exception as e:
            print(f"    [DEBUG] Could not parse JSON: {e}")
            print(f"    [DEBUG] Raw text: {resp.text[:1000]}")
            return []
    except Exception as e:
        print(f"    ❌ Failed to fetch JSON for @{handle}: {e}")
        return []

    try:
        edges = data["data"]["user"]["edge_owner_to_timeline_media"]["edges"]
    except KeyError:
        return []

    posts = []
    for edge in edges[:max_posts]:
        node = edge.get("node", {})
        caption = ""
        cap_edges = node.get("edge_media_to_caption", {}).get("edges", [])
        if cap_edges:
            caption = cap_edges[0].get("node", {}).get("text", "")

        posts.append({
            "shortcode": node.get("shortcode", ""),
            "caption": caption,
            "timestamp": node.get("taken_at_timestamp", 0),
            "likes": node.get("edge_liked_by", {}).get("count", 0),
            "comments": node.get("edge_media_to_comment", {}).get("count", 0),
        })
    return posts


def fetch_posts_via_html(handle, max_posts=MAX_POSTS_PER_PROFILE):
    """
    Scrape the public Instagram profile page and extract recent posts from embedded JSON.
    Returns a list of dicts: { 'shortcode','caption','timestamp','likes','comments' }.
    """
    url = f"https://www.instagram.com/{handle}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        html = resp.text
        # Find the script tag with window._sharedData or window.__additionalDataLoaded
        shared_data = None
        for line in html.splitlines():
            if 'window._sharedData' in line:
                json_str = line.split(' = ', 1)[1].rstrip(';')
                shared_data = json.loads(json_str)
                break
        if not shared_data:
            # Try to find window.__additionalDataLoaded
            soup = BeautifulSoup(html, 'html.parser')
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'window.__additionalDataLoaded' in script.string:
                    # Extract JSON from function call
                    start = script.string.find('{')
                    end = script.string.rfind('}') + 1
                    json_str = script.string[start:end]
                    shared_data = json.loads(json_str)
                    break
        if not shared_data:
            print(f"    [HTML SCRAPE] Could not find embedded JSON for @{handle}")
            return []
        # Try to extract posts from shared_data
        # The structure may vary, but usually:
        # shared_data['entry_data']['ProfilePage'][0]['graphql']['user']['edge_owner_to_timeline_media']['edges']
        try:
            edges = shared_data['entry_data']['ProfilePage'][0]['graphql']['user']['edge_owner_to_timeline_media']['edges']
        except Exception as e:
            print(f"    [HTML SCRAPE] Could not extract posts for @{handle}: {e}")
            return []
        posts = []
        for edge in edges[:max_posts]:
            node = edge.get('node', {})
            caption = ""
            cap_edges = node.get('edge_media_to_caption', {}).get('edges', [])
            if cap_edges:
                caption = cap_edges[0].get('node', {}).get('text', "")
            posts.append({
                "shortcode": node.get("shortcode", ""),
                "caption": caption,
                "timestamp": node.get("taken_at_timestamp", 0),
                "likes": node.get("edge_liked_by", {}).get("count", 0),
                "comments": node.get("edge_media_to_comment", {}).get("count", 0),
            })
        return posts
    except Exception as e:
        print(f"    [HTML SCRAPE] Failed for @{handle}: {e}")
        return []


def fetch_posts_via_playwright(handle, max_posts=3, browser=None, context=None):
    """
    Use Playwright to log in and scrape recent posts from a public Instagram profile.
    Returns a list of dicts: { 'shortcode','caption','timestamp','likes','comments' }.
    """
    from playwright.sync_api import sync_playwright
    posts = []
    try:
        if browser is None or context is None:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()
                # Prompt for credentials
                print("\n[Playwright] Instagram login required.")
                username = input("Instagram username: ").strip()
                password = getpass.getpass("Instagram password (input hidden): ")
                page.goto("https://www.instagram.com/accounts/login/")
                page.wait_for_selector("input[name='username']")
                page.fill("input[name='username']", username)
                page.fill("input[name='password']", password)
                page.click("button[type='submit']")
                page.wait_for_timeout(5000)
                # Check for login success
                if "challenge" in page.url or "two_factor" in page.url:
                    print("[Playwright] Login challenge or 2FA detected. Please complete it in the browser window.")
                    page.wait_for_timeout(20000)
                # Now scrape the handle
                posts = fetch_posts_via_playwright(handle, max_posts, browser, context)
                browser.close()
                return posts
        # Use provided browser/context
        page = context.new_page()
        url = f"https://www.instagram.com/{handle}/"
        page.goto(url)
        page.wait_for_selector("article")
        # Get post links
        post_links = page.query_selector_all("article a")
        shortcodes = []
        for link in post_links:
            href = link.get_attribute("href")
            if href and href.startswith("/p/"):
                shortcode = href.split("/p/")[1].split("/")[0]
                if shortcode not in shortcodes:
                    shortcodes.append(shortcode)
            if len(shortcodes) >= max_posts:
                break
        for shortcode in shortcodes:
            post_url = f"https://www.instagram.com/p/{shortcode}/"
            page.goto(post_url)
            page.wait_for_selector("time")
            # Extract caption
            try:
                caption_elem = page.query_selector("article div[role='presentation'] span")
                caption = caption_elem.inner_text() if caption_elem else ""
            except Exception:
                caption = ""
            # Extract timestamp
            try:
                time_elem = page.query_selector("time")
                timestamp = int(time_elem.get_attribute("datetime")[:19].replace('T', '').replace('-', '').replace(':', ''))
                # Instagram time is ISO 8601, but for your pipeline, use unix timestamp
                timestamp = int(time_elem.get_attribute("datetime"))
            except Exception:
                timestamp = 0
            # Likes/comments are harder to get reliably, so set to 0 for now
            posts.append({
                "shortcode": shortcode,
                "caption": caption,
                "timestamp": timestamp,
                "likes": 0,
                "comments": 0,
            })
        page.close()
        return posts
    except Exception as e:
        print(f"    [Playwright] Failed for @{handle}: {e}")
        return []


# ----------------------------------------------------------------------------
# 3) Ingestion Routine
# ----------------------------------------------------------------------------

def ingest_from_instagram():
    """
    1) Prompt for sessionid.  
    2) init_db() → create tables if needed.  
    3) For each handle, call fetch_posts_via_api(…) → parse captions → insert into raw_events.
    """
    # print("\nEnter your Instagram `sessionid` (copy from your browser's cookies):")
    # sessionid = input().strip()
    # if not sessionid:
    #     print("❌ No sessionid provided. Exiting.")
    #     return
    sessionid = ""  # Always blank, skip API

    print("\n[Ingestor] Initializing database…")
    init_db()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS raw_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT   NOT NULL,
            datetime    TEXT   NOT NULL,
            location    TEXT,
            description TEXT,
            source      TEXT   NOT NULL,
            created_at  TEXT   DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(title, datetime, source)
        );
    """)
    conn.commit()

    total_inserted = 0
    total_processed = 0

    for idx, handle in enumerate(INSTAGRAM_HANDLES):
        print(f"\n[Ingestor] Scraping @{handle} …")
        posts = fetch_posts_via_api(handle, sessionid, max_posts=MAX_POSTS_PER_PROFILE)
        if not posts:
            print(f"    – No posts returned for @{handle} via API, trying HTML scrape…")
            posts = fetch_posts_via_html(handle, max_posts=MAX_POSTS_PER_PROFILE)
        if not posts:
            print(f"    – No posts returned for @{handle} via HTML, trying Playwright browser automation…")
            posts = fetch_posts_via_playwright(handle, max_posts=MAX_POSTS_PER_PROFILE)
        if not posts:
            print(f"    – No posts returned for @{handle}")
        handle_inserted = 0
        handle_processed = 0
        for post in posts:
            handle_processed += 1
            total_processed  += 1
            caption = post.get("caption", "") or ""
            if len(caption.strip()) < 20:
                # skip very short captions
                continue
            title, dt_obj, location, description = parse_caption(caption)
            if not title or not dt_obj:
                print(f"    ❌ Skipped (no title/date): '{caption[:30]}…'")
                continue
            # skip if older than 2 years
            if dt_obj.date() < (datetime.now().date() - timedelta(days=730)):
                continue
            dt_iso = dt_obj.isoformat()
            try:
                c.execute(
                    """
                    INSERT OR IGNORE INTO raw_events
                      (title, datetime, location, description, source)
                    VALUES (?, ?, ?, ?, ?);
                    """,
                    (title, dt_iso, location, description, handle)
                )
                if c.rowcount > 0:
                    handle_inserted += 1
                    total_inserted += 1
                    print(f"    ✓ Inserted: '{title}' @ {dt_iso}")
                    # Insert notification for new future event
                    event_date = dt_obj.date()
                    if event_date >= datetime.now().date():
                        notif_title = f"New Event: {title}"
                        notif_body = f"Don't miss '{title}' on {dt_iso} at {location or 'TBA'}!"
                        try:
                            c.execute(
                                """
                                INSERT INTO notifications (title, body) VALUES (?, ?)
                                """,
                                (notif_title, notif_body)
                            )
                            conn.commit()
                        except Exception as ne:
                            print(f"    [Notification] Failed to insert notification: {ne}")
                else:
                    print(f"    – Duplicate: '{title}' @ {dt_iso}")
                conn.commit()
            except sqlite3.Error as e:
                print(f"    ❌ DB error inserting '{title}': {e}")
            time.sleep(random.uniform(1, 2))
        print(f"    → Done @{handle}: Processed {handle_processed}, Inserted {handle_inserted}")
        if idx < len(INSTAGRAM_HANDLES) - 1:
            time.sleep(DELAY_BETWEEN_PROFILES)
    conn.close()
    print(f"\n[Ingestor] Completed: Processed {total_processed} posts, Inserted {total_inserted} events.\n")


# ----------------------------------------------------------------------------
# 4) Entry Point
# ----------------------------------------------------------------------------

if __name__ == "__main__":
    print("Instagram Event Ingestor (via web_profile_info, requires sessionid)\n")
    ingest_from_instagram()
    print("Done.\n")
