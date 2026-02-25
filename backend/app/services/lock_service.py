import asyncio
import time
import logging
import hashlib
from contextlib import asynccontextmanager
from db.session import AsyncSessionLocal
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

class LockService:
    LOCK_TIMEOUT_SECONDS = 30.0  # Max time to wait to acquire a lock (increased for AI turns)

    _local_locks = {}  # dict mapping campaign_id -> asyncio.Task
    _local_counts = {} # dict mapping campaign_id -> int
    _local_sessions = {} # dict mapping campaign_id -> AsyncSession

    @staticmethod
    def _get_lock_id(campaign_id: str) -> int:
        """
        Convert a campaign_id string into a 64-bit integer for pg_advisory_lock.
        """
        # SHA256 -> take first 8 bytes -> convert to signed 64-bit int
        hash_digest = hashlib.sha256(campaign_id.encode('utf-8')).digest()
        lock_id = int.from_bytes(hash_digest[:8], byteorder='big', signed=True)
        return lock_id

    @classmethod
    @asynccontextmanager
    async def acquire(cls, campaign_id: str):
        """
        Async context manager that acquires a Postgres advisory lock for the campaign.
        Supports re-entrancy for the same asyncio task.
        """
        current_task = asyncio.current_task()

        # Fast-path for re-entrancy
        if cls._local_locks.get(campaign_id) == current_task:
            cls._local_counts[campaign_id] += 1
            try:
                yield
            finally:
                cls._local_counts[campaign_id] -= 1
            return

        lock_id = cls._get_lock_id(campaign_id)
        session = AsyncSessionLocal()
        acquired = False
        
        try:
            # We use an async timeout because pg_advisory_lock without NOWAIT will block indefinitely
            # until either it gets the lock, or the DB connection drops.
            # Using asyncio.wait_for allows us to enforce LOCK_TIMEOUT_SECONDS asynchronously.
            try:
                await asyncio.wait_for(
                    session.execute(text("SELECT pg_advisory_lock(:id)"), {"id": lock_id}),
                    timeout=cls.LOCK_TIMEOUT_SECONDS
                )
                acquired = True
            except asyncio.TimeoutError:
                raise TimeoutError(f"Failed to acquire advisory lock for campaign {campaign_id} within {cls.LOCK_TIMEOUT_SECONDS}s.")
            except SQLAlchemyError as e:
                logger.error(f"Database error acquiring advisory lock for {campaign_id}: {e}")
                raise
                
            cls._local_locks[campaign_id] = current_task
            cls._local_counts[campaign_id] = 1
            cls._local_sessions[campaign_id] = session
            
            yield
        finally:
            if acquired:
                cls._local_counts[campaign_id] -= 1
                if cls._local_counts[campaign_id] <= 0:
                    cls._local_locks.pop(campaign_id, None)
                    cls._local_counts.pop(campaign_id, None)
                    lock_session = cls._local_sessions.pop(campaign_id, None)
                    
                    if lock_session:
                        try:
                            await lock_session.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": lock_id})
                        except Exception as e:
                            logger.error(f"Error releasing advisory lock for {campaign_id}: {e}")
                        finally:
                            await lock_session.close()
            else:
                # If we failed to acquire, just close the session
                await session.close()
