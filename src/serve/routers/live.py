"""실황(live) — 노선 위 버스 **익명 위치** + 정류장 도착보드. real: 우리 raw 최신 스냅샷 패스스루.

개별 차량 추적·plate 식별 안 함(plate 비유일·운영불가). 도착보드 `eta_sec`(잔여 분초)는
2차 실시간추론 자리 → 현재 더미(stops_away 비례, eta_source=dummy).
"""

from fastapi import APIRouter, HTTPException

from .. import store, dummy
from ..schemas import LiveBus, ArrivalBoard, ArrivalItem, Source

router = APIRouter(prefix="/v1", tags=["실황(live)"])


@router.get("/routes/{stdid}/buses", response_model=list[LiveBus], summary="노선 위 버스 현재위치(익명)")
def route_buses(stdid: int) -> list[LiveBus]:
    """노선 위 버스들의 현재 위치(지도 점). 개별 추적 식별자 없음."""
    ts = store.now_kst().isoformat(timespec="seconds")
    return [LiveBus(**b, updated_at=ts, source=Source.live) for b in store.route_buses(stdid)]


@router.get("/stops/{stop_id}/arrivals", response_model=ArrivalBoard, summary="정류장 도착예정 보드")
def stop_arrivals(stop_id: int) -> ArrivalBoard:
    """이 정류장에 접근 중인 버스들. `stops_away`=실황(real). `eta_sec`=2차 모델 전까지 더미."""
    a = store.arrivals(stop_id)
    if a is None:
        raise HTTPException(404, f"정류장 {stop_id} 없음")
    return ArrivalBoard(
        stop_id=a["stop_id"], stop_name=a["stop_name"],
        arrivals=[ArrivalItem(brt_no=i["brt_no"], stdid=i["stdid"], stops_away=i["stops_away"],
                              eta_sec=dummy.arrival_eta_sec(i["stops_away"]), eta_source=Source.dummy)
                  for i in a["arrivals"]],
    )
