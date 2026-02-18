from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar


T = TypeVar("T")


def retry_call(
    fn: Callable[[], T],
    retries: int = 2,
    delay_sec: float = 1.0,
    backoff: float = 1.5,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> T:
    current_delay = delay_sec
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return fn()
        except exceptions as exc:
            last_error = exc
            if attempt >= retries:
                break
            time.sleep(current_delay)
            current_delay *= backoff
    if last_error is None:
        raise RuntimeError("retry_call failed without explicit exception.")
    raise last_error

