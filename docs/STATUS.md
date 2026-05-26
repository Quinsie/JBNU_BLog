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

## 다음 할 일 (순서)
1. **수집기 구현** (`src/collector/`, 이가은 아이디어 차용·직접 구현·paths 연동):
   - bus 5초 (446 stdid, `stdid_list.json` 로드), traffic 1분, weather 전격자(43), incident(URL 설정 시)
   - writer(jsonl append+fsync / atomic), logger(일자회전), 에러분류, tickstats, supervisor(`__main__`)
   - run.sh (nohup/systemd) + 중복실행방지
2. **robust 검증** — 1~2시간 가동 → 헬스로그·디스크증가율·무손실 확인
3. **가동** — 내일 첫차(05:30경) 전까지 띄워놓기

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
