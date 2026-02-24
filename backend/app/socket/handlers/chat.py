import socketio
import json
import logging
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import AsyncSessionLocal
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage



from app.socket.decorators import socket_event_handler
from app.models import GameState
from app.services.game_service import GameService
from app.services.context_builder import build_narrative_context
from app.services.ai_service import AIService
from app.services.chat_service import ChatService
from app.services.command_service import CommandService



def log_debug(message):
    import re
    # Also log to standard logger
    logging.getLogger(__name__).debug(str(message))

    sanitized_message = re.sub(r"('api_key':\s*')[^']+'", r"\1REDACTED'", str(message))
    sanitized_message = re.sub(r'("api_key":\s*")[^"]+"', r'\1REDACTED"', sanitized_message)
    try:
        with open("debug_chat.log", "a") as f:
            import datetime
            timestamp = datetime.datetime.now().isoformat()
            f.write(f"[{timestamp}] {sanitized_message}\n")
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to log: {e}")


# Handlers




# Handlers

@socket_event_handler
async def handle_clear_chat(sid, sio, connected_users):
    if sid not in connected_users:
        return

    user_data = connected_users[sid]
    campaign_id = user_data['campaign_id']
    user_id = user_data['user_id']



    async with AsyncSessionLocal() as db:
        await db.execute(text("DELETE FROM chat_messages WHERE campaign_id = :campaign_id"), {"campaign_id": campaign_id})
        await db.commit()

    await sio.emit('chat_cleared', {}, room=campaign_id)
    await sio.emit('system_message', {'content': "Chat history has been cleared."}, room=campaign_id)

@socket_event_handler
async def handle_clear_logs(sid, sio, connected_users):
    if sid not in connected_users:
        return

    user_data = connected_users[sid]
    campaign_id = user_data['campaign_id']
    user_id = user_data['user_id']



    async with AsyncSessionLocal() as db:
        await db.execute(text("DELETE FROM debug_logs WHERE campaign_id = :campaign_id"), {"campaign_id": campaign_id})
        await db.commit()

    await sio.emit('debug_logs_cleared', {}, room=campaign_id)

# Tracks per-campaign DM busy state
dm_busy_status = {}

@socket_event_handler
async def handle_chat_message(sid, data, sio, connected_users):
    log_debug(f"Received chat_message from {sid}: {data}")

    # Check session/user
    user_data = connected_users.get(sid)
    if not user_data:
        log_debug(f"User data not found for sid {sid}")
        return

    campaign_id = user_data['campaign_id']
    user_id = user_data['user_id']
    content = data.get('content', '')
    sender_name = data.get('sender_name') or 'Player'
    sender_id = data.get('sender_id') or user_id

    is_command = content.strip().startswith("@")

    # 1. Check DM Busy State for Commands
    if is_command and dm_busy_status.get(campaign_id, False):
        log_debug(f"Rejecting command from {sender_name} because DM is busy: {content}")
        await sio.emit('command_rejected', {
            'content': content,
            'reason': "The DM is currently narrating the scene. Wait a moment to see what happens."
        }, room=sid) # Send only to the user who tried to send it
        return

    # Lock if it's a command
    if is_command:
        dm_busy_status[campaign_id] = True

    try:
        # 1. Save User Message
        save_result = await ChatService.save_message(campaign_id, sender_id, sender_name, content)

        # 2. Broadcast to room
        await sio.emit('chat_message', {
            'sender_id': sender_id,
            'sender_name': sender_name,
            'content': content,
            'id': save_result['id'],
            'timestamp': save_result['timestamp']
        }, room=campaign_id)


        # 3. Handle Commands via Registry
        # This handles @move, @attack, @identify, @dm, @help, etc.
        if is_command:
            was_command = await CommandService.dispatch(campaign_id, sender_id, sender_name, content, sio, sid=sid)
            if was_command:
                return


        # 4. Trigger AI Characters via @Mention
        import re
        mentions = re.findall(r"@(\w+)", content)
        if mentions:
            log_debug(f"DEBUG: Found mentions in chat: {mentions}")
            unique_mentions = set(mentions)
            for mentioned_name in unique_mentions:
                async with AsyncSessionLocal() as db:
                    game_state = await GameService.get_game_state(campaign_id, db)
                    target_char = None

                    if game_state:
                        # Check Party
                        for char in game_state.party:
                            c_names = char.name.split()
                            if any(n.lower() == mentioned_name.lower() for n in c_names):
                                if char.is_ai or char.control_mode == 'ai':
                                    target_char = char
                                    break
                                else:
                                    log_debug(f"DEBUG: {char.name} matched but is NOT AI.")

                        # If not found in party, maybe check NPCs?
                        # The original code only checked 'party' from state_data.
                        # But if we want to talk to NPCs, we should check them too.
                        if not target_char:
                            for npc in game_state.npcs:
                                n_names = npc.name.split()
                                if any(n.lower() == mentioned_name.lower() for n in n_names):
                                    # NPCs are usually AI driven if they have data?
                                    # Or just always respond if mentioned?
                                    # Let's assume yes for now.
                                    target_char = npc
                                    break

                if target_char:
                    log_debug(f"DEBUG: triggering AI response for {target_char.name}")
                    await sio.emit('typing_indicator', {'sender_id': target_char.id, 'is_typing': True}, room=campaign_id)

                    try:
                        async with AsyncSessionLocal() as db:
                            history = await ChatService.get_chat_history(campaign_id, limit=20, db=db)

                            response_text = await AIService.generate_character_response(
                                campaign_id=campaign_id,
                                character=target_char,
                                history=history,
                                db=db,
                                sid=sid
                            )

                            if response_text:
                                save_result = await ChatService.save_message(campaign_id, target_char.id, target_char.name, response_text, db=db)
                                await sio.emit('chat_message', {
                                    'sender_id': target_char.id,
                                    'sender_name': target_char.name,
                                    'content': response_text,
                                    'id': save_result['id'],
                                    'timestamp': save_result['timestamp']
                                }, room=campaign_id)

                            await db.commit()
                    except Exception as e:
                        if 'db' in locals() and db is not None:
                            try:
                                await db.rollback()
                            except Exception:
                                pass
                        log_debug(f"Error in Mention generation: {e}")

                    await sio.emit('typing_indicator', {'sender_id': target_char.id, 'is_typing': False}, room=campaign_id)

    finally:
        # Release the lock if we took it
        if is_command:
            dm_busy_status[campaign_id] = False
