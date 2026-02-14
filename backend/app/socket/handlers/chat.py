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
    content = data.get('content')
    sender_name = data.get('sender_name') or 'Player'
    sender_id = data.get('sender_id') or user_id

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


    # 3. Handle @move command
    if content.strip().lower().startswith("@move"):
        target_name = content.strip()[5:].strip()
        if not target_name:
             await sio.emit('system_message', {'content': "Usage: @move <location_name>"}, room=campaign_id)
             return

        await CommandService.handle_move(campaign_id, sender_id, sender_name, target_name, sio, sid=sid)
        return

    # 4. Handle @attack command
    if content.strip().lower().startswith("@attack"):
        target_name = content.strip()[7:].strip()
        if not target_name:
             await sio.emit('system_message', {'content': "Usage: @attack <target_name>"}, room=campaign_id)
             return

        await CommandService.handle_attack(campaign_id, sender_id, sender_name, target_name, sio, sid=sid)
        return


    # 5. Handle @identify command
    if content.strip().lower().startswith("@identify"):
        target_name = content.strip()[9:].strip()
        if not target_name:
             await sio.emit('system_message', {'content': "Usage: @identify <target_name>"}, room=campaign_id)
             return

        await CommandService.handle_identify(campaign_id, sender_id, sender_name, target_name, sio, sid=sid)
        return

    # 4. Trigger DM
    if "@dm" in content.lower():
        await sio.emit('typing_indicator', {'sender_id': 'dm', 'is_typing': True}, room=campaign_id)

        try:
            # Build Rich Context
            rich_context = ""
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    text("SELECT state_data FROM game_states WHERE campaign_id = :campaign_id ORDER BY turn_index DESC, updated_at DESC LIMIT 1"),
                    {"campaign_id": campaign_id}
                )
                state_row = result.mappings().fetchone()
                if state_row:
                    gs = GameState(**json.loads(state_row['state_data']))
                    rich_context = await build_narrative_context(db, campaign_id, gs)

                # Call Service
                response_text = await AIService.generate_chat_response(
                    campaign_id=campaign_id,
                    sender_name=sender_name,
                    db=db,
                    sid=sid,
                    rich_context=rich_context
                )

                save_result = await ChatService.save_message(campaign_id, 'dm', 'Dungeon Master', response_text, db=db)
                await db.commit() # ENSURE COMMIT

                await sio.emit('chat_message', {
                    'sender_id': 'dm', 'sender_name': 'Dungeon Master', 'content': response_text, 'id': save_result['id'], 'timestamp': save_result['timestamp']
                }, room=campaign_id)
                log_debug(f"DEBUG: Successfully sent DM response to campaign {campaign_id}")

            # --- BANTER LOGIC ---
            import random

            ai_characters = []
            state_row = None

            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    text("SELECT state_data FROM game_states WHERE campaign_id = :campaign_id ORDER BY turn_index DESC, updated_at DESC LIMIT 1"),
                    {"campaign_id": campaign_id}
                )
                state_row = result.mappings().fetchone()

            if state_row:
                state_data = json.loads(state_row['state_data'])
                party = state_data.get('party', [])
                for char in party:
                    if char.get('is_ai') or char.get('control_mode') == 'ai':
                        ai_characters.append(char)

            if ai_characters:
                banter_char = random.choice(ai_characters)
                log_debug(f"DEBUG: Selected {banter_char['name']} for banter.")

                try:
                    await sio.emit('typing_indicator', {'sender_id': banter_char['id'], 'is_typing': True}, room=campaign_id)

                    async with AsyncSessionLocal() as db:
                        banter_history = await ChatService.get_chat_history(campaign_id, limit=20, db=db)

                        banter_instruction = HumanMessage(content=f"""
                        [System] The Dungeon Master just said: "{response_text}"

                        React to this statement.
                        - Make a short, in-character quip, comment, or observation.
                        - Do NOT be repetitive.
                        - If the DM was describing danger, be on guard.
                        - If the DM was funny, laugh.
                        - Keep it under 2 sentences.
                        """)

                        banter_response = await AIService.generate_character_response(
                            campaign_id=campaign_id,
                            character=banter_char,
                            history=banter_history + [banter_instruction],
                            db=db,
                            sid=sid
                        )

                        if banter_response:
                            save_result = await ChatService.save_message(campaign_id, banter_char['id'], banter_char['name'], banter_response, db=db)

                            await sio.emit('chat_message', {
                                'sender_id': banter_char['id'],
                                'sender_name': banter_char['name'],
                                'content': banter_response,
                                'id': save_result['id'],
                                'timestamp': save_result['timestamp']
                            }, room=campaign_id)
                            log_debug(f"DEBUG: Banter response content: '{banter_response}'")

                        await db.commit()

                except Exception as e:
                    log_debug(f"Error in Banter generation: {e}")

                await sio.emit('typing_indicator', {'sender_id': banter_char['id'], 'is_typing': False}, room=campaign_id)
            # --- END BANTER LOGIC ---

        except Exception as e:
            log_debug(f"Agent Error: {e}")
            await sio.emit('chat_message', {
                'sender_id': 'dm',
                'sender_name': 'System',
                'content': f"The DM is confused. (Error: {e})",
                'timestamp': 'Just now'
            }, room=campaign_id)

        await sio.emit('typing_indicator', {'sender_id': 'dm', 'is_typing': False}, room=campaign_id)

    # 4. Trigger AI Characters via @Mention
    import re
    mentions = re.findall(r"@(\w+)", content)
    if mentions:
        log_debug(f"DEBUG: Found mentions in chat: {mentions}")
        unique_mentions = set(mentions)
        for mentioned_name in unique_mentions:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    text("SELECT state_data FROM game_states WHERE campaign_id = :campaign_id ORDER BY turn_index DESC, updated_at DESC LIMIT 1"),
                    {"campaign_id": campaign_id}
                )
                state_row = result.mappings().fetchone()

                target_char = None
                if state_row:
                    state_data = json.loads(state_row['state_data'])
                    party = state_data.get('party', [])

                    for char in party:
                        c_names = char['name'].split()
                        if any(n.lower() == mentioned_name.lower() for n in c_names):
                            if char.get('is_ai') or char.get('control_mode') == 'ai':
                                target_char = char
                                break
                            else:
                                log_debug(f"DEBUG: {char['name']} matched but is NOT AI.")

            if target_char:
                log_debug(f"DEBUG: triggering AI response for {target_char['name']}")
                await sio.emit('typing_indicator', {'sender_id': target_char['id'], 'is_typing': True}, room=campaign_id)

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
                            save_result = await ChatService.save_message(campaign_id, target_char['id'], target_char['name'], response_text, db=db)
                            await sio.emit('chat_message', {
                                'sender_id': target_char['id'],
                                'sender_name': target_char['name'],
                                'content': response_text,
                                'id': save_result['id'],
                                'timestamp': save_result['timestamp']
                            }, room=campaign_id)

                        await db.commit()
                except Exception as e:
                    log_debug(f"Error in Mention generation: {e}")

                await sio.emit('typing_indicator', {'sender_id': target_char['id'], 'is_typing': False}, room=campaign_id)
