"""
Seed script for creating enhanced subtitle styles with animations.

Run with: 
  cd backend
  python -m scripts.seed_subtitle_styles
"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.models import SubtitleStyle


# Enhanced subtitle styles with various animations and looks
SUBTITLE_STYLES = [
    # === BASIC STYLES ===
    {
        "name": "Bold Pop",
        "style_json": {
            "fontFamily": "Arial Black",
            "fontSize": 76,
            "fontColor": "#FFFFFF",
            "bold": True,
            "outlineWidth": 4,
            "outlineColor": "#000000",
            "shadowOffset": 0,
            "alignment": 2,
            "position": "bottom",
            "animation": "word_highlight",
            "highlightColor": "#FFD700",
            "highlightStyle": "color",
        },
        "is_default_global": True,
    },
    {
        "name": "Minimal Clean",
        "style_json": {
            "fontFamily": "Inter",
            "fontSize": 64,
            "fontColor": "#FFFFFF",
            "bold": False,
            "outlineWidth": 2,
            "outlineColor": "#000000",
            "shadowOffset": 0,
            "alignment": 2,
            "position": "bottom",
            "animation": "none",
        },
        "is_default_global": False,
    },
    {
        "name": "Cinematic",
        "style_json": {
            "fontFamily": "Space Grotesk",
            "fontSize": 56,
            "fontColor": "#FFFFFF",
            "bold": False,
            "outlineWidth": 0,
            "outlineColor": "#000000",
            "shadowOffset": 3,
            "alignment": 2,
            "position": "middle",
            "animation": "none",
            "backgroundColor": "rgba(0,0,0,0.5)",
        },
        "is_default_global": False,
    },
    
    # === HIGHLIGHT/KARAOKE STYLES ===
    {
        "name": "Karaoke Yellow",
        "style_json": {
            "fontFamily": "Arial Black",
            "fontSize": 76,
            "fontColor": "#FFFFFF",
            "bold": True,
            "outlineWidth": 4,
            "outlineColor": "#000000",
            "shadowOffset": 0,
            "alignment": 2,
            "position": "bottom",
            "animation": "word_highlight",
            "highlightColor": "#FFD700",  # Gold/Yellow highlight
            "highlightStyle": "color",    # Change text color
        },
        "is_default_global": False,
    },
    {
        "name": "Karaoke Blue Box",
        "style_json": {
            "fontFamily": "Arial Black",
            "fontSize": 72,
            "fontColor": "#FFFFFF",
            "bold": True,
            "outlineWidth": 3,
            "outlineColor": "#000000",
            "shadowOffset": 0,
            "alignment": 2,
            "position": "bottom",
            "animation": "word_highlight",
            "highlightColor": "#3B82F6",  # Blue
            "highlightStyle": "background",  # Background box
            "highlightPadding": 8,
        },
        "is_default_global": False,
    },
    {
        "name": "Karaoke Green Glow",
        "style_json": {
            "fontFamily": "Impact",
            "fontSize": 80,
            "fontColor": "#FFFFFF",
            "bold": True,
            "outlineWidth": 4,
            "outlineColor": "#000000",
            "shadowOffset": 0,
            "alignment": 2,
            "position": "bottom",
            "animation": "word_highlight",
            "highlightColor": "#22C55E",  # Green
            "highlightStyle": "glow",     # Glow effect
            "glowRadius": 10,
        },
        "is_default_global": False,
    },
    {
        "name": "Karaoke Red Underline",
        "style_json": {
            "fontFamily": "Arial Black",
            "fontSize": 72,
            "fontColor": "#FFFFFF",
            "bold": True,
            "outlineWidth": 3,
            "outlineColor": "#000000",
            "shadowOffset": 0,
            "alignment": 2,
            "position": "bottom",
            "animation": "word_highlight",
            "highlightColor": "#EF4444",  # Red
            "highlightStyle": "underline",
            "underlineThickness": 4,
        },
        "is_default_global": False,
    },
    {
        "name": "Karaoke Purple Scale",
        "style_json": {
            "fontFamily": "Arial Black",
            "fontSize": 68,
            "fontColor": "#FFFFFF",
            "bold": True,
            "outlineWidth": 4,
            "outlineColor": "#000000",
            "shadowOffset": 0,
            "alignment": 2,
            "position": "bottom",
            "animation": "word_highlight",
            "highlightColor": "#A855F7",  # Purple
            "highlightStyle": "scale",    # Scale up current word
            "scaleAmount": 1.2,
        },
        "is_default_global": False,
    },
    
    # === MODERN STYLES ===
    {
        "name": "TikTok Style",
        "style_json": {
            "fontFamily": "Proxima Nova",
            "fontSize": 80,
            "fontColor": "#FFFFFF",
            "bold": True,
            "outlineWidth": 0,
            "outlineColor": "#000000",
            "shadowOffset": 4,
            "alignment": 2,
            "position": "bottom",
            "animation": "word_highlight",
            "highlightColor": "#FF0050",  # TikTok pink
            "highlightStyle": "background",
            "highlightPadding": 6,
            "borderRadius": 8,
        },
        "is_default_global": False,
    },
    {
        "name": "YouTube Shorts",
        "style_json": {
            "fontFamily": "Roboto",
            "fontSize": 72,
            "fontColor": "#FFFFFF",
            "bold": True,
            "outlineWidth": 3,
            "outlineColor": "#000000",
            "shadowOffset": 2,
            "alignment": 2,
            "position": "bottom",
            "animation": "word_highlight",
            "highlightColor": "#FF0000",  # YouTube red
            "highlightStyle": "color",
        },
        "is_default_global": False,
    },
    {
        "name": "Instagram Reels",
        "style_json": {
            "fontFamily": "SF Pro Display",
            "fontSize": 68,
            "fontColor": "#FFFFFF",
            "bold": True,
            "outlineWidth": 2,
            "outlineColor": "#000000",
            "shadowOffset": 0,
            "alignment": 2,
            "position": "bottom",
            "animation": "word_highlight",
            "highlightColor": "#E1306C",  # Instagram gradient pink
            "highlightStyle": "gradient",
            "gradientColors": ["#405DE6", "#5851DB", "#833AB4", "#C13584", "#E1306C", "#FD1D1D"],
        },
        "is_default_global": False,
    },
    
    # === SPECIAL EFFECTS ===
    {
        "name": "Neon Glow",
        "style_json": {
            "fontFamily": "Arial Black",
            "fontSize": 76,
            "fontColor": "#FFFFFF",
            "bold": True,
            "outlineWidth": 3,
            "outlineColor": "#000000",
            "shadowOffset": 0,
            "alignment": 2,
            "position": "bottom",
            "animation": "word_highlight",
            "highlightColor": "#00FFFF",  # Cyan glow
            "highlightStyle": "glow",
            "glowColor": "#00FFFF",
        },
        "is_default_global": False,
    },
    {
        "name": "Typewriter",
        "style_json": {
            "fontFamily": "Courier New",
            "fontSize": 64,
            "fontColor": "#00FF00",  # Matrix green
            "bold": False,
            "outlineWidth": 0,
            "outlineColor": "#000000",
            "shadowOffset": 0,
            "alignment": 2,
            "position": "bottom",
            "animation": "typewriter",
            "backgroundColor": "rgba(0,0,0,0.8)",
            "typingSpeed": 50,  # ms per character
        },
        "is_default_global": False,
    },
    {
        "name": "Comic Book",
        "style_json": {
            "fontFamily": "Comic Sans MS",
            "fontSize": 72,
            "fontColor": "#FFFF00",  # Yellow
            "bold": True,
            "outlineWidth": 5,
            "outlineColor": "#000000",
            "shadowOffset": 4,
            "alignment": 2,
            "position": "bottom",
            "animation": "word_highlight",
            "highlightColor": "#FF6B6B",
            "highlightStyle": "comic_burst",
        },
        "is_default_global": False,
    },
    
    # === POSITION VARIANTS ===
    {
        "name": "Top Center",
        "style_json": {
            "fontFamily": "Arial Black",
            "fontSize": 72,
            "fontColor": "#FFFFFF",
            "bold": True,
            "outlineWidth": 4,
            "outlineColor": "#000000",
            "shadowOffset": 0,
            "alignment": 8,  # Top center
            "position": "top",
            "marginV": 100,
            "animation": "none",
        },
        "is_default_global": False,
    },
    {
        "name": "Middle Center",
        "style_json": {
            "fontFamily": "Arial Black",
            "fontSize": 80,
            "fontColor": "#FFFFFF",
            "bold": True,
            "outlineWidth": 4,
            "outlineColor": "#000000",
            "shadowOffset": 0,
            "alignment": 5,  # Middle center
            "position": "middle",
            "animation": "word_highlight",
            "highlightColor": "#FFD700",
            "highlightStyle": "color",
        },
        "is_default_global": False,
    },
]


def seed_styles():
    """Seed subtitle styles to database."""
    db = SessionLocal()
    try:
        # Check existing styles
        existing = db.query(SubtitleStyle).filter(SubtitleStyle.user_id.is_(None)).all()
        existing_names = {s.name for s in existing}
        
        added = 0
        updated = 0
        
        for style_data in SUBTITLE_STYLES:
            if style_data["name"] in existing_names:
                # Update existing
                existing_style = db.query(SubtitleStyle).filter(
                    SubtitleStyle.name == style_data["name"],
                    SubtitleStyle.user_id.is_(None)
                ).first()
                if existing_style:
                    existing_style.style_json = style_data["style_json"]
                    existing_style.is_default_global = style_data["is_default_global"]
                    updated += 1
            else:
                # Create new
                style = SubtitleStyle(
                    user_id=None,
                    name=style_data["name"],
                    style_json=style_data["style_json"],
                    is_default_global=style_data["is_default_global"],
                )
                db.add(style)
                added += 1
        
        db.commit()
        print(f"✅ Subtitle styles seeded: {added} added, {updated} updated")
        print(f"   Total styles: {len(SUBTITLE_STYLES)}")
        
    finally:
        db.close()


if __name__ == "__main__":
    seed_styles()
