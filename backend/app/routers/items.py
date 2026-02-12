
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import json
from ..dependencies import get_db

router = APIRouter(prefix="/items", tags=["items"])

class Item(BaseModel):
    id: str
    name: str
    type: str | None
    data: dict

@router.get("/search", response_model=List[Item])
async def search_items(q: str = Query(None), db: AsyncSession = Depends(get_db)):
    """Search for items by name. Returns first 25 if no query."""
    if q and len(q.strip()) > 0:
        result = await db.execute(
            text("SELECT id, name, type, data FROM items WHERE name LIKE :q LIMIT 25"),
            {"q": f"%{q}%"}
        )
    else:
        result = await db.execute(
            text("SELECT id, name, type, data FROM items LIMIT 25")
        )
    rows = result.mappings().all()

    items = []
    for row in rows:
        try:
            data = json.loads(row['data'])
        except:
            data = {}

        items.append(Item(
            id=row['id'],
            name=row['name'],
            type=row['type'],
            data=data
        ))

    return items
