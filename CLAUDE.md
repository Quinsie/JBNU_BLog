# CLAUDE.md — 작업 대원칙

> 이 리포에서 일하는 Claude 의 **행동 규범**. 세션이 바뀌어도 이 원칙을 일관되게 따른다.
> **전체 그림은 항상 [`docs/VISION.md`](docs/VISION.md)(큰 그림 단일 권위)를 가장 먼저 짚는다.** 진행상황은 `docs/STATUS.md`, 데이터 신뢰성은 `docs/DATA_NOTES.md`. **작업 착수 규약은 바로 아래 §anti-drift — 이 리포의 1번 규칙.**

## 프로젝트
전주 시내버스 **자체 ETA 예측 모델 기반 목표 도착형 이동계획 AI Agent**.
→ 비전·차별점·2트랙·마일스톤·컴포넌트 역할 등 **큰 그림은 [docs/VISION.md](docs/VISION.md)** (단일 권위, 항상 먼저 짚는다).

## 작업 착수 의례 — anti-drift (이 리포의 1번 규칙)

> 이 리포에서 가장 자주 난 사고: **작업이 깊어질수록 큰 그림을 잃고, 최근 대화에 쏠려 사용자와 다른 걸 보면서 작업하는 것.** 아래는 그걸 막는 강제 절차다. **모든 작업은 이 의례로 시작한다.**

1. **VISION 짚기.** [`docs/VISION.md`](docs/VISION.md)(큰 그림 단일 권위)를 먼저 짚는다 — 이 작업이 §2 사용자 여정·§4 마일스톤의 어디에 기여하는지 안 채로 들어간다.
2. **라우팅대로 위성 읽기.** 아래 〈작업→필수문서〉 맵대로 관련 위성을 읽는다. 부족하면 위성이 가리키는 다른 문서까지 **연쇄로** 읽는다.
3. **체크인 선언.** 비자명한 작업은 착수 *전에* 한 줄로 선언한다 — `이 작업은 VISION §X에 기여 / 위성 [A,B] 짚음 / 내 이해: …`. 사용자가 그 자리에서 정합을 검증하고, 어긋나면 즉시 교정한다.
4. **착수.**

- **문서 > 최근 대화.** 최근 대화에 가중치가 쏠리지 않는다. 대화는 문서를 *바꾸는 입력*이지 *덮어쓰는 것*이 아니다. 충돌하면 문서가 이긴다.
- **변경 환류.** 대화에서 세부가 바뀌면, 작업에 앞서 **그 변경을 먼저 해당 문서에 먹인다**(큰 그림=VISION, 세부=위성/STATUS·DATA_NOTES). 그래야 다음 세션의 나도 같은 걸 본다.

### 작업 → 필수 문서 (라우팅 맵)
| 작업 | 착수 전 먼저 읽는다 |
|---|---|
| **무엇이든** | VISION(큰그림) + STATUS(현재위치) |
| trip 재구성·전처리 | trip-reconstruction + first-model §3(y라벨 의존) + DATA_NOTES |
| 1차 모델·feature | first-model + trip-reconstruction + DATA_SCHEMA |
| 2차 모델 | second-model + first-model(prior) |
| 에이전트 | agent + first/second-model + serve-api(plan) |
| serve API | serve-api + app-api-flow |
| 앱·와이어프레임 | wireframe + app-api-flow |
| 데이터 파일 신설 | DATA_SCHEMA — 같은 커밋에서 갱신 |

