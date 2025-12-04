"""
Virality Service for Viral Clip Generation.

Multi-modal analysis with:
- Audio, visual, transcript analysis
- Data-driven engagement scoring
- Intelligent clip selection
- Enhanced LLM prompts with real data
"""
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import structlog
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    ClipBatch,
    Clip,
    ClipLLMContext,
    TranscriptSegment,
    SceneSegment,
    AIUsageLog,
    VideoAnalysis,
)
from app.models.analysis import ClipAnalysis
from app.services import utils
from app.services import (
    audio_analysis,
    visual_analysis,
    sentiment_analysis,
    segmentation,
    engagement_scoring,
)

logger = structlog.get_logger()
settings = get_settings()

# In-memory cache
_llm_cache: dict[str, dict] = {}


def _target_duration(preset: str) -> Tuple[float, float]:
    """Get min and max duration for a preset."""
    mapping = {
        "0_30": (10.0, 30.0),
        "30_60": (30.0, 60.0),
        "60_90": (60.0, 90.0),
        "60_180": (60.0, 180.0),
        "auto_0_60": (15.0, 60.0),
        "0_90": (30.0, 90.0),
    }
    return mapping.get(preset, (15.0, 60.0))


def _compute_cache_key(video_source_id: int, config: dict, transcript_hash: str) -> str:
    """Generate cache key."""
    config_str = json.dumps({
        "video_type": config.get("video_type"),
        "aspect_ratio": config.get("aspect_ratio"),
        "clip_length_preset": config.get("clip_length_preset"),
        "processing_timeframe_start": config.get("processing_timeframe_start"),
        "processing_timeframe_end": config.get("processing_timeframe_end"),
    }, sort_keys=True)
    key_content = f"{video_source_id}:{config_str}:{transcript_hash}:v2"
    return hashlib.sha256(key_content.encode()).hexdigest()[:32]


def _get_cached_response(cache_key: str) -> Optional[dict]:
    cached = _llm_cache.get(cache_key)
    if cached:
        logger.info("virality.cache_hit", cache_key=cache_key)
        return cached
    return None


def _set_cached_response(cache_key: str, data: dict) -> None:
    _llm_cache[cache_key] = data
    if len(_llm_cache) > 100:
        oldest_key = next(iter(_llm_cache))
        del _llm_cache[oldest_key]
    logger.info("virality.cache_set", cache_key=cache_key)


def clear_llm_cache() -> None:
    _llm_cache.clear()
    logger.info("virality.cache_cleared")


