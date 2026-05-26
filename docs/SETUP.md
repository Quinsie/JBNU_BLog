# SETUP — 환경 셋업

코드는 절대경로를 박지 않는다. 모든 경로는 `src/common/paths.py` 한 곳에서 해석하며,
기본값은 **리포 루트의 `data/`** 다. 따라서 **아무 데서 클론해도 추가 설정 없이 동작**한다.
raw 데이터를 다른 디스크에 두는 경우에만 아래 추가 설정이 필요하다.

## 공통

```bash
git clone https://github.com/Quinsie/JBNU_BLog.git
cd JBNU_BLog
conda create -n Blog python=3.12 -y
conda activate Blog
pip install -r requirements.txt
cp .env.example .env          # 아래 'API 키' 참고해 KMA_API_KEY 입력
```

### API 키 (.env)
- `.env` 는 git 에 올라가지 않는다. **각자 자신의 공공데이터포털 키**를 `.env` 의 `KMA_API_KEY` 에 넣는다.
- 발급 키에는 **Encoding / Decoding** 두 형태가 있는데, **Decoding 키**(원문, `+` `/` `=` 포함)를 넣는다.
  코드가 요청 시 자동 URL 인코딩하므로 Encoding 키를 넣으면 이중 인코딩되어 실패한다.
- 예: `KMA_API_KEY=ttHSb/Plt...==`

## 경우별 raw 데이터 위치

### A. JBNU 서버 (공유 HDD)
원천 데이터는 용량이 커서 `/mnt/data1/B_Log/raw` (공유 디스크)에 둔다.
팀원 모두(jiho·yubin·hyewon·gaeun)가 같은 데이터를 읽고 쓸 수 있게 `blog` 그룹으로 공유.

```bash
bash src/scripts/setup_data.sh
```
이 스크립트가 하는 일:
- `blog` 그룹 생성 + 멤버 추가 (sudo)
- `/mnt/data1/B_Log` 를 `소유자:blog`, 권한 `2775`(setgid)로 설정 → 새 파일이 자동으로 `blog` 그룹 상속
- `data/raw` → `/mnt/data1/B_Log/raw` 심볼릭 링크 (이 링크는 git 에 안 올라감)

> 그룹 추가는 **재로그인 후** 반영된다. 스크립트를 처음 돌린 사용자(소유자)는 즉시 쓰기 가능.

### B. 다른 서버 / 개인 PC
아무것도 안 해도 된다. raw 가 `<repo>/data/raw` 로컬에 쌓인다.
raw 만 다른 디스크에 두고 싶으면:
```bash
echo "BLOG_RAW_DIR=/원하는/경로/raw" >> .env   # 또는 export
```

### C. jiho 한테서 원천 데이터를 전달받은 경우
받은 raw 묶음을 그냥 `data/raw/` 아래에 풀면 끝. (코드가 상대경로라 수정 불필요)
```bash
mkdir -p data/raw
tar xzf 받은_raw.tar.gz -C data/raw    # 결과: data/raw/{bus,traffic,weather,...}
```
다른 위치에 두려면 `BLOG_RAW_DIR` 로 가리키면 된다.

## 확인
```bash
python3 src/common/paths.py     # 해석된 경로 출력 (RAW_DIR 가 심볼릭인지 등)
```
