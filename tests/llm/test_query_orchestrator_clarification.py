from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.llm.query_orchestrator_impl.query_orchestrator_clarification import build_clarification_bundle


def test_build_clarification_bundle_limits_questions_and_choices() -> None:
    bundle = build_clarification_bundle(
        {
            "clarification": {
                "reason": "Need more detail.",
                "questions": [
                    {
                        "prompt": f"Q{i}",
                        "choices": [{"label": f"C{j}", "description": f"D{j}"} for j in range(7)],
                        "free_text_label": "Custom",
                    }
                    for i in range(7)
                ],
            }
        }
    )

    assert bundle is not None
    assert bundle.reason == "Need more detail."
    assert len(bundle.questions) == 5
    assert all(len(question.choices) == 5 for question in bundle.questions)
    assert all(question.free_text_label == "Custom" for question in bundle.questions)
