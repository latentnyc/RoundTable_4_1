"""Build the 'Tomb of the Serpent Kings — The False Tomb' POC campaign JSON.

Generates games/Tomb_of_the_Serpent_Kings.json per design_docs/tosk-poc-build-spec.md.
Authoring is code-generated so hex invariants hold by construction:
  * every hex is {q, r, s} with s = -q - r
  * every enemy/coffin position is a member of its room's walkable_hexes
  * every item id referenced by contents[]/loot exists in items[]

Source adventure: "Tomb of the Serpent Kings" v4 by Skerples — CC BY-NC-SA 4.0.
This generated data file is a derivative work, licensed CC BY-NC-SA 4.0, non-commercial.
Run from backend/:  venv/Scripts/python.exe scripts/build_tosk_campaign.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root
OUT = os.path.join(ROOT, "games", "Tomb_of_the_Serpent_Kings.json")


def block(qmin, qmax, rmin, rmax):
    """Rectangular hex pocket; s computed so s == -q-r always holds."""
    return [{"q": q, "r": r, "s": -q - r}
            for r in range(rmin, rmax + 1)
            for q in range(qmin, qmax + 1)]


def door(did, name, q, r, target, state="closed", locked=False, key_id=""):
    return {"id": did, "name": name, "type": "door", "state": state, "locked": locked,
            "key_id": key_id, "position": {"q": q, "r": r, "s": -q - r},
            "contents": [], "secrets": [], "target_location_id": target}


def coffin(cid, name, q, r, contents=None, secrets=None, ctype="coffin"):
    return {"id": cid, "name": name, "type": ctype, "state": "closed", "locked": False,
            "key_id": "", "position": {"q": q, "r": r, "s": -q - r},
            "contents": contents or [], "secrets": secrets or []}


def conn(direction, target, desc):
    return {"direction": direction, "target_id": target, "description": desc}


# ── IDs ───────────────────────────────────────────────────────────────────────
L1, L2, L3, L4 = "loc_tosk_01_entrance_hall", "loc_tosk_02_guard_tomb", "loc_tosk_03_scholar_tomb", "loc_tosk_04_sorcerer_tomb"
L5, L6, L7, L8 = "loc_tosk_05_hammer_door", "loc_tosk_06_false_kings_tomb", "loc_tosk_07_false_temple", "loc_tosk_08_secret_passage"

GAS = "The clay statue is hollow; smashing it open releases a cloud of poison gas. (DM ruling: 1d6 poison, cannot reduce a PC below 0 HP — a lesson, not a death.)"

# ── ATLAS (8 rooms, Level 1: The False Tomb) ──────────────────────────────────
atlas = [
    {
        "id": L1, "name": "Entrance Hall", "active_hours": "always",
        "description": {
            "visual": "A long, straight corridor of fitted grey stone runs north into the dark. Two low doorways open off each side — four small burial cells in all — and at the far end the passage is sealed by a massive barred door of stone.",
            "auditory": "Your footsteps slap and echo down the corridor; somewhere ahead, water drips with slow patience.",
            "olfactory": "Cold mineral air and the dry, undisturbed dust of centuries.",
            "anchors": ["long stone corridor", "four side cells", "barred stone door to the north"],
            "anti_drift": "The entry corridor of the False Tomb. Guard/scholar/sorcerer cells branch off the sides; the hammer-trap door lies north toward the king's tomb.",
            "connections": [
                conn("west", L2, "A low doorway into a small burial cell."),
                conn("east", L3, "A low doorway into a small burial cell."),
                conn("northwest", L4, "A low doorway into a robed figure's cell."),
                conn("north", L5, "The corridor ends at a massive barred stone door."),
            ],
            "secrets": [],
        },
        "environmental_state": {"light_level": "dark", "light_required": True, "hazards": []},
        "interactables": [
            door("door_01_to_02", "West Cell Doorway", -1, 1, L2, state="open"),
            door("door_01_to_03", "East Cell Doorway", 1, 1, L3, state="open"),
            door("door_01_to_04", "Far Cell Doorway", -1, -2, L4, state="open"),
            door("door_01_to_05", "Barred Stone Door", 0, -3, L5, state="closed", locked=True),
        ],
        "secrets": [], "walkable_hexes": block(-1, 1, -2, 2),
        "party_locations": [{"party_id": "default", "position": {"q": 0, "r": 2, "s": -2}}],
    },
    {
        "id": L2, "name": "Guard Tomb", "active_hours": "always",
        "description": {
            "visual": "A small burial cell. A single wooden coffin holds a hollow clay statue of a fanged snake-man warrior, posed at attention.",
            "auditory": "Silence, thick as the dust.",
            "olfactory": "Old clay and dry rot.",
            "anchors": ["wooden coffin", "clay snake-man warrior statue"],
            "anti_drift": "An identical guard cell. The statue is hollow: gold within, poison gas if smashed carelessly.",
            "connections": [conn("east", L1, "Back to the entrance corridor.")],
            "secrets": ["The statue is hollow and holds a 1gp gold amulet and a dried snake skeleton."],
        },
        "environmental_state": {"light_level": "dark", "light_required": True, "hazards": ["Hidden poison gas inside the statue."]},
        "interactables": [
            door("door_02_to_01", "Cell Doorway", 0, 2, L1, state="open"),
            coffin("coffin_02_warrior", "Warrior's Coffin", 0, -1, contents=["item_tosk_gold_amulet"], secrets=[GAS]),
        ],
        "secrets": [], "walkable_hexes": block(-1, 1, -1, 1), "party_locations": [],
    },
    {
        "id": L3, "name": "Scholar Tomb", "active_hours": "always",
        "description": {
            "visual": "A cell that mirrors the others. The coffin holds a clay statue of a thin, sly-looking snake-man scholar; the scrolls in its arms have crumbled to dust.",
            "auditory": "Your own breathing.",
            "olfactory": "Powdered parchment and dust.",
            "anchors": ["coffin", "clay scholar statue", "crumbled scrolls"],
            "anti_drift": "A scholar's cell, same trick as the guard tombs: amulet inside, poison gas if smashed.",
            "connections": [conn("west", L1, "Back to the entrance corridor.")],
            "secrets": ["Hollow statue: a 1gp amulet and a snake skeleton within."],
        },
        "environmental_state": {"light_level": "dark", "light_required": True, "hazards": ["Hidden poison gas inside the statue."]},
        "interactables": [
            door("door_03_to_01", "Cell Doorway", 0, 2, L1, state="open"),
            coffin("coffin_03_scholar", "Scholar's Coffin", 0, -1, contents=["item_tosk_gold_amulet"], secrets=[GAS]),
        ],
        "secrets": [], "walkable_hexes": block(-1, 1, -1, 1), "party_locations": [],
    },
    {
        "id": L4, "name": "Sorcerer Tomb", "active_hours": "always",
        "description": {
            "visual": "The last cell. Within the coffin stands a clay statue of a robed snake-man sorcerer — and on one sculpted finger gleams a real silver ring.",
            "auditory": "A faint, almost expectant stillness.",
            "olfactory": "Clay, dust, and something faintly bitter.",
            "anchors": ["coffin", "robed sorcerer statue", "silver ring on its finger"],
            "anti_drift": "The sorcerer's cell. Prying the ring off shatters the statue: amulet, poison gas, and the cursed Serpent-Fang Ring.",
            "connections": [conn("southeast", L1, "Back to the entrance corridor.")],
            "secrets": ["The silver ring is magical and CURSED (Serpent-Fang Ring). Taking it breaks the statue and releases poison gas; a 1gp amulet is also inside."],
        },
        "environmental_state": {"light_level": "dark", "light_required": True, "hazards": ["Hidden poison gas inside the statue."]},
        "interactables": [
            door("door_04_to_01", "Cell Doorway", 0, 2, L1, state="open"),
            coffin("coffin_04_sorcerer", "Sorcerer's Coffin", 0, -1,
                   contents=["item_tosk_serpent_ring", "item_tosk_gold_amulet"],
                   secrets=["Prying the ring free shatters the statue and releases poison gas.", GAS]),
        ],
        "secrets": [], "walkable_hexes": block(-1, 1, -1, 1), "party_locations": [],
    },
    {
        "id": L5, "name": "The Hammer-Trap Door", "active_hours": "always",
        "description": {
            "visual": "A short threshold before a large stone door, barred by a heavy length of stone resting on two iron pegs. The ceiling above the doorway is shadowed and oddly seamed.",
            "auditory": "A grinding tension in the stone, as if the door resents being opened.",
            "olfactory": "Cold grit.",
            "anchors": ["barred stone door", "iron pegs", "seamed ceiling"],
            "anti_drift": "The hammer-trap door. Lifting the bar raises the pegs and, when fully removed, drops a ceiling hammer down the corridor. Its first firing knocks the doors open to Room 6.",
            "connections": [
                conn("south", L1, "Back down the entrance corridor."),
                conn("north", L6, "The stone doors to the king's tomb (knocked open once the trap fires)."),
            ],
            "secrets": ["HAMMER TRAP (DM-narrated): fully removing the bar drops a ceiling hammer. Save to Dodge, or use a PC as a springboard (+2 / -2). On a hit: serious damage (DM ruling: 2d6+4 — NOT auto-death for this demo). Spotted by examining the pegs/ceiling or noticing the pegs rise."],
        },
        "environmental_state": {"light_level": "dark", "light_required": True, "hazards": ["Ceiling hammer trap over the doorway."]},
        "interactables": [
            door("door_05_to_01", "South Doorway", 0, 2, L1, state="open"),
            door("door_05_to_06", "Barred Stone Doors", 0, -2, L6, state="closed", locked=True),
        ],
        "secrets": [], "walkable_hexes": block(-1, 1, -2, 2), "party_locations": [],
    },
    # ── ROOM 6 — combat, seeded starting_location (per spec §0/§3) ──
    {
        "id": L6, "name": "False King's Tomb", "active_hours": "always",
        "description": {
            "visual": "A burial chamber some thirty feet on a side. Three wooden coffins stand against the north wall, their lids painted with stylized sleeping snake-men; the central coffin is larger, ornate, gilded at the edges.",
            "auditory": "Dead silence — until a lid is disturbed, and then the dry scrape of bone on wood.",
            "olfactory": "Damp stone, old dust, the faint sweetness of rot.",
            "anchors": ["three painted coffins", "ornate central coffin", "north wall"],
            "anti_drift": "The skeleton-ambush room at the end of the False Tomb. Three serpent-man skeletons lie in the coffins and attack the instant their rest is disturbed.",
            "connections": [
                conn("south", L5, "The stone doors knocked open by the hammer trap."),
                conn("north", L7, "A dark archway into the false temple."),
            ],
            "secrets": [],
        },
        "environmental_state": {"light_level": "dark", "light_required": True, "hazards": []},
        "interactables": [
            door("door_06_to_05", "Stone Doors", 0, 3, L5, state="open"),
            door("door_06_to_07", "North Archway", 0, -3, L7, state="open"),
            coffin("coffin_06_king", "Ornate Central Coffin", 0, -2,
                   secrets=["Disturbing it rouses the central skeleton."]),
            coffin("coffin_06_left", "Left Coffin", -2, -2),
            coffin("coffin_06_right", "Right Coffin", 2, -2),
        ],
        "secrets": [], "walkable_hexes": block(-2, 2, -2, 2),
        "party_locations": [
            {"party_id": "default", "position": {"q": -1, "r": 2, "s": -1}},
            {"party_id": "default", "position": {"q": 0, "r": 2, "s": -2}},
            {"party_id": "default", "position": {"q": 1, "r": 2, "s": -3}},
        ],
    },
    {
        "id": L7, "name": "False Temple", "active_hours": "always",
        "description": {
            "visual": "A wide shrine dominated by a giant statue of a hideous snake-man god — something between a toad, a heap of intestines, and a melted candle. Water has seeped in and eroded the floor, and beneath the idol a dark gap has opened.",
            "auditory": "The steady trickle and drip of water finding its way down.",
            "olfactory": "Wet stone, mildew, and a green, swampy reek.",
            "anchors": ["giant snake-god idol", "water-eroded floor", "dark gap beneath the statue"],
            "anti_drift": "The false temple. The eroded floor reveals a secret passage under the idol leading down to Level 2 — statues here mean secret passages.",
            "connections": [
                conn("south", L6, "Back toward the king's tomb."),
                conn("down", L8, "A gap in the eroded floor beneath the idol, descending into darkness."),
            ],
            "secrets": ["The eroded floor under the idol is a SECRET PASSAGE down to Level 2 (Room 8)."],
        },
        "environmental_state": {"light_level": "dark", "light_required": True, "hazards": ["Slick, eroded, unstable floor."]},
        "interactables": [
            door("door_07_to_06", "South Archway", 0, 2, L6, state="open"),
            coffin("idol_07_snakegod", "Idol of the Snake-God", 0, 0, ctype="chest",
                   secrets=["Statues here mark secret passages. The floor beneath has worn through to a passage below."]),
            door("door_07_to_08", "Gap Beneath the Idol", 0, -1, L8, state="open"),
        ],
        "secrets": ["A secret passage descends beneath the idol to Room 8."],
        "walkable_hexes": block(-2, 2, -2, 2), "party_locations": [],
    },
    {
        "id": L8, "name": "Secret Passage", "active_hours": "always",
        "description": {
            "visual": "A damp, narrow alcove directly below the false temple. It widens as it descends, the rough-hewn walls giving way to older, finer stonework ahead.",
            "auditory": "Dripping water and the hollow promise of a larger space below.",
            "olfactory": "Wet earth and deep, cold stone.",
            "anchors": ["narrow descending alcove", "older stonework ahead"],
            "anti_drift": "The session-ending beat: the hidden way down. The passage widens into the Upper Tomb (Level 2) — beyond the POC scope.",
            "connections": [
                conn("up", L7, "Back up through the gap into the false temple."),
                conn("down", "loc_tosk_09_statue_hall", "The passage widens into a great statue hall below — Level 2 (not yet built)."),
            ],
            "secrets": [],
        },
        "environmental_state": {"light_level": "dark", "light_required": True, "hazards": []},
        "interactables": [door("door_08_to_07", "Passage Up", 0, 1, L7, state="open")],
        "secrets": [], "walkable_hexes": block(-1, 1, -1, 1), "party_locations": [],
    },
]

# ── NPCS (Room 6: 3 hostile serpent-man skeletons) ────────────────────────────
def skeleton(suffix, q, r, central=False):
    name = "Serpent-King Skeleton" if central else "Serpent-Man Skeleton"
    return {
        "id": f"npc_tosk_skeleton_{suffix}", "name": name, "target_id": f"skeleton_{suffix}",
        "unidentified_name": "Stirring Bones",
        "unidentified_description": "A fanged skeleton wrapped in corroded bangles, clutching a rusted blade.",
        "llm_description": "A snake-skulled skeleton, yellowed bone hung with rotted burial linen, lurching upright from its coffin with a rusted sword.",
        "role": "Enemy", "race": "Undead",
        # NOTE: ability scores are FLAVOR with abbreviated keys (engine reads 'strength' etc. → +0).
        # The real levers are hp / ac / damage_dice (per spec §3).
        "stats": {"str": 12, "dex": 12, "con": 15, "int": 6, "wis": 8, "cha": 5,
                  "hp": 11 if central else 9, "ac": 12},
        "actions": [{
            "name": "Rusted Sword",
            "desc": "Melee Weapon Attack: reach 5 ft., one target. Hit: 1d6 slashing damage.",
            "attack_bonus": 4,
            "damage": [{"damage_type": {"name": "Slashing"}, "damage_dice": "1d6"}],
        }],
        "voice": {"tone": "A dry rattle; no words, only the clack of jaw and blade.",
                  "barks": {"aggro": ["*the painted lid bursts and the jaw clacks open*"],
                            "death": ["*collapses into a clatter of loose bone*"], "victory": []}},
        "knowledge": [],
        "loot": {"guaranteed": ["item_tosk_bone_trinket"],
                 "random": [{"item_id": "item_tosk_gold_amulet", "chance": 0.5}]},
        "equipment": [], "inventory": [],
        "schedule": [{"time": "00:00-24:00", "location": L6, "activity": "lying in wait within a coffin"}],
        "disposition": {"base": "aggressive", "attitude": "Hostile", "triggers": {},
                        "romance_eligible": False, "player_affinity": -10},
        "position": {"q": q, "r": r, "s": -q - r},
        "secrets": [], "hostile": True, "friendly": False, "ally": False,
    }


npcs = [
    skeleton("a", 0, -2, central=True),    # ornate central coffin
    skeleton("b", -2, -2),                 # left coffin
    skeleton("c", 2, -2),                  # right coffin
]

# ── ITEMS ─────────────────────────────────────────────────────────────────────
items = [
    {"id": "item_tosk_gold_amulet", "name": "Gold Amulet", "type": "treasure",
     "description": "A small snake-man amulet of thin gold, worth roughly 1gp.",
     "usage": "", "stats": {}, "abilities": [], "behavior": ""},
    {"id": "item_tosk_bone_trinket", "name": "Bone Trinket", "type": "treasure",
     "description": "A carved finger-bone charm, taken from the grave-goods of the dead.",
     "usage": "", "stats": {}, "abilities": [], "behavior": ""},
    {"id": "item_tosk_serpent_ring", "name": "Serpent-Fang Ring", "type": "wondrous",
     "description": "A silver ring. Worn, the fingernail becomes a long, bifurcated fang usable as a poison dagger (+1d6 poison vs. living). But each morning the wearer must save vs. poison or take 1d6; on the sixth failed save the finger drops off and becomes a snake.",
     "usage": "Wear", "stats": {}, "abilities": ["cursed", "poison_strike"],
     "behavior": "Cursed: a daily poison save while worn (DM-adjudicated)."},
]

campaign = {
    "campaign_meta": {
        "id": "tosk_false_tomb",
        "title": "Tomb of the Serpent Kings: The False Tomb",
        "genre": "OSR Dungeon Crawl",
        "description": "The classic teaching dungeon by Skerples (CC BY-NC-SA). Adapted for the RoundTable engine — see ATTRIBUTION. Not for sale.",
        "setting_system_prompt": (
            "You are the Dungeon Master of 'The False Tomb', the first level of the Tomb of the Serpent Kings. "
            "Tone: grim, dry, old-school, faintly wry. This is a shoddy DECOY tomb built to fool grave-robbers. "
            "Describe cold stone, dust, painted snake-men, and lurking danger. Reward caution and cleverness. "
            "Narrate ONLY the outcomes the engine reports; never invent treasure or resolve mechanics yourself."
        ),
        "time_config": {"day_length_hours": 24, "sunrise": "06:00", "sunset": "18:00",
                        "current_time": "12:00", "day_state": "day"},
        "starting_location": L6,   # ⚠️ seed at Room 6 for the combat demo (spec §0)
        "starting_npc": "",
    },
    "license": {
        "spdx": "CC-BY-NC-SA-4.0",
        "url": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
        "non_commercial": True,
        "title": "Tomb of the Serpent Kings (v4)",
        "derivative_notice": "Adapted for the RoundTable engine. This data file is a derivative work, licensed CC BY-NC-SA 4.0. Not for sale.",
        "credits": {"writing": "Skerples (coinsandscrolls.blogspot.com)",
                    "art": "Scrap Princess", "map": "Janon", "layout": "David Shugars"},
    },
    "narrative_state": {"active_quests": [], "variables": {}, "story_threads": {}, "timeline": []},
    "quests": [],
    "atlas": atlas,
    "npcs": npcs,
    "items": items,
    "monsters": [],
}


# ── VALIDATION (invariants the loader/engine depend on) ───────────────────────
def validate(c):
    errors = []
    item_ids = {it["id"] for it in c["items"]}
    loc_ids = {r["id"] for r in c["atlas"]}

    def check_hex(h, where):
        if h.get("s") != -h.get("q", 0) - h.get("r", 0):
            errors.append(f"{where}: s != -q-r for {h}")

    for room in c["atlas"]:
        wh = {(h["q"], h["r"]) for h in room["walkable_hexes"]}
        for h in room["walkable_hexes"]:
            check_hex(h, f"{room['id']} walkable")
        for inter in room["interactables"]:
            p = inter.get("position")
            if p:
                check_hex(p, f"{room['id']}/{inter['id']} pos")
            # door targets must resolve
            tgt = inter.get("target_location_id")
            if tgt and tgt not in loc_ids and not tgt.startswith("loc_tosk_09"):
                errors.append(f"{room['id']}/{inter['id']} door target '{tgt}' not a known location")
            for iid in inter.get("contents", []):
                if iid not in item_ids:
                    errors.append(f"{room['id']}/{inter['id']} contents item '{iid}' missing from items[]")
            # coffins/chests should sit on walkable floor
            if inter.get("type") in ("coffin", "chest") and p and (p["q"], p["r"]) not in wh:
                errors.append(f"{room['id']}/{inter['id']} position not in walkable_hexes")
        for pl in room.get("party_locations", []):
            check_hex(pl["position"], f"{room['id']} party_loc")
        # connections must resolve (allow the not-yet-built Level 2 hall)
        for cn in room["description"]["connections"]:
            t = cn["target_id"]
            if t not in loc_ids and not t.startswith("loc_tosk_09"):
                errors.append(f"{room['id']} connection target '{t}' not a known location")

    for n in c["npcs"]:
        check_hex(n["position"], f"{n['id']} pos")
        room = next((r for r in c["atlas"] if r["id"] == n["schedule"][0]["location"]), None)
        if not room:
            errors.append(f"{n['id']} schedule location '{n['schedule'][0]['location']}' has no room")
        else:
            wh = {(h["q"], h["r"]) for h in room["walkable_hexes"]}
            if (n["position"]["q"], n["position"]["r"]) not in wh:
                errors.append(f"{n['id']} position not in {room['id']} walkable_hexes")
        if not n.get("actions") or not n["actions"][0].get("damage"):
            errors.append(f"{n['id']} missing actions[0].damage (combat needs damage_dice)")
        for iid in n["loot"]["guaranteed"] + [r["item_id"] for r in n["loot"]["random"]]:
            if iid not in item_ids:
                errors.append(f"{n['id']} loot item '{iid}' missing from items[]")

    if c["campaign_meta"]["starting_location"] not in loc_ids:
        errors.append("starting_location is not a known room")
    return errors


if __name__ == "__main__":
    errs = validate(campaign)
    if errs:
        print("VALIDATION FAILED:")
        for e in errs:
            print("  -", e)
        sys.exit(1)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(campaign, f, indent=2, ensure_ascii=False)
    nhex = sum(len(r["walkable_hexes"]) for r in campaign["atlas"])
    print("VALIDATION PASSED")
    print(f"  rooms={len(campaign['atlas'])} npcs={len(campaign['npcs'])} items={len(campaign['items'])} total_hexes={nhex}")
    print(f"  starting_location={campaign['campaign_meta']['starting_location']}")
    print("WROTE:", OUT)
