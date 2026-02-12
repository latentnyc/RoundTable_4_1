from db.session import get_db_session
import logging

logger = logging.getLogger(__name__)

# Dependency
async def get_db():
    logger.debug("Entering get_db dependency (SQLAlchemy)")
    async for session in get_db_session():
        yield session
