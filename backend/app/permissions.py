from fastapi import Depends, HTTPException
from .dependencies import get_db
from .auth_utils import verify_token as verify_firebase_id_token
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

# Alias for consistent check
verify_token = verify_firebase_id_token

async def is_admin(user: dict, db: AsyncSession) -> bool:
    """
    Check if the user has admin privileges.
    Expects `user` dict from `verify_token` dependency.
    """
    uid = user.get("uid")
    if not uid:
        return False
        
    result = await db.execute(text("SELECT is_admin FROM profiles WHERE id = :uid"), {"uid": uid})
    row = result.mappings().fetchone()
    
    if row and row["is_admin"]:
        return True
    return False

async def require_admin(
    user: dict = Depends(verify_token), 
    db: AsyncSession = Depends(get_db)
):
    """
    Dependency that raises 403 if not admin.
    Returns user dict if authorized.
    """
    if not await is_admin(user, db):
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return user
