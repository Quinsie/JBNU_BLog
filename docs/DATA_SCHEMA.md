# DATA_SCHEMA — 모든 데이터 파일 구조

> **새 데이터 파일(raw·중간산출물)을 만들면 반드시 여기에 구조를 표기한다.**
> 파이프라인 단계 = 디렉토리: `reference → raw → interim → features → models → predictions`.
> 경로 해석은 `src/common/paths.py` 한 곳. raw 만 HDD 심볼릭, interim 이하 로컬(gitignore).

---

## raw/ — 수집 원천 (무손실, HDD, gitignore)

수집 1회 = 1레코드. 실패·빈응답도 그대로 저장(무손실). 공통 필드: `ts`(ISO+09:00), `ok`, `status`(HTTP), `elapsed_ms`. 실패 시 `error`, 일부 `raw`(응답 앞부분).

### raw/bus/{stdid}/{YYYYMMDD_HH}.jsonl
ITS `selectBisRouteLocationList`. 한 줄 = 한 노선 1폴링. 시(時) 버킷 파일.
```jsonc
{ "ts","stdid","status","ok","elapsed_ms",
  "body": { "busPosList": [ {
     "PLATE_NO": "2065  ",      // 차량번호(공백패딩) = trip 식별키
     "LATEST_STOP_ORD": 14,     // 마지막 통과 정류장 순번. ord=N → N→N+1 주행중
     "CURRENT_NODE_ORD": 18,    // 노드 순번(node−stop 오프셋 0→증가). 모델 미사용
     "LAT": 35.815288, "LNG": 127.139784,
     "SPEED": 34,               // km/h 추정. 정차 시 1, held 가능
     "LOW_FLAG": "0",           // 저상버스 여부
     "COMPANY_NAME": "성진여객", "TELNO": "063-214-5551"
  } ] } }
// 실패 시: body 없음 + error("HTTP_xxx"|"WAF"|"TIMEOUT"...) (+raw). 빈응답: body=null.
```
⚠️ `busPosList` = **그 순간 떠있는 버스만**. 발차/도착/회차 필드 **없음** → 발차는 GPS 궤적으로 검출.

### raw/traffic/{YYYYMMDD_HHMM}.json
ITS `selectTrafVrtxList`. 1분 주기, 한 파일 = 한 호출. 전주 BBOX 도로 링크 혼잡도.
```jsonc
{ "ts","status","ok","elapsed_ms",
  "body": { "resultList": [ {
     "ID": "...", "ORD": 1,             // 링크 식별·순번
     "X_CRDN": ..., "Y_CRDN": ...,      // 좌표
     "GRADE": 1                          // 혼잡등급
  } ] } }
```

### raw/weather/{type}/{YYYYMMDD_HH}.json  (KMA, 전주 격자 43개)
`type` = `realtime`(초단기실황 getUltraSrtNcst) · `shortForecast`(초단기예보 getUltraSrtFcst) · `midForecast`(단기예보 getVilageFcst).
```jsonc
{ "base_date","base_time","ts","api",
  "grids": { "62_91": {            // "nx_ny" 격자키
     "params": {"nx":62,"ny":91,"base_date","base_time", ...}, "status","ok","ts",
     "body": {"response": {"header": {...},
        "body": {"items": {"item": [
           {"baseDate","baseTime","category":"PTY","nx","ny",
            "obsrValue":"0"}   // 실황=obsrValue / 예보=fcstValue(+fcstDate/fcstTime)
        ]}}}}
  }, ... } }
// category: PTY(강수형태) RN1(1시간강수) T1H(기온) REH(습도) WSD(풍속) 등 KMA 코드.
```

### raw/weather/longForecast/{YYYYMMDD_HH}.json  (중기예보)
```jsonc
{ "ts","tmFc":"202605260600",   // 발표시각
  "land": {"ts","params","status","ok","error","raw","elapsed_ms"},  // getMidLandFcst(육상)
  "ta":   {"ts","params","status","ok","error","raw","elapsed_ms"} } // getMidTa(기온)
// ⚠️ 현재 KMA 중기예보 구독 미반영으로 403(land/ta error) — 비차단.
```

### raw/incident/
WAF 차단으로 **미수집(idle)**. `INCIDENT_URL` 설정 시에만 가동.

---

## reference/ — 정적 기준 데이터 (git 추적)

### reference/source/timetable/{stdid}.json
ITS `selectBisRouteTimeInfo`. 노선(방향)별 시점 시간표.
```jsonc
{ "fetched_at","stdid",
  "result": {
     "BRT_NO":"385", "BRT_STDID":305200112, "BRT_DNUM":32,   // 노선번호·하루 발차수
     "BRT_SNAME":"전주대학교", "BRT_ENAME":"우석대종점",       // 기점·종점명
     "BRT_LENGTH":21.4,
     "COURSE_STIMELIST":" 06:14, 06:42, ...",   // 평일 예정발차(쉼표구분 HH:MM)
     "SAT_NLIST":"...",                          // 토요일
     "HOLI_NLIST":"..." },                       // 일+공휴일
  "timeList": ["06:14","06:42", ...] }           // COURSE_STIMELIST(평일) 파싱본
```
- daytype 3클래스: 평일=COURSE_STIMELIST · 토=SAT_NLIST · 일+공휴일=HOLI_NLIST.

