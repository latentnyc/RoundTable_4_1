import socketio
import json
import logging
import traceback
from datetime import datetime
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from db.session import AsyncSessionLocal
from app.models import Player, Coordinates, GameState, Location
from app.socket.decorators import socket_event_handler
from app.services.chat_service import ChatService
from app.services.context_builder import build_narrative_context
from app.agents import get_dm_graph
from app.callbacks import SocketIOCallbackHandler
from langchain_core.messages import HumanMessage
from app.services.game_service import GameService
from app.services.state_service import StateService

logger = logging.getLogger(__name__)

@socket_event_handler
async def handle_join_campaign(sid, data, sio, connected_users):
    # data: { user_id, campaign_id, character_id }
    user_id = data.get('user_id')
    campaign_id = data.get('campaign_id')
    character_id = data.get('character_id')

    if not user_id or not campaign_id:
        return

    # Check if user is already in a different campaign room (Stuck Socket / Reuse)
    if sid in connected_users:
        old_data = connected_users[sid]
        old_campaign = old_data.get('campaign_id')
        if old_campaign and old_campaign != campaign_id:
            logger.info(f"[Socket] User {user_id} switching campaigns: Leaving {old_campaign}, Joining {campaign_id}")
            await sio.leave_room(sid, old_campaign)

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
            logger.info(f"[DEBUG] Found {len(char_rows)} characters for user {user_id}")

            for char_row in char_rows:
                try:
                    sheet_data = json.loads(char_row['sheet_data']) if char_row['sheet_data'] else {}
                except json.JSONDecodeError as e:
                    logger.warning(f"[DEBUG] Error parsing sheet_data for char {char_row['id']}: {e}")
                    sheet_data = {}

                # Safe Int Helpers
                def _safe_int(v, d):
                    try: return int(v)
                    except: return d

                hp_current = _safe_int(sheet_data.get('hpCurrent'), 10)
                hp_max = _safe_int(sheet_data.get('hpMax'), 10)
                speed = _safe_int(sheet_data.get('speed'), 30)
                level = _safe_int(char_row['level'], 1)
                xp = _safe_int(char_row['xp'], 0)
                
                # Derive AC & Initiative from Equipment + Stats
                dex_score = _safe_int(sheet_data.get('stats', {}).get('Dexterity'), 10)
                dex_mod = (dex_score - 10) // 2
                
                base_ac = 10
                shield_bonus = 0
                equipped_armor = None
                
                for item in sheet_data.get('equipment', []):
                    if isinstance(item, dict) and item.get('type') == 'Armor':
                        item_data = item.get('data', {})
                        if isinstance(item_data, dict) and item_data.get('type') == 'Shield':
                            ac_info_shield = item_data.get('armor_class', {})
                            shield_bonus = ac_info_shield.get('base', 2) if isinstance(ac_info_shield, dict) else 2
                        else:
                            equipped_armor = item
                            
                if isinstance(equipped_armor, dict):
                    ac_info = equipped_armor.get('data', {}).get('armor_class', {})
                    if isinstance(ac_info, dict):
                        base_ac = int(ac_info.get('base', 10))
                        if ac_info.get('dex_bonus'):
                            max_bonus = ac_info.get('max_bonus')
                            if max_bonus is not None and int(dex_mod) > int(max_bonus):
                                base_ac += int(max_bonus)
                            else:
                                base_ac += int(dex_mod)
                        else:
                            base_ac += int(dex_mod)
                    else:
                        base_ac += int(dex_mod)
                    
                derived_ac = int(base_ac) + int(shield_bonus)
                
                explicit_ac = sheet_data.get('ac')
                if explicit_ac is not None:
                     ac = _safe_int(explicit_ac, derived_ac)
                else:
                     ac = derived_ac
                
                initiative = _safe_int(sheet_data.get('initiative'), dex_mod)

                # Check control mode
                control_mode = str(char_row['control_mode']) if char_row.get('control_mode') else 'human'
                is_ai = bool(control_mode == 'ai')

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
                    role=char_row['role'] or "Unknown",
                    race=char_row['race'] or "Unknown",
                    level=level,
                    xp=xp,
                    sheet_data=sheet_data
                )
                players_to_sync.append(player_char)
                character_names.append(player_char.name)
                logger.info(f"[DEBUG] Synced character {player_char.name} ({player_char.id})")

            # 3. Load Game State (or init)
            game_state = await GameService.get_game_state(campaign_id, db)

            if game_state:
                # Fix for existing campaigns with generic default description
                if game_state.location.description == "A new adventure begins.":
                    logger.info("[DEBUG] Clearing generic default description for existing campaign.")
                    game_state.location.description = ""
            else:
                # Init new state
                game_state = GameState(
                    session_id=campaign_id,
                    location=Location(name="The Beginning", description=""), # Empty to prevent premature image gen
                    party=[]
                )

            # 4. Sync Characters

            # Map existing chars by ID
            existing_chars = {p.id: p for p in game_state.party}

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
                else:
                    # New character joining. Assign a spawn hex if available.
                    spawn_hexes = getattr(game_state.location, 'party_locations', [])
                    if spawn_hexes:
                        idx = len(game_state.party) % len(spawn_hexes)
                        spawn_data = spawn_hexes[idx].get('position', {})
                        if spawn_data:
                            new_p.position = Coordinates(
                                q=spawn_data.get('q', 0),
                                r=spawn_data.get('r', 0),
                                s=spawn_data.get('s', 0)
                            )

                game_state.party.append(new_p)

            # 4.5 Check for Fresh Campaign (Prevent Premature Image Gen)
            # If no chat messages exist and intro hasn't started, clear description so client waits for intro
            msg_check = await db.execute(text("SELECT 1 FROM chat_messages WHERE campaign_id = :cid LIMIT 1"), {"cid": campaign_id})
            msg_exists = msg_check.scalar()

            log_check = await db.execute(text("SELECT 1 FROM debug_logs WHERE campaign_id = :cid AND type = 'intro_start' LIMIT 1"), {"cid": campaign_id})
            intro_started = log_check.scalar()

            if not msg_exists and not intro_started:
                logger.info("[DEBUG] Fresh campaign detected. Clearing location description to prevent premature image generation.")
                game_state.location.description = ""

            # 5. Save Updated State
            # Ensure character JSON sheets capture the new spawn coordinates
            await StateService._save_party(game_state.party, campaign_id, db)

            await db.execute(
                text("INSERT INTO game_states (id, campaign_id, turn_index, phase, state_data) VALUES (:id, :campaign_id, :turn_index, :phase, :state_data)"),
                {"id": str(uuid4()), "campaign_id": campaign_id, "turn_index": game_state.turn_index, "phase": game_state.phase, "state_data": game_state.model_dump_json()}
            )
            await db.commit()

            # 5.5 Fetch & Emit AI Stats
            stats_res = await db.execute(
                text("SELECT total_input_tokens, total_output_tokens, query_count FROM campaigns WHERE id = :id"),
                {"id": campaign_id}
            )
            stats_row = stats_res.mappings().fetchone()
            if stats_row:
                 await sio.emit('ai_stats', {
                    'type': 'update',
                    'input_tokens': stats_row['total_input_tokens'] or 0,
                    'output_tokens': stats_row['total_output_tokens'] or 0,
                    'total_queries': stats_row['query_count'] or 0
                }, room=sid)

            # 6. Broadcast Update

            await StateService.emit_state_update(campaign_id, game_state, sio)

    except SQLAlchemyError as e:
        import traceback
        if 'db' in locals() and db is not None:
             await db.rollback()
        logger.error(f"Database error in join_campaign logic: {e}")
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
                'timestamp': row['created_at'].isoformat() if row['created_at'] else None,
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

        # Check if intro generation already started (prevent race condition)
        log_check = await db.execute(text("SELECT 1 FROM debug_logs WHERE campaign_id = :cid AND type = 'intro_start' LIMIT 1"), {"cid": campaign_id})
        intro_started = log_check.scalar()

        if not msg_exists and not intro_started:
            # Get API Key, Context, and Model
            key_res = await db.execute(text("SELECT api_key, model, system_prompt, description, template_id FROM campaigns WHERE id = :id"), {"id": campaign_id})
            camp_row = key_res.mappings().fetchone()

            if camp_row and camp_row['api_key']:
                api_key = camp_row['api_key']
                model_name = camp_row['model'] or "gemini-3-flash-preview"
                camp_description = camp_row['description'] or "A fantasy adventure."
                template_id = camp_row['template_id']

                # Try to claim the intro lock
                try:
                    await db.execute(
                        text("INSERT INTO debug_logs (id, campaign_id, type, content, created_at) VALUES (:id, :cid, 'intro_start', :msg, :now)"),
                        {"id": str(uuid4()), "cid": campaign_id, "msg": f"Starting generation with model: {model_name}", "now": datetime.utcnow()}
                    )
                    await db.commit()
                except SQLAlchemyError as e:
                    logger.warning(f"Intro start lock failed (likely race condition handled). Bailing out: {e}")
                    await db.rollback()
                    return

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
                    except SQLAlchemyError as ex:
                        logger.error(f"Error fetching starting NPC: {ex}")

                # Notify Users
                await sio.emit('typing_indicator', {'sender_id': 'dm', 'is_typing': True}, room=campaign_id)

                try:
                    # Construct Prompt
                    # We need the game state we just loaded/created

                    # Be specific about the location if we have it from GameState (which we should)
                    state_res = await db.execute(
                        text("SELECT id, state_data FROM game_states WHERE campaign_id = :campaign_id ORDER BY turn_index DESC, updated_at DESC LIMIT 1"),
                        {"campaign_id": campaign_id}
                    )
                    s_row = state_res.mappings().fetchone()
                    if s_row:
                        gs = GameState(**json.loads(s_row['state_data']))

                        rich_context = await build_narrative_context(db, campaign_id, gs)

                        opening_prompt = f"""
                        You are the Dungeon Master for a campaign described as: "{camp_description}"
                        The party has just gathered for the first time.

                        CAMPAIGN START
                        {rich_context}

                        {starting_npc_info if not gs.npcs else ""}

                        TASK:
                        1. Welcome the players to the campaign.
                        2. Describe the scene vividly, utilizing the location description, visible paths, and any interactables like doors.
                        3. Introduce/Acknowledge the party members present.
                        4. Introduce/Acknowledge any NPCs or enemies present.
                        5. Do NOT ask "What do you do?" or provide an immediate hook for action.
                        6. Simply set the scene and report who is present, letting the players soak in the atmosphere.

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
                            raw_content = final_state["messages"][-1].content

                            if isinstance(raw_content, list):
                                # Extract text from blocks (Google GenAI Multimodal format)
                                opening_text = "".join([block.get("text", "") for block in raw_content if isinstance(block, dict) and block.get("type") == "text"])
                                if not opening_text: # Fallback if structure is different
                                     opening_text = str(raw_content)
                            else:
                                opening_text = str(raw_content)

                            logger.info(f"[DEBUG] DM Intro Generated: {opening_text[:100]}...")

                            # Save & Emit Message
                            await ChatService.save_message(campaign_id, 'dm', 'Dungeon Master', opening_text)
                            await sio.emit('chat_message', {
                                'sender_id': 'dm',
                                'sender_name': 'Dungeon Master',
                                'content': opening_text,
                                'timestamp': 'Just now',
                                'message_type': 'narration'
                            }, room=campaign_id)

                            # Update Game State Location Description to match Intro
                            # This triggers the SceneVisPanel to generate the image based on the intro
                            gs.location.description = opening_text
                            logger.info(f"[DEBUG] Updated GameState location description to match intro.")

                            # Update DB
                            await db.execute(
                                text("UPDATE game_states SET state_data = :data WHERE id = :id"),
                                {"data": gs.model_dump_json(), "id": s_row['id']}
                            )
                            await db.commit()

                            # Emit Game State Update
                            await StateService.emit_state_update(campaign_id, gs, sio)

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
            except json.JSONDecodeError:
                full_content = str(row['full_content'])

            log_item = {
                'type': row['type'],
                'content': row['content'],
                'full_content': full_content,
                'timestamp': str(row['created_at'])
            }
            await sio.emit('debug_log', log_item, room=sid)
