import logging
import json
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from db.session import AsyncSessionLocal
from app.models import Player, Coordinates, GameState, Location
from app.services.state_service import StateService
from app.utils.entity_utils import EntityUtils
from app.services.narrator_service import NarratorService

logger = logging.getLogger(__name__)

class ConnectionService:
    @staticmethod
    async def process_user_join(campaign_id: str, user_id: str, sid: str, sio, connected_users=None):
        """
        Handles the heavy lifting of a user joining a campaign.
        Fetches characters, updates game state, sends history, and triggers intro if needed.
        """
        username = str(user_id)
        character_names = []
        
        try:
            async with AsyncSessionLocal() as db:
                # 1. Get Username
                result = await db.execute(text("SELECT username FROM profiles WHERE id = :id"), {"id": user_id})
                row = result.mappings().fetchone()
                if row:
                    username = row["username"]

                # 2. Get User Characters
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

                    stats = EntityUtils.derive_character_stats(sheet_data)
                    level = EntityUtils._safe_int(char_row['level'], 1)
                    xp = EntityUtils._safe_int(char_row['xp'], 0)

                    control_mode = str(char_row['control_mode']) if char_row.get('control_mode') else 'human'
                    is_ai = bool(control_mode == 'ai')

                    player_char = Player(
                        id=char_row['id'],
                        user_id=str(user_id),
                        name=char_row['name'] or "Unnamed",
                        is_ai=is_ai,
                        control_mode=control_mode,
                        hp_current=stats['hp_current'],
                        hp_max=stats['hp_max'],
                        ac=stats['ac'],
                        initiative=0,
                        speed=stats['speed'],
                        position=Coordinates(q=0, r=0, s=0),
                        role=char_row['role'] or "Unknown",
                        race=char_row['race'] or "Unknown",
                        level=level,
                        xp=xp,
                        sheet_data=sheet_data
                    )
                    players_to_sync.append(player_char)
                    character_names.append(player_char.name)

                # 3. Load or Init Game State
                game_state = await StateService.get_game_state(campaign_id, db)
                if game_state:
                    if game_state.location.description == "A new adventure begins.":
                        game_state.location.description = ""
                else:
                    game_state = GameState(
                        session_id=campaign_id,
                        location=Location(name="The Beginning", description=""),
                        party=[]
                    )

                # 4. Sync Characters into Party
                EntityUtils.splice_players_into_party(game_state, players_to_sync, user_id)

                # 4.5 Check for Fresh Campaign
                msg_check = await db.execute(text("SELECT 1 FROM chat_messages WHERE campaign_id = :cid LIMIT 1"), {"cid": campaign_id})
                msg_exists = msg_check.scalar()

                log_check = await db.execute(text("SELECT 1 FROM debug_logs WHERE campaign_id = :cid AND type = 'intro_start' LIMIT 1"), {"cid": campaign_id})
                intro_started = log_check.scalar()

                if not msg_exists and not intro_started:
                    game_state.location.description = ""

                # 5. Save Updated State
                await StateService.save_game_state(campaign_id, game_state, db)
                await db.commit()
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
            if 'db' in locals() and db is not None:
                 await db.rollback()
            logger.error(f"Database error in join_campaign logic: {e}")

        # Broadcast Join Message
        joined_names = ", ".join(character_names) if character_names else "Spectator"
        await sio.emit('system_message', {
            'content': f"{username} joined with: {joined_names}"
        }, room=campaign_id)
        
        # 6. Push Full Initial State directly to this specific connecting user
        if 'game_state' in locals() and game_state:
            await StateService.emit_initial_state(campaign_id, game_state, sio, sid)
            
            # Broadcast any changes (e.g. this player joining the active party) to the rest of the room as a patch
            await StateService.emit_state_update(campaign_id, game_state, sio)

        # 7. Send chat history and debug logs
        await ConnectionService._send_chat_history(campaign_id, sid, sio)
        await ConnectionService._send_debug_logs(campaign_id, sid, sio)

        # 8. Trigger Intro if Needed
        await NarratorService.generate_campaign_intro(campaign_id, sid, sio)


    @staticmethod
    async def _send_chat_history(campaign_id: str, sid: str, sio):
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                text("SELECT * FROM chat_messages WHERE campaign_id = :campaign_id ORDER BY created_at ASC"),
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

    @staticmethod
    async def _send_debug_logs(campaign_id: str, sid: str, sio):
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                text("SELECT * FROM debug_logs WHERE campaign_id = :campaign_id ORDER BY created_at ASC"),
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

