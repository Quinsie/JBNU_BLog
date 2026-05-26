"""사고/공사 수집기. WAF 차단 상태라 INCIDENT_URL 설정 시에만 가동 (없으면 idle).

저장: data/raw/incident/{YYYYMMDD_HHMM}.json
"""

import asyncio
import json
import time

import aiohttp

from src.common.clock import minute_key, sleep_until_aligned, ts_iso
from src.common.io import write_json_atomic
from src.common.log import get_logger
from .config import (
    INCIDENT_DIR, INCIDENT_INTERVAL_SEC, INCIDENT_PAYLOAD_JSON, INCIDENT_URL, ITS_HEADERS,
)
from .health import classify_error

log = get_logger("incident")


def _payload() -> dict:
    if not INCIDENT_PAYLOAD_JSON:
        return {}
    try:
        d = json.loads(INCIDENT_PAYLOAD_JSON)
        return d if isinstance(d, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


async def fetch_once(session, payload, ts) -> dict:
    rec = {"ts": ts_iso(ts)}
    t0 = time.monotonic()
    try:
        async with session.post(
            INCIDENT_URL, headers=ITS_HEADERS, data=payload,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as res:
            text = await res.text()
            rec["status"] = res.status
            if res.status != 200:
                rec.update(ok=False, error=f"HTTP_{res.status}", raw=text[:300])
            elif text.lstrip().startswith("<"):
                rec.update(ok=False, error="WAF", raw=text[:300])
            elif text.strip():
                rec.update(ok=True, body=json.loads(text))
            else:
                rec.update(ok=True, body=None)
    except Exception as e:  # noqa: BLE001
        rec.update(ok=False, error=f"{classify_error(e)}:{e}")
    rec["elapsed_ms"] = int(1000 * (time.monotonic() - t0))
    return rec


async def run() -> None:
    if not INCIDENT_URL:
        log.warning("INCIDENT_URL 미설정 — incident 수집기 idle. (WAF 우회는 v1)")
        while True:
            await asyncio.sleep(3600)
    payload = _payload()
    log.info(f"incident 시작: url={INCIDENT_URL} interval={INCIDENT_INTERVAL_SEC}s")
    async with aiohttp.ClientSession() as session:
        while True:
            ts = await sleep_until_aligned(INCIDENT_INTERVAL_SEC)
            rec = await fetch_once(session, payload, ts)
            try:
                write_json_atomic(INCIDENT_DIR / f"{minute_key(ts)}.json", rec)
            except Exception as we:  # noqa: BLE001
                log.error(f"write 실패: {we}")
