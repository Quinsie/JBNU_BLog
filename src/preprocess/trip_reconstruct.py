"""raw busPosList → 차량별 trip 재구성 (v1).

파이프라인 (docs/design/trip-reconstruction.md §4):
  로드 → 글리치필터(§4.3) → trip분할(§4.0) → 발차검출(§4.1) → 종료검출(§4.2)
  → 구간추출(§5) → trip 레코드.

철학: 완벽한 trip 경계가 아니라 *믿을 수 있는 구간*. 경계오류는 첫/마지막 구간만
건드리고 중간은 멀쩡 → 진입/소멸 정확검출 + 과도지터 폐기만으로 robust.

발차는 ord 전이로 잡지 않는다(= 다음 정류장 도착). 기점 ord run 안에서 GPS 지속이탈로.
node_ord 는 1·2차 모두 미사용. 위치는 LAT/LNG.

⚠️ v1 임계값(R_PARK/R_DEPART/K 등)은 잠정 — 실데이터 리플레이로 튜닝(반복개선).
⚠️ v1 은 발차검출이 GPS 단독. 시간표(timeList) prior 로 슬롯 게이팅하는 건 v1.1.
"""

from __future__ import annotations

import glob
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, date as date_cls

from src.common.paths import RAW_BUS_DIR, REF_SOURCE_DIR

# ── 잠정 임계값 (실데이터 튜닝 대상) ──────────────────────
MAX_KMH = 120.0        # 글리치: 틱간 추정속도가 이보다 크면 순간이동 의심
RESET_MARGIN = 5       # trip 분할: stop_ord 가 running_max 보다 이만큼 떨어지면 새 회차
GAP_MAX_SEC = 1800.0   # trip 분할: 같은 plate 관측 공백이 이보다 크면 분할
START_ORD_MAX = 2      # 시작 ord 가 이 이하면 "기점 포착" 후보(발차검출 시도)
R_PARK = 30.0          # 기점 정차 중심점 반경(m): 이 안이면 정차로 간주
R_DEPART = 50.0        # 발차 판정: 중심점에서 이만큼 벗어나고
K_DEPART = 3           #   K틱 연속 유지되면 지속이탈 = 발차


@dataclass
class Obs:
    ts: float          # epoch sec
    iso: str
    so: int            # LATEST_STOP_ORD
    spd: int
    lat: float
    lng: float


