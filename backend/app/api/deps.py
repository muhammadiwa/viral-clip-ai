from typing import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.models import User, ProcessingJob
from app.core.config import get_settings
from sqlalchemy import func

settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    sub = decode_access_token(token)
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(User).filter(User.email == sub).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def enforce_daily_job_limit(db: Session, user: User, max_jobs: int = 50) -> None:
    count = (
        db.query(ProcessingJob)
        .filter(
            ProcessingJob.created_at >= func.datetime("now", "-1 day"),
            ProcessingJob.video.has(user_id=user.id),
        )
        .count()
    )
    if count >= max_jobs:
        raise HTTPException(status_code=429, detail="Daily job limit reached")


def enforce_credits(db: Session, user: User, cost: int) -> None:
    if user.credits is not None and user.credits < cost:
        raise HTTPException(status_code=402, detail="Insufficient credits")
    if user.credits is not None:
        user.credits -= cost
        db.commit()
