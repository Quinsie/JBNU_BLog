"""dummy 응답 생성기 — 아직 모델이 없는 계층(사전/실시간추론·plan)용.

원칙(사용자 합의):
- "더미"임을 응답에 **명시**(`dummy:true` / `source:dummy` / `eta_source:dummy`).
- 값은 쓰레기·null 대신 **real 기준데이터/실황에 grounding** — 실제 노선·정류장·발차슬롯으로
  구성하고 *예측 수치(도착 clock-time·확률)만* 그럴듯하게 fabricate.
- 추론 단위 = **(stdid, 발차슬롯)** = 한 배차(trip). plate 아님.

real 교체 시 이 모듈 대신 1차/2차 모델·에이전트를 호출하고 `dummy=false`.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from src.common.clock import now_kst, ts_iso
from . import store
from . import schemas as S

_SEG_SEC = 90   # 더미 정류장간 소요(그럴듯한 평균)


def _today_at(hhmm: str) -> datetime:
    """오늘(KST) 의 HHMM 시각."""
    h, m = int(hhmm[:2]), int(hhmm[2:])
    return now_kst().replace(hour=h, minute=m, second=0, microsecond=0)


def arrival_eta_sec(stops_away: int) -> int:
    """도착보드 잔여시간 더미(2차 모델 전까지). stops_away 비례."""
    return max(stops_away, 0) * _SEG_SEC + 30


def departure_eta(stdid: int, hhmm: str, mode: S.Source) -> S.DepartureEta:
    """#10: (stdid, 발차)의 각 정류장 도착 clock-time — real 노선 정류장 기반, 시각만 더미."""
    rd = store.route_detail(stdid)
    stops = rd["stops"] if rd else []
    brt = rd["brt_no"] if rd else store._stdid_brt.get(int(stdid))
    base = _today_at(hhmm)
    items = [S.StopArrival(stop_ord=s["stop_ord"], stop_name=s["stop_name"],
                           arrival_iso=ts_iso(base + timedelta(seconds=_SEG_SEC * k)))
             for k, s in enumerate(stops)]
    if not items:
        items = [S.StopArrival(stop_ord=i, stop_name=f"정류장{i}",
                               arrival_iso=ts_iso(base + timedelta(seconds=_SEG_SEC * (i - 1))))
                 for i in range(1, 6)]
    return S.DepartureEta(stdid=int(stdid), brt_no=brt, depart=hhmm, mode=mode, dummy=True, stops=items)


def stop_board_eta(stop_id: int, mode: S.Source) -> S.StopBoardEta:
    """#9: 정류장에 다가오는 (노선,발차)별 도착예상 — real 경유노선·발차슬롯 기반, 시각만 더미."""
    idx = store._build_stop_index().get(stop_id)
    serves = idx["serves"] if idx else []
    now = now_kst()
    items: list[S.StopBoardItem] = []
    seen = set()
    for stdid, stop_ord in serves:
        if stdid in seen:
            continue
        seen.add(stdid)
        dep = store.route_departures(stdid)
        if not dep or not dep["departures"]:
            continue
        upcoming = [h for h in dep["departures"] if _today_at(h) >= now][:1] or dep["departures"][-1:]
        for h in upcoming:
            arr = _today_at(h) + timedelta(seconds=_SEG_SEC * max((stop_ord or 1) - 1, 0))
            items.append(S.StopBoardItem(brt_no=dep["brt_no"] or "?", stdid=stdid,
                                         depart=h, arrival_iso=ts_iso(arr)))
        if len(items) >= 8:
            break
    items.sort(key=lambda x: x.arrival_iso)
    if not items:
        base = ts_iso(now + timedelta(seconds=300))
        items = [S.StopBoardItem(brt_no="101", stdid=305000392, depart="0600", arrival_iso=base)]
    return S.StopBoardEta(stop_id=stop_id, mode=mode, dummy=True, items=items)


def plan(req: S.PlanRequest) -> S.PlanResponse:
    """이동계획 더미 — 출발지 인근 real 정류장·노선·발차로 구성, 시각·확률만 fabricate."""
    near = store.stops_nearby(req.origin.lat, req.origin.lng, 1000, limit=1)
    board_name, brt, stdid, depart = "전북대종점", "101", 305000392, "0600"
    if near:
        board_name = near[0]["stop_name"]
        idx = store._build_stop_index().get(near[0]["stop_id"])
        if idx and idx["serves"]:
            stdid = idx["serves"][0][0]
            dep = store.route_departures(stdid)
            if dep:
                brt = dep["brt_no"] or brt
                now = now_kst()
                up = [h for h in dep["departures"] if _today_at(h) >= now]
                depart = up[0] if up else (dep["departures"][-1] if dep["departures"] else depart)

    rec = S.PlanOption(
        leave_by=ts_iso(now_kst() + timedelta(seconds=120)), arrival_eta=req.target_arrival,
        miss_probability=0.12,
        legs=[
            S.PlanLeg(mode="walk", desc="승차 정류장까지 도보", from_name="현재위치", to_name=board_name,
                      start_iso=ts_iso(now_kst() + timedelta(seconds=120)),
                      end_iso=ts_iso(now_kst() + timedelta(seconds=420))),
            S.PlanLeg(mode="wait", desc=f"{depart} 발차 대기", from_name=board_name,
                      start_iso=ts_iso(now_kst() + timedelta(seconds=420)),
                      end_iso=ts_iso(now_kst() + timedelta(seconds=540))),
            S.PlanLeg(mode="bus", desc=f"{brt}번 {depart} 배차 탑승", brt_no=brt, stdid=stdid, depart=depart,
                      from_name=board_name, to_name="하차정류장",
                      start_iso=ts_iso(now_kst() + timedelta(seconds=540)),
                      end_iso=ts_iso(now_kst() + timedelta(seconds=1740))),
            S.PlanLeg(mode="walk", desc="목적지까지 도보", from_name="하차정류장", to_name="목적지",
                      start_iso=ts_iso(now_kst() + timedelta(seconds=1740)),
                      end_iso=ts_iso(now_kst() + timedelta(seconds=1920))),
        ],
    )
    alt = S.PlanOption(
        leave_by=ts_iso(now_kst() + timedelta(seconds=420)), arrival_eta=req.target_arrival,
        miss_probability=0.04,
        legs=[S.PlanLeg(mode="bus", desc=f"{brt}번 한 배차 일찍(안전 대안)", brt_no=brt, stdid=stdid,
                        from_name=board_name, to_name="하차정류장")],
    )
    return S.PlanResponse(
        recommended=rec, alternatives=[alt], dummy=True, source=S.Source.dummy,
        advice=f"약 2분 뒤 출발하면 {board_name}에서 {brt}번 {depart} 배차를 타고 목표시각 전에 도착합니다.",
    )
