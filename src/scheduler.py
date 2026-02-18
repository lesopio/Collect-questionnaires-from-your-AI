from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger


def run_scheduler(
    cron_expr: str,
    job: Callable[[], None],
    state_file: Path = Path("data/state/schedule_state.json"),
) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    scheduler = BlockingScheduler()
    running = {"active": False}

    def wrapped() -> None:
        if running["active"]:
            _write_state(state_file, {"status": "skipped_overlap"})
            return
        running["active"] = True
        _write_state(state_file, {"status": "started"})
        try:
            job()
            _write_state(state_file, {"status": "completed"})
        except Exception as exc:
            _write_state(state_file, {"status": "failed", "error": str(exc)})
            raise
        finally:
            running["active"] = False

    trigger = CronTrigger.from_crontab(cron_expr)
    scheduler.add_job(
        wrapped,
        trigger=trigger,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
    )
    print(f"[scheduler] started with cron='{cron_expr}'")
    scheduler.start()


def _write_state(path: Path, payload: dict) -> None:
    body = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")

