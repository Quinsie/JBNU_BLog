"""전주 ITS 비공식 API 클라이언트.

- Base: https://its.jeonju.go.kr  (작년 www.jeonjuits.go.kr 에서 변경)
- 전부 POST + x-www-form-urlencoded. `X-Requested-With` 누락 시 WAF 차단.
- 응답이 '<' 로 시작하면 WAF 차단 페이지 → WafBlocked.
- 정적 수집/디버그용 동기 클라이언트. (실시간 수집기는 aiohttp 별도)
"""

import time
import requests

BASE_URL = "https://its.jeonju.go.kr"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
}


class WafBlocked(RuntimeError):
    pass


def call(endpoint: str, params: dict | None = None, *,
         session: requests.Session | None = None,
         retries: int = 3, timeout: float = 10.0) -> dict:
    """`bis/selectXxx.do` 형태 endpoint 호출. locale=ko-kr 기본 주입."""
    url = f"{BASE_URL}/{endpoint}"
    data = {"locale": "ko-kr", **(params or {})}
    s = session or requests
    last: Exception | None = None
    for attempt in range(retries):
        try:
            r = s.post(url, headers=HEADERS, data=data, timeout=timeout)
            r.raise_for_status()
            if r.text.lstrip().startswith("<"):
                raise WafBlocked(endpoint)
            return r.json()
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    raise last  # type: ignore[misc]


# ── 정적 엔드포인트 헬퍼 ─────────────────────────────
def grp_route_list(session=None) -> list[dict]:
    """전체 노선번호 목록 (대표 stdid)."""
    return call("bis/selectGrpRouteList.do", {"brt_low": 0}, session=session).get("resultList", [])


def route_sublist(brt_no: str, session=None) -> list[dict]:
    """노선번호의 분선 목록 (stdid·방향·시종점·배차·첫막차)."""
    return call("bis/selectBisRouteSubList.do", {"brt_no": brt_no, "brt_low": 0},
                session=session).get("resultList", [])


def route_stops(stdid: int | str, session=None) -> list[dict]:
    """stdid 의 정류장 시퀀스 (ORD·좌표)."""
    return call("bis/selectBisRouteRsltList.do", {"routeId": stdid},
                session=session).get("resultList", [])


def route_vtx(stdid: int | str, session=None) -> list[dict]:
    """stdid 의 경로 vertex (LINK_ID·좌표). 배열 순서 = IDX."""
    return call("bis/selectBisRouteVtxList.do", {"routeId": stdid},
                session=session).get("resultList", [])


def route_time_info(stdid: int | str, session=None) -> dict:
    """stdid 의 시간표 + 메타 (result + timeList). BRT_TEXT 운행변동 포함."""
    return call("bis/selectBisRouteTimeInfo.do", {"routeId": stdid}, session=session)
