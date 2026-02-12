import functools
import traceback
import logging


logger = logging.getLogger(__name__)

def socket_event_handler(func):
    """
    Decorator to wrap socket event handlers with error handling and logging.
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in socket event {func.__name__}: {e}")
            logger.error(traceback.format_exc())
            # We could emit an error event to the client here if we had access to sio/sid
            # But arguments vary.
            # Minimal viable: log and swallow to prevent server crash.
    return wrapper
