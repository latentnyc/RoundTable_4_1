
import asyncio
import os
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from app.agents import get_dm_graph

# Load environment variables
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def get_db_key():
    url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:roundtable_dev_2024@127.0.0.1:5432/postgres")
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT api_key FROM campaigns WHERE api_key IS NOT NULL LIMIT 1"))
        row = result.fetchone()
        if row: return row[0]
        return None

async def verify_fix():
    api_key = await get_db_key()


    if not api_key:
        print("Error: GEMINI_API_KEY not found in environment.")
        return

    print("Initializing DM Agent...")
    dm_graph, error = get_dm_graph(api_key=api_key)
    if not dm_graph:
        print(f"Failed to initialize DM Agent: {error}")
        return

    # The system prompt is now dynamically selected inside agents.py based on mode.
    # We don't need to inject it manually here if we are testing the full graph logic, creates redundancy.
    # However, since get_dm_graph uses the internal call_model_local which builds the prompt,
    # we just need to pass the mode.

    # Scenario 1: MISS with combat_narration mode
    print("\n--- Testing Scenario 1: MISS (combat_narration) ---")

    # Mock history for Miss (including the "bad" command that used to confuse it)
    history_miss = [
        HumanMessage(content="@attack Goblin"),
        SystemMessage(content="Hero attacks Goblin. Roll: 5 + 2 = 7 vs AC 12. MISS! 🛡️")
    ]

    inputs_miss = {
        "messages": history_miss, # No injected system prompt needed, agent handles it
        "campaign_id": "test_campaign",
        "sender_name": "System",
        "mode": "combat_narration"
    }

    try:
        final_state = await dm_graph.ainvoke(inputs_miss)
        response = final_state["messages"][-1].content
        print("\n[DM Response - MISS]")
        print(response)

        if "use @attack" in response.lower() or "use '@attack" in response.lower() or "use the @attack" in response.lower():
            print("❌ FAILURE: DM advised to use @attack on MISS.")
        else:
            print("✅ SUCCESS: DM did not advise to use @attack on MISS.")

    except Exception as e:
        print(f"Fatal Error: {e}")
        import sys; sys.exit(1)

    # Scenario 2: HIT (The regression case)
    print("\n--- Testing Scenario 2: HIT ---")

    # Mock history for Hit
    history_hit = [
        HumanMessage(content="@attack Bork"),
        SystemMessage(content="**Zenon** attacks **Bork**! **Roll:** 19 + 0 = **19** vs AC 10 **HIT!** 🩸 Damage: **5** (1d8 ([5]) + 0) Target HP: 5")
    ]

    inputs_hit = {
        "messages": history_hit,
        "campaign_id": "test_campaign",
        "sender_name": "System",
        "mode": "combat_narration"
    }

    try:
        final_state = await dm_graph.ainvoke(inputs_hit)
        response = final_state["messages"][-1].content
        print("\n[DM Response - HIT]")
        print(response)

        if "use @attack" in response.lower() or "use '@attack" in response.lower() or "use the @attack" in response.lower():
            print("❌ FAILURE: DM advised to use @attack on HIT.")
        else:
            print("✅ SUCCESS: DM did not advise to use @attack on HIT.")

    except Exception as e:
        print(f"Fatal Error: {e}")
        import sys; sys.exit(1)


if __name__ == "__main__":
    # hack to run async in script
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(verify_fix())
