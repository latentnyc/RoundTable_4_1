from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import json
import logging
from pydantic import BaseModel
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

class ToolCall(BaseModel):
    name: str
    arguments: dict
    raw_call: Any  # Keep the original provider's tool call object for passing back

class LLMResponse(BaseModel):
    text: str
    function_calls: List[ToolCall] = []
    raw_response: Any  # Keep the original response object

class LLMProvider(ABC):
    @abstractmethod
    def __init__(self, api_key: str):
        pass

    @abstractmethod
    async def generate_content(
        self, 
        model: str, 
        system_instruction: str,
        messages: List[Dict[str, str]], 
        tools: Optional[List[Any]] = None
    ) -> LLMResponse:
        """Generates content given a history of standard messages [{"role": "user"|"model", "content": "..."}]"""
        pass

    @abstractmethod
    async def generate_with_tool_result(
        self,
        model: str,
        system_instruction: str,
        messages: List[Dict[str, str]],
        previous_response: LLMResponse,
        tool_results: List[Dict[str, Any]],
        tools: Optional[List[Any]] = None
    ) -> LLMResponse:
        """Generates content after a tool call.
        tool_results: [{"name": "tool_name", "result": "string_result"}]
        """
        pass

    @abstractmethod
    async def embed_content(self, model: str, text: str) -> List[float]:
        pass

class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)

    def _format_messages(self, messages: List[Dict[str, str]], new_prompt: Optional[str] = None) -> List[Any]:
        formatted = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            content = msg.get("content", msg.get("text", ""))
            formatted.append({"role": role, "parts": [{"text": content}]})
        
        if new_prompt:
            formatted.append({"role": "user", "parts": [{"text": new_prompt}]})
        return formatted

    async def generate_content(
        self, 
        model: str, 
        system_instruction: str,
        messages: List[Dict[str, str]], 
        tools: Optional[List[Any]] = None
    ) -> LLMResponse:
        formatted_history = self._format_messages(messages)
        
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            max_output_tokens=1500,
            safety_settings=[
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE,
                ),
            ]
        )
        if tools:
            config.tools = tools

        response = await self.client.aio.models.generate_content(
            model=model,
            contents=formatted_history,
            config=config
        )
        
        function_calls = []
        if response.function_calls:
            for fc in response.function_calls:
                function_calls.append(ToolCall(name=fc.name, arguments=fc.args, raw_call=fc))
                
        return LLMResponse(
            text=response.text or "",
            function_calls=function_calls,
            raw_response=response
        )

    async def generate_with_tool_result(
        self,
        model: str,
        system_instruction: str,
        messages: List[Dict[str, str]],
        previous_response: LLMResponse,
        tool_results: List[Dict[str, Any]],
        tools: Optional[List[Any]] = None
    ) -> LLMResponse:
        formatted_history = self._format_messages(messages)
        formatted_history.append(previous_response.raw_response.candidates[0].content)
        
        parts = []
        for tr in tool_results:
            func_resp_part = types.Part.from_function_response(
                name=tr["name"],
                response={"result": tr["result"]}
            )
            parts.append(func_resp_part)
            
        formatted_history.append({"role": "user", "parts": parts})
        
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            max_output_tokens=1500,
            safety_settings=[
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE,
                ),
            ]
        )
        if tools:
            config.tools = tools

        response = await self.client.aio.models.generate_content(
            model=model,
            contents=formatted_history,
            config=config
        )
        
        return LLMResponse(
            text=response.text or "",
            function_calls=[],
            raw_response=response
        )

    async def embed_content(self, model: str, text: str) -> List[float]:
        response = await self.client.aio.models.embed_content(
            model=model,
            contents=text
        )
        return response.embeddings[0].values

