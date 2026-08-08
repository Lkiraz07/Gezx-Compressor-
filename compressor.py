import asyncio
import os
import re
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

from media import MediaInfo, choose_video_stream


@dataclass
class CompressionResult:
    output_file: str
    original_size: int
    output_size: int
    crf: int
    duration: float


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(value, maximum))


def calculate_crf(media: MediaInfo) -> int:
    video = choose_video_stream(media)
    height = video.height
    fps = video.fps or 30.0
    source_bitrate = video.bitrate or media.bitrate or 0

    if height >= 2160:
        crf = 27
    elif height >= 1440:
        crf = 26
    elif height >= 1080:
        crf = 24
    elif height >= 720:
        crf = 23
    elif height >= 480:
        crf = 23
    else:
        crf = 22

    if source_bitrate >= 20_000_000:
        crf += 2
    elif source_bitrate >= 12_000_000:
        crf += 1

    if 0 < source_bitrate <= 900_000:
        crf -= 2
    elif 0 < source_bitrate <= 1_500_000:
        crf -= 1

    if fps >= 60:
        crf -= 1

    return clamp(crf, 20, 30)


def parse_ffmpeg_time(text: str) -> float:
    match = re.search(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if not match:
        return 0.0
    return int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3))


def build_ffmpeg_command(input_file: str, output_file: str, media: MediaInfo, crf: int) -> list[str]:
    mp4_output = output_file.lower().endswith(".mp4")
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostats",
        "-progress", "pipe:2", "-y", "-i", input_file,
    ]

    # Main video is re-encoded. Additional video streams are copied.
    for out_idx, _video in enumerate(media.videos):
        command += ["-map", f"0:v:{out_idx}"]
        if out_idx == 0:
            command += [
                f"-c:v:{out_idx}", "libx264",
                f"-preset:v:{out_idx}", "veryfast",
                f"-crf:v:{out_idx}", str(crf),
                f"-pix_fmt:v:{out_idx}", "yuv420p",
            ]
        else:
            command += [f"-c:v:{out_idx}", "copy"]

    command += ["-map", "0:a?", "-c:a", "copy"]
    command += ["-map", "0:s?", "-c:s", "copy"]
    command += ["-map_metadata", "0", "-map_chapters", "0"]

    if mp4_output:
        command += ["-movflags", "+faststart"]

    command.append(output_file)
    return command


async def compress_video(
    input_file: str,
    output_file: str,
    media: MediaInfo,
    progress_callback: Optional[Callable[[dict], Awaitable[None]]] = None,
    cancel_callback: Optional[Callable[[], Awaitable[bool]]] = None,
) -> CompressionResult:
    crf = calculate_crf(media)
    command = build_ffmpeg_command(input_file, output_file, media, crf)
    print("Running FFmpeg:", " ".join(command))

    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )

    duration = media.duration

    try:
        while True:
            if cancel_callback:
                try:
                    if await cancel_callback():
                        raise asyncio.CancelledError
                except asyncio.CancelledError:
                    raise
                except Exception:
                    pass

            line = await process.stderr.readline()
            if not line:
                break

            text = line.decode(errors="replace").strip()
            if not text:
                continue

            # FFmpeg -progress outputs key=value pairs.
            if text.startswith("out_time="):
                encoded_seconds = parse_ffmpeg_time("time=" + text.split("=", 1)[1])
                if progress_callback:
                    await progress_callback({
                        "percent": (encoded_seconds / duration * 100) if duration > 0 else 0.0,
                        "encoded_seconds": encoded_seconds,
                        "duration": duration,
                        "crf": crf,
                    })

            elif text == "progress=end" and progress_callback:
                await progress_callback({
                    "percent": 100.0,
                    "encoded_seconds": duration,
                    "duration": duration,
                    "crf": crf,
                })

        return_code = await process.wait()
        if return_code != 0:
            raise RuntimeError(f"FFmpeg exited with code {return_code}.")

        if not os.path.isfile(output_file):
            raise RuntimeError("FFmpeg finished but no output file was created.")

        original_size = os.path.getsize(input_file)
        output_size = os.path.getsize(output_file)
        return CompressionResult(output_file, original_size, output_size, crf, duration)

    except asyncio.CancelledError:
        if process.returncode is None:
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=5)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
        if os.path.exists(output_file):
            try:
                os.remove(output_file)
            except OSError:
                pass
        raise
    except Exception:
        if process.returncode is None:
            try:
                process.terminate()
            except ProcessLookupError:
                pass
        if os.path.exists(output_file):
            try:
                os.remove(output_file)
            except OSError:
                pass
        raise￼Enter asyncio
import os
import re
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

from media import MediaInfo, choose_video_stream


@dataclass
class CompressionResult:
    output_file: str
    original_size: int
    output_size: int
    crf: int
    duration: float


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(value, maximum))


def calculate_crf(media: MediaInfo) -> int:
    video = choose_video_stream(media)
    height = video.height
    fps = video.fps or 30.0
    source_bitrate = video.bitrate or media.bitrate or 0

    if height >= 2160:
        crf = 27
    elif height >= 1440:
        crf = 26
    elif height >= 1080:
        crf = 24
    elif height >= 720:
        crf = 23
    elif height >= 480:
        crf = 23
    else:
        crf = 22

    if source_bitrate >= 20_000_000:
        crf += 2
    elif source_bitrate >= 12_000_000:
        crf += 1

    if 0 < source_bitrate <= 900_000:
        crf -= 2
    elif 0 < source_bitrate <= 1_500_000:
        crf -= 1

    if fps >= 60:
        crf -= 1

    return clamp(crf, 20, 30)


def parse_ffmpeg_time(text: str) -> float:
    match = re.search(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if not match:
        return 0.0
    return int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3))


def build_ffmpeg_command(input_file: str, output_file: str, media: MediaInfo, crf: int) -> list[str]:
    mp4_output = output_file.lower().endswith(".mp4")
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostats",
        "-progress", "pipe:2", "-y", "-i", input_file,
    ]

    # Main video is re-encoded. Additional video streams are copied.
    for out_idx, _video in enumerate(media.videos):
        command += ["-map", f"0:v:{out_idx}"]
        if out_idx == 0:
            command += [
                f"-c:v:{out_idx}", "libx264",
                f"-preset:v:{out_idx}", "veryfast",
