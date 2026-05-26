"""수집기 통합 진입점.

- bus/traffic/weather/incident 를 동시 비동기 가동.
- 하나가 죽어도 나머지는 살아있고, 죽은 것만 지수백오프 재시작.
- 중복 실행 방지 (flock pidfile). SIGINT/SIGTERM 에 깔끔 종료.

사용: python3 -m src.collector
"""

import asyncio
import fcntl
import os
import signal
import sys

from dotenv import load_dotenv

load_dotenv()  # .env → 환경변수 (config import 전에)

from src.common.log import get_logger          # noqa: E402
from src.common.paths import LOG_DIR, ensure_dirs  # noqa: E402

log = get_logger("main")
_LOCK_PATH = LOG_DIR / "collector.pid"


def acquire_lock():
    """flock 기반 중복 실행 방지. 실패 시 종료."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    f = open(_LOCK_PATH, "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        log.error(f"이미 실행 중 (lock: {_LOCK_PATH}). 종료.")
        sys.exit(1)
    f.write(str(os.getpid()))
    f.flush()
    return f  # 프로세스 살아있는 동안 열어둠


async def supervised(name: str, run_coro):
    backoff = 1.0
    while True:
        try:
            log.info(f"[{name}] 시작")
            await run_coro()
            log.warning(f"[{name}] 정상 종료됨 — {backoff:.0f}s 후 재시작")
        except asyncio.CancelledError:
            log.info(f"[{name}] 취소됨")
            raise
        except Exception as e:  # noqa: BLE001
            log.error(f"[{name}] 죽음: {type(e).__name__}: {e} — {backoff:.0f}s 후 재시작")
        await asyncio.sleep(backoff)
        backoff = min(60.0, backoff * 2.0)


async def main():
    ensure_dirs()
    from . import bus, traffic, weather, incident  # noqa: E402

    log.info("=" * 50)
    log.info("수집기 시작: bus / traffic / weather / incident")

    tasks = [
        asyncio.create_task(supervised("bus", bus.run)),
        asyncio.create_task(supervised("traffic", traffic.run)),
        asyncio.create_task(supervised("weather", weather.run)),
        asyncio.create_task(supervised("incident", incident.run)),
    ]

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            signal.signal(sig, lambda *_: stop.set())

    await stop.wait()
    log.info("종료 시그널 — 모든 수집기 취소")
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    log.info("정상 종료")


if __name__ == "__main__":
    _lock = acquire_lock()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
