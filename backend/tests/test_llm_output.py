
import os
import asyncio
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

import pytest

pytestmark = pytest.mark.integration

load_dotenv()

async def test_llm_structure():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        pytest.skip("No GEMINI_API_KEY found in env.")

    print(f"Using API Key: {api_key[:5]}..." if api_key else "No API Key")

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=api_key,
        temperature=0
    )

    print("Invoking LLM...")
    response = await llm.agenerate([[HumanMessage(content="Hello, say 'test'")]])

    print("\n--- Response LLM Output ---")
    print(response.llm_output)

    print("\n--- Response Generations ---")
    for gen in response.generations[0]:
        print(f"Gen info: {gen.generation_info}")
        print(f"Message usage (if any): {getattr(gen.message, 'usage_metadata', None)}")

    print("\n--- Response Run Info ---")
    print(f"Run key: {response.run}")

if __name__ == "__main__":
    asyncio.run(test_llm_structure())
