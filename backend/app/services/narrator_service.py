import logging
import asyncio
from app.services.ai_service import AIService
from app.services.chat_service import ChatService
from db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

class NarratorService:
    @staticmethod
    async def narrate(campaign_id: str, context: str, sio, db=None, mode: str = "chat", prompt_context: str = None, sid: str = None):
        """
        Generates and sends DM narration.

        :param campaign_id: The campaign ID.
        :param context: The trigger context (e.g. "Attack Result: ...").
        :param sio: SocketIO server instance to emit events.
        :param db: Optional DB session. If provided, it is used. If not, a new one is created.
        :param mode: The narration mode (e.g. "combat_narration", "move_narration").
        :param prompt_context: Additional context for the prompt if needed.
        :param sid: The Session ID of the user triggering the event (for AI stats tracking).
        """

        # Helper to run logic with a session
        if db:
            await NarratorService._execute_narration(campaign_id, context, sio, db, mode, sid)
        else:
             async with AsyncSessionLocal() as session:
                 await NarratorService._execute_narration(campaign_id, context, sio, session, mode, sid)

    @staticmethod
    async def _execute_narration(campaign_id: str, context: str, sio, db, mode: str, sid: str = None):
        await sio.emit('typing_indicator', {'sender_id': 'dm', 'is_typing': True}, room=campaign_id)
        try:
            # Context Building
            # If we need history, we fetch it here
            recent_history = await ChatService.get_chat_history(campaign_id, limit=5, db=db)

            narration = await AIService.generate_dm_narration(
                campaign_id=campaign_id,
                context=context,
                history=recent_history,
                db=db,
                mode=mode,
                sid=sid
            )

            if narration:
                save_result = await ChatService.save_message(campaign_id, 'dm', 'Dungeon Master', narration, db=db)
                await sio.emit('chat_message', {
                    'sender_id': 'dm', 'sender_name': 'Dungeon Master', 'content': narration, 'id': save_result['id'], 'timestamp': save_result['timestamp'], 'message_type': 'narration'
                }, room=campaign_id)
                # We should commit if we saved a message, but we must be careful if the caller manages the transaction.
                # If 'db' was passed in, we usually expect the caller to commit?
                # But here we are performing a distinct action (Narration) that might be "fire and forget" logic wise.
                # However, since we are inside a transaction in TurnManager often, we can just let it be flush?
                # But save_message uses execute, which needs commit to persist if we want it seen immediately?
                # Using `await db.commit()` here might commit previous pending changes from the caller too.
                # In `TurnManager`, we commit mechanics BEFORE calling narration. So it is safe to commit here.
                await db.commit()

        except Exception as e:
            logger.error(f"Service Error: {e}", exc_info=True)
            await sio.emit('chat_message', {'sender_id': 'system', 'sender_name': 'System', 'content': f"🚫 DM Narrator Error: {e}", 'timestamp': "Just now", 'is_system': True, 'message_type': 'system'}, room=campaign_id)

        finally:
            await sio.emit('typing_indicator', {'sender_id': 'dm', 'is_typing': False}, room=campaign_id)
