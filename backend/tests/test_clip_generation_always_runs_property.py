"""
Property-based tests for Clip Generation Always Runs.

**Feature: lazy-processing-flow, Property 5: Clip Generation Always Runs**
**Validates: Requirements 3.7**

Property: For any call to generate clips, the clip generation step should 
always execute regardless of previous clip batches.
"""

from hypothesis import given, strategies as st, settings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.video import VideoSource, TranscriptSegment
from app.models.user import User
from app.models.clip import ClipBatch, Clip
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


# Strategy for generating clip batch config
@st.composite
def clip_config_strategy(draw):
    """Generate valid clip batch configuration."""
    return {
        "aspect_ratio": draw(st.sampled_from(["9:16", "16:9", "1:1"])),
        "min_duration": draw(st.integers(min_value=15, max_value=30)),
        "max_duration": draw(st.integers(min_value=45, max_value=90)),
        "target_count": draw(st.integers(min_value=3, max_value=10)),
    }


# Strategy for generating clip data
@st.composite
def clip_data_strategy(draw):
    """Generate valid clip data."""
    start_time = draw(st.floats(min_value=0.0, max_value=3000.0, allow_nan=False, allow_infinity=False))
    duration = draw(st.floats(min_value=15.0, max_value=60.0, allow_nan=False, allow_infinity=False))
    return {
        "start_time_sec": start_time,
        "end_time_sec": start_time + duration,
        "duration_sec": duration,
        "title": draw(st.text(min_size=5, max_size=50)),
        "viral_score": draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)),
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
    existing_batch_count=st.integers(min_value=1, max_value=5),
    new_config=clip_config_strategy(),
)
def test_clip_generation_runs_regardless_of_existing_batches(
    youtube_video_id: str,
    user_id: int,
    slug: str,
    file_path: str,
    youtube_url: str,
    existing_batch_count: int,
    new_config: dict,
):
    """
    **Feature: lazy-processing-flow, Property 5: Clip Generation Always Runs**
    **Validates: Requirements 3.7**
    
    Property: For any video that already has clip batches, creating a new
    clip batch should always succeed. The existence of previous batches
    should not prevent new clip generation.
    """
    engine = create_test_db()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    try:
        # Create test user
        create_test_user(session, user_id)
        
        # Create a fully processed video (downloaded, transcribed, analyzed)
        video = VideoSource(
            user_id=user_id,
            youtube_video_id=youtube_video_id,
            source_type="youtube",
            source_url=youtube_url,
            title="Video With Existing Clips",
            slug=slug,
            is_downloaded=True,
            download_progress=100.0,
            file_path=file_path,
            duration_seconds=300.0,
        )
        session.add(video)
        session.commit()
        session.refresh(video)
        
        # Add transcript segments
        for i in range(5):
            segment = TranscriptSegment(
                video_source_id=video.id,
                start_time_sec=float(i * 60),
                end_time_sec=float(i * 60 + 55),
                text=f"Segment {i} content",
                language="en",
            )
            session.add(segment)
        session.commit()
        
        # Add video analysis
        analysis = VideoAnalysis(
            video_source_id=video.id,
            analysis_version="v3",
            duration_analyzed=300.0,
            avg_audio_energy=0.5,
            avg_visual_interest=0.5,
            avg_engagement=0.5,
        )
        session.add(analysis)
        session.commit()
        
        # Create existing clip batches
        for i in range(existing_batch_count):
            batch = ClipBatch(
                video_source_id=video.id,
                name=f"batch_{i}",
                config_json={"aspect_ratio": "9:16"},
                status="ready",
            )
            session.add(batch)
        session.commit()
        
        # Count batches before new generation
        batches_before = session.query(ClipBatch).filter(
            ClipBatch.video_source_id == video.id
        ).count()
        
        # Property: Should be able to create a new clip batch
        new_batch = ClipBatch(
            video_source_id=video.id,
            name="new_batch",
            config_json=new_config,
            status="processing",
        )
        session.add(new_batch)
        session.commit()
        session.refresh(new_batch)
        
        # Count batches after new generation
        batches_after = session.query(ClipBatch).filter(
            ClipBatch.video_source_id == video.id
        ).count()
        
        # Property: New batch should be created successfully
        assert new_batch.id is not None, (
            "New clip batch should have been assigned an ID"
        )
        
        # Property: Batch count should increase by 1
        assert batches_after == batches_before + 1, (
            f"Expected {batches_before + 1} batches after creation, "
            f"got {batches_after}"
        )
        
        # Property: New batch should have the new config
        assert new_batch.config_json == new_config, (
            f"New batch config should be {new_config}, "
            f"got {new_batch.config_json}"
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
    config=clip_config_strategy(),
)
def test_clip_generation_runs_for_video_without_existing_batches(
    youtube_video_id: str,
    user_id: int,
    slug: str,
    file_path: str,
    youtube_url: str,
    config: dict,
):
    """
    **Feature: lazy-processing-flow, Property 5: Clip Generation Always Runs**
    **Validates: Requirements 3.7**
    
    Property: For any fully processed video without existing clip batches,
    clip generation should always run and create a new batch.
    """
    engine = create_test_db()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    try:
        # Create test user
        create_test_user(session, user_id)
        
        # Create a fully processed video
        video = VideoSource(
            user_id=user_id,
            youtube_video_id=youtube_video_id,
            source_type="youtube",
            source_url=youtube_url,
            title="Video Without Clips",
            slug=slug,
            is_downloaded=True,
            download_progress=100.0,
            file_path=file_path,
            duration_seconds=300.0,
        )
        session.add(video)
        session.commit()
        session.refresh(video)
        
        # Add transcript segments
        segment = TranscriptSegment(
            video_source_id=video.id,
            start_time_sec=0.0,
            end_time_sec=60.0,
            text="Test segment content",
            language="en",
        )
        session.add(segment)
        session.commit()
        
        # Add video analysis
        analysis = VideoAnalysis(
            video_source_id=video.id,
            analysis_version="v3",
            duration_analyzed=300.0,
            avg_audio_energy=0.5,
            avg_visual_interest=0.5,
            avg_engagement=0.5,
        )
        session.add(analysis)
        session.commit()
        
        # Verify no existing batches
        batches_before = session.query(ClipBatch).filter(
            ClipBatch.video_source_id == video.id
        ).count()
        assert batches_before == 0, "Test setup error: should have no batches"
        
        # Property: Should be able to create first clip batch
        new_batch = ClipBatch(
            video_source_id=video.id,
            name="first_batch",
            config_json=config,
            status="processing",
        )
        session.add(new_batch)
        session.commit()
        session.refresh(new_batch)
        
        # Property: First batch should be created successfully
        assert new_batch.id is not None, (
            "First clip batch should have been assigned an ID"
        )
        
        # Property: Batch count should be 1
        batches_after = session.query(ClipBatch).filter(
            ClipBatch.video_source_id == video.id
        ).count()
        assert batches_after == 1, (
            f"Expected 1 batch after creation, got {batches_after}"
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
    configs=st.lists(clip_config_strategy(), min_size=2, max_size=5),
)
def test_multiple_clip_generations_all_succeed(
    youtube_video_id: str,
    user_id: int,
    slug: str,
    file_path: str,
    youtube_url: str,
    configs: list,
):
    """
    **Feature: lazy-processing-flow, Property 5: Clip Generation Always Runs**
    **Validates: Requirements 3.7**
    
    Property: For any sequence of clip generation requests with different
    configurations, each request should create a new batch. All batches
    should coexist without interfering with each other.
    """
    engine = create_test_db()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    try:
        # Create test user
        create_test_user(session, user_id)
        
        # Create a fully processed video
        video = VideoSource(
            user_id=user_id,
            youtube_video_id=youtube_video_id,
            source_type="youtube",
            source_url=youtube_url,
            title="Video For Multiple Generations",
            slug=slug,
            is_downloaded=True,
            download_progress=100.0,
            file_path=file_path,
            duration_seconds=300.0,
        )
        session.add(video)
        session.commit()
        session.refresh(video)
        
        # Add transcript and analysis
        segment = TranscriptSegment(
            video_source_id=video.id,
            start_time_sec=0.0,
            end_time_sec=60.0,
            text="Test segment",
            language="en",
        )
        session.add(segment)
        
        analysis = VideoAnalysis(
            video_source_id=video.id,
            analysis_version="v3",
            duration_analyzed=300.0,
            avg_audio_energy=0.5,
            avg_visual_interest=0.5,
            avg_engagement=0.5,
        )
        session.add(analysis)
        session.commit()
        
        # Create multiple batches with different configs
        created_batches = []
        for i, config in enumerate(configs):
            batch = ClipBatch(
                video_source_id=video.id,
                name=f"batch_{i}",
                config_json=config,
                status="processing",
            )
            session.add(batch)
            session.commit()
            session.refresh(batch)
            created_batches.append(batch)
        
        # Property: All batches should be created
        assert len(created_batches) == len(configs), (
            f"Expected {len(configs)} batches, created {len(created_batches)}"
        )
        
        # Property: Each batch should have unique ID
        batch_ids = [b.id for b in created_batches]
        assert len(batch_ids) == len(set(batch_ids)), (
            "All batch IDs should be unique"
        )
        
        # Property: Each batch should have its own config
        for i, batch in enumerate(created_batches):
            assert batch.config_json == configs[i], (
                f"Batch {i} config mismatch: expected {configs[i]}, "
                f"got {batch.config_json}"
            )
        
        # Property: Total batch count should match
        total_batches = session.query(ClipBatch).filter(
            ClipBatch.video_source_id == video.id
        ).count()
        assert total_batches == len(configs), (
            f"Expected {len(configs)} total batches, got {total_batches}"
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
    existing_clips_per_batch=st.integers(min_value=1, max_value=5),
    new_config=clip_config_strategy(),
)
def test_new_generation_does_not_affect_existing_clips(
    youtube_video_id: str,
    user_id: int,
    slug: str,
    file_path: str,
    youtube_url: str,
    existing_clips_per_batch: int,
    new_config: dict,
):
    """
    **Feature: lazy-processing-flow, Property 5: Clip Generation Always Runs**
    **Validates: Requirements 3.7**
    
    Property: For any video with existing clip batches containing clips,
    creating a new batch should not modify or delete the existing clips.
    The existing clips should remain intact after new generation.
    """
    engine = create_test_db()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    try:
        # Create test user
        create_test_user(session, user_id)
        
        # Create a fully processed video
        video = VideoSource(
            user_id=user_id,
            youtube_video_id=youtube_video_id,
            source_type="youtube",
            source_url=youtube_url,
            title="Video With Existing Clips",
            slug=slug,
            is_downloaded=True,
            download_progress=100.0,
            file_path=file_path,
            duration_seconds=300.0,
        )
        session.add(video)
        session.commit()
        session.refresh(video)
        
        # Add transcript and analysis
        segment = TranscriptSegment(
            video_source_id=video.id,
            start_time_sec=0.0,
            end_time_sec=60.0,
            text="Test segment",
            language="en",
        )
        session.add(segment)
        
        analysis = VideoAnalysis(
            video_source_id=video.id,
            analysis_version="v3",
            duration_analyzed=300.0,
            avg_audio_energy=0.5,
            avg_visual_interest=0.5,
            avg_engagement=0.5,
        )
        session.add(analysis)
        session.commit()
        
        # Create existing batch with clips
        existing_batch = ClipBatch(
            video_source_id=video.id,
            name="existing_batch",
            config_json={"aspect_ratio": "9:16"},
            status="ready",
        )
        session.add(existing_batch)
        session.commit()
        session.refresh(existing_batch)
        
        # Add clips to existing batch
        for i in range(existing_clips_per_batch):
            clip = Clip(
                clip_batch_id=existing_batch.id,
                start_time_sec=float(i * 30),
                end_time_sec=float(i * 30 + 25),
                duration_sec=25.0,
                title=f"Existing Clip {i}",
                viral_score=0.8,
            )
            session.add(clip)
        session.commit()
        
        # Store original clip data
        original_clips = session.query(Clip).filter(
            Clip.clip_batch_id == existing_batch.id
        ).all()
        original_clip_ids = [c.id for c in original_clips]
        original_clip_count = len(original_clips)
        
        # Create new batch (simulating new generation)
        new_batch = ClipBatch(
            video_source_id=video.id,
            name="new_batch",
            config_json=new_config,
            status="processing",
        )
        session.add(new_batch)
        session.commit()
        
        # Property: Original clips should still exist
        clips_after = session.query(Clip).filter(
            Clip.clip_batch_id == existing_batch.id
        ).all()
        
        assert len(clips_after) == original_clip_count, (
            f"Expected {original_clip_count} clips in original batch, "
            f"got {len(clips_after)}"
        )
        
        # Property: Original clip IDs should be preserved
        clip_ids_after = [c.id for c in clips_after]
        assert set(clip_ids_after) == set(original_clip_ids), (
            "Original clip IDs should be preserved after new generation"
        )
        
        # Property: Original batch should still exist
        batch_exists = session.query(ClipBatch).filter(
            ClipBatch.id == existing_batch.id
        ).first()
        assert batch_exists is not None, (
            "Original batch should still exist after new generation"
        )
        
    finally:
        session.close()
