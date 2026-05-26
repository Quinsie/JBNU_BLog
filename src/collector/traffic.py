"""도로 교통혼잡도 수집기. selectTrafVrtxList 1분 주기, raw 통째 저장.

저장: data/raw/traffic/{YYYYMMDD_HHMM}.json  (한 호출 = 한 파일)
"""

import asyncio
import json
import time

import aiohttp

from src.common.clock import minute_key, now_kst, sleep_until_aligned, ts_iso
from src.common.io import write_json_atomic
from src.common.log import get_logger
from .config import (
    ITS_HEADERS, TRAFFIC_BBOX, TRAFFIC_DIR, TRAFFIC_INTERVAL_SEC, TRAFFIC_URL, its_local_addr,
)
from .health import classify_error

log = get_logger("traffic")


async def fetch_once(session: aiohttp.ClientSession, ts) -> dict:
    rec = {"ts": ts_iso(ts)}
    t0 = time.monotonic()
    try:
        async with session.post(
            TRAFFIC_URL, headers=ITS_HEADERS, data=TRAFFIC_BBOX,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as res:
            text = await res.text()
            rec["status"] = res.status
            if res.status != 200:
                rec.update(ok=False, error=f"HTTP_{res.status}", raw=text[:300])
            elif text.lstrip().startswith("<"):
                rec.update(ok=False, error="WAF", raw=text[:200])
            elif text.strip():
                rec.update(ok=True, body=json.loads(text))
            else:
                rec.update(ok=True, body=None)
    except Exception as e:  # noqa: BLE001
        rec.update(ok=False, error=f"{classify_error(e)}:{e}")
    rec["elapsed_ms"] = int(1000 * (time.monotonic() - t0))
    return rec


async def run() -> None:
    log.info(f"traffic 시작: interval={TRAFFIC_INTERVAL_SEC}s")
    connector = aiohttp.TCPConnector(local_addr=its_local_addr())
    async with aiohttp.ClientSession(connector=connector) as session:
        while True:
            ts = await sleep_until_aligned(TRAFFIC_INTERVAL_SEC)
            rec = await fetch_once(session, ts)
            try:
                write_json_atomic(TRAFFIC_DIR / f"{minute_key(ts)}.json", rec)
            except Exception as we:  # noqa: BLE001
                log.error(f"write 실패: {we}")
                continue
            if rec.get("ok") and isinstance(rec.get("body"), dict):
                n = len(rec["body"].get("resultList", []))
                log.info(f"OK {minute_key(ts)} vtx={n} {rec['elapsed_ms']}ms")
            else:
                log.warning(f"실패 {minute_key(ts)} {rec.get('error')}")
