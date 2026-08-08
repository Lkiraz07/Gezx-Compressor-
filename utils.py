import os
import re
from pathlib import Path
from typing import Optional

from media import MediaInfo


MP4_AUDIO_CODECS = {
    "aac",
    "mp3",
    "ac3",
    "eac3",
    "alac",
}

MP4_SUBTITLE_CODECS = {
    "mov_text",
    "subrip",
    "srt",
}


def human_size(size: int) -> str:

    if size < 1024:
        return f"{size} B"

    if size < 1024 ** 2:
        return f"{size / 1024:.2f} KB"

    if size < 1024 ** 3:
        return f"{size / 1024 ** 2:.2f} MB"

    return f"{size / 1024 ** 3:.2f} GB"


def safe_filename(filename: str) -> str:

    filename = os.path.basename(filename)

    filename = re.sub(
        r"[^\w.\- ()\[\]]+",
        "_",
        filename,
    )

    filename = filename.strip(" .")

    if not filename:
        filename = "video"

    return filename


def get_extension(filename: str) -> str:

    return Path(filename).suffix.lower()


def mp4_can_contain_audio(
    media: MediaInfo,
) -> bool:
    """
    Check whether every audio stream is suitable
    for our MP4 output.

    We COPY audio instead of re-encoding it.
    """

    for audio in media.audios:

        codec = (
            audio.codec or ""
        ).lower()

        if codec not in MP4_AUDIO_CODECS:
            return False

    return True


def mp4_can_contain_subtitles(
    media: MediaInfo,
) -> bool:
    """
    Because subtitles are copied exactly, only subtitle
    codecs that MP4 can safely carry should result in MP4.
    """

    for subtitle in media.subtitles:

        codec = (
            subtitle.codec or ""
        ).lower()

        if codec not in MP4_SUBTITLE_CODECS:
            return False

    return True


def choose_output_extension(
    media: MediaInfo,
) -> str:
    """
    Automatically select the safest container.

    MP4:
        Only when the copied audio/subtitle streams
        are compatible.

    MKV:
        Used when preserving the original streams
        requires a more flexible container.
    """

    if not mp4_can_contain_audio(media):
        return ".mkv"

    if not mp4_can_contain_subtitles(media):
        return ".mkv"

    return ".mp4"


def build_output_path(
    input_file: str,
    media: MediaInfo,
) -> str:

    source = Path(input_file)

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

    seconds %= 60

    if hours:

        return (
            f"{hours:02d}:"
            f"{minutes:02d}:"
            f"{seconds:02d}"
        )

    return (
        f"{minutes:02d}:"
        f"{seconds:02d}"
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
        "■" * filled
        + "□" * (width - filled)
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
