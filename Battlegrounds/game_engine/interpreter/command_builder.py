"""
Command Builder - Generic command construction from effect registry

Uses effect registry field maps to build interpreter commands automatically.
Replaces the manual command construction in add_effect_command().

UPDATED: Now accepts pre-formatted log messages from effect execution!
FIXED: build_trigger_command() now accepts and attaches log_message!

This is like ContextBuilder but for interpreter commands instead of effect contexts.
"""

import logging

logger = logging.getLogger(__name__)

from typing import Dict, Optional, Any, List
from game_engine.triggers.effect_registry import get_effect_definition
from .interpreter_registry import (
    get_command_metadata,
    get_default_duration,
    get_animation_override
)


class CommandBuilder:
    """
    Builds interpreter commands from effect results using registry definitions

    UPDATED: Now attaches pre-formatted log messages to commands!
    FIXED: Trigger commands now support log messages!

    This is the generic equivalent of the old add_effect_command() method.
    """

    def __init__(self):
        pass

    def build_effect_command(self, effect_type: str, effect_data: Dict,
                           changes: Dict, source_minion: Dict,
                           trigger_type: Optional[str] = None,
                           log_message: Optional[str] = None) -> Optional[Dict]:
        """
        Build an interpreter command for an effect using registry field maps

        UPDATED: Now accepts log_message parameter and attaches to command!

        Args:
            effect_type: Type of effect (heal, deal_damage, etc.)
            effect_data: Original effect data
            changes: Changes dict from effect execution
            source_minion: Minion that caused the effect
            trigger_type: Optional trigger type context
            log_message: Pre-formatted log message from effect execution

        Returns:
            Command dict ready for interpreter, or None if effect has no command
        """
        # Get effect definition from registry
        effect_def = get_effect_definition(effect_type)
        if not effect_def:
            logger.debug(f"[COMMAND_BUILDER] Unknown effect type: {effect_type}")
            return None

        # Get interpreter config from effect registry
        interpreter_config = effect_def.get('interpreter', {})
        command_type = interpreter_config.get('command')

        if not command_type:
            # Some effects (like conditional) don't create commands
            return None

        # Build context for field resolution
        context_data = {
            'effect_data': effect_data,
            'changes': changes,
            'context': {'source': source_minion}
        }

        # Build command from field map
        command = {'cmd': command_type}

        field_map = interpreter_config.get('field_map', {})
        for field_name, path in field_map.items():
            value = self._resolve_path(path, context_data)
            if value is not None:
                command[field_name] = value

        # Add common metadata
        command['is_effect_result'] = True
        command['timestamp'] = 0  # Will be set by interpreter
        command['effect_type'] = effect_type

        # Add source metadata for effect grouping
        if source_minion:
            command['source_golden'] = source_minion.get('golden', False)

        if trigger_type:
            command['trigger_type'] = trigger_type

        # Add trigger context if available
        trigger_context = changes.get('trigger_context', {})
        if trigger_context:
            command['trigger_context'] = trigger_context

        # UPDATED: Attach pre-formatted log message if provided
        if log_message:
            command['log_message'] = log_message
            logger.debug(f"[COMMAND_BUILDER] Attached log to {command_type}: {log_message[:50]}...")

        # Add default duration and animation metadata
        self._add_command_metadata(command, source_minion)

        return command

    def build_trigger_command(self, trigger_type: str, source_minion: Dict,
                            log_message: Optional[str] = None) -> Dict:
        """
        Build a trigger command (like TRIGGER_ASSAULT)

        FIXED: Now accepts log_message parameter and attaches it to command!

        Args:
            trigger_type: Type of trigger (assault, cast, etc.)
            source_minion: Minion triggering the ability
            log_message: Pre-formatted log message from trigger processing

        Returns:
            Trigger command dict
        """
        # Map trigger types to command types
        trigger_to_command = {
            'assault': 'TRIGGER_ASSAULT',
            'cast': 'TRIGGER_CAST',
            'death_toll': 'TRIGGER_DEATH_TOLL',
            'rage': 'TRIGGER_RAGE',
            'on_any_death': 'TRIGGER_ON_ANY_DEATH',
            'on_any_cast': 'TRIGGER_ON_ANY_CAST',
            'on_any_summon': 'TRIGGER_ON_ANY_SUMMON',
            'on_any_death_toll': 'TRIGGER_ON_ANY_DEATH_TOLL',
            'on_any_leap': 'TRIGGER_ON_ANY_LEAP',
            'start_of_combat': 'TRIGGER_START_OF_COMBAT',
            'on_damage': 'TRIGGER_ON_DAMAGE'
        }

        cmd_type = trigger_to_command.get(trigger_type)
        if not cmd_type:
            logger.debug(f"[COMMAND_BUILDER] Unknown trigger type: {trigger_type}")
            return None

        # Build command
        command = {
            'cmd': cmd_type,
            'source_id': source_minion.get('_combat_id'),
            'source_name': source_minion.get('name'),
            'golden': source_minion.get('golden', False)
        }

        # FIXED: Attach log message if provided
        if log_message:
            command['log_message'] = log_message
            logger.debug(f"[COMMAND_BUILDER] Attached log to {cmd_type}: {log_message[:50]}...")

        # Add metadata
        self._add_command_metadata(command, source_minion)

        return command

    def _resolve_path(self, path: str, data: Dict) -> Any:
        """
        Resolve a dot-notation path to its value

        Examples:
            'changes.targets.0._combat_id' → data['changes']['targets'][0]['_combat_id']
            'effect_data.amount' → data['effect_data']['amount']
            'context.source.name' → data['context']['source']['name']

        Args:
            path: Dot-notation path string
            data: Data dictionary to resolve from

        Returns:
            The resolved value, or None if not found
        """
        if not path:
            return None

        parts = path.split('.')
        current = data

        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
                if current is None:
                    return None
            elif isinstance(current, list):
                # Handle array indexing (e.g., 'targets.0')
                try:
                    index = int(part)
                    if 0 <= index < len(current):
                        current = current[index]
                    else:
                        return None
                except (ValueError, IndexError):
                    return None
            else:
                # Can't traverse further
                return None

        return current

    def _add_command_metadata(self, command: Dict, source_minion: Optional[Dict]):
        """
        Add metadata to command from interpreter registry

        Args:
            command: Command to add metadata to
            source_minion: Source minion for override checking
        """
        cmd_type = command['cmd']

        # Add duration if not present
        if 'duration' not in command:
            command['duration'] = get_default_duration(cmd_type)

        # Check for animation override
        if source_minion:
            minion_name = source_minion.get('name')
            override = get_animation_override(cmd_type, minion_name)

            if override:
                # Apply override duration if specified
                if 'duration' in override:
                    command['duration'] = override['duration']

                # Add override animation type
                if 'animation_type' in override:
                    command['animation_override'] = override['animation_type']

        # Add animation metadata (will be enhanced by animation system)
        if 'animation' not in command:
            command['animation'] = self._get_basic_animation_metadata(command)

    def _get_basic_animation_metadata(self, command: Dict) -> Dict:
        """
        Get basic animation metadata for a command

        This provides minimal animation info. The animation system will enhance it.
        """
        cmd_type = command.get('cmd')

        # Basic metadata
        animation = {
            'type': cmd_type.lower(),
            'priority': 50
        }

        # Add category-specific defaults
        if cmd_type in ['DEAL_DAMAGE', 'COMBAT_DAMAGE', 'COUNTER_DAMAGE']:
            animation['effects'] = ['damage_flash', 'damage_number']
            animation['color'] = 'red'

        elif cmd_type == 'HEAL':
            animation['effects'] = ['heal_glow', 'heal_number']
            animation['color'] = 'green'

        elif cmd_type in ['BUFF_STATS', 'PERMANENT_STAT_GAIN']:
            animation['effects'] = ['buff_sparkle']
            animation['color'] = 'blue'

        elif cmd_type == 'DEBUFF_STATS':
            animation['effects'] = ['debuff_glow']
            animation['color'] = 'purple'

        elif cmd_type == 'SUMMON_MINION':
            animation['effects'] = ['summon_appear']
            animation['color'] = 'gold'

        elif cmd_type == 'DEATH':
            animation['effects'] = ['death_fade']
            animation['color'] = 'black'

        elif cmd_type.startswith('TRIGGER_'):
            animation['effects'] = ['trigger_glow']
            animation['color'] = 'orange'

        return animation

    def validate_command(self, command: Dict) -> tuple:
        """
        Validate that a command has all required fields

        Returns:
            Tuple of (is_valid, error_message)
        """
        from game_engine.interpreter.interpreter_registry import validate_command
        return validate_command(command)