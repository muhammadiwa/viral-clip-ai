"""
Segmentation Service for Viral Clip Detection.

Combines multiple analysis signals to create intelligent scene segments:
- Audio energy and events
- Visual motion and scene cuts
- Transcript sentiment and hooks
- Engagement scoring

Also includes basic fallback segmentation using silence detection.
"""
from typing import Any, Dict, List, Optional, Tuple

import structlog
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import VideoSource, SceneSegment, TranscriptSegment
from app.services import audio_analysis, visual_analysis, sentiment_analysis, ai_vision_analysis
from app.services import utils

logger = structlog.get_logger()
settings = get_settings()


# =============================================================================
# BASIC SEGMENTATION (Fallback)
# =============================================================================

def _parse_silence(stderr: str, duration: float) -> List[SceneSegment]:
    """Parse ffmpeg silencedetect output to create segments."""
    silences = []
    for line in stderr.splitlines():
        if "silence_start" in line:
            try:
                silences.append(("start", float(line.strip().split("silence_start:")[1].strip())))
            except Exception:
                continue
        if "silence_end" in line:
            parts = line.strip().split("silence_end:")
            if len(parts) > 1:
                try:
                    ts = float(parts[1].split("|")[0].strip())
                    silences.append(("end", ts))
                except Exception:
                    continue
    
    silences_sorted = sorted([t for t in silences if isinstance(t[1], float)], key=lambda x: x[1])
    segments = []
    last = 0.0
    for typ, ts in silences_sorted:
        if typ == "start" and ts > last:
            segments.append((last, ts))
        if typ == "end":
            last = ts
    if last < duration:
        segments.append((last, duration))
    
    return [
        SceneSegment(
            video_source_id=None,
            start_time_sec=start,
            end_time_sec=end,
            score_energy=1.0,
            score_change=0.5,
        )
        for start, end in segments
        if end - start > 1.0
    ]


def detect_scenes_basic(db: Session, video: VideoSource) -> List[SceneSegment]:
    """
    Basic scene detection using ffmpeg silencedetect.
    Used as fallback when enhanced segmentation fails.
    """
    if not video.file_path:
        raise ValueError("Video file_path missing for scene detection")
    
    logger.info("segmentation.basic_start", video_id=video.id)
    duration = video.duration_seconds or utils.probe_duration(video.file_path) or 0.0
    db.query(SceneSegment).filter(SceneSegment.video_source_id == video.id).delete()

    cmd = [
        settings.ffmpeg_bin,
        "-i",
        video.file_path,
        "-af",
        "silencedetect=n=-30dB:d=0.6",
        "-f",
        "null",
        "-",
    ]
    code, _, err = utils.run_cmd(cmd)
    
    if code != 0:
        logger.warning("segmentation.ffmpeg_failed", error=err)
        scenes = []
    else:
        scenes = _parse_silence(err, duration)

    if not scenes:
        # Fallback: evenly sized segments
        window = max(duration / 5, 15.0) if duration else 30.0
        t = 0.0
        scenes = []
        while t < (duration or window * 3):
            start = t
            end = min(duration or t + window, t + window)
            scenes.append(
                SceneSegment(
                    video_source_id=None,
                    start_time_sec=start,
                    end_time_sec=end,
                    score_energy=0.8,
                    score_change=0.5,
                )
            )
            t = end

    for seg in scenes:
        seg.video_source_id = video.id
        db.add(seg)
    db.commit()
    
    logger.info("segmentation.basic_done", video_id=video.id, scenes=len(scenes))
    return scenes


# Legacy alias for backward compatibility
detect_scenes = detect_scenes_basic


# =============================================================================
# ENHANCED MULTI-MODAL SEGMENTATION
# =============================================================================

