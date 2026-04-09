"""
Spell service: Tier A whitelist, SRD→engine format normalization, spell lookup.

Only spells that can be fully mechanically resolved are available to players.
All others are hidden until the systems they require are implemented.
"""
import json
import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.schema import spells as spells_table

logger = logging.getLogger(__name__)

# ── Tier A Whitelist ──
# These are the only spells exposed to players. Each can be fully resolved
# by the engine: attack roll + damage, save + damage, auto-hit, healing,
# or condition application.
TIER_A_SPELLS = {
    # Attack roll + damage
    "fire-bolt", "ray-of-frost", "shocking-grasp", "chill-touch", "eldritch-blast",
    "guiding-bolt", "inflict-wounds", "acid-arrow",
    # Save + damage
    "sacred-flame", "poison-spray", "vicious-mockery", "hellish-rebuke",
    "blight", "harm", "finger-of-death", "disintegrate",
    # Auto-hit damage (special case)
    "magic-missile",
    # Healing
    "cure-wounds", "healing-word", "heal",
    # Condition-applying (save or be affected)
    "blindness-deafness", "command", "charm-person", "animal-friendship",
    # Concentration + condition (save or be affected, breaks on caster damage)
    "hold-person", "hold-monster", "entangle", "hideous-laughter",
    "phantasmal-killer", "banishment", "dominate-beast", "dominate-person",
    "dominate-monster", "eyebite", "flesh-to-stone",
}


def is_tier_a(spell_index: str) -> bool:
    """Check if a spell is in the Tier A whitelist."""
    return spell_index.lower() in TIER_A_SPELLS


def get_tier_a_for_class(class_name: str, all_spells: List[dict]) -> List[dict]:
    """Filter spells to only Tier A spells available to a given class."""
    result = []
    for spell in all_spells:
        index = spell.get("index", "")
        if index not in TIER_A_SPELLS:
            continue
        classes = spell.get("classes", [])
        class_names = [c.get("name", "") if isinstance(c, dict) else c for c in classes]
        if class_name in class_names:
            result.append(spell)
    return result


def normalize_spell_for_engine(srd_spell: dict) -> dict:
    """Convert SRD spell format to the nested format the GameEngine expects.

    SRD format (flat):
        {"name": "Fire Bolt", "level": 0, "attack_type": "ranged",
         "damage": {"damage_type": {"name": "Fire"}, "damage_at_character_level": {"1": "1d10"}},
         "range": "120 feet", "dc": {"dc_type": {"index": "dex"}}}

    Engine format (nested data):
        {"name": "Fire Bolt", "data": {"level": 0, "attack_type": "ranged",
         "damage": {"damage_dice": "1d10", "damage_type": {"name": "Fire"}},
         "range": "120 feet", "save": {"dc_type": {"index": "dex"}}}}
    """
    name = srd_spell.get("name", "Unknown Spell")
    index = srd_spell.get("index", "")
    level = srd_spell.get("level", 0)

    # Build the normalized data dict the engine reads via spell.get("data", {})
    data: Dict[str, Any] = {
        "level": level,
        "school": srd_spell.get("school", {}).get("name", "") if isinstance(srd_spell.get("school"), dict) else srd_spell.get("school", ""),
        "range": srd_spell.get("range", "Touch"),
        "casting_time": srd_spell.get("casting_time", "1 action"),
        "concentration": srd_spell.get("concentration", False),
    }

    # Attack type
    if srd_spell.get("attack_type"):
        data["attack_type"] = srd_spell["attack_type"]

    # Save / DC
    if srd_spell.get("dc"):
        data["save"] = srd_spell["dc"]

    # Damage — resolve dice string from SRD's nested structure
    srd_damage = srd_spell.get("damage")
    if srd_damage:
        damage_type = srd_damage.get("damage_type", {})
        damage_dice = _extract_damage_dice(srd_damage, level, index)

        data["damage"] = {
            "damage_dice": damage_dice,
            "damage_type": damage_type,
        }

    # Healing — SRD uses heal_at_slot_level
    srd_heal = srd_spell.get("heal_at_slot_level")
    if srd_heal:
        data["heal_at_slot_level"] = srd_heal

    # Condition-applying spells: attach condition metadata for the engine
    SPELL_CONDITIONS = {
        # Non-concentration
        "blindness-deafness": {"condition": "Blinded", "duration": 10},
        "command": {"condition": "Prone", "duration": 1},
        "charm-person": {"condition": "Charmed", "duration": -1},
        "animal-friendship": {"condition": "Charmed", "duration": -1},
        # Concentration (condition lasts while caster concentrates, up to 10 rounds)
        "hold-person": {"condition": "Paralyzed", "duration": 10},
        "hold-monster": {"condition": "Paralyzed", "duration": 10},
        "entangle": {"condition": "Restrained", "duration": 10},
        "hideous-laughter": {"condition": "Prone", "duration": 10},
        "phantasmal-killer": {"condition": "Frightened", "duration": 10},
        "banishment": {"condition": "Incapacitated", "duration": 10},
        "dominate-beast": {"condition": "Charmed", "duration": 10},
        "dominate-person": {"condition": "Charmed", "duration": 10},
        "dominate-monster": {"condition": "Charmed", "duration": 10},
        "eyebite": {"condition": "Frightened", "duration": 10},
        "flesh-to-stone": {"condition": "Restrained", "duration": 10},
    }
    if index in SPELL_CONDITIONS:
        data["applies_condition"] = SPELL_CONDITIONS[index]

    # Magic Missile special case: auto-hit, 3 darts of 1d4+1
    if index == "magic-missile":
        data["damage"] = {
            "damage_dice": "3d4+3",  # 3 darts × (1d4+1), simplified
            "damage_type": {"name": "Force"},
        }
        # No attack_type, no save — engine falls through to auto-hit branch

    return {
        "id": index,
        "name": name,
        "data": data,
    }


