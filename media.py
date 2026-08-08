import asyncio
import json
from dataclasses import dataclass
from typing import Optional


@dataclass
class VideoStream:
    index: int
    codec: str
    width: int
    height: int
    fps: float
    bitrate: Optional[int]
    duration: float
    pixel_format: Optional[str]


@dataclass
class AudioStream:
    index: int
    codec: str
    language: Optional[str]
    title: Optional[str]
    channels: int
    sample_rate: int
    bitrate: Optional[int]


@dataclass
class SubtitleStream:
    index: int
    codec: str
    language: Optional[str]
    title: Optional[str]


@dataclass
class MediaInfo:
    filename: str
    format_name: str
    duration: float
    size: int
    bitrate: Optional[int]

    videos: list[VideoStream]
    audios: list[AudioStream]
    subtitles: list[SubtitleStream]

    has_multiple_audio: bool
    has_subtitles: bool


async def _run_ffprobe(
    input_file: str,
) -> dict:

    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_streams",
        "-show_format",
        "-of",
        "json",
        input_file,
    ]

    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        error = stderr.decode(
            errors="replace"
        )

        raise RuntimeError(
            f"FFprobe failed: {error}"
        )

    try:
        return json.loads(
            stdout.decode(
                errors="replace"
            )
        )
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "FFprobe returned invalid data."
        ) from exc


def _safe_int(
    value,
    default=0,
) -> int:

    try:
        return int(value)
    except (
        TypeError,
        ValueError,
    ):
        return default


def _safe_float(
    value,
    default=0.0,
) -> float:

    try:
        return float(value)
    except (
        TypeError,
        ValueError,
    ):
        return default


def _parse_fraction(
    value: Optional[str],
) -> float:

    if not value:
        return 0.0

    try:
        if "/" in value:
            numerator, denominator = value.split(
                "/",
                1,
            )

            numerator = float(numerator)
            denominator = float(denominator)

            if denominator == 0:
                return 0.0

            return numerator / denominator

        return float(value)

    except (
        TypeError,
        ValueError,
        ZeroDivisionError,
    ):
        return 0.0


def _stream_bitrate(
    stream: dict,
) -> Optional[int]:

    value = stream.get(
        "bit_rate"
    )

    if value:
        try:
            return int(value)
        except ValueError:
            pass

    return None


def _language(
    stream: dict,
) -> Optional[str]:

    tags = stream.get(
        "tags",
        {},
    )

    return tags.get(
        "language"
    )


def _title(
    stream: dict,
) -> Optional[str]:

    tags = stream.get(
        "tags",
        {},
    )

    return tags.get(
        "title"
    )


async def analyze_media(
    input_file: str,
) -> MediaInfo:

    data = await _run_ffprobe(
        input_file
    )

    format_data = data.get(
        "format",
        {},
    )

    streams = data.get(
        "streams",
        [],
    )

    videos = []
    audios = []
    subtitles = []

    for stream in streams:

        codec_type = stream.get(
            "codec_type"
        )

        if codec_type == "video":

            videos.append(
                VideoStream(
                    index=_safe_int(
                        stream.get("index")
                    ),
                    codec=stream.get(
                        "codec_name",
                        "unknown",
                    ),
                    width=_safe_int(
                        stream.get("width")
                    ),
                    height=_safe_int(
                        stream.get("height")
                    ),
                    fps=_parse_fraction(
                        stream.get(
                            "avg_frame_rate"
                        )
                    ),
                    bitrate=_stream_bitrate(
                        stream
                    ),
                    duration=_safe_float(
                        stream.get(
                            "duration"
                        )
                    ),
                    pixel_format=stream.get(
                        "pix_fmt"
                    ),
                )
            )

        elif codec_type == "audio":

            audios.append(
                AudioStream(
                    index=_safe_int(
                        stream.get("index")
                    ),
                    codec=stream.get(
                        "codec_name",
                        "unknown",
                    ),
                    language=_language(
                        stream
                    ),
                    title=_title(
                        stream
                    ),
                    channels=_safe_int(
                        stream.get(
                            "channels"
                        )
                    ),
                    sample_rate=_safe_int(
                        stream.get(
                            "sample_rate"
                        )
                    ),
                    bitrate=_stream_bitrate(
                        stream
                    ),
                )
            )

        elif codec_type == "subtitle":

            subtitles.append(
                SubtitleStream(
                    index=_safe_int(
                        stream.get("index")
                    ),
                    codec=stream.get(
                        "codec_name",
                        "unknown",
                    ),
                    language=_language(
                        stream
                    ),
                    title=_title(
                        stream
                    ),
                )
            )

    if not videos:

        raise RuntimeError(
            "The file does not contain a video stream."
        )

    duration = _safe_float(
        format_data.get(
            "duration"
        )
    )

    size = _safe_int(
        format_data.get(
            "size"
        )
    )

    bitrate = None

    if format_data.get("bit_rate"):

        bitrate = _safe_int(
            format_data.get(
                "bit_rate"
            )
        )

    filename = input_file.rsplit(
        "/",
        1,
    )[-1]

    return MediaInfo(
        filename=filename,
        format_name=format_data.get(
            "format_name",
            "unknown",
        ),
        duration=duration,
        size=size,
        bitrate=bitrate,
        videos=videos,
        audios=audios,
        subtitles=subtitles,
        has_multiple_audio=len(audios) > 1,
        has_subtitles=bool(subtitles),
    )


def choose_video_stream(
    media: MediaInfo,
) -> VideoStream:

    # First video stream is the main video.
    return media.videos[0]


def resolution_label(
    width: int,
    height: int,
) -> str:

    if height >= 2160:
        return "4K"

    if height >= 1440:
        return "1440p"

    if height >= 1080:
        return "1080p"

    if height >= 720:
        return "720p"

    if height >= 480:
        return "480p"

    return f"{height}p"


def media_summary(
    media: MediaInfo,
) -> str:

    video = choose_video_stream(
        media
    )

    lines = [
        f"Format: {media.format_name}",
        (
            f"Video: {video.width}x"
            f"{video.height} "
            f"({resolution_label(video.width, video.height)})"
        ),
        f"Codec: {video.codec}",
        f"FPS: {video.fps:.2f}",
        f"Audio tracks: {len(media.audios)}",
        f"Subtitles: {len(media.subtitles)}",
    ]

    if media.duration:
        lines.append(
            f"Duration: {media.duration:.1f}s"
        )

    return "\n".join(lines)
