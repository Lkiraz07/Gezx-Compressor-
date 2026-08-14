import sys
import time
import asyncio
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Optional

from aiohttp import web
from pyrogram import Client, filters
from pyrogram.types import Message

from config import Config
from utils import human_bytes, human_time, cleanup_files
from media import MediaAnalyzer
from compressor import VideoCompressor
from progress import ProgressTracker

@dataclass
class JobState:
    cancel_event: asyncio.Event
    task: Optional[asyncio.Task] = None
    input_file: Optional[Path] = None
    output_file: Optional[Path] = None

# Single-job state tracking per Telegram User ID
ACTIVE_JOBS: Dict[int, JobState] = {}

# Initialize Pyrogram Bot Client
app = Client(
    name="Gezx-Compressor",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN
)

# Render Health Check Web Server
async def health_check_handler(request):
    return web.Response(text="Bot is operational & alive!", status=200)

async def start_health_server():
    server = web.Application()
    server.router.add_get("/", health_check_handler)
    server.router.add_get("/health", health_check_handler)
    runner = web.AppRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", Config.PORT)
    await site.start()
    print(f"Render HTTP Health Check server active on port {Config.PORT}")

@app.on_message(filters.command("start") & filters.private)
async def start_command_handler(client: Client, message: Message):
    welcome_text = (
        "👋 **Welcome to Fast Video Compressor Bot!**\n\n"
        "Send me any video file (as media or document attachment up to 2GB) "
        "and I will compress it adaptively while preserving multi-audio, subtitle tracks, and chapters.\n\n"
        "Commands:\n"
        "• `/cancel` - Cancel your ongoing active job."
    )
    await message.reply_text(welcome_text)

@app.on_message(filters.command("cancel") & filters.private)
async def cancel_command_handler(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id in ACTIVE_JOBS:
        job = ACTIVE_JOBS[user_id]
        job.cancel_event.set()
        if job.task:
            job.task.cancel()
        await message.reply_text("⛔ **Cancellation requested.** Terminating process & cleaning up files...")
    else:
        await message.reply_text("ℹ️ You have no active video compression job running.")

@app.on_message((filters.video | filters.document) & filters.private)
async def media_message_handler(client: Client, message: Message):
    user_id = message.from_user.id

    # Enforce one active job per user
    if user_id in ACTIVE_JOBS:
        await message.reply_text(
            "⚠️ **Job in progress!** You already have a video processing. "
            "Wait for completion or send `/cancel` to stop it."
        )
        return

    # Filter invalid non-video documents
    media = message.video or message.document
    if not media:
        return

    # Check mime type if document
    if message.document:
        mime = message.document.mime_type or ""
        if not mime.startswith("video/"):
            await message.reply_text("❌ Please send a valid video file.")
            return

    status_msg = await message.reply_text("⏳ **Initializing download task...**")
    
    # Setup state tracking
    cancel_event = asyncio.Event()
    job_state = JobState(cancel_event=cancel_event)
    ACTIVE_JOBS[user_id] = job_state

    # Launch execution task
    task = asyncio.create_task(
        process_video_pipeline(client, message, status_msg, job_state)
    )
    job_state.task = task

async def process_video_pipeline(
    client: Client,
    user_message: Message,
    status_msg: Message,
    job_state: JobState
):
    user_id = user_message.from_user.id
    unique_id = f"{user_id}_{int(time.time())}"
    
    input_path = None
    output_path = None

    try:
        # Step 1: Download File
        dl_tracker = ProgressTracker(client, status_msg, "📥 Downloading Video")
        
        input_path = await client.download_media(
            message=user_message,
            file_name=str(Config.WORK_DIR / f"input_{unique_id}"),
            progress=dl_tracker.on_download_upload_progress
        )

        if not input_path or job_state.cancel_event.is_set():
            raise asyncio.CancelledError("Download aborted or cancelled.")

        input_path = Path(input_path)
        job_state.input_file = input_path

        # Step 2: Analyze File with FFprobe
        await status_msg.edit_text("🔍 **Analyzing video metadata and streams...**")
        media_info = await MediaAnalyzer.analyze(input_path)

        if not media_info or media_info.duration <= 0:
            await status_msg.edit_text("❌ **Failed!** Corrupted or unsupported media file stream.")
            return

        # Step 3: Determine Container & Prepare Paths
        container = media_info.recommended_container
        output_path = Config.WORK_DIR / f"compressed_{unique_id}.{container}"
        job_state.output_file = output_path

        # Step 4: Execute Adaptive Compression
        compress_tracker = ProgressTracker(client, status_msg, "⚙️ Compressing Video")
        
        start_time = time.time()
        success = await VideoCompressor.compress(
            input_path=input_path,
            output_path=output_path,
            media=media_info,
            progress_callback=compress_tracker.on_compress_progress,
            cancel_event=job_state.cancel_event
        )

        if not success or job_state.cancel_event.is_set():
            raise asyncio.CancelledError("Compression failed or cancelled by user.")

        elapsed_time = time.time() - start_time

        # Step 5: Verify Output
        orig_size = input_path.stat().st_size
        comp_size = output_path.stat().st_size

        if comp_size == 0 or comp_size >= orig_size:
            # File didn't shrink significantly or produced 0 byte error
            if comp_size >= orig_size:
                await status_msg.edit_text("ℹ️ **Notice:** Original video was already optimally compressed. Upload aborted.")
                return

        saved_bytes = orig_size - comp_size
        savings_ratio = (saved_bytes / orig_size) * 100.0

        # Step 6: Upload Output File
        ul_tracker = ProgressTracker(client, status_msg, "📤 Uploading Compressed Video")
        
        caption_text = (
            f"🎬 **Compression Completed!**\n\n"
            f"• **Original Size:** `{human_bytes(orig_size)}`\n"
            f"• **Compressed Size:** `{human_bytes(comp_size)}`\n"
            f"• **Saved:** `{human_bytes(saved_bytes)}` (`{savings_ratio:.1f}%`)\n"
            f"• **Container:** `{container.upper()}`\n"
            f"• **Time Taken:** `{human_time(elapsed_time)}`"
        )

        await client.send_document(
            chat_id=user_message.chat.id,
            document=str(output_path),
            caption=caption_text,
            reply_to_message_id=user_message.id,
            progress=ul_tracker.on_download_upload_progress
        )

        await status_msg.delete()

    except asyncio.CancelledError:
        await status_msg.edit_text("⛔ **Job Cancelled.** All temporary files cleaned up.")
    except Exception as e:
        print(f"Pipeline error encountered for user {user_id}: {e}")
        await status_msg.edit_text("❌ **An error occurred during video processing.**")

    finally:
        # Step 7: Safe Cleanup
        cleanup_files(input_path, output_path)
        ACTIVE_JOBS.pop(user_id, None)

async def main():
    # Start web server for Render health checks
    await start_health_server()
    # Start Pyrogram MTProto Bot Client
    print("Starting Pyrogram Bot Client...")
    await app.start()
    print("Bot is fully running!")
    # Keep application loop active
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        sys.exit(0)
