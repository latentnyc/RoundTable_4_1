import socketio

from typing import Dict, List, Optional
import os
import json
from uuid import uuid4

# Import Handlers
from app.socket.handlers import connection, chat, game_state, inventory


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


# Store active connections: sid -> {user_id, campaign_id}
# In production, use Redis
connected_users: Dict[str, dict] = {}

@sio.event
async def connect(sid, environ, auth=None):
    try:
        user_id, decoded_token = await connection.handle_connect(sid, environ, auth, connected_users)
        # Store user_id in session for later use
        await sio.save_session(sid, {'user_id': user_id})
    except Exception as e:
        # handle_connect raises ConnectionRefusedError on auth failure
        raise e

@sio.event
async def disconnect(sid):
    await connection.handle_disconnect(sid, connected_users)

@sio.event
async def test_connection(sid, data=None):
    return await connection.handle_test_connection(sid, connected_users)

@sio.event
async def join_campaign(sid, data):
    await game_state.handle_join_campaign(sid, data, sio, connected_users)

@sio.event
async def chat_message(sid, data):
    await chat.handle_chat_message(sid, data, sio, connected_users)

@sio.event
async def clear_chat(sid):
    await chat.handle_clear_chat(sid, sio, connected_users)

@sio.event
async def take_items(sid, data):
    await inventory.handle_take_items(sid, data, sio, connected_users)

@sio.event
async def equip_item(sid, data):
    await inventory.handle_equip_item(sid, data, sio, connected_users)

@sio.event
async def clear_debug_logs(sid):
    await chat.handle_clear_logs(sid, sio, connected_users)
