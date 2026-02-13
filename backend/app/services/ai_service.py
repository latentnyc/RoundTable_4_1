from app.agents import get_dm_graph, get_character_graph, summarize_messages
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from app.callbacks import SocketIOCallbackHandler
from app.services.context_builder import build_narrative_context
from app.models import GameState
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import json
from uuid import uuid4
from typing import Optional

class AIService:
    @staticmethod
    async def get_campaign_config(campaign_id: str, db: AsyncSession):
        result = await db.execute(text("SELECT api_key, model FROM campaigns WHERE id = :id"), {"id": campaign_id})
        row = result.mappings().fetchone()
        if row:

            return (row["api_key"], row["model"])

        return (None, None)

    @staticmethod
    async def generate_dm_narration(campaign_id: str, context: str, history: list, db: AsyncSession, sid: str = None, mode: str = "chat"):
        """
        Generates DM narration based on context and history.
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"DEBUG: generate_dm_narration called with mode={mode}")

        api_key, model = await AIService.get_campaign_config(campaign_id, db)
        if not api_key:
            logger.debug("DEBUG: No API Key found.")
            return None

        # Determine System Prompt based on mode
        system_prompt = ""
        if mode == "combat_narration":
             # Split Prompt: Persona in System, Task in Human
             narrator_persona = "You are the Dungeon Master. Keep narrations brief (1-2 sentences), vivid, and strictly based on the mechanics provided."
             
             task_prompt = f"""
             ACTION REPORT:
             {context}

             INSTRUCTION:
             Narrate the above action.
             - If "MISS": Describe a near miss or block.
             - If "HIT": Describe the impact.
             - Use CAPS for NPC names.
             - Do not add new mechanics.
             """
             final_history = [SystemMessage(content=narrator_persona)] + history + [HumanMessage(content=task_prompt)]
             sender_name = "System"

        elif mode == "move_narration":
              system_prompt = f"""
                You are the Dungeon Master.
                The party has just moved to a new location.

                SCENE CONTEXT:
                {context}

                Narrate their arrival. Describe the sights, sounds, and smells of the new location.
                Mention any visible NPCs.
                Keep it immersive but concise (2-3 sentences).
                """
              final_history = history + [SystemMessage(content=system_prompt)]
              sender_name = "System"

        elif mode == "identify_narration":
              system_prompt = f"""
                You are the Dungeon Master.
                A player has attempted to IDENTIFY an NPC/Entity.

                RESULT:
                {context}

                NARRATION GUIDELINES:
                1. If it was a SUCCESS: Reveal the true nature/identity of the target. Be descriptive. Use the name in CAPS (e.g. SILAS).
                2. If it was a FAILURE: Describe how the character tries to study the target but fails to learn anything new.
                3. Stay in character as the storyteller.
                4. Keep it concise (1-2 sentences).
                """
              final_history = history + [SystemMessage(content=system_prompt)]
              sender_name = "System"
        else:
             # Standard Chat
             # Context must be pre-formatted string inserted into history
             final_history = history # Caller handles context injection for now
             sender_name = "Player"

        inputs = {
             "messages": final_history,
             "campaign_id": campaign_id,
             "sender_name": sender_name,
             "api_key": api_key,
             "mode": mode
        }

        dm_graph, _ = get_dm_graph(api_key=api_key, model_name=model or 'gemini-2.0-flash')
        if not dm_graph:
            logger.debug("DEBUG: Failed to get dm_graph.")
            return None

        config = {}
        if sid:
             callback_handler = SocketIOCallbackHandler(sid, campaign_id, agent_name="Dungeon Master")
             config = {"callbacks": [callback_handler]}

        try:
             final_state = await dm_graph.ainvoke(inputs, config=config)
             return final_state["messages"][-1].content
        except Exception as e:
             logger.error(f"DEBUG: dm_graph.ainvoke failed: {e}")
             return None

    @staticmethod
    async def get_latest_memory(campaign_id: str, db: AsyncSession):
        result = await db.execute(
            text("SELECT summary_text, created_at FROM campaign_memories WHERE campaign_id = :cid ORDER BY created_at DESC LIMIT 1"),
            {"cid": campaign_id}
        )
        row = result.mappings().fetchone()
        if row:
            return row['summary_text'], row['created_at']
        return None, None

    @staticmethod
    async def save_memory(campaign_id: str, summary_text: str, db: AsyncSession):
        await db.execute(
            text("INSERT INTO campaign_memories (id, campaign_id, summary_text) VALUES (:id, :cid, :txt)"),
            {"id": str(uuid4()), "cid": campaign_id, "txt": summary_text}
        )
        await db.commit()

    @staticmethod
    async def get_messages_after(campaign_id: str, after_date, db: AsyncSession):
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

    @staticmethod
    async def generate_chat_response(campaign_id: str, sender_name: str, db: AsyncSession, sid: str = None, rich_context: str = None):
        """
        Generates a DM response for a chat message, handling memory and summarization.
        """
        api_key, model = await AIService.get_campaign_config(campaign_id, db)
        if not api_key:
            return "The Campaign GM needs to configure an API Key in Campaign Settings per the AI to function."

        # Memory & Context Logic
        memory_text, memory_date = await AIService.get_latest_memory(campaign_id, db)
        recent_messages = await AIService.get_messages_after(campaign_id, memory_date, db)

        # Summarization Check
        if len(recent_messages) > 30:
            to_summarize = recent_messages[:-10]
            keep_messages = recent_messages[-10:]

            summarization_context = to_summarize
            if memory_text:
                    summarization_context = [SystemMessage(content=f"PREVIOUS SUMMARY: {memory_text}")] + to_summarize

            new_summary = await summarize_messages(summarization_context, api_key=api_key)

            if new_summary:
                await AIService.save_memory(campaign_id, new_summary, db)
                memory_text = new_summary
                recent_messages = keep_messages

        # Construct History
        final_history = recent_messages
        if rich_context:
            final_history = [SystemMessage(content=f"SYSTEM CONTEXT (REFERENCE ONLY):\n{rich_context}")] + final_history

        if memory_text:
            final_history = [SystemMessage(content=f"STORY SO FAR: {memory_text}")] + final_history

        inputs = {
            "messages": final_history,
            "campaign_id": campaign_id,
            "sender_name": sender_name,
            "api_key": api_key,
            "model_name": model or 'gemini-2.0-flash'
        }

        # Get DM Graph
        dm_graph, error_msg = get_dm_graph(api_key=api_key, model_name=model or 'gemini-2.0-flash')
        if not dm_graph:
                return f"DM Agent is offline (Initialization Failed: {error_msg})."

        config = {}
        if sid:
             callback_handler = SocketIOCallbackHandler(sid, campaign_id, agent_name="Dungeon Master")
             config = {"callbacks": [callback_handler]}

        final_state = await dm_graph.ainvoke(inputs, config=config)
        return final_state["messages"][-1].content

    @staticmethod
    async def generate_character_response(campaign_id: str, character: dict, history: list, db: AsyncSession, sid: str = None):
        """
        Generates a response from a specific character.
        """
        api_key, model = await AIService.get_campaign_config(campaign_id, db)
        if not api_key:
            return None

        char_details = {
            "name": character['name'],
            "race": character.get('race', 'Unknown'),
            "role": character.get('role', 'Unknown'),
            "character_id": character['id']
        }
        sheet_data = character.get('sheet_data', {})
        char_details['background'] = sheet_data.get('background', 'Unknown')
        char_details['alignment'] = sheet_data.get('alignment', 'Neutral')

        char_agent = get_character_graph(
            api_key=api_key,
            model_name=model or 'gemini-2.0-flash',
            character_details=char_details
        )

        if not char_agent:
            return None

        inputs = {
            "messages": history,
            "campaign_id": campaign_id,
            "sender_name": "System" # Or whatever triggered it
        }

        config = {}
        if sid:
             callback_handler = SocketIOCallbackHandler(sid, campaign_id, agent_name=character['name'])
             config = {"callbacks": [callback_handler]}

        final_state = await char_agent.ainvoke(inputs, config=config)
        return final_state["messages"][-1].content
