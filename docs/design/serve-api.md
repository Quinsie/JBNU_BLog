# serve API 설계 (Phase 7)

> 앱(Flutter)-facing API. 프론트와의 계약. **살아있는 계약서 = Swagger(`/docs`)**, 이 문서는 설계·결정·운영 근거.
> 진행상황은 [STATUS](../STATUS.md), 전체 그림은 [ROADMAP](../ROADMAP.md).

## 1. 목적
전주 시내버스 **목표 도착형 이동계획 에이전트**의 백엔드. 사용자가 *목적지 + 목표 도착시각*을 주면
서버가 "지금 출발 / 어떤 버스 / 안전한 대안 / 놓칠 확률"을 계산해 돌려준다.

핵심 원칙:
- **에이전트 의사결정은 서버에서**(클라 조합 아님). ETA모델·놓칠확률·대안이 전부 서버 자산.
- 기본 **dummy 로 전 계약을 먼저 띄우고**, 기능 완성 계층부터 **라우터 단위로 real 교체**.
- 응답마다 출처 플래그(`source` / `dummy` / `eta_source`)로 real/dummy 를 투명하게.

스택: **FastAPI**(코드가 곧 OpenAPI/Swagger) · pydantic v2 · uvicorn.

## 2. 계층 용어 (확정 — "정적" 금지어)
"정적"이 데이터(노선·정류장)와 1차추론 양쪽을 가리켜 혼동 → 폐기하고 아래로 고정.

| 계층 | 용어 | 모델 | 데이터 출처 | 상태 |
|---|---|---|---|---|
| 노선·정류장·polyline·시간표 | **기준데이터 (reference)** | — | `REF_BUILT/stdid_list`·`REF_SOURCE/stops`·`vtx` | **real** |
| BIS 실시간 버스위치 | **실황 (live)** | — | 우리 수집 raw 최신 스냅샷 패스스루 | **real** |
| 배차시각 기반 도착예상 | **사전추론 (pre-eta, 1차)** | 1차 | (모델) | dummy |
| 실시간위치 기반 도착예상 | **실시간추론 (live-eta, 2차)** | 2차 | (모델) | dummy |
| 목표도착 이동계획 | **plan (에이전트)** | 에이전트+ETA | (에이전트) | dummy |
| 날씨 | **weather** | — | 우리 수집 weather + KMA 격자 | **real** |

도보 ETA(OSRM)는 **엔드포인트 아님** — plan 내부 모듈로 흡수(별도로 도보만 돌려줄 필요 없음).

## 3. 진입 결정 (프론트 협의)
1. **에이전트 = 서버 `/plan` 단일 엔드포인트**(클라 조합 아님). 로직 보호·일관성·앱 경량·모델갱신 시 앱 재배포 불필요.
2. **목적지 = 임의 지점(주소/좌표)** — geocoding + 출발/도착 양쪽 도보. (정류장 단위 아님)
3. **도보 = OSRM 전주 추출**(서버 미설치 → 설치 예정). 그 전엔 plan 내부 더미.

## 4. 엔드포인트 (`/v1` 프리픽스)
| 메서드 | 경로 | 계층 | 상태 |
|---|---|---|---|
| GET | `/routes` | 기준데이터 | real |
| GET | `/routes/{stdid}` | 기준데이터(정류장 시퀀스 + polyline) | real |
| GET | `/stops/{stop_id}` | 기준데이터(좌표·경유노선) | real |
| GET | `/stops/search?q=` | 기준데이터 | real |
| GET | `/stops/nearby?lat=&lng=&radius_m=` | 기준데이터 | real |
| GET | `/buses?stdid=` | 실황 | real |
| GET | `/buses/{bus_id}` | 실황 | real |
| GET | `/stops/{stop_id}/arrivals` | 실황(stops_away) + eta_sec 더미 | 부분 real |
| GET | `/stops/{stop_id}/eta?mode=pre\|live` | 사전/실시간추론 | dummy |
| GET | `/buses/{bus_id}/eta?mode=pre\|live` | 사전/실시간추론 | dummy |
| GET | `/weather?lat=&lng=` | 날씨(현재+예보) | real |
| POST | `/plan`, `/plan/recheck` | 에이전트 | dummy |
| GET | `/health` | 운영 | real |

좌표는 (lat,lng) WGS84, 시각은 KST ISO8601, 잔여시간은 `*_sec`. 스키마 상세는 Swagger.

## 5. 데이터 액세스 (`src/serve/store.py`)
real 응답은 전부 여기 한 곳에서. 경로는 `src/common/paths.py`(절대경로 0).
- **기준데이터**: `stdid_list`(446) + 정류장 인덱스(stop_id→좌표·경유 stdid·ord, 1회 빌드 캐시). vtx→polyline.
- **실황**: ITS 를 **추가 호출하지 않고** 우리가 이미 수집한 `raw/bus/{stdid}/{YYYYMMDD_HH}.jsonl`의
  최신 줄을 패스스루(추가 부하 0 · IP차단 리스크 0). 전 노선 스냅샷 **TTL 8s 캐시**.
  `arrivals` 의 `stops_away` = 정류장 ord − 버스 현재 ord(지난 버스 제외).
- **날씨**: 좌표→KMA 격자(`common.grid.latlng_to_grid`) → 초단기실황(현재)+초단기예보(시간별). 실황 SKY 결측은 예보 첫 항목으로 보강.

## 6. 더미 정책
- "더미"임을 **명시**: `dummy:true`(StopEta·BusEta·PlanResponse) / `source:dummy` / `eta_source:dummy`.
- 값은 **쓰레기·null 금지 — real 에 grounding** 한 그럴듯한 값. 실제 정류장·노선·버스로 구성하고
  *예측 수치(시각·확률)만* fabricate(`src/serve/dummy.py`). 결정적(난수 없음).
- real 교체 시 모델 추론 호출 + `dummy:false`. **계약 모양은 유지**(세부 명세는 조금씩 바뀔 수 있음).

## 7. 운영 / 외부 공개
- 기동: `bash scripts/run_serve.sh` (uvicorn :8000 + cloudflared 임시 터널).
- **방화벽이 QUIC(UDP)을 막음 → cloudflared `--protocol http2`(TCP443) 필수**(없으면 CF 1033).
- **trycloudflare URL 은 cloudflared 재기동 시에만 변경**(코드 수정으론 안 바뀜. uvicorn `--reload` 면 코드 저장 자동반영).
- Cloudflare Tunnel 서비스는 **무료**(트래픽 과금 없음). 고정 URL = named tunnel + Cloudflare 등록 도메인(도메인값 별도). 무료 고정 대안 = Tailscale Funnel.
- ⚠️ 보류(공개 전 필수): **API키 + rate limit**, systemd 영속화(현재 자동복구 없음).

## 8. 남은 작업
1. geocoding(Kakao Local 또는 VWorld 키) + OSRM 전주 추출 설치 → plan 내부 도보 real.
2. 1차/2차 모델 완성 시 추론(pre/live-eta)·plan 라우터 real 교체.
3. 배포 영속화: systemd(uvicorn+cloudflared) + named tunnel(고정 URL) + API키/rate limit.
