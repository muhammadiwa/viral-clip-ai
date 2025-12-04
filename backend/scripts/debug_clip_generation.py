"""
Debug script to analyze why clip generation produces few clips.

This script:
1. Checks VideoAnalysis data in database
2. Shows engagement peaks found
3. Explains scoring breakdown
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.models import VideoSource, VideoAnalysis, ClipBatch, Clip
from app.models.analysis import ClipAnalysis
from app.core.config import get_settings

settings = get_settings()


def debug_video_analysis(video_id: int = 1):
    """Debug video analysis data."""
    print("\n" + "=" * 60)
    print(f"DEBUG: Video Analysis for Video ID {video_id}")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        # Get video
        video = db.query(VideoSource).filter(VideoSource.id == video_id).first()
        if not video:
            print(f"❌ Video {video_id} not found")
            return
        
        print(f"\n📹 Video: {video.title}")
        print(f"   Duration: {video.duration_seconds:.1f}s ({video.duration_seconds/60:.1f} min)")
        print(f"   Status: {video.status}")
        
        # Get analysis
        analysis = db.query(VideoAnalysis).filter(
            VideoAnalysis.video_source_id == video_id
        ).first()
        
        if not analysis:
            print(f"\n❌ No VideoAnalysis found for video {video_id}")
            print("   This means comprehensive analysis was not saved to database.")
            return
        
        print(f"\n📊 Analysis Data:")
        print(f"   Version: {analysis.analysis_version}")
        print(f"   Duration Analyzed: {analysis.duration_analyzed:.1f}s")
        print(f"   AI Vision Enabled: {analysis.ai_vision_enabled}")
        
        # Check timeline data
        audio_timeline = analysis.audio_timeline_json or []
        visual_timeline = analysis.visual_timeline_json or []
        combined_timeline = analysis.combined_timeline_json or []
        ai_viral_segments = analysis.ai_viral_segments_json or []
        
        print(f"\n📈 Timeline Data:")
        print(f"   Audio Timeline: {len(audio_timeline)} samples")
        print(f"   Visual Timeline: {len(visual_timeline)} samples")
        print(f"   Combined Timeline: {len(combined_timeline)} samples")
        print(f"   AI Viral Segments: {len(ai_viral_segments)} segments")
        
        # Check peaks
        audio_peaks = analysis.audio_peaks_json or []
        visual_peaks = analysis.visual_peaks_json or []
        engagement_peaks = analysis.engagement_peaks_json or []
        
        print(f"\n🔥 Peaks Found:")
        print(f"   Audio Peaks: {len(audio_peaks)}")
        print(f"   Visual Peaks: {len(visual_peaks)}")
        print(f"   Engagement Peaks (Viral Moments): {len(engagement_peaks)}")
        
        # Show sample of combined timeline
        if combined_timeline:
            print(f"\n📊 Sample Combined Timeline (first 5):")
            for t in combined_timeline[:5]:
                print(f"   t={t.get('time', 0):.0f}s: "
                      f"audio={t.get('audio_energy', 0):.2f}, "
                      f"visual={t.get('visual_interest', 0):.2f}, "
                      f"engagement={t.get('engagement_score', 0):.2f}, "
                      f"ai_vision={t.get('ai_vision_used', False)}")
        
        # Show AI viral segments
        if ai_viral_segments:
            print(f"\n🎯 AI Viral Segments (top 3):")
            for seg in ai_viral_segments[:3]:
                ai_analysis = seg.get("ai_analysis", {})
                print(f"   {seg.get('start_time', 0):.0f}s - {seg.get('end_time', 0):.0f}s:")
                print(f"      Viral Score: {seg.get('viral_score', 0):.2f}")
                print(f"      Is Viral Candidate: {seg.get('is_viral_candidate', False)}")
                print(f"      Reasoning: {ai_analysis.get('reasoning', 'N/A')[:100]}...")
                print(f"      Categories: {ai_analysis.get('categories', [])}")
        
        # Get clips
        batches = db.query(ClipBatch).filter(ClipBatch.video_source_id == video_id).all()
        print(f"\n🎬 Clip Batches: {len(batches)}")
        
        for batch in batches:
            clips = db.query(Clip).filter(Clip.clip_batch_id == batch.id).all()
            print(f"\n   Batch {batch.id} ({batch.status}):")
            print(f"   Clips: {len(clips)}")
            
            for clip in clips:
                print(f"\n   📎 Clip {clip.id}:")
                print(f"      Time: {clip.start_time_sec:.1f}s - {clip.end_time_sec:.1f}s ({clip.duration_sec:.1f}s)")
                print(f"      Title: {clip.title[:50]}...")
                print(f"      Viral Score: {clip.viral_score}")
                print(f"      Grades: Hook={clip.grade_hook}, Flow={clip.grade_flow}, Value={clip.grade_value}, Trend={clip.grade_trend}")
                
                # Get detailed analysis
                clip_analysis = db.query(ClipAnalysis).filter(ClipAnalysis.clip_id == clip.id).first()
                if clip_analysis:
                    print(f"      Detailed Scores:")
                    print(f"         Audio Energy: {clip_analysis.audio_energy_score:.1f}/10")
                    print(f"         Visual Interest: {clip_analysis.visual_interest_score:.1f}/10")
                    print(f"         Hook Strength: {clip_analysis.hook_strength_score:.1f}/10")
                    print(f"         Data Score: {clip_analysis.data_driven_score:.1f}")
                    print(f"         LLM Score: {clip_analysis.llm_score}")
                    print(f"         Final Score: {clip_analysis.final_score:.1f}")
                    print(f"      Strengths: {clip_analysis.strengths}")
                    print(f"      Weaknesses: {clip_analysis.weaknesses}")
        
        # Diagnosis
        print("\n" + "=" * 60)
        print("🔍 DIAGNOSIS")
        print("=" * 60)
        
        issues = []
        
        if len(audio_timeline) == 0:
            issues.append("❌ Audio analysis failed (0 samples) - check ffmpeg ebur128 filter")
        
        if not analysis.ai_vision_enabled:
            issues.append("⚠️ AI Vision was disabled during analysis")
        elif len(ai_viral_segments) == 0:
            issues.append("⚠️ AI Vision enabled but no viral segments found")
        
        if len(combined_timeline) < video.duration_seconds * 0.5:
            issues.append(f"⚠️ Combined timeline incomplete ({len(combined_timeline)} samples for {video.duration_seconds:.0f}s video)")
        
        if len(engagement_peaks) < 5:
            issues.append(f"⚠️ Few engagement peaks found ({len(engagement_peaks)}) - threshold may be too high")
        
        if not issues:
            print("✅ No obvious issues found in analysis data")
        else:
            for issue in issues:
                print(issue)
        
        print("\n💡 RECOMMENDATIONS:")
        if len(audio_timeline) == 0:
            print("   1. Check ffmpeg installation and ebur128 filter support")
            print("   2. Try running: ffmpeg -i <video> -af ebur128 -f null -")
        
        if len(ai_viral_segments) == 0 and analysis.ai_vision_enabled:
            print("   1. Check OpenAI API key and vision model access")
            print("   2. Check AI_VISION_ENABLED in .env")
        
        print("\n   To regenerate analysis, delete VideoAnalysis record and re-process video")
        
    finally:
        db.close()


def show_config():
    """Show current configuration."""
    print("\n" + "=" * 60)
    print("⚙️ CURRENT CONFIGURATION")
    print("=" * 60)
    
    print(f"\nAI Vision:")
    print(f"   Enabled: {settings.ai_vision_enabled}")
    print(f"   Sample Interval: {settings.ai_vision_sample_interval}s")
    print(f"   Max Frames: {settings.ai_vision_max_frames}")
    
    print(f"\nOpenAI:")
    print(f"   API Key: {'✅ Set' if settings.openai_api_key else '❌ Not set'}")
    print(f"   Vision Model: {settings.openai_vision_model}")
    print(f"   Responses Model: {settings.openai_responses_model}")


if __name__ == "__main__":
    show_config()
    
    video_id = 1
    if len(sys.argv) > 1:
        video_id = int(sys.argv[1])
    
    debug_video_analysis(video_id)
