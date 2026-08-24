"""
Context Builder - Resolves registry path specs to actual values

Handles path resolution like:
- 'source_minion' → the acting minion
- 'event.defender' → defender from event data
- 'event.summoned_minion' → summoned minion from summon event
"""

from typing import Dict, Any, Optional


class ContextBuilder:
    """Builds context dictionaries from registry definitions"""

    def __init__(self, context_manager):
        """
        Args:
            context_manager: The CombatContextManager for creating base contexts
        """
        self.context_manager = context_manager

    def build_trigger_context(self,
                              trigger_definition: Dict,
                              source_minion: Dict,
                              event_data: Dict,
                              base_context: Optional[Dict] = None) -> Dict:
        """
        Build a complete context for a trigger based on registry definition

        Args:
            trigger_definition: Definition from TRIGGER_REGISTRY
            source_minion: The minion with the trigger
            event_data: Data from the event that fired the trigger
            base_context: Optional base context to extend

        Returns:
            Complete context dictionary
        """
        # Start with base context or create new one
        if base_context is None:
            base_context = self.context_manager.create_combat_context_dict()

        context = dict(base_context)

        # Add trigger source
        trigger_type = trigger_definition.get('keyword', 'unknown')
        context['trigger_source'] = trigger_type

        # Build context fields from definition
        field_map = trigger_definition.get('context_fields', {})

        for context_key, source_path in field_map.items():
            value = self.resolve_path(source_path, {
                'source_minion': source_minion,
                'event': event_data
            })
            context[context_key] = value

        return context

    def resolve_path(self, path: str, data: Dict) -> Any:
        """
        Resolve a dot-notation path to its value

        Examples:
            'source_minion' → data['source_minion']
            'event.defender' → data['event']['defender']
            'event.summoned_minion' → data['event']['summoned_minion']

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
            else:
                # Can't traverse further
                return None

        return current

    def resolve_field_map(self, field_map: Dict, data: Dict) -> Dict:
        """
        Resolve multiple fields at once

        Args:
            field_map: Dictionary of {output_key: path_string}
            data: Data to resolve from

        Returns:
            Dictionary of resolved values
        """
        resolved = {}

        for key, path in field_map.items():
            resolved[key] = self.resolve_path(path, data)

        return resolved