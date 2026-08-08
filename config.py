import os
from pathlib import Path


# ============================================================
# Telegram
# ============================================================

BOT_TOKEN = os.getenv(
    "BOT_TOKEN",
    "",
).strip()

API_ID_RAW = os.getenv(
    "API_ID",
    "",
).strip()

API_HASH = os.getenv(
    "API_HASH",
    "",
).strip()


try:
    API_ID = int(API_ID_RAW)
except ValueError:
    API_ID = 0


# ============================================================
# Storage
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
# Limits
# ============================================================

# 2 GiB input limit.
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024


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
