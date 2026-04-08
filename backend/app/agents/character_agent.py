import os
import logging
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from app.agents.models import AgentState, should_continue

logger = logging.getLogger(__name__)

def get_character_graph(api_key: str, model_name: str, character_details: dict, campaign_id: str = None, db=None):
    """
    Creates a LangGraph agent for a specific NPC/Character.
    character_details should include:
    - name
    - race
    - role (class)
    - background
    - alignment
    - context (optional campaign context)
    """
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from app.ai_tools import create_interact_tool

        final_api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not final_api_key:
            return None

        llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0.8, # Slightly higher for creativity
            google_api_key=final_api_key,
            thinking_level="low" # Keep character chat snappy
        )
        char_tools = []
        if campaign_id and character_details.get('name'):
             char_tools.append(create_interact_tool(campaign_id, character_details['name'], db=db))
             
        # Bind the specific character tools
        if char_tools:
            llm_with_tools = llm.bind_tools(char_tools)
        else:
            llm_with_tools = llm

    except Exception as e:
        logger.error(f"Error initializing Character LLM: {e}")
        return None

    async def call_character_model(state: AgentState, config: RunnableConfig):
        messages = state["messages"]
        sender = state.get("sender_name", "Player")

        name = character_details.get("name", "Unknown")
        race = character_details.get("race", "Unknown")
        role = character_details.get("role", "Unknown")
        background = character_details.get("background", "Unknown")
        align = character_details.get("alignment", "Neutral")

        system_prompt = SystemMessage(content=f"""
        You are {name}, a {race} {role}.
        Background: {background}
        Alignment: {align}

        You are a character in a D&D campaign.
        The current player speaking is {sender}.

        roleplay as your character.
        - Speak in the first person.
        - React to what is said.
        - Use your background and alignment to inform your tone and decisions.
        - Keep responses concise (1-3 sentences) unless a monologue is appropriate.
        - Do not break character.

        If you need to perform an action (like attacking), describe it in narrative text.
        You can use tools if strictly necessary, but prefer roleplay.
        """)

        logger.debug(f"invoking character llm for {name}")
        response = await llm_with_tools.ainvoke([system_prompt] + messages, config=config)
        return {"messages": [response]}

    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_character_model)
    
    if char_tools:
         workflow.add_node("tools", ToolNode(char_tools))
         workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
         workflow.add_edge("tools", "agent")
    else:
         workflow.add_edge("agent", END)

    workflow.set_entry_point("agent")
    return workflow.compile()
