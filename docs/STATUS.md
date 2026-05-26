# STATUS

> **매 작업(commit)마다 갱신.** "지금 어디까지 왔고, 바로 다음 뭘 할지"를 항상 여기서 확인.

## 현재 단계
**Phase 1 수집기 구현** 직전 (Phase 0 골격 + 정적 기준 데이터 완료)

## 완료
- **Phase 0 골격**: 디렉토리, `.gitignore`(raw/interim/features/models/predictions·logs·zip·flutter·env 제외, reference 추적), `paths.py`(절대경로 0), `requirements.txt`, `.env.example`, docs(ROADMAP/STATUS/SETUP), README
- **공유 데이터**: `blog` 그룹(jiho·yubin·hyewon·gaeun, gid 1005), `/mnt/data1/B_Log`=`jiho:blog` 2775(setgid), `data/raw` 심볼릭. `setup_data.sh`
- **git**: `~/BLog` 독립 리포 init, remote `Quinsie/JBNU_BLog` 등록 (push 보류). 첫 commit `ec73d80`
- **정적 기준 데이터 (API 실수집, 446 기준)**:
  - `src/common/jeonju_api.py`(ITS 클라이언트, WAF체크), `src/common/grid.py`(격자변환)
  - `src/scripts/fetch_static.py` → `reference/source/`: route_list(132)·subList(132)·stops(446)·vtx(446)·timetable(446, BRT_TEXT 85개). 24MB
  - `src/scripts/build_reference.py` → `reference/built/`: `stdid_list.json`(446+메타)·`nx_ny_coords.json`(격자 43개)

## 완료 (이어서)
- **수집기 구현 완료** (`src/collector/`): bus/traffic/weather(전격자43)/incident + supervisor(`__main__`, flock 중복방지) + common(clock/log/io) + health(에러분류·tickstats). venv(.venv, py3.13) 설치.
- 스모크 테스트: bus 446 stdid 로드·busPosList 8필드 정상 저장 확인.

## 부하 문제 해결 — 균등 페이싱 (핵심 교훈)
- 문제는 89req/s 라는 **속도가 아니라 버스트**였음. 446개를 한꺼번에 쏘면 백로그→throttle (ok 88%, 19s 지연). 세마포어 방식은 느린응답→백로그→더느림 피드백 루프.
- **해결**: 5초 윈도 안에서 dt=5/N(≈11ms) 간격 **균등 페이싱** 디스패치. → 동시연결 ~6, 응답 ~15ms.
- **+ per-line fsync 제거**(HDD 동기블로킹이 이벤트루프 막음, flush만 유지). 
- **실측 결과: ok 100%, 446 stdid 전부 실효 polling 5.0s(p90 6s), 처리량 81/s.** ✅ 목표 달성.
- 기존 수집기(yubin pid236689 / gaeun run.sh pid133422)는 중단 완료 → BLog 단독 체제. 5/26 데이터는 오염(DATA_NOTES).
- 확정 설정: interval=5, 페이싱, BUS_CONCURRENCY=100(안전망), BUS_HTTP_TIMEOUT=4.5. USE_TIMETABLE_FILTER=0.

## 다음 할 일
1. `src/scripts/run.sh` (nohup supervisor) 로 상시 가동 → 내일 첫차 전부터 무손실 수집
2. weather(전격자43)·traffic 가동 검증, 디스크 증가율 측정
3. (이후) Phase 2 정적정비 잔여 / Phase 3 후처리

## 결정 사항 (확정)

## 결정 사항 (확정)
- 한 서버에서 전부 처리 (backend/midServer 분리 없음).
- app + src 한 리포(monorepo). app = Flutter.
- 원천 데이터(버스/교통/날씨/사고 실시간 고용량)만 HDD(`/mnt/data1/B_Log`) 심볼릭. 나머지 + 정적 산출물은 repo.
- 정적: `reference/source`(API 원본) vs `reference/built`(후처리 산출물, route_nodes 등).
- worklog 안 씀 → commit 단위로 추적. docs 한글.
- baseline = 이가은 collector. 1차=MLP/GBDT 실험, 2차=Transformer.

## 열린 질문 / 메모
- 날씨 전격자 수집 vs 단일격자: 격자맵(`nx_ny`) 빌드는 Phase 2 정적정비에 의존 → 수집기 1차 가동은 단일/소수 격자로 시작할지 결정 필요.
- 수집 대상 추가 항목(sky_air 미세먼지, 공지) 은 v1 로 이월 검토.
