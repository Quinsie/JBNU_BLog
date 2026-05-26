"""파일 기록 유틸. 강제종료/전력손실에 안전하게."""

import json
import os
import threading
from pathlib import Path
from typing import Any

_locks: dict[str, threading.Lock] = {}
_guard = threading.Lock()


def _lock_for(path: str) -> threading.Lock:
    with _guard:
        lk = _locks.get(path)
        if lk is None:
            lk = threading.Lock()
            _locks[path] = lk
        return lk


def append_jsonl(path: str | Path, obj: Any) -> None:
    """JSONL 한 줄 append + flush + fsync. 한 줄 = 한 호출 결과."""
    path = str(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    line = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    with _lock_for(path):
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())


def write_json_atomic(path: str | Path, obj: Any) -> None:
    """tmp 파일에 쓰고 rename → 부분 기록 방지."""
    path = str(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def file_exists_nonempty(path: str | Path) -> bool:
    try:
        return os.path.getsize(path) > 0
    except OSError:
        return False
