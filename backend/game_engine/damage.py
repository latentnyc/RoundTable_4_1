"""Typed damage pipeline: resistance / immunity / vulnerability by damage type.

5e rules: immunity zeroes the damage, vulnerability doubles it, resistance halves it
(rounding down). A creature is normally not both resistant and vulnerable to the same
type; precedence here is immunity > vulnerability > resistance. ``resist_all`` models
effects (e.g. Petrified) that grant resistance to every damage type.

Note: SRD resistance entries can carry qualifiers like "...from nonmagical attacks".
We tokenize and match on the damage-type word only, so such a creature is treated as
resistant regardless of the magical-ness of the source. That over-applies in rare
cases; refine when the effect system tracks magical/silvered/adamantine sources.
"""
import re
from typing import Iterable, Set, Tuple

# The 13 canonical 5e damage types. Used to extract damage-type words from the
# free-form SRD resistance/immunity/vulnerability strings.
DAMAGE_TYPES = frozenset({
    "acid", "bludgeoning", "cold", "fire", "force", "lightning", "necrotic",
    "piercing", "poison", "psychic", "radiant", "slashing", "thunder",
})

_WORD_SPLIT = re.compile(r"[^a-z]+")


def tokenize_keywords(entries: Iterable) -> Set[str]:
    """Reduce raw SRD damage entries to a set of canonical damage-type words.

    SRD entries are free-form, e.g. ``"cold"`` or
    ``"bludgeoning, piercing, and slashing from nonmagical attacks"``. We split on
    non-letters and keep only words that name a real damage type, so qualifiers
    ("from nonmagical attacks") are dropped and a compound entry expands to each of
    its types. See the module docstring for the magical-source caveat this implies.
    """
    out: Set[str] = set()
    for entry in entries or ():
        for word in _WORD_SPLIT.split(str(entry).lower()):
            if word in DAMAGE_TYPES:
                out.add(word)
    return out


def damage_multiplier(
    damage_type: str,
    resistances: set,
    immunities: set,
    vulnerabilities: set,
    resist_all: bool = False,
) -> Tuple[float, str]:
    """Return (multiplier, label) for a damage type against the given keyword sets."""
    dt = (damage_type or "").strip().lower()
    if dt and dt in immunities:
        return 0.0, "IMMUNE"
    if dt and dt in vulnerabilities:
        return 2.0, "VULNERABLE"
    if resist_all or (dt and dt in resistances):
        return 0.5, "RESISTED"
    return 1.0, ""


def apply_resistances(
    amount: int,
    damage_type: str,
    *,
    resistances: Iterable = (),
    immunities: Iterable = (),
    vulnerabilities: Iterable = (),
    resist_all: bool = False,
) -> Tuple[int, str]:
    """Apply 5e resistance math to a damage amount; returns (final_amount, label)."""
    mult, label = damage_multiplier(
        damage_type, set(resistances), set(immunities), set(vulnerabilities), resist_all
    )
    amount = int(amount)
    if mult == 0.0:
        return 0, label
    if mult == 2.0:
        return amount * 2, label
    if mult == 0.5:
        return amount // 2, label
    return amount, label


def apply_typed_damage(amount: int, damage_type: str, target_sheet, resist_all: bool = False) -> Tuple[int, str]:
    """Convenience wrapper: read resist/immune/vuln keyword sets from a CharacterSheet target."""
    return apply_resistances(
        amount,
        damage_type,
        resistances=target_sheet.get_damage_resistances(),
        immunities=target_sheet.get_damage_immunities(),
        vulnerabilities=target_sheet.get_damage_vulnerabilities(),
        resist_all=resist_all,
    )
