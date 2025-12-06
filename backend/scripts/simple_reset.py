#!/usr/bin/env python3
"""Simple reset script using direct SQLite connection."""

import sqlite3
import os

# Get database path
db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.db")
print(f"Database: {db_path}")

if not os.path.exists(db_path):
    print("Database file not found!")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get counts
tables = [
    ("subtitle_segments", "Subtitle segments"),
    ("clips", "Clips"),
    ("clip_batches", "Clip batches"),
    ("processing_jobs", "Processing jobs"),
    ("transcript_segments", "Transcript segments"),
    ("segment_analyses", "Segment analyses"),
    ("video_analyses", "Video analyses"),
    ("video_sources", "Videos"),
]

print("\nCurrent data:")
for table, name in tables:
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  {name}: {count}")
    except sqlite3.OperationalError as e:
        print(f"  {name}: table not found ({e})")

print("\nDeleting all video data...")

# Delete in order (foreign key constraints)
delete_order = [
    "subtitle_segments",
    "clips", 
    "clip_batches",
    "processing_jobs",
    "transcript_segments",
    "segment_analyses",
    "video_analyses",
    "video_sources",
]

for table in delete_order:
    try:
        cursor.execute(f"DELETE FROM {table}")
        deleted = cursor.rowcount
        if deleted > 0:
            print(f"  Deleted {deleted} from {table}")
    except sqlite3.OperationalError as e:
        print(f"  Skipped {table}: {e}")

# Also clean notifications with video_id
try:
    cursor.execute("DELETE FROM notifications WHERE data LIKE '%video_id%'")
    deleted = cursor.rowcount
    if deleted > 0:
        print(f"  Deleted {deleted} video notifications")
except sqlite3.OperationalError:
    pass

conn.commit()
conn.close()

print("\n✅ All video data cleaned!")
print("\nNext steps:")
print("1. Restart backend server")
print("2. Restart worker")
print("3. Test with a new YouTube URL")
