from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models import SubtitleStyle, User
from app.schemas import SubtitleStyleOut, SubtitleStyleCreate

router = APIRouter(prefix="/subtitle-styles", tags=["subtitle_styles"])


@router.get("", response_model=list[SubtitleStyleOut])
def list_subtitle_styles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    global_styles = db.query(SubtitleStyle).filter(SubtitleStyle.user_id.is_(None)).all()
    user_styles = db.query(SubtitleStyle).filter(SubtitleStyle.user_id == current_user.id).all()
    return [*global_styles, *user_styles]


@router.post("", response_model=SubtitleStyleOut)
def create_subtitle_style(
    payload: SubtitleStyleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    style = SubtitleStyle(
        user_id=current_user.id,
        name=payload.name,
        style_json=payload.style_json,
        is_default_global=False,
    )
    db.add(style)
    db.commit()
    db.refresh(style)
    return style
