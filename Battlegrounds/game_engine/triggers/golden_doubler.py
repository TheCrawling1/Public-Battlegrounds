"""
Golden Doubler - Applies golden doubling to effects based on registry

Uses effect registry to know which fields should be doubled.
"""

import copy
from typing import Dict, List
from .effect_registry import get_golden_double_fields, get_effect_definition


class GoldenDoubler:
    """Handles golden minion effect doubling"""

    def apply_golden_doubling(self, effect_data, minion: Dict):
        """
        Apply golden doubling to an effect if minion is golden

        Args:
            effect_data: Effect data to potentially double (Dict or List)
            minion: Minion performing the effect

        Returns:
            Modified effect_data (or original if not golden)
        """
        if not minion.get('golden', False):
            return effect_data

        # Handle arrays of effects (like Tooth Fairy's assault)
        if isinstance(effect_data, list):
            return self.apply_golden_doubling_to_list(effect_data, minion)

        effect_type = effect_data.get('type')
        if not effect_type:
            return effect_data

        # Get fields that should be doubled from registry
        fields_to_double = get_golden_double_fields(effect_type)

        if not fields_to_double:
            # Effect has no fields to double (or not in registry)
            return effect_data

        # Make a copy to avoid mutating original
        modified = copy.deepcopy(effect_data)

        # Double each field
        for field in fields_to_double:
            if field in modified:
                modified[field] *= 2

        return modified

    def apply_golden_doubling_to_list(self, effects: List[Dict], minion: Dict) -> List[Dict]:
        """Apply golden doubling to a list of effects"""
        if not minion.get('golden', False):
            return effects

        return [self.apply_golden_doubling(effect, minion) for effect in effects]

    def should_apply_doubling(self, trigger_data: Dict) -> bool:
        """
        Check if golden doubling should be applied

        Used to prevent double-application when effects are already doubled

        Args:
            trigger_data: Trigger data that may have 'golden_effects_applied' flag

        Returns:
            True if doubling should be applied
        """
        return not trigger_data.get('golden_effects_applied', False)