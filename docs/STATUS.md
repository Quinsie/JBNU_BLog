# STATUS

> **매 작업(commit)마다 갱신.** "지금 어디까지 왔고, 바로 다음 뭘 할지"를 항상 여기서 확인.
> 전체 그림·단계 의존성은 [ROADMAP.md](ROADMAP.md), 데이터 신뢰성은 [DATA_NOTES.md](DATA_NOTES.md).

## 현재 위치
**Phase 3 trip 재구성 v1 검증 완료 → v1.1 정련 진행 중** (branch `design/first-model`). 수집기는 `.74` 우회로 가동 중.
- v1.1 ①공휴일 캘린더 **완료**(`holidays` KR public: 음력명절·대체공휴일·선거일·2026 재지정 제헌절, 휴일>토 우선). ②종점 reference 연결 **완료**(max ROUTE_ORD 권위·`n_stops_route` 기록, 종점도달 55%로 정직화). ③이상치 분석 ④시간표 prior 게이팅 = 잔여.
- 1차 모델 검증·결정 → [design/first-model.md](design/first-model.md) (갈림길 3개 확정).
- trip 재구성 설계 확정 → [design/trip-reconstruction.md](design/trip-reconstruction.md) (발차검출·종료일반화·구간타깃).
- **v1 스크립트** `src/preprocess/trip_reconstruct.py`: 305200112 검증 — 발차 5건 전부 예정시간표 ±64s 매칭, 품질분기·종점·글리치·공백분할 정상.

## 완료
- **Phase 0**: 디렉토리 골격, `paths.py`(절대경로 0), `.gitignore`, conda env `Blog`, docs, `CLAUDE.md`, README.
- **공유 데이터**: `blog` 그룹(jiho·yubin·hyewon·gaeun), `/mnt/data1/B_Log`=`jiho:blog` 2775(setgid), `data/raw` 심볼릭. `setup_data.sh`.
- **git**: `~/BLog` 독립 리포, remote `Quinsie/JBNU_BLog` (push 보류).
- **Phase 2 정적 기준 데이터** (API 실수집, 446): `reference/source/`(route_list·subList·stops·vtx·timetable, 24MB) + `reference/built/`(stdid_list 446, nx_ny_coords 격자 43). 격자식 KMA 표준점 검증.
- **Phase 1 수집기** (`src/collector/`): bus(적응형+버스트금지)·traffic·weather(전격자43)·incident + supervisor(flock) + common(clock/log/io) + health.
  - **수집 rate 정책**: 버스 있으면 10s / 빈 응답이면 60s 백오프. 발사 간 20ms 강제(버스트 하드금지, 최대 50req/s). 로컬 mock 검증: 최소간격 20.2ms, 커버 446/446.
  - **systemd `blog-collector`** 설치·enabled(부팅 자동). env python 직접 실행.

## ⚠️ 막힌 것 / 임시조치
- **ITS IP 차단** (`.73`, 부하테스트 누적). 5시간+ 지속 = 수 시간~24h급 임시차단(영구 아님).
  - 🔧 **임시 우회 가동 중**: 보조 IP `210.117.134.74`(.73과 같은 /18, ARP로 빈 IP 확인)를 `enp6s0`에 붙이고, 수집기 ITS 아웃바운드를 거기로 소스바인딩(`ITS_SOURCE_IP` env, 없으면 기본 IP 자동 폴백). `.74`로 ITS 200 확인, 수집 재개(20:18~). **비영속(리부팅 시 IP 소멸→코드가 .73 폴백)**.
  - **원복(`.73` 차단 풀리면)**: ① `.env`의 `ITS_SOURCE_IP` 줄 삭제 ② `sudo ip addr del 210.117.134.74/18 dev enp6s0` ③ `sudo systemctl restart blog-collector`. (코드는 그대로 둬도 무해 — env 없으면 기본 IP 사용)
  - cf. `.74`는 **임시**(사용자 요청: 28일 02:00 무렵 .73 회복 기대). 자동원복 타이머는 두지 않음. (5/27 02시 기준 .73 여전히 차단)
- ~~중기예보(longForecast) 403~~ **해결**(5/26): KMA 중기예보 API 구독 반영 → land/ta ok=200 실데이터 수집 중.

## 다음 할 일
1. **trip 재구성 v1 전노선 스트레스테스트**: 저녁 데이터로 전 stdid 돌려 집계(풀trip 수율·발차매칭 분포·품질분기·이상치) → 임계값(R/K/gap) 튜닝.
2. **v1.1**: 시간표 prior 슬롯 게이팅(발차 애매구간 보정), 공휴일 캘린더, 종점 stop수 reference 연결.
3. **1차 feature 가공** → GBDT 학습 (Phase 4). 미결정 갈림길 #3(지리종속성→route_nodes) 결판.
4. (운영) `.73` 차단 풀리면 `.74` 우회 원복(STATUS 위 §원복).

## 후처리에서 풀 과제 (기억)
- **배차 시각 식별**: raw 만 받으므로 trip↔시간표 매칭 휴리스틱 필요.
- **vtx 불신**: 작년 101개 노선 vtx 어긋남 → 구글맵으로 수작업 보정했었음. mtime으로 복원: [design/vtx_manual_2025.json](design/vtx_manual_2025.json). 검수기=`checkRoute.py`(정류장 누락수), 육안검수 일회용 스크립트는 소실. **올해 데이터로 재구성·재검증 필요** = 지리기반 1차 모델의 선행조건.
  - ⚠️ route_nodes 가 1차 무관(2차 전용)이라던 기존 가정은 재검토 중 — 지리기반 종속성·교통결합을 1차에 넣으면 1차도 route_nodes 필요(미결정 갈림길 #3).

## 확정 사항
- 단일 서버 전부 처리(backend/midServer 분리 없음). app(Flutter)+src(Python) monorepo.
- 원천(버스·교통·날씨·사고 실시간)만 HDD 심볼릭. 정적/파생은 repo(reference 만 git).
- baseline=이가은 collector(아이디어). 1차=MLP/GBDT, 2차=Transformer. docs 한글, commit 단위 추적.
