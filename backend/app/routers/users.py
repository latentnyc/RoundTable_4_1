from fastapi import APIRouter, Depends, HTTPException, status
from ..dependencies import get_db
from ..dtos import Profile, UpdateProfileRequest
from ..auth_utils import verify_token
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

router = APIRouter(prefix="/users", tags=["users"])

from ..permissions import require_admin

@router.get("/", response_model=list[Profile])
async def list_users(admin_id: str = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(text("SELECT * FROM profiles"))
    rows = result.mappings().all()
    
    profiles = []
    for row in rows:
        profiles.append(Profile(
            id=row["id"],
            username=row["username"],
            is_admin=bool(row["is_admin"]) if "is_admin" in row else False,
            status=row["status"] if "status" in row else "interested"
        ))
    return profiles

@router.patch("/{user_id}", response_model=Profile)
async def update_user(user_id: str, req: UpdateProfileRequest, admin_id: str = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    # Check if user exists
    result = await db.execute(text("SELECT * FROM profiles WHERE id = :id"), {"id": user_id})
    row = result.mappings().fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
        
    updates = []
    values = {}
    
    if req.is_admin is not None:
        updates.append("is_admin = :is_admin")
        values["is_admin"] = req.is_admin
        
    if req.status is not None:
        updates.append("status = :status")
        values["status"] = req.status
        
    if not updates:
        # No updates
        return Profile(
            id=row["id"], 
            username=row["username"],
            is_admin=bool(row["is_admin"]) if "is_admin" in row else False,
            status=row["status"] if "status" in row else "interested"
        )
        
    values["id"] = user_id
    query = f"UPDATE profiles SET {', '.join(updates)} WHERE id = :id"
    
    await db.execute(text(query), values)
    await db.commit()
    
    # Fetch updated
    result = await db.execute(text("SELECT * FROM profiles WHERE id = :id"), {"id": user_id})
    row = result.mappings().fetchone()
    
    return Profile(
        id=row["id"], 
        username=row["username"],
        is_admin=bool(row["is_admin"]) if "is_admin" in row else False
    )

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: str, admin_id: str = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    # Check if user exists
    result = await db.execute(text("SELECT * FROM profiles WHERE id = :id"), {"id": user_id})
    row = result.mappings().fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if self-deletion (optional safety check, but might be annoying if admin wants to delete themselves)
    # Let's allow it for now, as the frontend warns about it.
    
    await db.execute(text("DELETE FROM profiles WHERE id = :id"), {"id": user_id})
    await db.commit()

