import os
import re
from pathlib import Path
from typing import Optional

from media import MediaInfo


VIDEO_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".mov",
    ".avi",
    ".webm",
    ".m4v",
    ".ts",
    ".mts",
    ".m2ts",
}


def human_size(size: int) -> str:

    if size < 1024:
        return f"{size} B"

    if size < 1024 ** 2:
        return f"{size / 1024:.2f} KB"

    if size < 1024 ** 3:
        return f"{size / 1024 ** 2:.2f} MB"

    return f"{size / 1024 ** 3:.2f} GB"


def safe_filename(
    filename: str,
) -> str:

    filename = os.path.basename(
        filename
    )

    filename = re.sub(
        r"[^\w.\- ()\[\]]+",
        "_",
        filename,
    )

    filename = filename.strip(
        " ."
    )

    if not filename:
        filename = "video"

    return filename


def get_extension(
    filename: str,
) -> str:

    return Path(
        filename
    ).suffix.lower()


def choose_output_extension(
    media: MediaInfo,
) -> str:

    # MP4 can safely contain common text
    # subtitle formats such as mov_text.
    #
    # But many subtitle streams (ASS/SSA,
    # PGS, VobSub, etc.) should remain in MKV.
    #
    # If ANY subtitle stream isn't suitable
    # for MP4, use MKV.

    incompatible_subtitles = {
        "ass",
        "ssa",
        "hdmv_pgs_subtitle",
        "pgssub",
        "dvd_subtitle",
        "vobsub",
        "dvb_subtitle",
        "xsub",
    }

    for subtitle in media.subtitles:

        codec = (
            subtitle.codec or ""
        ).lower()

        if codec in incompatible_subtitles:
            return ".mkv"

    # Multiple audio tracks are supported by MP4,
    # so they don't automatically require MKV.

    return ".mp4"


def build_output_path(
    input_file: str,
    media: MediaInfo,
) -> str:

    source = Path(
        input_file
    )

    extension = choose_output_extension(
        media
    )

    return str(
        source.with_name(
            f"{source.stem}_compressed{extension}"
        )
    )


def format_duration(
    seconds: float,
) -> str:

    seconds = int(
        max(0, seconds)
    )

    hours = seconds // 3600

    minutes = (
        seconds % 3600
    ) // 60

    secs = seconds % 60

    if hours:
        return (
            f"{hours:02d}:"
            f"{minutes:02d}:"
            f"{secs:02d}"
        )

    return (
        f"{minutes:02d}:"
        f"{secs:02d}"
    )


def calculate_percentage(
    current: float,
    total: float,
) -> float:

    if total <= 0:
        return 0.0

    return max(
        0.0,
        min(
            100.0,
            current / total * 100,
        ),
    )


def make_progress_bar(
    percentage: float,
    width: int = 12,
) -> str:

    percentage = max(
        0,
        min(
            100,
            percentage,
        ),
    )

    filled = int(
        width * percentage / 100
    )

    return (
        "█" * filled
        + "░" * (width - filled)
    )


def safe_remove(
    path: Optional[str],
) -> None:

    if not path:
        return

    try:

        if os.path.isfile(path):
            os.remove(path)

    except OSError:
        pass
