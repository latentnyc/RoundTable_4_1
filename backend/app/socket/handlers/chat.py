import socketio
import json
import logging
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import AsyncSessionLocal
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage



from app.socket.decorators import socket_event_handler
from game_engine.engine import GameEngine
from app.models import GameState
from app.services.context_builder import build_narrative_context
from app.services.game_service import GameService
from app.services.ai_service import AIService

# Helper Functions
async def save_message(campaign_id: str, sender_id: str, sender_name: str, content: str, db: AsyncSession = None):
    msg_id = str(uuid4())
    import datetime
    timestamp = datetime.datetime.now()

    if db:
        await db.execute(
            text("""INSERT INTO chat_messages (id, campaign_id, sender_id, sender_name, content, created_at)
               VALUES (:id, :campaign_id, :sender_id, :sender_name, :content, :created_at)"""),
            {"id": msg_id, "campaign_id": campaign_id, "sender_id": sender_id, "sender_name": sender_name, "content": content, "created_at": timestamp}
        )
        # Note: We do NOT commit here if db is provided, caller handles transaction.
        return {"id": msg_id, "timestamp": timestamp.isoformat()}
    else:
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("""INSERT INTO chat_messages (id, campaign_id, sender_id, sender_name, content, created_at)
                   VALUES (:id, :campaign_id, :sender_id, :sender_name, :content, :created_at)"""),
                {"id": msg_id, "campaign_id": campaign_id, "sender_id": sender_id, "sender_name": sender_name, "content": content, "created_at": timestamp}
            )
            await session.commit()
            return {"id": msg_id, "timestamp": timestamp.isoformat()}

async def get_chat_history(campaign_id: str, limit: int = 10, db: AsyncSession = None):
    if db:
        result = await db.execute(
            text("""SELECT * FROM chat_messages
               WHERE campaign_id = :campaign_id
               ORDER BY created_at DESC
               LIMIT :limit"""),
            {"campaign_id": campaign_id, "limit": limit}
        )
        # Reuse logic? We need to map it.
        # Ideally we refactor 'fetch' to work with db too but fetch creates a nested function.
        # Let's just do:
        rows = result.mappings().all()
    else:
        # We need to handle both cases efficiently.
        async def fetch(session):
            result = await session.execute(
                text("""SELECT * FROM chat_messages
                   WHERE campaign_id = :campaign_id
                   ORDER BY created_at DESC
                   LIMIT :limit"""),
                {"campaign_id": campaign_id, "limit": limit}
            )
            return result.mappings().all()

        async with AsyncSessionLocal() as session:
            rows = await fetch(session)

    messages = []

    # ... (rest of get_chat_history is fine, but I need to close the function properly in the replacement)
    # The snippet above replaces the top part. I need to be careful with the indentation and scope.
    # Actually, simpler to just replace the typo line and the commit block separately.
    # The user asked for multiple edits? 'replace_file_content' is single usage.
    # I should use multi_replace.


    messages = []
    for row in reversed(rows):
        if "DM Agent is offline" in row["content"] or "The DM is confused" in row["content"]:
            continue
        if row["sender_id"] == "dm":
            messages.append(AIMessage(content=row["content"]))
        elif row["sender_id"] == "system":
            messages.append(SystemMessage(content=row["content"]))
        else:
            messages.append(HumanMessage(content=f"{row['sender_name']}: {row['content']}"))
    return messages

async def get_latest_memory(campaign_id: str):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("SELECT summary_text, created_at FROM campaign_memories WHERE campaign_id = :cid ORDER BY created_at DESC LIMIT 1"),
            {"cid": campaign_id}
        )
        row = result.mappings().fetchone()
        if row:
            return row['summary_text'], row['created_at']
        return None, None

async def save_memory(campaign_id: str, summary_text: str):
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("INSERT INTO campaign_memories (id, campaign_id, summary_text) VALUES (:id, :cid, :txt)"),
            {"id": str(uuid4()), "cid": campaign_id, "txt": summary_text}
        )
        await db.commit()

