# JBNU_BLog

전주시 시내버스 **자체 ETA 예측 모델** 기반 **목표 도착형 이동계획 AI Agent**.

사용자가 *목적지 + 목표 도착 시각* 을 입력하면, 도보·탑승버스·환승·예상도착을 종합해
**"지금 출발해야 하는가 / 어떤 버스를 타야 하는가 / 안전한 대안은 무엇인가"** 를 행동 단위로 안내한다.

> 전체 그림은 [docs/ROADMAP.md](docs/ROADMAP.md), 현재 진행상황은 [docs/STATUS.md](docs/STATUS.md), 환경 셋업은 [docs/SETUP.md](docs/SETUP.md).

## 구조

```
app/    Flutter 앱 (iOS/Android)
src/    Python — 수집·전처리·모델·Agent·serve (단일 서버)
data/   reference(git) · raw/interim/features/models/predictions(gitignore)
docs/   문서
```

## 빠른 시작

```bash
git clone https://github.com/Quinsie/JBNU_BLog.git
cd JBNU_BLog
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # KMA_API_KEY 채우기

# (JBNU 서버에서) 공유 raw 디스크 연결
bash src/scripts/setup_data.sh
```

자세한 데이터 경로 설정(다른 서버 / 데이터를 전달받은 경우 포함)은 [docs/SETUP.md](docs/SETUP.md).
