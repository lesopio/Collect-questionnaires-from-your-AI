from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

import requests
import typer

from src.browser_session import BrowserSession
from src.config import (
    EnvConfig,
    Persona,
    PersonaConfig,
    TaskConfig,
    load_env_config,
    load_persona_config,
    load_urls,
    slugify_url,
    validate_tasks_against_urls,
)
from src.llm_client import OpenAICompatibleClient
from src.proxy_provider import ProxyProvider
from src.scheduler import run_scheduler
from src.survey.answer_planner import plan_answers
from src.survey.detector import detect_platform
from src.survey.extractor import build_mapping_template, extract_questions
from src.survey.mapper import load_mapping, map_questions
from src.survey.submitter import fill_and_submit
from src.utils.logging import JsonlLogger, ensure_runtime_dirs, get_daily_log_path, new_run_id
from src.utils.retry import retry_call


app = typer.Typer(help="授权问卷自动填写工具")


@app.command()
def doctor(
    env_file: str = ".env",
    url_file: str = "网址.txt",
    persona_file: str = "人格配置.json",
) -> None:
    ensure_runtime_dirs()
    errors: list[str] = []
    env: EnvConfig | None = None
    urls: list[str] = []
    persona_cfg: PersonaConfig | None = None

    try:
        env = load_env_config(env_file)
        print("[ok] .env loaded")
    except Exception as exc:
        errors.append(f".env check failed: {exc}")

    try:
        urls = load_urls(url_file)
        print(f"[ok] URL file loaded, count={len(urls)}")
    except Exception as exc:
        errors.append(f"URL file check failed: {exc}")

    try:
        persona_cfg = load_persona_config(persona_file)
        print(f"[ok] persona config loaded, tasks={len(persona_cfg.tasks)}")
    except Exception as exc:
        errors.append(f"persona config check failed: {exc}")

    if persona_cfg and urls:
        try:
            validate_tasks_against_urls(persona_cfg, urls)
            print("[ok] task URLs align with 网址.txt")
        except Exception as exc:
            errors.append(str(exc))

    if persona_cfg:
        for task in persona_cfg.tasks:
            mapping_path = Path(task.mapping_file)
            if not mapping_path.exists():
                errors.append(f"Missing mapping file: {mapping_path}")

    if env:
        try:
            provider = ProxyProvider(env)
            proxies = provider.fetch_proxies()
            if not proxies:
                errors.append("Proxy API returned 0 proxies.")
            else:
                print(f"[ok] proxy API returned {len(proxies)} items")
            healthy = provider.get_healthy_proxies()
            if not healthy:
                errors.append("No healthy proxy found from API.")
            else:
                print(f"[ok] healthy proxies={len(healthy)}")
        except Exception as exc:
            errors.append(f"proxy check failed: {exc}")

    for url in urls:
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code >= 400:
                errors.append(f"URL unreachable({resp.status_code}): {url}")
        except Exception as exc:
            errors.append(f"URL unreachable: {url} ({exc})")

    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        print("[ok] playwright importable")
    except Exception as exc:
        errors.append(f"playwright not ready: {exc}")

    if errors:
        print("[doctor] failed checks:")
        for e in errors:
            print(f"- {e}")
        raise typer.Exit(code=1)
    print("[doctor] all checks passed")


@app.command()
def scan(
    env_file: str = ".env",
    url_file: str = "网址.txt",
) -> None:
    ensure_runtime_dirs()
    env = load_env_config(env_file)
    urls = load_urls(url_file)
    provider = ProxyProvider(env)
    healthy = provider.get_healthy_proxies()
    if not healthy:
        raise typer.BadParameter("No healthy proxies available. Please check proxy API.")
    rotator = provider.build_rotator(healthy)
    generated = 0
    for url in urls:
        proxy = next(rotator)
        with BrowserSession(env, proxy=proxy) as session:
            page = session.open_page(url)
            questions = extract_questions(page)
            platform = detect_platform(url)
            template = build_mapping_template(url, platform, questions)
            output = Path("mappings") / f"{slugify_url(url)}.template.json"
            output.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
            generated += 1
            print(f"[scan] generated {output} ({len(questions)} questions)")
    print(f"[scan] done, files={generated}")


