import os
import logging
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from app.agents.models import AgentState, should_continue, get_llm_instance
from app.services.llm_provider import get_llm_provider_instance
from game_engine.tools import game_tools

logger = logging.getLogger(__name__)

# Cache for compiled graphs: (api_key, model_name, llm_provider) -> compiled_graph
_dm_graph_cache = {}

def get_dm_graph(api_key: str = None, model_name: str = "gemini-3-flash-preview", llm_provider: str = "gemini"):
    # Check cache first
    final_api_key = api_key
    cache_key = (final_api_key, model_name, llm_provider)

    if cache_key in _dm_graph_cache:
        return _dm_graph_cache[cache_key], None

    # Re-initialize LLM ensuring it attaches to current loop if needed
    try:
        if not final_api_key:
            logger.error("Error: No API Key provided for DM Agent.")
            return None, "No API Key"

        llm = get_llm_instance(
            api_key=final_api_key,
            model_name=model_name,
            llm_provider=llm_provider,
            temperature=0.7
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

        request_api_key = state.get("api_key") or api_key
        request_llm_provider = state.get("llm_provider") or llm_provider

        # RAG Rules Engine Retrieval
        retrieved_rules = []
        try:
            from app.services.rules_engine import rules_engine
            
            # Find the query text from the last human message or last message
            query_text = ""
            for msg in reversed(messages):
                if isinstance(msg, HumanMessage):
                    query_text = msg.content
                    break
            if not query_text and messages:
                query_text = messages[-1].content
            if not isinstance(query_text, str):
                query_text = str(query_text)
                
            provider_inst = get_llm_provider_instance(request_api_key, request_llm_provider)
            retrieved_rules = await rules_engine.retrieve(provider_inst, query_text, top_k=3)
        except Exception as rag_err:
            logger.warning(f"RAG rules retrieval failed: {rag_err}", exc_info=True)

        rules_block = ""
        if retrieved_rules:
            rules_block = "\n\n=== RETRIEVED DM RULES ===\n" + "\n---\n".join(retrieved_rules) + "\n=========================="

        # --- SPECIAL MODES (Narration) ---
        if mode != "chat":
             logger.debug(f"invoking llm in special mode: {mode} with {len(messages)} messages")
             local_messages = list(messages)
             if rules_block and local_messages:
                 if isinstance(local_messages[0], SystemMessage):
                     local_messages[0] = SystemMessage(content=local_messages[0].content + rules_block)
                 else:
                     local_messages.insert(0, SystemMessage(content=rules_block.strip()))
             response = await llm_with_tools.ainvoke(local_messages, config=config)
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

            **RULE 3: ENDING TURNS IN COMBAT**
            - If the player explicitly tells you they are done with their turn, or declines further action after you prompt them, you MUST include the exact string `[SYSTEM_COMMAND:END_TURN]` anywhere in your response. This will mechanically pass the turn.

            **SYSTEM MESSAGES**
            You will see messages from "System" containing the results of commands. Use these as the absolute truth.
            """

        if rules_block:
            system_prompt_content += rules_block

        system_prompt = SystemMessage(content=system_prompt_content)

        # --- FILTER STALE MESSAGES ---
        latest_message = messages[-1]
        filtered_history = []
        raw_history = messages[:-1]

        for msg in raw_history:
             if isinstance(msg, HumanMessage):
                 content = msg.content.lower().strip()
                 if "who am i" in content:
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

    async def execute_tools_local(state: AgentState, config: RunnableConfig):
        db = config.get("configurable", {}).get("db")
        campaign_id = config.get("configurable", {}).get("campaign_id")
        
        messages = state["messages"]
        last_message = messages[-1]
        
        tool_messages = []
        if last_message.tool_calls:
            for tool_call in last_message.tool_calls:
                # Find matching tool
                tool = next((t for t in game_tools if t.name == tool_call["name"]), None)
                if tool:
                    try:
                        if db and hasattr(tool, "execute_with_db"):
                            result = await tool.execute_with_db(
                                db=db,
                                campaign_id=campaign_id or "dev-test-campaign-001",
                                **tool_call["args"]
                            )
                        else:
                            result = tool._run(**tool_call["args"])
                    except Exception as err:
                        logger.error(f"Error executing tool {tool.name}: {err}", exc_info=True)
                        result = f"Error executing tool: {str(err)}"
                else:
                    result = f"Tool {tool_call['name']} not found."
                
                from langchain_core.messages import ToolMessage
                tool_messages.append(ToolMessage(
                    content=str(result),
                    name=tool_call["name"],
                    tool_call_id=tool_call["id"]
                ))
                
        return {"messages": tool_messages}

    workflow = StateGraph(AgentState)

    workflow.add_node("agent", call_model_local)
    workflow.add_node("tools", execute_tools_local)

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

    compiled = workflow.compile()
    _dm_graph_cache[cache_key] = compiled
    return compiled, None
