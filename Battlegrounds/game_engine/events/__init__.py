"""
Events Package - Event system for the game engine

This package contains:
- events.py: Event definitions
- event_templates.py: Reusable screen template registry
- event_system.py: Event execution system
- event_helpers.py: Centralized helpers for formula/tooltip/condition/validation
- combat_events.py: Combat-specific events
"""

from .events import (
    ALL_CUSTOM_EVENTS,
    BASIC_EVENTS,
    STORY_EVENTS,
    REPEATABLE_EVENTS,
    GENERAL_EVENT_POOL,
    get_event,
    get_events_by_visit_rule,
    get_story_events,
    get_repeatable_events,
    validate_event,
    validate_all_events
)

from .event_templates import (
    EVENT_SCREEN_REGISTRY,
    EVENT_VISIT_RULES,
    get_screen_template,
    get_all_screen_types,
    get_screens_by_category,
    validate_screen_parameters,
    can_visit_event,
    mark_event_visited,
    validate_event_template_registry
)

from .event_helpers import (
    resolve_formula,
    resolve_tooltip,
    evaluate_condition,
    build_tooltip_context,
    validate_choice_option,
    validate_event_choices,
    validate_all_general_event_choices,
    CONDITION_HANDLERS
)

from .effect_actions import (
    execute_on_select,
    is_registered,
    get_all_handler_names,
    EFFECT_REGISTRY,
    CUSTOM_HANDLERS,
    ACTION_EXECUTORS
)

__all__ = [
    # From events.py
    'ALL_CUSTOM_EVENTS',
    'BASIC_EVENTS',
    'STORY_EVENTS',
    'REPEATABLE_EVENTS',
    'GENERAL_EVENT_POOL',
    'get_event',
    'get_events_by_visit_rule',
    'get_story_events',
    'get_repeatable_events',
    'validate_event',
    'validate_all_events',

    # From event_templates.py
    'EVENT_SCREEN_REGISTRY',
    'EVENT_VISIT_RULES',
    'get_screen_template',
    'get_all_screen_types',
    'get_screens_by_category',
    'validate_screen_parameters',
    'can_visit_event',
    'mark_event_visited',
    'validate_event_template_registry',

    # From event_helpers.py
    'resolve_formula',
    'resolve_tooltip',
    'evaluate_condition',
    'build_tooltip_context',
    'validate_choice_option',
    'validate_event_choices',
    'validate_all_general_event_choices',
    'CONDITION_HANDLERS',

    # From effect_actions.py
    'execute_on_select',
    'is_registered',
    'get_all_handler_names',
    'EFFECT_REGISTRY',
    'CUSTOM_HANDLERS',
    'ACTION_EXECUTORS',
]
