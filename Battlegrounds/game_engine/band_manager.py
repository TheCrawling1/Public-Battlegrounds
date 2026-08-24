"""
Band Manager - Minion generation, band management, and power calculations
"""

import logging

logger = logging.getLogger(__name__)

from minions import generate_minion, generate_minion_multi_tier, generate_unique_minion_id


class BandManager:
    """Handles all minion generation, band operations, and power calculations"""

    @staticmethod
    def generate_minion(tier, pool_modifiers=None):
        """Generate a random minion based on tier and optional pool modifiers"""
        return generate_minion(tier, pool_modifiers)

    @staticmethod
    def generate_minion_for_run(run, tier=None):
        """
        Generate a minion for a specific run, using its current zone's pool modifiers.
        If tier is not specified, uses multi-tier generation based on ring level.

        Args:
            run: The run object
            tier: Optional specific tier (if None, uses multi-tier based on ring)

        Returns:
            Generated minion instance
        """
        from game_engine.zone_controller import ZoneController
        pool_modifiers = ZoneController.get_zone_pool_modifiers(run)

        if tier is not None:
            # Specific tier requested
            return generate_minion(tier, pool_modifiers)
        else:
            # Use multi-tier pool based on ring level
            return generate_minion_multi_tier(run.current_ring, pool_modifiers)

    @staticmethod
    def generate_npc_band_from_predefined_team(team_definition, tier, difficulty='normal'):
        """
        Generate an NPC band from a predefined team definition

        Args:
            team_definition: List of minion names or dicts with custom stats
                            e.g., ['Scout', 'Iron Wall'] or [{'name': 'Cat', 'health': 10, 'attack': 10}]
            tier: Tier to use for minion generation
            difficulty: Difficulty multiplier to apply

        Returns:
            List of minion instances
        """
        from minions import create_minion_instance, get_minion_by_name

        # Apply difficulty modifiers to stats and gold
        stat_multipliers = {
            'normal': 1.0,
            'hard': 1.2,
            'elite': 1.5,
            'champion': 1.8,
            'nightmare': 2.0
        }

        stat_mult = stat_multipliers.get(difficulty, 1.0)

        # Calculate spoofed gold for rich keyword (scales with tier and difficulty)
        # Base 10 gold + 5 per tier, multiplied by difficulty
        spoofed_gold = int((10 + tier * 5) * stat_mult)

        npc_band = []
        for i, minion_def in enumerate(team_definition):
            # Handle both string names and dicts with custom stats
            if isinstance(minion_def, str):
                # Simple minion name - get template and create instance
                minion_template = get_minion_by_name(minion_def)
                if not minion_template:
                    continue  # Skip if minion not found

                minion = create_minion_instance(minion_template, tier=tier, assign_band_id=False)

            elif isinstance(minion_def, dict):
                # Custom stats provided - get base template and override stats
                minion_name = minion_def.get('name')
                minion_template = get_minion_by_name(minion_name)
                if not minion_template:
                    continue  # Skip if minion not found

                minion = create_minion_instance(minion_template, tier=tier, assign_band_id=False)

                # Apply custom stat overrides
                if 'health' in minion_def:
                    minion['health'] = minion_def['health']
                if 'attack' in minion_def:
                    minion['attack'] = minion_def['attack']
                if 'golden' in minion_def:
                    minion['golden'] = minion_def['golden']
            else:
                continue  # Skip invalid definitions

            # Apply difficulty scaling
            if stat_mult != 1.0:
                minion['health'] = int(minion['health'] * stat_mult)
                minion['attack'] = int(minion['attack'] * stat_mult)

            # Add spoofed gold for rich keyword support
            minion['spoofed_gold'] = spoofed_gold

            minion['position'] = i
            npc_band.append(minion)

        return npc_band

    @staticmethod
    def generate_boss_band(boss_id, run=None, persistent_damage=None):
        """
        Generate a boss band for The Great Hunt encounters

        Args:
            boss_id: String identifier for the boss (e.g., 'dire_pack', 'congregation')
            run: Optional run object for context (used for greater_possessed random minions)
            persistent_damage: Optional dict mapping minion names to damage taken
                              e.g., {'Alpha Direwolf': 3} means Alpha has taken 3 damage

        Returns:
            List of minion instances for the boss encounter
        """
        from minions import get_boss_minion, get_minion_by_name, create_minion_instance
        from zone_teams import get_boss_team
        import random

        team_definition = get_boss_team(boss_id)
        if team_definition is None:
            logger.debug(f"[BOSS] Unknown boss_id: {boss_id}")
            return []

        persistent_damage = persistent_damage or {}
        npc_band = []

        # Special handling for greater_possessed - 5 random minions each possessed
        if boss_id == 'greater_possessed':
            # Generate 5 random tier-appropriate minions, each possessed by a Possessed
            tier = run.current_ring if run else 2
            from minions import filter_minions_by_modifiers
            from game_engine.zone_controller import ZoneController

            pool_modifiers = ZoneController.get_zone_pool_modifiers(run) if run else None
            available_minions = filter_minions_by_modifiers(tier, pool_modifiers)
            if not available_minions:
                available_minions = filter_minions_by_modifiers(tier, None)

            # Possessed's death_toll effect - grants random ally the same death_toll
            possessed_death_toll = {
                'type': 'grant_effect_to_minion',
                'target': 'random_ally',
                'exclude_name': 'Possessed',
                'effect_type': 'death_toll_effect',
                'effect_data': {
                    'type': 'summon_minion',
                    'minion_name': 'Possessed',
                    'health': 1,
                    'attack': 6
                }
            }

            for i in range(5):
                minion_template = random.choice(available_minions)
                minion = create_minion_instance(minion_template, tier=tier, assign_band_id=False)
                minion['position'] = i

                # Add death_toll keyword and effect (possessed by a Possessed)
                if 'death_toll' not in minion.get('keywords', []):
                    minion['keywords'] = minion.get('keywords', []) + ['death_toll']
                minion['death_toll_effect'] = possessed_death_toll.copy()

                npc_band.append(minion)

        # Add boss minions from the team definition
        position_offset = len(npc_band)
        for i, minion_name in enumerate(team_definition):
            # First check boss minions, then fall back to regular minions
            minion_template = get_boss_minion(minion_name)
            if not minion_template:
                minion_template = get_minion_by_name(minion_name, include_bosses=False)

            if not minion_template:
                logger.debug(f"[BOSS] Minion not found: {minion_name}")
                continue

            # Create instance (boss minions are tier 0 / special)
            minion = create_minion_instance(minion_template, tier=0, assign_band_id=False)

            # Apply persistent damage if any
            damage_key = minion_name
            if damage_key in persistent_damage:
                damage = persistent_damage[damage_key]
                minion['health'] = max(1, minion['health'] - damage)
                logger.debug(f"[BOSS] Applied {damage} persistent damage to {minion_name}, health now {minion['health']}")

            minion['position'] = position_offset + i
            npc_band.append(minion)

        return npc_band

    @staticmethod
    def generate_npc_band_for_run_scaled(run, tier, band_size, difficulty='normal', use_predefined_teams=True):
        """Generate an NPC band with explicit tier and size for ring-based scaling

        Args:
            run: The current run
            tier: Minion tier to use
            band_size: Number of minions to generate
            difficulty: Difficulty level for stat scaling
            use_predefined_teams: If False, always generate random minions (useful for duels)
        """
        from game_engine.zone_controller import ZoneController
        import zone_teams
        import random

        pool_modifiers = ZoneController.get_zone_pool_modifiers(run)

        # Try to get a predefined team for this zone and tier (unless disabled)
        if use_predefined_teams:
            current_zone = run.current_zone
            predefined_team = zone_teams.get_random_team(tier, current_zone)

            if predefined_team:
                # Use predefined team
                return BandManager.generate_npc_band_from_predefined_team(predefined_team, tier, difficulty)

        # Fall back to random generation if no predefined team exists
        # Apply difficulty modifiers to stats
        stat_multipliers = {
            'normal': 1.0,
            'hard': 1.2,
            'elite': 1.5,
            'champion': 1.8,
            'nightmare': 2.0
        }

        stat_mult = stat_multipliers.get(difficulty, 1.0)

        # Calculate spoofed gold for rich keyword (scales with tier and difficulty)
        # Base 10 gold + 5 per tier, multiplied by difficulty
        spoofed_gold = int((10 + tier * 5) * stat_mult)

        npc_band = []
        for i in range(band_size):
            # Enemy minions don't get band IDs (assign_band_id=False in generate_minion)
            from minions import create_minion_instance, filter_minions_by_modifiers

            # Get available minions for this tier
            available_minions = filter_minions_by_modifiers(tier, pool_modifiers)
            if not available_minions:
                available_minions = filter_minions_by_modifiers(tier, None)
            if not available_minions:
                available_minions = filter_minions_by_modifiers(1, None)

            minion_template = random.choice(available_minions)
            minion = create_minion_instance(minion_template, tier=tier, assign_band_id=False)  # Pass tier, no band ID for enemies

            # Apply difficulty scaling
            if stat_mult != 1.0:
                minion['health'] = int(minion['health'] * stat_mult)
                minion['attack'] = int(minion['attack'] * stat_mult)

            # Add spoofed gold for rich keyword support
            minion['spoofed_gold'] = spoofed_gold

            minion['position'] = i
            npc_band.append(minion)

        return npc_band

    @staticmethod
    def generate_npc_band(ring_level, difficulty, pool_modifiers=None):
        """Generate an NPC band for battle using appropriate tiers and optional pool modifiers"""
        # Map difficulties to minion tiers
        difficulty_tiers = {
            'npc_battle': 1,  # Basic fights use tier 1
            'strong_npc': 2,  # Stronger fights use tier 2
            'hard_npc': 2,  # Hard fights also use tier 2
            'boss_npc': 3,  # Boss fights use tier 3
            'elite_npc': 3,  # Elite fights use tier 3
            'champion_npc': 3,  # Champion fights use tier 3
            'nightmare_npc': 3  # Nightmare fights use tier 3
        }

        # Determine band size based on difficulty
        band_size_map = {
            'npc_battle': 2,  # Small bands for basic fights
            'strong_npc': 3,  # Medium bands
            'hard_npc': 3,  # Medium bands
            'boss_npc': 4,  # Larger bands for bosses
            'elite_npc': 4,  # Larger bands
            'champion_npc': 5,  # Even larger bands
            'nightmare_npc': 6  # Maximum bands for nightmare
        }

        # Map difficulties to stat multipliers for gold calculation
        difficulty_multipliers = {
            'npc_battle': 1.0,
            'strong_npc': 1.2,
            'hard_npc': 1.2,
            'boss_npc': 1.5,
            'elite_npc': 1.5,
            'champion_npc': 1.8,
            'nightmare_npc': 2.0
        }

        minion_tier = difficulty_tiers.get(difficulty, 1)
        band_size = band_size_map.get(difficulty, 3)
        difficulty_mult = difficulty_multipliers.get(difficulty, 1.0)

        # Cap band size based on ring level to prevent overwhelming early fights
        max_size = min(2 + ring_level, band_size)

        # Calculate spoofed gold for rich keyword (scales with tier and difficulty)
        # Base 10 gold + 5 per tier, multiplied by difficulty
        spoofed_gold = int((10 + minion_tier * 5) * difficulty_mult)

        npc_band = []
        for i in range(max_size):
            # Enemy minions don't get band IDs (assign_band_id=False in generate_minion)
            from minions import create_minion_instance, filter_minions_by_modifiers
            import random

            # Get available minions for this tier
            available_minions = filter_minions_by_modifiers(minion_tier, pool_modifiers)
            if not available_minions:
                available_minions = filter_minions_by_modifiers(minion_tier, None)
            if not available_minions:
                available_minions = filter_minions_by_modifiers(1, None)

            minion_template = random.choice(available_minions)
            minion = create_minion_instance(minion_template, tier=minion_tier, assign_band_id=False)  # Pass tier, no band ID for enemies

            # Add spoofed gold for rich keyword support
            minion['spoofed_gold'] = spoofed_gold

            minion['position'] = i
            npc_band.append(minion)

        return npc_band

    @staticmethod
    def generate_npc_band_for_run(run, difficulty):
        """Generate an NPC band for a specific run, using its current zone's pool modifiers"""
        from game_engine.zone_controller import ZoneController
        pool_modifiers = ZoneController.get_zone_pool_modifiers(run)
        return BandManager.generate_npc_band(run.current_ring, difficulty, pool_modifiers)

    @staticmethod
    def calculate_band_power(band):
        """Calculate total power level of a band"""
        total_power = 0
        for minion in band:
            base_power = minion['health'] + minion['attack'] * 2

            # Add keyword power modifiers
            keyword_bonus = 0
            keywords = minion.get('keywords', [])
            for keyword in keywords:
                if keyword.lower() == 'poke':
                    keyword_bonus += 5  # Poke adds defensive value

            # Golden minions have higher power value
            golden_bonus = 0
            if minion.get('golden', False):
                golden_bonus = int(base_power * 0.5)  # 50% bonus for golden minions

            total_power += base_power + keyword_bonus + golden_bonus
        return total_power

    @staticmethod
    def swap_minion_positions(run, index1, index2):
        """Swap positions of two minions in the band"""
        band = run.get_band()

        if 0 <= index1 < len(band) and 0 <= index2 < len(band) and index1 != index2:
            # Swap the minions
            band[index1], band[index2] = band[index2], band[index1]

            # Update their position values
            band[index1]['position'] = index1
            band[index2]['position'] = index2

            run.set_band(band)
            return {
                'success': True,
                'message': f"Swapped {band[index1]['name']} and {band[index2]['name']} positions",
                'band': band
            }

        return {'error': 'Invalid swap indices'}

    @staticmethod
    def abandon_minion(run, index):
        """Remove a minion from the band"""
        band = run.get_band()

        if 0 <= index < len(band):
            abandoned_minion = band.pop(index)

            # Update positions of remaining minions
            for i, minion in enumerate(band):
                minion['position'] = i

            run.set_band(band)
            return {
                'success': True,
                'message': f"Abandoned {abandoned_minion['name']}",
                'band': band
            }

        return {'error': 'Invalid minion index'}

    @staticmethod
    def validate_band(band):
        """Validate that a band is properly formed"""
        if not isinstance(band, list):
            return False, "Band must be a list"

        if len(band) > 6:  # MAX_BAND_SIZE
            return False, "Band cannot have more than 6 minions"

        for i, minion in enumerate(band):
            # Check required fields
            required_fields = ['name', 'health', 'attack', 'keywords', 'golden', 'position', 'tier']
            for field in required_fields:
                if field not in minion:
                    return False, f"Minion {i} missing required field: {field}"

            # Validate field types
            if not isinstance(minion['name'], str):
                return False, f"Minion {i}: Name must be a string"

            if not isinstance(minion['health'], int) or minion['health'] < 0:
                return False, f"Minion {i}: Health must be a non-negative integer"

            if not isinstance(minion['attack'], int) or minion['attack'] < 0:
                return False, f"Minion {i}: Attack must be a non-negative integer"

            if not isinstance(minion['keywords'], list):
                return False, f"Minion {i}: Keywords must be a list"

            if not isinstance(minion['golden'], bool):
                return False, f"Minion {i}: Golden must be a boolean"

            if not isinstance(minion['position'], int) or minion['position'] != i:
                return False, f"Minion {i}: Position must match array index"

            if not isinstance(minion['tier'], int) or minion['tier'] < 1:
                return False, f"Minion {i}: Tier must be a positive integer"

        return True, "Valid band"

    @staticmethod
    def normalize_band_positions(band):
        """Ensure all minions in a band have correct position values"""
        for i, minion in enumerate(band):
            minion['position'] = i
        return band

    @staticmethod
    def add_minion_to_band(band, minion):
        """Add a minion to a band with proper position assignment and band ID"""
        if len(band) >= 6:  # MAX_BAND_SIZE
            return False, "Band is full"

        minion = minion.copy()  # Don't modify original
        minion['position'] = len(band)

        # Ensure required fields exist
        if 'keywords' not in minion:
            minion['keywords'] = []
        if 'golden' not in minion:
            minion['golden'] = False
        if 'tier' not in minion:
            minion['tier'] = 1  # Default to tier 1 if missing

        # Ensure minion has a band_id (assign one if missing)
        if 'band_id' not in minion:
            minion['band_id'] = generate_unique_minion_id()

        band.append(minion)
        return True, "Minion added successfully"

    @staticmethod
    def remove_minion_from_band(band, index):
        """Remove a minion from a band and update positions"""
        if 0 <= index < len(band):
            removed_minion = band.pop(index)

            # Update positions of remaining minions
            for i, minion in enumerate(band):
                minion['position'] = i

            return True, removed_minion

        return False, None

    @staticmethod
    def get_band_statistics(band):
        """Get statistical information about a band"""
        if not band:
            return {
                'size': 0,
                'total_health': 0,
                'total_attack': 0,
                'average_health': 0,
                'average_attack': 0,
                'power': 0,
                'golden_count': 0,
                'keyword_count': 0,
                'types': {}
            }

        total_health = sum(minion['health'] for minion in band)
        total_attack = sum(minion['attack'] for minion in band)
        golden_count = sum(1 for minion in band if minion.get('golden', False))

        # Count keywords
        all_keywords = []
        for minion in band:
            all_keywords.extend(minion.get('keywords', []))

        # Count types
        types = {}
        for minion in band:
            minion_type = minion.get('type', 'None')
            types[minion_type] = types.get(minion_type, 0) + 1

        return {
            'size': len(band),
            'total_health': total_health,
            'total_attack': total_attack,
            'average_health': round(total_health / len(band), 1),
            'average_attack': round(total_attack / len(band), 1),
            'power': BandManager.calculate_band_power(band),
            'golden_count': golden_count,
            'keyword_count': len(all_keywords),
            'unique_keywords': len(set(all_keywords)),
            'types': types
        }

    @staticmethod
    def find_strongest_minion(band):
        """Find the minion with the highest individual power"""
        if not band:
            return None

        strongest = None
        highest_power = -1

        for minion in band:
            # Calculate individual minion power
            base_power = minion['health'] + minion['attack'] * 2

            keyword_bonus = 0
            keywords = minion.get('keywords', [])
            for keyword in keywords:
                if keyword.lower() == 'poke':
                    keyword_bonus += 5

            golden_bonus = 0
            if minion.get('golden', False):
                golden_bonus = int(base_power * 0.5)

            total_power = base_power + keyword_bonus + golden_bonus

            if total_power > highest_power:
                highest_power = total_power
                strongest = minion

        return strongest

    @staticmethod
    def find_weakest_minion(band):
        """Find the minion with the lowest individual power"""
        if not band:
            return None

        weakest = None
        lowest_power = float('inf')

        for minion in band:
            # Calculate individual minion power (same logic as find_strongest)
            base_power = minion['health'] + minion['attack'] * 2

            keyword_bonus = 0
            keywords = minion.get('keywords', [])
            for keyword in keywords:
                if keyword.lower() == 'poke':
                    keyword_bonus += 5

            golden_bonus = 0
            if minion.get('golden', False):
                golden_bonus = int(base_power * 0.5)

            total_power = base_power + keyword_bonus + golden_bonus

            if total_power < lowest_power:
                lowest_power = total_power
                weakest = minion

        return weakest

    @staticmethod
    def sort_band_by_power(band, descending=True):
        """Sort band by individual minion power"""
        def get_minion_power(minion):
            base_power = minion['health'] + minion['attack'] * 2

            keyword_bonus = 0
            keywords = minion.get('keywords', [])
            for keyword in keywords:
                if keyword.lower() == 'poke':
                    keyword_bonus += 5

            golden_bonus = 0
            if minion.get('golden', False):
                golden_bonus = int(base_power * 0.5)

            return base_power + keyword_bonus + golden_bonus

        sorted_band = sorted(band, key=get_minion_power, reverse=descending)

        # Update positions after sorting
        for i, minion in enumerate(sorted_band):
            minion['position'] = i

        return sorted_band

    @staticmethod
    def find_band_minion_by_id(run, band_id):
        """Find a minion in the band by its unique band_id"""
        if not band_id:
            return None

        band = run.get_band()
        for minion in band:
            if minion.get('band_id') == band_id:
                return minion
        return None

    @staticmethod
    def get_all_band_ids(run):
        """Get all band IDs from the current band"""
        band = run.get_band()
        return [minion.get('band_id') for minion in band if minion.get('band_id')]

    @staticmethod
    def ensure_all_band_minions_have_ids(run):
        """Ensure all minions in the band have band IDs (for migrating old saves)"""
        band = run.get_band()
        band_changed = False

        for minion in band:
            if 'band_id' not in minion or not minion['band_id']:
                minion['band_id'] = generate_unique_minion_id()
                band_changed = True

            # Also ensure tier exists for old minions
            if 'tier' not in minion:
                minion['tier'] = 1  # Default to tier 1
                band_changed = True

        if band_changed:
            run.set_band(band)

        return band_changed