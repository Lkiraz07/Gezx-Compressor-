import os
from pathlib import Path


# ============================================================
# Telegram Configuration
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

API_ID_RAW = os.getenv("API_ID", "").strip()

API_HASH = os.getenv("API_HASH", "").strip()


try:
    API_ID = int(API_ID_RAW)
except (TypeError, ValueError):
    API_ID = 0


# ============================================================
# Working Directory
# ============================================================

WORK_DIR = os.getenv(
    "WORK_DIR",
    "/tmp/fast-video-compressor",
).strip()

Path(WORK_DIR).mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# Telegram File Limits
# ============================================================

# Pyrogram uses Telegram's MTProto API.
# Pyrogram documents a 2000 MiB per-file limit for
# MTProto uploads/downloads. :contentReference[oaicite:0]{index=0}

MAX_FILE_SIZE = 2000 * 1024 * 1024

MAX_OUTPUT_SIZE = 2000 * 1024 * 1024


# ============================================================
# Compression Limits
# ============================================================

# Prevent a single user from accidentally creating
# multiple simultaneous compression jobs.

MAX_CONCURRENT_JOBS_PER_USER = 1


# ============================================================
# Validation
# ============================================================

def validate_config() -> None:

    missing = []

    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")

    if API_ID <= 0:
        missing.append("API_ID")

    if not API_HASH:
        missing.append("API_HASH")

    if missing:

        raise RuntimeError(
            "Missing required environment variables: "
            + ", ".join(missing)
        )


# ============================================================
# Startup Information
# ============================================================

def config_summary() -> str:

    return (
        "Configuration loaded\n"
        f"Work directory: {WORK_DIR}\n"
        f"Maximum input: "
        f"{MAX_FILE_SIZE / 1024 / 1024:.0f} MiB\n"
        f"Maximum output: "
        f"{MAX_OUTPUT_SIZE / 1024 / 1024:.0f} MiB"
    )
