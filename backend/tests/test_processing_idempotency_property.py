"""
Property-based tests for Processing Idempotency.

**Feature: lazy-processing-flow, Property 2: Processing Idempotency**
**Validates: Requirements 3.2**

Property: For any video that has already been downloaded, calling 
trigger_video_download should return immediately without re-downloading.
"""

import asyncio
from unittest.mock import patch, MagicMock

from hypothesis import given, strategies as st, settings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.video import VideoSource
from app.models.user import User
from app.services.video_ingest import trigger_video_download


# Strategy for generating valid YouTube video IDs (11 characters, alphanumeric + _ -)
youtube_video_id_strategy = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-",
    min_size=11,
    max_size=11,
)

# Strategy for generating user IDs (positive integers)
user_id_strategy = st.integers(min_value=1, max_value=1000)

# Strategy for generating slugs - build valid slugs directly without filtering
@st.composite
def slug_strategy(draw):
    """Generate valid slugs that don't start/end with dash and have no double dashes."""
    # Generate a base string of letters and numbers
    base = draw(st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
        min_size=3,
        max_size=20,
    ))
    # Optionally add some dashes in the middle
    parts = list(base)
    if len(parts) > 2:
        # Insert up to 2 dashes at random positions (not at start or end)
        num_dashes = draw(st.integers(min_value=0, max_value=min(2, len(parts) - 2)))
        for _ in range(num_dashes):
            pos = draw(st.integers(min_value=1, max_value=len(parts) - 1))
            if parts[pos - 1] != '-' and (pos >= len(parts) or parts[pos] != '-'):
                parts.insert(pos, '-')
    return ''.join(parts) if parts else "default-slug"


# Strategy for generating file paths - build directly without filtering
@st.composite
def file_path_strategy(draw):
    """Generate valid file paths ending in .mp4."""
    folder = draw(st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
        min_size=3,
        max_size=20,
    ))
    filename = draw(st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
        min_size=5,
        max_size=20,
    ))
    return f"/media/videos/{folder}/{filename}.mp4"


# Strategy for generating YouTube URLs
youtube_url_strategy = st.sampled_from([
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://youtu.be/dQw4w9WgXcQ",
    "https://www.youtube.com/watch?v=jNQXAC9IVRw",
])


def create_test_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine


