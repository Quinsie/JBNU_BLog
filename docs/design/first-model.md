# 1차 모델 설계 — 사전(pre-departure) ETA

> Phase 4. 실시간 정보 없이, *출발 전*에 "이 노선이 시간표 출발부터 각 정류장까지 몇 초 걸릴지"를 예측.
> 본 문서는 작년(BIS_APP) 1차 모델을 **검증**한 결과와, 그로부터 내린 **재설계 결정** + **미결정 갈림길**을 기록한다.
> 작년 코드는 *아이디어만* 채용하고 뿌리부터 새로 만든다(stdid가 451→446으로 바뀐 시점에 작년 산출물 직접 재사용은 의미가 적음).

---

## 0. 철학
- 1차 = **사전 ETA**(실시간 없음). 2차 = 실시간 보정(Transformer). route_nodes/실시간 교통은 원칙적으로 2차.
- 모든 가설(자가반성·종속성 구조·feature·mean 층화·timegroup 경계)은 **추측이 아니라 실험/측정으로** 정당성을 판정한다.
- 모든 모델은 **dumb baseline(해당 층의 mean 예측)을 이겨야** 의미가 있다 — 작년 내내 없던 검증 앵커.

---

## 1. 작년 1차 모델 검증 결과 (BIS_APP)

### 1.1 루프 구조 (코드 확인)
- **self_review**: 어제 raw + *예보* 날씨 + `prev_pred_elapsed`(어제 내가 예측했던 값) → 어제 replay 모델 로드 → 학습 → 오늘 self_review 모델 저장. 손실에 `0.3·relu(y − prev_pred)` 추가.
- **replay**: 같은 어제 raw + *관측* 날씨 + `prev_pred_elapsed=0` → 방금 self_review 모델 로드 → 학습 → 오늘 replay 모델 저장.
- **inference**: replay 모델로 추론(`prev_pred=0`).

### 1.2 타깃 y (코드 확인 — `buildFirstReplayParquet.py`)
```
base_time = logs[0]['time']          # trip 첫 기록 시각. 단 수집/trip분할 단계에서
                                     # 가장 가까운 시간표 출발로 '락온(강제고정)'된 값.
arr_time  = record['time']           # 현재 정류장 도착 시각
y = normalize(arr_time - base_time, 0, 7200)   # 출발→정류장 '누적 경과초', 0~2h 정규화
```
- → **구간(stop-to-stop) 소요시간이 아니라, 출발부터의 누적 경과초.**
- `base_time`은 첫 관측이지만, `departureCacheGenerator.py`(요일 weekday/saturday/holiday × 출발시각 → stdid 역색인)를 이용해 **시간표 출발로 스냅**됨. → 그래서 사실상 "시간표 출발 기준".

### 1.3 입력 feature (작년)
- 계층적 가산 임베딩: `dir = dir_raw + Linear(bus)`, `branch = branch_raw + Linear(dir)`, `ord_ratio = mlp + Linear(branch)`.
- mean_elapsed **4층**(total/weekday/timegroup/wd_tg) + prev_mean **4층** + mean_interval.
- 시간: sin/cos + timegroup emb + wd_tg emb (3중).
- 날씨: pty_emb + RN1 + T1H. prev_pred_elapsed(추론 시 0).
- 손실: heteroscedastic(`(y-μ)²·exp(-logvar)+logvar`) + ranking(`relu(pred_i-pred_j)`, trip내 ord순) + self_review penalty.

### 1.4 보조 정의 (코드 확인)
- **달력 = 3분류**: 시간표에 `COURSE_STIMELIST`(평일)/`SAT_NLIST`(토)/`HOLI_NLIST`(일+공휴일). `getDayType`도 weekday/saturday/holiday. (446 중 102개만 SAT/HOLI 별도표 보유)
- **timegroup = 손으로 자른 8구간**: 1)0530–0700 2)0700–0900(출근) 3)0900–1130 4)1130–1400 5)1400–1700 6)1700–1900(퇴근) 7)1900–2100 8)그외(야간).
- **운행 특이사항**: 시간표 `BRT_TEXT`(85개 노선)에 우회·경기일 변경 등 기록(예: 402번 "주말·공휴일 경기시 월드컵경기장 기점 변경"). → outlier 설명 feature 후보.

