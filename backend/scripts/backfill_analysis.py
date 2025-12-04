"""
Script to backfill analysis tables for existing videos, segments, and clips.

Run with:
  cd backend
  python -m scripts.backfill_analysis
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.models import VideoSource, TranscriptSegment, Clip, VideoAnalysis
from app.models.analysis import SegmentAnalysis, ClipAnalysis
from app.services import sentiment_analysis, segmentation, utils
from app.core.config import get_settings

settings = get_settings()


def backfill_video_analyses(db):
    """Backfill VideoAnalysis for videos that don't have it."""
    print("\n📹 Backfilling VideoAnalysis...")
    
    videos = db.query(VideoSource).all()
    created = 0
    
    for video in videos:
        # Check if already exists
        existing = db.query(VideoAnalysis).filter(
            VideoAnalysis.video_source_id == video.id
        ).first()
        
        if existing:
            print(f"   ✓ Video #{video.id} already has analysis")
            continue
        
        if not video.file_path or not os.path.exists(video.file_path):
            print(f"   ⚠ Video #{video.id} - file not found: {video.file_path}")
            continue
        
        print(f"   → Analyzing Video #{video.id}: {video.title}")
        
        try:
            duration = video.duration_seconds or utils.probe_duration(video.file_path) or 0.0
            
            # Get transcript segments
            segments = db.query(TranscriptSegment).filter(
                TranscriptSegment.video_source_id == video.id
            ).order_by(TranscriptSegment.start_time_sec).all()
            
            # Perform analysis
            analysis_data = segmentation.analyze_video_comprehensive(
                video.file_path, duration, segments
            )
            
            # Save to database
            video_analysis = VideoAnalysis(
                video_source_id=video.id,
                analysis_version="v2",
                duration_analyzed=duration,
                avg_audio_energy=analysis_data.get("avg_audio_energy", 0.5),
                avg_visual_interest=analysis_data.get("avg_visual_interest", 0.5),
                avg_engagement=analysis_data.get("avg_engagement", 0.5),
                audio_peaks_count=len(analysis_data.get("audio_peaks", [])),
                visual_peaks_count=len(analysis_data.get("visual_peaks", [])),
                viral_moments_count=len(analysis_data.get("viral_moments", [])),
                audio_timeline_json=analysis_data.get("audio_timeline"),
                visual_timeline_json=analysis_data.get("visual_timeline"),
                combined_timeline_json=analysis_data.get("combined_timeline"),
                audio_peaks_json=analysis_data.get("audio_peaks"),
                visual_peaks_json=analysis_data.get("visual_peaks"),
                engagement_peaks_json=analysis_data.get("viral_moments"),
            )
            db.add(video_analysis)
            db.commit()
            created += 1
            print(f"   ✅ Created VideoAnalysis for Video #{video.id}")
            
        except Exception as e:
            print(f"   ❌ Error analyzing Video #{video.id}: {e}")
            db.rollback()
    
    print(f"\n   Total VideoAnalysis created: {created}")


def backfill_segment_analyses(db):
    """Backfill SegmentAnalysis for transcript segments."""
    print("\n📝 Backfilling SegmentAnalysis...")
    
    segments = db.query(TranscriptSegment).all()
    created = 0
    skipped = 0
    
    for seg in segments:
        # Check if already exists
        existing = db.query(SegmentAnalysis).filter(
            SegmentAnalysis.transcript_segment_id == seg.id
        ).first()
        
        if existing:
            skipped += 1
            continue
        
        try:
            # Analyze segment
            analysis = sentiment_analysis.analyze_segment(seg)
            
            segment_analysis = SegmentAnalysis(
                transcript_segment_id=seg.id,
                sentiment_score=analysis["sentiment"]["sentiment"],
                sentiment_intensity=analysis["sentiment"]["intensity"],
                emotion=analysis["sentiment"]["emotion"],
                hook_word_count=analysis["hooks"]["total_count"],
                hook_words_found=analysis["hooks"]["found_words"],
                hook_score=analysis["hooks"]["hook_score"],
                has_question=analysis["questions"]["has_question"],
                has_cta=analysis["cta"]["has_cta"],
                viral_potential=analysis["viral_potential"],
            )
            db.add(segment_analysis)
            created += 1
            
            # Commit in batches
            if created % 100 == 0:
                db.commit()
                print(f"   → Processed {created + skipped} segments...")
                
        except Exception as e:
            print(f"   ❌ Error analyzing segment #{seg.id}: {e}")
    
    db.commit()
    print(f"\n   Total SegmentAnalysis created: {created}, skipped: {skipped}")


