from app.agents.models import get_llm_instance
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI


def test_get_llm_instance():
    # Gemini
    llm = get_llm_instance(api_key="mock_key", model_name="gemini-3-flash-preview", llm_provider="gemini")
    assert isinstance(llm, ChatGoogleGenerativeAI)
    assert llm.model == "gemini-3-flash-preview"

    # OpenAI
    llm = get_llm_instance(api_key="mock_key", model_name="gpt-4o", llm_provider="openai")
    assert isinstance(llm, ChatOpenAI)
    assert llm.model_name == "gpt-4o"

    # OpenRouter
    llm = get_llm_instance(api_key="mock_key", model_name="openai/gpt-4o", llm_provider="openrouter")
    assert isinstance(llm, ChatOpenAI)
    assert llm.model_name == "openai/gpt-4o"
    assert llm.openai_api_base == "https://openrouter.ai/api/v1"
