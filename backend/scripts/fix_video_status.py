"""
Fix video status script.
Run with: python -m scripts.fix_video_status
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.models import VideoSource


def fix_video_status():
    db = SessionLocal()
    try:
        # Find videos stuck in processing/pending
        stuck_videos = db.query(VideoSource).filter(
            VideoSource.status.in_(["processing", "pending"])
        ).all()
        
        if not stuck_videos:
            print("✅ No stuck videos found. All videos have valid status.")
            return
        
        print(f"Found {len(stuck_videos)} stuck video(s):")
        for v in stuck_videos:
            print(f"  - ID {v.id}: {v.title} (status: {v.status})")
        
        # Update to analyzed
        for v in stuck_videos:
            v.status = "analyzed"
        
        db.commit()
        print(f"\n✅ Updated {len(stuck_videos)} video(s) to 'analyzed' status")
        
    finally:
        db.close()


if __name__ == "__main__":
    fix_video_status()
