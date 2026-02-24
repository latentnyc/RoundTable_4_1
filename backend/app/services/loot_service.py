import json
import random
from typing import TYPE_CHECKING
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.state_service import StateService
from db.schema import locations

if TYPE_CHECKING:
    from app.models import GameState

class LootService:
    @staticmethod
    def generate_loot(entity) -> list[str]:
        """
        Generates a list of item IDs based on the entity's loot table.
        """
        loot_items = []

        # Access loot data
        loot_data = None
        if hasattr(entity, 'loot') and entity.loot:
            loot_data = entity.loot
        elif hasattr(entity, 'data') and entity.data:
            loot_data = entity.data.get('loot')

        if not loot_data:
            return []

        # 1. Guaranteed Items
        guaranteed = loot_data.get('guaranteed', [])
        loot_items.extend(guaranteed)

        # 2. Random Items
        random_drops = loot_data.get('random', [])
        for drop in random_drops:
            chance = drop.get('chance', 0.0)
            if random.random() < chance:
                item_id = drop.get('item_id')
                if item_id:
                    loot_items.append(item_id)

        return loot_items

    @staticmethod
    async def open_vessel(campaign_id: str, actor_name: str, vessel_name: str, db: AsyncSession):
        """
        Unlocks/Opens a vessel by name and returns its contents. Also handles doors and chests.
        """
        from app.services.game_service import GameService
        from app.services.combat_service import CombatService
        from app.models import Vessel, Coordinates

        game_state = await StateService.get_game_state(campaign_id, db)
        if not game_state:
            return {"success": False, "message": "No active game state."}

        interrupted, opp_msg, latest_state = await CombatService._handle_opportunity_attack(campaign_id, actor_name, f"open {vessel_name}", db, game_state)
        game_state = await StateService.get_game_state(campaign_id, db)
        if interrupted:
            return {"success": False, "message": opp_msg, "game_state": latest_state}

        # 1. Check permanent architecture (interactables)
        query = select(locations.c.data).where(locations.c.id == game_state.location.id)
        loc_res = await db.execute(query)
        loc_data_str = loc_res.scalar_one_or_none()

        loc_data = json.loads(loc_data_str) if loc_data_str else {}
        interactables = loc_data.get('interactables', [])

        target_interactable = None
        target_idx = -1
        for i, item in enumerate(interactables):
            if vessel_name.lower() in item.get('name', '').lower() or vessel_name.lower() in item.get('id', '').lower():
                target_interactable = item
                target_idx = i
                break

        if target_interactable:
            item_type = target_interactable.get('type')
            current_state = target_interactable.get('state', 'closed')

            if current_state == 'open':
                return {"success": False, "message": f"The {target_interactable['name']} is already open."}

            interactables[target_idx]['state'] = 'open'
            loc_data['interactables'] = interactables

            stmt = (
                update(locations)
                .where(locations.c.id == game_state.location.id)
                .values(data=json.dumps(loc_data))
            )
            await db.execute(stmt)
            await db.commit()

            if item_type == 'door':
                reveal_text = ""
                t_id = target_interactable.get('target_location_id')

                # Fallback to connection list if target_location_id isn't on the interactable
                if not t_id:
                    desc_data = loc_data.get('description', {})
                    connections = desc_data.get('connections', [])
                    if connections:
                        t_id = connections[0].get('target_id')

                if t_id:
                     q_dest = select(locations.c.id, locations.c.source_id, locations.c.name, locations.c.data).where(
                         locations.c.campaign_id == campaign_id,
                         locations.c.source_id == t_id
                     )
                     dest_res = await db.execute(q_dest)
                     dest_row = dest_res.first()

                     if dest_row:
                         d_data = json.loads(dest_row.data)
                         vis = d_data.get('description', {}).get('visual', '')
                         if vis:
                              vis_lower = vis[0].lower() + vis[1:] if vis else ""
                              reveal_text = f", revealing {vis_lower}"

                         # FOG OF WAR: Add to discovered locations
                         from app.models import Location
                         already_discovered = any(dl.source_id == t_id for dl in game_state.discovered_locations)
                         if not already_discovered and game_state.location.source_id != t_id:
                             new_loc = Location(
                                 id=dest_row.id,
                                 source_id=dest_row.source_id,
                                 name=dest_row.name,
                                 description=str(d_data.get('description', '')),
                                 interactables=d_data.get('interactables', []),
                                 walkable_hexes=d_data.get('walkable_hexes', [])
                             )
                             game_state.discovered_locations.append(new_loc)
                             await StateService.save_game_state(campaign_id, game_state, db)
                             await db.commit()

                return {"success": True, "message": f"**{actor_name}** creaks open the {target_interactable['name']}{reveal_text}."}
            elif item_type == 'chest':
                contents = target_interactable.get('contents', [])
                currency = target_interactable.get('currency', {"pp": 0, "gp": 0, "sp": 0, "cp": 0})

                chest_name = target_interactable.get('name', 'Chest')
                existing = next((v for v in game_state.vessels if v.name == chest_name), None)

                if not existing:
                    actor = next((p for p in game_state.party if p.name == actor_name), None)
                    new_vessel = Vessel(
                        name=chest_name,
                        description=f"An opened {chest_name.lower()}.",
                        position=actor.position if actor else Coordinates(q=0, r=0, s=0),
                        contents=contents,
                        currency=currency
                    )
                    game_state.vessels.append(new_vessel)
                    existing = new_vessel

                    target_interactable['contents'] = []
                    target_interactable['currency'] = {"pp": 0, "gp": 0, "sp": 0, "cp": 0}

                    stmt = (
                        update(locations)
                        .where(locations.c.id == game_state.location.id)
                        .values(data=json.dumps(loc_data))
                    )
                    await db.execute(stmt)

                    game_state.location.description = json.dumps(loc_data)
                    await StateService.save_game_state(campaign_id, game_state, db)
                    await db.commit()

                return {
                    "success": True,
                    "message": f"**{actor_name}** opens the {target_interactable['name']}.",
                    "vessel": existing
                }
            return {"success": True, "message": f"**{actor_name}** opens the {target_interactable['name']}."}

        # 2. Check GameState transient vessels (corpses)
        target_vessel = None
        for v in game_state.vessels:
            if v.name.lower() == vessel_name.lower():
                target_vessel = v
                break

        if not target_vessel:
             for v in game_state.vessels:
                 if vessel_name.lower() in v.name.lower():
                     target_vessel = v
                     break

        if not target_vessel:
            return {"success": False, "message": f"Could not find '{vessel_name}' to open."}

        # Format Contents
        items_msg = "Nothing"
        if target_vessel.contents:
             cleaned_items = [i.replace('-', ' ').title() for i in target_vessel.contents]
             items_msg = ", ".join(cleaned_items)

        curr_parts = []
        if target_vessel.currency:
            for c_type in ["pp", "gp", "sp", "cp"]:
                val = target_vessel.currency.get(c_type, 0)
                if val > 0:
                     curr_parts.append(f"{val} {c_type}")

        currency_msg = ", ".join(curr_parts)
        if not currency_msg: currency_msg = "No currency"

        msg = f"**{actor_name}** searches {target_vessel.name}. Inside you find: {items_msg}.\nWealth: {currency_msg}."

        return {
            "success": True,
            "message": msg,
            "vessel": target_vessel
        }

    @staticmethod
    async def take_items(campaign_id: str, actor_id: str, vessel_id: str, item_ids: list, take_currency: bool, db: AsyncSession):
        """
        Transfers items and currency from a vessel to a player's inventory.
        """
        game_state = await StateService.get_game_state(campaign_id, db)
        if not game_state:
            return {"success": False, "message": "No active game state."}

        actor = next((p for p in game_state.party if p.id == actor_id), None)
        if not actor:
            return {"success": False, "message": "Actor not found in party."}

        vessel = next((v for v in game_state.vessels if v.id == vessel_id), None)
        if not vessel:
            return {"success": False, "message": "Vessel not found."}

        taken_items = []
        for i_id in item_ids:
            if i_id in vessel.contents:
                vessel.contents.remove(i_id)
                actor.inventory.append(i_id)
                taken_items.append(i_id)

        taken_currency = {}
        if take_currency and vessel.currency:
            for c_type, amount in vessel.currency.items():
                if amount > 0:
                    actor.currency[c_type] = actor.currency.get(c_type, 0) + amount
                    taken_currency[c_type] = amount
            vessel.currency = {"pp": 0, "gp": 0, "sp": 0, "cp": 0}

        await StateService.save_game_state(campaign_id, game_state, db)
        await db.commit()
        await db.commit()

        return {
            "success": True,
            "taken_items": taken_items,
            "taken_currency": taken_currency,
            "vessel": vessel,
            "actor": actor
        }

    @staticmethod
    async def equip_item(campaign_id: str, actor_id: str, item_id: str, is_equip: bool, db: AsyncSession, target_slot: str = None):
        """
        Moves an item between inventory and equipment.
        Handles target_slot (main_hand, off_hand, armor, etc.) to support Paper Doll UI.
        """
        game_state = await StateService.get_game_state(campaign_id, db)
        if not game_state:
            return {"success": False, "message": "No active game state."}

        actor = next((p for p in game_state.party if p.id == actor_id), None)
        if not actor:
            return {"success": False, "message": "Actor not found."}

        if 'equipment' not in actor.sheet_data:
            actor.sheet_data['equipment'] = []

        if is_equip:
            # Find item in inventory
            inventory_item = None
            for item in actor.inventory:
                if isinstance(item, str) and item == item_id:
                    inventory_item = item
                    break
                elif isinstance(item, dict) and (item.get('id') == item_id or item.get('name') == item_id):
                    inventory_item = item
                    break

            if not inventory_item:
                return {"success": False, "message": "Item not in inventory."}

            if isinstance(inventory_item, dict):
                item_data = inventory_item
            else:
                # Fallback basic item dict if it was just a string
                is_weapon = item_id.startswith("wpn-")
                is_armor = item_id.startswith("arm-")
                i_type = "Weapon" if is_weapon else ("Armor" if is_armor else "Item")

                # Try to extract stats from compendium or default
                item_data = {"id": item_id, "name": item_id.replace('-', ' ').title().replace('Wpn ', '').replace('Arm ', '').replace('Itm ', ''), "type": i_type}
                if is_weapon:
                    item_data["data"] = {"damage": {"damage_dice": "1d4"}}
                if is_armor:
                    item_data["data"] = {"armor_class": {"base": 11}}

            # Determine Intended Slot
            item_type = item_data.get("type", "")
            item_sub_type = item_data.get("data", {}).get("type", "")

            slot = target_slot
            if not slot:
                if item_sub_type == "Shield":
                    slot = "off_hand"
                elif item_type == "Armor":
                    slot = "armor"
                elif item_type == "Weapon":
                    slot = "main_hand"
                else:
                    slot = "accessory"

            # Helper to check if item has "Two-Handed" property
            def is_two_handed(item_dict):
                props = item_dict.get("data", {}).get("properties", [])
                for p in props:
                    if isinstance(p, dict) and p.get("name", "").lower() == "two-handed":
                        return True
                return False

            # Enforce Equipment Limits based on Slot Logic
            equipped_items = actor.sheet_data['equipment']
            items_to_unequip = []

            if slot == "armor":
                items_to_unequip = [eq for eq in equipped_items if isinstance(eq, dict) and eq.get("type", "") == "Armor" and eq.get("data", {}).get("type", "") != "Shield"]
            elif slot == "off_hand":
                # Unequip existing Shield OR Off-Hand weapon
                existing_offhands = [
                    eq for eq in equipped_items if isinstance(eq, dict) and (
                        eq.get("data", {}).get("type", "") == "Shield" or
                        (eq.get("type", "") == "Weapon" and eq != inventory_item and "off_hand" in str(eq)) # Need a generic way if two weapons
                    )
                ]
                items_to_unequip.extend([eq for eq in equipped_items if isinstance(eq, dict) and eq.get("data", {}).get("type", "") == "Shield"])

                weapons_equipped = [eq for eq in equipped_items if isinstance(eq, dict) and eq.get("type", "") == "Weapon"]
                if item_type == "Weapon" and len(weapons_equipped) >= 2:
                     items_to_unequip.append(weapons_equipped[-1])

                if weapons_equipped and is_two_handed(weapons_equipped[0]):
                     items_to_unequip.append(weapons_equipped[0])

            elif slot == "main_hand":
                weapons_equipped = [eq for eq in equipped_items if isinstance(eq, dict) and eq.get("type", "") == "Weapon"]
                if weapons_equipped:
                    items_to_unequip.append(weapons_equipped[0])

                if is_two_handed(item_data):
                     shields = [eq for eq in equipped_items if isinstance(eq, dict) and eq.get("data", {}).get("type", "") == "Shield"]
                     items_to_unequip.extend(shields)
                     if len(weapons_equipped) >= 2:
                         items_to_unequip.append(weapons_equipped[1]) # The offhand weapon

            # Unequip old items taking up the slot (deduplicate just in case)
            for eq_item in list({v['id']:v for v in items_to_unequip if isinstance(v, dict)}.values()):
                if eq_item in equipped_items:
                    equipped_items.remove(eq_item)
                    actor.inventory.append(eq_item) # Preserve stats by appending dict

            # Move from inventory to equipment
            actor.inventory.remove(inventory_item)
            actor.sheet_data['equipment'].append(item_data)

            await StateService.save_game_state(campaign_id, game_state, db)
            return {"success": True, "message": f"Equipped {item_data.get('name', item_id)}.", "actor": actor}

        else:
            # Unequip
            if 'equipment' not in actor.sheet_data:
                return {"success": False, "message": "No equipment."}

            # Find item in equipment
            equipped_items = actor.sheet_data['equipment']
            item_to_remove = next((i for i in equipped_items if isinstance(i, dict) and (i.get('id') == item_id or i.get('name', '').lower() == item_id.lower())), None)

            if not item_to_remove:
                return {"success": False, "message": "Item not equipped."}

            equipped_items.remove(item_to_remove)

            # Add back to inventory preserving full data
            actor.inventory.append(item_to_remove)

            await StateService.save_game_state(campaign_id, game_state, db)
            return {"success": True, "message": f"Unequipped {item_to_remove.get('name', item_id)}.", "actor": actor}
