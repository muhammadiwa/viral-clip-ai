#!/usr/bin/env python3
"""
Script to force clean ALL video data without confirmation.
WARNING: This will delete all videos, clips, transcripts, etc.
"""

import sys
import os

# Add backend directory to path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)
os.chdir(backend_dir)

from sqlalchemy.orm import Session
from app.database import get_db
from app.models import (
    VideoSource, ClipBatch, Clip, ProcessingJob, 
    TranscriptSegment, VideoAnalysis, SegmentAnalysis,
    SubtitleSegment, Notification
)

def force_clean_all():
    """Force clean all video-related data from database."""
    db = next(get_db())
    
    try:
        print("🧹 Force cleaning all video data...")
        
        # Count before deletion
        video_count = db.query(VideoSource).count()
        batch_count = db.query(ClipBatch).count()
        clip_count = db.query(Clip).count()
        job_count = db.query(ProcessingJob).count()
        transcript_count = db.query(TranscriptSegment).count()
        analysis_count = db.query(VideoAnalysis).count()
        segment_analysis_count = db.query(SegmentAnalysis).count()
        subtitle_count = db.query(SubtitleSegment).count()
        
        print(f"Found:")
        print(f"  - {video_count} videos")
        print(f"  - {batch_count} clip batches")
        print(f"  - {clip_count} clips")
        print(f"  - {job_count} processing jobs")
        print(f"  - {transcript_count} transcript segments")
        print(f"  - {analysis_count} video analyses")
        print(f"  - {segment_analysis_count} segment analyses")
        print(f"  - {subtitle_count} subtitle segments")
        
        if video_count == 0:
            print("\n✅ No data to clean - database is already empty!")
            return True
        
        print("\nDeleting data...")
        
        # Delete in correct order (foreign key constraints)
        if subtitle_count > 0:
            db.query(SubtitleSegment).delete()
            print(f"  ✅ Deleted {subtitle_count} subtitle segments")
        
        if clip_count > 0:
            db.query(Clip).delete()
            print(f"  ✅ Deleted {clip_count} clips")
        
        if batch_count > 0:
            db.query(ClipBatch).delete()
            print(f"  ✅ Deleted {batch_count} clip batches")
        
        if job_count > 0:
            db.query(ProcessingJob).delete()
            print(f"  ✅ Deleted {job_count} processing jobs")
        
        if transcript_count > 0:
            db.query(TranscriptSegment).delete()
            print(f"  ✅ Deleted {transcript_count} transcript segments")
        
        if segment_analysis_count > 0:
            db.query(SegmentAnalysis).delete()
            print(f"  ✅ Deleted {segment_analysis_count} segment analyses")
        
        if analysis_count > 0:
            db.query(VideoAnalysis).delete()
            print(f"  ✅ Deleted {analysis_count} video analyses")
        
        # Clean video-related notifications
        notification_count = db.query(Notification).filter(
            Notification.data.like('%video_id%')
        ).count()
        if notification_count > 0:
            db.query(Notification).filter(
                Notification.data.like('%video_id%')
            ).delete(synchronize_session=False)
            print(f"  ✅ Deleted {notification_count} video notifications")
        
        if video_count > 0:
            db.query(VideoSource).delete()
            print(f"  ✅ Deleted {video_count} videos")
        
        db.commit()
        print("\n🎉 All video data cleaned successfully!")
        return True
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error cleaning data: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    force_clean_all()
