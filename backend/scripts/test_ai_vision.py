"""
Test script for AI Vision Analysis.

Run with:
  cd backend
  python -m scripts.test_ai_vision
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings
from app.services import ai_vision_analysis

settings = get_settings()


def test_ai_vision():
    print("=" * 60)
    print("AI VISION ANALYSIS TEST")
    print("=" * 60)
    
    print(f"\n📋 Configuration:")
    print(f"   AI Vision Enabled: {settings.ai_vision_enabled}")
    print(f"   Sample Interval: {settings.ai_vision_sample_interval}s")
    print(f"   Batch Size: {settings.ai_vision_batch_size}")
    print(f"   Max Frames: {settings.ai_vision_max_frames}")
    print(f"   Vision Model: {settings.openai_vision_model}")
    
    if not settings.ai_vision_enabled:
        print("\n⚠️  AI Vision is DISABLED in settings")
        print("   Set AI_VISION_ENABLED=true in .env to enable")
        return
    
    # Find a test video
    media_root = settings.media_root
    test_video = None
    
    for root, dirs, files in os.walk(media_root):
        for f in files:
            if f.endswith(('.mp4', '.webm', '.mov')):
                test_video = os.path.join(root, f)
                break
        if test_video:
            break
    
    if not test_video:
        print("\n❌ No video found in media folder for testing")
        return
    
    print(f"\n🎬 Test Video: {test_video}")
    
    # Get video duration
    from app.services.utils import probe_duration
    duration = probe_duration(test_video)
    print(f"   Duration: {duration:.1f}s")
    
    # Calculate expected frames
    expected_frames = min(
        int(duration / settings.ai_vision_sample_interval),
        settings.ai_vision_max_frames
    )
    print(f"   Expected Frames: {expected_frames}")
    
    # Estimate cost
    # GPT-4o-mini: ~$0.00015 per image (low detail)
    estimated_cost = expected_frames * 0.00015
    print(f"   Estimated Cost: ${estimated_cost:.4f}")
    
    # Ask for confirmation
    print("\n" + "=" * 60)
    response = input("Run AI Vision analysis? (y/n): ").strip().lower()
    
    if response != 'y':
        print("Cancelled.")
        return
    
    print("\n🔍 Starting AI Vision Analysis...")
    
    def progress(p, msg):
        print(f"   [{p*100:.0f}%] {msg}")
    
    try:
        result = ai_vision_analysis.analyze_video_with_vision(
            test_video,
            duration,
            progress_callback=progress,
        )
        
        print("\n" + "=" * 60)
        print("✅ ANALYSIS COMPLETE")
        print("=" * 60)
        
        summary = result.get("summary", {})
        print(f"\n📊 Summary:")
        print(f"   Total Frames Analyzed: {summary.get('total_frames', 0)}")
        print(f"   Avg Face Count: {summary.get('avg_face_count', 0):.2f}")
        print(f"   Face Presence Ratio: {summary.get('face_presence_ratio', 0):.1%}")
        print(f"   Avg Visual Interest: {summary.get('avg_visual_interest', 0):.2f}")
        print(f"   Dominant Scene Type: {summary.get('dominant_scene_type', 'unknown')}")
        
        emotions = summary.get("emotion_distribution", {})
        if emotions:
            print(f"\n😊 Emotion Distribution:")
            for em, count in sorted(emotions.items(), key=lambda x: -x[1])[:5]:
                print(f"   - {em}: {count}")
        
        indicators = summary.get("engagement_indicator_counts", {})
        if indicators:
            print(f"\n🔥 Engagement Indicators:")
            for ind, count in sorted(indicators.items(), key=lambda x: -x[1])[:5]:
                print(f"   - {ind}: {count}")
        
        viral_moments = result.get("viral_moments", [])
        if viral_moments:
            print(f"\n⭐ Top Viral Moments ({len(viral_moments)} found):")
            for i, moment in enumerate(viral_moments[:5], 1):
                print(f"   {i}. {moment['timestamp']:.1f}s - Score: {moment['score']:.2f}")
                print(f"      Reasons: {', '.join(moment.get('reasons', []))}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_ai_vision()
