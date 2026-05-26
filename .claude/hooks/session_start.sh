#!/usr/bin/env bash
# SessionStart 훅: 매 세션 시작 시 "작업 일관성 체크리스트 + 현재 STATUS(마일스톤)"를
# 모델 컨텍스트에 자동 주입한다. 어떤 세션으로 시작하든 규약·진행상황이 항상 들어오도록.
# cwd 와 무관하게 스크립트 자기 위치 기준으로 repo root 를 해석한다.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STATUS_FILE="$ROOT/docs/STATUS.md"

read -r -d '' CHECKLIST <<'EOF' || true
=== BLog 작업 시작 — 일관성 체크리스트 (SessionStart 훅 자동 주입) ===
어떤 세션이든 작업 전 반드시 숙지 (행동규약은 CLAUDE.md 가 자동 로드됨):
- docs/STATUS.md      현재 진행상황·마일스톤·다음 할 일  ← 아래 전문 첨부
- docs/ROADMAP.md     전체 그림·단계 의존성
- docs/DATA_NOTES.md  데이터 신뢰성 이슈
- docs/DATA_SCHEMA.md 모든 데이터 파일 json/jsonl 구조
핵심 원칙: 잘게 쪼개 commit+STATUS 갱신 / 큰 결정은 먼저 상의 / 임시방편 금지 /
추측 말고 검증 / CPU 전처리는 멀티프로세싱 / push 는 사용자 신호 시.

--- 현재 docs/STATUS.md 전문 ---
EOF

STATUS_CONTENT="$(cat "$STATUS_FILE" 2>/dev/null || echo '(docs/STATUS.md 를 찾지 못함)')"
CTX="$CHECKLIST
$STATUS_CONTENT"

# jq 미설치 환경 → python3 로 안전하게 JSON 생성. additionalContext 로 컨텍스트 주입.
printf '%s' "$CTX" | python3 -c 'import json,sys; print(json.dumps({"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":sys.stdin.read()}}))'
