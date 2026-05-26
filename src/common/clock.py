"""KST 시각 유틸 + 정렬 sleep. (고정 +09:00, DST 없음)"""

import asyncio
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))


def now_kst() -> datetime:
    return datetime.now(KST)


def ts_iso(dt: datetime | None = None) -> str:
    """레코드 ts: 2026-05-26T05:30:11+09:00"""
    return (dt or now_kst()).isoformat(timespec="seconds")


def hour_key(dt: datetime | None = None) -> str:
    return (dt or now_kst()).strftime("%Y%m%d_%H")


def minute_key(dt: datetime | None = None) -> str:
    return (dt or now_kst()).strftime("%Y%m%d_%H%M")


def date_key(dt: datetime | None = None) -> str:
    return (dt or now_kst()).strftime("%Y%m%d")


def next_aligned(interval_sec: int, base: datetime | None = None) -> datetime:
    """다음 interval 정렬 시각 (예 interval=5, 09:00:07 → 09:00:10)."""
    base = base or now_kst()
    epoch = int(base.timestamp())
    nxt = ((epoch // interval_sec) + 1) * interval_sec
    return datetime.fromtimestamp(nxt, tz=KST)


async def sleep_until_aligned(interval_sec: int) -> datetime:
    """다음 정렬 시각까지 비동기 sleep, 그 시각 반환."""
    target = next_aligned(interval_sec)
    delay = (target - now_kst()).total_seconds()
    if delay > 0:
        await asyncio.sleep(delay)
    return target
