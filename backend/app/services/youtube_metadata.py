"""
YouTube Metadata Service

Provides functionality to extract video metadata from YouTube without downloading.
Uses YouTube oEmbed API (no API key required) for fetching video information.
"""

import re
from typing import Optional
from urllib.parse import parse_qs, urlparse

import structlog
from pydantic import BaseModel

logger = structlog.get_logger()


class YouTubeVideoInfo(BaseModel):
    """Video metadata from YouTube."""
    video_id: str
    title: str
    thumbnail_url: str
    duration_seconds: Optional[int] = None
    channel_name: Optional[str] = None
    channel_url: Optional[str] = None


class YouTubeMetadataError(Exception):
    """Exception raised for YouTube metadata errors."""
    pass


class YouTubeMetadataService:
    """
    Service for fetching YouTube video metadata without downloading.
    
    Uses YouTube oEmbed API which doesn't require an API key.
    """
    
    # Regex patterns for different YouTube URL formats
    YOUTUBE_URL_PATTERNS = [
        # youtube.com/watch?v=VIDEO_ID
        r'(?:https?://)?(?:www\.)?youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})',
        # youtu.be/VIDEO_ID
        r'(?:https?://)?(?:www\.)?youtu\.be/([a-zA-Z0-9_-]{11})',
        # youtube.com/embed/VIDEO_ID
        r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        # youtube.com/shorts/VIDEO_ID
        r'(?:https?://)?(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]{11})',
        # youtube.com/v/VIDEO_ID
        r'(?:https?://)?(?:www\.)?youtube\.com/v/([a-zA-Z0-9_-]{11})',
        # m.youtube.com/watch?v=VIDEO_ID (mobile)
        r'(?:https?://)?m\.youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})',
    ]
    
    OEMBED_URL = "https://www.youtube.com/oembed"
    
    def extract_video_id(self, url: str) -> Optional[str]:
        """
        Extract YouTube video ID from various URL formats.
        
        Supported formats:
        - youtube.com/watch?v=VIDEO_ID
        - youtu.be/VIDEO_ID
        - youtube.com/embed/VIDEO_ID
        - youtube.com/shorts/VIDEO_ID
        - youtube.com/v/VIDEO_ID
        - m.youtube.com/watch?v=VIDEO_ID
        
        Args:
            url: YouTube URL in any supported format
            
        Returns:
            11-character video ID or None if not found
        """
        if not url:
            return None
            
        url = url.strip()
        
        # Try regex patterns first
        for pattern in self.YOUTUBE_URL_PATTERNS:
            match = re.search(pattern, url)
            if match:
                video_id = match.group(1)
                logger.debug("youtube.video_id_extracted", video_id=video_id, url=url[:50])
                return video_id
        
        # Fallback: try parsing URL query parameters
        try:
            parsed = urlparse(url)
            if 'youtube.com' in parsed.netloc or 'youtu.be' in parsed.netloc:
                # Check query params for 'v'
                query_params = parse_qs(parsed.query)
                if 'v' in query_params:
                    video_id = query_params['v'][0]
                    if len(video_id) == 11:
                        return video_id
        except Exception:
            pass
        
        logger.warning("youtube.video_id_not_found", url=url[:50])
        return None
    
    def get_thumbnail_url(self, video_id: str, quality: str = "maxresdefault") -> str:
        """
        Generate YouTube thumbnail URL for a video ID.
        
        Quality options:
        - maxresdefault: 1280x720 (may not exist for all videos)
        - sddefault: 640x480
        - hqdefault: 480x360
        - mqdefault: 320x180
        - default: 120x90
        
        Args:
            video_id: YouTube video ID
            quality: Thumbnail quality preset
            
        Returns:
            Direct URL to YouTube thumbnail
        """
        return f"https://img.youtube.com/vi/{video_id}/{quality}.jpg"
    
    def _get_duration_with_ytdlp(self, video_id: str) -> Optional[int]:
        """
        Get video duration using yt-dlp (fast, no download).
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            Duration in seconds or None if failed
        """
        try:
            import yt_dlp
            
            url = f"https://www.youtube.com/watch?v={video_id}"
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
                'extract_flat': False,  # Need full info for duration
                'socket_timeout': 10,  # Timeout for network operations
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                duration = info.get('duration')
                if duration:
                    logger.info("youtube.duration_fetched", video_id=video_id, duration=duration)
                    return int(duration)
                    
        except Exception as e:
            logger.warning("youtube.duration_fetch_failed", video_id=video_id, error=str(e))
            
        return None
    
    async def get_video_info_fast(self, youtube_url: str) -> YouTubeVideoInfo:
        """
        Fetch video metadata from YouTube using oEmbed API only (fast, no duration).
        
        Use this for instant preview where speed is critical.
        Duration will be fetched later during download.
        
        Args:
            youtube_url: YouTube URL in any supported format
            
        Returns:
            YouTubeVideoInfo with title, thumbnail_url (duration will be None)
        """
        import urllib.request
        import urllib.parse
        import json
        import ssl
        
        video_id = self.extract_video_id(youtube_url)
        if not video_id:
            raise YouTubeMetadataError(f"Invalid YouTube URL: {youtube_url}")
        
        # Build oEmbed request URL
        canonical_url = f"https://www.youtube.com/watch?v={video_id}"
        oembed_params = urllib.parse.urlencode({
            "url": canonical_url,
            "format": "json"
        })
        oembed_request_url = f"{self.OEMBED_URL}?{oembed_params}"
        
        try:
            ctx = ssl.create_default_context()
            req = urllib.request.Request(oembed_request_url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            with urllib.request.urlopen(req, timeout=5, context=ctx) as response:
                data = json.loads(response.read().decode('utf-8'))
            
            logger.info("youtube.oembed_fast_success", video_id=video_id, title=data.get("title", "")[:50])
            
            return YouTubeVideoInfo(
                video_id=video_id,
                title=data.get("title", f"YouTube Video {video_id}"),
                thumbnail_url=self.get_thumbnail_url(video_id, "maxresdefault"),
                duration_seconds=None,  # Skip duration for fast response
                channel_name=data.get("author_name"),
                channel_url=data.get("author_url"),
            )
            
        except Exception as e:
            logger.error("youtube.oembed_fast_error", video_id=video_id, error=str(e))
            raise YouTubeMetadataError(f"Failed to fetch video info: {str(e)}")

    async def get_video_info(self, youtube_url: str) -> YouTubeVideoInfo:
        """
        Fetch video metadata from YouTube using oEmbed API + yt-dlp for duration.
        
        Args:
            youtube_url: YouTube URL in any supported format
            
        Returns:
            YouTubeVideoInfo with title, thumbnail_url, duration, etc.
            
        Raises:
            YouTubeMetadataError: If video ID cannot be extracted or API fails
        """
        import urllib.request
        import urllib.parse
        import json
        import ssl
        
        video_id = self.extract_video_id(youtube_url)
        if not video_id:
            raise YouTubeMetadataError(f"Invalid YouTube URL: {youtube_url}")
        
        # Build oEmbed request URL
        canonical_url = f"https://www.youtube.com/watch?v={video_id}"
        oembed_params = urllib.parse.urlencode({
            "url": canonical_url,
            "format": "json"
        })
        oembed_request_url = f"{self.OEMBED_URL}?{oembed_params}"
        
        try:
            # Create SSL context
            ctx = ssl.create_default_context()
            
            # Make request with timeout
            req = urllib.request.Request(oembed_request_url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            with urllib.request.urlopen(req, timeout=10, context=ctx) as response:
                data = json.loads(response.read().decode('utf-8'))
            
            logger.info("youtube.oembed_success", video_id=video_id, title=data.get("title", "")[:50])
            
            # Extract info from oEmbed response
            title = data.get("title", f"YouTube Video {video_id}")
            channel_name = data.get("author_name")
            channel_url = data.get("author_url")
            
            # oEmbed provides thumbnail but we'll use our own URL for better quality
            thumbnail_url = self.get_thumbnail_url(video_id, "maxresdefault")
            
            # Get duration using yt-dlp (fast, metadata only)
            duration_seconds = self._get_duration_with_ytdlp(video_id)
            
            return YouTubeVideoInfo(
                video_id=video_id,
                title=title,
                thumbnail_url=thumbnail_url,
                duration_seconds=duration_seconds,
                channel_name=channel_name,
                channel_url=channel_url,
            )
            
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise YouTubeMetadataError(f"Video not found or unavailable: {video_id}")
            elif e.code == 401:
                raise YouTubeMetadataError(f"Video is private: {video_id}")
            else:
                logger.error("youtube.oembed_http_error", video_id=video_id, code=e.code)
                raise YouTubeMetadataError(f"Failed to fetch video info: HTTP {e.code}")
                
        except urllib.error.URLError as e:
            logger.error("youtube.oembed_url_error", video_id=video_id, error=str(e))
            raise YouTubeMetadataError(f"Network error fetching video info: {str(e)}")
            
        except json.JSONDecodeError as e:
            logger.error("youtube.oembed_json_error", video_id=video_id, error=str(e))
            raise YouTubeMetadataError(f"Invalid response from YouTube API")
            
        except Exception as e:
            logger.error("youtube.oembed_error", video_id=video_id, error=str(e))
            raise YouTubeMetadataError(f"Failed to fetch video info: {str(e)}")


# Singleton instance for convenience
youtube_metadata_service = YouTubeMetadataService()
