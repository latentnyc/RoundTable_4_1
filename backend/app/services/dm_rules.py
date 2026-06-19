"""Static DM rule docs, loaded once and injected directly into the DM prompt.

These four files (persona, combat protocol, conditions reference, narration guide)
are small, stable behavioral guardrails — they must apply on *every* turn, so they
are injected directly rather than semantically retrieved. Semantic retrieval is
reserved for large, per-campaign corpora (long-term memory, lore) where always
including everything would be wasteful; a ~60-line static guardrail set is not that.
"""
import os
import logging

logger = logging.getLogger(__name__)

_RULE_FILES = [
    "dm_persona.md",
    "combat_protocol.md",
    "conditions_reference.md",
    "narration_guide.md",
]


def _load_rules_block() -> str:
    # backend/app/services/dm_rules.py -> backend/
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    rules_dir = os.path.join(base_dir, "data", "dm_rules")

    sections = []
    for fname in _RULE_FILES:
        path = os.path.join(rules_dir, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
        except FileNotFoundError:
            logger.warning("DM rule doc missing: %s", path)
            continue
        if content:
            sections.append(content)

    if not sections:
        return ""
    return "\n\n=== DM RULES ===\n" + "\n\n---\n\n".join(sections) + "\n=== END DM RULES ===\n"


# Loaded once at import — the corpus is small and static.
RULES_BLOCK = _load_rules_block()
