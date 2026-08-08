import asyncio
import shutil
import time
from pathlib import Path

from pyrogram import Client, filters
from pyrogram.types import Message

from config import (
    API_HASH,
    API_ID,
    BOT_TOKEN,
    MAX_FILE_SIZE,
    WORK_DIR,
)

from compressor import compress_video
from media import analyze_media, media_summary
from progress import (
    ProgressTracker,
    compression_progress_callback,
)
from utils import (
    build_output_path,
    human_size,
    safe_filename,
)


# ============================================================
# Telegram Client
# ============================================================

app = Client(
    "fast_video_compressor",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)


# ============================================================
# Active jobs
# ============================================================

active_jobs = {}


def get_user_id(message: Message) -> int:

    if message.from_user:
        return message.from_user.id

    return message.chat.id


# ============================================================
# /start
# ============================================================

@app.on_message(filters.command("start"))
async def start_command(
    client: Client,
    message: Message,
):

    await message.reply_text(
        "Fast Video Compressor\n\n"
        "Send a video or video file and I will "
        "compress the video while preserving "
        "audio tracks and subtitles whenever possible.\n\n"
        "Commands:\n"
        "/cancel - cancel your current job"
    )


# ============================================================
# /cancel
# ============================================================

@app.on_message(filters.command("cancel"))
async def cancel_command(
    client: Client,
    message: Message,
):

    user_id = get_user_id(message)

    job = active_jobs.get(user_id)

    if job is None:

        await message.reply_text(
            "You don't have an active job."
        )

        return

    job["cancel"] = True

    await message.reply_text(
        "Cancellation requested."
    )


# ============================================================
# Get file size
# ============================================================

def get_file_size(
    message: Message,
) -> int:

    if message.video:

        return (
            message.video.file_size
            or 0
        )

    if message.document:

        return (
            message.document.file_size
            or 0
        )

    return 0


# ============================================================
# Get filename
# ============================================================

def get_filename(
    message: Message,
) -> str:

    if message.document:

        if message.document.file_name:

            return safe_filename(
                message.document.file_name
            )

    if message.video:

        if message.video.file_name:

            return safe_filename(
                message.video.file_name
            )

    return (
        f"video_{message.id}.mp4"
    )


# ============================================================
# Download callback
# ============================================================

async def download_progress(
    current: int,
    total: int,
    tracker: ProgressTracker,
):

    await tracker.render(
        current=current,
        total=total,
    )


# ============================================================
# Upload callback
# ============================================================

async def upload_progress(
    current: int,
    total: int,
    tracker: ProgressTracker,
):

    await tracker.render(
        current=current,
        total=total,
    )


# ============================================================
# Main handler
# ============================================================

