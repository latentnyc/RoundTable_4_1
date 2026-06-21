# Hex → Square Grid Migration Plan — RoundTable 4.1

> **Status:** Final, execution-ready. This document folds in every fix from the adversarial critique. The biggest correctness blocker — three conflicting line-of-sight algorithms — is resolved to **one** canonical supercover implementation below (§2.4), and all consumers/tests are pinned to it.

---

## 1. Overview & Locked Decisions

RoundTable 4.1 currently runs on a **flat-top hex grid** using cube coordinates `{q, r, s}` (invariant `s = -q - r`). This plan converts it to a **square grid** with 8-way Chebyshev movement and a `{x, y}` coordinate type. It is a **hard cut** — no dual-grid abstraction, no permanent backward-compat layer.

### Locked decisions (design to these; do not relitigate)

1. **Grid:** Hexes → squares. Hard cut.
2. **Movement:** 8-way Chebyshev. Diagonals allowed; **every** step (orthogonal or diagonal) costs **5 ft**. `distance = max(|dx|, |dy|)`. Each cell has **8 neighbors**. (NOT the 5e alternating 5/10 rule.)
3. **Coordinate type:** Full rename `{q, r, s}` → `{x, y}`. Remove the `s` field. Includes a **data migration** of already-persisted positions (the `game_states` JSON blob plus `characters`/`monsters`/`npcs`/`locations` JSON columns): map `q→x`, `r→y`, drop `s`.

### Verified facts that shape this plan (corrections to the inventory)

These were confirmed by reading the live code, not inherited from the inventory:

- **Live combat AI path is `TurnManager.execute_ai_turn`** (called at `turn_manager.py:205` / `:214`), not `AITurnService`. `TurnManager` carries inline BFS/LOS/distance.
- **`AITurnService.execute_ai_turn` is fully dead** — zero external callers (only internal self-references inside `ai_turn_service.py`). It is **deleted**, not migrated (§5, Phase 2).
- **Live follow path is `GameService.process_ai_following`** (`exploration.py:127`). `MovementService.process_ai_following` and the orphan `resolution_move` duplicate are **dead** and deleted in Phase 2.
- **There is no `s = -q - r` model validator** — only a `# s = -q - r` comment and cube math inside `get_line_to`. "Removing the validator" reduces to deleting the field + the cube line math.
- **Alembic is never invoked.** Startup runs `init_db_async()` only (`main.py:34`). No `command.upgrade`, no `alembic upgrade` in any script. **`init_db.py` is the sole migration execution path.** No Alembic revision is created (§4).
- **Seed files live at repo-root `games/`** (`games/Goblin_Combat_Test.json`, `games/Tomb_of_the_Serpent_Kings.json`, `games/blank_schema.json`). **`backend/games/` does not exist.** Build scripts in `backend/scripts/` must read/write `../../games/`.
- **Positions are stored only inside JSON text columns** — no coordinate DB columns exist. The migration is a JSON transform, not DDL.
- **`get_game_state` reads only the latest `game_states` row** (`limit(1)`, ordered `updated_at desc`). Older snapshots are never hydrated at runtime.

---

## 2. Target Design

### 2.1 The cell and its size

One cell = **5 ft** of game distance. The backend never converts to pixels; pixel size is a frontend rendering concern.

- **Frontend:** `CELL_SIZE = 40` (px), replacing `HEX_SIZE = 30`. Rationale: the old sheared hex transform spaced cells ~45px horizontal / ~52px vertical; the new linear map spaces them exactly `CELL_SIZE` edge-to-edge. At 30 the grid renders visibly denser and token glyphs (`0.7 × SIZE`) cramp the cell; 40 restores breathing room. Token multipliers (`×0.9`, `×0.7`, `×0.6`, `×0.8`) are ratios and stay unchanged. *This is a visual-tuning call, not correctness — keep 30 if pixel-stable diffs are wanted.*

### 2.2 Coordinate type

```python
# backend/app/models.py
class Coordinates(BaseModel):
    x: int
    y: int
```
```ts
// frontend/src/lib/socket.ts
export interface Coordinates { x: number; y: number; }
```

The `s` field, the `s = -q - r` comment, and all cube math are removed.

### 2.3 Chebyshev distance & 8 neighbors

**Distance:** `max(|x1 - x2|, |y1 - y2|)`. Every step (orthogonal or diagonal) = 1 cell = 5 ft.

**8 neighbors of `(x, y)`:** all `(dx, dy) ∈ {-1, 0, 1}² \ {(0,0)}`:
```
(x+1, y)   (x-1, y)   (x, y+1)   (x, y-1)          # orthogonal
(x+1, y+1) (x+1, y-1) (x-1, y+1) (x-1, y-1)        # diagonal
```

**BFS cost model:** uniform 1 per step. Because every neighbor (orthogonal or diagonal) costs exactly 1, uniform-cost BFS over the 8 neighbors **is** Chebyshev movement. **Do not** add 5e alternating 5/10 diagonal costs (explicitly excluded). Movement budget `speed // 5` cells is correct as-is and must be left alone.

**Movement corner-cutting:** diagonal movement is allowed freely — no requirement that both orthogonal-flanking cells be walkable. (All current maps are open rooms; this matches the locked "diagonals allowed, 5 ft each" rule with no flanking caveat.) A future `block_diagonal_corner_cut` flag can be added without an interface change.

### 2.4 Line-of-sight algorithm — ONE canonical implementation (resolves the blocker)

