"""
Regenerate hashtags for all clips.
Use --force to regenerate even if hashtags exist.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import joinedload
from sqlalchemy.orm.attributes import flag_modified
from app.db.session import SessionLocal
from app.models import Clip, TranscriptSegment
from app.models.clip import ClipLLMContext
from app.services.virality import _generate_hashtags_with_llm

force = "--force" in sys.argv

db = SessionLocal()

try:
    clips = db.query(Clip).options(joinedload(Clip.llm_context)).all()
    print(f"Found {len(clips)} clips")
    if force:
        print("Force mode: regenerating all hashtags")
    
    updated = 0
    for clip in clips:
        # Get LLM context directly
        llm_ctx = (
            db.query(ClipLLMContext)
            .filter(ClipLLMContext.clip_id == clip.id)
            .order_by(ClipLLMContext.created_at.desc())
            .first()
        )
        
        # Check if hashtags exist
        has_hashtags = False
        if llm_ctx and llm_ctx.response_json:
            hashtags = llm_ctx.response_json.get("hashtags", [])
            if hashtags and len(hashtags) > 0:
                has_hashtags = True
        
        if has_hashtags and not force:
            print(f"Clip {clip.id}: Already has hashtags (use --force to regenerate)")
            continue
        
        # Get transcript for this clip
        transcript = (
            db.query(TranscriptSegment)
            .filter(
                TranscriptSegment.video_source_id == clip.batch.video_source_id,
                TranscriptSegment.start_time_sec >= clip.start_time_sec,
                TranscriptSegment.end_time_sec <= clip.end_time_sec,
            )
            .order_by(TranscriptSegment.start_time_sec)
            .all()
        )
        transcript_text = " ".join([t.text for t in transcript])
        
        # Get video type from existing context
        video_type = "unknown"
        if llm_ctx and llm_ctx.response_json:
            video_type = llm_ctx.response_json.get("detected_video_type", "unknown")
        
        # Generate hashtags
        print(f"Clip {clip.id}: Generating hashtags...")
        new_hashtags = _generate_hashtags_with_llm(
            transcript_text, clip.title or "", video_type
        )
        
        # Update or create LLM context
        if llm_ctx:
            # Create a new dict to ensure SQLAlchemy detects the change
            response_json = dict(llm_ctx.response_json) if llm_ctx.response_json else {}
            response_json["hashtags"] = new_hashtags
            llm_ctx.response_json = response_json
            flag_modified(llm_ctx, "response_json")
        else:
            # Create new LLM context
            llm_ctx = ClipLLMContext(
                clip_id=clip.id,
                prompt="",
                response_json={"hashtags": new_hashtags}
            )
            db.add(llm_ctx)
        
        print(f"Clip {clip.id}: Generated {len(new_hashtags)} hashtags: {new_hashtags[:5]}")
        updated += 1
    
    db.commit()
    print(f"\nUpdated {updated} clips with new hashtags")
    
finally:
    db.close()
