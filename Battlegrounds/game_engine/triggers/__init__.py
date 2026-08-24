"""
Triggers Package - Registry-based trigger system

This package contains the complete registry-driven trigger system:
- Registries: Define triggers and effects as data
- Processors: Generic processing based on registry definitions
- Registrar: Automatic trigger discovery and registration
- Supporting: Condition checking, context building, golden doubling

USAGE:
    from game_engine.triggers import TriggerRegistrar, GenericTriggerProcessor
    
ARCHITECTURE:
    Event → Registrar → Queue → Generic Processor → Effects
"""

# Registry definitions (data)
from .trigger_registry import (
    TRIGGER_REGISTRY,
    TriggerEvent,
    ConditionType,
    get_trigger_definition,
    get_all_triggers_for_event,
    validate_trigger_registry
)

from .effect_registry import (
    EFFECT_REGISTRY,
    get_effect_definition,
    get_golden_double_fields,
    validate_effect_registry
)

# Core processors
from .generic_processor import GenericTriggerProcessor
from .registrar import TriggerRegistrar

# Supporting systems
from .condition_checker import ConditionChecker
from .context_builder import ContextBuilder
from .golden_doubler import GoldenDoubler

# Package version
__version__ = '1.0.0'

# Public API
__all__ = [
    # Registries
    'TRIGGER_REGISTRY',
    'EFFECT_REGISTRY',
    'TriggerEvent',
    'ConditionType',
    'get_trigger_definition',
    'get_all_triggers_for_event',
    'get_effect_definition',
    'get_golden_double_fields',
    
    # Core processors
    'GenericTriggerProcessor',
    'TriggerRegistrar',
    
    # Supporting systems
    'ConditionChecker',
    'ContextBuilder',
    'GoldenDoubler',
    
    # Validation
    'validate_trigger_registry',
    'validate_effect_registry',
]