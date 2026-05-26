"""수집기 설정. 값은 환경변수로 오버라이드 가능 (.env)."""

import os
import socket

from src.common.paths import (
    RAW_BUS_DIR, RAW_TRAFFIC_DIR, RAW_WEATHER_DIR, RAW_INCIDENT_DIR,
    REF_BUILT_DIR,
)

# ── 버스 위치 (핵심) ─────────────────────────────────
BUS_URL = "https://its.jeonju.go.kr/bis/selectBisRouteLocationList.do"
# 적응형 폴링: 버스 있으면 ACTIVE 주기, 빈 응답이면 IDLE 주기로 백오프.
BUS_ACTIVE_INTERVAL_SEC = float(os.environ.get("BUS_ACTIVE_INTERVAL_SEC", "10"))
BUS_IDLE_INTERVAL_SEC = float(os.environ.get("BUS_IDLE_INTERVAL_SEC", "30"))
# 버스트 방지 핵심: launch 사이 강제 최소 간격(ms). 어떤 경우에도 이보다 촘촘히 안 쏨.
BUS_MIN_GAP_MS = float(os.environ.get("BUS_MIN_GAP_MS", "20"))
BUS_CONCURRENCY = int(os.environ.get("BUS_CONCURRENCY", "50"))   # in-flight 안전망 상한
BUS_HTTP_TIMEOUT = float(os.environ.get("BUS_HTTP_TIMEOUT", "8"))
BUS_DIR = RAW_BUS_DIR
STDID_LIST_PATH = REF_BUILT_DIR / "stdid_list.json"

# (옵션) 시간표 운행창 밖 노선은 폴링 생략. 기본 OFF (적응형 백오프가 idle 을 자동 처리).
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

# ── ITS 아웃바운드 소스 IP (임시 차단 우회용) ────────────
# .73 이 ITS 에 차단됐을 때, 보조 IP(.74)로 내보내기 위한 임시 바인딩.
# 해당 IP 가 로컬에 실제로 붙어있지 않으면(원복/리부팅 후) 자동으로 기본 IP 로 폴백.
ITS_SOURCE_IP = os.environ.get("ITS_SOURCE_IP", "").strip()


def its_local_addr():
    """ITS_SOURCE_IP 가 로컬에 바인딩 가능하면 (ip, 0) 반환, 아니면 None(기본 IP 사용)."""
    if not ITS_SOURCE_IP:
        return None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((ITS_SOURCE_IP, 0))
        s.close()
        return (ITS_SOURCE_IP, 0)
    except OSError:
        return None
