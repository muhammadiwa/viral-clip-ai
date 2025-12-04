"""
AI Vision Analysis Service for Enhanced Viral Clip Detection.

Uses OpenAI Vision API to analyze video segments for viral potential with:
- Reasoning: Natural language explanation of WHY content is viral
- Categories: Multiple viral categories per segment
- Engagement Factors: Contextual factors that drive engagement
- Scene Merging: Combines frames into coherent segments
- Transcript Context: Uses dialog to understand content better

Output format matches proven viral detection patterns.
"""
import base64
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import structlog

from app.core.config import get_settings
from app.services.utils import run_cmd, ensure_dir, get_openai_client

logger = structlog.get_logger()
settings = get_settings()

# Retry configuration
MAX_RETRIES = 3
RETRY_BACKOFF = 2.0  # seconds


def extract_frames(
    video_path: str,
    output_dir: Path,
    sample_interval: float = 5.0,
    max_frames: int = 120,
    duration: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Extract frames from video at specified intervals."""
    logger.info(
        "ai_vision.extract_frames_start",
        video_path=video_path,
        interval=sample_interval,
        max_frames=max_frames,
    )
    
    ensure_dir(output_dir)
    fps = 1.0 / sample_interval
    
    cmd = [
        settings.ffmpeg_bin,
        "-y",
        "-i", video_path,
        "-vf", f"fps={fps}",
        "-frames:v", str(max_frames),
        "-q:v", "2",
        str(output_dir / "frame_%04d.jpg"),
    ]
    
    code, _, err = run_cmd(cmd)
    if code != 0:
        logger.error("ai_vision.extract_frames_failed", error=err[:500])
        return []
    
    frames = []
    frame_files = sorted(output_dir.glob("frame_*.jpg"))
    
    for idx, frame_path in enumerate(frame_files):
        timestamp = idx * sample_interval
        frames.append({
            "frame_path": str(frame_path),
            "timestamp": timestamp,
            "frame_index": idx,
        })
    
    logger.info("ai_vision.extract_frames_done", frames_extracted=len(frames))
    return frames


def encode_image_base64(image_path: str) -> str:
    """Encode image file to base64 string."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def analyze_segment_with_vision(
    client,
    frames: List[Dict[str, Any]],
    transcript_text: str = "",
    start_time: float = 0.0,
    end_time: float = 0.0,
) -> Dict[str, Any]:
    """
    Analyze a video segment (multiple frames) with AI Vision.
    
    This is the core analysis function that produces the optimal output format
    with reasoning, categories, and engagement factors.
    """
    content = []
    
    # Build the prompt with transcript context
    transcript_context = ""
    if transcript_text:
        transcript_context = f"""
TRANSCRIPT/DIALOG for this segment:
"{transcript_text[:500]}"
"""
    
    content.append({
        "type": "text",
        "text": f"""You are a viral content expert analyzing video segments for TikTok/Reels/Shorts potential.

Analyze these {len(frames)} frames from a video segment (timestamps {start_time:.1f}s - {end_time:.1f}s).
{transcript_context}
Evaluate the VIRAL POTENTIAL and provide:

1. viral_score (0.0-1.0): Overall viral potential. Be STRICT - only >0.7 for genuinely viral content.

2. reasoning (string): 2-3 sentences explaining WHY this segment is/isn't viral. Be specific about:
   - What makes it visually compelling
   - What emotional response it triggers
   - Why someone would stop scrolling or share it

3. categories (array): ALL that apply from:
   ["action", "humor", "surprise", "suspense", "drama", "competition", "reaction", "tutorial", 
    "transformation", "reveal", "emotional", "satisfying", "fail", "win", "cute", "wholesome",
    "controversial", "relatable", "spectacle", "challenge"]

4. hook_potential (0.0-1.0): Would this make someone STOP SCROLLING in first 3 seconds?

5. engagement_factors (array): Specific factors driving engagement:
   ["drama", "tension", "group dynamics", "visual spectacle", "high stakes", "competition",
    "humor", "unexpected twist", "emotional moment", "satisfying conclusion", "relatable situation",
    "impressive skill", "unique concept", "celebrity/influencer", "trending topic", "controversy",
    "before/after", "transformation", "reaction", "challenge", "tutorial value"]

6. action_level: "low", "medium", or "high"

7. is_viral_candidate (boolean): true if viral_score > 0.6

Return JSON object:
{{
  "viral_score": 0.85,
  "reasoning": "High-energy competition scene with dramatic stakes. Large group dynamics and visual spectacle create immediate engagement. The trap concept is unique and intriguing.",
  "categories": ["action", "competition", "suspense", "spectacle"],
  "hook_potential": 0.9,
  "engagement_factors": ["group dynamics", "high stakes", "dramatic tension", "visual impact", "unique concept"],
  "action_level": "high",
  "is_viral_candidate": true
}}

Analyze based on BOTH the visual content AND the transcript context. Return ONLY valid JSON."""
    })
    
    # Add frame images
    for frame in frames[:5]:  # Limit to 5 frames per segment to control cost
        try:
            base64_image = encode_image_base64(frame["frame_path"])
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}",
                    "detail": "low",
                },
            })
        except Exception as e:
            logger.warning("ai_vision.encode_failed", frame=frame["frame_path"], error=str(e))
    
    # Retry logic with exponential backoff
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=settings.openai_vision_model,
                messages=[{"role": "user", "content": content}],
                max_tokens=500,
                temperature=0.3,
            )
            
            response_text = response.choices[0].message.content.strip()
            if response_text.startswith("```"):
                response_text = response_text.strip("```json").strip("```").strip()
            
            result = json.loads(response_text)
            return _normalize_segment_result(result, start_time, end_time, len(frames), transcript_text)
            
        except json.JSONDecodeError as e:
            last_error = e
            logger.warning(
                "ai_vision.json_parse_failed",
                attempt=attempt,
                error=str(e),
                start_time=start_time,
            )
            # Don't retry JSON errors - likely bad response format
            break
            
        except Exception as e:
            last_error = e
            logger.warning(
                "ai_vision.segment_analysis_retry",
                attempt=attempt,
                max_retries=MAX_RETRIES,
                error=str(e),
                start_time=start_time,
            )
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF * attempt)  # Exponential backoff
    
    logger.error(
        "ai_vision.segment_analysis_failed",
        error=str(last_error),
        start_time=start_time,
        end_time=end_time,
    )
    return _create_fallback_segment(start_time, end_time, len(frames), transcript_text)


