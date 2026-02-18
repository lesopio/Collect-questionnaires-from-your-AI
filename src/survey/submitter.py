from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Any

from src.survey.mapper import MappingExecutionError, MapperExecutor
from src.utils.human_gate import wait_for_manual_intervention


CAPTCHA_SELECTORS = (
    ".captcha",
    "#captcha",
    "iframe[src*='captcha']",
    "input[name*='captcha']",
)

SUBMIT_SELECTORS = (
    "button[type='submit']",
    "input[type='submit']",
    "#submit_button",
    "#ctlNext",
    ".submit-btn",
)


def fill_and_submit(
    page,
    mapped_questions: list[dict[str, Any]],
    answer_map: dict[str, Any],
    screenshot_dir: Path,
    run_id: str,
    delay_ms_range: tuple[int, int],
    human_gate_timeout_sec: int = 300,
) -> dict[str, Any]:
    executor = MapperExecutor()
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    for question in mapped_questions:
        qid = str(question.get("qid"))
        answer = answer_map.get(qid)
        if answer is None:
            continue
        try:
            executor.apply_answer(page, question, answer)
        except Exception as exc:
            raise MappingExecutionError(f"Failed answering {qid}: {exc}") from exc
        _sleep_by_profile(delay_ms_range)
        if _has_captcha(page):
            captcha_path = screenshot_dir / f"{run_id}_captcha.png"
            page.screenshot(path=str(captcha_path), full_page=True)
            approved = wait_for_manual_intervention(
                reason=f"检测到验证码，请人工处理后继续。截图: {captcha_path}",
                timeout_sec=human_gate_timeout_sec,
            )
            if not approved:
                return {"status": "needs_manual", "detail": "captcha_timeout"}
    before_submit = screenshot_dir / f"{run_id}_before_submit.png"
    page.screenshot(path=str(before_submit), full_page=True)
    submitted = _click_submit(page)
    if not submitted:
        return {"status": "failed", "detail": "submit_button_not_found"}
    _sleep_by_profile(delay_ms_range)
    after_submit = screenshot_dir / f"{run_id}_after_submit.png"
    page.screenshot(path=str(after_submit), full_page=True)
    if _is_submit_success(page):
        return {"status": "success", "detail": "submitted"}
    return {"status": "failed", "detail": "submit_not_confirmed"}


def _sleep_by_profile(delay_ms_range: tuple[int, int]) -> None:
    min_ms, max_ms = delay_ms_range
    wait_ms = random.randint(min_ms, max_ms)
    time.sleep(wait_ms / 1000.0)


def _has_captcha(page) -> bool:
    for selector in CAPTCHA_SELECTORS:
        if page.locator(selector).count() > 0:
            return True
    return False


def _click_submit(page) -> bool:
    for selector in SUBMIT_SELECTORS:
        loc = page.locator(selector)
        if loc.count() > 0:
            loc.first.click()
            return True
    return False


def _is_submit_success(page) -> bool:
    keywords = ("提交成功", "感谢", "谢谢", "已完成", "success")
    body = page.inner_text("body")[:3000].lower()
    return any(k.lower() in body for k in keywords)
