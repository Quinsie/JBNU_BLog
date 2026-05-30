"""에이전트(plan) — 앱의 본체. 목적지+목표도착 → 행동 단위 이동계획.

내부적으로 OSRM(도보)·사전/실시간추론·놓칠확률을 조합한다(도보는 별도 엔드포인트 아님).
에이전트·ETA 모델 의존 → 전부 완성될 때까지 dummy.
"""

from fastapi import APIRouter

from .. import dummy
from ..schemas import PlanRequest, PlanResponse

router = APIRouter(prefix="/v1", tags=["에이전트(plan)"])


@router.post("/plan", response_model=PlanResponse, summary="목표 도착형 이동계획")
def make_plan(req: PlanRequest) -> PlanResponse:
    """목적지+목표도착시각 → 추천안(승차정류장·버스·출발시각·도보구간·놓칠확률)+안전 대안.

    도보는 내부 OSRM 모듈로 계산(엔드포인트 미제공). **현재 dummy.**
    """
    return dummy.plan(req)


@router.post("/plan/recheck", response_model=PlanResponse, summary="이동 중 계획 재평가")
def recheck_plan(req: PlanRequest) -> PlanResponse:
    """이동 중 현재 위치로 놓칠확률·대안을 재평가. **현재 dummy.**"""
    return dummy.plan(req)