def _extract_damage_dice(damage_info: dict, spell_level: int, index: str) -> str:
    """Extract the damage dice string from SRD damage structure."""
    # Priority 1: damage_at_slot_level (leveled spells)
    at_slot = damage_info.get("damage_at_slot_level")
    if at_slot:
        # Use base level for the spell
        dice = at_slot.get(str(spell_level))
        if dice:
            return dice
        # Fallback to lowest available slot
        for lvl in sorted(at_slot.keys(), key=int):
            return at_slot[lvl]

    # Priority 2: damage_at_character_level (cantrips that scale)
    at_char = damage_info.get("damage_at_character_level")
    if at_char:
        # Use level 1 as default (cantrip base damage)
        return at_char.get("1", "1d4")

    # Priority 3: flat damage_dice field
    if "damage_dice" in damage_info:
        return damage_info["damage_dice"]

    return "1d4"  # absolute fallback


async def lookup_spell(spell_name: str, db: AsyncSession) -> Optional[dict]:
    """Look up a spell from the spells table by name (fuzzy match)."""
    # Exact match first
    result = await db.execute(
        select(spells_table.c.data)
        .where(spells_table.c.name.ilike(spell_name))
    )
    row = result.scalar()
    if row:
        return json.loads(row) if isinstance(row, str) else row

    # Partial match
    result = await db.execute(
        select(spells_table.c.data)
        .where(spells_table.c.name.ilike(f"%{spell_name}%"))
    )
    row = result.scalar()
    if row:
        return json.loads(row) if isinstance(row, str) else row

    return None


async def resolve_spell_for_cast(
    spell_ref: dict,
    actor_class: str,
    db: AsyncSession
) -> Optional[dict]:
    """Given a spell reference from a character's sheet_data, resolve it to
    a fully normalized spell dict ready for the engine.

    Returns None if the spell is not in Tier A or can't be found.
    """
    spell_name = spell_ref.get("name", "") if isinstance(spell_ref, dict) else str(spell_ref)
    spell_index = spell_ref.get("id", "") if isinstance(spell_ref, dict) else ""

    # Check Tier A whitelist
    if spell_index and spell_index in TIER_A_SPELLS:
        pass  # whitelisted by index
    elif not any(spell_name.lower() in ta.replace("-", " ") for ta in TIER_A_SPELLS):
        return None  # not in Tier A

    # If the spell ref already has rich data (e.g., SRD format from compendium fetch),
    # normalize and return
    if isinstance(spell_ref, dict) and (spell_ref.get("damage") or spell_ref.get("dc") or spell_ref.get("attack_type") or spell_ref.get("heal_at_slot_level")):
        return normalize_spell_for_engine(spell_ref)

    # If the spell ref has nested data that's already engine-compatible, check it
    if isinstance(spell_ref, dict) and isinstance(spell_ref.get("data"), dict):
        inner = spell_ref["data"]
        if inner.get("damage") or inner.get("save") or inner.get("attack_type") or inner.get("heal_at_slot_level"):
            return spell_ref  # already in engine format

    # Otherwise, look up from DB and normalize
    srd_spell = await lookup_spell(spell_name, db)
    if srd_spell:
        return normalize_spell_for_engine(srd_spell)

    return None


