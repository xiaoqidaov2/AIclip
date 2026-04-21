from __future__ import annotations

from dataclasses import fields
from datetime import datetime, timezone
from typing import Any, Dict


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def list_of_dicts(items: Any, cls: Any):
    if not items:
        return []
    return [cls.from_dict(item) if isinstance(item, dict) else item for item in items]


def filter_known_fields(cls: Any, data: Dict[str, Any]) -> Dict[str, Any]:
    allowed = {item.name for item in fields(cls)}
    return {key: value for key, value in data.items() if key in allowed}
