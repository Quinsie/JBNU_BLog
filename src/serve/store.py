"""real 데이터 액세스 — 기준데이터(reference)·실황(raw 최신 스냅샷)·날씨(수집분).

원칙:
- 경로는 전부 `src/common/paths.py`. 절대경로 박지 않음.
- 실황은 ITS 를 추가 호출하지 않고 **우리가 이미 수집한 raw 최신 스냅샷**을 패스스루
  (추가 부하 0 · IP차단 리스크 0).
- 기준데이터/정류장 인덱스는 한 번 빌드 후 캐시. 실황 스냅샷은 짧은 TTL 캐시.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from src.common.clock import now_kst
from src.common.grid import latlng_to_grid
from src.common.paths import REF_SOURCE_DIR, REF_BUILT_DIR, RAW_BUS_DIR, RAW_WEATHER_DIR
# 발차슬롯·daytype 은 trip 재구성과 **같은 소스**를 재사용(= 1차 학습 단위와 일치 보장)
from src.preprocess.trip_reconstruct import (
    load_route_meta as _trip_meta, daytype_of as _daytype_of, _parse_slots)

_STOPS_DIR = REF_SOURCE_DIR / "stops"
_VTX_DIR = REF_SOURCE_DIR / "vtx"

# 코드 → 한글
_PTY = {"0": "없음", "1": "비", "2": "비/눈", "3": "눈", "5": "빗방울",
        "6": "빗방울눈날림", "7": "눈날림"}
_SKY = {"1": "맑음", "3": "구름많음", "4": "흐림"}


def _load(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _latest_file(d: Path, pattern: str) -> Path | None:
    files = sorted(d.glob(pattern))
    return files[-1] if files else None


def haversine_m(lat1, lng1, lat2, lng2) -> float:
    from math import radians, sin, cos, asin, sqrt
    dlat, dlng = radians(lat2 - lat1), radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * 6371000 * asin(sqrt(a))


# ── 기준데이터 ────────────────────────────────────────
_routes_cache: list[dict] | None = None
_stdid_brt: dict[int, str] = {}


def routes() -> list[dict]:
    global _routes_cache
    if _routes_cache is None:
        data = _load(REF_BUILT_DIR / "stdid_list.json")
        _routes_cache = data.get("routes", [])
        for r in _routes_cache:
            _stdid_brt[int(r["stdid"])] = r.get("brt_no")
    return _routes_cache


def route_detail(stdid: int) -> dict | None:
    sp = _STOPS_DIR / f"{stdid}.json"
    if not sp.exists():
        return None
    stops_raw = sorted(_load(sp).get("resultList", []), key=lambda s: s.get("STOP_ORD", 0))
    stops = [{"stop_ord": s["STOP_ORD"], "stop_id": s["STOP_ID"], "stop_name": s["STOP_NAME"],
              "lat": s["LAT"], "lng": s["LNG"]} for s in stops_raw]
    vtx_path = _VTX_DIR / f"{stdid}.json"
    poly = [{"lat": v["LAT"], "lng": v["LNG"]} for v in _load(vtx_path).get("resultList", [])] \
        if vtx_path.exists() else [{"lat": s["lat"], "lng": s["lng"]} for s in stops]
    routes()  # ensure brt map
    return {"stdid": stdid, "brt_no": _stdid_brt.get(stdid, ""), "stops": stops, "polyline": poly}


# 정류장 인덱스: stop_id → 좌표/이름 + 경유 (stdid, stop_ord)
_stop_index: dict[int, dict] | None = None


def _build_stop_index() -> dict[int, dict]:
    global _stop_index
    if _stop_index is not None:
        return _stop_index
    routes()
    idx: dict[int, dict] = {}
    for sp in _STOPS_DIR.glob("*.json"):
        try:
            stdid = int(sp.stem)
        except ValueError:
            continue
        for s in _load(sp).get("resultList", []):
            sid = s["STOP_ID"]
            e = idx.get(sid)
            if e is None:
                e = idx[sid] = {"stop_id": sid, "stop_name": s["STOP_NAME"],
                                "lat": s["LAT"], "lng": s["LNG"], "serves": []}
            e["serves"].append((stdid, s.get("STOP_ORD")))
    _stop_index = idx
    return idx


def stop(stop_id: int) -> dict | None:
    e = _build_stop_index().get(stop_id)
    if e is None:
        return None
    brt = sorted({_stdid_brt.get(sd) for sd, _ in e["serves"]} - {None})
    return {**{k: e[k] for k in ("stop_id", "stop_name", "lat", "lng")}, "routes": brt}


def search_stops(q: str, limit: int = 20) -> list[dict]:
    out = []
    for e in _build_stop_index().values():
        if q in e["stop_name"]:
            brt = sorted({_stdid_brt.get(sd) for sd, _ in e["serves"]} - {None})
            out.append({**{k: e[k] for k in ("stop_id", "stop_name", "lat", "lng")}, "routes": brt})
            if len(out) >= limit:
                break
    return out


def current_daytype() -> str:
    return _daytype_of(now_kst().date())


def route_departures(stdid: int, daytype: str | None = None) -> dict | None:
    """노선의 시간표 발차슬롯(HHMM 정렬). trip_reconstruct 와 같은 소스 → 1차 단위와 일치."""
    meta = _trip_meta(stdid)
    if not meta:
        return None
    dt = daytype or current_daytype()
    hhmm, _ = _parse_slots((meta.get("sched") or {}).get(dt, []))
    routes()
    return {"stdid": int(stdid), "brt_no": meta.get("brt_no") or _stdid_brt.get(int(stdid)),
            "daytype": dt, "departures": [h.replace(":", "") for h in hhmm]}


def stops_nearby(lat: float, lng: float, radius_m: int, limit: int = 30) -> list[dict]:
    res = []
    for e in _build_stop_index().values():
        dist = haversine_m(lat, lng, e["lat"], e["lng"])
        if dist <= radius_m:
            brt = sorted({_stdid_brt.get(sd) for sd, _ in e["serves"]} - {None})
            res.append((dist, {**{k: e[k] for k in ("stop_id", "stop_name", "lat", "lng")}, "routes": brt}))
    res.sort(key=lambda x: x[0])
    return [r for _, r in res[:limit]]


# ── 실황 (raw 최신 스냅샷, TTL 캐시) ──────────────────
_snap: dict | None = None
_snap_ts: float = 0.0
_SNAP_TTL = 8.0   # 초


def _latest_bus_line(stdid: int) -> list[dict]:
    d = RAW_BUS_DIR / str(stdid)
    f = _latest_file(d, "*.jsonl")
    if f is None:
        return []
    last = None
    with f.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                last = line
    if not last:
        return []
    try:
        body = json.loads(last).get("body") or {}
        return body.get("busPosList") or []
    except json.JSONDecodeError:
        return []


def _snapshot() -> dict:
    """{stdid: [bus,...]} 전 노선 최신 위치. TTL 동안 캐시."""
    global _snap, _snap_ts
    now = time.time()
    if _snap is not None and now - _snap_ts < _SNAP_TTL:
        return _snap
    snap: dict[int, list[dict]] = {}
    for r in routes():
        sd = int(r["stdid"])
        buses = []
        for b in _latest_bus_line(sd):
            buses.append({   # 익명 위치 — plate 노출 안 함(비유일·추적 불가)
                "stdid": sd, "brt_no": r.get("brt_no", ""),
                "lat": b.get("LAT"), "lng": b.get("LNG"),
                "stop_ord": b.get("LATEST_STOP_ORD"),
            })
        if buses:
            snap[sd] = buses
    _snap, _snap_ts = snap, now
    return snap


def route_buses(stdid: int) -> list[dict]:
    """노선 위 버스들의 현재 위치(익명)."""
    return _snapshot().get(int(stdid), [])


def arrivals(stop_id: int) -> dict | None:
    e = _build_stop_index().get(stop_id)
    if e is None:
        return None
    snap = _snapshot()
    items = []
    for stdid, stop_ord in e["serves"]:
        if stop_ord is None:
            continue
        for b in snap.get(stdid, []):
            bord = b.get("stop_ord")
            if bord is None or bord > stop_ord:
                continue   # 이미 지난 버스 제외
            items.append({"brt_no": b["brt_no"], "stdid": stdid,
                          "stops_away": stop_ord - bord})
    items.sort(key=lambda x: x["stops_away"])
    return {"stop_id": stop_id, "stop_name": e["stop_name"], "arrivals": items}


# ── 날씨 ──────────────────────────────────────────────
def _grid_items(realtime: bool, key: str):
    sub = "realtime" if realtime else "shortForecast"
    f = _latest_file(RAW_WEATHER_DIR / sub, "*.json")
    if f is None:
        return None, None
    data = _load(f)
    g = (data.get("grids") or {}).get(key)
    if not g or not g.get("ok"):
        return None, f
    try:
        return g["body"]["response"]["body"]["items"]["item"], f
    except (KeyError, TypeError):
        return None, f


def weather(lat: float, lng: float) -> dict:
    nx, ny = latlng_to_grid(lat, lng)
    key = f"{nx}_{ny}"
    now_items, _ = _grid_items(True, key)
    now = {"lat": lat, "lng": lng, "observed_at": now_kst().isoformat(timespec="seconds"),
           "temp_c": None, "precipitation_type": None, "rain_mm": None, "sky": None}
    if now_items:
        v = {it["category"]: it["obsrValue"] for it in now_items}
        now["temp_c"] = _f(v.get("T1H"))
        now["precipitation_type"] = _PTY.get(str(v.get("PTY")), None)
        now["rain_mm"] = _f(v.get("RN1"))
        # 실황엔 SKY 없음 → 예보 첫 항목으로 보강(아래)

    fc_items, _ = _grid_items(False, key)
    forecast = []
    if fc_items:
        by_t: dict[tuple, dict] = {}
        for it in fc_items:
            t = (it["fcstDate"], it["fcstTime"])
            by_t.setdefault(t, {})[it["category"]] = it["fcstValue"]
        for (fd, ft), v in sorted(by_t.items()):
            iso = f"{fd[:4]}-{fd[4:6]}-{fd[6:]}T{ft[:2]}:{ft[2:]}:00+09:00"
            forecast.append({"forecast_at": iso, "temp_c": _f(v.get("T1H")),
                             "precipitation_type": _PTY.get(str(v.get("PTY"))),
                             "rain_mm": _f(v.get("RN1")), "sky": _SKY.get(str(v.get("SKY")))})
        if now["sky"] is None and forecast:
            now["sky"] = forecast[0]["sky"]
    return {"now": now, "forecast": forecast}


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None