### reference/source/  기타
`route_list`(전체노선) · `subList`(노선↔방향/stdid) · `stops`(노선별 정류장) · `vtx`(노선 선형 좌표열). ⚠️ vtx 일부 어긋남 → 올해 데이터로 재검증 필요.
- **stops 의 ord 2종**: `ROUTE_ORD`(노드기반, 결번有) vs `STOP_ORD`(정류장 연속 1..N). 버스 `LATEST_STOP_ORD` = **STOP_ORD 공간** → 종점 ord·trip 재구성은 STOP_ORD 사용(DATA_NOTES 검증).

### reference/built/
- `stdid_list.json` — `{routes:[{stdid, first_time, last_time, ...}]}` 446개(수집 대상).
- `nx_ny_coords.json` — 전주 KMA 격자 43개 좌표(격자식 KMA 표준점 검증).

---

## interim/ — 전처리 산출물 (재생성 가능, 로컬, gitignore)

### interim/trips/{YYYYMMDD}/{stdid}.jsonl
`src/preprocess/trip_reconstruct.py` 출력. 한 줄 = 재구성된 trip 1개(차량 1회 운행).
```jsonc
{ "stdid":305200112, "brt_no":"385", "plate_no":"2055",
  "service_date":"20260526", "daytype":"평일",
  "departure_ts":"2026-05-26T21:36:56+09:00",  // 검출 실발차(없으면 null)
  "departure_quality":"origin_wait",            // origin_wait|origin_moving|mid_entry
  "matched_sched":"21:38", "sched_delta_sec":-64, // 배정된 예정슬롯 + (검출−예정)초 (미배정 시 둘 다 null)
  "on_schedule":true,                           // 전역1:1 배정됨=true / 발차검출O 배정X(추가운행·검출이상)=false / 발차없음(mid_entry)=null
  "start_ord":1, "end_ord":42,
  "n_stops_route":43,                           // 노선 종점 ord(reference max STOP_ORD, =정류장수). ROUTE_ORD 아님 — 버스 ord 는 STOP_ORD 공간
  "reached_terminus":true,                      // end_ord >= n_stops_route-1 (ord 의미상 −1 허용)
  "n_obs":328, "glitch_dropped":0,
  "seg_gps_recovered":2,                        // ord 얼음으로 결측된 정류장을 GPS 근접매칭으로 복원한 수
  "stops_unrecoverable":1,                      // ord·GPS 둘 다 얼어 못 잡은 정류장 수(쓸 수 없는 구간)
  "stops":    [ {"ord":1,"pass_ts":"...","src":"ord"}, {"ord":7,"pass_ts":"...","src":"gps"}, ... ],
  "segments": [ {"from":1,"to":2,"elapsed_sec":210.0,"src":"ord"}, ... ] }  // ← 1차 모델 y(구간소요)
}
```
- `pass_ts[기점ord]` = 발차시각으로 대체(첫관측은 정차/시스템-on 시점이라 통과 아님).
- **`src`** (stops·segments): `"ord"`=LATEST_STOP_ORD 전이 관측(고신뢰) / `"gps"`=ord 가 얼어 결측된 걸 GPS↔정류장좌표 근접매칭(`R_STOP_MATCH`=150m)으로 복원(저신뢰). segment 는 양끝 다 ord 면 "ord", GPS복원 끼면 "gps". **y 학습 시 신뢰도로 필터/가중 가능.** GPS 도 얼어 근접 못 한 정류장은 복원 안 함(보간 금지) → 그 구간 비움(`stops_unrecoverable`). 근거 [DATA_NOTES](DATA_NOTES.md) telemetry 불량.
- 발차↔슬롯은 **노선전역 시간순 1:1 배정**(greedy 최근접 아님 — `assign_departures_to_slots`). 중복매칭·순서꼬임 구조적 제거.
- 설계 근거: [design/trip-reconstruction.md](design/trip-reconstruction.md), [design/first-model.md](design/first-model.md) §3.1.

### interim/trips/{YYYYMMDD}/_match_diag.jsonl
노선전역 발차↔슬롯 배정 진단(한 줄 = 한 노선). trip 레코드 밖 노선단위 리포트.
```jsonc
{ "stdid":305001763, "service_date":"20260526", "daytype":"평일",
  "n_slots":36, "n_dep":6,          // 예정슬롯 수 / 검출발차 수
  "n_matched":5,                     // 1:1 배정 성공
  "n_off_schedule_dep":1,            // 발차검출됐으나 미배정(추가운행·검출이상·게이트밖)
  "unmatched_slots":["06:20","07:00", ...] }  // 관측 못 한 예정 발차(수집공백·미운행·검출누락)
```
- ⚠️ 수집창이 부분(예: 5/26 저녁만)이면 unmatched_slots 가 대부분(아침·낮 슬롯) — 정상. 전일 수집 시 해소.
