#!/usr/bin/env python3
"""Debug script to analyze subtitle data for duplicate issues."""

import sqlite3
import os
import sys

# Get database path
db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.db")

if not os.path.exists(db_path):
    print(f"Database not found: {db_path}")
    sys.exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()


def analyze_clip_subtitles(clip_id: int):
    """Analyze subtitles for a specific clip."""
    # Get clip info
    cursor.execute("""
        SELECT c.id, c.title, c.start_time_sec, c.end_time_sec, c.duration_sec, cb.video_source_id
        FROM clips c
        JOIN clip_batches cb ON c.clip_batch_id = cb.id
        WHERE c.id = ?
    """, (clip_id,))
    clip = cursor.fetchone()
    
    if not clip:
        print(f"Clip {clip_id} not found")
        return
    
    print(f"\n{'='*60}")
    print(f"CLIP {clip['id']}: {clip['title']}")
    print(f"Time: {clip['start_time_sec']:.2f}s - {clip['end_time_sec']:.2f}s (duration: {clip['duration_sec']:.2f}s)")
    print(f"Video Source ID: {clip['video_source_id']}")
    print(f"{'='*60}")
    
    # Get subtitle segments
    cursor.execute("""
        SELECT id, start_time_sec, end_time_sec, text, words_json
        FROM subtitle_segments
        WHERE clip_id = ?
        ORDER BY start_time_sec
    """, (clip_id,))
    subs = cursor.fetchall()
    
    print(f"\nSubtitle Segments ({len(subs)} total):")
    print("-" * 60)
    
    prev_text = None
    prev_end = None
    duplicates = []
    overlaps = []
    
    for i, sub in enumerate(subs):
        text = sub['text']
        
        # Check for duplicate text
        is_duplicate = text == prev_text
        if is_duplicate:
            duplicates.append((i, sub))
        
        # Check for overlapping times
        is_overlap = prev_end is not None and sub['start_time_sec'] < prev_end
        if is_overlap:
            overlaps.append((i, sub, prev_end))
        
        # Relative time (to clip start)
        rel_start = sub['start_time_sec'] - clip['start_time_sec']
        rel_end = sub['end_time_sec'] - clip['start_time_sec']
        
        status = ""
        if is_duplicate:
            status = " [DUPLICATE TEXT]"
        if is_overlap:
            status += " [OVERLAP]"
        
        print(f"  [{i+1}] {sub['start_time_sec']:.2f}s - {sub['end_time_sec']:.2f}s (rel: {rel_start:.2f}s - {rel_end:.2f}s)")
        text_preview = text[:80] + '...' if len(text) > 80 else text
        print(f"      Text: {text_preview}{status}")
        
        if sub['words_json']:
            import json
            try:
                words = json.loads(sub['words_json']) if isinstance(sub['words_json'], str) else sub['words_json']
                print(f"      Words: {len(words)} word timestamps")
            except:
                pass
        
        prev_text = text
        prev_end = sub['end_time_sec']
    
    if duplicates:
        print(f"\n⚠️  Found {len(duplicates)} DUPLICATE TEXT entries!")
    if overlaps:
        print(f"\n⚠️  Found {len(overlaps)} OVERLAPPING time entries!")
    
    # Also check source transcript segments
    print(f"\n\nSource Transcript Segments (overlapping with clip):")
    print("-" * 60)
    
    cursor.execute("""
        SELECT id, start_time_sec, end_time_sec, text
        FROM transcript_segments
        WHERE video_source_id = ?
          AND start_time_sec < ?
          AND end_time_sec > ?
        ORDER BY start_time_sec
    """, (clip['video_source_id'], clip['end_time_sec'], clip['start_time_sec']))
    
    transcript_segments = cursor.fetchall()
    print(f"Found {len(transcript_segments)} transcript segments")
    
    prev_text = None
    for i, seg in enumerate(transcript_segments):
        is_dup = seg['text'] == prev_text
        dup_marker = " [DUP]" if is_dup else ""
        print(f"  [{i+1}] {seg['start_time_sec']:.2f}s - {seg['end_time_sec']:.2f}s{dup_marker}")
        text_preview = seg['text'][:80] + '...' if len(seg['text']) > 80 else seg['text']
        print(f"      {text_preview}")
        prev_text = seg['text']


def analyze_all_clips(video_id: int = None, limit: int = 5):
    """Analyze subtitles for all clips or clips from a specific video."""
    if video_id:
        cursor.execute("""
            SELECT c.id FROM clips c
            JOIN clip_batches cb ON c.clip_batch_id = cb.id
            WHERE cb.video_source_id = ?
            ORDER BY c.id DESC
            LIMIT ?
        """, (video_id, limit))
    else:
        cursor.execute("""
            SELECT id FROM clips
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
    
    clips = cursor.fetchall()
    
    print(f"Analyzing {len(clips)} clips...")
    
    for clip in clips:
        analyze_clip_subtitles(clip['id'])


def list_clips():
    """List all clips with subtitle counts."""
    cursor.execute("""
        SELECT c.id, c.title, c.start_time_sec, c.end_time_sec,
               (SELECT COUNT(*) FROM subtitle_segments WHERE clip_id = c.id) as sub_count
        FROM clips c
        ORDER BY c.id DESC
        LIMIT 20
    """)
    clips = cursor.fetchall()
    
    print(f"\nRecent Clips ({len(clips)}):")
    print("-" * 80)
    for clip in clips:
        title = clip['title'][:40] if clip['title'] else "Untitled"
        print(f"  ID: {clip['id']:3d} | {title:40s} | {clip['start_time_sec']:.1f}s-{clip['end_time_sec']:.1f}s | Subs: {clip['sub_count']}")


def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == "all":
            video_id = int(sys.argv[2]) if len(sys.argv) > 2 else None
            limit = int(sys.argv[3]) if len(sys.argv) > 3 else 5
            analyze_all_clips(video_id, limit)
        elif sys.argv[1] == "list":
            list_clips()
        else:
            clip_id = int(sys.argv[1])
            analyze_clip_subtitles(clip_id)
    else:
        print("Usage:")
        print("  python scripts/debug_subtitles.py <clip_id>")
        print("  python scripts/debug_subtitles.py all [video_id] [limit]")
        print("  python scripts/debug_subtitles.py list")
        print("\nExamples:")
        print("  python scripts/debug_subtitles.py 5")
        print("  python scripts/debug_subtitles.py all")
        print("  python scripts/debug_subtitles.py all 1 10")
        print("  python scripts/debug_subtitles.py list")


if __name__ == "__main__":
    main()
    conn.close()
