import asyncio
import time
from typing import Optional

from pyrogram.types import Message
from utils import human_size, make_progress_bar


class ProgressTracker:
    def __init__(self, message: Message, operation: str, total: int = 0, update_interval: float = 3.0):
        self.message = message
        self.operation = operation
        self.total = total
        self.update_interval = update_interval
        self.start_time = time.monotonic()
        self.current = 0
        self.speed = 0.0
        self.eta = 0
        self._last_update = 0.0
        self._lock = asyncio.Lock()

    def update_values(self, current: int, total: Optional[int] = None):
        self.current = max(0, current)
        if total is not None and total > 0:
            self.total = total
        elapsed = time.monotonic() - self.start_time
        if elapsed > 0:
            self.speed = self.current / elapsed
        if self.total > 0 and self.speed > 0:
            self.eta = max(0, int((self.total - self.current) / self.speed))

    def percentage(self) -> float:
        return min(100.0, self.current / self.total * 100) if self.total > 0 else 0.0

    def speed_text(self) -> str:
        return f"{human_size(int(self.speed))}/s" if self.speed > 0 else "--"

    def eta_text(self) -> str:
        if self.eta <= 0:
            return "--"
        h, rem = divmod(self.eta, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

    def text(self, extra: str = "") -> str:
        pct = self.percentage()
        lines = [
            self.operation,
            "",
            f"{make_progress_bar(pct)} {pct:.1f}%",
            "",
            f"Size: {human_size(self.current)} / {human_size(self.total) if self.total else '--'}",
            f"Speed: {self.speed_text()}",
            f"ETA: {self.eta_text()}",
        ]
        if extra:
            lines += ["", extra]
        return "\n".join(lines)

    async def render(self, current: int, total: Optional[int] = None, extra: str = "", force: bool = False):
        self.update_values(current, total)
        now = time.monotonic()
        if not force and now - self._last_update < self.update_interval:
            return
        async with self._lock:
            now = time.monotonic()
            if not force and now - self._last_update < self.update_interval:
                return
            self._last_update = now
            try:
                await self.message.edit_text(self.text(extra))
            except Exception:
                pass


def compression_progress_callback(tracker: ProgressTracker):
    async def callback(data: dict):
        duration = float(data.get("duration", 0) or 0)
        encoded = float(data.get("encoded_seconds", 0) or 0)
        crf = data.get("crf", "--")
        await tracker.render(
            current=int(encoded),
            total=int(duration) if duration > 0 else None,
            extra=f"CRF: {crf}",
        )
    return callback
