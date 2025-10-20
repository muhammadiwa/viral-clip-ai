"""Execute dataset-driven QA checks for media heuristics."""

from __future__ import annotations

import argparse
import math
from collections import Counter
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Iterable, Optional, Sequence

import json


from apps.workers.workers.heuristics import (
    compute_candidate_confidence,
    resolve_style,
    build_mix_profile,
    watermark_position,
)

from .dataset import (
    ClipCase,
    MixCase,
    QADataset,
    RangeExpectation,
    SubtitleCase,
    WatermarkCase,
    load_dataset,
    OverlayDescriptor,
)


ArtifactMap = dict[str, dict[str, list[str]]]


@dataclass
class FindingDetail:
    category: str
    case_name: str
    message: str
    reference_urls: list[str] = field(default_factory=list)
    reference_artifact_ids: list[str] = field(default_factory=list)
    overlay_url: Optional[str] = None
    overlay_metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class EvaluationReport:
    dataset_name: str = "baseline"
    dataset_version: str = "1.0"
    clip_cases: int = 0
    subtitle_cases: int = 0
    mix_cases: int = 0
    watermark_cases: int = 0
    failures: list[str] = field(default_factory=list)
    clip_failed_cases: set[str] = field(default_factory=set)
    subtitle_failed_cases: set[str] = field(default_factory=set)
    mix_failed_cases: set[str] = field(default_factory=set)
    watermark_failed_cases: set[str] = field(default_factory=set)
    detailed_failures: list[FindingDetail] = field(default_factory=list)
    locale_coverage: Counter[str] = field(default_factory=Counter)
    genre_coverage: Counter[str] = field(default_factory=Counter)
    frame_diff_failures: set[str] = field(default_factory=set)

    @property
    def succeeded(self) -> bool:
        return not self.failures

    @property
    def clip_pass_rate(self) -> float:
        return _pass_rate(self.clip_cases, len(self.clip_failed_cases))

    @property
    def subtitle_pass_rate(self) -> float:
        return _pass_rate(self.subtitle_cases, len(self.subtitle_failed_cases))

    @property
    def mix_pass_rate(self) -> float:
        return _pass_rate(self.mix_cases, len(self.mix_failed_cases))

    @property
    def watermark_pass_rate(self) -> float:
        return _pass_rate(self.watermark_cases, len(self.watermark_failed_cases))

    @property
    def failure_count(self) -> int:
        return len(self.failures)

    def record_case_failures(
        self,
        category: str,
        case_name: str,
        case_failures: Sequence[str],
        reference_urls: Sequence[str] | None = None,
        reference_artifact_ids: Sequence[str] | None = None,
        overlay: OverlayDescriptor | None = None,
    ) -> None:
        if not case_failures:
            return
        references = list(reference_urls or [])
        artifact_ids = [str(value) for value in (reference_artifact_ids or [])]
        overlay_url = overlay.url if overlay else None
        overlay_metadata: dict[str, object] = dict(overlay.metadata) if overlay else {}
        for failure in case_failures:
            self.failures.append(failure)
            self.detailed_failures.append(
                FindingDetail(
                    category=category,
                    case_name=case_name,
                    message=failure,
                    reference_urls=references,
                    reference_artifact_ids=artifact_ids,
                    overlay_url=overlay_url,
                    overlay_metadata=overlay_metadata,
                )
            )
        if category == "clip":
            self.clip_failed_cases.add(case_name)
        elif category == "subtitle":
            self.subtitle_failed_cases.add(case_name)
        elif category == "mix":
            self.mix_failed_cases.add(case_name)
        elif category == "watermark":
            self.watermark_failed_cases.add(case_name)

    @property
    def failure_artifacts(self) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for detail in self.detailed_failures:
            for ref in detail.reference_urls:
                if ref not in seen:
                    seen.add(ref)
                    ordered.append(ref)
        return ordered

    @property
    def failure_artifact_ids(self) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for detail in self.detailed_failures:
            for artifact_id in detail.reference_artifact_ids:
                if artifact_id not in seen:
                    seen.add(artifact_id)
                    ordered.append(artifact_id)
        return ordered

    def record_locale(self, locale: str | None) -> None:
        if not locale:
            return
        self.locale_coverage[locale] += 1

    def record_genre(self, genre: str | None) -> None:
        if not genre:
            return
        self.genre_coverage[genre] += 1

    def findings_payload(self) -> list[dict[str, object]]:
        payload: list[dict[str, object]] = []
        for detail in self.detailed_failures:
            payload.append(
                {
                    "category": detail.category,
                    "case_name": detail.case_name,
                    "message": detail.message,
                    "reference_urls": detail.reference_urls,
                    "reference_artifact_ids": detail.reference_artifact_ids,
                    "overlay_url": detail.overlay_url,
                    "overlay_metadata": detail.overlay_metadata,
                }
            )
        return payload

    def metrics(self) -> list[dict[str, object]]:
        dataset_label = {"dataset": self.dataset_name, "version": self.dataset_version}
        metrics: list[dict[str, object]] = [
            {
                "name": "qa.clip.pass_rate",
                "metric_type": "gauge",
                "value": self.clip_pass_rate,
                "labels": dataset_label,
            },
            {
                "name": "qa.subtitle.pass_rate",
                "metric_type": "gauge",
                "value": self.subtitle_pass_rate,
                "labels": dataset_label,
            },
            {
                "name": "qa.mix.pass_rate",
                "metric_type": "gauge",
                "value": self.mix_pass_rate,
                "labels": dataset_label,
            },
            {
                "name": "qa.watermark.pass_rate",
                "metric_type": "gauge",
                "value": self.watermark_pass_rate,
                "labels": dataset_label,
            },
            {
                "name": "qa.total.failure_count",
                "metric_type": "gauge",
                "value": float(self.failure_count),
                "labels": dataset_label,
            },
        ]

        for locale, count in self.locale_coverage.items():
            metrics.append(
                {
                    "name": "qa.coverage.locale",
                    "metric_type": "gauge",
                    "value": float(count),
                    "labels": {**dataset_label, "locale": locale},
                }
            )
        for genre, count in self.genre_coverage.items():
            metrics.append(
                {
                    "name": "qa.coverage.genre",
                    "metric_type": "gauge",
                    "value": float(count),
                    "labels": {**dataset_label, "genre": genre},
                }
            )
        metrics.append(
            {
                "name": "qa.clip.frame_diff_failures",
                "metric_type": "gauge",
                "value": float(len(self.frame_diff_failures)),
                "labels": dataset_label,
            }
        )
        return metrics

    def to_dict(self) -> dict[str, object]:
        return {
            "dataset_name": self.dataset_name,
            "dataset_version": self.dataset_version,
            "clip_cases": self.clip_cases,
            "subtitle_cases": self.subtitle_cases,
            "mix_cases": self.mix_cases,
            "watermark_cases": self.watermark_cases,
            "clip_pass_rate": self.clip_pass_rate,
            "subtitle_pass_rate": self.subtitle_pass_rate,
            "mix_pass_rate": self.mix_pass_rate,
            "watermark_pass_rate": self.watermark_pass_rate,
            "failure_count": self.failure_count,
            "failures": list(self.failures),
            "failure_artifact_urls": self.failure_artifacts,
            "failure_artifact_ids": self.failure_artifact_ids,
            "locale_coverage": dict(self.locale_coverage),
            "genre_coverage": dict(self.genre_coverage),
            "frame_diff_failures": len(self.frame_diff_failures),
            "frame_diff_failure_cases": list(self.frame_diff_failures),
        }


