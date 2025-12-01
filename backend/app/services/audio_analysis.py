"""
Audio Analysis Service for Viral Clip Detection.

Analyzes audio to detect:
- Energy levels (loudness/RMS)
- Speech vs silence vs music
- Laughter and applause
- Pitch variations (excitement indicators)
"""
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import structlog

from app.core.config import get_settings
from app.services.utils import run_cmd, ensure_dir

logger = structlog.get_logger()
settings = get_settings()


def analyze_audio_energy(
    video_path: str,
    sample_interval: float = 1.0,
) -> List[Dict[str, Any]]:
    """
    Analyze audio energy (RMS levels) per interval.
    
    Returns list of dicts with:
    - time: timestamp in seconds
    - energy: normalized energy 0-1
    - db_level: raw dB level
    """
    logger.info("audio_analysis.energy_start", video_path=video_path)
    
    # Use ffmpeg to get audio volume statistics per interval
    cmd = [
        settings.ffmpeg_bin,
        "-i", video_path,
        "-af", f"astats=metadata=1:reset={int(sample_interval * 100)}",
        "-f", "null",
        "-"
    ]
    
    code, _, stderr = run_cmd(cmd)
    if code != 0:
        logger.warning("audio_analysis.energy_failed", error=stderr[:500])
        return []
    
    # Parse RMS levels from stderr
    energy_data = _parse_audio_stats(stderr, sample_interval)
    logger.info("audio_analysis.energy_done", samples=len(energy_data))
    
    return energy_data


def _parse_audio_stats(stderr: str, interval: float) -> List[Dict[str, Any]]:
    """Parse ffmpeg astats output to extract RMS levels."""
    results = []
    current_time = 0.0
    
    # Pattern for RMS level
    rms_pattern = re.compile(r"RMS_level[:\s]+([-\d.]+)")
    
    lines = stderr.split("\n")
    rms_values = []
    
    for line in lines:
        match = rms_pattern.search(line)
        if match:
            try:
                db_level = float(match.group(1))
                rms_values.append(db_level)
            except ValueError:
                continue
    
    # Convert to per-interval samples
    if rms_values:
        # Normalize dB to 0-1 scale (-60dB = 0, 0dB = 1)
        for i, db in enumerate(rms_values):
            time = i * interval
            # Clamp and normalize: -60dB to 0dB -> 0 to 1
            normalized = max(0, min(1, (db + 60) / 60))
            results.append({
                "time": time,
                "energy": normalized,
                "db_level": db,
            })
    
    return results


def analyze_audio_with_volumedetect(video_path: str) -> Dict[str, float]:
    """
    Get overall audio statistics using volumedetect filter.
    
    Returns:
    - mean_volume: average dB
    - max_volume: peak dB
    - normalized_mean: 0-1 scale
    """
    cmd = [
        settings.ffmpeg_bin,
        "-i", video_path,
        "-af", "volumedetect",
        "-f", "null",
        "-"
    ]
    
    code, _, stderr = run_cmd(cmd)
    if code != 0:
        return {"mean_volume": -30, "max_volume": -10, "normalized_mean": 0.5}
    
    mean_vol = -30.0
    max_vol = -10.0
    
    for line in stderr.split("\n"):
        if "mean_volume" in line:
            match = re.search(r"mean_volume:\s*([-\d.]+)", line)
            if match:
                mean_vol = float(match.group(1))
        if "max_volume" in line:
            match = re.search(r"max_volume:\s*([-\d.]+)", line)
            if match:
                max_vol = float(match.group(1))
    
    normalized = max(0, min(1, (mean_vol + 60) / 60))
    
    return {
        "mean_volume": mean_vol,
        "max_volume": max_vol,
        "normalized_mean": normalized,
    }


def detect_audio_events(
    video_path: str,
    duration: float,
) -> List[Dict[str, Any]]:
    """
    Detect audio events: high energy moments, potential laughter, applause.
    
    Uses multiple ffmpeg filters to detect:
    - Silence periods (low energy)
    - High energy peaks
    - Sudden volume changes (potential reactions)
    """
    events = []
    
    # 1. Detect silence periods
    silence_events = _detect_silence(video_path, duration)
    events.extend(silence_events)
    
    # 2. Detect high energy periods (inverse of silence)
    high_energy_events = _detect_high_energy(video_path, duration)
    events.extend(high_energy_events)
    
    # Sort by time
    events.sort(key=lambda x: x["time"])
    
    return events


def _detect_silence(video_path: str, duration: float) -> List[Dict[str, Any]]:
    """Detect silence periods using silencedetect filter."""
    cmd = [
        settings.ffmpeg_bin,
        "-i", video_path,
        "-af", "silencedetect=n=-35dB:d=0.5",
        "-f", "null",
        "-"
    ]
    
    code, _, stderr = run_cmd(cmd)
    if code != 0:
        return []
    
    events = []
    silence_start = None
    
    for line in stderr.split("\n"):
        if "silence_start:" in line:
            match = re.search(r"silence_start:\s*([\d.]+)", line)
            if match:
                silence_start = float(match.group(1))
        elif "silence_end:" in line and silence_start is not None:
            match = re.search(r"silence_end:\s*([\d.]+)", line)
            if match:
                silence_end = float(match.group(1))
                events.append({
                    "time": silence_start,
                    "end_time": silence_end,
                    "duration": silence_end - silence_start,
                    "type": "silence",
                    "energy": 0.1,
                })
                silence_start = None
    
    return events


