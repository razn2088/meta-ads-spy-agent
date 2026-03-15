import asyncio
import random

from config.settings import DELAY_MIN, DELAY_MAX


async def random_delay(min_s: float = DELAY_MIN, max_s: float = DELAY_MAX) -> None:
    delay = random.uniform(min_s, max_s)
    await asyncio.sleep(delay)
