from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from dotenv import dotenv_values


REQUIRED_ENV_KEYS = (
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "LLM_MODEL",
    "PROXY_API_URL",
    "PROXY_API_AUTH_HEADER",
    "PROXY_API_RESULT_PATH",
    "PROXY_API_ITEM_SCHEMA",
)


@dataclass
class EnvConfig:
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    proxy_api_url: str
    proxy_api_auth_header: str
    proxy_api_result_path: str
    proxy_api_item_schema: dict[str, str]
    llm_timeout_sec: int = 30
    browser_headless: bool = False
    action_delay_min_ms: int = 800
    action_delay_max_ms: int = 3500
    submit_retry_per_task: int = 2
    proxy_healthcheck_url: str = "https://httpbin.org/ip"
    proxy_default_username: str = ""
    proxy_default_password: str = ""

    @property
    def proxy_auth_header_pair(self) -> tuple[str, str]:
        if ":" not in self.proxy_api_auth_header:
            raise ValueError(
                "PROXY_API_AUTH_HEADER must follow 'Header-Name: value' format."
            )
        key, value = self.proxy_api_auth_header.split(":", 1)
        return key.strip(), value.strip()


@dataclass
class Persona:
    persona_id: str
    description: str
    weight: float
    style: str
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskConfig:
    url: str
    submit_count: int
    mapping_file: str
    persona_mix: dict[str, float]
    delay_profile: str = "slow_random"


@dataclass
class PersonaConfig:
    personas: list[Persona]
    tasks: list[TaskConfig]

    @property
    def persona_index(self) -> dict[str, Persona]:
        return {p.persona_id: p for p in self.personas}


def load_env_config(env_path: Path | str = ".env") -> EnvConfig:
    env_file = Path(env_path)
    if not env_file.exists():
        raise ValueError(f"Missing env file: {env_file}")
    raw_env = {k: v for k, v in dotenv_values(env_file).items() if v is not None}
    missing = [k for k in REQUIRED_ENV_KEYS if not raw_env.get(k)]
    if missing:
        raise ValueError(f"Missing required .env keys: {', '.join(missing)}")
    schema_raw = raw_env["PROXY_API_ITEM_SCHEMA"]
    try:
        schema = json.loads(schema_raw)
    except json.JSONDecodeError as exc:
        raise ValueError("PROXY_API_ITEM_SCHEMA must be a JSON object string.") from exc
    for key in ("host", "port", "protocol", "username", "password"):
        if key not in schema:
            raise ValueError(f"PROXY_API_ITEM_SCHEMA missing key: {key}")
    min_ms = int(raw_env.get("ACTION_DELAY_MIN_MS", 800))
    max_ms = int(raw_env.get("ACTION_DELAY_MAX_MS", 3500))
    if min_ms < 0 or max_ms <= 0 or min_ms > max_ms:
        raise ValueError("Invalid action delay range.")
    return EnvConfig(
        llm_base_url=raw_env["LLM_BASE_URL"].rstrip("/"),
        llm_api_key=raw_env["LLM_API_KEY"],
        llm_model=raw_env["LLM_MODEL"],
        proxy_api_url=raw_env["PROXY_API_URL"],
        proxy_api_auth_header=raw_env["PROXY_API_AUTH_HEADER"],
        proxy_api_result_path=raw_env["PROXY_API_RESULT_PATH"],
        proxy_api_item_schema=schema,
        llm_timeout_sec=int(raw_env.get("LLM_TIMEOUT_SEC", 30)),
        browser_headless=_to_bool(raw_env.get("BROWSER_HEADLESS", "false")),
        action_delay_min_ms=min_ms,
        action_delay_max_ms=max_ms,
        submit_retry_per_task=int(raw_env.get("SUBMIT_RETRY_PER_TASK", 2)),
        proxy_healthcheck_url=raw_env.get("PROXY_HEALTHCHECK_URL", "https://httpbin.org/ip"),
        proxy_default_username=raw_env.get("PROXY_DEFAULT_USERNAME", ""),
        proxy_default_password=raw_env.get("PROXY_DEFAULT_PASSWORD", ""),
    )