@app.on_message(
    filters.video
    | filters.document
)
async def video_handler(
    client: Client,
    message: Message,
):

    user_id = get_user_id(message)

    # --------------------------------------------------------
    # One job per user
    # --------------------------------------------------------

    if user_id in active_jobs:

        await message.reply_text(
            "You already have a compression job running."
        )

        return

    file_size = get_file_size(
        message
    )

    if file_size <= 0:

        await message.reply_text(
            "I couldn't determine the file size."
        )

        return

    # --------------------------------------------------------
    # Input limit
    # --------------------------------------------------------

    if file_size > MAX_FILE_SIZE:

        await message.reply_text(
            "This file is larger than the "
            "current 2 GB input limit."
        )

        return

    filename = get_filename(
        message
    )

    # --------------------------------------------------------
    # Create job directory
    # --------------------------------------------------------

    job_dir = (
        Path(WORK_DIR)
        / str(user_id)
        / str(message.id)
    )

    job_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    input_file = (
        job_dir
        / filename
    )

    active_jobs[user_id] = {
        "cancel": False,
        "directory": str(job_dir),
    }

    status = await message.reply_text(
        "Preparing..."
    )

    started = time.monotonic()

    try:

        # ====================================================
        # DOWNLOAD
        # ====================================================

        download_tracker = ProgressTracker(
            message=status,
            operation="Downloading",
            total=file_size,
        )

        async def download_callback(
            current,
            total,
        ):

            await download_progress(
                current,
                total,
                download_tracker,
            )

        await client.download_media(
            message,
            file_name=str(
                input_file
            ),
            progress=download_callback,
        )

        # Check cancellation after download.

        if active_jobs[user_id]["cancel"]:

            raise asyncio.CancelledError

        # Verify download.

        if not input_file.is_file():

            raise RuntimeError(
                "Download completed but "
                "the file was not found."
            )

        downloaded_size = (
            input_file.stat().st_size
        )

        if downloaded_size <= 0:

            raise RuntimeError(
                "Downloaded file is empty."
            )

        # ====================================================
        # ANALYZE
        # ====================================================

        await status.edit_text(
            "Analyzing media..."
        )

        media = await analyze_media(
            str(input_file)
        )

        # Show information.

        summary = media_summary(
            media
        )

        await status.edit_text(
            "Media detected\n\n"
            f"{summary}\n\n"
            "Preparing compression..."
        )

        # ====================================================
        # OUTPUT
        # ====================================================

        output_file = build_output_path(
            str(input_file),
            media,
        )

        # ====================================================
        # COMPRESSION
        # ====================================================

        compression_tracker = ProgressTracker(
            message=status,
            operation="Compressing",
        )

        compression_callback = (
            compression_progress_callback(
                compression_tracker
            )
        )

        async def cancel_callback():

            job = active_jobs.get(
                user_id
            )

            if job is None:
                return True

            return job["cancel"]

        result = await compress_video(
            input_file=str(
                input_file
            ),

            output_file=output_file,

            media=media,

            progress_callback=(
                compression_callback
            ),

            cancel_callback=(
                cancel_callback
            ),
        )

        # ====================================================
        # VERIFY CANCELLATION
        # ====================================================

        if active_jobs[user_id]["cancel"]:

            raise asyncio.CancelledError

        # ====================================================
        # VERIFY OUTPUT
        # ====================================================

        output_path = Path(
            result.output_file
        )

        if not output_path.is_file():

            raise RuntimeError(
                "Compression finished but "
                "the output file does not exist."
            )

        if output_path.stat().st_size <= 0:

            raise RuntimeError(
                "The compressed file is empty."
            )

        # ====================================================
        # SIZE CALCULATION
        # ====================================================

        original_size = (
            result.original_size
        )

        compressed_size = (
            result.output_size
        )

        saved_bytes = (
            original_size
            - compressed_size
        )

        if original_size > 0:

            reduction = (
                saved_bytes
                / original_size
                * 100
            )

        else:

            reduction = 0.0

        # If compression somehow made the file larger,
        # don't report negative "saved" size.

        saved_text = human_size(
            max(
                0,
                saved_bytes,
            )
        )

        # ====================================================
        # UPLOAD
        # ====================================================

        upload_tracker = ProgressTracker(
            message=status,
            operation="Uploading",
            total=compressed_size,
        )

        async def upload_callback(
            current,
            total,
        ):

            await upload_progress(
                current,
                total,
                upload_tracker,
            )

        extension = (
            output_path.suffix.lower()
        )

        container_text = (
            "MKV"
            if extension == ".mkv"
            else "MP4"
        )

        caption = (
            "Compressed video\n\n"
            f"Original: "
            f"{human_size(original_size)}\n"
            f"Compressed: "
            f"{human_size(compressed_size)}\n"
            f"Saved: {saved_text}\n"
            f"Reduction: {reduction:.1f}%\n"
            f"Container: {container_text}\n"
            f"Video CRF: {result.crf}"
        )

        await client.send_document(
            chat_id=message.chat.id,
            document=str(output_path),
            caption=caption,
            progress=upload_callback,
        )

        # ====================================================
        # COMPLETE
        # ====================================================

        elapsed = (
            time.monotonic()
            - started
        )

        await status.edit_text(
            "Completed.\n\n"
            f"Original: "
            f"{human_size(original_size)}\n"
            f"Compressed: "
            f"{human_size(compressed_size)}\n"
            f"Saved: {saved_text}\n"
            f"Reduction: {reduction:.1f}%\n"
            f"Time: {int(elapsed)} sec"
        )

    # ========================================================
    # CANCELLED
    # ========================================================

    except asyncio.CancelledError:

        try:

            await status.edit_text(
                "Compression cancelled."
            )

        except Exception:
            pass

    # ========================================================
    # ERROR
    # ========================================================

    except Exception as error:

        print(
            "JOB ERROR:",
            repr(error),
        )

        try:

            await status.edit_text(
                "Compression failed.\n\n"
                f"{str(error)[:1500]}"
            )

        except Exception:
            pass

    # ========================================================
    # CLEANUP
    # ========================================================

    finally:

        active_jobs.pop(
            user_id,
            None,
        )

        try:

            shutil.rmtree(
                job_dir,
                ignore_errors=True,
            )

        except Exception as cleanup_error:

            print(
                "Cleanup error:",
                repr(cleanup_error),
            )


# ============================================================
# Start bot
# ============================================================

if __name__ == "__main__":

    print(
        "Fast Video Compressor is starting..."
    )

    app.run()
