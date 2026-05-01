# =============================================================================
# FFIA — api/main.py
# FastAPI application entry point.
# Must mock streamlit BEFORE importing any app.* or data.* modules
# because app/utils/auth.py and data/db.py transitively import streamlit.
# =============================================================================

# Step 1: Streamlit mock — prevents ImportError when data/db.py loads app/utils/auth.py
import os
import sys
import logging
from types import ModuleType
from pathlib import Path

_st = ModuleType("streamlit")
_st.cache_resource = lambda fn=None, **kw: (fn if callable(fn) else lambda f: f)
_st.cache_data = lambda fn=None, ttl=None, **kw: (fn if callable(fn) else lambda f: f)
sys.modules.setdefault("streamlit", _st)

# Step 2: Add project root to sys.path so agent.*, app.*, data.* imports resolve
sys.path.insert(0, str(Path(__file__).parent.parent))

# Step 3: FastAPI imports
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Step 4: Router imports
from api.routes import chat as sandbox_chat
from api.routes import business_setup as sandbox_business_setup
from api.routes import dashboard as sandbox_dashboard
from api.routes import demo_users as sandbox_demo_users
from api.routes import health as sandbox_health
from api.routes import invoices as sandbox_invoices
from api.routes import login as sandbox_login

logger = logging.getLogger(__name__)

try:
    from api.routers import auth, dashboard, upload, profile, chat
except ModuleNotFoundError as exc:
    auth = dashboard = upload = profile = chat = None
    logger.warning("Legacy authenticated routers disabled: %s", exc)

# Step 5: App setup
app = FastAPI(
    title="FFIA API",
    description="FastAPI backend for FFIA — Fuel & Food Impact Analyzer",
    version="1.0.0",
)

# Step 6: CORS — allow Next.js dev server and production origin
default_cors_origins = ",".join([
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://192.168.1.106:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
])

cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", default_cors_origins).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Step 7: Register routers
app.include_router(sandbox_health.router, tags=["sandbox"])
app.include_router(sandbox_demo_users.router, tags=["sandbox"])
app.include_router(sandbox_login.router, tags=["sandbox"])
app.include_router(sandbox_chat.router, tags=["sandbox"])
app.include_router(sandbox_dashboard.router, tags=["sandbox"])
app.include_router(sandbox_business_setup.router, tags=["sandbox"])
app.include_router(sandbox_invoices.router,       tags=["sandbox"])

if auth and dashboard and upload and profile and chat:
    app.include_router(auth.router,      prefix="/auth",      tags=["auth"])
    app.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
    app.include_router(upload.router,    prefix="/upload",    tags=["upload"])
    app.include_router(profile.router,   prefix="/profile",   tags=["profile"])
    app.include_router(chat.router,      prefix="/chat",      tags=["chat"])
