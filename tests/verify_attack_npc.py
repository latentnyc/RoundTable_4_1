import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.models import GameState, Location, Player, NPC, Coordinates
from game_engine.engine import GameEngine

def test_attack_npc_logic():
    print("Initializing GameState with NPC 'Bork'...")

    bork = NPC(
        id="npc-bork",
        name="Bork",
        role="Innkeeper",
        is_ai=True,
        hp_current=20,
        hp_max=20,
        ac=10,
        position=Coordinates(q=0, r=0, s=0)
    )

    player = Player(
        id="player-1",
        name="Hero",
        role="Fighter",
        hp_current=20,
        hp_max=20,
        is_ai=False,
        position=Coordinates(q=0, r=0, s=0)
    )

    state = GameState(
        session_id="test-session",
        location=Location(name="Tavern", description="A cozy tavern."),
        party=[player],
        npcs=[bork]
    )

    print("Simulating @attack bork command processing...")
    target_name = "bork"

    # 1. Target Resolution Logic (mimicking chat.py)
    target_char = None

    # Check enemies (empty)
    for e in state.enemies:
        if target_name.lower() in e.name.lower():
            target_char = e
            break

    # Check NPCs
    if not target_char:
        for n in state.npcs:
            if target_name.lower() in n.name.lower():
                target_char = n
                break

    if not target_char:
        print("FAILED: Could not find target 'bork'")
        return

    print(f"SUCCESS: Found target '{target_char.name}' (ID: {target_char.id})")

    # 2. Engine Resolution
    print("Running GameEngine.resolve_action...")
    engine = GameEngine()

    actor_data = player.dict()
    target_data = target_char.dict()

    # Mock dice roll for consistency if needed, but random is fine for this test
    result = engine.resolve_action(actor_data, "attack", target_data)

    print("Engine Result:", result)

    if not result['success']:
        print("FAILED: Engine resolution failed.")
        return

    # 3. State Update Logic
    print("Updating State...")
    new_hp = result['target_hp_remaining']

    target_updated = False
    for n in state.npcs:
        if n.id == target_char.id:
            n.hp_current = new_hp
            target_updated = True
            break

    if not target_updated:
        print("FAILED: Could not update NPC in state.")
        return

    print(f"SUCCESS: Bork's HP updated from 20 to {state.npcs[0].hp_current}")
    print("Verification Complete.")

if __name__ == "__main__":
    test_attack_npc_logic()
