
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

@router.get("/spells", response_model=List[CompendiumItem])
async def search_spells(q: str = Query(None), db: AsyncSession = Depends(get_db)):
    """Search for spells by name. Returns first 25 if no query."""
    if q and len(q.strip()) > 0:
        result = await db.execute(
            text("SELECT id, name, data FROM spells WHERE name LIKE :q LIMIT 25"),
            {"q": f"%{q}%"}
        )
    else:
        result = await db.execute(
            text("SELECT id, name, data FROM spells LIMIT 25")
        )
    rows = result.mappings().all()
    
    results = []
    for row in rows:
        try:
            data = json.loads(row['data'])
        except:
            data = {}
        
        results.append(CompendiumItem(
            id=row['id'],
            name=row['name'],
            data=data
        ))
        
    return results

@router.get("/feats", response_model=List[CompendiumItem])
async def search_feats(q: str = Query(None), db: AsyncSession = Depends(get_db)):
    """Search for feats by name. Returns first 25 if no query."""
    if q and len(q.strip()) > 0:
        result = await db.execute(
            text("SELECT id, name, data FROM feats WHERE name LIKE :q LIMIT 25"),
            {"q": f"%{q}%"}
        )
    else:
        result = await db.execute(
            text("SELECT id, name, data FROM feats LIMIT 25")
        )
    rows = result.mappings().all()
    
    results = []
    for row in rows:
        try:
            data = json.loads(row['data'])
        except:
            data = {}
        
        results.append(CompendiumItem(
            id=row['id'],
            name=row['name'],
            data=data
        ))
        
    return results

@router.get("/races", response_model=List[CompendiumItem])
async def search_races(q: str = Query(None), db: AsyncSession = Depends(get_db)):
    """Search for races by name. Returns first 25 if no query."""
    if q and len(q.strip()) > 0:
        result = await db.execute(
            text("SELECT id, name, data FROM races WHERE name LIKE :q LIMIT 25"),
            {"q": f"%{q}%"}
        )
    else:
        result = await db.execute(
            text("SELECT id, name, data FROM races LIMIT 25")
        )
    rows = result.mappings().all()
    
    results = []
    for row in rows:
        try:
            data = json.loads(row['data'])
        except:
            data = {}
        
        results.append(CompendiumItem(
            id=row['id'],
            name=row['name'],
            data=data
        ))
        
    return results

@router.get("/classes", response_model=List[CompendiumItem])
async def search_classes(q: str = Query(None), db: AsyncSession = Depends(get_db)):
    """Search for classes by name. Returns first 25 if no query."""
    if q and len(q.strip()) > 0:
        result = await db.execute(
            text("SELECT id, name, data FROM classes WHERE name LIKE :q LIMIT 25"),
            {"q": f"%{q}%"}
        )
    else:
        result = await db.execute(
            text("SELECT id, name, data FROM classes LIMIT 25")
        )
    rows = result.mappings().all()
    
    results = []
    for row in rows:
        try:
            data = json.loads(row['data'])
        except:
            data = {}
        
        results.append(CompendiumItem(
            id=row['id'],
            name=row['name'],
            data=data
        ))
        
    return results

@router.get("/alignments", response_model=List[CompendiumItem])
async def search_alignments(q: str = Query(None), db: AsyncSession = Depends(get_db)):
    """Search for alignments by name. Returns first 25 if no query."""
    if q and len(q.strip()) > 0:
        result = await db.execute(
            text("SELECT id, name, data FROM alignments WHERE name LIKE :q LIMIT 25"),
            {"q": f"%{q}%"}
        )
    else:
        result = await db.execute(
            text("SELECT id, name, data FROM alignments LIMIT 25")
        )
    rows = result.mappings().all()
    
    results = []
    for row in rows:
        try:
            data = json.loads(row['data'])
        except:
            data = {}
        
        results.append(CompendiumItem(
            id=row['id'],
            name=row['name'],
            data=data
        ))
        
    return results

@router.get("/subraces", response_model=List[CompendiumItem])
async def search_subraces(q: str = Query(None), db: AsyncSession = Depends(get_db)):
    """Search for subraces by name. Returns first 25 if no query."""
    if q and len(q.strip()) > 0:
        result = await db.execute(
            text("SELECT id, name, data FROM subraces WHERE name LIKE :q LIMIT 25"),
            {"q": f"%{q}%"}
        )
    else:
        result = await db.execute(
            text("SELECT id, name, data FROM subraces LIMIT 25")
        )
    rows = result.mappings().all()
    
    results = []
    for row in rows:
        try:
            data = json.loads(row['data'])
        except:
            data = {}
        
        results.append(CompendiumItem(
            id=row['id'],
            name=row['name'],
            data=data
        ))
        
    return results


@router.get("/backgrounds", response_model=List[CompendiumItem])
async def search_backgrounds(q: str = Query(None), db: AsyncSession = Depends(get_db)):
    """Search for backgrounds. Returns all or matches."""
    if q and len(q.strip()) > 0:
        result = await db.execute(
            text("SELECT id, name, data FROM backgrounds WHERE name LIKE :q LIMIT 25"),
            {"q": f"%{q}%"}
        )
    else:
        result = await db.execute(
            text("SELECT id, name, data FROM backgrounds LIMIT 50")
        )
    rows = result.mappings().all()
    
    results = []
    for row in rows:
        try:
            data = json.loads(row['data'])
        except:
            data = {}
        
        results.append(CompendiumItem(
            id=row['id'],
            name=row['name'],
            data=data
        ))
        
    return results
