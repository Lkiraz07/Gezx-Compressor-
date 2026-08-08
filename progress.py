import asyncio
import time
from typing import Optional

from pyrogram.types import Message

from utils import (
    human_size,
    make_progress_bar,
)


class ProgressTracker:

    def __init__(
        self,
        message: Message,
        operation: str,
        total: int = 0,
        update_interval: float = 3.0,
    ):
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

        self.finished = False

    def update_values(
        self,
        current: int,
        total: Optional[int] = None,
    ):

        self.current = max(
            0,
            current,
        )

        if total:
            self.total = total

        elapsed = (
            time.monotonic()
            - self.start_time
        )

        if elapsed > 0:
            self.speed = (
                self.current / elapsed
            )

        if (
            self.total > 0
            and self.speed > 0
        ):

            remaining = (
                self.total
                - self.current
            )

            self.eta = int(
                remaining / self.speed
            )

    def percentage(self) -> float:

        if self.total <= 0:
            return 0.0

        return min(
            100.0,
            (
                self.current
                / self.total
                * 100
            ),
        )

    def speed_text(self) -> str:

        if self.speed <= 0:
            return "--"

        return (
            human_size(
                int(self.speed)
            )
            + "/s"
        )

    def eta_text(self) -> str:

        if self.eta <= 0:
            return "--"

        seconds = self.eta

        hours = seconds // 3600

        minutes = (
            seconds % 3600
        ) // 60

        seconds %= 60

        if hours:
            return (
                f"{hours:02d}:"
                f"{minutes:02d}:"
                f"{seconds:02d}"
            )

        return (
            f"{minutes:02d}:"
            f"{seconds:02d}"
        )

    def text(
        self,
        extra: str = "",
    ) -> str:

        percentage = self.percentage()

        bar = make_progress_bar(
            percentage
        )

        current = human_size(
            self.current
        )

        total = (
            human_size(self.total)
            if self.total > 0
            else "--"
        )

        lines = [
            f"{self.operation}",
            "",
            f"{bar} {percentage:.1f}%",
            "",
            f"Size: {current} / {total}",
            f"Speed: {self.speed_text()}",
            f"ETA: {self.eta_text()}",
        ]

        if extra:
            lines.extend(
                [
                    "",
                    extra,
                ]
            )

        return "\n".join(lines)

    async def render(
        self,
        current: int,
        total: Optional[int] = None,
        extra: str = "",
        force: bool = False,
    ):

        self.update_values(
            current,
            total,
        )

        now = time.monotonic()

        if (
            not force
            and now - self._last_update
            < self.update_interval
        ):
            return

        async with self._lock:

            now = time.monotonic()

            if (
                not force
                and now - self._last_update
                < self.update_interval
            ):
                return

            self._last_update = now

            try:

                await self.message.edit_text(
                    self.text(extra)
                )

            except Exception:
                # Telegram may reject an edit if
                # the message hasn't changed.
                pass

    async def finish(
        self,
        text: Optional[str] = None,
    ):

        self.finished = True

        if text is None:
            text = self.text()

        try:

            await self.message.edit_text(
                text
            )

        except Exception:
            pass


def telegram_progress_callback(
    tracker: ProgressTracker,
):

    async def callback(
        current: int,
        total: int,
    ):

        await tracker.render(
            current=current,
            total=total,
        )

    return callback


def compression_progress_callback(
    tracker: ProgressTracker,
):

    async def callback(
        data: dict,
    ):

        percent = data.get(
            "percent",
            0,
        )

        duration = data.get(
            "duration",
            0,
        )

        encoded = data.get(
            "encoded_seconds",
            0,
        )

        crf = data.get(
            "crf",
            "--",
        )

        if duration > 0:

            current = int(
                duration
                * percent
                / 100
            )

        else:
            current = int(encoded)

        await tracker.render(
            current=current,
            total=int(duration),
            extra=f"CRF: {crf}",
        )

    return callback
