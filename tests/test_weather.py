# -*- coding: utf-8 -*-
import json
from unittest.mock import MagicMock, patch

from src.weather import WeatherService


def _mock_http_response(payload):
    resp = MagicMock()
    resp.read.return_value = json.dumps(payload).encode("utf-8")
    ctx = MagicMock()
    ctx.__enter__.return_value = resp
    ctx.__exit__.return_value = False
    return ctx


def _kma_payload(pty=0, t1h=20):
    return {
        "response": {
            "body": {
                "items": {
                    "item": [
                        {"category": "PTY", "obsrValue": str(pty)},
                        {"category": "T1H", "obsrValue": str(t1h)},
                    ]
                }
            }
        }
    }


def test_weather_factor_precipitation():
    service = WeatherService(service_key="dummy")
    with patch("src.weather.urlopen", return_value=_mock_http_response(_kma_payload(pty=1, t1h=18))):
        assert service.get_weather_factor() == 1.15


def test_weather_factor_extreme_temperature():
    service = WeatherService(service_key="dummy")
    with patch("src.weather.urlopen", return_value=_mock_http_response(_kma_payload(pty=0, t1h=35))):
        assert service.get_weather_factor() == 1.08


def test_weather_factor_normal_condition():
    service = WeatherService(service_key="dummy")
    with patch("src.weather.urlopen", return_value=_mock_http_response(_kma_payload(pty=0, t1h=22))):
        assert service.get_weather_factor() == 1.0


def test_weather_cache_ttl_one_hour():
    service = WeatherService(service_key="dummy", cache_ttl_seconds=3600)
    with patch("src.weather.urlopen", return_value=_mock_http_response(_kma_payload(pty=3, t1h=-2))) as mocked_urlopen:
        with patch("src.weather.time.time", side_effect=[1000, 1010]):
            first = service.get_weather_factor()
            second = service.get_weather_factor()

    assert first == 1.15
    assert second == 1.15
    assert mocked_urlopen.call_count == 1


def test_weather_graceful_degradation_on_api_failure():
    service = WeatherService(service_key="dummy")
    with patch("src.weather.urlopen", side_effect=RuntimeError("kma fail")):
        assert service.get_weather_factor() == 1.0


def test_weather_without_api_key_returns_default():
    service = WeatherService(service_key=None)
    with patch("src.weather.urlopen") as mocked_urlopen:
        assert service.get_weather_factor() == 1.0
    mocked_urlopen.assert_not_called()
