import socketio
print("DEBUG: socket_manager imported socketio", flush=True)
from typing import Dict, List, Optional
import logging
import os
import json
from uuid import uuid4
print("DEBUG: socket_manager imports (stdlib) done", flush=True)

from sqlalchemy import text
print("DEBUG: socket_manager imported sqlalchemy", flush=True)

from db.session import AsyncSessionLocal
print("DEBUG: socket_manager imported db.session", flush=True)

from firebase_admin import auth as firebase_auth
print("DEBUG: socket_manager imported firebase_admin", flush=True)

# Store active connections: sid -> {user_id, campaign_id}
# In production, use Redis
connected_users: Dict[str, dict] = {}

print("DEBUG: socket_manager initializing AsyncServer...", flush=True)
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=[
        "http://localhost:3000", 
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://roundtable41-1dc2c.web.app",
        "https://roundtable41-1dc2c.firebaseapp.com"
    ]
)
print("DEBUG: socket_manager initialized AsyncServer", flush=True)

LOG_FILE = r"C:\Users\laten\Vibes\RoundTable_4_1\backend\debug_socket.log"

try:
    with open(LOG_FILE, "a") as f:
        f.write("Socket Manager Module Loaded\n")
except Exception as e:
    print(f"Failed to write log: {e}")

print("DEBUG: socket_manager module init done", flush=True)

@sio.event
async def connect(sid, environ, auth=None):
    with open(LOG_FILE, "a") as f:
        f.write(f"Connect attempt: {sid}\n")
        f.write(f"Auth data: {auth}\n")
    
    print(f"Client connecting: {sid}")
    
    if not auth or 'token' not in auth:
        with open(LOG_FILE, "a") as f:
            f.write(f"REJECTED {sid}: No token\n")
        print(f"Connection rejected: No token provided for {sid}")
        raise ConnectionRefusedError("Authentication failed: No token provided")
        
    token = auth['token']
    try:
        decoded_token = firebase_auth.verify_id_token(token)
        user_id = decoded_token['uid']
        print(f"Authorized user {user_id} on socket {sid}")
        with open("debug_socket.log", "a") as f:
            f.write(f"ACCEPTED {sid}: User {user_id}\n")
        
        # Store user_id in session for later use
        await sio.save_session(sid, {'user_id': user_id})
    except Exception as e:
        with open("debug_socket.log", "a") as f:
            f.write(f"REJECTED {sid}: Exception {e}\n")
        print(f"Connection rejected: Invalid token for {sid}. Error: {e}")
        raise ConnectionRefusedError("Authentication failed: Invalid token")

@sio.event
async def disconnect(sid):
    if sid in connected_users:
        user = connected_users[sid]
        print(f"Client disconnected: {sid} (User: {user.get('user_id')})")
        del connected_users[sid]

@sio.event
async def test_connection(sid, data=None):
    """
    Verifies the connection and returns context-aware details.
    """
    if sid not in connected_users:
        return {'status': 'error', 'message': 'Not authenticated'}
        
    user_data = connected_users[sid]
    user_id = user_data.get('user_id')
    campaign_id = user_data.get('campaign_id')
    
    response = {
        'status': 'online',
        'sid': sid,
        'user_name': 'Unknown',
        'campaign_name': 'Unknown',
        'character_name': 'None (Spectator/DM)'
    }
    
    try:
        async with AsyncSessionLocal() as db:
            # 1. Get User Name
            result = await db.execute(text("SELECT username FROM profiles WHERE id = :id"), {"id": user_id})
            row = result.mappings().fetchone()
            if row:
                response['user_name'] = row['username']
                
            # 2. Get Campaign Name
            result = await db.execute(text("SELECT name FROM campaigns WHERE id = :id"), {"id": campaign_id})
            row = result.mappings().fetchone()
            if row:
                response['campaign_name'] = row['name']
                
            # 3. Get Character Name (if applicable)
            result = await db.execute(
                text("SELECT name FROM characters WHERE user_id = :user_id AND campaign_id = :campaign_id AND control_mode != 'disabled'"),
                {"user_id": user_id, "campaign_id": campaign_id}
            )
            rows = result.mappings().all()
            if rows:
                names = [r['name'] for r in rows]
                response['character_name'] = ", ".join(names)
                
    except Exception as e:
        print(f"Error in test_connection: {e}")
        response['status'] = 'partial_error'
        response['error'] = str(e)
        import traceback
        traceback.print_exc()
        
    return response

