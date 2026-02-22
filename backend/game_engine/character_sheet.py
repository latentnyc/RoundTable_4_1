import math

class CharacterSheet:
    def __init__(self, data: dict):
        self.data = data

        # Stats could be top-level (primitive dict) or inside sheet_data (model dump)
        self.stats = data.get("stats", {})
        if not self.stats and "sheet_data" in data and isinstance(data["sheet_data"], dict):
            self.stats = data["sheet_data"].get("stats", {})

        # Support flat structure (Pydantic model dump) vs nested structure
        if "hp_current" in data:
             self.hp = {"current": int(data["hp_current"]), "max": int(data.get("hp_max", 10))}
        else:
             self.hp = data.get("hp", {"current": 10, "max": 10})

        self.name = data.get("name", "Unknown")

    def get_mod(self, stat: str) -> int:
        score = next((v for k, v in self.stats.items() if str(k).lower() == stat.lower()), 10)
        return math.floor((int(score) - 10) / 2)

    def get_save(self, stat: str) -> int:
        return self.get_mod(stat)

    def take_damage(self, amount: int) -> str:
        self.hp["current"] = max(0, self.hp["current"] - amount)
        if self.hp["current"] == 0:
            return f"{self.name} is unconscious!"
        return f"{self.name} takes {amount} damage. ({self.hp['current']}/{self.hp['max']} HP)"

    def heal(self, amount: int) -> str:
        self.hp["current"] = min(self.hp["max"], self.hp["current"] + amount)
        return f"{self.name} heals for {amount}. ({self.hp['current']}/{self.hp['max']} HP)"

    @property
    def equipment(self):
        if "sheet_data" in self.data and isinstance(self.data["sheet_data"], dict):
            if "equipment" in self.data["sheet_data"]:
                return self.data["sheet_data"]["equipment"]
        if "data" in self.data and isinstance(self.data["data"], dict):
            if "equipment" in self.data["data"]:
                return self.data["data"]["equipment"]
        return self.data.get("equipment", [])

    def get_weapon(self):
        for item in self.equipment:
            if isinstance(item, dict) and item.get("type") == "Weapon":
                return item

        # Fallback for monsters/NPCs without standard equipment arrays
        actions = self.data.get("data", {}).get("actions", [])
        if not actions:
            actions = self.data.get("actions", [])

        for action in actions:
            if action.get("damage") and isinstance(action["damage"], list):
                dmg_list = action["damage"]
                if len(dmg_list) > 0:
                    dmg_dice = dmg_list[0].get("damage_dice", "1d4")
                    # engine.py dynamically adds stat modifiers, so we strip hardcoded flat mods from the monster dice string
                    clean_dice = dmg_dice.split("+")[0].strip()
                    clean_dice = clean_dice.split("-")[0].strip()

                    is_ranged = "ranged" in action.get("desc", "").lower()
                    is_finesse = "finesse" in action.get("desc", "").lower()

                    properties = []
                    if is_finesse:
                        properties.append({"name": "Finesse"})

                    w_type = "Ranged Weapon" if is_ranged else "Melee Weapon"

                    return {
                        "name": action.get("name", "Natural Weapon"),
                        "type": "Weapon",
                        "data": {
                            "type": w_type,
                            "damage": {"damage_dice": clean_dice},
                            "properties": properties
                        }
                    }

        return None

    def get_ac(self):
        base_ac = 10
        dex_mod = self.get_mod("dexterity")

        armor = None
        shield = None
        for item in self.equipment:
            if isinstance(item, dict) and item.get("type") == "Armor":
                item_subtype = item.get("data", {}).get("type", "")
                if "Shield" in item_subtype:
                    shield = item
                else:
                    armor = item

        if isinstance(armor, dict):
            armor_data = armor.get("data") or {}
            ac_info = armor_data.get("armor_class") or {}
            base_ac = ac_info.get("base", 10)
            if ac_info.get("dex_bonus", False):
                max_bonus = ac_info.get("max_bonus")
                if max_bonus is not None and dex_mod > max_bonus:
                    base_ac += max_bonus
                else:
                    base_ac += dex_mod
        else:
            base_ac += dex_mod

        if isinstance(shield, dict):
            shield_data = shield.get("data") or {}
            ac_info = shield_data.get("armor_class") or {}
            base_ac += ac_info.get("base", 2)

        explicit_ac = self.data.get("ac", 10)

        # Fallback for monsters (which define AC in an array or single integer inside their data dictionary)
        monster_ac_data = self.data.get("data", {}).get("armor_class", [])
        if not monster_ac_data:
            monster_ac_data = self.data.get("armor_class", [])

        monster_ac = 0
        if isinstance(monster_ac_data, list) and len(monster_ac_data) > 0:
            mac = monster_ac_data[0]
            if isinstance(mac, dict):
                monster_ac = mac.get("value", 10)
        elif isinstance(monster_ac_data, int):
            monster_ac = monster_ac_data

        return max(base_ac, explicit_ac, monster_ac)
