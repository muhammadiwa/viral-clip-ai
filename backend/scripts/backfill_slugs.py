"""
Backfill slugs for existing videos.

This script generates slugs for videos that were created before the
instant-youtube-preview feature was implemented.
"""

import sys
import os
import re
import unicodedata

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


def generate_slug(title: str) -> str:
    """Generate URL-friendly slug from video title."""
    if not title:
        return "untitled"
    
    # Normalize unicode characters
    slug = unicodedata.normalize('NFD', title)
    slug = slug.encode('ascii', 'ignore').decode('ascii')
    
    # Convert to lowercase
    slug = slug.lower()
    
    # Replace spaces and underscores with hyphens
    slug = re.sub(r'[\s_]+', '-', slug)
    
    # Remove all characters except alphanumeric and hyphens
    slug = re.sub(r'[^a-z0-9-]', '', slug)
    
    # Collapse multiple consecutive hyphens into one
    slug = re.sub(r'-+', '-', slug)
    
    # Strip leading and trailing hyphens
    slug = slug.strip('-')
    
    # Truncate to max length
    if len(slug) > 100:
        slug = slug[:100].rstrip('-')
    
    return slug if slug else "untitled"


def ensure_unique_slug(base_slug: str, existing_slugs: set) -> str:
    """Ensure slug is unique by appending numeric suffix if needed."""
    if not base_slug:
        base_slug = "untitled"
    
    if base_slug not in existing_slugs:
        return base_slug
    
    suffix = 2
    while True:
        candidate = f"{base_slug}-{suffix}"
        if candidate not in existing_slugs:
            return candidate
        suffix += 1
        if suffix > 10000:
            import time
            return f"{base_slug}-{int(time.time())}"


def backfill_slugs():
    """Generate slugs for all videos that don't have one."""
    
    # Use SQLite database directly
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.db")
    engine = create_engine(f"sqlite:///{db_path}")
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Get all videos without slugs
        result = session.execute(
            text("SELECT id, title FROM video_sources WHERE slug IS NULL OR slug = ''")
        )
        videos = result.fetchall()
        
        if not videos:
            print("No videos need slug backfill.")
            return
        
        print(f"Found {len(videos)} videos without slugs.")
        
        # Get all existing slugs
        existing_result = session.execute(
            text("SELECT slug FROM video_sources WHERE slug IS NOT NULL AND slug != ''")
        )
        existing_slugs = [row[0] for row in existing_result.fetchall()]
        
        # Convert to set for faster lookup
        existing_slugs_set = set(existing_slugs)
        
        # Generate slugs for each video
        for video_id, title in videos:
            # Generate base slug from title
            base_slug = generate_slug(title or f"video-{video_id}")
            
            # Ensure uniqueness
            unique_slug = ensure_unique_slug(base_slug, existing_slugs_set)
            
            # Update video
            session.execute(
                text("UPDATE video_sources SET slug = :slug WHERE id = :id"),
                {"slug": unique_slug, "id": video_id}
            )
            
            # Add to existing slugs for next iteration
            existing_slugs_set.add(unique_slug)
            
            print(f"  Video {video_id}: '{title}' -> '{unique_slug}'")
        
        session.commit()
        print(f"\nSuccessfully backfilled {len(videos)} slugs.")
        
    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    backfill_slugs()
