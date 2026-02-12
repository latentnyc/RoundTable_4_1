import socketio
import json
import logging
import traceback
from datetime import datetime
from uuid import uuid4
from sqlalchemy import text
from db.session import AsyncSessionLocal
from app.models import Player, Coordinates, GameState, Location
from app.socket.decorators import socket_event_handler
from app.socket.handlers.chat import save_message
from app.agents import get_dm_graph
from app.callbacks import SocketIOCallbackHandler
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)

@socket_event_handler
async def handle_join_campaign(sid, data, sio, connected_users):
    # data: { user_id, campaign_id, character_id }
    user_id = data.get('user_id')
    campaign_id = data.get('campaign_id')
    character_id = data.get('character_id')

    if not user_id or not campaign_id:
        return

    # Store session info
    connected_users[sid] = data

    # Join the socket room specific to this campaign
    await sio.enter_room(sid, campaign_id)

    # Fetch username
    username = str(user_id)
    character_names = []

    try:
        async with AsyncSessionLocal() as db:
            # 1. Get Username
            result = await db.execute(text("SELECT username FROM profiles WHERE id = :id"), {"id": user_id})
            row = result.mappings().fetchone()
            if row:
                username = row["username"]

            # 2. Get All User Characters where control_mode != 'disabled' AND belong to this campaign
            result = await db.execute(
                text("SELECT * FROM characters WHERE user_id = :user_id AND campaign_id = :campaign_id AND (control_mode IS NULL OR control_mode != 'disabled')"),
                {"user_id": user_id, "campaign_id": campaign_id}
            )
            char_rows = result.mappings().all()

            players_to_sync = []

            for char_row in char_rows:
                try:
                    sheet_data = json.loads(char_row['sheet_data']) if char_row['sheet_data'] else {}
                except json.JSONDecodeError:
                    sheet_data = {}

                # Determine AI status
                control_mode = char_row['control_mode'] if 'control_mode' in char_row and char_row['control_mode'] else 'human'
                is_ai = (control_mode == 'ai')

                # Ensure defaults for sheet data with type safety
                def safe_int(val, default):
                    try:
                        return int(val)
                    except (ValueError, TypeError):
                        return default

                hp_current = safe_int(sheet_data.get('hpCurrent'), 10)
                hp_max = safe_int(sheet_data.get('hpMax'), 10)
                ac = safe_int(sheet_data.get('ac'), 10)
                speed = safe_int(sheet_data.get('speed'), 30)

                # Safe access to DB columns
                role = char_row['role'] or "Unknown"
                race = char_row['race'] or "Unknown"
                level = safe_int(char_row['level'], 1)
                xp = safe_int(char_row['xp'], 0)

                player_char = Player(
                    id=char_row['id'],
                    user_id=str(user_id),
                    name=char_row['name'] or "Unnamed",
                    is_ai=is_ai,
                    control_mode=control_mode,
                    hp_current=hp_current,
                    hp_max=hp_max,
                    ac=ac,
                    initiative=0,
                    speed=speed,
                    position=Coordinates(q=0, r=0, s=0),
                    role=role,
                    race=race,
                    level=level,
                    xp=xp,
                    sheet_data=sheet_data
                )
                players_to_sync.append(player_char)
                character_names.append(player_char.name)

            # 3. Load Game State (or init)
            result = await db.execute(
                text("SELECT state_data FROM game_states WHERE campaign_id = :campaign_id ORDER BY turn_index DESC, updated_at DESC LIMIT 1"),
                {"campaign_id": campaign_id}
            )
            state_row = result.mappings().fetchone()

            if state_row:
                game_state = GameState(**json.loads(state_row['state_data']))
            else:
                # Init new state
                game_state = GameState(
                    session_id=campaign_id,
                    location=Location(name="The Beginning", description="A new adventure begins."),
                    party=[]
                )

            # 4. Sync Characters

            # Map existing chars by ID
            existing_chars = {p.id: p for p in game_state.party if str(p.user_id) == str(user_id)}

            # Clear user's chars from party list
            game_state.party = [p for p in game_state.party if str(p.user_id) != str(user_id)]

            for new_p in players_to_sync:
                if new_p.id in existing_chars:
                    old_p = existing_chars[new_p.id]
                    # Preserve transient state
                    new_p.hp_current = old_p.hp_current
                    new_p.position = old_p.position
                    new_p.status_effects = old_p.status_effects
                    new_p.initiative = old_p.initiative

                game_state.party.append(new_p)

            # 5. Save Updated State
            await db.execute(
                text("INSERT INTO game_states (id, campaign_id, turn_index, phase, state_data) VALUES (:id, :campaign_id, :turn_index, :phase, :state_data)"),
                {"id": str(uuid4()), "campaign_id": campaign_id, "turn_index": game_state.turn_index, "phase": game_state.phase, "state_data": game_state.model_dump_json()}
            )
            await db.commit()

            # 6. Broadcast Update

            await sio.emit('game_state_update', game_state.model_dump(), room=campaign_id)

    except Exception as e:
        logger.error(f"Error in join_campaign logic: {e}")
        logger.error(traceback.format_exc())

    joined_names = ", ".join(character_names) if character_names else "Spectator"
    await sio.emit('system_message', {
        'content': f"{username} joined with: {joined_names}"
    }, room=campaign_id)



    # We also need to send chat history and debug logs
    # This was originally in socket_manager.join_campaign
    # We should probably keep it here or call a helper

    # Send existing chat history
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("""SELECT * FROM chat_messages
               WHERE campaign_id = :campaign_id
               ORDER BY created_at ASC"""),
            {"campaign_id": campaign_id}
        )
        rows = result.mappings().all()

        history_data = []
        for row in rows:
            if "DM Agent is offline" in row["content"] or "The DM is confused" in row["content"]:
                continue

            history_data.append({
                'sender_id': row['sender_id'],
                'sender_name': row['sender_name'],
                'content': row['content'],
                'timestamp': row['created_at'],
                'is_system': row['sender_id'] == 'system'
            })

        await sio.emit('chat_history', history_data, room=sid)

    # 7. Check for Opening Scene Trigger (If chat is empty)
    # We do this AFTER sending history so the user sees the new message appear live (or we append it to history if we did it before, but async logic suggests we can just emit it)
    # Only the FIRST user to join effectively triggers this if they are close together, but we need a lock or just rely on the DB check.
    # The DB check inside the async block should be reasonably safe if we check again.

    # 7. Check for Opening Scene Trigger (If chat is empty)
    async with AsyncSessionLocal() as db:
        # Check if messages exist
        msg_check = await db.execute(text("SELECT 1 FROM chat_messages WHERE campaign_id = :cid LIMIT 1"), {"cid": campaign_id})
        msg_exists = msg_check.scalar()

        # Log check
        await db.execute(
            text("INSERT INTO debug_logs (id, campaign_id, type, content, created_at) VALUES (:id, :cid, 'intro_check', :msg, :now)"),
            {"id": str(uuid4()), "cid": campaign_id, "msg": f"Checking intro. Chat exists: {msg_exists}", "now": datetime.utcnow()}
        )
        await db.commit()

        if not msg_exists:
            # Get API Key, Context, and Model
            key_res = await db.execute(text("SELECT api_key, model, system_prompt, description, template_id FROM campaigns WHERE id = :id"), {"id": campaign_id})
            camp_row = key_res.mappings().fetchone()

            if camp_row and camp_row['api_key']:
                api_key = camp_row['api_key']
                model_name = camp_row['model'] or "gemini-2.0-flash"
                camp_description = camp_row['description'] or "A fantasy adventure."
                template_id = camp_row['template_id']

                await db.execute(
                    text("INSERT INTO debug_logs (id, campaign_id, type, content, created_at) VALUES (:id, :cid, 'intro_start', :msg, :now)"),
                    {"id": str(uuid4()), "cid": campaign_id, "msg": f"Starting generation with model: {model_name}", "now": datetime.utcnow()}
                )
                await db.commit()

                # Try to get Starting NPC from Template
                starting_npc_info = ""
                if template_id:
                    try:
                        t_res = await db.execute(text("SELECT config FROM campaign_templates WHERE id = :tid"), {"tid": template_id})
                        t_row = t_res.mappings().fetchone()
                        if t_row and t_row['config']:
                            t_config = json.loads(t_row['config'])
                            start_npc_id = t_config.get('starting_npc')

                            if start_npc_id:
                                n_res = await db.execute(text("SELECT name, role FROM npcs WHERE campaign_id = :cid AND source_id = :sid"), {"cid": campaign_id, "sid": start_npc_id})
                                n_row = n_res.mappings().fetchone()
                                if n_row:
                                    starting_npc_info = f"\nStarting NPC nearby: {n_row['name']} ({n_row['role']})."
                    except Exception as ex:
                        logger.error(f"Error fetching starting NPC: {ex}")

                # Notify Users
                await sio.emit('typing_indicator', {'sender_id': 'dm', 'is_typing': True}, room=campaign_id)

                try:
                    # Construct Prompt
                    # We need the game state we just loaded/created

                    # Be specific about the location if we have it from GameState (which we should)
                    state_res = await db.execute(
                        text("SELECT state_data FROM game_states WHERE campaign_id = :campaign_id ORDER BY turn_index DESC LIMIT 1"),
                        {"campaign_id": campaign_id}
                    )
                    s_row = state_res.mappings().fetchone()
                    if s_row:
                        gs = GameState(**json.loads(s_row['state_data']))

                        location_txt = f"{gs.location.name}: {gs.location.description}"
                        party_txt = ", ".join([p.name for p in gs.party])

                        opening_prompt = f"""
                        You are the Dungeon Master for a campaign described as: "{camp_description}"
                        The party has just gathered for the first time.

                        CAMPAIGN START
                        Location: {location_txt}
                        Party: {party_txt}
                        {starting_npc_info}

                        TASK:
                        1. Welcome the players to the campaign.
                        2. Describe the scene vividly, utilizing the location description and the mood.
                        3. Introduce the starting NPC ({starting_npc_info.strip() if starting_npc_info else "a local"}) if applicable, or have them approach the party.
                        4. Do NOT ask "What do you do?" or provide an immediate hook for action.
                        5. Simply set the scene and letting the players soak in the atmosphere.

                        Keep it under 2 paragraphs. Be atmospheric and immersive.
                        """

                        dm_graph, err = get_dm_graph(api_key=api_key, model_name=model_name)
                        if dm_graph:
                            await db.execute(
                                text("INSERT INTO debug_logs (id, campaign_id, type, content, created_at) VALUES (:id, :cid, 'intro_graph', 'Graph initialized', :now)"),
                                {"id": str(uuid4()), "cid": campaign_id, "now": datetime.utcnow()}
                            )
                            await db.commit()

                            # Use a temporary callback handler tied to the campaign room (or just this user? Room is better)
                            # But we don't have a specific SID for the DM, using the triggering user's SID for callback info is okay?
                            # Actually we want to broadcast to room. The handler supports room.
                            # We pass 'sid' just for logging/connection tracking usually.

                            cb = SocketIOCallbackHandler(sid, campaign_id, agent_name="Dungeon Master")
                            config = {"callbacks": [cb]}

                            inputs = {
                                "messages": [HumanMessage(content=opening_prompt)],
                                "campaign_id": campaign_id,
                                "sender_name": "System"
                            }

                            final_state = await dm_graph.ainvoke(inputs, config=config)
                            opening_text = final_state["messages"][-1].content

                            # Save & Emit
                            await save_message(campaign_id, 'dm', 'Dungeon Master', opening_text)
                            await sio.emit('chat_message', {
                                'sender_id': 'dm',
                                'sender_name': 'Dungeon Master',
                                'content': opening_text,
                                'timestamp': 'Just now'
                            }, room=campaign_id)

                            await db.execute(
                                text("INSERT INTO debug_logs (id, campaign_id, type, content, created_at) VALUES (:id, :cid, 'intro_success', 'Message sent', :now)"),
                                {"id": str(uuid4()), "cid": campaign_id, "now": datetime.utcnow()}
                            )
                            await db.commit()
                        else:
                            await db.execute(
                                text("INSERT INTO debug_logs (id, campaign_id, type, content, created_at) VALUES (:id, :cid, 'intro_error', :err, :now)"),
                                {"id": str(uuid4()), "cid": campaign_id, "err": f"Graph Init Failed: {err}", "now": datetime.utcnow()}
                            )
                            await db.commit()

                except Exception as e:
                    import traceback
                    tb = traceback.format_exc()
                    await db.execute(
                        text("INSERT INTO debug_logs (id, campaign_id, type, content, created_at) VALUES (:id, :cid, 'intro_exception', :err, :now)"),
                        {"id": str(uuid4()), "cid": campaign_id, "err": str(e) + "\n" + tb, "now": datetime.utcnow()}
                    )
                    await db.commit()

                await sio.emit('typing_indicator', {'sender_id': 'dm', 'is_typing': False}, room=campaign_id)
            else:
                await db.execute(
                    text("INSERT INTO debug_logs (id, campaign_id, type, content, created_at) VALUES (:id, :cid, 'intro_skip', 'No API Key', :now)"),
                    {"id": str(uuid4()), "cid": campaign_id, "now": datetime.utcnow()}
                )
                await db.commit()


    # Send existing debug logs
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("""SELECT * FROM debug_logs
               WHERE campaign_id = :campaign_id
               ORDER BY created_at ASC"""),
            {"campaign_id": campaign_id}
        )
        rows = result.mappings().all()

        for row in rows:
            try:
                full_content = json.loads(row['full_content']) if row['full_content'] else None
            except:
                full_content = str(row['full_content'])

            log_item = {
                'type': row['type'],
                'content': row['content'],
                'full_content': full_content,
                'timestamp': row['created_at']
            }
            await sio.emit('debug_log', log_item, room=sid)
