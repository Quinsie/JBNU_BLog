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

## ⚠️ 막힌 지점 — 수집 부하/조율 (사용자 결정 필요)
- 446 stdid @5s = 초당 89req. **게다가 같은 머신/IP에서 yubin(132@5s, pid236689)·gaeun(run.sh, pid133422) 수집기가 동시 가동 중** → ITS 서버 throttle. 내 테스트 중 yubin 로그에도 tick 지연 경고 발생.
- 측정: 내 수집기 단독 아닌 상태라 timeout/SERVER_DISCONNECTED 다발, median latency 큼 (세마포어 대기 포함 과장).
- **결정 필요**: ① BLog 수집기가 yubin/gaeun 것을 대체 → 그 둘 중단? ② 446@5s 단독도 버거우면 부하정책(시간표필터 ON / 10초 주기 / 그대로).

## 다음 할 일 (사용자 결정 후)
1. 기존 수집기 중단 조율 → 내 수집기 단독으로 446@5s 실측
2. 필요시 USE_TIMETABLE_FILTER=1 또는 interval 조정
3. run.sh(nohup/systemd) + 디스크 증가율 측정 → 내일 첫차 전 가동

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