def _normalize_segment_result(
    result: Dict[str, Any],
    start_time: float,
    end_time: float,
    frame_count: int,
    transcript: str,
) -> Dict[str, Any]:
    """Normalize and validate segment analysis result."""
    viral_score = min(1.0, max(0.0, float(result.get("viral_score", 0.5))))
    hook_potential = min(1.0, max(0.0, float(result.get("hook_potential", 0.5))))
    
    return {
        "start_time": start_time,
        "end_time": end_time,
        "duration": end_time - start_time,
        "scene_count": frame_count,
        "viral_score": viral_score,
        "ai_analysis": {
            "avg_score": viral_score,
            "peak_score": viral_score,
            "reasoning": result.get("reasoning", "Analysis not available"),
            "categories": result.get("categories", []),
            "hook_potential": hook_potential,
            "engagement_factors": result.get("engagement_factors", []),
        },
        "action_level": result.get("action_level", "medium"),
        "is_viral_candidate": result.get("is_viral_candidate", viral_score > 0.6),
        "transcription": transcript[:200] if transcript else "",
        "complexity_score": min(1.0, frame_count / 10),
        "is_merged": frame_count > 1,
    }


def _create_fallback_segment(
    start_time: float,
    end_time: float,
    frame_count: int,
    transcript: str,
) -> Dict[str, Any]:
    """Create fallback segment when AI analysis fails."""
    return {
        "start_time": start_time,
        "end_time": end_time,
        "duration": end_time - start_time,
        "scene_count": frame_count,
        "viral_score": 0.5,
        "ai_analysis": {
            "avg_score": 0.5,
            "peak_score": 0.5,
            "reasoning": "Analysis failed - using default values",
            "categories": [],
            "hook_potential": 0.5,
            "engagement_factors": [],
        },
        "action_level": "medium",
        "is_viral_candidate": False,
        "transcription": transcript[:200] if transcript else "",
        "complexity_score": 0.5,
        "is_merged": frame_count > 1,
    }



