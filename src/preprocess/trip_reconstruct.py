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
from datetime import datetime, date as date_cls, timedelta

import holidays as _holidays

from src.common.paths import RAW_BUS_DIR, REF_SOURCE_DIR

# ── 잠정 임계값 (실데이터 튜닝 대상) ──────────────────────
MAX_KMH = 120.0        # 글리치: 틱간 추정속도가 이보다 크면 순간이동 의심
RESET_MARGIN = 5       # trip 분할: stop_ord 가 running_max 보다 이만큼 떨어지면 새 회차
GAP_MAX_SEC = 1800.0   # trip 분할: 같은 plate 관측 공백이 이보다 크면 분할
START_ORD_MAX = 2      # 시작 ord 가 이 이하면 "기점 포착" 후보(발차검출 시도)
R_PARK = 30.0          # 기점 정차 중심점 반경(m): 이 안이면 정차로 간주
R_DEPART = 50.0        # 발차 판정: 중심점에서 이만큼 벗어나고
K_DEPART = 3           #   K틱 연속 유지되면 지속이탈 = 발차
MATCH_GATE_SEC = 600   # 매칭 게이트: 검출발차가 최근접 예정슬롯과 이보다 멀면 off-schedule
                       #   (벽지노선 슬롯공백·미편성 운행 등 → 무의미한 강제매칭 방지)
R_STOP_MATCH = 150     # GPS 복원: ord 가 얼어 빠진 정류장을, 버스 GPS 가 정류장 좌표
                       #   이 반경 안에 든 샘플이 있으면 통과시각 복원(case A). 없으면
                       #   복원불가=쓸수없는구간(case B). 결측 ord별 GPS최근접 분포 p60≈160m.


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
def load_observations(stdid: int | str, dates: str | list[str]) -> dict[str, list[Obs]]:
    """raw bus jsonl → {plate: [Obs ...]} (plate 내 시간순).

    dates: 단일 날짜 또는 리스트. **여러 날짜를 하나의 연속 스트림으로 병합**한다
    (자정 무경계 — trip 분할은 달력 날짜가 아니라 gap·ord리셋 신호로만)."""
    if isinstance(dates, str):
        dates = [dates]
    out: dict[str, list[Obs]] = {}
    for date_str in dates:
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
def extract_segments(
    trip: list[Obs], departure_iso: str | None,
    stop_coords: dict[int, tuple[float, float]] | None = None,
) -> tuple[list[dict], list[dict], int, int]:
    """정류장 통과시각(stops) + 구간 소요시간(segments) + (gps복원수, 복원불가수).

    pass_ts[N] = stop_ord==N 최초 관측 ts. 단 기점(첫 ord)은 발차시각으로 대체.
    각 stop 에 `src`: "ord"(LATEST_STOP_ORD 전이) | "gps"(아래 복원).

    GPS 복원(§DATA_NOTES telemetry 불량): LATEST_STOP_ORD 가 얼어 점프하면
    그 사이 정류장 통과시각이 결측. 버스 GPS 는 그 정류장들을 물리적으로 지났으므로
    (검증됨), 점프 gap 시간창에서 정류장 좌표(`stop_coords`)에 R_STOP_MATCH 안으로
    근접한 GPS 샘플이 있으면 그 시각으로 복원(case A). 근접 샘플이 없으면(GPS 도 그
    구간에 얼어 한 번도 못 다가감) 복원불가 = 쓸 수 없는 구간 → 비움(case B).
    보간하지 않는다(작년 오염 방식 회피) — 실제 GPS 샘플만 사용."""
    first_ord = trip[0].so
    pass_ts: dict[int, str] = {}
    pass_epoch: dict[int, float] = {}
    src: dict[int, str] = {}
    for o in trip:
        if o.so is None or o.so in pass_ts:
            continue
        pass_ts[o.so] = o.iso
        pass_epoch[o.so] = o.ts
        src[o.so] = "ord"

    if departure_iso is not None and first_ord in pass_ts:
        pass_ts[first_ord] = departure_iso
        pass_epoch[first_ord] = datetime.fromisoformat(departure_iso).timestamp()

    # GPS 근접매칭 복원 (점프 gap 만 — 깨끗한 연속 ord 는 손대지 않음)
    n_recovered = n_unrecoverable = 0
    if stop_coords:
        observed = sorted(pass_epoch)
        for a, b in zip(observed, observed[1:]):
            if b - a < 2:        # 점프 아님(연속)
                continue
            win = [o for o in trip if pass_epoch[a] <= o.ts <= pass_epoch[b]]
            prev_t = pass_epoch[a]
            for m in range(a + 1, b):
                if m not in stop_coords:
                    continue
                slat, slng = stop_coords[m]
                cands = [o for o in win if o.ts > prev_t]   # 시간단조 보장
                best = min(cands, key=lambda o: haversine(o.lat, o.lng, slat, slng),
                           default=None)
                if best is not None and \
                        haversine(best.lat, best.lng, slat, slng) <= R_STOP_MATCH:
                    pass_ts[m] = best.iso
                    pass_epoch[m] = best.ts
                    src[m] = "gps"
                    prev_t = best.ts
                    n_recovered += 1
                else:
                    n_unrecoverable += 1   # GPS 도 근접 못 함 = 쓸 수 없는 구간

    ords = sorted(pass_ts)
    stops = [{"ord": n, "pass_ts": pass_ts[n], "src": src.get(n, "ord")} for n in ords]
    segments = []
    for n in ords:
        if n + 1 in pass_epoch:
            segments.append({
                "from": n, "to": n + 1,
                "elapsed_sec": round(pass_epoch[n + 1] - pass_epoch[n], 1),
                # 양끝 다 ord 면 high-conf, GPS복원 끼면 "gps"(다운스트림이 선택)
                "src": "ord" if src[n] == "ord" and src[n + 1] == "ord" else "gps",
            })
    return stops, segments, n_recovered, n_unrecoverable


