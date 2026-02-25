import logging
import asyncio
from app.services.game_service import GameService
from app.services.chat_service import ChatService
from app.services.narrator_service import NarratorService
from app.services.turn_manager import TurnManager
from app.services.context_builder import build_narrative_context
from db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

import logging
import asyncio
from db.session import AsyncSessionLocal
from app.commands.registry import CommandRegistry, CommandContext
from app.commands.combat import AttackCommand
from app.commands.exploration import MoveCommand, IdentifyCommand
from app.commands.interaction import OpenCommand
from app.commands.system import HelpCommand, DMCommand

logger = logging.getLogger(__name__)

class CommandService:
    @staticmethod
    def register_commands():
        """
        Called on startup to register all available commands.
        """
        registry = CommandRegistry()
        registry.register(AttackCommand())
        registry.register(MoveCommand())
        registry.register(IdentifyCommand())
        registry.register(OpenCommand())
        registry.register(HelpCommand())
        registry.register(DMCommand())
        logger.info("CommandService: All commands registered.")

    @staticmethod
    async def dispatch(campaign_id: str, sender_id: str, sender_name: str, content: str, sio, sid=None, target_id=None):
        """
        Delegates command execution to the Registry.
        """
        async with AsyncSessionLocal() as db:
            ctx = CommandContext(
                campaign_id=campaign_id,
                sender_id=sender_id,
                sender_name=sender_name,
                sio=sio,
                db=db,
                sid=sid,
                target_id=target_id
            )

            # Dispatch
            # Note: dispatch returns True if a command was found and executed (or tried to), False otherwise.
            was_command = await CommandRegistry.dispatch(content, ctx)
            if was_command:
                await db.commit()
            return was_command
