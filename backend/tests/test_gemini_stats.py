
import asyncio
import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult
from langchain_core.messages import HumanMessage

load_dotenv()

class DebugCallbackHandler(AsyncCallbackHandler):
    async def on_llm_end(self, response: LLMResult, **kwargs) -> None:
        print("\n--- LLM Result Debug ---")
        print(f"LLM Output: {response.llm_output}")
        if response.generations:
            print(f"Generations: {len(response.generations)}")
            if response.generations[0]:
                print(f"First Generation Info: {response.generations[0][0].generation_info}")
                print(f"message.response_metadata: {response.generations[0][0].message.response_metadata}")
        print("------------------------\n")

async def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Skipping test: GEMINI_API_KEY not found in env.")
        return

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=api_key,
        temperature=0
    )

    handler = DebugCallbackHandler()

    print("Invoking LLM...")
    try:
        await llm.ainvoke(
            [HumanMessage(content="Hello, say 'test'.")],
            config={"callbacks": [handler]}
        )
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
