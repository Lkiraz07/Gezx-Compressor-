import json
import asyncio
from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path

@dataclass
class StreamInfo:
    index: int
    codec_type: str
    codec_name: str
    language: str = "und"
    title: str = ""

@dataclass
class MediaInfo:
    duration: float
    size_bytes: int
    video_codec: str
    width: int
    height: int
    fps: float
    video_bitrate: int
    streams: List[StreamInfo] = field(default_factory=list)
    has_audio: bool = False
    has_subtitles: bool = False
    recommended_container: str = "mp4"

class MediaAnalyzer:
    MP4_COMPATIBLE_AUDIO = {"aac", "mp3", "ac3", "eac3", "alac", "m4a"}
    MP4_COMPATIBLE_SUBS = {"mov_text", "tx3g"}

    @classmethod
    async def analyze(cls, file_path: Path) -> Optional[MediaInfo]:
        """Run ffprobe on given input file to inspect streams and metadata."""
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(file_path)
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                print(f"FFprobe failed with returncode {process.returncode}: {stderr.decode()}")
                return None

            data = json.loads(stdout.decode('utf-8'))
            format_info = data.get("format", {})
            duration = float(format_info.get("duration", 0.0))
            size_bytes = int(format_info.get("size", file_path.stat().st_size if file_path.exists() else 0))

            streams = []
            video_codec = ""
            width = 0
            height = 0
            fps = 25.0
            video_bitrate = 0
            has_audio = False
            has_subtitles = False
            
            mp4_compatible = True

            for s in data.get("streams", []):
                index = int(s.get("index", 0))
                codec_type = s.get("codec_type", "").lower()
                codec_name = s.get("codec_name", "").lower()
                tags = s.get("tags", {})
                language = tags.get("language", "und")
                title = tags.get("title", "")

                stream_obj = StreamInfo(
                    index=index,
                    codec_type=codec_type,
                    codec_name=codec_name,
                    language=language,
                    title=title
                )
                streams.append(stream_obj)

                if codec_type == "video" and not video_codec:
                    video_codec = codec_name
                    width = int(s.get("width", 0))
                    height = int(s.get("height", 0))
                    
                    # Extract FPS safely
                    r_fps = s.get("r_frame_rate", "25/1")
                    if "/" in r_fps:
                        num, den = map(float, r_fps.split("/"))
                        fps = num / den if den > 0 else 25.0
                    else:
                        fps = float(r_fps) if r_fps else 25.0

                    # Extract or compute estimated video bitrate
                    if "bit_rate" in s and s["bit_rate"].isdigit():
                        video_bitrate = int(s["bit_rate"])
                    elif "bit_rate" in format_info and format_info["bit_rate"].isdigit():
                        # Fallback approximate bitrate from total file size
                        video_bitrate = int(format_info["bit_rate"])

                elif codec_type == "audio":
                    has_audio = True
                    if codec_name not in cls.MP4_COMPATIBLE_AUDIO:
                        mp4_compatible = False

                elif codec_type == "subtitle":
                    has_subtitles = True
                    if codec_name not in cls.MP4_COMPATIBLE_SUBS:
                        mp4_compatible = False

            container = "mp4" if mp4_compatible else "mkv"

            return MediaInfo(
                duration=duration,
                size_bytes=size_bytes,
                video_codec=video_codec,
                width=width,
                height=height,
                fps=fps,
                video_bitrate=video_bitrate,
                streams=streams,
                has_audio=has_audio,
                has_subtitles=has_subtitles,
                recommended_container=container
            )

        except Exception as e:
            print(f"Exception while running FFprobe: {e}")
            return None
