<img width="2342" height="1267" alt="image" src="https://github.com/user-attachments/assets/5834177e-7800-4e6c-a54e-9f41f5dc1bb1" />
﻿# Frontend Version (Gradio)

This folder contains a simple web UI for the existing backend CLI.
It does not replace backend logic, it only wraps commands with buttons.

## Files

- `frontend_version/app.py`: single frontend script
- `frontend_version/.env`: frontend runtime config
- `frontend_version/README.md`: this guide

## What It Calls

The UI runs these commands from project root:

- `python -m src.main doctor`
- `python -m src.main scan`
- `python -m src.main run`
- `python -m src.main schedule --cron "..."`

## Start

1. Install Gradio in your project venv:

```bash
.\.venv\Scripts\python.exe -m pip install gradio
```

2. Launch frontend:

```bash
.\.venv\Scripts\python.exe frontend_version/app.py
```

3. Open browser:

```text
http://127.0.0.1:7860
```

## UI Inputs

- `Env File`: path to backend `.env` (default: root `.env`)
- `URL File`: path to the root URL list file
- `Persona File`: path to the root persona config JSON file
- `Cron`: schedule expression for `schedule`

## Frontend .env

- `FRONTEND_HOST=127.0.0.1`
- `FRONTEND_PORT=7860`
- `FRONTEND_SHARE=false`
- `FRONTEND_THEME=soft`
- `CLI_TIMEOUT_SEC=1800`

## Notes

- Keep using authorized questionnaire links only.
- If proxy health checks fail, `doctor` and `run` will show errors in output.
- `Start Schedule` launches one background scheduler process from this UI.

