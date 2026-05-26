"""수집기 건강 모니터링: 에러 분류 + 주기적 집계 로그."""

import asyncio
import json as _json
import time
from collections import defaultdict

from src.common.log import get_logger


def classify_error(exc: BaseException) -> str:
    name = type(exc).__name__
    try:
        import aiohttp
        if isinstance(exc, aiohttp.ClientResponseError):
            return f"HTTP_{exc.status}"
        if isinstance(exc, aiohttp.ClientConnectorError):
            return "CONN_ERROR"
        if isinstance(exc, aiohttp.ServerDisconnectedError):
            return "SERVER_DISCONNECTED"
        if isinstance(exc, aiohttp.ClientPayloadError):
            return "PAYLOAD_ERROR"
        if isinstance(exc, aiohttp.ClientError):
            return f"CLIENT_{name}"
    except ImportError:
        pass
    if isinstance(exc, asyncio.TimeoutError) or name == "TimeoutError":
        return "TIMEOUT"
    if isinstance(exc, _json.JSONDecodeError):
        return "JSON_DECODE"
    if isinstance(exc, OSError):
        return f"OS_{name}"
    return name


class TickStats:
    """주기적으로 종류별 카운트를 한 줄 요약 로그로 flush."""

    def __init__(self, source: str, period_sec: float = 60.0) -> None:
        self.source = source
        self.period = period_sec
        self.counts: dict[str, int] = defaultdict(int)
        self.last = time.monotonic()
        self.log = get_logger(source)

    def add(self, kind: str, n: int = 1) -> None:
        self.counts[kind] += n
        if time.monotonic() - self.last >= self.period:
            self.flush()

    def flush(self) -> None:
        if not self.counts:
            self.last = time.monotonic()
            return
        summary = " ".join(f"{k}={v}" for k, v in sorted(self.counts.items()))
        self.log.info(f"[{int(self.period)}s] {summary}")
        self.counts.clear()
        self.last = time.monotonic()
