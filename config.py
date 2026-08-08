import os

BOT_TOKEN = os.environ["BOT_TOKEN"]
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]

# Maximum input size: 2 GB
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024

# Working directory
WORK_DIR = os.getenv(
    "WORK_DIR",
    "/tmp/fast-video-compressor"
)

# Adaptive compression settings
MIN_VIDEO_BITRATE_KBPS = 250
MAX_VIDEO_BITRATE_KBPS = 12000

# Quality targets
BALANCED_CRF = 24
MAX_COMPRESSION_CRF = 30
HIGH_QUALITY_CRF = 20
