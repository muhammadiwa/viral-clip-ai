"""
Fix duplicate LLM contexts for clips.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import func
from app.db.session import SessionLocal
from app.models import Clip
from app.models.clip import ClipLLMContext

db = SessionLocal()

try:
    # Find clips with multiple LLM contexts
    duplicates = (
        db.query(ClipLLMContext.clip_id, func.count(ClipLLMContext.id).label('count'))
        .group_by(ClipLLMContext.clip_id)
        .having(func.count(ClipLLMContext.id) > 1)
        .all()
    )
    
    print(f"Found {len(duplicates)} clips with duplicate LLM contexts")
    
    for clip_id, count in duplicates:
        print(f"\nClip {clip_id} has {count} LLM contexts")
        
        # Get all contexts for this clip
        contexts = (
            db.query(ClipLLMContext)
            .filter(ClipLLMContext.clip_id == clip_id)
            .order_by(ClipLLMContext.created_at.desc())
            .all()
        )
        
        # Keep the most recent one (first in list), delete the rest
        keep = contexts[0]
        print(f"  Keeping context {keep.id} (created: {keep.created_at})")
        print(f"  Hashtags: {keep.response_json.get('hashtags', [])[:5] if keep.response_json else 'None'}")
        
        for ctx in contexts[1:]:
            print(f"  Deleting context {ctx.id} (created: {ctx.created_at})")
            db.delete(ctx)
    
    db.commit()
    print(f"\nFixed {len(duplicates)} clips")
    
finally:
    db.close()
