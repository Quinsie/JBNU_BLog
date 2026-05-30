"""날씨(weather) — 수집 중인 실황 + 단기예보. 모델 불필요 → 다음 단위에서 real 교체.

real 교체 시 좌표→KMA 격자(nx,ny) 변환 후 RAW_WEATHER_DIR 최신 수집분 서빙.
"""

from fastapi import APIRouter, Query

from .. import dummy
from ..schemas import WeatherResponse

router = APIRouter(prefix="/v1", tags=["날씨(weather)"])


@router.get("/weather", response_model=WeatherResponse, summary="현재 날씨 + 단기예보")
def get_weather(lat: float = Query(...), lng: float = Query(...)) -> WeatherResponse:
    """좌표 기준 현재 날씨 + 단기예보(시간별). **현재 dummy** → 수집 데이터로 교체 예정."""
    return dummy.weather(lat, lng)
