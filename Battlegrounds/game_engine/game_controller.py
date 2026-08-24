"""
Game Controller - Main game flow coordination and state management
"""

import random
import copy
from config import RING_EVENTS, DEFAULT_RING_PATTERN, ZONE_RING_EVENTS, RING_SIZE, MAX_COMBAT_ROUNDS, RESET_HEALTH_AFTER_COMBAT, \
    MAX_BAND_SIZE, EVENT_SCALING
from keywords import apply_combat_keywords, has_keyword, validate_keywords, select_combat_target
from minions import generate_minion, generate_minion_multi_tier, create_golden_minion, can_combine_minions, validate_minion


class GameController:
    """Main game flow coordination and high-level state management"""

    @staticmethod
    def get_ring_events(ring_level, zone=None):
        """Get the event sequence for a given ring, optionally zone-specific

        Args:
            ring_level: The ring number
            zone: Optional zone key for zone-specific events

        Returns:
            List of events for this ring
        """
        # Check for zone-specific ring events first
        if zone and zone in ZONE_RING_EVENTS:
            zone_rings = ZONE_RING_EVENTS[zone]
            if ring_level in zone_rings:
                return zone_rings[ring_level]

        # Fall back to default ring events
        if ring_level in RING_EVENTS:
            return RING_EVENTS[ring_level]
        else:
            # For rings beyond defined ones, use the default pattern
            return DEFAULT_RING_PATTERN.copy()

    @staticmethod
    def get_current_event(run):
        """Get the current event type based on ring and position"""
        zone = getattr(run, 'current_zone', None)
        events = GameController.get_ring_events(run.current_ring, zone=zone)
        event = events[run.ring_position % len(events)]

        # Check if it's a split event (list of events)
        if isinstance(event, list):
            return 'split_event'
        else:
            return event

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
                elif keyword.lower() == 'guard':
                    keyword_bonus += 3  # Guard adds tactical value

            # Golden minions have higher power value
            golden_bonus = 0
            if minion.get('golden', False):
                golden_bonus = int(base_power * 0.5)  # 50% bonus for golden minions

            total_power += base_power + keyword_bonus + golden_bonus
        return total_power

    @staticmethod
    def process_event(run, event_type):
        """Process an event and return the result (fallback for immediate processing with multi-tier scaling)"""
        band = run.get_band()
        resources = run.get_resources()

        result = {
            'event_type': event_type,
            'message': '',
            'band_changes': [],
            'resource_changes': {}
        }

        # Handle minion events with multi-tier pool
        if event_type == 'minion_event':
            new_minion = generate_minion_multi_tier(run.current_ring)
            band.append(new_minion)
            result['message'] = f"Found {new_minion['name']}!"
            result['band_changes'] = [f"Added {new_minion['name']}"]

        # Handle scaling buff events
        elif event_type.startswith('buff_event'):
            if band:
                # Get scaling configuration
                scaling_config = EVENT_SCALING.get(event_type, EVENT_SCALING['buff_event'])
                ring_multiplier = run.current_ring * scaling_config.get('base_multiplier', 1)

                target = random.choice(band)
                buff_type = random.choice(['health', 'attack'])

                if buff_type == 'health':
                    buff_amount = int(3 + (ring_multiplier - 1) * 2)
                else:
                    buff_amount = int(2 + (ring_multiplier - 1) * 1.5)

                target[buff_type] += buff_amount
                result['message'] = f"{target['name']} gained +{buff_amount} {buff_type}!"
                result['band_changes'] = [f"{target['name']}: +{buff_amount} {buff_type}"]

        # Handle shop events with multi-tier pool
        elif event_type == 'shop_event':
            scaling_config = EVENT_SCALING.get('shop_event')
            base_cost = scaling_config.get('base_cost', 5)
            cost_per_ring = scaling_config.get('cost_per_ring', 3)
            cost = base_cost + (cost_per_ring * run.current_ring)

            if resources['gold'] >= cost:
                # Can afford - buy a minion from multi-tier pool
                new_minion = generate_minion_multi_tier(run.current_ring)
                band.append(new_minion)
                resources['gold'] -= cost
                result['message'] = f"Bought {new_minion['name']} for {cost} gold!"
                result['band_changes'] = [f"Bought {new_minion['name']}"]
                result['resource_changes'] = {'gold': f"-{cost}"}
            else:
                # Can't afford - gain some gold instead
                gold_gain = 3 + run.current_ring
                resources['gold'] += gold_gain
                result['message'] = f"Not enough gold for shop! Found {gold_gain} coins instead."
                result['resource_changes'] = {'gold': f"+{gold_gain}"}

        # Handle scaling combat events
        elif event_type.startswith('combat_event'):
            scaling_config = EVENT_SCALING.get(event_type, EVENT_SCALING['combat_event'])

            # Calculate enemy band size
            band_size_base = scaling_config.get('band_size_base', 2)
            band_size_per_ring = scaling_config.get('band_size_per_ring', 0.5)
            enemy_band_size = int(band_size_base + (run.current_ring - 1) * band_size_per_ring)
            enemy_band_size = min(enemy_band_size, 6)

            # Generate enemy band at current tier
            tier = min(run.current_ring, 3)
            difficulty = scaling_config.get('difficulty', 'normal')

            npc_band = GameController._generate_npc_band_scaled(tier, enemy_band_size, difficulty)
            battle_result = GameController.auto_battle(band, npc_band)

            if battle_result['winner'] == 'player':
                # Scale reward with ring and difficulty
                reward_multiplier = {'normal': 1, 'hard': 1.5, 'elite': 2, 'champion': 2.5, 'nightmare': 3}
                mult = reward_multiplier.get(difficulty, 1)
                reward_gold = int((3 + run.current_ring * 2) * mult)
                resources['gold'] += reward_gold
                result['message'] = f"Victory! Earned {reward_gold} gold."
                result['resource_changes'] = {'gold': f"+{reward_gold}"}
            else:
                # Player loses - damage to band
                for minion in band:
                    minion['health'] = max(1, minion['health'] - 2)
                result['message'] = "Defeat! Your minions are wounded."
                result['band_changes'] = ["All minions took damage"]

        run.set_band(band)
        run.set_resources(resources)
        return result

    @staticmethod
    def _generate_minion(tier):
        """Generate a random minion based on tier"""
        return generate_minion(tier)

    @staticmethod
    def _generate_npc_band_scaled(tier, band_size, difficulty):
        """Generate an NPC band with explicit tier and size for fallback processing"""
        stat_multipliers = {
            'normal': 1.0,
            'hard': 1.2,
            'elite': 1.5,
            'champion': 1.8,
            'nightmare': 2.0
        }

        stat_mult = stat_multipliers.get(difficulty, 1.0)

        npc_band = []
        for i in range(band_size):
            minion = GameController._generate_minion(tier)

            # Apply difficulty scaling
            if stat_mult != 1.0:
                minion['health'] = int(minion['health'] * stat_mult)
                minion['attack'] = int(minion['attack'] * stat_mult)

            minion['position'] = i
            npc_band.append(minion)

        return npc_band

    @staticmethod
    def _generate_npc_band(ring_level, difficulty):
        """Generate an NPC band for battle using appropriate tiers (legacy method)"""
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

        minion_tier = difficulty_tiers.get(difficulty, 1)
        band_size = band_size_map.get(difficulty, 3)

        # Cap band size based on ring level to prevent overwhelming early fights
        max_size = min(2 + ring_level, band_size)

        npc_band = []
        for i in range(max_size):
            minion = GameController._generate_minion(minion_tier)
            minion['position'] = i
            npc_band.append(minion)

        return npc_band

    @staticmethod
    def auto_battle(player_band, enemy_band):
        """Simulate auto-battle between two bands using guard-aware targeting"""
        p_band = copy.deepcopy(player_band)
        e_band = copy.deepcopy(enemy_band)

        battle_log = []
        round_count = 0

        while p_band and e_band and round_count < MAX_COMBAT_ROUNDS:
            round_count += 1

            # Get alive minions for targeting
            alive_p_band = [m for m in p_band if m['health'] > 0]
            alive_e_band = [m for m in e_band if m['health'] > 0]

            # Check if battle is over
            if not alive_p_band or not alive_e_band:
                break

            # Player attacks first (if they have units)
            if alive_p_band and alive_e_band:
                attacker = alive_p_band[0]
                defender = select_combat_target(attacker, alive_e_band)

                damage_to_defender = attacker['attack']
                base_counter_damage = defender['attack']

                # Apply keyword effects
                actual_counter_damage, keyword_logs = apply_combat_keywords(attacker, defender, base_counter_damage)

                defender['health'] -= damage_to_defender
                attacker['health'] -= actual_counter_damage

                battle_log.append(f"{attacker['name']} attacks {defender['name']} for {damage_to_defender} damage")
                if actual_counter_damage > 0:
                    battle_log.append(f"{defender['name']} counter-attacks for {actual_counter_damage} damage")

                # Add keyword logs
                battle_log.extend(keyword_logs)

                if defender['health'] <= 0:
                    battle_log.append(f"{defender['name']} is defeated!")
                if attacker['health'] <= 0:
                    battle_log.append(f"{attacker['name']} is defeated!")

            # Update alive lists after player attack
            alive_p_band = [m for m in p_band if m['health'] > 0]
            alive_e_band = [m for m in e_band if m['health'] > 0]

            # Enemy attacks back (if they still have units and didn't already attack)
            if alive_e_band and alive_p_band:
                attacker = alive_e_band[0]
                defender = select_combat_target(attacker, alive_p_band)

                damage_to_defender = attacker['attack']
                base_counter_damage = defender['attack']

                # Apply keyword effects
                actual_counter_damage, keyword_logs = apply_combat_keywords(attacker, defender, base_counter_damage)

                defender['health'] -= damage_to_defender
                attacker['health'] -= actual_counter_damage

                battle_log.append(f"{attacker['name']} attacks {defender['name']} for {damage_to_defender} damage")
                if actual_counter_damage > 0:
                    battle_log.append(f"{defender['name']} counter-attacks for {actual_counter_damage} damage")

                # Add keyword logs
                battle_log.extend(keyword_logs)

                if defender['health'] <= 0:
                    battle_log.append(f"{defender['name']} is defeated!")
                if attacker['health'] <= 0:
                    battle_log.append(f"{attacker['name']} is defeated!")

            # Remove dead minions from bands for next round
            p_band = [m for m in p_band if m['health'] > 0]
            e_band = [m for m in e_band if m['health'] > 0]

        # Determine winner
        if p_band and not e_band:
            winner = 'player'
        elif e_band and not p_band:
            winner = 'enemy'
        else:
            winner = 'draw'

        return {
            'winner': winner,
            'rounds': round_count,
            'battle_log': battle_log,
            'surviving_player': p_band,
            'surviving_enemy': e_band
        }