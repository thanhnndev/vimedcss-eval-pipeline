import os
import logging
from typing import Optional

logger = logging.getLogger("asr.audio_utils")


def verify_audio_file(
    path: str,
    expected_extensions: list[str],
    min_duration: float,
    max_duration: float,
) -> bool:
    """Verify an audio file exists, has an allowed extension, and basic duration constraints.

    Falls back to extension-only check if neither mutagen nor soundfile is available.
    """
    if not os.path.exists(path):
        logger.warning(f"Audio file not found: {path}")
        return False

    ext = os.path.splitext(path)[1].lower()
    if ext not in [e.lower() for e in expected_extensions]:
        logger.warning(f"Unexpected audio extension {ext} for {path}")
        return False

    duration = _get_duration(path)
    if duration is None:
        logger.warning(f"Could not determine duration for {path}; accepting based on extension only")
        return True

    if duration < min_duration:
        logger.warning(f"Audio too short ({duration}s < {min_duration}s): {path}")
        return False
    if duration > max_duration:
        logger.warning(f"Audio too long ({duration}s > {max_duration}s): {path}")
        return False

    return True


def resolve_audio_path(metadata_row, local_raw_dir: str) -> str:
    """Resolve the audio file path from a metadata row.

    Priority:
    1. Absolute or relative path from metadata
    2. Path relative to local_raw_dir using filename from metadata
    3. Recurse search under local_raw_dir for a matching basename
    """
    raw_path = metadata_row.get("audio") if isinstance(metadata_row, dict) else getattr(metadata_row, "audio", None)
    if not raw_path:
        return ""

    if os.path.isabs(raw_path) and os.path.exists(raw_path):
        return raw_path

    candidate = os.path.join(local_raw_dir, raw_path)
    if os.path.exists(candidate):
        return candidate

    basename = os.path.basename(raw_path)
    for root, _, files in os.walk(local_raw_dir):
        if basename in files:
            return os.path.join(root, basename)

    return candidate


def _get_duration(path: str) -> Optional[float]:
    """Return audio duration in seconds if a backend is available, else None."""
    try:
        import soundfile as sf  # type: ignore
        with sf.SoundFile(path) as f:
            return len(f) / f.samplerate
    except Exception:
        pass

    try:
        from mutagen import File as MutagenFile  # type: ignore
        info = MutagenFile(path)
        if info is not None and getattr(info, "info", None) is not None:
            return float(info.info.length)
    except Exception:
        pass

    return None