def load_urls(url_file: Path | str = "网址.txt") -> list[str]:
    path = Path(url_file)
    if not path.exists():
        raise ValueError(f"Missing URL file: {path}")
    urls: list[str] = []
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parsed = urlparse(line)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError(f"Invalid URL in {path}: {line}")
        urls.append(line)
    if not urls:
        raise ValueError(f"No valid URLs found in {path}")
    return urls


def load_persona_config(config_file: Path | str = "人格配置.json") -> PersonaConfig:
    path = Path(config_file)
    if not path.exists():
        raise ValueError(f"Missing persona config file: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}") from exc
    personas = _parse_personas(payload.get("personas"))
    tasks = _parse_tasks(payload.get("tasks"), personas)
    return PersonaConfig(personas=personas, tasks=tasks)


def validate_tasks_against_urls(persona_cfg: PersonaConfig, urls: list[str]) -> None:
    url_set = set(urls)
    missing = [t.url for t in persona_cfg.tasks if t.url not in url_set]
    if missing:
        raise ValueError(
            "Tasks contain URLs not present in 网址.txt: " + ", ".join(sorted(set(missing)))
        )


def slugify_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.replace(":", "_").replace(".", "_")
    path = parsed.path.strip("/").replace("/", "_")
    query = parsed.query.replace("=", "_").replace("&", "_")
    parts = [p for p in (host, path, query) if p]
    slug = "__".join(parts)
    return slug[:120] or "survey"


def _parse_personas(raw: Any) -> list[Persona]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("personas must be a non-empty list.")
    personas: list[Persona] = []
    ids: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("Each persona must be an object.")
        persona_id = str(item.get("id", "")).strip()
        if not persona_id:
            raise ValueError("Persona id is required.")
        if persona_id in ids:
            raise ValueError(f"Duplicate persona id: {persona_id}")
        ids.add(persona_id)
        description = str(item.get("description", "")).strip()
        if not description:
            raise ValueError(f"Persona '{persona_id}' missing description.")
        style = str(item.get("style") or item.get("answer_style") or "").strip()
        if not style:
            raise ValueError(f"Persona '{persona_id}' missing style.")
        weight = float(item.get("weight", 1.0))
        if weight <= 0:
            raise ValueError(f"Persona '{persona_id}' weight must be > 0.")
        meta = {k: v for k, v in item.items() if k not in {"id", "description", "weight", "style", "answer_style"}}
        personas.append(
            Persona(
                persona_id=persona_id,
                description=description,
                weight=weight,
                style=style,
                meta=meta,
            )
        )
    return personas


def _parse_tasks(raw: Any, personas: list[Persona]) -> list[TaskConfig]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("tasks must be a non-empty list.")
    persona_ids = {p.persona_id for p in personas}
    defaults = {p.persona_id: p.weight for p in personas}
    tasks: list[TaskConfig] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("Each task must be an object.")
        url = str(item.get("url", "")).strip()
        if not url:
            raise ValueError("Task url is required.")
        submit_count = item.get("submit_count")
        if not isinstance(submit_count, int) or submit_count <= 0:
            raise ValueError(f"Task submit_count must be a positive integer: {url}")
        mapping_file = str(item.get("mapping_file", "")).strip()
        if not mapping_file:
            raise ValueError(f"Task mapping_file is required: {url}")
        delay_profile = str(item.get("delay_profile", "slow_random")).strip() or "slow_random"
        mix = item.get("persona_mix") or defaults
        if not isinstance(mix, dict) or not mix:
            raise ValueError(f"Task persona_mix must be an object: {url}")
        normalized_mix: dict[str, float] = {}
        total = 0.0
        for pid, value in mix.items():
            if pid not in persona_ids:
                raise ValueError(f"Task {url} references unknown persona id: {pid}")
            weight = float(value)
            if weight <= 0:
                raise ValueError(f"Task {url} persona_mix weight must be > 0: {pid}")
            normalized_mix[pid] = weight
            total += weight
        for pid in list(normalized_mix):
            normalized_mix[pid] = normalized_mix[pid] / total
        tasks.append(
            TaskConfig(
                url=url,
                submit_count=submit_count,
                mapping_file=mapping_file,
                persona_mix=normalized_mix,
                delay_profile=delay_profile,
            )
        )
    return tasks


def _to_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}
