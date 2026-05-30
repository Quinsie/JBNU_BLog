#!/usr/bin/env bash
# SessionStart 훅 (anti-drift 주입 — 첫 겹): 매 세션 시작 시
#   [일관성 체크리스트 → VISION 큰그림(BRIEF) → 현재 STATUS 전문]
# 을 모델 컨텍스트에 자동 주입한다. 순서가 핵심 — 큰 그림(VISION)을 먼저 깔고, 그 위에 현재 위치(STATUS).
# cwd 와 무관하게 스크립트 자기 위치 기준으로 repo root 를 해석한다.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VISION_FILE="$ROOT/docs/VISION.md"
STATUS_FILE="$ROOT/docs/STATUS.md"

read -r -d '' CHECKLIST <<'EOF' || true
=== BLog 작업 시작 — anti-drift 체크리스트 (SessionStart 훅 자동 주입) ===
어떤 세션이든 작업 전 반드시 (행동규약 전문은 CLAUDE.md 자동 로드):
- docs/VISION.md   큰 그림 단일 권위 — 항상 가장 먼저 짚는다   ← 아래 BRIEF 첨부
- docs/STATUS.md   현재 진행상황·마일스톤·다음 할 일           ← 아래 전문 첨부
- 작업별 필수 위성은 CLAUDE.md §anti-drift 의 〈작업→필수문서〉 라우팅 맵 참조
핵심: 문서 > 최근 대화 / 잘게 쪼개 commit+STATUS / 큰 결정은 먼저 상의 /
임시방편 금지 / 추측 말고 검증 / 비자명 작업은 착수 전 체크인 선언.

--- docs/VISION.md 큰그림 (BRIEF §1~§5) ---
EOF

# VISION.md 의 BRIEF 마커 구간(<!-- BRIEF:START --> ~ <!-- BRIEF:END -->)만 추출(마커 라인 제외).
VISION_BRIEF="$(awk '/<!-- BRIEF:START/{f=1;next} /<!-- BRIEF:END/{f=0} f' "$VISION_FILE" 2>/dev/null)"
[ -z "$VISION_BRIEF" ] && VISION_BRIEF="(docs/VISION.md BRIEF 마커를 찾지 못함 — 파일 직접 확인)"

STATUS_CONTENT="$(cat "$STATUS_FILE" 2>/dev/null || echo '(docs/STATUS.md 를 찾지 못함)')"

CTX="$CHECKLIST
$VISION_BRIEF

--- docs/STATUS.md 현재 위치 (전문) ---
$STATUS_CONTENT"

# jq 미설치 환경 → python3 로 안전하게 JSON 생성. additionalContext 로 컨텍스트 주입.
printf '%s' "$CTX" | python3 -c 'import json,sys; print(json.dumps({"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":sys.stdin.read()}}))'
