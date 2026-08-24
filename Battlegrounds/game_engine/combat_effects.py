"""
Combat Effects System - Compatibility shim for legacy code

This module provides backward compatibility for code that expects the old
combat_effects.py structure. It wraps the new modular system to maintain
the same interface while using the improved architecture underneath.

IMPORTANT: New code should import from the specific modules directly:
- game_engine.trigger_processor for trigger processing
- game_engine.effects for effect application
- game_engine.trigger_queue for queue management
"""

import copy
from typing import Dict, List, Optional, Tuple, Any
from game_engine.trigger_queue import TriggerQueue
from game_engine.trigger_processor import TriggerProcessor
from game_engine.combat_context import CombatContextManager, EffectType, DamageSource
from game_engine.events.combat_events import CombatEventSystem, CombatEventType
from game_engine.effects import apply_effect, apply_effects_list
from keywords import has_keyword


class CombatEffects:
    """
    Legacy compatibility class for combat effects

    This class provides static methods that match the old interface
    but use the new modular system underneath.
    """

    # Class-level processor instance for shared state
    _processor: Optional[TriggerProcessor] = None

    @classmethod
    def _get_processor(cls) -> TriggerProcessor:
        """Get or create the processor instance"""
        if cls._processor is None:
            cls._processor = TriggerProcessor()
        return cls._processor

    @staticmethod
    def apply_golden_doubling(effect_data: Dict, acting_minion: Dict) -> Dict:
        """
        Apply golden minion doubling to ALL numeric values in effect data

        Legacy method maintained for compatibility.
        """
        if not acting_minion.get('golden', False):
            return effect_data

        modified_effect = copy.deepcopy(effect_data)
        effect_type = modified_effect.get('type')

        # Double numeric values based on effect type
        if effect_type == 'deal_damage':
            modified_effect['amount'] = modified_effect.get('amount', 1) * 2
            if 'target_count' in modified_effect:
                modified_effect['target_count'] = modified_effect['target_count'] * 2

        elif effect_type == 'deal_aoe_damage':
            modified_effect['amount'] = modified_effect.get('amount', 1) * 2
            if 'max_targets' in modified_effect:
                modified_effect['max_targets'] = modified_effect['max_targets'] * 2

        elif effect_type == 'heal':
            modified_effect['amount'] = modified_effect.get('amount', 1) * 2
            if 'target_count' in modified_effect:
                modified_effect['target_count'] = modified_effect['target_count'] * 2

        elif effect_type == 'heal_self':
            modified_effect['amount'] = modified_effect.get('amount', 1) * 2

        elif effect_type == 'buff_stats':
            if 'health' in modified_effect:
                modified_effect['health'] = modified_effect['health'] * 2
            if 'attack' in modified_effect:
                modified_effect['attack'] = modified_effect['attack'] * 2
            if 'target_count' in modified_effect:
                modified_effect['target_count'] = modified_effect['target_count'] * 2

        elif effect_type == 'buff_stats_tribe':
            if 'health' in modified_effect:
                modified_effect['health'] = modified_effect['health'] * 2
            if 'attack' in modified_effect:
                modified_effect['attack'] = modified_effect['attack'] * 2

        elif effect_type == 'debuff_stats':
            if 'attack' in modified_effect:
                modified_effect['attack'] = modified_effect['attack'] * 2

        elif effect_type == 'summon_minion':
            modified_effect['summon_count'] = modified_effect.get('summon_count', 1) * 2
            if 'health' in modified_effect:
                modified_effect['health'] = modified_effect['health'] * 2
            if 'attack' in modified_effect:
                modified_effect['attack'] = modified_effect['attack'] * 2

        elif effect_type == 'permanent_stat_gain':
            if 'health' in modified_effect:
                modified_effect['health'] = modified_effect['health'] * 2
            if 'attack' in modified_effect:
                modified_effect['attack'] = modified_effect['attack'] * 2
            if 'max_stacks' in modified_effect and modified_effect['max_stacks'] < 999:
                modified_effect['max_stacks'] = modified_effect['max_stacks'] * 2

        elif effect_type == 'modify_fatigue':
            modified_effect['amount'] = modified_effect.get('amount', 20) * 2

        elif effect_type == 'damage_self':
            modified_effect['amount'] = modified_effect.get('amount', 1) * 2

        elif effect_type == 'move_minion':
            modified_effect['distance'] = modified_effect.get('distance', 1) * 2

        elif effect_type == 'destroy_and_transform':
            modified_effect['summon_count'] = modified_effect.get('summon_count', 2) * 2

        return modified_effect

    @staticmethod
    def resolve_trigger_queue(trigger_queue: TriggerQueue, context: Dict,
                            cast_used: Optional[List[bool]] = None) -> List[str]:
        """
        Resolve all triggers in the queue until empty

        Legacy method that wraps the new processor system.
        """
        processor = CombatEffects._get_processor()

        # Initialize processor with context if not already done
        processor.context_manager.initialize_combat(
            combat_state=context.get('combat_state', {}),
            player_band=context.get('player_band', []),
            enemy_band=context.get('enemy_band', []),
            registry=context.get('combat_registry'),
            run=context.get('run')
        )

        # Transfer the queue to the processor
        processor.trigger_queue = trigger_queue

        # Resolve all triggers
        return processor.resolve_all_triggers(cast_used)

    @staticmethod
    def create_assault_trigger(source_minion: Dict, context: Dict) -> List[Dict]:
        """Create assault trigger(s) for a minion"""
        assault_triggers = []
        assault_effects = CombatEffects.get_trigger_effects(source_minion, 'assault')

        for effect_data in assault_effects:
            assault_trigger = {
                'type': 'assault',
                'source_minion': source_minion,
                'effect_data': effect_data
            }
            assault_triggers.append(assault_trigger)

        return assault_triggers

    @staticmethod
    def create_cast_trigger(source_minion: Dict, context: Dict) -> List[Dict]:
        """Create cast trigger(s) for a minion"""
        cast_triggers = []
        cast_effects = CombatEffects.get_trigger_effects(source_minion, 'cast')

        for effect_data in cast_effects:
            cast_trigger = {
                'type': 'cast',
                'source_minion': source_minion,
                'effect_data': effect_data
            }
            cast_triggers.append(cast_trigger)

        return cast_triggers

    @staticmethod
    def is_minion_alive(minion: Dict) -> bool:
        """Check if a minion is still alive"""
        return minion.get('health', 0) > 0

    @staticmethod
    def apply_effect(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
        """
        Apply a single combat effect

        Legacy method that wraps the new effects system.
        """
        # Apply golden doubling if applicable
        acting_minion = context.get('acting_minion', context.get('attacker'))
        if acting_minion and acting_minion.get('golden', False):
            effect_data = CombatEffects.apply_golden_doubling(effect_data, acting_minion)

        # Use the new apply_effect function
        return apply_effect(effect_data, context)

    @staticmethod
    def apply_effects_list(effects_list: List[Dict], context: Dict) -> Tuple[bool, List[str], Dict]:
        """Apply multiple effects in sequence"""
        return apply_effects_list(effects_list, context)

    @staticmethod
    def get_trigger_effects(minion: Dict, trigger_type: str) -> List[Dict]:
        """Get all effects for a specific trigger type from a minion"""
        effect_key = f'{trigger_type}_effect'
        effect_data = minion.get(effect_key)

        if not effect_data:
            return []

        if isinstance(effect_data, list):
            return effect_data
        else:
            return [effect_data]

    @staticmethod
    def has_trigger_effects(minion: Dict, trigger_type: str) -> bool:
        """Check if a minion has effects for a specific trigger"""
        effect_key = f'{trigger_type}_effect'
        return effect_key in minion and minion[effect_key] is not None

    @staticmethod
    def create_combat_context(attacker: Optional[Dict], defender: Optional[Dict],
                             player_band: List[Dict], enemy_band: List[Dict],
                             run: Optional[Any] = None,
                             combat_registry: Optional[Any] = None,
                             combat_state: Optional[Dict] = None,
                             additional_data: Optional[Dict] = None) -> Dict:
        """
        Create a combat context dictionary for effect processing

        Legacy method maintained for compatibility.
        """
        context = {
            'attacker': attacker,
            'defender': defender,
            'player_band': player_band,
            'enemy_band': enemy_band,
            'absolute_player_band': player_band,
            'absolute_enemy_band': enemy_band,
            'run': run,
            'combat_registry': combat_registry,
            'combat_state': combat_state
        }

        if additional_data:
            context.update(additional_data)

        return context

    # Legacy private method mappings for any code that might use them
    @staticmethod
    def _process_assault_trigger(source_minion: Dict, effect_data: Dict,
                                context: Dict, trigger_queue: TriggerQueue) -> Tuple[bool, List[str], Dict]:
        """Legacy method - redirects to new system"""
        processor = CombatEffects._get_processor()
        processor.trigger_queue = trigger_queue
        effect_context = processor.context_manager.create_effect_context(
            EffectType.ABILITY, source_minion, 'assault'
        )
        return processor._process_assault_trigger(source_minion, effect_data, effect_context)

    @staticmethod
    def _process_cast_trigger(source_minion: Dict, effect_data: Dict,
                            context: Dict, trigger_queue: TriggerQueue,
                            cast_used: Optional[List[bool]] = None) -> Tuple[bool, List[str], Dict]:
        """Legacy method - redirects to new system"""
        processor = CombatEffects._get_processor()
        processor.trigger_queue = trigger_queue
        effect_context = processor.context_manager.create_effect_context(
            EffectType.SPELL, source_minion, 'cast'
        )
        return processor._process_cast_trigger(source_minion, effect_data, effect_context, cast_used)

    @staticmethod
    def _process_death_toll_trigger(source_minion: Dict, effect_data: Dict,
                                   context: Dict, trigger_queue: TriggerQueue) -> Tuple[bool, List[str], Dict]:
        """Legacy method - redirects to new system"""
        processor = CombatEffects._get_processor()
        processor.trigger_queue = trigger_queue
        effect_context = processor.context_manager.create_effect_context(
            EffectType.ABILITY, source_minion, 'death_toll'
        )
        return processor._process_death_toll_trigger(source_minion, effect_data, effect_context)

    @staticmethod
    def _process_rage_trigger(source_minion: Dict, effect_data: Dict,
                            context: Dict, trigger_queue: TriggerQueue) -> Tuple[bool, List[str], Dict]:
        """Legacy method - redirects to new system"""
        processor = CombatEffects._get_processor()
        processor.trigger_queue = trigger_queue
        effect_context = processor.context_manager.create_effect_context(
            EffectType.ABILITY, source_minion, 'rage'
        )
        return processor._process_rage_trigger(source_minion, effect_data, effect_context)

    @staticmethod
    def _check_deaths_and_generate_triggers(context: Dict) -> Tuple[bool, List[str], List[Dict]]:
        """Legacy method - redirects to new system"""
        processor = CombatEffects._get_processor()
        processor.context_manager.combat_registry = context.get('combat_registry')
        return processor._check_deaths_and_generate_triggers()


# Legacy export - TriggerQueue used to be in this file
__all__ = ['CombatEffects', 'TriggerQueue']