import logging
from typing import Dict, List, Optional
from .base import Command, CommandContext

logger = logging.getLogger(__name__)

class CommandRegistry:
    _instance = None
    _commands: Dict[str, Command] = {}
    _aliases: Dict[str, str] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CommandRegistry, cls).__new__(cls)
        return cls._instance

    @classmethod
    def register(cls, command: Command):
        """Registers a command instance."""
        cls._commands[command.name.lower()] = command
        for alias in command.aliases:
            cls._aliases[alias.lower()] = command.name.lower()
        logger.info(f"Registered command: @{command.name}")

    @classmethod
    def get_command(cls, name: str) -> Optional[Command]:
        """Retrieves a command by name or alias."""
        name = name.lower()
        if name in cls._commands:
            return cls._commands[name]
        if name in cls._aliases:
            return cls._commands[cls._aliases[name]]
        return None

    @classmethod
    def get_all_commands(cls) -> List[Command]:
        """Returns a list of all unique registered commands."""
        return list(cls._commands.values())

    @classmethod
    async def dispatch(cls, input_text: str, ctx: CommandContext):
        """
        Parses and executes a command from input text.
        Expects input to start with valid command trigger (handled by caller typically, but we double check).
        """
        parts = input_text.strip().split()
        if not parts:
            return False

        # Remove '@' if present
        cmd_name = parts[0]
        if cmd_name.startswith("@"):
            cmd_name = cmd_name[1:]

        command = cls.get_command(cmd_name)
        if not command:
            return False

        args = parts[1:]
        try:
            await command.execute(ctx, args)
            return True
        except Exception as e:
            logger.error(f"Error executing command {cmd_name}: {e}")
            await ctx.sio.emit('system_message', {'content': f"Command Error: {e}"}, room=ctx.campaign_id)
            return True # Logic handled, even if error
