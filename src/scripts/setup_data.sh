#!/usr/bin/env bash
# 공유 raw 데이터 디스크 연결.
# - JBNU 서버: /mnt/data1/B_Log 를 blog 그룹 공유로 만들고 data/raw 를 심볼릭 링크.
# - 그 외 환경: 로컬 data/raw 디렉토리만 생성 (코드는 어차피 상대경로라 그대로 동작).
# 멱등(여러 번 실행해도 안전). 권한 작업은 sudo 필요.

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

SHARED_RAW="${SHARED_RAW:-/mnt/data1/B_Log/raw}"
SHARED_BASE="$(dirname "$SHARED_RAW")"          # /mnt/data1/B_Log
DISK_ROOT="$(dirname "$SHARED_BASE")"           # /mnt/data1
GROUP="blog"
OWNER="${SUDO_USER:-$(id -un)}"                 # 주 개발자(=소유자)
MEMBERS=(jiho yubin hyewon gaeun)

echo "[setup] repo  = $REPO_ROOT"

if [ -d "$DISK_ROOT" ]; then
  echo "[setup] 공유 디스크 감지: $SHARED_BASE  (소유자=$OWNER, 그룹=$GROUP)"

  if ! getent group "$GROUP" >/dev/null; then
    echo "[setup] 그룹 '$GROUP' 생성"
    sudo groupadd "$GROUP"
  fi
  for u in "${MEMBERS[@]}"; do
    if id "$u" >/dev/null 2>&1; then sudo usermod -aG "$GROUP" "$u"; fi
  done

  sudo mkdir -p "$SHARED_RAW"
  # 소유자는 즉시 쓰기 가능, 그룹원은 재로그인 후. setgid → 새 파일이 그룹 상속.
  sudo chown -R "$OWNER":"$GROUP" "$SHARED_BASE"
  sudo chmod -R 2775 "$SHARED_BASE"

  if [ -L "$REPO_ROOT/data/raw" ] || [ -e "$REPO_ROOT/data/raw" ]; then
    echo "[setup] data/raw 이미 존재 — 링크 생성 건너뜀"
  else
    ln -s "$SHARED_RAW" "$REPO_ROOT/data/raw"
    echo "[setup] 링크: data/raw -> $SHARED_RAW"
  fi
else
  echo "[setup] 공유 디스크 없음 — 로컬 data/raw 사용"
  mkdir -p "$REPO_ROOT/data/raw"
fi

echo "[setup] 완료. (그룹 추가는 각 사용자 재로그인 후 반영)"
