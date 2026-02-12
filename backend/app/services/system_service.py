from google import genai
from typing import List, Optional

class SystemService:
    @staticmethod
    def validate_api_key(api_key: str, provider: str = "Gemini") -> List[str]:
        """
        Validates an API key and returns a list of available models.
        Raises Exception if validation fails.
        """
        if provider.lower() != "gemini":
            raise ValueError(f"Unsupported provider: {provider}")

        if not api_key:
            raise ValueError("API Key is required")

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

        except Exception as e:
            # Re-raise with clear message
            raise ValueError(f"Failed to validate API Key: {str(e)}")
