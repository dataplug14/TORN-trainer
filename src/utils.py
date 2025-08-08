import asyncio
import os
import random
import sys
from dataclasses import dataclass
from datetime import datetime
from getpass import getpass
from typing import Optional

from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler


def load_env(dotenv_path: Optional[str] = None) -> None:
    load_dotenv(dotenv_path or os.getenv("DOTENV_PATH") or ".env")


def ensure_directory(path: str) -> None:
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)


def setup_logging(log_level: str = "INFO", log_dir: str = "logs") -> logging.Logger:
    ensure_directory(log_dir)
    logger = logging.getLogger("torn_trainer")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    # Avoid duplicate handlers if re-configured
    if logger.handlers:
        return logger

    log_path = os.path.join(log_dir, "trainer.log")
    file_handler = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=5)
    file_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    file_formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    console_handler.setFormatter(file_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


async def safe_sleep(seconds: float) -> None:
    if seconds <= 0:
        await asyncio.sleep(0)
    else:
        await asyncio.sleep(seconds)


def small_jitter(base_seconds: float, jitter_fraction: float = 0.15) -> float:
    # +/- fraction jitter
    delta = base_seconds * jitter_fraction
    return max(0.0, base_seconds + random.uniform(-delta, delta))


def prompt_api_key_and_user_id() -> tuple[str, str]:
    print("Enter Torn configuration (values are not stored unless you place them in .env):")
    api_key = getpass("API key: ")
    user_id = input("User ID: ")
    return api_key.strip(), user_id.strip()


@dataclass
class MonotonicClock:
    last: float = 0.0

    def now(self) -> float:
        return asyncio.get_event_loop().time()


class TokenBucketLimiter:
    """Token bucket limiter with min spacing and jitter.

    - capacity: maximum tokens (per 60s window equivalent)
    - refill_rate: tokens per second
    - min_spacing: minimum time between acquired tokens
    """

    def __init__(
        self,
        capacity: int,
        refill_rate_per_sec: float,
        min_spacing: float = 1.0,
        jitter_fraction: float = 0.15,
    ) -> None:
        self.capacity = max(1, capacity)
        self.tokens = float(self.capacity)
        self.refill_rate_per_sec = max(0.001, refill_rate_per_sec)
        self.min_spacing = max(0.0, min_spacing)
        self.jitter_fraction = jitter_fraction
        self._clock = MonotonicClock()
        self._last_refill = self._clock.now()
        self._last_acquire = 0.0
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = self._clock.now()
        elapsed = now - self._last_refill
        if elapsed <= 0:
            return
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate_per_sec)
        self._last_refill = now

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                self._refill()
                now = self._clock.now()
                spacing_needed = self.min_spacing - (now - self._last_acquire)
                if self.tokens >= 1.0 and spacing_needed <= 0:
                    self.tokens -= 1.0
                    # Enforce jittered spacing after grant
                    self._last_acquire = self._clock.now()
                    break
                # Sleep until either spacing satisfied or tokens refilled
                delay = 0.05
                if spacing_needed > 0:
                    delay = max(delay, small_jitter(spacing_needed, self.jitter_fraction))
                await safe_sleep(delay)


def utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

