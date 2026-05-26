"""위경도 → 기상청 격자(nx, ny) 변환 (Lambert Conformal Conic).

기상청 단기예보 API 격자 규격. 작년 convertToGrid.py 와 동일.
"""

import math


def latlng_to_grid(lat: float, lng: float) -> tuple[int, int]:
    RE = 6371.00877   # 지구 반경 (km)
    GRID = 5.0        # 격자 간격 (km)
    SLAT1, SLAT2 = 30.0, 60.0   # 투영 위도
    OLON, OLAT = 126.0, 38.0    # 기준점 경위도
    XO, YO = 43, 136            # 기준점 격자

    DEGRAD = math.pi / 180.0
    re = RE / GRID
    slat1, slat2 = SLAT1 * DEGRAD, SLAT2 * DEGRAD
    olon, olat = OLON * DEGRAD, OLAT * DEGRAD

    sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
    sf = (sf ** sn * math.cos(slat1)) / sn
    ro = math.tan(math.pi * 0.25 + olat * 0.5)
    ro = re * sf / (ro ** sn)

    ra = math.tan(math.pi * 0.25 + lat * DEGRAD * 0.5)
    ra = re * sf / (ra ** sn)
    theta = lng * DEGRAD - olon
    if theta > math.pi:
        theta -= 2.0 * math.pi
    if theta < -math.pi:
        theta += 2.0 * math.pi
    theta *= sn

    x = int(ra * math.sin(theta) + XO + 0.5)
    y = int(ro - ra * math.cos(theta) + YO + 0.5)
    return x, y
