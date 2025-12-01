"""
Engagement Scoring System for Viral Clip Detection.

Provides data-driven scoring for clips based on:
- Audio engagement signals
- Visual engagement signals
- Content/transcript signals
- Hook strength
- Viral potential indicators
"""
from typing import Any, Dict, List, Optional

import structlog

from app.models import TranscriptSegment
from app.services import sentiment_analysis

logger = structlog.get_logger()

# Weights for different scoring components
SCORING_WEIGHTS = {
    # Audio factors (30%)
    "audio_energy": 0.10,
    "audio_excitement": 0.10,
    "speech_presence": 0.10,
    
    # Visual factors (25%)
    "visual_interest": 0.10,
    "motion_score": 0.08,
    "face_presence": 0.07,
    
    # Content factors (35%)
    "hook_strength": 0.12,
    "sentiment_intensity": 0.08,
    "hook_words": 0.08,
    "has_question": 0.04,
    "has_cta": 0.03,
    
    # Structural factors (10%)
    "optimal_duration": 0.05,
    "clean_boundaries": 0.05,
}


def calculate_viral_score(
    clip_data: Dict[str, Any],
    transcript_text: str,
    transcripts: List[TranscriptSegment],
) -> Dict[str, Any]:
    """
    Calculate comprehensive viral score for a clip.
    
    Args:
        clip_data: Dict with audio/visual analysis data
        transcript_text: Full transcript for the clip
        transcripts: List of TranscriptSegment for detailed analysis
    
    Returns:
        Dict with:
        - viral_score: 0-10 final score
        - component_scores: individual scores
        - grade: A/B/C/D/F letter grade
        - strengths: what makes this clip strong
        - weaknesses: what could be improved
    """
    scores = {}
    
    # Audio scores
    scores["audio_energy"] = clip_data.get("avg_audio_energy", 0.5) * 10
    scores["audio_excitement"] = clip_data.get("avg_audio_excitement", 0.5) * 10
    scores["speech_presence"] = 7.0 if clip_data.get("has_speech", True) else 3.0
    
    # Visual scores
    scores["visual_interest"] = clip_data.get("avg_visual_interest", 0.5) * 10
    scores["motion_score"] = clip_data.get("avg_motion", 0.5) * 10
    scores["face_presence"] = clip_data.get("avg_face_likelihood", 0.5) * 10
    
    # Content analysis
    hook_analysis = sentiment_analysis.analyze_text_for_hook_strength(transcript_text)
    scores["hook_strength"] = hook_analysis["hook_strength"] * 10
    
    sentiment = sentiment_analysis.analyze_text_sentiment(transcript_text)
    scores["sentiment_intensity"] = sentiment["intensity"] * 10
    
    hooks = sentiment_analysis.count_hook_words(transcript_text)
    scores["hook_words"] = min(10, hooks["total_count"] * 2)
    
    questions = sentiment_analysis.detect_questions(transcript_text)
    scores["has_question"] = 8.0 if questions["has_question"] else 3.0
    
    cta = sentiment_analysis.detect_cta(transcript_text)
    scores["has_cta"] = 7.0 if cta["has_cta"] else 4.0
    
    # Structural scores
    duration = clip_data.get("duration", 30)
    # Optimal duration: 15-60 seconds
    if 15 <= duration <= 60:
        scores["optimal_duration"] = 10.0
    elif 10 <= duration <= 90:
        scores["optimal_duration"] = 7.0
    else:
        scores["optimal_duration"] = 4.0
    
    # Clean boundaries (starts/ends at natural points)
    scores["clean_boundaries"] = clip_data.get("boundary_score", 6.0)
    
    # Calculate weighted final score
    weighted_sum = sum(
        scores[key] * SCORING_WEIGHTS[key]
        for key in SCORING_WEIGHTS
        if key in scores
    )
    
    # Normalize to 0-10
    viral_score = min(10.0, max(0.0, weighted_sum))
    
    # Determine grade
    if viral_score >= 8.0:
        grade = "A"
    elif viral_score >= 6.5:
        grade = "B"
    elif viral_score >= 5.0:
        grade = "C"
    elif viral_score >= 3.5:
        grade = "D"
    else:
        grade = "F"
    
    # Identify strengths and weaknesses
    strengths = []
    weaknesses = []
    
    for key, score in scores.items():
        if score >= 7.0:
            strengths.append(_score_to_strength(key, score))
        elif score <= 4.0:
            weaknesses.append(_score_to_weakness(key, score))
    
    return {
        "viral_score": round(viral_score, 1),
        "component_scores": scores,
        "grade": grade,
        "strengths": strengths[:5],
        "weaknesses": weaknesses[:3],
        "hook_analysis": hook_analysis,
        "sentiment": sentiment,
    }


