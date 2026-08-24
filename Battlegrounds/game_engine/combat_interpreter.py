"""
Combat Interpreter - Converts combat results into a sequence of commands for frontend playback

This module takes the results of combat processing and generates a command sequence
that the frontend can step through locally, enabling animations and speed control.

UPDATED: Now uses registry-based command building and bundle detection!
UPDATED: Commands include pre-formatted log messages from backend!
- CommandBuilder: Builds commands from effect registry field maps
- BundleDetector: Detects bundles using registry patterns
- No more hardcoded command construction or bundle detection

This is the orchestrator that uses the registry system.
"""

import logging

logger = logging.getLogger(__name__)

from typing import Dict, List, Optional, Any, Tuple
import copy

# Import registry-based systems
from game_engine.interpreter import (
    CommandBuilder,
    BundleDetector,
    get_default_duration,
    get_animation_priority
)


class CombatCommand:
    """Constants for command types"""
    # Combat flow
    START = 'START'
    END = 'END'
    ROUND_START = 'ROUND_START'
    TURN_START = 'TURN_START'

    # Attack sequence
    DECLARE_ATTACK = 'DECLARE_ATTACK'
    ATTACK_CANCELLED = 'ATTACK_CANCELLED'
    COMBAT_DAMAGE = 'COMBAT_DAMAGE'
    COUNTER_DAMAGE = 'COUNTER_DAMAGE'

    # Triggers
    TRIGGER_RAGE = 'TRIGGER_RAGE'
    TRIGGER_ASSAULT = 'TRIGGER_ASSAULT'
    TRIGGER_CAST = 'TRIGGER_CAST'
    TRIGGER_DEATH_TOLL = 'TRIGGER_DEATH_TOLL'
    TRIGGER_ON_ANY_DEATH = 'TRIGGER_ON_ANY_DEATH'
    TRIGGER_ON_ANY_CAST = 'TRIGGER_ON_ANY_CAST'
    TRIGGER_ON_ANY_SUMMON = 'TRIGGER_ON_ANY_SUMMON'
    TRIGGER_START_OF_COMBAT = 'TRIGGER_START_OF_COMBAT'
    TRIGGER_ON_DAMAGE = 'TRIGGER_ON_DAMAGE'

    # Effects
    DEAL_DAMAGE = 'DEAL_DAMAGE'
    HEAL = 'HEAL'
    BUFF_STATS = 'BUFF_STATS'
    DEBUFF_STATS = 'DEBUFF_STATS'
    SUMMON_MINION = 'SUMMON_MINION'
    DESTROY_MINION = 'DESTROY_MINION'
    DEATH = 'DEATH'
    REMOVE_FROM_BAND = 'REMOVE_FROM_BAND'
    MOVE_MINION = 'MOVE_MINION'
    PERMANENT_STAT_GAIN = 'PERMANENT_STAT_GAIN'
    STUN = 'STUN'
    GIVE_KEYWORD = 'GIVE_KEYWORD'

    # Special
    MULTI_ATTACK = 'MULTI_ATTACK'
    FATIGUE_DAMAGE = 'FATIGUE_DAMAGE'
    STUN_SKIP = 'STUN_SKIP'
    STUN_REDUCED = 'STUN_REDUCED'
    AURA_RECALCULATION = 'AURA_RECALCULATION'

    # Log entries (for messages only)
    LOG = 'LOG'


