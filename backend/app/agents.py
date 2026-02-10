import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
from typing import TypedDict, List, Annotated
import operator
from game_engine.tools import game_tools
from dotenv import load_dotenv
from langchain_core.runnables import RunnableConfig

load_dotenv()

# --- STATE ---
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    campaign_id: str
    sender_name: str

def should_continue(state: AgentState):
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "tools"
    return END

# Global Singleton for now? No, let's make it a factory to avoid loop issues
# dm_graph = make_dm_graph()

def get_dm_graph(api_key: str = None, model_name: str = "gemini-2.0-flash"):
    # Re-initialize LLM ensuring it attaches to current loop if needed
    try:
        final_api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not final_api_key:
            print("Error: No API Key provided for DM Agent.")
            return None
            
        llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0.7,
            google_api_key=final_api_key
        )
        llm_with_tools = llm.bind_tools(game_tools)
    except Exception as e:
        print(f"Error initializing LLM: {e}")
        return None, str(e)

    # Redefine node using the local llm_with_tools
    # Redefine node using the local llm_with_tools
    async def call_model_local(state: AgentState, config: RunnableConfig):
        messages = state["messages"]
        sender = state.get("sender_name", "Player")
        
        system_prompt = SystemMessage(content=f"""
        You are the Dungeon Master (DM) for a 5e D&D campaign. 
        The current player speaking is {sender}.
        
        Your responsibilities:
        1. Narrate the story vividly.
        2. adjudicate rules fairly.
        3. CALL TOOLS when a rule check is needed (Attack, Skill Check).
        
        DO NOT hallucinate dice rolls. 
        If a player says "I attack the goblin", call the `attack` tool.
        If a player says "I try to lift the rock", call the `check` tool.
        
        After the tool executes, use its output to describe what happens.
        If the tool says "Hit! 8 damage", describe the blow connecting.
        """)
        
        print(f"DEBUG: invoking llm with config: {config}", flush=True)
        response = await llm_with_tools.ainvoke([system_prompt] + messages, config=config)
        return {"messages": [response]}

    workflow = StateGraph(AgentState)
    
    workflow.add_node("agent", call_model_local)
    workflow.add_node("tools", ToolNode(game_tools))
    
    workflow.set_entry_point("agent")
    
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            END: END
        }
    )
    
    workflow.add_edge("tools", "agent")
    
    return workflow.compile(), None

def get_character_graph(api_key: str, model_name: str, character_details: dict):
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
        
        final_api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not final_api_key:
            return None
            
        llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0.8, # Slightly higher for creativity
            google_api_key=final_api_key
        )
        # Characters might not need tools yet, or maybe they do?
        # For now, let's give them tools but maybe restrict usage instructions?
        # Actually, let's keep it simple: No tools for now, just chat. 
        # Or maybe safe tools?
        # Let's bind tools but not emphasize them in prompt unless needed.
        llm_with_tools = llm.bind_tools(game_tools)
        
    except Exception as e:
        print(f"Error initializing Character LLM: {e}")
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
        
        print(f"DEBUG: invoking character llm for {name}", flush=True)
        response = await llm_with_tools.ainvoke([system_prompt] + messages, config=config)
        return {"messages": [response]}

    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_character_model)
    workflow.add_node("tools", ToolNode(game_tools))
    
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    workflow.add_edge("tools", "agent")
    
    return workflow.compile()