class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, base_url: Optional[str] = None):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def generate_content(
        self, 
        model: str, 
        system_instruction: str,
        messages: List[Dict[str, str]], 
        tools: Optional[List[Any]] = None
    ) -> LLMResponse:
        formatted_messages = [{"role": "system", "content": system_instruction}]
        for msg in messages:
            role = "user" if msg["role"] == "user" else "assistant"
            content = msg.get("content", msg.get("text", ""))
            formatted_messages.append({"role": role, "content": content})

        # LangChain tools bind schemas automatically, but since this is direct provider wrapper:
        openai_tools = None # Standard direct narration uses no tools. If needed in future: schemas could be added.
        
        kwargs = {
            "model": model,
            "messages": formatted_messages,
            "max_tokens": 1500,
        }
        if openai_tools:
            kwargs["tools"] = openai_tools

        response = await self.client.chat.completions.create(**kwargs)
        message = response.choices[0].message
        
        function_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                if tc.type == "function":
                    args = json.loads(tc.function.arguments)
                    function_calls.append(ToolCall(
                        name=tc.function.name, 
                        arguments=args, 
                        raw_call=tc
                    ))
                    
        return LLMResponse(
            text=message.content or "",
            function_calls=function_calls,
            raw_response=response
        )

    async def generate_with_tool_result(
        self,
        model: str,
        system_instruction: str,
        messages: List[Dict[str, str]],
        previous_response: LLMResponse,
        tool_results: List[Dict[str, Any]],
        tools: Optional[List[Any]] = None
    ) -> LLMResponse:
        formatted_messages = [{"role": "system", "content": system_instruction}]
        for msg in messages:
            role = "user" if msg["role"] == "user" else "assistant"
            content = msg.get("content", msg.get("text", ""))
            formatted_messages.append({"role": role, "content": content})
            
        assistant_msg = previous_response.raw_response.choices[0].message
        formatted_messages.append(assistant_msg.model_dump(exclude_none=True))
        
        for tr in tool_results:
            tool_call_id = None
            for tc in assistant_msg.tool_calls:
                if tc.function.name == tr["name"]:
                    tool_call_id = tc.id
                    break
                    
            if tool_call_id:
                formatted_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "name": tr["name"],
                    "content": tr["result"]
                })

        kwargs = {
            "model": model,
            "messages": formatted_messages,
            "max_tokens": 1500,
        }

        response = await self.client.chat.completions.create(**kwargs)
        
        return LLMResponse(
            text=response.choices[0].message.content or "",
            function_calls=[],
            raw_response=response
        )

    async def embed_content(self, model: str, text: str) -> List[float]:
        try:
            if "text-embedding" not in model:
                model = "text-embedding-3-small"
                
            response = await self.client.embeddings.create(
                model=model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.warning(f"Embeddings failed: {e}. Falling back to zero-vector.")
            return [0.0] * 1536

class OpenRouterProvider(OpenAIProvider):
    def __init__(self, api_key: str):
        super().__init__(api_key=api_key, base_url="https://openrouter.ai/api/v1")

    async def generate_content(
        self, 
        model: str, 
        system_instruction: str,
        messages: List[Dict[str, str]], 
        tools: Optional[List[Any]] = None
    ) -> LLMResponse:
        return await super().generate_content(model, system_instruction, messages, tools)

    async def generate_with_tool_result(
        self,
        model: str,
        system_instruction: str,
        messages: List[Dict[str, str]],
        previous_response: LLMResponse,
        tool_results: List[Dict[str, Any]],
        tools: Optional[List[Any]] = None
    ) -> LLMResponse:
        return await super().generate_with_tool_result(model, system_instruction, messages, previous_response, tool_results, tools)

    async def embed_content(self, model: str, text: str) -> List[float]:
        try:
            if "text-embedding" not in model:
                model = "openai/text-embedding-3-small"
            return await super().embed_content(model, text)
        except Exception as e:
            logger.warning(f"OpenRouter embeddings failed: {e}. Falling back to zero-vector.")
            return [0.0] * 1536

def get_llm_provider_instance(api_key: str, llm_provider: str) -> LLMProvider:
    provider = (llm_provider or "gemini").lower()
    if provider == "gemini":
        return GeminiProvider(api_key=api_key)
    elif provider == "openai":
        return OpenAIProvider(api_key=api_key)
    elif provider == "openrouter":
        return OpenRouterProvider(api_key=api_key)
    else:
        raise ValueError(f"Unknown LLM provider: {llm_provider}")

