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
    """
    Adaptive video-only compression.

    No fixed output-size target is used.
    """

    video = choose_video_stream(media)

    height = video.height
    fps = video.fps or 30.0

    source_bitrate = (
        video.bitrate
        or media.bitrate
        or 0
    )

    # Base CRF according to resolution.
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

    # High-bitrate sources have more room for compression.
    if source_bitrate >= 20_000_000:
        crf += 2
    elif source_bitrate >= 12_000_000:
        crf += 1

    # Don't aggressively compress already-low-bitrate sources.
    if 0 < source_bitrate <= 900_000:
        crf -= 2
    elif 0 < source_bitrate <= 1_500_000:
        crf -= 1

    # High-FPS video needs a little more quality.
    if fps >= 60:
        crf -= 1

    return clamp(crf, 20, 30)


def is_mp4(output_file: str) -> bool:
    return output_file.lower().endswith(".mp4")


def parse_ffmpeg_time(text: str) -> float:
    match = re.search(
        r"time=(\d+):(\d+):(\d+(?:\.\d+)?)",
        text,
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


def build_ffmpeg_command(
    input_file: str,
    output_file: str,
    media: MediaInfo,
    crf: int,
) -> list[str]:

    mp4_output = is_mp4(output_file)

    command = [
        "ffmpeg",

        "-hide_banner",
        "-loglevel", "warning",
        "-y",

        "-i",
        input_file,

        # ==================================================
        # VIDEO
        # ==================================================

        "-map",
        "0:v:0",

        "-c:v",
        "libx264",

        "-preset",
        "veryfast",

        "-crf",
        str(crf),

        "-pix_fmt",
        "yuv420p",

        # ==================================================
        # ALL AUDIO TRACKS
        # ==================================================

        "-map",
        "0:a?",

        "-c:a",
        "copy",

        # ==================================================
        # ALL SUBTITLE TRACKS
        # ==================================================

        "-map",
        "0:s?",

        "-c:s",
        "copy",

        # ==================================================
        # METADATA
        # ==================================================

        "-map_metadata",
        "0",

        "-map_chapters",
        "0",
    ]

    # ------------------------------------------------------
    # MP4-specific optimization
    # ------------------------------------------------------

    if mp4_output:
        command += [
            "-movflags",
            "+faststart",
        ]

    command += [
        output_file,
    ]

    return command


async def compress_video(
    input_file: str,
    output_file: str,
    media: MediaInfo,
    progress_callback: Optional[
        Callable[
            [dict],
            Awaitable[None],
        ]
    ] = None,
    cancel_callback: Optional[
        Callable[[], Awaitable[bool]]
    ] = None,
) -> CompressionResult:

    crf = calculate_crf(media)

    command = build_ffmpeg_command(
        input_file=input_file,
        output_file=output_file,
        media=media,
        crf=crf,
    )

    print(
        "Running FFmpeg:",
        " ".join(command),
    )

    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )

    duration = media.duration

    try:

        while True:

            # ==================================================
            # CANCELLATION
            # ==================================================

            if cancel_callback:

                try:
                    cancelled = (
                        await cancel_callback()
                    )
                except Exception:
                    cancelled = False

                if cancelled:

                    try:
                        process.terminate()
                    except ProcessLookupError:
                        pass

                    try:
                        await asyncio.wait_for(
                            process.wait(),
                            timeout=5,
                        )
                    except asyncio.TimeoutError:

                        try:
                            process.kill()
                        except ProcessLookupError:
                            pass

                        await process.wait()

                    raise asyncio.CancelledError

            # ==================================================
            # FFmpeg output
            # ==================================================

            line = await process.stderr.readline()

            if not line:
                break

            text = line.decode(
                errors="replace"
            ).strip()

            if "time=" not in text:
                continue

            encoded_seconds = parse_ffmpeg_time(
                text
            )

            if duration > 0:

                percent = (
                    encoded_seconds
                    / duration
                    * 100
                )

                percent = max(
                    0.0,
                    min(
                        100.0,
                        percent,
                    ),
                )

            else:
                percent = 0.0

            if progress_callback:

                await progress_callback(
                    {
                        "percent": percent,
                        "encoded_seconds": encoded_seconds,
                        "duration": duration,
                        "crf": crf,
                    }
                )

        return_code = await process.wait()

        if return_code != 0:
            raise RuntimeError(
                f"FFmpeg exited with code {return_code}."
            )

        if not os.path.isfile(output_file):
            raise RuntimeError(
                "FFmpeg finished but the output file "
                "was not created."
            )

        original_size = os.path.getsize(
            input_file
        )

        output_size = os.path.getsize(
            output_file
        )

        # Final progress update.
        if progress_callback:

            await progress_callback(
                {
                    "percent": 100.0,
                    "encoded_seconds": duration,
                    "duration": duration,
                    "crf": crf,
                }
            )

        return CompressionResult(
            output_file=output_file,
            original_size=original_size,
            output_size=output_size,
            crf=crf,
            duration=duration,
        )

    except asyncio.CancelledError:

        try:

            if process.returncode is None:
                process.terminate()

                try:
                    await asyncio.wait_for(
                        process.wait(),
                        timeout=5,
                    )
                except asyncio.TimeoutError:

                    process.kill()
                    await process.wait()

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

        raise
