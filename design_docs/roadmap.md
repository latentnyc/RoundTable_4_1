# RoundTable_4_1: Short & Medium-Term Roadmap

*A strategic plan building upon the "Survived the Blizzard" foundational update.*

---

## 🏔️ Phase 1: Short-Term Roadmap (1-2 Months) - "The Thawing Spring"

*Focus: Deepening core mechanics, enhancing combat, and improving player agency.*

### 1. Advanced Combat & Abilities
While base stats and AC are now dynamically hydrated, combat needs more tactical depth.
- **Strict Hex Distance Math**: Implement formula (`distance = max(abs(dq), abs(dr), abs(ds))`) to strictly enforce movement budgets on the grid, preventing clients from dragging tokens further than their allotted movement speed.
- **Melee & Attack Range Validation**: Hook hex distance math directly into `resolution_attack` to ensure melee strikes and spells respect adjacent or Reach constraints.
- **Active Class Abilities**: Implement specific actions like Paladin's *Divine Smite*, Fighter's *Action Surge*, and rogue's *Sneak Attack*.
- **Spellcasting System**: Expand the 5e Compendium integration to support active spellcasting, tracking spell slots, and defining Area of Effect (AoE) hex-grid templates.
- **Status Effects Overhaul**: Visual and mechanical implementation of conditions (e.g., *Poisoned*, *Blinded*, *Prone*), affecting calculations and movement logic.

### 2. Deeper Inventory & Economy
Moving beyond basic loot metadata and interactive chests.
- **Inventory Management**: A dedicated UI to drag-and-drop items, equip to specific slots (Main Hand, Off-Hand, Armor, Accessories), and trade items between party members.
- **Merchants & Economy**: Implement gold tracking and NPC shopkeepers (driven by the AI DM) where players can buy and sell gear.
- **Consumables**: Functional potions, scrolls, and throwables that mechanically affect the game state.

### 3. Environment & Map Interactivity
The map is currently defined by rooms and doors. Let's make it dangerous.
- **Traps & Hidden Objects**: Entities that require Passive Perception or active 'Search' actions to reveal.
- **Fog of War & Line of Sight (LoS)**: Obscuring parts of the hex grid based on character vision mechanics, blocking view through solid walls or closed doors.
- **Dynamic Terrain**: Hexes with difficult terrain, hazards (like lava or acid), or elevation changes.

### 4. AI DM Enhancements
Making the LangGraph/Gemini AI DM feel more like a persistent storyteller.
- **Proactive Interventions**: Allowing the AI DM to trigger spontaneous events, ambushes, or narrative twists without waiting for player prompts.
- **Long-Term Memory**: Better RAG integration or summary generation to allow the DM to remember character actions from several sessions ago.

---

## 🌍 Phase 2: Medium-Term Roadmap (3-6 Months) - "The Expanding Realm"

*Focus: Scaling the experience, multiplayer, and campaign longevity.*

### 1. Multiplayer & Co-op Support
Transitioning from a single-player controlling a party (or AI squadmates) to a true virtual tabletop experience.
- **Session Joining**: Allow human players to connect to the same WebSocket session via unique invite codes.
- **Role Assignment**: Assign specific party members to specific connected clients.
- **Simultaneous Turns**: (Optional) Allow simultaneous non-combat exploration actions, locking into rigid turns only when in the "combat" phase.

### 2. Campaign Builder & DM Tooling
 Empowering human creators instead of relying solely on code changes to add rooms (like the Goblin Room).
- **Visual Map Editor**: A drag-and-drop interface to create hex maps, place walls, doors, monster spawns, and chests.
- **Scenario Architect**: Tools to define overarching plot hooks, factions, and key NPCs that the AI DM will use as a framework for the narrative.

### 3. Progression & Leveling
Character growth beyond the initial loadouts.
- **Experience Points (XP) & Milestones**: Tracking XP gains from combat and social encounters.
- **Level-Up Flow**: UI for selecting new hit points, ASI (Ability Score Improvements), Feats, and new class features/spells.

### 4. Atmosphere & Audiovisual Polish
- **Dynamic Audio**: Integrate contextual background music and sound effects based on the game state (e.g., combat tracks engaging upon rolling initiative).
- **Refined AI Image Generation**: A more stable pipeline for generating character portraits that visually reflect their currently equipped armor/weapons, and generating seamless battlemap backdrops based on the AI DM's location descriptions.
