#!/usr/bin/env bash
# serve API 로컬 기동 + cloudflared 임시 터널(외부 공개).
#
# - uvicorn 을 0.0.0.0:8000 에 띄우고, cloudflared quick tunnel 로 공개 HTTPS URL 발급.
# - ⚠️ 캠퍼스 방화벽이 QUIC(UDP 7844)을 막으므로 `--protocol http2`(TCP 443) 필수.
#   (이거 없으면 edge 등록 실패 → Cloudflare 1033.)
# - ⚠️ trycloudflare URL 은 재기동마다 바뀜(고정 URL 은 named tunnel + 계정 필요).
# - ⚠️ uvicorn/cloudflared 는 systemd 미관리 → 리부팅/크래시 시 자동복구 없음(배포 시 보강).
#
# 사용:  bash scripts/run_serve.sh
set -euo pipefail
PORT="${PORT:-8000}"

source ~/miniconda3/etc/profile.d/conda.sh 2>/dev/null || source ~/anaconda3/etc/profile.d/conda.sh
conda activate Blog

if ! pgrep -f "uvicorn src.serve.app" >/dev/null; then
  echo "[serve] uvicorn 기동 :$PORT"
  nohup python -m uvicorn src.serve.app:app --host 0.0.0.0 --port "$PORT" \
        > /tmp/blog_serve.log 2>&1 &
  sleep 3
fi
curl -fsS "http://localhost:$PORT/health" && echo "  ← 로컬 OK"

CF="${CLOUDFLARED:-$HOME/.local/bin/cloudflared}"
echo "[serve] cloudflared 터널(http2) — 아래 trycloudflare URL 을 프론트에 전달, /docs 가 Swagger"
exec "$CF" tunnel --protocol http2 --url "http://localhost:$PORT"
