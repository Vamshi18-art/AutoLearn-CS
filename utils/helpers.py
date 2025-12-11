import os, re
from datetime import datetime
from utils.logger import logger

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)
    logger.info("Directory ensured: %s", path)

def sanitize_filename(s: str) -> str:
    return re.sub(r'[\\/*?:"<>| ]', "_", s)

def timestamped_filename(prefix: str, ext: str = "png") -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{ts}.{ext}"
