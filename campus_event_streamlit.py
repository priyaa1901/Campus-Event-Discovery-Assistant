import streamlit as st
import sqlite3
import pandas as pd
from streamlit.components.v1 import html

# Connect to your events database
conn = sqlite3.connect('events.db')
df = pd.read_sql_query("SELECT * FROM events", conn)

# Query to get the count of notifications using the created_at column
notifications_count_query = "SELECT COUNT(*) FROM notifications WHERE created_at > ?"
today = pd.to_datetime("today").date()
notifications_count = pd.read_sql_query(notifications_count_query, conn, params=(today,)).iloc[0, 0]

st.set_page_config(page_title="Campus Event Discovery", layout="wide")

st.title("🎉 Campus Event Discovery Assistant")

# Filter bar
col1, col2, col3 = st.columns([2,2,2])

with col1:
    category = st.selectbox("Category", ["All"] + sorted(df['category'].dropna().unique().tolist()))
with col2:
    date = st.date_input("Date (show events on or after)", pd.to_datetime("today"))
with col3:
    keyword = st.text_input("Keyword search")

# Filtering logic
filtered = df.copy()
if category != "All":
    filtered = filtered[filtered['category'] == category]
if keyword:
    filtered = filtered[filtered['title'].str.contains(keyword, case=False, na=False) | 
                        filtered['description'].str.contains(keyword, case=False, na=False)]
if date:
    filtered = filtered[pd.to_datetime(filtered['datetime']).dt.date >= date]

# Show events
if filtered.empty:
    st.warning("No events found for your filters.")
else:
    for idx, row in filtered.iterrows():
        with st.container():
            st.markdown(f"### {row['title']}")
            st.markdown(f"**Date:** {row['datetime']}  |  **Location:** {row['location'] or 'TBA'}")
            st.markdown(f"**Category:** {row.get('category', 'Other')}")
            st.markdown(f"**Source:** {row.get('sources', row.get('source', ''))}")
            st.markdown(row['description'])
            st.markdown("---")

# Add a bell icon for notifications
st.markdown("<h3>Notifications</h3>", unsafe_allow_html=True)

# Bell icon HTML with dynamic notification count
bell_icon = f"""
<div style="position: relative; display: inline-block;">
    <button style="background: none; border: none; cursor: pointer;">
        <img src="https://img.icons8.com/ios-filled/50/000000/bell.png" width="30" height="30"/>
    </button>
    <span style="position: absolute; top: -10px; right: -10px; background-color: red; color: white; border-radius: 50%; padding: 5px; font-size: 12px;">
        {notifications_count}
    </span>
</div>
"""

# Render the bell icon
html(bell_icon)

st.caption("© 2025 Campus Event Discovery • All Rights Reserved")
