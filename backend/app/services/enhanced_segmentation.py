"""
Enhanced Segmentation Service for Viral Clip Detection.

Combines multiple analysis signals to create intelligent scene segments:
- Audio energy and events
- Visual motion and scene cuts
- Transcript sentiment and hooks
- Engagement scoring
"""
from typing import Any, Dict, List, Optional, Tuple

import structlog
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import VideoSource, SceneSegment, TranscriptSegment
from app.services import audio_analysis, visual_analysis, sentiment_analysis
from app.services.utils import probe_duration

logger = structlog.get_logger()
settings = get_settings()


def analyze_video_comprehensive(
    video_path: str,
    duration: float,
    transcripts: List[TranscriptSegment],
) -> Dict[str, Any]:
    """
    Perform comprehensive multi-modal analysis of a video.
    
    Returns:
    - audio_timeline: per-second audio analysis
    - visual_timeline: per-second visual analysis
    - transcript_analysis: per-segment sentiment analysis
    - combined_timeline: merged engagement scores
    """
    logger.info("enhanced_seg.comprehensive_start", video_path=video_path, duration=duration)
    
    # 1. Audio Analysis
    audio_timeline = audio_analysis.calculate_energy_timeline(
        video_path, duration, window_size=1.0
    )
    audio_peaks = audio_analysis.find_audio_peaks(audio_timeline, min_duration=5.0, top_n=20)
    
    # 2. Visual Analysis
    visual_timeline = visual_analysis.calculate_visual_timeline(
        video_path, duration, sample_interval=1.0
    )
    visual_peaks = visual_analysis.find_visual_peaks(visual_timeline, min_duration=5.0, top_n=20)
    
    # 3. Transcript/Sentiment Analysis
    transcript_analysis = sentiment_analysis.analyze_transcript_segments(transcripts)
    viral_moments = sentiment_analysis.find_viral_moments_from_transcript(
        transcript_analysis, min_score=0.3
    )
    
    # 4. Combine into unified timeline
    combined_timeline = _merge_timelines(
        audio_timeline, visual_timeline, transcript_analysis, duration
    )
    
    logger.info(
        "enhanced_seg.comprehensive_done",
        audio_samples=len(audio_timeline),
        visual_samples=len(visual_timeline),
        transcript_segments=len(transcript_analysis),
    )
    
    return {
        "audio_timeline": audio_timeline,
        "visual_timeline": visual_timeline,
        "transcript_analysis": transcript_analysis,
        "combined_timeline": combined_timeline,
        "audio_peaks": audio_peaks,
        "visual_peaks": visual_peaks,
        "viral_moments": viral_moments,
    }


def _merge_timelines(
    audio_timeline: List[Dict[str, Any]],
    visual_timeline: List[Dict[str, Any]],
    transcript_analysis: List[Dict[str, Any]],
    duration: float,
) -> List[Dict[str, Any]]:
    """
    Merge audio, visual, and transcript analysis into a single timeline.
    """
    # Create time-indexed lookups
    audio_lookup = {int(a["time"]): a for a in audio_timeline}
    visual_lookup = {int(v["time"]): v for v in visual_timeline}
    
    # Create transcript lookup by time range
    def get_transcript_score(t: float) -> Tuple[float, str]:
        for seg in transcript_analysis:
            if seg["start_time"] <= t < seg["end_time"]:
                return seg["viral_potential"], seg["sentiment"]["emotion"]
        return 0.3, "neutral"
    
    combined = []
    t = 0.0
    
    while t < duration:
        t_int = int(t)
        
        # Get audio data
        audio = audio_lookup.get(t_int, {})
        audio_energy = audio.get("energy", 0.5)
        audio_excitement = audio.get("excitement_score", 0.5)
        
        # Get visual data
        visual = visual_lookup.get(t_int, {})
        visual_interest = visual.get("visual_interest", 0.5)
        motion = visual.get("motion_score", 0.5)
        face = visual.get("face_likelihood", 0.5)
        
        # Get transcript data
        transcript_score, emotion = get_transcript_score(t)
        
        # Calculate combined engagement score
        engagement_score = (
            audio_energy * 0.15 +
            audio_excitement * 0.15 +
            visual_interest * 0.20 +
            motion * 0.10 +
            face * 0.15 +
            transcript_score * 0.25
        )
        
        combined.append({
            "time": t,
            "audio_energy": audio_energy,
            "audio_excitement": audio_excitement,
            "visual_interest": visual_interest,
            "motion": motion,
            "face_likelihood": face,
            "transcript_score": transcript_score,
            "emotion": emotion,
            "engagement_score": engagement_score,
        })
        
        t += 1.0
    
    return combined


