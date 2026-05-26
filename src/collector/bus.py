"""버스 실시간 위치 수집기 (핵심).

- selectBisRouteLocationList.do 를 stdid 별 5초 폴링.
- 매칭/필터/이벤트추출 일체 없음. raw 응답 통째로 박는다. 빈 응답·실패도 기록.
- 저장: data/raw/bus/{stdid}/{YYYYMMDD_HH}.jsonl  (한 줄 = 한 호출)
- 부하저감 레버: USE_TIMETABLE_FILTER (기본 OFF = 전체 5초 폴링).
"""

import asyncio
import json
import time

import aiohttp

from src.common.clock import hour_key, now_kst, ts_iso
from src.common.io import append_jsonl
from src.common.log import get_logger
from .config import (
    ACTIVE_POSTROLL_MIN, ACTIVE_PREROLL_MIN, BUS_CONCURRENCY, BUS_DIR,
    BUS_HTTP_TIMEOUT, BUS_INTERVAL_SEC, BUS_URL, ITS_HEADERS,
    STDID_LIST_PATH, USE_TIMETABLE_FILTER,
)
from .health import TickStats, classify_error

log = get_logger("bus")
stats = TickStats("bus", period_sec=60.0)


def load_routes() -> list[dict]:
    with open(STDID_LIST_PATH, encoding="utf-8") as f:
        return json.load(f)["routes"]


def _hhmm_to_min(v) -> int | None:
    """'550'/'2250'/'0550' → 분(자정기준). None 이면 무시."""
    if v is None:
        return None
    s = str(v).strip()
    if not s.isdigit():
        return None
    s = s.zfill(4)
    return int(s[:2]) * 60 + int(s[2:])


def active_window(route: dict) -> tuple[int, int] | None:
    """[first-preroll, last+postroll] 분 구간. None = 항상 active."""
    f = _hhmm_to_min(route.get("first_time"))
    l = _hhmm_to_min(route.get("last_time"))
    if f is None or l is None:
        return None
    return (f - ACTIVE_PREROLL_MIN, l + ACTIVE_POSTROLL_MIN)


def is_active(win: tuple[int, int] | None) -> bool:
    if not USE_TIMETABLE_FILTER or win is None:
        return True
    n = now_kst()
    mod = n.hour * 60 + n.minute
    s, e = win
    if s <= mod <= e:
        return True
    if s < 0 and mod >= s + 1440:        # 새벽 전날 경계
        return True
    if e >= 1440 and mod <= e - 1440:    # 자정 넘김
        return True
    return False


async def fetch_one(session: aiohttp.ClientSession, sem: asyncio.Semaphore,
                    stdid: int, ts) -> None:
    rec = {"ts": ts_iso(ts), "stdid": stdid}
    t0 = time.monotonic()
    try:
        async with sem:
            async with session.post(
                BUS_URL, headers=ITS_HEADERS,
                data={"locale": "ko-kr", "routeId": stdid},
                timeout=aiohttp.ClientTimeout(total=BUS_HTTP_TIMEOUT),
            ) as res:
                text = await res.text()
                rec["status"] = res.status
                if res.status != 200:
                    rec.update(ok=False, error=f"HTTP_{res.status}", raw=text[:300])
                    stats.add(f"http_{res.status}")
                elif text.lstrip().startswith("<"):
                    rec.update(ok=False, error="WAF", raw=text[:200])
                    stats.add("waf")
                elif not text.strip():
                    rec.update(ok=True, body=None)
                    stats.add("empty_body")
                else:
                    body = json.loads(text)
                    rec.update(ok=True, body=body)
                    n = len(body.get("busPosList", [])) if isinstance(body, dict) else 0
                    stats.add("active" if n else "idle")
    except Exception as e:  # noqa: BLE001
        kind = classify_error(e)
        rec.update(ok=False, error=f"{kind}:{e}")
        stats.add(kind.lower())

    rec["elapsed_ms"] = int(1000 * (time.monotonic() - t0))
    try:
        append_jsonl(BUS_DIR / str(stdid) / f"{hour_key(ts)}.jsonl", rec)
    except Exception as we:  # noqa: BLE001
        log.error(f"{stdid} write 실패: {we}")
        stats.add("write_fail")


async def stdid_loop(session, sem, route: dict, offset: float) -> None:
    stdid = route["stdid"]
    win = active_window(route)
    await asyncio.sleep(offset)
    while True:
        t0 = time.monotonic()
        if is_active(win):
            try:
                await fetch_one(session, sem, stdid, now_kst())
            except Exception as e:  # noqa: BLE001
                log.error(f"{stdid} loop 오류: {e}")
        else:
            stats.add("skipped")
        await asyncio.sleep(max(0.0, BUS_INTERVAL_SEC - (time.monotonic() - t0)))


async def run() -> None:
    routes = load_routes()
    log.info(f"bus 시작: stdid={len(routes)} interval={BUS_INTERVAL_SEC}s "
             f"concurrency={BUS_CONCURRENCY} timetable_filter={USE_TIMETABLE_FILTER}")
    connector = aiohttp.TCPConnector(limit=BUS_CONCURRENCY * 2, ttl_dns_cache=300)
    sem = asyncio.Semaphore(BUS_CONCURRENCY)
    n = len(routes)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            asyncio.create_task(stdid_loop(session, sem, r, (i / n) * BUS_INTERVAL_SEC))
            for i, r in enumerate(routes)
        ]
        await asyncio.gather(*tasks)
