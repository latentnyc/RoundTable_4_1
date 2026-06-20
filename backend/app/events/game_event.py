"""Generic game-event payload — the system-agnostic firewall for memory.

A GameEvent carries only neutral facts (damage, hp_after, item_id, rarity) —
never ruleset-specific keys like `dexterity` or `gp`. That generic `facts` dict
is the entire portability seam: the memory layer never sees D&D 5e specifics, so
a future ruleset can emit the same events without touching the memory/narrative
core. (Sprint 1 defines the model only; an EventBus is deferred to Sprint 2,
when multiple producers and consumers justify the fan-out.)
"""
from typing import Any, Optional
from pydantic import BaseModel, Field


class EntityRef(BaseModel):
    """A reference to an entity a memory is *about* or that witnessed it."""
    kind: str                       # "player" | "enemy" | "npc" | "item"
    id: str
    name: Optional[str] = None


class GameEvent(BaseModel):
    campaign_id: str
    kind: str                       # event | death | loot | summary | quest | relationship
    content: str                    # the narrative line worth remembering
    facts: dict[str, Any] = Field(default_factory=dict)          # neutral deterministic payload
    subject_refs: list[EntityRef] = Field(default_factory=list)  # who/what it is ABOUT
    witnessed_by: list[str] = Field(default_factory=list)        # entity ids present at the time
    importance: Optional[float] = None   # None → memory_service.compute_salience decides
    source_ref: str = ""            # stable, unique-per-real-event key for idempotent writes
