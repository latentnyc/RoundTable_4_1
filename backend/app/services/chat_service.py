import logging
import datetime
import json
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import AsyncSessionLocal
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

logger = logging.getLogger(__name__)

class ChatService:
    @staticmethod
    async def save_message(campaign_id: str, sender_id: str, sender_name: str, content: str, db: AsyncSession = None):
        msg_id = str(uuid4())
        timestamp = datetime.datetime.now()

        # Ensure content is a string for the DB
        if not isinstance(content, str):
            try:
                content = json.dumps(content)
            except Exception as e:
                logger.error(f"Service Error: {e}", exc_info=True)
                raise e
                content = str(content)

        if db:
            await db.execute(
                text("""INSERT INTO chat_messages (id, campaign_id, sender_id, sender_name, content, created_at)
                   VALUES (:id, :campaign_id, :sender_id, :sender_name, :content, :created_at)"""),
                {"id": msg_id, "campaign_id": campaign_id, "sender_id": sender_id, "sender_name": sender_name, "content": content, "created_at": timestamp}
            )
            # Note: We do NOT commit here if db is provided, caller handles transaction.
            return {"id": msg_id, "timestamp": timestamp.isoformat()}
        else:
            async with AsyncSessionLocal() as session:
                await session.execute(
                    text("""INSERT INTO chat_messages (id, campaign_id, sender_id, sender_name, content, created_at)
                       VALUES (:id, :campaign_id, :sender_id, :sender_name, :content, :created_at)"""),
                    {"id": msg_id, "campaign_id": campaign_id, "sender_id": sender_id, "sender_name": sender_name, "content": content, "created_at": timestamp}
                )
                await session.commit()
                return {"id": msg_id, "timestamp": timestamp.isoformat()}

    @staticmethod
    async def get_chat_history(campaign_id: str, limit: int = 10, db: AsyncSession = None):
        if db:
            result = await db.execute(
                text("""SELECT * FROM chat_messages
                   WHERE campaign_id = :campaign_id
                   ORDER BY created_at DESC
                   LIMIT :limit"""),
                {"campaign_id": campaign_id, "limit": limit}
            )
            rows = result.mappings().all()
        else:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    text("""SELECT * FROM chat_messages
                       WHERE campaign_id = :campaign_id
                       ORDER BY created_at DESC
                       LIMIT :limit"""),
                    {"campaign_id": campaign_id, "limit": limit}
                )
                rows = result.mappings().all()

        messages = []
        for row in reversed(rows):
            if "DM Agent is offline" in row["content"] or "The DM is confused" in row["content"]:
                continue
            if row["sender_id"] == "dm":
                messages.append(AIMessage(content=row["content"]))
            elif row["sender_id"] == "system":
                messages.append(SystemMessage(content=row["content"]))
            else:
                messages.append(HumanMessage(content=f"{row['sender_name']}: {row['content']}"))
        return messages

    @staticmethod
    async def get_latest_memory(campaign_id: str):
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                text("SELECT summary_text, created_at FROM campaign_memories WHERE campaign_id = :cid ORDER BY created_at DESC LIMIT 1"),
                {"cid": campaign_id}
            )
            row = result.mappings().fetchone()
            if row:
                return row['summary_text'], row['created_at']
            return None, None

    @staticmethod
    async def save_memory(campaign_id: str, summary_text: str):
        async with AsyncSessionLocal() as db:
            await db.execute(
                text("INSERT INTO campaign_memories (id, campaign_id, summary_text) VALUES (:id, :cid, :txt)"),
                {"id": str(uuid4()), "cid": campaign_id, "txt": summary_text}
            )
            await db.commit()

    @staticmethod
    async def get_messages_after(campaign_id: str, after_date):
        async with AsyncSessionLocal() as db:
            # If no date, get all (with safe limit)
            if not after_date:
                result = await db.execute(
                    text("SELECT * FROM chat_messages WHERE campaign_id = :cid ORDER BY created_at ASC LIMIT 100"),
                    {"cid": campaign_id}
                )
            else:
                result = await db.execute(
                    text("SELECT * FROM chat_messages WHERE campaign_id = :cid AND created_at > :dt ORDER BY created_at ASC LIMIT 100"),
                    {"cid": campaign_id, "dt": after_date}
                )

            rows = result.mappings().all()
            # Convert to LangChain messages
            messages = []
            for row in rows:
                if "DM Agent is offline" in row["content"] or "The DM is confused" in row["content"]:
                    continue
                if row["sender_id"] == "dm":
                    messages.append(AIMessage(content=row["content"]))
                elif row["sender_id"] == "system":
                    messages.append(SystemMessage(content=row["content"]))
                else:
                    messages.append(HumanMessage(content=f"{row['sender_name']}: {row['content']}"))
            return messages