def analyze_video_comprehensive(
    video_path: str,
    duration: float,
    transcripts: List[TranscriptSegment],
    progress_callback: callable = None,
) -> Dict[str, Any]:
    """
    Perform comprehensive multi-modal analysis of a video.
    
    Uses a hybrid approach:
    - FFmpeg for audio energy and basic visual analysis
    - AI Vision (optional) for accurate face/emotion detection
    - Sentiment analysis for transcript hooks
    
    Returns:
    - audio_timeline: per-second audio analysis
    - visual_timeline: per-second visual analysis
    - ai_vision_timeline: per-second AI vision analysis (if enabled)
    - transcript_analysis: per-segment sentiment analysis
    - combined_timeline: merged engagement scores
    """
    logger.info(
        "segmentation.comprehensive_start", 
        video_path=video_path, 
        duration=duration,
        ai_vision_enabled=settings.ai_vision_enabled,
    )
    
    # 1. Audio Analysis (20% of work)
    if progress_callback:
        progress_callback(0.0, "Analyzing audio patterns...")
    audio_timeline = audio_analysis.calculate_energy_timeline(
        video_path, duration, window_size=1.0
    )
    if progress_callback:
        progress_callback(0.15, "Finding audio peaks...")
    audio_peaks = audio_analysis.find_audio_peaks(audio_timeline, min_duration=5.0, top_n=20)
    
    # 2. Basic Visual Analysis with FFmpeg (20% of work)
    if progress_callback:
        progress_callback(0.2, "Analyzing visual motion...")
    visual_timeline = visual_analysis.calculate_visual_timeline(
        video_path, duration, sample_interval=1.0
    )
    if progress_callback:
        progress_callback(0.35, "Finding visual peaks...")
    visual_peaks = visual_analysis.find_visual_peaks(visual_timeline, min_duration=5.0, top_n=20)
    
    # 3. AI Vision Analysis (30% of work) - if enabled
    ai_vision_result = None
    ai_vision_timeline = []
    ai_viral_moments = []
    ai_viral_segments = []
    
    if settings.ai_vision_enabled:
        if progress_callback:
            progress_callback(0.4, "Starting AI vision analysis...")
        
        def vision_progress(progress, message):
            if progress_callback:
                # Scale from 0.4 to 0.7
                scaled = 0.4 + (progress * 0.3)
                progress_callback(scaled, f"AI Vision: {message}")
        
        try:
            # Convert transcripts to dict format for AI Vision
            transcript_dicts = [
                {"start_time_sec": t.start_time_sec, "end_time_sec": t.end_time_sec, "text": t.text}
                for t in transcripts
            ] if transcripts else []
            
            ai_vision_result = ai_vision_analysis.analyze_video_with_vision(
                video_path,
                duration,
                progress_callback=vision_progress,
                transcripts=transcript_dicts,  # Pass transcripts for context
            )
            ai_vision_timeline = ai_vision_result.get("timeline", [])
            ai_viral_moments = ai_vision_result.get("viral_moments", [])
            ai_viral_segments = ai_vision_result.get("viral_segments", [])
            logger.info(
                "segmentation.ai_vision_done",
                viral_segments=len(ai_viral_segments),
                viral_moments=len(ai_viral_moments),
            )
        except Exception as e:
            logger.error("segmentation.ai_vision_failed", error=str(e))
            ai_vision_result = None
    else:
        if progress_callback:
            progress_callback(0.7, "AI Vision disabled, skipping...")
    
    # 4. Transcript/Sentiment Analysis (15% of work)
    if progress_callback:
        progress_callback(0.75, "Analyzing transcript sentiment...")
    transcript_analysis = sentiment_analysis.analyze_transcript_segments(transcripts)
    if progress_callback:
        progress_callback(0.85, "Finding viral moments from transcript...")
    viral_moments = sentiment_analysis.find_viral_moments_from_transcript(
        transcript_analysis, min_score=0.3
    )
    
    # 5. Combine into unified timeline (15% of work)
    if progress_callback:
        progress_callback(0.9, "Merging all analysis results...")
    combined_timeline = _merge_timelines_enhanced(
        audio_timeline, 
        visual_timeline, 
        ai_vision_timeline,
        transcript_analysis, 
        duration
    )
    
    # Merge viral moments from AI vision with transcript viral moments
    all_viral_moments = viral_moments.copy()
    for ai_moment in ai_viral_moments:
        # Add AI vision moments with adjusted format
        all_viral_moments.append({
            "start_time": ai_moment["timestamp"],
            "end_time": ai_moment["timestamp"] + 5.0,  # Assume 5 second window
            "text": "",
            "viral_potential": ai_moment["score"],
            "reason": ", ".join(ai_moment.get("reasons", [])),
            "source": "ai_vision",
            "emotions": ai_moment.get("emotions", []),
            "indicators": ai_moment.get("indicators", []),
        })
    
    # Sort by viral potential
    all_viral_moments.sort(key=lambda x: x.get("viral_potential", 0), reverse=True)
    
    if progress_callback:
        progress_callback(1.0, "Analysis complete")
    
    logger.info(
        "segmentation.comprehensive_done",
        audio_samples=len(audio_timeline),
        visual_samples=len(visual_timeline),
        ai_vision_samples=len(ai_vision_timeline),
        transcript_segments=len(transcript_analysis),
        total_viral_moments=len(all_viral_moments),
    )
    
    return {
        "audio_timeline": audio_timeline,
        "visual_timeline": visual_timeline,
        "ai_vision_timeline": ai_vision_timeline,
        "ai_vision_summary": ai_vision_result.get("summary") if ai_vision_result else None,
        "ai_viral_segments": ai_viral_segments,  # NEW: Full segment analysis with reasoning
        "transcript_analysis": transcript_analysis,
        "combined_timeline": combined_timeline,
        "audio_peaks": audio_peaks,
        "visual_peaks": visual_peaks,
        "viral_moments": all_viral_moments,
        "ai_vision_enabled": settings.ai_vision_enabled and ai_vision_result is not None,
    }


