# ToSK POC — FINAL BUILD SPEC (engineer-ready)

**Goal:** Ingest the first playable section of *Tomb of the Serpent Kings* (Skerples, CC BY-NC-SA) into a RoundTable campaign that loads through the **real** `parse_and_load`/`instantiate_campaign` path, run the Room-6 skeleton combat deterministically, and — with `MEMORY_RAG_ENABLED=true` — observe a **death→recall** (reliable) and a **loot→recall** (conditional). Every claim is cited to code read this session.

---

## 0. Pipeline (grounded, in one paragraph)

`games/<file>.json` → on startup `campaign_loader.parse_and_load()` globs `games/*.json` (skips `blank_schema.json`), flattens `campaign_meta.*` to root keys, requires a resolvable `id`, and writes a `campaign_templates` row (`campaign_loader.py:194-231`). At campaign creation `instantiate_campaign()` copies `npcs`/`atlas`/`quests`/`items`/`monsters` into per-campaign tables (`campaign_loader.py:92-189`). A `test_campaign_setup`-style seeder then builds the first `GameState` from `starting_location` and spawns every NPC whose `schedule[].location == starting_location` (`test_campaign_setup.py:206-253`). At play time `StateService.get_game_state` hydrates entities; the `data` blob carries `stats`/`actions`/`loot`/`voice`/`disposition` through to combat.

**Load-bearing facts — all verified this session:**

| Fact | Cite |
|---|---|
| Rooms key is **`atlas`**, not `locations` | `campaign_loader.py:124` |
| Unknown top-level keys (the `license` block) are **silently ignored** | loader reads only `campaign_meta/atlas/npcs/items/quests/monsters` |
| Fightable monsters must be **`npcs[]` with `hostile:true`**; `disposition.attitude` ∈ {hostile,aggressive,violent,enemy,"attack on sight"} auto-sets `hostile` **only if `hostile` key absent** | `campaign_loader.py:103-109`; `combat_service.py:656` |
| An NPC spawns into a room **only if** some `schedule[].location == room source_id` | `test_campaign_setup.py:237` |
| **TO-HIT GOTCHA (CONFIRMED):** to-hit/damage mod = `get_mod("strength"/"dexterity")`, which matches a stat key whose `lower()=="strength"`. **Abbreviated `"str"` does NOT match → falls to default 10 → +0.** The shipped Goblin Lizardfolk (`"str":15`) attacks at **+0 today**. | `character_sheet.py:22`; `attack_resolver.py:42-51`; `Goblin_Combat_Test.json:569` |
| `attack_bonus` in actions is **never read** | `attack_resolver.py` (no reference) |
| Damage = `actions[0].damage[0].damage_dice` with flat `+N/-N` **stripped**, then the (+0) mod re-added | `character_sheet.py:72-75`; `attack_resolver.py:106` |
| AC honored via `max(base, explicit_ac, monster_ac)` — `stats.ac` flows as `explicit_ac` | `character_sheet.py:130-145` |
| Initiative reads `getattr(stats,"dexterity",10)` → abbreviated-key NPCs roll init at **dex +0** too | `combat_service.py:37` |
| Corpse vessel contents = `inventory` + `generate_loot()`, and **`generate_loot` reads `loot.guaranteed`** | `combat_service.py:626-627`; `loot_service.py:32-33` |
| **Death memory** recorded in `_handle_entity_death`; hostile death salience **1.0** (always pooled) | `combat_service.py:689-696`; `memory_service.py:91` |
| **Loot memory** recorded in `take_items`; salience hardcoded `rarity:"common"` → **0.2**, **below** IMPORTANCE_FLOOR 0.6 → pooled **only on FTS query match** | `loot_service.py:348-353`; `memory_service.py:88,48,256-257` |
| All memory gated by `MEMORY_RAG_ENABLED` | `memory_service.py:52-54` |
| Coordinates require **`s = -q-r`**; only `party_locations` auto-append to `walkable_hexes` | `models.py` |
| **`resolution_move` does NOT spawn destination NPCs, drops `walkable_hexes`/`party_locations` on the new Location, and clears `vessels`** | `movement_service.py:99-107` |

### ⚠️ The one thing that breaks the naive plan (read this before building)

`resolution_move` (the room-transition handler) **rebuilds `game_state.location` without `walkable_hexes` or `party_locations`, never queries the `npcs` table, and clears `vessels`** (`movement_service.py:99-107`). Consequences:

- **You cannot start at Room 1 and walk to Room 6 to find skeletons** — none will spawn there. The earlier draft's "the party walks to room 6" is **wrong**.
- After any move the destination has **no walkable floor**, degrading combat/pathfinding.
- **Loot the corpse before leaving the room** — moving wipes `vessels`.

