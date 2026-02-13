import asyncio
import os
import sys
import json
from uuid import uuid4
from unittest.mock import MagicMock

# Add backend to path
sys.path.append(os.getcwd())

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text, insert
from db.schema import metadata, campaigns, debug_logs, campaign_participants

# Test DB
TEST_DB_PATH = "test_logs_api.db"
DATABASE_URL = f"sqlite+aiosqlite:///{TEST_DB_PATH}"

async def setup_db():
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
        
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    
    return sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def test_logs_endpoint():
    print("Setting up DB...")
    SessionLocal = await setup_db()
    
    cid = str(uuid4())
    uid = str(uuid4())
    
    async with SessionLocal() as db:
        # 1. Seed Campaign & Participant
        await db.execute(insert(campaigns).values(id=cid, name="Test Campaign", gm_id=uid))
        await db.execute(insert(campaign_participants).values(
            id=str(uuid4()), campaign_id=cid, user_id=uid, role="gm", status="active"
        ))
        
        # 2. Seed Debug Logs
        from datetime import datetime
        # Log 1 (Oldest)
        await db.execute(insert(debug_logs).values(
            id=str(uuid4()), campaign_id=cid, type="llm_start", 
            content="Log 1", full_content=json.dumps({"msg": "Hello"}),
            created_at=datetime(2024, 1, 1, 10, 0, 0)
        ))
        # Log 2 (Newest)
        await db.execute(insert(debug_logs).values(
            id=str(uuid4()), campaign_id=cid, type="llm_end", 
            content="Log 2", full_content=json.dumps({"msg": "World"}),
            created_at=datetime(2024, 1, 1, 10, 0, 5)
        ))
        await db.commit()
        
    print("Data seeded. Calling endpoint function...")
    
    # Import the function to test
    from app.routers.campaigns import get_campaign_logs
    
    # Mock User
    mock_user = {"uid": uid, "email": "test@example.com"}
    
    async with SessionLocal() as db:
        # Call directly
        logs = await get_campaign_logs(campaign_id=cid, limit=10, user=mock_user, db=db)
        
        print(f"Retrieved {len(logs)} logs.")
        for l in logs:
            print(f"- [{l['created_at']}] {l['type']}: {l['content']}")
            
        # Assertions
        assert len(logs) == 2
        # Verify Order (Desc)
        assert logs[0]['type'] == 'llm_end'
        assert logs[1]['type'] == 'llm_start'
        
        print("SUCCESS: Logs retrieved and ordered correctly.")

if __name__ == "__main__":
    asyncio.run(test_logs_endpoint())
