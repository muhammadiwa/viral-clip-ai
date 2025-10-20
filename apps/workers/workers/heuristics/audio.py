"""Audio mixing heuristics that avoid heavy runtime dependencies."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class MixProfile:
    bed_gain: float
    voice_gain: float
    loudness_target_i: float
    loudness_true_peak: float
    loudness_range: float


def db_to_gain(db_value: float) -> float:
    return math.pow(10.0, db_value / 20.0)


def build_mix_profile(settings) -> MixProfile:
    return MixProfile(
        bed_gain=db_to_gain(getattr(settings, "tts_music_gain_db", -9.0)),
        voice_gain=db_to_gain(getattr(settings, "tts_voice_gain_db", -1.5)),
        loudness_target_i=float(getattr(settings, "tts_loudness_target_i", -16.0)),
        loudness_true_peak=float(getattr(settings, "tts_loudness_true_peak", -1.5)),
        loudness_range=float(getattr(settings, "tts_loudness_range", 11.0)),
    )
