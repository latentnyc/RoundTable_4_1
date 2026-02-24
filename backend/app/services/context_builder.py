import json
import logging
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.models import GameState, Player, Enemy, NPC

logger = logging.getLogger(__name__)

async def get_stat_block(sheet_data: dict) -> str:
    """Formats core stats like (STR 16, DEX 12, ...)"""
    stats = sheet_data.get("stats", {})
    if not stats:
        return ""

    # Standard order
    order = ["str", "dex", "con", "int", "wis", "cha"]
    parts = []
    for stat in order:
        if stat in stats:
            val = stats[stat]
            # Calculate mod? (val - 10) // 2
            mod = (int(val) - 10) // 2
            sign = "+" if mod >= 0 else ""
            parts.append(f"{stat.upper()} {val} ({sign}{mod})")

    return ", ".join(parts)

async def format_player_state(party: List[Player]) -> str:
    """
    Formats the party state into a narrative block.
    Includes: Name, Race/Class, HP status, AC, Weapons, Active Conditions.
    """

    # Return as JSON block to prevent narrative leak
    import json
    party_data = []
    for p in party:
        sheet = p.sheet_data or {}
        stats_str = await get_stat_block(sheet)

        # Calculate Status
        hp_percent = p.hp_current / p.hp_max if p.hp_max > 0 else 0
        status = "Healthy"
        if hp_percent <= 0: status = "Unconscious"
        elif hp_percent < 0.5: status = "Injured"

        # Equipment
        equipment = sheet.get("equipment", [])
        equipped = []
        if equipment:
             for item in equipment:
                 if isinstance(item, dict): equipped.append(item.get("name", "Item"))
                 elif isinstance(item, str): equipped.append(item)

        p_info = {
            "name": p.name,
            "race": p.race,
            "class": p.role,
            "level": p.level,
            "hp": f"{p.hp_current}/{p.hp_max}",
            "status": status,
            "ac": p.ac,
            "stats": stats_str,
            "equipment": equipped
        }
        party_data.append(p_info)

    return "```json\n" + json.dumps(party_data, indent=2) + "\n```"

async def format_npc_state(npcs: List[NPC]) -> str:
    """
    Formats the list of active NPCs in the GameState.
    """
    if not npcs:
        return "None visible."

    lines = []
    for n in npcs:
        # Status based on HP
        hp_percent = n.hp_current / n.hp_max if n.hp_max > 0 else 0
        status = "Healthy"
        if hp_percent <= 0: status = "Unconscious/Dead"
        elif hp_percent < 0.5: status = "Injured"

        # Tone/Desc from data
        data = n.data or {}
        voice = data.get('voice', {})
        tone = voice.get('tone', 'Unknown')
        race = data.get('race', 'Unknown')
        desc = data.get('description', '')

        # Disposition
        disposition = data.get('disposition', {})
        attitude = disposition.get('attitude', 'Neutral')

        # Identity Logic
        # If identified: "SILAS (Human Shopkeeper)"
        # If not: "HUMAN SHOPKEEPER" (or similar fallback)
        is_identified = getattr(n, 'identified', False) # Default false if missing

        if is_identified:
            display_name = f"{n.name.upper()} ({race} {n.role})"
        else:
            display_name = n.unidentified_name.upper() if n.unidentified_name else f"{race.upper()} {n.role.upper()}"

        line = f"- **{display_name}**: {status} | Attitude: {attitude} [{tone}]"
        if desc:
            line += f" - _{desc}_"

        llm_desc = getattr(n, 'llm_description', None) or data.get('llm_description', '')
        if llm_desc:
            line += f" - *Visuals*: {llm_desc}"

        # Knowledge Hints (for DM context only)
        knowledge = data.get('knowledge', [])
        if knowledge:
            k_list = [f"[{k.get('id')}]: {k.get('description')}" for k in knowledge]
            line += f"\n  - *Secret Knowledge*: {'; '.join(k_list)}"

        # Voice/Bark Hints
        barks = data.get('voice', {}).get('barks', {})
        if barks:
            # Just show a few sample keys or aggression barks to set tone
            aggro = barks.get('aggro', [])
            if aggro:
                line += f"\n  - *Voice Style*: \"{aggro[0]}\""

        lines.append(line)

    return "\n".join(lines)

