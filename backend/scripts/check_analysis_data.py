"""
Script to check analysis tables data status.

Run with:
  cd backend
  python -m scripts.check_analysis_data
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.models import VideoSource, VideoAnalysis, TranscriptSegment, Clip
from app.models.analysis import SegmentAnalysis, ClipAnalysis


def check_analysis_data():
    db = SessionLocal()
    try:
        # Count records
        videos = db.query(VideoSource).count()
        video_analyses = db.query(VideoAnalysis).count()
        transcript_segments = db.query(TranscriptSegment).count()
        segment_analyses = db.query(SegmentAnalysis).count()
        clips = db.query(Clip).count()
        clip_analyses = db.query(ClipAnalysis).count()
        
        print("=" * 60)
        print("ANALYSIS TABLES STATUS")
        print("=" * 60)
        
        print(f"\n📹 Videos: {videos}")
        print(f"   └─ VideoAnalysis records: {video_analyses}")
        if videos > 0:
            coverage = (video_analyses / videos) * 100
            print(f"   └─ Coverage: {coverage:.1f}%")
        
        print(f"\n📝 TranscriptSegments: {transcript_segments}")
        print(f"   └─ SegmentAnalysis records: {segment_analyses}")
        if transcript_segments > 0:
            coverage = (segment_analyses / transcript_segments) * 100
            print(f"   └─ Coverage: {coverage:.1f}%")
        
        print(f"\n🎬 Clips: {clips}")
        print(f"   └─ ClipAnalysis records: {clip_analyses}")
        if clips > 0:
            coverage = (clip_analyses / clips) * 100
            print(f"   └─ Coverage: {coverage:.1f}%")
        
        # Check VideoAnalysis details
        print("\n" + "=" * 60)
        print("VIDEO ANALYSIS DETAILS")
        print("=" * 60)
        
        va_records = db.query(VideoAnalysis).all()
        for va in va_records:
            video = db.query(VideoSource).filter(VideoSource.id == va.video_source_id).first()
            print(f"\n📊 VideoAnalysis #{va.id} for Video #{va.video_source_id}")
            print(f"   Title: {video.title if video else 'N/A'}")
            print(f"   Version: {va.analysis_version}")
            print(f"   Duration: {va.duration_analyzed:.1f}s" if va.duration_analyzed else "   Duration: N/A")
            print(f"   Avg Audio Energy: {va.avg_audio_energy:.2f}" if va.avg_audio_energy else "   Avg Audio Energy: N/A")
            print(f"   Avg Visual Interest: {va.avg_visual_interest:.2f}" if va.avg_visual_interest else "   Avg Visual Interest: N/A")
            print(f"   Audio Peaks: {va.audio_peaks_count}")
            print(f"   Visual Peaks: {va.visual_peaks_count}")
            print(f"   Viral Moments: {va.viral_moments_count}")
            
            # Check JSON data
            has_audio_timeline = bool(va.audio_timeline_json)
            has_visual_timeline = bool(va.visual_timeline_json)
            has_combined_timeline = bool(va.combined_timeline_json)
            print(f"   Has Audio Timeline: {'✅' if has_audio_timeline else '❌'}")
            print(f"   Has Visual Timeline: {'✅' if has_visual_timeline else '❌'}")
            print(f"   Has Combined Timeline: {'✅' if has_combined_timeline else '❌'}")
        
        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY & RECOMMENDATIONS")
        print("=" * 60)
        
        issues = []
        
        if video_analyses < videos:
            issues.append(f"⚠️  {videos - video_analyses} videos missing VideoAnalysis")
        
        if segment_analyses == 0 and transcript_segments > 0:
            issues.append("⚠️  SegmentAnalysis table is EMPTY - not being populated")
        
        if clip_analyses == 0 and clips > 0:
            issues.append("⚠️  ClipAnalysis table is EMPTY - not being populated")
        
        if issues:
            print("\nISSUES FOUND:")
            for issue in issues:
                print(f"  {issue}")
        else:
            print("\n✅ All analysis tables are properly populated!")
        
    finally:
        db.close()


if __name__ == "__main__":
    check_analysis_data()
