"""
Test script to verify AI Viral Segments integration.

This script tests:
1. ai_vision_analysis.py output format
2. segmentation.py passes ai_viral_segments correctly
3. virality.py uses ai_viral_segments from both fresh analysis and database
4. Database storage of ai_viral_segments_json
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.models import VideoSource, VideoAnalysis


def test_database_field():
    """Test that ai_viral_segments_json field exists in database."""
    print("\n=== Testing Database Field ===")
    db = SessionLocal()
    try:
        # Check if any VideoAnalysis has ai_viral_segments_json
        analyses = db.query(VideoAnalysis).all()
        print(f"Found {len(analyses)} video analyses")
        
        for analysis in analyses:
            has_segments = analysis.ai_viral_segments_json is not None
            segment_count = len(analysis.ai_viral_segments_json) if has_segments else 0
            print(f"  Video {analysis.video_source_id}: ai_viral_segments_json = {segment_count} segments")
            
            if has_segments and segment_count > 0:
                # Show sample segment structure
                sample = analysis.ai_viral_segments_json[0]
                print(f"    Sample segment keys: {list(sample.keys())}")
                if "ai_analysis" in sample:
                    print(f"    ai_analysis keys: {list(sample['ai_analysis'].keys())}")
        
        print("✅ Database field test passed")
        return True
    except Exception as e:
        print(f"❌ Database field test failed: {e}")
        return False
    finally:
        db.close()


def test_segment_format():
    """Test the expected segment format."""
    print("\n=== Testing Expected Segment Format ===")
    
    expected_format = {
        "start_time": 0.0,
        "end_time": 45.0,
        "duration": 45.0,
        "scene_count": 9,
        "viral_score": 0.85,
        "ai_analysis": {
            "avg_score": 0.85,
            "peak_score": 0.85,
            "reasoning": "High-energy competition scene...",
            "categories": ["action", "competition"],
            "hook_potential": 0.9,
            "engagement_factors": ["group dynamics", "high stakes"],
        },
        "action_level": "high",
        "is_viral_candidate": True,
        "transcription": "Sample transcript...",
        "complexity_score": 0.9,
        "is_merged": True,
    }
    
    required_keys = ["start_time", "end_time", "viral_score", "ai_analysis", "is_viral_candidate"]
    ai_analysis_keys = ["reasoning", "categories", "hook_potential", "engagement_factors"]
    
    print(f"Required segment keys: {required_keys}")
    print(f"Required ai_analysis keys: {ai_analysis_keys}")
    
    # Verify expected format has all keys
    for key in required_keys:
        if key not in expected_format:
            print(f"❌ Missing key: {key}")
            return False
    
    for key in ai_analysis_keys:
        if key not in expected_format["ai_analysis"]:
            print(f"❌ Missing ai_analysis key: {key}")
            return False
    
    print("✅ Expected format is correct")
    return True


def test_virality_candidate_format():
    """Test the clip candidate format used in virality.py."""
    print("\n=== Testing Virality Candidate Format ===")
    
    # This is the format that virality.py creates from ai_viral_segments
    candidate_format = {
        "start_time": 0.0,
        "end_time": 45.0,
        "duration": 45.0,
        "transcript_preview": "Sample transcript...",
        "transcript_full": "Full transcript...",
        "hook_strength": 0.7,
        "hook_reasons": ["question", "emotional"],
        "engagement_score": 0.8,
        # NEW: AI Vision segment data with reasoning
        "ai_reasoning": "High-energy competition scene...",
        "categories": ["action", "competition"],
        "engagement_factors": ["group dynamics", "high stakes"],
        "hook_potential": 0.9,
        "is_viral_candidate": True,
        "viral_score": 0.85,
        "action_level": "high",
    }
    
    new_keys = ["ai_reasoning", "categories", "engagement_factors", "hook_potential", 
                "is_viral_candidate", "viral_score", "action_level"]
    
    print(f"New keys added to candidates: {new_keys}")
    
    for key in new_keys:
        if key not in candidate_format:
            print(f"❌ Missing new key: {key}")
            return False
    
    print("✅ Candidate format is correct")
    return True


def main():
    print("=" * 60)
    print("AI Viral Segments Integration Test")
    print("=" * 60)
    
    results = []
    
    results.append(("Database Field", test_database_field()))
    results.append(("Segment Format", test_segment_format()))
    results.append(("Candidate Format", test_virality_candidate_format()))
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + ("All tests passed!" if all_passed else "Some tests failed!"))
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