---

## 2. 재설계 결정

### 2.1 자가반성 페널티 폐기 + 증분학습 채택
- 작년 `relu(y−prev_pred)`는 **과소추정만 벌해 예측을 위로(=늦게) 편향**시킴. BIS에선 *늦게 추정 = 버스 놓침*이라 치명적 → 목적과 정반대. **폐기 확정.**
- `prev_pred_elapsed`는 학습 때만 실제, 추론 땐 0인 train/inference mismatch까지 있었음 → 입력에서도 **제거**.
- 다만 "어제 실제값으로 다시 학습" 자체가 이미 교정(=진짜 의미의 반성). → **증분학습은 유지.**
- **갱신 전략 확정 방향**: *초기 통째(첫 2~4주) 학습 → 이후 일단위 증분*(직전 가중치 이어받음). 시간제약(작년 2주에 ~2h) 현실적. catastrophic forgetting 방지로 *최근 N일 replay 혼합*을 옵션으로 둠(작년의 가짜 replay 아님).

### 2.2 종속성: 노선ID 위계 → **지리(geometry) 기반**으로 전환
- 작년 의도: 101 상/하행, 본/분/지선 위계로 gradient 공유 → 희소노선 일반화.
- **결함**: 101 상행1번 ↔ 하행1번이 gradient 공유는 틀림(지리적 정반대).
- **올바른 추상 = 공간**: 같은 도로 구간을 지나면 노선이 달라도(101·1001·5001 …) 그 구간 통행양상이 닮음 → 희소노선이 인접노선 신호를 빌림. 교통데이터(링크 기반)와 결합도 자연스러움.
- 단 1차에 들어가는 교통/지리는 **실시간이 아니라 과거 전형치(시간대별 구간 typical 속도/혼잡)**만. 실시간은 2차.

### 2.3 feature·mean — "많이"가 아니라 "하나를 잘", 전부 실험으로 판정
- mean 4층(total/wd/tg/wd_tg)은 **함수적 종속(파생 중복)**. wd_tg가 최미세, 나머지는 그 주변합 → 공선성·과의존.
- **방향**: 미세 칸을 쓰되 희소하면 상위로 **수축(shrinkage/경험적 베이즈)**하는 **단일 prior 하나**로 합침.
- **mean을 타깃 기준으로 쓰지 않음**(작년 "평균에서의 편차" 아이디어): mean이 갱신마다 흔들려 *moving target*이 됨. → **y는 안정적 절대값, mean은 입력 feature 하나**.
- **실험으로 판정할 것**: ① timegroup 8구간이 분산을 의미있게 줄이는가(wd_tg vs tg-only vs wd-only ANOVA/R²) ② 손-binning vs sin/cos 연속표현+트리 ③ 토 vs 일+공휴일 분리 vs lump ④ 누적 교통집계 vs 최근추세 ⑤ 날씨·BRT_TEXT 이벤트 feature 기여도.

### 2.4 손실
- 비대칭 손실로 **과대추정(늦게)에 더 큰 페널티**(quantile/pinball 등). BIS 특성 반영. heteroscedastic은 유지 검토(누적경과초는 ord 클수록 분산↑).

---

## 3. y(타깃) 정의 & trip 노이즈 — 가장 어려운 문제

### 3.1 결정해야 할 것
- **앵커**: 누적경과초의 시작점 = 시간표 출발(권장, agent 의미상) vs 첫 관측. 시간표 출발이면 Phase 3 trip↔시간표 매칭이 선행.
- **형태**: 누적(출발→정류장) vs **구간(정류장간) 예측 후 합산**. 지리/교통 결합엔 구간 단위가 압도적으로 자연스러움(구간시간↔도로링크↔교통) + 누적의 분산누적/이분산 완화.

