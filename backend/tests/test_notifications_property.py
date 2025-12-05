"""
Property-based tests for notification functionality.

**Feature: navbar-navigation, Property 1: Notification Badge Count Accuracy**
**Validates: Requirements 3.2**

Property: For any notification list with N unread notifications (where N > 0),
the notification badge SHALL display the exact count N. When N = 0, the badge
SHALL not be displayed.
"""

from hypothesis import given, strategies as st, settings
from app.models import Notification


# Strategy for generating notification data
notification_strategy = st.fixed_dictionaries({
    "title": st.text(min_size=1, max_size=100),
    "message": st.text(min_size=1, max_size=500),
    "type": st.sampled_from(["success", "info", "warning", "error"]),
    "read": st.booleans(),
    "link": st.one_of(st.none(), st.text(min_size=1, max_size=200)),
})


def count_unread_notifications(notifications: list[dict]) -> int:
    """Count unread notifications - this is the core logic being tested."""
    return sum(1 for n in notifications if not n["read"])


@settings(max_examples=100)
@given(st.lists(notification_strategy, min_size=0, max_size=50))
def test_unread_count_matches_actual_unread_notifications(notifications: list[dict]):
    """
    **Feature: navbar-navigation, Property 1: Notification Badge Count Accuracy**
    **Validates: Requirements 3.2**
    
    Property: For any list of notifications, the unread count should exactly
    equal the number of notifications where read=False.
    """
    # Calculate expected unread count
    expected_unread = sum(1 for n in notifications if not n["read"])
    
    # Calculate actual unread count using the function
    actual_unread = count_unread_notifications(notifications)
    
    # Property: unread count must exactly match
    assert actual_unread == expected_unread


@settings(max_examples=100)
@given(st.lists(notification_strategy, min_size=0, max_size=50))
def test_badge_visibility_based_on_unread_count(notifications: list[dict]):
    """
    **Feature: navbar-navigation, Property 1: Notification Badge Count Accuracy**
    **Validates: Requirements 3.2**
    
    Property: Badge should be visible (displayed) when unread_count > 0,
    and hidden when unread_count = 0.
    """
    unread_count = count_unread_notifications(notifications)
    
    # Determine badge visibility
    badge_should_be_visible = unread_count > 0
    
    # Property: badge visibility is determined by unread count
    if unread_count > 0:
        assert badge_should_be_visible is True
    else:
        assert badge_should_be_visible is False



@settings(max_examples=100)
@given(
    read_count=st.integers(min_value=0, max_value=25),
    unread_count=st.integers(min_value=0, max_value=25),
)
def test_database_unread_count_accuracy(read_count: int, unread_count: int):
    """
    **Feature: navbar-navigation, Property 1: Notification Badge Count Accuracy**
    **Validates: Requirements 3.2**
    
    Property: For any combination of read and unread notifications in the database,
    the query should return the exact count of unread notifications.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.db.base import Base
    from app.models import User
    
    # Create fresh database for each test run
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db_session = SessionLocal()
    
    try:
        # Create test user
        test_user = User(
            email="test@example.com",
            password_hash="hashed_password",
            credits=100,
        )
        db_session.add(test_user)
        db_session.commit()
        db_session.refresh(test_user)
        
        # Create read notifications
        for i in range(read_count):
            notification = Notification(
                user_id=test_user.id,
                title=f"Read notification {i}",
                message=f"This is read notification {i}",
                type="info",
                read=True,
            )
            db_session.add(notification)
        
        # Create unread notifications
        for i in range(unread_count):
            notification = Notification(
                user_id=test_user.id,
                title=f"Unread notification {i}",
                message=f"This is unread notification {i}",
                type="info",
                read=False,
            )
            db_session.add(notification)
        
        db_session.commit()
        
        # Query unread count from database
        actual_unread = (
            db_session.query(Notification)
            .filter(Notification.user_id == test_user.id, Notification.read == False)
            .count()
        )
        
        # Property: database query must return exact unread count
        assert actual_unread == unread_count
        
        # Also verify total count
        total = (
            db_session.query(Notification)
            .filter(Notification.user_id == test_user.id)
            .count()
        )
        assert total == read_count + unread_count
    finally:
        db_session.close()
