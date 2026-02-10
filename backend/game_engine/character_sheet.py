import math

class CharacterSheet:
    def __init__(self, data: dict):
        self.data = data
        self.stats = data.get("stats", {})
        self.hp = data.get("hp", {"current": 10, "max": 10})
        self.name = data.get("name", "Unknown")
        
    def get_mod(self, stat: str) -> int:
        score = self.stats.get(stat.lower(), 10)
        return math.floor((score - 10) / 2)

    def get_save(self, stat: str) -> int:
        # TODO: Add proficiency bonus logic
        return self.get_mod(stat)

    def take_damage(self, amount: int) -> str:
        self.hp["current"] = max(0, self.hp["current"] - amount)
        if self.hp["current"] == 0:
            return f"{self.name} is unconscious!"
        return f"{self.name} takes {amount} damage. ({self.hp['current']}/{self.hp['max']} HP)"

    def heal(self, amount: int) -> str:
        self.hp["current"] = min(self.hp["max"], self.hp["current"] + amount)
        return f"{self.name} heals for {amount}. ({self.hp['current']}/{self.hp['max']} HP)"
