hereimport os
import sys
from pathlib import Path

class Config:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()
    API_ID: int = int(os.getenv("API_ID", "0"))
    API_HASH: str = os.getenv("API_HASH", "").strip()
    
    # Working Directory Configuration
    WORK_DIR: Path = Path(os.getenv("WORK_DIR", "/tmp/fast-video-compressor"))
    
    # Render Specific Port
    PORT: int = int(os.getenv("PORT", "8080"))

    @classmethod
    def validate(cls):
        missing = []
        if not cls.BOT_TOKEN:
            missing.append("BOT_TOKEN")
        if not cls.API_ID:
            missing.append("API_ID")
        if not cls.API_HASH:
            missing.append("API_HASH")
            
        if missing:
            print(f"CRITICAL ERROR: Missing required environment variables: {', '.join(missing)}", file=sys.stderr)
            sys.exit(1)
            
        # Ensure temporary work directory exists
        cls.WORK_DIR.mkdir(parents=True, exist_ok=True)

# Run validation on import
Config.validate()
