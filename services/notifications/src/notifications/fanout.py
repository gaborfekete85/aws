"""Send many emails concurrently with asyncio, within SES limits.

- a **semaphore** bounds how many sends are in flight;
- a **token-bucket rate limiter** bounds how many start per second (SES sandbox: 1/s);
- each blocking boto3 call runs in a worker thread (``asyncio.to_thread``);
- failures are collected, not raised one by one, so every other Attendee still
  gets their email; the caller then fails the SQS record and the retry only
  re-sends to Attendees without a sent-marker.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any


class RateLimiter:
    """Async token bucket: at most ``rate`` acquisitions per second, bursts up to ``burst``."""

    def __init__(
        self,
        rate: float,
        burst: int = 1,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if rate <= 0:
            raise ValueError("rate must be > 0")
        self.rate = rate
        self.capacity = float(burst)
        self.tokens = float(burst)
        self.clock = clock
        self.sleep = sleep
        self.updated = clock()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:  # one waiter refills at a time: fair and simple
            while True:
                now = self.clock()
                self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rate)
                self.updated = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                await self.sleep((1 - self.tokens) / self.rate)


@dataclass
class FanoutResult:
    sent: int = 0
    skipped: int = 0  # already sent on an earlier attempt
    failed: list[tuple[Any, BaseException]] = field(default_factory=list)


class PartialFailure(Exception):
    def __init__(self, result: FanoutResult) -> None:
        super().__init__(f"{len(result.failed)} email(s) failed, {result.sent} sent")
        self.result = result


async def fan_out[T](
    items: Sequence[T],
    send: Callable[[T], bool],
    *,
    max_concurrency: int,
    limiter: RateLimiter,
    on_progress: Callable[[int], None] | None = None,
) -> FanoutResult:
    """Run the blocking ``send(item)`` for every item (True = sent now, False = skipped)."""
    semaphore = asyncio.Semaphore(max_concurrency)
    result = FanoutResult()

    async def one(item: T) -> None:
        async with semaphore:
            await limiter.acquire()
            try:
                sent_now = await asyncio.to_thread(send, item)
            except Exception as error:  # collect; keep sending to everyone else
                result.failed.append((item, error))
                return
            if sent_now:
                result.sent += 1
            else:
                result.skipped += 1
            if on_progress:
                on_progress(result.sent + result.skipped)

    await asyncio.gather(*(one(item) for item in items))
    return result
