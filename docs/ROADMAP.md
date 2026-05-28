# ROADMAP

> 살아있는 문서. 큰 단계와 목표만 적는다. "지금 어디까지/다음 뭐"는 [STATUS.md](STATUS.md).

## 프로젝트 목표

전주시 시내버스 **자체 ETA 예측 모델** 기반의 **목표 도착형 이동계획 AI Agent**.

사용자가 *목적지 + 목표 도착 시각* 을 입력하면 →
정류장까지 도보, 탑승 가능 버스, 환승 가능성, 예상 도착을 종합해
**"지금 출발해야 하는가 / 어떤 버스를 타야 하는가 / 안전한 대안은 무엇인가"** 를
행동 단위로 안내한다.

기존 BIS 도착정보가 부정확하다는 한계를, 직접 만든 강건한 ETA 모델로 극복하는 것이 핵심.

## 설계 원칙

- **한 서버에서 전부**: 수집 → 전처리 → 학습 → 1차(사전)추론 → 2차(실시간)추론 → Agent 의사결정. (작년 backend/midServer 분리 폐지)
- **수집기는 raw 무손실 저장만**. 매칭·가공·ML은 전부 후처리. (작년 모놀리식 수집기가 데이터 손실의 주범)
- 작년(2025) BIS_APP 코드는 ML 입문기 연습 — **정답 아님, 뿌리부터 재설계**.
- **작업을 잘게 쪼개고 작업마다 commit + docs 갱신.** 둘 다 진행상황을 잃지 않게.

## 단계

| Phase | 내용 | 상태 | 의존(gate) |
|---|---|---|---|
| 0 | 환경/구조 셋업 (리포·경로·공유데이터·문서·CLAUDE.md) | ✅ 완료 | |
| 1 | 수집기 (raw 무손실, 적응형+버스트금지) | ✅ 구현완료 (ITS .73 차단 → .74 우회 가동) | |
| 2 | 정적 기준 데이터 (노선·정류장·시간표·격자) | ✅ 완료 (446·격자43) | |
| 3 | **trip 재구성 + 클렌징** (raw→실제운행 ground truth) — *모델 무관* | ✅ v1.1 완료 + 5/27 풀데 funnel 확정(슬롯의 91%가 학습 trip) | clean 데이터 축적 |
| 4 | **1차 모델: vtx 재검증 + route_nodes·교통매핑 + feature 가공 + 학습** (사전 ETA, GBDT→MLP) | 진입(설계 path 결정 대기) | Phase 3 |
| 5 | 2차 모델 (실시간 ETA, Transformer) | 대기 | Phase 4 |
| 6 | Agent (목표 도착형 이동계획 의사결정) | 대기 | 1·2차 ETA |
| 7 | serve API + Flutter 앱 (iOS/Android) | 대기 | Agent |

### 핵심 의존성 (작업 순서를 정하는 원리)
- **raw 수집은 작년 인라인 전처리의 상위집합.** 작년이 수집 중 했던 trip 묶기·route-node 감지·도착시각·혼잡도 매핑은 전부 raw 응답에서 후처리로 재구성 가능(정보 손실 0). 단 작년이 락온으로 거저 알던 *배차시각* 은 trip↔시간표 **휴리스틱 매칭**으로 대체.
- **후처리는 두 층**: ① *모델 무관* — trip 재구성·클렌징·실제 도착시각(=ground truth, Phase 3). ② *모델 종속* — feature 가공·타깃·정규화·임베딩 입력(Phase 4, **모델 구조 확정 후**에만 확정 가능).
- **route_nodes·traffic 매핑은 1차 모델 임계경로**(2025 가정 폐기). 갈림길 #3 결정([design/first-model.md](design/first-model.md) §2.2): 지리(geometry) 종속성을 1차에 채용 → 200m route-node 리샘플 + 정류장 30m 스냅 + 노드↔교통 typical 속도 매핑이 1차 feature 의 일부. 이에 따라 vtx 재검증(작년 101노선 어긋남 사례)도 1차 선행작업으로 격상.
- 데이터 축적은 **Phase 3 검증/임계값 튜닝 + Phase 4 모델 신뢰도 확보**에 계속 필요(평일 다중일·주말 풀데이터로 결행 vs 검출누락 구분).

## 디렉토리 구조

```
JBNU_BLog/
├── app/                  # Flutter (iOS + Android)
├── src/                  # Python — 단일 서버 파이프라인
│   ├── collector/        #   실시간/정적 수집
│   ├── preprocess/       #   raw → trip 재구성 → feature
│   ├── models/           #   1차(MLP/GBDT) · 2차(Transformer)
│   ├── agent/            #   목표 도착형 이동계획 의사결정
│   ├── serve/            #   추론·쿼리 API (app 이 호출)
│   ├── common/           #   paths·config·로거·API클라이언트·유틸
│   └── scripts/          #   정적 fetch·배치·셋업 진입점
├── docs/                 # ROADMAP · STATUS · design/
└── data/
    ├── reference/        # 정적 기준 (git)
    │   ├── source/       #   API 정적 원본 (subList·stops·vtx·시간표)
    │   └── built/        #   후처리 산출 참조물 (route_nodes·격자맵·446목록)
    ├── raw/              # 수집 원천 로그 (HDD 심볼릭, gitignore)
    ├── interim/          # raw 가공 중간물 (gitignore)
    ├── features/         # ML 입력셋 parquet (gitignore)
    ├── models/           # 학습 모델 (gitignore)
    └── predictions/      # 추론 산출물 (gitignore)
```

데이터 흐름: `reference` 를 곁에 두고 `raw → interim → features → models → predictions` 한 방향.

## 참고 자산

- `~/BIS_APP/` — 작년(2025) 프로토타입 + 재설계 문서(`API_CATALOG.md`, `COLLECTOR_SPEC.md`, `PROJECT_PLAN.md`). 참고용.
- 이가은 수집기 — 이번 수집기의 baseline (config 주도 · 에러분류 · incident · 전격자 날씨 · 시간표필터).
- 2026 stdid = **446개** (작년 451 → 노선 개편).
