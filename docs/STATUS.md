# STATUS

> **매 작업(commit)마다 갱신.** "지금 어디까지 왔고, 바로 다음 뭘 할지"를 항상 여기서 확인.
> 전체 그림·단계 의존성은 [ROADMAP.md](ROADMAP.md), 데이터 신뢰성은 [DATA_NOTES.md](DATA_NOTES.md).

## 현재 위치
**Phase 3 trip 재구성 v1.1 + robustness + 첫 풀데 검증 완료** (branch `design/first-model`). 수집기는 `.74` 우회로 가동 중.
다음: **Phase 4 — 1차 모델 설계 진입**. 진입 path(Path A vtx 재검증 선행 vs Path B 비지리 baseline 우선) 결정 대기.

**trip 재구성 `src/preprocess/trip_reconstruct.py` — 출력 정착**: trip당 `stdid·brt_no·plate_no·company_name·service_date·daytype·발차(검출+품질)·매칭(on_schedule)·종점·구간(elapsed+src)·품질플래그`. 노선단위 진단 `_match_diag.jsonl`. 스키마 상세 [DATA_SCHEMA](DATA_SCHEMA.md).

v1.1 + 보강 항목(상세는 [DATA_NOTES](DATA_NOTES.md)·[design/trip-reconstruction.md](design/trip-reconstruction.md)):
- ① 공휴일 캘린더(`holidays` KR) ② 종점=**max STOP_ORD**(ROUTE_ORD 아님) ③ 이상치 분석(시간표 최신 재확인) ④ 발차↔슬롯 **노선전역 1:1 배정**(greedy 폐기, max delta 8787→584s) ⑤ 매칭게이트 600s
- ⑥ **ord 얼음 GPS 근접매칭 복원**(API불신·교차검증, `src=ord/gps`, 보간금지) ⑦ **자정 무경계**(연속성 기반, 24h버스·전국확장 대비) ⑧ **off-route 게이팅**(불가능 ord 드롭 + `off_route_obs` flag)
- 회사+번호판을 차량/기사 키로(`company_name`, PLATE 4자리 비유일 보강)

**raw robustness 점검 완료**(5/26 31만 관측 기본위생 + 5/27 풀데 172만 관측 검증): 좌표·SPEED·중복·badjson 0. PLATE_NO 비유일·off-route·자정·ord얼음 전부 처리. (설계근거 [design/first-model.md](design/first-model.md))

**5/27 첫 풀데이터(24h, 평일) funnel 확정**:
```
raw 차량관측 1,719,458 → 시간표슬롯 4,466 → trip 4,290 → 1차 학습 trip 4,063 (슬롯 91%) → segment 184,595 (y라벨)
```
종점도달 89%, 발차매칭 median 24s(≤180s 97%), off-schedule 1.6%. 손실 = 슬롯→trip 9% (검출누락+결행+미운행) + segment 단위 추가 1.07% 복원불가. 검토거리 4건은 [DATA_NOTES](DATA_NOTES.md) 5/27 항목.

**갈림길 #3 — 정리**: 설계상 결정 **완료**(=지리종속성 1차 통합 + route_nodes·교통 typical 매핑을 1차 임계경로에 포함, [first-model.md](design/first-model.md) §2.2·§5). STATUS 의 기존 "미결정" 표현은 부정확이었음 — 결정은 됐고, 그 선행작업(vtx 올해데이터 재검증)이 미착수.

## 완료
- **Phase 0**: 디렉토리 골격, `paths.py`(절대경로 0), `.gitignore`, conda env `Blog`, docs, `CLAUDE.md`, README.
- **공유 데이터**: `blog` 그룹(jiho·yubin·hyewon·gaeun), `/mnt/data1/B_Log`=`jiho:blog` 2775(setgid), `data/raw` 심볼릭. `setup_data.sh`.
- **git**: `~/BLog` 독립 리포, remote `Quinsie/JBNU_BLog` (push 보류).
- **Phase 2 정적 기준 데이터** (API 실수집, 446): `reference/source/`(route_list·subList·stops·vtx·timetable, 24MB) + `reference/built/`(stdid_list 446, nx_ny_coords 격자 43). 격자식 KMA 표준점 검증.
- **Phase 1 수집기** (`src/collector/`): bus(적응형+버스트금지)·traffic·weather(전격자43)·incident(idle) + supervisor(flock) + common(clock/log/io) + health.
  - **수집 rate 정책**: 버스 있으면 10s / 빈 응답이면 60s 백오프. 발사 간 20ms 강제(버스트 하드금지, 최대 50req/s).
  - **systemd `blog-collector`** 설치·enabled(부팅 자동).