def haversine(lat1, lng1, lat2, lng2) -> float:
    """두 좌표 거리(m)."""
    if None in (lat1, lng1, lat2, lng2):
        return 0.0
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# ── 로드 ────────────────────────────────────────────────
def load_observations(stdid: int | str, date_str: str) -> dict[str, list[Obs]]:
    """raw bus jsonl → {plate: [Obs ...]} (plate 내 시간순)."""
    out: dict[str, list[Obs]] = {}
    pattern = str(RAW_BUS_DIR / str(stdid) / f"{date_str}_*.jsonl")
    for fp in sorted(glob.glob(pattern)):
        with open(fp, encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                if not rec.get("ok"):
                    continue
                body = rec.get("body")
                if not isinstance(body, dict):
                    continue
                ts = datetime.fromisoformat(rec["ts"]).timestamp()
                for b in body.get("busPosList", []):
                    plate = str(b.get("PLATE_NO", "")).strip()
                    if not plate:
                        continue
                    out.setdefault(plate, []).append(Obs(
                        ts=ts, iso=rec["ts"],
                        so=b.get("LATEST_STOP_ORD"),
                        spd=b.get("SPEED") or 0,
                        lat=b.get("LAT"), lng=b.get("LNG"),
                    ))
    for seq in out.values():
        seq.sort(key=lambda o: o.ts)
    return out


# ── 글리치 필터 (§4.3) ──────────────────────────────────
def filter_glitches(seq: list[Obs]) -> tuple[list[Obs], int]:
    """좌표가 비현실 속도로 튀었다 돌아오는 단발 스파이크 제거."""
    if len(seq) < 3:
        return seq, 0
    keep = [seq[0]]
    dropped = 0
    for i in range(1, len(seq) - 1):
        a, b, c = seq[i - 1], seq[i], seq[i + 1]
        dt_ab = max(b.ts - a.ts, 1e-3)
        dt_bc = max(c.ts - b.ts, 1e-3)
        kmh_ab = haversine(a.lat, a.lng, b.lat, b.lng) / dt_ab * 3.6
        kmh_bc = haversine(b.lat, b.lng, c.lat, c.lng) / dt_bc * 3.6
        if kmh_ab > MAX_KMH and kmh_bc > MAX_KMH:
            dropped += 1   # 나갔다 돌아온 스파이크 = 글리치
            continue
        keep.append(b)
    keep.append(seq[-1])
    return keep, dropped


# ── trip 분할 (§4.0) ────────────────────────────────────
def split_trips(seq: list[Obs]) -> list[list[Obs]]:
    """stop_ord 리셋(회차) / 큰 관측공백 기준으로 trip 분할."""
    trips: list[list[Obs]] = []
    cur: list[Obs] = []
    run_max = -1
    for o in seq:
        if cur:
            gap = o.ts - cur[-1].ts
            reset = o.so is not None and o.so < run_max - RESET_MARGIN
            if gap > GAP_MAX_SEC or reset:
                trips.append(cur)
                cur = []
                run_max = -1
        cur.append(o)
        if o.so is not None:
            run_max = max(run_max, o.so)
    if cur:
        trips.append(cur)
    return trips


# ── 발차 검출 (§4.1) ────────────────────────────────────
def detect_departure(trip: list[Obs]) -> tuple[str | None, str]:
    """(발차_iso, 품질). 품질 ∈ origin_wait | origin_moving | mid_entry."""
    first_ord = trip[0].so
    if first_ord is None or first_ord > START_ORD_MAX:
        return None, "mid_entry"

    # 기점 ord run (선두에서 so == first_ord 인 구간)
    origin = []
    for o in trip:
        if o.so == first_ord:
            origin.append(o)
        else:
            break
    if not origin:
        return None, "mid_entry"

    # 정차 중심점: 선두에서 R_PARK 안에 머무는 prefix
    cx, cy = origin[0].lat, origin[0].lng
    parked_end = 0
    for i, o in enumerate(origin):
        if haversine(cx, cy, o.lat, o.lng) <= R_PARK:
            parked_end = i
        else:
            break

    if parked_end == 0:
        # 첫 관측부터 이미 이동 중 → 대기 못 봄
        return trip[0].iso, "origin_moving"

    # 지속 이탈 탐색: 중심점에서 R_DEPART 넘어 K틱 연속 유지
    for j in range(parked_end + 1, len(trip)):
        if all(
            k < len(trip) and haversine(cx, cy, trip[k].lat, trip[k].lng) > R_DEPART
            for k in range(j, j + K_DEPART)
        ):
            return trip[j - 1].iso, "origin_wait"   # 정차 마지막 틱 = 발차 직전
    # 이탈을 못 잡으면(드묾) 정차 끝 시각으로 폴백
    return origin[parked_end].iso, "origin_wait"


# ── 구간 추출 (§5) ──────────────────────────────────────
def extract_segments(trip: list[Obs], departure_iso: str | None,
                     ) -> tuple[list[dict], list[dict]]:
    """정류장 통과시각(stops) + 구간 소요시간(segments).

    pass_ts[N] = stop_ord==N 최초 관측 ts. 단 기점(첫 ord)은 발차시각으로 대체
    (ord=1 최초관측은 기점 정차/시스템-on 시점이라 통과가 아님)."""
    first_ord = trip[0].so
    pass_ts: dict[int, str] = {}
    pass_epoch: dict[int, float] = {}
    for o in trip:
        if o.so is None or o.so in pass_ts:
            continue
        pass_ts[o.so] = o.iso
        pass_epoch[o.so] = o.ts

    if departure_iso is not None and first_ord in pass_ts:
        pass_ts[first_ord] = departure_iso
        pass_epoch[first_ord] = datetime.fromisoformat(departure_iso).timestamp()

    ords = sorted(pass_ts)
    stops = [{"ord": n, "pass_ts": pass_ts[n]} for n in ords]
    segments = []
    for n in ords:
        if n + 1 in pass_epoch:
            segments.append({
                "from": n, "to": n + 1,
                "elapsed_sec": round(pass_epoch[n + 1] - pass_epoch[n], 1),
            })
    return stops, segments


# ── 시간표 prior / 매칭 (§4.4) ──────────────────────────
def daytype_of(d: date_cls) -> str:
    """평일 / 토 / 일+공휴일. (공휴일 캘린더는 미반영 — TODO)"""
    wd = d.weekday()
    if wd == 5:
        return "토"
    if wd == 6:
        return "일+공휴일"
    return "평일"


def _parse_hhmm_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


def load_route_meta(stdid: int | str) -> dict:
    """timetable 파일 → {brt_no, sname, ename, sched{daytype:[hhmm]}}."""
    fp = REF_SOURCE_DIR / "timetable" / f"{stdid}.json"
    if not fp.exists():
        return {}
    d = json.load(open(fp, encoding="utf-8"))
    r = d.get("result", {})
    return {
        "brt_no": r.get("BRT_NO"),
        "sname": r.get("BRT_SNAME"), "ename": r.get("BRT_ENAME"),
        "sched": {
            "평일": _parse_hhmm_list(r.get("COURSE_STIMELIST")),
            "토": _parse_hhmm_list(r.get("SAT_NLIST")),
            "일+공휴일": _parse_hhmm_list(r.get("HOLI_NLIST")),
        },
    }


def match_schedule(dep_iso: str | None, sched: list[str]) -> tuple[str | None, int | None]:
    """검출 발차를 가장 가까운 예정 슬롯에 매칭 → (슬롯hhmm, delta_sec)."""
    if dep_iso is None or not sched:
        return None, None
    dep = datetime.fromisoformat(dep_iso)
    dep_min = dep.hour * 60 + dep.minute + dep.second / 60
    best, best_dist, best_smin = None, None, None
    for hhmm in sched:
        try:
            h, m = hhmm.split(":")
            smin = int(h) * 60 + int(m)
        except ValueError:
            continue
        d = abs(dep_min - smin)
        if best_dist is None or d < best_dist:
            best, best_dist, best_smin = hhmm, d, smin
    if best is None:
        return None, None
    return best, int(round((dep_min - best_smin) * 60))


# ── 한 노선 재구성 ──────────────────────────────────────
def reconstruct_stdid(stdid: int | str, date_str: str) -> list[dict]:
    meta = load_route_meta(stdid)
    svc_date = datetime.strptime(date_str, "%Y%m%d").date()
    dtype = daytype_of(svc_date)
    sched = meta.get("sched", {}).get(dtype, [])

    by_plate = load_observations(stdid, date_str)
    # 종점 추정용: 노선 전체 관측 최대 ord
    global_max = max((o.so for seq in by_plate.values() for o in seq
                      if o.so is not None), default=0)

    records: list[dict] = []
    for plate, seq in by_plate.items():
        clean, dropped = filter_glitches(seq)
        for trip in split_trips(clean):
            if len(trip) < 2:
                continue
            dep_iso, quality = detect_departure(trip)
            stops, segments = extract_segments(trip, dep_iso)
            if not segments:
                continue
            max_ord = max((o.so for o in trip if o.so is not None), default=0)
            slot, delta = match_schedule(dep_iso, sched)
            records.append({
                "stdid": int(stdid), "brt_no": meta.get("brt_no"),
                "plate_no": plate, "service_date": date_str, "daytype": dtype,
                "departure_ts": dep_iso, "departure_quality": quality,
                "matched_sched": slot, "sched_delta_sec": delta,
                "start_ord": trip[0].so, "end_ord": max_ord,
                "reached_terminus": global_max > 0 and max_ord >= global_max - 1,
                "n_obs": len(trip), "glitch_dropped": dropped,
                "stops": stops, "segments": segments,
            })
    return records


# ── CLI ─────────────────────────────────────────────────
def _summary(records: list[dict]) -> None:
    from collections import Counter
    q = Counter(r["departure_quality"] for r in records)
    print(f"trip {len(records)}개 | 품질 {dict(q)}")
    for r in records:
        seg = r["segments"]
        tot = sum(s["elapsed_sec"] for s in seg)
        dep = (r["departure_ts"] or "—")[11:19]
        sd = r["sched_delta_sec"]
        sd_s = f"{sd:+d}s vs {r['matched_sched']}" if sd is not None else "—"
        print(f"  PLATE {r['plate_no']:<5} {r['departure_quality']:<13} 발차 {dep} "
              f"[{sd_s}] ord {r['start_ord']}→{r['end_ord']}"
              f"{'·종점' if r['reached_terminus'] else ''} "
              f"구간 {len(seg)}개 총 {tot/60:.1f}분 glitch버림 {r['glitch_dropped']}")


def stdids_with_data(date_str: str) -> list[str]:
    """해당 날짜 raw 파일이 있는 stdid 목록."""
    out = []
    for d in sorted(RAW_BUS_DIR.glob("*")):
        if d.is_dir() and any(d.glob(f"{date_str}_*.jsonl")):
            out.append(d.name)
    return out


def _save(records: list[dict], date_str: str, stdid: str) -> None:
    from src.common.paths import INTERIM_DIR
    out_dir = INTERIM_DIR / "trips" / date_str
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / f"{stdid}.jsonl", "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _aggregate(all_recs: list[dict]) -> None:
    """전노선 집계 리포트 (스트레스테스트용)."""
    from collections import Counter
    import statistics as st
    n = len(all_recs)
    q = Counter(r["departure_quality"] for r in all_recs)
    full = sum(1 for r in all_recs if r["reached_terminus"])
    deltas = [abs(r["sched_delta_sec"]) for r in all_recs
              if r["sched_delta_sec"] is not None]
    glitch = sum(r["glitch_dropped"] for r in all_recs)
    seg_counts = [len(r["segments"]) for r in all_recs]

    def p(v, q_):
        v = sorted(v)
        return v[min(len(v) - 1, int(len(v) * q_))] if v else None

    print(f"\n{'='*60}\n전노선 집계: trip {n}개")
    print(f"  품질분기: {dict(q)}")
    print(f"  종점도달(풀trip): {full} ({full/n*100:.0f}%)")
    print(f"  구간수/trip: median {st.median(seg_counts):.0f} max {max(seg_counts)}")
    if deltas:
        within = lambda s: sum(1 for d in deltas if d <= s) / len(deltas) * 100
        print(f"  발차매칭 |오차|: median {st.median(deltas):.0f}s p90 {p(deltas,.9)}s "
              f"max {max(deltas)}s | ≤60s {within(60):.0f}% ≤180s {within(180):.0f}%")
    print(f"  글리치 버린 관측 총합: {glitch}")


def _reconstruct_one(task: tuple[str, str, bool]) -> list[dict]:
    """전노선 배치용 워커(피클 가능, 모듈 레벨). 저장까지 워커가 수행."""
    sid, date_str, save = task
    recs = reconstruct_stdid(sid, date_str)
    if save and recs:
        _save(recs, date_str, sid)
    return recs


if __name__ == "__main__":
    import argparse
    import os
    ap = argparse.ArgumentParser(description="trip 재구성 v1")
    ap.add_argument("stdid", help="단일 stdid 또는 'all'(전노선)")
    ap.add_argument("date", help="YYYYMMDD")
    ap.add_argument("--save", action="store_true", help="interim 에 jsonl 저장")
    ap.add_argument("--workers", type=int, default=os.cpu_count(),
                    help="전노선 모드 프로세스 수(기본=전 코어)")
    args = ap.parse_args()

    if args.stdid == "all":
        from concurrent.futures import ProcessPoolExecutor
        sids = stdids_with_data(args.date)
        print(f"전노선 재구성: {len(sids)}개 노선, date={args.date} "
              f"(workers={args.workers}/{os.cpu_count()}코어)")
        tasks = [(s, args.date, args.save) for s in sids]
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            results = list(ex.map(_reconstruct_one, tasks, chunksize=4))
        all_recs = [r for recs in results for r in recs]
        empty = sum(1 for recs in results if not recs)
        print(f"trip 산출 노선 {len(sids)-empty} / trip 0개 노선 {empty}")
        _aggregate(all_recs)
        if args.save:
            from src.common.paths import INTERIM_DIR
            print(f"저장 위치: {INTERIM_DIR / 'trips' / args.date}/")
    else:
        recs = reconstruct_stdid(args.stdid, args.date)
        _summary(recs)
        if args.save:
            _save(recs, args.date, args.stdid)
            from src.common.paths import INTERIM_DIR
            print(f"저장: {INTERIM_DIR / 'trips' / args.date / (args.stdid + '.jsonl')}")
