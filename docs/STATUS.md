# STATUS

> **매 작업(commit)마다 갱신.** "지금 어디까지 왔고, 바로 다음 뭘 할지"를 항상 여기서 확인.
> 전체 그림·단계 의존성은 [ROADMAP.md](ROADMAP.md), 데이터 신뢰성은 [DATA_NOTES.md](DATA_NOTES.md).

## 현재 위치
**Phase 1(수집기) 구현 완료 → ITS IP 차단으로 가동 일시 중단(쿨다운).**
차단 풀리면 재가동, 데이터 축적되면 Phase 3(trip 재구성) 설계로.

## 완료
- **Phase 0**: 디렉토리 골격, `paths.py`(절대경로 0), `.gitignore`, conda env `Blog`, docs, `CLAUDE.md`, README.
- **공유 데이터**: `blog` 그룹(jiho·yubin·hyewon·gaeun), `/mnt/data1/B_Log`=`jiho:blog` 2775(setgid), `data/raw` 심볼릭. `setup_data.sh`.
- **git**: `~/BLog` 독립 리포, remote `Quinsie/JBNU_BLog` (push 보류).
- **Phase 2 정적 기준 데이터** (API 실수집, 446): `reference/source/`(route_list·subList·stops·vtx·timetable, 24MB) + `reference/built/`(stdid_list 446, nx_ny_coords 격자 43). 격자식 KMA 표준점 검증.
- **Phase 1 수집기** (`src/collector/`): bus(적응형+버스트금지)·traffic·weather(전격자43)·incident + supervisor(flock) + common(clock/log/io) + health.
  - **수집 rate 정책**: 버스 있으면 10s / 빈 응답이면 60s 백오프. 발사 간 20ms 강제(버스트 하드금지, 최대 50req/s). 로컬 mock 검증: 최소간격 20.2ms, 커버 446/446.
  - **systemd `blog-collector`** 설치·enabled(부팅 자동). env python 직접 실행.

## ⚠️ 막힌 것
- **ITS IP 차단** (오늘 부하테스트 누적). connect timeout, KMA·DNS 정상 = rate-limit 쿨다운(영구 아님). 수집기 stop(enabled 유지).
  - **재가동**: ITS 443 연결 회복 확인 → `sudo systemctl start blog-collector`. (적응형+gap 적용본이라 재발 위험 낮음)
- **중기예보(longForecast) 403**: KMA 키 중기예보 API 구독 반영 대기(비차단).

## 다음 할 일
1. (차단 해제 후) 수집 재가동 → 1~2h 무손실·디스크 추세 확인. clean 데이터 축적 시작.
2. 데이터 쌓는 동안 **설계**(ITS 불필요):
   - **trip 재구성 + 배차시각 매칭 휴리스틱** 설계 (모델 무관, Phase 3)
   - **1차 모델 구조** 결정 (MLP vs GBDT, 입력/타깃) — feature 가공을 여는 키스톤
3. 모델 구조 확정 → feature 가공 → 1차 학습 (Phase 4)

## 후처리에서 풀 과제 (기억)
- **배차 시각 식별**: raw 만 받으므로 trip↔시간표 매칭 휴리스틱 필요.
- **vtx 불신**: 작년 101개 노선이 실제 경로/정류장과 어긋남 → route_nodes 만들면 검증 동반. 단 route_nodes 는 **2차 전용**(1차 무관), busPosList 의 CURRENT_NODE_ORD/LATEST_STOP_ORD 가 진행도 직접 제공.

## 확정 사항
- 단일 서버 전부 처리(backend/midServer 분리 없음). app(Flutter)+src(Python) monorepo.
- 원천(버스·교통·날씨·사고 실시간)만 HDD 심볼릭. 정적/파생은 repo(reference 만 git).
- baseline=이가은 collector(아이디어). 1차=MLP/GBDT, 2차=Transformer. docs 한글, commit 단위 추적.
