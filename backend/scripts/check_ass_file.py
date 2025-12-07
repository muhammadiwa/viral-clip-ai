#!/usr/bin/env python3
"""Check ASS subtitle file for duplicates."""

import sys
import os
from pathlib import Path

def analyze_ass_file(ass_path: str):
    """Analyze ASS file for duplicate events."""
    if not os.path.exists(ass_path):
        print(f"File not found: {ass_path}")
        return
    
    with open(ass_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f"Analyzing: {ass_path}")
    print("=" * 60)
    
    # Find events section
    if "[Events]" not in content:
        print("No [Events] section found")
        return
    
    events_section = content.split("[Events]")[1]
    lines = events_section.strip().split("\n")
    
    # Skip format line
    events = [l for l in lines if l.startswith("Dialogue:")]
    
    print(f"Total events: {len(events)}")
    print("-" * 60)
    
    # Parse events
    prev_text = None
    prev_time = None
    duplicates = []
    overlaps = []
    
    for i, event in enumerate(events):
        # Parse: Dialogue: 0,0:00:00.00,0:00:01.00,Default,,0,0,0,,Text
        parts = event.split(",", 9)
        if len(parts) < 10:
            continue
        
        start_time = parts[1]
        end_time = parts[2]
        text = parts[9] if len(parts) > 9 else ""
        
        # Remove ASS formatting tags for comparison
        import re
        clean_text = re.sub(r'\{[^}]*\}', '', text).strip()
        
        # Check for duplicate text
        if clean_text == prev_text:
            duplicates.append((i, start_time, end_time, clean_text[:50]))
        
        # Check for overlapping times (simplified)
        if prev_time and start_time < prev_time:
            overlaps.append((i, start_time, prev_time))
        
        print(f"[{i+1}] {start_time} - {end_time}")
        print(f"    {clean_text[:80]}{'...' if len(clean_text) > 80 else ''}")
        
        prev_text = clean_text
        prev_time = end_time
    
    print("-" * 60)
    if duplicates:
        print(f"\n⚠️  Found {len(duplicates)} events with DUPLICATE TEXT:")
        for idx, start, end, text in duplicates[:10]:
            print(f"  Event {idx}: {start}-{end} '{text}'")
    
    if overlaps:
        print(f"\n⚠️  Found {len(overlaps)} OVERLAPPING events")


def find_recent_ass_files(media_root: str = "media"):
    """Find recent ASS files in media directory."""
    ass_files = []
    for root, dirs, files in os.walk(media_root):
        for f in files:
            if f.endswith('.ass'):
                path = os.path.join(root, f)
                mtime = os.path.getmtime(path)
                ass_files.append((path, mtime))
    
    # Sort by modification time (newest first)
    ass_files.sort(key=lambda x: x[1], reverse=True)
    return [f[0] for f in ass_files[:10]]


def main():
    if len(sys.argv) > 1:
        ass_path = sys.argv[1]
        analyze_ass_file(ass_path)
    else:
        print("Looking for recent ASS files...")
        ass_files = find_recent_ass_files()
        
        if not ass_files:
            print("No ASS files found in media directory")
            print("\nUsage: python scripts/check_ass_file.py <path_to_ass_file>")
            return
        
        print(f"Found {len(ass_files)} ASS files:")
        for i, f in enumerate(ass_files):
            print(f"  [{i+1}] {f}")
        
        print("\nAnalyzing most recent file...")
        analyze_ass_file(ass_files[0])


if __name__ == "__main__":
    main()