@dataclass
class QASettings:
    subtitle_default_preset: str = "brand-kit"
    subtitle_brand_preset_name: str = "brand-kit"
    subtitle_brand_font_family: str | None = None
    subtitle_brand_text_color: str | None = None
    subtitle_brand_background_color: str | None = None
    subtitle_brand_stroke_color: str | None = None
    subtitle_brand_highlight_color: str | None = None
    subtitle_brand_uppercase: bool = False
    tts_music_gain_db: float = -9.0
    tts_voice_gain_db: float = -1.5
    tts_loudness_target_i: float = -16.0
    tts_loudness_true_peak: float = -1.5
    tts_loudness_range: float = 11.0


def _check_range(label: str, value: float, expectation: RangeExpectation, failures: list[str]) -> None:
    if expectation.min is not None and value < expectation.min:
        failures.append(f"{label}={value:.3f} below min {expectation.min:.3f}")
    if expectation.max is not None and value > expectation.max:
        failures.append(f"{label}={value:.3f} above max {expectation.max:.3f}")
    if expectation.approx is not None:
        tolerance = expectation.tolerance
        if math.fabs(value - expectation.approx) > tolerance:
            failures.append(
                f"{label}={value:.3f} outside ±{tolerance:.3f} of {expectation.approx:.3f}"
            )


