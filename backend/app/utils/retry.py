import asyncio
import logging
from functools import wraps
from typing import Type, Tuple

logger = logging.getLogger(__name__)


async def async_retry(
    coro,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 8.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    service_name: str = "unknown",
):
    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await coro
        except exceptions as e:
            last_exc = e
            if attempt < max_attempts:
                delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                logger.warning(f"{service_name} attempt {attempt}/{max_attempts} failed: {e}. Retrying in {delay}s...")
                await asyncio.sleep(delay)
            else:
                logger.error(f"{service_name} failed after {max_attempts} attempts: {e}")
    raise last_exc