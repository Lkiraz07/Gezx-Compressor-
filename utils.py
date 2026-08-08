hereimport os
import re
from pathlib import Path
from typing import Optional

from media import MediaInfo

# Conservative MP4 compatibility list because streams are COPIED, not re-encoded.
MP4_AUDIO_CODECS = {"aac", "mp3", "ac3", "eac3", "alac"}
# For exact subtitle copying, SubRip cannot simply be copied into MP4 as mov_text.
# Therefore MP4 is selected only when subtitles are already mov_text.
MP4_SUBTITLE_CODECS = {"mov_text"}


def human_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 ** 2:
        return f"{size / 1024:.2f} KB"
    if size < 1024 ** 3:
        return f"{size / 1024 ** 2:.2f} MB"
    return f"{size / 1024 ** 3:.2f} GB"


def safe_filename(filename: str) -> str:
    filename = os.path.basename(filename or "video")
    filename = re.sub(r"[^\w.\- ()\[\]]+", "_", filename)
    filename = filename.strip(" .")
    return filename or "video"


def mp4_can_contain_audio(media: MediaInfo) -> bool:
    return all((a.codec or "").lower() in MP4_AUDIO_CODECS for a in media.audios)


def mp4_can_contain_subtitles(media: MediaInfo) -> bool:
    return all((s.codec or "").lower() in MP4_SUBTITLE_CODECS for s in media.subtitles)


def choose_output_extension(media: MediaInfo) -> str:
    # Multiple video streams are kept safely in MKV.
    if len(media.videos) > 1:
        return ".mkv"
    if not mp4_can_contain_audio(media):
        return ".mkv"
    if not mp4_can_contain_subtitles(media):
        return ".mkv"
    return ".mp4"


def build_output_path(input_file: str, media: MediaInfo) -> str:
    source = Path(input_file)
    return str(source.with_name(f"{source.stem}_compressed{choose_output_extension(media)}"))


def make_progress_bar(percentage: float, width: int = 12) -> str:
    percentage = max(0.0, min(100.0, percentage))
    filled = int(width * percentage / 100)
    return "â– " * filled + "â–¡" * (width - filled)


def safe_remove(path: Optional[str]) -> None:
    if not path:
        return
    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass
