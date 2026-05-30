"""추론 — 사전추론(pre-eta, 1차) / 실시간추론(live-eta, 2차). 모델 의존 → 모델 완성까지 dummy.

**단위 = (stdid, 발차슬롯)** = 한 배차(trip). plate 아님.
- 사전추론(pre): 시간표 발차 기반(현재 버스위치 무관). 1차 모델.
- 실시간추론(live): 실시간 위치로 보정. 2차 모델.
mode 쿼리로 둘 구분(엔드포인트 공유). 둘 다 현재 dummy.
"""

from fastapi import APIRouter, HTTPException, Query

from .. import store, dummy
from ..schemas import DepartureEta, StopBoardEta, Source

router = APIRouter(prefix="/v1", tags=["추론(pre/live-eta)"])

_MODES = {"pre": Source.pre_eta, "live": Source.live_eta}


@router.get("/routes/{stdid}/departures/{hhmm}/eta", response_model=DepartureEta,
            summary="배차별 각 정류장 도착예상(1차/2차)")
def departure_eta(stdid: int, hhmm: str, mode: str = Query("pre", enum=["pre", "live"])) -> DepartureEta:
    """stdid 의 `hhmm` 발차가 노선 위 각 정류장에 언제 도착하는지. `mode=pre`(1차)/`live`(2차). **현재 dummy.**"""
    dep = store.route_departures(stdid)
    if dep is None:
        raise HTTPException(404, f"노선 {stdid} 시간표 없음")
    return dummy.departure_eta(stdid, hhmm, _MODES.get(mode, Source.pre_eta))


@router.get("/stops/{stop_id}/eta", response_model=StopBoardEta, summary="정류장에 오는 배차별 도착예상(1차/2차)")
def stop_eta(stop_id: int, mode: str = Query("pre", enum=["pre", "live"])) -> StopBoardEta:
    """이 정류장에 다가오는 (노선,발차)들의 도착예상. `mode=pre`(1차)/`live`(2차). **현재 dummy.**"""
    if store._build_stop_index().get(stop_id) is None:
        raise HTTPException(404, f"정류장 {stop_id} 없음")
    return dummy.stop_board_eta(stop_id, _MODES.get(mode, Source.pre_eta))
