# JBNU_BLog

전주시 시내버스 **자체 ETA 예측 모델** 기반 **목표 도착형 이동계획 AI Agent**.

기존 BIS·네이버지도·카카오맵은 *"저 버스가 지금 어디냐 / 몇 분 뒤 오냐"* 까지 답한다.
이 프로젝트는 한 단계 더 간다 — **"N시 M분까지 거기 도착하려면 *지금 무엇을 해야 하나*" 를 역산**한다.

> 지방은 배차가 수십 분이라 무턱대고 나가 기다리면 시간을 버린다. 버스에 정시성이 없고 중간 정류장
> 시간표 힌트도 없어 아무도 못 하던 "역산"을, **중간 정류장 도착시각을 자체 모델로 고품질 예측**해 가능케 한다.

```
[등록]  전북대 9:00 도착          ← 사용자가 하는 유일한 입력
   ├─ (전날/사전) "내일 7:35쯤 나가면 됩니다"      ← 에이전트 역산 + 1차 ETA
   ├─ "지금 나가세요" → "○○정류장으로" (도보)      ← 현위치 역산 + OSRM
   ├─ "104번 07:48 차를 타세요"                      ← 1·2차 ETA로 배차 선택
   ├─ (GPS가 버스 궤적 추종) "정상 탑승 확인"
   ├─ "다음 정류장에서 내려 환승 준비"               ← 2차 실시간 ETA
   └─ "도착". 목표시각 준수.
```

> 📖 **큰 그림·비전은 [docs/VISION.md](docs/VISION.md) 가 단일 권위.** 진행상황은 [docs/STATUS.md](docs/STATUS.md),
> 환경 셋업은 [docs/SETUP.md](docs/SETUP.md), 작업 규범은 [CLAUDE.md](CLAUDE.md).

---

## 시스템 큰 그림 — 2트랙 + 합류점

예측 자산을 만드는 **코어 트랙**과 사용자 접점인 **서비스 트랙**이 병렬로 전진하다 **serve API 에서 합류**한다.
serve 는 "맨 끝 단계"가 아니라 처음부터 양 트랙을 잇는 척추 — 더미계약으로 먼저 띄우고, 자산이 완성되는 계층부터 real 로 교체한다.

```
코어 트랙 ──  raw수집 ─▶ trip재구성 ─▶ 1차모델 ─▶ 2차모델 ─▶ 에이전트 ─┐
 (예측 자산)   ✅          ✅          (설계)     (예정)     (예정)    │
                                                                       ▼
                                                               ┌──────────────┐
                                                               │   serve API   │ ◀ 합류점 (앱-facing 계약)
                                                               │  (부분 real)  │
                                                               └──────────────┘
                                                                       ▲
서비스 트랙 ─ 와이어프레임 ─▶ Flutter 앱 ─────────────────────────────┘
 (사용자 접점)  (예정)          (미착수)
```

데이터는 한 방향으로만 흐른다: `reference`(기준, 곁에 둠) │ `raw → interim → features → models → predictions`.

### 컴포넌트 한눈에

| 컴포넌트 | 역할 (입력 → 출력) | 상태 |
|---|---|---|
| **수집기** | ITS·KMA 를 raw 무손실 저장 (가공 0) | ✅ 가동 |
| **trip 재구성** | raw → 실제 운행 trip + 구간 y라벨 | ✅ v1.1 |
| **1차 모델 (사전추론)** | 발차 전, 전 정류장 도착 clock-time 예측 (배차 = `(stdid, 발차슬롯)`) | 설계 |
| **2차 모델 (실시간추론)** | 발차 감지 후 1차를 prior 로 남은 정류장 보정 (attention-transformer) | 예정 |
| **에이전트** | 목적지+목표시각 → 탑승 버스열 역산 → 현위치 기반 지속 알림 | 예정 |
| **serve API** | 두 트랙 합류점. 앱-facing REST 계약 | 부분 real |
| **앱 (Flutter)** | 사용자 입출력 + 알림 수신 (iOS/Android) | 미착수 |

> 마일스톤(M0~M5)·여정·책임 경계 등 권위 정의는 [docs/VISION.md](docs/VISION.md), 지금 어디까지 왔는지는 [docs/STATUS.md](docs/STATUS.md).

---

## 리포 구조

monorepo — 한 서버에서 수집→전처리→ML→추론→Agent 를 전부 처리하고, 앱은 그 위에 얹는다.

```
app/                 Flutter 앱 (iOS/Android) — 미착수
src/                 Python (단일 서버)
  collector/         수집기 — bus·traffic·weather·incident + supervisor(flock)
  common/            공용 — paths·clock·grid·io·log·jeonju_api
  preprocess/        trip_reconstruct.py (trip 재구성, all-core)
  models/            1차·2차 모델 (예정)
  agent/             목표도착 역산 에이전트 (예정)
  serve/             FastAPI 앱-facing API — app·routers·store·schemas
  scripts/           build_reference·fetch_static·setup_data.sh·run.sh(수집기 supervisor)
scripts/             run_serve.sh (serve 기동 + cloudflared 터널)
data/                reference(git 추적) · raw/interim/features/models/predictions(gitignore)
deploy/              blog-collector.service (systemd)
docs/                VISION·STATUS·ROADMAP·DATA_SCHEMA·DATA_NOTES·SETUP + design/
```

