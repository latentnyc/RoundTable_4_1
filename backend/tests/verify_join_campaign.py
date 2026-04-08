import asyncio
import socketio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_join_campaign():
    sio = socketio.AsyncClient()
    
    events_received = []

    # Get existing campaign ID from DB
    from db.session import AsyncSessionLocal
    from sqlalchemy import text
    
    async def get_test_credentials():
        async with AsyncSessionLocal() as db:
            c_res = await db.execute(text("SELECT id FROM campaigns LIMIT 1"))
            c_row = c_res.mappings().fetchone()
            campaign_id = c_row['id'] if c_row else 'test-campaign-id'

            u_res = await db.execute(text("SELECT id FROM profiles LIMIT 1"))
            u_row = u_res.mappings().fetchone()
            user_id = u_row['id'] if u_row else 'test-user-id'
            return campaign_id, user_id

    campaign_id, user_id = await get_test_credentials()

    @sio.on('connect')
    async def on_connect():
        logger.info("Connected to server")
        logger.info(f"Emitting join_campaign for Campaign: {campaign_id}")
        await sio.emit('join_campaign', {
            'user_id': user_id,
            'campaign_id': campaign_id
        })

    @sio.on('system_message')
    async def on_system_message(data):
        logger.info(f"System message received: {data}")
        events_received.append('system_message')
        
    @sio.on('chat_history')
    async def on_chat_history(data):
        logger.info(f"Chat history received: {len(data)} messages")
        events_received.append('chat_history')

    @sio.on('debug_log')
    async def on_debug_log(data):
        events_received.append('debug_log')

    @sio.on('game_state_update')
    async def on_game_state_update(data):
        logger.info("State update received.")
        events_received.append('game_state_update')
        
    @sio.on('game_state_patch')
    async def on_game_state_patch(data):
        logger.info("State patch received.")
        events_received.append('game_state_patch')

    try:
        await sio.connect('http://localhost:8000', auth={'token': 'test_token'})
        await asyncio.sleep(6) # Wait for events to trickle in
        
        logger.info(f"Events received: {set(events_received)}")
        state_received = 'game_state_update' in events_received or 'game_state_patch' in events_received
        if 'system_message' in events_received and state_received and 'chat_history' in events_received:
             logger.info("Verification SUCCESS: Core connection events received.")
        else:
             logger.error("Verification FAILED: Missing expected connection events.")
             
    except Exception as e:
        logger.error(f"Error during connection test: {e}")
    finally:
        if sio.connected:
            await sio.disconnect()

if __name__ == '__main__':
    asyncio.run(test_join_campaign())
