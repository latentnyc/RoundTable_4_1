from .registry import CommandRegistry
from .system import HelpCommand, DMCommand
from .combat import AttackCommand, CastCommand
from .exploration import MoveCommand, IdentifyCommand, EquipCommand, UnequipCommand
from .interaction import OpenCommand

# Register all commands here so they are loaded when `app.commands` is imported

CommandRegistry.register(HelpCommand())
CommandRegistry.register(DMCommand())
CommandRegistry.register(AttackCommand())
CommandRegistry.register(CastCommand())
CommandRegistry.register(MoveCommand())
CommandRegistry.register(IdentifyCommand())
CommandRegistry.register(OpenCommand())
CommandRegistry.register(EquipCommand())
CommandRegistry.register(UnequipCommand())
