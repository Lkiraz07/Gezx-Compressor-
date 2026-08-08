hereimport os
from pathlib import Path


# ============================================================
# TELEGRAM
# ============================================================

BOT_TOKEN = os.getenv(
    "BOT_TOKEN",
    ""
).strip()

API_ID_RAW = os.getenv(
    "API_ID",
    ""
).strip()

API_HASH = os.getenv(
    "API_HASH",
    ""
).strip()


try:
    API_ID = int(API_ID_RAW)
except (TypeError, ValueError):
    API_ID = 0


# ============================================================
# RENDER / STORAGE
# ============================================================

# Render provides PORT automatically for Web Services.
PORT = int(
    os.getenv(
        "PORT",
        "10000"
    )
)

# Temporary working directory.
WORK_DIR = os.getenv(
    "WORK_DIR",
    "/tmp/fast-video-compressor"
).strip()

Path(WORK_DIR).mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# TELEGRAM FILE LIMITS
# ============================================================

# 2000 MiB.
#
# This is the maximum size we allow the bot to accept.
# The actual available processing capacity on Render Free
# can be lower because of its resource limitations.

MAX_FILE_SIZE = (
    2000 * 1024 * 1024
)

MAX_OUTPUT_SIZE = (
    2000 * 1024 * 1024
)


# ============================================================
# JOB SETTINGS
# ============================================================

# One compression job per user at a time.
MAX_CONCURRENT_JOBS_PER_USER = 1


# ============================================================
# MEDIA SETTINGS
# ============================================================

# Video extensions accepted by the bot.
VIDEO_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".avi",
    ".mov",
    ".webm",
    ".m4v",
    ".ts",
    ".mts",
    ".m2ts",
    ".flv",
    ".wmv",
    ".3gp",
}


# ============================================================
# CONFIGURATION VALIDATION
# ============================================================

def validate_config() -> None:

    missing = []

    if not BOT_TOKEN:
        missing.append(
            "BOT_TOKEN"
        )

    if API_ID <= 0:
        missing.append(
            "API_ID"
        )

    if not API_HASH:
        missing.append(
            "API_HASH"
        )

    if missing:

        raise RuntimeError(
            "Missing required environment variables: "
            + ", ".join(missing)
        )


# ============================================================
# CONFIG SUMMARY
# ============================================================

def config_summary() -> str:

    max_input_mib = (
        MAX_FILE_SIZE
        / 1024
        / 1024
    )

    max_output_mib = (
        MAX_OUTPUT_SIZE
        / 1024
        / 1024
    )

    return (
        "Fast Video Compressor configuration\n"
        f"Port: {PORT}\n"
        f"Work directory: {WORK_DIR}\n"
        f"Maximum input: {max_input_mib:.0f} MiB\n"
        f"Maximum output: {max_output_mib:.0f} MiB\n"
        f"Max jobs per user: "
        f"{MAX_CONCURRENT_JOBS_PER_USER}"
    )
