"""KMA 초단기실황 기반 날씨 보정 서비스."""

import json
import math
import os
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import urlopen


class WeatherService:
    """KMA API를 조회해 혼잡도 보정 계수를 계산한다."""

    _API_URL = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst"

    def __init__(self, service_key=None, cache_ttl_seconds=3600, timeout_seconds=4):
        self.service_key = service_key or os.getenv("KMA_API_KEY")
        self.cache_ttl_seconds = cache_ttl_seconds
        self.timeout_seconds = timeout_seconds
        self._cache = {}

    def get_weather_factor(self, lat=37.4979, lng=127.0276):
        """좌표 기준으로 날씨 보정 계수를 반환한다."""
        cache_key = (round(float(lat), 4), round(float(lng), 4))
        cached = self._cache.get(cache_key)
        now_ts = time.time()
        if cached and now_ts - cached[0] < self.cache_ttl_seconds:
            return cached[1]

        if not self.service_key:
            return 1.0

        try:
            nx, ny = self._latlng_to_grid(lat, lng)
            base_date, base_time = self._get_base_datetime()
            payload = {
                "serviceKey": self.service_key,
                "numOfRows": 100,
                "pageNo": 1,
                "dataType": "JSON",
                "base_date": base_date,
                "base_time": base_time,
                "nx": nx,
                "ny": ny,
            }
            url = f"{self._API_URL}?{urlencode(payload)}"
            with urlopen(url, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
            factor = self._extract_factor(raw)
        except Exception:
            factor = 1.0

        self._cache[cache_key] = (now_ts, factor)
        return factor

    def _extract_factor(self, raw_body):
        """응답에서 강수/기온 정보를 추출해 보정 계수를 계산한다."""
        data = json.loads(raw_body)
        body = data.get("response", {}).get("body", {})
        items = body.get("items", {}).get("item", [])

        pty = None
        t1h = None
        for item in items:
            category = item.get("category")
            value = item.get("obsrValue")
            if category == "PTY":
                try:
                    pty = int(float(value))
                except (TypeError, ValueError):
                    pty = None
            elif category == "T1H":
                try:
                    t1h = float(value)
                except (TypeError, ValueError):
                    t1h = None

        if pty in (1, 2, 3, 4):
            return 1.15
        if t1h is not None and (t1h >= 33 or t1h <= -5):
            return 1.08
        return 1.0

    def _get_base_datetime(self):
        """초단기실황 조회 기준시각(정시)으로 변환한다."""
        kst = timezone(timedelta(hours=9))
        now = datetime.now(kst)
        if now.minute < 40:
            now = now - timedelta(hours=1)
        base = now.replace(minute=0, second=0, microsecond=0)
        return base.strftime("%Y%m%d"), base.strftime("%H%M")

    def _latlng_to_grid(self, lat, lng):
        """위경도를 기상청 격자(nx, ny)로 변환한다."""
        re = 6371.00877
        grid = 5.0
        slat1 = 30.0
        slat2 = 60.0
        olon = 126.0
        olat = 38.0
        xo = 43.0
        yo = 136.0

        degrad = math.pi / 180.0
        re = re / grid
        slat1 = slat1 * degrad
        slat2 = slat2 * degrad
        olon = olon * degrad
        olat = olat * degrad

        sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
        sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
        sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
        sf = math.pow(sf, sn) * math.cos(slat1) / sn
        ro = math.tan(math.pi * 0.25 + olat * 0.5)
        ro = re * sf / math.pow(ro, sn)

        ra = math.tan(math.pi * 0.25 + float(lat) * degrad * 0.5)
        ra = re * sf / math.pow(ra, sn)
        theta = float(lng) * degrad - olon
        if theta > math.pi:
            theta -= 2.0 * math.pi
        if theta < -math.pi:
            theta += 2.0 * math.pi
        theta *= sn

        nx = int(ra * math.sin(theta) + xo + 0.5)
        ny = int(ro - ra * math.cos(theta) + yo + 0.5)
        return nx, ny