**Decision (mandatory for the POC): seed the combat-demo GameState directly at Room 6** as `starting_location`. The party begins in the skeleton tomb; the fight is immediately reachable and fully mechanical. Rooms 1–5/7–8 are authored for atmosphere/exploration narration and as the "session" surface, but the **demo's seeded entry point is Room 6**. (If you later want walk-in spawns, that is an engine change to `resolution_move` — out of POC scope.)

---

## 1. Target campaign JSON schema (reconciled with loader + seeder + models)

Top-level object. Only `campaign_meta`, `atlas`, `npcs`, `items`, `quests`, `monsters` are read; any other top-level key is ignored (so `license` rides along safely).

```jsonc
{
  "campaign_meta": {
    "id":            "tosk_false_tomb",                         // REQUIRED (no id → file skipped, loader:223)
    "title":         "Tomb of the Serpent Kings: The False Tomb", // REQUIRED
    "genre":         "OSR Dungeon Crawl",
    "description":   "A teaching dungeon by Skerples (CC BY-NC-SA). Adapted for RoundTable.", // mirror a credit here (§6c)
    "setting_system_prompt": "You are the DM of a grim, shoddy 'false tomb'...tone notes...",
    "time_config":   {"day_length_hours":24,"sunrise":"06:00","sunset":"18:00","current_time":"12:00","day_state":"day"},
    "starting_location": "loc_tosk_06_false_kings_tomb",        // ⚠️ Room 6 for the combat demo (see §0)
    "starting_npc":  ""
  },
  "license": { /* §6 — ignored by loader, travels with data */ },
  "narrative_state": { "active_quests": [], "variables": {}, "story_threads": {}, "timeline": [] },
  "quests": [],
  "atlas": [ /* one entry per ToSK room */ ],
  "npcs":  [ /* hostile skeletons (combat) + optional friendly NPC */ ],
  "items": [ /* every id referenced by a contents[] or loot */ ],
  "monsters": []   // compendium templates are NOT auto-placed — leave empty for the POC
}
```

### Location (atlas entry)
```jsonc
{
  "id": "loc_tosk_06_false_kings_tomb",   // REQUIRED, referenced by doors + schedules
  "name": "False King's Tomb",
  "active_hours": "always",
  "description": {                         // description.visual is read as the DM read-aloud (test_campaign_setup:217-218)
    "visual": "AUTHORED read-aloud (ToSK has no read-aloud boxes — write from the room key + cheat-sheet)",
    "auditory": "...", "olfactory": "...",
    "anchors": ["..."],
    "anti_drift": "One line pinning the room's purpose.",
    "connections": [ {"direction":"south","target_id":"loc_tosk_05_hammer_door","description":"..."} ], // OBJECT form (Goblin/blank), NOT bare-string
    "secrets": []
  },
  "environmental_state": {"light_level":"dark","light_required":true,"hazards":[]},
  "interactables": [ /* doors, coffins, chests */ ],
  "secrets": [],
  "walkable_hexes": [ {"q":..,"r":..,"s":..}, ... ],  // REQUIRED allow-list; every entity/coffin position must be a member
  "party_locations": [ {"party_id":"default","position":{"q":..,"r":..,"s":..}} ] // ONLY consumed for the seeded starting room
}
```
**Door interactable:** `{id,name,type:"door",state,locked,key_id,position{q,r,s},contents:[],secrets:[],target_location_id:"<dest id>"}`. **Author the reciprocal door in the adjacent room** (doors are one-directional in JSON; `resolution_move` matches `connections[].target_id` to the dest `source_id`).
**Coffin/chest:** `{id,name,type:"chest"|"coffin",state,locked,key_id,position{q,r,s},contents:["item_id",...],currency?{pp,gp,sp,cp},secrets:[]}`.

