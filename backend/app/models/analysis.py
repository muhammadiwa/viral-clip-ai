"""
Database models for storing video analysis data.

These models store the results of multi-modal analysis for:
- Audio analysis (energy, excitement, events)
- Visual analysis (motion, brightness, faces)
- Engagement timeline
"""
from sqlalchemy import Column, Integer, Float, String, Text, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.common import TimestampMixin


class VideoAnalysis(Base, TimestampMixin):
    """
    Stores comprehensive analysis results for a video.
    """
    __tablename__ = "video_analyses"

    id = Column(Integer, primary_key=True)
    video_source_id = Column(Integer, ForeignKey("video_sources.id"), nullable=False, unique=True)
    
    # Analysis metadata
    analysis_version = Column(String, default="v2")
    duration_analyzed = Column(Float)
    
    # Summary statistics
    avg_audio_energy = Column(Float)
    avg_visual_interest = Column(Float)
    avg_engagement = Column(Float)
    
    # Peak counts
    audio_peaks_count = Column(Integer, default=0)
    visual_peaks_count = Column(Integer, default=0)
    viral_moments_count = Column(Integer, default=0)
    
    # Full analysis data (JSON)
    audio_timeline_json = Column(JSON)  # Per-second audio data
    visual_timeline_json = Column(JSON)  # Per-second visual data
    combined_timeline_json = Column(JSON)  # Merged engagement data
    
    # Peaks and moments (JSON arrays)
    audio_peaks_json = Column(JSON)
    visual_peaks_json = Column(JSON)
    engagement_peaks_json = Column(JSON)
    
    video = relationship("VideoSource", backref="analysis")


class SegmentAnalysis(Base, TimestampMixin):
    """
    Stores analysis for individual transcript segments.
    """
    __tablename__ = "segment_analyses"

    id = Column(Integer, primary_key=True)
    transcript_segment_id = Column(Integer, ForeignKey("transcript_segments.id"), nullable=False)
    
    # Sentiment analysis
    sentiment_score = Column(Float)  # -1 to 1
    sentiment_intensity = Column(Float)  # 0 to 1
    emotion = Column(String)  # positive, negative, neutral, etc.
    
    # Hook analysis
    hook_word_count = Column(Integer, default=0)
    hook_words_found = Column(JSON)  # List of found hook words
    hook_score = Column(Float)  # 0 to 1
    
    # Engagement indicators
    has_question = Column(Boolean, default=False)
    has_cta = Column(Boolean, default=False)
    viral_potential = Column(Float)  # 0 to 1
    
    transcript_segment = relationship("TranscriptSegment", backref="analysis")


class ClipAnalysis(Base, TimestampMixin):
    """
    Stores detailed analysis for generated clips.
    """
    __tablename__ = "clip_analyses"

    id = Column(Integer, primary_key=True)
    clip_id = Column(Integer, ForeignKey("clips.id"), nullable=False, unique=True)
    
    # Component scores (0-10)
    audio_energy_score = Column(Float)
    audio_excitement_score = Column(Float)
    visual_interest_score = Column(Float)
    motion_score = Column(Float)
    face_presence_score = Column(Float)
    hook_strength_score = Column(Float)
    sentiment_intensity_score = Column(Float)
    
    # Grade details (JSON with score, grade, analysis)
    hook_grade_json = Column(JSON)
    flow_grade_json = Column(JSON)
    value_grade_json = Column(JSON)
    trend_grade_json = Column(JSON)
    
    # Calculated scores
    data_driven_score = Column(Float)  # Our calculated score
    llm_score = Column(Float)  # LLM's score
    final_score = Column(Float)  # Combined score
    
    # Strengths and weaknesses
    strengths = Column(JSON)  # List of strength descriptions
    weaknesses = Column(JSON)  # List of improvement suggestions
    
    # Timeline data for this clip
    timeline_data_json = Column(JSON)
    
    clip = relationship("Clip", backref="detailed_analysis")
