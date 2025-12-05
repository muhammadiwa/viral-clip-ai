"""
Property-based tests for Transcript Reuse.

**Feature: lazy-processing-flow, Property 3: Transcript Reuse**
**Validates: Requirements 3.4**

Property: For any video that has existing transcript segments, the smart 
processing pipeline should skip transcription.
"""

from hypothesis import given, strategies as st, settings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.video import VideoSource, TranscriptSegment
from app.models.user import User
from app.services.smart_processing import check_processing_status, ProcessingStatus


# Strategy for generating valid YouTube video IDs (11 characters, alphanumeric + _ -)
youtube_video_id_strategy = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-",
    min_size=11,
    max_size=11,
)

# Strategy for generating user IDs (positive integers)
user_id_strategy = st.integers(min_value=1, max_value=1000)


@st.composite
def slug_strategy(draw):
    """Generate valid slugs that don't start/end with dash and have no double dashes."""
    base = draw(st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
        min_size=3,
        max_size=20,
    ))
    parts = list(base)
    if len(parts) > 2:
        num_dashes = draw(st.integers(min_value=0, max_value=min(2, len(parts) - 2)))
        for _ in range(num_dashes):
            pos = draw(st.integers(min_value=1, max_value=len(parts) - 1))
            if parts[pos - 1] != '-' and (pos >= len(parts) or parts[pos] != '-'):
                parts.insert(pos, '-')
    return ''.join(parts) if parts else "default-slug"


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


# Strategy for generating transcript segment data
@st.composite
def transcript_segment_strategy(draw):
    """Generate valid transcript segment data."""
    start_time = draw(st.floats(min_value=0.0, max_value=3600.0, allow_nan=False, allow_infinity=False))
    duration = draw(st.floats(min_value=0.5, max_value=30.0, allow_nan=False, allow_infinity=False))
    end_time = start_time + duration
    text = draw(st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz ABCDEFGHIJKLMNOPQRSTUVWXYZ.,!?",
        min_size=5,
        max_size=200,
    ))
    return {
        "start_time_sec": start_time,
        "end_time_sec": end_time,
        "text": text,
        "language": "en",
    }


