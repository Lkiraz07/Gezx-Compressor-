import re
import asyncio
from pathlib import Path
from typing import Callable, Optional, Dict, Any
from media import MediaInfo

class VideoCompressor:
    @staticmethod
    def calculate_adaptive_params(media: MediaInfo) -> Dict[str, Any]:
        """
        Dynamically determine CRF and encoding preset based on resolution, bitrate,
        and frame rate without arbitrarily stripping stream properties.
        """
        res_pixels = media.width * media.height
        
        # Base CRF baseline selection
        if res_pixels >= 3840 * 2160: # 4K
            crf = 26
            preset = "veryfast"
        elif res_pixels >= 1920 * 1080: # 1080p
            crf = 24
            preset = "veryfast"
        elif res_pixels >= 1280 * 720: # 720p
            crf = 23
            preset = "faster"
        else: # Standard definition
            crf = 22
            preset = "faster"

        # Adjust CRF for high frame rates
        if media.fps >= 50:
            crf += 1

        # Bitrate safety adjustments (Avoid re-encoding low-bitrate streams aggressively)
        # Standard bitrates in bps: 1080p high is ~8Mbps, 720p is ~3.5Mbps
        if media.video_bitrate > 0:
            kbps = media.video_bitrate / 1000.0
            if res_pixels >= 1920 * 1080 and kbps < 2500:
                crf -= 2 # Light compression to protect already low bitrate
            elif res_pixels >= 1280 * 720 and kbps < 1200:
                crf -= 2

        # Sanity check CRF values
        crf = max(18, min(32, crf))

        return {
            "crf": crf,
            "preset": preset
        }

    @classmethod
    async def compress(
        cls,
        input_path: Path,
        output_path: Path,
        media: MediaInfo,
        progress_callback: Optional[Callable[[float, float, float], None]] = None,
        cancel_event: Optional[asyncio.Event] = None
    ) -> bool:
        """
        Executes FFmpeg compression with real-time stderr stdout parsing.
        Maintains all audio/subtitle streams (-c:a copy, -c:s copy).
        """
        params = cls.calculate_adaptive_params(media)
        
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel", "info",
            "-i", str(input_path),
            "-map", "0",              # Map all video, audio, subtitle streams
            "-c:v", "libx264",        # Encode video with standard x264
            "-crf", str(params["crf"]),
            "-preset", params["preset"],
            "-c:a", "copy",           # Copy all audio streams as-is
            "-c:s", "copy",           # Copy all subtitle streams as-is
            "-map_metadata", "0",     # Preserve global metadata
            "-map_chapters", "0"      # Preserve chapters
        ]

        # Enable faststart for web/telegram streaming if output container is MP4
        if output_path.suffix.lower() == ".mp4":
            cmd.extend(["-movflags", "+faststart"])

        cmd.append(str(output_path))

        process = None
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Regex pattern to match FFmpeg progress line: time=00:01:23.45
            time_pattern = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")
            speed_pattern = re.compile(r"speed=\s*([\d\.]+)x")

            start_time = asyncio.get_event_loop().time()

            async for line_bytes in process.stderr:
                if cancel_event and cancel_event.is_set():
                    print("Cancel signal detected. Terminating FFmpeg process...")
                    try:
                        process.terminate()
                        await process.wait()
                    except Exception:
                        pass
                    return False

                line = line_bytes.decode('utf-8', errors='ignore')
                time_match = time_pattern.search(line)
                
                if time_match and media.duration > 0:
                    hours, minutes, seconds = map(float, time_match.groups())
                    current_seconds = hours * 3600 + minutes * 60 + seconds
                    percentage = min(100.0, (current_seconds / media.duration) * 100.0)

                    speed = 1.0
                    speed_match = speed_pattern.search(line)
                    if speed_match:
                        try:
                            speed = float(speed_match.group(1))
                        except ValueError:
                            speed = 1.0

                    # Calculate ETA
                    remaining_sec = media.duration - current_seconds
                    eta = remaining_sec / speed if speed > 0 else 0

                    if progress_callback:
                        if asyncio.iscoroutinefunction(progress_callback):
                            await progress_callback(percentage, speed, eta)
                        else:
                            progress_callback(percentage, speed, eta)

            await process.wait()
            return process.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0

        except Exception as e:
            print(f"Exception encountered during FFmpeg execution: {e}")
            if process:
                try:
                    process.kill()
                except Exception:
                    pass
            return False
