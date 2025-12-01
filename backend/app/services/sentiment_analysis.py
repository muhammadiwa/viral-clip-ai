"""
Sentiment Analysis Service for Viral Clip Detection.

Analyzes transcript text to detect:
- Sentiment polarity (positive/negative/neutral)
- Emotional intensity
- Hook words and viral triggers
- Questions and calls-to-action
"""
import re
from typing import Any, Dict, List, Optional

import structlog

from app.core.config import get_settings
from app.services.utils import get_openai_client
from app.models import TranscriptSegment

logger = structlog.get_logger()
settings = get_settings()

# Viral hook words that grab attention
HOOK_WORDS = {
    "high_impact": [
        "secret", "shocking", "never", "always", "best", "worst",
        "amazing", "incredible", "unbelievable", "insane", "crazy",
        "breaking", "exclusive", "revealed", "truth", "exposed",
        "warning", "urgent", "critical", "important", "finally",
    ],
    "curiosity": [
        "how to", "why", "what if", "imagine", "discover", "learn",
        "find out", "the reason", "here's why", "this is how",
        "you won't believe", "wait until", "watch what happens",
    ],
    "value": [
        "free", "save", "hack", "trick", "tip", "strategy",
        "mistake", "avoid", "stop", "start", "must", "need",
        "proven", "guaranteed", "results", "success", "fail",
    ],
    "emotional": [
        "love", "hate", "fear", "hope", "dream", "nightmare",
        "beautiful", "terrible", "perfect", "disaster", "miracle",
        "heartbreaking", "hilarious", "terrifying", "inspiring",
    ],
    "social": [
        "everyone", "nobody", "people", "they", "we", "you",
        "viral", "trending", "famous", "celebrity", "influencer",
    ],
}

# Flatten for quick lookup
ALL_HOOK_WORDS = []
for category, words in HOOK_WORDS.items():
    ALL_HOOK_WORDS.extend(words)


def analyze_text_sentiment(text: str) -> Dict[str, Any]:
    """
    Analyze sentiment of a text segment using rule-based approach.
    
    Returns:
    - sentiment: -1 to 1 (negative to positive)
    - intensity: 0 to 1 (how strong the emotion)
    - emotion: primary emotion detected
    """
    text_lower = text.lower()
    
    # Positive and negative word lists
    positive_words = [
        "good", "great", "awesome", "amazing", "love", "best", "happy",
        "excellent", "wonderful", "fantastic", "perfect", "beautiful",
        "success", "win", "yes", "right", "true", "brilliant", "incredible",
    ]
    negative_words = [
        "bad", "terrible", "awful", "hate", "worst", "sad", "wrong",
        "fail", "failure", "no", "never", "problem", "issue", "mistake",
        "horrible", "disaster", "ugly", "stupid", "boring", "annoying",
    ]
    
    # Count occurrences
    pos_count = sum(1 for w in positive_words if w in text_lower)
    neg_count = sum(1 for w in negative_words if w in text_lower)
    
    # Calculate sentiment
    total = pos_count + neg_count
    if total == 0:
        sentiment = 0.0
    else:
        sentiment = (pos_count - neg_count) / total
    
    # Intensity based on exclamation marks, caps, and word count
    exclamations = text.count("!")
    questions = text.count("?")
    caps_ratio = sum(1 for c in text if c.isupper()) / max(1, len(text))
    word_count = len(text.split())
    
    intensity = min(1.0, (
        0.3 +  # Base intensity
        exclamations * 0.1 +
        questions * 0.05 +
        caps_ratio * 0.3 +
        (total / max(1, word_count)) * 0.5
    ))
    
    # Determine primary emotion
    if sentiment > 0.3:
        emotion = "positive"
    elif sentiment < -0.3:
        emotion = "negative"
    elif questions > 0:
        emotion = "curious"
    elif exclamations > 0:
        emotion = "excited"
    else:
        emotion = "neutral"
    
    return {
        "sentiment": sentiment,
        "intensity": intensity,
        "emotion": emotion,
    }