def analyze_video_segments(
    video_path: str,
    duration: float,
    transcripts: List[Dict[str, Any]] = None,
    segment_duration: float = 45.0,
    sample_interval: float = 5.0,
    progress_callback: Optional[callable] = None,
) -> Dict[str, Any]:
    """
    Analyze video by segments with AI Vision.
    
    This is the main entry point that:
    1. Divides video into segments (~45 seconds each)
    2. Extracts key frames from each segment
    3. Gets transcript for each segment
    4. Analyzes each segment with AI Vision
    5. Returns segments sorted by viral potential
    
    Args:
        video_path: Path to video file
        duration: Video duration in seconds
        transcripts: List of transcript segments with start_time_sec, end_time_sec, text
        segment_duration: Target duration for each segment (default 45s)
        sample_interval: Seconds between frame samples
        progress_callback: Optional callback(progress, message)
    
    Returns:
        Dict with viral_segments, summary, and metadata
    """
    if not settings.ai_vision_enabled:
        logger.info("ai_vision.disabled", msg="AI Vision analysis is disabled")
        return _create_empty_result(duration)
    
    client = get_openai_client()
    if not client:
        logger.warning("ai_vision.no_client", msg="OpenAI client not available")
        return _create_empty_result(duration)
    
    logger.info(
        "ai_vision.segment_analysis_start",
        video_path=video_path,
        duration=duration,
        segment_duration=segment_duration,
    )
    
    transcripts = transcripts or []
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Step 1: Extract all frames
        if progress_callback:
            progress_callback(0.1, "Extracting video frames...")
        
        max_frames = min(int(duration / sample_interval) + 1, settings.ai_vision_max_frames)
        frames = extract_frames(
            video_path,
            temp_path,
            sample_interval=sample_interval,
            max_frames=max_frames,
            duration=duration,
        )
        
        if not frames:
            logger.warning("ai_vision.no_frames")
            return _create_empty_result(duration)
        
        # Step 2: Divide into segments
        segments_to_analyze = []
        current_time = 0.0
        
        while current_time < duration:
            seg_end = min(current_time + segment_duration, duration)
            
            # Get frames for this segment
            seg_frames = [f for f in frames if current_time <= f["timestamp"] < seg_end]
            
            # Get transcript for this segment
            seg_transcript = _get_transcript_for_range(transcripts, current_time, seg_end)
            
            if seg_frames:
                segments_to_analyze.append({
                    "start_time": current_time,
                    "end_time": seg_end,
                    "frames": seg_frames,
                    "transcript": seg_transcript,
                })
            
            current_time = seg_end
        
        # Step 3: Analyze each segment
        if progress_callback:
            progress_callback(0.2, f"Analyzing {len(segments_to_analyze)} segments...")
        
        viral_segments = []
        total_segments = len(segments_to_analyze)
        
        for idx, seg in enumerate(segments_to_analyze):
            if progress_callback:
                progress = 0.2 + (0.7 * (idx + 1) / total_segments)
                progress_callback(progress, f"Analyzing segment {idx + 1}/{total_segments}")
            
            result = analyze_segment_with_vision(
                client,
                seg["frames"],
                seg["transcript"],
                seg["start_time"],
                seg["end_time"],
            )
            viral_segments.append(result)
        
        # Step 4: Sort by viral score
        viral_segments.sort(key=lambda x: x["viral_score"], reverse=True)
        
        # Step 5: Calculate summary
        if progress_callback:
            progress_callback(0.95, "Calculating summary...")
        
        summary = _calculate_segments_summary(viral_segments)
        
        if progress_callback:
            progress_callback(1.0, "AI vision analysis complete")
        
        logger.info(
            "ai_vision.segment_analysis_done",
            segments_analyzed=len(viral_segments),
            viral_candidates=sum(1 for s in viral_segments if s["is_viral_candidate"]),
        )
        
        return {
            "viral_segments": viral_segments,
            "summary": summary,
            "ai_vision_enabled": True,
            "total_segments": len(viral_segments),
            "viral_candidates_count": sum(1 for s in viral_segments if s["is_viral_candidate"]),
        }


def _get_transcript_for_range(
    transcripts: List[Dict[str, Any]],
    start_time: float,
    end_time: float,
) -> str:
    """Get transcript text for a time range."""
    texts = []
    for t in transcripts:
        t_start = t.get("start_time_sec", t.get("start_time", 0))
        t_end = t.get("end_time_sec", t.get("end_time", 0))
        
        # Check overlap
        if t_end > start_time and t_start < end_time:
            texts.append(t.get("text", ""))
    
    return " ".join(texts)


