import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from typing import AsyncGenerator
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

# Determine DB Driver
# DATABASE_URL should be set (Postgres).

DATABASE_URL = os.getenv("DATABASE_URL")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if not DATABASE_URL:
    raise ValueError("DATABASE_URL must be set.")

# Postgres
# Ensure usage of asyncpg driver
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

logger.info(f"Using Database: PostgreSQL ({DATABASE_URL.split('@')[-1]}) with timeout=10s") # Hide credentials

logger.debug("TRACE: Calling create_async_engine (postgres)...")
try:
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        future=True,
        pool_pre_ping=True, # Good for Cloud SQL
        pool_size=50,
        max_overflow=20,
        connect_args={
            "timeout": 10 # 10 seconds connection timeout
        }
    )
    logger.debug("TRACE: create_async_engine returned")
except Exception as e:
    logger.critical(f"create_async_engine failed: {e}")
    raise e

# Create Session Factory
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