def _ensure_equal(label: str, actual, expected, failures: list[str]) -> None:
    if actual != expected:
        failures.append(f"{label} expected {expected!r} but found {actual!r}")


def _lookup_artifact_ids(
    artifact_map: ArtifactMap | None, category: str, case_name: str
) -> list[str]:
    if not artifact_map:
        return []
    cases = artifact_map.get(category)
    if not cases:
        return []
    values = cases.get(case_name)
    if values is None:
        return []
    if isinstance(values, (str, bytes)):
        return [str(values)]
    return [str(value) for value in values]


def _load_artifact_map(path: Optional[Path]) -> ArtifactMap:
    if path is None:
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    artifact_map: ArtifactMap = {}
    for category, items in raw.items():
        category_map: dict[str, list[str]] = {}
        for case_name, identifiers in items.items():
            if isinstance(identifiers, (str, bytes)):
                category_map[case_name] = [str(identifiers)]
            else:
                category_map[case_name] = [str(value) for value in identifiers]
        artifact_map[category] = category_map
    return artifact_map


def _evaluate_clip_cases(
    dataset: QADataset,
    report: EvaluationReport,
    artifact_map: ArtifactMap | None,
) -> None:
    for case in dataset.clip_cases:
        case_failures: list[str] = []
        report.record_locale(case.locale)
        report.record_genre(case.genre)
        confidence, components = compute_candidate_confidence(
            motion_strength=case.motion_strength,
            audio_energy=case.audio_energy,
            peak_energy=case.peak_energy,
            keyword_score=case.keyword_score,
            duration_ms=case.duration_ms,
            target_duration_ms=case.target_duration_ms,
            weight_motion=case.weights.get("motion", 0.0),
            weight_audio=case.weights.get("audio", 0.0),
            weight_keywords=case.weights.get("keywords", 0.0),
            weight_duration=case.weights.get("duration", 0.0),
            bias=case.bias,
        )
        _check_range(
            f"clip[{case.name}].confidence",
            confidence,
            case.expected_confidence,
            case_failures,
        )
        for component, expectation in case.component_expectations.items():
            value = components.get(component)
            if value is None:
                case_failures.append(f"clip[{case.name}] missing component {component}")
                continue
            _check_range(
                f"clip[{case.name}].{component}",
                value,
                expectation,
                case_failures,
            )
        if case.passes_threshold is not None:
            passes = confidence >= case.threshold
            if passes != case.passes_threshold:
                case_failures.append(
                    f"clip[{case.name}] threshold expectation failed: {confidence:.3f} vs {case.threshold:.3f}"
                )
        if (
            case.frame_diff_expectation.min is not None
            or case.frame_diff_expectation.max is not None
            or case.frame_diff_expectation.approx is not None
        ):
            target = max(case.target_duration_ms, 1)
            diff_ratio = math.fabs(case.duration_ms - target) / target
            before = len(case_failures)
            _check_range(
                f"clip[{case.name}].frame_diff_ratio",
                diff_ratio,
                case.frame_diff_expectation,
                case_failures,
            )
            if len(case_failures) > before:
                report.frame_diff_failures.add(case.name)
        if case.golden_artifact_uri and case.golden_artifact_uri not in case.reference_artifacts:
            case.reference_artifacts.append(case.golden_artifact_uri)
        report.clip_cases += 1
        artifact_ids = _lookup_artifact_ids(artifact_map, "clip", case.name)
        report.record_case_failures(
            "clip",
            case.name,
            case_failures,
            case.reference_artifacts,
            artifact_ids,
            overlay=case.failure_overlay,
        )


