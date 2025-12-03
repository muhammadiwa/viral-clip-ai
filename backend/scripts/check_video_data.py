"""
Check video data script.
Run with: python -m scripts.check_video_data
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.models import VideoSource, TranscriptSegment, ClipBatch, Clip


def check_video_data():
    db = SessionLocal()
    try:
        # Get all videos
        videos = db.query(VideoSource).all()
        
        print(f"\n📹 Found {len(videos)} video(s):\n")
        
        for v in videos:
            print(f"Video ID {v.id}: {v.title}")
            print(f"  Status: {v.status}")
            print(f"  Duration: {v.duration_seconds}s")
            print(f"  File: {v.file_path}")
            
            # Check transcripts
            transcripts = db.query(TranscriptSegment).filter(
                TranscriptSegment.video_source_id == v.id
            ).all()
            print(f"  Transcripts: {len(transcripts)} segments")
            
            # Check batches
            batches = db.query(ClipBatch).filter(
                ClipBatch.video_source_id == v.id
            ).all()
            print(f"  Batches: {len(batches)}")
            
            for b in batches:
                clips = db.query(Clip).filter(Clip.clip_batch_id == b.id).all()
                print(f"    - Batch {b.id} ({b.name}): {b.status}, {len(clips)} clips")
            
            print()
        
    finally:
        db.close()


if __name__ == "__main__":
    check_video_data()
