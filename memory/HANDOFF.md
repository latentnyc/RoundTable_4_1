# Working Memory / Handoff

> Written 2026-06-26 before retiring the old PC. Read this first when resuming on the new machine.

## Where things stand

- **Active branch:** `feat/phase3a-damage-pipeline` — pushed to `origin` with upstream tracking.
- **Latest commit:** `b9e29ff feat(combat): typed damage resistance/immunity/vulnerability pipeline`
- **`main`:** at `519f200` (= `origin/main`). The phase-3a branch is **ahead of main** by the one damage-pipeline commit and has **not** been merged in yet.
- Everything committed locally is on GitHub. No uncommitted work anywhere (main tree + all worktrees clean).

## What the last commit did (Phase 3a — typed damage pipeline)

New module `backend/game_engine/damage.py`:
- `tokenize_keywords()` — reduces free-form SRD resistance entries
  (e.g. `"bludgeoning, piercing, and slashing from nonmagical attacks"`) to canonical
  damage-type words.
- `damage_multiplier()` / `apply_resistances()` / `apply_typed_damage()` — 5e math:
  **immunity zeroes, vulnerability doubles, resistance halves** (round down).
  Precedence: immunity > vulnerability > resistance. `resist_all` preserves the
  legacy Petrified resist-all flag.

Wired into:
- `backend/game_engine/character_sheet.py` — `get_damage_{resistances,immunities,vulnerabilities}()`
  with dual-path reads (`data` / `sheet_data` / top-level) mirroring `get_weapon`/`get_ac`.
- `backend/game_engine/engine.py` — all four damage paths routed through `_apply_typed`,
  applied **last** per RAW (after crit-doubling and save-halving).
- `backend/app/services/combat_service.py` — threads `weapon_damage_type` into params.

## Next actions when resuming

1. **Run the backend test suite** — this change was committed but the tests were NOT run.
   `cd backend && ./venv/bin/pytest -m "not integration"` (or the venv path on the new box).
   Worth adding a unit test for `damage.py` (resist/immune/vuln/resist_all + tokenizer of
   compound SRD strings).
2. **Merge decision:** if tests pass and the feature is considered done, follow the solo-dev
   workflow — fast-forward `feat/phase3a-damage-pipeline` into `main`, then push `main`.
   (No PRs; see git-workflow note below.)
3. Known caveat in `damage.py` docstring: resistance qualifiers like "from nonmagical
   attacks" are ignored (we match the type word only), so such resistances over-apply.
   Refine once the effect system tracks magical/silvered/adamantine sources.

## Roadmap context

- Holistic review + Phase 0–5 plan lived in a gitignored `holistic-review.md` and the
  auto-memory file `roundtable-review-and-roadmap.md` (machine-local — may not transfer).
  Status as of now: Phases 0–1 done, Phase 2 (version-gating) done, Redis deferred,
  **Phase 3 in progress** (3a = this damage pipeline). If the roadmap doc didn't make it to
  the new machine, reconstruct from git history + CLAUDE.md "Known Fragile Areas".

## Repo / workflow notes

- **Git workflow (solo dev, no PRs):** branch per phase → fast-forward into `main` → push `main`.
- Pre-commit hooks are active (trailing whitespace, EOF, secrets scan, no `print()` in backend,
  no `console.log` in frontend). Keep commits clean to pass them.
- Several `claude/*` worktrees exist under `.claude/worktrees/` — all clean, all their commits
  already on remotes. The local-only label branches `integrate/pr-2`, `pr-2`, `pr-3` point at
  commits that are already on GitHub (safe to ignore / recreate).
- Dev start: `./scripts/dev-start.sh` (see CLAUDE.md Quick Start; needs Docker, Java 21,
  Python 3.11, Node 20+).
