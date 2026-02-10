import random
import re

class Dice:
    @staticmethod
    def roll(expression: str) -> dict:
        """
        Parses strings like "1d20+5", "2d6", "1d20 adv"
        Returns { "total": int, "rolls": list, "detail": str }
        """
        # Simple parser for now
        expression = expression.lower().strip()
        advantage = "adv" in expression
        disadvantage = "dis" in expression
        
        # Remove words
        clean_expr = expression.replace("adv", "").replace("dis", "").strip()
        
        if "d" not in clean_expr:
            try:
                val = int(clean_expr)
                return {"total": val, "rolls": [], "detail": str(val)}
            except:
                return {"total": 0, "rolls": [], "detail": "Invalid"}

        parts = clean_expr.split("+")
        total = 0
        details = []
        all_rolls = []

        for part in parts:
            part = part.strip()
            if "d" in part:
                count, sides = part.split("d")
                count = int(count) if count else 1
                sides = int(sides)
                
                part_total = 0
                part_rolls = []
                
                if (advantage or disadvantage) and count == 1 and sides == 20:
                    r1 = random.randint(1, sides)
                    r2 = random.randint(1, sides)
                    if advantage:
                        val = max(r1, r2)
                        detail = f"max({r1}, {r2})"
                    else:
                        val = min(r1, r2)
                        detail = f"min({r1}, {r2})"
                    part_total = val
                    part_rolls = [r1, r2]
                    details.append(f"1d20 ({detail})")
                else:
                    for _ in range(count):
                        r = random.randint(1, sides)
                        part_rolls.append(r)
                        part_total += r
                    details.append(f"{count}d{sides} ({part_rolls})")
                
                total += part_total
                all_rolls.extend(part_rolls)
            else:
                try:
                    mod = int(part)
                    total += mod
                    details.append(str(mod))
                except:
                    pass

        return {
            "total": total,
            "rolls": all_rolls,
            "detail": " + ".join(details)
        }
