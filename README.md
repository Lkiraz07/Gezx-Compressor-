# Gezx Compressor Bot

A Telegram video compressor built with Python, Pyrogram and FFmpeg.

## Features

- Video compression without a fixed target size
- Adaptive CRF
- Up to Telegram's supported MTProto file size
- Multiple audio tracks preserved
- Audio streams copied without re-encoding
- Subtitle streams preserved when the selected container supports them
- Metadata preservation
- Chapter preservation
- MP4/MKV container selection
- Download progress
- Compression progress
- Upload progress
- ETA and speed information
- Job cancellation
- Automatic temporary-file cleanup
- Docker deployment
- Render worker deployment

## Architecture

Telegram
↓
Pyrogram / MTProto
↓
Download
↓
FFprobe
↓
Media analysis
↓
FFmpeg
↓
Video compression
↓
Audio/subtitle preservation
↓
Output verification
↓
Telegram upload
↓
Cleanup

## Environment Variables

The following variables are required:

BOT_TOKEN
API_ID
API_HASH

Optional:

WORK_DIR

Default:

/tmp/fast-video-compressor

## Important

The bot does not use a fixed output-size target such as 130 MB.

The final size depends on:

- Source resolution
- Source bitrate
- Frame rate
- Video complexity
- CRF
- Audio/subtitle streams

Audio streams are copied rather than re-encoded.

Therefore the final file size can vary significantly.

## Deployment

The project is designed to run as a Docker worker.

FFmpeg and FFprobe are installed through the Docker image.

Do not place Telegram credentials directly inside the source code.

Use Render environment variables instead.
