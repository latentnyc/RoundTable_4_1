import json
import os
import copy

file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "games", "Goblin_Combat_Test.json"))

with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)

# 1. Update Starting Room
for loc in data["atlas"]:
    if loc["id"] == "loc_room":
        # Add door to interactables if not exists
        if not any(i["id"] == "door_north" for i in loc.get("interactables", [])):
            loc["interactables"].append({
                "id": "door_north",
                "name": "Reinforced Wooden Door",
                "type": "door",
                "state": "closed",
                "locked": False,
                "key_id": "",
                "contents": [],
                "secrets": []
            })

        # Add connection
        if not any(c.get("direction") == "north" for c in loc.get("description", {}).get("connections", [])):
            loc["description"]["connections"].append({
                "direction": "north",
                "target_id": "loc_north_room",
                "description": "A reinforced wooden door leading north."
            })

# 2. Add North Room
if not any(loc["id"] == "loc_north_room" for loc in data["atlas"]):
    data["atlas"].append({
        "id": "loc_north_room",
        "name": "The Guard Room",
        "active_hours": "always",
        "description": {
            "visual": "A wide rectangular chamber with slightly colder air. Scuff marks on the floor suggest frequent activity.",
            "auditory": "Low guttural whispering.",
            "olfactory": "Stale sweat and wet dog.",
            "anchors": ["scuffed floor", "colder air"],
            "anti_drift": "A room to fight the guards in.",
            "connections": [
                {
                    "direction": "south",
                    "target_id": "loc_room",
                    "description": "A reinforced wooden door leading back south."
                }
            ],
            "secrets": []
        },
        "environmental_state": {
            "light_level": "dim",
            "light_required": False,
            "hazards": []
        },
        "interactables": [],
        "secrets": []
    })

# 3. Add 2 Goblins
base_goblin = None
for npc in data["npcs"]:
    if npc["id"] == "npc_goblin":
        base_goblin = npc
        break

if base_goblin:
    for i in range(1, 3):
        new_id = f"npc_goblin_north_{i}"
        if not any(npc["id"] == new_id for npc in data["npcs"]):
            new_goblin = copy.deepcopy(base_goblin)
            new_goblin["id"] = new_id
            new_goblin["name"] = f"Skrag {i}"
            new_goblin["target_id"] = f"skrag_{i}"
            # Put them in the new room
            new_goblin["schedule"][0]["location"] = "loc_north_room"
            data["npcs"].append(new_goblin)

with open(file_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4)

print("Successfully updated JSON.")
