from google import genai
from typing import List, Optional

class SystemService:
    @staticmethod
    def validate_api_key(api_key: str, provider: str = "Gemini") -> List[str]:
        """
        Validates an API key and returns a list of available models.
        Raises Exception if validation fails.
        """
        if not api_key:
            raise ValueError("API Key is required")

        prov_lower = provider.lower()
        if prov_lower not in ["gemini", "openai", "openrouter"]:
            raise ValueError(f"Unsupported provider: {provider}")


        if prov_lower == "gemini":
            try:
                client = genai.Client(api_key=api_key)
                models = []
                # genai.Client.models.list() returns an iterable of Model objects
                for m in client.models.list():
                    if 'generateContent' in (m.supported_actions or []):
                        # Filter for Gemini models roughly
                        if 'gemini' in m.name.lower():
                            # The name usually comes as "models/gemini-pro", let's strip "models/" if present
                            name = m.name.replace("models/", "")
                            models.append(name)

                # Sort for better UX
                models.sort(reverse=True)

                if not models:
                     # It's possible to have a valid key but no access to models, but unlikely for Gemini free tier
                     # We treat no models as a failure to validate for our purposes
                     raise ValueError("No compatible models found for this API Key.")

                return models

            except genai.errors.APIError as e:
                raise ValueError(f"Gemini API Error: {str(e)}")
            except Exception as e:
                # Re-raise with clear message for unknown errors
                raise ValueError(f"Failed to validate API Key: {str(e)}")

        elif prov_lower in ["openai", "openrouter"]:
            import openai
            try:
                base_url = "https://openrouter.ai/api/v1" if prov_lower == "openrouter" else None
                client = openai.OpenAI(api_key=api_key, base_url=base_url)
                res = client.models.list()
                if prov_lower == "openai":
                    models = [m.id for m in res.data if "gpt" in m.id.lower() or "o1" in m.id.lower()]
                else:
                    models = [m.id for m in res.data]
                models.sort()
                
                # If list of models is empty, provide common fallback models
                if not models:
                    if prov_lower == "openai":
                        models = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"]
                    else:
                        models = ["openai/gpt-4o", "openai/gpt-4o-mini", "meta-llama/llama-3-8b-instruct"]
                return models
            except Exception as e:
                raise ValueError(f"{provider} API Error: {str(e)}")

