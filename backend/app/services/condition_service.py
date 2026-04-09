"""
Condition service: apply, query, tick, and remove conditions on entities.

Implements the 11 mechanically-enforceable 5e SRD conditions.
"""
import logging
from typing import List, Optional, Set
from app.models import Condition

logger = logging.getLogger(__name__)

# ── Condition Effects Registry ──
# Maps condition name to its mechanical effects.
# Effects are checked by the combat engine and turn manager.

CONDITION_EFFECTS = {
    "Blinded": {
        "attack_disadvantage": True,    # This entity has disadvantage on attacks
        "attacked_advantage": True,     # Attacks against this entity have advantage
    },
    "Charmed": {
        "cannot_attack_source": True,   # Cannot attack the charmer (source_id)
    },
    "Deafened": {
        # Primarily narrative — fails hearing checks
    },
    "Frightened": {
        "attack_disadvantage": True,    # Disadvantage on attacks while source visible
        "check_disadvantage": True,     # Disadvantage on ability checks
    },
    "Grappled": {
        "speed_zero": True,             # Speed becomes 0
    },
    "Incapacitated": {
        "skip_turn": True,              # Cannot take actions or reactions
    },
    "Invisible": {
        "attack_advantage": True,       # This entity has advantage on attacks
        "attacked_disadvantage": True,  # Attacks against this entity have disadvantage
    },
    "Paralyzed": {
        "skip_turn": True,
        "auto_fail_str_dex": True,      # Auto-fail STR and DEX saves
        "attacked_advantage": True,
        "melee_auto_crit": True,        # Melee hits are automatic crits
    },
    "Petrified": {
        "skip_turn": True,
        "auto_fail_str_dex": True,
        "attacked_advantage": True,
        "damage_resistance": True,      # Resistance to all damage
    },
    "Poisoned": {
        "attack_disadvantage": True,
        "check_disadvantage": True,
    },
    "Prone": {
        "attack_disadvantage": True,     # This entity has disadvantage on attacks
        "melee_attacked_advantage": True,  # Melee attacks against have advantage
        "ranged_attacked_disadvantage": True,  # Ranged attacks against have disadvantage
    },
    "Restrained": {
        "speed_zero": True,
        "attack_disadvantage": True,
        "attacked_advantage": True,
        "dex_save_disadvantage": True,
    },
    "Stunned": {
        "skip_turn": True,
        "auto_fail_str_dex": True,
        "attacked_advantage": True,
    },
    "Unconscious": {
        "skip_turn": True,
        "auto_fail_str_dex": True,
        "attacked_advantage": True,
        "melee_auto_crit": True,
    },
}


def apply_condition(entity, condition_name: str, duration: int = -1,
                    expires_on: str = "start", source_id: str = None,
                    save_dc: int = None, save_stat: str = None) -> bool:
    """Apply a condition to an entity. Returns True if newly applied, False if already present."""
    # Don't stack the same condition
    for c in entity.conditions:
        if c.name == condition_name:
            # Refresh duration if new one is longer
            if duration > c.duration:
                c.duration = duration
                c.source_id = source_id
                c.save_dc = save_dc
                c.save_stat = save_stat
            return False

    entity.conditions.append(Condition(
        name=condition_name,
        duration=duration,
        expires_on=expires_on,
        source_id=source_id,
        save_dc=save_dc,
        save_stat=save_stat,
    ))
    logger.debug(f"Applied {condition_name} to {entity.name} (duration={duration})")
    return True


def remove_condition(entity, condition_name: str) -> bool:
    """Remove a condition from an entity. Returns True if removed."""
    before = len(entity.conditions)
    entity.conditions = [c for c in entity.conditions if c.name != condition_name]
    removed = len(entity.conditions) < before
    if removed:
        logger.debug(f"Removed {condition_name} from {entity.name}")
    return removed


def has_condition(entity, condition_name: str) -> bool:
    """Check if an entity has a specific condition."""
    return any(c.name == condition_name for c in entity.conditions)


def get_active_effects(entity) -> Set[str]:
    """Get the set of all active mechanical effects for an entity.
    Returns effect keys like 'attack_disadvantage', 'skip_turn', etc."""
    effects = set()
    for condition in entity.conditions:
        cond_effects = CONDITION_EFFECTS.get(condition.name, {})
        effects.update(cond_effects.keys())
    return effects


def should_skip_turn(entity) -> bool:
    """Check if entity's conditions prevent them from acting."""
    effects = get_active_effects(entity)
    return "skip_turn" in effects


def has_speed_zero(entity) -> bool:
    """Check if entity's conditions prevent movement."""
    effects = get_active_effects(entity)
    return "speed_zero" in effects


