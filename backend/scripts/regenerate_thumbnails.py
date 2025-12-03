#!/usr/bin/env python3
"""
Script to regenerate thumbnails for existing videos and clips.
Useful when thumbnails are missing or corrupted.
"""
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import VideoSource, Clip
from app.services import utils

settings = get_settings()


def regenerate_video_thumbnails():
    """Regenerate thumbnails for all videos."""
    db = SessionLocal()
    try:
        videos = db.query(VideoSource).filter(VideoSource.file_path.isnot(None)).all()
        print(f"Found {len(videos)} videos with file paths")
        
        regenerated = 0
        for video in videos:
            if not video.file_path or not Path(video.file_path).exists():
                print(f"  ⚠️  Video {video.id}: file not found")
                continue
            
            thumb_dir = utils.ensure_dir(Path(settings.media_root) / "thumbnails" / "videos" / str(video.id))
            thumb_path = thumb_dir / "thumb.jpg"
            thumbnail_saved = False
            
            # For YouTube videos, try to get original thumbnail
            if video.source_type == "youtube" and video.source_url:
                try:
                    from yt_dlp import YoutubeDL
                    with YoutubeDL({"quiet": True}) as ydl:
                        info = ydl.extract_info(video.source_url, download=False)
                        thumbnail_url = info.get("thumbnail")
                        if not thumbnail_url:
                            thumbnails = info.get("thumbnails", [])
                            if thumbnails:
                                best_thumb = max(thumbnails, key=lambda t: t.get("height", 0) or 0)
                                thumbnail_url = best_thumb.get("url")
                        if thumbnail_url:
                            thumbnail_saved = utils.download_thumbnail(thumbnail_url, str(thumb_path))
                            if thumbnail_saved:
                                print(f"  ✓ Video {video.id}: Downloaded YouTube thumbnail")
                except Exception as e:
                    print(f"  ⚠️  Video {video.id}: YouTube thumbnail failed: {e}")
            
            # Fallback: generate from video file
            if not thumbnail_saved:
                duration = video.duration_seconds or utils.probe_duration(video.file_path) or 10
                thumb_timestamp = duration * 0.1
                thumbnail_saved = utils.render_thumbnail(video.file_path, str(thumb_path), thumb_timestamp)
                if thumbnail_saved:
                    print(f"  ✓ Video {video.id}: Generated from video")
            
            if thumbnail_saved:
                try:
                    relative = thumb_path.relative_to(Path(settings.media_root))
                    video.thumbnail_path = f"{settings.media_base_url}/{relative.as_posix()}"
                    regenerated += 1
                except Exception:
                    video.thumbnail_path = str(thumb_path)
            else:
                print(f"  ✗ Video {video.id}: thumbnail generation failed")
        
        db.commit()
        print(f"\n✅ Regenerated {regenerated}/{len(videos)} video thumbnails")
        
    finally:
        db.close()


def regenerate_clip_thumbnails():
    """Regenerate thumbnails for all clips."""
    db = SessionLocal()
    try:
        clips = db.query(Clip).all()
        print(f"Found {len(clips)} clips")
        
        regenerated = 0
        for clip in clips:
            video = clip.batch.video
            if not video.file_path or not Path(video.file_path).exists():
                print(f"  ⚠️  Clip {clip.id}: video file not found")
                continue
            
            # Generate thumbnail at middle of clip
            mid = clip.start_time_sec + (clip.duration_sec / 2)
            thumb_dir = utils.ensure_dir(Path(settings.media_root) / "thumbnails" / "clips")
            thumb_path = thumb_dir / f"{clip.id}.jpg"
            
            if utils.render_thumbnail(video.file_path, str(thumb_path), mid):
                try:
                    relative = thumb_path.relative_to(Path(settings.media_root))
                    clip.thumbnail_path = f"{settings.media_base_url}/{relative.as_posix()}"
                    regenerated += 1
                    print(f"  ✓ Clip {clip.id}: {clip.thumbnail_path}")
                except Exception:
                    clip.thumbnail_path = str(thumb_path)
                    print(f"  ✓ Clip {clip.id}: {thumb_path} (local path)")
            else:
                print(f"  ✗ Clip {clip.id}: thumbnail generation failed")
        
        db.commit()
        print(f"\n✅ Regenerated {regenerated}/{len(clips)} clip thumbnails")
        
    finally:
        db.close()


def main():
    print("=" * 50)
    print("🖼️  THUMBNAIL REGENERATION")
    print("=" * 50)
    print()
    
    print("📹 Regenerating video thumbnails...")
    regenerate_video_thumbnails()
    print()
    
    print("🎬 Regenerating clip thumbnails...")
    regenerate_clip_thumbnails()
    print()
    
    print("=" * 50)
    print("✅ Done!")
    print("=" * 50)


if __name__ == "__main__":
    main()
