from __future__ import annotations

from src.config import Persona
from src.survey.answer_planner import plan_answers


class FakeLLM:
    def generate_answer_map(self, persona, questions):
        return {
            "q1": "不存在选项",
            "q2": ["A", "B", "C"],
            "q3": 9,
            "q4": "",
        }


def test_plan_answers_normalizes_invalid_values() -> None:
    questions = [
        {"qid": "q1", "type": "single_choice", "options": ["A", "B"], "constraints": {}},
        {
            "qid": "q2",
            "type": "multi_choice",
            "options": ["A", "B", "C"],
            "constraints": {"max_select": 2},
        },
        {"qid": "q3", "type": "rating", "options": [], "constraints": {}},
        {"qid": "q4", "type": "text", "options": [], "constraints": {}},
    ]
    persona = Persona(
        persona_id="p1",
        description="desc",
        weight=1.0,
        style="理性",
    )
    answer_map = plan_answers(questions, persona, llm_client=FakeLLM())
    assert answer_map["q1"] == "A"
    assert answer_map["q2"] == ["A", "B"]
    assert answer_map["q3"] == 5
    assert isinstance(answer_map["q4"], str) and answer_map["q4"]