def analyze_with_llm(
    text: str,
    client: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Analyze sentiment using OpenAI for more accurate results.
    Falls back to rule-based if LLM unavailable.
    """
    if not client:
        client = get_openai_client()
    
    if not client:
        return analyze_text_sentiment(text)
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Analyze the sentiment. Return JSON: {sentiment: -1 to 1, intensity: 0 to 1, emotion: string, viral_potential: 0 to 1}"
                },
                {"role": "user", "content": text[:500]}
            ],
            temperature=0.3,
            max_tokens=100,
        )
        
        import json
        result_text = response.choices[0].message.content
        # Try to parse JSON
        result_text = result_text.strip()
        if result_text.startswith("```"):
            result_text = re.sub(r"```json?\s*", "", result_text)
            result_text = result_text.replace("```", "")
        
        result = json.loads(result_text)
        return {
            "sentiment": float(result.get("sentiment", 0)),
            "intensity": float(result.get("intensity", 0.5)),
            "emotion": result.get("emotion", "neutral"),
            "viral_potential": float(result.get("viral_potential", 0.5)),
        }
    except Exception as e:
        logger.warning("sentiment.llm_failed", error=str(e))
        return analyze_text_sentiment(text)


def count_hook_words(text: str) -> Dict[str, Any]:
    """
    Count viral hook words in text.
    
    Returns:
    - total_count: total hook words found
    - by_category: count per category
    - found_words: list of found words
    - hook_score: 0-1 score based on hook word density
    """
    text_lower = text.lower()
    word_count = len(text.split())
    
    found = []
    by_category = {}
    
    for category, words in HOOK_WORDS.items():
        category_count = 0
        for word in words:
            if word in text_lower:
                found.append(word)
                category_count += 1
        by_category[category] = category_count
    
    total_count = len(found)
    
    # Hook score: more hooks relative to text length = higher score
    if word_count == 0:
        hook_score = 0.0
    else:
        hook_density = total_count / word_count
        hook_score = min(1.0, hook_density * 10)  # Scale appropriately
    
    return {
        "total_count": total_count,
        "by_category": by_category,
        "found_words": found,
        "hook_score": hook_score,
    }


def detect_questions(text: str) -> Dict[str, Any]:
    """
    Detect questions in text - questions increase engagement.
    
    Returns:
    - has_question: bool
    - question_count: number of questions
    - questions: list of question sentences
    """
    # Split into sentences
    sentences = re.split(r'[.!?]+', text)
    
    questions = []
    question_words = ["who", "what", "where", "when", "why", "how", "is", "are", "do", "does", "can", "could", "would", "should"]
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        
        # Check if ends with ? or starts with question word
        if "?" in text and sentence.lower().split()[0] in question_words if sentence.split() else False:
            questions.append(sentence)
        elif sentence.lower().startswith(tuple(question_words)):
            questions.append(sentence)
    
    return {
        "has_question": len(questions) > 0,
        "question_count": len(questions),
        "questions": questions,
    }


def detect_cta(text: str) -> Dict[str, Any]:
    """
    Detect calls-to-action in text.
    
    Returns:
    - has_cta: bool
    - cta_count: number of CTAs
    - cta_phrases: found CTA phrases
    """
    text_lower = text.lower()
    
    cta_patterns = [
        r"subscribe", r"like", r"comment", r"share", r"follow",
        r"click", r"link in bio", r"check out", r"watch", r"listen",
        r"sign up", r"join", r"get your", r"grab your", r"don't miss",
        r"tap", r"swipe", r"dm me", r"let me know", r"tell me",
    ]
    
    found_ctas = []
    for pattern in cta_patterns:
        if re.search(pattern, text_lower):
            found_ctas.append(pattern)
    
    return {
        "has_cta": len(found_ctas) > 0,
        "cta_count": len(found_ctas),
        "cta_phrases": found_ctas,
    }


def analyze_segment(segment: TranscriptSegment) -> Dict[str, Any]:
    """
    Comprehensive analysis of a transcript segment.
    """
    text = segment.text
    
    sentiment = analyze_text_sentiment(text)
    hooks = count_hook_words(text)
    questions = detect_questions(text)
    cta = detect_cta(text)
    
    # Calculate overall viral potential for this segment
    viral_potential = (
        sentiment["intensity"] * 0.2 +
        hooks["hook_score"] * 0.3 +
        (0.2 if questions["has_question"] else 0) +
        (0.1 if cta["has_cta"] else 0) +
        abs(sentiment["sentiment"]) * 0.2  # Strong emotion either way
    )
    viral_potential = min(1.0, viral_potential)
    
    return {
        "start_time": segment.start_time_sec,
        "end_time": segment.end_time_sec,
        "text": text,
        "sentiment": sentiment,
        "hooks": hooks,
        "questions": questions,
        "cta": cta,
        "viral_potential": viral_potential,
    }


def analyze_transcript_segments(
    segments: List[TranscriptSegment],
) -> List[Dict[str, Any]]:
    """
    Analyze all transcript segments.
    """
    logger.info("sentiment.analyze_start", segment_count=len(segments))
    
    results = []
    for segment in segments:
        analysis = analyze_segment(segment)
        results.append(analysis)
    
    logger.info("sentiment.analyze_done", analyzed=len(results))
    return results


def find_viral_moments_from_transcript(
    analyzed_segments: List[Dict[str, Any]],
    min_score: float = 0.4,
) -> List[Dict[str, Any]]:
    """
    Find high viral potential moments from analyzed transcript.
    
    Returns moments sorted by viral potential.
    """
    moments = []
    
    for seg in analyzed_segments:
        if seg["viral_potential"] >= min_score:
            reason_parts = []
            if seg["hooks"]["total_count"] > 0:
                reason_parts.append(f"hooks:{seg['hooks']['total_count']}")
            if seg["questions"]["has_question"]:
                reason_parts.append("has_question")
            if seg["sentiment"]["intensity"] > 0.6:
                reason_parts.append(f"emotional:{seg['sentiment']['emotion']}")
            if seg["cta"]["has_cta"]:
                reason_parts.append("has_cta")
            
            moments.append({
                "start_time": seg["start_time"],
                "end_time": seg["end_time"],
                "text": seg["text"],
                "viral_potential": seg["viral_potential"],
                "reason": ", ".join(reason_parts) if reason_parts else "engaging_content",
                "sentiment": seg["sentiment"]["sentiment"],
                "emotion": seg["sentiment"]["emotion"],
                "hook_words": seg["hooks"]["found_words"],
            })
    
    # Sort by viral potential
    moments.sort(key=lambda x: x["viral_potential"], reverse=True)
    
    return moments


def get_transcript_for_time_range(
    segments: List[TranscriptSegment],
    start_time: float,
    end_time: float,
) -> str:
    """
    Get transcript text for a specific time range.
    """
    texts = []
    for seg in segments:
        # Check if segment overlaps with time range
        if seg.end_time_sec > start_time and seg.start_time_sec < end_time:
            texts.append(seg.text)
    
    return " ".join(texts)


def analyze_text_for_hook_strength(text: str) -> Dict[str, Any]:
    """
    Analyze how strong the opening hook is.
    
    A good hook should:
    - Grab attention in first few words
    - Create curiosity or emotion
    - Promise value
    """
    if not text:
        return {"hook_strength": 0, "reason": "empty"}
    
    words = text.split()
    first_words = " ".join(words[:10]).lower() if len(words) >= 10 else text.lower()
    
    score = 0.3  # Base score
    reasons = []
    
    # Check for question start
    if any(first_words.startswith(q) for q in ["what", "why", "how", "who", "when", "where"]):
        score += 0.2
        reasons.append("opens_with_question")
    
    # Check for hook words in opening
    hooks_in_opening = count_hook_words(first_words)
    if hooks_in_opening["total_count"] > 0:
        score += 0.2 * min(hooks_in_opening["total_count"], 3)
        reasons.append(f"hook_words:{hooks_in_opening['found_words'][:3]}")
    
    # Check for "you" addressing viewer directly
    if "you" in first_words:
        score += 0.1
        reasons.append("addresses_viewer")
    
    # Check for numbers (specific = more credible)
    if re.search(r'\d+', first_words):
        score += 0.1
        reasons.append("has_number")
    
    score = min(1.0, score)
    
    return {
        "hook_strength": score,
        "reasons": reasons,
        "first_words": first_words,
    }