def _score_to_strength(key: str, score: float) -> str:
    """Convert a high score to a strength description."""
    mapping = {
        "audio_energy": "High energy audio keeps viewers engaged",
        "audio_excitement": "Exciting audio moments capture attention",
        "speech_presence": "Clear speech content",
        "visual_interest": "Visually engaging content",
        "motion_score": "Dynamic movement holds attention",
        "face_presence": "Face-focused content connects with viewers",
        "hook_strength": "Strong opening hook",
        "sentiment_intensity": "Strong emotional content",
        "hook_words": "Uses attention-grabbing language",
        "has_question": "Questions engage viewer curiosity",
        "has_cta": "Clear call-to-action",
        "optimal_duration": "Ideal clip length",
        "clean_boundaries": "Natural start and end points",
    }
    return mapping.get(key, f"Strong {key.replace('_', ' ')}")


def _score_to_weakness(key: str, score: float) -> str:
    """Convert a low score to an improvement suggestion."""
    mapping = {
        "audio_energy": "Consider clips with more energy",
        "audio_excitement": "Audio could be more dynamic",
        "speech_presence": "Limited speech content",
        "visual_interest": "Visual content could be more engaging",
        "motion_score": "More movement would improve engagement",
        "face_presence": "Consider clips with more face time",
        "hook_strength": "Opening could be stronger",
        "sentiment_intensity": "Content could be more emotional",
        "hook_words": "Use more attention-grabbing words",
        "has_question": "Adding questions could boost engagement",
        "has_cta": "Consider adding a call-to-action",
        "optimal_duration": "Clip length may not be optimal",
        "clean_boundaries": "Start/end points could be cleaner",
    }
    return mapping.get(key, f"Improve {key.replace('_', ' ')}")


def calculate_hook_score(transcript_text: str) -> Dict[str, Any]:
    """
    Specifically evaluate the hook (first few seconds) of a clip.
    
    Returns:
    - score: 0-10
    - grade: A/B/C letter grade
    - analysis: detailed breakdown
    """
    if not transcript_text:
        return {"score": 0, "grade": "F", "analysis": "No transcript"}
    
    # Get first ~30 words (approximately first 5-10 seconds of speech)
    words = transcript_text.split()
    first_words = " ".join(words[:30])
    
    analysis = sentiment_analysis.analyze_text_for_hook_strength(first_words)
    
    # Additional hook-specific checks
    score = analysis["hook_strength"] * 10
    details = {
        "first_words": first_words[:100],
        "reasons": analysis.get("reasons", []),
    }
    
    # Bonus for specific hook patterns
    first_lower = first_words.lower()
    
    # Pattern: Number + Adjective + Noun ("3 simple ways", "5 biggest mistakes")
    import re
    if re.search(r'\d+\s+\w+\s+(ways?|tips?|tricks?|mistakes?|reasons?|secrets?)', first_lower):
        score += 1.5
        details["reasons"].append("numbered_list_hook")
    
    # Pattern: "You" in first 5 words
    first_five = " ".join(words[:5]).lower()
    if "you" in first_five:
        score += 0.5
        if "you" not in analysis.get("reasons", []):
            details["reasons"].append("immediate_you_address")
    
    # Pattern: Starts with action verb
    action_verbs = ["watch", "listen", "look", "see", "hear", "imagine", "think", "stop", "wait"]
    if words and words[0].lower() in action_verbs:
        score += 0.5
        details["reasons"].append("action_verb_start")
    
    score = min(10.0, score)
    
    if score >= 8.0:
        grade = "A"
    elif score >= 6.0:
        grade = "B"
    elif score >= 4.0:
        grade = "C"
    else:
        grade = "D"
    
    return {
        "score": round(score, 1),
        "grade": grade,
        "analysis": details,
    }


