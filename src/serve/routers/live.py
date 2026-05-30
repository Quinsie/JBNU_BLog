"""실황(live) — BIS 실시간 버스위치. **real**: ITS 추가호출 없이 우리가 수집한 raw 최신 스냅샷 패스스루.

도착보드의 `eta_sec`(잔여 분초)는 2차 실시간추론 자산 → 그 전까지 null(eta_source=dummy).
`stops_away`(몇 정류장 전)는 실황으로 계산.
"""

from fastapi import APIRouter, HTTPException, Query

from .. import store
from ..schemas import BusLive, ArrivalBoard, ArrivalItem, Source

router = APIRouter(prefix="/v1", tags=["실황(live)"])


@router.get("/buses", response_model=list[BusLive], summary="실시간 버스 위치들")
def list_buses(stdid: int | None = Query(None, description="노선 stdid 필터")) -> list[BusLive]:
    """노선(또는 전체)의 실시간 버스 위치 — raw 최신 스냅샷."""
    return [BusLive(**b, updated_at=store.now_kst().isoformat(timespec="seconds"),
                    source=Source.live) for b in store.buses(stdid)]


@router.get("/buses/{bus_id}", response_model=BusLive, summary="특정 버스 실시간 위치")
def get_bus(bus_id: str) -> BusLive:
    """특정 차량의 실시간 위치/진행."""
    b = store.bus_one(bus_id)
    if b is None:
        raise HTTPException(404, f"버스 {bus_id} 실황 없음")
    return BusLive(**b, updated_at=store.now_kst().isoformat(timespec="seconds"), source=Source.live)


@router.get("/stops/{stop_id}/arrivals", response_model=ArrivalBoard, summary="정류장 도착예정 보드")
def stop_arrivals(stop_id: int) -> ArrivalBoard:
    """이 정류장에 접근 중인 버스들(몇 정류장 전 = 실황). 잔여 분초는 2차 모델 후 채움."""
    a = store.arrivals(stop_id)
    if a is None:
        raise HTTPException(404, f"정류장 {stop_id} 없음")
    return ArrivalBoard(
        stop_id=a["stop_id"], stop_name=a["stop_name"],
        arrivals=[ArrivalItem(brt_no=i["brt_no"], stdid=i["stdid"], bus_id=i["bus_id"],
                              stops_away=i["stops_away"], eta_sec=None, eta_source=Source.dummy)
                  for i in a["arrivals"]],
    )
