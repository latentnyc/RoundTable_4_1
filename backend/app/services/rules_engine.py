import math
import re
import asyncio
import logging
import os
from typing import List
from app.services.llm_provider import LLMProvider

logger = logging.getLogger(__name__)

def cosine_similarity(v1, v2):
    """Pure Python dot-product implementation."""
    dot_product = sum(a * b for a, b in zip(v1, v2))
    magnitude_v1 = math.sqrt(sum(a * a for a in v1))
    magnitude_v2 = math.sqrt(sum(b * b for b in v2))
    if magnitude_v1 == 0 or magnitude_v2 == 0:
        return 0.0
    return dot_product / (magnitude_v1 * magnitude_v2)

class RulesEngine:
    _instance = None
    _lock = asyncio.Lock()

    def __init__(self):
        self.chunks = []
        self.model_name = "text-embedding-004"
        self.embeddings_cached = {}
        self._lock = asyncio.Lock()
        
        # Absolute path resolution to prevent working directory issues
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Load our 4 D&D rule documents
        self._parse_markdown(os.path.join(base_dir, "data", "dm_rules", "dm_persona.md"), "PERSONA")
        self._parse_markdown(os.path.join(base_dir, "data", "dm_rules", "combat_protocol.md"), "COMBAT")
        self._parse_markdown(os.path.join(base_dir, "data", "dm_rules", "conditions_reference.md"), "CONDITIONS")
        self._parse_markdown(os.path.join(base_dir, "data", "dm_rules", "narration_guide.md"), "NARRATION")

    def _parse_markdown(self, filepath, prefix):
        """Chunks the markdown files into memory."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except FileNotFoundError as e:
            logger.warning(f"RulesEngine document missing: {filepath}")
            return
            
        sections = re.split(r'\n## ', content)
        for i, section in enumerate(sections):
            if not section.strip(): continue
            lines = section.split('\n')
            title = lines[0].strip()
            if i == 0 and not section.startswith('##'):
                title = "Overview"
            title = f"[{prefix}] {title.replace('#', '').strip()}"
            body = '\n'.join(lines[1:]).strip()
            if body:
                self.chunks.append({"title": title, "content": f"{title}\n{body}", "embedding": None})

    async def _ensure_document_embeddings(self, llm: LLMProvider):
        """Lazy-loads document embeddings using the active provider key."""
        provider_name = type(llm).__name__
        if self.embeddings_cached.get(provider_name) or not self.chunks:
            return
            
        async with self._lock:
            if self.embeddings_cached.get(provider_name):
                return
                
            logger.info(f"⚙️ [RulesEngine] Generating rules embeddings via {provider_name}...")
            # Determine embedding model name for the provider
            embed_model = self.model_name
            if provider_name == "OpenAIProvider":
                embed_model = "text-embedding-3-small"
            elif provider_name == "OpenRouterProvider":
                embed_model = "openai/text-embedding-3-small"

            for chunk in self.chunks:
                chunk[f"embedding_{provider_name}"] = await llm.embed_content(embed_model, chunk["content"])
                
            self.embeddings_cached[provider_name] = True

    async def retrieve(self, llm: LLMProvider, query: str, top_k=3) -> List[str]:
        """Embeds the state-aware query and returns the most relevant rules."""
        await self._ensure_document_embeddings(llm)
        provider_name = type(llm).__name__
        
        embed_model = self.model_name
        if provider_name == "OpenAIProvider":
            embed_model = "text-embedding-3-small"
        elif provider_name == "OpenRouterProvider":
            embed_model = "openai/text-embedding-3-small"

        # Embed the query
        query_embedding = await llm.embed_content(embed_model, query)
        
        # Calculate similarity
        scored_chunks = []
        for chunk in self.chunks:
            chunk_embedding = chunk.get(f"embedding_{provider_name}")
            if chunk_embedding:
                score = cosine_similarity(query_embedding, chunk_embedding)
                scored_chunks.append((score, chunk))
                
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        return [c["content"] for score, c in scored_chunks[:top_k]]

# Single global instance
rules_engine = RulesEngine()