@app.command()
def run(
    env_file: str = ".env",
    url_file: str = "网址.txt",
    persona_file: str = "人格配置.json",
) -> None:
    logger = JsonlLogger(get_daily_log_path())
    _run_once(env_file=env_file, url_file=url_file, persona_file=persona_file, logger=logger)


@app.command()
def schedule(
    cron: str = typer.Option(..., "--cron", help="crontab expression, e.g. '*/30 * * * *'"),
    env_file: str = ".env",
    url_file: str = "网址.txt",
    persona_file: str = "人格配置.json",
) -> None:
    ensure_runtime_dirs()
    logger = JsonlLogger(get_daily_log_path())
    run_scheduler(
        cron_expr=cron,
        job=lambda: _run_once(
            env_file=env_file,
            url_file=url_file,
            persona_file=persona_file,
            logger=logger,
        ),
    )


def _run_once(
    env_file: str,
    url_file: str,
    persona_file: str,
    logger: JsonlLogger,
) -> None:
    ensure_runtime_dirs()
    env = load_env_config(env_file)
    urls = load_urls(url_file)
    persona_cfg = load_persona_config(persona_file)
    validate_tasks_against_urls(persona_cfg, urls)
    provider = ProxyProvider(env)
    healthy = provider.get_healthy_proxies()
    if not healthy:
        raise RuntimeError("No healthy proxies available.")
    proxy_rotator = provider.build_rotator(healthy)
    llm_client = OpenAICompatibleClient(env)
    for task in persona_cfg.tasks:
        mapping = load_mapping(task.mapping_file)
        for idx in range(task.submit_count):
            run_id = new_run_id()
            proxy = next(proxy_rotator)
            persona = _pick_persona(persona_cfg, task)
            screenshot_dir = Path("data/screenshots") / run_id
            payload = {
                "run_id": run_id,
                "url": task.url,
                "task_submit_index": idx + 1,
                "proxy": proxy.proxy_url,
                "persona_id": persona.persona_id,
            }
            try:
                result = retry_call(
                    lambda: _execute_single_submission(
                        env=env,
                        task=task,
                        mapping=mapping,
                        persona=persona,
                        llm_client=llm_client,
                        proxy=proxy,
                        screenshot_dir=screenshot_dir,
                        run_id=run_id,
                    ),
                    retries=env.submit_retry_per_task,
                )
                payload.update(result)
                logger.log("submission_result", payload)
                print(
                    f"[run] {task.url} #{idx + 1}/{task.submit_count} -> {result.get('status')}"
                )
            except Exception as exc:
                payload.update({"status": "failed", "detail": str(exc)})
                logger.log("submission_result", payload)
                print(
                    f"[run] {task.url} #{idx + 1}/{task.submit_count} -> failed ({exc})"
                )


def _execute_single_submission(
    env: EnvConfig,
    task: TaskConfig,
    mapping: dict[str, Any],
    persona: Persona,
    llm_client: OpenAICompatibleClient,
    proxy,
    screenshot_dir: Path,
    run_id: str,
) -> dict[str, Any]:
    with BrowserSession(env=env, proxy=proxy) as session:
        page = session.open_page(task.url)
        extracted = extract_questions(page)
        mapped = map_questions(extracted, mapping)
        answers = plan_answers(
            questions=mapped,
            persona=persona,
            llm_client=llm_client,
            llm_retries=2,
        )
        result = fill_and_submit(
            page=page,
            mapped_questions=mapped,
            answer_map=answers,
            screenshot_dir=screenshot_dir,
            run_id=run_id,
            delay_ms_range=(env.action_delay_min_ms, env.action_delay_max_ms),
            human_gate_timeout_sec=300,
        )
        if result.get("status") == "failed":
            raise RuntimeError(result.get("detail", "submission_failed"))
        return result


def _pick_persona(persona_cfg: PersonaConfig, task: TaskConfig) -> Persona:
    persona_by_id = persona_cfg.persona_index
    ids = list(task.persona_mix.keys())
    weights = [task.persona_mix[i] for i in ids]
    selected_id = random.choices(ids, weights=weights, k=1)[0]
    return persona_by_id[selected_id]


if __name__ == "__main__":
    app()

