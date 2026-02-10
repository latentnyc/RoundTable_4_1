import os
import firebase_admin
from firebase_admin import auth, credentials
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Initialize Firebase Admin SDK
# In Cloud Run, it uses Application Default Credentials automatically.
# Locally, make sure you have GOOGLE_APPLICATION_CREDENTIALS set or run `gcloud auth application-default login`
# Firebase is initialized in main.py -> firebase_config.py
# This ensures we use the correct emulator settings before any auth calls are made.

security = HTTPBearer()

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    print("DEBUG: Entering verify_token dependency", flush=True)
    token = credentials.credentials
    try:
        decoded_token = auth.verify_id_token(token)
        print("DEBUG: Token verified successfully", flush=True)
        return decoded_token
    except Exception as e:
        print(f"Auth Error: {e}", flush=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user(token_data: dict = Depends(verify_token)):
    return token_data

async def get_current_profile(token_data: dict = Depends(verify_token)):
    # Import here to avoid circular dependency if possible, or move to dependencies.py
    # But dependencies.py imports get_db. 
    # Let's perform a raw DB lookup or import get_db inside.
    from .dependencies import get_db
    
    # We need a new async generator context for get_db since it's a generator
    # But Depends(get_db) works in FastAPI. 
    # To do this manually inside a function is tricky without Depends.
    # So we should use Depends(get_db) in the signature.
    pass

# We will define these in routers or a separate complex dependencies file to avoid circular imports.
# For now, let's keep auth_utils simple and do the admin check in the router using Depends.
