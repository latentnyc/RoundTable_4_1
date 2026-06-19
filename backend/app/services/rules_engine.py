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
        """
        Hierarchical Markdown Chunker:
        1. Tracks the active H1 and H2 headers.
        2. Splits the content by double newlines or lines to isolate paragraphs/lists.
        3. Prepends the hierarchy path (e.g. [PREFIX > H1 > H2]) to each block.
        4. Combines consecutive blocks under the same hierarchy up to max 600 characters.
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except FileNotFoundError as e:
            logger.warning(f"RulesEngine document missing: {filepath}")
            return

        # Split content into lines to parse headers and accumulate paragraphs
        lines = content.split('\n')
        
        current_h1 = "Overview"
        current_h2 = ""
        
        blocks = []
        current_block_lines = []
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('# '):
                # Save previous block if any
                if current_block_lines:
                    blocks.append((current_h1, current_h2, '\n'.join(current_block_lines).strip()))
                    current_block_lines = []
                current_h1 = stripped[2:].strip()
                current_h2 = "" # Reset H2 when H1 changes
            elif stripped.startswith('## '):
                # Save previous block if any
                if current_block_lines:
                    blocks.append((current_h1, current_h2, '\n'.join(current_block_lines).strip()))
                    current_block_lines = []
                current_h2 = stripped[3:].strip()
            else:
                if stripped:
                    current_block_lines.append(line)
                else:
                    # Empty line acts as a paragraph separator
                    if current_block_lines:
                        blocks.append((current_h1, current_h2, '\n'.join(current_block_lines).strip()))
                        current_block_lines = []
                        
        if current_block_lines:
            blocks.append((current_h1, current_h2, '\n'.join(current_block_lines).strip()))

        # Now, combine consecutive blocks under the same hierarchy path up to 600 characters
        temp_content = []
        temp_h1 = None
        temp_h2 = None
        
        def flush_temp():
            if temp_content:
                # Build hierarchy path string
                path_parts = [prefix]
                if temp_h1:
                    path_parts.append(temp_h1)
                if temp_h2:
                    path_parts.append(temp_h2)
                
                path_header = f"[{' > '.join(path_parts)}]"
                body = '\n\n'.join(temp_content)
                full_content = f"{path_header}\n{body}"
                
                self.chunks.append({
                    "title": path_header,
                    "content": full_content,
                    "embedding": None
                })
                temp_content.clear()

        for h1, h2, text in blocks:
            if not text:
                continue
            # If hierarchy changes or combining exceeds 600 characters, flush and start a new chunk
            current_len = sum(len(t) for t in temp_content) + len(text) + (2 * len(temp_content) if temp_content else 0)
            if (h1 != temp_h1 or h2 != temp_h2) or (current_len > 600):
                flush_temp()
                temp_h1 = h1
                temp_h2 = h2
            temp_content.append(text)
            
        flush_temp()

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
