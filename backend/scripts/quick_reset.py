#!/usr/bin/env python3
"""
Quick reset script - no confirmation needed.
Use with caution!
"""
import os
import shutil
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.db.base import Base

settings = get_settings()


def main():
    print("🔄 Quick Reset Starting...")
    
    # 1. Reset database by dropping and recreating tables
    print("📦 Resetting database...")
    try:
        # Close any existing connections
        engine.dispose()
        
        # Drop all tables
        Base.metadata.drop_all(bind=engine)
        print("   ✓ Tables dropped")
        
        # Recreate all tables
        Base.metadata.create_all(bind=engine)
        print("   ✓ Tables recreated")
    except Exception as e:
        print(f"   ⚠️  Database reset error: {e}")
        print("   Trying to continue anyway...")
    
    # 2. Clean media
    media_root = Path(settings.media_root)
    print(f"🗑️  Cleaning media: {media_root}")
    
    if media_root.exists():
        for item in media_root.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
    
    # 3. Create structure
    folders = [
        "videos",
        "audio/extracted",
        "audio/dubs",
        "thumbnails/videos",
        "thumbnails/clips",
        "clips",
        "exports",
        "temp",
    ]
    
    for folder in folders:
        (media_root / folder).mkdir(parents=True, exist_ok=True)
        (media_root / folder / ".gitkeep").touch()
    print("   ✓ Media folders created")
    
    # 4. Seed data
    print("🌱 Seeding data...")
    db = SessionLocal()
    try:
        from app.models import SubtitleStyle, User
        
        # Check if user exists
        user = db.query(User).filter(User.email == "demo@example.com").first()
        if not user:
            user = User(
                email="demo@example.com",
                password_hash="demo_hash",
                credits=100,
            )
            db.add(user)
            db.commit()
            print("   ✓ Created demo user")
        else:
            print("   ✓ Demo user already exists")
        
        styles = [
            ("Classic White", {"fontFamily": "Arial", "fontSize": 48, "fontColor": "#FFFFFF", "strokeColor": "#000000", "strokeWidth": 2}, True),
            ("Bold Yellow", {"fontFamily": "Impact", "fontSize": 52, "fontColor": "#FFFF00", "strokeColor": "#000000", "strokeWidth": 3}, False),
            ("TikTok Style", {"fontFamily": "Proxima Nova", "fontSize": 56, "fontColor": "#FFFFFF", "strokeColor": "#000000", "strokeWidth": 4, "highlightColor": "#FF0050"}, False),
        ]
        
        for name, style_json, is_default_global in styles:
            existing = db.query(SubtitleStyle).filter(SubtitleStyle.name == name).first()
            if not existing:
                db.add(SubtitleStyle(user_id=user.id, name=name, style_json=style_json, is_default_global=is_default_global))
        
        db.commit()
        print("   ✓ Subtitle styles seeded")
    finally:
        db.close()
    
    print()
    print("✅ Reset complete!")
    print()
    print("Next: Restart backend and worker")


if __name__ == "__main__":
    main()
