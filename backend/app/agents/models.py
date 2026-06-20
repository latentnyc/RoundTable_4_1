import logging
import os
from typing import TypedDict, List, Annotated
import operator
from langchain_core.messages import BaseMessage

logger = logging.getLogger(__name__)

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    campaign_id: str
    sender_name: str
    mode: str
    api_key: str
    model_name: str
    llm_provider: str

def should_continue(state: AgentState):
    from langgraph.graph import END
    messages = state["messages"]
    last_message = messages[-1]
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "tools"
    return END

def get_llm_instance(api_key: str, model_name: str, llm_provider: str, temperature: float = 0.7):
    provider = (llm_provider or "gemini").lower()
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        # Set default model name for Gemini if not provided or mismatched
        model = model_name or "gemini-3-flash-preview"
        if "gpt" in model or "claude" in model:
            model = "gemini-3-flash-preview"
        return ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature,
            google_api_key=api_key,
            thinking_level="low"
        )
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        model = model_name or "gpt-4o"
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            api_key=api_key
        )
    elif provider == "openrouter":
        from langchain_openai import ChatOpenAI
        model = model_name or "openai/gpt-4o"
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1"
        )
    elif provider in ("local", "ollama", "lmstudio"):
        # Local OpenAI-compatible server (Ollama :11434/v1, LM Studio :1234/v1, llama.cpp, vLLM).
        # Free inference; the server ignores the api_key, so a non-empty placeholder is fine.
        from langchain_openai import ChatOpenAI
        base_url = os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1")
        model = model_name or os.getenv("LOCAL_LLM_MODEL", "qwen2.5:14b-instruct")
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            api_key=(api_key or "local"),
            base_url=base_url,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {llm_provider}")
