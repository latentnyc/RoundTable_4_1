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
        import os
        result = await db.execute(text("SELECT api_key, model FROM campaigns WHERE id = :id"), {"id": campaign_id})
        row = result.mappings().fetchone()

        fallback_key = os.getenv("GEMINI_API_KEY")
        fallback_model = "gemini-2.5-flash"

        if row:
            api_key = row.get("api_key")
            if not api_key:
                api_key = fallback_key
            model = row.get("model")
            if not model:
                model = fallback_model
            return (api_key, model)

        return (fallback_key, fallback_model)

    @staticmethod
    def _build_combat_narration_prompt(context: str, history: list) -> list:
         narrator_persona = "You are the Dungeon Master. Keep narrations brief (1-2 sentences), vivid, and strictly based on the mechanics provided."
         task_prompt = f"""
         ACTION REPORT:
         {context}

         INSTRUCTION:
         Narrate the above action.
         - WHO IS WHO: Pay close attention to who is the Attacker and who is the Target. The Attacker acts against the Target. Do not accidentally say the Target attacked.

         COMBAT TAGS:
         - Identify any bracketed tags (e.g., [RANGED WEAPON ATTACK]) in the report and tailor your description:
           * [RANGED WEAPON ATTACK]: Describe projectiles (arrows, bolts, magic) flying from a distance. Do NOT describe melee strikes or blades.
           * [FINESSE MELEE WEAPON ATTACK]: Describe quick, precise, agile melee strikes (thrusts, swift slashes).
           * [HEAVY/STANDARD MELEE WEAPON ATTACK]: Describe forceful, heavy, or standard physical strikes.
           * [UNARMED STRIKE]: Describe punches, kicks, or physical blows without a weapon.
           * [KILLING BLOW]: The target is definitively struck down by this attack. Describe their dramatic defeat, death, or unconsciousness resulting from the blow.

         CRITICAL HEALTH CHECK:
         - READ "Target HP" in the report.
         - If HP > 0 and there is NO [KILLING BLOW] tag: The target is ALIVE and CONSCIOUS. Do NOT narrate death, dying, or unconsciousness.
         - If HP <= 0 or there IS a [KILLING BLOW] tag: The target is DEFEATED (Dead or Unconscious).

         - Use CAPS for NPC names.
         - Do not add new mechanics.
         """
         return [SystemMessage(content=narrator_persona)] + history + [HumanMessage(content=task_prompt)]

    @staticmethod
    def _build_move_narration_prompt(context: str, history: list) -> list:
          narrator_persona = "You are the Dungeon Master. The party has successfully arrived at a new location."
          task_prompt = f"""
          SCENE CONTEXT:
          {context}

          INSTRUCTION:
          The party has effectively traversed to this new location. Ignore any previous movement commands in the chat log.
          Narrate their arrival. Describe the sights, sounds, and smells of the new location based ONLY on the Scene Context.
          Mention any visible NPCs or interactables.
          Keep it immersive but concise (2-3 sentences).
          """
          return [SystemMessage(content=narrator_persona)] + history + [HumanMessage(content=task_prompt)]

    @staticmethod
    def _build_identify_narration_prompt(context: str, history: list) -> list:
          narrator_persona = "You are the Dungeon Master. A player has attempted to IDENTIFY an NPC/Entity."
          task_prompt = f"""
          RESULT:
          {context}

          NARRATION GUIDELINES:
          1. If it was a SUCCESS: Reveal the true nature/identity of the target. Be descriptive. Use the name in CAPS (e.g. SILAS).
          2. If it was a FAILURE: Describe how the character tries to study the target but fails to learn anything new.
          3. Stay in character as the storyteller.
          4. Keep it concise (1-2 sentences).
          """
          return [SystemMessage(content=narrator_persona)] + history + [HumanMessage(content=task_prompt)]

    @staticmethod
    def _build_interaction_narration_prompt(context: str, history: list) -> list:
          narrator_persona = "You are the Dungeon Master. A player has just interacted with the environment or an object."
          task_prompt = f"""
          ACTION REPORT:
          {context}

          INSTRUCTION:
          Narrate the result of this interaction.
          - Describe what the player discovers or does based ONLY on the report.
          - Do NOT invent new rooms, enemies, or lore unless explicitly stated.
          - Stay in character as the storyteller.
          - Keep it concise (1-2 sentences).
          """
          return [SystemMessage(content=narrator_persona)] + history + [HumanMessage(content=task_prompt)]

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
        final_history = []
        sender_name = "System"

        if mode == "combat_narration":
             final_history = AIService._build_combat_narration_prompt(context, history)
        elif mode == "move_narration":
              final_history = AIService._build_move_narration_prompt(context, history)
        elif mode == "identify_narration":
              final_history = AIService._build_identify_narration_prompt(context, history)
        elif mode == "interaction_narration":
              final_history = AIService._build_interaction_narration_prompt(context, history)
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

        # Model overrides for narration? (Optional, stick to campaign config for now)
        dm_graph, _ = get_dm_graph(api_key=api_key, model_name=model or 'gemini-2.5-flash')
        if not dm_graph:
            logger.debug("DEBUG: Failed to get dm_graph.")
            return None

        callback_handler = SocketIOCallbackHandler(sid or "system", campaign_id, agent_name="Dungeon Master")
        config = {"callbacks": [callback_handler], "recursion_limit": 10}

        try:
             final_state = await dm_graph.ainvoke(inputs, config=config)
             msg_content = final_state["messages"][-1].content
             if isinstance(msg_content, list):
                 return "".join([b.get("text", "") if isinstance(b, dict) else str(b) for b in msg_content])
             return str(msg_content)
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
            "model_name": model or 'gemini-2.5-flash'
        }

        # Get DM Graph
        dm_graph, error_msg = get_dm_graph(api_key=api_key, model_name=model or 'gemini-2.5-flash')
        if not dm_graph:
                return f"DM Agent is offline (Initialization Failed: {error_msg})."

        config = {"recursion_limit": 10}
        if sid:
             callback_handler = SocketIOCallbackHandler(sid, campaign_id, agent_name="Dungeon Master")
             config = {"callbacks": [callback_handler], "recursion_limit": 10}

        final_state = await dm_graph.ainvoke(inputs, config=config)
        msg_content = final_state["messages"][-1].content
        if isinstance(msg_content, list):
            return "".join([b.get("text", "") if isinstance(b, dict) else str(b) for b in msg_content])
        return str(msg_content)

    @staticmethod
    async def generate_character_response(campaign_id: str, character: dict, history: list, db: AsyncSession, sid: str = None):
        """
        Generates a response from a specific character.
        """
        api_key, model = await AIService.get_campaign_config(campaign_id, db)
        if not api_key:
            return None

        char_details = {
            "name": getattr(character, 'name', 'Unknown'),
            "race": getattr(character, 'race', 'Unknown'),
            "role": getattr(character, 'role', 'Unknown'),
            "character_id": getattr(character, 'id', 'Unknown')
        }
        sheet_data = getattr(character, 'sheet_data', {})
        if not sheet_data:
            sheet_data = {}
        char_details['background'] = sheet_data.get('background', 'Unknown')
        char_details['alignment'] = sheet_data.get('alignment', 'Neutral')

        char_agent = get_character_graph(
            api_key=api_key,
            model_name=model or 'gemini-2.5-flash',
            character_details=char_details
        )

        if not char_agent:
            return None

        inputs = {
            "messages": history,
            "campaign_id": campaign_id,
            "sender_name": "System" # Or whatever triggered it
        }

        config = {"recursion_limit": 10}
        if sid:
             callback_handler = SocketIOCallbackHandler(sid, campaign_id, agent_name=char_details['name'])
             config = {"callbacks": [callback_handler], "recursion_limit": 10}

        final_state = await char_agent.ainvoke(inputs, config=config)
        msg_content = final_state["messages"][-1].content
        if isinstance(msg_content, list):
            return "".join([b.get("text", "") if isinstance(b, dict) else str(b) for b in msg_content])
        return str(msg_content)

    @staticmethod
    async def generate_scene_image(campaign_id: str, prompt: str, db: AsyncSession):
        from google import genai
        from google.genai import types

        api_key, _ = await AIService.get_campaign_config(campaign_id, db)
        if not api_key:
            return None

        client = genai.Client(api_key=api_key)

        # Pipeline Constraint: Prevent Party Members from being drawn, enforce style, and prevent clutter/gore
        negative_prompt = "CRITICAL INSTRUCTION: Do NOT draw any humans, adventurers, or party members. Do NOT draw any alive, awake, or standing monsters. No active creatures, no upright figures, no fighting, no action. The room must only contain the specific items requested."

        style_prompt = "Black, white, and grey detailed pencil drawing style, monochrome pencil sketch, high contrast, vertical composition, portrait orientation."

        enhanced_prompt = f"{style_prompt} Scene: {prompt} {negative_prompt}"

        # Model: using imagen-4.0-fast-generate-001 as requested
        try:
            response = client.models.generate_images(
                model='imagen-4.0-fast-generate-001',
                prompt=enhanced_prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio="3:4", # Good for sidebar portrait usage
                )
            )
            if response.generated_images:
                return response.generated_images[0].image.image_bytes # bytes
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Image Gen Error: {e}")

        return None