def _settings_with_overrides(base: QASettings, overrides: dict[str, object]) -> QASettings:
    if not overrides:
        return base
    return replace(base, **overrides)


def _evaluate_subtitle_cases(
    dataset: QADataset,
    report: EvaluationReport,
    base_settings: QASettings,
    artifact_map: ArtifactMap | None,
) -> None:
    for case in dataset.subtitle_cases:
        case_failures: list[str] = []
        report.record_locale(case.locale)
        settings = _settings_with_overrides(base_settings, case.settings_overrides)
        style = resolve_style(case.preset, case.overrides, settings=settings)
        for key, expectation in case.expected.items():
            actual = style.get(key)
            if isinstance(expectation, dict):
                range_expectation = RangeExpectation.from_dict(expectation)
                if actual is None:
                    case_failures.append(f"subtitle[{case.name}] missing {key}")
                else:
                    _check_range(
                        f"subtitle[{case.name}].{key}",
                        float(actual),
                        range_expectation,
                        case_failures,
                    )
            else:
                _ensure_equal(
                    f"subtitle[{case.name}].{key}",
                    actual,
                    expectation,
                    case_failures,
                )
        report.subtitle_cases += 1
        artifact_ids = _lookup_artifact_ids(artifact_map, "subtitle", case.name)
        report.record_case_failures(
            "subtitle",
            case.name,
            case_failures,
            case.reference_artifacts,
            artifact_ids,
            overlay=case.failure_overlay,
        )


def _evaluate_mix_cases(
    dataset: QADataset,
    report: EvaluationReport,
    base_settings: QASettings,
    artifact_map: ArtifactMap | None,
) -> None:
    for case in dataset.mix_cases:
        case_failures: list[str] = []
        report.record_locale(case.locale)
        settings = _settings_with_overrides(base_settings, case.settings_overrides)
        profile = build_mix_profile(settings)
        for key, expectation in case.expectations.items():
            value = getattr(profile, key, None)
            if value is None:
                case_failures.append(
                    f"mix[{case.name}] missing expectation value for {key}"
                )
                continue
            if isinstance(expectation, dict):
                _check_range(
                    f"mix[{case.name}].{key}",
                    float(value),
                    RangeExpectation.from_dict(expectation),
                    case_failures,
                )
            else:
                _ensure_equal(
                    f"mix[{case.name}].{key}",
                    float(value),
                    float(expectation),
                    case_failures,
                )
        report.mix_cases += 1
        artifact_ids = _lookup_artifact_ids(artifact_map, "mix", case.name)
        report.record_case_failures(
            "mix",
            case.name,
            case_failures,
            case.reference_artifacts,
            artifact_ids,
            overlay=case.failure_overlay,
        )


def _evaluate_watermark_cases(
    dataset: QADataset,
    report: EvaluationReport,
    artifact_map: ArtifactMap | None,
) -> None:
    for case in dataset.watermark_cases:
        case_failures: list[str] = []
        x, y = watermark_position(case.position)
        _ensure_equal(
            f"watermark[{case.name}].x",
            x,
            case.expected_x,
            case_failures,
        )
        _ensure_equal(
            f"watermark[{case.name}].y",
            y,
            case.expected_y,
            case_failures,
        )
        report.watermark_cases += 1
        artifact_ids = _lookup_artifact_ids(artifact_map, "watermark", case.name)
        report.record_case_failures(
            "watermark",
            case.name,
            case_failures,
            case.reference_artifacts,
            artifact_ids,
            overlay=case.failure_overlay,
        )


def run(
    dataset_path: Optional[Path] = None,
    *,
    artifact_map: ArtifactMap | None = None,
) -> EvaluationReport:
    dataset = load_dataset(dataset_path)
    dataset_name = dataset_path.stem if dataset_path else "baseline"
    base_settings = QASettings()
    report = EvaluationReport(dataset_name=dataset_name, dataset_version=dataset.version)
    _evaluate_clip_cases(dataset, report, artifact_map)
    _evaluate_subtitle_cases(dataset, report, base_settings, artifact_map)
    _evaluate_mix_cases(dataset, report, base_settings, artifact_map)
    _evaluate_watermark_cases(dataset, report, artifact_map)
    return report


