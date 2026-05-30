"""날씨(weather) — **real**: 수집 중인 실황(초단기실황) + 단기예보(초단기예보).

좌표→KMA 격자(src/common/grid) 변환 후 RAW_WEATHER_DIR 최신 수집분 서빙.
실황엔 SKY 없어 예보 첫 항목으로 보강.
"""

from fastapi import APIRouter, Query

from .. import store
from ..schemas import WeatherResponse, WeatherNow, WeatherForecastItem, Source

router = APIRouter(prefix="/v1", tags=["날씨(weather)"])


@router.get("/weather", response_model=WeatherResponse, summary="현재 날씨 + 단기예보")
def get_weather(lat: float = Query(...), lng: float = Query(...)) -> WeatherResponse:
    """좌표 기준 현재 날씨 + 단기예보(시간별)."""
    w = store.weather(lat, lng)
    return WeatherResponse(
        now=WeatherNow(**w["now"], source=Source.reference),
        forecast=[WeatherForecastItem(**f) for f in w["forecast"]],
    )
