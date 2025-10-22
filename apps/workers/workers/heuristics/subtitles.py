"""Subtitle styling heuristics shared across workers and QA tests."""

from __future__ import annotations

from typing import Dict, Optional

DEFAULT_SUBTITLE_STYLE: Dict[str, object] = {
    "font_family": "Inter",
    "font_size": 48,
    "text_color": "#FFFFFF",
    "background_color": "#00000080",
    "stroke_color": "#000000",
    "highlight_color": "#FDE047",
    "outline": 2,
    "shadow": 1,
    "alignment": 2,
    "margin_horizontal": 40,
    "margin_vertical": 60,
    "fade_in_ms": 120,
    "fade_out_ms": 90,
    "karaoke": False,
    "uppercase": False,
}

BASE_SUBTITLE_PRESETS: Dict[str, Dict[str, object]] = {
    "bold-yellow": {
        "font_family": "Poppins",
        "font_size": 54,
        "text_color": "#FFFFFF",
        "background_color": "#111827B3",
        "stroke_color": "#FACC15",
        "outline": 3,
        "shadow": 2,
        "margin_vertical": 72,
    },
    "clean-white": {
        "font_family": "Inter",
        "font_size": 46,
        "text_color": "#F8FAFC",
        "background_color": "#00000055",
        "stroke_color": "#020617",
        "outline": 1,
        "shadow": 0,
        "uppercase": False,
        "margin_vertical": 64,
    },
    "karaoke-neon": {
        "font_family": "Montserrat",
        "font_size": 52,
        "text_color": "#F5F3FF",
        "background_color": "#11182740",
        "stroke_color": "#A855F7",
        "highlight_color": "#10B981",
        "outline": 2,
        "shadow": 3,
        "karaoke": True,
        "fade_in_ms": 80,
        "fade_out_ms": 60,
        "margin_vertical": 70,
    },
}


def _brand_overrides(settings) -> Dict[str, object]:
    overrides: Dict[str, object] = {}
    if getattr(settings, "subtitle_brand_font_family", None):
        overrides["font_family"] = settings.subtitle_brand_font_family
    if getattr(settings, "subtitle_brand_text_color", None):
        overrides["text_color"] = settings.subtitle_brand_text_color
    if getattr(settings, "subtitle_brand_background_color", None):
        overrides["background_color"] = settings.subtitle_brand_background_color
    if getattr(settings, "subtitle_brand_stroke_color", None):
        overrides["stroke_color"] = settings.subtitle_brand_stroke_color
    if getattr(settings, "subtitle_brand_highlight_color", None):
        overrides["highlight_color"] = settings.subtitle_brand_highlight_color
    if getattr(settings, "subtitle_brand_uppercase", False):
        overrides["uppercase"] = True
    return overrides


def _available_presets(settings) -> Dict[str, Dict[str, object]]:
    presets = dict(BASE_SUBTITLE_PRESETS)
    brand_overrides = _brand_overrides(settings)
    preset_name = getattr(settings, "subtitle_brand_preset_name", "brand-kit")
    if brand_overrides:
        presets[preset_name] = brand_overrides
    return presets


def resolve_style(
    preset: Optional[str], overrides: Dict[str, object], *, settings
) -> Dict[str, object]:
    style = dict(DEFAULT_SUBTITLE_STYLE)
    selected = preset or getattr(settings, "subtitle_default_preset", "brand-kit")
    presets = _available_presets(settings)
    if selected and selected in presets:
        style.update(presets[selected])
    elif not preset:
        style.update(_brand_overrides(settings))
    # Always layer brand overrides to respect environment or project-specific settings.
    style.update(_brand_overrides(settings))
    for key, value in overrides.items():
        if value is not None:
            style[key] = value
    return style
