from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import json
from ..dependencies import get_db

router = APIRouter(prefix="/compendium", tags=["compendium"])

class CompendiumItem(BaseModel):
    id: str
    name: str
    data: dict

async def search_compendium(table_name: str, q: str, db: AsyncSession, limit_val: int = 25) -> List[CompendiumItem]:
    """Generic helper to search a given table by name."""
    if q and len(q.strip()) > 0:
        result = await db.execute(
            text(f"SELECT id, name, data FROM {table_name} WHERE name LIKE :q LIMIT :limit"),
            {"q": f"%{q}%", "limit": limit_val}
        )
    else:
        result = await db.execute(
            text(f"SELECT id, name, data FROM {table_name} LIMIT :limit"),
            {"limit": limit_val}
        )
    rows = result.mappings().all()

    results = []
    for row in rows:
        try:
            data = json.loads(row['data'])
        except json.JSONDecodeError:
            data = {}

        results.append(CompendiumItem(
            id=row['id'],
            name=row['name'],
            data=data
        ))

    return results

@router.get("/spells", response_model=List[CompendiumItem])
async def search_spells(q: str = Query(None), db: AsyncSession = Depends(get_db)):
    """Search for spells by name. Returns first 25 if no query."""
    return await search_compendium("spells", q, db)

@router.get("/spells/{item_id}", response_model=CompendiumItem)
async def get_spell(item_id: str, db: AsyncSession = Depends(get_db)):
    """Get a specific spell by ID."""
    result = await db.execute(
        text("SELECT id, name, data FROM spells WHERE id = :id"),
        {"id": item_id}
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Spell not found")
    
    try:
        data = json.loads(row['data'])
    except json.JSONDecodeError:
        data = {}

    return CompendiumItem(id=row['id'], name=row['name'], data=data)
@router.get("/feats", response_model=List[CompendiumItem])
async def search_feats(q: str = Query(None), db: AsyncSession = Depends(get_db)):
    """Search for feats by name. Returns first 25 if no query."""
    return await search_compendium("feats", q, db)

@router.get("/races", response_model=List[CompendiumItem])
async def search_races(q: str = Query(None), db: AsyncSession = Depends(get_db)):
    """Search for races by name. Returns first 25 if no query."""
    return await search_compendium("races", q, db)

@router.get("/classes", response_model=List[CompendiumItem])
async def search_classes(q: str = Query(None), db: AsyncSession = Depends(get_db)):
    """Search for classes by name. Returns first 25 if no query."""
    return await search_compendium("classes", q, db)

@router.get("/alignments", response_model=List[CompendiumItem])
async def search_alignments(q: str = Query(None), db: AsyncSession = Depends(get_db)):
    """Search for alignments by name. Returns first 25 if no query."""
    return await search_compendium("alignments", q, db)

@router.get("/subraces", response_model=List[CompendiumItem])
async def search_subraces(q: str = Query(None), db: AsyncSession = Depends(get_db)):
    """Search for subraces by name. Returns first 25 if no query."""
    return await search_compendium("subraces", q, db)

@router.get("/backgrounds", response_model=List[CompendiumItem])
async def search_backgrounds(q: str = Query(None), db: AsyncSession = Depends(get_db)):
    """Search for backgrounds. Returns all or matches."""
    return await search_compendium("backgrounds", q, db, limit_val=50)
