"""
Script to fix clip viral scores to be consistent with grades.

This script recalculates viral_score for all clips based on their grades
to ensure consistency between displayed grades and scores.

Usage:
    python -m scripts.fix_clip_scores
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models import Clip


def grade_to_score(grade: str) -> float:
    """Convert letter grade to numeric score."""
    mapping = {"A": 9.0, "B": 7.0, "C": 5.0, "D": 3.0}
    return mapping.get(grade, 5.0)


def calculate_viral_score(clip: Clip) -> float:
    """Calculate viral score from grades."""
    return (
        grade_to_score(clip.grade_hook or "C") * 0.35 +
        grade_to_score(clip.grade_flow or "C") * 0.20 +
        grade_to_score(clip.grade_value or "C") * 0.25 +
        grade_to_score(clip.grade_trend or "C") * 0.20
    )


def fix_clip_scores():
    """Fix all clip scores to be consistent with grades."""
    db: Session = SessionLocal()
    
    try:
        clips = db.query(Clip).all()
        print(f"Found {len(clips)} clips to check")
        
        updated = 0
        for clip in clips:
            expected_score = calculate_viral_score(clip)
            current_score = clip.viral_score or 0
            
            # Check if score is inconsistent (more than 0.5 difference)
            if abs(expected_score - current_score) > 0.5:
                print(f"Clip {clip.id}: {current_score:.1f} -> {expected_score:.1f} "
                      f"(H:{clip.grade_hook} F:{clip.grade_flow} V:{clip.grade_value} T:{clip.grade_trend})")
                clip.viral_score = round(expected_score, 1)
                updated += 1
        
        if updated > 0:
            db.commit()
            print(f"\nUpdated {updated} clips")
        else:
            print("\nAll clips have consistent scores")
            
    finally:
        db.close()


if __name__ == "__main__":
    fix_clip_scores()
