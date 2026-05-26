"""버스 실시간 위치 수집기 (핵심).

- selectBisRouteLocationList.do 를 전 stdid 5초 주기 폴링.
- 매칭/필터/이벤트추출 일체 없음. raw 응답 통째로 박는다. 빈 응답·실패도 기록.
- 저장: data/raw/bus/{stdid}/{YYYYMMDD_HH}.jsonl  (한 줄 = 한 호출)

[핵심 설계 — 균등 페이싱]
446개를 한꺼번에 쏘면(버스트) 서버가 백로그·throttle 로 무너진다(ok 88%, 19s 지연).
대신 5초 윈도 안에서 dt=5/N(≈11ms) 간격으로 고르게 흘려보내면 동시연결 ~6,
응답 ~15ms, ok 100% 로 446개 전부 5초 해상도 달성. (실측 검증)
세마포어는 서버 hiccup 시 백프레셔용 안전망일 뿐 평상시엔 안 걸린다.

- 부하저감 레버: USE_TIMETABLE_FILTER (기본 OFF). 운행시간 밖 노선 폴링 생략.
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


async def fetch_one(session: aiohttp.ClientSession, stdid: int, ts) -> None:
    rec = {"ts": ts_iso(ts), "stdid": stdid}
    t0 = time.monotonic()
    try:
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
        # 고빈도(89건/s) → fsync 생략(flush만). HDD fsync 가 이벤트 루프를 막는다.
        append_jsonl(BUS_DIR / str(stdid) / f"{hour_key(ts)}.jsonl", rec, fsync=False)
    except Exception as we:  # noqa: BLE001
        log.error(f"{stdid} write 실패: {we}")
        stats.add("write_fail")


async def run() -> None:
    routes = load_routes()
    n = len(routes)
    dt = BUS_INTERVAL_SEC / n  # 균등 페이싱 간격 (≈11ms)
    log.info(f"bus 시작: stdid={n} interval={BUS_INTERVAL_SEC}s pacing={dt*1000:.1f}ms "
             f"safety_cap={BUS_CONCURRENCY} timetable_filter={USE_TIMETABLE_FILTER}")

    sem = asyncio.Semaphore(BUS_CONCURRENCY)   # 평상시 안 걸림. 서버 hiccup 시 백프레셔.
    connector = aiohttp.TCPConnector(limit=BUS_CONCURRENCY * 2, ttl_dns_cache=300)

    wins = {r["stdid"]: active_window(r) for r in routes}

    async def fire(stdid, ts):
        try:
            await fetch_one(session, stdid, ts)
        finally:
            sem.release()

    async with aiohttp.ClientSession(connector=connector) as session:
        while True:
            cycle = time.monotonic()
            for r in routes:
                sid = r["stdid"]
                if is_active(wins[sid]):
                    await sem.acquire()           # 안전망 + 백프레셔 (평상시 즉시 통과)
                    asyncio.create_task(fire(sid, now_kst()))
                else:
                    stats.add("skipped")
                await asyncio.sleep(dt)            # 균등 페이싱
            # 남은 윈도 소진 (페이싱이 윈도를 다 못 채운 경우)
            await asyncio.sleep(max(0.0, BUS_INTERVAL_SEC - (time.monotonic() - cycle)))
