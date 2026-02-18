from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def ensure_runtime_dirs(root: Path = Path(".")) -> None:
    for relative in ("data/logs", "data/screenshots", "data/state", "mappings"):
        (root / relative).mkdir(parents=True, exist_ok=True)


def get_daily_log_path(root: Path = Path(".")) -> Path:
    now = datetime.now(timezone.utc)
    return root / "data" / "logs" / f"runs-{now:%Y%m%d}.jsonl"


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


class JsonlLogger:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, event_type: str, payload: dict[str, Any]) -> None:
        row = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            **payload,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

