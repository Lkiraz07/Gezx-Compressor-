hereimport asyncio
import json
from dataclasses import dataclass, field


@dataclass
class VideoStream:
    index: int
    codec: str = ""
    width: int = 0
    height: int = 0
    fps: float = 0.0
    bitrate: int = 0
    language: str = ""
    title: str = ""


@dataclass
class AudioStream:
    index: int
    codec: str = ""
    bitrate: int = 0
    channels: int = 0
    sample_rate: int = 0
    language: str = ""
    title: str = ""


@dataclass
class SubtitleStream:
    index: int
    codec: str = ""
    language: str = ""
    title: str = ""


@dataclass
class MediaInfo:
    duration: float = 0.0
    bitrate: int = 0
    format_name: str = ""
    videos: list[VideoStream] = field(default_factory=list)
    audios: list[AudioStream] = field(default_factory=list)
    subtitles: list[SubtitleStream] = field(default_factory=list)


def parse_int(value) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def parse_fps(value: str) -> float:
    if not value:
        return 0.0
    try:
        if "/" in value:
            numerator, denominator = value.split("/", 1)
            denominator = float(denominator)
            if denominator == 0:
                return 0.0
            return float(numerator) / denominator
        return float(value)
    except (TypeError, ValueError):
        return 0.0


async def run_ffprobe(input_file: str) -> dict:
    command = [
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", input_file,
    ]
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        error = stderr.decode(errors="replace").strip()
        raise RuntimeError("FFprobe failed: " + (error or "unknown error"))
    try:
        return json.loads(stdout.decode(errors="replace"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("FFprobe returned invalid JSON.") from exc


async def analyze_media(input_file: str) -> MediaInfo:
    data = await run_ffprobe(input_file)
    fmt = data.get("format", {}) or {}
    media = MediaInfo(
        duration=float(fmt.get("duration", 0) or 0),
        bitrate=parse_int(fmt.get("bit_rate", 0)),
        format_name=fmt.get("format_name", "") or "",
    )

    for stream in data.get("streams", []):
        codec_type = stream.get("codec_type", "")
        tags = stream.get("tags", {}) or {}
        language = tags.get("language", "") or ""
        title = tags.get("title", "") or ""
        index = parse_int(stream.get("index", 0))
        codec = (stream.get("codec_name", "") or "").lower()

        if codec_type == "video":
            fps = parse_fps(stream.get("avg_frame_rate", ""))
            if fps <= 0:
                fps = parse_fps(stream.get("r_frame_rate", ""))
            media.videos.append(VideoStream(
                index=index,
                codec=codec,
                width=parse_int(stream.get("width", 0)),
                height=parse_int(stream.get("height", 0)),
                fps=fps,
                bitrate=parse_int(stream.get("bit_rate", 0)),
                language=language,
                title=title,
            ))
        elif codec_type == "audio":
            media.audios.append(AudioStream(
                index=index,
                codec=codec,
                bitrate=parse_int(stream.get("bit_rate", 0)),
                channels=parse_int(stream.get("channels", 0)),
                sample_rate=parse_int(stream.get("sample_rate", 0)),
                language=language,
                title=title,
            ))
        elif codec_type == "subtitle":
            media.subtitles.append(SubtitleStream(
                index=index,
                codec=codec,
                language=language,
                title=title,
            ))

    if not media.videos:
        raise RuntimeError("No video stream was found.")
    return media


def choose_video_stream(media: MediaInfo) -> VideoStream:
    if not media.videos:
        raise RuntimeError("No video stream available.")
    return max(media.videos, key=lambda s: (s.width * s.height, s.bitrate))


def media_summary(media: MediaInfo) -> str:
    video = choose_video_stream(media)
    lines = [
        f"Video: {video.width}x{video.height}",
        f"FPS: {video.fps:.2f}" if video.fps > 0 else "FPS: --",
        f"Video codec: {video.codec or '--'}",
        f"Video streams: {len(media.videos)}",
        f"Audio tracks: {len(media.audios)}",
        f"Subtitle tracks: {len(media.subtitles)}",
        f"Container: {media.format_name or '--'}",
    ]
    return "\n".join(lines)
