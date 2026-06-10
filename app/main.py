from fastapi import FastAPI

from app.config import get_settings
from app.db import get_latest_signals, init_db
from app.worker import run_once

settings = get_settings()
app = FastAPI(title=settings.app_name)


@app.on_event("startup")
def startup() -> None:
    init_db(settings.sqlite_path)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "environment": settings.environment, "market_mode": settings.market_mode}


@app.get("/signals/latest")
def latest_signals(limit: int = 20) -> list[dict]:
    return get_latest_signals(settings.sqlite_path, limit=limit)


@app.post("/scan-now")
async def scan_now() -> dict:
    candidate = await run_once(settings, send_alert=False)
    if candidate is None:
        return {"selected": None}
    return {"selected": candidate.to_dict()}
