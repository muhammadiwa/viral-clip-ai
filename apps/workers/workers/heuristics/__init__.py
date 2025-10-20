"""Shared heuristics reused by workers and QA harness."""

from .clip import compute_candidate_confidence
from .subtitles import DEFAULT_SUBTITLE_STYLE, BASE_SUBTITLE_PRESETS, resolve_style
from .audio import build_mix_profile, db_to_gain
from .export import watermark_position

__all__ = [
    "compute_candidate_confidence",
    "DEFAULT_SUBTITLE_STYLE",
    "BASE_SUBTITLE_PRESETS",
    "resolve_style",
    "build_mix_profile",
    "db_to_gain",
    "watermark_position",
]