- **코드에 절대경로 금지** — 모든 경로는 `src/common/paths.py` 한 곳에서 해석.
- **원천 데이터(고용량 실시간)만** HDD(`/mnt/data1/B_Log`) 심볼릭 + gitignore. 정적·파생물은 `data/`(git 은 `reference/` 만).

---

## 빠른 시작

```bash
git clone https://github.com/Quinsie/JBNU_BLog.git
cd JBNU_BLog

conda create -n Blog python=3.12 -y     # venv 안 씀, conda env "Blog"
conda activate Blog
pip install -r requirements.txt

cp .env.example .env                     # KMA_API_KEY 에 본인 Decoding 키 입력

# (JBNU 서버에서) 공유 raw 디스크 연결
bash src/scripts/setup_data.sh
```

> API 키는 공공데이터포털 발급 키의 **Decoding** 형태를 `.env` 의 `KMA_API_KEY` 에 넣는다 (git 에 안 올라감).
> 다른 서버·데이터를 전달받은 경우 등 경로 설정 상세는 [docs/SETUP.md](docs/SETUP.md).

### 실행

```bash
# 수집기 상시 가동 (크래시 시 지수백오프 재시작)
nohup bash src/scripts/run.sh >/dev/null 2>&1 &
tail -f logs/run.out
#   또는 systemd:  sudo systemctl start blog-collector   (deploy/blog-collector.service)

# serve API — 로컬 :8000 + Swagger(/docs) + cloudflared 임시 터널(외부 공개)
bash scripts/run_serve.sh
```

> serve 외부 공개는 캠퍼스 방화벽 때문에 `--protocol http2` 가 필수이며(스크립트에 반영됨),
> trycloudflare URL 은 재기동마다 바뀐다. 운영 영속화(고정 URL·systemd·API키)는 [docs/STATUS.md](docs/STATUS.md) 참조.

---

## 기술 스택

- **언어/환경**: Python 3.12, conda env `Blog` (의존성 `requirements.txt`)
- **수집**: aiohttp · requests · APScheduler (적응형 폴링 + 버스트 하드금지)
- **전처리**: multiprocessing 전 코어(`ProcessPoolExecutor`) · holidays(KR 공휴일)
- **serve API**: FastAPI · uvicorn · pydantic (코드가 곧 OpenAPI/Swagger)
- **외부 공개**: cloudflared (임시 터널)
- **ML (예정)**: LightGBM(1차 GBDT) · PyTorch(2차 Transformer) · scikit-learn · pandas · pyarrow
- **앱 (예정)**: Flutter (iOS + Android)

---

## 문서 맵

| 문서 | 내용 |
|---|---|
| [docs/VISION.md](docs/VISION.md) | **큰 그림 단일 권위** — 비전·2트랙·마일스톤·여정·컴포넌트 |
| [docs/STATUS.md](docs/STATUS.md) | 현재 위치 — 어디까지·막힌 것·다음 할 일 (매 commit 갱신) |
| [docs/ROADMAP.md](docs/ROADMAP.md) | 실행 시퀀스 — Phase별 작업·의존 순서·게이트 |
| [docs/DATA_SCHEMA.md](docs/DATA_SCHEMA.md) | 모든 raw/중간산출 json 구조 |
| [docs/DATA_NOTES.md](docs/DATA_NOTES.md) | 데이터 신뢰성 이슈 (날짜별 기록) |
| [docs/SETUP.md](docs/SETUP.md) | 환경 셋업 — 경로·키·systemd |
| [CLAUDE.md](CLAUDE.md) | 작업 규범 — 방식·커밋 규약·아키텍처/데이터 원칙 |
| [docs/design/trip-reconstruction.md](docs/design/trip-reconstruction.md) | 코어: trip 재구성 (발차검출·시간표매칭·GPS복원) |
| [docs/design/first-model.md](docs/design/first-model.md) | 코어: 1차 모델 (y라벨·지리종속성·GBDT·평가) |
| [docs/design/serve-api.md](docs/design/serve-api.md) | 서비스: API 계약 (엔드포인트·계층용어·운영) |

---

## 참고

- 전북대학교(JBNU) 팀 프로젝트. git remote `Quinsie/JBNU_BLog`.
- 작년 프로토타입(`~/BIS_APP/`)은 ML 입문기 연습물 — 아이디어만 참고하고 뿌리부터 재설계한다.
- 비밀(`.env`·API 키)은 git 에 올리지 않는다.
</content>
</invoke>