## 작업 방식 (가장 중요)
1. **아주 잘게 쪼갠다.** 한 번에 큰 덩어리를 하지 않는다. 규모가 크므로 작은 단위로 전진한다.
2. **작업 단위마다 commit + `docs/STATUS.md` 갱신.** 나도 사용자도 "어디까지 왔고 다음에 뭘 할지" 를 항상 알 수 있어야 한다. 둘 다 길을 잃지 않는 게 최우선.
3. **큰 결정은 먼저 상의한다.** 구조 변경, 배포, 삭제/덮어쓰기, 팀원 리소스(다른 사용자 프로세스·데이터)에 영향 주는 일은 진행 전에 확인.
4. **임시방편 금지.** "오늘은 대충" 식 단기 타협을 하지 않는다. 시간이 없으면 범위를 줄이되 품질은 낮추지 않는다. 제대로 만든다.
5. **추측하지 말고 검증·측정으로 결정한다.** 가져온 데이터/산출물은 원본을 맹신하지 말고 검증한다(예: 격자 변환식은 KMA 표준 기준점으로 확인). 성능/부하는 실측으로 판단한다.
6. **작년 코드(`~/BIS_APP/`)는 정답이 아니다.** ML 입문기 연습물이므로 참고만 하고 뿌리부터 재설계한다.
7. **docs·commit 메시지는 한글.** worklog 는 두지 않는다(= commit 단위로 추적).
8. **커밋은 Conventional Commits 규약을 지킨다.** `type(scope): 설명` 형식.
   - type: `feat`(기능) `fix`(버그) `docs`(문서) `refactor` `perf`(성능) `chore`(잡무·설정) `test` `build` `ci`
   - scope(선택): `collector` `reference` `preprocess` `models` `agent` `serve` `deploy` 등
   - 설명은 한글, 명령형/요약형. 본문엔 상세, 끝에 `Co-Authored-By` 트레일러.
   - 예: `feat(collector): 적응형 폴링 + 버스트 하드금지`
9. **브랜치 → PR 워크플로.** main 에서 직접 작업하지 않는다. 작업 단위로 브랜치(`type/주제`,
   예 `design/first-model`)를 따고, 완료되면 PR 로 main 에 merge. main 은 항상 동작/배포 가능 상태 유지.

## 아키텍처 원칙
- **한 서버에서 전부**: 수집 → 전처리 → ML 학습 → 1차(사전)추론 → 2차(실시간)추론 → Agent 의사결정. (작년 backend/midServer 분리는 폐지)
- **수집기는 raw 무손실 저장만.** 매칭·필터·trip 재구성·이상치·ML 은 전부 후처리로 분리. (수집 단계에서 가공하면 데이터가 깨진다)
- 1차 모델: MLP vs GBDT 실험으로 최선 탐색. 2차 모델: Attention-Transformer 시계열로 재구축.
- 작년 데이터 품질 문제(결측·이상치·운행패턴 변화)에 대한 강건성을 강화한다.

## 코드 / 데이터 규약
- **코드에 절대경로를 박지 않는다.** 모든 경로는 `src/common/paths.py` 한 곳에서 해석. 머신 차이는 심볼릭 링크 + 환경변수로 흡수.
- **원천 데이터(실시간 고용량: bus·traffic·weather·incident)만** HDD(`/mnt/data1/B_Log`) 심볼릭 + gitignore. 정적 산출물·파생물·중간물은 `data/` 에 두되 git 은 `data/reference/` 만 추적.
- 파이프라인 단계 = 디렉토리 이름: `reference → raw → interim → features → models → predictions` (한 방향, 동의어 없음).
- **새로 만드는 모든 데이터 파일(raw·중간산출물)의 json/jsonl 구조는 `docs/DATA_SCHEMA.md` 에 반드시 표기.** 파일을 만들면 스키마 문서화는 당연한 동반 작업(같은 커밋에서 갱신).
- **CPU 전처리는 전부 multiprocessing(전 코어) 으로.** trip 재구성·feature 가공 등 CPU 바운드 작업은 `ProcessPoolExecutor(max_workers=os.cpu_count())` + 모듈레벨 워커로 all-core 사용. 직렬 처리 금지.
- **conda 환경 `Blog`** 사용 (venv 안 씀). 의존성은 `requirements.txt`.
- 구조: `app/`(Flutter, iOS+Android) + `src/`(Python) **monorepo**. git remote `Quinsie/JBNU_BLog`. **push 는 사용자 신호가 있을 때만.**
- 비밀(`.env`, API 키)은 git 에 올리지 않는다. 데이터 신뢰성 이슈는 `docs/DATA_NOTES.md` 에 기록.
