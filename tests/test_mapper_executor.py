from __future__ import annotations

from src.survey.mapper import MapperExecutor


class FakePage:
    def __init__(self):
        self.calls = []

    def fill(self, selector, value):
        self.calls.append(("fill", selector, value))

    def check(self, selector):
        self.calls.append(("check", selector))

    def click(self, selector):
        self.calls.append(("click", selector))


def test_mapper_executor_apply_text_and_single_and_multi() -> None:
    executor = MapperExecutor()
    page = FakePage()
    executor.apply_answer(
        page,
        {
            "qid": "q1",
            "type": "text",
            "locator": {"fallback_selector": "#q1 input"},
        },
        "hello",
    )
    executor.apply_answer(
        page,
        {
            "qid": "q2",
            "type": "single_choice",
            "locator": {"fallback_selector": "#q2"},
        },
        "选项A",
    )
    executor.apply_answer(
        page,
        {
            "qid": "q3",
            "type": "multi_choice",
            "locator": {"fallback_selector": "#q3"},
        },
        ["选项1", "选项2"],
    )
    assert ("fill", "#q1 input", "hello") in page.calls
    assert ("click", "#q2 >> text=选项A") in page.calls
    assert ("click", "#q3 >> text=选项1") in page.calls
    assert ("click", "#q3 >> text=选项2") in page.calls