# ── 시간표 prior / 매칭 (§4.4) ──────────────────────────
_kr_holidays_cache: dict[int, object] = {}


def _kr_holidays(year: int):
    """연도별 한국 공휴일(public) 캐시. 음력 명절·대체공휴일·선거일·재지정 제헌절 포함."""
    h = _kr_holidays_cache.get(year)
    if h is None:
        h = _holidays.SouthKorea(years=year, categories=("public",))
        _kr_holidays_cache[year] = h
    return h


def daytype_of(d: date_cls) -> str:
    """평일 / 토 / 일+공휴일. 공휴일(holidays KR public)은 토·평일보다 우선."""
    if d in _kr_holidays(d.year):
        return "일+공휴일"          # 공휴일이 토요일과 겹쳐도 일+공휴일 시간표 우선
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


def load_terminus_ord(stdid: int | str) -> int | None:
    """stops reference → 종점 ord(= max STOP_ORD).

    ⚠️ ROUTE_ORD 가 아니라 STOP_ORD 다. stops 레코드엔 두 ord 가 있다:
      - ROUTE_ORD: 노드 기반(비정류장 노드 포함) → 결번 존재(446중 76노선).
      - STOP_ORD : 정류장 연속 순번 1..N(전 446노선 결번 0, = len).
    버스 API LATEST_STOP_ORD 는 STOP_ORD 공간을 쓴다(검증: 결번노선에서 버스
    관측값이 ROUTE_ORD 결번값을 그대로 갖고 연속 1..N → STOP_ORD 와 일치).
    ROUTE_ORD 를 쓰면 종점이 과대추정되고 버스 ord 와 어긋난다."""
    fp = REF_SOURCE_DIR / "stops" / f"{stdid}.json"
    if not fp.exists():
        return None
    d = json.load(open(fp, encoding="utf-8"))
    ords = [s.get("STOP_ORD") for s in d.get("resultList", [])]
    ords = [o for o in ords if o is not None]
    return max(ords) if ords else None