class CombatInterpreter:
    """
    Main interface between combat system and frontend.

    UPDATED: Now uses registry-based systems for command building and bundle detection.
    UPDATED: Commands include pre-formatted log messages from backend effect execution.
    """

    def __init__(self):
        self.commands: List[Dict] = []
        # band_states[i] is the serialized board immediately AFTER commands[i] runs.
        # Same length as commands; one snapshot per command. The frontend uses these
        # as the source of truth for what the board looks like at step i, so it
        # never has to re-derive state from deltas.
        self.band_states: List[Dict] = []
        self.current_index = 0
        self.initial_player_band = None
        self.initial_enemy_band = None
        # Live references to the band lists owned by combat_state. Mutated in
        # place by effects; we read from them when snapshotting in add_command.
        self._live_player_band: Optional[List[Dict]] = None
        self._live_enemy_band: Optional[List[Dict]] = None
        self.is_finalized = False

        # Track effect commands separately for debugging
        self.effect_commands_count = 0
        self.trigger_commands_count = 0

        # Animation bundles
        self.animation_bundles: List[Dict] = []

        # REGISTRY-BASED SYSTEMS
        self.command_builder = CommandBuilder()
        self.bundle_detector = BundleDetector()

    def initialize(self, player_band: List[Dict], enemy_band: List[Dict]):
        """Initialize the interpreter with starting bands"""
        self.initial_player_band = copy.deepcopy(player_band)
        self.initial_enemy_band = copy.deepcopy(enemy_band)
        # Hold the same list refs that combat_state holds. Effects mutate the
        # minion dicts in place, so these refs always reflect current truth.
        self._live_player_band = player_band
        self._live_enemy_band = enemy_band
        self.commands = []
        self.band_states = []
        self.current_index = 0
        self.is_finalized = False
        self.effect_commands_count = 0
        self.trigger_commands_count = 0

        # Reset bundle system (detector tracks bundle ID counter)
        self.animation_bundles = []

        # Add START command
        self.add_command({
            'cmd': CombatCommand.START,
            'player_band': self._serialize_band(player_band),
            'enemy_band': self._serialize_band(enemy_band)
        })

    def reset_for_replay(self):
        """Reset the interpreter for replay (used in dev mode)"""
        logger.debug("[INTERPRETER] Resetting for replay - clearing bundle state")

        # Clear all bundle-related state
        self.animation_bundles = []

        # Clear bundle markings from all commands
        for command in self.commands:
            if 'animation_bundle' in command:
                del command['animation_bundle']
            if 'bundle_position' in command:
                del command['bundle_position']
            if 'is_bundle_start' in command:
                del command['is_bundle_start']
            if 'is_bundle_end' in command:
                del command['is_bundle_end']
            if 'bundle_animation' in command:
                del command['bundle_animation']
            if 'template_data' in command:
                del command['template_data']

        # Reset other state
        self.current_index = 0
        self.is_finalized = False

        logger.debug("[INTERPRETER] Bundle state cleared, ready for re-detection")

    def add_command(self, command: Dict):
        """Add a command to the sequence"""
        if self.is_finalized:
            logger.warning("[INTERPRETER WARNING] Attempting to add command after finalization")
            return

        if not command or 'cmd' not in command:
            logger.warning("[INTERPRETER WARNING] Invalid command - missing 'cmd' field")
            return

        # Add sequence number for debugging
        command['seq'] = len(self.commands)

        # Add timing hint if not present
        if 'duration' not in command:
            command['duration'] = get_default_duration(command['cmd'])

        # Add animation metadata if applicable and not already present
        if 'animation' not in command:
            command['animation'] = self._get_animation_metadata(command)

        # Track command types for debugging
        cmd_type = command['cmd']
        if cmd_type.startswith('TRIGGER_'):
            self.trigger_commands_count += 1
        elif cmd_type in [CombatCommand.DEAL_DAMAGE, CombatCommand.HEAL, CombatCommand.BUFF_STATS,
                         CombatCommand.DEBUFF_STATS, CombatCommand.SUMMON_MINION, CombatCommand.DESTROY_MINION,
                         CombatCommand.PERMANENT_STAT_GAIN, CombatCommand.MOVE_MINION, CombatCommand.STUN,
                         CombatCommand.GIVE_KEYWORD]:
            self.effect_commands_count += 1

        self.commands.append(command)

        # Snapshot the live bands AFTER this command's effect has been applied.
        # The frontend reads band_states[i] to render the board at step i without
        # ever needing to compute deltas client-side. Empty dicts before initialize()
        # is rare-but-possible (LOG commands added before bands attached); fall back
        # to empty bands so band_states stays length-aligned with commands.
        self.band_states.append({
            'player_band': self._serialize_band(self._live_player_band) if self._live_player_band is not None else [],
            'enemy_band': self._serialize_band(self._live_enemy_band) if self._live_enemy_band is not None else [],
        })

        # Log with message preview if present
        log_preview = f" (log: {command['log_message'][:30]}...)" if command.get('log_message') else ""
        logger.debug(f"[INTERPRETER] Added command {len(self.commands)}: {command.get('cmd')} (seq: {command['seq']}){log_preview}")

    def add_log(self, message: str, log_type: str = 'info'):
        """Add a log message command"""
        self.add_command({
            'cmd': CombatCommand.LOG,
            'message': message,
            'log_type': log_type
        })

    def add_effect_command(self, effect_type: str, log_message: str = None, **kwargs):
        """
        Add an effect command using the registry-based command builder

        UPDATED: Now uses CommandBuilder instead of manual construction!
        UPDATED: Now accepts log_message parameter to attach pre-formatted logs!

        Args:
            effect_type: Type of effect (heal, deal_damage, etc.)
            log_message: Pre-formatted log message from effect execution
            **kwargs: Effect-specific parameters
        """
        # Build effect data from kwargs
        effect_data = {'type': effect_type}

        # Extract common parameters
        source_minion = kwargs.get('source_minion', {
            'name': kwargs.get('source_name', 'Unknown'),
            '_combat_id': kwargs.get('source_id'),
            'golden': kwargs.get('source_golden', False)
        })

        trigger_type = kwargs.get('trigger_type')

        # Build changes dict from kwargs
        changes = {}

        # Map effect types to their changes structure
        if effect_type in ['heal', 'heal_self']:
            changes = {
                'targets': [kwargs.get('target_minion', {
                    'name': kwargs.get('target_name'),
                    '_combat_id': kwargs.get('target_id')
                })],
                'healing_done': kwargs.get('amount', 0)
            }

        elif effect_type == 'deal_damage':
            changes = {
                'targets': [kwargs.get('target_minion', {
                    'name': kwargs.get('target_name'),
                    '_combat_id': kwargs.get('target_id')
                })],
                'damage_dealt': kwargs.get('amount', 0)
            }

        elif effect_type in ['buff_stats', 'debuff_stats', 'permanent_stat_gain']:
            changes = {
                'targets': [kwargs.get('target_minion', {
                    'name': kwargs.get('target_name'),
                    '_combat_id': kwargs.get('target_id')
                })]
            }

        elif effect_type == 'summon':
            minion_data = kwargs.get('minion')
            if not minion_data or not minion_data.get('image'):
                minion_data['image'] = 'default_minion.png'

            changes = {
                'summoned_minions': [minion_data],
                'summon_band': kwargs.get('band', 'unknown')
            }

        elif effect_type == 'destroy_minion':
            changes = {
                'targets': [kwargs.get('target_minion', {
                    'name': kwargs.get('target_name'),
                    '_combat_id': kwargs.get('target_id')
                })],
                'destroyed': kwargs.get('target_name'),
                'saved_stats': kwargs.get('saved_stats', False)
            }

        elif effect_type == 'move_minion':
            changes = {
                'targets': [kwargs.get('minion', {
                    'name': kwargs.get('minion_name'),
                    '_combat_id': kwargs.get('minion_id')
                })],
                'old_position': kwargs.get('from_position', 0),
                'new_position': kwargs.get('to_position', 0)
            }

        elif effect_type == 'stun':
            changes = {
                'targets': [kwargs.get('target_minion', {
                    'name': kwargs.get('target_name'),
                    '_combat_id': kwargs.get('target_id')
                })],
                'stun_applied': kwargs.get('stun_count', 1)
            }

        elif effect_type == 'give_keyword':
            changes = {
                'targets': [kwargs.get('target_minion', {
                    'name': kwargs.get('target_name'),
                    '_combat_id': kwargs.get('target_id')
                })],
                'keyword_granted': kwargs.get('keyword')
            }

        # Use CommandBuilder to create the command WITH log message
        command = self.command_builder.build_effect_command(
            effect_type,
            effect_data,
            changes,
            source_minion,
            trigger_type,
            log_message=log_message  # ← NEW: Pass the log message!
        )

        if command:
            # Add any extra kwargs that weren't handled by the builder
            for key, value in kwargs.items():
                if key not in command and key not in ['source_minion', 'target_minion',
                                                       'minion', 'source_name', 'source_id',
                                                       'source_golden', 'trigger_type', 'log_message']:
                    command[key] = value

            self.add_command(command)
            logger.debug(f"[INTERPRETER] Added effect command via builder: {effect_type} -> {command['cmd']}")
        else:
            logger.error(f"[INTERPRETER ERROR] Failed to build command for effect type: {effect_type}")

    def detect_animation_bundles(self):
        """
        Detect animation bundles in the command sequence

        UPDATED: Now uses BundleDetector instead of hardcoded detection!
        """
        logger.debug("[INTERPRETER] Detecting animation bundles using registry patterns...")

        # Use bundle detector to find all bundles
        detected_bundles = self.bundle_detector.detect_all_bundles(self.commands)

        # Store bundles and mark commands
        for bundle in detected_bundles:
            self.animation_bundles.append(bundle)
            self.bundle_detector.mark_commands_with_bundle(self.commands, bundle)

        logger.debug(f"[INTERPRETER] Detected {len(detected_bundles)} animation bundles")

    def finalize_combat(self, combat_result: Dict) -> Dict:
        """
        Finalize the combat sequence and prepare for frontend delivery

        FIXED: Now attaches winner log message to END command!
        """
        if self.is_finalized:
            logger.warning("[INTERPRETER WARNING] Combat already finalized")
            return self.get_interpreter_data()

        # Detect animation bundles before finalizing
        self.detect_animation_bundles()

        # Generate winner log message
        winner = combat_result.get('winner', 'draw')
        if winner == 'player':
            winner_log = "🏆 Player wins!"
        elif winner == 'enemy':
            winner_log = "💀 Enemy wins!"
        else:
            winner_log = "🤝 Draw!"

        # FIXED: Add END command WITH log message
        self.add_command({
            'cmd': CombatCommand.END,
            'winner': winner,
            'rounds': combat_result.get('rounds', 0),
            'attacks': combat_result.get('attacks', 0),
            'final_player_band': self._serialize_band(combat_result.get('player_band', [])),
            'final_enemy_band': self._serialize_band(combat_result.get('enemy_band', [])),
            'log_message': winner_log  # ← FIXED: Attach the winner log!
        })

        self.is_finalized = True

        logger.debug(f"[INTERPRETER] Combat finalized with {len(self.commands)} total commands")
        logger.debug(
            f"[INTERPRETER] Commands breakdown: {self.trigger_commands_count} triggers, {self.effect_commands_count} effects")
        logger.debug(f"[INTERPRETER] Animation bundles: {len(self.animation_bundles)}")

        return self.get_interpreter_data()

    def get_interpreter_data(self) -> Dict:
        """Get the complete interpreter data for frontend"""
        # Length must match by construction (snapshot appended in add_command).
        # If they ever drift, the snapshot-based player would render stale state,
        # so log loudly and pad with the last-known good snapshot rather than
        # silently emit a malformed payload.
        if len(self.band_states) != len(self.commands):
            logger.warning(f"[INTERPRETER WARNING] band_states/commands length mismatch: "
                  f"{len(self.band_states)} vs {len(self.commands)}")
            last = self.band_states[-1] if self.band_states else {'player_band': [], 'enemy_band': []}
            while len(self.band_states) < len(self.commands):
                self.band_states.append(last)

        steps = [
            {
                'command': self.commands[i],
                'state_after': self.band_states[i],
            }
            for i in range(len(self.commands))
        ]

        return {
            # Legacy delta stream — kept for the existing client interpreter until
            # the snapshot-based player is rolled out and verified.
            'commands': self.commands,
            'total_commands': len(self.commands),
            'command_breakdown': {
                'trigger_commands': self.trigger_commands_count,
                'effect_commands': self.effect_commands_count,
                'other_commands': len(self.commands) - self.trigger_commands_count - self.effect_commands_count
            },
            'initial_state': {
                'player_band': self._serialize_band(self.initial_player_band) if self.initial_player_band else [],
                'enemy_band': self._serialize_band(self.initial_enemy_band) if self.initial_enemy_band else []
            },
            'is_finalized': self.is_finalized,
            'animation_bundles': self.animation_bundles,
            # New snapshot-based stream: each step pairs a command with the board
            # state immediately after it. Frontend can render position N as
            # steps[N].state_after with no client-side reduction.
            'steps': steps,
        }

    def _get_animation_metadata(self, command: Dict) -> Dict:
        """Get animation metadata for a command using the animation system"""
        cmd_type = command.get('cmd')

        # Try to get animation from the animation system
        try:
            from game_engine.animations import get_animation_for_effect, get_animation_for_trigger

            # Map command types to animation requests
            if cmd_type in [CombatCommand.DEAL_DAMAGE, CombatCommand.COMBAT_DAMAGE, CombatCommand.COUNTER_DAMAGE]:
                return get_animation_for_effect('deal_damage',
                                                target_id=command.get('target_id'),
                                                source_golden=command.get('source_golden', False)) or {}

            elif cmd_type == CombatCommand.HEAL:
                effect_type = 'heal_self' if command.get('is_self_heal') else 'heal'
                return get_animation_for_effect(effect_type,
                                                target_id=command.get('target_id'),
                                                source_golden=command.get('source_golden', False)) or {}

            elif cmd_type == CombatCommand.BUFF_STATS:
                effect_type = 'permanent_stat_gain' if command.get('is_permanent') else 'buff_stats'
                return get_animation_for_effect(effect_type,
                                                target_id=command.get('target_id'),
                                                source_golden=command.get('source_golden', False)) or {}

            elif cmd_type == CombatCommand.DEBUFF_STATS:
                return get_animation_for_effect('debuff_stats',
                                                target_id=command.get('target_id'),
                                                source_golden=command.get('source_golden', False)) or {}

            elif cmd_type == CombatCommand.SUMMON_MINION:
                return get_animation_for_effect('summon',
                                                target_id=command.get('minion', {}).get('_combat_id'),
                                                source_golden=command.get('source_golden', False)) or {}

            elif cmd_type == CombatCommand.DEATH:
                return get_animation_for_effect('death',
                                                target_id=command.get('minion_id')) or {}

            elif cmd_type == CombatCommand.STUN:
                return get_animation_for_effect('stun',
                                                target_id=command.get('target_id')) or {}

            elif cmd_type == CombatCommand.MOVE_MINION:
                return get_animation_for_effect('move_minion',
                                                target_id=command.get('minion_id'),
                                                from_position=command.get('from_position'),
                                                to_position=command.get('to_position')) or {}

            elif cmd_type.startswith('TRIGGER_'):
                # Map command to trigger type for animation
                trigger_map = {
                    CombatCommand.TRIGGER_ASSAULT: 'assault',
                    CombatCommand.TRIGGER_CAST: 'cast',
                    CombatCommand.TRIGGER_DEATH_TOLL: 'death_toll',
                    CombatCommand.TRIGGER_RAGE: 'rage',
                    CombatCommand.TRIGGER_ON_ANY_DEATH: 'on_any_death',
                    CombatCommand.TRIGGER_ON_ANY_CAST: 'on_any_cast',
                    CombatCommand.TRIGGER_ON_ANY_SUMMON: 'on_any_summon',
                    CombatCommand.TRIGGER_START_OF_COMBAT: 'start_of_combat',
                    CombatCommand.TRIGGER_ON_DAMAGE: 'on_damage'
                }
                trigger_type = trigger_map.get(cmd_type)
                if trigger_type:
                    animation = get_animation_for_trigger(trigger_type,
                                                          target_id=command.get('source_id'),
                                                          source_golden=command.get('golden', False))
                    if animation:
                        return animation

        except ImportError:
            logger.warning("[INTERPRETER WARNING] Animation system not available")
        except Exception as e:
            logger.error(f"[INTERPRETER ERROR] Failed to get animation: {e}")

        # Fallback to basic animation metadata
        return self._get_basic_animation_metadata(command)

    def _get_basic_animation_metadata(self, command: Dict) -> Dict:
        """Get basic animation metadata for a command (fallback)"""
        cmd_type = command.get('cmd')

        animation_data = {
            'type': cmd_type.lower(),
            'priority': get_animation_priority(cmd_type),
            'effects': []
        }

        # Add specific animation data based on command type
        if cmd_type in [CombatCommand.COMBAT_DAMAGE, CombatCommand.COUNTER_DAMAGE, CombatCommand.DEAL_DAMAGE]:
            animation_data['effects'].append('damage_flash')
            animation_data['effects'].append('damage_number')
            animation_data['color'] = 'red'

        elif cmd_type == CombatCommand.HEAL:
            animation_data['effects'].append('heal_glow')
            animation_data['effects'].append('heal_number')
            animation_data['color'] = 'green'

        elif cmd_type in [CombatCommand.BUFF_STATS, CombatCommand.PERMANENT_STAT_GAIN]:
            animation_data['effects'].append('buff_sparkle')
            animation_data['color'] = 'blue'

        elif cmd_type == CombatCommand.DEBUFF_STATS:
            animation_data['effects'].append('debuff_glow')
            animation_data['color'] = 'purple'

        elif cmd_type == CombatCommand.DESTROY_MINION:
            animation_data['effects'].append('destroy_flash')
            animation_data['effects'].append('shatter_effect')
            animation_data['color'] = 'orange'

        elif cmd_type == CombatCommand.DEATH:
            animation_data['effects'].append('death_fade')
            animation_data['color'] = 'black'

        elif cmd_type == CombatCommand.SUMMON_MINION:
            animation_data['effects'].append('summon_appear')
            animation_data['color'] = 'gold'

        elif cmd_type == CombatCommand.MOVE_MINION:
            animation_data['effects'].append('move_slide')
            animation_data['color'] = 'cyan'

        elif cmd_type == CombatCommand.STUN:
            animation_data['effects'].append('stun_stars')
            animation_data['color'] = 'yellow'

        elif cmd_type.startswith('TRIGGER_'):
            animation_data['effects'].append('trigger_glow')
            animation_data['color'] = 'orange'

        return animation_data

    def _serialize_band(self, band: List[Dict]) -> List[Dict]:
        """Serialize a band for frontend consumption - INCLUDES ALL EFFECT DATA FOR TOOLTIPS"""
        if not band:
            return []

        serialized = []
        for minion in band:
            # Start with basic minion data
            # CRITICAL: Copy mutable objects (lists/dicts) to prevent reference mutation
            # Clamp hp to >= 0 to match the legacy reducer's contract. The server
            # briefly stores negative hp mid-damage-resolution; the UI has always
            # clamped to 0 at render time, so normalize here.
            raw_hp = minion.get('health', 0) or 0
            minion_data = {
                'name': minion.get('name'),
                'health': max(0, raw_hp),
                'attack': minion.get('attack'),
                'type': minion.get('type', 'None'),
                'keywords': list(minion.get('keywords', [])),  # Copy list to prevent mutation
                'golden': minion.get('golden', False),
                'position': minion.get('position', 0),
                'band_id': minion.get('band_id'),
                '_combat_id': minion.get('_combat_id'),
                'stun_count': minion.get('stun_count', 0),
                'permanent_health': minion.get('permanent_health', 0),
                'permanent_attack': minion.get('permanent_attack', 0),
                'image': minion.get('image'),
                'rarity': minion.get('rarity', 'common'),
                # Hide keyword fields (needed for tooltips)
                'hide_count': minion.get('hide_count'),
                'hide_remaining': minion.get('hide_remaining'),
                'is_hidden': minion.get('is_hidden'),
                # Leap keyword fields (needed for tooltips)
                'leap_distance': minion.get('leap_distance'),
                # Ring keyword field (needed for "Ring X" display)
                'permanent_ring_count': minion.get('permanent_ring_count', 0),
                # Cleave keyword amount (needed for tooltip/attack resolution)
                'cleave_amount': minion.get('cleave_amount'),
            }

            # Include ALL effect data fields for tooltips
            # Note: Effect dicts are typically not mutated during combat, but copy lists to be safe
            effect_fields = [
                'assault_effect', 'cast_effect', 'death_toll_effect',
                'rage_effect', 'on_any_death_effect', 'on_any_cast_effect',
                'on_any_summon_effect', 'on_damage_effect', 'aura_effect',
                'sacrifice_effect', 'multi_attack_count', 'permanent_stacks',
                'aura_buffs', 'all_keywords'
            ]

            for field in effect_fields:
                if field in minion:
                    value = minion[field]
                    # Copy mutable objects to prevent reference mutation
                    if isinstance(value, list):
                        minion_data[field] = list(value)
                    elif isinstance(value, dict):
                        minion_data[field] = dict(value)
                    else:
                        minion_data[field] = value

            # Ensure image has a fallback if missing
            if not minion_data['image']:
                minion_data['image'] = 'default_minion.png'

            # Add derived fields for frontend convenience
            minion_data['total_health'] = minion_data['health'] + minion_data['permanent_health']
            minion_data['total_attack'] = minion_data['attack'] + minion_data['permanent_attack']
            minion_data['is_stunned'] = minion_data['stun_count'] > 0

            serialized.append(minion_data)

        return serialized

    # Utility methods for getting specific command types
    def get_commands_by_type(self, cmd_type: str) -> List[Dict]:
        """Get all commands of a specific type"""
        return [cmd for cmd in self.commands if cmd.get('cmd') == cmd_type]

    def get_effect_commands(self) -> List[Dict]:
        """Get all effect result commands"""
        effect_command_types = [
            CombatCommand.DEAL_DAMAGE, CombatCommand.HEAL, CombatCommand.BUFF_STATS,
            CombatCommand.DEBUFF_STATS, CombatCommand.SUMMON_MINION, CombatCommand.DESTROY_MINION,
            CombatCommand.PERMANENT_STAT_GAIN, CombatCommand.MOVE_MINION, CombatCommand.STUN,
            CombatCommand.GIVE_KEYWORD
        ]
        return [cmd for cmd in self.commands if cmd.get('cmd') in effect_command_types]

    def get_trigger_commands(self) -> List[Dict]:
        """Get all trigger commands"""
        return [cmd for cmd in self.commands if cmd.get('cmd', '').startswith('TRIGGER_')]

    def step_forward(self) -> Optional[Dict]:
        """Step forward one command"""
        if self.current_index < len(self.commands):
            command = self.commands[self.current_index]
            self.current_index += 1
            return command
        return None

    def step_backward(self) -> Optional[Dict]:
        """Step backward one command"""
        if self.current_index > 0:
            self.current_index -= 1
            return self.commands[self.current_index]
        return None

    def get_current_command(self) -> Optional[Dict]:
        """Get the current command without advancing"""
        if 0 <= self.current_index < len(self.commands):
            return self.commands[self.current_index]
        return None

    def reset(self):
        """Reset to the beginning"""
        self.current_index = 0

    def jump_to(self, index: int):
        """Jump to a specific command index"""
        if 0 <= index < len(self.commands):
            self.current_index = index
            return True
        return False

    def get_command_count(self) -> int:
        """Get total number of commands"""
        return len(self.commands)

    def get_debug_info(self) -> Dict:
        """Get debugging information about the interpreter state"""
        return {
            'total_commands': len(self.commands),
            'trigger_commands': self.trigger_commands_count,
            'effect_commands': self.effect_commands_count,
            'animation_bundles': len(self.animation_bundles),
            'current_index': self.current_index,
            'is_finalized': self.is_finalized,
            'command_types': {
                cmd_type: len(self.get_commands_by_type(cmd_type))
                for cmd_type in [
                    CombatCommand.TRIGGER_ASSAULT, CombatCommand.TRIGGER_CAST,
                    CombatCommand.DEAL_DAMAGE, CombatCommand.HEAL,
                    CombatCommand.BUFF_STATS, CombatCommand.SUMMON_MINION, CombatCommand.DESTROY_MINION
                ]
            },
            'recent_commands': [
                {'seq': cmd.get('seq'), 'cmd': cmd.get('cmd')}
                for cmd in self.commands[-5:]
            ],
            'bundle_summary': [
                {
                    'bundle_id': bundle['bundle_id'],
                    'type': bundle['bundle_type'],
                    'commands': len(bundle['command_indices']),
                    'targets': len(bundle['target_ids']),
                    'has_template': 'template_data' in bundle
                }
                for bundle in self.animation_bundles
            ]
        }