async def get_messages_after(campaign_id: str, after_date):
    async with AsyncSessionLocal() as db:
        # If no date, get all (with safe limit)
        if not after_date:
            result = await db.execute(
                text("SELECT * FROM chat_messages WHERE campaign_id = :cid ORDER BY created_at ASC LIMIT 100"),
                {"cid": campaign_id}
            )
        else:
            result = await db.execute(
                text("SELECT * FROM chat_messages WHERE campaign_id = :cid AND created_at > :dt ORDER BY created_at ASC LIMIT 100"),
                {"cid": campaign_id, "dt": after_date}
            )

        rows = result.mappings().all()
        # Convert to LangChain messages
        messages = []
        for row in rows:
            if "DM Agent is offline" in row["content"] or "The DM is confused" in row["content"]:
                continue
            if row["sender_id"] == "dm":
                messages.append(AIMessage(content=row["content"]))
            elif row["sender_id"] == "system":
                messages.append(SystemMessage(content=row["content"]))
            else:
                messages.append(HumanMessage(content=f"{row['sender_name']}: {row['content']}"))
        return messages

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


async def process_attack(campaign_id: str, attacker_id: str, attacker_name: str, target_name: str, sio, db, sid=None, allow_counterattack: bool = True, is_counterattack: bool = False, recursion_depth: int = 0):
    """
    Processes an attack command using GameService.
    recursion_depth: tracks the depth of counterattacks (0 = initial attack, 1 = first counterattack)
    """
    prefix = "⚡ **COUNTERATTACK!** " if is_counterattack else "⚔️ "
    log_debug(f"DEBUG: Processing {prefix} from {attacker_name} ({attacker_id}) on {target_name} [Depth: {recursion_depth}]")

    if recursion_depth > 1:
        log_debug(f"DEBUG: Max recursion depth reached ({recursion_depth}). Stopping counterattack chain.")
        return

    # 1. Mechanical Resolution via Service
    result = await GameService.resolution_attack(campaign_id, attacker_id, attacker_name, target_name, db)

    if not result.get("success"):
        if recursion_depth == 0: # Only notify user if main attack fails
            await sio.emit('system_message', {'content': result.get("message", "Attack failed.")}, room=campaign_id)
        return

    # Extract Data
    actor_char = result['actor_object']
    target_char = result['target_object']
    game_state = result['game_state']

    # 2. Construct Mechanical Message
    mech_msg = f"{prefix}**{result['attacker_name']}** attacks **{result['target_name']}**!\n"
    mech_msg += f"**Roll:** {result['attack_roll']} + {result['attack_mod']} = **{result['attack_total']}** vs AC {result['target_ac']}\n"
    if result['is_hit']:
        mech_msg += f"**HIT!** 🩸 Damage: **{result['damage_total']}** ({result['damage_detail']})\n"
        mech_msg += f"Target HP: {result['target_hp_remaining']}"
    else:
        mech_msg += "**MISS!** 🛡️"

    save_result = await save_message(campaign_id, 'system', 'System', mech_msg, db=db)
    await sio.emit('chat_message', {
        'sender_id': 'system', 'sender_name': 'System', 'content': mech_msg, 'id': save_result['id'], 'timestamp': save_result['timestamp'], 'is_system': True
    }, room=campaign_id)

    # 3. Trigger DM Narration via Service
    await sio.emit('typing_indicator', {'sender_id': 'dm', 'is_typing': True}, room=campaign_id)
    try:
        # Get recent history for context
        recent_history = await get_chat_history(campaign_id, limit=5, db=db)

        # Call AI Service
        narration = await AIService.generate_dm_narration(
            campaign_id=campaign_id,
            context=mech_msg,
            history=recent_history,
            db=db,
            sid=sid,
            mode="combat_narration"
        )

        if narration:
            save_result = await save_message(campaign_id, 'dm', 'Dungeon Master', narration, db=db)
            await sio.emit('chat_message', {
                'sender_id': 'dm', 'sender_name': 'Dungeon Master', 'content': narration, 'id': save_result['id'], 'timestamp': save_result['timestamp']
            }, room=campaign_id)
    except Exception as e:
        log_debug(f"DM Narration Error: {e}")

    await sio.emit('typing_indicator', {'sender_id': 'dm', 'is_typing': False}, room=campaign_id)

    # 4. Counterattack Trigger
    # Only allow counterattack if:
    # - Specifically allowed by caller
    # - Target is still alive
    # - Recursion depth is 0 (meaning this is the initial attack, so we allow ONE counterattack)
    if allow_counterattack and result.get("target_hp_remaining", 0) > 0 and recursion_depth == 0:
            is_npc = any(n.id == target_char.id for n in game_state.npcs)
            is_enemy = any(e.id == target_char.id for e in game_state.enemies)

            if (is_npc or is_enemy) and any(p.id == actor_char.id for p in game_state.party):
                is_hostile = True
                if is_npc:
                    is_hostile = target_char.data.get('hostile', False)

                if is_hostile:
                    log_debug(f"DEBUG: Triggering recursive counterattack from {target_char.name}")
                    # Recursively call self with depth incremented
                    # allow_counterattack=False prevents infinite loop logically, but recursion_depth ensures it structurally
                    await process_attack(
                        campaign_id,
                        target_char.id,
                        target_char.name,
                        actor_char.name,
                        sio,
                        db,
                        sid=sid,
                        allow_counterattack=False,
                        is_counterattack=True,
                        recursion_depth=recursion_depth + 1
                    )

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
    save_result = await save_message(campaign_id, sender_id, sender_name, content)

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

        async with AsyncSessionLocal() as db:
             move_result = await GameService.resolution_move(campaign_id, target_name, db)

             if move_result['success']:
                 # Emit updates
                 await sio.emit('game_state_update', move_result['game_state'].model_dump(), room=campaign_id)
                 await sio.emit('system_message', {'content': move_result['message']}, room=campaign_id)

                 # Trigger DM Narration
                 await sio.emit('typing_indicator', {'sender_id': 'dm', 'is_typing': True}, room=campaign_id)
                 try:
                    # Build Context
                    rich_context = await build_narrative_context(db, campaign_id, move_result['game_state'])
                    recent_history = await get_chat_history(campaign_id, limit=5, db=db)

                    narration = await AIService.generate_dm_narration(
                         campaign_id=campaign_id,
                         context=rich_context,
                         history=recent_history,
                         db=db,
                         sid=sid,
                         mode="move_narration"
                    )

                    if narration:
                        save_result = await save_message(campaign_id, 'dm', 'Dungeon Master', narration, db=db)
                        await sio.emit('chat_message', {
                            'sender_id': 'dm', 'sender_name': 'Dungeon Master', 'content': narration, 'id': save_result['id'], 'timestamp': save_result['timestamp']
                        }, room=campaign_id)
                 except Exception as e:
                     log_debug(f"Error during DM Narration for move: {e}")
                 await sio.emit('typing_indicator', {'sender_id': 'dm', 'is_typing': False}, room=campaign_id)

             else:
                 await sio.emit('system_message', {'content': move_result.get('message', "Move failed.")}, room=campaign_id)

        return

    # 4. Handle @attack command
    if content.strip().lower().startswith("@attack"):
        target_name = content.strip()[7:].strip()
        if not target_name:
             await sio.emit('system_message', {'content': "Usage: @attack <target_name>"}, room=campaign_id)
             return

        async with AsyncSessionLocal() as db:
             await process_attack(campaign_id, sender_id, sender_name, target_name, sio, db, sid=sid)
             await db.commit()
        return

    # 5. Handle @identify command
    if content.strip().lower().startswith("@identify"):
        target_name = content.strip()[9:].strip()
        if not target_name:
             await sio.emit('system_message', {'content': "Usage: @identify <target_name>"}, room=campaign_id)
             return

        async with AsyncSessionLocal() as db:
             result = await GameService.resolution_identify(campaign_id, sender_name, target_name, db)

             # Persist system message (The Roll)
             roll_msg = f"🔍 **{result.get('actor_name', sender_name)}** investigates **{result.get('target_name', target_name)}**.\n"
             roll_msg += f"**Roll:** {result.get('roll_detail', '?')} = **{result.get('roll_total', '?')}**"
             if result.get('success'):
                 roll_msg += " (SUCCESS)"
             else:
                 roll_msg += " (FAILURE)"

             save_result = await save_message(campaign_id, 'system', 'System', roll_msg, db=db)
             await sio.emit('chat_message', {
                'sender_id': 'system', 'sender_name': 'System', 'content': roll_msg, 'id': save_result['id'], 'timestamp': save_result['timestamp'], 'is_system': True
             }, room=campaign_id)

             # Trigger DM Narration
             await sio.emit('typing_indicator', {'sender_id': 'dm', 'is_typing': True}, room=campaign_id)
             try:
                 # Provide context to DM
                 outcome_context = roll_msg
                 if result.get('success'):
                     t_obj = result.get('target_object')
                     if hasattr(t_obj, 'name'):
                        outcome_context += f"\n[SYSTEM SECRET]: The target is truly {t_obj.name.upper()} ({getattr(t_obj, 'role', '')} {getattr(t_obj, 'race', '')})."

                 # Get recent history
                 recent_history = await get_chat_history(campaign_id, limit=5, db=db)

                 narration = await AIService.generate_dm_narration(
                     campaign_id=campaign_id,
                     context=outcome_context,
                     history=recent_history,
                     db=db,
                     sid=sid,
                     mode="identify_narration"
                 )

                 if narration:
                    save_result = await save_message(campaign_id, 'dm', 'Dungeon Master', narration, db=db)
                    await sio.emit('chat_message', {
                        'sender_id': 'dm', 'sender_name': 'Dungeon Master', 'content': narration, 'id': save_result['id'], 'timestamp': save_result['timestamp']
                    }, room=campaign_id)
             except Exception as e:
                 log_debug(f"DM Identify Error: {e}")

             await sio.emit('typing_indicator', {'sender_id': 'dm', 'is_typing': False}, room=campaign_id)

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

                save_result = await save_message(campaign_id, 'dm', 'Dungeon Master', response_text, db=db)
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
                        banter_history = await get_chat_history(campaign_id, limit=20, db=db)

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
                            save_result = await save_message(campaign_id, banter_char['id'], banter_char['name'], banter_response, db=db)

                            await sio.emit('chat_message', {
                                'sender_id': banter_char['id'],
                                'sender_name': banter_char['name'],
                                'content': banter_response,
                                'id': save_result['id'],
                                'timestamp': save_result['timestamp']
                            }, room=campaign_id)
                            log_debug(f"DEBUG: Banter response content: '{banter_response}'")

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
                        history = await get_chat_history(campaign_id, limit=20, db=db)

                        response_text = await AIService.generate_character_response(
                            campaign_id=campaign_id,
                            character=target_char,
                            history=history,
                            db=db,
                            sid=sid
                        )

                        if response_text:
                            save_result = await save_message(campaign_id, target_char['id'], target_char['name'], response_text, db=db)
                            await sio.emit('chat_message', {
                                'sender_id': target_char['id'],
                                'sender_name': target_char['name'],
                                'content': response_text,
                                'id': save_result['id'],
                                'timestamp': save_result['timestamp']
                            }, room=campaign_id)
                except Exception as e:
                     log_debug(f"Error in Mention generation: {e}")

                await sio.emit('typing_indicator', {'sender_id': target_char['id'], 'is_typing': False}, room=campaign_id)