def find_engagement_peaks(
    combined_timeline: List[Dict[str, Any]],
    min_duration: float = 10.0,
    max_duration: float = 90.0,
    top_n: int = 15,
) -> List[Dict[str, Any]]:
    """
    Find peak engagement moments from the combined timeline.
    
    Returns optimal clip candidates with:
    - start_time, end_time
    - engagement_score
    - dominant_signal (what makes this engaging)
    """
    if not combined_timeline:
        return []
    
    # Calculate dynamic threshold based on video's overall engagement
    all_scores = [c["engagement_score"] for c in combined_timeline]
    mean_score = sum(all_scores) / len(all_scores)
    threshold = max(0.4, mean_score * 1.2)  # 20% above mean or 0.4 minimum
    
    peaks = []
    i = 0
    
    while i < len(combined_timeline):
        if combined_timeline[i]["engagement_score"] >= threshold:
            start_idx = i
            peak_score = combined_timeline[i]["engagement_score"]
            scores_sum = combined_timeline[i]["engagement_score"]
            
            # Extend while engagement stays reasonable
            while i < len(combined_timeline) and combined_timeline[i]["engagement_score"] >= threshold * 0.7:
                peak_score = max(peak_score, combined_timeline[i]["engagement_score"])
                scores_sum += combined_timeline[i]["engagement_score"]
                i += 1
            
            end_idx = i
            duration = combined_timeline[end_idx - 1]["time"] - combined_timeline[start_idx]["time"]
            
            if min_duration <= duration <= max_duration:
                segment_data = combined_timeline[start_idx:end_idx]
                avg_score = scores_sum / len(segment_data)
                
                # Determine dominant signal
                avg_audio = sum(s["audio_excitement"] for s in segment_data) / len(segment_data)
                avg_visual = sum(s["visual_interest"] for s in segment_data) / len(segment_data)
                avg_transcript = sum(s["transcript_score"] for s in segment_data) / len(segment_data)
                
                if avg_audio >= avg_visual and avg_audio >= avg_transcript:
                    dominant = "audio_excitement"
                elif avg_visual >= avg_transcript:
                    dominant = "visual_interest"
                else:
                    dominant = "compelling_content"
                
                # Get emotion distribution
                emotions = {}
                for s in segment_data:
                    em = s.get("emotion", "neutral")
                    emotions[em] = emotions.get(em, 0) + 1
                primary_emotion = max(emotions, key=emotions.get) if emotions else "neutral"
                
                peaks.append({
                    "start_time": combined_timeline[start_idx]["time"],
                    "end_time": combined_timeline[end_idx - 1]["time"],
                    "duration": duration,
                    "peak_score": peak_score,
                    "avg_score": avg_score,
                    "dominant_signal": dominant,
                    "primary_emotion": primary_emotion,
                    "avg_audio_excitement": avg_audio,
                    "avg_visual_interest": avg_visual,
                    "avg_transcript_score": avg_transcript,
                })
        else:
            i += 1
    
    # Sort by average score (more representative than peak)
    peaks.sort(key=lambda x: x["avg_score"], reverse=True)
    
    return peaks[:top_n]