### 3.2 trip 노이즈 카탈로그 (raw에서 후처리로 잡아내야 할 정상 판별 문제)
- 1~3번 정류장 미감지 → 4번부터 갑자기 등장.
- 하행 1번에서 출발 안 하고 정지(상행 종점 운전 기사가 추적기 안 끄고 휴식 등).
- 종점 통과 전 추적기 OFF / 통과 후에도 OFF 안 함.
- 시간표보다 일찍/늦게 출발, "준비"만 누르고 대기.
- → 작년엔 번호판 락온으로도 잘못된 lock-on·노이즈로 문제 多. **raw 전수집 상황에서 휴리스틱으로 정상 trip 판별**이 핵심 과제(Phase 3).
- 작년 클렌징 규칙(`cleanBusLogs.py`): 1일 초과 log 삭제 / ORD간 15분 초과 삭제 / 출발 후 2시간 초과 삭제. → 참고 baseline.

---

## 4. 기하(vtx) 검증·보정 — 작년 수작업 복원

### 4.1 작년에 실제로 한 것 (복원)
- vtx 선형이 깨진 노선은 **구글맵으로 위경도를 직접 따서 raw vtx를 손수 수정**했음(확실).
- 문제노선 **검수기 = `checkRoute.py`**: route_nodes가 정류장을 몇 개 놓쳤는지(`missing_count`) 카운트(=vtx가 정류장 30m 내로 안 지나가면 누락).
- **육안확인용 일회용 스크립트는 git에 없음(복구 불가).** 삭제됐지만 참고 가능한 관련 도구: `mapVtxToRoadId.py`, `analyzeFirstETA.py`, `measureETAError*.py`.
- **수작업 노선 목록 복원**: `vtx/` mtime 분석 → bulk(05-04 08:31, 350개)와 다른 **101개**가 후처리/수정 대상. (DATA_NOTES의 "101개 노선 vtx 어긋남"과 정확히 일치)
  - 10:48 일괄 93개(일괄 재저장 성격) + **개별 손편집 8개**(가장 확실): 노선 40·55·535·752·1994.
  - 노선번호 분포상 길거나 분지 많은 노선(20·85·40·165·25·23 …)이 깨지기 쉬움.
  - 산출물: [`vtx_manual_2025.json`](vtx_manual_2025.json) (stdid는 2026과 다름 → 노선번호 참고용).

### 4.2 자동 파이프라인 (작년, 재사용 가능)
- `generateRouteNodes.py`: vtx 선형 **200m 리샘플** + 정류장 **30m 내 스냅** → 순서있는 route_nodes.
- `mapRouteNodesToTraffic.py`: 각 노드를 **반경 100m 최근접 교통노드 매핑** (= 지리↔교통 결합. 2.2의 핵심을 이미 구현).

### 4.3 올해 해야 할 것
- stdid·노선 개편 + route/traffic 노드 변화 → **올해 데이터로 재구성·재검증** 필수.
- vtx가 정상일 수도 있으니 **먼저 뜯어보고 검증**(checkRoute 동등 검수 + 시각화 재작성), 깨진 것만 수작업 보정.
- **이것이 1차 모델의 선행조건** — 기하가 확실해야 지리기반 종속성/교통결합이 성립.

---

## 5. 미결정 갈림길 (합의 필요 — CLAUDE.md 원칙 3: 큰 결정은 상의)
1. **y 앵커**: 시간표 출발(권장) vs 첫 관측.
2. **y 형태**: 누적 vs 구간예측+합산(→ 지리/교통결합·1·2차 granularity 통일에 유리). "구간=2차"였던 기존 구획을 바꿀지.
3. **선행작업 수용**: 2.2를 하려면 route_nodes·traffic매핑(작년 자산)을 Phase 5에서 **앞당겨** 1차 전에 수행.

> 잠정 추천: (1) 시간표 출발, (2) 구간예측+합산으로 1·2차 통일, (3) 선행작업 수용. 셋이 맞물려 지리·교통·희소노선 일반화가 함께 풀림.

---

## 6. 평가 프로토콜
- **baseline 앵커**: 해당 층 mean 예측. 모든 모델은 이걸 이겨야 함.
- 모델 순서: baseline → **GBDT(LightGBM)** (범주형 native, feature importance 무료로 §2.2~2.3 검증) → 부족하면 공간 임베딩 NN.
- 누수 방지: 모든 feature는 "그 trip 발생 시점에 이미 과거"인 정보만. mean/교통집계는 과거만, 증분학습은 시간순 준수. (작년 `mean_date=target-2, raw_date=target-1` 규율 계승)
