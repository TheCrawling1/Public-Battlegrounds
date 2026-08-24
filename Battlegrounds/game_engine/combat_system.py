"""
Combat System - Registry-based interactive combat management

FULLY REGISTRY-DRIVEN: All combat actions use the combat_action_registry system.
No hardcoded command creation or log generation.

FIXED: Start of combat now properly checks for keywords (fast, rich, aura, divide_attack)
FIXED: Start of combat uses proper alternating order with player preference
ADDED: Cleave keyword support - deals damage to adjacent enemies
"""

import logging

logger = logging.getLogger(__name__)

import copy
from typing import Dict, List, Optional, Tuple, Any
from config import RESET_HEALTH_AFTER_COMBAT
from keywords import has_keyword, select_combat_target, get_multi_attack_count, is_stunned, reduce_stun

# Module-level flag to suppress debug output (set True for headless/batch runs).
# Debug output also respects the logging level (see logging_config); this flag
# provides an explicit hard override for batch runs.
QUIET_MODE = False

def _debug(*args, **kwargs):
    if not QUIET_MODE and args:
        logger.debug(" ".join(str(a) for a in args))
from game_engine.combat_registry import CombatRegistry
from game_random import game_random, SelectionType
from hero_definitions import get_scaled_effect_value

# Import registry-based combat action system
from game_engine.combat_actions import (
    process_combat_damage,
    process_declare_attack,
    process_turn_start,
    process_stun_skip,
    process_round_start,
    process_attack_cancelled,
    process_no_attack_skip,
    process_cast_finished
)
from game_engine.interpreter import CombatActionBuilder

# Import the trigger processor system
from game_engine.trigger_processor import TriggerProcessor
from game_engine.trigger_queue import TriggerPriority
from game_engine.combat_context import CombatContextManager
from game_engine.events.combat_events import CombatEventSystem, CombatEventType

# Import the interpreter system
from game_engine.combat_interpreter import CombatInterpreter, CombatCommand

# Import the centralized damage handler
from game_engine.damage_handler import apply_damage, DamageType, reset_damage_handler

