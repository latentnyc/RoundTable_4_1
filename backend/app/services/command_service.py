import logging
from db.session import AsyncSessionLocal
from app.commands.registry import CommandRegistry, CommandContext
from app.commands.combat import AttackCommand, CastCommand, EndTurnCommand
from app.commands.exploration import MoveCommand, IdentifyCommand, EquipCommand, UnequipCommand, RestCommand, CheckCommand
from app.commands.interaction import OpenCommand
from app.commands.system import HelpCommand, DMCommand

logger = logging.getLogger(__name__)

class CommandService:
    @staticmethod
    def register_commands():
        """Called on startup to register all available commands."""
        registry = CommandRegistry()
        registry.register(AttackCommand())
        registry.register(CastCommand())
        registry.register(EndTurnCommand())
        registry.register(MoveCommand())
        registry.register(IdentifyCommand())
        registry.register(EquipCommand())
        registry.register(UnequipCommand())
        registry.register(RestCommand())
        registry.register(CheckCommand())
        registry.register(OpenCommand())
        registry.register(HelpCommand())
        registry.register(DMCommand())
        logger.info("CommandService: All commands registered.")

    @staticmethod
    async def dispatch(campaign_id: str, sender_id: str, sender_name: str, content: str, sio, sid=None, target_id=None):
        """Delegates command execution to the Registry."""
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
            was_command = await CommandRegistry.dispatch(content, ctx)
            if was_command:
                await db.commit()
            return was_command
