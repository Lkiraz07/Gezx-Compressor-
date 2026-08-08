from pyrogram import Client, filters
from pyrogram.types import Message

from config import BOT_TOKEN, API_ID, API_HASH


app = Client(
    "fast_compressor_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)


@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    await message.reply_text(
        "Fast Video Compressor Bot\n\n"
        "Send me a video or file and I will process it."
    )


@app.on_message(filters.video | filters.document)
async def receive_file(client: Client, message: Message):
    await message.reply_text(
        "File received.\n\n"
        "Compression system is coming next."
    )


print("Bot is starting...")


app.run()
