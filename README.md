here# Gezx Fast Video Compressor Bot

Telegram video compressor using Pyrogram, FFmpeg and Render.

## Behavior

- Main video stream is re-encoded with adaptive CRF.
- All audio streams are copied without re-encoding.
- All subtitle streams are copied.
- Metadata and chapters are preserved.
- Additional video streams are copied and force MKV output.
- MP4 is used only when the copied audio/subtitle streams are conservatively compatible.
- Temporary files are removed after each job.
- Download, compression and upload progress are shown.
- `/cancel` can cancel the active job.

## Environment variables

Required:

- `BOT_TOKEN`
- `API_ID`
- `API_HASH`

Optional:

- `WORK_DIR` (defaults to `/tmp/fast-video-compressor`)

Render provides `PORT` automatically.

## Important

A smaller output size is not guaranteed for every source. CRF-based compression is quality-targeted, not a fixed-size encoder. Large audio tracks that are copied exactly can also make the final file relatively large.

The Render Free plan has resource and sleeping limitations. A 2 GB input may exceed the available CPU, RAM, disk or execution capacity even though the Telegram transfer path can handle large files.
