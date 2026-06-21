"""Tests for the {q,r,s} -> {x,y} JSON coordinate migration."""
import json
from db.migrate_coords import migrate_json_text, _walk


def test_basic_coord_migration():
    raw = json.dumps({"position": {"q": 3, "r": -2, "s": -1}})
    new_raw, changed = migrate_json_text(raw)
    assert changed
    assert json.loads(new_raw) == {"position": {"x": 3, "y": -2}}


def test_nested_structures():
    raw = json.dumps({
        "walkable_cells": [{"q": 0, "r": 0, "s": 0}, {"q": 1, "r": 2, "s": -3}],
        "party_locations": [{"position": {"q": 5, "r": 5, "s": -10}}],
        "interactables": [{"id": "door", "position": {"q": -1, "r": 0, "s": 1}}],
    })
    new = json.loads(migrate_json_text(raw)[0])
    assert new["walkable_cells"] == [{"x": 0, "y": 0}, {"x": 1, "y": 2}]
    assert new["party_locations"][0]["position"] == {"x": 5, "y": 5}
    assert new["interactables"][0] == {"id": "door", "position": {"x": -1, "y": 0}}


def test_idempotent():
    raw = json.dumps({"position": {"q": 1, "r": 2, "s": -3}})
    once, changed1 = migrate_json_text(raw)
    twice, changed2 = migrate_json_text(once)
    assert changed1 is True
    assert changed2 is False
    assert once == twice


def test_already_square_unchanged():
    raw = json.dumps({"position": {"x": 1, "y": 2}})
    new_raw, changed = migrate_json_text(raw)
    assert changed is False
    assert new_raw == raw


def test_null_and_garbage_safe():
    assert migrate_json_text(None) == (None, False)
    assert migrate_json_text("") == ("", False)
    assert migrate_json_text("not json {{{") == ("not json {{{", False)


def test_qr_without_s_migrates():
    raw = json.dumps({"position": {"q": 4, "r": 5}})
    new = json.loads(migrate_json_text(raw)[0])
    assert new["position"] == {"x": 4, "y": 5}


def test_mixed_dict_preserves_real_x():
    # A dict already carrying x must NOT be clobbered by a stray q (strict guard).
    node = {"x": 9, "y": 8, "z": 7, "q": 1, "r": 2, "s": -3}
    result = _walk(node)
    assert result["x"] == 9 and result["y"] == 8


def test_walkable_hexes_key_renamed_to_cells():
    # The field rename rides along with the coordinate transform so a persisted
    # Location with the legacy key (and legacy coords) doesn't silently lose its map.
    raw = json.dumps({"location": {"walkable_hexes": [{"q": 0, "r": 0, "s": 0}, {"q": 1, "r": 0, "s": -1}]}})
    new = json.loads(migrate_json_text(raw)[0])
    assert "walkable_hexes" not in new["location"]
    assert new["location"]["walkable_cells"] == [{"x": 0, "y": 0}, {"x": 1, "y": 0}]