def _merge_timelines(
    audio_timeline: List[Dict[str, Any]],
    visual_timeline: List[Dict[str, Any]],
    transcript_analysis: List[Dict[str, Any]],
    duration: float,
) -> List[Dict[str, Any]]:
    """Merge audio, visual, and transcript analysis into a single timeline (legacy)."""
    return _merge_timelines_enhanced(
        audio_timeline, visual_timeline, [], transcript_analysis, duration
    )


def _merge_timelines_enhanced(
    audio_timeline: List[Dict[str, Any]],
    visual_timeline: List[Dict[str, Any]],
    ai_vision_timeline: List[Dict[str, Any]],
    transcript_analysis: List[Dict[str, Any]],
    duration: float,
) -> List[Dict[str, Any]]:
    """
    Merge audio, visual, AI vision, and transcript analysis into a single timeline.
    
    When AI Vision is available, it provides much more accurate:
    - Face detection (real vs heuristic)
    - Emotion detection
    - Scene understanding
    - Engagement indicators
    
    Weights are adjusted based on AI Vision availability.
    """
    audio_lookup = {int(a["time"]): a for a in audio_timeline}
    visual_lookup = {int(v["time"]): v for v in visual_timeline}
    ai_vision_lookup = {int(v["time"]): v for v in ai_vision_timeline}
    
    has_ai_vision = len(ai_vision_timeline) > 0
    
    def get_transcript_score(t: float) -> Tuple[float, str]:
        for seg in transcript_analysis:
            if seg["start_time"] <= t < seg["end_time"]:
                return seg["viral_potential"], seg["sentiment"]["emotion"]
        return 0.3, "neutral"
    
    combined = []
    t = 0.0
    
    while t < duration:
        t_int = int(t)
        
        # Audio data
        audio = audio_lookup.get(t_int, {})
        audio_energy = audio.get("energy", 0.5)
        audio_excitement = audio.get("excitement_score", 0.5)
        
        # Basic visual data (FFmpeg)
        visual = visual_lookup.get(t_int, {})
        visual_interest_ffmpeg = visual.get("visual_interest", 0.5)
        motion = visual.get("motion_score", 0.5)
        face_ffmpeg = visual.get("face_likelihood", 0.5)
        
        # AI Vision data (if available)
        ai_vision = ai_vision_lookup.get(t_int, {})
        
        # Transcript data
        transcript_score, emotion = get_transcript_score(t)
        
        if has_ai_vision and ai_vision.get("ai_analyzed", False):
            # Use AI Vision data for face and visual interest
            face_count = ai_vision.get("face_count", 0)
            face_likelihood = min(1.0, face_count * 0.5) if face_count > 0 else 0.2
            
            # Get detailed viral metrics from AI Vision
            visual_impact = ai_vision.get("visual_impact", 0.5)
            emotional_appeal = ai_vision.get("emotional_appeal", 0.5)
            hook_potential = ai_vision.get("hook_potential", 0.5)
            action_level = ai_vision.get("action_level", "medium")
            
            # Boost for emotions
            face_emotions = ai_vision.get("face_emotions", [])
            emotion_boost = 0.0
            viral_emotions = {"happy", "surprised", "shocked", "excited"}
            if any(em in viral_emotions for em in face_emotions):
                emotion_boost = 0.1
            
            # AI visual interest (combined score)
            ai_visual_interest = ai_vision.get("visual_interest_score", 0.5)
            
            # Engagement indicators boost
            indicators = ai_vision.get("engagement_indicators", [])
            indicator_boost = min(0.15, len(indicators) * 0.03)
            
            # Action level boost
            action_boost = 0.0
            if action_level == "high":
                action_boost = 0.1
            elif action_level == "medium":
                action_boost = 0.05
            
            # Combined visual interest (blend AI and FFmpeg)
            visual_interest = (ai_visual_interest * 0.7 + visual_interest_ffmpeg * 0.3)
            
            # Enhanced engagement score with AI Vision viral metrics
            # Weights: Audio 20%, AI Vision 50%, Face/Motion 10%, Transcript 15%, Bonuses 5%
            engagement_score = (
                # Audio signals (20%)
                audio_energy * 0.10 +
                audio_excitement * 0.10 +
                # AI Vision viral metrics (50%)
                visual_impact * 0.15 +
                emotional_appeal * 0.15 +
                hook_potential * 0.20 +
                # Face/motion (10%)
                face_likelihood * 0.05 +
                motion * 0.05 +
                # Transcript (15%)
                transcript_score * 0.15 +
                # Bonuses (5%)
                emotion_boost +
                indicator_boost +
                action_boost
            )
            
            combined.append({
                "time": t,
                "audio_energy": audio_energy,
                "audio_excitement": audio_excitement,
                "visual_interest": visual_interest,
                "motion": motion,
                "face_likelihood": face_likelihood,
                "face_count": face_count,
                "face_emotions": face_emotions,
                "engagement_indicators": indicators,
                "transcript_score": transcript_score,
                "emotion": emotion,
                "engagement_score": min(1.0, engagement_score),
                # Detailed viral metrics
                "visual_impact": visual_impact,
                "emotional_appeal": emotional_appeal,
                "hook_potential": hook_potential,
                "action_level": action_level,
                "ai_vision_used": True,
            })
        else:
            # Fallback to FFmpeg-only analysis
            engagement_score = (
                audio_energy * 0.15 +
                audio_excitement * 0.15 +
                visual_interest_ffmpeg * 0.20 +
                motion * 0.10 +
                face_ffmpeg * 0.15 +
                transcript_score * 0.25
            )
            
            combined.append({
                "time": t,
                "audio_energy": audio_energy,
                "audio_excitement": audio_excitement,
                "visual_interest": visual_interest_ffmpeg,
                "motion": motion,
                "face_likelihood": face_ffmpeg,
                "face_count": 0,
                "face_emotions": [],
                "engagement_indicators": [],
                "transcript_score": transcript_score,
                "emotion": emotion,
                "engagement_score": engagement_score,
                "ai_vision_used": False,
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
    
    Returns optimal clip candidates with start_time, end_time, engagement_score, etc.
    """
    if not combined_timeline:
        return []
    
    all_scores = [c["engagement_score"] for c in combined_timeline]
    mean_score = sum(all_scores) / len(all_scores)
    threshold = max(0.4, mean_score * 1.2)
    
    peaks = []
    i = 0
    
    while i < len(combined_timeline):
        if combined_timeline[i]["engagement_score"] >= threshold:
            start_idx = i
            peak_score = combined_timeline[i]["engagement_score"]
            scores_sum = combined_timeline[i]["engagement_score"]
            
            while i < len(combined_timeline) and combined_timeline[i]["engagement_score"] >= threshold * 0.7:
                peak_score = max(peak_score, combined_timeline[i]["engagement_score"])
                scores_sum += combined_timeline[i]["engagement_score"]
                i += 1
            
            end_idx = i
            duration = combined_timeline[end_idx - 1]["time"] - combined_timeline[start_idx]["time"]
            
            if min_duration <= duration <= max_duration:
                segment_data = combined_timeline[start_idx:end_idx]
                avg_score = scores_sum / len(segment_data)
                
                avg_audio = sum(s["audio_excitement"] for s in segment_data) / len(segment_data)
                avg_visual = sum(s["visual_interest"] for s in segment_data) / len(segment_data)
                avg_transcript = sum(s["transcript_score"] for s in segment_data) / len(segment_data)
                
                if avg_audio >= avg_visual and avg_audio >= avg_transcript:
                    dominant = "audio_excitement"
                elif avg_visual >= avg_transcript:
                    dominant = "visual_interest"
                else:
                    dominant = "compelling_content"
                
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
    
    peaks.sort(key=lambda x: x["avg_score"], reverse=True)
    return peaks[:top_n]



def create_enhanced_segments(
    db: Session,
    video: VideoSource,
    transcripts: List[TranscriptSegment],
    progress_callback: callable = None,
) -> Tuple[List[SceneSegment], Dict[str, Any]]:
    """
    Create enhanced scene segments using multi-modal analysis.
    
    Returns:
    - List of SceneSegment objects
    - Analysis metadata
    """
    if not video.file_path:
        raise ValueError("Video file_path missing")
    
    duration = video.duration_seconds or utils.probe_duration(video.file_path) or 0.0
    if duration <= 0:
        raise ValueError("Cannot determine video duration")
    
    logger.info("segmentation.enhanced_start", video_id=video.id, duration=duration)
    
    def analysis_progress(progress: float, message: str):
        if progress_callback:
            progress_callback(progress * 0.8, message)
    
    analysis = analyze_video_comprehensive(video.file_path, duration, transcripts, analysis_progress)
    
    if progress_callback:
        progress_callback(0.8, "Finding engagement peaks...")
    
    peaks = find_engagement_peaks(
        analysis["combined_timeline"],
        min_duration=10.0,
        max_duration=90.0,
        top_n=15,
    )
    
    if progress_callback:
        progress_callback(0.85, "Merging peak data...")
    
    all_peak_times = set()
    for peak in peaks:
        all_peak_times.add((peak["start_time"], peak["end_time"]))
    
    for ap in analysis["audio_peaks"][:10]:
        if not any(abs(ap["start_time"] - p[0]) < 5 for p in all_peak_times):
            all_peak_times.add((ap["start_time"], ap["end_time"]))
    
    for vp in analysis["visual_peaks"][:10]:
        if not any(abs(vp["start_time"] - p[0]) < 5 for p in all_peak_times):
            all_peak_times.add((vp["start_time"], vp["end_time"]))
    
    if progress_callback:
        progress_callback(0.9, "Creating scene segments...")
    
    db.query(SceneSegment).filter(SceneSegment.video_source_id == video.id).delete()
    
    segments = []
    for peak in peaks:
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
    
    # Fallback if not enough segments
    if len(segments) < 5:
        window = max(duration / 8, 15.0)
        t = 0.0
        while t < duration and len(segments) < 10:
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
    
    if progress_callback:
        progress_callback(1.0, f"Created {len(segments)} segments")
    
    metadata = {
        "total_segments": len(segments),
        "analysis_type": "multi_modal",
        "audio_peaks_found": len(analysis["audio_peaks"]),
        "visual_peaks_found": len(analysis["visual_peaks"]),
        "viral_moments_found": len(analysis["viral_moments"]),
        "combined_timeline_length": len(analysis["combined_timeline"]),
    }
    
    logger.info("segmentation.enhanced_done", video_id=video.id, segments=len(segments))
    return segments, metadata


def get_segment_details(
    segment: SceneSegment,
    analysis: Dict[str, Any],
    transcripts: List[TranscriptSegment],
) -> Dict[str, Any]:
    """Get detailed information for a specific segment."""
    start = segment.start_time_sec
    end = segment.end_time_sec
    
    transcript_text = sentiment_analysis.get_transcript_for_time_range(transcripts, start, end)
    
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
