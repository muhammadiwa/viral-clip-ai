"""
Script to generate/update thumbnails for existing videos.
- YouTube videos: fetch original thumbnail from YouTube
- Upload videos: generate from video file

Run from backend directory: venv\Scripts\python scripts\generate_missing_thumbnails.py
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import VideoSource
from app.services import utils

try:
    from yt_dlp import YoutubeDL
except Exception:
    YoutubeDL = None

settings = get_settings()


def get_youtube_thumbnail(url: str) -> str | None:
    """Fetch thumbnail URL from YouTube."""
    if not YoutubeDL or not url:
        return None
    try:
        ydl_opts = {"quiet": True, "no_warnings": True}
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return None
            # Try main thumbnail first
            thumbnail_url = info.get("thumbnail")
            if not thumbnail_url:
                # Get from thumbnails list (highest resolution)
                thumbnails = info.get("thumbnails", [])
                if thumbnails:
                    best_thumb = max(thumbnails, key=lambda t: t.get("height", 0) or 0)
                    thumbnail_url = best_thumb.get("url")
            return thumbnail_url
    except Exception as e:
        print(f"    Error fetching YouTube thumbnail: {e}")
        return None


def main():
    db = SessionLocal()
    try:
        # Get all videos without thumbnails
        videos = db.query(VideoSource).filter(
            VideoSource.thumbnail_path.is_(None),
        ).all()
        
        print(f"Found {len(videos)} videos without thumbnails")
        
        for video in videos:
            print(f"  Video {video.id} ({video.source_type}): {video.title or 'Untitled'}")
            
            if video.source_type == "youtube" and video.source_url:
                # Fetch original YouTube thumbnail
                thumbnail_url = get_youtube_thumbnail(video.source_url)
                if thumbnail_url:
                    video.thumbnail_path = thumbnail_url
                    db.commit()
                    print(f"    -> YouTube thumbnail: {thumbnail_url[:80]}...")
                else:
                    print(f"    -> Failed to fetch YouTube thumbnail")
            
            elif video.source_type == "upload" and video.file_path:
                # Generate thumbnail from video file
                if not Path(video.file_path).exists():
                    print(f"    -> File not found, skipping")
                    continue
                
                thumb_dir = utils.ensure_dir(
                    Path(settings.media_root) / "thumbnails" / "videos" / str(video.id)
                )
                thumb_path = thumb_dir / "thumb.jpg"
                
                duration = video.duration_seconds or utils.probe_duration(video.file_path) or 10
                thumb_timestamp = duration * 0.1
                
                if utils.render_thumbnail(video.file_path, str(thumb_path), thumb_timestamp):
                    try:
                        relative = thumb_path.relative_to(Path(settings.media_root))
                        video.thumbnail_path = f"{settings.media_base_url}/{relative.as_posix()}"
                    except Exception:
                        video.thumbnail_path = str(thumb_path)
                    db.commit()
                    print(f"    -> Generated: {video.thumbnail_path}")
                else:
                    print(f"    -> Thumbnail generation failed")
            else:
                print(f"    -> Skipped (no source)")
        
        print("\nDone!")
    finally:
        db.close()


if __name__ == "__main__":
    main()