# Strategy for generating a list of transcript segments (at least 1)
transcript_segments_strategy = st.lists(
    transcript_segment_strategy(),
    min_size=1,
    max_size=10,
)


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
    transcript_segments=transcript_segments_strategy,
)
def test_video_with_transcript_skips_transcription(
    youtube_video_id: str,
    user_id: int,
    slug: str,
    file_path: str,
    youtube_url: str,
    transcript_segments: list,
):
    """
    **Feature: lazy-processing-flow, Property 3: Transcript Reuse**
    **Validates: Requirements 3.4**
    
    Property: For any video that has existing transcript segments,
    check_processing_status should return has_transcript=True and needs_transcript=False.
    """
    engine = create_test_db()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    try:
        # Create test user
        create_test_user(session, user_id)
        
        # Create a video with downloaded status
        video = VideoSource(
            user_id=user_id,
            youtube_video_id=youtube_video_id,
            source_type="youtube",
            source_url=youtube_url,
            title="Video With Transcript",
            slug=slug,
            is_downloaded=True,
            download_progress=100.0,
            file_path=file_path,
        )
        session.add(video)
        session.commit()
        session.refresh(video)
        
        # Add transcript segments to the video
        for seg_data in transcript_segments:
            segment = TranscriptSegment(
                video_source_id=video.id,
                start_time_sec=seg_data["start_time_sec"],
                end_time_sec=seg_data["end_time_sec"],
                text=seg_data["text"],
                language=seg_data["language"],
            )
            session.add(segment)
        session.commit()
        
        # Check processing status
        status = check_processing_status(session, video)
        
        # Property: Video with transcript segments should have has_transcript=True
        assert status.has_transcript is True, (
            f"Expected has_transcript=True for video with {len(transcript_segments)} segments, "
            f"got has_transcript={status.has_transcript}"
        )
        
        # Property: Video with transcript should NOT need transcription
        assert status.needs_transcript is False, (
            f"Expected needs_transcript=False for video with existing transcript, "
            f"got needs_transcript={status.needs_transcript}"
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
)
def test_video_without_transcript_needs_transcription(
    youtube_video_id: str,
    user_id: int,
    slug: str,
    file_path: str,
    youtube_url: str,
):
    """
    **Feature: lazy-processing-flow, Property 3: Transcript Reuse**
    **Validates: Requirements 3.4**
    
    Property: For any video that has NO transcript segments,
    check_processing_status should return has_transcript=False and needs_transcript=True.
    This is the inverse property that validates the detection logic works correctly.
    """
    engine = create_test_db()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    try:
        # Create test user
        create_test_user(session, user_id)
        
        # Create a video WITHOUT transcript segments
        video = VideoSource(
            user_id=user_id,
            youtube_video_id=youtube_video_id,
            source_type="youtube",
            source_url=youtube_url,
            title="Video Without Transcript",
            slug=slug,
            is_downloaded=True,
            download_progress=100.0,
            file_path=file_path,
        )
        session.add(video)
        session.commit()
        session.refresh(video)
        
        # Do NOT add any transcript segments
        
        # Check processing status
        status = check_processing_status(session, video)
        
        # Property: Video without transcript segments should have has_transcript=False
        assert status.has_transcript is False, (
            f"Expected has_transcript=False for video with no segments, "
            f"got has_transcript={status.has_transcript}"
        )
        
        # Property: Video without transcript should need transcription
        assert status.needs_transcript is True, (
            f"Expected needs_transcript=True for video without transcript, "
            f"got needs_transcript={status.needs_transcript}"
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
    transcript_segments=transcript_segments_strategy,
)
def test_transcript_reuse_preserves_existing_segments(
    youtube_video_id: str,
    user_id: int,
    slug: str,
    file_path: str,
    youtube_url: str,
    transcript_segments: list,
):
    """
    **Feature: lazy-processing-flow, Property 3: Transcript Reuse**
    **Validates: Requirements 3.4**
    
    Property: For any video with existing transcript segments, checking the
    processing status should not modify or delete the existing segments.
    The segment count should remain the same before and after the check.
    """
    engine = create_test_db()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    try:
        # Create test user
        create_test_user(session, user_id)
        
        # Create a video
        video = VideoSource(
            user_id=user_id,
            youtube_video_id=youtube_video_id,
            source_type="youtube",
            source_url=youtube_url,
            title="Video With Transcript",
            slug=slug,
            is_downloaded=True,
            download_progress=100.0,
            file_path=file_path,
        )
        session.add(video)
        session.commit()
        session.refresh(video)
        
        # Add transcript segments
        for seg_data in transcript_segments:
            segment = TranscriptSegment(
                video_source_id=video.id,
                start_time_sec=seg_data["start_time_sec"],
                end_time_sec=seg_data["end_time_sec"],
                text=seg_data["text"],
                language=seg_data["language"],
            )
            session.add(segment)
        session.commit()
        
        # Count segments before status check
        segments_before = session.query(TranscriptSegment).filter(
            TranscriptSegment.video_source_id == video.id
        ).count()
        
        # Check processing status (should not modify segments)
        status = check_processing_status(session, video)
        
        # Count segments after status check
        segments_after = session.query(TranscriptSegment).filter(
            TranscriptSegment.video_source_id == video.id
        ).count()
        
        # Property: Segment count should be preserved
        assert segments_before == segments_after, (
            f"Segment count changed from {segments_before} to {segments_after} "
            f"after check_processing_status call"
        )
        
        # Property: Segment count should match input
        assert segments_after == len(transcript_segments), (
            f"Expected {len(transcript_segments)} segments, got {segments_after}"
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
    num_segments=st.integers(min_value=1, max_value=50),
)
def test_transcript_detection_works_for_any_segment_count(
    youtube_video_id: str,
    user_id: int,
    slug: str,
    file_path: str,
    youtube_url: str,
    num_segments: int,
):
    """
    **Feature: lazy-processing-flow, Property 3: Transcript Reuse**
    **Validates: Requirements 3.4**
    
    Property: For any positive number of transcript segments (1 to N),
    the system should correctly detect that transcript exists and skip transcription.
    """
    engine = create_test_db()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    try:
        # Create test user
        create_test_user(session, user_id)
        
        # Create a video
        video = VideoSource(
            user_id=user_id,
            youtube_video_id=youtube_video_id,
            source_type="youtube",
            source_url=youtube_url,
            title="Video With Variable Segments",
            slug=slug,
            is_downloaded=True,
            download_progress=100.0,
            file_path=file_path,
        )
        session.add(video)
        session.commit()
        session.refresh(video)
        
        # Add the specified number of transcript segments
        for i in range(num_segments):
            segment = TranscriptSegment(
                video_source_id=video.id,
                start_time_sec=float(i * 10),
                end_time_sec=float(i * 10 + 9),
                text=f"Segment {i} text content",
                language="en",
            )
            session.add(segment)
        session.commit()
        
        # Check processing status
        status = check_processing_status(session, video)
        
        # Property: Any positive number of segments should be detected
        assert status.has_transcript is True, (
            f"Expected has_transcript=True for video with {num_segments} segments, "
            f"got has_transcript={status.has_transcript}"
        )
        
        # Property: Should not need transcription
        assert status.needs_transcript is False, (
            f"Expected needs_transcript=False for video with {num_segments} segments, "
            f"got needs_transcript={status.needs_transcript}"
        )
        
    finally:
        session.close()
