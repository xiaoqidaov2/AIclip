from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..clarification import ClarificationBundle, ClarificationChoice, ClarificationQuestion


def build_clarification_bundle(plan: Dict[str, Any]) -> Optional[ClarificationBundle]:
    raw = plan.get("clarification")
    if not isinstance(raw, dict):
        return None
    questions: List[ClarificationQuestion] = []
    for item in raw.get("questions", [])[:5]:
        if not isinstance(item, dict):
            continue
        prompt = str(item.get("prompt") or "").strip()
        if not prompt:
            continue
        choices: List[ClarificationChoice] = []
        for raw_choice in (item.get("choices") or [])[:5]:
            if isinstance(raw_choice, dict):
                label = str(raw_choice.get("label") or "").strip()
                description = str(raw_choice.get("description") or "").strip()
            else:
                label = str(raw_choice or "").strip()
                description = ""
            if label:
                choices.append(ClarificationChoice(label=label, description=description))
        questions.append(
            ClarificationQuestion(
                prompt=prompt,
                choices=choices,
                free_text_label=str(item.get("free_text_label") or "Other"),
            )
        )
    if not questions:
        return None
    return ClarificationBundle(
        reason=str(raw.get("reason") or "More input is required before editing."),
        questions=questions,
        metadata={"source": "llm_plan", "question_count": len(questions)},
    )
