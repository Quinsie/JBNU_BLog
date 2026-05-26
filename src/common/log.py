"""통합 로거. 모듈별 일자회전 파일 + 콘솔, KST 타임스탬프."""

import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime

from .clock import KST
from .paths import LOG_DIR

_loggers: dict[str, logging.Logger] = {}


class _KSTFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=KST)
        return dt.strftime(datefmt or "%Y-%m-%d %H:%M:%S")


def get_logger(name: str) -> logging.Logger:
    if name in _loggers:
        return _loggers[name]
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    fmt = _KSTFormatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s")

    fh = TimedRotatingFileHandler(
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
