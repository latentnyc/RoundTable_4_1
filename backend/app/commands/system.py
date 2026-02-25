from typing import List
from .base import Command, CommandContext
from .registry import CommandRegistry
from app.services.chat_service import ChatService
from app.services.ai_service import AIService
from app.services.context_builder import build_narrative_context
from app.models import GameState
from sqlalchemy import text
import json
import random
from langchain_core.messages import HumanMessage
from app.services.game_service import GameService

class HelpCommand(Command):
    name = "help"
    aliases = ["h", "commands"]
    description = "List available commands."
    args_help = ""

    async def execute(self, ctx: CommandContext, args: List[str]):
        commands = CommandRegistry.get_all_commands()
        help_text = "**Available Commands:**\n"
        for cmd in commands:
            help_text += f"- `@{cmd.name}`: {cmd.description}\n"

        await ctx.sio.emit('system_message', {'content': help_text}, room=ctx.campaign_id)

class DMCommand(Command):
    name = "dm"
    aliases = ["gm"]
    description = "Ask the Dungeon Master a question."
    args_help = "<question>"

    async def execute(self, ctx: CommandContext, args: List[str]):
        # Current logic for @dm trigger
        # We need to rejoin the args to get the full question if any, or just use the full context?
        # Actually in the new system `args` is everything after `@dm`.
        # But wait - the user might have typed a sentence containing @dm in the middle?
        # The parser splits by space.
        # If the user typed "Hello @dm help me", the parser logic in Registry handles "starts with @".
        # So this command only triggers if the message STARTS with @dm.
        # The original code handled "@dm" ANYWHERE in the string.
        # We need to preserve that behavior in `chat.py` OR change it to be a strict command.
        # Strict command is cleaner. Let's stick to strict command: `@dm <message>`

        # Immediate Feedback
        await ctx.sio.emit('typing_indicator', {'sender_id': 'dm', 'is_typing': True}, room=ctx.campaign_id)

        try:
            # Build Rich Context
            rich_context = ""
            # Use GameService for consistent state retrieval
            game_state = await GameService.get_game_state(ctx.campaign_id, ctx.db)

            if game_state:
                state_row = {'state_data': game_state.model_dump_json()} # Keep compatibility for banter logic below or refactor banter
                rich_context = await build_narrative_context(ctx.db, ctx.campaign_id, game_state)

            # Call Service
            # We don't have the full original message here, only args.
            # But the user sent a message that triggered this.
            # Ideally we want the AI to respond to the *content*.
            # If the user typed `@dm What do I see?`, args is `["What", "do", "I", "see?"]`.
            user_query = " ".join(args)

            # Use `AIService.generate_chat_response` which usually takes history.
            # We need to inject the prompt?
            # In `chat_service.py`, `generate_chat_response` pulls recent history.
            # Since the user's message `@dm ...` was ALREADY saved by `chat.py` before dispatching?
            # Wait, `chat.py` saves the message FIRST.
            # So the history WILL contain `@dm What do I see?`.
            # So we just need to trigger the generation.

            response_text = await AIService.generate_chat_response(
                campaign_id=ctx.campaign_id,
                sender_name=ctx.sender_name,
                db=ctx.db,
                sid=ctx.sid,
                rich_context=rich_context
            )

            # Check for system commands
            end_turn_triggered = False
            if "[SYSTEM_COMMAND:END_TURN]" in response_text:
                response_text = response_text.replace("[SYSTEM_COMMAND:END_TURN]", "").strip()
                end_turn_triggered = True
                if not response_text:
                    response_text = "I'll pass the turn to the next in initiative."

            save_result = await ChatService.save_message(ctx.campaign_id, 'dm', 'Dungeon Master', response_text, db=ctx.db)
            await ctx.db.commit()

            await ctx.sio.emit('chat_message', {
                'sender_id': 'dm', 'sender_name': 'Dungeon Master', 'content': response_text, 'id': save_result['id'], 'timestamp': save_result['timestamp']
            }, room=ctx.campaign_id)

            if end_turn_triggered and game_state.phase == 'combat':
                from app.services.turn_manager import TurnManager
                await TurnManager.advance_turn(ctx.campaign_id, ctx.sio, ctx.db, current_game_state=game_state)
                await ctx.db.commit()

            # --- BANTER LOGIC (Refactored slightly to run here) ---
            # Ideally this moves to an event bus, but for now we keep it here to match functionality
            await self._handle_banter(ctx, response_text, state_row)

        except Exception as e:
            await ctx.sio.emit('chat_message', {
                'sender_id': 'dm', 'sender_name': 'System', 'content': f"The DM is confused. (Error: {e})", 'timestamp': 'Just now'
            }, room=ctx.campaign_id)

        await ctx.sio.emit('typing_indicator', {'sender_id': 'dm', 'is_typing': False}, room=ctx.campaign_id)

    async def _handle_banter(self, ctx, response_text, state_row):
        ai_characters = []
        if state_row:
            state_data = json.loads(state_row['state_data'])
            party = state_data.get('party', [])
            for char in party:
                if char.get('is_ai') or char.get('control_mode') == 'ai':
                    ai_characters.append(char)

        if ai_characters:
            banter_char = random.choice(ai_characters)
            try:
                await ctx.sio.emit('typing_indicator', {'sender_id': banter_char['id'], 'is_typing': True}, room=ctx.campaign_id)

                banter_history = await ChatService.get_chat_history(ctx.campaign_id, limit=20, db=ctx.db)

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
                    campaign_id=ctx.campaign_id,
                    character=banter_char,
                    history=banter_history + [banter_instruction],
                    db=ctx.db,
                    sid=ctx.sid
                )

                if banter_response:
                    save_result = await ChatService.save_message(ctx.campaign_id, banter_char['id'], banter_char['name'], banter_response, db=ctx.db)

                    await ctx.sio.emit('chat_message', {
                        'sender_id': banter_char['id'],
                        'sender_name': banter_char['name'],
                        'content': banter_response,
                        'id': save_result['id'],
                        'timestamp': save_result['timestamp']
                    }, room=ctx.campaign_id)

                await ctx.db.commit()

            except Exception as e:
                 # Silently fail banter
                 pass

            await ctx.sio.emit('typing_indicator', {'sender_id': banter_char['id'], 'is_typing': False}, room=ctx.campaign_id)
