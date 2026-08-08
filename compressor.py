import asyncio
import json
import os
import re
from typing import Callable, Optional


async def run_command(command):

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

        raise RuntimeError(error)

    return stdout.decode(
        errors="replace"
    )


async def get_media_info(input_file: str):

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

    output = await run_command(command)

    return json.loads(output)


def calculate_bitrates(
    duration: float,
    target_size_mb: int,
    audio_bitrate_kbps: int = 128,
):

    target_bits = (
        target_size_mb
        * 1024
        * 1024
        * 8
    )

    audio_bits = (
        audio_bitrate_kbps
        * 1000
        * duration
    )

    # Reserve space for container overhead.
    available_video_bits = (
        target_bits
        * 0.94
        - audio_bits
    )

    if available_video_bits <= 0:
        raise RuntimeError(
            "Target size is too small for this video's duration."
        )

    video_bitrate = (
        available_video_bits
        / duration
    )

    return max(
        int(video_bitrate / 1000),
        100,
    )


def parse_ffmpeg_time(value: str) -> float:

    match = re.search(
        r"(\d+):(\d+):(\d+(?:\.\d+)?)",
        value,
    )

    if not match:
        return 0.0

    hours = int(match.group(1))
    minutes = int(match.group(2))
    seconds = float(match.group(3))

    return (
        hours * 3600
        + minutes * 60
        + seconds
    )


async def compress_video(
    input_file: str,
    output_file: str,
    target_size_mb: int,
    progress_callback: Optional[
        Callable
    ] = None,
    cancel_callback: Optional[
        Callable
    ] = None,
):

    info = await get_media_info(
        input_file
    )

    streams = info.get(
        "streams",
        [],
    )

    format_info = info.get(
        "format",
        {},
    )

    duration = float(
        format_info.get(
            "duration",
            0,
        )
        or 0
    )

    if duration <= 0:
        raise RuntimeError(
            "Invalid or unknown video duration."
        )

    video_streams = [
        stream
        for stream in streams
        if stream.get("codec_type") == "video"
    ]

    audio_streams = [
        stream
        for stream in streams
        if stream.get("codec_type") == "audio"
    ]

    subtitle_streams = [
        stream
        for stream in streams
        if stream.get("codec_type") == "subtitle"
    ]

    if not video_streams:
        raise RuntimeError(
            "No video stream found."
        )

    # Choose an audio bitrate that gives
    # reasonable quality without consuming
    # the entire target size.
    audio_count = len(audio_streams)

    if audio_count == 0:
        audio_bitrate = 0
    elif audio_count == 1:
        audio_bitrate = 128
    elif audio_count == 2:
        audio_bitrate = 96
    else:
        audio_bitrate = 80

    total_audio_bitrate = (
        audio_bitrate * audio_count
    )

    video_bitrate = calculate_bitrates(
        duration=duration,
        target_size_mb=target_size_mb,
        audio_bitrate_kbps=total_audio_bitrate,
    )

    command = [
        "ffmpeg",
        "-hide_banner",
        "-y",

        "-i",
        input_file,

        # Map the first video stream.
        "-map",
        "0:v:0",
    ]

    # Map every audio stream.
    if audio_streams:
        command += [
            "-map",
            "0:a?",
        ]

    # Map every subtitle stream.
    if subtitle_streams:
        command += [
            "-map",
            "0:s?",
        ]

    # Video encoding.
    command += [
        "-c:v",
        "libx264",

        "-preset",
        "veryfast",

        "-b:v",
        f"{video_bitrate}k",

        "-maxrate",
        f"{int(video_bitrate * 1.15)}k",

        "-bufsize",
        f"{int(video_bitrate * 2)}k",

        "-pix_fmt",
        "yuv420p",
    ]

    # Audio.
    if audio_streams:

        command += [
            "-c:a",
            "aac",
            "-b:a",
            f"{audio_bitrate}k",
        ]

    # Subtitle handling.
    if subtitle_streams:

        command += [
            "-c:s",
            "copy",
        ]

    # Metadata.
    command += [
        "-map_metadata",
        "0",

        "-map_chapters",
        "0",

        "-movflags",
        "+faststart",

        output_file,
    ]

    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )

    last_progress = 0

    while True:

        if cancel_callback:
            cancelled = cancel_callback()

            if cancelled:

                try:
                    process.terminate()
                except ProcessLookupError:
                    pass

                await process.wait()

                if os.path.exists(output_file):
                    os.remove(output_file)

                raise asyncio.CancelledError

        line = await process.stderr.readline()

        if not line:
            break

        text = line.decode(
            errors="replace"
        ).strip()

        if "time=" in text:

            match = re.search(
                r"time=(\d+:\d+:\d+(?:\.\d+)?)",
                text,
            )

            if match:

                encoded_seconds = parse_ffmpeg_time(
                    match.group(1)
                )

                percent = min(
                    encoded_seconds
                    / duration
                    * 100,
                    100,
                )

                if (
                    progress_callback
                    and percent - last_progress >= 1
                ):

                    last_progress = percent

                    await progress_callback(
                        {
                            "percent": percent,
                            "encoded_seconds": encoded_seconds,
                            "duration": duration,
                        }
                    )

    return_code = await process.wait()

    if return_code != 0:

        if os.path.exists(output_file):
            os.remove(output_file)

        raise RuntimeError(
            "FFmpeg compression failed."
        )

    if not os.path.exists(output_file):

        raise RuntimeError(
            "FFmpeg finished without creating output."
        )

    return output_file
