import os
print("TRACE: os imported", flush=True)
from dotenv import load_dotenv
print("TRACE: dotenv imported", flush=True)
load_dotenv()
print("TRACE: Dotenv loaded", flush=True)

from fastapi import FastAPI, Depends
print("TRACE: FastAPI imported", flush=True)
from starlette.middleware.base import BaseHTTPMiddleware
print("TRACE: starlette middleware imported", flush=True)
from starlette.requests import Request
from starlette.responses import Response
print("TRACE: starlette requests/responses imported", flush=True)

load_dotenv()
print("TRACE: Dotenv loaded", flush=True)

fastapi_app = FastAPI()
print("TRACE: FastAPI app initialized", flush=True)

# Import Routers
print("TRACE: Importing routers...", flush=True)
print("TRACE: Import game", flush=True)
from app.routers import game
print("TRACE: Import auth", flush=True)
from app.routers import auth
print("TRACE: Import characters", flush=True)
from app.routers import characters
print("TRACE: Import settings", flush=True)
from app.routers import settings
print("TRACE: Import items", flush=True)
from app.routers import items
print("TRACE: Import compendium", flush=True)
from app.routers import compendium
print("TRACE: Import campaigns", flush=True)
from app.routers import campaigns
print("TRACE: Import users", flush=True)
from app.routers import users
print("TRACE: Imported all routers", flush=True)

from app.socket_manager import sio
print("TRACE: Socket Manager imported (main.py side)", flush=True)
import socketio
print("TRACE: SocketIO imported", flush=True)
from db.init_db import init_db_async
print("TRACE: Init DB imported", flush=True)
from app.firebase_config import init_firebase
from app.auth_utils import verify_token
# Import data loader service
from app.services.data_loader import load_basic_dataset, is_dataset_loaded
from db.session import AsyncSessionLocal
# ...
@fastapi_app.on_event("startup")
async def startup_event():
    try:
        await init_db_async()
        init_firebase()
        print("Database initialized successfully.")
        
        # Automatic Data Load Check
        print("Checking if dataset is loaded...", flush=True)
        async with AsyncSessionLocal() as db:
            if not await is_dataset_loaded(db):
                print("Dataset not found. Loading basic dataset...", flush=True)
                await load_basic_dataset()
            else:
                print("Dataset already loaded.", flush=True)
    except Exception as e:
        print(f"CRITICAL: Database initialization failed: {e}", flush=True)
        # Raise exception to crash the container so Cloud Run knows it failed
        raise e

# 2. Include Routers
fastapi_app.include_router(game.router, dependencies=[Depends(verify_token)])
fastapi_app.include_router(auth.router) 
fastapi_app.include_router(campaigns.router, prefix="/campaigns", dependencies=[Depends(verify_token)])
fastapi_app.include_router(characters.router, dependencies=[Depends(verify_token)])
fastapi_app.include_router(items.router, dependencies=[Depends(verify_token)])
fastapi_app.include_router(compendium.router, dependencies=[Depends(verify_token)])
fastapi_app.include_router(settings.router, dependencies=[Depends(verify_token)])
fastapi_app.include_router(users.router, dependencies=[Depends(verify_token)])

@fastapi_app.get("/")
async def health_check():
    return {
        "status": "online",
        "service": "RoundTable 4.1 Orchestrator",
        "version": "0.1.0"
    }

# 3. Middleware Configuration

# Hardcoded defaults to ensure production always works
default_origins = [
    "https://roundtable41-1dc2c.web.app",
    "https://roundtable41-1dc2c.firebaseapp.com",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173"
]

origins_env = os.getenv("ALLOWED_ORIGINS", "")
allow_origins = []
if origins_env:
    if ";" in origins_env:
        allow_origins = [o.strip() for o in origins_env.split(";") if o.strip()]
    else:
        allow_origins = [o.strip() for o in origins_env.split(",") if o.strip()]

allowed_origins = list(set(allow_origins + default_origins))
print(f"Proprietary CORS Loaded. Allowed: {allowed_origins}")

# Custom Logging Middleware
class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin")
        print(f"Incoming Request: {request.method} {request.url.path} | Origin: {origin}", flush=True)
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            print(f"Error processing request: {e}", flush=True)
            raise e

# Add Middleware
fastapi_app.add_middleware(LoggingMiddleware)

from fastapi.middleware.cors import CORSMiddleware

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from sqlalchemy import text
from db.session import AsyncSessionLocal

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
