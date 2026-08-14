import time
import asyncio
from pyrogram.errors import FloodWait, MessageNotModified
from utils import human_bytes, human_time, generate_progress_bar

class ProgressTracker:
    def __init__(self, client, message, action_title: str):
        self.client = client
        self.message = message
        self.action_title = action_title
        self.last_update_time = 0.0
        self.start_time = time.time()

    async def on_download_upload_progress(self, current: int, total: int):
        """Callback suitable for Pyrogram's progress parameter."""
        now = time.time()
        # Throttle edits to once every 4.0 seconds to satisfy Telegram limits
        if (now - self.last_update_time) < 4.0 and current < total:
            return

        self.last_update_time = now
        elapsed = now - self.start_time
        percentage = (current / total) * 100 if total > 0 else 0
        speed = current / elapsed if elapsed > 0 else 0
        eta = (total - current) / speed if speed > 0 else 0

        bar = generate_progress_bar(percentage)
        
        text = (
            f"**{self.action_title}**\n\n"
            f"[{bar}] `{percentage:.1f}%`\n"
            f"• **Done:** `{human_bytes(current)}` / `{human_bytes(total)}`\n"
            f"• **Speed:** `{human_bytes(speed)}/s`\n"
            f"• **ETA:** `{human_time(eta)}`"
        )

        try:
            await self.message.edit_text(text)
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except MessageNotModified:
            pass
        except Exception as e:
            print(f"Error updating message: {e}")

    async def on_compress_progress(self, percentage: float, speed: float, eta: float):
        """Callback suitable for FFmpeg compression progress loop."""
        now = time.time()
        if (now - self.last_update_time) < 4.0 and percentage < 100.0:
            return

        self.last_update_time = now
        bar = generate_progress_bar(percentage)

        text = (
            f"**⚙️ Compressing Video**\n\n"
            f"[{bar}] `{percentage:.1f}%`\n"
            f"• **Speed factor:** `{speed:.2f}x`\n"
            f"• **ETA:** `{human_time(eta)}`\n\n"
            f"_preserving original audio & subtitle streams..._"
        )

        try:
            await self.message.edit_text(text)
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except MessageNotModified:
            pass
        except Exception as e:
            print(f"Error updating compression message: {e}")
