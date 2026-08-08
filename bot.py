import asyncio
import os
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
# Telegram client
# ============================================================

app = Client(
    "fast_video_compressor",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)


# ============================================================
# Job management
# ============================================================

active_jobs = {}


def user_id_from_message(
    message: Message,
) -> int:

    if message.from_user:
        return message.from_user.id

    return message.chat.id


# ============================================================
# /start
# ============================================================

@app.on_message(filters.command("start"))
async def start_handler(
    client: Client,
    message: Message,
):

    await message.reply_text(
        "Fast Video Compressor\n\n"
        "Send me a video or video file.\n\n"
        "The compressor automatically chooses "
        "compression strength based on the source.\n\n"
        "Commands:\n"
        "/cancel - cancel your current job"
    )


# ============================================================
# /cancel
# ============================================================

@app.on_message(filters.command("cancel"))
async def cancel_handler(
    client: Client,
    message: Message,
):

    user_id = user_id_from_message(
        message
    )

    job = active_jobs.get(
        user_id
    )

    if not job:

        await message.reply_text(
            "You don't have an active job."
        )

        return

    job["cancel"] = True

    await message.reply_text(
        "Cancellation requested."
    )


# ============================================================
# File information
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


def get_original_filename(
    message: Message,
) -> str:

    if (
        message.document
        and message.document.file_name
    ):

        return safe_filename(
            message.document.file_name
        )

    if (
        message.video
        and message.video.file_name
    ):

        return safe_filename(
            message.video.file_name
        )

    return (
        f"video_{message.id}.mp4"
    )


# ============================================================
# Download progress callback
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
# Upload progress callback
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
# Main video handler
# ============================================================

@app.on_message(
    filters.video
    | filters.document
)
async def video_handler(
    client: Client,
    message: Message,
):

    user_id = user_id_from_message(
        message
    )

    # --------------------------------------------------------
    # Prevent multiple jobs per user
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
            "Unable to determine file size."
        )

        return

    # --------------------------------------------------------
    # 2 GB input safeguard
    # --------------------------------------------------------

    if file_size > MAX_FILE_SIZE:

        await message.reply_text(
            "This file is larger than "
            "the current 2 GB input limit."
        )

        return

    filename = get_original_filename(
        message
    )

    # --------------------------------------------------------
    # Job directory
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
        "Preparing your video..."
    )

    started_at = time.monotonic()

    try:

        # ====================================================
        # DOWNLOAD
        # ====================================================

        download_tracker = ProgressTracker(
            message=status,
            operation="Downloading",
            total=file_size,
        )

        async def download_cb(
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
            progress=download_cb,
        )

        if active_jobs[user_id]["cancel"]:

            raise asyncio.CancelledError

        # ====================================================
        # ANALYZE
        # ====================================================

        await status.edit_text(
            "Analyzing media..."
        )

        media = await analyze_media(
            str(input_file)
        )

        summary = media_summary(
            media
        )

        await status.edit_text(
            "Media detected\n\n"
            f"{summary}\n\n"
            "Preparing adaptive compression..."
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

        compression_cb = (
            compression_progress_callback(
                compression_tracker
            )
        )

        async def cancel_cb():

            return active_jobs[
                user_id
            ]["cancel"]

        result = await compress_video(
            input_file=str(
                input_file
            ),

            output_file=output_file,

            media=media,

            progress_callback=compression_cb,

            cancel_callback=cancel_cb,
        )

        if active_jobs[user_id]["cancel"]:

            raise asyncio.CancelledError

        # ====================================================
        # RESULT
        # ====================================================

        original_size = (
            result.original_size
        )

        compressed_size = (
            result.output_size
        )

        saved = (
            original_size
            - compressed_size
        )

        if original_size > 0:

            reduction = (
                saved
                / original_size
                * 100
            )

        else:

            reduction = 0

        elapsed = (
            time.monotonic()
            - started_at
        )

        await status.edit_text(
            "Compression complete.\n\n"
            f"Original: "
            f"{human_size(original_size)}\n"
            f"Compressed: "
            f"{human_size(compressed_size)}\n"
            f"Saved: "
            f"{human_size(max(saved, 0))}\n"
            f"Reduction: "
            f"{reduction:.1f}%\n\n"
            f"CRF: {result.crf}"
        )

        # ====================================================
        # UPLOAD
        # ====================================================

        upload_tracker = ProgressTracker(
            message=status,
            operation="Uploading",
            total=compressed_size,
        )

        async def upload_cb(
            current,
            total,
        ):

            await upload_progress(
                current,
                total,
                upload_tracker,
            )

        caption = (
            "Compressed video\n\n"
            f"Original: "
            f"{human_size(original_size)}\n"
            f"Compressed: "
            f"{human_size(compressed_size)}\n"
            f"Saved: "
            f"{human_size(max(saved, 0))}\n"
            f"Reduction: "
            f"{reduction:.1f}%"
        )

        extension = (
            Path(output_file)
            .suffix
            .lower()
        )

        # ----------------------------------------------------
        # Send as document to preserve container/streams.
        # ----------------------------------------------------

        await client.send_document(
            chat_id=message.chat.id,
            document=output_file,
            caption=caption,
            progress=upload_cb,
        )

        # ====================================================
        # FINISH
        # ====================================================

        await status.edit_text(
            "Done.\n\n"
            f"Original: "
            f"{human_size(original_size)}\n"
            f"Compressed: "
            f"{human_size(compressed_size)}\n"
            f"Saved: "
            f"{human_size(max(saved, 0))}\n"
            f"Time: "
            f"{int(elapsed)} sec"
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
            "Compression error:",
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

        except Exception:
            pass


# ============================================================
# Start
# ============================================================

print(
    "Fast Video Compressor is starting..."
)

app.run()
