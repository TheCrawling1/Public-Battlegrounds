"""
Combat Action Builder - Builds interpreter commands from combat action results

Similar to CommandBuilder but for combat actions from combat_action_registry.
"""

import logging

logger = logging.getLogger(__name__)

from typing import Dict, Optional, Any, List


class CombatActionBuilder:
    """Builds interpreter commands from combat action handler results"""

    def __init__(self):
        pass

    def build_action_command(self, action_type: str, action_data: Dict,
                            changes: Dict, log_message: Optional[str] = None) -> Optional[Dict]:
        """
        Build an interpreter command for a combat action using registry

        Args:
            action_type: Type of action (combat_damage, declare_attack, etc.)
            action_data: Original action data
            changes: Changes dict from action handler
            log_message: Pre-formatted log message from handler

        Returns:
            Command dict ready for interpreter, or None if action has no command
        """
        from game_engine.combat_action_registry import get_action_definition

        # Get action definition from registry
        action_def = get_action_definition(action_type)
        if not action_def:
            logger.debug(f"[COMBAT_ACTION_BUILDER] Unknown action type: {action_type}")
            return None

        # Get interpreter config
        interpreter_config = action_def.get('interpreter', {})
        command_type = interpreter_config.get('command')

        if not command_type:
            logger.debug(f"[COMBAT_ACTION_BUILDER] No command for action: {action_type}")
            return None

        # Build context for field resolution
        context_data = {
            'action_data': action_data,
            'changes': changes
        }

        # Build command from field map
        command = {'cmd': command_type}

        field_map = interpreter_config.get('field_map', {})
        for field_name, path in field_map.items():
            value = self._resolve_path(path, context_data)
            if value is not None:
                command[field_name] = value

        # Add common metadata
        command['is_combat_action'] = True
        command['timestamp'] = 0  # Will be set by interpreter
        command['action_type'] = action_type

        # Attach log message if provided
        if log_message:
            command['log_message'] = log_message
            logger.debug(f"[COMBAT_ACTION_BUILDER] Attached log to {command_type}: {log_message[:50]}...")

        # Add default duration
        command['duration'] = self._get_default_duration(command_type)

        return command

    def build_action_commands(self, action_type: str, action_data: Dict,
                             changes: Dict, logs: List[str]) -> List[Dict]:
        """
        Build multiple commands for actions that generate multiple commands
        (e.g., combat_damage generates both COMBAT_DAMAGE and COUNTER_DAMAGE)

        Args:
            action_type: Type of action
            action_data: Original action data
            changes: Changes dict from action handler
            logs: List of log messages (one per command)

        Returns:
            List of command dicts
        """
        from game_engine.combat_action_registry import get_action_definition

        action_def = get_action_definition(action_type)
        if not action_def:
            return []

        generates = action_def.get('generates_commands', [])

        if len(generates) == 1:
            # Single command
            command = self.build_action_command(action_type, action_data, changes, logs[0] if logs else None)
            return [command] if command else []

        elif action_type == 'combat_damage' and len(generates) == 2:
            # Special handling for combat_damage which generates COMBAT_DAMAGE + COUNTER_DAMAGE
            commands = []

            # COMBAT_DAMAGE command
            combat_cmd = {
                'cmd': 'COMBAT_DAMAGE',
                'target_id': changes['defender'].get('_combat_id'),
                'target_name': changes['defender'].get('name'),
                'amount': changes['damage_dealt'],
                'source_id': changes['attacker'].get('_combat_id'),
                'source_name': changes['attacker'].get('name'),
                'obliterate_kill': changes.get('obliterate_kill', False),
                'is_combat_action': True,
                'action_type': action_type,
                'timestamp': 0,
                'duration': 500
            }

            # Attach the main log to the combat damage command
            if logs:
                combat_cmd['log_message'] = logs[0]

            commands.append(combat_cmd)

            # COUNTER_DAMAGE command (if counter damage was dealt)
            if changes.get('counter_damage_dealt', 0) > 0:
                counter_cmd = {
                    'cmd': 'COUNTER_DAMAGE',
                    'target_id': changes['attacker'].get('_combat_id'),
                    'target_name': changes['attacker'].get('name'),
                    'amount': changes['counter_damage_dealt'],
                    'source_id': changes['defender'].get('_combat_id'),
                    'source_name': changes['defender'].get('name'),
                    'obliterate_kill': changes.get('counter_obliterate_kill', False),
                    'is_combat_action': True,
                    'action_type': action_type,
                    'timestamp': 0,
                    'duration': 400
                }
                # Counter damage doesn't get a separate log (it's in the main log)
                commands.append(counter_cmd)

            return commands

        else:
            # Default: single command
            command = self.build_action_command(action_type, action_data, changes, logs[0] if logs else None)
            return [command] if command else []

    def _resolve_path(self, path: str, data: Dict) -> Any:
        """
        Resolve a dot-notation path to its value

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
                # Handle array indexing
                try:
                    index = int(part)
                    if 0 <= index < len(current):
                        current = current[index]
                    else:
                        return None
                except (ValueError, IndexError):
                    return None
            else:
                return None

        return current

    def _get_default_duration(self, command_type: str) -> int:
        """Get default duration for command type"""
        # Import from interpreter registry
        try:
            from game_engine.interpreter.interpreter_registry import get_default_duration
            return get_default_duration(command_type)
        except ImportError:
            # Fallback defaults
            durations = {
                'COMBAT_DAMAGE': 500,
                'COUNTER_DAMAGE': 400,
                'DECLARE_ATTACK': 300,
                'TURN_START': 100,
                'STUN_SKIP': 400,
                'ROUND_START': 200,
                'ATTACK_CANCELLED': 200,
                'LOG': 0
            }
            return durations.get(command_type, 200)