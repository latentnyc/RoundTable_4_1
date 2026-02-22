from fastapi import APIRouter, Depends, HTTPException
import logging
import os
from ..dependencies import get_db
from ..dtos import CreateProfileRequest, Profile
from ..auth_utils import verify_token
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from uuid import uuid4


router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

@router.post("/login", response_model=Profile)
async def login(token_data: dict = Depends(verify_token), db: AsyncSession = Depends(get_db)):

    """
    Syncs the Firebase User with the 'profiles' table.
    """
    try:
        uid = token_data["uid"]
        # Use email or name from token as default username if needed, or pass in body
        # For now, we'll just use the UID or a placeholder if creating new

        async with db.begin(): # Transaction
            result = await db.execute(text("SELECT * FROM profiles WHERE id = :uid"), {"uid": uid})
            row = result.mappings().fetchone()

            # Get username from token (e.g. "John Doe") or fallback
            token_username = token_data.get("name", "Adventurer")

            if row:
                # Update username if different (and potentially other fields later)
                current_username = row["username"]
                # SQLAlchemy row mapping keys check
                is_admin = bool(row["is_admin"]) if "is_admin" in row else False # dict-like
                status = row["status"] if "status" in row else "interested"

                if token_username != "Adventurer" and token_username != current_username:
                    try:
                        await db.execute(text("UPDATE profiles SET username = :username WHERE id = :uid"), {"username": token_username, "uid": uid})
                        # Commit happens at end of block or explicit
                        return Profile(id=uid, username=token_username, is_admin=is_admin, status=status)
                    except Exception as e:
                        logger.warning(f"Failed to update username (likely duplicate): {e}")
                        # Fallback to existing name
                        return Profile(id=row["id"], username=current_username, is_admin=is_admin, status=status)

                return Profile(id=row["id"], username=current_username, is_admin=is_admin, status=status)

            # Create new profile
            try:
                # check if this is the FIRST user
                res = await db.execute(text("SELECT COUNT(*) as count FROM profiles"))
                count_row = res.mappings().fetchone()
                is_first = count_row["count"] == 0

                is_admin = is_first # First user is admin

                # First user gets 'active' status, others 'interested'
                status = "active" if is_first else "interested"

                await db.execute(text("INSERT INTO profiles (id, username, is_admin, status) VALUES (:id, :username, :is_admin, :status)"),
                                 {"id": uid, "username": token_username, "is_admin": is_admin, "status": status})
            except Exception as e:
                logger.error(f"Failed to create profile: {e}")
                import traceback
                logger.error(traceback.format_exc())
                # Identify if error is due to missing columns or constraints
                raise HTTPException(status_code=500, detail=f"Profile creation failed: {e}")

            return Profile(id=uid, username=token_username, is_admin=is_admin, status=status)
    except HTTPException as he:
        raise he
    except Exception as e:
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Login failed: {e}")
