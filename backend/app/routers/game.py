print("TRACE: game.py start", flush=True)
from fastapi import APIRouter, Depends, HTTPException
print("TRACE: game.py imported fastapi", flush=True)
from ..models import GameState
print("TRACE: game.py imported models", flush=True)
from ..dependencies import get_db
print("TRACE: game.py imported dependencies", flush=True)
from sqlalchemy.ext.asyncio import AsyncSession
print("TRACE: game.py imported sqlalchemy asyncsession", flush=True)
from sqlalchemy import text
print("TRACE: game.py imported sqlalchemy text", flush=True)
import json
from uuid import uuid4
print("TRACE: game.py imports done", flush=True)

router = APIRouter(prefix="/game", tags=["game"])

@router.get("/state/{session_id}", response_model=GameState)
async def get_game_state(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("SELECT state_data FROM game_states WHERE campaign_id = :session_id ORDER BY turn_index DESC LIMIT 1"), 
        {"session_id": session_id}
    )
    row = result.mappings().fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return GameState(**json.loads(row["state_data"]))

@router.post("/state/{session_id}")
async def update_game_state(session_id: str, state: GameState, db: AsyncSession = Depends(get_db)):
    # This checks if campaign exists, if not 404
    # For now, just insert
    await db.execute(
        text("INSERT INTO game_states (id, campaign_id, turn_index, phase, state_data) VALUES (:id, :campaign_id, :turn_index, :phase, :state_data)"),
        {
            "id": str(uuid4()), 
            "campaign_id": session_id, 
            "turn_index": state.turn_index, 
            "phase": state.phase, 
            "state_data": state.model_dump_json()
        }
    )
    await db.commit()
    return {"status": "updated"}
