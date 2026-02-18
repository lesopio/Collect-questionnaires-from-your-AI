from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import gradio as gr
from dotenv import dotenv_values


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
FRONTEND_ENV_PATH = BASE_DIR / ".env"

_SCHEDULE_PROCESS: subprocess.Popen | None = None


def _load_frontend_env() -> dict[str, str]:
    if FRONTEND_ENV_PATH.exists():
        return {k: v for k, v in dotenv_values(FRONTEND_ENV_PATH).items() if v is not None}
    return {}


FRONTEND_ENV = _load_frontend_env()
CLI_TIMEOUT_SEC = int(FRONTEND_ENV.get("CLI_TIMEOUT_SEC", "1800"))
DEFAULT_HOST = FRONTEND_ENV.get("FRONTEND_HOST", "127.0.0.1")
DEFAULT_PORT = int(FRONTEND_ENV.get("FRONTEND_PORT", "7860"))
DEFAULT_SHARE = FRONTEND_ENV.get("FRONTEND_SHARE", "false").lower() in {"1", "true", "yes", "on"}
DEFAULT_THEME = FRONTEND_ENV.get("FRONTEND_THEME", "soft")


def _run_cli(command: list[str], timeout_sec: int | None = None) -> str:
    cmd = [sys.executable, "-m", "src.main", *command]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec or CLI_TIMEOUT_SEC,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return f"[timeout]\nCommand: {' '.join(cmd)}\n{exc}"
    output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
    return f"[exit_code={result.returncode}]\nCommand: {' '.join(cmd)}\n\n{output}".strip()


def run_doctor(env_file: str, url_file: str, persona_file: str) -> str:
    return _run_cli(
        [
            "doctor",
            "--env-file",
            env_file.strip(),
            "--url-file",
            url_file.strip(),
            "--persona-file",
            persona_file.strip(),
        ]
    )


def run_scan(env_file: str, url_file: str) -> str:
    return _run_cli(
        [
            "scan",
            "--env-file",
            env_file.strip(),
            "--url-file",
            url_file.strip(),
        ]
    )


def run_fill(env_file: str, url_file: str, persona_file: str) -> str:
    return _run_cli(
        [
            "run",
            "--env-file",
            env_file.strip(),
            "--url-file",
            url_file.strip(),
            "--persona-file",
            persona_file.strip(),
        ]
    )


def start_schedule(env_file: str, url_file: str, persona_file: str, cron: str) -> str:
    global _SCHEDULE_PROCESS
    if _SCHEDULE_PROCESS is not None and _SCHEDULE_PROCESS.poll() is None:
        return f"定时任务已在运行。PID={_SCHEDULE_PROCESS.pid}"
    cmd = [
        sys.executable,
        "-m",
        "src.main",
        "schedule",
        "--cron",
        cron.strip(),
        "--env-file",
        env_file.strip(),
        "--url-file",
        url_file.strip(),
        "--persona-file",
        persona_file.strip(),
    ]
    _SCHEDULE_PROCESS = subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return f"定时任务已启动。PID={_SCHEDULE_PROCESS.pid}\n命令: {' '.join(cmd)}"


def stop_schedule() -> str:
    global _SCHEDULE_PROCESS
    if _SCHEDULE_PROCESS is None or _SCHEDULE_PROCESS.poll() is not None:
        return "当前没有运行中的定时任务进程。"
    _SCHEDULE_PROCESS.terminate()
    try:
        _SCHEDULE_PROCESS.wait(timeout=5)
    except subprocess.TimeoutExpired:
        _SCHEDULE_PROCESS.kill()
    pid = _SCHEDULE_PROCESS.pid
    _SCHEDULE_PROCESS = None
    return f"定时任务已停止。PID={pid}"


def schedule_status() -> str:
    if _SCHEDULE_PROCESS is None:
        return "定时任务状态：未启动。"
    code = _SCHEDULE_PROCESS.poll()
    if code is None:
        return f"定时任务状态：运行中（PID={_SCHEDULE_PROCESS.pid}）。"
    return f"定时任务状态：已退出（PID={_SCHEDULE_PROCESS.pid}，code={code}）。"


def _default_path(filename: str) -> str:
    return str(PROJECT_ROOT / filename)


with gr.Blocks(title="问卷自动填写前端", theme=DEFAULT_THEME) as app:
    gr.Markdown(
        """
# 问卷自动填写前端（Gradio）

仅用于已授权问卷。该页面调用项目根目录现有 CLI：
`doctor` / `scan` / `run` / `schedule`.
"""
    )

    with gr.Row():
        env_file = gr.Textbox(label="环境配置文件（.env）", value=_default_path(".env"))
        url_file = gr.Textbox(label="问卷网址文件", value=_default_path("\u7f51\u5740.txt"))
        persona_file = gr.Textbox(label="人格配置文件", value=_default_path("\u4eba\u683c\u914d\u7f6e.json"))

    cron_expr = gr.Textbox(label="Cron 表达式", value="*/30 * * * *")

    with gr.Row():
        doctor_btn = gr.Button("运行 Doctor 预检", variant="primary")
        scan_btn = gr.Button("运行 Scan 生成模板")
        run_btn = gr.Button("运行 Run 开始填写")

    with gr.Row():
        schedule_start_btn = gr.Button("启动定时任务")
        schedule_stop_btn = gr.Button("停止定时任务")
        schedule_status_btn = gr.Button("查看定时任务状态")

    output = gr.Textbox(label="输出日志", lines=24, max_lines=36)

    doctor_btn.click(
        run_doctor,
        inputs=[env_file, url_file, persona_file],
        outputs=output,
    )
    scan_btn.click(
        run_scan,
        inputs=[env_file, url_file],
        outputs=output,
    )
    run_btn.click(
        run_fill,
        inputs=[env_file, url_file, persona_file],
        outputs=output,
    )
    schedule_start_btn.click(
        start_schedule,
        inputs=[env_file, url_file, persona_file, cron_expr],
        outputs=output,
    )
    schedule_stop_btn.click(stop_schedule, outputs=output)
    schedule_status_btn.click(schedule_status, outputs=output)


if __name__ == "__main__":
    app.launch(
        server_name=DEFAULT_HOST,
        server_port=DEFAULT_PORT,
        share=DEFAULT_SHARE,
    )