@sio.event
async def join_campaign(sid, data):
    # data: { user_id, campaign_id, character_id }
    user_id = data.get('user_id')
    campaign_id = data.get('campaign_id')
    
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
            from .models import Player, Coordinates
            
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
            
            from .models import GameState, Location
            
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
            # Note: We should probably UPDATE the existing latest state if it hasn't changed turn, 
            # OR insert a new one. For now, inserting ensures history.
            await db.execute(
                text("INSERT INTO game_states (id, campaign_id, turn_index, phase, state_data) VALUES (:id, :campaign_id, :turn_index, :phase, :state_data)"),
                {"id": str(uuid4()), "campaign_id": campaign_id, "turn_index": game_state.turn_index, "phase": game_state.phase, "state_data": game_state.model_dump_json()}
            )
            await db.commit()
            
            # 6. Broadcast Update
            print(f"Broadcasting Game State Update with {len(game_state.party)} players")
            await sio.emit('game_state_update', game_state.model_dump(), room=campaign_id)

    except Exception as e:
        print(f"Error in join_campaign logic: {e}")
        import traceback
        traceback.print_exc()

    joined_names = ", ".join(character_names) if character_names else "Spectator"
    await sio.emit('system_message', {
        'content': f"{username} joined with: {joined_names}"
    }, room=campaign_id)
    
    print(f"User {username} ({user_id}) joined campaign {campaign_id}")

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

@sio.event
async def clear_chat(sid):
    if sid not in connected_users:
        return
        
    user_data = connected_users[sid]
    campaign_id = user_data['campaign_id']
    user_id = user_data['user_id']
    
    print(f"Clearing chat for campaign {campaign_id} requested by {user_id}")
    
    async with AsyncSessionLocal() as db:
        await db.execute(text("DELETE FROM chat_messages WHERE campaign_id = :campaign_id"), {"campaign_id": campaign_id})
        await db.commit()
        
    await sio.emit('chat_cleared', {}, room=campaign_id)
    await sio.emit('system_message', {'content': "Chat history has been cleared."}, room=campaign_id)

@sio.event
async def clear_debug_logs(sid):
    if sid not in connected_users:
        return
        
    user_data = connected_users[sid]
    campaign_id = user_data['campaign_id']
    user_id = user_data['user_id']
    
    print(f"Clearing debug logs for campaign {campaign_id} requested by {user_id}")
    
    async with AsyncSessionLocal() as db:
        await db.execute(text("DELETE FROM debug_logs WHERE campaign_id = :campaign_id"), {"campaign_id": campaign_id})
        await db.commit()
        
    await sio.emit('debug_logs_cleared', {}, room=campaign_id)


from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

async def save_message(campaign_id: str, sender_id: str, sender_name: str, content: str):
    async with AsyncSessionLocal() as db:
        msg_id = str(uuid4())
        await db.execute(
            text("""INSERT INTO chat_messages (id, campaign_id, sender_id, sender_name, content) 
               VALUES (:id, :campaign_id, :sender_id, :sender_name, :content)"""),
            {"id": msg_id, "campaign_id": campaign_id, "sender_id": sender_id, "sender_name": sender_name, "content": content}
        )
        await db.commit()

async def get_chat_history(campaign_id: str, limit: int = 10):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("""SELECT * FROM chat_messages 
               WHERE campaign_id = :campaign_id 
               ORDER BY created_at DESC 
               LIMIT :limit"""),
            {"campaign_id": campaign_id, "limit": limit}
        )
        rows = result.mappings().all()
        
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

def log_debug(message):
    import re
    sanitized_message = re.sub(r"('api_key':\s*')[^']+'", r"\1REDACTED'", str(message))
    sanitized_message = re.sub(r'("api_key":\s*")[^"]+"', r'\1REDACTED"', sanitized_message)
    try:
        with open("debug_chat.log", "a") as f:
            import datetime
            timestamp = datetime.datetime.now().isoformat()
            f.write(f"[{timestamp}] {sanitized_message}\n")
    except Exception as e:
        print(f"Failed to log: {e}")
    print(message, flush=True)