### Hostile NPC = combat monster (the only working spawn path for a fight)
```jsonc
{
  "id":"npc_tosk_skeleton_a","name":"Serpent-Man Skeleton","target_id":"skeleton_a",
  "unidentified_name":"Stirring Bones","unidentified_description":"A painted lid begins to shift.",
  "llm_description":"...", "role":"Enemy","race":"Undead",
  "stats":{ "str":12,"dex":12,"con":15,"int":6,"wis":8,"cha":5, // ⚠️ ability scores are FLAVOR ONLY (abbreviated keys → +0 to-hit/dmg)
            "hp":9,"ac":12 },                                    // hp/ac ARE used (seeder reads stats.hp/stats.ac; AC flows as explicit_ac)
  "actions":[ {                                                  // REQUIRED — engine reads actions[0].damage[0].damage_dice
    "name":"Rusted Sword",
    "desc":"Melee Weapon Attack: reach 5 ft., one target. Hit: 1d6 slashing damage.", // "ranged"/"finesse" in desc switch the mod path
    "attack_bonus":4,                                            // COSMETIC — never read
    "damage":[ {"damage_type":{"name":"Slashing"},"damage_dice":"1d6"} ] // the ONLY real damage lever
  } ],
  "voice":{"tone":"Dry rattle, no words.","barks":{"aggro":["*jaw clacks open*"],"death":["*collapses into bone*"],"victory":[]}},
  "knowledge":[],
  "loot":{"guaranteed":["item_tosk_bone_trinket"],"random":[{"item_id":"item_tosk_gold_amulet","chance":0.5}]}, // guaranteed → corpse vessel
  "equipment":[], "inventory":[],
  "schedule":[ {"time":"00:00-24:00","location":"loc_tosk_06_false_kings_tomb","activity":"lying in wait"} ], // MUST equal the room id
  "disposition":{"base":"aggressive","attitude":"Hostile","triggers":{},"romance_eligible":false,"player_affinity":-10},
  "position":{"q":0,"r":-2,"s":2},                               // must be in that room's walkable_hexes
  "secrets":[], "hostile":true, "friendly":false, "ally":false
}
```

### Item
```jsonc
{ "id":"item_tosk_gold_amulet","name":"Gold Amulet","type":"treasure",
  "description":"A small snake-man amulet, worth ~1gp.","usage":"","stats":{},"abilities":[],"behavior":"" }
```
Weapon variant: `"type":"weapon","usage":"Weapon","stats":{"damage":"1d10 slashing"}`. Every id in any `contents[]`/`loot` must exist in `items[]` or it renders as a bare id.

---

## 2. POC slice scope

**Build Rooms 1–8 (Level 1, "The False Tomb"). Source labels: Rooms 1–7 are the author's first-session unit; Room 8 is the Secret Passage down to Level 2 (the session-ender). Rooms 9–13 are Level 2 ("The Upper Tomb") — optional stretch.** (Source structure per the module's level headings; the earlier draft mislabeled 1–8 as the author's declared unit — corrected here.)

| Room | Content | Engine role |
|---|---|---|
| 1 Entrance Hall | corridor, 4 side exits, barred N door | Location, hub |
| 2/3/4 Tomb cells | coffin + clay statue + poison-gas (narrated) + 1gp amulet; **room 4** also holds the cursed **Serpent Ring** | Locations + coffin `contents` + items (**loot**) |
| 5 Hammer-trap door | barred stone door, hammer trap (narrated, **2d6+4** not auto-kill) | door + `secrets`/`hazards` text |
| **6 False King's Tomb** | **3× Serpent-Man Skeleton** in coffins | **COMBAT — kill→memory. Seeded as `starting_location` (§0).** |
| 7 False Temple | idol, eroded floor → visible secret passage | Location + secret interactable |
| 8 Secret Passage | descends to Level 2 | Location, session-ending beat |

**POC requirements satisfied:** ≥1 combat = Room 6 (3 skeletons); lootable treasure = amulets/ring in 2/3/4 + skeleton corpse loot in 6; ~8 rooms = a session.

**Stretch (Level 2, Rooms 9–13)** adds combats/loot: Statue Hall (9), Secret Guardroom (10, polearms + 5gp icon), Tomb Atrium (11, **2× Mummy Claw** + pool treasure incl. 35gp chain & Ring of Eyesight), Tomb of Xisor (12, lightning plate 4d6 narrated, 10gp electrum disc), Tomb of Sparamuntar (13, **HD-3 Skeleton**, greataxe **1d8** per source, 10gp trinkets). **Hard stop before Room 14** (Black Pudding) and **Rooms 18/19** (Level-3 stairs, Stone Cobra boss, wandering monsters, lich). Stretch needs only the Mummy Claw + an HD-3 Skeleton variant (both below).

**Living NPCs:** the slice is all undead. To exercise companion-voice/knowledge memory, optionally add the author-suggested friendly **"Smee" goblin** in Room 7 (no `actions`, `attitude:"Friendly"`, `friendly:true,hostile:false`). Optional.

---

## 3. Fully worked example — Room 6 (combat) + Room 4 items, as engine JSON that loads

**`atlas[]` — Room 6** (5×5 hex pocket; party enters from the south edge, 3 coffins on the north wall). `starting_location` for the demo, so `party_locations` here **are** consumed.

