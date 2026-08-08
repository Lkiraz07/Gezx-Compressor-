hereimport os
from pathlib import Path

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
API_ID_RAW = os.getenv("API_ID", "").strip()
API_HASH = os.getenv("API_HASH", "").strip()

try:
    API_ID = int(API_ID_RAW)
except (TypeError, ValueError):
    API_ID = 0

PORT = int(os.getenv("PORT", "10000"))
WORK_DIR = os.getenv(
    "WORK_DIR", "/tmp/fast-video-compressor"
).strip()
Path(WORK_DIR).mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 2000 * 1024 * 1024
MAX_OUTPUT_SIZE = 2000 * 1024 * 1024
MAX_CONCURRENT_JOBS_PER_USER = 1


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
            "Missing required environment variables: " + ", ".join(missing)
        )