def _calculate_segments_summary(segments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate summary statistics from segment analyses."""
    if not segments:
        return {
            "total_segments": 0,
            "avg_viral_score": 0.5,
            "viral_candidates": 0,
            "top_categories": [],
            "top_engagement_factors": [],
        }
    
    total = len(segments)
    
    # Average scores
    avg_viral = sum(s["viral_score"] for s in segments) / total
    avg_hook = sum(s["ai_analysis"]["hook_potential"] for s in segments) / total
    
    # Count viral candidates
    viral_count = sum(1 for s in segments if s["is_viral_candidate"])
    
    # Aggregate categories
    all_categories = {}
    for s in segments:
        for cat in s["ai_analysis"].get("categories", []):
            all_categories[cat] = all_categories.get(cat, 0) + 1
    top_categories = sorted(all_categories.items(), key=lambda x: -x[1])[:10]
    
    # Aggregate engagement factors
    all_factors = {}
    for s in segments:
        for factor in s["ai_analysis"].get("engagement_factors", []):
            all_factors[factor] = all_factors.get(factor, 0) + 1
    top_factors = sorted(all_factors.items(), key=lambda x: -x[1])[:10]
    
    # Action level distribution
    action_levels = {}
    for s in segments:
        level = s.get("action_level", "medium")
        action_levels[level] = action_levels.get(level, 0) + 1
    
    return {
        "total_segments": total,
        "avg_viral_score": round(avg_viral, 2),
        "avg_hook_potential": round(avg_hook, 2),
        "viral_candidates": viral_count,
        "viral_ratio": round(viral_count / total, 2) if total > 0 else 0,
        "top_categories": [{"category": c, "count": n} for c, n in top_categories],
        "top_engagement_factors": [{"factor": f, "count": n} for f, n in top_factors],
        "action_level_distribution": action_levels,
    }


def _create_empty_result(duration: float) -> Dict[str, Any]:
    """Create empty result when AI vision is disabled or fails."""
    return {
        "viral_segments": [],
        "summary": {
            "total_segments": 0,
            "avg_viral_score": 0.5,
            "viral_candidates": 0,
            "top_categories": [],
            "top_engagement_factors": [],
        },
        "ai_vision_enabled": False,
        "total_segments": 0,
        "viral_candidates_count": 0,
    }


# Legacy compatibility functions
def analyze_video_with_vision(
    video_path: str,
    duration: float,
    sample_interval: Optional[float] = None,
    max_frames: Optional[int] = None,
    progress_callback: Optional[callable] = None,
    transcripts: List[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Legacy wrapper for backward compatibility.
    Converts new segment-based output to old timeline-based format.
    """
    sample_interval = sample_interval or settings.ai_vision_sample_interval
    
    result = analyze_video_segments(
        video_path=video_path,
        duration=duration,
        transcripts=transcripts or [],
        segment_duration=45.0,
        sample_interval=sample_interval,
        progress_callback=progress_callback,
    )
    
    if not result.get("ai_vision_enabled"):
        return {
            "frame_analyses": [],
            "timeline": [],
            "summary": result.get("summary", {}),
            "viral_moments": [],
            "ai_vision_enabled": False,
        }
    
    # Convert segments to timeline format
    timeline = []
    viral_moments = []
    
    for seg in result.get("viral_segments", []):
        # Add to timeline
        t = seg["start_time"]
        while t < seg["end_time"]:
            timeline.append({
                "time": t,
                "visual_interest_score": seg["viral_score"],
                "hook_potential": seg["ai_analysis"]["hook_potential"],
                "engagement_indicators": seg["ai_analysis"].get("engagement_factors", []),
                "categories": seg["ai_analysis"].get("categories", []),
                "reasoning": seg["ai_analysis"].get("reasoning", ""),
                "ai_analyzed": True,
            })
            t += 1.0
        
        # Add viral moments
        if seg["is_viral_candidate"]:
            viral_moments.append({
                "timestamp": seg["start_time"],
                "end_time": seg["end_time"],
                "score": seg["viral_score"],
                "reasoning": seg["ai_analysis"].get("reasoning", ""),
                "categories": seg["ai_analysis"].get("categories", []),
                "engagement_factors": seg["ai_analysis"].get("engagement_factors", []),
                "hook_potential": seg["ai_analysis"]["hook_potential"],
                "is_viral_candidate": True,
            })
    
    return {
        "frame_analyses": [],  # Not used in new format
        "timeline": timeline,
        "summary": result.get("summary", {}),
        "viral_moments": viral_moments,
        "viral_segments": result.get("viral_segments", []),
        "ai_vision_enabled": True,
    }
