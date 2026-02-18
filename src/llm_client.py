from __future__ import annotations

import json
import re
from typing import Any

import requests

from src.config import EnvConfig, Persona


class LLMClientError(RuntimeError):
    pass


class OpenAICompatibleClient:
    def __init__(self, env: EnvConfig, session: requests.Session | None = None):
        self.base_url = env.llm_base_url.rstrip("/")
        self.api_key = env.llm_api_key
        self.model = env.llm_model
        self.timeout_sec = env.llm_timeout_sec
        self.session = session or requests.Session()

    def generate_answer_map(
        self,
        persona: Persona,
        questions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        system_prompt = (
            "你是问卷助手。必须返回严格 JSON 对象，key 是 qid，value 是答案。"
            "不要输出额外解释。"
        )
        user_prompt = json.dumps(
            {
                "persona": {
                    "id": persona.persona_id,
                    "description": persona.description,
                    "style": persona.style,
                },
                "questions": questions,
                "format": {"qid": "answer"},
            },
            ensure_ascii=False,
        )
        response = self.session.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "temperature": 0.7,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
            timeout=self.timeout_sec,
        )
        if response.status_code >= 400:
            raise LLMClientError(
                f"LLM request failed: status={response.status_code} body={response.text[:300]}"
            )
        payload = response.json()
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMClientError("LLM response format is invalid.") from exc
        parsed = _parse_json_from_text(content)
        if not isinstance(parsed, dict):
            raise LLMClientError("LLM output is not a JSON object.")
        return parsed


def _parse_json_from_text(text: str) -> Any:
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return json.loads(stripped)
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", stripped, re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))
    # Last fallback: first JSON object in string.
    first = stripped.find("{")
    last = stripped.rfind("}")
    if first >= 0 and last > first:
        return json.loads(stripped[first : last + 1])
    raise LLMClientError("No JSON object found in LLM content.")

