import os
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

# Determine DB Driver
# If DATABASE_URL is set, use it (Postgres).
# Otherwise, fall back to SQLite.

DATABASE_URL = os.getenv("DATABASE_URL")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", os.path.join(BASE_DIR, "game.db"))

if DATABASE_URL:
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
            pool_size=20,
            max_overflow=10,
            connect_args={
                "timeout": 10 # 10 seconds connection timeout
            }
        )
        logger.debug("TRACE: create_async_engine returned")
    except Exception as e:
        logger.critical(f"create_async_engine failed: {e}")
        raise e
else:
    # SQLite
    logger.info(f"Using Database: SQLite ({SQLITE_DB_PATH})")
    DATABASE_URL = f"sqlite+aiosqlite:///{SQLITE_DB_PATH}"
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        future=True,
        connect_args={"check_same_thread": False} # Needed for SQLite
    )

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

# Create Session Factory
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
