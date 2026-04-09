"""Tests for the condition system: apply, remove, effects, lifecycle."""
import pytest
from app.models import Condition, Entity, Player, Enemy, NPC
from app.services.condition_service import (
    apply_condition, remove_condition, has_condition,
    should_skip_turn, has_speed_zero,
    get_attack_modifiers, get_save_modifiers,
    tick_conditions, get_active_effects,
)


class TestApplyRemove:
    def test_apply_condition(self, player_factory):
        p = player_factory()
        result = apply_condition(p, "Poisoned", duration=3)
        assert result is True
        assert has_condition(p, "Poisoned")
        assert len(p.conditions) == 1

    def test_no_duplicate_stacking(self, player_factory):
        p = player_factory()
        apply_condition(p, "Poisoned", duration=3)
        result = apply_condition(p, "Poisoned", duration=2)
        assert result is False  # not newly applied
        assert len(p.conditions) == 1

    def test_refresh_longer_duration(self, player_factory):
        p = player_factory()
        apply_condition(p, "Poisoned", duration=2)
        apply_condition(p, "Poisoned", duration=5)
        assert p.conditions[0].duration == 5

    def test_remove_condition(self, player_factory):
        p = player_factory()
        apply_condition(p, "Poisoned")
        result = remove_condition(p, "Poisoned")
        assert result is True
        assert not has_condition(p, "Poisoned")

    def test_remove_nonexistent(self, player_factory):
        p = player_factory()
        result = remove_condition(p, "Stunned")
        assert result is False

    def test_multiple_conditions(self, player_factory):
        p = player_factory()
        apply_condition(p, "Poisoned")
        apply_condition(p, "Blinded")
        assert len(p.conditions) == 2
        remove_condition(p, "Poisoned")
        assert len(p.conditions) == 1
        assert has_condition(p, "Blinded")


class TestSkipTurn:
    def test_stunned_skips(self, player_factory):
        p = player_factory()
        apply_condition(p, "Stunned", duration=1)
        assert should_skip_turn(p) is True

    def test_paralyzed_skips(self, player_factory):
        p = player_factory()
        apply_condition(p, "Paralyzed", duration=1)
        assert should_skip_turn(p) is True

    def test_incapacitated_skips(self, player_factory):
        p = player_factory()
        apply_condition(p, "Incapacitated", duration=1)
        assert should_skip_turn(p) is True

    def test_poisoned_does_not_skip(self, player_factory):
        p = player_factory()
        apply_condition(p, "Poisoned", duration=1)
        assert should_skip_turn(p) is False

    def test_no_conditions_does_not_skip(self, player_factory):
        p = player_factory()
        assert should_skip_turn(p) is False


class TestSpeedZero:
    def test_grappled_stops_movement(self, player_factory):
        p = player_factory()
        apply_condition(p, "Grappled")
        assert has_speed_zero(p) is True

    def test_restrained_stops_movement(self, player_factory):
        p = player_factory()
        apply_condition(p, "Restrained")
        assert has_speed_zero(p) is True

    def test_poisoned_allows_movement(self, player_factory):
        p = player_factory()
        apply_condition(p, "Poisoned")
        assert has_speed_zero(p) is False


class TestAttackModifiers:
    def test_blinded_attacker_has_disadvantage(self, player_factory, enemy_factory):
        p = player_factory()
        e = enemy_factory()
        apply_condition(p, "Blinded")
        mods = get_attack_modifiers(p, e)
        assert mods["disadvantage"] is True

    def test_blinded_target_grants_advantage(self, player_factory, enemy_factory):
        p = player_factory()
        e = enemy_factory()
        apply_condition(e, "Blinded")
        mods = get_attack_modifiers(p, e)
        assert mods["advantage"] is True

    def test_invisible_attacker_has_advantage(self, player_factory, enemy_factory):
        p = player_factory()
        e = enemy_factory()
        apply_condition(p, "Invisible")
        mods = get_attack_modifiers(p, e)
        assert mods["advantage"] is True

    def test_advantage_and_disadvantage_cancel(self, player_factory, enemy_factory):
        p = player_factory()
        e = enemy_factory()
        apply_condition(p, "Blinded")    # disadvantage on attacks
        apply_condition(e, "Stunned")    # advantage against target
        mods = get_attack_modifiers(p, e)
        # Both cancel out
        assert mods["advantage"] is False
        assert mods["disadvantage"] is False

    def test_prone_melee_advantage(self, player_factory, enemy_factory):
        p = player_factory()
        e = enemy_factory()
        apply_condition(e, "Prone")
        melee_mods = get_attack_modifiers(p, e, is_melee=True)
        ranged_mods = get_attack_modifiers(p, e, is_melee=False)
        assert melee_mods["advantage"] is True
        assert ranged_mods["disadvantage"] is True

    def test_charmed_blocks_attack_on_source(self, player_factory, enemy_factory):
        p = player_factory()
        e = enemy_factory()
        apply_condition(p, "Charmed", source_id=e.id)
        mods = get_attack_modifiers(p, e)
        assert mods["blocked"] is True


class TestSaveModifiers:
    def test_paralyzed_auto_fails_str_dex(self, player_factory):
        p = player_factory()
        apply_condition(p, "Paralyzed")
        str_mods = get_save_modifiers(p, "strength")
        dex_mods = get_save_modifiers(p, "dexterity")
        wis_mods = get_save_modifiers(p, "wisdom")
        assert str_mods["auto_fail"] is True
        assert dex_mods["auto_fail"] is True
        assert wis_mods["auto_fail"] is False

    def test_restrained_dex_disadvantage(self, player_factory):
        p = player_factory()
        apply_condition(p, "Restrained")
        dex_mods = get_save_modifiers(p, "dexterity")
        str_mods = get_save_modifiers(p, "strength")
        assert dex_mods["disadvantage"] is True
        assert str_mods["disadvantage"] is False


