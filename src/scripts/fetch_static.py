"""정적 기준 데이터를 전주 ITS API 로 받아 data/reference/source/ 에 저장.

수집 항목:
  route_list.json          노선번호 목록 (selectGrpRouteList)
  subList/{brt_no}.json    노선번호별 분선 목록 (selectBisRouteSubList)
  stops/{stdid}.json       정류장 시퀀스 (selectBisRouteRsltList)
  vtx/{stdid}.json         경로 vertex (selectBisRouteVtxList)
  timetable/{stdid}.json   시간표 + BRT_TEXT (selectBisRouteTimeInfo)

노선 개편 시 재실행. 사용: python3 -m src.scripts.fetch_static
"""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta

import requests

from src.common import jeonju_api as api
from src.common.paths import REF_SOURCE_DIR

KST = timezone(timedelta(hours=9))
WORKERS = 6

SUBLIST_DIR = REF_SOURCE_DIR / "subList"
STOPS_DIR = REF_SOURCE_DIR / "stops"
VTX_DIR = REF_SOURCE_DIR / "vtx"
TIMETABLE_DIR = REF_SOURCE_DIR / "timetable"


def _now() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


def _save(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)


def _local_session() -> requests.Session:
    return requests.Session()


def fetch_sublists(brt_nos: list[str]) -> set[int]:
    """노선번호별 분선 목록 저장 + 전체 stdid 집합 반환."""
    stdids: set[int] = set()
    fails = []

    def work(no):
        s = _local_session()
        rows = api.route_sublist(no, session=s)
        _save(SUBLIST_DIR / f"{no}.json", {"fetched_at": _now(), "brt_no": no, "resultList": rows})
        return no, [r["BRT_STDID"] for r in rows if r.get("BRT_STDID") is not None]

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(work, no): no for no in brt_nos}
        for fut in as_completed(futs):
            try:
                _, sids = fut.result()
                stdids.update(sids)
            except Exception as e:  # noqa: BLE001
                fails.append((futs[fut], str(e)))
    if fails:
        print(f"  [subList 실패 {len(fails)}]: {fails[:5]}")
    return stdids


def fetch_per_stdid(stdids: list[int]):
    """stdid별 stops/vtx/timetable 저장."""
    fails = []

    def work(sid):
        s = _local_session()
        _save(STOPS_DIR / f"{sid}.json",
              {"fetched_at": _now(), "stdid": sid, "resultList": api.route_stops(sid, session=s)})
        _save(VTX_DIR / f"{sid}.json",
              {"fetched_at": _now(), "stdid": sid, "resultList": api.route_vtx(sid, session=s)})
        ti = api.route_time_info(sid, session=s)
        _save(TIMETABLE_DIR / f"{sid}.json",
              {"fetched_at": _now(), "stdid": sid,
               "result": ti.get("result", {}), "timeList": ti.get("timeList", [])})
        return sid

    done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(work, sid): sid for sid in stdids}
        for fut in as_completed(futs):
            try:
                fut.result()
                done += 1
                if done % 50 == 0:
                    print(f"  ... {done}/{len(stdids)}")
            except Exception as e:  # noqa: BLE001
                fails.append((futs[fut], str(e)))
    if fails:
        print(f"  [per-stdid 실패 {len(fails)}]: {fails[:5]}")
    return done, fails


def main():
    print(f"[fetch_static] 시작 {_now()}  → {REF_SOURCE_DIR}")

    print("[1/3] route_list (selectGrpRouteList)")
    routes = api.grp_route_list()
    _save(REF_SOURCE_DIR / "route_list.json",
          {"fetched_at": _now(), "total": len(routes), "resultList": routes})
    brt_nos = sorted({r["BRT_NO"] for r in routes if r.get("BRT_NO")})
    print(f"      노선번호 {len(brt_nos)}개")

    print("[2/3] subList (분선 목록)")
    stdids = sorted(fetch_sublists(brt_nos))
    print(f"      전체 stdid {len(stdids)}개")

    print("[3/3] stops / vtx / timetable (stdid별)")
    done, fails = fetch_per_stdid(stdids)
    print(f"      완료 {done}/{len(stdids)}  실패 {len(fails)}")

    print(f"[fetch_static] 종료 {_now()}")


if __name__ == "__main__":
    main()
