"""
Bundle Detector - Generic animation bundle detection using registry patterns

Detects multi-command sequences that should be animated as coordinated bundles.
Replaces hardcoded _detect_wizard_cast_bundle() style methods.

This is like TriggerRegistrar but for animation bundles instead of triggers.
"""

import logging

logger = logging.getLogger(__name__)

from typing import Dict, List, Optional
from .bundle_registry import (
    BUNDLE_REGISTRY,
    get_bundle_definition,
    get_bundles_for_trigger,
    matches_source_filter
)


class BundleDetector:
    """
    Generic bundle detection using registry patterns

    ONE method detects ALL bundle types!
    """

    def __init__(self):
        self.next_bundle_id = 1

    def detect_all_bundles(self, commands: List[Dict]) -> List[Dict]:
        """
        Detect all animation bundles in a command sequence

        Args:
            commands: List of interpreter commands

        Returns:
            List of detected bundle definitions
        """
        bundles = []
        processed_indices = set()  # Track which commands are already in bundles

        logger.debug(f"[BUNDLE_DETECTOR] Scanning {len(commands)} commands for bundles")

        for i, command in enumerate(commands):
            # Skip if this command is already part of a bundle
            if i in processed_indices:
                continue

            # Try to detect bundles starting at this command
            bundle = self._try_detect_bundle(commands, i, processed_indices)

            if bundle:
                bundles.append(bundle)
                # Mark all bundle commands as processed
                for idx in bundle['command_indices']:
                    processed_indices.add(idx)

                logger.debug(f"[BUNDLE_DETECTOR] Detected {bundle['bundle_type']} with {len(bundle['command_indices'])} commands")

        logger.debug(f"[BUNDLE_DETECTOR] Found {len(bundles)} total bundles")
        return bundles

    def _try_detect_bundle(self, commands: List[Dict], start_index: int,
                          processed_indices: set) -> Optional[Dict]:
        """
        Try to detect a bundle starting at a specific command

        Args:
            commands: Full command list
            start_index: Index to start checking from
            processed_indices: Indices already in bundles

        Returns:
            Bundle dict if detected, None otherwise
        """
        start_command = commands[start_index]
        trigger_cmd = start_command.get('cmd')

        # Get all bundle types that could start with this trigger
        possible_bundles = get_bundles_for_trigger(trigger_cmd)

        if not possible_bundles:
            return None

        # Try each possible bundle pattern
        for bundle_type, definition in possible_bundles:
            bundle = self._match_bundle_pattern(
                commands, start_index, bundle_type, definition, processed_indices
            )

            if bundle:
                return bundle

        return None

    def _match_bundle_pattern(self, commands: List[Dict], start_index: int,
                             bundle_type: str, definition: Dict,
                             processed_indices: set) -> Optional[Dict]:
        """
        Try to match a specific bundle pattern

        Args:
            commands: Full command list
            start_index: Starting command index
            bundle_type: Type of bundle to match
            definition: Bundle definition from registry
            processed_indices: Indices already in bundles

        Returns:
            Bundle dict if pattern matches, None otherwise
        """
        start_command = commands[start_index]
        detection = definition['detection']

        # Check source filter
        source_minion = self._get_source_minion_from_command(start_command)
        source_filter = detection.get('source_filter', {})

        if not matches_source_filter(source_minion, source_filter):
            return None

        # Find follow-up commands matching the pattern
        pattern = detection['follow_up_pattern']
        follow_up_indices = self._find_follow_up_commands(
            commands, start_index + 1, pattern, start_command, processed_indices
        )

        # Must have at least one follow-up command for a bundle
        if not follow_up_indices:
            return None

        # Build bundle metadata
        bundle_id = f"{bundle_type}_{self.next_bundle_id}"
        self.next_bundle_id += 1

        # Collect all command indices (trigger + follow-ups)
        all_indices = [start_index] + follow_up_indices

        # Collect target IDs from follow-up commands
        target_ids = self._collect_target_ids(commands, follow_up_indices)

        # Build bundle
        bundle = {
            'bundle_id': bundle_id,
            'bundle_type': bundle_type,
            'source_id': start_command.get('source_id'),
            'source_name': start_command.get('source_name'),
            'target_ids': target_ids,
            'command_indices': all_indices,
            'animation_data': self._build_animation_data(definition, target_ids),
            'template_data': self._get_template_data(definition, start_command, target_ids)
        }

        return bundle

    def _find_follow_up_commands(self, commands: List[Dict], start_index: int,
                                pattern: Dict, trigger_command: Dict,
                                processed_indices: set) -> List[int]:
        """
        Find commands that match the follow-up pattern

        Args:
            commands: Full command list
            start_index: Where to start looking
            pattern: Follow-up pattern from bundle definition
            trigger_command: The trigger command that started the bundle
            processed_indices: Indices already in bundles

        Returns:
            List of matching command indices
        """
        matching_indices = []

        allowed_commands = pattern['commands']
        same_source = pattern.get('same_source', True)
        max_count = pattern.get('max_count', 10)
        stop_on_different_source = pattern.get('stop_on_different_source', True)
        stop_on_other_trigger = pattern.get('stop_on_other_trigger', True)
        allow_interleaved = pattern.get('allow_interleaved', False)

        source_id = trigger_command.get('source_id')

        for i in range(start_index, len(commands)):
            # Skip already bundled commands
            if i in processed_indices:
                if not allow_interleaved:
                    break
                continue

            command = commands[i]
            cmd_type = command.get('cmd')

            # Check if this is a matching follow-up command
            if cmd_type in allowed_commands:
                # Check source matching if required
                if same_source:
                    if command.get('source_id') != source_id:
                        if stop_on_different_source:
                            break
                        continue

                # This command matches!
                matching_indices.append(i)

                # Check if we've hit the max count
                if len(matching_indices) >= max_count:
                    break

            else:
                # This is a different command type

                # Stop on other triggers?
                if stop_on_other_trigger and cmd_type.startswith('TRIGGER_'):
                    break

                # Stop when another minion takes a turn (bundle should be per-turn)
                if cmd_type == 'TURN_START':
                    turn_minion_id = command.get('minion_id')
                    if turn_minion_id and turn_minion_id != source_id:
                        break

                # Stop on different source effects?
                if stop_on_different_source:
                    if cmd_type in ['DEAL_DAMAGE', 'HEAL', 'BUFF_STATS', 'SUMMON_MINION']:
                        if command.get('source_id') != source_id:
                            break

                # ALWAYS stop on critical state-changing commands (deaths, removals)
                # These should never be skipped by bundles
                if cmd_type in ['DEATH', 'REMOVE_FROM_BAND', 'MINION_KILLED']:
                    break

                # ALWAYS stop on non-matching commands to ensure consecutive bundles
                # The frontend can't handle non-consecutive bundle indices properly
                # (it would skip commands in between)
                break

        return matching_indices

    def _collect_target_ids(self, commands: List[Dict], indices: List[int]) -> List[str]:
        """Collect target IDs from commands (handles both single and AOE targets)"""
        target_ids = []
        for idx in indices:
            command = commands[idx]
            # Check for single target_id (regular damage)
            target_id = command.get('target_id')
            if target_id and target_id not in target_ids:
                target_ids.append(target_id)
            # Check for multiple target_ids (AOE damage)
            aoe_target_ids = command.get('target_ids', [])
            for tid in aoe_target_ids:
                if tid and tid not in target_ids:
                    target_ids.append(tid)
        return target_ids

    def _build_animation_data(self, definition: Dict, target_ids: List[str]) -> Dict:
        """Build animation data from bundle definition"""
        animation_config = definition['animation']

        animation_data = {
            'type': animation_config.get('bundle_type', 'generic_bundle'),
            'duration': animation_config.get('duration', 1000),
            'target_positions': target_ids,
            'target_count': len(target_ids)
        }

        # Copy over any additional animation properties
        for key in ['firing_pattern', 'bolt_style', 'arrow_style', 'embed_duration',
                   'effect_style', 'coordination', 'summon_style']:
            if key in animation_config:
                animation_data[key] = animation_config[key]

        return animation_data

    def _get_template_data(self, definition: Dict, trigger_command: Dict,
                          target_ids: List[str]) -> Optional[Dict]:
        """
        Get template animation data if bundle uses template system

        Args:
            definition: Bundle definition
            trigger_command: The trigger command
            target_ids: List of target IDs

        Returns:
            Template data dict or None
        """
        animation_config = definition['animation']

        if not animation_config.get('use_template_system'):
            return None

        template_name = animation_config.get('template_name')
        if not template_name:
            return None

        try:
            from game_engine.animations import get_template_animation

            # Build context for template
            context = {
                'source_id': trigger_command.get('source_id'),
                'source_name': trigger_command.get('source_name'),
                'source_golden': trigger_command.get('golden', False),
                'target_ids': target_ids,
                'target_count': len(target_ids)
            }

            template_data = get_template_animation(template_name, **context)
            if template_data:
                logger.debug(f"[BUNDLE_DETECTOR] Got template data for {template_name}")
                return template_data
            else:
                logger.debug(f"[BUNDLE_DETECTOR] No template found for {template_name}")
                return None

        except ImportError:
            logger.debug("[BUNDLE_DETECTOR] Animation system not available for templates")
            return None
        except Exception as e:
            logger.error(f"[BUNDLE_DETECTOR] Error getting template data: {e}")
            return None

    def _get_source_minion_from_command(self, command: Dict) -> Dict:
        """
        Extract source minion data from command

        Commands don't store full minion data, so we reconstruct what we need
        from command fields.
        """
        return {
            'name': command.get('source_name', ''),
            '_combat_id': command.get('source_id'),
            'golden': command.get('golden', False)
        }

    def mark_commands_with_bundle(self, commands: List[Dict], bundle: Dict):
        """
        Mark commands with bundle information

        Args:
            commands: Full command list
            bundle: Bundle definition to apply
        """
        for i, command_index in enumerate(bundle['command_indices']):
            if command_index >= len(commands):
                continue

            command = commands[command_index]
            command['animation_bundle'] = bundle['bundle_id']
            command['bundle_position'] = i
            command['is_bundle_start'] = (i == 0)
            command['is_bundle_end'] = (i == len(bundle['command_indices']) - 1)

            # Add bundle animation data to the first command
            if i == 0:
                command['bundle_animation'] = bundle['animation_data']

                # Add template data if available
                if bundle.get('template_data'):
                    command['template_data'] = bundle['template_data']