> **Critique resolution (blocker #1 & #2):** Three slices specified three conflicting `get_line_to` implementations that disagreed on the pure-diagonal corner-cutting case. They are reconciled here to **a single true supercover line**. The pathfinding slice's thin-diagonal "supercover" (which actually cut corners) and the rename slice's `round(lerp)` Bresenham are **discarded**. The geometry slice's true supercover is the canonical algorithm. All four LOS consumers call this one `get_line_to`; the line-length test is rewritten to assert a *covering*, not a fixed length (§7).

**Decision: true supercover (no corner-cutting).** LOS here means "is every cell the segment passes through walkable?" A diagonal wall (two diagonally-adjacent blocking cells) **must** block LOS — otherwise players shoot/see through wall corners. True supercover includes **both** flanking cells at every corner crossing, so a diagonal wall correctly blocks. This is the conservative, exploit-free default and matches the spirit of the old hex line (hexes have no corner-cut ambiguity).

**Canonical implementation** — replaces `Coordinates.get_line_to` body (`models.py` lines 24-53; deletes `cube_lerp`, `cube_round`, the `1e-6/2e-6` nudges):

```python
def get_line_to(self, other: 'Coordinates') -> List['Coordinates']:
    """
    True supercover line from self to other (inclusive). Includes EVERY cell the
    segment passes through, including both flanking cells at a diagonal corner
    crossing, so a diagonal wall blocks line-of-sight (no corner-cutting).
    Used by PathfindingService.check_line_of_sight and combat opportunity-attack LOS.
    """
    x0, y0 = self.x, self.y
    x1, y1 = other.x, other.y
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx = 1 if x1 > x0 else -1
    sy = 1 if y1 > y0 else -1

    cells = [Coordinates(x=x0, y=y0)]
    if dx == 0 and dy == 0:
        return cells

    x, y = x0, y0
    err = dx - dy
    n = dx + dy
    while n > 0:
        e2 = 2 * err
        if e2 == 0:
            # Exact corner crossing: emit BOTH flanking cells, then step diagonally.
            cells.append(Coordinates(x=x + sx, y=y))
            cells.append(Coordinates(x=x, y=y + sy))
            x += sx
            y += sy
            err += dx - dy
            n -= 2
        elif e2 > -dy:
            err -= dy
            x += sx
            n -= 1
        else:  # e2 < dx
            err += dx
            y += sy
            n -= 1
        cells.append(Coordinates(x=x, y=y))
    return cells
```

**Behavioral contract for consumers and tests:**
- Endpoints always included.
- **Pure orthogonal / axis-aligned line:** `len(line) == distance + 1`.
- **Any line with a diagonal component:** `len(line) > distance + 1` (supercover adds flank cells). **Do not** assert a fixed length for diagonal lines — assert the cell set is a valid contiguous covering (see §7 test rewrite).
- A diagonal wall (both flank cells non-walkable) → `check_line_of_sight` returns `False`. This is the real regression guard.

**Frontend has NO LOS function** today and gets none — porting it would be dead code and a parity-drift risk. LOS stays backend-only.

### 2.5 Coordinate ↔ pixel (frontend only)

The old `hexToPixel` is a **sheared** map (`y` depends on both `q` and `r`). It is replaced wholesale (a partial rename leaves the grid skewed):

```ts
// Returns {px, py} (NOT {x, y}) to avoid colliding with the now-{x,y} coordinate fields.
export const cellToPixel = (x: number, y: number) => ({ px: x * CELL_SIZE, py: y * CELL_SIZE });
```
All 9 call sites destructure `{ px, py }`. (`pixelToCell` is **not** added — no current consumer.)

### 2.6 SVG cell shape

`HEX_HEIGHT` is deleted. `HEX_PATH` (6-vertex hexagon) → `CELL_PATH` (square centered at origin):
```ts
export const CELL_PATH = `M ${-CELL_SIZE/2} ${-CELL_SIZE/2} h ${CELL_SIZE} v ${CELL_SIZE} h ${-CELL_SIZE} Z`;
```
Render sites change `d={HEX_PATH}` → `d={CELL_PATH}` (one-line swaps; no JSX restructuring).

### 2.7 Room & door model

- A **room** is one or more axis-aligned rectangles of floor cells (`rect(x0, x1, y0, y1)` generator). Corridors are width-1 rects. Each room keeps its own local `{x, y}` frame; the renderer computes a per-room bounding box and translates independently.
- A **door** sits on the **perimeter ring one cell outside** the room rectangle, orthogonally adjacent to the floor edge it connects through (N: `y0-1`, S: `y1+1`, W: `x0-1`, E: `x1+1`). The door cell **is** included in `walkable_cells` so it is steppable and pathfindable. There is no wall/edge data model — doors are interactables on cells.
- **Room rendering padding becomes symmetric:** the old asymmetric `padX = HEX_SIZE*1.5` / `padY = √3*HEX_SIZE` (a flat-top-hex artifact) → a single `pad = CELL_SIZE`. Since the bounding box is computed from floor (non-door) cells, one cell of pad exactly frames the edge-ring doors.

### 2.8 Field-name decision: `walkable_hexes` → `walkable_cells`

Per the hard-cut directive, the JSON/wire key **is renamed** to `walkable_cells`, guarded during the cutover by a transitional `mode="before"` validator on `Location` that accepts the legacy key. The rename is sequenced as its **own phase after** the geometry is proven (Phase 5), so a missed accessor — which silently empties the map — is debugged in isolation. The `party_locations` field name is kept (it carries no hex terminology; only its embedded `position` shape changes).

---

## 3. Inventory by Subsystem

Concise file → change per area. Difficulty: T=trivial, L=low, M=medium, H=high.

### 3.1 Geometry core

| File | Change | Diff |
|---|---|---|
| `backend/app/models.py` (16-22) | `Coordinates` → `{x:int, y:int}`; `distance_to` → `max(\|dx\|,\|dy\|)`. Add transitional `@model_validator(mode="before")` mapping legacy `q/r→x/y`. | M |
| `backend/app/models.py` (24-53) | Replace `get_line_to` with canonical supercover (§2.4); delete `cube_lerp`/`cube_round`/nudges. Signature unchanged. | H |
| `backend/app/utils/grid_utils.py` (1-5) | `hex_distance(q1,r1,s1,q2,r2,s2)` → `chebyshev_distance(x1,y1,x2,y2)` (4 args). | L |
| `backend/app/utils/grid_utils.py` (7-18) | `get_neighbors(2-tuple)` returns 8 cells. Name kept (importers unchanged). | L |

### 3.2 Pathfinding & movement (consolidate → migrate)

| File | Change | Diff |
|---|---|---|
| `backend/app/services/pathfinding_service.py` | `find_reachable_hexes`→`find_reachable_cells` (2-tuples, `deque`); add `find_best_cell_toward`, `find_best_cell_adjacent_to`; `check_line_of_sight` uses `(c.x,c.y)` sets. | M |
| `backend/app/services/turn_manager.py` (351-581) | **Live combat path.** Replace 2 inline LOS blocks, inline `get_neighbors` (433-441), inline BFS (443-456), inline 3-axis distance (462/465) with shared service calls; writes `.x/.y`; anim `{x,y}`; logs `x=/y=`. | H |
| `backend/app/services/game_service.py` (318-417) | **Live follow path.** Delete inline `hex_distance` (334-336) + inline `get_neighbors` (375-383) + inline BFS; call `find_best_cell_toward`; writes `.x/.y`; anim `{x,y}`. | H |
| `backend/app/ai_tools.py` (79-150) | `t_pos`→`Coordinates(x=,y=)`; replace inline BFS/adjacency with `find_best_cell_adjacent_to`; writes `.x/.y`; anim `{x,y}`; tool-arg dict keys `q/r/s`→`x/y`. | M |
| `backend/app/services/ai_turn_service.py` | **DELETE entire file** (dead — zero external callers). | T |
| `backend/app/services/movement_service.py` | **Delete `process_ai_following`** (dead); delete orphan `resolution_move`; clean up unused `grid_utils` imports. | L |
| `backend/app/services/combat_service.py` (221-636) | `distance_to` calls unchanged; LOS set/check → `(x,y)` (553/567); cloned `Coordinates(x=,y=)` (636); keep `//5` and range comparisons; var/string `hex`→`cell` cosmetic. | M |
| `backend/app/services/loot_service.py` (92-310) | `Coordinates(q=,r=,s=)` → `Coordinates(x=,y=)`; fallback `(0,0)`; `distance_to` unchanged. | L |
| `backend/app/utils/entity_utils.py` (189-223) | Spawn/occupied tuples `(q,r,s)`→`(x,y)`; `(0,0,0)`→`(0,0)`; writes `.x/.y`. | L |

### 3.3 Socket handlers & wire protocol

| File | Change | Diff |
|---|---|---|
| `backend/app/socket/handlers/exploration.py` (23-97) | Read `data.get('x')/('y')`; **drop the `target_s` null-guard** (currently hard-rejects null `s`); walkable/collision → `.x/.y`; write `Coordinates(x=,y=)`. `move_entity` server contract. | M |
| `backend/app/socket/handlers/exploration.py` (~100) | `entity_path_animation` re-emit of client path — **pass-through, NO transform** (correct once frontend sends `{x,y}`). | — |
| `backend/app/socket/handlers/game_state.py` (143, 187-197) | Default `Coordinates(x=0,y=0)`; spawn `spawn_data.get('x'/'y')`, drop `s`; comment `spawn hex`→`spawn cell`. | L |
| `backend/app/services/connection_service.py` (64) | `Coordinates(x=0,y=0)`. | T |
| `backend/app/routers/campaigns.py` (262) | `Coordinates(x=0,y=0)`; `walkable_hexes` pass-through follows field rename. | T |

### 3.4 State / persistence

| File | Change | Diff |
|---|---|---|
| `backend/app/services/state_service.py` (148/207/251) | Hydration default `{"q":0,"r":0,"s":0}` → `{"x":0,"y":0}` (×3). Save path self-heals via `model_dump()`. | L |
| `backend/app/services/state_service.py` (16-35) | `_last_broadcasted_state` cache: cleared free on process restart; explicit `.clear()` on startup as `--reload` insurance (§4, §6). | L |
| `backend/db/init_db.py` | Add idempotent fail-open migration block (§4) — **sole migration execution path**. | H |
| `backend/db/migrate_coords.py` (NEW) | `_walk` + `migrate_json_text` (§4). | M |
| `backend/main.py` (after `init_db_async()`) | `StateService._last_broadcasted_state.clear()`. | T |
| `backend/db/schema.py` | No DDL change (positions are JSON-in-Text). | — |

### 3.5 Seed data & authoring (repo-root `games/`)

| File | Change | Diff |
|---|---|---|
| `backend/scripts/build_tosk_campaign.py` | `block`→`rect`; doors to edge ring; `{x,y}` literals; **delete `check_hex`/`s=-q-r` invariant**; rewrite `validate`; coffin/skeleton co-location fix; writes to `../../games/`. | H |
| `games/Tomb_of_the_Serpent_Kings.json` | **Regenerated** from build script (144 positions). | — |
| `backend/scripts/build_goblin_test.py` (NEW) | Generator mirroring ToSK; rectangles + edge doors; folds latent fixes (treasury chest position, north-room door, north-goblin positions). | H |
| `games/Goblin_Combat_Test.json` | **Regenerated** (73 positions). | — |
| `games/blank_schema.json` | `walkable_cells`, door `position {x,y}`, `party_locations` scaffold. | T |
| `backend/app/services/test_campaign_setup.py` (43/68/93/247/252) | Sheet positions `{x,y}`; NPC `Coordinates(x=,y=)`, drop `s=-q-r` fallback. | L |
| `backend/app/services/tosk_setup.py` (123/127/137) | NPC `Coordinates(x=,y=)`, drop `s=-q-r`; placed tuple `(x,y)`; `hex` comments. | L |
| `backend/app/services/campaign_loader.py` | Pass-through; optional one-line `migrate_json_text` guard before insert (idempotent belt-and-suspenders). | T |

### 3.6 Frontend

| File | Change | Diff |
|---|---|---|
| `frontend/src/lib/hexMath.ts` → `gridMath.ts` (NEW name) | `CELL_SIZE`, `CELL_PATH`, `cellToPixel`→`{px,py}`, `chebyshevDistance`, 8-neighbor `getNeighbors`; delete `HEX_HEIGHT`. | M |
| `frontend/src/lib/socket.ts` (28-32) | `Coordinates {x,y}`. | T |
| `frontend/src/components/BattlemapPanel.tsx` | Import swap; ~70 `.q/.r→.x/.y`; `{q,r,s}` literals→`Coordinates`/`{x,y}`; `move_entity` emit `{entity_id,x,y,path}` (drop `q/r/s`); BFS 8-way `getNeighbors`; `cellToPixel` `{px,py}` ×9; symmetric `pad = CELL_SIZE` (429-438); `d={CELL_PATH}`; `animatingPath` `{x,y}`. | H |
| `frontend/src/test/SocketProvider.test.tsx` (185) | Fixture `{q,r,s}`→`{x,y}` (typed `any` — tsc won't catch; fix by hand). | T |
| `frontend/src/lib/SocketProvider.tsx` (127-162) | **No code change.** Existing 3-failure resync is the cutover safety net (§6). | — |

### 3.7 Tests

| File | Change | Diff |
|---|---|---|
| `backend/tests/conftest.py` (18, 104-117) | `coords`→`Coordinates(x=q,y=r)`; `location_factory` rectangle arena; `cells=`/`walkable_cells=`. | L |
| `backend/tests/test_models.py` | Delete `test_s_invariant`; rewrite distance (diagonal Chebyshev) + **supercover line covering** asserts (§7); add corner-cut LOS tests; `{x,y}` fixtures. | M |
| `backend/tests/test_hex_movement.py` → `test_square_movement.py` | Rename; inline `hex_distance`→Chebyshev; `{x,y}`; recompute distances. | M |
| `backend/tests/test_ai_pathfinding.py` | `{x,y}`; recompute end-cell if diagonals change optimal path (straight corridor unaffected). | M |
| `backend/tests/test_coord_migration.py` (NEW) | `migrate_json_text` unit tests incl. mixed `{x,y,q,r,s}` guard (§4, §7). | L |
| `test_turn_manager`, `test_turn_concurrency`, `test_game_loop`, `test_multiattack`, `test_combat_loot_debug`, `test_conditions`, `test_identification` | Mechanical `{q,r,s}→{x,y}`; `test_identification` drops `q/r/s/z`, keeps `x/y`. | L |

### 3.8 Diagnostics & docs (Phase 5, low priority)

`backend/check_hexes.py`, `backend/inspect_map.py`, `backend/inspect_positions.py`, root `tests/verify_*.py`, `backend/scripts/verification/*.py`, `commands/combat.py:114` & `commands/interaction.py:123` (LLM-facing "hex" strings), `CLAUDE.md`, `README.md`, `design_docs/*`.

---

## 4. Data Migration (JSON transform + broadcast-cache reset)

> **Critique resolution (high #4):** Alembic is **never invoked** in this repo — no `command.upgrade`, no `alembic upgrade` in any script; startup runs `init_db_async()` only. **No Alembic revision is created.** The `init_db.py` block is the **sole** migration execution path, consistent with the existing `ALTER TABLE … IF NOT EXISTS` convention.

> **Critique resolution (low #7):** `get_game_state` reads only the **latest** `game_states` row. Older snapshots are never hydrated. Load-safety comes from **(a)** the `Coordinates` compat shim + **(b)** transforming the latest row. We still transform all rows (cheap, idempotent, defensive), but this is not the load-safety guarantee.

### Step 1 — Where positions live (verified)

No coordinate columns exist. All positions are JSON inside **Text** columns:

| Table | Column | Contents |
|---|---|---|
| `game_states` | `state_data` | Full GameState: `location.walkable_hexes[]`, `party_locations[].position`, `interactables[].position`, party/enemy/npc/vessel positions |
| `characters` | `sheet_data` | player `position` |
| `monsters` | `data` | enemy `position` |
| `npcs` | `data` | NPC `position` |
| `locations` | `data` | authored `walkable_hexes[]`, `interactables[].position`, `party_locations[].position` |

### Step 2 — The transform (`backend/db/migrate_coords.py`, NEW)

> **Critique resolution (medium #6):** Two slices shipped subtly different `_walk` guards. The **stricter** guard is canonical: migrate only when `'q' in node and 'r' in node and 'x' not in node`. This preserves any dict that already carries `x` (e.g. a mixed `{x,y,z,q,r,s}` fixture), preventing the real `x` from being clobbered by `q`.

```python
# backend/db/migrate_coords.py
import json

def _walk(node):
    """Recursively map {q,r,s?} -> {x,y}, dropping s. Idempotent.
    Stricter guard: only migrate dicts that have q & r but NOT x, so a dict
    already carrying x (mixed/half-migrated) is never clobbered."""
    if isinstance(node, dict):
        if "q" in node and "r" in node and "x" not in node:
            migrated = {"x": node["q"], "y": node["r"]}
            for k, v in node.items():
                if k not in ("q", "r", "s"):
                    migrated[k] = _walk(v)
            return migrated
        return {k: _walk(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_walk(v) for v in node]
    return node

def migrate_json_text(raw: str):
    """Returns (new_json_text, changed?). Safe on NULL/garbage (returns unchanged)."""
    if not raw:
        return raw, False
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return raw, False
    migrated = _walk(data)
    if migrated == data:
        return raw, False
    return json.dumps(migrated), True
```

Idempotency: after one pass every coord is `{x,y}`, so the guard never fires again → `changed=False`.

### Step 3 — The `Coordinates` compat shim (transitional, removed in Phase 5)

The locked decision is a hard cut, but `Coordinates(**pos)` runs on hydrate. A `mode="before"` validator makes the cutover crash-proof even if one row/file is missed:

```python
@model_validator(mode="before")
@classmethod
def _accept_legacy_qrs(cls, data):
    # Transitional: tolerate pre-migration {q,r,...} dicts. Removed in Phase 5
    # once census confirms 0 legacy rows. New code never emits q/r/s.
    if isinstance(data, dict) and "x" not in data and "q" in data:
        return {"x": data["q"], "y": data["r"]}
    return data
```

A parallel `Location` `mode="before"` shim handles the `walkable_hexes`→`walkable_cells` **key** rename (Pydantic would otherwise silently drop the unknown key, emptying the map):

```python
@model_validator(mode="before")
@classmethod
def _accept_legacy_walkable_hexes(cls, values):
    if isinstance(values, dict) and "walkable_cells" not in values and "walkable_hexes" in values:
        values["walkable_cells"] = values.pop("walkable_hexes")
    return values
```

### Step 4 — Migration block in `init_db.py` (sole execution path)

Add after the existing `ALTER TABLE` block, mirroring its `try/except` convention:

```python
    # --- COORDINATE MIGRATION: {q,r,s} -> {x,y} (idempotent, fail-open) ---
    try:
        from db.migrate_coords import migrate_json_text
        targets = [
            ("game_states", "id", "state_data"),
            ("characters",  "id", "sheet_data"),
            ("monsters",    "id", "data"),
            ("npcs",        "id", "data"),
            ("locations",   "id", "data"),
        ]
        async with engine.begin() as conn:
            for table, pk, col in targets:
                res = await conn.execute(text(f"SELECT {pk}, {col} FROM {table}"))
                for row_id, raw in res.fetchall():
                    new_raw, changed = migrate_json_text(raw)
                    if changed:
                        await conn.execute(
                            text(f"UPDATE {table} SET {col} = :v WHERE {pk} = :id"),
                            {"v": new_raw, "id": row_id},
                        )
    except SQLAlchemyError as e:
        logger.warning(f"Coordinate migration failed (non-fatal): {e}")
```

> If `walkable_hexes`→`walkable_cells` is committed in Phase 5, add a key-rename step to `_walk` (or a second pass) and re-run this block over the 5 columns. Until then, the `Location` `before` shim handles reads.

### Step 5 — Seed-source files (repo-root `games/`)

> **Critique resolution (medium #5):** seed files are at **repo-root `games/`** — `backend/games/` does not exist. All in-place transforms and build-script outputs target `games/` (build scripts in `backend/scripts/` write to `../../games/`).

The cleanest path is **regeneration** via the migrated build scripts (Phase 4e). As belt-and-suspenders for files not regenerated, transform in place:

```bash
python -c "import json,sys; sys.path.insert(0,'backend'); \
from db.migrate_coords import migrate_json_text; \
p=sys.argv[1]; t=open(p).read(); n,c=migrate_json_text(t); \
open(p,'w').write(n) if c else None; print(p, 'changed' if c else 'clean')" \
  games/Goblin_Combat_Test.json
```
(Also: `games/Tomb_of_the_Serpent_Kings.json`, `games/blank_schema.json`. The other three `games/*.json` have 0 coordinate keys — confirmed clean.)

### Step 6 — Broadcast-cache reset

> **Critique resolution (medium #5b):** `_last_broadcasted_state` is a class-level dict, **empty on every fresh process start** — a normal restart clears it for free, and `emit_state_update` already sends a full `game_state_update` when the prior dict is falsy. The explicit clear is cheap insurance for `uvicorn --reload` warm reloads only; **the real guarantee is "deploy = process restart."**

In `main.py` startup, **after** `init_db_async()`:
```python
from app.services.state_service import StateService
StateService._last_broadcasted_state.clear()  # insurance for --reload; restart clears it anyway
```
Effect: the first `emit_state_update` per campaign is a full state, so no patch ever references a stale `q/r/s` path.

---

## 5. Phased Migration Sequence (the core)

The ordering keeps the app **loadable at every commit boundary**. The breaking rename is **one atomic phase**. Consolidation lands **before** the rename to shrink its surface.

### Phase 0 — Preflight

**Changes:** Branch `feat/square-grid-migration` off `main`. `pg_dump "$DATABASE_URL" > /tmp/pre_square_migration.sql`. Census legacy coords:
```bash
psql "$DATABASE_URL" -c "SELECT 'game_states', count(*) FROM game_states WHERE state_data LIKE '%\"s\":%'
  UNION ALL SELECT 'characters', count(*) FROM characters WHERE sheet_data LIKE '%\"q\":%'
  UNION ALL SELECT 'monsters', count(*) FROM monsters WHERE data LIKE '%\"q\":%'
  UNION ALL SELECT 'npcs', count(*) FROM npcs WHERE data LIKE '%\"q\":%'
  UNION ALL SELECT 'locations', count(*) FROM locations WHERE data LIKE '%\"q\":%';"
```
Confirm live paths (done): combat = `TurnManager.execute_ai_turn`; follow = `GameService.process_ai_following`.

**Working state:** Working. **Verification:** census returns counts; dump non-empty. **Rollback:** delete branch. **Effort:** ~0.5 hr.

### Phase 1 — Shared pathfinding skeleton (hex-preserving consolidation)

**Goal:** Make `PathfindingService` the single home for BFS/LOS/distance and route the **live** paths through it — still on hex math, so behavior is identical.

**Changes:** Add `find_best_cell_toward` / `find_best_cell_adjacent_to` to `PathfindingService` in **hex form** (3-tuple BFS + `hex_distance` internally). Replace inline BFS/`get_neighbors`/sort in the **live** paths only — `turn_manager._execute_ai_turn`, `game_service.process_ai_following`, `ai_tools._run_interact` — with calls to these helpers (still hex). Leave dead duplicates for Phase 2.

**Working state:** Working (pure refactor; identical hex behavior). **Verification:** `cd backend && ./venv/bin/pytest -m "not integration"` green; manual dev quick-test — AI combat turn + follow move identically to pre-change. **Rollback:** `git revert`. **Effort:** ~1 day.

### Phase 2 — Delete dead code

> **Critique resolution (high #3):** `AITurnService.execute_ai_turn` has **zero external callers** (verified). It is deleted, not migrated — removing ~400 lines of `q/r/s` from the Phase 4 surface. Its multiattack/spell logic, if wanted in live combat, is a **separate feature task**, decided explicitly — not migrated as live code.

**Changes:** Delete `backend/app/services/ai_turn_service.py` entirely. Delete `MovementService.process_ai_following` + its inline BFS. Delete the orphan `resolution_move` duplicate (keep whichever the live move handler calls — grep `resolution_move` callers). Remove now-unused `grid_utils` imports.

**Working state:** Working (removing unreachable code). **Verification:** `grep -rn "AITurnService\|MovementService.process_ai_following\|\.resolution_move" backend/app/` shows no live callers to deleted symbols; `./venv/bin/python -c "import main"`; `./venv/bin/pytest -m "not integration"`. **Rollback:** `git revert`. **Effort:** ~0.5 day.

### Phase 3 — *(folded into Phase 4)*

An intermediate "8-way math on `{q,r,s}` fields" step would force throwaway code that fabricates `s = -q-r` per neighbor. Since the math change and field rename touch the same functions, they land together in Phase 4. **Effort:** 0.

### Phase 4 — THE ATOMIC RENAME `{q,r,s}→{x,y}` (single commit / PR)

Type + math + all call sites + wire + data migration + cache reset + seeds + frontend + tests, in one indivisible commit. The app is broken **only inside the working tree**; it is **load-safe at the commit boundary** via the compat shim + bundled migration + restart. Internal order:

- **4a — Type + geometry core:** `models.py` `Coordinates {x,y}`, `distance_to` Chebyshev, **canonical supercover `get_line_to` (§2.4)**, compat shim. `grid_utils.py` `chebyshev_distance` + 8-neighbor `get_neighbors`.
- **4b — Shared service + backend call sites:** `pathfinding_service` cells-typed; finalize helpers; convert `turn_manager`, `game_service`, `ai_tools`, `combat_service`, `loot_service`, `entity_utils`, `connection_service`, `state_service` defaults, `routers/campaigns.py`, `game_state.py`. `Location` validator → `(x,y)` + `walkable_hexes` `before` shim.
- **4c — Wire protocol (flip together):** `exploration.py` reads `{x,y}`, drops `target_s` guard; **5 server-side `entity_path_animation` emit sites** build `{x,y}` (`ai_tools`, `turn_manager`, `game_service`; `ai_turn_service`/`movement_service` already deleted). `exploration.py:100` is **pass-through, no edit** (correct once frontend sends `{x,y}`). Frontend: `socket.ts`, `gridMath.ts`, `BattlemapPanel.tsx`.
- **4d — Data migration + cache reset:** `migrate_coords.py`; `init_db.py` block (sole path — **no Alembic**); `main.py` cache clear.
- **4e — Seeds (repo-root `games/`):** rewrite `build_tosk_campaign.py` (writes `../../games/`), regenerate `games/Tomb_of_the_Serpent_Kings.json`; new `build_goblin_test.py`, regenerate `games/Goblin_Combat_Test.json` with latent fixes; `games/blank_schema.json`; `test_campaign_setup.py` + `tosk_setup.py` seed reads.
- **4f — Tests:** `conftest`; `test_models` (delete `test_s_invariant`, rewrite as **supercover covering** asserts + corner-cut LOS guards); rename `test_hex_movement`→`test_square_movement`; `test_ai_pathfinding`; new `test_coord_migration` (incl. mixed-dict guard); mechanical fixture renames across the suite; `SocketProvider.test.tsx:185`.

**Working state:** Breaking *within* the commit; **load-safe at the boundary.** Deploy = process restart (clears cache) + migration runs (init_db) before clients connect.

**Verification:**
1. `cd backend && ./venv/bin/pytest` (full, incl. integration) green.
2. `./venv/bin/python -c "import main"` clean.
3. Census re-run: `… LIKE '%"s":%'` and `… LIKE '%"q":%'` return **0** across all 5 columns.
4. Load-every-campaign smoke: `StateService.get_game_state(campaign_id)` for all campaigns — no Pydantic raise.
5. `./scripts/dev-start.sh --reset-db`; dev campaign Quick Join → Enter: tokens at correct cells, click-to-move emits `{x,y}` (WS devtools), server accepts, `entity_path_animation` carries `{x,y}`, **diagonal moves reachable**, no console patch errors.
6. Full AI combat turn + out-of-combat follow: no backend `KeyError`/Pydantic errors; rooms render as rectangles, doors symmetrically framed.
7. Idempotency: restart → migration reports 0 changed rows.

**Rollback:** Forward-only by decision. Recovery = `psql < /tmp/pre_square_migration.sql` + `git revert`. Compat shim means a partially-applied migration still loads; an interrupted run is recoverable by re-running (idempotent). **Effort:** ~3–4 days.

### Phase 5 — Terminology hard-cut, `walkable_hexes` rename, shim removal

**Changes:** Commit `walkable_hexes`→`walkable_cells` across `socket.ts`, `Location` model, seed/loader sites, ~7 backend + ~6 frontend readers, and the JSON-blob key (add a key-rename step to `migrate_json_text` + re-run). Rename `hex`→`cell`/`square` in vars/comments/classNames (`handleHexHover`→`handleCellHover`, `className="hex-rooms"`→`"grid-rooms"` — grep stylesheets first), LLM-facing strings (`commands/combat.py:114`, `commands/interaction.py:123`), diagnostics, docs (`CLAUDE.md`, `README.md`, `design_docs/*`). **Remove both compat shims** once census confirms 0 legacy rows and seeds are regenerated.

**Working state:** Working throughout (cosmetic + already-migrated cleanups). Shim removal only after Phase 4 verification + census = 0. **Verification:** `./venv/bin/pytest`; frontend `npm run build` (tsc) clean; full dev quick-test; `grep -rn "\.q\b\|hex_distance\|walkable_hexes\|getHexNeighbors" backend/app frontend/src` returns only intended remnants. **Rollback:** `git revert`; if shim removal surfaces an unmigrated row, re-add shim + re-run migration. **Effort:** ~1–1.5 days.

### At-a-glance

| Phase | Scope | Boundary state |
|---|---|---|
| 0 | Snapshot, census, confirm live paths | Working |
| 1 | Consolidate BFS/LOS into PathfindingService (hex-preserving) | Working |
| 2 | Delete dead code (AITurnService, MovementService dups, orphan resolution_move) | Working |
| 3 | *(folded into 4)* | — |
| **4** | **ATOMIC: type + math + call sites + wire + migration + cache reset + seeds + frontend + tests** | **Breaking in-commit; load-safe at boundary** |
| 5 | Terminology, `walkable_cells` rename, shim removal | Working |

---

## 6. Risk Register & Gotchas

| # | Risk | Mitigation |
|---|---|---|
| R1 | **LOS algorithm divergence** (was the blocker): three conflicting `get_line_to` implementations disagreed on the pure diagonal. | **Resolved.** One canonical true-supercover (§2.4). All 4 consumers (`check_line_of_sight`, `combat_service:564`, `turn_manager` 406/495 → now shared-service calls) use it. Corner-cut regression tests pin it (§7). |
| R2 | **Line-length test ambiguity** depends on which line algorithm. | **Resolved.** Test rewritten: orthogonal `len==distance+1`; diagonal asserts a *valid covering* + explicit corner-cut `LOS==False` cases (§7). |
| R3 | **`move_entity` wire contract** — `exploration.py:28` hard-rejects null `s`; frontend emits `{q,r,s}`. | Flip both in Phase 4c (same PR). Drop the `s` null-guard server-side; frontend emits `{x,y}`. |
| R4 | **`entity_path_animation` payload** built `{q,r,s}` at 5 server sites + consumed by `BattlemapPanel`. | Flip the 5 BFS emit sites to `{x,y}` in Phase 4c. `exploration.py:100` is **pass-through — no edit** (critique low #9). |
| R5 | **Multiple inline `get_neighbors`/`hex_distance`/BFS copies** — missing one silently leaves hex behavior. | Phase 1 consolidates the **live** copies into `PathfindingService`; Phase 2 deletes the **dead** copies (AITurnService, MovementService). After Phase 2 only the live shared copy remains to rename. |
| R6 | **`Coordinates(**pos)` raises on un-migrated rows** after `s` removal. | `mode="before"` compat shim (§4 step 3) + migration in same deploy. Shim removed in Phase 5. |
| R7 | **Stale broadcast-cache → garbage JSON Patch.** | Real guarantee is restart (cache is fresh-process-empty); explicit `.clear()` insurance for `--reload`; first emit is always full state (critique medium #5b). |
| R8 | **Seed `--reset-db` re-injects hex** if `games/*.json` not migrated. | Regenerate via build scripts (Phase 4e) writing to repo-root `games/`; optional `migrate_json_text` guard in `campaign_loader`. |
| R9 | **Wrong seed paths** — `backend/games/` does not exist. | All transforms/build outputs target repo-root `games/`; build scripts write `../../games/` (critique medium #5). |
| R10 | **Mixed `{x,y,q,r,s}` dict clobber** (`test_identification` fixture). | Stricter `_walk` guard (`x not in node`) preserves real `x`; unit-tested (critique medium #6). |
| R11 | **Over-eagerly "fixing" `//5` budget or `distance_to` math** that is already Chebyshev-correct. | Leave `speed//5`, `max_reach=6`, range comparisons untouched; only field names + `s` axis change. |
| R12 | **Goblin map redesign** — irregular hex disks, no generator, latent bugs (treasury chest has no position; north room has no door; north goblins have no position). | New `build_goblin_test.py` (rectangles + edge doors) folds the fixes in (Phase 4e). |
| R13 | **`cellToPixel {px,py}` vs coordinate `{x,y}` name collision.** | `cellToPixel` returns `{px,py}`; all 9 call sites destructure accordingly. |
| R14 | **Integration-marked tests** don't run in the fast suite — coordinate breakage hides. | Phase 4 verification runs the **full** suite (incl. integration). |
| R15 | **Dead Alembic ceremony** mistaken for a safety net. | No Alembic revision created; `init_db.py` is the sole, plainly-stated execution path (critique high #4). |

---

## 7. Verification Strategy

### Automated tests

**`PathfindingService` unit tests (no DB):**
1. `find_reachable_cells((0,0), 1, open5x5, set())` → 9 keys (8 neighbors + start), each path length 1.
2. Diagonal reachability: `(0,0)→(2,2)` reachable at `max_move=2` (proves diagonals cost 1).
3. `find_best_cell_toward` picks a diagonal cell when it is strictly closest.
4. `find_best_cell_adjacent_to` returns a cell 8-adjacent to target with shortest path.

**LOS / `get_line_to` (`test_models.py`) — rewritten for canonical supercover:**
- DELETE `test_s_invariant`.
- Distance: `Coordinates(0,0).distance_to(Coordinates(3,2)) == 3` (diagonal Chebyshev).
- **Orthogonal covering:** for `(0,0)→(4,0)`, `len(line) == 5` and cells are contiguous on `y=0`.
- **Diagonal covering (NOT fixed length):** for `(0,0)→(3,3)`, assert the returned cells form a valid contiguous supercover that includes both flank cells at each corner; assert `len(line) > distance + 1`. Do not assert a magic number.
- **Corner-cut regression (the real guard):** with a diagonal wall (two diagonally-adjacent cells non-walkable), `check_line_of_sight` across the corner returns **`False`**; with a clean diagonal corridor, returns **`True`**.

**Migration (`test_coord_migration.py`, fast suite):**
- Basic `{q,r,s}`→`{x,y}` (drops `s`).
- Nested `walkable_hexes` / `party_locations` / `interactables`.
- Idempotent (already-`{x,y}` → `changed=False`).
- NULL / garbage safe.
- `{q,r}` without `s` migrates.
- **Mixed `{x,y,z,q,r,s}` preserves real `x,y`** (stricter-guard regression).

**Model round-trip:** `Coordinates(**{"q":1,"r":2,"s":-3}).x == 1 and .y == 2` (compat shim).

**Suite run:** `cd backend && ./venv/bin/pytest` (full, incl. integration) after Phase 4. Frontend `npm run build` (tsc) after frontend changes.

### Manual dev-campaign checks (per CLAUDE.md quick-start)

`./scripts/dev-start.sh --reset-db`, then `http://localhost:3000/campaign_dash/dev-test-campaign-001` → Quick Join → Enter:
1. Tokens render at correct cells; rooms are rectangles; doors symmetrically framed (no clip/gap).
2. Click-to-move: hover plots a path including diagonals; `move_entity` emits `{x,y}` (WS devtools); server accepts; token animates; `entity_path_animation` carries `{x,y}`.
3. **Diagonal reachability:** a cell two diagonal steps away is reachable within speed budget.
4. Attack the Lizardfolk; trigger an AI combat turn (the live `TurnManager` path) — AI paths to an adjacent cell and attacks; no backend errors.
5. Out-of-combat: move the party leader; AI followers (live `GameService.process_ai_following`) keep within 3 cells.
6. No `applyPatch` errors in the browser console across the session.

### Pre/post census

Before: record legacy counts (Phase 0). After Phase 4: re-run — all 5 columns return **0** for both `"s":` and `"q":`. After restart: migration reports 0 changed rows (idempotency).

---

## 8. Total Effort Estimate

| Phase | Effort |
|---|---|
| 0 — Preflight | 0.5 hr |
| 1 — Consolidation (hex-preserving) | 1 day |
| 2 — Delete dead code | 0.5 day |
| 3 — *(folded)* | 0 |
| 4 — Atomic rename + migration + seeds + frontend + tests | 3–4 days |
| 5 — Terminology, `walkable_cells` rename, shim removal | 1–1.5 days |
| **Total** | **~6–7.5 days** (single engineer) |

Phase 4 is the bulk and is a reviewer-heavy single PR. Phases 1–2 (consolidate-then-delete) are the leverage: they cut Phase 4's duplicated-implementation surface from ~9 copies to ~1, and remove a dead ~400-line `AITurnService`.

---

## 9. Out of Scope / Future

- **AoE / spell templates** (cones, spheres, lines, cubes). No template geometry exists today — spells/attacks are strictly single-target via `target_char`. Square-grid AoE is a future feature, not a migration concern.
- **Cover system / partial cover.** No cover model exists; LOS is binary walkable-vs-blocked.
- **Permissive vs strict diagonal LOS toggle.** The canonical supercover is strict (corner-blocking). If playtest wants permissive LOS, it is a one-function swap behind a flag — not structural.
- **Diagonal movement corner-cut prevention** (requiring both flanking cells walkable to move diagonally). Hook (`block_diagonal_corner_cut`) noted; not enabled (locked decision allows free diagonals).
- **Reviving `AITurnService` multiattack/spell logic in combat.** The live `TurnManager.execute_ai_turn` lacks multiattack/spell handling that the dead `AITurnService` had — a pre-existing feature gap. Restoring it is a **separate feature task**, explicitly out of scope here.
- **`get_game_state` multi-snapshot loading.** Runtime reads only the latest row; surfacing older snapshots is unrelated future work.
- **Migrating the other `games/*.json`** (Echoes, Great Pie Caper, Cellar Sovereignty) — confirmed 0 coordinate keys; nothing to do.

---

### Files of record (atomic Phase 4), absolute paths

`/Users/latent/Vibes/RoundTable_4_1/backend/app/models.py` · `/Users/latent/Vibes/RoundTable_4_1/backend/app/utils/grid_utils.py` · `/Users/latent/Vibes/RoundTable_4_1/backend/app/services/pathfinding_service.py` · `/Users/latent/Vibes/RoundTable_4_1/backend/app/services/turn_manager.py` · `/Users/latent/Vibes/RoundTable_4_1/backend/app/services/game_service.py` · `/Users/latent/Vibes/RoundTable_4_1/backend/app/ai_tools.py` · `/Users/latent/Vibes/RoundTable_4_1/backend/app/services/combat_service.py` · `/Users/latent/Vibes/RoundTable_4_1/backend/app/socket/handlers/exploration.py` · `/Users/latent/Vibes/RoundTable_4_1/backend/db/migrate_coords.py` (new) · `/Users/latent/Vibes/RoundTable_4_1/backend/db/init_db.py` · `/Users/latent/Vibes/RoundTable_4_1/backend/main.py` · `/Users/latent/Vibes/RoundTable_4_1/backend/scripts/build_tosk_campaign.py` · `/Users/latent/Vibes/RoundTable_4_1/backend/scripts/build_goblin_test.py` (new) · `/Users/latent/Vibes/RoundTable_4_1/games/Goblin_Combat_Test.json` · `/Users/latent/Vibes/RoundTable_4_1/games/Tomb_of_the_Serpent_Kings.json` · `/Users/latent/Vibes/RoundTable_4_1/frontend/src/lib/gridMath.ts` (new) · `/Users/latent/Vibes/RoundTable_4_1/frontend/src/lib/socket.ts` · `/Users/latent/Vibes/RoundTable_4_1/frontend/src/components/BattlemapPanel.tsx`

**Deleted in Phase 2:** `/Users/latent/Vibes/RoundTable_4_1/backend/app/services/ai_turn_service.py` (dead), `MovementService.process_ai_following` + orphan `resolution_move`.