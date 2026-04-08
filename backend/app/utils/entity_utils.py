import secrets
secure_random = secrets.SystemRandom()

class EntityUtils:
    @staticmethod
    def find_char_by_name(game_state, search_term: str, target_id: str = None):
        all_entities = game_state.entities.values() if game_state and hasattr(game_state, 'entities') else []

        if target_id:
            for c in all_entities:
                if c.id == target_id:
                    return c

        if not search_term:
            return None

        term = search_term.lower()

        # Priority 1: Exact ID or target_id Match
        for c in all_entities:
            if term == c.id.lower():
                return c
            if hasattr(c, 'target_id') and c.target_id and term == c.target_id.lower():
                return c

        # Priority 2: Exact Name Match
        for c in all_entities:
            if term == c.name.lower():
                return c

        # Priority 3: Prefix Name Match
        for c in all_entities:
            if c.name.lower().startswith(term):
                return c

        # Priority 4: Race / Type / Role Exact Match
        for c in all_entities:
            # Player
            if hasattr(c, 'race') and c.race and term == c.race.lower(): return c
            if hasattr(c, 'role') and c.role and term == c.role.lower(): return c

            # Enemy
            if hasattr(c, 'type') and c.type and term == c.type.lower(): return c

            # NPC
            if hasattr(c, 'data') and c.data:
                if 'race' in c.data and term == str(c.data['race']).lower(): return c
                if 'type' in c.data and term == str(c.data['type']).lower(): return c
                if 'role' in c.data and term == str(c.data['role']).lower(): return c

        # Priority 5: Substring Name Match (Fallback)
        for c in all_entities:
            if term in c.name.lower():
                return c

        return None

    @staticmethod
    def get_display_name(entity):
        """Returns name or unidentified_name based on state"""
        if hasattr(entity, 'identified') and not entity.identified:
            if entity.unidentified_name:
                return entity.unidentified_name
            return "Unknown Entity"
        return entity.name

    @staticmethod
    def get_display_description(entity):
        """Returns description or unidentified_description based on state"""
        if hasattr(entity, 'identified') and not entity.identified:
            if entity.unidentified_description:
                return entity.unidentified_description
            if entity.unidentified_name: 
                return f"A mysterious {entity.unidentified_name}."

        if hasattr(entity, 'description') and entity.description:
            return entity.description

        return f"You see {entity.name}."

    @staticmethod
    def get_bark(entity, trigger: str) -> str | None:
        """
        Retrieves a bark for the given entity based on a trigger 
        (e.g., 'aggro', 'death', 'idle', 'flee').
        """
        barks = getattr(entity, 'barks', {})
        if not barks:
            # Fallback to data.voice.barks or data.barks depending on schema version
            data = getattr(entity, 'data', {})
            if data:
                barks = data.get('voice', {}).get('barks', {}) or data.get('barks', {})
                
        if not barks or not isinstance(barks, dict):
            return None

        trigger_barks = barks.get(trigger, [])
        if not trigger_barks:
            return None

        return secure_random.choice(trigger_barks)

    @staticmethod
    def _safe_int(v, d):
        try: return int(v)
        except Exception: return d

    @staticmethod
    def derive_character_stats(sheet_data: dict) -> dict:
        """
        Calculates HP, AC, Speed, Initiative from 5e JSON sheet data.
        """
        hp_current = EntityUtils._safe_int(sheet_data.get('hpCurrent'), 10)
        hp_max = EntityUtils._safe_int(sheet_data.get('hpMax'), 10)
        speed = EntityUtils._safe_int(sheet_data.get('speed'), 30)

        dex_score = EntityUtils._safe_int(sheet_data.get('stats', {}).get('Dexterity'), 10)
        dex_mod = (dex_score - 10) // 2

        base_ac = 10
        shield_bonus = 0
        equipped_armor = None

        for item in sheet_data.get('equipment', []):
            if isinstance(item, dict) and item.get('type') == 'Armor':
                item_data = item.get('data', {})
                if isinstance(item_data, dict) and item_data.get('type') == 'Shield':
                    ac_info_shield = item_data.get('armor_class', {})
                    shield_bonus = ac_info_shield.get('base', 2) if isinstance(ac_info_shield, dict) else 2
                else:
                    equipped_armor = item
                    
        if isinstance(equipped_armor, dict):
            ac_info = equipped_armor.get('data', {}).get('armor_class', {})
            if isinstance(ac_info, dict):
                base_ac = int(ac_info.get('base', 10))
                if ac_info.get('dex_bonus'):
                    max_bonus = ac_info.get('max_bonus')
                    if max_bonus is not None and int(dex_mod) > int(max_bonus):
                        base_ac += int(max_bonus)
                    else:
                        base_ac += int(dex_mod)
                else:
                    base_ac += int(dex_mod)
            else:
                base_ac += int(dex_mod)
            
        derived_ac = int(base_ac) + int(shield_bonus)

        explicit_ac = sheet_data.get('ac')
        if explicit_ac is not None:
             ac = EntityUtils._safe_int(explicit_ac, derived_ac)
        else:
             ac = derived_ac

        return {
            "hp_current": hp_current,
            "hp_max": hp_max,
            "speed": speed,
            "ac": ac,
            "initiative_mod": dex_mod
        }

    @staticmethod
    def _run_engine_resolution(engine, actor, action, target, params=None):
        """Wrapper for running the game engine synchronously."""
        return engine.resolve_action(actor, action, target, params)

    @staticmethod
    def splice_players_into_party(game_state, players_to_sync, user_id):
        if getattr(game_state, 'entities', None) is None:
            game_state.entities = {}

        current_sync_ids = {p.id for p in players_to_sync}

        # Remove entities owned by user that are no longer in players_to_sync
        for p_id in list(game_state.party_ids):
            p = game_state.entities.get(p_id)
            if p and getattr(p, 'user_id', None) == str(user_id) and p.id not in current_sync_ids:
                del game_state.entities[p_id]
                game_state.party_ids.remove(p_id)

        # Extract available spawn positions
        available_spawns = []
        if getattr(game_state, 'location', None) and getattr(game_state.location, 'party_locations', None):
            for loc in game_state.location.party_locations:
                pos = loc.get('position')
                if pos:
                    available_spawns.append((pos.get('q', 0), pos.get('r', 0), pos.get('s', 0)))

        # Track occupied positions to avoid stacking
        occupied_positions = set()
        for p in game_state.party:
            occupied_positions.add((p.position.q, p.position.r, p.position.s))

        for player in players_to_sync:
            needs_spawn = False
            
            if player.id in game_state.party_ids:
                existing = game_state.entities[player.id]
                player.position = getattr(existing, 'position', player.position)
                player.initiative = getattr(existing, 'initiative', player.initiative)
                player.entity_type = "player"
                game_state.entities[player.id] = player
                
                # If they are stacked at (0,0,0) and that's not a designated spawn, try respawning
                pos_tuple = (player.position.q, player.position.r, player.position.s)
                if pos_tuple == (0, 0, 0) and pos_tuple not in available_spawns:
                    needs_spawn = True
                    occupied_positions.discard(pos_tuple)
            else:
                needs_spawn = True
                player.entity_type = "player"
                game_state.entities[player.id] = player
                game_state.party_ids.append(player.id)

            if needs_spawn:
                # Find an empty spawn point if possible
                for spawn in available_spawns:
                    if spawn not in occupied_positions:
                         player.position.q = spawn[0]
                         player.position.r = spawn[1]
                         player.position.s = spawn[2]
                         occupied_positions.add(spawn)
                         break