def create_test_user(session, user_id: int) -> User:
    """Create a test user if not exists."""
    user = session.query(User).filter(User.id == user_id).first()
    if not user:
        user = User(
            id=user_id,
            email=f"user{user_id}@example.com",
            password_hash="hashed_password",
            credits=100,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    return user


@settings(max_examples=100)
@given(
    youtube_video_id=youtube_video_id_strategy,
    user_id=user_id_strategy,
    slug=slug_strategy(),
    file_path=file_path_strategy(),
    youtube_url=youtube_url_strategy,
)
def test_already_downloaded_video_returns_immediately(
    youtube_video_id: str,
    user_id: int,
    slug: str,
    file_path: str,
    youtube_url: str,
):
    """
    **Feature: lazy-processing-flow, Property 2: Processing Idempotency**
    **Validates: Requirements 3.2**
    
    Property: For any video that has already been downloaded (is_downloaded=True),
    calling trigger_video_download should return immediately without re-downloading.
    The function should NOT call yt-dlp or any download logic.
    """
    engine = create_test_db()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    try:
        # Create test user
        create_test_user(session, user_id)
        
        # Create a video that is already downloaded
        video = VideoSource(
            user_id=user_id,
            youtube_video_id=youtube_video_id,
            source_type="youtube",
            source_url=youtube_url,
            title="Already Downloaded Video",
            slug=slug,
            is_downloaded=True,  # Already downloaded
            download_progress=100.0,
            file_path=file_path,
        )
        session.add(video)
        session.commit()
        session.refresh(video)
        
        original_video_id = video.id
        original_file_path = video.file_path
        original_is_downloaded = video.is_downloaded
        
        # Mock YoutubeDL to track if it's called
        with patch('app.services.video_ingest.YoutubeDL') as mock_ydl:
            # Run the trigger_video_download function
            result = asyncio.run(
                trigger_video_download(session, video)
            )
            
            # Property 1: YoutubeDL should NOT be called for already downloaded videos
            mock_ydl.assert_not_called()
            
            # Property 2: The returned video should be the same video
            assert result.id == original_video_id, (
                f"Expected same video id {original_video_id}, got {result.id}"
            )
            
            # Property 3: is_downloaded should still be True
            assert result.is_downloaded == original_is_downloaded, (
                f"is_downloaded changed from {original_is_downloaded} to {result.is_downloaded}"
            )
            
            # Property 4: file_path should remain unchanged
            assert result.file_path == original_file_path, (
                f"file_path changed from {original_file_path} to {result.file_path}"
            )
        
    finally:
        session.close()


@settings(max_examples=100)
@given(
    youtube_video_id=youtube_video_id_strategy,
    user_id=user_id_strategy,
    slug=slug_strategy(),
    file_path=file_path_strategy(),
    youtube_url=youtube_url_strategy,
    num_calls=st.integers(min_value=2, max_value=5),
)
def test_multiple_download_calls_idempotent(
    youtube_video_id: str,
    user_id: int,
    slug: str,
    file_path: str,
    youtube_url: str,
    num_calls: int,
):
    """
    **Feature: lazy-processing-flow, Property 2: Processing Idempotency**
    **Validates: Requirements 3.2**
    
    Property: For any video that is already downloaded, calling trigger_video_download
    multiple times should always return the same result without side effects.
    """
    engine = create_test_db()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    try:
        # Create test user
        create_test_user(session, user_id)
        
        # Create a video that is already downloaded
        video = VideoSource(
            user_id=user_id,
            youtube_video_id=youtube_video_id,
            source_type="youtube",
            source_url=youtube_url,
            title="Already Downloaded Video",
            slug=slug,
            is_downloaded=True,
            download_progress=100.0,
            file_path=file_path,
        )
        session.add(video)
        session.commit()
        session.refresh(video)
        
        original_state = {
            'id': video.id,
            'is_downloaded': video.is_downloaded,
            'file_path': video.file_path,
            'download_progress': video.download_progress,
        }
        
        # Mock YoutubeDL to track calls
        with patch('app.services.video_ingest.YoutubeDL') as mock_ydl:
            # Call trigger_video_download multiple times
            for i in range(num_calls):
                result = asyncio.run(
                    trigger_video_download(session, video)
                )
                
                # Each call should return the same video with same state
                assert result.id == original_state['id'], (
                    f"Call {i+1}: video id changed"
                )
                assert result.is_downloaded == original_state['is_downloaded'], (
                    f"Call {i+1}: is_downloaded changed"
                )
                assert result.file_path == original_state['file_path'], (
                    f"Call {i+1}: file_path changed"
                )
                assert result.download_progress == original_state['download_progress'], (
                    f"Call {i+1}: download_progress changed"
                )
            
            # YoutubeDL should never be called
            mock_ydl.assert_not_called()
        
    finally:
        session.close()


@settings(max_examples=100)
@given(
    youtube_video_id=youtube_video_id_strategy,
    user_id=user_id_strategy,
    slug=slug_strategy(),
    file_path=file_path_strategy(),
    youtube_url=youtube_url_strategy,
)
def test_download_state_preserved_after_idempotent_call(
    youtube_video_id: str,
    user_id: int,
    slug: str,
    file_path: str,
    youtube_url: str,
):
    """
    **Feature: lazy-processing-flow, Property 2: Processing Idempotency**
    **Validates: Requirements 3.2**
    
    Property: For any downloaded video, calling trigger_video_download should
    preserve all download-related state (is_downloaded, file_path, download_progress).
    """
    engine = create_test_db()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    try:
        # Create test user
        create_test_user(session, user_id)
        
        # Create a video that is already downloaded with specific state
        video = VideoSource(
            user_id=user_id,
            youtube_video_id=youtube_video_id,
            source_type="youtube",
            source_url=youtube_url,
            title="Downloaded Video",
            slug=slug,
            is_downloaded=True,
            download_progress=100.0,
            file_path=file_path,
            duration_seconds=120.5,
        )
        session.add(video)
        session.commit()
        session.refresh(video)
        
        # Capture original state
        original_state = {
            'is_downloaded': video.is_downloaded,
            'download_progress': video.download_progress,
            'file_path': video.file_path,
            'duration_seconds': video.duration_seconds,
            'title': video.title,
            'slug': video.slug,
        }
        
        with patch('app.services.video_ingest.YoutubeDL'):
            result = asyncio.run(
                trigger_video_download(session, video)
            )
            
            # All state should be preserved
            assert result.is_downloaded == original_state['is_downloaded']
            assert result.download_progress == original_state['download_progress']
            assert result.file_path == original_state['file_path']
            assert result.duration_seconds == original_state['duration_seconds']
            assert result.title == original_state['title']
            assert result.slug == original_state['slug']
        
    finally:
        session.close()