def calculate_flow_score(
    timeline_data: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Evaluate the flow/pacing of a clip.
    
    Good flow:
    - Consistent engagement (not too many dips)
    - Building momentum
    - Strong ending
    """
    if not timeline_data or len(timeline_data) < 3:
        return {"score": 5.0, "grade": "C", "analysis": "Insufficient data"}
    
    scores = [t.get("engagement_score", 0.5) for t in timeline_data]
    
    # Check for consistency (low variance is good)
    mean_score = sum(scores) / len(scores)
    variance = sum((s - mean_score) ** 2 for s in scores) / len(scores)
    consistency = max(0, 1 - variance * 4)  # Lower variance = higher consistency
    
    # Check for momentum (should build or maintain)
    first_third = scores[:len(scores)//3]
    last_third = scores[-(len(scores)//3):]
    
    first_avg = sum(first_third) / len(first_third) if first_third else 0.5
    last_avg = sum(last_third) / len(last_third) if last_third else 0.5
    
    momentum = 0.5 + (last_avg - first_avg) * 2  # Bonus if ending stronger
    momentum = max(0, min(1, momentum))
    
    # Check for dips (bad for retention)
    dip_count = sum(1 for i in range(1, len(scores)-1) 
                    if scores[i] < scores[i-1] * 0.7 and scores[i] < scores[i+1] * 0.7)
    dip_penalty = min(0.3, dip_count * 0.1)
    
    flow_score = (consistency * 0.4 + momentum * 0.4 + mean_score * 0.2 - dip_penalty) * 10
    flow_score = max(0, min(10, flow_score))
    
    if flow_score >= 7.0:
        grade = "A"
    elif flow_score >= 5.5:
        grade = "B"
    elif flow_score >= 4.0:
        grade = "C"
    else:
        grade = "D"
    
    return {
        "score": round(flow_score, 1),
        "grade": grade,
        "analysis": {
            "consistency": round(consistency, 2),
            "momentum": round(momentum, 2),
            "dip_count": dip_count,
            "mean_engagement": round(mean_score, 2),
        },
    }


def calculate_value_score(
    transcript_text: str,
) -> Dict[str, Any]:
    """
    Evaluate the value/substance of a clip's content.
    
    High value:
    - Educational content
    - Actionable advice
    - Unique insights
    - Entertainment value
    """
    if not transcript_text:
        return {"score": 5.0, "grade": "C", "analysis": "No transcript"}
    
    text_lower = transcript_text.lower()
    word_count = len(transcript_text.split())
    
    score = 5.0  # Base score
    reasons = []
    
    # Educational indicators
    educational_words = ["learn", "understand", "know", "realize", "discover", "found", "research", "study", "fact"]
    edu_count = sum(1 for w in educational_words if w in text_lower)
    if edu_count >= 2:
        score += 1.5
        reasons.append("educational_content")
    
    # Actionable advice indicators
    action_words = ["step", "first", "then", "next", "finally", "tip", "trick", "how to", "way to", "method"]
    action_count = sum(1 for w in action_words if w in text_lower)
    if action_count >= 2:
        score += 1.5
        reasons.append("actionable_advice")
    
    # Specific/concrete indicators (numbers, examples)
    import re
    has_numbers = bool(re.search(r'\d+', transcript_text))
    has_examples = "example" in text_lower or "for instance" in text_lower or "like when" in text_lower
    
    if has_numbers:
        score += 0.5
        reasons.append("specific_numbers")
    if has_examples:
        score += 0.5
        reasons.append("concrete_examples")
    
    # Story/narrative indicators (entertainment value)
    story_words = ["story", "happened", "once", "remember", "back when", "told me", "said"]
    story_count = sum(1 for w in story_words if w in text_lower)
    if story_count >= 2:
        score += 1.0
        reasons.append("narrative_element")
    
    # Depth indicator (longer explanations tend to have more value)
    if word_count >= 100:
        score += 0.5
        reasons.append("substantial_content")
    
    score = min(10.0, score)
    
    if score >= 7.5:
        grade = "A"
    elif score >= 6.0:
        grade = "B"
    elif score >= 4.5:
        grade = "C"
    else:
        grade = "D"
    
    return {
        "score": round(score, 1),
        "grade": grade,
        "analysis": {
            "reasons": reasons,
            "word_count": word_count,
        },
    }


def calculate_trend_score(
    transcript_text: str,
    hooks_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Evaluate trend/relevance potential of a clip.
    
    High trend potential:
    - Timely topics
    - Relatable content
    - Shareable format
    """
    if not transcript_text:
        return {"score": 5.0, "grade": "C", "analysis": "No transcript"}
    
    text_lower = transcript_text.lower()
    score = 5.0
    reasons = []
    
    # Relatable indicators
    relatable_words = ["everyone", "we all", "you know", "right?", "same", "relatable", "feels", "mood"]
    relatable_count = sum(1 for w in relatable_words if w in text_lower)
    if relatable_count >= 1:
        score += 1.0
        reasons.append("relatable_content")
    
    # Controversy/debate potential
    debate_words = ["actually", "wrong", "myth", "truth", "unpopular opinion", "hot take", "controversial"]
    debate_count = sum(1 for w in debate_words if w in text_lower)
    if debate_count >= 1:
        score += 1.5
        reasons.append("debate_potential")
    
    # Social proof
    social_words = ["viral", "trending", "everyone's talking", "blowing up", "famous", "celebrity"]
    social_count = sum(1 for w in social_words if w in text_lower)
    if social_count >= 1:
        score += 1.0
        reasons.append("social_proof")
    
    # Use hook word analysis
    if hooks_data.get("total_count", 0) >= 3:
        score += 1.0
        reasons.append("hook_word_density")
    
    # Shareability indicators
    if "?" in transcript_text:  # Questions encourage comments
        score += 0.5
        reasons.append("encourages_engagement")
    
    score = min(10.0, score)
    
    if score >= 7.5:
        grade = "A"
    elif score >= 6.0:
        grade = "B"
    elif score >= 4.5:
        grade = "C"
    else:
        grade = "D"
    
    return {
        "score": round(score, 1),
        "grade": grade,
        "analysis": {
            "reasons": reasons,
        },
    }


def generate_full_grades(
    clip_data: Dict[str, Any],
    transcript_text: str,
    timeline_data: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Generate all grades for a clip (Hook, Flow, Value, Trend).
    """
    hooks = sentiment_analysis.count_hook_words(transcript_text)
    
    hook = calculate_hook_score(transcript_text)
    flow = calculate_flow_score(timeline_data)
    value = calculate_value_score(transcript_text)
    trend = calculate_trend_score(transcript_text, hooks)
    
    return {
        "hook": hook,
        "flow": flow,
        "value": value,
        "trend": trend,
        "overall_grade": _calculate_overall_grade(hook, flow, value, trend),
    }


def _calculate_overall_grade(hook, flow, value, trend) -> str:
    """Calculate overall letter grade from component grades."""
    grade_values = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}
    
    avg = (
        grade_values.get(hook["grade"], 2) * 0.35 +
        grade_values.get(flow["grade"], 2) * 0.20 +
        grade_values.get(value["grade"], 2) * 0.25 +
        grade_values.get(trend["grade"], 2) * 0.20
    )
    
    if avg >= 3.5:
        return "A"
    elif avg >= 2.5:
        return "B"
    elif avg >= 1.5:
        return "C"
    elif avg >= 0.5:
        return "D"
    else:
        return "F"