def backfill_clip_analyses(db):
    """Backfill ClipAnalysis for existing clips."""
    print("\n🎬 Backfilling ClipAnalysis...")
    
    clips = db.query(Clip).all()
    created = 0
    skipped = 0
    
    for clip in clips:
        # Check if already exists
        existing = db.query(ClipAnalysis).filter(
            ClipAnalysis.clip_id == clip.id
        ).first()
        
        if existing:
            skipped += 1
            continue
        
        try:
            # Get video analysis for timeline data
            batch = clip.clip_batch
            if not batch:
                continue
                
            video_analysis = db.query(VideoAnalysis).filter(
                VideoAnalysis.video_source_id == batch.video_source_id
            ).first()
            
            timeline_data = []
            if video_analysis and video_analysis.combined_timeline_json:
                timeline_data = [
                    t for t in video_analysis.combined_timeline_json
                    if clip.start_time_sec <= t.get("time", 0) < clip.end_time_sec
                ]
            
            # Calculate scores from timeline or use defaults
            def avg_from_timeline(key, default=0.5):
                if not timeline_data:
                    return default
                values = [t.get(key, default) for t in timeline_data]
                return sum(values) / len(values) if values else default
            
            audio_energy = avg_from_timeline("audio_energy")
            audio_excitement = avg_from_timeline("audio_excitement")
            visual_interest = avg_from_timeline("visual_interest")
            motion = avg_from_timeline("motion")
            face_likelihood = avg_from_timeline("face_likelihood")
            
            # Calculate data-driven score
            data_score = (
                audio_energy * 2.0 +
                audio_excitement * 2.0 +
                visual_interest * 2.0 +
                motion * 1.5 +
                face_likelihood * 1.5
            )
            
            # Grade to score helper
            def grade_to_score(grade):
                return {"A": 9.0, "B": 7.0, "C": 5.0, "D": 3.0}.get(grade, 5.0)
            
            # Determine strengths and weaknesses
            strengths = []
            weaknesses = []
            
            if audio_energy > 0.6:
                strengths.append("High audio energy")
            elif audio_energy < 0.3:
                weaknesses.append("Low audio energy")
            
            if visual_interest > 0.6:
                strengths.append("Visually interesting")
            elif visual_interest < 0.3:
                weaknesses.append("Low visual interest")
            
            if clip.grade_hook in ["A", "B"]:
                strengths.append(f"Strong hook (Grade {clip.grade_hook})")
            elif clip.grade_hook == "D":
                weaknesses.append("Weak opening hook")
            
            clip_analysis = ClipAnalysis(
                clip_id=clip.id,
                audio_energy_score=round(audio_energy * 10, 2),
                audio_excitement_score=round(audio_excitement * 10, 2),
                visual_interest_score=round(visual_interest * 10, 2),
                motion_score=round(motion * 10, 2),
                face_presence_score=round(face_likelihood * 10, 2),
                hook_strength_score=grade_to_score(clip.grade_hook),
                sentiment_intensity_score=grade_to_score(clip.grade_value),
                hook_grade_json={"grade": clip.grade_hook},
                flow_grade_json={"grade": clip.grade_flow},
                value_grade_json={"grade": clip.grade_value},
                trend_grade_json={"grade": clip.grade_trend},
                data_driven_score=round(data_score, 2),
                llm_score=None,
                final_score=clip.viral_score or round(data_score, 2),
                strengths=strengths,
                weaknesses=weaknesses,
                timeline_data_json=timeline_data[:50] if timeline_data else None,
            )
            db.add(clip_analysis)
            created += 1
            
        except Exception as e:
            print(f"   ❌ Error analyzing clip #{clip.id}: {e}")
    
    db.commit()
    print(f"\n   Total ClipAnalysis created: {created}, skipped: {skipped}")


def main():
    print("=" * 60)
    print("BACKFILL ANALYSIS TABLES")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        backfill_video_analyses(db)
        backfill_segment_analyses(db)
        backfill_clip_analyses(db)
        
        print("\n" + "=" * 60)
        print("✅ BACKFILL COMPLETE")
        print("=" * 60)
        
    finally:
        db.close()


if __name__ == "__main__":
    main()
