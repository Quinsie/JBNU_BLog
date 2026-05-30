"""FastAPI 앱 진입점. 전 엔드포인트 dummy 로 띄워 완전한 Swagger 계약을 제공한다.

실행:  uvicorn src.serve.app:app --host 0.0.0.0 --port 8000
문서:  http://<host>:8000/docs   (OpenAPI: /openapi.json)

real 교체는 routers/<계층>.py 단위로 진행 — app 구조는 그대로 둔다.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .schemas import Health
from .routers import reference, live, inference, weather, plan

API_VERSION = "0.1.0-dummy"

app = FastAPI(
    title="BLog — 전주 버스 목표도착형 이동계획 API",
    version=API_VERSION,
    description=(
        "전주 시내버스 ETA 기반 목표도착형 이동계획 에이전트 API.\n\n"
        "**현재 전 엔드포인트 dummy** — 기능 완성 계층부터 real 로 교체.\n"
        "각 응답의 `source` 필드로 dummy/real 출처를 표기.\n\n"
        "계층: 기준데이터(reference) · 실황(live) · 추론(pre/live-eta) · 날씨(weather) · 에이전트(plan)."
    ),
)

# 프론트(모바일/웹)에서 직접 호출 — dev 단계 전체 허용. 배포 시 도메인 화이트리스트로 좁힌다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (reference, live, inference, weather, plan):
    app.include_router(r.router)


@app.get("/health", response_model=Health, tags=["운영"], summary="헬스체크")
def health() -> Health:
    return Health(version=API_VERSION)
