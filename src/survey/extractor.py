from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


QUESTION_CONTAINER_SELECTORS = (
    ".field",
    ".question",
    ".survey-question",
    "[data-question-id]",
)


def extract_questions(page) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    containers = None
    for selector in QUESTION_CONTAINER_SELECTORS:
        loc = page.locator(selector)
        if loc.count() > 0:
            containers = loc
            break
    if containers is None:
        return []
    count = min(containers.count(), 200)
    for idx in range(count):
        container = containers.nth(idx)
        text = _extract_question_text(container, idx)
        qid = container.get_attribute("id") or f"q{idx + 1}"
        q_type = _detect_type(container)
        options = _extract_options(container)
        required = _detect_required(container, text)
        questions.append(
            {
                "qid": qid,
                "text": text,
                "type": q_type,
                "options": options,
                "constraints": {
                    "required": required,
                    "max_select": 1 if q_type == "single_choice" else len(options),
                },
                "locator": {
                    "anchor_text": text[:120],
                    "fallback_selector": "",
                },
            }
        )
    return questions


def build_mapping_template(url: str, platform: str, questions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "meta": {
            "url": url,
            "platform": platform,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "version": 1,
        },
        "questions": questions,
    }


def _extract_question_text(container, idx: int) -> str:
    for selector in (
        ".field-label",
        ".title",
        ".topic",
        "legend",
        ".question-title",
    ):
        loc = container.locator(selector)
        if loc.count() > 0:
            value = " ".join(loc.first.inner_text().split())
            if value:
                return value
    value = " ".join(container.inner_text().split())
    return value[:160] if value else f"Question {idx + 1}"


def _detect_type(container) -> str:
    if container.locator("input[type='radio']").count() > 0:
        return "single_choice"
    if container.locator("input[type='checkbox']").count() > 0:
        return "multi_choice"
    if container.locator("textarea").count() > 0:
        return "text"
    if container.locator("select").count() > 0:
        return "single_choice"
    if container.locator(".star, .rating, [role='slider']").count() > 0:
        return "rating"
    if container.locator("input[type='text']").count() > 0:
        return "text"
    return "unknown"


def _extract_options(container) -> list[str]:
    options: list[str] = []
    for selector in ("label", ".option", "li"):
        loc = container.locator(selector)
        count = min(loc.count(), 25)
        for i in range(count):
            text = " ".join(loc.nth(i).inner_text().split())
            if text and text not in options:
                options.append(text[:100])
    return options


def _detect_required(container, text: str) -> bool:
    class_name = (container.get_attribute("class") or "").lower()
    if "required" in class_name or "must" in class_name or "req" in class_name:
        return True
    return "*" in text

