import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

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

    print(f"Using Database: PostgreSQL ({DATABASE_URL.split('@')[-1]}) with timeout=10s", flush=True) # Hide credentials

    print("TRACE: Calling create_async_engine (postgres)...", flush=True)
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
        print("TRACE: create_async_engine returned", flush=True)
    except Exception as e:
        print(f"CRITICAL: create_async_engine failed: {e}", flush=True)
        raise e
else:
    # SQLite
    print(f"Using Database: SQLite ({SQLITE_DB_PATH})", flush=True)
    DATABASE_URL = f"sqlite+aiosqlite:///{SQLITE_DB_PATH}"
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        future=True,
        connect_args={"check_same_thread": False} # Needed for SQLite
    )

# Create Session Factory
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
