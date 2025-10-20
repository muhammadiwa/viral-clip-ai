"""Expose Celery tasks so autodiscovery loads them."""

from importlib import import_module
import warnings


_TASK_MODULES = [
    "ingest",
    "transcode",
    "transcription",
    "alignment",
    "clip_discovery",
    "subtitle_render",
    "tts",
    "retell",
    "export",
]

__all__: list[str] = []

for module in _TASK_MODULES:
    try:
        import_module(f"{__name__}.{module}")
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency guard
        warnings.warn(
            f"Skipping task module '{module}' during import because dependency '{exc.name}' is missing.",
            RuntimeWarning,
            stacklevel=2,
        )
        continue
    __all__.append(module)
