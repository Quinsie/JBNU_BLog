"""기준데이터(reference) — 노선·정류장·polyline. **real**(reference 파일 서빙).

데이터 출처: src/common/paths.py REF_BUILT_DIR(stdid_list) · REF_SOURCE_DIR(stops·vtx).
"""

from fastapi import APIRouter, HTTPException, Query

from .. import store
from ..schemas import (RouteSummary, RouteDetail, StopSummary, StopInRoute, LatLng,
                       DepartureList, Source)

router = APIRouter(prefix="/v1", tags=["기준데이터(reference)"])


@router.get("/routes", response_model=list[RouteSummary], summary="노선 목록")
def list_routes() -> list[RouteSummary]:
    """전체 노선(stdid 단위) 목록."""
    return [RouteSummary(stdid=r["stdid"], brt_no=r.get("brt_no"), subid=r.get("subid"),
                         direction=r.get("direction"), start_name=r.get("start_name"),
                         end_name=r.get("end_name"), first_time=r.get("first_time"),
                         last_time=r.get("last_time")) for r in store.routes()]


@router.get("/routes/{stdid}", response_model=RouteDetail, summary="노선 상세(정류장 시퀀스 + polyline)")
def get_route(stdid: int) -> RouteDetail:
    """노선의 정류장 순서 + 지도 표시용 경로 vtx."""
    d = store.route_detail(stdid)
    if d is None:
        raise HTTPException(404, f"노선 {stdid} 없음")
    return RouteDetail(
        stdid=d["stdid"], brt_no=d["brt_no"],
        stops=[StopInRoute(**s) for s in d["stops"]],
        polyline=[LatLng(**p) for p in d["polyline"]],
        source=Source.reference,
    )


@router.get("/routes/{stdid}/departures", response_model=DepartureList, summary="노선 발차슬롯 목록")
def route_departures(stdid: int, daytype: str | None = Query(None, description="평일|토|일+공휴일 (미지정=오늘)")) -> DepartureList:
    """그 노선의 시간표 발차슬롯(HHMM). 추론 엔드포인트의 `depart` 키 소스(= trip 재구성·1차 단위와 동일)."""
    d = store.route_departures(stdid, daytype)
    if d is None:
        raise HTTPException(404, f"노선 {stdid} 시간표 없음")
    return DepartureList(**d, source=Source.reference)


@router.get("/stops/search", response_model=list[StopSummary], summary="정류장 검색")
def search_stops(q: str = Query(..., description="정류장명 검색어")) -> list[StopSummary]:
    """이름으로 정류장 검색."""
    return [StopSummary(**s, source=Source.reference) for s in store.search_stops(q)]


@router.get("/stops/nearby", response_model=list[StopSummary], summary="좌표 인근 정류장")
def nearby_stops(
    lat: float = Query(...), lng: float = Query(...),
    radius_m: int = Query(500, description="검색 반경(m)"),
) -> list[StopSummary]:
    """좌표 주변 정류장(가까운 순)."""
    return [StopSummary(**s, source=Source.reference) for s in store.stops_nearby(lat, lng, radius_m)]


@router.get("/stops/{stop_id}", response_model=StopSummary, summary="정류장 상세(좌표·경유노선)")
def get_stop(stop_id: int) -> StopSummary:
    """정류장 좌표 + 경유 노선."""
    s = store.stop(stop_id)
    if s is None:
        raise HTTPException(404, f"정류장 {stop_id} 없음")
    return StopSummary(**s, source=Source.reference)
