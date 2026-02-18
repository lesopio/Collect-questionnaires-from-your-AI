from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class MappingExecutionError(RuntimeError):
    pass


def load_mapping(mapping_file: Path | str) -> dict[str, Any]:
    path = Path(mapping_file)
    if not path.exists():
        raise ValueError(f"Missing mapping file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("Mapping must be a JSON object.")
    questions = payload.get("questions")
    if not isinstance(questions, list) or not questions:
        raise ValueError("Mapping questions must be a non-empty list.")
    return payload


def map_questions(
    extracted_questions: list[dict[str, Any]],
    mapping: dict[str, Any],
) -> list[dict[str, Any]]:
    extracted_by_id = {q.get("qid"): q for q in extracted_questions}
    mapped: list[dict[str, Any]] = []
    for m in mapping["questions"]:
        if not isinstance(m, dict):
            continue
        merged: dict[str, Any] = {}
        qid = m.get("qid")
        anchor_text = ((m.get("locator") or {}).get("anchor_text") or m.get("text") or "").strip()
        source = None
        if qid and qid in extracted_by_id:
            source = extracted_by_id[qid]
        elif anchor_text:
            source = _find_by_anchor(extracted_questions, anchor_text)
        if source:
            merged.update(source)
        merged.update(m)
        if "qid" not in merged:
            merged["qid"] = qid or f"mapped_{len(mapped) + 1}"
        mapped.append(merged)
    if not mapped:
        raise ValueError("No questions could be mapped from mapping file.")
    return mapped


class MapperExecutor:
    def apply_answer(self, page, question: dict[str, Any], answer: Any) -> None:
        q_type = question.get("type", "unknown")
        locator = question.get("locator") or {}
        selector = (locator.get("fallback_selector") or "").strip()
        if q_type == "text":
            self._answer_text(page, selector, answer)
            return
        if q_type == "single_choice":
            self._answer_single(page, selector, answer)
            return
        if q_type == "multi_choice":
            self._answer_multi(page, selector, answer)
            return
        if q_type == "rating":
            self._answer_rating(page, selector, answer)
            return
        raise MappingExecutionError(f"Unsupported question type: {q_type}")

    def _answer_text(self, page, selector: str, answer: Any) -> None:
        if not selector:
            selector = "textarea, input[type='text']"
        page.fill(selector, str(answer))

    def _answer_single(self, page, selector: str, answer: Any) -> None:
        if isinstance(answer, int):
            idx = max(0, answer)
            base = selector or "input[type='radio']"
            page.check(f"{base}:nth-of-type({idx + 1})")
            return
        option_text = str(answer)
        if selector:
            page.click(f"{selector} >> text={option_text}")
        else:
            page.click(f"text={option_text}")

    def _answer_multi(self, page, selector: str, answer: Any) -> None:
        values = answer if isinstance(answer, list) else [answer]
        for value in values:
            if isinstance(value, int):
                idx = max(0, value)
                base = selector or "input[type='checkbox']"
                page.check(f"{base}:nth-of-type({idx + 1})")
            else:
                option_text = str(value)
                if selector:
                    page.click(f"{selector} >> text={option_text}")
                else:
                    page.click(f"text={option_text}")

    def _answer_rating(self, page, selector: str, answer: Any) -> None:
        value = int(answer)
        if selector:
            page.click(f"{selector} [data-value='{value}'], {selector} .star:nth-child({value})")
        else:
            page.click(f"text={value}")


def _find_by_anchor(extracted_questions: list[dict[str, Any]], anchor: str) -> dict[str, Any] | None:
    low_anchor = anchor.lower()
    for q in extracted_questions:
        text = str(q.get("text", "")).lower()
        if low_anchor in text or text in low_anchor:
            return q
    return None

