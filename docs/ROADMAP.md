# ROADMAP — 실행 시퀀스

> **큰 그림(비전·2트랙·마일스톤 정의)은 [VISION.md](VISION.md)** — 이 문서는 그걸 *어떤 순서로 짓는지*다.
> "지금 어디까지 / 다음 뭐"는 [STATUS.md](STATUS.md). 행동 규약은 [CLAUDE.md](../CLAUDE.md).

## 2트랙 × 통합 마일스톤

두 트랙(코어·서비스)이 serve API에서 합류하며 **M0~M5 게이트**를 통과한다(정의·합류 구조 → [VISION §3·§4](VISION.md)). 트랙별 작업 시퀀스와 기여 마일스톤:

### 코어 트랙 (예측 자산)
| 작업 | 산출 | 상태 | → M |
|---|---|---|---|
| 수집기 (raw 무손실, 적응형+버스트금지) | raw bus·traffic·weather | ✅ | M0 |
| 기준 데이터 (446 노선·정류장·시간표·격자43) | reference/ | ✅ | M0 |
| **trip 재구성 + 클렌징** (raw→ground truth, *모델 무관*) | interim/trips (y 라벨) | ✅ v1.1 | M0→M1 |
| **1차 모델 (사전 ETA)**: vtx 재검증 + route_nodes·교통매핑 + feature + 학습 (GBDT→MLP) | 사전추론 | 진입 | **M1** |
| **2차 모델** (실시간 ETA, Attention-Transformer) | 실시간추론 | 대기 | **M2** |
| **에이전트** (목표도착 역산·추적·알림) | plan | 대기 | **M3** |

### 서비스 트랙 (사용자 접점)
| 작업 | 산출 | 상태 | → M |
|---|---|---|---|
| serve API 스캐폴드 (전 엔드포인트 dummy + 기준데이터·실황·날씨 real) | FastAPI | ✅ | **M0** |
| 추론·plan 라우터 real 교체 | serve real | 대기 | M1·M2·M3 |
| 와이어프레임 (ASCII 목업+명세) | design/wireframe | 대기 | M4 |
| 화면↔서버 API 계약 | design/app-api-flow | 대기 | M4 |
| Flutter 앱 (iOS/Android) | app/ | 대기 | **M4** |
| 외부 공개 (고정URL·API키·rate limit·systemd 영속화) | 배포 | 대기 | **M5** |

> 마일스톤 정의 = [VISION §4](VISION.md). 현재 진척·funnel·막힌것 = [STATUS](STATUS.md). 컴포넌트 역할·깊이 문서 = [VISION §5·§6](VISION.md).

## 핵심 의존성 (작업 순서를 정하는 원리)
- **raw 수집은 작년 인라인 전처리의 상위집합.** 작년이 수집 중 했던 trip 묶기·route-node 감지·도착시각·혼잡도 매핑은 전부 raw 응답에서 후처리로 재구성 가능(정보 손실 0). 단 작년이 락온으로 거저 알던 *배차시각* 은 trip↔시간표 **휴리스틱 매칭**으로 대체.
- **후처리는 두 층**: ① *모델 무관* — trip 재구성·클렌징·실제 도착시각(=ground truth, 코어 트랙 3번째). ② *모델 종속* — feature 가공·타깃·정규화·임베딩 입력(1차 모델 단계, **모델 구조 확정 후**에만 확정 가능).
- **route_nodes·traffic 매핑은 1차 모델 임계경로**(2025 가정 폐기). 갈림길 #3 결정([design/first-model.md](design/first-model.md) §2.2): 지리(geometry) 종속성을 1차에 채용 → 200m route-node 리샘플 + 정류장 30m 스냅 + 노드↔교통 typical 속도 매핑이 1차 feature 의 일부. 이에 따라 vtx 재검증(작년 101노선 어긋남 사례)도 1차 선행작업으로 격상.
- 데이터 축적은 **trip 재구성 검증/임계값 튜닝 + 1차 모델 신뢰도 확보**에 계속 필요(평일 다중일·주말 풀데이터로 결행 vs 검출누락 구분).

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
├── docs/                 # VISION · STATUS · ROADMAP · design/
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

- `~/BIS_APP/` — 작년(2025) 프로토타입 + 재설계 문서(`API_CATALOG.md`, `COLLECTOR_SPEC.md`, `PROJECT_PLAN.md`). 참고용(아이디어만).
- 이가은 수집기 — 이번 수집기의 baseline (config 주도 · 에러분류 · incident · 전격자 날씨 · 시간표필터).
- 2026 stdid = **446개** (작년 451 → 노선 개편).