# ── Spell Slot Management ──

# Standard full caster slot table (Wizard, Cleric, Druid, Bard, Sorcerer)
FULL_CASTER_SLOTS = {
    1: {1: 2}, 2: {1: 3}, 3: {1: 4, 2: 2}, 4: {1: 4, 2: 3},
    5: {1: 4, 2: 3, 3: 2}, 6: {1: 4, 2: 3, 3: 3},
    7: {1: 4, 2: 3, 3: 3, 4: 1}, 8: {1: 4, 2: 3, 3: 3, 4: 2},
    9: {1: 4, 2: 3, 3: 3, 4: 3, 5: 1}, 10: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2},
}

# Half caster slot table (Paladin, Ranger) — slots start at class level 2
HALF_CASTER_SLOTS = {
    1: {}, 2: {1: 2}, 3: {1: 3}, 4: {1: 3}, 5: {1: 4, 2: 2},
    6: {1: 4, 2: 2}, 7: {1: 4, 2: 3}, 8: {1: 4, 2: 3},
    9: {1: 4, 2: 3, 3: 2}, 10: {1: 4, 2: 3, 3: 2},
}

# Warlock pact magic — fewer slots but they're all max level, refresh on short rest
WARLOCK_SLOTS = {
    1: {1: 1}, 2: {1: 2}, 3: {2: 2}, 4: {2: 2}, 5: {3: 2},
    6: {3: 2}, 7: {4: 2}, 8: {4: 2}, 9: {5: 2}, 10: {5: 2},
}

FULL_CASTERS = {"wizard", "cleric", "druid", "bard", "sorcerer"}
HALF_CASTERS = {"paladin", "ranger"}


def get_max_slots(role: str, level: int) -> Dict[int, int]:
    """Get max spell slots for a class at a given level. Keys are spell level, values are slot count."""
    role_lower = role.lower()
    if role_lower == "warlock":
        return dict(WARLOCK_SLOTS.get(min(level, 10), {}))
    elif role_lower in HALF_CASTERS:
        return dict(HALF_CASTER_SLOTS.get(min(level, 10), {}))
    elif role_lower in FULL_CASTERS:
        return dict(FULL_CASTER_SLOTS.get(min(level, 10), {}))
    return {}  # Non-casters (Fighter, Barbarian, Monk, Rogue)


def init_spell_slots(sheet_data: dict, role: str, level: int) -> None:
    """Initialize spell slot tracking in sheet_data if not already present."""
    if "spell_slots_max" not in sheet_data:
        max_slots = get_max_slots(role, level)
        sheet_data["spell_slots_max"] = max_slots
        sheet_data["spell_slots_current"] = dict(max_slots)


def consume_spell_slot(sheet_data: dict, spell_level: int) -> bool:
    """Consume a spell slot. Returns True if successful, False if no slots available."""
    if spell_level == 0:
        return True  # Cantrips are free

    current = sheet_data.get("spell_slots_current", {})

    # Try the exact level first, then higher levels (upcasting)
    for lvl in range(spell_level, 10):
        key = str(lvl)
        if current.get(key, 0) > 0:
            current[key] -= 1
            sheet_data["spell_slots_current"] = current
            return True

    return False


def restore_spell_slots(sheet_data: dict, role: str, level: int, rest_type: str = "long") -> None:
    """Restore spell slots on rest. Long rest restores all. Short rest restores Warlock slots only."""
    max_slots = get_max_slots(role, level)

    if rest_type == "long" or role.lower() == "warlock":
        sheet_data["spell_slots_current"] = dict(max_slots)
        sheet_data["spell_slots_max"] = dict(max_slots)
    # Short rest: only Warlocks recover slots (already handled above)
