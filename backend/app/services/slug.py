"""
Slug Service

Provides functionality to generate URL-friendly slugs from video titles.
Handles slug generation and uniqueness enforcement.
"""

import re
import unicodedata
from typing import List

import structlog

logger = structlog.get_logger()


class SlugService:
    """
    Service for generating URL-friendly slugs from video titles.
    
    Slugs are used for SEO-friendly URLs instead of numeric IDs.
    """
    
    MAX_SLUG_LENGTH = 100
    
    def generate_slug(self, title: str) -> str:
        """
        Generate URL-friendly slug from video title.
        
        Processing steps:
        1. Normalize unicode characters (NFD normalization)
        2. Convert to lowercase
        3. Replace spaces and underscores with hyphens
        4. Remove special characters (keep only alphanumeric and hyphens)
        5. Collapse multiple consecutive hyphens
        6. Strip leading/trailing hyphens
        7. Truncate to max 100 characters
        
        Args:
            title: Video title to convert to slug
            
        Returns:
            URL-safe slug containing only lowercase letters, numbers, and hyphens
        """
        if not title:
            return "untitled"
        
        # Normalize unicode characters (e.g., é -> e)
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
        if len(slug) > self.MAX_SLUG_LENGTH:
            slug = slug[:self.MAX_SLUG_LENGTH].rstrip('-')
        
        # Fallback for empty result
        if not slug:
            return "untitled"
        
        logger.debug("slug.generated", title=title[:50], slug=slug)
        return slug
    
    def ensure_unique_slug(self, base_slug: str, existing_slugs: List[str]) -> str:
        """
        Ensure slug is unique by appending numeric suffix if needed.
        
        If base_slug already exists in existing_slugs, appends -2, -3, etc.
        until a unique slug is found.
        
        Args:
            base_slug: The base slug to make unique
            existing_slugs: List of existing slugs to check against
            
        Returns:
            Unique slug (e.g., "my-video" or "my-video-2")
        """
        if not base_slug:
            base_slug = "untitled"
        
        # Convert to set for O(1) lookup
        existing_set = set(existing_slugs)
        
        # If base slug is unique, return it
        if base_slug not in existing_set:
            logger.debug("slug.unique", slug=base_slug)
            return base_slug
        
        # Find next available suffix
        suffix = 2
        while True:
            candidate = f"{base_slug}-{suffix}"
            if candidate not in existing_set:
                logger.debug("slug.unique_with_suffix", base_slug=base_slug, slug=candidate)
                return candidate
            suffix += 1
            
            # Safety limit to prevent infinite loop
            if suffix > 10000:
                # Fallback: append timestamp-like suffix
                import time
                candidate = f"{base_slug}-{int(time.time())}"
                logger.warning("slug.fallback_timestamp", slug=candidate)
                return candidate


# Singleton instance for convenience
slug_service = SlugService()
