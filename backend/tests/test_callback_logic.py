
import asyncio
import os
import sys
from unittest.mock import MagicMock, AsyncMock

# Ensure backend modules can be imported
sys.path.append(os.getcwd())

from app.callbacks import SocketIOCallbackHandler
from langchain_core.outputs import LLMResult, Generation, ChatGeneration
from langchain_core.messages import AIMessage

async def test_callback_logic():
    print("Testing callback logic (Start -> End)...", flush=True)

    # Create dummy campaign to ensure DB update works
    from db.session import AsyncSessionLocal
    from sqlalchemy import text
    import uuid

    dummy_camp_id = str(uuid.uuid4())
    print(f"Creating dummy campaign {dummy_camp_id}...", flush=True)
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("INSERT INTO campaigns (id, title, status) VALUES (:id, 'Test Campaign', 'active')"),
            {"id": dummy_camp_id}
        )
        await db.commit()

    # Mock dependencies
    handler = SocketIOCallbackHandler(sid="test_sid", campaign_id=dummy_camp_id, agent_name="TestAgent")
    handler._emit = AsyncMock() # type: ignore

    # 1. Simulate on_chat_model_start
    print("Simulating on_chat_model_start...", flush=True)
    serialized = {
        'id': ['langchain', 'chat_models', 'google_palm', 'ChatGooglePalm'],
        'kwargs': {'model_name': 'gemini-2.0-flash-captured'}
    }
    messages = [[MagicMock(content="Hello")]]
    await handler.on_chat_model_start(serialized, messages)

    # Verify captured model name
    if handler.last_model_name == 'gemini-2.0-flash-captured':
        print(f"SUCCESS: Captured model name: {handler.last_model_name}", flush=True)
    else:
        print(f"FAILURE: Did not capture model name. Got: {handler.last_model_name}", flush=True)

    # 2. Simulate response WITHOUT model name in output
    print("Simulating response without model name...", flush=True)
    msg = AIMessage(content="test", usage_metadata={'input_tokens': 10, 'output_tokens': 20, 'total_tokens': 30})
    gen = ChatGeneration(text="test", message=msg)

    response = LLMResult(generations=[[gen]], llm_output={})

    print("Invoking on_chat_model_end...", flush=True)
    try:
        await handler.on_chat_model_end(response)

        emit_calls = handler._emit.call_args_list # type: ignore
        found_stats = False
        for call in emit_calls:
            event = call[0][0]
            data = call[0][1]
            if event == 'ai_stats':
                found_stats = True
                model = data.get('model')
                print(f"Emitted AI Stats Model: {model}", flush=True)
                if model == 'gemini-2.0-flash-captured':
                     print("SUCCESS: AI Stats used captured model name.", flush=True)
                else:
                     print(f"FAILURE: AI Stats used wrong model name: {model}", flush=True)

        if not found_stats:
            print("WARNING: No ai_stats event emitted.", flush=True)

    except Exception as e:
        print(f"Detailed Error: {e}", flush=True)
    finally:
        # Cleanup
        print("Cleaning up...", flush=True)
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(text("DELETE FROM campaigns WHERE id = :id"), {"id": dummy_camp_id})
                await db.commit()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(test_callback_logic())
