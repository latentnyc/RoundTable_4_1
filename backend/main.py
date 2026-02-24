import os
from app.logging_config import logger

from app.config import settings
logger.info("Configuration loaded")

from fastapi import FastAPI, Depends
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

fastapi_app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION)
logger.warning("FastAPI app initialized")

# Import Routers
from app.routers import game, auth, characters, settings as settings_router, items, compendium, campaigns, users, chat
logger.info("Routers imported")

from app.socket_manager import sio
import socketio
from db.init_db import init_db_async
from app.firebase_config import init_firebase
from app.auth_utils import verify_token
# Import data loader service
from app.services.data_loader import load_basic_dataset, is_dataset_loaded
from app.services.campaign_loader import parse_and_load
from db.session import AsyncSessionLocal
from sqlalchemy import text  # Moved up for cleaner imports

# ...
@fastapi_app.on_event("startup")
async def startup_event():
    try:
        await init_db_async()

        # Database initialized via Alembic and init_db
        logger.info("Database schema verified.")

        init_firebase()
        logger.info("Firebase initialized successfully.")

        # Automatic Data Load Check
        logger.info("Checking if dataset is loaded...")
        async with AsyncSessionLocal() as db:
            if not await is_dataset_loaded(db):
                logger.info("Dataset not found. Loading basic dataset...")
                await load_basic_dataset()
            else:
                logger.info("Dataset already loaded.")

        # Sync Campaign Templates
        logger.info("Syncing campaign templates...")
        await parse_and_load()
        logger.info("Campaign templates synced.")

    except Exception as e:
        logger.critical(f"Database initialization failed: {e}")
        # Raise exception to crash the container so Cloud Run knows it failed
        raise e

    # Register Commands
    from app.services.command_service import CommandService
    CommandService.register_commands()

# 2. Include Routers
fastapi_app.include_router(game.router, dependencies=[Depends(verify_token)])
fastapi_app.include_router(auth.router)
fastapi_app.include_router(campaigns.router, prefix="/campaigns", dependencies=[Depends(verify_token)])
fastapi_app.include_router(characters.router, dependencies=[Depends(verify_token)])
fastapi_app.include_router(items.router, dependencies=[Depends(verify_token)])
fastapi_app.include_router(compendium.router, dependencies=[Depends(verify_token)])
fastapi_app.include_router(settings_router.router, prefix="/api/settings", dependencies=[Depends(verify_token)])
fastapi_app.include_router(users.router, dependencies=[Depends(verify_token)])
fastapi_app.include_router(chat.router, prefix="/chat", dependencies=[Depends(verify_token)])

@fastapi_app.get("/")
async def health_check():
    return {
        "status": "online",
        "service": "RoundTable 4.1 Orchestrator",
        "version": "0.1.0"
    }

# 3. Middleware Configuration

# CORS Configured via settings
logger.info(f"CORS Configured. Allowed Origins: {settings.ALLOWED_ORIGINS}")

# Custom Logging Middleware
class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin")
        # logger.debug(f"Incoming Request: {request.method} {request.url.path} | Origin: {origin}")
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            logger.error(f"Error processing request: {e}")
            raise e

# Add Middleware
fastapi_app.add_middleware(LoggingMiddleware)

from fastapi.middleware.cors import CORSMiddleware

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@fastapi_app.get("/debug/config")
async def debug_config():
    async with AsyncSessionLocal() as db:
        try:
            spells = (await db.execute(text("SELECT COUNT(*) FROM spells"))).scalar()
            monsters = (await db.execute(text("SELECT COUNT(*) FROM monsters"))).scalar()
            camp_res = (await db.execute(text("SELECT api_key FROM campaigns LIMIT 1"))).fetchone()
            has_key = bool(camp_res and camp_res[0])

            return {
                "spells_count": spells,
                "monsters_count": monsters,
                "has_campaign_key": has_key,
                "backend_version": "v1.3 (Agent Fix + DM Check + Debug)"
            }
        except Exception as e:
            return {"error": str(e)}

# 5. Wrap with SocketIO (Final Step)
# This creates the ASGI app that Uvicorn will actually run.
# It wraps the fully-configured FastAPI app.
app = socketio.ASGIApp(sio, fastapi_app)

# Removed uvicorn.run block as it is not needed for production deployment