# Legacy compatibility - InterpreterSession wrapper
class InterpreterSession:
    """
    Manages an interpreter session for a specific combat
    DEPRECATED: Use CombatInterpreter directly instead
    """

    def __init__(self, run_id: int):
        self.run_id = run_id
        self.interpreter = CombatInterpreter()
        self.current_position = 0
        self.is_complete = False
        logger.debug("[INTERPRETER] Using deprecated InterpreterSession - consider using CombatInterpreter directly")

    def initialize_from_combat(self, player_band: List[Dict], enemy_band: List[Dict]):
        """Initialize from combat bands"""
        self.interpreter.initialize(player_band, enemy_band)
        self.current_position = 0
        self.is_complete = False

    def add_commands(self, commands: List[Dict]):
        """Add multiple commands to the session"""
        for command in commands:
            self.interpreter.add_command(command)

    def finalize(self, combat_result: Dict):
        """Finalize the session with combat result"""
        self.interpreter.finalize_combat(combat_result)
        self.is_complete = True

    def get_state(self) -> Dict:
        """Get the current session state"""
        return {
            'run_id': self.run_id,
            'current_position': self.current_position,
            'total_commands': self.interpreter.get_command_count(),
            'is_complete': self.is_complete
        }

    def get_full_data(self) -> Dict:
        """Get all interpreter data for frontend initialization"""
        return self.interpreter.get_interpreter_data()


# Global session storage (deprecated)
INTERPRETER_SESSIONS: Dict[str, InterpreterSession] = {}


def get_or_create_session(run_id: int, combat_state: Dict = None) -> InterpreterSession:
    """Get existing session or create new one - DEPRECATED"""
    session_key = f"combat_{run_id}"

    if session_key not in INTERPRETER_SESSIONS:
        session = InterpreterSession(run_id)
        if combat_state:
            player_band = combat_state.get('player_band', [])
            enemy_band = combat_state.get('enemy_band', [])
            session.initialize_from_combat(player_band, enemy_band)
        INTERPRETER_SESSIONS[session_key] = session

    return INTERPRETER_SESSIONS[session_key]


def clear_session(run_id: int):
    """Clear a session - DEPRECATED"""
    session_key = f"combat_{run_id}"
    if session_key in INTERPRETER_SESSIONS:
        del INTERPRETER_SESSIONS[session_key]