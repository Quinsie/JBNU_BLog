"""기준데이터(reference) — 노선·정류장·polyline. 모델 불필요 → 다음 단위에서 real 교체 예정.

현재: dummy. real 교체 시 `src/common/paths.py` 의 REF_SOURCE_DIR/REF_BUILT_DIR 사용.
"""

from fastapi import APIRouter, Query

from .. import dummy
from ..schemas import RouteSummary, RouteDetail, StopSummary

router = APIRouter(prefix="/v1", tags=["기준데이터(reference)"])


@router.get("/routes", response_model=list[RouteSummary], summary="노선 목록")
def list_routes() -> list[RouteSummary]:
    """전체 노선(stdid 단위) 목록. **현재 dummy.**"""
    return dummy.route_list()


@router.get("/routes/{stdid}", response_model=RouteDetail, summary="노선 상세(정류장 시퀀스 + polyline)")
def get_route(stdid: int) -> RouteDetail:
    """노선의 정류장 순서 + 지도 표시용 경로 vtx. **현재 dummy.**"""
    return dummy.route_detail(stdid)


@router.get("/stops/search", response_model=list[StopSummary], summary="정류장 검색")
def search_stops(q: str = Query(..., description="정류장명 검색어")) -> list[StopSummary]:
    """이름으로 정류장 검색. **현재 dummy.**"""
    return dummy.stop_search(q)


@router.get("/stops/nearby", response_model=list[StopSummary], summary="좌표 인근 정류장")
def nearby_stops(
    lat: float = Query(...), lng: float = Query(...),
    radius_m: int = Query(500, description="검색 반경(m)"),
) -> list[StopSummary]:
    """좌표 주변 정류장. **현재 dummy.**"""
    return dummy.stops_nearby(lat, lng, radius_m)


@router.get("/stops/{stop_id}", response_model=StopSummary, summary="정류장 상세(좌표·경유노선)")
def get_stop(stop_id: int) -> StopSummary:
    """정류장 좌표 + 경유 노선. **현재 dummy.**"""
    return dummy.stop_summary(stop_id)
