from __future__ import annotations

from src.config import EnvConfig
from src.proxy_provider import ProxyProvider


class FakeResponse:
    def __init__(self, json_data=None, status_code: int = 200, text: str = ""):
        self._json_data = json_data or {}
        self.status_code = status_code
        self.text = text

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("http_error")

    def json(self):
        if self._json_data is None:
            raise ValueError("not json")
        return self._json_data


class FakeSession:
    def get(self, url, headers=None, timeout=None, proxies=None):
        if "proxy-api" in url:
            return FakeResponse(
                {
                    "data": {
                        "proxies": [
                            {
                                "ip": "1.2.3.4",
                                "port": 8080,
                                "scheme": "http",
                                "u": "",
                                "p": "",
                            }
                        ]
                    }
                }
            )
        return FakeResponse(status_code=200)


class FakeTextSession:
    def get(self, url, headers=None, timeout=None, proxies=None):
        if "proxy-api" in url:
            return FakeResponse(json_data=None, text="8.8.8.8:3128")
        return FakeResponse(status_code=200)


def test_proxy_provider_parse_and_healthcheck() -> None:
    env = EnvConfig(
        llm_base_url="https://api.openai.com/v1",
        llm_api_key="k",
        llm_model="m",
        proxy_api_url="https://proxy-api.example.com/list",
        proxy_api_auth_header="Authorization: Bearer x",
        proxy_api_result_path="data.proxies",
        proxy_api_item_schema={
            "host": "ip",
            "port": "port",
            "protocol": "scheme",
            "username": "u",
            "password": "p",
        },
    )
    provider = ProxyProvider(env=env, session=FakeSession())
    proxies = provider.fetch_proxies()
    assert len(proxies) == 1
    assert proxies[0].proxy_url == "http://1.2.3.4:8080"
    assert provider.healthcheck(proxies[0]) is True


def test_proxy_provider_text_plain_fallback() -> None:
    env = EnvConfig(
        llm_base_url="https://api.openai.com/v1",
        llm_api_key="k",
        llm_model="m",
        proxy_api_url="https://proxy-api.example.com/list",
        proxy_api_auth_header="Authorization: Bearer x",
        proxy_api_result_path="data.proxies",
        proxy_api_item_schema={
            "host": "ip",
            "port": "port",
            "protocol": "scheme",
            "username": "u",
            "password": "p",
        },
    )
    provider = ProxyProvider(env=env, session=FakeTextSession())
    proxies = provider.fetch_proxies()
    assert len(proxies) == 1
    assert proxies[0].host == "8.8.8.8"
    assert proxies[0].port == 3128