def _enrich_candidates_with_ai_segments(
    engagement_peaks: List[Dict[str, Any]],
    transcripts: List,
    ai_viral_segments: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Enrich engagement peaks with transcript and AI Vision segment data.
    
    This is a shared function used by both db_analysis and fresh analysis paths
    to avoid code duplication.
    
    Args:
        engagement_peaks: List of peaks from find_engagement_peaks
        transcripts: List of TranscriptSegment objects
        ai_viral_segments: List of AI viral segment analysis results
    
    Returns:
        List of enriched clip candidates
    """
    # Create lookup for AI viral segments by time range
    def find_ai_segment(start: float, end: float) -> Optional[Dict]:
        for seg in ai_viral_segments:
            seg_start = seg.get("start_time", 0)
            seg_end = seg.get("end_time", 0)
            # Check for overlap
            if seg_end > start and seg_start < end:
                return seg
        return None
    
    clip_candidates = []
    
    for peak in engagement_peaks:
        transcript_text = sentiment_analysis.get_transcript_for_time_range(
            transcripts, peak["start_time"], peak["end_time"]
        )
        hook_analysis = sentiment_analysis.analyze_text_for_hook_strength(transcript_text)
        
        # Get AI Vision segment data (format with reasoning)
        ai_segment = find_ai_segment(peak["start_time"], peak["end_time"])
        
        # Default values
        ai_reasoning = ""
        categories = []
        engagement_factors = []
        ai_hook_potential = 0.5
        is_viral_candidate = False
        ai_viral_score = 0.5
        action_level = "medium"
        
        if ai_segment:
            ai_analysis = ai_segment.get("ai_analysis", {})
            ai_reasoning = ai_analysis.get("reasoning", "")
            categories = ai_analysis.get("categories", [])
            engagement_factors = ai_analysis.get("engagement_factors", [])
            ai_hook_potential = ai_analysis.get("hook_potential", 0.5)
            is_viral_candidate = ai_segment.get("is_viral_candidate", False)
            ai_viral_score = ai_segment.get("viral_score", 0.5)
            action_level = ai_segment.get("action_level", "medium")
        
        candidate = {
            **peak,
            "transcript_preview": transcript_text[:300],
            "transcript_full": transcript_text,
            "hook_strength": hook_analysis["hook_strength"],
            "hook_reasons": hook_analysis.get("reasons", []),
            "engagement_score": peak["avg_score"],
            # AI Vision segment data with reasoning
            "ai_reasoning": ai_reasoning,
            "categories": categories,
            "engagement_factors": engagement_factors,
            "hook_potential": ai_hook_potential,
            "is_viral_candidate": is_viral_candidate,
            "viral_score": ai_viral_score,
            "action_level": action_level,
        }
        clip_candidates.append(candidate)
    
    clip_candidates.sort(key=lambda x: x["engagement_score"], reverse=True)
    return clip_candidates


def _build_enhanced_prompt(
    config: dict,
    clip_candidates: List[Dict[str, Any]],
    include_specific_moments: str = "",
) -> str:
    """Build an enhanced prompt with real engagement data."""
    min_dur, max_dur = _target_duration(config.get("clip_length_preset", "30_60"))
    
    candidates_text = []
    for i, clip in enumerate(clip_candidates[:15], 1):
        # Build AI Vision info - NEW FORMAT with reasoning
        ai_analysis_info = ""
        
        # Check for new format with reasoning and categories
        if clip.get("ai_reasoning") or clip.get("categories"):
            reasoning = clip.get("ai_reasoning", "")
            categories = clip.get("categories", [])
            engagement_factors = clip.get("engagement_factors", [])
            
            ai_analysis_info = f"""
- AI ANALYSIS:
  • Reasoning: {reasoning[:200]}
  • Categories: {', '.join(categories[:5]) if categories else 'none'}
  • Engagement Factors: {', '.join(engagement_factors[:5]) if engagement_factors else 'none'}
  • Hook Potential: {clip.get('hook_potential', 0.5):.2f}
  • Is Viral Candidate: {clip.get('is_viral_candidate', False)}"""
        
        # Fallback to old format
        elif clip.get("visual_impact") or clip.get("engagement_indicators"):
            indicators = clip.get("engagement_indicators", [])
            ai_analysis_info = f"""
- AI ANALYSIS:
  • Hook Potential: {clip.get('hook_potential', 0.5):.2f}
  • Engagement Indicators: {', '.join(indicators[:5]) if indicators else 'none'}"""
        
        candidates_text.append(f"""
Candidate #{i}:
- Time: {clip['start_time']:.1f}s - {clip['end_time']:.1f}s ({clip['duration']:.1f}s)
- Viral Score: {clip.get('viral_score', clip.get('engagement_score', 0.5)):.2f}/1.0
- Dominant Signal: {clip.get('dominant_signal', 'mixed')}
- Audio Energy: {clip.get('avg_audio_energy', 0.5):.2f}
- Hook Strength: {clip.get('hook_strength', 0.5):.2f}{ai_analysis_info}
- Transcript Preview: "{clip.get('transcript_preview', '')[:300]}..."
""")
    
    specific_moments_instruction = ""
    if include_specific_moments and include_specific_moments.strip():
        specific_moments_instruction = f"""
IMPORTANT - USER REQUESTED SPECIFIC MOMENTS:
The user wants clips that include these specific moments: "{include_specific_moments}"
Parse the timestamps mentioned (e.g., "02:10" = 130 seconds, "10:30" = 630 seconds).
PRIORITIZE creating clips that contain these requested moments.
"""
    
    prompt = f"""You are an expert viral video editor. Analyze the content and auto-detect the video type (podcast, interview, tutorial, vlog, gaming, etc.).

TASK: Select and refine the best viral clips from the following pre-analyzed candidates.
Target duration: {min_dur:.0f}-{max_dur:.0f} seconds per clip.
Aspect ratio: {config.get('aspect_ratio', '9:16')}
{specific_moments_instruction}
ENGAGEMENT DATA (already analyzed by AI):
{chr(10).join(candidates_text)}

SELECTION CRITERIA:
1. HOOK (35%): First 3 seconds must grab attention. Look for questions, surprising statements, or emotional hooks.
2. FLOW (20%): Smooth pacing, no awkward cuts. Should feel complete.
3. VALUE (25%): Delivers entertainment, education, or emotional impact.
4. TREND (20%): Relatable, shareable, conversation-starting.

RULES:
- Prioritize candidates with engagement_score > 0.5
- Adjust start/end times to ensure clean sentence boundaries
- The opening hook is CRITICAL - the first sentence makes or breaks virality
- Each clip MUST be between {min_dur:.0f} and {max_dur:.0f} seconds
- If user requested specific moments, MUST include at least 2-3 clips from those timestamps

TITLE & DESCRIPTION GUIDELINES:
- Title: Use power words (INSANE, SHOCKING, UNBELIEVABLE, EPIC, etc.)
- Title: Create curiosity gap ("You won't believe what happens next")
- Title: Use numbers when relevant ("3 seconds that changed everything")
- Title: Keep it under 60 characters
- Description: Write like a viral TikTok caption
- Description: Include emotional hooks and call-to-action feel
- Description: 100-150 characters, engaging and shareable

Return JSON with key 'clips' containing 8-12 items. Each clip:
{{
    "start_sec": float,
    "end_sec": float,
    "title": "VIRAL catchy title max 60 chars - use power words!",
    "description": "Engaging social media caption 100-150 chars with hooks",
    "viral_score": float (0-10 based on criteria above),
    "detected_video_type": "podcast/interview/tutorial/vlog/gaming/other",
    "grades": {{
        "hook": "A/B/C/D",
        "flow": "A/B/C/D", 
        "value": "A/B/C/D",
        "trend": "A/B/C/D"
    }},
    "hook_text": "The exact opening line that grabs attention",
    "hashtags": ["viral", "trending", "mustwatch"]
}}

Respond ONLY with valid JSON, no commentary."""
    
    return prompt


def _parse_llm_response(resp_text: str) -> List[dict]:
    """Parse LLM response to extract clips."""
    if not resp_text:
        return []
    
    cleaned = resp_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:cleaned.rfind("```")].strip()
    
    if not cleaned:
        return []
    
    if cleaned[0] not in "[{":
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start:end + 1]
    
    try:
        data = json.loads(cleaned)
    except Exception as e:
        logger.error("virality.parse_failed", error=str(e), preview=cleaned[:200])
        return []
    
    if isinstance(data, dict):
        clips = data.get("clips", [])
        return clips if isinstance(clips, list) else []
    if isinstance(data, list):
        return data
    return []


def _extract_response_text(response) -> str:
    """Extract text from OpenAI response."""
    if response is None:
        return ""
    
    chunks = []
    
    output = getattr(response, "output", None)
    if output:
        for item in output:
            for content in getattr(item, "content", []) or []:
                text_obj = getattr(content, "text", None)
                if text_obj and getattr(text_obj, "value", None):
                    chunks.append(text_obj.value)
                elif getattr(content, "value", None):
                    chunks.append(content.value)
    
    if not chunks:
        textual = getattr(response, "output_text", None)
        if textual:
            chunks.append(textual)
    
    if not chunks and getattr(response, "choices", None):
        choice0 = response.choices[0]
        message = getattr(choice0, "message", None)
        if message:
            content = getattr(message, "content", None)
            if isinstance(content, str):
                chunks.append(content)
            elif isinstance(content, list):
                for part in content:
                    text_val = part.get("text") if isinstance(part, dict) else getattr(part, "text", None)
                    if text_val:
                        chunks.append(str(text_val))
    
    return "\n".join([c for c in chunks if c]).strip()


def generate_clips_for_batch(
    db: Session,
    batch: ClipBatch,
    config: dict,
    progress_callback: callable = None,
) -> Tuple[List[Clip], dict]:
    """
    Generate viral clips using enhanced multi-modal analysis.
    
    Args:
        db: Database session
        batch: ClipBatch to generate clips for
        config: Configuration dict with aspect_ratio, clip_length_preset, etc.
        progress_callback: Optional callback(step, progress, message) for progress updates
    """
    logger.info("virality.start", batch_id=batch.id)
    
    video = batch.video
    if not video.file_path:
        raise ValueError("Video file_path missing")
    
    duration = video.duration_seconds or utils.probe_duration(video.file_path) or 0.0
    timeframe_start = config.get("processing_timeframe_start") or 0.0
    timeframe_end = config.get("processing_timeframe_end") or duration
    
    # Get transcripts
    transcripts = (
        db.query(TranscriptSegment)
        .filter(TranscriptSegment.video_source_id == batch.video_source_id)
        .order_by(TranscriptSegment.start_time_sec)
        .all()
    )
    
    transcripts = [t for t in transcripts 
                   if t.start_time_sec >= timeframe_start and t.end_time_sec <= timeframe_end]
    
    # Clear existing clips
    existing_clip_ids = [c.id for c in db.query(Clip).filter(Clip.clip_batch_id == batch.id).all()]
    if existing_clip_ids:
        db.query(ClipLLMContext).filter(ClipLLMContext.clip_id.in_(existing_clip_ids)).delete(
            synchronize_session=False
        )
    db.query(Clip).filter(Clip.clip_batch_id == batch.id).delete(synchronize_session=False)
    
    # Generate cache key
    transcript_hash = hashlib.md5(
        " ".join(t.text for t in transcripts).encode()
    ).hexdigest()[:16]
    cache_key = _compute_cache_key(batch.video_source_id, config, transcript_hash)
    
    # Check database for existing analysis first
    existing_analysis = db.query(VideoAnalysis).filter(
        VideoAnalysis.video_source_id == batch.video_source_id
    ).first()
    
    # Check in-memory cache
    cached = _get_cached_response(cache_key)
    analysis_data = None
    clip_candidates = []
    llm_clips = []
    response_text = ""
    cache_used = False
    db_analysis_used = False
    
    if cached:
        llm_clips = cached.get("llm_clips", [])
        analysis_data = cached.get("analysis_data")
        response_text = cached.get("response_text", "")
        cache_used = True
        logger.info("virality.using_memory_cache", batch_id=batch.id)
        if progress_callback:
            progress_callback("analyze", 1.0, "Using cached analysis")
    elif existing_analysis and existing_analysis.combined_timeline_json:
        # Load from database - NO RE-ANALYSIS needed!
        logger.info("virality.using_db_analysis", batch_id=batch.id, analysis_id=existing_analysis.id)
        analysis_data = {
            "audio_timeline": existing_analysis.audio_timeline_json or [],
            "visual_timeline": existing_analysis.visual_timeline_json or [],
            "combined_timeline": existing_analysis.combined_timeline_json or [],
            "audio_peaks": existing_analysis.audio_peaks_json or [],
            "visual_peaks": existing_analysis.visual_peaks_json or [],
            "viral_moments": existing_analysis.engagement_peaks_json or [],
            "ai_viral_segments": existing_analysis.ai_viral_segments_json or [],  # NEW: Load AI viral segments
            "transcript_analysis": [],
        }
        db_analysis_used = True
        if progress_callback:
            progress_callback("analyze", 1.0, "Using saved analysis from database")
        
        # Still need to find peaks and do LLM selection
        if progress_callback:
            progress_callback("find_peaks", 0.1, "Finding engagement peaks...")
        
        min_dur, max_dur = _target_duration(config.get("clip_length_preset", "30_60"))
        
        engagement_peaks = segmentation.find_engagement_peaks(
            analysis_data["combined_timeline"],
            min_duration=min_dur,
            max_duration=max_dur,
            top_n=15,
        )
        
        # Enrich candidates using shared helper function
        ai_viral_segments = analysis_data.get("ai_viral_segments", [])
        clip_candidates = _enrich_candidates_with_ai_segments(
            engagement_peaks, transcripts, ai_viral_segments
        )
        
        if progress_callback:
            progress_callback("find_peaks", 1.0, f"Found {len(clip_candidates)} candidates")
        
        # Use LLM for final selection
        if progress_callback:
            progress_callback("llm_select", 0.1, "AI selecting best clips...")
        
        client = utils.get_openai_client()
        
        if client and clip_candidates:
            try:
                prompt = _build_enhanced_prompt(
                    config, 
                    clip_candidates, 
                    config.get("include_specific_moments", "")
                )
                
                if progress_callback:
                    progress_callback("llm_select", 0.3, "Sending to AI...")
                
                response = client.responses.create(
                    model=settings.openai_responses_model,
                    input=[
                        {
                            "role": "system",
                            "content": [{"type": "input_text", "text": "You are an expert viral video editor. Respond ONLY with valid JSON."}],
                        },
                        {"role": "user", "content": [{"type": "input_text", "text": prompt}]},
                    ],
                    temperature=0.4,
                )
                
                if progress_callback:
                    progress_callback("llm_select", 0.8, "Processing AI response...")
                
                response_text = _extract_response_text(response)
                llm_clips = _parse_llm_response(response_text)
                
                usage = getattr(response, "usage", None)
                if usage:
                    db.add(AIUsageLog(
                        user_id=video.user_id,
                        provider="openai",
                        model=settings.openai_responses_model,
                        tokens_input=getattr(usage, "prompt_tokens", 0) or 0,
                        tokens_output=getattr(usage, "completion_tokens", 0) or 0,
                    ))
                
            except Exception as exc:
                logger.error("virality.llm_failed", error=str(exc))
                llm_clips = []
        
        # Cache results
        if llm_clips or clip_candidates:
            _set_cached_response(cache_key, {
                "llm_clips": llm_clips,
                "clip_candidates": [
                    {k: v for k, v in c.items() if k != "transcript_full"} 
                    for c in clip_candidates
                ],
                "response_text": response_text[:2000],
                "analysis_data": {
                    "audio_peaks_count": len(analysis_data.get("audio_peaks", [])),
                    "visual_peaks_count": len(analysis_data.get("visual_peaks", [])),
                    "viral_moments_count": len(analysis_data.get("viral_moments", [])),
                },
            })
    
    if not cached and not db_analysis_used:
        # Perform comprehensive analysis (only if no saved analysis)
        logger.info("virality.analyzing_fresh", batch_id=batch.id)
        if progress_callback:
            progress_callback("analyze", 0.1, "Analyzing video content...")
        
        analysis_data = segmentation.analyze_video_comprehensive(
            video.file_path, duration, transcripts
        )
        
        if progress_callback:
            progress_callback("analyze", 0.8, "Analysis complete")
        
        # Find engagement peaks
        if progress_callback:
            progress_callback("find_peaks", 0.1, "Finding engagement peaks...")
        
        min_dur, max_dur = _target_duration(config.get("clip_length_preset", "30_60"))
        
        engagement_peaks = segmentation.find_engagement_peaks(
            analysis_data["combined_timeline"],
            min_duration=min_dur,
            max_duration=max_dur,
            top_n=15,
        )
        
        # Enrich candidates using shared helper function
        ai_viral_segments = analysis_data.get("ai_viral_segments", [])
        clip_candidates = _enrich_candidates_with_ai_segments(
            engagement_peaks, transcripts, ai_viral_segments
        )
        
        if progress_callback:
            progress_callback("find_peaks", 1.0, f"Found {len(clip_candidates)} candidates")
        
        # Use LLM for final selection
        if progress_callback:
            progress_callback("llm_select", 0.1, "AI selecting best clips...")
        
        client = utils.get_openai_client()
        
        if client and clip_candidates:
            try:
                prompt = _build_enhanced_prompt(
                    config, 
                    clip_candidates, 
                    config.get("include_specific_moments", "")
                )
                
                if progress_callback:
                    progress_callback("llm_select", 0.3, "Sending to AI...")
                
                response = client.responses.create(
                    model=settings.openai_responses_model,
                    input=[
                        {
                            "role": "system",
                            "content": [{"type": "input_text", "text": "You are an expert viral video editor. Respond ONLY with valid JSON."}],
                        },
                        {"role": "user", "content": [{"type": "input_text", "text": prompt}]},
                    ],
                    temperature=0.4,
                )
                
                if progress_callback:
                    progress_callback("llm_select", 0.8, "Processing AI response...")
                
                response_text = _extract_response_text(response)
                llm_clips = _parse_llm_response(response_text)
                
                usage = getattr(response, "usage", None)
                if usage:
                    db.add(AIUsageLog(
                        user_id=video.user_id,
                        provider="openai",
                        model=settings.openai_responses_model,
                        tokens_input=getattr(usage, "prompt_tokens", 0) or 0,
                        tokens_output=getattr(usage, "completion_tokens", 0) or 0,
                    ))
                
            except Exception as exc:
                logger.error("virality.llm_failed", error=str(exc))
                llm_clips = []
        
        # Cache results
        if llm_clips or clip_candidates:
            _set_cached_response(cache_key, {
                "llm_clips": llm_clips,
                "clip_candidates": [
                    {k: v for k, v in c.items() if k != "transcript_full"} 
                    for c in clip_candidates
                ],
                "response_text": response_text[:2000],
                "analysis_data": {
                    "audio_peaks_count": len(analysis_data.get("audio_peaks", [])),
                    "visual_peaks_count": len(analysis_data.get("visual_peaks", [])),
                    "viral_moments_count": len(analysis_data.get("viral_moments", [])),
                },
            })
    
    if progress_callback:
        progress_callback("llm_select", 1.0, "AI selection complete")
    
    # Create clips from LLM response or fallback
    if progress_callback:
        progress_callback("score_clips", 0.1, "Scoring clips...")
    
    clips = []
    
    if llm_clips:
        clips = _create_clips_from_llm(
            db, batch, llm_clips, transcripts, analysis_data, 
            config, timeframe_start, timeframe_end
        )
    
    # Fallback: use clip candidates directly if LLM failed
    if not clips and clip_candidates:
        logger.warning("virality.using_fallback", batch_id=batch.id)
        clips = _create_clips_from_candidates(
            db, batch, clip_candidates, analysis_data, config
        )
    
    # Ultimate fallback: create clips from transcript segments
    if not clips and transcripts:
        logger.warning("virality.using_transcript_fallback", batch_id=batch.id)
        clips = _create_clips_from_transcripts(
            db, batch, transcripts, config, timeframe_start
        )
    
    db.commit()
    
    # Generate thumbnails and store context
    _generate_thumbnails_and_context(
        db, clips, video, config, clip_candidates, llm_clips, response_text, analysis_data
    )
    
    # Save detailed clip analysis
    _save_clip_analyses(db, clips, analysis_data, llm_clips)
    
    batch.status = "ready" if clips else "failed"
    db.commit()
    
    logger.info(
        "virality.done", 
        batch_id=batch.id, 
        clips=len(clips), 
        llm_used=bool(llm_clips), 
        cache_used=cache_used,
        db_analysis_used=db_analysis_used,
    )
    
    return clips, {
        "llm_used": bool(llm_clips),
        "cache_used": cache_used,
        "db_analysis_used": db_analysis_used,
        "clip_count": len(clips),
        "candidates_analyzed": len(clip_candidates),
        "analysis_type": "multi_modal_enhanced",
    }


def _create_clips_from_llm(
    db: Session, batch: ClipBatch, llm_clips: List[dict], 
    transcripts: List, analysis_data: dict, config: dict,
    timeframe_start: float, timeframe_end: float
) -> List[Clip]:
    """Create Clip objects from LLM response."""
    clips = []
    
    for idx, clip_obj in enumerate(llm_clips):
        start = float(clip_obj.get("start_sec", 0.0))
        end = float(clip_obj.get("end_sec", start + 30))
        
        if end > timeframe_end:
            end = timeframe_end
        if start < timeframe_start:
            start = timeframe_start
        if end <= start:
            continue
        
        duration_sec = end - start
        
        transcript_text = sentiment_analysis.get_transcript_for_time_range(transcripts, start, end)
        
        timeline_data = []
        if analysis_data and analysis_data.get("combined_timeline"):
            timeline_data = [t for t in analysis_data["combined_timeline"] if start <= t["time"] < end]
        
        grades_data = engagement_scoring.generate_full_grades(
            {
                "duration": duration_sec,
                "avg_audio_energy": _avg_from_timeline(timeline_data, "audio_energy"),
                "avg_audio_excitement": _avg_from_timeline(timeline_data, "audio_excitement"),
                "avg_visual_interest": _avg_from_timeline(timeline_data, "visual_interest"),
                "avg_motion": _avg_from_timeline(timeline_data, "motion"),
                "avg_face_likelihood": _avg_from_timeline(timeline_data, "face_likelihood"),
            },
            transcript_text,
            timeline_data,
        )
        
        llm_viral_score = float(clip_obj.get("viral_score", 0))
        data_viral_score = (
            grades_data["hook"]["score"] * 0.35 +
            grades_data["flow"]["score"] * 0.20 +
            grades_data["value"]["score"] * 0.25 +
            grades_data["trend"]["score"] * 0.20
        )
        final_score = (llm_viral_score + data_viral_score) / 2 if llm_viral_score > 0 else data_viral_score
        
        clip = Clip(
            clip_batch_id=batch.id,
            start_time_sec=start,
            end_time_sec=end,
            duration_sec=duration_sec,
            title=clip_obj.get("title") or f"Viral moment #{idx+1}",
            description=clip_obj.get("description"),
            viral_score=round(final_score, 1),
            grade_hook=clip_obj.get("grades", {}).get("hook") or grades_data["hook"]["grade"],
            grade_flow=clip_obj.get("grades", {}).get("flow") or grades_data["flow"]["grade"],
            grade_value=clip_obj.get("grades", {}).get("value") or grades_data["value"]["grade"],
            grade_trend=clip_obj.get("grades", {}).get("trend") or grades_data["trend"]["grade"],
            language=config.get("language") or "en",
            status="candidate",
        )
        db.add(clip)
        clips.append(clip)
    
    return clips


def _generate_viral_title_description(transcript_text: str, idx: int) -> Tuple[str, str]:
    """Generate viral title and description using AI."""
    client = utils.get_openai_client()
    
    if not client or not transcript_text.strip():
        return f"Viral Moment #{idx+1}", transcript_text[:150] if transcript_text else ""
    
    try:
        prompt = f"""Based on this transcript, create a viral social media title and description.

TRANSCRIPT:
"{transcript_text[:500]}"

RULES:
- Title: Max 60 chars, catchy, curiosity-inducing, use power words
- Description: 100-150 chars, engaging, include call-to-action feel
- Make it sound like a viral TikTok/YouTube Short
- Use hooks like "Wait for it...", "This is insane!", "You won't believe..."

Return JSON:
{{"title": "...", "description": "..."}}

JSON only, no commentary."""

        response = client.responses.create(
            model=settings.openai_responses_model,
            input=[
                {"role": "user", "content": [{"type": "input_text", "text": prompt}]},
            ],
            temperature=0.7,
        )
        
        resp_text = _extract_response_text(response)
        if resp_text:
            data = json.loads(resp_text.strip().strip("```json").strip("```"))
            return (
                data.get("title", f"Viral Moment #{idx+1}")[:60],
                data.get("description", transcript_text[:150])[:200]
            )
    except Exception as e:
        logger.warning("virality.title_gen_failed", error=str(e))
    
    # Fallback: extract first sentence as title
    sentences = transcript_text.split('.')
    title = sentences[0][:60] if sentences else f"Viral Moment #{idx+1}"
    return title, transcript_text[:150]


def _create_clips_from_candidates(
    db: Session, batch: ClipBatch, clip_candidates: List[dict],
    analysis_data: dict, config: dict
) -> List[Clip]:
    """Create Clip objects from engagement candidates."""
    clips = []
    
    for idx, candidate in enumerate(clip_candidates[:12]):
        start = candidate["start_time"]
        end = candidate["end_time"]
        duration_sec = end - start
        
        transcript_text = candidate.get("transcript_full", "")
        
        # Generate viral title and description
        title, description = _generate_viral_title_description(transcript_text, idx + 1)
        
        timeline_data = []
        if analysis_data and analysis_data.get("combined_timeline"):
            timeline_data = [t for t in analysis_data["combined_timeline"] if start <= t["time"] < end]
        
        grades_data = engagement_scoring.generate_full_grades(
            {
                "duration": duration_sec,
                "avg_audio_energy": candidate.get("avg_audio_energy", 0.5),
                "avg_visual_interest": candidate.get("avg_visual_interest", 0.5),
            },
            transcript_text,
            timeline_data,
        )
        
        viral_score = candidate["engagement_score"] * 10
        
        clip = Clip(
            clip_batch_id=batch.id,
            start_time_sec=start,
            end_time_sec=end,
            duration_sec=duration_sec,
            title=title,
            description=description,
            viral_score=round(viral_score, 1),
            grade_hook=grades_data["hook"]["grade"],
            grade_flow=grades_data["flow"]["grade"],
            grade_value=grades_data["value"]["grade"],
            grade_trend=grades_data["trend"]["grade"],
            language=config.get("language") or "en",
            status="candidate",
        )
        db.add(clip)
        clips.append(clip)
    
    return clips


def _create_clips_from_transcripts(
    db: Session, batch: ClipBatch, transcripts: List,
    config: dict, timeframe_start: float
) -> List[Clip]:
    """Create Clip objects from transcript segments as ultimate fallback."""
    clips = []
    min_dur, max_dur = _target_duration(config.get("clip_length_preset", "30_60"))
    
    current_start = transcripts[0].start_time_sec if transcripts else timeframe_start
    current_texts = []
    
    for seg in transcripts:
        current_texts.append(seg.text)
        potential_duration = seg.end_time_sec - current_start
        
        if potential_duration >= min_dur:
            transcript_text = " ".join(current_texts)
            title, description = _generate_viral_title_description(transcript_text, len(clips) + 1)
            
            clip = Clip(
                clip_batch_id=batch.id,
                start_time_sec=current_start,
                end_time_sec=min(seg.end_time_sec, current_start + max_dur),
                duration_sec=min(potential_duration, max_dur),
                title=title,
                description=description,
                viral_score=5.0,
                grade_hook="B",
                grade_flow="B",
                grade_value="B",
                grade_trend="B",
                language=config.get("language") or "en",
                status="candidate",
            )
            db.add(clip)
            clips.append(clip)
            
            current_start = seg.end_time_sec
            current_texts = []
            
            if len(clips) >= 10:
                break
    
    return clips


def _generate_thumbnails_and_context(
    db: Session, clips: List[Clip], video, config: dict,
    clip_candidates: List, llm_clips: List, response_text: str, analysis_data: dict
):
    """Generate thumbnails and store LLM context for clips."""
    for clip in clips:
        mid = clip.start_time_sec + (clip.duration_sec / 2)
        
        if video.file_path:
            # Store thumbnails in organized structure: thumbnails/clips/{clip_id}.jpg
            thumb_dir = utils.ensure_dir(Path(settings.media_root) / "thumbnails" / "clips")
            thumb_path = thumb_dir / f"{clip.id}.jpg"
            
            if utils.render_thumbnail(video.file_path, str(thumb_path), mid):
                try:
                    relative = thumb_path.relative_to(Path(settings.media_root))
                    clip.thumbnail_path = f"{settings.media_base_url}/{relative.as_posix()}"
                    logger.info("clip.thumbnail_generated", clip_id=clip.id, path=clip.thumbnail_path)
                except Exception as e:
                    clip.thumbnail_path = str(thumb_path)
                    logger.warning("clip.thumbnail_path_error", clip_id=clip.id, error=str(e))
            else:
                logger.warning("clip.thumbnail_failed", clip_id=clip.id, video_path=video.file_path)
                if video.thumbnail_path:
                    clip.thumbnail_path = video.thumbnail_path
        elif video.thumbnail_path:
            clip.thumbnail_path = video.thumbnail_path
            logger.info("clip.using_video_thumbnail", clip_id=clip.id)
        
        # Find matching LLM clip data for hashtags
        clip_llm_data = None
        if llm_clips:
            for llm_clip in llm_clips:
                llm_start = float(llm_clip.get("start_sec", 0))
                if abs(llm_start - clip.start_time_sec) < 2.0:  # Within 2 seconds
                    clip_llm_data = llm_clip
                    break
        
        db.add(ClipLLMContext(
            clip_id=clip.id,
            prompt=_build_enhanced_prompt(config, clip_candidates[:5], config.get("include_specific_moments", "")) if clip_candidates else "",
            response_json={
                "llm_clips": llm_clips[:5] if llm_clips else [],
                "raw_text": response_text[:1000],
                "hashtags": clip_llm_data.get("hashtags", ["viral", "trending", "fyp"]) if clip_llm_data else ["viral", "trending", "fyp"],
                "hook_text": clip_llm_data.get("hook_text", "") if clip_llm_data else "",
                "detected_video_type": clip_llm_data.get("detected_video_type", "unknown") if clip_llm_data else "unknown",
                "analysis_summary": {
                    "audio_peaks": len(analysis_data.get("audio_peaks", [])) if analysis_data else 0,
                    "visual_peaks": len(analysis_data.get("visual_peaks", [])) if analysis_data else 0,
                    "candidates_analyzed": len(clip_candidates),
                },
            },
        ))
    
    db.commit()


def _avg_from_timeline(timeline: List[Dict], key: str, default: float = 0.5) -> float:
    """Calculate average of a key from timeline data."""
    if not timeline:
        return default
    values = [t.get(key, default) for t in timeline]
    return sum(values) / len(values)


def _save_clip_analyses(
    db: Session, 
    clips: List[Clip], 
    analysis_data: Optional[Dict], 
    llm_clips: List[Dict]
):
    """
    Save detailed analysis for each generated clip.
    
    This populates the clip_analyses table with:
    - Component scores (audio, visual, hook, etc.)
    - Grade details
    - Strengths and weaknesses
    """
    for clip in clips:
        # Check if analysis already exists
        existing = db.query(ClipAnalysis).filter(ClipAnalysis.clip_id == clip.id).first()
        if existing:
            continue
        
        # Get timeline data for this clip's time range
        timeline_data = []
        if analysis_data and analysis_data.get("combined_timeline"):
            timeline_data = [
                t for t in analysis_data["combined_timeline"] 
                if clip.start_time_sec <= t.get("time", 0) < clip.end_time_sec
            ]
        
        # Calculate component scores
        audio_energy = _avg_from_timeline(timeline_data, "audio_energy", 0.5)
        audio_excitement = _avg_from_timeline(timeline_data, "audio_excitement", 0.5)
        visual_interest = _avg_from_timeline(timeline_data, "visual_interest", 0.5)
        motion = _avg_from_timeline(timeline_data, "motion", 0.5)
        face_likelihood = _avg_from_timeline(timeline_data, "face_likelihood", 0.5)
        
        # Find matching LLM clip for additional data
        llm_clip_data = None
        for llm_clip in llm_clips:
            llm_start = float(llm_clip.get("start_sec", 0))
            if abs(llm_start - clip.start_time_sec) < 2.0:
                llm_clip_data = llm_clip
                break
        
        # Get grades from clip or LLM data
        grades = llm_clip_data.get("grades", {}) if llm_clip_data else {}
        
        # Calculate data-driven score
        data_score = (
            audio_energy * 2.0 +
            audio_excitement * 2.0 +
            visual_interest * 2.0 +
            motion * 1.5 +
            face_likelihood * 1.5
        )  # Max ~10
        
        llm_score = float(llm_clip_data.get("viral_score", 0)) if llm_clip_data else 0
        final_score = clip.viral_score or ((data_score + llm_score) / 2 if llm_score > 0 else data_score)
        
        # Determine strengths and weaknesses
        strengths = []
        weaknesses = []
        
        if audio_energy > 0.6:
            strengths.append("High audio energy - engaging sound")
        elif audio_energy < 0.3:
            weaknesses.append("Low audio energy - may feel flat")
        
        if visual_interest > 0.6:
            strengths.append("Visually interesting content")
        elif visual_interest < 0.3:
            weaknesses.append("Low visual interest - consider more dynamic visuals")
        
        if face_likelihood > 0.5:
            strengths.append("Face presence increases engagement")
        
        if clip.grade_hook in ["A", "B"]:
            strengths.append(f"Strong opening hook (Grade {clip.grade_hook})")
        elif clip.grade_hook in ["D"]:
            weaknesses.append("Weak opening hook - first 3 seconds need work")
        
        if clip.grade_flow in ["A", "B"]:
            strengths.append("Good pacing and flow")
        elif clip.grade_flow in ["D"]:
            weaknesses.append("Pacing issues - may feel choppy")
        
        # Create ClipAnalysis record
        clip_analysis = ClipAnalysis(
            clip_id=clip.id,
            audio_energy_score=round(audio_energy * 10, 2),
            audio_excitement_score=round(audio_excitement * 10, 2),
            visual_interest_score=round(visual_interest * 10, 2),
            motion_score=round(motion * 10, 2),
            face_presence_score=round(face_likelihood * 10, 2),
            hook_strength_score=_grade_to_score(clip.grade_hook),
            sentiment_intensity_score=_grade_to_score(clip.grade_value),
            hook_grade_json={"grade": clip.grade_hook, "analysis": grades.get("hook", "")},
            flow_grade_json={"grade": clip.grade_flow, "analysis": grades.get("flow", "")},
            value_grade_json={"grade": clip.grade_value, "analysis": grades.get("value", "")},
            trend_grade_json={"grade": clip.grade_trend, "analysis": grades.get("trend", "")},
            data_driven_score=round(data_score, 2),
            llm_score=round(llm_score, 2) if llm_score else None,
            final_score=round(final_score, 2),
            strengths=strengths,
            weaknesses=weaknesses,
            timeline_data_json=timeline_data[:50] if timeline_data else None,  # Limit size
        )
        db.add(clip_analysis)
    
    db.commit()
    logger.info("virality.clip_analyses_saved", count=len(clips))


def _grade_to_score(grade: str) -> float:
    """Convert letter grade to numeric score (0-10)."""
    grade_map = {"A": 9.0, "B": 7.0, "C": 5.0, "D": 3.0}
    return grade_map.get(grade, 5.0)