def _detect_high_energy(video_path: str, duration: float) -> List[Dict[str, Any]]:
    """Detect high energy periods by analyzing volume peaks."""
    # Get per-second energy
    energy_data = analyze_audio_energy(video_path, sample_interval=0.5)
    
    if not energy_data:
        return []
    
    events = []
    in_high_energy = False
    high_start = 0.0
    threshold = 0.6  # Energy above 0.6 is considered "high"
    
    for sample in energy_data:
        if sample["energy"] >= threshold and not in_high_energy:
            in_high_energy = True
            high_start = sample["time"]
        elif sample["energy"] < threshold and in_high_energy:
            in_high_energy = False
            if sample["time"] - high_start >= 1.0:  # At least 1 second
                events.append({
                    "time": high_start,
                    "end_time": sample["time"],
                    "duration": sample["time"] - high_start,
                    "type": "high_energy",
                    "energy": 0.8,
                })
    
    # Handle case where high energy continues to end
    if in_high_energy and energy_data:
        last_time = energy_data[-1]["time"]
        if last_time - high_start >= 1.0:
            events.append({
                "time": high_start,
                "end_time": last_time,
                "duration": last_time - high_start,
                "type": "high_energy",
                "energy": 0.8,
            })
    
    return events


def calculate_energy_timeline(
    video_path: str,
    duration: float,
    window_size: float = 1.0,
) -> List[Dict[str, Any]]:
    """
    Calculate comprehensive energy timeline for the entire video.
    
    Returns per-second analysis:
    - time: timestamp
    - energy: normalized 0-1
    - is_speech: likely speech (mid energy, consistent)
    - is_music: likely music (consistent high energy)
    - is_silence: low energy period
    - excitement_score: based on energy variance
    """
    energy_data = analyze_audio_energy(video_path, sample_interval=window_size)
    
    if not energy_data:
        # Fallback: generate basic timeline
        timeline = []
        t = 0.0
        while t < duration:
            timeline.append({
                "time": t,
                "energy": 0.5,
                "is_speech": True,
                "is_music": False,
                "is_silence": False,
                "excitement_score": 0.5,
            })
            t += window_size
        return timeline
    
    # Enhance with classification
    timeline = []
    window = 5  # Look at 5 samples for variance calculation
    
    for i, sample in enumerate(energy_data):
        # Calculate local variance for excitement detection
        start_idx = max(0, i - window // 2)
        end_idx = min(len(energy_data), i + window // 2 + 1)
        local_energies = [energy_data[j]["energy"] for j in range(start_idx, end_idx)]
        
        if local_energies:
            mean_energy = sum(local_energies) / len(local_energies)
            variance = sum((e - mean_energy) ** 2 for e in local_energies) / len(local_energies)
        else:
            mean_energy = sample["energy"]
            variance = 0
        
        # Classify audio type
        energy = sample["energy"]
        is_silence = energy < 0.2
        is_speech = 0.3 <= energy <= 0.7 and variance < 0.05
        is_music = energy > 0.5 and variance < 0.02  # Consistent high energy
        
        # Excitement score: high energy + high variance = excitement
        excitement = min(1.0, energy * 0.6 + (variance ** 0.5) * 4)
        
        timeline.append({
            "time": sample["time"],
            "energy": energy,
            "is_speech": is_speech,
            "is_music": is_music,
            "is_silence": is_silence,
            "excitement_score": excitement,
            "variance": variance,
        })
    
    return timeline


def find_audio_peaks(
    timeline: List[Dict[str, Any]],
    min_duration: float = 5.0,
    top_n: int = 20,
) -> List[Dict[str, Any]]:
    """
    Find peak engagement moments based on audio analysis.
    
    Returns top N peaks with:
    - start_time, end_time
    - peak_score
    - reason (why this is a peak)
    """
    if not timeline:
        return []
    
    # Score each second
    scored = []
    for sample in timeline:
        score = (
            sample["energy"] * 0.4 +
            sample["excitement_score"] * 0.4 +
            (0.2 if sample["is_speech"] else 0)
        )
        scored.append({
            "time": sample["time"],
            "score": score,
            **sample,
        })
    
    # Find peaks (local maxima sustained for min_duration)
    peaks = []
    i = 0
    while i < len(scored):
        if scored[i]["score"] >= 0.5:  # Threshold for peak
            start_idx = i
            peak_score = scored[i]["score"]
            
            # Extend while score stays high
            while i < len(scored) and scored[i]["score"] >= 0.4:
                peak_score = max(peak_score, scored[i]["score"])
                i += 1
            
            end_idx = i
            duration = scored[end_idx - 1]["time"] - scored[start_idx]["time"]
            
            if duration >= min_duration:
                # Determine reason for peak
                avg_energy = sum(s["energy"] for s in scored[start_idx:end_idx]) / (end_idx - start_idx)
                avg_excitement = sum(s["excitement_score"] for s in scored[start_idx:end_idx]) / (end_idx - start_idx)
                
                if avg_excitement > 0.6:
                    reason = "high_excitement"
                elif avg_energy > 0.6:
                    reason = "high_energy"
                else:
                    reason = "engaging_speech"
                
                peaks.append({
                    "start_time": scored[start_idx]["time"],
                    "end_time": scored[end_idx - 1]["time"],
                    "duration": duration,
                    "peak_score": peak_score,
                    "avg_score": sum(s["score"] for s in scored[start_idx:end_idx]) / (end_idx - start_idx),
                    "reason": reason,
                    "avg_energy": avg_energy,
                    "avg_excitement": avg_excitement,
                })
        else:
            i += 1
    
    # Sort by score and return top N
    peaks.sort(key=lambda x: x["peak_score"], reverse=True)
    return peaks[:top_n]
