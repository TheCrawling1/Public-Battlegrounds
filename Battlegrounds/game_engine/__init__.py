"""
Game Engine Package - Modular game systems for Auto Battler Arena

This package contains all the core game systems including the newly
refactored combat effects system with improved modularity and dev mode support.
"""

# Core game controllers
from .game_controller import GameController
from .events.event_system import EventSystem
from .selection_system import SelectionSystem
from .band_manager import BandManager
from .zone_controller import ZoneController
from .sub_ring_controller import SubRingController

# Combat systems
from .combat_system import CombatSystem
from .combat_registry import CombatRegistry

# New modular trigger and effects system
from .trigger_queue import TriggerQueue, TriggerPriority
from .trigger_processor import TriggerProcessor
from .combat_context import CombatContextManager, EffectContext, EffectType, DamageSource
from .events.combat_events import CombatEventSystem, CombatEventType, CombatEvent, EventListener

# Effects modules
from .effects import (
    apply_effect,
    apply_effects_list,
    get_effect_description,
    validate_effect_data,
    get_available_effect_types,
    register_custom_effect
)

# Legacy compatibility - CombatEffects and TriggerQueue were previously in combat_effects.py
# We import them here for backward compatibility
from .combat_effects import CombatEffects

__all__ = [
    # Core controllers
    'GameController',
    'EventSystem',
    'SelectionSystem',
    'BandManager',
    'ZoneController',
    'SubRingController',

    # Combat systems
    'CombatSystem',
    'CombatRegistry',

    # Trigger and queue system
    'TriggerQueue',
    'TriggerPriority',
    'TriggerProcessor',

    # Context and events
    'CombatContextManager',
    'EffectContext',
    'EffectType',
    'DamageSource',
    'CombatEventSystem',
    'CombatEventType',
    'CombatEvent',
    'EventListener',

    # Effects functions
    'apply_effect',
    'apply_effects_list',
    'get_effect_description',
    'validate_effect_data',
    'get_available_effect_types',
    'register_custom_effect',

    # Legacy compatibility
    'CombatEffects',
]

# Version info
__version__ = '2.0.0'  # Major version bump for the refactored effects system