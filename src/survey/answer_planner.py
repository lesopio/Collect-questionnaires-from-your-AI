from __future__ import annotations

import random
from typing import Any

from src.config import Persona


def plan_answers(
    questions: list[dict[str, Any]],
    persona: Persona,
    llm_client=None,
    llm_retries: int = 2,
) -> dict[str, Any]:
    raw_answers: dict[str, Any] = {}
    if llm_client is not None:
        for _ in range(llm_retries + 1):
            try:
                raw_answers = llm_client.generate_answer_map(persona, questions)
                if isinstance(raw_answers, dict):
                    break
            except Exception:
                continue
    final_answers: dict[str, Any] = {}
    for question in questions:
        qid = str(question.get("qid"))
        chosen = raw_answers.get(qid)
        normalized = normalize_answer(question, chosen, persona)
        final_answers[qid] = normalized
    return final_answers


def normalize_answer(question: dict[str, Any], value: Any, persona: Persona) -> Any:
    q_type = question.get("type", "unknown")
    options = question.get("options") or []
    constraints = question.get("constraints") or {}
    if q_type == "single_choice":
        return _normalize_single(value, options)
    if q_type == "multi_choice":
        max_select = int(constraints.get("max_select", len(options) or 1))
        return _normalize_multi(value, options, max_select=max_select)
    if q_type == "rating":
        return _normalize_rating(value)
    if q_type == "text":
        return _normalize_text(value, persona)
    return _normalize_text(value, persona)


def _normalize_single(value: Any, options: list[str]) -> Any:
    if options:
        if isinstance(value, int):
            idx = value if value >= 0 else 0
            idx = min(idx, len(options) - 1)
            return options[idx]
        if isinstance(value, str):
            stripped = value.strip()
            if stripped in options:
                return stripped
            for option in options:
                if stripped and stripped in option:
                    return option
        return options[0]
    return str(value) if value is not None else ""


def _normalize_multi(value: Any, options: list[str], max_select: int) -> list[Any]:
    values = value if isinstance(value, list) else [value]
    resolved: list[Any] = []
    for item in values:
        if isinstance(item, int) and options:
            idx = max(0, min(item, len(options) - 1))
            selected = options[idx]
        elif isinstance(item, str) and options:
            selected = None
            for option in options:
                if item.strip() == option or item.strip() in option:
                    selected = option
                    break
            if selected is None:
                continue
        else:
            selected = item
        if selected and selected not in resolved:
            resolved.append(selected)
    if not resolved:
        if options:
            return options[: max(1, min(max_select, len(options)))]
        return []
    return resolved[: max(1, max_select)]


def _normalize_rating(value: Any) -> int:
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    if not isinstance(value, int):
        return 3
    return max(1, min(value, 5))


def _normalize_text(value: Any, persona: Persona) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()[:200]
    templates = [
        f"整体体验符合{persona.style}偏好，回答较为中性。",
        f"从{persona.description}角度看，本问卷内容清晰。",
        "题目理解成本较低，填写流畅。",
    ]
    return random.choice(templates)

