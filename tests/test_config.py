from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.config import (
    load_env_config,
    load_persona_config,
    load_urls,
    validate_tasks_against_urls,
)


def test_load_env_config_success(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "LLM_BASE_URL=https://api.openai.com/v1",
                "LLM_API_KEY=abc",
                "LLM_MODEL=gpt-test",
                "PROXY_API_URL=https://proxy.test/api",
                "PROXY_API_AUTH_HEADER=Authorization: Bearer x",
                "PROXY_API_RESULT_PATH=data.proxies",
                'PROXY_API_ITEM_SCHEMA={"host":"ip","port":"port","protocol":"scheme","username":"u","password":"p"}',
            ]
        ),
        encoding="utf-8",
    )
    cfg = load_env_config(env_file)
    assert cfg.llm_model == "gpt-test"
    assert cfg.action_delay_min_ms == 800


def test_load_env_config_missing_key(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("LLM_BASE_URL=https://api.openai.com/v1\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_env_config(env_file)


def test_validate_tasks_against_urls(tmp_path: Path) -> None:
    urls_file = tmp_path / "网址.txt"
    urls_file.write_text("https://a.example.com/form\n", encoding="utf-8")
    persona_file = tmp_path / "人格配置.json"
    persona_file.write_text(
        json.dumps(
            {
                "personas": [
                    {"id": "p1", "description": "desc", "weight": 1, "style": "style"}
                ],
                "tasks": [
                    {
                        "url": "https://a.example.com/form",
                        "submit_count": 1,
                        "mapping_file": "mappings/a.json",
                        "persona_mix": {"p1": 1},
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    urls = load_urls(urls_file)
    persona_cfg = load_persona_config(persona_file)
    validate_tasks_against_urls(persona_cfg, urls)

