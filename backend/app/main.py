"""CampusFlow FastAPI application entry point.

Sets up CORS, lifespan (DB init + scheduler), health endpoint, and router mounting.
"""

import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv(override=True)  # Ensure env vars are available in reloaded worker

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(name)s - %(message)s")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx

from app.database import init_db
from app.scheduler import start_scheduler, stop_scheduler
from app.startup import run_startup_orchestrator, shutdown_ngrok
from app.routers import profile, notices, tasks, digest, webhooks, academic, chat, vtop_proxy

# Import models to ensure they are registered with SQLModel metadata before init_db runs
import app.models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize database, start scheduler, and run startup orchestration."""
    await init_db()
    start_scheduler()
    await run_startup_orchestrator()
    yield
    stop_scheduler()
    shutdown_ngrok()


app = FastAPI(title="CampusFlow", lifespan=lifespan)

# CORS - allow all origins for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/api/status")
async def service_status():
    """Return status of all connected services (ngrok, WhatsApp, VTOP)."""
    from app.startup import get_ngrok_url, EVOLUTION_BASE, EVOLUTION_API_KEY, INSTANCE_NAME
    from app.connectors.vtop.session_store import SessionStore

    status = {
        "ngrok": {"active": False, "url": None},
        "whatsapp": {"connected": False, "state": "unknown"},
        "vtop": {"session_valid": False},
    }

    # ngrok
    ngrok_url = get_ngrok_url()
    if ngrok_url:
        status["ngrok"] = {"active": True, "url": ngrok_url}

    # WhatsApp
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(
                f"{EVOLUTION_BASE}/instance/connectionState/{INSTANCE_NAME}",
                headers={"apikey": EVOLUTION_API_KEY},
            )
            if r.status_code == 200:
                data = r.json()
                state = data.get("instance", data).get("state", "unknown")
                status["whatsapp"] = {"connected": state == "open", "state": state}
    except Exception:
        pass

    # VTOP session - use DB-based SessionStore
    session_store = SessionStore()
    active_session = await session_store.get_active_session()
    status["vtop"]["session_valid"] = active_session is not None

    return status


# Routers
app.include_router(profile.router, prefix="/api")
app.include_router(notices.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(digest.router, prefix="/api")
app.include_router(webhooks.router, prefix="/api")
app.include_router(academic.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(vtop_proxy.router)
