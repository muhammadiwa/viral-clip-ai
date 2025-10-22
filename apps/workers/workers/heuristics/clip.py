"""Clip scoring heuristics shared between workers and QA tests."""

from __future__ import annotations

from typing import Dict, Tuple


def compute_candidate_confidence(
    *,
    motion_strength: float,
    audio_energy: float,
    peak_energy: float,
    keyword_score: float,
    duration_ms: int,
    target_duration_ms: int,
    weight_motion: float,
    weight_audio: float,
    weight_keywords: float,
    weight_duration: float,
    bias: float,
) -> Tuple[float, Dict[str, float]]:
    """Return the aggregated confidence and component scores for a clip candidate."""

    def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
        return max(minimum, min(maximum, value))

    peak = max(peak_energy, 0.0)
    motion = _clamp(motion_strength)
    audio = _clamp(audio_energy / peak) if peak else 0.0
    keywords = _clamp(keyword_score)
    if target_duration_ms > 0:
        deviation = abs(duration_ms - target_duration_ms)
        duration = _clamp(1.0 - (deviation / max(target_duration_ms, 1)))
    else:
        duration = 1.0

    weight_motion = max(weight_motion, 0.0)
    weight_audio = max(weight_audio, 0.0)
    weight_keywords = max(weight_keywords, 0.0)
    weight_duration = max(weight_duration, 0.0)
    weight_total = weight_motion + weight_audio + weight_keywords + weight_duration
    if weight_total <= 0:
        weight_total = 1.0

    weighted_total = (
        (motion * weight_motion)
        + (audio * weight_audio)
        + (keywords * weight_keywords)
        + (duration * weight_duration)
    )
    weighted = weighted_total / weight_total
    confidence = _clamp(bias + weighted)

    return confidence, {
        "motion": motion,
        "audio": audio,
        "keywords": keywords,
        "duration": duration,
        "weighted": weighted,
        "bias": bias,
    }
