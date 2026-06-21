import json


_KEY_RENAMES = {"walkable_hexes": "walkable_cells"}


def _rename_key(k):
    return _KEY_RENAMES.get(k, k)


def _walk(node):
    """
    Recursively map cube coordinate dicts {q, r, s?} -> {x, y}, dropping s, and rename
    the {walkable_hexes -> walkable_cells} key. Idempotent.

    Strict guard: only migrate a dict that has 'q' and 'r' but NOT 'x', so a dict that
    already carries 'x' (already migrated, or a mixed/half-migrated record) is never
    clobbered by the legacy 'q' value.
    """
    if isinstance(node, dict):
        if "q" in node and "r" in node and "x" not in node:
            migrated = {"x": node["q"], "y": node["r"]}
            for k, v in node.items():
                if k not in ("q", "r", "s"):
                    migrated[_rename_key(k)] = _walk(v)
            return migrated
        return {_rename_key(k): _walk(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_walk(v) for v in node]
    return node


def migrate_json_text(raw):
    """
    Transform a JSON text blob's coordinate dicts from {q,r,s} to {x,y}.
    Returns (new_json_text, changed?). Safe on NULL/empty/garbage input (returns it
    unchanged). Idempotent: a second pass reports changed=False.
    """
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
