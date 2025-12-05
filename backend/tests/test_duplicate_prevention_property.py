"""
Property-based tests for Duplicate Prevention.

**Feature: lazy-processing-flow, Property 1: Duplicate Prevention**
**Validates: Requirements 1.1, 1.2, 7.1**

Property: For any YouTube video ID and user ID combination, there should be 
at most one VideoSource record in the database.
"""

from hypothesis import given, strategies as st, settings
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import IntegrityError

from app.db.base import Base
from app.models.video import VideoSource
from app.models.user import User


# Strategy for generating valid YouTube video IDs (11 characters, alphanumeric + _ -)
youtube_video_id_strategy = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-",
    min_size=11,
    max_size=11,
)

# Strategy for generating user IDs (positive integers)
user_id_strategy = st.integers(min_value=1, max_value=1000)

# Strategy for generating slugs (unique per video)
slug_strategy = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789-",
    min_size=5,
    max_size=50,
).filter(lambda s: s and not s.startswith('-') and not s.endswith('-') and '--' not in s)


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
    slug1=slug_strategy,
    slug2=slug_strategy,
)
def test_duplicate_youtube_video_per_user_prevented(
    youtube_video_id: str, user_id: int, slug1: str, slug2: str
):
    """
    **Feature: lazy-processing-flow, Property 1: Duplicate Prevention**
    **Validates: Requirements 1.1, 1.2, 7.1**
    
    Property: For any YouTube video ID and user ID combination, attempting to
    insert a second record with the same combination should raise an IntegrityError.
    """
    # Ensure slugs are different
    if slug1 == slug2:
        slug2 = slug2 + "-2"
    
    engine = create_test_db()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    try:
        # Create test user
        create_test_user(session, user_id)
        
        # Create first video - should succeed
        video1 = VideoSource(
            user_id=user_id,
            youtube_video_id=youtube_video_id,
            source_type="youtube",
            title="Test Video 1",
            slug=slug1,
        )
        session.add(video1)
        session.commit()
        
        # Attempt to create second video with same youtube_video_id and user_id
        # This should raise IntegrityError due to unique constraint
        video2 = VideoSource(
            user_id=user_id,
            youtube_video_id=youtube_video_id,
            source_type="youtube",
            title="Test Video 2",
            slug=slug2,
        )
        session.add(video2)
        
        duplicate_prevented = False
        try:
            session.commit()
        except IntegrityError:
            duplicate_prevented = True
            session.rollback()
        
        # Property: duplicate should be prevented
        assert duplicate_prevented, (
            f"Duplicate video was allowed: youtube_video_id={youtube_video_id}, user_id={user_id}"
        )
        
    finally:
        session.close()


@settings(max_examples=100)
@given(
    youtube_video_id=youtube_video_id_strategy,
    user_id1=user_id_strategy,
    user_id2=user_id_strategy,
    slug1=slug_strategy,
    slug2=slug_strategy,
)
def test_same_youtube_video_allowed_for_different_users(
    youtube_video_id: str, user_id1: int, user_id2: int, slug1: str, slug2: str
):
    """
    **Feature: lazy-processing-flow, Property 1: Duplicate Prevention**
    **Validates: Requirements 1.4**
    
    Property: For any YouTube video ID, different users should be able to have
    their own VideoSource records for the same video.
    """
    # Ensure user IDs are different
    if user_id1 == user_id2:
        user_id2 = user_id1 + 1
    
    # Ensure slugs are different
    if slug1 == slug2:
        slug2 = slug2 + "-2"
    
    engine = create_test_db()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    try:
        # Create test users
        create_test_user(session, user_id1)
        create_test_user(session, user_id2)
        
        # Create video for first user
        video1 = VideoSource(
            user_id=user_id1,
            youtube_video_id=youtube_video_id,
            source_type="youtube",
            title="Test Video User 1",
            slug=slug1,
        )
        session.add(video1)
        session.commit()
        
        # Create video for second user with same youtube_video_id
        # This should succeed because user_id is different
        video2 = VideoSource(
            user_id=user_id2,
            youtube_video_id=youtube_video_id,
            source_type="youtube",
            title="Test Video User 2",
            slug=slug2,
        )
        session.add(video2)
        
        try:
            session.commit()
            both_created = True
        except IntegrityError:
            both_created = False
            session.rollback()
        
        # Property: both videos should be created successfully
        assert both_created, (
            f"Same video for different users was blocked: "
            f"youtube_video_id={youtube_video_id}, user_id1={user_id1}, user_id2={user_id2}"
        )
        
        # Verify both records exist
        count = session.query(func.count(VideoSource.id)).filter(
            VideoSource.youtube_video_id == youtube_video_id
        ).scalar()
        
        assert count == 2, f"Expected 2 records, got {count}"
        
    finally:
        session.close()


@settings(max_examples=100)
@given(
    youtube_video_id=youtube_video_id_strategy,
    user_id=user_id_strategy,
    slug=slug_strategy,
)
def test_single_video_per_user_youtube_id_invariant(
    youtube_video_id: str, user_id: int, slug: str
):
    """
    **Feature: lazy-processing-flow, Property 1: Duplicate Prevention**
    **Validates: Requirements 7.1, 7.2**
    
    Property: After any sequence of insert operations, there should be at most
    one VideoSource record for any (youtube_video_id, user_id) combination.
    """
    engine = create_test_db()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    try:
        # Create test user
        create_test_user(session, user_id)
        
        # Create first video
        video = VideoSource(
            user_id=user_id,
            youtube_video_id=youtube_video_id,
            source_type="youtube",
            title="Test Video",
            slug=slug,
        )
        session.add(video)
        session.commit()
        
        # Try to insert duplicates multiple times (simulating concurrent requests)
        for i in range(5):
            try:
                duplicate = VideoSource(
                    user_id=user_id,
                    youtube_video_id=youtube_video_id,
                    source_type="youtube",
                    title=f"Duplicate Video {i}",
                    slug=f"{slug}-dup-{i}",
                )
                session.add(duplicate)
                session.commit()
            except IntegrityError:
                session.rollback()
        
        # Property: count should always be exactly 1
        count = session.query(func.count(VideoSource.id)).filter(
            VideoSource.youtube_video_id == youtube_video_id,
            VideoSource.user_id == user_id,
        ).scalar()
        
        assert count == 1, (
            f"Expected exactly 1 record for (youtube_video_id={youtube_video_id}, "
            f"user_id={user_id}), got {count}"
        )
        
    finally:
        session.close()

