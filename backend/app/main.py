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

from app.database import init_db
from app.scheduler import start_scheduler, stop_scheduler
from app.routers import profile, notices, tasks, digest, webhooks, academic

# Import models to ensure they are registered with SQLModel metadata before init_db runs
import app.models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize database tables and start scheduler on startup."""
    await init_db()
    start_scheduler()
    yield
    stop_scheduler()


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


# Routers
app.include_router(profile.router, prefix="/api")
app.include_router(notices.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(digest.router, prefix="/api")
app.include_router(webhooks.router, prefix="/api")
app.include_router(academic.router, prefix="/api")
