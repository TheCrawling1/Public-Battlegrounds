"""
Generic condition checking system

Evaluates conditions defined in trigger registry.

UPDATED: Added EVENT_MINION_NOT_HAS_KEYWORD condition for checking keywords on event data minions
FIXED: Rage can now check if the attacker has cast keyword
FIXED: Replaced WATCHER_ALIVE with IS_ALIVE that supports target parameter
"""

import logging

logger = logging.getLogger(__name__)

from .trigger_registry import ConditionType
from keywords import has_keyword


class ConditionChecker:
    """Evaluates trigger conditions from registry definitions"""

    def check_condition(self, condition: dict, minion: dict, event_data: dict = None) -> bool:
        """
        Check if a condition is met

        Args:
            condition: Condition definition from registry
            minion: The minion to check (usually source_minion)
            event_data: Additional event context

        Returns:
            True if condition is met
        """
        condition_type = condition.get('type')

        if condition_type == ConditionType.NOT_HAS_KEYWORD:
            return self._check_not_has_keyword(minion, condition)

        elif condition_type == ConditionType.HAS_KEYWORD:
            return self._check_has_keyword(minion, condition)

        elif condition_type == ConditionType.POSITIVE_STAT:
            return self._check_positive_stat(minion, condition)

        elif condition_type == ConditionType.IS_ALIVE:
            return self._check_is_alive(minion, condition, event_data)

        elif condition_type == ConditionType.CAST_NOT_USED:
            return self._check_cast_not_used(minion, condition)

        elif condition_type == ConditionType.STAT_GREATER_THAN:
            return self._check_stat_comparison(minion, condition, greater=True)

        elif condition_type == ConditionType.STAT_LESS_THAN:
            return self._check_stat_comparison(minion, condition, greater=False)

        elif condition_type == ConditionType.EVENT_MINION_NOT_HAS_KEYWORD:
            return self._check_event_minion_not_has_keyword(minion, condition, event_data)

        elif condition_type == ConditionType.CAST_NOT_USED:
            return self._check_cast_not_used(minion, condition)

        else:
            logger.debug(f"[CONDITION] Unknown condition type: {condition_type}")
            return True  # Default to allowing trigger

    def check_all_conditions(self, conditions: list, minion: dict, event_data: dict = None) -> bool:
        """Check if ALL conditions are met (AND logic)"""
        for condition in conditions:
            if not self.check_condition(condition, minion, event_data):
                return False
        return True

    def _check_not_has_keyword(self, minion: dict, condition: dict) -> bool:
        """Check minion does NOT have a keyword"""
        keyword = condition['keyword']
        result = not has_keyword(minion, keyword)
        return result

    def _check_has_keyword(self, minion: dict, condition: dict) -> bool:
        """Check minion HAS a keyword"""
        keyword = condition['keyword']
        result = has_keyword(minion, keyword)
        return result

    def _check_positive_stat(self, minion: dict, condition: dict) -> bool:
        """Check minion has positive value for a stat"""
        stat = condition['stat']
        value = minion.get(stat, 0)
        result = value > 0
        return result

    def _check_is_alive(self, minion: dict, condition: dict, event_data: dict = None) -> bool:
        """
        Check if a minion is alive (health > 0)

        Can specify a target to check instead of the default minion:
        {'type': ConditionType.IS_ALIVE, 'target': 'source_minion'}
        """
        target_spec = condition.get('target')

        # If no target specified, check the passed minion
        if not target_spec or target_spec == 'source_minion':
            target_minion = minion
        # Can add more target resolution here if needed
        # elif target_spec == 'event.attacker':
        #     target_minion = event_data.get('attacker') if event_data else None
        else:
            # Default to the passed minion if target spec not recognized
            target_minion = minion

        if not target_minion:
            return False

        result = target_minion.get('health', 0) > 0
        return result

    def _check_stat_comparison(self, minion: dict, condition: dict, greater: bool) -> bool:
        """Check stat comparison"""
        stat = condition['stat']
        value = condition['value']
        minion_value = minion.get(stat, 0)

        if greater:
            result = minion_value > value
        else:
            result = minion_value < value

        return result

    def _check_event_minion_not_has_keyword(self, minion: dict, condition: dict, event_data: dict) -> bool:
        """
        Check that a minion from event_data does NOT have a keyword

        Used for triggers like Rage that need to check if the attacker has 'cast'
        """
        if not event_data:
            return False

        event_minion_key = condition.get('event_minion_key')
        keyword = condition.get('keyword')

        if not event_minion_key or not keyword:
            return False

        event_minion = event_data.get(event_minion_key)
        if not event_minion:
            return False

        result = not has_keyword(event_minion, keyword)
        return result

    def _check_cast_not_used(self, minion: dict, condition: dict) -> bool:
        """Check that cast has not been used yet this combat"""
        cast_used_ref = condition.get('cast_used_ref', 'cast_used')
        result = not minion.get(cast_used_ref, False)
        return result