@sio.event
async def chat_message(sid, data):
    log_debug(f"Received chat_message from {sid}: {data}")
    
    session = await sio.get_session(sid)
    if not session:
        log_debug(f"No session for {sid}")
        return

    user_id = session.get('user_id')
    user_data = connected_users.get(sid)
    if not user_data:
        log_debug(f"User data not found for sid {sid}")
        return

    campaign_id = user_data['campaign_id']
    content = data.get('content')
    sender_name = data.get('sender_name') or 'Player' 
    sender_id = data.get('sender_id') or user_id 
    
    # 1. Save User Message
    await save_message(campaign_id, sender_id, sender_name, content)
    
    # 2. Broadcast to room
    await sio.emit('chat_message', {
        'sender_id': sender_id,
        'sender_name': sender_name,
        'content': content,
        'timestamp': 'Just now'
    }, room=campaign_id)
    
    # 3. Trigger DM
    if "@dm" in content.lower():
        await sio.emit('typing_indicator', {'sender_id': 'dm', 'is_typing': True}, room=campaign_id)
        
        try:
            from .callbacks import SocketIOCallbackHandler
            
            async with AsyncSessionLocal() as db:
                result = await db.execute(text("SELECT api_key FROM campaigns WHERE id = :id"), {"id": campaign_id})
                row = result.mappings().fetchone()
                campaign_api_key = row["api_key"] if row else None
                log_debug(f"DEBUG: Retrieved API Key for campaign {campaign_id}: {campaign_api_key[:10] if campaign_api_key else 'None'}...")

            history = await get_chat_history(campaign_id, limit=20)
            
            inputs = {
                "messages": history, 
                "campaign_id": campaign_id,
                "sender_name": sender_name,
                "api_key": data.get('api_key'),
                "model_name": data.get('model_name')
            }
            
            if not campaign_api_key:
                response_text = "The Campaign GM needs to configure an API Key in Campaign Settings for the AI to function."
            else:
                from app.agents import get_dm_graph
                requested_model = data.get('model_name') or 'gemini-2.0-flash'
                dm_graph, error_msg = get_dm_graph(api_key=campaign_api_key, model_name=requested_model)
                
                if not dm_graph:
                     response_text = f"DM Agent is offline (Initialization Failed: {error_msg})."
                else:
                    callback_handler = SocketIOCallbackHandler(sid, campaign_id, agent_name="Dungeon Master")
                    config = {"callbacks": [callback_handler]}
                    log_debug(f"DEBUG: Calling dm_graph.ainvoke with config: {config}")
                    
                    final_state = await dm_graph.ainvoke(inputs, config=config)
                    ai_msg = final_state["messages"][-1]
                    response_text = ai_msg.content
            
            await save_message(campaign_id, 'dm', 'Dungeon Master', response_text)

            await sio.emit('chat_message', {
                'sender_id': 'dm',
                'sender_name': 'Dungeon Master',
                'content': response_text,
                'timestamp': 'Just now'
            }, room=campaign_id)
            log_debug(f"DEBUG: Successfully sent DM response to campaign {campaign_id}")

            # --- BANTER LOGIC ---
            import random
            
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    text("SELECT state_data FROM game_states WHERE campaign_id = :campaign_id ORDER BY turn_index DESC, updated_at DESC LIMIT 1"), 
                    {"campaign_id": campaign_id}
                )
                state_row = result.mappings().fetchone()
                
                ai_characters = []
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
                    
                    char_details = {
                        "name": banter_char['name'],
                        "race": banter_char.get('race', 'Unknown'),
                        "role": banter_char.get('role', 'Unknown'),
                        "character_id": banter_char['id']
                    }
                    sheet_data = banter_char.get('sheet_data', {})
                    char_details['background'] = sheet_data.get('background', 'Unknown')
                    char_details['alignment'] = sheet_data.get('alignment', 'Neutral')

                    banter_instruction = HumanMessage(content=f"""
                    [System] The Dungeon Master just said: "{response_text}"
                    
                    React to this statement. 
                    - Make a short, in-character quip, comment, or observation.
                    - Do NOT be repetitive. 
                    - If the DM was describing danger, be on guard. 
                    - If the DM was funny, laugh.
                    - Keep it under 2 sentences.
                    """)
                    
                    from app.agents import get_character_graph
                    requested_model = data.get('model_name', 'gemini-2.0-flash')
                    
                    banter_history = await get_chat_history(campaign_id, limit=20)

                    char_agent = get_character_graph(api_key=campaign_api_key, model_name=requested_model, character_details=char_details)
                    
                    if char_agent:
                        banter_inputs = {
                            "messages": banter_history + [banter_instruction],
                            "campaign_id": campaign_id,
                            "sender_name": "System" 
                        }
                        
                        log_debug(f"DEBUG: Invoking char agent with {len(banter_inputs['messages'])} messages")
                        
                        from app.callbacks import SocketIOCallbackHandler
                        callback_handler = SocketIOCallbackHandler(sid, campaign_id, agent_name=banter_char['name'])
                        config = {"callbacks": [callback_handler]}

                        final_state = await char_agent.ainvoke(banter_inputs, config=config)
                        last_msg = final_state["messages"][-1]
                        banter_response = last_msg.content
                        
                        await save_message(campaign_id, banter_char['id'], banter_char['name'], banter_response)
                        
                        await sio.emit('chat_message', {
                            'sender_id': banter_char['id'],
                            'sender_name': banter_char['name'],
                            'content': banter_response,
                            'timestamp': 'Just now'
                        }, room=campaign_id)
                        log_debug(f"DEBUG: Banter response content: '{banter_response}'")

                except Exception as e:
                    log_debug(f"Error in Banter generation: {e}")
                    import traceback
                    traceback.print_exc()

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
                    char_details = {
                        "name": target_char['name'],
                        "race": target_char.get('race', 'Unknown'),
                        "role": target_char.get('role', 'Unknown'),
                    }
                    
                    sheet_data = target_char.get('sheet_data', {})
                    char_details['background'] = sheet_data.get('background', 'Unknown')
                    char_details['alignment'] = sheet_data.get('alignment', 'Neutral')
                    
                    async with AsyncSessionLocal() as db:
                        result = await db.execute(text("SELECT api_key FROM campaigns WHERE id = :id"), {"id": campaign_id})
                        row = result.mappings().fetchone()
                        campaign_api_key = row["api_key"] if row else None
                        
                    if not campaign_api_key:
                        log_debug("DEBUG: No Campaign API Key found, cannot generate AI response.")
                        continue  
                        
                    history = await get_chat_history(campaign_id, limit=20)
                    
                    inputs = {
                        "messages": history,
                        "campaign_id": campaign_id,
                        "sender_name": sender_name
                    }
                    
                    from app.agents import get_character_graph
                    requested_model = data.get('model_name') or 'gemini-2.0-flash'
                    char_agent = get_character_graph(api_key=campaign_api_key, model_name=requested_model, character_details=char_details)
                    
                    if char_agent:
                        from app.callbacks import SocketIOCallbackHandler
                        callback_handler = SocketIOCallbackHandler(sid, campaign_id, agent_name=target_char['name'])
                        config = {"callbacks": [callback_handler]}

                        final_state = await char_agent.ainvoke(inputs, config=config)
                        response_text = final_state["messages"][-1].content
                        
                        await save_message(campaign_id, target_char['id'], target_char['name'], response_text)
                        
                        await sio.emit('chat_message', {
                            'sender_id': target_char['id'],
                            'sender_name': target_char['name'],
                            'content': response_text,
                            'timestamp': 'Just now'
                        }, room=campaign_id)
                    else:
                        log_debug("DEBUG: Failed to initialize/compile character agent graph.")
                    
                except Exception as e:
                    log_debug(f"Error in AI Character response: {e}")
                    import traceback
                    traceback.print_exc()
                    
                await sio.emit('typing_indicator', {'sender_id': target_char['id'], 'is_typing': False}, room=campaign_id)
