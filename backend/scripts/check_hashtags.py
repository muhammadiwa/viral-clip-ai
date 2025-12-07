"""
Check hashtags for all clips.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import joinedload
from app.db.session import SessionLocal
from app.models import Clip
from app.models.clip import ClipLLMContext

db = SessionLocal()

try:
    # Use fresh query with explicit join to get latest data
    clips = (
        db.query(Clip)
        .options(joinedload(Clip.llm_context))
        .all()
    )
    print(f"Total clips: {len(clips)}\n")
    
    for clip in clips:
        # Query LLM context directly to ensure fresh data
        llm_ctx = (
            db.query(ClipLLMContext)
            .filter(ClipLLMContext.clip_id == clip.id)
            .order_by(ClipLLMContext.created_at.desc())
            .first()
        )
        
        hashtags = []
        if llm_ctx and llm_ctx.response_json:
            hashtags = llm_ctx.response_json.get("hashtags", [])
        
        title = clip.title[:40] if clip.title else "No title"
        print(f"Clip {clip.id}: {title}")
        print(f"  Viral Score: {clip.viral_score}")
        print(f"  Hashtags ({len(hashtags)}): {' '.join(['#' + h for h in hashtags[:5]])}")
        if len(hashtags) > 5:
            print(f"    + {len(hashtags) - 5} more")
        print()
        
finally:
    db.close()
