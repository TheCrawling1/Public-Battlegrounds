"""
Interpreter Package - Registry-based interpreter system

This package contains the complete registry-driven interpreter system:
- Registries: Define commands and bundles as data
- Builders: Generic command construction from effect results
- Detectors: Generic bundle detection from command patterns
- Combat Interpreter: Orchestrates command sequence generation

USAGE:
    from game_engine.interpreter import CommandBuilder, BundleDetector, CombatActionBuilder

ARCHITECTURE:
    Effect → Command Builder → Command Sequence → Bundle Detector → Frontend
    Combat Action → Combat Action Builder → Command Sequence → Frontend
"""

# Registry definitions (data)
from .interpreter_registry import (
    INTERPRETER_COMMAND_REGISTRY,
    CommandCategory,
    get_command_metadata,
    get_default_duration,
    get_animation_priority,
    get_required_fields,
    get_optional_fields,
    get_animation_override,
    validate_command,
    validate_interpreter_registry
)

from .bundle_registry import (
    BUNDLE_REGISTRY,
    get_bundle_definition,
    get_all_bundle_types,
    get_bundles_for_trigger,
    matches_source_filter,
    validate_bundle_registry
)

# Builders and Detectors
from .command_builder import CommandBuilder
from .bundle_detector import BundleDetector
from .combat_action_builder import CombatActionBuilder

# Package version
__version__ = '1.0.0'

# Public API
__all__ = [
    # Registries
    'INTERPRETER_COMMAND_REGISTRY',
    'BUNDLE_REGISTRY',
    'CommandCategory',
    'get_command_metadata',
    'get_default_duration',
    'get_animation_priority',
    'get_required_fields',
    'get_optional_fields',
    'get_animation_override',
    'get_bundle_definition',
    'get_all_bundle_types',
    'get_bundles_for_trigger',
    'matches_source_filter',

    # Builders and Detectors
    'CommandBuilder',
    'BundleDetector',
    'CombatActionBuilder',

    # Validation
    'validate_command',
    'validate_interpreter_registry',
    'validate_bundle_registry',
]