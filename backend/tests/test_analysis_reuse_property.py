"""
Property-based tests for Analysis Reuse.

**Feature: lazy-processing-flow, Property 4: Analysis Reuse**
**Validates: Requirements 3.6**

Property: For any video that has existing analysis, the smart 
processing pipeline should skip analysis.
"""

from hypothesis import given, strategies as st, settings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.video import VideoSource, TranscriptSegment
from app.models.user import User
from app.models.analysis import VideoAnalysis
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


youtube_url_strategy = st.sampled_from([
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://youtu.be/dQw4w9WgXcQ",
    "https://www.youtube.com/watch?v=jNQXAC9IVRw",
])


# Strategy for generating video analysis data
@st.composite
def video_analysis_strategy(draw):
    """Generate valid video analysis data."""
    return {
        "analysis_version": draw(st.sampled_from(["v1", "v2", "v3"])),
        "duration_analyzed": draw(st.floats(min_value=10.0, max_value=3600.0, allow_nan=False, allow_infinity=False)),
        "avg_audio_energy": draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)),
        "avg_visual_interest": draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)),
        "avg_engagement": draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)),
        "audio_peaks_count": draw(st.integers(min_value=0, max_value=100)),
        "visual_peaks_count": draw(st.integers(min_value=0, max_value=100)),
        "viral_moments_count": draw(st.integers(min_value=0, max_value=50)),
    }


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
    analysis_data=video_analysis_strategy(),
)
def test_video_with_analysis_skips_analysis(
    youtube_video_id: str,
    user_id: int,
    slug: str,
    file_path: str,
    youtube_url: str,
    analysis_data: dict,
):
    """
    **Feature: lazy-processing-flow, Property 4: Analysis Reuse**
    **Validates: Requirements 3.6**
    
    Property: For any video that has existing analysis,
    check_processing_status should return has_analysis=True and needs_analysis=False.
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
            title="Video With Analysis",
            slug=slug,
            is_downloaded=True,
            download_progress=100.0,
            file_path=file_path,
        )
        session.add(video)
        session.commit()
        session.refresh(video)
        
        # Add video analysis
        analysis = VideoAnalysis(
            video_source_id=video.id,
            analysis_version=analysis_data["analysis_version"],
            duration_analyzed=analysis_data["duration_analyzed"],
            avg_audio_energy=analysis_data["avg_audio_energy"],
            avg_visual_interest=analysis_data["avg_visual_interest"],
            avg_engagement=analysis_data["avg_engagement"],
            audio_peaks_count=analysis_data["audio_peaks_count"],
            visual_peaks_count=analysis_data["visual_peaks_count"],
            viral_moments_count=analysis_data["viral_moments_count"],
        )
        session.add(analysis)
        session.commit()
        
        # Check processing status
        status = check_processing_status(session, video)
        
        # Property: Video with analysis should have has_analysis=True
        assert status.has_analysis is True, (
            f"Expected has_analysis=True for video with analysis, "
            f"got has_analysis={status.has_analysis}"
        )
        
        # Property: Video with analysis should NOT need analysis
        assert status.needs_analysis is False, (
            f"Expected needs_analysis=False for video with existing analysis, "
            f"got needs_analysis={status.needs_analysis}"
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
def test_video_without_analysis_needs_analysis(
    youtube_video_id: str,
    user_id: int,
    slug: str,
    file_path: str,
    youtube_url: str,
):
    """
    **Feature: lazy-processing-flow, Property 4: Analysis Reuse**
    **Validates: Requirements 3.6**
    
    Property: For any video that has NO analysis,
    check_processing_status should return has_analysis=False and needs_analysis=True.
    This is the inverse property that validates the detection logic works correctly.
    """
    engine = create_test_db()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    try:
        # Create test user
        create_test_user(session, user_id)
        
        # Create a video WITHOUT analysis
        video = VideoSource(
            user_id=user_id,
            youtube_video_id=youtube_video_id,
            source_type="youtube",
            source_url=youtube_url,
            title="Video Without Analysis",
            slug=slug,
            is_downloaded=True,
            download_progress=100.0,
            file_path=file_path,
        )
        session.add(video)
        session.commit()
        session.refresh(video)
        
        # Do NOT add any analysis
        
        # Check processing status
        status = check_processing_status(session, video)
        
        # Property: Video without analysis should have has_analysis=False
        assert status.has_analysis is False, (
            f"Expected has_analysis=False for video with no analysis, "
            f"got has_analysis={status.has_analysis}"
        )
        
        # Property: Video without analysis should need analysis
        assert status.needs_analysis is True, (
            f"Expected needs_analysis=True for video without analysis, "
            f"got needs_analysis={status.needs_analysis}"
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
    analysis_data=video_analysis_strategy(),
)
def test_analysis_reuse_preserves_existing_analysis(
    youtube_video_id: str,
    user_id: int,
    slug: str,
    file_path: str,
    youtube_url: str,
    analysis_data: dict,
):
    """
    **Feature: lazy-processing-flow, Property 4: Analysis Reuse**
    **Validates: Requirements 3.6**
    
    Property: For any video with existing analysis, checking the
    processing status should not modify or delete the existing analysis.
    The analysis data should remain the same before and after the check.
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
            title="Video With Analysis",
            slug=slug,
            is_downloaded=True,
            download_progress=100.0,
            file_path=file_path,
        )
        session.add(video)
        session.commit()
        session.refresh(video)
        
        # Add video analysis
        analysis = VideoAnalysis(
            video_source_id=video.id,
            analysis_version=analysis_data["analysis_version"],
            duration_analyzed=analysis_data["duration_analyzed"],
            avg_audio_energy=analysis_data["avg_audio_energy"],
            avg_visual_interest=analysis_data["avg_visual_interest"],
            avg_engagement=analysis_data["avg_engagement"],
            audio_peaks_count=analysis_data["audio_peaks_count"],
            visual_peaks_count=analysis_data["visual_peaks_count"],
            viral_moments_count=analysis_data["viral_moments_count"],
        )
        session.add(analysis)
        session.commit()
        session.refresh(analysis)
        
        # Store original values
        original_version = analysis.analysis_version
        original_duration = analysis.duration_analyzed
        original_audio_energy = analysis.avg_audio_energy
        
        # Check processing status (should not modify analysis)
        status = check_processing_status(session, video)
        
        # Refresh analysis from database
        session.refresh(analysis)
        
        # Property: Analysis data should be preserved
        assert analysis.analysis_version == original_version, (
            f"Analysis version changed from {original_version} to {analysis.analysis_version} "
            f"after check_processing_status call"
        )
        assert analysis.duration_analyzed == original_duration, (
            f"Duration analyzed changed from {original_duration} to {analysis.duration_analyzed} "
            f"after check_processing_status call"
        )
        assert analysis.avg_audio_energy == original_audio_energy, (
            f"Avg audio energy changed from {original_audio_energy} to {analysis.avg_audio_energy} "
            f"after check_processing_status call"
        )
        
        # Property: Analysis should still exist
        analysis_count = session.query(VideoAnalysis).filter(
            VideoAnalysis.video_source_id == video.id
        ).count()
        assert analysis_count == 1, (
            f"Expected 1 analysis record, got {analysis_count}"
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
    analysis_version=st.sampled_from(["v1", "v2", "v3"]),
)
def test_analysis_detection_works_for_any_version(
    youtube_video_id: str,
    user_id: int,
    slug: str,
    file_path: str,
    youtube_url: str,
    analysis_version: str,
):
    """
    **Feature: lazy-processing-flow, Property 4: Analysis Reuse**
    **Validates: Requirements 3.6**
    
    Property: For any analysis version (v1, v2, v3),
    the system should correctly detect that analysis exists and skip analysis.
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
            title="Video With Variable Analysis Version",
            slug=slug,
            is_downloaded=True,
            download_progress=100.0,
            file_path=file_path,
        )
        session.add(video)
        session.commit()
        session.refresh(video)
        
        # Add video analysis with specified version
        analysis = VideoAnalysis(
            video_source_id=video.id,
            analysis_version=analysis_version,
            duration_analyzed=120.0,
            avg_audio_energy=0.5,
            avg_visual_interest=0.5,
            avg_engagement=0.5,
        )
        session.add(analysis)
        session.commit()
        
        # Check processing status
        status = check_processing_status(session, video)
        
        # Property: Any analysis version should be detected
        assert status.has_analysis is True, (
            f"Expected has_analysis=True for video with {analysis_version} analysis, "
            f"got has_analysis={status.has_analysis}"
        )
        
        # Property: Should not need analysis
        assert status.needs_analysis is False, (
            f"Expected needs_analysis=False for video with {analysis_version} analysis, "
            f"got needs_analysis={status.needs_analysis}"
        )
        
    finally:
        session.close()
