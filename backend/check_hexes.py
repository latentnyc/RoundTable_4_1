import asyncio
from app.db.session import async_session
from sqlalchemy import text

async def explore():
    async with async_session() as db:
        res = await db.execute(text("SELECT data FROM campaigns LIMIT 1"))
        state = res.scalar()
        if state and 'location' in state:
            loc = state['location']
            print("Location Walkable Hexes Type:", type(loc.get('walkable_hexes', [])[0]) if loc.get('walkable_hexes') else "Empty")
            print("First item:", loc.get('walkable_hexes', [])[:1])
            
asyncio.run(explore())
