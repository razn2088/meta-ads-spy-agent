from datetime import datetime
from pathlib import Path

from config.settings import SCREENSHOTS_DIR
from utils.logger import log


async def save_error_screenshot(page, label: str) -> Path:
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{label}_{timestamp}.png"
    filepath = SCREENSHOTS_DIR / filename
    await page.screenshot(path=str(filepath), full_page=True)
    log.info(f"Error screenshot saved: {filepath}")
    return filepath
