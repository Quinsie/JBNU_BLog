"""통합 로거. 모듈별 일자회전 파일 + 콘솔, KST 타임스탬프.

회전 시점·suffix 모두 KST(+09:00) 기준 — 시스템 TZ 무관.
(표준 TimedRotatingFileHandler 는 시스템 localtime 의존이라 TZ=UTC 환경에선 KST 09:00 에 회전했음.)
"""

import logging
import os
import time
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime

from .clock import KST
from .paths import LOG_DIR

_loggers: dict[str, logging.Logger] = {}
_KST_OFFSET_SEC = 9 * 3600


class _KSTFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=KST)
        return dt.strftime(datefmt or "%Y-%m-%d %H:%M:%S")


class _KSTMidnightRotatingFileHandler(TimedRotatingFileHandler):
    """KST 자정에 회전. 회전된 파일 suffix 도 KST 일자. 시스템 TZ 무관."""

    def computeRollover(self, currentTime: float) -> int:
        t_kst = currentTime + _KST_OFFSET_SEC
        next_kst_midnight = (int(t_kst) // 86400 + 1) * 86400
        return next_kst_midnight - _KST_OFFSET_SEC

    def doRollover(self):
        if self.stream:
            self.stream.close()
            self.stream = None
        # 직전 KST 자정의 KST 일자를 suffix 로
        t_prev = self.rolloverAt - self.interval
        suffix = time.strftime(self.suffix, time.gmtime(t_prev + _KST_OFFSET_SEC))
        dfn = self.rotation_filename(self.baseFilename + "." + suffix)
        if os.path.exists(dfn):
            os.remove(dfn)
        self.rotate(self.baseFilename, dfn)
        if self.backupCount > 0:
            for s in self.getFilesToDelete():
                os.remove(s)
        if not self.delay:
            self.stream = self._open()
        new_rollover = self.computeRollover(int(time.time()))
        while new_rollover <= int(time.time()):
            new_rollover += self.interval
        self.rolloverAt = new_rollover


def get_logger(name: str) -> logging.Logger:
    if name in _loggers:
        return _loggers[name]
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    fmt = _KSTFormatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s")

    fh = _KSTMidnightRotatingFileHandler(
        LOG_DIR / f"{name}.log", when="midnight", backupCount=30, encoding="utf-8"
    )
    fh.suffix = "%Y%m%d"
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    _loggers[name] = logger
    return logger
