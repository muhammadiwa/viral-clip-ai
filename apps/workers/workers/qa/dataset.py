"""Dataset models for the worker QA harness."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import json


@dataclass
class RangeExpectation:
    min: Optional[float] = None
    max: Optional[float] = None
    approx: Optional[float] = None
    tolerance: float = 0.05

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "RangeExpectation":
        if data is None:
            return cls()
        return cls(
            min=data.get("min"),
            max=data.get("max"),
            approx=data.get("approx"),
            tolerance=float(data.get("tolerance", 0.05)),
        )


@dataclass
class OverlayDescriptor:
    url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "OverlayDescriptor | None":
        if data is None:
            return None
        metadata = data.get("metadata") if isinstance(data, dict) else None
        return cls(
            url=data.get("url") if isinstance(data, dict) else None,
            metadata=dict(metadata or {}),
        )


@dataclass
class ClipCase:
    name: str
    motion_strength: float
    audio_energy: float
    peak_energy: float
    keyword_score: float
    duration_ms: int
    target_duration_ms: int
    weights: Dict[str, float]
    bias: float
    threshold: float
    passes_threshold: Optional[bool]
    expected_confidence: RangeExpectation
    component_expectations: Dict[str, RangeExpectation] = field(default_factory=dict)
    reference_artifacts: List[str] = field(default_factory=list)
    locale: str = "en-US"
    genre: str = "general"
    frame_diff_expectation: RangeExpectation = field(
        default_factory=RangeExpectation
    )
    golden_artifact_uri: Optional[str] = None
    failure_overlay: Optional[OverlayDescriptor] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ClipCase":
        components = {
            key: RangeExpectation.from_dict(value)
            for key, value in (data.get("components") or {}).items()
        }
        return cls(
            name=data["name"],
            motion_strength=float(data["motion_strength"]),
            audio_energy=float(data["audio_energy"]),
            peak_energy=float(data["peak_energy"]),
            keyword_score=float(data["keyword_score"]),
            duration_ms=int(data["duration_ms"]),
            target_duration_ms=int(data.get("target_duration_ms", 0)),
            weights={key: float(value) for key, value in data.get("weights", {}).items()},
            bias=float(data.get("bias", 0.0)),
            threshold=float(data.get("threshold", 0.0)),
            passes_threshold=data.get("passes_threshold"),
            expected_confidence=RangeExpectation.from_dict(
                data.get("expected_confidence")
            ),
            component_expectations=components,
            reference_artifacts=[str(item) for item in data.get("reference_artifacts", [])],
            locale=data.get("locale", "en-US"),
            genre=data.get("genre", "general"),
            frame_diff_expectation=RangeExpectation.from_dict(
                data.get("frame_diff_expectation")
            ),
            golden_artifact_uri=data.get("golden_artifact_uri"),
            failure_overlay=OverlayDescriptor.from_dict(data.get("failure_overlay")),
        )


@dataclass
class SubtitleCase:
    name: str
    locale: str | None
    preset: Optional[str]
    overrides: Dict[str, Any]
    settings_overrides: Dict[str, Any]
    expected: Dict[str, Any]
    reference_artifacts: List[str] = field(default_factory=list)
    failure_overlay: Optional[OverlayDescriptor] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SubtitleCase":
        return cls(
            name=data["name"],
            locale=data.get("locale"),
            preset=data.get("preset"),
            overrides=data.get("overrides", {}),
            settings_overrides=data.get("settings_overrides", {}),
            expected=data.get("expected", {}),
            reference_artifacts=[str(item) for item in data.get("reference_artifacts", [])],
            failure_overlay=OverlayDescriptor.from_dict(data.get("failure_overlay")),
        )


@dataclass
class MixCase:
    name: str
    locale: str | None
    settings_overrides: Dict[str, Any]
    expectations: Dict[str, Any]
    reference_artifacts: List[str] = field(default_factory=list)
    failure_overlay: Optional[OverlayDescriptor] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MixCase":
        return cls(
            name=data["name"],
            locale=data.get("locale"),
            settings_overrides=data.get("settings_overrides", {}),
            expectations=data.get("expectations", {}),
            reference_artifacts=[str(item) for item in data.get("reference_artifacts", [])],
            failure_overlay=OverlayDescriptor.from_dict(data.get("failure_overlay")),
        )


@dataclass
class WatermarkCase:
    name: str
    position: str
    expected_x: str
    expected_y: str
    aspect_ratio: str | None = None
    reference_artifacts: List[str] = field(default_factory=list)
    failure_overlay: Optional[OverlayDescriptor] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WatermarkCase":
        return cls(
            name=data["name"],
            position=data["position"],
            expected_x=str(data["expected_x"]),
            expected_y=str(data["expected_y"]),
            aspect_ratio=data.get("aspect_ratio"),
            reference_artifacts=[str(item) for item in data.get("reference_artifacts", [])],
            failure_overlay=OverlayDescriptor.from_dict(data.get("failure_overlay")),
        )


@dataclass
class QADataset:
    version: str = "1.0"
    clip_cases: List[ClipCase] = field(default_factory=list)
    subtitle_cases: List[SubtitleCase] = field(default_factory=list)
    mix_cases: List[MixCase] = field(default_factory=list)
    watermark_cases: List[WatermarkCase] = field(default_factory=list)


def load_dataset(path: Optional[Path] = None) -> QADataset:
    if path is None:
        path = Path(__file__).resolve().parent / "datasets" / "baseline.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return QADataset(
        version=str(raw.get("version", "1.0")),
        clip_cases=[ClipCase.from_dict(item) for item in raw.get("clip_cases", [])],
        subtitle_cases=[
            SubtitleCase.from_dict(item) for item in raw.get("subtitle_cases", [])
        ],
        mix_cases=[MixCase.from_dict(item) for item in raw.get("mix_cases", [])],
        watermark_cases=[
            WatermarkCase.from_dict(item) for item in raw.get("watermark_cases", [])
        ],
    )
