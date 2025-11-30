from fastapi import APIRouter, Depends, UploadFile, File
import os
import uuid
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.core.config import get_settings
from app.models import BrandKit, User
from app.schemas import BrandKitCreate, BrandKitOut

settings = get_settings()
router = APIRouter(prefix="/brand-kit", tags=["brand_kit"])


@router.get("", response_model=BrandKitOut | None)
def get_brand_kit(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    kit = db.query(BrandKit).filter(BrandKit.user_id == current_user.id).first()
    return kit


@router.post("", response_model=BrandKitOut)
def upsert_brand_kit(
    payload: BrandKitCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    kit = db.query(BrandKit).filter(BrandKit.user_id == current_user.id).first()
    if not kit:
        kit = BrandKit(user_id=current_user.id)
        db.add(kit)
    for key, value in payload.model_dump().items():
        setattr(kit, key, value)
    db.commit()
    db.refresh(kit)
    return kit


@router.post("/logo", response_model=BrandKitOut)
async def upload_logo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    kit = db.query(BrandKit).filter(BrandKit.user_id == current_user.id).first()
    if not kit:
        kit = BrandKit(user_id=current_user.id)
        db.add(kit)
        db.commit()
        db.refresh(kit)
    media_root = settings.media_root
    user_dir = os.path.join(media_root, "brand", str(current_user.id))
    os.makedirs(user_dir, exist_ok=True)
    ext = os.path.splitext(file.filename or "")[1] or ".png"
    path = os.path.join(user_dir, f"{uuid.uuid4().hex}{ext}")
    with open(path, "wb") as f:
        f.write(await file.read())
    kit.logo_path = path
    db.commit()
    db.refresh(kit)
    return kit
