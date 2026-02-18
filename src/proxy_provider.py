from __future__ import annotations

from dataclasses import dataclass
from itertools import cycle
import re
from typing import Any

import requests

from src.config import EnvConfig


@dataclass
class ProxyEndpoint:
    protocol: str
    host: str
    port: int
    username: str = ""
    password: str = ""

    @property
    def proxy_url(self) -> str:
        auth = ""
        if self.username and self.password:
            auth = f"{self.username}:{self.password}@"
        return f"{self.protocol}://{auth}{self.host}:{self.port}"


class ProxyProvider:
    def __init__(self, env: EnvConfig, session: requests.Session | None = None):
        self.env = env
        self.session = session or requests.Session()

    def fetch_proxies(self) -> list[ProxyEndpoint]:
        header_key, header_val = self.env.proxy_auth_header_pair
        response = self.session.get(
            self.env.proxy_api_url,
            headers={header_key: header_val},
            timeout=15,
        )
        response.raise_for_status()
        proxies: list[ProxyEndpoint] = []
        # Primary mode: JSON payload parsed by mapping schema.
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if payload is not None:
            items = _path_get(payload, self.env.proxy_api_result_path)
            if isinstance(items, dict):
                items = [items]
            if isinstance(items, list):
                proxies.extend(self._parse_json_items(items))
        # Fallback mode: text/plain "ip:port" (single or multi-line).
        if not proxies:
            proxies.extend(
                _parse_text_proxies(
                    response.text,
                    default_username=self.env.proxy_default_username,
                    default_password=self.env.proxy_default_password,
                )
            )
        if not proxies:
            raise ValueError("No proxies parsed from proxy API response.")
        return proxies

    def healthcheck(self, proxy: ProxyEndpoint) -> bool:
        proxy_url = proxy.proxy_url
        try:
            response = self.session.get(
                self.env.proxy_healthcheck_url,
                timeout=10,
                proxies={"http": proxy_url, "https": proxy_url},
            )
        except requests.RequestException:
            return False
        return response.status_code < 400

    def get_healthy_proxies(self, max_to_test: int = 30) -> list[ProxyEndpoint]:
        all_proxies = self.fetch_proxies()
        healthy: list[ProxyEndpoint] = []
        for proxy in all_proxies[:max_to_test]:
            if self.healthcheck(proxy):
                healthy.append(proxy)
        return healthy

    @staticmethod
    def build_rotator(proxies: list[ProxyEndpoint]):
        if not proxies:
            raise ValueError("No proxies available for rotation.")
        return cycle(proxies)

    def _parse_json_items(self, items: list[Any]) -> list[ProxyEndpoint]:
        proxies: list[ProxyEndpoint] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            mapped = {}
            for field_name, source_path in self.env.proxy_api_item_schema.items():
                mapped[field_name] = _path_get(item, source_path)
            host = str(mapped.get("host", "")).strip()
            protocol = str(mapped.get("protocol", "")).strip() or "http"
            port_raw = mapped.get("port")
            if not host or port_raw is None:
                continue
            try:
                port = int(port_raw)
            except (TypeError, ValueError):
                continue
            proxies.append(
                ProxyEndpoint(
                    protocol=protocol,
                    host=host,
                    port=port,
                    username=str(mapped.get("username", "") or ""),
                    password=str(mapped.get("password", "") or ""),
                )
            )
        return proxies


def _path_get(data: Any, path: str) -> Any:
    current = data
    for part in path.split("."):
        part = part.strip()
        if not part:
            continue
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _parse_text_proxies(
    text: str,
    default_username: str = "",
    default_password: str = "",
) -> list[ProxyEndpoint]:
    candidates = [
        token.strip()
        for token in re.split(r"[\r\n,;]+", text or "")
        if token and token.strip()
    ]
    proxies: list[ProxyEndpoint] = []
    for token in candidates:
        value = token
        protocol = "http"
        if "://" in value:
            protocol, value = value.split("://", 1)
            protocol = protocol.strip().lower() or "http"
        auth_part = ""
        host_port = value
        if "@" in value:
            auth_part, host_port = value.rsplit("@", 1)
        if ":" not in host_port:
            continue
        host, port_raw = host_port.rsplit(":", 1)
        host = host.strip()
        try:
            port = int(port_raw.strip())
        except ValueError:
            continue
        username = ""
        password = ""
        if auth_part and ":" in auth_part:
            username, password = auth_part.split(":", 1)
        if (not username) and default_username:
            username = default_username
            password = default_password
        proxies.append(
            ProxyEndpoint(
                protocol=protocol,
                host=host,
                port=port,
                username=username,
                password=password,
            )
        )
    return proxies
