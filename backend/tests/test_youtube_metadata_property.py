"""
Property-based tests for YouTube metadata service.

**Feature: instant-youtube-preview, Property 1: YouTube URL Parsing Consistency**
**Validates: Requirements 1.1**

Property: For any valid YouTube URL format (youtube.com/watch, youtu.be, 
youtube.com/embed, youtube.com/shorts), extracting the video ID and 
reconstructing a canonical URL should produce the same video ID.
"""

from hypothesis import given, strategies as st, settings, assume
import string

from app.services.youtube_metadata import YouTubeMetadataService


# YouTube video IDs are exactly 11 characters from this alphabet
YOUTUBE_ID_ALPHABET = string.ascii_letters + string.digits + "_-"

# Strategy for generating valid YouTube video IDs (11 chars from allowed alphabet)
video_id_strategy = st.text(
    alphabet=YOUTUBE_ID_ALPHABET,
    min_size=11,
    max_size=11,
)

# Strategy for URL format types
url_format_strategy = st.sampled_from([
    "watch",      # youtube.com/watch?v=VIDEO_ID
    "short",      # youtu.be/VIDEO_ID
    "embed",      # youtube.com/embed/VIDEO_ID
    "shorts",     # youtube.com/shorts/VIDEO_ID
    "v",          # youtube.com/v/VIDEO_ID
    "mobile",     # m.youtube.com/watch?v=VIDEO_ID
])

# Strategy for optional URL components
protocol_strategy = st.sampled_from(["https://", "http://", ""])
www_strategy = st.sampled_from(["www.", ""])


def build_youtube_url(video_id: str, format_type: str, protocol: str, www: str) -> str:
    """Build a YouTube URL from components."""
    if format_type == "watch":
        return f"{protocol}{www}youtube.com/watch?v={video_id}"
    elif format_type == "short":
        # youtu.be doesn't use www
        return f"{protocol}youtu.be/{video_id}"
    elif format_type == "embed":
        return f"{protocol}{www}youtube.com/embed/{video_id}"
    elif format_type == "shorts":
        return f"{protocol}{www}youtube.com/shorts/{video_id}"
    elif format_type == "v":
        return f"{protocol}{www}youtube.com/v/{video_id}"
    elif format_type == "mobile":
        # mobile uses m. instead of www.
        return f"{protocol}m.youtube.com/watch?v={video_id}"
    else:
        return f"{protocol}{www}youtube.com/watch?v={video_id}"


@settings(max_examples=100)
@given(
    video_id=video_id_strategy,
    format_type=url_format_strategy,
    protocol=protocol_strategy,
    www=www_strategy,
)
def test_url_parsing_extracts_correct_video_id(
    video_id: str, format_type: str, protocol: str, www: str
):
    """
    **Feature: instant-youtube-preview, Property 1: YouTube URL Parsing Consistency**
    **Validates: Requirements 1.1**
    
    Property: For any valid YouTube video ID and URL format, extracting the 
    video ID should return the original video ID.
    """
    service = YouTubeMetadataService()
    
    # Build URL from components
    url = build_youtube_url(video_id, format_type, protocol, www)
    
    # Extract video ID
    extracted_id = service.extract_video_id(url)
    
    # Property: extracted ID must match original
    assert extracted_id == video_id, f"URL: {url}, Expected: {video_id}, Got: {extracted_id}"


@settings(max_examples=100)
@given(
    video_id=video_id_strategy,
    format_type=url_format_strategy,
    protocol=protocol_strategy,
    www=www_strategy,
)
def test_url_parsing_round_trip_consistency(
    video_id: str, format_type: str, protocol: str, www: str
):
    """
    **Feature: instant-youtube-preview, Property 1: YouTube URL Parsing Consistency**
    **Validates: Requirements 1.1**
    
    Property: Extracting a video ID from any URL format and then constructing
    a canonical URL should yield the same video ID when parsed again.
    """
    service = YouTubeMetadataService()
    
    # Build URL from components
    original_url = build_youtube_url(video_id, format_type, protocol, www)
    
    # Extract video ID
    extracted_id = service.extract_video_id(original_url)
    assert extracted_id is not None
    
    # Build canonical URL
    canonical_url = f"https://www.youtube.com/watch?v={extracted_id}"
    
    # Extract from canonical URL
    canonical_extracted_id = service.extract_video_id(canonical_url)
    
    # Property: both extractions should yield the same ID
    assert extracted_id == canonical_extracted_id


@settings(max_examples=100)
@given(video_id=video_id_strategy)
def test_thumbnail_url_format_validity(video_id: str):
    """
    **Feature: instant-youtube-preview, Property 2: Thumbnail URL Generation**
    **Validates: Requirements 3.1**
    
    Property: For any YouTube video ID, the generated thumbnail URL should
    follow YouTube's thumbnail URL pattern.
    """
    service = YouTubeMetadataService()
    
    # Test all quality options
    qualities = ["maxresdefault", "sddefault", "hqdefault", "mqdefault", "default"]
    
    for quality in qualities:
        thumbnail_url = service.get_thumbnail_url(video_id, quality)
        
        # Property: URL must follow YouTube thumbnail pattern
        assert thumbnail_url.startswith("https://img.youtube.com/vi/")
        assert video_id in thumbnail_url
        assert thumbnail_url.endswith(f"/{quality}.jpg")
        
        # Verify full URL structure
        expected_url = f"https://img.youtube.com/vi/{video_id}/{quality}.jpg"
        assert thumbnail_url == expected_url


@settings(max_examples=50)
@given(
    video_id=video_id_strategy,
    extra_params=st.text(alphabet=string.ascii_letters + string.digits, min_size=0, max_size=20),
)
def test_url_parsing_with_extra_query_params(video_id: str, extra_params: str):
    """
    **Feature: instant-youtube-preview, Property 1: YouTube URL Parsing Consistency**
    **Validates: Requirements 1.1**
    
    Property: URL parsing should correctly extract video ID even when
    additional query parameters are present.
    """
    service = YouTubeMetadataService()
    
    # Build URL with extra query parameters
    if extra_params:
        url = f"https://www.youtube.com/watch?v={video_id}&t={extra_params}"
    else:
        url = f"https://www.youtube.com/watch?v={video_id}"
    
    # Extract video ID
    extracted_id = service.extract_video_id(url)
    
    # Property: extracted ID must match original despite extra params
    assert extracted_id == video_id
