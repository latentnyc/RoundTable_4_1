from abc import ABC, abstractmethod
from typing import List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession

class CommandContext:
    def __init__(self,
                 campaign_id: str,
                 sender_id: str,
                 sender_name: str,
                 sio: Any,
                 db: AsyncSession,
                 sid: Optional[str] = None,
                 target_id: Optional[str] = None):
        self.campaign_id = campaign_id
        self.sender_id = sender_id
        self.sender_name = sender_name
        self.sio = sio
        self.db = db
        self.sid = sid
        self.target_id = target_id

class Command(ABC):
    name: str = "base"
    aliases: List[str] = []
    description: str = "Base command"
    usage: str = "@command"

    @abstractmethod
    async def execute(self, ctx: CommandContext, args: List[str]):
        """
        Execute the command logic.
        """
        pass
