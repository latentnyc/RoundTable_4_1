
import asyncio
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from app.callbacks import SocketIOCallbackHandler

load_dotenv()

async def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Skipping test: GEMINI_API_KEY not found in env.")
        return

    print("--- Initializing LLM ---")
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=api_key,
        temperature=0
    )

    # Mock SID and Campaign ID
    sid = "mock_sid"
    campaign_id = "mock_campaign_id"

    # We need to mock the socketio emit and db connection within the handler
    # OR we can just use the handler and see what it logs if we patch the dependencies.
    # For now, let's just use a subclass that overrides _emit to print instead of using socketio/db.

    class DebugSocketIOCallbackHandler(SocketIOCallbackHandler):
        async def _emit(self, event: str, data: dict):
            if event == 'ai_stats':
                print(f"\n[EMIT ai_stats] {data}")
            elif event == 'debug_log':
                # print(f"[DEBUG LOG] {data.get('content')}")
                pass

    handler = DebugSocketIOCallbackHandler(sid, campaign_id, agent_name="DebugAgent")

    print("--- Invoking LLM with Handler ---")
    try:
        await llm.ainvoke(
            [HumanMessage(content="Hello, answer with one word: Test.")],
            config={"callbacks": [handler]}
        )
    except Exception as e:
        print(f"Fatal Error: {e}")
        import sys; sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