def create_enhanced_segments(
    db: Session,
    video: VideoSource,
    transcripts: List[TranscriptSegment],
) -> Tuple[List[SceneSegment], Dict[str, Any]]:
    """
    Create enhanced scene segments using multi-modal analysis.
    
    Returns:
    - List of SceneSegment objects
    - Analysis metadata
    """
    if not video.file_path:
        raise ValueError("Video file_path missing")
    
    duration = video.duration_seconds or probe_duration(video.file_path) or 0.0
    if duration <= 0:
        raise ValueError("Cannot determine video duration")
    
    logger.info("enhanced_seg.create_start", video_id=video.id, duration=duration)
    
    # Perform comprehensive analysis
    analysis = analyze_video_comprehensive(video.file_path, duration, transcripts)
    
    # Find engagement peaks
    peaks = find_engagement_peaks(
        analysis["combined_timeline"],
        min_duration=10.0,
        max_duration=90.0,
        top_n=15,
    )
    
    # Also include audio and visual peaks that might have been missed
    all_peak_times = set()
    
    # Add combined peaks
    for peak in peaks:
        all_peak_times.add((peak["start_time"], peak["end_time"]))
    
    # Add audio peaks not covered
    for ap in analysis["audio_peaks"][:10]:
        if not any(abs(ap["start_time"] - p[0]) < 5 for p in all_peak_times):
            all_peak_times.add((ap["start_time"], ap["end_time"]))
    
    # Add visual peaks not covered
    for vp in analysis["visual_peaks"][:10]:
        if not any(abs(vp["start_time"] - p[0]) < 5 for p in all_peak_times):
            all_peak_times.add((vp["start_time"], vp["end_time"]))
    
    # Clear existing segments
    db.query(SceneSegment).filter(SceneSegment.video_source_id == video.id).delete()
    
    # Create SceneSegment objects
    segments = []
    for peak in peaks:
        # Find corresponding data in combined timeline
        start_idx = int(peak["start_time"])
        end_idx = int(peak["end_time"])
        
        if start_idx < len(analysis["combined_timeline"]):
            timeline_slice = analysis["combined_timeline"][start_idx:end_idx]
            avg_energy = sum(t["audio_energy"] for t in timeline_slice) / max(1, len(timeline_slice))
        else:
            avg_energy = 0.5
        
        segment = SceneSegment(
            video_source_id=video.id,
            start_time_sec=peak["start_time"],
            end_time_sec=peak["end_time"],
            score_energy=avg_energy,
            score_change=peak["avg_score"],
        )
        db.add(segment)
        segments.append(segment)
    
    # If we don't have enough segments, add fallback segments
    if len(segments) < 5:
        window = max(duration / 8, 15.0)
        t = 0.0
        while t < duration and len(segments) < 10:
            # Check if this time is not already covered
            if not any(s.start_time_sec <= t <= s.end_time_sec for s in segments):
                segment = SceneSegment(
                    video_source_id=video.id,
                    start_time_sec=t,
                    end_time_sec=min(t + window, duration),
                    score_energy=0.5,
                    score_change=0.4,
                )
                db.add(segment)
                segments.append(segment)
            t += window
    
    db.commit()
    
    # Prepare metadata
    metadata = {
        "total_segments": len(segments),
        "analysis_type": "multi_modal",
        "audio_peaks_found": len(analysis["audio_peaks"]),
        "visual_peaks_found": len(analysis["visual_peaks"]),
        "viral_moments_found": len(analysis["viral_moments"]),
        "combined_timeline_length": len(analysis["combined_timeline"]),
    }
    
    logger.info("enhanced_seg.create_done", video_id=video.id, segments=len(segments))
    
    return segments, metadata


def get_segment_details(
    segment: SceneSegment,
    analysis: Dict[str, Any],
    transcripts: List[TranscriptSegment],
) -> Dict[str, Any]:
    """
    Get detailed information for a specific segment.
    """
    start = segment.start_time_sec
    end = segment.end_time_sec
    
    # Get transcript for this segment
    transcript_text = sentiment_analysis.get_transcript_for_time_range(
        transcripts, start, end
    )
    
    # Get timeline data for this segment
    timeline = analysis.get("combined_timeline", [])
    segment_timeline = [t for t in timeline if start <= t["time"] < end]
    
    if segment_timeline:
        avg_engagement = sum(t["engagement_score"] for t in segment_timeline) / len(segment_timeline)
        avg_audio = sum(t["audio_energy"] for t in segment_timeline) / len(segment_timeline)
        avg_visual = sum(t["visual_interest"] for t in segment_timeline) / len(segment_timeline)
    else:
        avg_engagement = 0.5
        avg_audio = 0.5
        avg_visual = 0.5
    
    # Analyze hook strength of opening
    hook_analysis = sentiment_analysis.analyze_text_for_hook_strength(transcript_text)
    
    return {
        "start_time": start,
        "end_time": end,
        "duration": end - start,
        "transcript": transcript_text,
        "avg_engagement": avg_engagement,
        "avg_audio_energy": avg_audio,
        "avg_visual_interest": avg_visual,
        "hook_strength": hook_analysis["hook_strength"],
        "hook_reasons": hook_analysis.get("reasons", []),
    }
