hereFast Telegram Video Compressor Bot "Gezx-Compressor"
​Production-ready Telegram Bot built with Python, Pyrogram MTProto, FFmpeg, and Docker. Designed specifically to run on Render's Free Web Service tier.
​Features
​Adaptive Quality Compression: Intelligent dynamic CRF calculation based on video resolution, frame rate, and input bitrate.
​Full Track Preservation: Audio streams (-c:a copy) and subtitle streams (-c:s copy) are preserved without re-encoding or burning.
​Metadata Retention: Global metadata and chapter layouts are preserved.
​Smart Container Selection: Selects MP4 if audio and subtitles are natively supported; automatically switches to MKV otherwise.
​Job Controls: Single active task per user restriction with a /cancel command.
​Render Health Check: Built-in lightweight HTTP health endpoint to prevent Render Free Service sleep timeouts.
​Step-by-Step Guidance: Development & Deployment
​Step 1: Obtain Credentials
​Telegram API ID & Hash:
​Log in to my.telegram.org.
​Go to API development tools and create an application to obtain API_ID and API_HASH.
​Bot Token:
​Open Telegram and message @BotFather.
​Send /newbot and follow instructions to get your BOT_TOKEN.
​Step 2: Set Up GitHub Repository
