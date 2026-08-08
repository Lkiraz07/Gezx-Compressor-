import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set")

if not API_ID:
    raise ValueError("API_ID is not set")

if not API_HASH:
    raise ValueError("API_HASH is not set")
