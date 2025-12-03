#!/usr/bin/env python3
"""
Script to reset database and cleanup media files.
Creates a clean slate with proper folder structure.
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


def reset_database():
    """Drop all tables and recreate them."""
    print("🗑️  Resetting database...")
    
    # Drop all tables
    Base.metadata.drop_all(bind=engine)
    print("   ✓ All tables dropped")
    
    # Recreate all tables
    Base.metadata.create_all(bind=engine)
    print("   ✓ All tables recreated")
    
    print("✅ Database reset complete!")


def cleanup_media():
    """Remove all media files and recreate folder structure."""
    media_root = Path(settings.media_root)
    
    print(f"🗑️  Cleaning up media folder: {media_root}")
    
    if media_root.exists():
        # Remove all contents
        for item in media_root.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
                print(f"   ✓ Removed {item.name}/")
            else:
                item.unlink()
                print(f"   ✓ Removed {item.name}")
    
    # Create new organized structure
    folders = [
        "videos",           # Source videos: videos/{video_id}/source.mp4
        "audio/extracted",  # Extracted audio: audio/extracted/{video_id}.wav
        "audio/dubs",       # AI dubbed audio: audio/dubs/{clip_id}.mp3
        "thumbnails/videos",# Video thumbnails: thumbnails/videos/{video_id}.jpg
        "thumbnails/clips", # Clip thumbnails: thumbnails/clips/{clip_id}.jpg
        "clips",            # Generated clips: clips/{video_id}/{clip_id}.mp4
        "exports",          # Final exports: exports/{export_id}.mp4
        "temp",             # Temporary files
    ]
    
    for folder in folders:
        folder_path = media_root / folder
        folder_path.mkdir(parents=True, exist_ok=True)
        print(f"   ✓ Created {folder}/")
    
    # Create .gitkeep files
    for folder in folders:
        gitkeep = media_root / folder / ".gitkeep"
        gitkeep.touch()
    
    print("✅ Media folder cleanup complete!")


def seed_default_data():
    """Seed default subtitle styles."""
    print("🌱 Seeding default data...")
    
    db = SessionLocal()
    try:
        from app.models import SubtitleStyle, User
        
        # Create default user if not exists
        user = db.query(User).filter(User.email == "demo@example.com").first()
        if not user:
            user = User(
                email="demo@example.com",
                name="Demo User",
                hashed_password="demo",
                credits=100,
            )
            db.add(user)
            db.commit()
            print("   ✓ Created demo user")
        
        # Seed subtitle styles
        styles = [
            {
                "name": "Classic White",
                "description": "Clean white text with black outline",
                "style_json": {
                    "fontFamily": "Arial",
                    "fontSize": 48,
                    "fontColor": "#FFFFFF",
                    "strokeColor": "#000000",
                    "strokeWidth": 2,
                    "position": "bottom",
                    "animation": "none"
                },
                "is_default": True,
            },
            {
                "name": "Bold Yellow",
                "description": "Eye-catching yellow text",
                "style_json": {
                    "fontFamily": "Impact",
                    "fontSize": 52,
                    "fontColor": "#FFFF00",
                    "strokeColor": "#000000",
                    "strokeWidth": 3,
                    "position": "bottom",
                    "animation": "pop"
                },
            },
            {
                "name": "Minimal",
                "description": "Simple and clean",
                "style_json": {
                    "fontFamily": "Helvetica",
                    "fontSize": 40,
                    "fontColor": "#FFFFFF",
                    "strokeColor": "transparent",
                    "strokeWidth": 0,
                    "backgroundColor": "rgba(0,0,0,0.5)",
                    "position": "bottom",
                    "animation": "fade"
                },
            },
            {
                "name": "TikTok Style",
                "description": "Trendy TikTok-like captions",
                "style_json": {
                    "fontFamily": "Proxima Nova",
                    "fontSize": 56,
                    "fontColor": "#FFFFFF",
                    "strokeColor": "#000000",
                    "strokeWidth": 4,
                    "position": "center",
                    "animation": "bounce",
                    "highlightColor": "#FF0050"
                },
            },
        ]
        
        for style_data in styles:
            existing = db.query(SubtitleStyle).filter(
                SubtitleStyle.name == style_data["name"]
            ).first()
            if not existing:
                style = SubtitleStyle(
                    user_id=user.id,
                    **style_data
                )
                db.add(style)
                print(f"   ✓ Created style: {style_data['name']}")
        
        db.commit()
        print("✅ Default data seeded!")
        
    except Exception as e:
        print(f"❌ Error seeding data: {e}")
        db.rollback()
    finally:
        db.close()


def main():
    print("=" * 50)
    print("🔄 VIRAL CLIP AI - RESET & CLEANUP")
    print("=" * 50)
    print()
    
    # Confirm
    confirm = input("⚠️  This will DELETE all data. Continue? (yes/no): ")
    if confirm.lower() != "yes":
        print("Cancelled.")
        return
    
    print()
    
    # Step 1: Reset database
    reset_database()
    print()
    
    # Step 2: Cleanup media
    cleanup_media()
    print()
    
    # Step 3: Seed default data
    seed_default_data()
    print()
    
    print("=" * 50)
    print("🎉 RESET COMPLETE!")
    print("=" * 50)
    print()
    print("Next steps:")
    print("1. Restart backend: uvicorn app.main:app --reload")
    print("2. Restart worker: python -m app.worker.main")
    print("3. Upload a new video to test")


if __name__ == "__main__":
    main()