async def build_narrative_context(db: AsyncSession, campaign_id: str, state: GameState) -> str:
    """
    Constructs the rich narrative context block.
    """
    # 1. Location Header
    loc_header = f"**CURRENT LOCATION**: {state.location.name}"
    loc_desc = f"_{state.location.description}_"

    # 2. Party Context
    party_block = await format_player_state(state.party)

    # 3. NPC Context
    npc_block = await format_npc_state(state.npcs)

    # 4. Combat/Enemy Context
    enemy_block = ""
    if state.enemies:
        enemy_lines = []
        for e in state.enemies:
            status = "Healthy"
            if e.hp_current <= 0: status = "Dead"
            elif e.hp_current < e.hp_max / 2: status = "Bloodied"

            # Identity Logic for Enemies
            is_identified = getattr(e, 'identified', False)
            if is_identified:
                display_name = f"{e.name.upper()} ({e.type})"
            else:
                display_name = e.type.upper()

            line = f"- {display_name}: {status}"

            e_data = getattr(e, 'data', {}) or {}
            desc = getattr(e, 'unidentified_description', None) or e_data.get('unidentified_description', '')
            if desc:
                line += f" - _{desc}_"

            llm_desc = getattr(e, 'llm_description', None) or e_data.get('llm_description', '')
            if llm_desc:
                line += f" - *Visuals*: {llm_desc}"

            enemy_lines.append(line)
        if enemy_lines:
            enemy_block = "\n**ENEMIES**:\n" + "\n".join(enemy_lines)

    # 5. Visible Paths / Exits
    paths_block = "None visible."
    interactables_block = ""
    if state.location.source_id:
        try:
            # Fetch current location data to get 'connections'
            l_res = await db.execute(
                text("SELECT data FROM locations WHERE campaign_id = :cid AND source_id = :sid"),
                {"cid": campaign_id, "sid": state.location.source_id}
            )
            l_row = l_res.mappings().fetchone()
            if l_row:
                l_data = json.loads(l_row['data'])
                description_data = l_data.get('description', {})
                connections = description_data.get('connections', [])
                if connections:
                    exit_names = []
                    for conn in connections:
                        if isinstance(conn, dict):
                            direction = conn.get('direction', 'unknown')
                            desc = conn.get('description', '')
                            if desc:
                                exit_names.append(f"- {direction.capitalize()}: {desc}")
                            else:
                                exit_names.append(f"- {direction.capitalize()} (pathway)")
                        else:
                            # Fallback for old string IDs
                            c_res = await db.execute(
                                text("SELECT name FROM locations WHERE campaign_id = :cid AND source_id = :sid"),
                                {"cid": campaign_id, "sid": conn}
                            )
                            c_row = c_res.mappings().fetchone()
                            if c_row:
                                exit_names.append(f"- {c_row['name']}")

                    if exit_names:
                        paths_block = "\n".join(exit_names)

                # Also process interactables (Doors/Chests)
                interactables = l_data.get('interactables', [])
                if interactables:
                    int_names = []
                    for it in interactables:
                        state_str = f" ({it.get('state')})" if 'state' in it else ""
                        int_names.append(f"- {it.get('name')}{state_str}")
                    if int_names:
                        interactables_block = "\n**INTERACTABLES**:\n" + "\n".join(int_names)
        except SQLAlchemyError as e:
            logger.error("Database error fetching paths/interactables: %s", str(e))

    # Assembly
    context = f"""
{loc_header}
{loc_desc}
{interactables_block}

**VISIBLE PATHS**:
{paths_block}

**NPCS PRESENT**:
{npc_block}

**PARTY STATUS**:
{party_block}
{enemy_block}
"""
    return context.strip()
