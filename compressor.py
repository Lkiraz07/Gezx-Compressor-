import asyncio
import os
import re
from typing import Callable, Optional

from media import MediaInfo, choose_video_stream


class CompressionResult:
    def __init__(
        self,
        output_file: str,
        original_size: int,
        output_size: int,
        video_bitrate: int,
        audio_bitrate: int,
        crf: int,
    ):
        self.output_file = output_file
        self.original_size = original_size
        self.output_size = output_size
        self.video_bitrate = video_bitrate
        self.audio_bitrate = audio_bitrate
        self.crf = crf


def clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:

    return max(
        minimum,
        min(value, maximum),
    )


def calculate_audio_bitrate(
    media: MediaInfo,
) -> int:

    count = len(media.audios)

    if count == 0:
        return 0

    # Keep multiple tracks, but don't allow
    # audio to consume the entire output.
    if count == 1:
        return 128

    if count == 2:
        return 96

    if count <= 4:
        return 80

    return 64


def calculate_compression_profile(
    media: MediaInfo,
):
    """
    Automatically chooses a sensible compression
    profile based on the source media.

    There is intentionally NO fixed output size.
    """

    video = choose_video_stream(media)

    width = video.width
    height = video.height
    fps = video.fps or 30.0

    source_bitrate = (
        video.bitrate
        or media.bitrate
        or 0
    )

    # Base CRF.
    crf = 24

    # Very high resolution:
    # allow stronger compression.
    if height >= 2160:
        crf = 27

    elif height >= 1440:
        crf = 26

    elif height >= 1080:
        crf = 24

    elif height >= 720:
        crf = 23

    else:
        crf = 22

    # Extremely high source bitrate means
    # there is usually more room to reduce size.
    if source_bitrate:

        if source_bitrate > 20_000_000:
            crf += 2

        elif source_bitrate > 12_000_000:
            crf += 1

    # Very low source bitrate:
    # don't compress too aggressively.
    if source_bitrate:

        if source_bitrate < 1_000_000:
            crf -= 2

        elif source_bitrate < 2_000_000:
            crf -= 1

    # High FPS needs more bitrate.
    if fps >= 60:
        crf -= 1

    # Clamp CRF to a reasonable range.
    crf = int(
        clamp(
            crf,
            20,
            30,
        )
    )

    # Audio bitrate.
    audio_bitrate = calculate_audio_bitrate(
        media
    )

    return {
        "crf": crf,
        "audio_bitrate": audio_bitrate,
    }


def parse_ffmpeg_time(
    value: str,
) -> float:

    match = re.search(
        r"time=(\d+):(\d+):(\d+(?:\.\d+)?)",
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
    media: MediaInfo,
    progress_callback: Optional[
        Callable
    ] = None,
    cancel_callback: Optional[
        Callable
    ] = None,
) -> CompressionResult:

    profile = calculate_compression_profile(
        media
    )

    crf = profile["crf"]

    audio_bitrate = profile[
        "audio_bitrate"
    ]

    video = choose_video_stream(
        media
    )

    # -----------------------------------------
    # Build FFmpeg command
    # -----------------------------------------

    command = [
        "ffmpeg",

        "-hide_banner",

        "-y",

        "-i",
        input_file,

        # Main video stream.
        "-map",
        "0:v:0",
    ]

    # -----------------------------------------
    # Audio
    # -----------------------------------------

    if media.audios:

        command += [
            "-map",
            "0:a?",
        ]

    # -----------------------------------------
    # Subtitles
    # -----------------------------------------

    if media.subtitles:

        command += [
            "-map",
            "0:s?",
        ]

    # -----------------------------------------
    # Video encoder
    # -----------------------------------------

    command += [
        "-c:v",
        "libx264",

        "-preset",
        "veryfast",

        "-crf",
        str(crf),

        # Good compatibility.
        "-pix_fmt",
        "yuv420p",

        # Prevent unnecessarily huge
        # bitrate spikes.
        "-maxrate",
        "12000k",

        "-bufsize",
        "24000k",
    ]

    # -----------------------------------------
    # Audio encoder
    # -----------------------------------------

    if media.audios:

        command += [
            "-c:a",
            "aac",

            "-b:a",
            f"{audio_bitrate}k",

            "-ac",
            "2",
        ]

    # -----------------------------------------
    # Subtitles
    # -----------------------------------------

    if media.subtitles:

        command += [
            "-c:s",
            "copy",
        ]

    # -----------------------------------------
    # Metadata + chapters
    # -----------------------------------------

    command += [
        "-map_metadata",
        "0",

        "-map_chapters",
        "0",
    ]

    # -----------------------------------------
    # MP4 optimization
    # -----------------------------------------

    command += [
        "-movflags",
        "+faststart",
    ]

    # -----------------------------------------
    # Output
    # -----------------------------------------

    command += [
        output_file,
    ]

    process = await asyncio.create_subprocess_exec(
        *command,

        stdout=asyncio.subprocess.DEVNULL,

        stderr=asyncio.subprocess.PIPE,
    )

    duration = media.duration

    last_percent = -1

    # -----------------------------------------
    # Read FFmpeg progress
    # -----------------------------------------

    while True:

        if cancel_callback:

            cancelled = cancel_callback()

            if cancelled:

                try:
                    process.terminate()

                except ProcessLookupError:
                    pass

                await process.wait()

                if os.path.exists(
                    output_file
                ):
                    os.remove(
                        output_file
                    )

                raise asyncio.CancelledError

        line = await process.stderr.readline()

        if not line:
            break

        text = line.decode(
            errors="replace"
        ).strip()

        if "time=" not in text:
            continue

        encoded_time = parse_ffmpeg_time(
            text
        )

        if duration > 0:

            percent = (
                encoded_time
                / duration
                * 100
            )

            percent = min(
                100,
                max(0, percent),
            )

        else:
            percent = 0

        if (
            progress_callback
            and int(percent)
            != last_percent
        ):

            last_percent = int(
                percent
            )

            await progress_callback(
                {
                    "percent": percent,

                    "encoded_seconds":
                        encoded_time,

                    "duration":
                        duration,

                    "crf":
                        crf,

                    "audio_bitrate":
                        audio_bitrate,
                }
            )

    return_code = await process.wait()

    if return_code != 0:

        if os.path.exists(
            output_file
        ):
            os.remove(
                output_file
            )

        raise RuntimeError(
            "FFmpeg failed while "
            "compressing the video."
        )

    if not os.path.exists(
        output_file
    ):

        raise RuntimeError(
            "FFmpeg completed but "
            "no output file was created."
        )

    original_size = os.path.getsize(
        input_file
    )

    output_size = os.path.getsize(
        output_file
    )

    return CompressionResult(
        output_file=output_file,

        original_size=original_size,

        output_size=output_size,

        video_bitrate=(
            video.bitrate or 0
        ),

        audio_bitrate=audio_bitrate,

        crf=crf,
    )