```json
{
  "id": "loc_tosk_06_false_kings_tomb",
  "name": "False King's Tomb",
  "active_hours": "always",
  "description": {
    "visual": "A burial chamber some thirty feet on a side. Three wooden coffins stand against the north wall, their lids painted with stylized sleeping snake-men; the central coffin is larger, ornate, gilded at the edges.",
    "auditory": "Dead silence — until a lid is disturbed, and then the dry scrape of bone on wood.",
    "olfactory": "Damp stone, old dust, the faint sweetness of rot.",
    "anchors": ["three coffins", "ornate central coffin", "painted snake-men"],
    "anti_drift": "The skeleton-ambush room at the end of the False Tomb's main corridor.",
    "connections": [
      {"direction":"south","target_id":"loc_tosk_05_hammer_door","description":"The stone doors knocked open by the hammer trap."}
    ],
    "secrets": []
  },
  "environmental_state": {"light_level":"dark","light_required":true,"hazards":[]},
  "interactables": [
    {"id":"door_06_to_05","name":"Stone Doors","type":"door","state":"open","locked":false,"key_id":"",
     "position":{"q":0,"r":3,"s":-3},"contents":[],"secrets":[],"target_location_id":"loc_tosk_05_hammer_door"},
    {"id":"coffin_06_king","name":"Ornate Central Coffin","type":"coffin","state":"closed","locked":false,"key_id":"",
     "position":{"q":0,"r":-2,"s":2},"contents":[],"secrets":["Disturbing it wakes the central skeleton."]},
    {"id":"coffin_06_left","name":"Left Coffin","type":"coffin","state":"closed","locked":false,"key_id":"",
     "position":{"q":-2,"r":-2,"s":4},"contents":[],"secrets":[]},
    {"id":"coffin_06_right","name":"Right Coffin","type":"coffin","state":"closed","locked":false,"key_id":"",
     "position":{"q":2,"r":-2,"s":0},"contents":[],"secrets":[]}
  ],
  "secrets": [],
  "walkable_hexes": [
    {"q":-2,"r":-2,"s":4},{"q":-1,"r":-2,"s":3},{"q":0,"r":-2,"s":2},{"q":1,"r":-2,"s":1},{"q":2,"r":-2,"s":0},
    {"q":-2,"r":-1,"s":3},{"q":-1,"r":-1,"s":2},{"q":0,"r":-1,"s":1},{"q":1,"r":-1,"s":0},{"q":2,"r":-1,"s":-1},
    {"q":-2,"r":0,"s":2},{"q":-1,"r":0,"s":1},{"q":0,"r":0,"s":0},{"q":1,"r":0,"s":-1},{"q":2,"r":0,"s":-2},
    {"q":-2,"r":1,"s":1},{"q":-1,"r":1,"s":0},{"q":0,"r":1,"s":-1},{"q":1,"r":1,"s":-2},{"q":2,"r":1,"s":-3},
    {"q":-2,"r":2,"s":0},{"q":-1,"r":2,"s":-1},{"q":0,"r":2,"s":-2},{"q":1,"r":2,"s":-3},{"q":2,"r":2,"s":-4}
  ],
  "party_locations": [
    {"party_id":"default","position":{"q":-1,"r":2,"s":-1}},
    {"party_id":"default","position":{"q":0,"r":2,"s":-2}},
    {"party_id":"default","position":{"q":1,"r":2,"s":-3}}
  ]
}
```

**`npcs[]` — skeleton A** (clone to B/C with new `id`/`target_id`/`position`/coffin; B → `{"q":-2,"r":-2,"s":4}`, C → `{"q":2,"r":-2,"s":0}`):

```json
{
  "id":"npc_tosk_skeleton_a","name":"Serpent-Man Skeleton","target_id":"skeleton_a",
  "unidentified_name":"Stirring Bones","unidentified_description":"A fanged skeleton wrapped in corroded bangles, clutching a rusted blade.",
  "llm_description":"A snake-skulled skeleton, yellowed bone hung with rotted burial linen, lurching upright from its coffin with a rusted sword.",
  "role":"Enemy","race":"Undead",
  "stats":{"str":12,"dex":12,"con":15,"int":6,"wis":8,"cha":5,"hp":9,"ac":12},
  "actions":[
    {"name":"Rusted Sword","desc":"Melee Weapon Attack: reach 5 ft., one target. Hit: 1d6 slashing damage.",
     "attack_bonus":4,"damage":[{"damage_type":{"name":"Slashing"},"damage_dice":"1d6"}]}
  ],
  "voice":{"tone":"Dry rattle, no words.","barks":{"aggro":["*the jaw clacks open*"],"death":["*collapses into a clatter of bone*"],"victory":[]}},
  "knowledge":[],
  "loot":{"guaranteed":["item_tosk_bone_trinket"],"random":[{"item_id":"item_tosk_gold_amulet","chance":0.5}]},
  "equipment":[],"inventory":[],
  "schedule":[{"time":"00:00-24:00","location":"loc_tosk_06_false_kings_tomb","activity":"lying in wait"}],
  "disposition":{"base":"aggressive","attitude":"Hostile","triggers":{},"romance_eligible":false,"player_affinity":-10},
  "position":{"q":0,"r":-2,"s":2},
  "secrets":[],"hostile":true,"friendly":false,"ally":false
}
```

