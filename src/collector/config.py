"""수집기 설정. 값은 환경변수로 오버라이드 가능 (.env)."""

import os

from src.common.paths import (
    RAW_BUS_DIR, RAW_TRAFFIC_DIR, RAW_WEATHER_DIR, RAW_INCIDENT_DIR,
    REF_BUILT_DIR,
)

# ── 버스 위치 (핵심) ─────────────────────────────────
BUS_URL = "https://its.jeonju.go.kr/bis/selectBisRouteLocationList.do"
BUS_INTERVAL_SEC = int(os.environ.get("BUS_INTERVAL_SEC", "5"))
BUS_CONCURRENCY = int(os.environ.get("BUS_CONCURRENCY", "100"))
BUS_HTTP_TIMEOUT = float(os.environ.get("BUS_HTTP_TIMEOUT", "4.5"))
BUS_DIR = RAW_BUS_DIR
STDID_LIST_PATH = REF_BUILT_DIR / "stdid_list.json"

# v1 부하저감 레버: 시간표 active 구간만 폴링 (기본 OFF = 전체 5초)
USE_TIMETABLE_FILTER = os.environ.get("USE_TIMETABLE_FILTER", "0") == "1"
ACTIVE_PREROLL_MIN = int(os.environ.get("ACTIVE_PREROLL_MIN", "10"))
ACTIVE_POSTROLL_MIN = int(os.environ.get("ACTIVE_POSTROLL_MIN", "140"))

# ── 도로 교통혼잡도 ──────────────────────────────────
TRAFFIC_URL = "https://its.jeonju.go.kr/atms/selectTrafVrtxList.do"
TRAFFIC_INTERVAL_SEC = int(os.environ.get("TRAFFIC_INTERVAL_SEC", "60"))
TRAFFIC_DIR = RAW_TRAFFIC_DIR
TRAFFIC_BBOX = {
    "minlat": 35.62887212891432, "maxlat": 36.010764597679966,
    "minlng": 126.81920706935077, "maxlng": 127.39975969071274,
    "link_lv": 2, "levl": 5,
}

# ── 사고/공사 (WAF 차단 → URL 설정 시에만 가동) ──────
INCIDENT_URL = os.environ.get("INCIDENT_URL", "").strip()
INCIDENT_PAYLOAD_JSON = os.environ.get("INCIDENT_PAYLOAD_JSON", "").strip()
INCIDENT_INTERVAL_SEC = int(os.environ.get("INCIDENT_INTERVAL_SEC", "300"))
INCIDENT_DIR = RAW_INCIDENT_DIR

# ── 날씨 (기상청, 전격자) ────────────────────────────
KMA_KEY = os.environ.get("KMA_API_KEY", "").strip()
WEATHER_DIR = RAW_WEATHER_DIR
GRID_MAP_PATH = REF_BUILT_DIR / "nx_ny_coords.json"
WEATHER_PER_REQ_SLEEP = float(os.environ.get("WEATHER_PER_REQ_SLEEP", "0.2"))

KMA = {
    "ncst":   "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst",
    "ultra":  "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtFcst",
    "vilage": "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst",
    "midland": "https://apis.data.go.kr/1360000/MidFcstInfoService/getMidLandFcst",
    "midta":   "https://apis.data.go.kr/1360000/MidFcstInfoService/getMidTa",
}
# 중기예보 지역코드: 전북 육상 / 전주 기온
MID_LAND_REGID = os.environ.get("MID_LAND_REGID", "11F10000")
MID_TA_REGID = os.environ.get("MID_TA_REGID", "11F10201")
VILAGE_BASE_TIMES = ["0200", "0500", "0800", "1100", "1400", "1700", "2000", "2300"]
MID_BASE_TIMES = ["0600", "1800"]

ITS_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
}
