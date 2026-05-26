# STATUS

> **매 작업(commit)마다 갱신.** "지금 어디까지 왔고, 바로 다음 뭘 할지"를 항상 여기서 확인.

## 현재 단계
**Phase 0 — 환경/구조 셋업** (진행중)

## 완료
- 디렉토리 골격 (`app/ src/ docs/ data/`)
- `.gitignore` (data raw/interim/features/models/predictions·zip·flutter·env 제외, reference 추적)
- `src/common/paths.py` — 경로 단일 해석 (절대경로 미사용, `BLOG_RAW_DIR`/`BLOG_DATA_ROOT` 오버라이드)
- `requirements.txt`, `.env.example`, `docs/ROADMAP.md`

## 다음 할 일 (순서)
1. **공유 데이터 셋업** — `blog` 그룹(jiho·yubin·hyewon·gaeun) 생성, `/mnt/data1/B_Log` chown(2775 setgid), `data/raw` → `/mnt/data1/B_Log/raw` 심볼릭. `src/scripts/setup_data.sh` + `docs/SETUP.md`.
2. **git init** — `~/BLog` 독립 리포, remote `Quinsie/JBNU_BLog` (push 는 사용자 신호 후).
3. **수집기 이식** — 이가은 collector → `src/collector/`, paths.py 연동.
4. **stdid 446 반영** — 수집기가 446개 stdid 로드하도록 (정적 목록 `data/reference/source/`).
5. **수집기 robust 가동** — bus 5초 / traffic 1분 / weather / incident, 24h 무손실 검증.

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
