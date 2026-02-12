from fastapi import APIRouter, Depends, HTTPException
import logging
from ..dependencies import get_db
from ..dtos import CreateCharacterRequest, CharacterResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import json
from uuid import uuid4

router = APIRouter(prefix="/characters", tags=["characters"])
logger = logging.getLogger(__name__)

@router.post("/", response_model=CharacterResponse)
async def create_character(req: CreateCharacterRequest, db: AsyncSession = Depends(get_db)):
    if not req.campaign_id:
        raise HTTPException(status_code=400, detail="Campaign ID is required to create a character.")

    new_id = str(uuid4())
    sheet_data_json = json.dumps(req.sheet_data)

    try:
        await db.execute(
            text("""INSERT INTO characters
               (id, user_id, campaign_id, name, role, race, level, xp, sheet_data, backstory, control_mode)
               VALUES (:id, :user_id, :campaign_id, :name, :role, :race, :level, :xp, :sheet_data, :backstory, :control_mode)"""),
            {
                "id": new_id,
                "user_id": req.user_id,
                "campaign_id": req.campaign_id,
                "name": req.name,
                "role": req.role,
                "race": req.race,
                "level": req.level,
                "xp": req.xp,
                "sheet_data": sheet_data_json,
                "backstory": req.backstory,
                "control_mode": req.control_mode
            }
        )
        await db.commit()
    except Exception as e:
        logger.error(f"Error creating character: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    return CharacterResponse(
        id=new_id,
        user_id=req.user_id,
        campaign_id=req.campaign_id,
        name=req.name,
        role=req.role,
        control_mode=req.control_mode,
        race=req.race,
        level=req.level,
        xp=req.xp,
        sheet_data=req.sheet_data,
        backstory=req.backstory
    )

@router.get("/user/{user_id}", response_model=list[CharacterResponse])
async def get_user_characters(user_id: str, campaign_id: str | None = None, db: AsyncSession = Depends(get_db)):
    if campaign_id:
        result = await db.execute(text("SELECT * FROM characters WHERE user_id = :user_id AND campaign_id = :campaign_id"), {"user_id": user_id, "campaign_id": campaign_id})
    else:
        # Backward compatibility or list all?
        # Maybe list all, front end filters? Or assume if no campaign_id, getting for "Lobby"?
        result = await db.execute(text("SELECT * FROM characters WHERE user_id = :user_id"), {"user_id": user_id})

    rows = result.mappings().all()

    return [
        CharacterResponse(
            id=row["id"],
            user_id=row["user_id"],
            campaign_id=row["campaign_id"] if "campaign_id" in row.keys() else None,
            name=row["name"],
            role=row["role"],
            control_mode=row["control_mode"] if "control_mode" in row.keys() else "human",
            race=row["race"],
            level=row["level"],
            xp=row["xp"],
            sheet_data=json.loads(row["sheet_data"]),
            backstory=row["backstory"]
        ) for row in rows
    ]

@router.delete("/{character_id}")
async def delete_character(character_id: str, db: AsyncSession = Depends(get_db)):
    # Check if exists
    result = await db.execute(text("SELECT * FROM characters WHERE id = :id"), {"id": character_id})
    row = result.mappings().fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Character not found")

    await db.execute(text("DELETE FROM characters WHERE id = :id"), {"id": character_id})
    await db.commit()
    return {"message": "Character deleted successfully"}

@router.patch("/{character_id}", response_model=CharacterResponse)
async def update_character(character_id: str, req: CreateCharacterRequest | dict, db: AsyncSession = Depends(get_db)):
    # Note: Using CreateCharacterRequest | dict is a bit loose, ideally use UpdateCharacterRequest
    # But for now let's just accept a partial update if we can, or strict.
    # Let's use the actual UpdateCharacterRequest we defined in DTOs.
    from ..dtos import UpdateCharacterRequest

    if isinstance(req, dict):
        # Fallback if Pydantic doesn't catch it
        req = UpdateCharacterRequest(**req)

    result = await db.execute(text("SELECT * FROM characters WHERE id = :id"), {"id": character_id})
    row = result.mappings().fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Character not found")

    # Build update values dynamically
    update_values = {}
    if req.control_mode is not None:
        update_values["control_mode"] = req.control_mode
    if req.name is not None:
        update_values["name"] = req.name
    if req.role is not None:
        update_values["role"] = req.role
    if req.race is not None:
        update_values["race"] = req.race
    if req.level is not None:
        update_values["level"] = req.level
    if req.xp is not None:
        update_values["xp"] = req.xp
    if req.sheet_data is not None:
        update_values["sheet_data"] = json.dumps(req.sheet_data)
    if req.backstory is not None:
        update_values["backstory"] = req.backstory
    if req.campaign_id is not None:
        update_values["campaign_id"] = req.campaign_id

    if update_values:
        # Construct SQL dynamically
        set_clauses = [f"{key} = :{key}" for key in update_values.keys()]
        query = f"UPDATE characters SET {', '.join(set_clauses)} WHERE id = :id"
        update_values["id"] = character_id

        await db.execute(text(query), update_values)
        await db.commit()

    # Return updated
    result = await db.execute(text("SELECT * FROM characters WHERE id = :id"), {"id": character_id})
    row = result.mappings().fetchone()

    return CharacterResponse(
        id=row["id"],
        user_id=row["user_id"],
        name=row["name"],
        role=row["role"],
        control_mode=row["control_mode"] if "control_mode" in row.keys() else "human", # Handle legacy rows if any (schema default should handle it though)
        race=row["race"],
        level=row["level"],
        xp=row["xp"],
        sheet_data=json.loads(row["sheet_data"]),
        backstory=row["backstory"]
    )
