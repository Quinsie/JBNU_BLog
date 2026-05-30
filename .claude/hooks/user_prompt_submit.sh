#!/usr/bin/env bash
# UserPromptSubmit 훅 (anti-drift 주입 — 둘째 겹): 매 사용자 턴마다 짧은 가드를 주입한다.
# 세션 중간에도 큰 그림으로 끌어당겨 "최근 대화에 쏠려 길 잃는" 패턴을 구조적으로 막는다.
# 짧게 유지(매 턴 주입이라 — 노이즈 최소). 상세는 CLAUDE.md §anti-drift / docs/VISION.md.
set -uo pipefail

read -r -d '' GUARD <<'EOF' || true
=== anti-drift 가드 (매 턴 자동 주입) ===
작업 착수 전: ① docs/VISION.md 큰그림을 짚었나 ② CLAUDE.md §anti-drift 〈작업→필수문서〉 라우팅대로 관련 위성을 읽었나(부족하면 위성이 가리키는 데까지 연쇄로) ③ 비자명 작업이면 "이 작업은 VISION §X에 기여 / 위성 [A,B] 짚음 / 내 이해: …" 한 줄 체크인 선언 후 착수.
원칙: 문서 > 최근 대화. 대화는 문서를 *바꾸는 입력*이지 *덮어쓰는 것*이 아니다. 세부가 바뀌면 먼저 해당 문서에 먹이고(VISION/위성/STATUS) 진행한다.
EOF

# jq 미설치 환경 → python3 로 JSON 생성. UserPromptSubmit 의 additionalContext 로 주입.
printf '%s' "$GUARD" | python3 -c 'import json,sys; print(json.dumps({"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":sys.stdin.read()}}))'
