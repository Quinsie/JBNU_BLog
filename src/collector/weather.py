"""기상청 날씨 수집기 (전격자).

4종을 각자 주기로 수집, 격자(43개)를 순회해 한 base 당 한 파일로 저장:
  realtime/      getUltraSrtNcst   초단기실황 (매시)
  shortForecast/ getUltraSrtFcst   초단기예보 (매시)
  midForecast/   getVilageFcst     단기예보   (발표 8회/일)
  longForecast/  getMidLandFcst+getMidTa  중기예보 (발표 2회/일, 격자무관 지역코드)

저장: data/raw/weather/{종류}/{YYYYMMDD_HH}.json   (이미 있으면 skip)
"""

import asyncio
import json
import time
from datetime import datetime, timedelta

import aiohttp

from src.common.clock import KST, hour_key, now_kst, ts_iso
from src.common.io import file_exists_nonempty, write_json_atomic
from src.common.log import get_logger
from .config import (
    GRID_MAP_PATH, KMA, KMA_KEY, MID_BASE_TIMES, MID_LAND_REGID, MID_TA_REGID,
    VILAGE_BASE_TIMES, WEATHER_DIR, WEATHER_PER_REQ_SLEEP,
)
from .health import classify_error

log = get_logger("weather")


def load_grids() -> list[tuple[int, int]]:
    d = json.load(open(GRID_MAP_PATH, encoding="utf-8"))["grids"]
    return [(g["nx"], g["ny"]) for g in d.values()]


async def kma_get(session, url, params) -> dict:
    rec = {"ts": ts_iso(), "params": {k: v for k, v in params.items() if k != "serviceKey"}}
    t0 = time.monotonic()
    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as res:
            text = await res.text()
            rec["status"] = res.status
            if res.status == 200 and text.strip():
                try:
                    rec.update(ok=True, body=json.loads(text))
                except Exception as je:  # noqa: BLE001
                    rec.update(ok=False, error=f"JSON_DECODE:{je}", raw=text[:500])
            else:
                rec.update(ok=False, error=f"HTTP_{res.status}", raw=text[:300])
    except Exception as e:  # noqa: BLE001
        rec.update(ok=False, error=f"{classify_error(e)}:{e}")
    rec["elapsed_ms"] = int(1000 * (time.monotonic() - t0))
    return rec


async def collect_grids(session, url, base_date, base_time, grids) -> dict:
    out = {"base_date": base_date, "base_time": base_time, "grids": {}}
    for nx, ny in grids:
        params = {"serviceKey": KMA_KEY, "pageNo": 1, "numOfRows": 1000, "dataType": "JSON",
                  "base_date": base_date, "base_time": base_time, "nx": nx, "ny": ny}
        out["grids"][f"{nx}_{ny}"] = await kma_get(session, url, params)
        await asyncio.sleep(WEATHER_PER_REQ_SLEEP)
    return out


# ── base 시각 계산 ───────────────────────────────────
def ncst_base(now):
    b = now if now.minute >= 40 else now - timedelta(hours=1)
    b = b.replace(minute=0)
    return b.strftime("%Y%m%d"), b.strftime("%H00")


def ultra_base(now):
    b = now if now.minute >= 45 else now - timedelta(hours=1)
    b = b.replace(minute=30)
    return b.strftime("%Y%m%d"), b.strftime("%H30")


def _pick_base(now, base_times, avail_min):
    """발표시각 목록 중 (now - avail_min) 이전 최신 발표분."""
    th = now.replace(second=0, microsecond=0)
    today, yest = now.strftime("%Y%m%d"), (now - timedelta(days=1)).strftime("%Y%m%d")
    chosen = None
    for d in (yest, today):
        for t in base_times:
            bt = datetime.strptime(d + t, "%Y%m%d%H%M").replace(tzinfo=KST)
            if bt + timedelta(minutes=avail_min) <= th:
                chosen = (d, t)
    return chosen or (yest, base_times[-1])


# ── 주기 작업 ────────────────────────────────────────
async def _periodic(name, subdir, interval, do):
    save_dir = WEATHER_DIR / subdir
    log.info(f"weather/{subdir} 시작: interval={int(interval)}s")
    while True:
        t0 = time.monotonic()
        try:
            await do(save_dir)
        except Exception as e:  # noqa: BLE001
            log.error(f"weather/{subdir}: {classify_error(e)}:{e}")
        await asyncio.sleep(max(1.0, interval - (time.monotonic() - t0)))


def _make_grid_job(session, grids, url, api_name, base_fn):
    async def job(save_dir):
        now = now_kst()
        path = save_dir / f"{hour_key(now)}.json"
        if file_exists_nonempty(path):
            return
        bd, bt = base_fn(now)
        out = await collect_grids(session, url, bd, bt, grids)
        out.update(ts=ts_iso(now), api=api_name)
        write_json_atomic(path, out)
        oks = sum(1 for g in out["grids"].values() if g.get("ok"))
        log.info(f"{save_dir.name} {hour_key(now)} base={bd}_{bt} grids={oks}/{len(grids)}")
    return job


def _make_long_job(session):
    async def job(save_dir):
        now = now_kst()
        bd, bt = _pick_base(now, MID_BASE_TIMES, 10)
        path = save_dir / f"{bd}_{bt[:2]}.json"
        if file_exists_nonempty(path):
            return
        tmfc = f"{bd}{bt}"
        base = {"serviceKey": KMA_KEY, "pageNo": 1, "numOfRows": 10, "dataType": "JSON", "tmFc": tmfc}
        land = await kma_get(session, KMA["midland"], {**base, "regId": MID_LAND_REGID})
        await asyncio.sleep(WEATHER_PER_REQ_SLEEP)
        ta = await kma_get(session, KMA["midta"], {**base, "regId": MID_TA_REGID})
        write_json_atomic(path, {"ts": ts_iso(now), "tmFc": tmfc, "land": land, "ta": ta})
        log.info(f"longForecast {bd}_{bt} land={land.get('ok')} ta={ta.get('ok')}")
    return job


async def run() -> None:
    if not KMA_KEY:
        log.error("KMA_API_KEY 미설정 — weather 수집기 종료")
        return
    grids = load_grids()
    log.info(f"weather 시작: 격자 {len(grids)}개")
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        await asyncio.gather(
            _periodic("realtime", "realtime", 3600,
                      _make_grid_job(session, grids, KMA["ncst"], "getUltraSrtNcst", ncst_base)),
            _periodic("short", "shortForecast", 3600,
                      _make_grid_job(session, grids, KMA["ultra"], "getUltraSrtFcst", ultra_base)),
            _periodic("vilage", "midForecast", 1800,
                      _make_grid_job(session, grids, KMA["vilage"], "getVilageFcst",
                                     lambda n: _pick_base(n, VILAGE_BASE_TIMES, 15))),
            _periodic("long", "longForecast", 1800, _make_long_job(session)),
        )
