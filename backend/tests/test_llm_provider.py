import pytest
from app.agents.models import get_llm_instance
from app.services.llm_provider import get_llm_provider_instance, GeminiProvider, OpenAIProvider, OpenRouterProvider
from app.services.rules_engine import rules_engine
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

def test_get_llm_provider_instance():
    p = get_llm_provider_instance(api_key="mock_key", llm_provider="gemini")
    assert isinstance(p, GeminiProvider)

    p = get_llm_provider_instance(api_key="mock_key", llm_provider="openai")
    assert isinstance(p, OpenAIProvider)

    p = get_llm_provider_instance(api_key="mock_key", llm_provider="openrouter")
    assert isinstance(p, OpenRouterProvider)

def test_rules_engine_chunks_loaded():
    assert len(rules_engine.chunks) > 0
    # Check that we parsed chunks from different files
    categories = [chunk["title"] for chunk in rules_engine.chunks]
    assert any("PERSONA" in cat for cat in categories)
    assert any("COMBAT" in cat for cat in categories)
    assert any("CONDITIONS" in cat for cat in categories)
    assert any("NARRATION" in cat for cat in categories)

    # Hierarchical and structural checks
    for chunk in rules_engine.chunks:
        title = chunk["title"]
        content = chunk["content"]
        
        # Verify title path format (e.g. [PERSONA > H1 > H2])
        assert title.startswith("[") and title.endswith("]")
        assert " > " in title
        assert content.startswith(title)
        
        # Extract body text and verify size limits
        body = content[len(title):].strip()
        assert len(body) > 0
        # Check that combined rule body does not exceed 1500 chars (soft limit of 600 for combining)
        assert len(body) < 1500

