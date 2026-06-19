import os
import logging
from typing import List
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from app.agents.models import get_llm_instance

logger = logging.getLogger(__name__)

async def summarize_messages(messages: List[BaseMessage], api_key: str = None, llm_provider: str = "gemini", model_name: str = "gemini-3-flash-preview") -> str | None:
    """
    Summarizes a list of messages into a concise paragraph using a cheap model.
    """
    try:
        final_api_key = api_key
        if not final_api_key:
            return None

        llm = get_llm_instance(
            api_key=final_api_key,
            model_name=model_name,
            llm_provider=llm_provider,
            temperature=0.3
        )


        # Convert messages to string
        transcript = ""
        for m in messages:
            sender = "System"
            if isinstance(m, HumanMessage): sender = "Player"
            elif isinstance(m, AIMessage): sender = "DM/AI"
            elif isinstance(m, SystemMessage): sender = "System"
            transcript += f"{sender}: {m.content}\n"

        prompt = f"""
        Summarize the following D&D chat transcript into a single concise paragraph.
        Focus on key events, decisions, and current state.
        Ignore banter.

        TRANSCRIPT:
        {transcript}

        SUMMARY:
        """

        response = await llm.ainvoke([HumanMessage(content=prompt)])
        return response.content
    except Exception as e:
        logger.error(f"Error summarizing messages: {e}")
        return None
