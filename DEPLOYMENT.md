# Deployment Notes

This project can run locally or on a small VM. Do not upload local secrets or runtime state by accident.

## Do Not Upload

- `.env`
- `.venv/`
- `data/kis_token*.json`
- `data/signals.db`
- `logs/`
- `__pycache__/`
- `.pytest_cache/`

These are already covered by `.gitignore`.

## Upload Or Commit

- `app/`
- `scripts/`
- `tests/`
- `.env.example`
- `.gitignore`
- `README.md`
- `DEPLOYMENT.md`
- `requirements.txt`

## Server Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Then edit `.env` on the server and run:

```powershell
python -m app.tools.kis_auth_check
python -m app.tools.ai_check
python -m app.tools.scan_once
```

## Local Background Worker

```powershell
.\scripts\start_worker_bg.ps1
.\scripts\worker_status.ps1
.\scripts\stop_worker.ps1
```

## Pre-Deploy Check

```powershell
python -m app.tools.deploy_check
python -m app.tools.security_check
```
