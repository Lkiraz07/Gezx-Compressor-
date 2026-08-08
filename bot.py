import asyncio
import os
import shutil
import time
from pathlib import Path

from aiohttp import web
from pyrogram import Client, filters
from pyrogram.types import Message

from config import API_HASH, API_ID, BOT_TOKEN, MAX_FILE_SIZE, MAX_OUTPUT_SIZE, WORK_DIR, validate_config
from compressor import compress_video
from media import analyze_media, media_summary
from progress import ProgressTracker, compression_progress_callback
from utils import build_output_path, human_size, safe_filename


app = Client("fast_video_compressor", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
active_jobs = {}


def get_user_id(message: Message) -> int:
    return message.from_user.id if message.from_user else message.chat.id


@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    await message.reply_text(
        "Fast Video Compressor\n\n"
        "Send a video or video file. The video stream is compressed while audio and subtitle streams are copied.\n\n"
        "/cancel - cancel your current job"
    )


@app.on_message(filters.command("cancel"))
async def cancel_command(client: Client, message: Message):
    user_id = get_user_id(message)
    job = active_jobs.get(user_id)
    if job is None:
        await message.reply_text("You don't have an active job.")
        return
    job["cancel"] = True
    await message.reply_text("Cancellation requested.")


def get_file_size(message: Message) -> int:
    if message.video:
        return message.video.file_size or 0
    if message.document:
        return message.document.file_size or 0
    return 0


def get_filename(message: Message) -> str:
    if message.document and message.document.file_name:
        return safe_filename(message.document.file_name)
    if message.video and message.video.file_name:
        return safe_filename(message.video.file_name)
    return f"video_{message.id}.mp4"


@app.on_message(filters.video | filters.document)
async def video_handler(client: Client, message: Message):
    user_id = get_user_id(message)
    if user_id in active_jobs:
        await message.reply_text("You already have a compression job running.")
        return

    file_size = get_file_size(message)
    if file_size <= 0:
        await message.reply_text("I couldn't determine the file size.")
        return
    if file_size > MAX_FILE_SIZE:
        await message.reply_text("This file is larger than the 2000 MiB input limit.")
        return

    filename = get_filename(message)
    job_dir = Path(WORK_DIR) / str(user_id) / str(message.id)
    job_dir.mkdir(parents=True, exist_ok=True)
    input_file = job_dir / filename
    active_jobs[user_id] = {"cancel": False}
    status = await message.reply_text("Preparing...")
    started = time.monotonic()

    try:
        tracker = ProgressTracker(status, "Downloading", file_size)

        async def download_callback(current, total):
            await tracker.render(current, total)

        await client.download_media(message, file_name=str(input_file), progress=download_callback)
        if active_jobs[user_id]["cancel"]:
            raise asyncio.CancelledError
        if not input_file.is_file() or input_file.stat().st_size <= 0:
            raise RuntimeError("Download failed or produced an empty file.")

        await status.edit_text("Analyzing media...")
        media = await analyze_media(str(input_file))
        await status.edit_text("Media detected\n\n" + media_summary(media) + "\n\nPreparing compression...")

        output_file = build_output_path(str(input_file), media)
        compression_tracker = ProgressTracker(status, "Compressing")
        compression_callback = compression_progress_callback(compression_tracker)

        async def cancel_callback():
            job = active_jobs.get(user_id)
            return job is None or job.get("cancel", False)

        result = await compress_video(
            str(input_file), output_file, media,
            progress_callback=compression_callback,
            cancel_callback=cancel_callback,
        )

        output_path = Path(result.output_file)
        if not output_path.is_file() or output_path.stat().st_size <= 0:
            raise RuntimeError("Compression produced no valid output file.")

        compressed_size = output_path.stat().st_size
        if compressed_size > MAX_OUTPUT_SIZE:
            raise RuntimeError("The compressed file is still larger than Telegram's 2000 MiB limit.")

        original_size = result.original_size
        saved_bytes = max(0, original_size - compressed_size)
        reduction = (saved_bytes / original_size * 100) if original_size else 0.0

        await status.edit_text("Uploading...")
        upload_tracker = ProgressTracker(status, "Uploading", compressed_size)

        async def upload_callback(current, total):
            await upload_tracker.render(current, total)

        caption = (
            "Compressed video\n\n"
            f"Original: {human_size(original_size)}\n"
            f"Compressed: {human_size(compressed_size)}\n"
            f"Saved: {human_size(saved_bytes)}\n"
            f"Reduction: {reduction:.1f}%\n"
            f"Container: {output_path.suffix.upper().lstrip('.') }\n"
            f"Video CRF: {result.crf}"
        )

        await client.send_document(
            chat_id=message.chat.id,
            document=str(output_path),
            caption=caption,
            progress=upload_callback,
        )

        elapsed = int(time.monotonic() - started)
        await status.edit_text(
            "Completed.\n\n"
            f"Original: {human_size(original_size)}\n"
            f"Compressed: {human_size(compressed_size)}\n"
            f"Saved: {human_size(saved_bytes)}\n"
            f"Reduction: {reduction:.1f}%\n"
            f"Time: {elapsed} sec"
        )

    except asyncio.CancelledError:
        try:
            await status.edit_text("Compression cancelled.")
        except Exception:
            pass
    except Exception as exc:
        print("JOB ERROR:", repr(exc))
        try:
            await status.edit_text("Compression failed.\n\n" + str(exc)[:1500])
        except Exception:
            pass
    finally:
        active_jobs.pop(user_id, None)
        shutil.rmtree(job_dir, ignore_errors=True)


async def health(request):
    return web.Response(text="OK")


async def start_health_server():
    port = int(os.getenv("PORT", "10000"))
    web_app = web.Application()
    web_app.router.add_get("/", health)
    web_app.router.add_get("/health", health)
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Health server listening on {port}")
    return runner


async def main():
    validate_config()
    runner = await start_health_server()
    try:
        await app.start()
        print("Telegram bot started.")
        await asyncio.Event().wait()
    finally:
        await app.stop()
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