def load_stop_coords(stdid: int | str) -> dict[int, tuple[float, float]]:
    """stops reference → {STOP_ORD: (lat, lng)}. GPS 근접매칭 복원용."""
    fp = REF_SOURCE_DIR / "stops" / f"{stdid}.json"
    if not fp.exists():
        return {}
    d = json.load(open(fp, encoding="utf-8"))
    out: dict[int, tuple[float, float]] = {}
    for s in d.get("resultList", []):
        so, lat, lng = s.get("STOP_ORD"), s.get("LAT"), s.get("LNG")
        if so is not None and lat is not None and lng is not None:
            out[so] = (lat, lng)
    return out


def _parse_slots(sched: list[str]) -> tuple[list[str], list[int]]:
    """예정 시간표 → (hhmm 정렬, 분단위 정렬). 파싱불가 슬롯은 버림."""
    pairs = []
    for hhmm in sched:
        try:
            h, m = hhmm.split(":")
            pairs.append((hhmm.strip(), int(h) * 60 + int(m)))
        except ValueError:
            continue
    pairs.sort(key=lambda p: p[1])
    return [p[0] for p in pairs], [p[1] for p in pairs]


def assign_departures_to_slots(
    dep_min: list[float], slot_min: list[int], gate_sec: float,
) -> tuple[list[int | None], list[int]]:
    """검출발차열 ↔ 예정슬롯열 시간순보존 1:1 배정 (greedy 최근접 대체).

    둘 다 시간정렬 입력. 단조 매칭 DP 로 `(매칭수 최대, 총|delta| 최소)` 를
    사전식으로 최적화. 슬롯·발차 각각 최대 1회, 게이트(gate_sec) 초과 매칭 금지,
    순서 보존(앞선 발차가 뒤 슬롯에 붙고 뒤 발차가 앞 슬롯에 붙는 교차 불가).
    → greedy 의 '두 버스가 같은 슬롯' / 수집중단 시 오배정 구조적 제거.

    반환 (dep_slot, unmatched_slots): dep_slot[i] = 발차 i 에 배정된 슬롯 idx 또는 None,
    unmatched_slots = 배정 안 된 슬롯 idx 목록(=관측 못 한 예정 발차 → 수집공백·미운행)."""
    m, n = len(dep_min), len(slot_min)
    gate_min = gate_sec / 60.0
    # dp[i][j] = (매칭수, -총delta) 사전식 최대. bp = 역추적용 선택.
    dp = [[(0, 0.0)] * (n + 1) for _ in range(m + 1)]
    bp = [[""] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        for j in range(n + 1):
            if i == 0 and j == 0:
                continue
            cands = []
            if i > 0:
                cands.append((dp[i - 1][j], "d"))          # 발차 i-1 미매칭
            if j > 0:
                cands.append((dp[i][j - 1], "s"))          # 슬롯 j-1 미매칭
            if i > 0 and j > 0:
                d = abs(dep_min[i - 1] - slot_min[j - 1])
                if d <= gate_min:
                    pm, pd = dp[i - 1][j - 1]
                    cands.append(((pm + 1, pd - d), "m"))   # 매칭
            dp[i][j], bp[i][j] = max(cands, key=lambda c: c[0])

    dep_slot: list[int | None] = [None] * m
    matched_slot = [False] * n
    i, j = m, n
    while i > 0 or j > 0:
        c = bp[i][j]
        if c == "d":
            i -= 1
        elif c == "s":
            j -= 1
        else:  # "m"
            dep_slot[i - 1] = j - 1
            matched_slot[j - 1] = True
            i -= 1
            j -= 1
    unmatched = [k for k in range(n) if not matched_slot[k]]
    return dep_slot, unmatched


# ── 한 노선 재구성 ──────────────────────────────────────
def reconstruct_stdid(stdid: int | str, date_str: str) -> tuple[list[dict], dict]:
    """반환 (trip 레코드들, 노선단위 매칭진단). 진단=미매칭 슬롯 등."""
    meta = load_route_meta(stdid)
    svc_date = datetime.strptime(date_str, "%Y%m%d").date()
    dtype = daytype_of(svc_date)
    slot_hhmm, slot_min = _parse_slots(meta.get("sched", {}).get(dtype, []))

    # 자정 무경계: 전날·다음날까지 연속 로드해 split 이 신호로만 자르게 한다.
    # trip 은 "시작(첫 관측) 날짜"가 소유 — owner != date_str 면 그 trip 은 다른 운행일
    # 소유라 스킵(인접일 처리 때 잡힘). 이러면 23h→00h crosser 온전·중복 0·24h버스 OK.
    prev_d = (svc_date - timedelta(days=1)).strftime("%Y%m%d")
    next_d = (svc_date + timedelta(days=1)).strftime("%Y%m%d")
    by_plate = load_observations(stdid, [prev_d, date_str, next_d])
    stop_coords = load_stop_coords(stdid)
    # 종점 ord: reference(권위) 우선, 없으면 그날 관측 최대 ord 로 폴백
    terminus_ord = load_terminus_ord(stdid)
    if terminus_ord is None:
        terminus_ord = max((o.so for seq in by_plate.values() for o in seq
                            if o.so is not None), default=0)

    # 1) trip 레코드 (매칭 필드는 아래 노선전역 배정에서 채움)
    records: list[dict] = []
    for plate, seq in by_plate.items():
        clean, dropped = filter_glitches(seq)
        for trip in split_trips(clean):
            if len(trip) < 2:
                continue
            if trip[0].iso[:10].replace("-", "") != date_str:
                continue   # 시작일이 다른 운행일 → 인접일 처리에서 소유(중복방지)
            dep_iso, quality = detect_departure(trip)
            stops, segments, n_rec, n_unrec = extract_segments(
                trip, dep_iso, stop_coords)
            if not segments:
                continue
            max_ord = max((o.so for o in trip if o.so is not None), default=0)
            records.append({
                "stdid": int(stdid), "brt_no": meta.get("brt_no"),
                "plate_no": plate, "service_date": date_str, "daytype": dtype,
                "departure_ts": dep_iso, "departure_quality": quality,
                "matched_sched": None, "sched_delta_sec": None,
                "on_schedule": None,  # 발차없음(mid_entry)=null, 발차있음은 아래서 T/F
                "start_ord": trip[0].so, "end_ord": max_ord,
                "n_stops_route": terminus_ord,
                "reached_terminus": terminus_ord > 0 and max_ord >= terminus_ord - 1,
                "n_obs": len(trip), "glitch_dropped": dropped,
                "seg_gps_recovered": n_rec,        # ord 얼음 → GPS 근접으로 복원한 정류장 수
                "stops_unrecoverable": n_unrec,    # ord·GPS 둘 다 얼어 못 잡은 정류장 수(쓸수없음)
                "stops": stops, "segments": segments,
            })

    # 2) 노선전역 발차↔슬롯 1:1 배정 (시간순)
    dep_recs = sorted(
        ((datetime.fromisoformat(r["departure_ts"]), k)
         for k, r in enumerate(records) if r["departure_ts"]),
        key=lambda x: x[0])
    dep_min = [t.hour * 60 + t.minute + t.second / 60 for t, _ in dep_recs]
    dep_slot, unmatched_slot = assign_departures_to_slots(
        dep_min, slot_min, MATCH_GATE_SEC)

    for di, (_, k) in enumerate(dep_recs):
        sj = dep_slot[di]
        if sj is not None:
            records[k]["matched_sched"] = slot_hhmm[sj]
            records[k]["sched_delta_sec"] = int(round((dep_min[di] - slot_min[sj]) * 60))
            records[k]["on_schedule"] = True
        else:
            records[k]["on_schedule"] = False   # 발차 검출됐으나 게이트 내 배정슬롯 없음

    diag = {
        "stdid": int(stdid), "service_date": date_str, "daytype": dtype,
        "n_slots": len(slot_min), "n_dep": len(dep_recs),
        "n_matched": sum(1 for x in dep_slot if x is not None),
        "n_off_schedule_dep": sum(1 for x in dep_slot if x is None),
        "unmatched_slots": [slot_hhmm[j] for j in unmatched_slot],
    }
    return records, diag


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


def _print_diag(diag: dict) -> None:
    print(f"  매칭: 발차 {diag['n_dep']} / 슬롯 {diag['n_slots']} → "
          f"배정 {diag['n_matched']}, off-schedule 발차 {diag['n_off_schedule_dep']}, "
          f"미매칭 슬롯 {len(diag['unmatched_slots'])}{diag['unmatched_slots'][:8]}")


def _aggregate(all_recs: list[dict], all_diags: list[dict]) -> None:
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
    # 노선전역 1:1 배정 결과 집계
    tot_dep = sum(d["n_dep"] for d in all_diags)
    tot_slot = sum(d["n_slots"] for d in all_diags)
    tot_match = sum(d["n_matched"] for d in all_diags)
    tot_off = sum(d["n_off_schedule_dep"] for d in all_diags)
    tot_unmatched = sum(len(d["unmatched_slots"]) for d in all_diags)
    print(f"  매칭(전역1:1, 게이트 {MATCH_GATE_SEC}s): 발차 {tot_dep} 중 배정 {tot_match} "
          f"/ off-schedule 발차 {tot_off} ({tot_off/tot_dep*100:.1f}%)" if tot_dep else "")
    print(f"  예정슬롯 {tot_slot} 중 미매칭 {tot_unmatched} "
          f"({tot_unmatched/tot_slot*100:.0f}%, =수집공백·미운행·검출누락)" if tot_slot else "")
    # ord 얼음 GPS 복원 집계
    rec = sum(r.get("seg_gps_recovered", 0) for r in all_recs)
    unrec = sum(r.get("stops_unrecoverable", 0) for r in all_recs)
    seg_gps = sum(1 for r in all_recs for s in r["segments"] if s.get("src") == "gps")
    seg_all = sum(len(r["segments"]) for r in all_recs)
    print(f"  ord얼음 정류장: GPS복원 {rec} / 복원불가(쓸수없음) {unrec} "
          f"({rec/(rec+unrec)*100:.0f}% 복원)" if rec + unrec else "  ord얼음: 없음")
    print(f"  구간 출처: ord(고신뢰) {seg_all-seg_gps} / gps복원 {seg_gps} ({seg_gps/seg_all*100:.1f}%)")
    print(f"  글리치 버린 관측 총합: {glitch}")


def _save_diags(diags: list[dict], date_str: str) -> None:
    from src.common.paths import INTERIM_DIR
    out_dir = INTERIM_DIR / "trips" / date_str
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "_match_diag.jsonl", "w", encoding="utf-8") as f:
        for d in diags:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")


def _reconstruct_one(task: tuple[str, str, bool]) -> tuple[list[dict], dict]:
    """전노선 배치용 워커(피클 가능, 모듈 레벨). 저장까지 워커가 수행."""
    sid, date_str, save = task
    recs, diag = reconstruct_stdid(sid, date_str)
    if save and recs:
        _save(recs, date_str, sid)
    return recs, diag


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
        all_recs = [r for recs, _ in results for r in recs]
        all_diags = [diag for _, diag in results]
        empty = sum(1 for recs, _ in results if not recs)
        print(f"trip 산출 노선 {len(sids)-empty} / trip 0개 노선 {empty}")
        _aggregate(all_recs, all_diags)
        if args.save:
            from src.common.paths import INTERIM_DIR
            _save_diags(all_diags, args.date)
            print(f"저장 위치: {INTERIM_DIR / 'trips' / args.date}/ (+_match_diag.jsonl)")
    else:
        recs, diag = reconstruct_stdid(args.stdid, args.date)
        _summary(recs)
        _print_diag(diag)
        if args.save:
            _save(recs, args.date, args.stdid)
            from src.common.paths import INTERIM_DIR
            print(f"저장: {INTERIM_DIR / 'trips' / args.date / (args.stdid + '.jsonl')}")
