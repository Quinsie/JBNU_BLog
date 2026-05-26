"""버스 실시간 위치 수집기 (핵심).

- selectBisRouteLocationList.do 를 stdid 별로 폴링. raw 응답 통째 저장(빈 응답·실패 포함).
- 저장: data/raw/bus/{stdid}/{YYYYMMDD_HH}.jsonl  (한 줄 = 한 호출)

[적응형 폴링]
- 버스가 있으면(busPosList 비어있지 않음) ACTIVE 주기(기본 10s).
- 빈 응답이면 IDLE 주기(기본 60s)로 백오프 → 운행 안 하는 노선/시간대 부하 급감.
  버스가 다시 잡히면 자동으로 ACTIVE 복귀.

[버스트 절대 금지 — gap 스케줄러]
- 단일 디스패처가 "가장 밀린(overdue) stdid 하나"를 골라 발사하고, 발사 사이에
  반드시 BUS_MIN_GAP_MS 만큼 쉰다. 따라서 아무리 많은 stdid 가 동시에 due 여도
  최대 1/gap 속도로만 나가고 절대 동시 발사(burst)되지 않는다. (IP 차단 방지의 핵심)
- in-flight 는 stdid 당 1개만(중복 발사 방지) + 세마포어로 총량 안전망.
"""

import asyncio
import json
import time

import aiohttp

from src.common.clock import hour_key, now_kst, ts_iso
from src.common.io import append_jsonl
from src.common.log import get_logger
from .config import (
    ACTIVE_POSTROLL_MIN, ACTIVE_PREROLL_MIN, BUS_ACTIVE_INTERVAL_SEC, BUS_CONCURRENCY,
    BUS_DIR, BUS_HTTP_TIMEOUT, BUS_IDLE_INTERVAL_SEC, BUS_MIN_GAP_MS, BUS_URL,
    ITS_HEADERS, STDID_LIST_PATH, USE_TIMETABLE_FILTER, its_local_addr,
)
from .health import TickStats, classify_error

log = get_logger("bus")
stats = TickStats("bus", period_sec=60.0)

_GAP = BUS_MIN_GAP_MS / 1000.0


def load_routes() -> list[dict]:
    with open(STDID_LIST_PATH, encoding="utf-8") as f:
        return json.load(f)["routes"]


def _hhmm_to_min(v) -> int | None:
    if v is None:
        return None
    s = str(v).strip()
    if not s.isdigit():
        return None
    s = s.zfill(4)
    return int(s[:2]) * 60 + int(s[2:])


def active_window(route: dict) -> tuple[int, int] | None:
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
    if s < 0 and mod >= s + 1440:
        return True
    if e >= 1440 and mod <= e - 1440:
        return True
    return False


async def fetch_one(session: aiohttp.ClientSession, stdid: int, ts) -> bool:
    """1회 호출 + 저장. busPosList 에 버스가 있으면 True 반환(없거나 실패면 False)."""
    rec = {"ts": ts_iso(ts), "stdid": stdid}
    t0 = time.monotonic()
    has_bus = False
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
                has_bus = n > 0
                stats.add("active" if has_bus else "idle")
    except Exception as e:  # noqa: BLE001
        kind = classify_error(e)
        rec.update(ok=False, error=f"{kind}:{e}")
        stats.add(kind.lower())

    rec["elapsed_ms"] = int(1000 * (time.monotonic() - t0))
    try:
        # 고빈도 → fsync 생략(flush만). HDD fsync 가 이벤트 루프를 막는다.
        append_jsonl(BUS_DIR / str(stdid) / f"{hour_key(ts)}.jsonl", rec, fsync=False)
    except Exception as we:  # noqa: BLE001
        log.error(f"{stdid} write 실패: {we}")
        stats.add("write_fail")
    return has_bus


async def run() -> None:
    routes = load_routes()
    stdids = [r["stdid"] for r in routes]
    wins = {r["stdid"]: active_window(r) for r in routes}
    log.info(f"bus 시작: stdid={len(stdids)} active={BUS_ACTIVE_INTERVAL_SEC}s "
             f"idle={BUS_IDLE_INTERVAL_SEC}s gap={BUS_MIN_GAP_MS}ms cap={BUS_CONCURRENCY} "
             f"timetable_filter={USE_TIMETABLE_FILTER}")

    sem = asyncio.Semaphore(BUS_CONCURRENCY)
    local_addr = its_local_addr()
    if local_addr:
        log.info(f"ITS 아웃바운드 소스 IP 바인딩: {local_addr[0]}")
    connector = aiohttp.TCPConnector(limit=BUS_CONCURRENCY * 2, ttl_dns_cache=300,
                                     local_addr=local_addr)

    next_due = {s: 0.0 for s in stdids}   # monotonic 기준 다음 폴링 시각 (0 = 즉시)
    inflight: set[int] = set()

    async def fire(session, sid):
        try:
            has_bus = await fetch_one(session, sid, now_kst())
            interval = BUS_ACTIVE_INTERVAL_SEC if has_bus else BUS_IDLE_INTERVAL_SEC
        except Exception as e:  # noqa: BLE001
            log.error(f"{sid} fire 오류: {e}")
            interval = BUS_ACTIVE_INTERVAL_SEC   # 일시 오류는 곧 재시도
        finally:
            next_due[sid] = time.monotonic() + interval
            inflight.discard(sid)
            sem.release()

    async with aiohttp.ClientSession(connector=connector) as session:
        while True:
            now = time.monotonic()
            # 발사 후보: in-flight 아니고 due 지난 것 중 '가장 밀린' 하나
            cand, cand_due = None, None
            soonest = None
            for s in stdids:
                if s in inflight:
                    continue
                d = next_due[s]
                if d <= now:
                    if cand_due is None or d < cand_due:
                        cand, cand_due = s, d
                elif soonest is None or d < soonest:
                    soonest = d

            if USE_TIMETABLE_FILTER and cand is not None and not is_active(wins[cand]):
                # 운행창 밖이면 폴링 생략하고 IDLE 만큼 미룸
                next_due[cand] = now + BUS_IDLE_INTERVAL_SEC
                stats.add("skipped")
                continue

            if cand is None:
                # due 없음 → 가장 이른 시각까지 (gap~1s 범위로) 대기
                wait = (soonest - now) if soonest is not None else _GAP
                await asyncio.sleep(min(max(wait, 0.001), 1.0))
                continue

            await sem.acquire()          # in-flight 총량 안전망
            inflight.add(cand)
            asyncio.create_task(fire(session, cand))
            await asyncio.sleep(_GAP)    # ★ 버스트 방지: 발사 간 최소 간격 강제
