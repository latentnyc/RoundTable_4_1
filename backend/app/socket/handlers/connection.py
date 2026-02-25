import socketio
import logging
from firebase_admin import auth as firebase_auth
from sqlalchemy import text
from db.session import AsyncSessionLocal
from app.socket.decorators import socket_event_handler

logger = logging.getLogger(__name__)

# We will need a way to reference the main `sio` instance or pass it context
# But handlers are usually registered to `sio`.
# We'll define functions that take `sid` and `data` and uses a shared context for `connected_users`.

@socket_event_handler
async def handle_connect(sid, environ, auth, connected_users):


    if not auth or 'token' not in auth:

        raise ConnectionRefusedError("Authentication failed: No token provided")

    token = auth['token']
    try:
        decoded_token = firebase_auth.verify_id_token(token)
        user_id = decoded_token['uid']


        # We don't have sio session yet, but return user_id to be stored
        return user_id, decoded_token
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        raise ConnectionRefusedError("Authentication failed: Invalid token")

@socket_event_handler
async def handle_disconnect(sid, connected_users):
    if sid in connected_users:
        user = connected_users[sid]

        del connected_users[sid]

@socket_event_handler
async def handle_test_connection(sid, connected_users):
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
            if user_id:
                result = await db.execute(text("SELECT username FROM profiles WHERE id = :id"), {"id": user_id})
                row = result.mappings().fetchone()
                if row: response['user_name'] = row['username']

            if campaign_id:
                result = await db.execute(text("SELECT name FROM campaigns WHERE id = :id"), {"id": campaign_id})
                row = result.mappings().fetchone()
                if row: response['campaign_name'] = row['name']

                # Get Character Name
                if user_id:
                    result = await db.execute(
                        text("SELECT name FROM characters WHERE user_id = :user_id AND campaign_id = :campaign_id AND control_mode != 'disabled'"),
                        {"user_id": user_id, "campaign_id": campaign_id}
                    )
                    rows = result.mappings().all()
                    if rows:
                        names = [r['name'] for r in rows]
                        response['character_name'] = ", ".join(names)

    except Exception as e:
        logger.error(f"Error in test_connection: {e}")
        response['status'] = 'partial_error'
        response['error'] = str(e)

    return response
