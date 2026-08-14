hereimport time
import math
from pathlib import Path

def human_bytes(size: float) -> str:
    """Convert bytes into human-readable representation."""
    if not size or size < 0:
        return "0 B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(size, 1024))) if size > 0 else 0
    p = math.pow(1024, i)
    s = round(size / p, 2)
    return f"{s} {size_name[i]}"

def human_time(seconds: float) -> str:
    """Format seconds into HH:MM:SS or MM:SS strings."""
    if not seconds or seconds < 0 or math.isinf(seconds) or math.isnan(seconds):
        return "00:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def generate_progress_bar(percentage: float, length: int = 10) -> str:
    """Generate an ASCII visual progress bar."""
    filled_length = int(round(length * percentage / 100))
    bar = '■' * filled_length + '□' * (length - filled_length)
    return bar

def cleanup_files(*file_paths: Path):
    """Safely delete arbitrary files or paths if they exist."""
    for path in file_paths:
        if path and isinstance(path, Path):
            try:
                if path.is_file() or path.is_symlink():
                    path.unlink(missing_ok=True)
            except Exception as e:
                print(f"Failed to cleanup file {path}: {e}")
