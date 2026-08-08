import os

BOT_TOKEN = os.environ["BOT_TOKEN"]
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]

# Compression defaults
DEFAULT_TARGET_MB = int(os.getenv("DEFAULT_TARGET_MB", "130"))

# Temporary working directory
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "/tmp/compressor")

# Maximum input size we allow the bot to attempt
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2 GB
