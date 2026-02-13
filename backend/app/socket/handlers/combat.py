import logging
from app.services.turn_manager import TurnManager

# DEPRECATED: Use app.services.turn_manager.TurnManager instead

logger = logging.getLogger(__name__)

async def advance_turn(campaign_id: str, sio, db=None, recursion_depth=0):
    logger.warning("app.socket.handlers.combat.advance_turn is deprecated. Use TurnManager.advance_turn")
    await TurnManager.advance_turn(campaign_id, sio, db, recursion_depth)

async def process_turn(campaign_id: str, active_id: str, game_state, sio, recursion_depth=0):
    logger.warning("app.socket.handlers.combat.process_turn is deprecated. Use TurnManager.process_turn")
    await TurnManager.process_turn(campaign_id, active_id, game_state, sio, recursion_depth)

# execute_ai_turn is internal to TurnManager now, so we don't need to re-export it unless used elsewhere.
# It was not used in chat.py.