def _format_summary(report: EvaluationReport) -> str:
    return (
        "QA summary: "
        f"clips={report.clip_cases}, "
        f"subtitles={report.subtitle_cases}, "
        f"mixes={report.mix_cases}, "
        f"watermarks={report.watermark_cases}, "
        f"failures={report.failure_count}"
    )


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run media QA regression checks")
    parser.add_argument("--dataset", type=Path, default=None, help="Path to QA dataset JSON")
    parser.add_argument(
        "--report-json",
        type=Path,
        default=None,
        help="Optional path to write the QA summary JSON report",
    )
    parser.add_argument(
        "--report-api-base",
        type=str,
        default=None,
        help="FastAPI base URL for recording observability metrics",
    )
    parser.add_argument(
        "--report-token",
        type=str,
        default=None,
        help="Bearer token used when reporting metrics",
    )
    parser.add_argument(
        "--report-org-id",
        type=str,
        default=None,
        help="Organization identifier for observability metrics",
    )
    parser.add_argument(
        "--artifact-map",
        type=Path,
        default=None,
        help="Optional JSON map of QA cases to generated artifact IDs",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    artifact_map = _load_artifact_map(args.artifact_map)
    report = run(args.dataset, artifact_map=artifact_map)
    if args.report_json is not None:
        args.report_json.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    if args.report_api_base and args.report_token and args.report_org_id:
        _push_metrics(
            report,
            api_base=args.report_api_base,
            token=args.report_token,
            org_id=args.report_org_id,
        )
    if report.succeeded:
        print(_format_summary(report))
        return 0
    for failure in report.failures:
        print(f"FAIL: {failure}")
    print(_format_summary(report))
    return 1


def _pass_rate(total: int, failed: int) -> float:
    if total <= 0:
        return 1.0
    return max(0.0, min(1.0, (total - failed) / total))


def _push_metrics(report: EvaluationReport, *, api_base: str, token: str, org_id: str) -> None:
    try:
        import httpx
    except ImportError as exc:
        raise RuntimeError(
            "httpx is required to report QA metrics. Install it via apps/workers/requirements.txt."
        ) from exc

    base = api_base.rstrip("/")
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Org-ID": org_id,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    metrics_url = f"{base}/v1/observability/metrics"
    qa_runs_url = f"{base}/v1/observability/qa-runs"
    with httpx.Client(timeout=10.0) as client:
        for metric in report.metrics():
            response = client.post(metrics_url, json=metric, headers=headers)
            response.raise_for_status()
        qa_payload = {
            "dataset_name": report.dataset_name,
            "dataset_version": report.dataset_version,
            "clip_cases": report.clip_cases,
            "subtitle_cases": report.subtitle_cases,
            "mix_cases": report.mix_cases,
            "watermark_cases": report.watermark_cases,
            "clip_failures": len(report.clip_failed_cases),
            "subtitle_failures": len(report.subtitle_failed_cases),
            "mix_failures": len(report.mix_failed_cases),
            "watermark_failures": len(report.watermark_failed_cases),
            "failure_details": list(report.failures),
            "clip_pass_rate": report.clip_pass_rate,
            "subtitle_pass_rate": report.subtitle_pass_rate,
            "mix_pass_rate": report.mix_pass_rate,
            "watermark_pass_rate": report.watermark_pass_rate,
            "failure_artifact_urls": report.failure_artifacts,
            "failure_artifact_ids": report.failure_artifact_ids,
            "locale_coverage": dict(report.locale_coverage),
            "genre_coverage": dict(report.genre_coverage),
            "frame_diff_failures": len(report.frame_diff_failures),
            "findings": report.findings_payload(),
        }
        response = client.post(qa_runs_url, json=qa_payload, headers=headers)
        response.raise_for_status()


if __name__ == "__main__":
    raise SystemExit(main())