**CORRECTED combat trace** (verified against `character_sheet.py:22` + `attack_resolver.py:42-51,106`):
- Hydration → `hp_max=9`, `ac=12` (seeder reads `stats.hp/stats.ac`; AC flows as `explicit_ac`).
- `get_weapon` → `actions[0]` → `"1d6"`, melee (no "ranged"/"finesse" in `desc`).
- **`hit_mod = get_mod("strength")`. Stat key is `"str"`, which ≠ `"strength"`, so the lookup defaults to 10 → mod = `floor((10-10)/2) = +0`.** Roll = **`1d20+0` vs AC**.
- On hit, damage = **`1d6+0`** (flat). The `attack_bonus:4` and `str:12` are **inert**.
- **Ability scores are FLAVOR ONLY with abbreviated keys.** The real difficulty levers are **`stats.hp`, `stats.ac`, and `damage_dice`.** Tune the fight with those.
- With `1d20+0` vs party AC ~14–18, skeletons hit on nat 14–18+ — they will land occasional ~3.5-dmg hits but rarely drop a tanky PC. **The reliable death trigger is a skeleton dying to the party** (which always fires the death hook). Do not rely on a PC death. HP 9 / 1d6 party attacks → each skeleton dies in ~2 hits.
- To get a *real* +N you would have to key stats as full names (`"strength":12`) — **untested in any shipped file; do NOT rely on it without verifying it doesn't break hydration/`flatten_data_fields`.** Recommendation: accept +0 and tune dice/HP/AC.

**`items[]`:**
```json
{ "id":"item_tosk_gold_amulet","name":"Gold Amulet","type":"treasure",
  "description":"A small snake-man amulet, roughly 1gp.","usage":"","stats":{},"abilities":[],"behavior":"" },
{ "id":"item_tosk_bone_trinket","name":"Bone Trinket","type":"treasure",
  "description":"A carved finger-bone charm taken from the dead.","usage":"","stats":{},"abilities":[],"behavior":"" },
{ "id":"item_tosk_serpent_ring","name":"Serpent-Fang Ring","type":"wondrous",
  "description":"A silver ring. Worn, the fingernail becomes a fang usable as a poison dagger (+1d6 poison vs living). Each morning the wearer saves vs poison or takes 1d6; on the sixth failure the finger drops off and becomes a snake.",
  "usage":"Wear","stats":{},"abilities":["cursed","poison_strike"],"behavior":"Cursed: daily poison save while worn (DM-adjudicated)." }
```
Place the ring + an amulet in Room 4's sorcerer coffin: `"contents":["item_tosk_serpent_ring","item_tosk_gold_amulet"]`.

