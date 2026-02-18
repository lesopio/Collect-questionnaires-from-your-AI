from __future__ import annotations

import time


def wait_for_manual_intervention(reason: str, timeout_sec: int = 300) -> bool:
    print(f"[HUMAN_GATE] {reason}")
    print("[HUMAN_GATE] 处理完成后按 Enter 继续。")
    if timeout_sec <= 0:
        return False
    try:
        import msvcrt  # type: ignore
    except ImportError:
        input()
        return True
    start = time.time()
    while time.time() - start < timeout_sec:
        if msvcrt.kbhit():
            key = msvcrt.getwch()
            if key in {"\r", "\n"}:
                return True
        time.sleep(0.2)
    return False

