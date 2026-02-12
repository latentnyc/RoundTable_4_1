import os
import asyncio
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

# Load env
load_dotenv()

# --- Configurations ---
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = "gemini-2.0-flash"

if not API_KEY:
    print("Error: No GEMINI_API_KEY found in environment or .env file.")
    exit(1)

# --- Mock Context ---
# This simulates what context_builder.py produces
RICH_CONTEXT = """
**CURRENT LOCATION**: The Stone Chamber
_A torchlit stone chamber with flickering flames casting long shadows._

**VISIBLE PATHS**:
None visible.

**NPCS PRESENT**:
- **GOBLIN ENEMY**: Healthy | Attitude: Hostile [Aggressive] - _Small, scowling figure._

**PARTY STATUS**:
```json
[
  {
    "name": "Sylum",
    "race": "Human",
    "class": "Paladin",
    "level": 3,
    "hp": "25/25",
    "status": "Healthy",
    "ac": 16,
    "stats": "STR 16 (+3), DEX 12 (+1), CON 14 (+2), INT 10 (+0), WIS 12 (+1), CHA 14 (+2)",
    "equipment": [
      "Longsword"
    ]
  }
]
```
"""

STORY_SO_FAR = "The party entered the chamber and saw a goblin."

# --- The "Current" System Prompt Logic (copied/adapted from agents.py) ---
def build_messages(history, sender_name="Sylum"):
    # This reflects the NEW state of agents.py (after fix)

    system_prompt_content = f"""
    You are the Dungeon Master (DM) for a 5e D&D campaign.
    The current player speaking is {sender_name}.

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

    **IMPORTANT: NPC IDENTIFICATION**
    - **CAPITALIZATION**: Refer to ALL NPCs/Enemies by their **CAPITALIZED NAME or TITLE** (e.g. SILAS, THE GOBLIN).
    - **UNIDENTIFIED NPCs**: If an NPC is described in "SYSTEM CONTEXT" only by their Role/Species (e.g. "HUNTER"), do **NOT** invent a name or reveal their true name. Call them "THE HUNTER" or "THE MAN".
    - **IDENTIFIED NPCs**: If the System Context says "SILAS (Human Hunter)", you may call him "SILAS".

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

    # Inject Context
    final_history = list(history)

    # --- PYTHON SIDE FILTERING ---
    # Issue: User sends "Who am I?" then "Who is he?" quickly.
    # The first "Who am I?" is unanswered in history. Model sees both and answers both.
    # We want to suppress "Who am I?" if it's not the last message.

    filtered_history = []
    if final_history:
        last_msg_idx = len(final_history) - 1
        for i, msg in enumerate(final_history):
            if isinstance(msg, HumanMessage):
                content = msg.content.lower().strip()
                # Check for "who am i" variants
                if "who am i" in content:
                    # If this is NOT the last message, skip it
                    if i != last_msg_idx:
                        print(f"[FILTERING]: Dropped stale 'Who am I' message: {msg.content}")
                        continue
            filtered_history.append(msg)

    final_history = filtered_history
    # -----------------------------

    # Prefix context
    final_history.insert(0, SystemMessage(content=f"STORY SO FAR: {STORY_SO_FAR}"))
    final_history.insert(0, SystemMessage(content=f"SYSTEM CONTEXT (REFERENCE ONLY):\n{RICH_CONTEXT}"))

    # System Prompt at start
    final_history.insert(0, SystemMessage(content=system_prompt_content))

    # Focus Instruction (The logic from agents.py)
    # Sandwich the latest with focus instruction
    latest_msg = final_history[-1]
    history_mid = final_history[:-1]

    focus_instruction = SystemMessage(content="""
    [IMPERATIVE INSTRUCTION]
    1. Respond ONLY to the very last message in the history.
    2. If the user asked "Who am I?" in a previous message that is NOT the last one, DO NOT ANSWER IT. Ignore it completely.
    3. The JSON data is for reference only. DO NOT summarize it or tell the player who they are unless the LAST message explicitly asks.
    """)

    return history_mid + [focus_instruction] + [latest_msg]


async def run_test():
    print(f"--- Starting Race Condition Repetition Test (Model: {MODEL_NAME}) ---")
    llm = ChatGoogleGenerativeAI(model=MODEL_NAME, google_api_key=API_KEY, temperature=0.7)

    history = []

    # User sends two messages quickly.
    # The first one "Who am I?" remains unanswered in the history passed to the second call.
    print("\n[SCENARIO]: User sends 'Who am I?', then 'Who is that guy?' without waiting.")

    history.append(HumanMessage(content="Who am I?"))
    history.append(HumanMessage(content="Who is that guy?"))

    print(f"[HISTORY]: {[m.content for m in history]}")

    messages = build_messages(history)

    print("Generating response...")
    response = await llm.ainvoke(messages)
    print(f"\n[DM RESPONSE]:\n{response.content}")

if __name__ == "__main__":
    asyncio.run(run_test())