**Traps are DM-narrated.** No first-class trap-resolution code exists. Model the Room-5 hammer and Room-2/3/4 gas as `interactables[].secrets[]` + `environmental_state.hazards[]` text; the DM applies damage as a ruling (use **2d6+4** for the hammer, not auto-death, so a demo party isn't one-shot). **Only Room 6's combat must be mechanical** — and it is.

---

## 4. Data to create (engine-shaped stat/item blocks)

**Core (Rooms 1–8):**
- **Skeleton ×3** — the §3 `npcs[]` block, distinct `id`/`target_id`/`position`/coffin.
- **Items:** `item_tosk_gold_amulet`, `item_tosk_bone_trinket`, `item_tosk_serpent_ring`.
- Note: an SRD Skeleton exists in `backend/json_data/monsters.json`, but the `monsters` table is **not auto-placed**. For a real fight it **must** be authored as a hostile `npc` (above).

**Stretch (Rooms 9–13 only):**
- **Mummy Claw ×2** (Room 11) — full block below.
- **Sparamuntar, HD-3 Skeleton** (Room 13) — clone the §3 Skeleton; `stats.hp≈14`; swap action to `"name":"Greataxe","damage_dice":"1d8"` (per source; the die is the only real damage lever since the mod is +0).
- **Items:** `item_tosk_silver_icon` (5gp), `item_tosk_hooked_polearm` (`type:"weapon","stats":{"damage":"1d10 slashing"}`), `item_tosk_gold_chain` (35gp), `item_tosk_ring_of_eyesight`, `item_tosk_electrum_disc` (10gp), `item_tosk_funeral_trinkets` (10gp).

**Mummy Claw (`npcs[]`):**
```json
{
  "id":"npc_tosk_mummy_claw_a","name":"Mummy Claw","target_id":"mummy_claw_a",
  "unidentified_name":"Thing in the Pool","unidentified_description":"A severed, bandaged hand scrabbling at the lip of the dark water.",
  "llm_description":"A rotting, bandage-wrapped hand, severed at the wrist, that drags itself out of the oily pool to clutch and strangle.",
  "role":"Enemy","race":"Undead",
  "stats":{"str":16,"dex":13,"con":11,"int":5,"wis":10,"cha":4,"hp":9,"ac":11},
  "actions":[
    {"name":"Claw","desc":"Melee Weapon Attack: reach 5 ft., one target. Hit: 1d4 bludgeoning damage.",
     "attack_bonus":3,"damage":[{"damage_type":{"name":"Bludgeoning"},"damage_dice":"1d4"}]}
  ],
  "voice":{"tone":"Wordless; a wet, scrabbling rasp.","barks":{"aggro":["*scrabbles up the stone lip*"],"death":["*flops still, fingers twitching*"],"victory":[]}},
  "knowledge":[],"loot":{"guaranteed":[],"random":[]},"equipment":[],"inventory":[],
  "schedule":[{"time":"00:00-24:00","location":"loc_tosk_11_tomb_atrium","activity":"lurking in the pool"}],
  "disposition":{"base":"aggressive","attitude":"Hostile","triggers":{},"romance_eligible":false,"player_affinity":-10},
  "position":{"q":0,"r":0,"s":0},
  "secrets":[],"hostile":true,"friendly":false,"ally":false
}
```
(STR 16 is flavor; effective attack is `1d20+0`, damage `1d4`. Strangle/Mummy-Rot are DM-narrated.)

---

## 5. Hex-layout convention (apply to every room)

- **Frame:** each `Location` has its own **local** axial frame; coordinates are not global and may overlap between rooms. One `Location` per numbered room.
- **Invariant:** every hex is `{q,r,s}` with **`s = -q - r`** (`models.py`). Validate every triple — a wrong `s` corrupts distance/LoS.
- **Scale:** **5 ft per hex** (range converts `dist_ft//5`; speed 30 = 6 hexes). A ~30 ft room ≈ **5–6 hexes** across. Cheat-sheet 10-ft squares → ×2 for hex span.
- **Footprint:** `walkable_hexes` is the explicit floor allow-list; anything unlisted is wall. BFS/movement are constrained to it.
- **Origin/entry:** center the pocket near (0,0); party spawns on the **entry edge** (south, larger `r`), threat opposite (north, negative `r`) — mirrors `Goblin_Combat_Test.json`.
- **Positions:** every **enemy/coffin/chest** `position` **must** be a member of `walkable_hexes` (these are NOT auto-appended — only `party_locations` are). A **door** `position` should be **one hex just outside** the wall edge ("in the doorway"); doors needn't be walkable.
- **Helper** (validate by constructing `Location(**room)`):
```python
def gen_hexes(rows, cols, q0=0, r0=0):
    return [{"q": q0+dc, "r": r0+dr, "s": -(q0+dc)-(r0+dr)}
            for dr in range(rows) for dc in range(cols)]
```
- **Doors are one-directional in JSON** — author the reciprocal door in each adjacent room with `target_location_id` (and a matching `connections` entry) pointing back.
- ⚠️ **`resolution_move` drops `walkable_hexes`/`party_locations` on entered rooms** (`movement_service.py:99-106`). The seeded **starting room (Room 6) keeps them**; non-seeded rooms entered by walking will have an empty floor. This is fine for the seeded-at-Room-6 demo; note it if you exercise exploration.

---

## 6. License / attribution (CC BY-NC-SA, non-commercial)

The converted JSON is a **derivative** — it must carry the license + four credits and stay non-commercial. Attaches to the **data file only**; does not infect engine code.

**(a) Top-level `license` block** (loader ignores unknown top-level keys — verified):
```json
"license": {
  "spdx": "CC-BY-NC-SA-4.0",
  "url": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
  "non_commercial": true,
  "title": "Tomb of the Serpent Kings (v4)",
  "derivative_notice": "Adapted for the RoundTable engine. This data file is a derivative work, licensed CC BY-NC-SA 4.0. Not for sale.",
  "credits": { "writing": "Skerples (coinsandscrolls.blogspot.com)", "art": "Scrap Princess", "map": "Janon", "layout": "David Shugars" }
}
```
**(b)** An `ATTRIBUTION.md`/`NOTICE` beside the JSON (`games/Tomb of the Serpent_Kings v4/ATTRIBUTION.md`) restating credits + license URL + non-commercial constraint in prose — the durable backstop if a future loader drops unknown keys.
**(c)** Mirror a one-line credit into `campaign_meta.description` so it surfaces on the in-app card.
**(d)** Do not bundle the original `_layout.pdf`/`images/` into any shipped/commercial build without the same notice.

---

## 7. Build + playtest task list (ordered, concrete)

**A. Author the content file**
1. Create **`games/Tomb_of_the_Serpent_Kings.json`** (directly in `games/` so `parse_and_load`'s `glob("games/*.json")` catalogs it; the existing `games/Tomb of the Serpent_Kings v4/` `.md` folder is **not** scanned). Set `campaign_meta.id="tosk_false_tomb"` and **`starting_location="loc_tosk_06_false_kings_tomb"`** (§0). Add the `license` block (§6) and `narrative_state`.
2. Author the 8 `atlas` rooms (1–8). Write `description.{visual,auditory,olfactory}` from the room key + cheat-sheet. Generate `walkable_hexes` with `gen_hexes`. Add doors **both directions** + matching `connections`; coffin/statue interactables; `party_locations` on **Room 6** (the seeded start).
3. Author Room 6's **3 hostile-skeleton `npcs[]`** with distinct ids/positions/coffins, `schedule[].location="loc_tosk_06_false_kings_tomb"`, and `loot.guaranteed:["item_tosk_bone_trinket"]`.
4. Author `items[]` (amulet, bone trinket, serpent ring); put ring+amulet in Room 4's coffin `contents`.
5. **Validate before DB:** round-trip every room/NPC through Pydantic — `for r in atlas: Location(**r)` and construct each NPC. A construction failure is a content bug caught early (enforces `s=-q-r`, positions-in-walkable, types).

**B. Load + verify against the real loader + Postgres**
6. Start the stack (`./scripts/dev-start.sh`). Confirm startup logs `Processing Tomb_of_the_Serpent_Kings.json` and `Auto-marked ... as Hostile` (only fires if you *omit* `hostile` — since you set `hostile:true` explicitly, the auto-mark may be skipped; the entity is still hostile — verify the row regardless). Check: `SELECT id,name FROM campaign_templates WHERE id='tosk_false_tomb';`
7. Create a campaign row and call `instantiate_campaign(db, <campaign_id>, 'tosk_false_tomb')` (mirror `test_campaign_setup.create_test_campaign` as a small seed script/endpoint). Verify: `SELECT count(*) FROM npcs WHERE campaign_id=...;` (3), `... FROM locations` (8), `... FROM items`.
8. Build the first `GameState` the `test_campaign_setup` way — **but with two required seeder patches:**
   - **(i) Spawn position:** `test_campaign_setup.py:249` hardcodes `position=Coordinates(q=0,r=0,s=0)` for every spawned NPC. **PRIMARY fix: read the authored position** — `position=Coordinates(**n_data['position'])` — so the 3 skeletons sit on their coffin hexes instead of stacking at origin (which degrades pathfinding/targeting).
   - **(ii) Starting room = Room 6:** since `starting_location` is now Room 6, the seeder's schedule filter (`slot.location == start_loc_id`) **matches the 3 skeletons** and spawns them into the first state. (This is the whole reason for seeding at Room 6 — `resolution_move` does **not** spawn NPCs on walk-in; `movement_service.py:99-107`.)
   - Confirm `stats.hp/stats.ac` keying (seeder reads `stats.hp`/`stats.ac` — your blocks include both). Persist to `game_states`; confirm 3 skeletons on distinct coffin hexes, AC 12, HP 9.

**C. Enable memory + play the slice**
9. Set `MEMORY_RAG_ENABLED=true` in `backend/.env`; restart backend. Confirm `memory_service.is_enabled()` → true.
10. Join the campaign (party spliced in on `join_campaign`), **start combat with the 3 skeletons**, play until **≥1 skeleton dies** (the reliable trigger — see §3; do not count on a PC death). **Loot the corpse vessel before moving** (`take_items` pulls `item_tosk_bone_trinket` that `generate_loot` placed there). ⚠️ Moving rooms clears `vessels` (`movement_service.py:107`) — loot first.

**D. What to observe (the POC's point)**
11. **Death recorded (RELIABLE):** after a skeleton dies, `SELECT kind,content,importance FROM memory_episodes WHERE campaign_id=... ORDER BY created_at DESC LIMIT 5;` → a `kind='death'` row, **`importance=1.0`** (hostile), content "...was struck down/slain in battle" (`combat_service.py:686-696`; `memory_service.py:91`).
12. **Loot recorded (write always succeeds):** after looting, a `kind='loot'` row, **`importance=0.2`** (hardcoded `rarity:"common"`), content "...recovered N item(s) from CORPSE OF ..." (`loot_service.py:345-353`; `memory_service.py:88`).
13. **Recall:**
   - **Death recall (RELIABLE):** death salience 1.0 ≥ IMPORTANCE_FLOOR 0.6, so the death episode is **always pooled** regardless of query/presence — and surfaces even though the slain skeleton was **removed** from state on death (`combat_service.py:648`; recall is via high-importance pooling, NOT entity presence — `memory_service.py:131-133,256`). Trigger any later DM/companion prompt and confirm the **"RELEVANT MEMORIES (narrative reference only ...)"** fenced block (`format_memory_block`, lines 317-321) appears above PARTY STATUS, surfacing the kill.
   - **Loot recall (CONDITIONAL — by design):** loot salience 0.2 is **below** the 0.6 floor, so it is pooled **only on a full-text query match** (`_POOL_SQL` lines 256-257). To demonstrate it, the playtester must issue a prompt whose text references the looted item/container (e.g. *examine the bone trinket*, *ask about what we recovered from the corpse*). If you do **not** topically query it, loot will **silently not surface** — this is correct behavior, **not a bug**. (If a guaranteed loot-recall demo is required, raise loot salience or set a non-common `rarity` in `facts`.)
14. **Cross-session recall (optional, if "several sessions ago" is in scope):** the death/loot tasks above only exercise *same-session* recall. To demo aged recall, call `bump_session(campaign_id)` and/or `ingest_episode_from_summary(...)` (`memory_service.py:205,223`) to promote a rolling summary, then re-prompt and confirm the older episode resurfaces (the weighted-SUM ranker keeps old-but-relevant rows alive — lines 44,150). If not in scope, drop the cross-session claim from the goal.
15. **DM narration + atmosphere:** confirm the DM narrates Room 6 from `description.visual` (read as the read-aloud) and the authored ToSK tone comes through; confirm `voice.barks.death` fires on a skeleton's death.

**Done =** the file loads via the real `parse_and_load`/`instantiate_campaign`; the seeder (patched for authored position) spawns 3 skeletons on their coffin hexes in Room 6; the fight resolves deterministically (`1d20+0` to-hit, `1d6` damage, HP 9 / AC 12); a `death` (1.0) and a `loot` (0.2) episode are written; the death recalls in the fenced block on any later prompt, and the loot recalls on a topical query.

---

### Defensibility notes (post-critique reconciliation)
- **The draft's headline combat trace was WRONG and is corrected.** `get_mod("strength")` requires the key `"strength"`; the authored/shipped `"str"` keys fall through to default 10 → **+0**, confirmed by reading `character_sheet.py:22`, `attack_resolver.py:42-51`, and the shipped `Goblin_Combat_Test.json:569`. Ability scores are flavor; HP/AC/`damage_dice` are the real levers. The "use STR 15 to match SRD +4" guidance is removed.
- **The biggest "will it run" risk — movement spawn — is now resolved, not hand-waved.** `resolution_move` (`movement_service.py:99-107`) does not spawn destination NPCs, drops the floor, and clears vessels. The spec therefore **seeds the demo at Room 6** rather than walking in. This is a new, load-bearing correction over the draft.
- **Loot recall is correctly characterized as conditional** (salience 0.2 < floor 0.6; FTS-gated), with an explicit playtest instruction and a no-this-isn't-a-bug note — preventing a false "memory is broken" read.
- **Death recall is attributed to high salience (always-pooled), not entity presence** — the slain skeleton is removed from state on death (`combat_service.py:648`), so a presence-based explanation would be wrong.
- **Vessel loot path verified:** `generate_loot` reads `loot.guaranteed` (`loot_service.py:32-33`), and `_handle_entity_death` copies its output into the corpse vessel (`combat_service.py:626-627`) — so `loot.guaranteed:["item_tosk_bone_trinket"]` reliably populates the corpse. No inventory workaround needed.
- **Seeder (0,0,0) spawn** (`test_campaign_setup.py:249`) — primary mitigation is patching the loop to read authored `position` (Task 8(i)).
- **Skeleton slashing/piercing resistance is dropped** for the POC: `engine.py` supports a caller-passed `damage_resistance` param but there is **no** entity-level `damage_resistances` auto-application path, so relying on it would be undefensible. Add later as flavor.
- **Traps are explicitly DM-narrated** (no trap-resolution code); only Room 6's combat is mechanical, which is sufficient for the death→memory demo.