class CombatSystem:
    """Handles interactive combat flows with full registry integration"""

    # Class-level processor for handling triggers
    _trigger_processor: Optional[TriggerProcessor] = None

    @classmethod
    def _get_trigger_processor(cls) -> TriggerProcessor:
        """Get or create the trigger processor"""
        if cls._trigger_processor is None:
            cls._trigger_processor = TriggerProcessor()
        return cls._trigger_processor

    @staticmethod
    def enable_dev_mode_combat(pause_on_trigger: bool = True, pause_on_effect: bool = False):
        """Enable dev mode for combat with trigger interception"""
        processor = CombatSystem._get_trigger_processor()
        processor.enable_dev_mode(pause_on_trigger, pause_on_effect)

    @staticmethod
    def _add_ui_display_data(combat_state):
        """Add pre-calculated UI display data"""
        player_band = combat_state.get('player_band', [])
        enemy_band = combat_state.get('enemy_band', [])
        is_player_turn = combat_state.get('player_turn', True)
        combat_over = combat_state.get('combat_over', False)

        alive_player_count = sum(1 for m in player_band if m.get('health', 0) > 0)
        alive_enemy_count = sum(1 for m in enemy_band if m.get('health', 0) > 0)

        active_player_index = None
        active_enemy_index = None

        if not combat_over:
            multi_attack_queue = combat_state.get('multi_attack_queue', [])
            if multi_attack_queue:
                next_multi_attack = multi_attack_queue[0]
                multi_attacker = next_multi_attack['attacker']

                if multi_attacker in player_band:
                    active_player_index = player_band.index(multi_attacker)
                elif multi_attacker in enemy_band:
                    active_enemy_index = enemy_band.index(multi_attacker)
            else:
                if is_player_turn:
                    active_player_index = CombatSystem._find_next_alive_unit(player_band, combat_state.get('current_player_unit', 0))
                else:
                    active_enemy_index = CombatSystem._find_next_alive_unit(enemy_band, combat_state.get('current_enemy_unit', 0))

        combat_state['ui_data'] = {
            'alive_player_count': alive_player_count,
            'alive_enemy_count': alive_enemy_count,
            'active_player_index': active_player_index,
            'active_enemy_index': active_enemy_index,
            'total_player_count': len(player_band),
            'total_enemy_count': len(enemy_band)
        }

    @staticmethod
    def _find_next_alive_unit(band, start_index):
        """Find the next alive unit in the band"""
        if not band or not isinstance(band, list):
            return None

        if start_index is None:
            start_index = 0

        if start_index >= len(band):
            start_index = 0

        for i in range(len(band)):
            check_index = (start_index + i) % len(band)
            minion = band[check_index]
            if isinstance(minion, dict) and minion.get('health', 0) > 0:
                return check_index

        return None

    @staticmethod
    def _check_combat_end_after_triggers(combat_state):
        """Check if combat should end after all triggers processed"""
        player_band = combat_state.get('player_band', [])
        enemy_band = combat_state.get('enemy_band', [])

        alive_player_band = [m for m in player_band if m.get('health', 0) > 0]
        alive_enemy_band = [m for m in enemy_band if m.get('health', 0) > 0]

        if not alive_player_band or not alive_enemy_band:
            combat_state['combat_over'] = True

            if alive_player_band and not alive_enemy_band:
                combat_state['winner'] = 'player'
                if 'combat_log' not in combat_state:
                    combat_state['combat_log'] = []
                combat_state['combat_log'].append("🏆 Player wins!")
            elif alive_enemy_band and not alive_player_band:
                combat_state['winner'] = 'enemy'
                if 'combat_log' not in combat_state:
                    combat_state['combat_log'] = []
                combat_state['combat_log'].append("💀 Enemy wins!")
            else:
                combat_state['winner'] = 'draw'
                if 'combat_log' not in combat_state:
                    combat_state['combat_log'] = []
                combat_state['combat_log'].append("🤝 Draw!")
            return True
        return False

    @staticmethod
    def _get_interpreter(combat_state: Dict) -> Optional[CombatInterpreter]:
        """Get or create interpreter from combat state"""
        if 'interpreter' not in combat_state:
            return None
        return combat_state['interpreter']

    @staticmethod
    def _add_action_command(combat_state: Dict, action_type: str, action_data: Dict, changes: Dict, logs: List[str]):
        """
        Add combat action command(s) to interpreter using CombatActionBuilder

        This is the registry-based replacement for manual command creation
        """
        interpreter = CombatSystem._get_interpreter(combat_state)
        if not interpreter:
            return

        action_builder = CombatActionBuilder()

        # Build command(s) using registry
        commands = action_builder.build_action_commands(action_type, action_data, changes, logs)

        # Add all commands to interpreter
        for command in commands:
            interpreter.add_command(command)

        _debug(f"[COMBAT_SYSTEM] Added {len(commands)} command(s) for {action_type}")

    @staticmethod
    def _detect_band_composition_change(combat_state: Dict) -> bool:
        """Detect if the band composition changed this turn"""
        deaths_occurred = combat_state.get('deaths_this_turn', False)
        summons_occurred = combat_state.get('summons_this_turn', False)

        combat_state['deaths_this_turn'] = False
        combat_state['summons_this_turn'] = False

        band_changed = deaths_occurred or summons_occurred

        if band_changed:
            _debug(f"[DEBUG] Band composition change detected")

        return band_changed

    @staticmethod
    def _advance_turn_order_after_band_change(combat_state: Dict, is_player_turn: bool, original_attacker_position: int, current_band_size: int) -> bool:
        """Simple turn order advancement: always advance to next position after original attacker"""
        if current_band_size == 0:
            if is_player_turn:
                combat_state['current_player_unit'] = 0
            else:
                combat_state['current_enemy_unit'] = 0
            return False

        next_position = (original_attacker_position + 1) % current_band_size

        if is_player_turn:
            combat_state['current_player_unit'] = next_position
        else:
            combat_state['current_enemy_unit'] = next_position

        return True

    @staticmethod
    def _queue_multi_attacks(attacker, combat_state):
        """Queue additional attacks for multi_attack minions"""
        if combat_state.get('in_multi_attack', False):
            return 0

        if not has_keyword(attacker, 'multi_attack'):
            return 0

        additional_attacks = get_multi_attack_count(attacker)

        if additional_attacks <= 0:
            return 0

        if 'multi_attack_queue' not in combat_state:
            combat_state['multi_attack_queue'] = []

        is_player_turn = combat_state.get('player_turn', True)

        for i in range(additional_attacks):
            combat_state['multi_attack_queue'].append({
                'attacker': attacker,
                'is_player_turn': is_player_turn,
                'attack_number': i + 2
            })

        # Use registry system for multi-attack command
        interpreter = CombatSystem._get_interpreter(combat_state)
        if interpreter:
            interpreter.add_command({
                'cmd': CombatCommand.MULTI_ATTACK,
                'attacker_id': attacker.get('_combat_id'),
                'attacker_name': attacker.get('name'),
                'attack_count': additional_attacks
            })

        return additional_attacks

    @staticmethod
    def _should_process_attack(attacker):
        """Check if a minion should process their attack turn"""
        if attacker.get('attack', 0) <= 0:
            has_assault = has_keyword(attacker, 'assault')
            has_cast = has_keyword(attacker, 'cast')

            if has_assault or has_cast:
                return True, True
            else:
                return False, False

        return True, False

    @staticmethod
    def _process_multi_attack_queue(combat_state, run=None):
        """Process any queued multi-attacks"""
        if 'multi_attack_queue' not in combat_state or not combat_state['multi_attack_queue']:
            return False

        multi_attack_data = combat_state['multi_attack_queue'].pop(0)
        attacker = multi_attack_data['attacker']

        if attacker.get('health', 0) <= 0:
            combat_state['multi_attack_queue'] = [
                ma for ma in combat_state['multi_attack_queue']
                if ma['attacker'] != attacker
            ]
            return False

        registry_data = combat_state.get('combat_registry_data')
        player_band = combat_state.get('player_band', [])
        enemy_band = combat_state.get('enemy_band', [])

        if registry_data:
            registry = CombatRegistry.from_dict(registry_data, player_band, enemy_band)
        else:
            registry = CombatRegistry()
            registry.register_band(player_band, 'player')
            registry.register_band(enemy_band, 'enemy')

        band_type = registry.get_minion_band_type(attacker)

        if band_type == 'player':
            alive_defenders = [m for m in enemy_band if m.get('health', 0) > 0]
        elif band_type == 'enemy':
            alive_defenders = [m for m in player_band if m.get('health', 0) > 0]
        else:
            return False

        target = select_combat_target(attacker, alive_defenders)

        if not target:
            combat_state['multi_attack_queue'] = []
            return False

        combat_state['in_multi_attack'] = True

        if 'combat_log' not in combat_state:
            combat_state['combat_log'] = []

        attack_number = multi_attack_data['attack_number']
        combat_state['combat_log'].append(f"⚔️ {attacker['name']}'s multi-attack #{attack_number}!")

        if band_type == 'player':
            attacker_index = player_band.index(attacker)
        else:
            attacker_index = enemy_band.index(attacker)

        CombatSystem._execute_attack_with_triggers(
            attacker, target, attacker_index,
            combat_state, run, registry
        )

        combat_state['in_multi_attack'] = False
        combat_state['combat_registry_data'] = registry.to_dict()

        return True

    @staticmethod
    def process_combat_step(combat_state, run=None):
        """
        Process one step of combat using registry-based actions

        REGISTRY-DRIVEN: All actions go through combat action handlers
        """
        _debug(f"[DEBUG] === Processing combat step ===")

        if combat_state.get('combat_over', False):
            return combat_state

        # Process multi-attack queue first
        if CombatSystem._process_multi_attack_queue(combat_state, run):
            CombatSystem._check_combat_end_after_triggers(combat_state)
            CombatSystem._add_ui_display_data(combat_state)
            return combat_state

        player_band = combat_state.get('player_band', [])
        enemy_band = combat_state.get('enemy_band', [])
        initial_player_count = len([m for m in player_band if m.get('health', 0) > 0])
        initial_enemy_count = len([m for m in enemy_band if m.get('health', 0) > 0])

        # Deserialize registry
        registry_data = combat_state.get('combat_registry_data')
        if registry_data:
            registry = CombatRegistry.from_dict(registry_data, player_band, enemy_band)
        else:
            registry = CombatRegistry()
            registry.register_band(player_band, 'player')
            registry.register_band(enemy_band, 'enemy')

        if 'attack_count' not in combat_state:
            combat_state['attack_count'] = 0
        if 'turn_count' not in combat_state:
            combat_state['turn_count'] = 0
        if 'fatigue_active' not in combat_state:
            combat_state['fatigue_active'] = False
        if 'fatigue_attacks' not in combat_state:
            combat_state['fatigue_attacks'] = 0

        # Increment turn_count every step (unlike attack_count, this always goes up)
        combat_state['turn_count'] += 1

        is_player_turn = combat_state.get('player_turn', True)

        # Check fatigue auto-end (attacks OR turns - whichever hits limit first)
        if combat_state['attack_count'] >= 200 or combat_state['turn_count'] >= 500:
            combat_state['combat_over'] = True
            player_count = len([m for m in player_band if m.get('health', 0) > 0])
            enemy_count = len([m for m in enemy_band if m.get('health', 0) > 0])

            if 'combat_log' not in combat_state:
                combat_state['combat_log'] = []

            if player_count > enemy_count:
                combat_state['winner'] = 'player'
                combat_state['combat_log'].append(f"⏰💀 Fatigue limit reached! Player wins!")
            elif enemy_count > player_count:
                combat_state['winner'] = 'enemy'
                combat_state['combat_log'].append(f"⏰💀 Fatigue limit reached! Enemy wins!")
            else:
                combat_state['winner'] = 'draw'
                combat_state['combat_log'].append(f"⏰💀 Fatigue limit reached! Draw!")
            return combat_state

        # Add round start command
        if combat_state.get('round_number', 1) == 1 and combat_state.get('current_player_unit', 0) == 0 and combat_state.get('current_enemy_unit', 0) == 0:
            # REGISTRY-BASED: Use process_round_start handler
            action_data = {'round': combat_state.get('round_number', 1)}
            context = {'combat_state': combat_state}
            success, logs, changes = process_round_start(action_data, context)

            if success:
                combat_state['combat_log'].extend(logs)
                CombatSystem._add_action_command(combat_state, 'round_start', action_data, changes, logs)

        # Activate fatigue based on turns if no attacks are happening (0-attack stalemate)
        if not combat_state.get('fatigue_active', False) and combat_state['turn_count'] >= 100:
            combat_state['fatigue_active'] = True
            if 'combat_log' not in combat_state:
                combat_state['combat_log'] = []
            combat_state['combat_log'].append("💀⚡ Combat fatigue begins! (stalemate)")
            # Add fatigue command to interpreter
            interpreter = combat_state.get('interpreter')
            if interpreter:
                interpreter.add_command({
                    'cmd': 'LOG',
                    'log_message': "💀⚡ Combat fatigue begins! (stalemate)"
                })

        # Apply fatigue damage at the start of each round (if fatigue is active)
        if combat_state.get('fatigue_active', False):
            # Only apply at the start of a round (player's first turn)
            if combat_state.get('current_player_unit', 0) == 0 and combat_state.get('current_enemy_unit', 0) == 0 and is_player_turn:
                # Calculate fatigue damage - scales with how long combat has lasted
                # Use whichever counter is higher to scale damage
                effective_count = max(combat_state['attack_count'], combat_state['turn_count'] // 3)
                fatigue_damage = 1 + (max(0, effective_count - 40) // 20)  # At least 1 damage

                # Track fatigue attacks
                combat_state['fatigue_attacks'] = combat_state.get('fatigue_attacks', 0) + 1

                # Get all alive minions
                affected_minions = []
                for minion in player_band + enemy_band:
                    if minion.get('health', 0) > 0:
                        affected_minions.append(minion)
                        # Apply fatigue damage using damage handler
                        damage_result = apply_damage(
                            target=minion,
                            amount=fatigue_damage,
                            damage_type=DamageType.FATIGUE,
                            source_minion=None
                        )

                # Log and create command
                fatigue_log = f"💀⚡ Fatigue deals {fatigue_damage} damage to all minions!"
                if 'combat_log' not in combat_state:
                    combat_state['combat_log'] = []
                combat_state['combat_log'].append(fatigue_log)

                # Add FATIGUE_DAMAGE command to interpreter
                interpreter = combat_state.get('interpreter')
                if interpreter:
                    affected_ids = [m.get('_combat_id') for m in affected_minions]
                    fatigue_command = {
                        'cmd': 'FATIGUE_DAMAGE',
                        'amount': fatigue_damage,
                        'affected_minions': affected_ids,
                        'log_message': fatigue_log
                    }
                    interpreter.add_command(fatigue_command)

        # Execute attack for current turn
        if is_player_turn:
            attacker_index = CombatSystem._find_next_alive_unit(player_band, combat_state.get('current_player_unit', 0))
            original_attacker_position = attacker_index if attacker_index is not None else 0

            if attacker_index is None:
                pass
            else:
                attacker = player_band[attacker_index]

                # REGISTRY-BASED: Use process_turn_start handler
                action_data = {
                    'minion': attacker,
                    'side': 'player'
                }
                context = {'combat_state': combat_state}
                success, logs, changes = process_turn_start(action_data, context)

                if success:
                    combat_state['combat_log'].extend(logs)
                    CombatSystem._add_action_command(combat_state, 'turn_start', action_data, changes, logs)

                # Check stun
                if is_stunned(attacker):
                    # REGISTRY-BASED: Use process_stun_skip handler
                    stun_remaining = attacker.get('stun_count', 0)
                    action_data = {
                        'minion': attacker,
                        'stun_remaining': stun_remaining,
                        'minion_index': attacker_index,
                        'is_enemy': False
                    }
                    context = {'combat_state': combat_state}
                    success, logs, changes = process_stun_skip(action_data, context)

                    if success:
                        combat_state['combat_log'].extend(logs)
                        CombatSystem._add_action_command(combat_state, 'stun_skip', action_data, changes, logs)

                    remaining_stun = reduce_stun(attacker)
                    if remaining_stun == 0:
                        combat_state['combat_log'].append(f"✅ {attacker['name']} is no longer stunned!")

                else:
                    should_process, has_combat_tricks = CombatSystem._should_process_attack(attacker)

                    if not should_process:
                        # REGISTRY-BASED: Use process_no_attack_skip handler
                        reason = 'cant_attack' if has_keyword(attacker, 'cant_attack') else 'zero_attack'
                        action_data = {
                            'minion': attacker,
                            'reason': reason,
                            'minion_index': attacker_index,
                            'is_enemy': False
                        }
                        context = {'combat_state': combat_state}
                        success, logs, changes = process_no_attack_skip(action_data, context)

                        if success:
                            combat_state['combat_log'].extend(logs)
                            CombatSystem._add_action_command(combat_state, 'no_attack_skip', action_data, changes, logs)
                    else:
                        alive_enemy_band = [m for m in enemy_band if m.get('health', 0) > 0]
                        target = select_combat_target(attacker, alive_enemy_band)

                        if target:
                            skip_damage = (has_keyword(attacker, 'cant_attack') or attacker.get('attack', 0) <= 0)

                            CombatSystem._execute_attack_with_triggers(
                                attacker, target, attacker_index,
                                combat_state, run, registry,
                                skip_damage=skip_damage
                            )

                            if (attacker.get('attack', 0) > 0 and
                                not is_stunned(attacker) and
                                not has_keyword(attacker, 'cant_attack')):
                                additional_attacks = CombatSystem._queue_multi_attacks(attacker, combat_state)
                                if additional_attacks > 0:
                                    combat_state['combat_log'].append(f"⚔️ {attacker['name']} will attack {additional_attacks} more time(s)!")

                        else:
                            if has_combat_tricks:
                                if 'combat_log' not in combat_state:
                                    combat_state['combat_log'] = []
                                combat_state['combat_log'].append(f"🔮 {attacker['name']} #{attacker_index + 1} has no targets but uses abilities")

                                CombatSystem._execute_attack_with_triggers(
                                    attacker, None, attacker_index,
                                    combat_state, run, registry,
                                    skip_damage=True
                                )

            # Handle turn advancement
            final_player_count = len([m for m in player_band if m.get('health', 0) > 0])
            if final_player_count != initial_player_count:
                combat_state['deaths_this_turn'] = True

            if len(player_band) != combat_state.get('original_player_count', len(player_band)):
                combat_state['summons_this_turn'] = True
                combat_state['original_player_count'] = len(player_band)

            band_changed = CombatSystem._detect_band_composition_change(combat_state)

            if band_changed:
                CombatSystem._advance_turn_order_after_band_change(
                    combat_state, is_player_turn, original_attacker_position, len(player_band)
                )
            else:
                if len(player_band) > 0:
                    combat_state['current_player_unit'] = (attacker_index + 1) % len(player_band)
                else:
                    combat_state['current_player_unit'] = 0

        else:
            # Enemy turn - same logic
            attacker_index = CombatSystem._find_next_alive_unit(enemy_band, combat_state.get('current_enemy_unit', 0))
            original_attacker_position = attacker_index if attacker_index is not None else 0

            if attacker_index is None:
                pass
            else:
                attacker = enemy_band[attacker_index]

                # REGISTRY-BASED: Use process_turn_start handler
                action_data = {
                    'minion': attacker,
                    'side': 'enemy'
                }
                context = {'combat_state': combat_state}
                success, logs, changes = process_turn_start(action_data, context)

                if success:
                    combat_state['combat_log'].extend(logs)
                    CombatSystem._add_action_command(combat_state, 'turn_start', action_data, changes, logs)

                # Check stun
                if is_stunned(attacker):
                    stun_remaining = attacker.get('stun_count', 0)
                    action_data = {
                        'minion': attacker,
                        'stun_remaining': stun_remaining,
                        'minion_index': attacker_index,
                        'is_enemy': True
                    }
                    context = {'combat_state': combat_state}
                    success, logs, changes = process_stun_skip(action_data, context)

                    if success:
                        combat_state['combat_log'].extend(logs)
                        CombatSystem._add_action_command(combat_state, 'stun_skip', action_data, changes, logs)

                    remaining_stun = reduce_stun(attacker)
                    if remaining_stun == 0:
                        combat_state['combat_log'].append(f"✅ Enemy {attacker['name']} is no longer stunned!")

                else:
                    should_process, has_combat_tricks = CombatSystem._should_process_attack(attacker)

                    if not should_process:
                        reason = 'cant_attack' if has_keyword(attacker, 'cant_attack') else 'zero_attack'
                        action_data = {
                            'minion': attacker,
                            'reason': reason,
                            'minion_index': attacker_index,
                            'is_enemy': True
                        }
                        context = {'combat_state': combat_state}
                        success, logs, changes = process_no_attack_skip(action_data, context)

                        if success:
                            combat_state['combat_log'].extend(logs)
                            CombatSystem._add_action_command(combat_state, 'no_attack_skip', action_data, changes, logs)
                    else:
                        alive_player_band = [m for m in player_band if m.get('health', 0) > 0]
                        target = select_combat_target(attacker, alive_player_band)

                        if target:
                            skip_damage = (has_keyword(attacker, 'cant_attack') or attacker.get('attack', 0) <= 0)

                            CombatSystem._execute_attack_with_triggers(
                                attacker, target, attacker_index,
                                combat_state, run, registry,
                                skip_damage=skip_damage
                            )

                            if (attacker.get('attack', 0) > 0 and
                                not is_stunned(attacker) and
                                not has_keyword(attacker, 'cant_attack')):
                                additional_attacks = CombatSystem._queue_multi_attacks(attacker, combat_state)
                                if additional_attacks > 0:
                                    combat_state['combat_log'].append(f"⚔️ Enemy {attacker['name']} will attack {additional_attacks} more time(s)!")

                        else:
                            if has_combat_tricks:
                                if 'combat_log' not in combat_state:
                                    combat_state['combat_log'] = []
                                combat_state['combat_log'].append(f"🔮 Enemy {attacker['name']} #{attacker_index + 1} has no targets but uses abilities")

                                CombatSystem._execute_attack_with_triggers(
                                    attacker, None, attacker_index,
                                    combat_state, run, registry,
                                    skip_damage=True
                                )

            # Handle turn advancement
            final_enemy_count = len([m for m in enemy_band if m.get('health', 0) > 0])
            if final_enemy_count != initial_enemy_count:
                combat_state['deaths_this_turn'] = True

            if len(enemy_band) != combat_state.get('original_enemy_count', len(enemy_band)):
                combat_state['summons_this_turn'] = True
                combat_state['original_enemy_count'] = len(enemy_band)

            band_changed = CombatSystem._detect_band_composition_change(combat_state)

            if band_changed:
                CombatSystem._advance_turn_order_after_band_change(
                    combat_state, is_player_turn, original_attacker_position, len(enemy_band)
                )
            else:
                if len(enemy_band) > 0:
                    combat_state['current_enemy_unit'] = (attacker_index + 1) % len(enemy_band)
                else:
                    combat_state['current_enemy_unit'] = 0

        # Switch turns (with hero effect check for extra starting turns)
        should_switch = True
        if is_player_turn and combat_state.get('hero_extra_starting_turns', 0) > 0:
            # Player hero effect: extra starting turns
            remaining = combat_state['hero_extra_starting_turns'] - 1
            combat_state['hero_extra_starting_turns'] = remaining
            should_switch = False
            combat_state['combat_log'].append(f"🦸 Puck's power activates! Player gets another turn!")
            _debug(f"[COMBAT] Hero effect: Player gets another turn ({remaining} extra turns remaining)")
        elif not is_player_turn and combat_state.get('enemy_hero_extra_starting_turns', 0) > 0:
            # Enemy (ghost) hero effect: extra starting turns
            remaining = combat_state['enemy_hero_extra_starting_turns'] - 1
            combat_state['enemy_hero_extra_starting_turns'] = remaining
            should_switch = False
            combat_state['combat_log'].append(f"👻 Ghost Puck's power activates! Enemy gets another turn!")
            _debug(f"[COMBAT] Enemy hero effect: Enemy gets another turn ({remaining} extra turns remaining)")

        if should_switch:
            combat_state['player_turn'] = not is_player_turn

        # Increment round
        current_enemy_unit = combat_state.get('current_enemy_unit', 0)
        if not is_player_turn and current_enemy_unit == 0:
            combat_state['round_number'] = combat_state.get('round_number', 1) + 1

        combat_state['player_band'] = player_band
        combat_state['enemy_band'] = enemy_band

        CombatSystem._check_combat_end_after_triggers(combat_state)
        combat_state['combat_registry_data'] = registry.to_dict()
        CombatSystem._add_ui_display_data(combat_state)

        return combat_state

    @staticmethod
    def _execute_attack_with_triggers(attacker, defender, attacker_index,
                                      combat_state=None, run=None, registry=None, skip_damage=False):
        """
        Execute a single attack using registry-based combat actions

        REGISTRY-DRIVEN: All combat damage goes through combat action handlers
        """
        _debug(
            f"[DEBUG] === Executing attack: {attacker['name']} -> {defender['name'] if defender else 'No Target'} ===")

        # REGISTRY-BASED: Use process_declare_attack handler (only if defender exists)
        if defender:
            action_data = {
                'attacker': attacker,
                'defender': defender,
                'attacker_index': attacker_index
            }
            context = {'combat_state': combat_state}
            success, logs, changes = process_declare_attack(action_data, context)

            if success:
                combat_state['combat_log'].extend(logs)
                CombatSystem._add_action_command(combat_state, 'declare_attack', action_data, changes, logs)

        # Get trigger processor
        processor = CombatSystem._get_trigger_processor()

        if combat_state is None:
            combat_state = {}

        combat_log = combat_state.get('combat_log', [])

        if 'attack_count' not in combat_state:
            combat_state['attack_count'] = 0
        if 'fatigue_active' not in combat_state:
            combat_state['fatigue_active'] = False
        if 'fatigue_attacks' not in combat_state:
            combat_state['fatigue_attacks'] = 0

        combat_state['attack_count'] += 1

        # Fatigue handling (simplified)
        if combat_state['attack_count'] >= 40 and not combat_state['fatigue_active']:
            combat_state['fatigue_active'] = True
            combat_log.append("💀⚡ Combat fatigue begins!")

        actual_player_band = combat_state.get('player_band', [])
        actual_enemy_band = combat_state.get('enemy_band', [])

        # Initialize processor
        processor.initialize_combat(
            combat_state=combat_state,
            player_band=actual_player_band,
            enemy_band=actual_enemy_band,
            registry=registry,
            run=run
        )

        processor.context_manager.combat_state = combat_state

        # Add initial triggers (assault/cast/rage)
        processor.add_initial_triggers(attacker, defender)

        # Resolve triggers
        cast_used = [False]
        trigger_logs = processor.resolve_all_triggers(cast_used)
        combat_log.extend(trigger_logs)

        # Check deaths/summons
        if any(minion.get('health', 0) <= 0 for minion in actual_player_band + actual_enemy_band):
            combat_state['deaths_this_turn'] = True

        if len(actual_player_band) > combat_state.get('original_player_count', len(actual_player_band)):
            combat_state['summons_this_turn'] = True
        if len(actual_enemy_band) > combat_state.get('original_enemy_count', len(actual_enemy_band)):
            combat_state['summons_this_turn'] = True

        # Check if attacker died
        if not attacker or attacker.get('health', 0) <= 0:
            # REGISTRY-BASED: Use process_attack_cancelled handler
            action_data = {
                'attacker': attacker,
                'reason': 'attacker_died',
                'attacker_index': attacker_index
            }
            context = {'combat_state': combat_state}
            success, logs, changes = process_attack_cancelled(action_data, context)

            if success:
                combat_state['combat_log'].extend(logs)
                CombatSystem._add_action_command(combat_state, 'attack_cancelled', action_data, changes, logs)
            return

        # Check if defender died (only if we have a defender)
        if defender and (not defender or defender.get('health', 0) <= 0):
            # REGISTRY-BASED: Use process_attack_cancelled handler
            action_data = {
                'attacker': attacker,
                'defender': defender,  # Include defender for animation targeting
                'reason': 'defender_died',
                'cast_used': cast_used[0],
                'attacker_index': attacker_index
            }
            context = {'combat_state': combat_state}
            success, logs, changes = process_attack_cancelled(action_data, context)

            if success:
                combat_state['combat_log'].extend(logs)
                CombatSystem._add_action_command(combat_state, 'attack_cancelled', action_data, changes, logs)
            return

        # Combat Damage Phase
        if cast_used[0]:
            # REGISTRY-BASED: Use process_cast_finished handler
            action_data = {
                'caster': attacker,
                'caster_index': attacker_index
            }
            context = {'combat_state': combat_state}
            success, logs, changes = process_cast_finished(action_data, context)

            if success:
                combat_state['combat_log'].extend(logs)
                CombatSystem._add_action_command(combat_state, 'cast_finished', action_data, changes, logs)

        elif skip_damage:
            # No damage phase
            pass
        elif not defender:
            # No defender
            pass
        else:
            # REGISTRY-BASED: Use process_combat_damage handler with CLEAVE support
            base_damage = attacker['attack']
            base_counter = defender['attack']
            has_poke = has_keyword(attacker, 'poke')  # HARDCODED - NEEDS TO BE REMOVED
            defender_cant_retaliate = has_keyword(defender, 'cant_retaliate')

            # NEW: Check for cleave - HARDCODED - NEEDS TO BE REMOVED
            has_cleave = has_keyword(attacker, 'cleave')
            cleave_amount = attacker.get('cleave_amount', 1) if has_cleave else 0

            action_data = {
                'attacker': attacker,
                'defender': defender,
                'base_damage': base_damage,
                'base_counter': base_counter,
                'has_poke': has_poke,  # HARDCODED - NEEDS TO BE REMOVED
                'defender_cant_retaliate': defender_cant_retaliate,
                'attacker_index': attacker_index,
                'has_cleave': has_cleave,  # HARDCODED - NEEDS TO BE REMOVED
                'cleave_amount': cleave_amount  # HARDCODED - NEEDS TO BE REMOVED
            }

            context = {
                'combat_state': combat_state,
                'registry': registry,
                'trigger_processor': processor,
                'registrar': processor.registrar,  # For hero effects that trigger on_any_leap
                'absolute_player_band': actual_player_band,
                'absolute_enemy_band': actual_enemy_band,
                'combat_registry': registry,
                'run': run,
                'interpreter': combat_state.get('interpreter')  # CRITICAL FIX: For Olimpia commands
            }

            success, logs, changes = process_combat_damage(action_data, context)

            if success:
                combat_state['combat_log'].extend(logs)
                CombatSystem._add_action_command(combat_state, 'combat_damage', action_data, changes, logs)

        # Final death check
        final_trigger_logs = processor.resolve_all_triggers()
        combat_log.extend(final_trigger_logs)

    @staticmethod
    def _apply_damage_modifiers(attacker, defender, base_counter_damage):
        """Apply damage modification keywords"""
        actual_counter_damage = base_counter_damage

        if has_keyword(attacker, 'poke'):
            actual_counter_damage = 0

        if has_keyword(defender, 'cant_retaliate'):
            actual_counter_damage = 0

        return actual_counter_damage

    @staticmethod
    def create_initial_combat_state(player_band, enemy_band, run=None, enemy_hero_effects=None):
        """Create the initial combat state"""
        from minions import prepare_band_for_combat, get_minion_by_name

        working_player_band = []
        for minion in player_band or []:
            combat_minion = copy.deepcopy(minion)
            if 'band_id' in minion:
                combat_minion['band_id'] = minion['band_id']

            # ALWAYS merge with template to ensure complete data for consistent tooltips
            # This ensures ALL template fields are present (effects, hide_count, leap_distance, etc.)
            template = get_minion_by_name(combat_minion['name'])
            if template:
                # Template provides base data, combat_minion overrides with runtime state
                combat_minion = {**template, **combat_minion}

            working_player_band.append(combat_minion)

        working_enemy_band = []
        for minion in enemy_band or []:
            combat_minion = copy.deepcopy(minion)

            # ALWAYS merge with template to ensure complete data
            template = get_minion_by_name(combat_minion['name'])
            if template:
                combat_minion = {**template, **combat_minion}

            working_enemy_band.append(combat_minion)

        registry = CombatRegistry()
        registry.register_band(working_player_band, 'player')
        registry.register_band(working_enemy_band, 'enemy')

        prepare_band_for_combat(working_player_band)
        prepare_band_for_combat(working_enemy_band)

        interpreter = CombatInterpreter()
        interpreter.initialize(working_player_band, working_enemy_band)

        combat_state = {
            'combat_over': False,
            'winner': None,
            'player_band': working_player_band,
            'enemy_band': working_enemy_band,
            'initial_enemy_band': copy.deepcopy(working_enemy_band),
            'combat_registry_data': registry.to_dict(),
            'player_turn': True,
            'current_player_unit': 0,
            'current_enemy_unit': 0,
            'round_number': 1,
            'combat_log': [],
            'attack_count': 0,
            'fatigue_active': False,
            'fatigue_attacks': 0,
            'multi_attack_queue': [],
            'interpreter': interpreter,
            'deaths_this_turn': False,
            'summons_this_turn': False,
            'original_player_count': len(working_player_band),
            'original_enemy_count': len(working_enemy_band)
        }

        # FIXED: Use registrar-based start of combat processing
        combat_state = CombatSystem._process_start_of_combat_triggers(combat_state, registry, run)

        # Apply player hero effects (e.g., Puck's extra starting turns)
        if run:
            hero_effects = run.get_hero_effects()
            if 'extra_starting_turns' in hero_effects:
                base_extra_turns = hero_effects['extra_starting_turns']
                extra_turns = get_scaled_effect_value(hero_effects, 'extra_starting_turns', base_extra_turns)
                combat_state['hero_extra_starting_turns'] = extra_turns
                total_minions = 1 + extra_turns
                combat_state['combat_log'].append(f"🦸 Hero Effect - Puck: First {total_minions} minions attack before enemy!")
                _debug(f"[COMBAT] Hero effect: First {total_minions} minions will attack before enemy")

        # Apply enemy hero effects (ghost battles - the ghost's hero power)
        if enemy_hero_effects:
            if 'extra_starting_turns' in enemy_hero_effects:
                base_extra_turns = enemy_hero_effects['extra_starting_turns']
                extra_turns = get_scaled_effect_value(enemy_hero_effects, 'extra_starting_turns', base_extra_turns)
                combat_state['enemy_hero_extra_starting_turns'] = extra_turns
                total_minions = 1 + extra_turns
                combat_state['combat_log'].append(f"👻 Ghost Hero - Puck: First {total_minions} enemy minions attack before player!")
                _debug(f"[COMBAT] Enemy hero effect: First {total_minions} enemy minions will attack before player")

        CombatSystem._add_ui_display_data(combat_state)

        return combat_state

    @staticmethod
    def _has_start_of_combat_trigger(minion: Dict) -> bool:
        """
        Check if minion has any start_of_combat trigger

        Checks for:
        1. Explicit start_of_combat_effect field
        2. Keywords that grant start_of_combat effects (rich, aura, divide_attack, fast, ring)

        This matches the registrar's logic in _register_self_trigger
        """
        # Check for explicit effect field
        if 'start_of_combat_effect' in minion:
            return True

        # Check for keywords that grant start_of_combat effects
        keywords_with_start_effects = ['rich', 'aura', 'divide_attack', 'fast', 'ring']
        for keyword in keywords_with_start_effects:
            if has_keyword(minion, keyword):
                return True

        return False

    @staticmethod
    def _create_alternating_start_of_combat_order(player_band: List[Dict], enemy_band: List[Dict]) -> List[Dict]:
        """
        Create alternating list of minions with start_of_combat effects

        FIXED: Now properly checks for keywords (fast, rich, aura, divide_attack, ring) in addition to explicit effects
        FIXED: Uses proper alternating order with player preference

        Algorithm:
        1. Find all minions with start_of_combat triggers from each band (sorted by position)
        2. Determine who starts: compare leftmost from each side, player preference on tie
        3. Alternate taking from each side until both lists empty

        Args:
            player_band: Player's minions
            enemy_band: Enemy's minions

        Returns:
            Alternating list of minions with start_of_combat effects
        """
        # Get minions with triggers (explicit field OR keywords), sorted by position
        player_effects = [
            m for m in sorted(player_band, key=lambda x: x.get('position', 0))
            if m.get('health', 0) > 0 and CombatSystem._has_start_of_combat_trigger(m)
        ]

        enemy_effects = [
            m for m in sorted(enemy_band, key=lambda x: x.get('position', 0))
            if m.get('health', 0) > 0 and CombatSystem._has_start_of_combat_trigger(m)
        ]

        _debug(f"[START_OF_COMBAT] Player triggers: {len(player_effects)}, Enemy triggers: {len(enemy_effects)}")
        for p in player_effects:
            _debug(f"[START_OF_COMBAT]   Player: {p.get('name')} at pos {p.get('position')}")
        for e in enemy_effects:
            _debug(f"[START_OF_COMBAT]   Enemy: {e.get('name')} at pos {e.get('position')}")

        if not player_effects and not enemy_effects:
            return []

        # Determine who starts
        if player_effects and enemy_effects:
            player_pos = player_effects[0].get('position', 0)
            enemy_pos = enemy_effects[0].get('position', 0)

            # Enemy starts only if they're more left AND player has none at that position
            # Otherwise player starts (player preference)
            if enemy_pos < player_pos:
                current_side = 'enemy'
                _debug(f"[START_OF_COMBAT] Enemy starts (pos {enemy_pos} < {player_pos})")
            else:
                current_side = 'player'
                _debug(f"[START_OF_COMBAT] Player starts (pos {player_pos} >= {enemy_pos} or player preference)")
        elif player_effects:
            current_side = 'player'
            _debug(f"[START_OF_COMBAT] Player starts (only player has triggers)")
        else:
            current_side = 'enemy'
            _debug(f"[START_OF_COMBAT] Enemy starts (only enemy has triggers)")

        # Alternate taking from each side
        result = []
        player_index = 0
        enemy_index = 0

        while player_index < len(player_effects) or enemy_index < len(enemy_effects):
            if current_side == 'player':
                if player_index < len(player_effects):
                    minion = player_effects[player_index]
                    result.append(minion)
                    _debug(f"[START_OF_COMBAT] Added player {minion.get('name')} at position {minion.get('position')}")
                    player_index += 1
                # Switch sides
                current_side = 'enemy'
            else:  # enemy
                if enemy_index < len(enemy_effects):
                    minion = enemy_effects[enemy_index]
                    result.append(minion)
                    _debug(f"[START_OF_COMBAT] Added enemy {minion.get('name')} at position {minion.get('position')}")
                    enemy_index += 1
                # Switch sides
                current_side = 'player'

        return result

    @staticmethod
    def _process_start_of_combat_triggers(combat_state: Dict, registry: CombatRegistry, run=None) -> Dict:
        """
        Process all start_of_combat effects using registrar

        FIXED: Now properly checks for keywords (fast, rich, aura, divide_attack)
        FIXED: Uses proper alternating order with player preference
        """
        player_band = combat_state.get('player_band', [])
        enemy_band = combat_state.get('enemy_band', [])

        # Create alternating list with proper ordering (includes keyword checks)
        alternating_minions = CombatSystem._create_alternating_start_of_combat_order(player_band, enemy_band)

        if not alternating_minions:
            _debug(f"[START_OF_COMBAT] No minions with start_of_combat triggers")
            return combat_state

        _debug(f"[START_OF_COMBAT] Processing {len(alternating_minions)} triggers in alternating order")

        # Get trigger processor and initialize
        processor = CombatSystem._get_trigger_processor()
        processor.initialize_combat(
            combat_state=combat_state,
            player_band=player_band,
            enemy_band=enemy_band,
            registry=registry,
            run=run
        )

        combat_state['run'] = run

        # Use registrar to register triggers in the correct order
        registrar = processor.registrar
        if registrar:
            registrar.register_start_of_combat_triggers(alternating_minions)
            _debug(f"[START_OF_COMBAT] Registered {len(alternating_minions)} triggers via registrar")
        else:
            logger.error(f"[START_OF_COMBAT ERROR] No registrar available!")
            return combat_state

        # Resolve all triggers
        trigger_logs = processor.resolve_all_triggers()

        if 'combat_log' not in combat_state:
            combat_state['combat_log'] = []
        combat_state['combat_log'].extend(trigger_logs)

        _debug(f"[START_OF_COMBAT] Completed processing, generated {len(trigger_logs)} log entries")

        return combat_state

    @staticmethod
    def resolve_combat(player_band, enemy_band, max_rounds=50, run=None, enemy_hero_effects=None):
        """Resolve a complete combat"""
        combat_state = CombatSystem.create_initial_combat_state(player_band, enemy_band, run, enemy_hero_effects=enemy_hero_effects)

        while not combat_state.get('combat_over', False) and combat_state.get('round_number', 1) <= max_rounds:
            try:
                combat_state = CombatSystem.process_combat_step(combat_state, run)

                if combat_state.get('attack_count', 0) >= 200 or combat_state.get('turn_count', 0) >= 500:
                    # Ensure winner is determined before breaking
                    if combat_state.get('winner') is None:
                        combat_state['combat_over'] = True
                        alive_p = [m for m in combat_state.get('player_band', []) if m.get('health', 0) > 0]
                        alive_e = [m for m in combat_state.get('enemy_band', []) if m.get('health', 0) > 0]
                        if len(alive_p) > len(alive_e):
                            combat_state['winner'] = 'player'
                        elif len(alive_e) > len(alive_p):
                            combat_state['winner'] = 'enemy'
                        else:
                            combat_state['winner'] = 'draw'
                    break

            except Exception as e:
                logger.error(f"Error in combat step: {e}")
                import traceback
                traceback.print_exc()
                combat_state['combat_over'] = True
                combat_state['winner'] = 'draw'
                combat_state['combat_log'] = combat_state.get('combat_log', []) + [f"Combat error: {str(e)}"]
                break

        if combat_state.get('round_number', 1) > max_rounds and not combat_state.get('combat_over', False):
            combat_state['combat_over'] = True

            alive_player_band = [m for m in combat_state.get('player_band', []) if m.get('health', 0) > 0]
            alive_enemy_band = [m for m in combat_state.get('enemy_band', []) if m.get('health', 0) > 0]

            player_count = len(alive_player_band)
            enemy_count = len(alive_enemy_band)

            if player_count > enemy_count:
                combat_state['winner'] = 'player'
                combat_state['combat_log'].append(f"⏰ Round limit!")
            elif enemy_count > player_count:
                combat_state['winner'] = 'enemy'
                combat_state['combat_log'].append(f"⏰ Round limit!")
            else:
                combat_state['winner'] = 'draw'
                combat_state['combat_log'].append(f"⏰ Round limit!")

        # Finalize interpreter
        interpreter_data = None
        if 'interpreter' in combat_state:
            interpreter = combat_state['interpreter']
            combat_result = {
                'winner': combat_state.get('winner') or 'draw',
                'rounds': combat_state.get('round_number', 1),
                'attacks': combat_state.get('attack_count', 0),
                'player_band': combat_state.get('player_band', []),
                'enemy_band': combat_state.get('enemy_band', [])
            }
            interpreter_data = interpreter.finalize_combat(combat_result)

        surviving_player = [m for m in combat_state.get('player_band', []) if m.get('health', 0) > 0]
        surviving_enemy = [m for m in combat_state.get('enemy_band', []) if m.get('health', 0) > 0]

        # Ensure winner is never None (safety net)
        winner = combat_state.get('winner')
        if winner is None:
            if len(surviving_player) > len(surviving_enemy):
                winner = 'player'
            elif len(surviving_enemy) > len(surviving_player):
                winner = 'enemy'
            else:
                winner = 'draw'

        return {
            'winner': winner,
            'rounds': combat_state.get('round_number', 1),
            'attacks': combat_state.get('attack_count', 0),
            'fatigue_active': combat_state.get('fatigue_active', False),
            'player_band': combat_state.get('player_band', []),
            'enemy_band': combat_state.get('enemy_band', []),
            'initial_enemy_band': combat_state.get('initial_enemy_band', []),
            'surviving_player': surviving_player,
            'surviving_enemy': surviving_enemy,
            'combat_log': combat_state.get('combat_log', []),
            'ui_data': combat_state.get('ui_data', {}),
            'interpreter_data': interpreter_data
        }

    @staticmethod
    def _reset_band_health(band):
        """Reset all minion health to full"""
        from minions import get_minion_by_name

        for minion in band:
            original_template = get_minion_by_name(minion['name'])
            if original_template:
                base_health = original_template['health']
                # Golden minions have doubled base stats
                if minion.get('golden'):
                    base_health *= 2
                permanent_health = minion.get('permanent_health', 0)
                minion['health'] = base_health + permanent_health
            else:
                permanent_health = minion.get('permanent_health', 0)
                minion['health'] = max(1, permanent_health)

            minion['stun_count'] = 0
            if 'stun' in minion.get('keywords', []):
                minion['keywords'].remove('stun')

    @staticmethod
    def resolve_combat_selection(run, selection_id):
        """Resolve combat selection"""
        from minions import prepare_band_for_combat

        pending = run.get_pending_selection()
        if not pending or pending.get('event_type') not in ('combat', 'boss_combat'):
            return {'error': 'No pending combat'}

        # Optimistic lock: prevent concurrent combat resolution
        if selection_id in ('end', 'next', 'auto'):
            from models import db
            from sqlalchemy import text
            expected_version = run.selection_version or 0
            rows = db.session.execute(
                text("UPDATE runs SET selection_version = selection_version + 1 "
                     "WHERE id = :id AND selection_version = :ver"),
                {'id': run.id, 'ver': expected_version}
            ).rowcount
            if rows == 0:
                return {'error': 'Selection already processed'}
            run.selection_version = expected_version + 1

        if selection_id == 'continue':
            # Check if there's a next event to chain to based on combat result
            combat_state = pending.get('combat_state', {})
            winner = combat_state.get('winner')

            next_event_id = None
            if winner == 'player':
                next_event_id = pending.get('on_victory_event')
            elif winner == 'enemy':
                next_event_id = pending.get('on_defeat_event')

            # Clear combat selection
            run.set_pending_selection(None)

            # Chain to next event if specified
            if next_event_id:
                from game_engine.events.event_system import EventSystem
                # Set back context for the chained event - combat victories don't have refunds
                event_state = run.get_event_state()
                event_state['pending_back_label'] = 'End event'
                event_state['pending_back_refund'] = 0
                run.set_event_state(event_state)
                EventSystem.create_event_selection(run, next_event_id)
                return {
                    'success': True,
                    'combat_continue': True,
                    'message': f'Combat complete. Transitioning to {next_event_id}...',
                    'results': ['Combat complete', f'Transitioning to {next_event_id}...'],
                    'band_changes': [],
                    'resource_changes': {}
                }

            return {
                'success': True,
                'combat_continue': True,
                'message': 'Combat complete',
                'results': ['Combat complete'],
                'band_changes': [],
                'resource_changes': {}
            }

        # Check if we already have interpreter data (combat already resolved)
        if 'interpreter_data' in pending:
            _debug("[COMBAT] Using existing interpreter_data, not re-running combat")
            interpreter_data = pending['interpreter_data']

            # Get initial state from interpreter data
            initial_state = interpreter_data.get('initial_state', {})
            initial_player_band = initial_state.get('player_band', [])
            initial_enemy_band = initial_state.get('enemy_band', [])

            # Find the END command to get the winner and final bands
            commands = interpreter_data.get('commands', [])
            winner = 'draw'
            final_player_band = initial_player_band
            final_enemy_band = initial_enemy_band

            for cmd in reversed(commands):
                if cmd.get('cmd') == 'END':
                    winner = cmd.get('winner', 'draw')
                    final_player_band = cmd.get('final_player_band', initial_player_band)
                    final_enemy_band = cmd.get('final_enemy_band', initial_enemy_band)
                    break

            message = f"⚔️ Combat ready - {winner} wins!"

            # Build battle_result dict for _apply_combat_results
            battle_result = {
                'winner': winner,
                'player_band': final_player_band,
                'enemy_band': final_enemy_band,
                'initial_enemy_band': initial_enemy_band,
                'combat_log': []  # Not available from pre-generated data
            }

            # Apply combat results (handles ghost battles, resource changes, etc.)
            resource_changes = CombatSystem._apply_combat_results(
                run,
                battle_result,
                pending.get('combat_type', 'unknown'),
                pending
            )

            # Mark combat as complete
            pending['combat_complete'] = True
            pending['message'] = message

            run.set_pending_selection(pending)

            return {
                'success': True,
                'combat_complete': True,
                'combat_result': winner,
                'message': message,
                'results': [message],
                'band_changes': [],
                'resource_changes': resource_changes,
                'interpreter_data': interpreter_data,
                'selection_mode': selection_id
            }

        # Legacy path: No interpreter data, need to run combat
        if 'combat_state' in pending:
            combat_state = pending['combat_state']
            player_band = combat_state.get('player_band', [])
            enemy_band = combat_state.get('enemy_band', [])
        else:
            player_band = run.get_band()
            enemy_band = pending.get('enemy_band', [])

        try:
            battle_result = CombatSystem.resolve_combat(player_band, enemy_band, run=run)

            if selection_id == 'next':
                message = f"🎮 Combat ready - {battle_result['winner']} wins!"
            elif selection_id == 'auto':
                message = f"⚡ Combat ready - {battle_result['winner']} wins!"
            elif selection_id == 'end':
                message = f"⏭️ Combat complete - {battle_result['winner']} wins!"
            else:
                message = f"⚔️ Combat complete - {battle_result['winner']} wins!"

            final_state = {
                'combat_over': True,
                'winner': battle_result['winner'],
                'combat_log': battle_result.get('combat_log', []),
                'player_band': battle_result['player_band'],
                'enemy_band': battle_result['enemy_band'],
                'attack_count': battle_result.get('attacks', 0),
                'fatigue_active': battle_result.get('fatigue_active', False),
                'player_turn': False,
                'round_number': battle_result.get('rounds', 1),
                'ui_data': battle_result.get('ui_data', {})
            }

            resource_changes = CombatSystem._apply_combat_results(run, battle_result, pending.get('combat_type', 'unknown'), pending)

            pending['combat_complete'] = True
            pending['combat_state'] = final_state
            pending['message'] = message

            interpreter_data = battle_result.get('interpreter_data')
            if interpreter_data:
                pending['interpreter_data'] = interpreter_data

            run.set_pending_selection(pending)

            return {
                'success': True,
                'combat_complete': True,
                'combat_result': battle_result['winner'],
                'message': message,
                'results': [message],
                'band_changes': [],
                'resource_changes': resource_changes,
                'combat_state': final_state,
                'interpreter_data': interpreter_data,
                'selection_mode': selection_id
            }

        except Exception as e:
            logger.error(f"Error in combat: {e}")
            import traceback
            traceback.print_exc()
            return {'error': f'Combat failed: {str(e)}'}

    @staticmethod
    def _calculate_player_damage(enemy_band):
        """Calculate damage to player from alive enemy minions (excluding summons/tokens)"""
        damage = 0
        for enemy in enemy_band:
            # Only count alive enemies that are not summons/tokens
            if enemy.get('health', 0) > 0 and enemy.get('rarity') != 'token':
                tier = enemy.get('tier', 1)
                damage += tier
        return damage

    @staticmethod
    def _apply_combat_results(run, battle_result, combat_type, pending_selection=None):
        """Apply combat results"""
        # Check if this is a duel - duels use a copy of the champion, so don't reset the whole band
        is_duel = pending_selection.get('is_duel', False) if pending_selection else False

        # Get the band once and work with it
        band = run.get_band()

        if RESET_HEALTH_AFTER_COMBAT and not is_duel:
            CombatSystem._reset_band_health(band)
            # Save the band after resetting health
            run.set_band(band)

        winner = battle_result['winner']
        resource_changes = {}

        # Ghost battles have special reward/penalty rules
        if combat_type == 'ghost_battle' or combat_type == 'ghost_battle_early':
            if winner == 'player':
                # Player wins ghost battle - no gold reward
                pass
            else:
                # Player loses ghost battle - take damage but no gold loss
                final_enemy_band = battle_result.get('enemy_band', [])
                damage = CombatSystem._calculate_player_damage(final_enemy_band)

                # Apply damage to player health
                run.health = max(0, run.health - damage)

                # Note: Don't mark run.is_active = False here
                # The run will be marked inactive by the /end endpoint after the end screen is shown
                # This allows the frontend to complete the flow without "Run not found or inactive" errors

                resource_changes['health'] = -damage

            # Record the ghost battle completion
            from database import record_ghost_battle, pre_generate_ghost_opponent_for_milestone
            from models import GhostSnapshot

            # Get the ghost ID from pending selection
            ghost_id = pending_selection.get('ghost_id') if pending_selection else None
            if ghost_id:
                ghost = GhostSnapshot.query.get(ghost_id)
                if ghost:
                    # Record the battle (winner is 'player' or 'enemy', convert 'enemy' to 'ghost')
                    battle_winner = 'player' if winner == 'player' else 'ghost'
                    record_ghost_battle(run, ghost, battle_winner, battle_result.get('combat_log', []))

                    # Clear the current upcoming ghost
                    run.upcoming_ghost_id = None

                    # For early fights, generate next ghost at milestone AFTER the one just defeated
                    # DON'T advance events_count - player stays at current position with more steps available
                    if combat_type == 'ghost_battle_early':
                        original_milestone = pending_selection.get('original_milestone') if pending_selection else None
                        _debug(f"[EARLY GHOST DEBUG] Early ghost battle won! events_count={run.events_count}, original_milestone={original_milestone}")
                        if original_milestone:
                            # DON'T change events_count - player stays at current position
                            # Generate ghost for the milestone AFTER the one we just fought
                            from config import EVENTS_FOR_GHOST_BATTLE
                            next_milestone = original_milestone + EVENTS_FOR_GHOST_BATTLE
                            _debug(f"[EARLY GHOST DEBUG] Staying at event {run.events_count}, generating next ghost for milestone {next_milestone}")
                            pre_generate_ghost_opponent_for_milestone(run, next_milestone)
                            _debug(f"[EARLY GHOST DEBUG] After ghost gen, upcoming_ghost_id={run.upcoming_ghost_id}, steps available: {next_milestone - run.events_count}")
                        else:
                            # Fallback to normal generation
                            pre_generate_ghost_opponent_for_milestone(run, None)
                    else:
                        # Regular ghost battle - generate for next milestone
                        pre_generate_ghost_opponent_for_milestone(run, None)

        # Boss combat handling - save persistent damage
        elif combat_type == 'boss_combat':
            # Save persistent damage for boss minions
            persistent_damage_key = pending_selection.get('persistent_damage_key') if pending_selection else None
            if persistent_damage_key:
                initial_enemy_band = battle_result.get('initial_enemy_band', [])
                final_enemy_band = battle_result.get('enemy_band', [])
                event_state = run.get_event_state()

                # Get existing persistent damage
                persistent_damage = event_state.get(persistent_damage_key, {})

                # Calculate damage taken by each boss minion
                for initial_enemy in initial_enemy_band:
                    enemy_name = initial_enemy.get('name')
                    enemy_pos = initial_enemy.get('position', -1)
                    initial_health = initial_enemy.get('health', 0)

                    # Find the same minion in final band
                    final_enemy = None
                    for e in final_enemy_band:
                        if e.get('name') == enemy_name and e.get('position') == enemy_pos:
                            final_enemy = e
                            break

                    # Calculate damage taken (or if dead, full damage)
                    if final_enemy is None or final_enemy.get('health', 0) <= 0:
                        # Minion died - track full damage (initial health)
                        damage_taken = initial_health
                    else:
                        # Minion survived - track damage taken (initial - final)
                        final_health = final_enemy.get('health', 0)
                        damage_taken = initial_health - final_health

                    # Add to persistent damage (not replace - accumulate)
                    if damage_taken > 0:
                        existing_damage = persistent_damage.get(enemy_name, 0)
                        persistent_damage[enemy_name] = existing_damage + damage_taken
                        _debug(f"[BOSS] {enemy_name} took {damage_taken} damage (total persistent: {persistent_damage[enemy_name]})")

                # Save updated persistent damage
                event_state[persistent_damage_key] = persistent_damage
                run.set_event_state(event_state)

            # Boss combat doesn't give gold rewards or deal player damage on loss
            # Victory rewards are handled by the on_victory_event chain
            if winner == 'enemy':
                # On boss defeat, player doesn't lose health but combat ends
                # They can try again later
                resource_changes['message'] = 'The boss defeated you! It retains its damage for next time.'

        else:
            # Regular combat rewards/penalties
            if winner == 'player':
                initial_enemy_band = battle_result.get('initial_enemy_band', [])
                final_enemy_band = battle_result.get('enemy_band', [])

                gold_reward = 0
                for enemy in initial_enemy_band:
                    enemy_name = enemy.get('name')
                    enemy_pos = enemy.get('position', -1)

                    final_enemy = None
                    for e in final_enemy_band:
                        if e.get('name') == enemy_name and e.get('position') == enemy_pos:
                            final_enemy = e
                            break

                    enemy_died = (final_enemy is None or final_enemy.get('health', 0) <= 0)

                    if enemy_died:
                        if enemy.get('rarity') != 'token':
                            tier = enemy.get('tier', 1)
                            gold_reward += tier

                            # Check for bounty mark - award extra gold if this enemy type matches
                            event_state = run.get_event_state()
                            bounty_mark = event_state.get('bounty_mark')
                            if bounty_mark and bounty_mark.get('minion_name') == enemy_name:
                                bounty_gold = bounty_mark.get('gold_reward', 5)
                                gold_reward += bounty_gold

                # Check if gold rewards should be disabled for this combat
                disable_gold = pending_selection.get('disable_gold_reward', False) if pending_selection else False

                if not disable_gold:
                    # Check for double gold bounty from Great Hunt
                    event_state = run.get_event_state()
                    if event_state.get('double_gold_next_combat'):
                        gold_reward *= 2
                        event_state['double_gold_next_combat'] = False
                        run.set_event_state(event_state)
                        resource_changes['bounty_bonus'] = 'Double gold from bounty!'

                    resources = run.get_resources()
                    resources['gold'] += gold_reward
                    run.set_resources(resources)
                    resource_changes['gold'] = gold_reward

                # Apply duel victory buff if this was a duel
                if is_duel:
                    event_state = run.get_event_state()
                    champion_index = event_state.get('champion_index')
                    buff_per_tier = event_state.get('duel_buff_per_tier', 3)
                    tier = run.current_ring
                    buff_amount = buff_per_tier * tier

                    if champion_index is not None:
                        # Re-get band in case it changed (use local band variable)
                        if champion_index < len(band):
                            champion = band[champion_index]
                            champion['health'] = champion.get('health', 0) + buff_amount
                            champion['attack'] = champion.get('attack', 0) + buff_amount
                            champion['permanent_health'] = champion.get('permanent_health', 0) + buff_amount
                            champion['permanent_attack'] = champion.get('permanent_attack', 0) + buff_amount
                            resource_changes['duel_buff'] = f"{champion['name']} gained +{buff_amount}/+{buff_amount}!"
                            # Save the band with duel buff applied
                            run.set_band(band)

                    # Clear duel state
                    event_state.pop('champion_index', None)
                    event_state.pop('duel_buff_per_tier', None)
                    run.set_event_state(event_state)

            elif winner == 'enemy':
                # Check if health loss is disabled for this combat (e.g., duels)
                disable_health_loss = pending_selection.get('disable_health_loss', False) if pending_selection else False

                if not disable_health_loss:
                    # Calculate damage from alive enemy minions (excluding summons)
                    final_enemy_band = battle_result.get('enemy_band', [])
                    damage = CombatSystem._calculate_player_damage(final_enemy_band)

                    # Apply damage to player health
                    run.health = max(0, run.health - damage)
                    resource_changes['health'] = -damage

                    # Note: Don't mark run.is_active = False here
                    # The run will be marked inactive by the /end endpoint after the end screen is shown
                    # This allows the frontend to complete the flow without "Run not found or inactive" errors

                # Always apply gold loss (even in duels)
                gold_loss = 5
                resources = run.get_resources()
                resources['gold'] = max(0, resources['gold'] - gold_loss)
                run.set_resources(resources)
                resource_changes['gold'] = -gold_loss

        return resource_changes