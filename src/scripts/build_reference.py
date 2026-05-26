"""reference/source 원본 → reference/built 파생 참조물 생성.

생성물:
  stdid_list.json     수집 대상 446 stdid + 메타(노선번호·방향·그룹·시종점·배차·첫막차)
  nx_ny_coords.json   날씨 수집용 격자맵 (정류장+vtx 좌표 → 유니크 기상청 격자)

사용: python3 -m src.scripts.build_reference
"""

import glob
import json
from datetime import datetime, timezone, timedelta

from src.common.grid import latlng_to_grid
from src.common.paths import REF_SOURCE_DIR, REF_BUILT_DIR

KST = timezone(timedelta(hours=9))


def _now() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


def _save(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)


def build_stdid_list():
    """subList 전체를 모아 stdid → 메타 목록 생성."""
    routes = []
    for f in sorted(glob.glob(str(REF_SOURCE_DIR / "subList" / "*.json"))):
        for r in json.load(open(f, encoding="utf-8")).get("resultList", []):
            sid = r.get("BRT_STDID")
            if sid is None:
                continue
            routes.append({
                "stdid": sid,
                "brt_no": r.get("BRT_NO"),
                "subid": r.get("BRT_SUBID"),
                "direction": r.get("BRT_DIRECTION"),   # "1"=상행 "2"=하행
                "grpnm": r.get("BRT_GRPNM"),            # 본선/지선/마을 등
                "start_name": r.get("BRT_SNAME"),
                "end_name": r.get("BRT_ENAME"),
                "first_time": r.get("BRT_FIRSTTIME"),
                "last_time": r.get("BRT_LASTTIME"),
                "min_interval": r.get("BRT_MININTERVAL"),
                "max_interval": r.get("BRT_MAXINTERVAL"),
                "irregular": r.get("BRT_ILREGINTERVALYN"),
            })
    routes.sort(key=lambda x: x["stdid"])
    _save(REF_BUILT_DIR / "stdid_list.json",
          {"built_at": _now(), "total": len(routes), "routes": routes})
    print(f"  stdid_list.json: {len(routes)}개")
    return routes


def build_grid_map():
    """정류장 + vtx 좌표를 격자로 변환, 유니크 격자 집합 생성."""
    grids: dict[str, dict] = {}

    def add(lat, lng):
        if lat is None or lng is None:
            return
        try:
            nx, ny = latlng_to_grid(float(lat), float(lng))
        except (TypeError, ValueError):
            return
        key = f"{nx}_{ny}"
        g = grids.setdefault(key, {"nx": nx, "ny": ny, "n": 0})
        g["n"] += 1

    for f in glob.glob(str(REF_SOURCE_DIR / "stops" / "*.json")):
        for r in json.load(open(f, encoding="utf-8")).get("resultList", []):
            add(r.get("LAT"), r.get("LNG"))
    for f in glob.glob(str(REF_SOURCE_DIR / "vtx" / "*.json")):
        for r in json.load(open(f, encoding="utf-8")).get("resultList", []):
            add(r.get("LAT"), r.get("LNG"))

    _save(REF_BUILT_DIR / "nx_ny_coords.json",
          {"built_at": _now(), "total": len(grids), "grids": grids})
    print(f"  nx_ny_coords.json: 격자 {len(grids)}개  "
          f"(범위 nx {min(g['nx'] for g in grids.values())}~{max(g['nx'] for g in grids.values())}, "
          f"ny {min(g['ny'] for g in grids.values())}~{max(g['ny'] for g in grids.values())})")
    return grids


def main():
    print(f"[build_reference] 시작 {_now()}")
    build_stdid_list()
    build_grid_map()
    print(f"[build_reference] 종료 {_now()}")


if __name__ == "__main__":
    main()
