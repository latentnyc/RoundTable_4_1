import os
import logging
from typing import List
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage

logger = logging.getLogger(__name__)

async def summarize_messages(messages: List[BaseMessage], api_key: str = None) -> str | None:
    """
    Summarizes a list of messages into a concise paragraph using a cheap model.
    """
    try:
        final_api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not final_api_key:
            return None

        # Use Flash for speed/cost
        llm = ChatGoogleGenerativeAI(
            model="gemini-3-flash-preview",
            temperature=0.3, # Low temp for factual summary
            google_api_key=final_api_key
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
