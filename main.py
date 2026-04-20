from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
import logging

# Instantly load variables from .env file securely into memory
load_dotenv()

# Ensure absolute imports work correctly in our structure
from routes.api import router as api_router
from routes.ws import router as ws_router
from routes.history import router as history_router

# --- Basic Logging System ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("aura.main")

# --- FastAPI App Setup ---
app = FastAPI(title="AURA Backend", version="2.0.0")

# Enable CORS for the future React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Module Registration ---
# Mount the API router
app.include_router(api_router, prefix="/api")

# Mount the WebSocket router
app.include_router(ws_router, prefix="/ws")

# Mount the Chat History router
app.include_router(history_router, prefix="/api")


@app.on_event("startup")
async def startup_event():
    """Connect to MongoDB on FastAPI startup."""
    from core.chat_history import chat_history
    await chat_history.connect()
    # Auto-cleanup sessions older than 30 days on startup
    await chat_history.cleanup_old_sessions(days=30)
    logger.info("AURA Backend Initialization Complete.")


@app.on_event("shutdown")
async def shutdown_event():
    """Gracefully close MongoDB connection."""
    from core.chat_history import chat_history
    await chat_history.disconnect()
    logger.info("AURA Backend Shutdown Complete.")


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "AURA Modular Pipeline"}
