"""실황(live) — BIS 실시간 버스위치 패스스루. 모델 불필요 → 다음 단위에서 real(BIS) 교체.

도착보드의 `eta_sec`(잔여 분초)는 2차 실시간추론 자산 → 그 전까지 null/dummy.
"""

from fastapi import APIRouter, Query

from .. import dummy
from ..schemas import BusLive, ArrivalBoard

router = APIRouter(prefix="/v1", tags=["실황(live)"])


@router.get("/buses", response_model=list[BusLive], summary="실시간 버스 위치들")
def list_buses(stdid: int | None = Query(None, description="노선 stdid 필터")) -> list[BusLive]:
    """노선(또는 전체)의 실시간 버스 위치. **현재 dummy** → BIS 패스스루로 교체 예정."""
    return dummy.buses(stdid)


@router.get("/buses/{bus_id}", response_model=BusLive, summary="특정 버스 실시간 위치")
def get_bus(bus_id: str) -> BusLive:
    """특정 차량의 실시간 위치/진행. **현재 dummy.**"""
    return dummy.bus_one(bus_id)


@router.get("/stops/{stop_id}/arrivals", response_model=ArrivalBoard, summary="정류장 도착예정 보드")
def stop_arrivals(stop_id: int) -> ArrivalBoard:
    """이 정류장에 접근 중인 버스들(몇 정류장 전 = 실황). 잔여 분초는 2차 모델 후 채움. **현재 dummy.**"""
    return dummy.arrivals(stop_id)
