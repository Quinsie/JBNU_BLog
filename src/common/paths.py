"""경로 단일 해석 지점.

코드 어디에도 절대경로(`/mnt/data1` 등)를 박지 않는다. 모든 경로는 이 파일에서만
정의하고, 머신별 차이는 환경변수 + 심볼릭 링크로 흡수한다.

- 기본값: 리포 루트의 `data/` 하위. (아무 데서 클론해도 그대로 동작)
- 서버에서 raw 만 다른 디스크(HDD)에 두려면: `data/raw` 를 심볼릭 링크로 걸거나
  환경변수 `BLOG_RAW_DIR` 를 지정. (자세한 건 docs/SETUP.md)

환경변수:
  BLOG_DATA_ROOT  data/ 위치 자체를 옮길 때 (기본: <repo>/data)
  BLOG_RAW_DIR    raw 만 별도 위치로 (기본: <DATA_ROOT>/raw)
"""

import os
from pathlib import Path

# src/common/paths.py → parents[2] == 리포 루트
REPO_ROOT = Path(__file__).resolve().parents[2]

DATA_ROOT = Path(os.environ.get("BLOG_DATA_ROOT", REPO_ROOT / "data"))

# ── 정적 기준 데이터 (git 추적) ──────────────────────
REFERENCE_DIR = DATA_ROOT / "reference"
REF_SOURCE_DIR = REFERENCE_DIR / "source"   # API 에서 받은 정적 원본
REF_BUILT_DIR = REFERENCE_DIR / "built"     # 후처리로 만든 참조물 (route_nodes 등)

# ── 수집 원천 로그 (고용량, HDD, gitignore) ──────────
RAW_DIR = Path(os.environ.get("BLOG_RAW_DIR", DATA_ROOT / "raw"))
RAW_BUS_DIR = RAW_DIR / "bus"
RAW_TRAFFIC_DIR = RAW_DIR / "traffic"
RAW_WEATHER_DIR = RAW_DIR / "weather"
RAW_INCIDENT_DIR = RAW_DIR / "incident"

# ── 파이프라인 단계 산출물 (재생성 가능, gitignore) ──
INTERIM_DIR = DATA_ROOT / "interim"
FEATURES_DIR = DATA_ROOT / "features"
MODELS_DIR = DATA_ROOT / "models"
PREDICTIONS_DIR = DATA_ROOT / "predictions"

# ── 로그 ─────────────────────────────────────────────
LOG_DIR = Path(os.environ.get("BLOG_LOG_DIR", REPO_ROOT / "logs"))

_ALL_DIRS = [
    REF_SOURCE_DIR, REF_BUILT_DIR,
    RAW_BUS_DIR, RAW_TRAFFIC_DIR, RAW_WEATHER_DIR, RAW_INCIDENT_DIR,
    INTERIM_DIR, FEATURES_DIR, MODELS_DIR, PREDICTIONS_DIR,
    LOG_DIR,
]


def ensure_dirs() -> None:
    """필요한 디렉토리를 모두 생성 (이미 있으면 통과)."""
    for p in _ALL_DIRS:
        p.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    print(f"REPO_ROOT   = {REPO_ROOT}")
    print(f"DATA_ROOT   = {DATA_ROOT}")
    print(f"RAW_DIR     = {RAW_DIR}  (symlink? {RAW_DIR.is_symlink()})")
    print(f"REFERENCE   = {REFERENCE_DIR}")
    print(f"LOG_DIR     = {LOG_DIR}")
