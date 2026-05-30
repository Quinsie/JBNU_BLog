"""추론 — 사전추론(pre-eta, 1차) / 실시간추론(live-eta, 2차). 모델 의존 → 모델 완성까지 dummy.

- pre-eta : 배차시각 기반(현재 버스위치 무관) 도착예상. 1차 모델.
- live-eta: 실시간 버스위치 기반 도착예상. 2차 모델.
mode 쿼리로 둘을 구분(엔드포인트는 공유). 둘 다 현재 dummy.
"""

from fastapi import APIRouter, Query

from .. import dummy
from ..schemas import StopEta, BusEta, Source

router = APIRouter(prefix="/v1", tags=["추론(pre/live-eta)"])

_MODES = {"pre": Source.pre_eta, "live": Source.live_eta}


def _mode(m: str) -> Source:
    return _MODES.get(m, Source.pre_eta)


@router.get("/stops/{stop_id}/eta", response_model=StopEta, summary="정류장별 버스 도착예상(1차/2차)")
def stop_eta(stop_id: int, mode: str = Query("pre", enum=["pre", "live"])) -> StopEta:
    """이 정류장에 각 노선 버스가 언제 도착할지. `mode=pre`(1차)/`live`(2차). **현재 dummy.**"""
    return dummy.stop_eta(stop_id, _mode(mode))


@router.get("/buses/{bus_id}/eta", response_model=BusEta, summary="버스별 각 정류장 도착예상(1차/2차)")
def bus_eta(bus_id: str, mode: str = Query("pre", enum=["pre", "live"])) -> BusEta:
    """이 버스가 각 정류장에 언제 도착할지. `mode=pre`(1차)/`live`(2차). **현재 dummy.**"""
    return dummy.bus_eta(bus_id, _mode(mode))
