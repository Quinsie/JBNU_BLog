#!/usr/bin/env bash
# 수집기 상시 가동 supervisor. 크래시 시 지수백오프 재시작.
# 사용:
#   nohup bash src/scripts/run.sh >/dev/null 2>&1 &
#   tail -f logs/run.out
# 종료:
#   pkill -f 'src.collector'   (또는 logs/collector.pid 확인)
# 중복 실행은 src/collector 내부 flock 으로 자동 차단.

set -u
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO"
mkdir -p logs
CONDA_BIN="${CONDA_BIN:-$HOME/miniconda3/bin/conda}"
ENV_NAME="${BLOG_CONDA_ENV:-Blog}"

backoff=1
while true; do
    echo "[$(date '+%F %T')] start collector (backoff=${backoff}s)" >> logs/run.out
    "$CONDA_BIN" run -n "$ENV_NAME" --no-capture-output python -m src.collector >> logs/run.out 2>&1
    code=$?
    echo "[$(date '+%F %T')] exited code=$code" >> logs/run.out
    if [ "$code" -eq 130 ] || [ "$code" -eq 143 ]; then
        echo "[$(date '+%F %T')] signal exit — supervisor stop" >> logs/run.out
        exit 0
    fi
    sleep "$backoff"
    if [ "$backoff" -lt 60 ]; then backoff=$((backoff * 2)); [ "$backoff" -gt 60 ] && backoff=60; fi
done
