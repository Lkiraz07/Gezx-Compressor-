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
    DEFAULT_TARGET_MB,
    DOWNLOAD_DIR,
    MAX_FILE_SIZE,
)

from compressor import compress_video, get_media_info


app = Client(
    "fast_video_compressor",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)


os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def human_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"

    if size < 1024 ** 2:
        return f"{size / 1024:.2f} KB"

    if size < 1024 ** 3:
        return f"{size / 1024 ** 2:.2f} MB"

    return f"{size / 1024 ** 3:.2f} GB"


def get_filename(message: Message) -> str:
    if message.document and message.document.file_name:
        return message.document.file_name

    if message.video and message.video.file_name:
        return message.video.file_name

    return f"video_{message.id}.mp4"


def get_size(message: Message) -> int:
    if message.document:
        return message.document.file_size or 0

    if message.video:
        return message.video.file_size or 0

    return 0


@app.on_message(filters.command("start"))
async def start_handler(client: Client, message: Message):

    await message.reply_text(
        "Fast Video Compressor\n\n"
        "Send me a video or video file.\n\n"
        f"Default target: {DEFAULT_TARGET_MB} MB\n"
        "Maximum input: 2 GB"
    )


@app.on_message(filters.command("cancel"))
async def cancel_handler(client: Client, message: Message):

    job = getattr(message.from_user, "id", None)

    if job in active_jobs:
        active_jobs[job]["cancel"] = True

        await message.reply_text(
            "Cancellation requested."
        )

    else:
        await message.reply_text(
            "No active compression job."
        )


active_jobs = {}


@app.on_message(filters.video | filters.document)
async def video_handler(client: Client, message: Message):

    user_id = message.from_user.id if message.from_user else message.chat.id

    if user_id in active_jobs:
        await message.reply_text(
            "You already have a compression job running."
        )
        return

    file_size = get_size(message)

    if file_size <= 0:
        await message.reply_text(
            "Unable to determine file size."
        )
        return

    if file_size > MAX_FILE_SIZE:
        await message.reply_text(
            "File is larger than the 2 GB limit."
        )
        return

    filename = get_filename(message)

    job_dir = Path(DOWNLOAD_DIR) / str(user_id) / str(message.id)

    job_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    input_file = job_dir / filename

    output_file = job_dir / f"compressed_{filename}"

    active_jobs[user_id] = {
        "cancel": False,
        "message_id": message.id,
    }

    status = await message.reply_text(
        "Preparing compression..."
    )

    start_time = time.time()

    try:

        await status.edit_text(
            "Downloading...\n\n"
            f"File: {filename}\n"
            f"Size: {human_size(file_size)}"
        )

        await client.download_media(
            message,
            file_name=str(input_file),
        )

        if active_jobs[user_id]["cancel"]:
            raise asyncio.CancelledError

        await status.edit_text(
            "Analyzing video..."
        )

        media_info = await get_media_info(
            str(input_file)
        )

        duration = media_info["format"].get(
            "duration",
            0,
        )

        duration = float(duration or 0)

        if duration <= 0:
            raise RuntimeError(
                "Unable to determine video duration."
            )

        await status.edit_text(
            "Starting compression...\n\n"
            f"Original: {human_size(file_size)}\n"
            f"Target: {DEFAULT_TARGET_MB} MB"
        )

        async def progress_callback(progress):

            if user_id not in active_jobs:
                return

            if active_jobs[user_id]["cancel"]:
                return

            percent = progress["percent"]

            elapsed = time.time() - start_time

            speed = (
                progress["encoded_seconds"] / elapsed
                if elapsed > 0
                else 0
            )

            remaining = (
                (duration - progress["encoded_seconds"]) / speed
                if speed > 0
                else 0
            )

            await status.edit_text(
                "Compressing...\n\n"
                f"Progress: {percent:.1f}%\n"
                f"Speed: {speed:.2f}x\n"
                f"ETA: {int(max(remaining, 0))} sec\n\n"
                f"Original: {human_size(file_size)}"
            )

        await compress_video(
            input_file=str(input_file),
            output_file=str(output_file),
            target_size_mb=DEFAULT_TARGET_MB,
            progress_callback=progress_callback,
            cancel_callback=lambda:
                active_jobs[user_id]["cancel"],
        )

        if active_jobs[user_id]["cancel"]:
            raise asyncio.CancelledError

        if not output_file.exists():
            raise RuntimeError(
                "FFmpeg did not create the output file."
            )

        output_size = output_file.stat().st_size

        await status.edit_text(
            "Compression complete.\n\n"
            f"Original: {human_size(file_size)}\n"
            f"Compressed: {human_size(output_size)}"
        )

        caption = (
            "Compressed video\n\n"
            f"Original: {human_size(file_size)}\n"
            f"Compressed: {human_size(output_size)}"
        )

        await client.send_document(
            chat_id=message.chat.id,
            document=str(output_file),
            caption=caption,
        )

        await status.delete()

    except asyncio.CancelledError:

        await status.edit_text(
            "Compression cancelled."
        )

    except Exception as error:

        print(
            f"Compression error for {user_id}: {error}"
        )

        await status.edit_text(
            "Compression failed.\n\n"
            f"Reason: {str(error)[:1000]}"
        )

    finally:

        active_jobs.pop(user_id, None)

        shutil.rmtree(
            job_dir,
            ignore_errors=True,
        )


print("Fast Video Compressor is starting...")

app.run()