def get_attack_modifiers(attacker, target, is_melee: bool = True) -> dict:
    """Determine advantage/disadvantage for an attack based on conditions.

    Returns {"advantage": bool, "disadvantage": bool}.
    If both are True, they cancel out (5e rules).
    """
    advantage = False
    disadvantage = False

    # Attacker's conditions
    attacker_effects = get_active_effects(attacker)
    if "attack_disadvantage" in attacker_effects:
        disadvantage = True
    if "attack_advantage" in attacker_effects:
        advantage = True

    # Charmed: cannot attack source
    for c in attacker.conditions:
        if c.name == "Charmed" and c.source_id == getattr(target, 'id', None):
            return {"advantage": False, "disadvantage": False, "blocked": True,
                    "reason": f"{attacker.name} is charmed and cannot attack {target.name}"}

    # Target's conditions
    target_effects = get_active_effects(target)
    if "attacked_advantage" in target_effects:
        advantage = True
    if "attacked_disadvantage" in target_effects:
        disadvantage = True

    # Prone special case: melee advantage, ranged disadvantage
    if has_condition(target, "Prone"):
        if is_melee:
            advantage = True
        else:
            disadvantage = True

    # If both advantage and disadvantage, they cancel (5e rules)
    if advantage and disadvantage:
        advantage = False
        disadvantage = False

    return {"advantage": advantage, "disadvantage": disadvantage, "blocked": False}


def get_save_modifiers(entity, save_stat: str) -> dict:
    """Determine advantage/disadvantage/auto-fail for a saving throw."""
    effects = get_active_effects(entity)

    if "auto_fail_str_dex" in effects and save_stat in ("strength", "dexterity"):
        return {"auto_fail": True, "advantage": False, "disadvantage": False}

    if "dex_save_disadvantage" in effects and save_stat == "dexterity":
        return {"auto_fail": False, "advantage": False, "disadvantage": True}

    return {"auto_fail": False, "advantage": False, "disadvantage": False}


def has_damage_resistance(entity) -> bool:
    """Check if entity has resistance to all damage (Petrified)."""
    effects = get_active_effects(entity)
    return "damage_resistance" in effects


def tick_conditions(entity) -> List[str]:
    """Tick condition durations at the start/end of an entity's turn.
    Call this at the appropriate turn phase (start or end).
    Returns list of expired condition names."""
    expired = []
    remaining = []

    for c in entity.conditions:
        if c.duration == 0:
            expired.append(c.name)
            continue
        if c.duration > 0:
            c.duration -= 1
            if c.duration == 0:
                expired.append(c.name)
                continue
        remaining.append(c)

    entity.conditions = remaining

    for name in expired:
        logger.debug(f"Condition {name} expired on {entity.name}")

    return expired


# ── Concentration ──

def break_concentration(caster, game_state=None) -> Optional[str]:
    """Break concentration, removing the spell's effect from the target.

    Returns the spell name that was broken, or None if not concentrating.
    """
    if not getattr(caster, 'concentrating_on', None):
        return None

    spell_name = caster.concentrating_on
    target_id = getattr(caster, 'concentration_target_id', None)

    # Remove the condition from the target
    if target_id and game_state:
        all_entities = list(getattr(game_state, 'party', [])) + \
                       list(getattr(game_state, 'enemies', [])) + \
                       list(getattr(game_state, 'npcs', []))
        target = next((e for e in all_entities if e.id == target_id), None)
        if target:
            # Remove conditions applied by this caster
            target.conditions = [
                c for c in target.conditions
                if c.source_id != caster.id
            ]

    caster.concentrating_on = None
    caster.concentration_target_id = None

    logger.info(f"{caster.name} lost concentration on {spell_name}")
    return spell_name


def start_concentration(caster, spell_name: str, target_id: str = None,
                        game_state=None) -> Optional[str]:
    """Start concentrating on a spell. Breaks existing concentration first.

    Returns the name of the previously concentrated spell if one was broken,
    or None if this is the first concentration.
    """
    broken = None
    if getattr(caster, 'concentrating_on', None):
        broken = break_concentration(caster, game_state)

    caster.concentrating_on = spell_name
    caster.concentration_target_id = target_id
    logger.debug(f"{caster.name} now concentrating on {spell_name}")
    return broken


def check_concentration_save(caster, damage: int) -> bool:
    """Check if caster maintains concentration after taking damage.

    DC = max(10, damage // 2). Returns True if concentration held.
    """
    if not getattr(caster, 'concentrating_on', None):
        return True  # Not concentrating, nothing to check

    from game_engine.character_sheet import CharacterSheet
    from game_engine.dice import Dice

    dc = max(10, damage // 2)
    sheet = CharacterSheet(caster.model_dump() if hasattr(caster, 'model_dump') else {})
    save_mod = sheet.get_save("constitution")
    roll = Dice.roll("1d20")
    total = roll["total"] + save_mod

    held = total >= dc
    logger.debug(f"Concentration save: {caster.name} rolled {total} vs DC {dc} — {'held' if held else 'BROKEN'}")
    return held
