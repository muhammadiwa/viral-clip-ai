"""Export heuristics available without FFmpeg bindings."""

from __future__ import annotations


def watermark_position(position: str) -> tuple[str, str]:
    margin = 40
    mapping = {
        "top-left": (str(margin), str(margin)),
        "top-right": (f"main_w - overlay_w - {margin}", str(margin)),
        "bottom-left": (str(margin), f"main_h - overlay_h - {margin}"),
        "bottom-right": (
            f"main_w - overlay_w - {margin}",
            f"main_h - overlay_h - {margin}",
        ),
        "center": (
            "(main_w/2) - (overlay_w/2)",
            "main_h - (overlay_h * 1.5)",
        ),
        "center-lower-third": (
            "(main_w/2) - (overlay_w/2)",
            "main_h - (overlay_h * 1.5)",
        ),
    }
    return mapping.get(position, mapping["bottom-right"])
