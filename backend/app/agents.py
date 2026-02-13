import os
import logging
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

logger = logging.getLogger(__name__)

# --- STATE ---
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    campaign_id: str
    sender_name: str
    mode: str
    api_key: str
    model_name: str

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
            logger.error("Error: No API Key provided for DM Agent.")
            return None, "No API Key"

        llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0.7,
            google_api_key=final_api_key
        )
        llm_with_tools = llm.bind_tools(game_tools)
    except Exception as e:
        logger.error(f"Error initializing LLM: {e}")
        return None, str(e)

    # Redefine node using the local llm_with_tools
    async def call_model_local(state: AgentState, config: RunnableConfig):
        messages = state["messages"]
        sender = state.get("sender_name", "Player")
        # Ensure mode is retrieved safely; defaults to 'chat'
        mode = state.get("mode", "chat")

        # --- SPECIAL MODES (Narration) ---
        # If mode is explicitly set to something other than 'chat', we assume
        # the caller (AIService) has already constructed the prompts.
        # We just pass it through 1:1.
        if mode != "chat":
             logger.debug(f"invoking llm in special mode: {mode} with {len(messages)} messages")
             response = await llm_with_tools.ainvoke(messages, config=config)
             return {"messages": [response]}

        # --- STANDARD CHAT MODE ---
        system_prompt_content = f"""
            You are the Dungeon Master (DM) for a 5e D&D campaign.
            The current player speaking is {sender}.

            Your responsibilities:
            1. Narrate the story vividly.
            2. Roleplay NPCs when they speak.
            3. React to the player's actions.

            **IMPORTANT: CONTEXT USE**
            - You will see a `PARTY STATUS` block in JSON format.
            - **THIS IS METADATA ONLY**.
            - **DO NOT** read this data aloud.
            - **DO NOT** tell the player who they are based on this data.
            - **DO NOT** describe the player's equipment or stats unless the result of an action explicitly changes it.
            - Use this data *silently* to know what the player is capable of.

            **IMPORTANT: CAPITALIZATION RULES**
            - **NPCS & ENEMIES**: You **MUST** refer to all NPCs, Enemies, and Monsters using **UPPERCASE** names or titles.
              - **CORRECT**: "You see SILAS.", "The GOBLIN attacks.", "THE MYSTERIOUS FIGURE watches."
              - **INCORRECT**: "You see Silas.", "The goblin attacks.", "The mysterious figure watches."
            - **PLAYER NAMES**: Capitalize the Player's Name when addressing them directly (e.g. "Welcome, FAEITH.").
            - **UNIDENTIFIED NPCs**: Use their visible description in CAPS (e.g. "THE HOODED MAN", "THE BEAST").

            **IMPORTANT: NPC IDENTIFICATION**
            - **UNIDENTIFIED**: If context says "HUNTER (Human)", call him "THE HUNTER".
            - **IDENTIFIED**: If context says "SILAS (Human Hunter)", call him "SILAS".

            **STYLE GUIDE**
            - **Narrative**: Be vivid but concise.
            - **Conversational**: Respond directly to what the player just said.
            - **No Repetition**: Do not tell the player who they are ("You are Sylum...") unless they explicitly ask "Who am I?".

            **IMPORTANT: ADDRESSING**
            - **DEFAULT**: Assume the player is talking to YOU (The DM/System/Narrator).
            - **EXCEPTION**: If the player says "I ask [NPC Name]..." or "I say to [NPC Name]...", then roleplay that NPC responding.

            **IMPORTANT: MECHANICAL ACTIONS**
            - Combat and mechanical actions are handled by the Game Engine via commands starting with `@`.

            **RULE 1: IF THE USER MESSAGE STARTS WITH `@`:**
            - **ONLY** narrate the *result* of the action based on the "System" message that follows.
            - **NEVER** provide usage tips.

            **RULE 2: IF THE USER DESCRIBES AN ACTION WITHOUT USING `@`:**
            - Narrate the *intent* briefly.
            - Then ADD this tip: "(To perform this action mechanically, use `@attack <target>` or `@check <stat>`)".

            **SYSTEM MESSAGES**
            You will see messages from "System" containing the results of commands. Use these as the absolute truth.
            """

        system_prompt = SystemMessage(content=system_prompt_content)

        # Override API Key if provided in state
        request_api_key = state.get("api_key") or api_key

        # --- REPETITION FIX ---
        # Sandwich the latest message with a strict instruction to focus ONLY on it.
        latest_message = messages[-1]

        # --- FILTER STALE MESSAGES ---
        # If the user sends multiple messages quickly, we might see "Who am I?" followed by "Who is he?".
        # If "Who am I?" is not the last message, we filter it out to prevent the DM from answering it (and repeating identity).
        filtered_history = []
        raw_history = messages[:-1]

        for msg in raw_history:
             if isinstance(msg, HumanMessage):
                 content = msg.content.lower().strip()
                 # Check for "who am i" variants - simplified check
                 if "who am i" in content:
                     # This is a Human Message in history (not the latest one). Drop it.
                     continue
             filtered_history.append(msg)

        history = filtered_history

        focus_instruction = SystemMessage(content="""
        [INSTRUCTION: Respond directly to the player's last message above. The JSON data is for reference only. DO NOT summarize it or tell the player who they are unless asked.]
        """)

        final_messages = [system_prompt] + history + [focus_instruction] + [latest_message]

        logger.debug(f"invoking llm with config: {config}")
        response = await llm_with_tools.ainvoke(final_messages, config=config)
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
    workflow.add_node("tools", ToolNode(game_tools))

    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    workflow.add_edge("tools", "agent")

    return workflow.compile()

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
            model="gemini-2.0-flash",
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