class TestTickLifecycle:
    def test_tick_decrements_duration(self, player_factory):
        p = player_factory()
        apply_condition(p, "Poisoned", duration=3)
        expired = tick_conditions(p)
        assert expired == []
        assert p.conditions[0].duration == 2

    def test_tick_expires_at_zero(self, player_factory):
        p = player_factory()
        apply_condition(p, "Stunned", duration=1)
        expired = tick_conditions(p)
        assert expired == ["Stunned"]
        assert len(p.conditions) == 0

    def test_permanent_never_expires(self, player_factory):
        p = player_factory()
        apply_condition(p, "Blinded", duration=-1)
        expired = tick_conditions(p)
        assert expired == []
        assert len(p.conditions) == 1
        assert p.conditions[0].duration == -1

    def test_multiple_conditions_tick_independently(self, player_factory):
        p = player_factory()
        apply_condition(p, "Poisoned", duration=2)
        apply_condition(p, "Stunned", duration=1)
        apply_condition(p, "Blinded", duration=-1)

        expired = tick_conditions(p)
        assert "Stunned" in expired
        assert "Poisoned" not in expired
        assert len(p.conditions) == 2  # Poisoned (1 remaining) + Blinded (permanent)


class TestBackwardCompat:
    def test_old_status_effects_migrated(self):
        """Old status_effects: List[str] should migrate to conditions."""
        p = Player(
            id="test", name="Hero", role="Fighter", is_ai=False,
            hp_current=10, hp_max=10,
            position={"q": 0, "r": 0, "s": 0},
            status_effects=["Poisoned", "Blinded"],
        )
        assert len(p.conditions) == 2
        assert p.conditions[0].name == "Poisoned"
        assert p.conditions[1].name == "Blinded"

    def test_conditions_from_data_dict(self):
        """Conditions stored in data dict should promote to model field."""
        e = Enemy(
            id="test", name="Goblin", type="Goblin", is_ai=True,
            hp_current=7, hp_max=7,
            position={"q": 0, "r": 0, "s": 0},
            data={"conditions": [{"name": "Stunned", "duration": 2}]},
        )
        assert len(e.conditions) == 1
        assert e.conditions[0].name == "Stunned"
        assert e.conditions[0].duration == 2


class TestConcentration:
    """Tests for concentration tracking."""

    def test_start_concentration(self, player_factory, enemy_factory):
        from app.services.condition_service import start_concentration, apply_condition
        p = player_factory(name="Wizard")
        e = enemy_factory(name="Goblin")
        apply_condition(e, "Paralyzed", duration=10, source_id=p.id)
        broken = start_concentration(p, "Hold Person", target_id=e.id)
        assert broken is None
        assert p.concentrating_on == "Hold Person"
        assert p.concentration_target_id == e.id

    def test_new_concentration_breaks_old(self, player_factory, enemy_factory, game_state_factory):
        from app.services.condition_service import start_concentration, apply_condition
        p = player_factory(name="Wizard")
        e1 = enemy_factory(name="Goblin1")
        e2 = enemy_factory(name="Goblin2")
        gs = game_state_factory(players=[p], enemies=[e1, e2])

        # First concentration
        apply_condition(e1, "Paralyzed", duration=10, source_id=p.id)
        start_concentration(p, "Hold Person", target_id=e1.id, game_state=gs)

        # Second concentration should break the first
        apply_condition(e2, "Frightened", duration=10, source_id=p.id)
        broken = start_concentration(p, "Fear", target_id=e2.id, game_state=gs)

        assert broken == "Hold Person"
        assert p.concentrating_on == "Fear"
        # First target should have lost their condition
        assert not any(c.name == "Paralyzed" for c in e1.conditions)

    def test_break_concentration_removes_condition(self, player_factory, enemy_factory, game_state_factory):
        from app.services.condition_service import start_concentration, break_concentration, apply_condition
        p = player_factory(name="Wizard")
        e = enemy_factory(name="Goblin")
        gs = game_state_factory(players=[p], enemies=[e])

        apply_condition(e, "Restrained", duration=-1, source_id=p.id)
        start_concentration(p, "Entangle", target_id=e.id)

        broken = break_concentration(p, gs)
        assert broken == "Entangle"
        assert p.concentrating_on is None
        assert not any(c.name == "Restrained" for c in e.conditions)

    def test_concentration_save_easy(self, player_factory):
        """Low damage should be easy to save (DC 10)."""
        from app.services.condition_service import check_concentration_save
        p = player_factory(name="Wizard")
        p.concentrating_on = "Hold Person"

        # Run many times — with CON mod and DC 10, should succeed sometimes
        results = [check_concentration_save(p, 5) for _ in range(20)]
        assert any(results), "Should pass DC 10 at least once in 20 tries"

    def test_concentration_save_hard(self, player_factory):
        """Massive damage should be hard to save (DC = damage/2)."""
        from app.services.condition_service import check_concentration_save
        p = player_factory(name="Wizard")
        p.concentrating_on = "Hold Person"

        # DC = 50/2 = 25, impossible with d20 + any reasonable mod
        results = [check_concentration_save(p, 50) for _ in range(10)]
        assert not any(results), "Should never pass DC 25"

    def test_not_concentrating_always_passes(self, player_factory):
        from app.services.condition_service import check_concentration_save
        p = player_factory()
        assert check_concentration_save(p, 100) is True