- **Phase 3 trip 재구성**: 위 현재 위치 항목 일체.

## ⚠️ 막힌 것 / 임시조치
- **ITS IP 차단** (`.73`, 부하테스트 누적). **48h+ 지속**(5/26 저녁~5/28 현재, 매일 재확인 중).
  - 🔧 **임시 우회 가동 중**: 보조 IP `210.117.134.74`(.73과 같은 /18)를 `enp6s0`에 붙이고, 수집기 ITS 아웃바운드를 거기로 소스바인딩(`ITS_SOURCE_IP` env, 없으면 기본 IP 자동 폴백). **비영속**(리부팅·네트워크 단절 시 IP 소멸 → 코드가 .73 폴백 → 차단으로 수집 중단).
  - ⚠️ **재발 사례**: 5/28 15:13~15:19 인터넷 일시단절 시 `.74` 휘발 → 6분간 ITS 수집 실패(`cannot assign requested address`). 수동 재부착으로 복구. **현재 자동복구 없음** — 인터넷 끊김마다 동일 사고 가능.
  - **원복(`.73` 차단 풀리면)**: ① `.env`의 `ITS_SOURCE_IP` 줄 삭제 ② `sudo ip addr del 210.117.134.74/18 dev enp6s0` ③ `sudo systemctl restart blog-collector`. (코드는 그대로 둬도 무해 — env 없으면 기본 IP 사용)
- **incident 수집 idle**: ITS WAF 차단으로 사고/공사 API 미수집 상태(`INCIDENT_URL` 미설정). 코드는 준비됨(`src/collector/incident.py`) — URL/WAF 우회 작업은 v1 이후로 보류.
- ~~중기예보(longForecast) 403~~ **해결**(5/26): KMA 중기예보 API 구독 반영 → land/ta ok=200 실데이터 수집 중.

## 다음 할 일
1. **(결정 대기) Phase 4 1차 모델 진입 path 선택**:
   - **Path A (design 임계경로)**: vtx 검수 → 깨진 노선 보정 → route_nodes 재생성 → 교통 typical 매핑 → 지리feature 포함 GBDT
   - **Path B (빠른 iteration)**: 비지리 feature 만으로 dumb baseline + 첫 GBDT → 측정 후 지리feature 추가 정당화
2. **1차 feature 가공** → dumb baseline 비교 → GBDT 학습 (Phase 4 본격)
3. **데이터 축적 계속**: 평일 다중일·주말 풀데이터 → 결행 vs 검출누락 구분, 임계값(R/K/gap/MATCH_GATE/R_STOP) 재튜닝
4. (운영) `.73` 차단 풀리면 `.74` 우회 원복(STATUS 위 §원복).
5. (운영, 검토) `.74` 휘발 자동복구 옵션(systemd ExecStartPre 로 IP 재부착) — 현재는 수동.

## 후처리에서 풀 과제 (기억)
- **vtx 재검증**: 작년 101노선 vtx 어긋남(구글맵 수작업 보정 흔적: [design/vtx_manual_2025.json](design/vtx_manual_2025.json)). 검수기=`checkRoute.py`(정류장 누락수). 올해 stdid 개편(451→446) + 노드 변화로 **올해 데이터로 재구성·재검증 필수** = 지리기반 1차 모델 임계경로의 일부(갈림길 #3 결정의 귀결).
- **plate 4자리 충돌 식별한계**: raw `PLATE_NO`가 4자리만 와서 같은 회사 두 차량(예: 31바1203·31사1203)을 (plate, company) 키로도 구분 못 함. 학습 ID 충돌 가능성 — 한글 prefix 가 raw 응답에 들어오게 할 방법 모색하거나 GPS 궤적 클러스터링으로 보강 필요.
- **검토거리 4건** ([DATA_NOTES](DATA_NOTES.md) 5/27 결론): 미매칭 검출누락 315/저빈도 결행 31노선/plate 충돌/얼음 심각 75 trip — 다중일 데이터 누적되면 (1·2)는 결행패턴 분석으로 결판.

## 확정 사항
- 단일 서버 전부 처리(backend/midServer 분리 없음). app(Flutter)+src(Python) monorepo.
- 원천(버스·교통·날씨·사고 실시간)만 HDD 심볼릭. 정적/파생은 repo(reference 만 git).
- baseline=이가은 collector(아이디어). 1차=MLP/GBDT, 2차=Transformer. docs 한글, commit 단위 추적.
- **1차 모델 핵심 결정** ([first-model.md](design/first-model.md) §5): y앵커=실제 출발 검출 / y형태=구간(정류장간)+cumsum / 지리종속성 1차 채용 + route_nodes·교통매핑 1차 임계경로 포함.
