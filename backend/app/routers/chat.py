from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from ..permissions import verify_token, is_admin
from ..dependencies import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from pydantic import BaseModel
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

class ChatMessage(BaseModel):
    id: str
    campaign_id: str
    sender_id: str
    sender_name: str
    content: str
    created_at: datetime
    is_system: bool = False

    class Config:
        from_attributes = True

@router.get("/{campaign_id}/history", response_model=List[ChatMessage])
async def get_chat_history(
    campaign_id: str,
    limit: int = Query(50, ge=1, le=100),
    before: Optional[datetime] = None,
    user: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    # Verify User is in Campaign (or Admin)
    # Simple check: If not admin, check participation
    if not await is_admin(user, db):
        check = await db.execute(
            text("SELECT status FROM campaign_participants WHERE campaign_id=:cid AND user_id=:uid"),
            {"cid": campaign_id, "uid": user['uid']}
        )
        if not check.scalar():
             raise HTTPException(status_code=403, detail="Must join campaign to view chat")

    query_str = """
        SELECT id, campaign_id, sender_id, sender_name, content, created_at,
               CASE WHEN sender_id = 'system' THEN true ELSE false END as is_system
        FROM chat_messages
        WHERE campaign_id = :cid
    """
    params = {"cid": campaign_id, "limit": limit}

    if before:
        query_str += " AND created_at < :before"
        params["before"] = before

    query_str += " ORDER BY created_at DESC LIMIT :limit"

    result = await db.execute(text(query_str), params)
    rows = result.mappings().all()

    # Return reversed so client gets oldest -> newest
    return [dict(row) for row in reversed(rows)]

@router.delete("/{campaign_id}")
async def clear_chat_history(
    campaign_id: str,
    user: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    # GM or Admin Only
    is_adm = await is_admin(user, db)
    if not is_adm:
        # Check GM
        gm_check = await db.execute(
            text("SELECT role FROM campaign_participants WHERE campaign_id = :cid AND user_id = :uid AND role = 'gm'"),
            {"cid": campaign_id, "uid": user['uid']}
        )
        if not gm_check.scalar():
            raise HTTPException(status_code=403, detail="Only GM or Admin can clear chat")

    try:
        await db.execute(
            text("DELETE FROM chat_messages WHERE campaign_id = :cid"),
            {"cid": campaign_id}
        )
        await db.commit()
        return {"status": "success", "message": "Chat history cleared"}
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error("Database error clearing chat history for campaign %s: %s", campaign_id, str(e))
        raise HTTPException(status_code=500, detail="Failed to clear chat history due to database error.")
