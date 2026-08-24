"""
Event System - Event creation, configuration, and processing with ring-based scaling
"""

import logging

logger = logging.getLogger(__name__)

from config import MAX_BAND_SIZE, EVENT_SCALING
from minions import create_golden_minion, can_combine_minions
from lucide_icons import generate_lucide_svg, format_minion_stats
from hero_definitions import get_scaled_effect_value
from game_engine.events.event_helpers import (
    resolve_formula, resolve_tooltip, evaluate_condition, build_tooltip_context
)


def get_effective_max_band_size(run):
    """Get the effective max band size including extra slots from events"""
    event_state = run.get_event_state()
    extra_slots = event_state.get('extra_band_slots', 0)
    return MAX_BAND_SIZE + extra_slots


class EventSystem:
    """Handles all event creation and configuration logic with ring-based scaling"""

    @staticmethod
    def create_event_selection(run, event_type):
        """Create a selection for an event instead of immediately processing it"""

        # FIRST: Check if this is a template-based event
        from game_engine.events import get_event
        template_event = get_event(event_type)
        if template_event:
            return EventSystem._create_template_based_event(run, template_event)

        # Handle general_event - random event from pool, becomes buff after visit
        if event_type == 'general_event':
            return EventSystem._create_general_event_selection(run)

        # LEGACY: Fall back to old hardcoded event logic
        if event_type == 'split_event':
            # Get the actual split event options
            from game_engine.game_controller import GameController
            from game_engine.sub_ring_controller import SubRingController

            if SubRingController.is_in_sub_ring(run):
                # This shouldn't happen - sub-rings don't have split events
                return {
                    'event_type': 'split_event',
                    'message': 'Split events not available in sub-rings',
                    'band_changes': [],
                    'resource_changes': {}
                }

            zone = getattr(run, 'current_zone', None)
            events = GameController.get_ring_events(run.current_ring, zone=zone)
            event_options = events[run.ring_position % len(events)]
            return EventSystem._create_split_event_selection(run, event_options)

        # Handle minion events with multi-tier pool
        elif event_type == 'minion_event':
            return EventSystem._create_minion_selection(run)

        # Handle scaling buff events
        elif event_type.startswith('buff_event'):
            return EventSystem._create_scaling_buff_selection(run, event_type)

        # Handle shop events with multi-tier pool
        elif event_type == 'shop_event':
            return EventSystem._create_shop_selection(run)

        # Handle scaling combat events
        elif event_type.startswith('combat_event'):
            return EventSystem._create_scaling_combat_selection(run, event_type)

        elif event_type == 'statue':
            # Statue events - Combine minions (repeating + leaveable)
            return EventSystem._create_combine_minions_selection(run, event_type)

        elif event_type == 'artifact':
            # Placeholder for artifact events
            return {
                'event_type': event_type,
                'message': 'You find a mysterious artifact... (Coming Soon!)',
                'band_changes': [],
                'resource_changes': {}
            }

        else:
            # Default fallback
            return {
                'event_type': event_type,
                'message': f'Event {event_type} is not yet implemented',
                'band_changes': [],
                'resource_changes': {}
            }

    @staticmethod
    def _create_minion_selection(run, count=None, tier_pool=None, rarity_filter=None,
                                 title=None, message=None, allow_skip=True, minion_pool=None,
                                 tribe_filter=None):
        """Create a minion selection event using multi-tier pool based on ring level

        Args:
            minion_pool: Optional list of specific minion names to offer (e.g. ['Quartermaster', 'Warlord'])
            tribe_filter: Optional tribe name to filter minions (e.g. 'Human', 'Beast')
        """
        current_band = run.get_band()

        # Get scaling configuration if parameters not provided
        scaling_config = EVENT_SCALING.get('minion_event')
        num_choices = count if count is not None else scaling_config.get('choices', 3)

        # Generate minions to choose from
        from game_engine.band_manager import BandManager
        offered_minions = []

        if minion_pool:
            # Use specific minions from the pool
            from minions import get_minion_by_name, create_minion_instance
            tier = run.current_ring
            for minion_name in minion_pool:
                template = get_minion_by_name(minion_name)
                if template:
                    minion = create_minion_instance(template, tier=tier, assign_band_id=True)
                    offered_minions.append(minion)
        else:
            # Generate random minions using multi-tier pool
            max_attempts = num_choices * 10  # Prevent infinite loop
            attempts = 0
            while len(offered_minions) < num_choices and attempts < max_attempts:
                minion = BandManager.generate_minion_for_run(run)  # No tier specified = multi-tier
                # Apply tribe filter if specified
                if tribe_filter and minion.get('type') != tribe_filter:
                    attempts += 1
                    continue
                offered_minions.append(minion)
                attempts += 1

        title = title or f"{generate_lucide_svg('gift', width=24, height=24)} Free Minion"

        effective_max = get_effective_max_band_size(run)
        if len(current_band) >= effective_max:
            # Band is full - need replacement selection
            options = []
            for i, minion in enumerate(offered_minions):
                options.append({
                    'type': 'replacement',
                    'render_as': 'replacement',
                    'data': minion,
                    'cost': 0,
                    'message': f"Choose {minion['name']} ({format_minion_stats(minion['health'], minion['attack'])})",
                    'id': f'new_minion_{i}'
                })

            # Always add skip option when band is full - player shouldn't be forced to replace
            options.append({
                'type': 'skip',
                'message': 'Leave without taking',
                'id': 'skip'
            })

            selection = {
                'event_type': 'minion_event',
                'title': title,
                'message': 'Your band is full! Choose a minion to replace, or skip:',
                'offered_minions': offered_minions,
                'current_band': current_band,
                'options': options,
                'min_selections': 0,  # Can always skip when band is full
                'max_selections': 1,
                'repeating': False,
                'leaveable': True  # Always leaveable when band is full
            }
        else:
            # Normal minion selection
            options = []
            for i, minion in enumerate(offered_minions):
                options.append({
                    'type': 'minion',
                    'render_as': 'minion',
                    'data': minion,
                    'cost': 0,
                    'id': f'minion_{i}'
                })

            # Add skip option if allowed
            if allow_skip:
                options.append({
                    'type': 'skip',
                    'message': 'Skip this event',
                    'id': 'skip'
                })

            selection = {
                'event_type': 'minion_event',
                'title': title,
                'message': 'Choose a minion for your band:',
                'options': options,
                'min_selections': 0 if allow_skip else 1,  # Must choose if can't skip
                'max_selections': 1,  # Can only choose 1 minion (or skip)
                'repeating': False,
                'leaveable': allow_skip
            }

        # Debug logging for full band case
        if len(current_band) >= effective_max:
            logger.debug(f"DEBUG _create_minion_selection: Band full, creating replacement selection")
            logger.debug(f"  Options count: {len(selection.get('options', []))}")
            logger.debug(f"  Option IDs: {[opt.get('id') for opt in selection.get('options', [])]}")
            logger.debug(f"  Event type: {selection.get('event_type')}")

        run.set_pending_selection(selection)
        return {
            'event_type': 'minion_event',
            'message': 'Selection available!',
            'selection_created': True,
            'band_changes': [],
            'resource_changes': {}
        }

    @staticmethod
    def _create_scaling_buff_selection(run, event_type, ring_value=None, return_to_event=None):
        """Create a buff selection event that scales with ring"""
        band = run.get_band()

        if not band:
            # No minions to buff - auto-skip
            return {
                'event_type': event_type,
                'message': 'No minions to buff!',
                'band_changes': [],
                'resource_changes': {}
            }

        # Check if this is a ring buff
        is_ring_buff = (event_type == 'buff_event_ring' or ring_value is not None)

        if is_ring_buff:
            # Special handling for Ring buff
            if ring_value == 'tier' or ring_value is None:
                ring_value = run.current_ring

            buff_options = [{
                'name': f'Ring {ring_value}',
                'description': f'Grant Ring {ring_value} keyword',
                'type': 'ring',
                'ring_value': ring_value
            }]
        else:
            # Normal buff options
            # Get scaling configuration
            scaling_config = EVENT_SCALING.get(event_type, EVENT_SCALING['buff_event'])

            # Scale buff values with ring (+1 per ring above 1)
            ring_bonus = run.current_ring - 1

            health_opts = scaling_config.get('health_options', [3, 0, 1])
            attack_opts = scaling_config.get('attack_options', [0, 2, 1])

            # Generate buff options
            buff_options = []

            # Health-only option
            if health_opts[0] > 0:
                health_amount = health_opts[0] + ring_bonus
                buff_options.append({
                    'name': f'+{health_amount} Health',
                    'description': f'Gain {health_amount} health',
                    'type': 'health',
                    'amount': health_amount
                })

            # Attack-only option
            if attack_opts[1] > 0:
                attack_amount = attack_opts[1] + ring_bonus
                buff_options.append({
                    'name': f'+{attack_amount} Attack',
                    'description': f'Gain {attack_amount} attack',
                    'type': 'attack',
                    'amount': attack_amount
                })

            # Both stats option
            health_both = health_opts[2] + ring_bonus
            attack_both = attack_opts[2] + ring_bonus
            buff_options.append({
                'name': f'+{health_both}/+{attack_both}',
                'description': f'Gain {health_both} health and {attack_both} attack',
                'type': 'both',
                'health': health_both,
                'attack': attack_both
            })

        # Create selection options for buff types
        options = []
        for i, buff in enumerate(buff_options):
            options.append({
                'type': 'choose_buff',
                'render_as': 'choose_buff',
                'buff_data': buff,
                'message': buff['name'],  # Just show the name, not redundant description
                'id': f'buff_{i}'
            })

        # Add skip option (unless this is a ring buff which can't be skipped)
        allow_skip = not is_ring_buff
        if allow_skip:
            skip_option = {
                'type': 'skip',
                'message': 'Skip this blessing',
                'id': 'skip'
            }
            if return_to_event:
                skip_option['return_to_event'] = return_to_event
            options.append(skip_option)

        # Determine event title (clean, no SVG icons)
        if is_ring_buff:
            title = 'Bell Tower Blessing'
        else:
            title = 'Blessing'

        selection = {
            'event_type': event_type,
            'title': title,
            'current_band': band,
            'options': options,
            'min_selections': 0 if allow_skip else 1,  # Must choose if can't skip
            'max_selections': 1,  # Can only choose 1 buff type (or skip)
            'repeating': False,
            'leaveable': allow_skip,
            'return_to_event': return_to_event  # Event to return to after action
        }

        run.set_pending_selection(selection)
        return {
            'event_type': event_type,
            'message': 'Blessing available!',
            'selection_created': True,
            'band_changes': [],
            'resource_changes': {}
        }

    @staticmethod
    def _create_shop_selection(run, title=None, return_to_event=None, num_offers=None):
        """Create a shop selection event using multi-tier pool with tier-based costs"""
        current_band = run.get_band()
        resources = run.get_resources()

        # Get scaling configuration
        scaling_config = EVENT_SCALING.get('shop_event')
        if num_offers is None:
            num_offers = scaling_config.get('num_offers', 4)

        # Use provided title or default
        title = title or "Tavern"

        options = []

        # Generate minions for sale using multi-tier pool
        from game_engine.band_manager import BandManager
        for i in range(num_offers):
            minion = BandManager.generate_minion_for_run(run)  # No tier specified = multi-tier

            # Cost is based on minion tier: Tier 1 = 3g, Tier 2 = 6g, Tier 3 = 9g, Tier 4 = 12g
            cost = minion.get('tier', 1) * 3

            # Apply hero cost reduction (e.g., Silas hero) - scales with power upgrades
            hero_effects = run.get_hero_effects()
            if 'cost_reduction' in hero_effects:
                base_reduction = hero_effects['cost_reduction']
                reduction = get_scaled_effect_value(hero_effects, 'cost_reduction', base_reduction)
                cost = max(0, cost - reduction)

            can_afford = resources['gold'] >= cost

            effective_max = get_effective_max_band_size(run)
            if len(current_band) >= effective_max:
                # Shop purchase with replacement needed
                purchase_type = 'shop_replacement'
                message = f"Buy {minion['name']} for {cost} gold (choose replacement)"
            else:
                # Normal shop purchase
                purchase_type = 'purchase'
                message = f"Buy {minion['name']} for {cost} gold"

            options.append({
                'type': purchase_type,
                'render_as': purchase_type,
                'data': minion,
                'cost': cost,
                'affordable': can_afford,
                'message': message,
                'id': f'buy_{i}'
            })

        # Skip option - include return_to_event if specified
        skip_option = {
            'type': 'skip',
            'message': 'Leave without buying',
            'id': 'skip'
        }
        if return_to_event:
            skip_option['return_to_event'] = return_to_event
        options.append(skip_option)

        effective_max_shop = get_effective_max_band_size(run)
        # If returning to an event after action, don't repeat (one action per visit)
        repeating = not return_to_event
        selection = {
            'event_type': 'shop_event',
            'title': title,
            'message': 'A quaint tavern for gathering hirelings.',
            'current_band': current_band,
            'band_full': len(current_band) >= effective_max_shop,
            'options': options,
            'min_selections': 0,  # Can skip/leave without buying
            'max_selections': 1 if return_to_event else 4,  # One action if returning, else can buy multiple
            'repeating': repeating,  # Shops are repeating unless returning to event
            'leaveable': True,   # Can leave by moving
            'return_to_event': return_to_event  # Event to return to after action
        }

        run.set_pending_selection(selection)
        return {
            'event_type': 'shop_event',
            'message': 'Shop opened!',
            'selection_created': True,
            'band_changes': [],
            'resource_changes': {}
        }

    @staticmethod
    def _create_scaling_combat_selection(run, event_type, on_victory_event=None, on_defeat_event=None,
                                         pool_filter=None, disable_gold_reward=False, title=None):
        """Create a combat event that scales with ring"""
        player_band = run.get_band()
        from game_engine.band_manager import BandManager

        # Get scaling configuration
        scaling_config = EVENT_SCALING.get(event_type, EVENT_SCALING['combat_event'])

        # Calculate enemy band size
        band_size_base = scaling_config.get('band_size_base', 2)
        band_size_per_ring = scaling_config.get('band_size_per_ring', 0.5)
        enemy_band_size = int(band_size_base + (run.current_ring - 1) * band_size_per_ring)
        enemy_band_size = min(enemy_band_size, 6)  # Cap at 6

        # Generate enemy band at tier based on ring + offset
        # Normal combat = ring tier, Hard combat = ring + 1 tier
        tier_offset = scaling_config.get('tier_offset', 0)
        tier = min(run.current_ring + tier_offset, 4)  # Cap at tier 4
        difficulty = scaling_config.get('difficulty', 'normal')

        # Generate NPC band with proper tier and size
        # TODO: Apply pool filter if specified (e.g., "Human" for bell tower guardians)
        # Currently pool_filter is not supported by generate_npc_band_for_run_scaled
        enemy_band = BandManager.generate_npc_band_for_run_scaled(
            run,
            tier=tier,
            band_size=enemy_band_size,
            difficulty=difficulty
        )

        # Determine who goes first (player if >= enemy minion count)
        player_goes_first = len(player_band) >= len(enemy_band)

        # Create combat state
        combat_state = {
            'player_band': [minion.copy() for minion in player_band],
            'enemy_band': enemy_band,
            'player_turn': player_goes_first,
            'current_player_unit': 0,  # Track which player unit attacks next
            'current_enemy_unit': 0,  # Track which enemy unit attacks next
            'combat_log': [],
            'round_number': 1,
            'combat_over': False,
            'winner': None
        }

        # Add initial log entry
        combat_state['combat_log'].append(f"Combat begins! {len(player_band)} vs {len(enemy_band)} minions")
        combat_state['combat_log'].append(f"{'Player' if player_goes_first else 'Enemy'} goes first!")

        # Determine event title
        if not title:
            title_map = {
                'combat_event': f"{generate_lucide_svg('swords', width=24, height=24)} Combat",
                'combat_event_hard': f"{generate_lucide_svg('skull', width=24, height=24)} Hard Combat"
            }
            title = title_map.get(event_type, f"{generate_lucide_svg('swords', width=24, height=24)} Combat")
            title = f'{title} (Ring {run.current_ring})'

        selection = {
            'event_type': 'combat',
            'combat_type': event_type,
            'title': title,
            'message': 'Choose how to proceed with combat:',
            'combat_state': combat_state,
            'options': [
                {
                    'type': 'combat_next',
                    'message': 'Next Attack',
                    'description': 'Execute one attack and see the result',
                    'id': 'next'
                },
                {
                    'type': 'combat_auto',
                    'message': 'Auto Combat',
                    'description': 'Run combat automatically to completion',
                    'id': 'auto'
                },
                {
                    'type': 'combat_end',
                    'message': 'End Combat',
                    'description': 'Skip to final combat result immediately',
                    'id': 'end'
                }
            ],
            'min_selections': 1,  # Must choose exactly 1 combat action
            'max_selections': 1,
            'repeating': False,  # Combat is not repeating
            'leaveable': False   # Cannot leave combat once started
        }

        # Add event chaining parameters if specified
        if on_victory_event:
            selection['on_victory_event'] = on_victory_event
        if on_defeat_event:
            selection['on_defeat_event'] = on_defeat_event
        if disable_gold_reward:
            selection['disable_gold_reward'] = disable_gold_reward

        run.set_pending_selection(selection)
        return {
            'event_type': event_type,
            'message': 'Combat initiated!',
            'selection_created': True,
            'band_changes': [],
            'resource_changes': {}
        }

    @staticmethod
    def _create_duel_combat_selection(run, champion_index, on_victory_event=None, on_defeat_event=None,
                                       disable_gold_reward=True, disable_health_loss=True, title=None):
        """Create a 1v1 duel combat using only the champion minion"""
        band = run.get_band()
        champion = band[champion_index]
        from game_engine.band_manager import BandManager

        # Generate 1 random enemy minion scaled to current ring tier
        tier = run.current_ring
        enemy_band = BandManager.generate_npc_band_for_run_scaled(
            run,
            tier=tier,
            band_size=1,
            difficulty='normal',
            use_predefined_teams=False  # Duels always use random minions
        )

        # Use only the champion as player band (make a copy)
        duel_player_band = [champion.copy()]

        # Determine who goes first (champion goes first in duels)
        player_goes_first = True

        # Create combat state
        combat_state = {
            'player_band': duel_player_band,
            'enemy_band': enemy_band,
            'player_turn': player_goes_first,
            'current_player_unit': 0,
            'current_enemy_unit': 0,
            'combat_log': [],
            'round_number': 1,
            'combat_over': False,
            'winner': None,
            'is_duel': True,  # Mark as duel combat
            'champion_index': champion_index  # Track which minion in the real band is fighting
        }

        # Add initial log entry
        enemy_name = enemy_band[0]['name'] if enemy_band else 'Unknown'
        combat_state['combat_log'].append(f"Duel begins! {champion['name']} vs {enemy_name}")
        combat_state['combat_log'].append("Champion strikes first!")

        # Determine title
        if not title:
            title = f"{generate_lucide_svg('swords', width=24, height=24)} Duel (Ring {run.current_ring})"

        selection = {
            'event_type': 'combat',
            'combat_type': 'duel',
            'title': title,
            'message': f'{champion["name"]} faces their opponent!',
            'combat_state': combat_state,
            'options': [
                {
                    'type': 'combat_next',
                    'message': 'Next Attack',
                    'description': 'Execute one attack and see the result',
                    'id': 'next'
                },
                {
                    'type': 'combat_auto',
                    'message': 'Auto Combat',
                    'description': 'Run combat automatically to completion',
                    'id': 'auto'
                },
                {
                    'type': 'combat_end',
                    'message': 'End Combat',
                    'description': 'Skip to combat results',
                    'id': 'end'
                }
            ],
            'min_selections': 1,
            'max_selections': 1,
            'repeating': False,
            'leaveable': False,
            'is_duel': True,
            'champion_index': champion_index
        }

        # Add event chaining parameters
        if on_victory_event:
            selection['on_victory_event'] = on_victory_event
        if on_defeat_event:
            selection['on_defeat_event'] = on_defeat_event
        if disable_gold_reward:
            selection['disable_gold_reward'] = disable_gold_reward
        if disable_health_loss:
            selection['disable_health_loss'] = disable_health_loss

        run.set_pending_selection(selection)
        return {
            'event_type': 'duel_combat',
            'message': 'Duel initiated!',
            'selection_created': True,
            'band_changes': [],
            'resource_changes': {}
        }

    @staticmethod
    def _create_boss_combat_selection(run, boss_id, on_victory_event=None, on_defeat_event=None,
                                       title=None, persistent_damage_key=None):
        """Create a boss combat for The Great Hunt encounters

        Args:
            run: The current run
            boss_id: String identifier for the boss (e.g., 'dire_pack', 'congregation')
            on_victory_event: Event to chain to on victory
            on_defeat_event: Event to chain to on defeat
            title: Optional custom title for the combat
            persistent_damage_key: Key in event_state to store/load boss damage
        """
        player_band = run.get_band()
        from game_engine.band_manager import BandManager

        # Load persistent damage from event_state if key provided
        persistent_damage = {}
        if persistent_damage_key:
            event_state = run.get_event_state()
            persistent_damage = event_state.get(persistent_damage_key, {})

        # Generate boss band
        enemy_band = BandManager.generate_boss_band(boss_id, run=run, persistent_damage=persistent_damage)

        if not enemy_band:
            return {
                'event_type': 'boss_combat',
                'message': f'Failed to generate boss band for {boss_id}',
                'band_changes': [],
                'resource_changes': {}
            }

        # Determine who goes first (player if >= enemy minion count)
        player_goes_first = len(player_band) >= len(enemy_band)

        # Create combat state
        combat_state = {
            'player_band': [minion.copy() for minion in player_band],
            'enemy_band': enemy_band,
            'player_turn': player_goes_first,
            'current_player_unit': 0,
            'current_enemy_unit': 0,
            'combat_log': [],
            'round_number': 1,
            'combat_over': False,
            'winner': None,
            'boss_combat': True,  # Flag for boss combat
            'boss_id': boss_id
        }

        # Add initial log entry
        combat_state['combat_log'].append(f"Boss Battle: {boss_id.replace('_', ' ').title()}!")
        combat_state['combat_log'].append(f"{len(player_band)} vs {len(enemy_band)} minions")
        combat_state['combat_log'].append(f"{'Player' if player_goes_first else 'Enemy'} goes first!")

        # Determine event title
        if not title:
            boss_names = {
                'dire_pack': 'The Dire Pack',
                'congregation': 'Congregation',
                'chained_beast': 'Chained Beast',
                'behemoth': 'Ancient Behemoth',
                'venomspawn': 'Venomspawn',
                'greater_possessed': 'Greater Possessed'
            }
            boss_display_name = boss_names.get(boss_id, boss_id.replace('_', ' ').title())
            title = f"{generate_lucide_svg('target', width=24, height=24)} {boss_display_name}"

        selection = {
            'event_type': 'boss_combat',
            'combat_type': 'boss_combat',
            'title': title,
            'message': 'Choose how to proceed with combat:',
            'combat_state': combat_state,
            'options': [
                {
                    'type': 'combat_next',
                    'message': 'Next Attack',
                    'description': 'Execute one attack and see the result',
                    'id': 'next'
                },
                {
                    'type': 'combat_auto',
                    'message': 'Auto Combat',
                    'description': 'Run combat automatically to completion',
                    'id': 'auto'
                },
                {
                    'type': 'combat_end',
                    'message': 'End Combat',
                    'description': 'Skip to final combat result immediately',
                    'id': 'end'
                }
            ],
            'min_selections': 1,
            'max_selections': 1,
            'repeating': False,
            'leaveable': False,
            'disable_gold_reward': True,  # Boss combats don't give gold
            'boss_id': boss_id,
            'persistent_damage_key': persistent_damage_key
        }

        # Add event chaining parameters if specified
        if on_victory_event:
            selection['on_victory_event'] = on_victory_event
        if on_defeat_event:
            selection['on_defeat_event'] = on_defeat_event

        run.set_pending_selection(selection)
        return {
            'event_type': 'boss_combat',
            'message': f'Boss battle initiated: {boss_id}!',
            'selection_created': True,
            'band_changes': [],
            'resource_changes': {}
        }

    @staticmethod
    def _create_bounty_target_selection(run, template_event, screen, parameters):
        """Create a bounty target selection for The Great Hunt

        Rolls N minions from current tier and lets player mark one type for gold bounty.
        When you kill that minion type in combat, you gain tier × 5 gold.
        """
        import random
        from minions import MINIONS

        tier = run.current_ring
        roll_count = parameters.get('roll_count', 4)

        # Get all minions from current tier
        tier_minions = MINIONS.get(tier, [])

        # Filter to non-boss minions only
        regular_minions = [m for m in tier_minions if m.get('rarity') != 'boss']

        if not regular_minions:
            return {
                'event_type': template_event['id'],
                'message': 'No minions available for bounty selection.',
                'band_changes': [],
                'resource_changes': {}
            }

        # Roll N random minions (can have duplicates, but we dedupe by name)
        rolled = random.sample(regular_minions, min(roll_count, len(regular_minions)))

        # Create options - one per unique minion type
        options = []
        seen_names = set()
        for minion in rolled:
            name = minion['name']
            if name in seen_names:
                continue
            seen_names.add(name)

            gold_reward = tier * 5
            options.append({
                'type': 'bounty_target',
                'id': f'bounty_{name.lower().replace(" ", "_")}',
                'message': name,
                'description': f'Mark this type. Gain {gold_reward} gold when you kill a {name}.',
                'minion_data': minion,
                'bounty_gold': gold_reward,
                'minion_type': minion.get('type', 'Unknown')
            })

        # Add skip option
        options.append({
            'type': 'skip',
            'id': 'skip_bounty',
            'message': 'Skip',
            'description': 'Leave without marking a bounty.'
        })

        selection = {
            'event_type': template_event['id'],
            'title': parameters.get('title', 'Choose Bounty Target'),
            'message': parameters.get('message', f'Mark one minion type. Earn {tier * 5} gold when you defeat that type.'),
            'options': options,
            'min_selections': 1,
            'max_selections': 1,
            'leaveable': True,
            'on_select': parameters.get('on_select'),
            'template_event': template_event,
            'current_screen_id': screen.get('id')
        }

        run.set_pending_selection(selection)
        return {
            'event_type': template_event['id'],
            'message': 'Bounty targets rolled!',
            'selection_created': True,
            'band_changes': [],
            'resource_changes': {}
        }

    @staticmethod
    def _create_combine_minions_selection(run, event_type):
        """Create a combine minions selection event for statues"""
        band = run.get_band()

        if len(band) < 2:
            # Not enough minions to combine
            return {
                'event_type': event_type,
                'message': 'You need at least 2 minions to use the statue!',
                'band_changes': [],
                'resource_changes': {}
            }

        # Find which minions can be combined (same name, both not golden)
        combinable_pairs = EventSystem._find_combinable_pairs(band)

        if not combinable_pairs:
            # No combinable minions
            return {
                'event_type': event_type,
                'message': 'The ancient statue hums, but you have no matching minions to combine.',
                'band_changes': [],
                'resource_changes': {}
            }

        # Create selection for combining minions
        options = []
        for i, minion in enumerate(band):
            # Only show minions that have a possible pair
            has_pair = any(pair[0] == i or pair[1] == i for pair in combinable_pairs)
            if has_pair:
                options.append({
                    'type': 'select_minion_for_combine',
                    'render_as': 'select_minion_for_combine',
                    'minion_index': i,
                    'minion_data': minion,
                    'message': f"Select {minion['name']} ({format_minion_stats(minion['health'], minion['attack'])})",
                    'id': f'combine_minion_{i}'
                })

        # Add skip option
        options.append({
            'type': 'skip',
            'message': 'Leave the statue alone',
            'id': 'skip'
        })

        selection = {
            'event_type': 'combine_minions',
            'title': '🗿 Ancient Statue - Combine Minions',
            'message': 'The statue glows with ancient power. Select two identical minions to combine them into a golden version!',
            'current_band': band,
            'combinable_pairs': combinable_pairs,
            'options': options,
            'min_selections': 0,  # Can skip
            'max_selections': 2,  # Must select exactly 2 minions to combine (or skip)
            'repeating': True,  # Statues are repeating - can combine multiple times
            'leaveable': True   # Can leave by moving
        }

        run.set_pending_selection(selection)
        return {
            'event_type': event_type,
            'message': 'The ancient statue offers to combine your minions!',
            'selection_created': True,
            'band_changes': [],
            'resource_changes': {}
        }

    @staticmethod
    def _create_split_event_selection(run, event_options):
        """Create a selection for split events"""
        if not isinstance(event_options, list) or len(event_options) < 2:
            # Fallback to first option if malformed
            return EventSystem.create_event_selection(run, event_options[0] if event_options else 'minion_event')

        # Create selection options for each event
        options = []
        for i, event_type in enumerate(event_options):
            options.append({
                'type': 'choose_event',
                'render_as': 'template_choice',
                'event_type': event_type,
                'message': EventSystem._get_event_display_name(event_type),
                'icon': EventSystem._get_event_icon(event_type),
                'description': EventSystem._get_event_description(event_type),
                'id': f'event_{i}'
            })

        selection = {
            'event_type': 'split_event',
            'title': 'Choose Your Path',
            'message': 'Select one of these opportunities:',
            'event_options': event_options,
            'options': options,
            'min_selections': 1,  # Must choose exactly 1 event
            'max_selections': 1,
            'repeating': False,
            'leaveable': True
        }

        run.set_pending_selection(selection)
        return {
            'event_type': 'split_event',
            'message': 'Choose your path!',
            'selection_created': True,
            'band_changes': [],
            'resource_changes': {}
        }

    @staticmethod
    def _create_branching_choice_selection(run):
        """Create a selection for branching choice events with proper sub-ring display"""
        from game_engine.game_controller import GameController

        zone = getattr(run, 'current_zone', None)
        events = GameController.get_ring_events(run.current_ring, zone=zone)
        choice_event = events[run.ring_position % len(events)]

        if not isinstance(choice_event, dict) or choice_event.get('type') != 'branching_choice':
            # Fallback to regular event if something went wrong
            return {
                'event_type': 'branching_choice',
                'message': 'Invalid branching choice configuration',
                'band_changes': [],
                'resource_changes': {}
            }

        # Get sub-ring templates for lookup
        sub_ring_templates = {
            'risky_path': {
                'name': 'Risky Path',
                'description': 'Face greater dangers for better rewards',
                'events': ['combat_event_hard', 'buff_event', 'combat_event_hard'],
                'exit_offset': 4,
                'icon': '⚡'
            }
        }

        # Create selection options from the branching choice
        options = []
        for i, choice in enumerate(choice_event.get('choices', [])):
            # For immediate events, show the event name
            if choice['type'] == 'immediate':
                display_name = f"{choice['icon']} {choice['name']}"
                description = choice['description']

            # For sub-ring events, show the sub-ring contents
            elif choice['type'] == 'sub_ring':
                template_name = choice['template']
                template = sub_ring_templates.get(template_name)

                if template:
                    # Use event names for display
                    EVENT_DISPLAY = {
                        'minion_event': {'name': 'Free Minion', 'icon': generate_lucide_svg('gift', width=24, height=24)},
                        'combat_event': {'name': 'Combat', 'icon': generate_lucide_svg('swords', width=24, height=24)},
                        'combat_event_hard': {'name': 'Hard Combat', 'icon': generate_lucide_svg('skull', width=24, height=24)},
                        'buff_event': {'name': 'Blessing', 'icon': generate_lucide_svg('sparkles', width=24, height=24)},
                        'statue': {'name': 'Statue', 'icon': generate_lucide_svg('ferris-wheel', width=24, height=24)},
                        'zone_portal': {'name': 'Portal', 'icon': generate_lucide_svg('signpost', width=24, height=24)}
                    }

                    event_names = []
                    for event in template['events']:
                        event_info = EVENT_DISPLAY.get(event, {'name': event.replace('_', ' ').title()})
                        event_names.append(event_info['name'])

                    event_list = " → ".join(event_names)
                    display_name = f"{choice['icon']} {choice['name']}"
                    description = f"{choice['description']}\nPath: {event_list}"
                else:
                    display_name = f"{choice['icon']} {choice['name']}"
                    description = choice['description']
            else:
                display_name = f"{choice['icon']} {choice['name']}"
                description = choice['description']

            options.append({
                'type': 'branching_choice_option',
                'choice_type': choice['type'],
                'choice_data': choice,
                'message': display_name,
                'description': description,
                'id': f'choice_{i}'
            })

        selection = {
            'event_type': 'branching_choice',
            'title': choice_event.get('title', 'Choose Your Path'),
            'message': choice_event.get('description', 'Select your approach:'),
            'choice_event': choice_event,
            'options': options,
            'min_selections': 1,  # Must choose exactly 1 path
            'max_selections': 1,
            'repeating': False,
            'leaveable': True
        }

        run.set_pending_selection(selection)
        return {
            'event_type': 'branching_choice',
            'message': 'Branching choice available!',
            'selection_created': True,
            'band_changes': [],
            'resource_changes': {}
        }

    @staticmethod
    def _get_event_display_name(event_type):
        """Get display name for events in split selections"""
        display_names = {
            # Minion events
            'minion_event': 'Free Minion',

            # Buff events
            'buff_event': 'Blessing',

            # Combat events
            'combat_event': 'Combat',
            'combat_event_hard': 'Hard Combat',

            # Shop events
            'shop_event': 'Minion Shop',

            # Static events
            'statue': 'Ancient Statue',
            'artifact': 'Artifact',
        }
        return display_names.get(event_type, event_type.replace('_', ' ').title())

    @staticmethod
    def _get_event_icon(event_type):
        """Get Lucide SVG icon for events in split selections"""
        event_icons = {
            'minion_event': generate_lucide_svg('gift', width=24, height=24),
            'buff_event': generate_lucide_svg('sparkles', width=24, height=24),
            'combat_event': generate_lucide_svg('swords', width=24, height=24),
            'combat_event_hard': generate_lucide_svg('skull', width=24, height=24),
            'shop_event': generate_lucide_svg('shopping-cart', width=24, height=24),
            'statue': generate_lucide_svg('ferris-wheel', width=24, height=24),
            'artifact': generate_lucide_svg('scroll', width=24, height=24),
        }
        return event_icons.get(event_type, generate_lucide_svg('help-circle', width=24, height=24))

    @staticmethod
    def _create_template_based_event(run, template_event):
        """
        Create an event selection from a template-based event definition

        This is the new template system that uses declarative event definitions
        from events.py. It processes the first screen of the event and creates
        the appropriate selection.
        """
        # Check for active boss redirect (Great Hunt mechanic)
        # If this event has check_active_boss flag and there's an active boss,
        # redirect directly to boss combat instead of showing choices
        if template_event.get('check_active_boss'):
            event_state = run.get_event_state()
            active_boss = event_state.get('active_boss')
            logger.debug(f"[GREAT_HUNT] check_active_boss: active_boss={active_boss}, boss_defeated_this_tier={event_state.get('boss_defeated_this_tier')}")
            if active_boss and active_boss.get('boss_id'):
                logger.debug(f"[GREAT_HUNT] Active boss detected: {active_boss['boss_id']}, redirecting to boss combat")
                # Get the boss encounter event and process it instead
                from game_engine.events import get_event
                boss_event = get_event('great_hunt_boss_encounter')
                if boss_event:
                    return EventSystem._create_template_based_event(run, boss_event)
            else:
                logger.debug(f"[GREAT_HUNT] No active boss, showing normal event choices")

        # Get the first screen to process
        screens = template_event.get('screens', [])
        if not screens:
            return {
                'event_type': template_event['id'],
                'message': 'Event has no screens defined',
                'band_changes': [],
                'resource_changes': {}
            }

        first_screen = screens[0]
        screen_type = first_screen.get('type')
        parameters = first_screen.get('parameters', {})

        # Delegate to the appropriate screen handler based on type
        if screen_type == 'select_minion':
            return EventSystem._create_minion_selection(
                run,
                count=parameters.get('count', 3),
                tier_pool=parameters.get('tier_pool', 'multi_tier'),
                rarity_filter=parameters.get('rarity_filter'),
                title=parameters.get('title', 'Choose a Minion'),
                message=parameters.get('message', 'Select a minion to add to your band'),
                allow_skip=parameters.get('allow_skip', True),
                minion_pool=parameters.get('minion_pool'),
                tribe_filter=parameters.get('tribe_filter')
            )

        elif screen_type == 'select_buff_type':
            buff_power = parameters.get('buff_power', 'normal')

            # Check if this is a ring buff
            if buff_power == 'ring':
                ring_value = parameters.get('ring_value', 'tier')
                return EventSystem._create_scaling_buff_selection(run, 'buff_event_ring', ring_value=ring_value)

            # All buff powers now use buff_event (scales with ring)
            return EventSystem._create_scaling_buff_selection(run, 'buff_event')

        elif screen_type == 'select_buff_target':
            # Direct minion selection for a predefined buff (skips buff type selection)
            # Uses the same format as choose_buff's second screen
            buff_type = parameters.get('buff_type') or parameters.get('buff_power')
            tribe_filter = parameters.get('tribe_filter')
            band = run.get_band()

            if not band:
                return {
                    'event_type': template_event['id'],
                    'message': 'No minions to buff!',
                    'band_changes': [],
                    'resource_changes': {}
                }

            # Filter band by tribe if specified
            if tribe_filter:
                filtered_band = [(i, m) for i, m in enumerate(band) if m.get('type') == tribe_filter]
                if not filtered_band:
                    return {
                        'event_type': template_event['id'],
                        'message': f'No {tribe_filter} minions to select!',
                        'band_changes': [],
                        'resource_changes': {}
                    }
            else:
                filtered_band = list(enumerate(band))

            # Create buff_data based on buff type (same format as blessing)
            if buff_type == 'ring':
                ring_value = parameters.get('ring_value', 'tier')
                if ring_value == 'tier':
                    ring_value = run.current_ring
                # Dynamic description based on ring value
                if ring_value == 1:
                    ring_desc = 'Start of combat: Trigger 1 random friendly death toll. Decrease this by 1.'
                else:
                    ring_desc = f'Start of combat: Trigger {ring_value} random friendly death tolls. Decrease this by 1 each trigger.'
                buff_data = {
                    'name': f'Ring {ring_value}',
                    'description': ring_desc,
                    'type': 'ring',
                    'ring_value': ring_value
                }
            elif buff_type and buff_type.startswith('keyword_'):
                keyword = buff_type.replace('keyword_', '')
                buff_data = {
                    'name': keyword.title(),
                    'description': f'Grant {keyword.title()} keyword',
                    'type': 'keyword',
                    'keyword': keyword
                }
            elif buff_type == 'duel':
                # Duel: fight 1v1, on victory gain +3/+3 per tier
                tier = run.current_ring
                buff_amount = 3 * tier
                buff_data = {
                    'name': 'Duel Champion',
                    'description': f'Fight a 1v1 duel. Victory: +{buff_amount}/+{buff_amount}',
                    'type': 'duel',
                    'buff_per_tier': 3
                }
            elif buff_type == 'feed_sacrifice':
                # Feed Your Pack: apply stored sacrifice stats to a Beast
                event_state = run.get_event_state()
                feed_stats = event_state.get('feed_sacrifice_stats', {})
                atk = feed_stats.get('attack', 0)
                hp = feed_stats.get('health', 0)
                name = feed_stats.get('name', 'minion')
                buff_data = {
                    'name': 'Feed the Beast',
                    'description': f"Transfer {name}'s stats: +{atk}/+{hp}",
                    'type': 'feed_sacrifice'
                }
            elif buff_type == 'boss_chained_beast':
                # Chained Beast boss reward: +8/+8 and Leap 2
                buff_data = {
                    'name': 'Unbound',
                    'description': '+8/+8 and gain Leap 2',
                    'type': 'boss_reward'
                }
            elif buff_type == 'boss_chained_ethereal':
                # Chained Beast boss reward: Ethereal [Left], Can't Cast, Can't Retaliate
                buff_data = {
                    'name': 'Cursed Freedom',
                    'description': 'Ethereal [Left], Can\'t Cast, Can\'t Retaliate',
                    'type': 'boss_keyword'
                }
            elif buff_type == 'boss_behemoth':
                # Behemoth boss reward: Guard and +5/+12
                buff_data = {
                    'name': 'Thick Hide',
                    'description': '+5/+12 and gain Guard',
                    'type': 'boss_reward'
                }
            elif buff_type == 'boss_dire_pack_keyword':
                # Dire Pack boss reward: On Any Death: +2/+2 to self
                buff_data = {
                    'name': 'Pack Bond',
                    'description': 'On Any Death: +2/+2',
                    'type': 'boss_keyword'
                }
            elif buff_type == 'boss_congregation_tribe':
                # Congregation boss reward: Gain Cult tribe
                buff_data = {
                    'name': 'Convert',
                    'description': 'Become a Cult minion',
                    'type': 'boss_keyword'
                }
            elif buff_type == 'boss_congregation_ignoble':
                # Congregation boss reward: Gain Ignoble
                buff_data = {
                    'name': 'Ignoble',
                    'description': 'Gain Ignoble (cannot take combat damage)',
                    'type': 'boss_keyword'
                }
            elif buff_type == 'boss_venomspawn_cast':
                # Venomspawn boss reward: Cast: Deal 2 damage to all enemies
                buff_data = {
                    'name': 'Venom Spit',
                    'description': 'Cast: Deal 2 damage to all enemy minions',
                    'type': 'boss_keyword'
                }
            elif buff_type == 'boss_possessed_deathtoll':
                # Greater Possessed boss reward: Death Toll: Summon a Possessed
                buff_data = {
                    'name': 'Dark Pact',
                    'description': 'Death Toll: Summon a Possessed',
                    'type': 'boss_keyword'
                }
            else:
                # Fall back to normal buff selection
                return EventSystem._create_scaling_buff_selection(run, 'buff_event')

            # For feed_sacrifice, exclude the minion being sacrificed from targets
            if buff_type == 'feed_sacrifice':
                event_state = run.get_event_state()
                sacrifice_index = event_state.get('feed_sacrifice_stats', {}).get('index')
                if sacrifice_index is not None:
                    filtered_band = [(i, m) for i, m in filtered_band if i != sacrifice_index]

            # Create target options using same format as choose_buff (use filtered band)
            on_select = parameters.get('on_select')  # Get on_select handler from parameters
            target_options = []
            for original_index, minion in filtered_band:
                option = {
                    'type': 'apply_targeted_effect',
                    'render_as': 'apply_targeted_effect',
                    'effect_type': 'buff',
                    'effect_data': buff_data,
                    'target_index': original_index,  # Use original band index for proper targeting
                    'data': minion,
                    'message': f"Apply to {minion['name']} ({format_minion_stats(minion['health'], minion['attack'])})",
                    'id': f'target_{original_index}'
                }
                # Pass on_select handler for boss rewards that need custom processing
                if on_select:
                    option['on_select'] = on_select
                target_options.append(option)

            # Check for back context from parent event chain (stored in event_state)
            event_state = run.get_event_state()
            back_label = event_state.get('pending_back_label')
            back_refund = event_state.get('pending_back_refund', 0)
            back_event = event_state.get('pending_back_event')  # Parent event to return to

            # Add back option if there's a back label from parent
            if back_label:
                target_options.append({
                    'type': 'back_with_refund',
                    'message': back_label,
                    'refund_amount': back_refund,
                    'return_to_event': back_event,  # Event to return to (if any)
                    'id': 'back'
                })
                # Clear the pending back context after using it
                event_state.pop('pending_back_label', None)
                event_state.pop('pending_back_refund', None)
                event_state.pop('pending_back_event', None)
                run.set_event_state(event_state)

            # Create selection matching choose_buff's second screen
            selection = {
                'event_type': 'target_minion',
                'title': parameters.get('title', buff_data['name']),
                'effect_preview': {
                    'name': buff_data['name'],
                    'description': buff_data['description'],
                    'type': buff_data.get('type', 'buff'),  # 'ring', 'keyword', etc.
                    'icon': buff_data.get('icon', '')
                },
                'current_band': band,
                'options': target_options,
                'min_selections': 1,
                'max_selections': 1,
                'repeating': False,
                'leaveable': back_label is not None  # Leaveable if there's a back option
            }

            # Only add message if explicitly provided
            if parameters.get('message'):
                selection['message'] = parameters['message']

            run.set_pending_selection(selection)
            return {
                'event_type': template_event['id'],
                'message': f'Choose target for {buff_data["name"]}',
                'selection_created': True,
                'band_changes': [],
                'resource_changes': {}
            }

        elif screen_type == 'combat':
            difficulty = parameters.get('difficulty', 'normal')

            # Check if hard combats should be downgraded (Watchtower Storm effect)
            event_state = run.get_event_state()
            hard_combat_downgrades = event_state.get('hard_combat_downgrades', 0)
            if difficulty == 'hard' and hard_combat_downgrades > 0:
                difficulty = 'normal'  # Downgrade to normal
                event_state['hard_combat_downgrades'] = hard_combat_downgrades - 1
                run.set_event_state(event_state)
                logger.debug(f"[COMBAT] Hard combat downgraded to normal! ({hard_combat_downgrades - 1} downgrades remaining)")

            # Map to old event type format
            event_type_map = {
                'normal': 'combat_event',
                'hard': 'combat_event_hard'
            }
            mapped_event_type = event_type_map.get(difficulty, 'combat_event')
            # Pass along event chaining parameters
            on_victory_event = first_screen.get('on_victory_event')
            on_defeat_event = first_screen.get('on_defeat_event')
            pool_filter = parameters.get('pool_filter')
            disable_gold_reward = parameters.get('disable_gold_reward', False)
            title = parameters.get('title')
            return EventSystem._create_scaling_combat_selection(
                run,
                mapped_event_type,
                on_victory_event=on_victory_event,
                on_defeat_event=on_defeat_event,
                pool_filter=pool_filter,
                disable_gold_reward=disable_gold_reward,
                title=title
            )

        elif screen_type == 'boss_combat':
            # Boss combat for The Great Hunt encounters
            boss_id = parameters.get('boss_id')
            event_state = run.get_event_state()

            # Check if we should use active_boss from event_state (reworked Great Hunt)
            if parameters.get('use_active_boss'):
                active_boss = event_state.get('active_boss', {})
                if active_boss and active_boss.get('boss_id'):
                    boss_id = active_boss['boss_id']
                    logger.debug(f"[BOSS_COMBAT] Using active_boss from event_state: {boss_id}")

            # If still no boss_id, select randomly from boss_pool (legacy behavior)
            if not boss_id:
                boss_pool = parameters.get('boss_pool', [])
                if boss_pool:
                    import random
                    boss_id = random.choice(boss_pool)
                    logger.debug(f"[BOSS_COMBAT] Selected random boss from pool: {boss_id}")
                else:
                    return {
                        'event_type': 'boss_combat',
                        'message': 'Error: No boss_id or boss_pool specified for boss_combat',
                        'band_changes': [],
                        'resource_changes': {}
                    }

            # Determine which victory event to chain to based on boss
            on_victory_event = first_screen.get('on_victory_event')
            # Route to boss-specific victory event if generic victory is specified
            if on_victory_event == 'great_hunt_boss_victory':
                boss_victory_events = {
                    'dire_pack': 'great_hunt_victory_dire_pack',
                    'congregation': 'great_hunt_victory_congregation',
                    'chained_beast': 'great_hunt_victory_chained_beast',
                    'behemoth': 'great_hunt_victory_behemoth',
                    'venomspawn': 'great_hunt_victory_venomspawn',
                    'greater_possessed': 'great_hunt_victory_greater_possessed'
                }
                on_victory_event = boss_victory_events.get(boss_id, on_victory_event)
                logger.debug(f"[BOSS_COMBAT] Routing victory to: {on_victory_event}")

            on_defeat_event = first_screen.get('on_defeat_event')
            title = parameters.get('title')
            persistent_damage_key = parameters.get('persistent_damage_key')

            return EventSystem._create_boss_combat_selection(
                run,
                boss_id=boss_id,
                on_victory_event=on_victory_event,
                on_defeat_event=on_defeat_event,
                title=title,
                persistent_damage_key=persistent_damage_key
            )

        elif screen_type == 'boss_reward_router':
            # Fallback boss reward router - should normally be routed to boss-specific victory events
            # If we get here, something went wrong with the routing
            event_state = run.get_event_state()
            active_boss = event_state.get('active_boss', {})
            boss_id = active_boss.get('boss_id')
            logger.debug(f"[BOSS_REWARD_ROUTER] Fallback triggered! boss_id={boss_id}")

            # Try to route to boss-specific victory event
            if boss_id:
                boss_victory_events = {
                    'dire_pack': 'great_hunt_victory_dire_pack',
                    'congregation': 'great_hunt_victory_congregation',
                    'chained_beast': 'great_hunt_victory_chained_beast',
                    'behemoth': 'great_hunt_victory_behemoth',
                    'venomspawn': 'great_hunt_victory_venomspawn',
                    'greater_possessed': 'great_hunt_victory_greater_possessed'
                }
                victory_event_id = boss_victory_events.get(boss_id)
                if victory_event_id:
                    from game_engine.events import get_event
                    victory_event = get_event(victory_event_id)
                    if victory_event:
                        logger.debug(f"[BOSS_REWARD_ROUTER] Routing to {victory_event_id}")
                        return EventSystem._create_template_based_event(run, victory_event)

            # Ultimate fallback: clear boss and show generic message
            logger.debug("[BOSS_REWARD_ROUTER] No boss_id found, clearing boss state")
            event_state['active_boss'] = None
            # Use bosses_defeated dict with tier key (matches the condition check)
            if 'bosses_defeated' not in event_state:
                event_state['bosses_defeated'] = {}
            event_state['bosses_defeated'][str(run.current_ring)] = 'unknown'
            run.set_event_state(event_state)

            # Create a simple story screen
            options = [{
                'type': 'continue',
                'message': 'Continue',
                'id': 'continue'
            }]
            selection = {
                'event_type': template_event['id'],
                'title': parameters.get('title', 'Boss Defeated!'),
                'message': 'The hunt is complete! (Reward routing failed - boss state cleared)',
                'icon': parameters.get('icon', 'trophy'),
                'options': options,
                'min_selections': 1,
                'max_selections': 1,
                'template_event': template_event
            }
            run.set_pending_selection(selection)
            return {
                'event_type': template_event['id'],
                'message': 'Boss reward router fallback',
                'selection_created': True,
                'band_changes': [],
                'resource_changes': {}
            }

        elif screen_type == 'roll_bounty_targets':
            # Roll bounty targets for The Great Hunt
            return EventSystem._create_bounty_target_selection(
                run,
                template_event,
                first_screen,
                parameters
            )

        elif screen_type == 'shop':
            return EventSystem._create_shop_selection(run, title=parameters.get('title', 'Tavern'))

        elif screen_type == 'statue':
            return EventSystem._create_combine_minions_selection(run, event_type='statue')

        elif screen_type == 'story':
            # Story screens display text with a continue button
            # They need to create a pending selection to show the UI
            on_continue = first_screen.get('on_continue')
            on_select = parameters.get('on_select')

            # Create a simple continue selection
            options = [{
                'type': 'continue',
                'message': parameters.get('continue_text', 'Continue'),
                'id': 'continue',
                'next_screen': on_continue,
                'on_select': on_select  # Pass along any handler for reward claiming etc.
            }]

            selection = {
                'event_type': template_event['id'],
                'title': parameters.get('title', 'Story'),
                'message': parameters.get('text', ''),
                'icon': parameters.get('icon', 'book-open'),
                'options': options,
                'min_selections': 1,
                'max_selections': 1,
                'template_event': template_event,  # Store for screen chaining
                'current_screen_id': first_screen.get('id')
            }

            run.set_pending_selection(selection)
            return {
                'event_type': template_event['id'],
                'message': 'Story screen opened',
                'selection_created': True,
                'band_changes': [],
                'resource_changes': {}
            }

        elif screen_type == 'make_choice':
            # Choice screens present multiple branching options
            return EventSystem._create_template_choice_selection(run, template_event, first_screen, parameters)

        elif screen_type == 'grant_minion':
            # Grant a specific minion to the player
            return EventSystem._create_specific_minion_selection(
                run,
                minion_name=parameters.get('minion_name'),
                tier=parameters.get('tier', 1),
                title=parameters.get('title', 'New Ally'),
                message=parameters.get('message', 'A minion joins your band!')
            )

        elif screen_type == 'select_champion':
            # Select a minion to be the champion for a duel
            # Stores champion_index in event_state for the subsequent duel combat
            band = run.get_band()

            if not band:
                return {
                    'event_type': template_event['id'],
                    'message': 'No minions to choose as champion!',
                    'band_changes': [],
                    'resource_changes': {}
                }

            # Create target options for each minion
            target_options = []
            for i, minion in enumerate(band):
                target_options.append({
                    'type': 'select_champion_target',
                    'target_index': i,
                    'data': minion,
                    'message': f"{minion['name']} ({format_minion_stats(minion['health'], minion['attack'])})",
                    'id': f'champion_{i}'
                })

            # Store template_event info for chaining to next screen (duel_combat)
            # Use 'duel_template_event' instead of 'template_event' to avoid
            # triggering _resolve_template_event_selection routing
            selection = {
                'event_type': 'target_minion',
                'title': parameters.get('title', 'Choose Your Champion'),
                'message': parameters.get('message', 'Select a minion to fight in the duel'),
                'effect_preview': {
                    'name': 'Champion Selection',
                    'description': 'This minion will fight alone. Victory: +3/+3 per tier.',
                    'type': 'champion'
                },
                'current_band': band,
                'options': target_options,
                'min_selections': 1,
                'max_selections': 1,
                'repeating': False,
                'leaveable': False,
                'duel_template_event': template_event,  # Use different key to avoid template routing
                'current_screen_id': first_screen.get('id')
            }

            run.set_pending_selection(selection)
            return {
                'event_type': template_event['id'],
                'message': 'Choose your champion',
                'selection_created': True,
                'band_changes': [],
                'resource_changes': {}
            }

        elif screen_type == 'duel_combat':
            # Special 1v1 duel combat using the champion from event_state
            event_state = run.get_event_state()
            champion_index = event_state.get('champion_index')

            if champion_index is None:
                return {
                    'event_type': template_event['id'],
                    'message': 'No champion selected for duel!',
                    'band_changes': [],
                    'resource_changes': {}
                }

            # Get the champion minion
            band = run.get_band()
            if champion_index >= len(band):
                return {
                    'event_type': template_event['id'],
                    'message': 'Champion no longer in band!',
                    'band_changes': [],
                    'resource_changes': {}
                }

            champion = band[champion_index]

            # Create duel combat selection
            on_victory_event = first_screen.get('on_victory_event')
            on_defeat_event = first_screen.get('on_defeat_event')
            title = parameters.get('title', '⚔️ Duel')
            disable_gold_reward = parameters.get('disable_gold_reward', True)
            disable_health_loss = parameters.get('disable_health_loss', True)

            return EventSystem._create_duel_combat_selection(
                run,
                champion_index=champion_index,
                on_victory_event=on_victory_event,
                on_defeat_event=on_defeat_event,
                disable_gold_reward=disable_gold_reward,
                disable_health_loss=disable_health_loss,
                title=title
            )

        elif screen_type == 'duel_victory':
            # Apply buff to the champion after duel victory
            event_state = run.get_event_state()
            champion_index = event_state.get('champion_index')

            band = run.get_band()
            if champion_index is None or champion_index >= len(band):
                # No champion found, just end the event
                run.set_pending_selection(None)
                return {
                    'event_type': template_event['id'],
                    'message': 'Victory! (Champion not found for buff)',
                    'band_changes': [],
                    'resource_changes': {}
                }

            champion = band[champion_index]
            tier = run.current_ring
            buff_per_tier = parameters.get('buff_per_tier', 3)
            buff_amount = buff_per_tier * tier

            # Apply the buff to the champion
            champion['health'] = champion.get('health', 0) + buff_amount
            champion['attack'] = champion.get('attack', 0) + buff_amount

            # Also update permanent stats for persistence
            champion['permanent_health'] = champion.get('permanent_health', 0) + buff_amount
            champion['permanent_attack'] = champion.get('permanent_attack', 0) + buff_amount

            run.set_band(band)

            # Clear champion_index from event_state
            event_state.pop('champion_index', None)
            run.set_event_state(event_state)

            # Create a simple continue screen to show the result
            title = parameters.get('title', 'Victory!')
            message = f"{champion['name']} gains +{buff_amount}/+{buff_amount} from their victory!"

            options = [{
                'type': 'continue',
                'message': 'Continue',
                'id': 'continue',
                'next_screen': None  # Event ends after this
            }]

            selection = {
                'event_type': template_event['id'],
                'title': title,
                'message': message,
                'icon': 'trophy',
                'options': options,
                'min_selections': 1,
                'max_selections': 1,
                'template_event': template_event,
                'current_screen_id': first_screen.get('id')
            }

            run.set_pending_selection(selection)
            return {
                'event_type': template_event['id'],
                'message': message,
                'selection_created': True,
                'band_changes': [message],
                'resource_changes': {}
            }

        elif screen_type == 'select_sacrifice_target':
            # Select a minion to sacrifice (remove from band)
            band = run.get_band()

            if not band:
                return {
                    'event_type': template_event['id'],
                    'message': 'No minions to sacrifice!',
                    'band_changes': [],
                    'resource_changes': {}
                }

            # Create target options for each minion
            target_options = []
            for i, minion in enumerate(band):
                target_options.append({
                    'type': 'sacrifice_target',
                    'render_as': 'sacrifice_target',
                    'target_index': i,
                    'data': minion,
                    'message': f"Sacrifice {minion['name']} ({format_minion_stats(minion['health'], minion['attack'])})",
                    'id': f'sacrifice_{i}',
                    'on_sacrifice': parameters.get('on_sacrifice')  # Pass through for handler
                })

            # Add cancel option
            target_options.append({
                'type': 'back_to_parent',
                'message': 'Cancel',
                'id': 'cancel'
            })

            selection = {
                'event_type': 'sacrifice_selection',
                'title': parameters.get('title', 'Sacrifice'),
                'message': parameters.get('message', 'Choose a minion to sacrifice'),
                'current_band': band,
                'options': target_options,
                'min_selections': 1,
                'max_selections': 1,
                'repeating': False,
                'leaveable': True,
                'template_event': template_event,
                'current_screen_id': first_screen.get('id')
            }

            run.set_pending_selection(selection)
            return {
                'event_type': template_event['id'],
                'message': 'Choose a minion to sacrifice',
                'selection_created': True,
                'band_changes': [],
                'resource_changes': {}
            }

        elif screen_type == 'select_golden_target':
            # Select a minion to make golden
            band = run.get_band()

            if not band:
                return {
                    'event_type': template_event['id'],
                    'message': 'No minions to transform!',
                    'band_changes': [],
                    'resource_changes': {}
                }

            # Create target options for each minion (excluding already golden ones)
            target_options = []
            for i, minion in enumerate(band):
                is_golden = minion.get('golden', False)
                target_options.append({
                    'type': 'golden_target',
                    'render_as': 'golden_target',
                    'target_index': i,
                    'data': minion,
                    'message': f"Make {minion['name']} golden ({format_minion_stats(minion['health'], minion['attack'])})" + (" (already golden)" if is_golden else ""),
                    'id': f'golden_{i}',
                    'disabled': is_golden
                })

            # Add cancel option
            target_options.append({
                'type': 'back_to_parent',
                'message': 'Cancel',
                'id': 'cancel'
            })

            selection = {
                'event_type': 'golden_selection',
                'title': parameters.get('title', 'Golden Forge'),
                'message': parameters.get('message', 'Choose a minion to make golden'),
                'current_band': band,
                'options': target_options,
                'min_selections': 1,
                'max_selections': 1,
                'repeating': False,
                'leaveable': True,
                'template_event': template_event,
                'current_screen_id': first_screen.get('id')
            }

            run.set_pending_selection(selection)
            return {
                'event_type': template_event['id'],
                'message': 'Choose a minion to make golden',
                'selection_created': True,
                'band_changes': [],
                'resource_changes': {}
            }

        elif screen_type == 'select_minion_and_number':
            # General screen: Select a minion, then choose a number value
            # Used for stat reduction (attack/health)
            band = run.get_band()

            if not band:
                return {
                    'event_type': template_event['id'],
                    'message': 'No minions available!',
                    'band_changes': [],
                    'resource_changes': {}
                }

            stat = parameters.get('stat', 'attack')  # 'attack' or 'health'
            min_value = parameters.get('min_value', 0)
            on_complete = parameters.get('on_complete')  # Handler name

            # Create minion selection options - render as minion cards
            target_options = []
            for i, minion in enumerate(band):
                current_stat = minion.get(stat, 0)
                # Calculate max reduction (can't go below min_value)
                max_reduction = current_stat - min_value

                target_options.append({
                    'type': 'select_for_number_choice',
                    'render_as': 'minion_card',  # Tell frontend to render as card
                    'target_index': i,
                    'minion': minion,  # Full minion data for card rendering
                    'stat': stat,
                    'min_value': min_value,
                    'current_value': current_stat,
                    'max_reduction': max_reduction,
                    'on_complete': on_complete,
                    'id': f'target_{i}',
                    'disabled': max_reduction <= 0  # Disable if nothing to reduce
                })

            # Add skip/back option
            target_options.append({
                'type': 'back_to_parent',
                'render_as': 'button',
                'message': 'Cancel',
                'id': 'cancel'
            })

            selection = {
                'event_type': 'select_minion_for_stat',
                'title': parameters.get('title', f'Reduce {stat.title()}'),
                'message': parameters.get('message', f'Choose a minion to reduce {stat}'),
                'render_options_as': 'minion_cards',  # Tell frontend this is a minion card selection
                'options': target_options,
                'min_selections': 1,
                'max_selections': 1,
                'repeating': False,
                'leaveable': True,
                'template_event': template_event,
                'current_screen_id': first_screen.get('id')
            }

            run.set_pending_selection(selection)
            return {
                'event_type': template_event['id'],
                'message': f'Choose a minion to reduce {stat}',
                'selection_created': True,
                'band_changes': [],
                'resource_changes': {}
            }

        elif screen_type == 'select_minion_and_choice':
            # General screen: Select a minion, then choose items from a list
            # Used for removing keywords or types
            band = run.get_band()

            if not band:
                return {
                    'event_type': template_event['id'],
                    'message': 'No minions available!',
                    'band_changes': [],
                    'resource_changes': {}
                }

            choice_source = parameters.get('choice_source', 'keywords')  # 'keywords' or 'types'
            on_complete = parameters.get('on_complete')
            all_or_nothing = parameters.get('all_or_nothing', False)  # If True, only "Remove All" or "Leave"

            # Create minion selection options - render as minion cards
            target_options = []
            for i, minion in enumerate(band):
                if choice_source == 'keywords':
                    items = minion.get('keywords', [])
                else:  # types
                    minion_type = minion.get('type', 'None')
                    if isinstance(minion_type, list):
                        items = minion_type
                    elif minion_type and minion_type != 'None':
                        items = [minion_type]
                    else:
                        items = []

                target_options.append({
                    'type': 'select_for_choice_list',
                    'render_as': 'minion_card',  # Tell frontend to render as card
                    'target_index': i,
                    'minion': minion,  # Full minion data for card rendering
                    'choice_source': choice_source,
                    'available_items': items,
                    'all_or_nothing': all_or_nothing,  # Pass through for confirmation screen
                    'on_complete': on_complete,
                    'id': f'target_{i}',
                    'disabled': len(items) == 0  # Disable if nothing to remove
                })

            # Add skip/back option
            target_options.append({
                'type': 'back_to_parent',
                'render_as': 'button',
                'message': 'Cancel',
                'id': 'cancel'
            })

            selection = {
                'event_type': 'select_minion_for_choice',
                'title': parameters.get('title', f'Remove {choice_source.title()}'),
                'message': parameters.get('message', f'Choose a minion to remove {choice_source} from'),
                'render_options_as': 'minion_cards',  # Tell frontend this is a minion card selection
                'options': target_options,
                'min_selections': 1,
                'max_selections': 1,
                'repeating': False,
                'leaveable': True,
                'template_event': template_event,
                'current_screen_id': first_screen.get('id')
            }

            run.set_pending_selection(selection)
            return {
                'event_type': template_event['id'],
                'message': f'Choose a minion',
                'selection_created': True,
                'band_changes': [],
                'resource_changes': {}
            }

        elif screen_type == 'ad_nauseam':
            # Ad Nauseam wrapper: Escalating health cost, chains to inner screen type
            # Each use costs 1 more HP (tracked per-choice in event_state)
            from game_engine.selection_system import SelectionSystem

            event_state = run.get_event_state()
            cost_tracker = parameters.get('cost_tracker', 'ad_nauseam_cost')
            inner_type = parameters.get('inner_type', 'shop')  # What screen to chain to

            # Get current cost (starts at 1, increments each use)
            current_cost = event_state.get(cost_tracker, 1)

            # Pay health cost (respects Lichdom - converts to gold)
            payment = SelectionSystem._pay_health_cost(run, current_cost)
            if not payment['success']:
                return {
                    'event_type': template_event['id'],
                    'message': payment['error'],
                    'band_changes': [],
                    'resource_changes': {}
                }

            # Increment cost for next use
            event_state[cost_tracker] = current_cost + 1
            run.set_event_state(event_state)

            # Get return_to_event if specified (for Great Work sub-events)
            return_to_event = parameters.get('return_to_event')

            # Chain to inner screen type
            if inner_type == 'shop':
                return EventSystem._create_shop_selection(run, title=parameters.get('title', 'Search the Graves'), return_to_event=return_to_event, num_offers=parameters.get('num_offers', 3))
            elif inner_type == 'blessing':
                return EventSystem._create_scaling_buff_selection(run, 'buff_event', return_to_event=return_to_event)
            elif inner_type == 'scry':
                # Create scry selection (see next event)
                return EventSystem._create_scry_selection(run, parameters, template_event, cost_tracker, return_to_event=return_to_event)
            else:
                return {
                    'event_type': template_event['id'],
                    'message': f'Unknown inner type: {inner_type}',
                    'band_changes': [],
                    'resource_changes': {}
                }

        else:
            # Unknown screen type
            return {
                'event_type': template_event['id'],
                'message': f'Unknown screen type: {screen_type}',
                'band_changes': [],
                'resource_changes': {}
            }

    @staticmethod
    def _create_template_choice_selection(run, template_event, screen, parameters):
        """
        Create a choice selection from a make_choice screen.

        Uses centralized helpers from event_helpers.py for:
        - Condition evaluation (evaluate_condition)
        - Formula resolution (resolve_formula)
        - Tooltip substitution (resolve_tooltip + build_tooltip_context)

        To add a new general event, define it in events.py using the standard
        choice option fields. Conditions and formulas are handled automatically.
        """
        choices = parameters.get('choices', [])
        event_state = run.get_event_state()
        tier = run.current_ring

        # Track if we actually use the unlock_special_options flag
        unlock_flag_used = False

        # Check for Lichdom hero effect (converts health costs to gold)
        hero_effects = run.get_hero_effects()
        has_lichdom = hero_effects.get('lichdom', False)
        resources = run.get_resources()

        options = []
        for i, choice in enumerate(choices):
            # --- Condition evaluation ---
            condition = choice.get('condition')
            state_defaults = template_event.get('state_defaults')
            disabled = evaluate_condition(condition, run, event_state, state_defaults)

            # Check if special options should be unlocked (from Watchtower Pay for Help)
            if disabled and event_state.get('unlock_special_options'):
                disabled = False
                unlock_flag_used = True

            # --- Resolve formulas ---
            cost = resolve_formula(choice.get('gold_cost'), tier)
            reward = resolve_formula(choice.get('gold_reward'), tier)
            stat_bonus = resolve_formula(choice.get('stat_bonus'), tier)

            # --- Gold affordability check ---
            can_afford = cost is None or cost <= 0 or resources.get('gold', 0) >= cost

            # --- Health cost (static or tracked) ---
            health_cost_tracker = choice.get('health_cost_tracker')
            static_health_cost = choice.get('health_cost')
            health_cost = 0

            if health_cost_tracker:
                health_cost = event_state.get(health_cost_tracker, 1)
            elif static_health_cost:
                health_cost = static_health_cost

            # With Lichdom, health costs become gold costs - check affordability
            if health_cost > 0 and has_lichdom:
                if resources.get('gold', 0) < health_cost:
                    disabled = True
                    can_afford = False

            # --- Tooltip resolution ---
            tooltip_context = build_tooltip_context(choice, tier, event_state, run, event_def=template_event)
            # Add resolved formula values to context
            tooltip_context['gold_cost'] = cost
            tooltip_context['gold_reward'] = reward
            tooltip_context['stat_bonus'] = stat_bonus
            tooltip = resolve_tooltip(choice.get('tooltip', ''), tier, tooltip_context)

            option = {
                'type': 'template_choice',
                'render_as': 'template_choice',
                'message': choice['name'],
                'description': choice.get('description', ''),
                'tooltip': tooltip,
                'icon': choice.get('icon', ''),
                'id': f'choice_{i}',
                'next_screen': choice.get('next_screen'),
                'next_event': choice.get('next_event'),
                'on_select': choice.get('on_select'),
                'gold_cost': cost,
                'health_cost': health_cost,
                'health_cost_tracker': health_cost_tracker,
                'lichdom': has_lichdom,
                'affordable': can_afford and not disabled,
                'disabled': disabled,
                'disabled_until_met': choice.get('disabled_until_met', False),
                'mark_event_complete': choice.get('mark_event_complete', False)
            }
            options.append(option)

        # Check if this is an ad_nauseam event (escalating costs)
        is_ad_nauseam = parameters.get('ad_nauseam', False)
        warning_text = parameters.get('warning_text', '')

        selection = {
            'event_type': template_event['id'],
            'title': parameters.get('title', 'Make a Choice'),
            'message': parameters.get('message', 'Choose your path'),
            'warning_text': warning_text,
            'ad_nauseam': is_ad_nauseam,
            'options': options,
            'min_selections': 1,
            'max_selections': 1,
            'template_event': template_event,
            'current_screen_id': screen.get('id'),
            'event_state': event_state
        }

        run.set_pending_selection(selection)

        # Consume the unlock_special_options flag only if it was actually used
        if unlock_flag_used and event_state.get('unlock_special_options'):
            event_state['unlock_special_options'] = False
            run.set_event_state(event_state)

        return {
            'event_type': template_event['id'],
            'message': 'Choice screen opened',
            'selection_created': True,
            'band_changes': [],
            'resource_changes': {}
        }

    @staticmethod
    def _create_scry_selection(run, parameters, template_event, cost_tracker, return_to_event=None):
        """Create a scry selection - see and manipulate the next event"""
        import random
        from game_engine.events.events import GENERAL_EVENT_POOL, CROSSROADS_EVENTS

        # Roll a random event from the general event pool
        rolled_event_id = random.choice(GENERAL_EVENT_POOL)
        rolled_event = CROSSROADS_EVENTS.get(rolled_event_id, {})

        # Extract event choices from screens using centralized helpers
        event_choices = []
        tier = run.current_ring
        event_state = run.get_event_state()
        for screen in rolled_event.get('screens', []):
            if screen.get('type') == 'make_choice':
                choices = screen.get('parameters', {}).get('choices', [])
                for choice in choices:
                    gold_cost = resolve_formula(choice.get('gold_cost'), tier)
                    gold_cost_display = f"{gold_cost} gold" if gold_cost else ''

                    tooltip_context = build_tooltip_context(choice, tier, event_state, run, event_def=rolled_event)
                    tooltip_context['gold_cost'] = gold_cost
                    tooltip = resolve_tooltip(choice.get('tooltip', ''), tier, tooltip_context)

                    event_choices.append({
                        'name': choice.get('name', ''),
                        'description': choice.get('description', ''),
                        'tooltip': tooltip,
                        'gold_cost': gold_cost,
                        'gold_cost_display': gold_cost_display,
                        'icon': choice.get('icon', '')
                    })
                break  # Only get choices from first make_choice screen

        # Build options: Keep, Discard, Done
        # All options return to parent event if specified
        keep_option = {
            'type': 'scry_keep',
            'render_as': 'scry_keep',
            'message': 'Keep',
            'description': 'Set this as your next general event',
            'id': 'keep'
        }
        discard_option = {
            'type': 'scry_discard',
            'render_as': 'scry_discard',
            'message': 'Discard',
            'description': 'Skip this event entirely',
            'id': 'discard'
        }
        done_option = {
            'type': 'back_to_parent',
            'render_as': 'back_to_parent',
            'message': 'Done',
            'description': 'Return without making a choice',
            'id': 'done'
        }

        if return_to_event:
            keep_option['return_to_event'] = return_to_event
            discard_option['return_to_event'] = return_to_event
            done_option['return_to_event'] = return_to_event

        options = [keep_option, discard_option, done_option]

        selection = {
            'event_type': 'scry_selection',
            'title': parameters.get('title', 'Mark the Scrolls'),
            'message': 'Your next general event is revealed:',
            'scried_event': {
                'id': rolled_event_id,
                'title': rolled_event.get('title', rolled_event_id),
                'description': rolled_event.get('description', ''),
                'choices': event_choices
            },
            'options': options,
            'min_selections': 1,
            'max_selections': 1,
            'repeating': False,
            'leaveable': True,
            'template_event': template_event,
            'return_to_event': return_to_event  # Event to return to after action
        }

        run.set_pending_selection(selection)
        return {
            'event_type': template_event['id'],
            'message': 'Scry selection opened',
            'selection_created': True,
            'band_changes': [],
            'resource_changes': {}
        }

    @staticmethod
    def _create_specific_minion_selection(run, minion_name, tier=1, title='New Ally', message='A minion joins your band!'):
        """Create a selection to grant a specific minion"""
        from minions import get_minion_by_name, create_minion_instance

        # Get the minion template
        minion_template = get_minion_by_name(minion_name)
        if not minion_template:
            return {
                'event_type': 'grant_minion',
                'message': f'Minion {minion_name} not found',
                'band_changes': [],
                'resource_changes': {}
            }

        # Create the minion instance at the specified tier
        minion = create_minion_instance(minion_template, tier=tier, assign_band_id=True)

        current_band = run.get_band()
        effective_max = get_effective_max_band_size(run)

        if len(current_band) >= effective_max:
            # Band is full - need replacement selection
            options = [{
                'type': 'replacement',
                'render_as': 'replacement',
                'data': minion,
                'cost': 0,
                'message': f"Add {minion['name']} ({format_minion_stats(minion['health'], minion['attack'])})",
                'id': 'new_minion'
            }]

            # Add skip option
            options.append({
                'type': 'skip',
                'message': 'Leave without taking',
                'id': 'skip'
            })

            selection = {
                'event_type': 'grant_minion',
                'title': title,
                'message': f'{message} (Your band is full - choose a minion to replace)',
                'offered_minions': [minion],
                'current_band': current_band,
                'options': options,
                'min_selections': 0,
                'max_selections': 1
            }
        else:
            # Band has space - simple add
            options = [{
                'type': 'minion',
                'render_as': 'minion',
                'data': minion,
                'cost': 0,
                'message': f"Add {minion['name']} ({format_minion_stats(minion['health'], minion['attack'])})",
                'id': 'add_minion'
            }]

            selection = {
                'event_type': 'grant_minion',
                'title': title,
                'message': message,
                'offered_minions': [minion],
                'current_band': current_band,
                'options': options,
                'min_selections': 1,
                'max_selections': 1
            }

        run.set_pending_selection(selection)
        return {
            'event_type': 'grant_minion',
            'message': f'{minion_name} ready to join!',
            'selection_created': True,
            'band_changes': [],
            'resource_changes': {}
        }

    @staticmethod
    def _get_event_description(event_type):
        """Get description for events in split selections"""
        descriptions = {
            # Minion events
            'minion_event': 'Choose from 3 minions from the multi-tier pool',

            # Buff events
            'buff_event': 'Enhance one of your minions with a blessing',

            # Combat events
            'combat_event': 'Fight enemies for gold rewards',
            'combat_event_hard': 'Fight tougher enemies (tier+1) for better rewards',

            # Shop events
            'shop_event': 'Purchase minions with gold from the multi-tier pool',

            # Static events
            'statue': 'Combine identical minions into golden versions',
            'artifact': 'Discover mysterious artifacts (Coming Soon)',
        }
        return descriptions.get(event_type, 'A mysterious event...')

    @staticmethod
    def _find_combinable_pairs(band):
        """Find pairs of minions that can be combined (same name, both not golden)"""
        combinable_pairs = []

        for i in range(len(band)):
            for j in range(i + 1, len(band)):
                minion1 = band[i]
                minion2 = band[j]

                # Can combine if same name and neither is golden
                if (minion1['name'] == minion2['name'] and
                        not minion1.get('golden', False) and
                        not minion2.get('golden', False)):
                    combinable_pairs.append((i, j))

        return combinable_pairs

    @staticmethod
    def _create_golden_minion(minion1, minion2):
        """Create a golden minion by combining two identical minions"""
        # Create golden minion with combined stats from both minions
        golden = minion1.copy()

        # Combine the stats of both minions
        golden['health'] = minion1['health'] + minion2['health']
        golden['attack'] = minion1['attack'] + minion2['attack']
        golden['golden'] = True

        # Combine permanent stats from both minions
        golden['permanent_health'] = minion1.get('permanent_health', 0) + minion2.get('permanent_health', 0)
        golden['permanent_attack'] = minion1.get('permanent_attack', 0) + minion2.get('permanent_attack', 0)

        return golden

    @staticmethod
    def _validate_combine_selection(band, selected_indices):
        """Validate that the selected minions can be combined"""
        if len(selected_indices) != 2:
            return False, "Must select exactly 2 minions to combine"

        idx1, idx2 = selected_indices
        if idx1 >= len(band) or idx2 >= len(band):
            return False, "Invalid minion indices"

        minion1 = band[idx1]
        minion2 = band[idx2]

        # FIXED: can_combine_minions returns only a boolean, need to return tuple
        can_combine = can_combine_minions(minion1, minion2)

        if can_combine:
            return True, "Minions can be combined"
        else:
            # Check specific reasons why they can't be combined
            if minion1['name'] != minion2['name']:
                return False, f"Cannot combine different minions: {minion1['name']} and {minion2['name']}"
            elif minion1.get('golden', False):
                return False, f"{minion1['name']} is already golden"
            elif minion2.get('golden', False):
                return False, f"{minion2['name']} is already golden"
            else:
                return False, "These minions cannot be combined"

    @staticmethod
    def _create_general_event_selection(run):
        """
        Create a general event selection.

        General events:
        1. If player has scrap curse, force scrap_heap event
        2. If position already visited this zone, return buff_event
        3. Otherwise, randomly select from GENERAL_EVENT_POOL and mark visited
        """
        import random
        from game_engine.events.events import GENERAL_EVENT_POOL

        event_state = run.get_event_state()
        ring_position = run.ring_position
        current_zone = getattr(run, 'current_zone', 'starting_plains')

        # Initialize visited_general_events tracking if not present
        if 'visited_general_events' not in event_state:
            event_state['visited_general_events'] = {}

        # Track by zone - reset when zone changes
        if 'visited_general_events_zone' not in event_state:
            event_state['visited_general_events_zone'] = current_zone

        # Check if zone changed - reset visited positions
        if event_state.get('visited_general_events_zone') != current_zone:
            event_state['visited_general_events'] = {}
            event_state['visited_general_events_zone'] = current_zone
            run.set_event_state(event_state)

        visited_positions = event_state.get('visited_general_events', {})

        # 1. Check for scrap curse - forces scrap_heap
        if event_state.get('curse_type') == 'scrap_heap':
            logger.debug(f"[GENERAL_EVENT] Scrap curse active - forcing scrap_heap event")
            return EventSystem.create_event_selection(run, 'scrap_heap')

        # 2. Check if this position was already visited - return buff_event
        position_key = str(ring_position)
        if position_key in visited_positions:
            logger.debug(f"[GENERAL_EVENT] Position {ring_position} already visited - returning buff_event")
            return EventSystem.create_event_selection(run, 'buff_event')

        # 3. Randomly select from pool
        selected_event = random.choice(GENERAL_EVENT_POOL)
        logger.debug(f"[GENERAL_EVENT] Randomly selected: {selected_event} at position {ring_position}")

        # Mark this position as visited
        visited_positions[position_key] = selected_event
        event_state['visited_general_events'] = visited_positions
        run.set_event_state(event_state)

        # Create the selected event
        return EventSystem.create_event_selection(run, selected_event)