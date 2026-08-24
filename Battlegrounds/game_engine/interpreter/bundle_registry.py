"""
Bundle Registry - Declarative definitions for animation bundles

Defines patterns for detecting multi-command animation sequences that should
be played as coordinated bundles (like wizard spell barrage, huntsman arrow shot).

Each bundle defines:
- Detection pattern: How to identify the bundle in command sequence
- Animation template: What template animation to use
- Coordination: How commands are bundled together
"""

import logging

logger = logging.getLogger(__name__)

from typing import Dict, List, Optional

BUNDLE_REGISTRY = {
    'wizard_spell_barrage': {
        'description': 'Wizard casts spell hitting multiple targets with lightning bolts',

        'detection': {
            # What command starts this bundle?
            'trigger_command': 'TRIGGER_CAST',

            # Filter for the source minion
            'source_filter': {
                'name': 'Wizard'
            },

            # Pattern for follow-up commands
            'follow_up_pattern': {
                'commands': ['DEAL_AOE_DAMAGE'],  # Wizard's AOE generates this command
                'same_source': True,  # Must be from same source?
                'max_count': 10,  # Maximum follow-up commands
                'stop_on_different_source': True,  # Stop when different source?
                'stop_on_other_trigger': True,  # Stop on other triggers?
                'allow_interleaved': False  # Allow other commands between?
            }
        },

        'animation': {
            'use_template_system': True,
            'template_name': 'wizard_spell_barrage',
            'bundle_type': 'wizard_bolt_barrage',  # For legacy compatibility

            # Animation metadata
            'duration': 1500,
            'firing_pattern': 'simultaneous',

            # Additional animation data
            'bolt_style': 'arcane',
            'coordination': 'parallel'
        }
    },

    'huntsman_arrow_shot': {
        'description': 'Huntsman fires arrow that embeds in target',

        'detection': {
            'trigger_command': 'TRIGGER_ASSAULT',

            'source_filter': {
                'name': 'Huntsman'
            },

            'follow_up_pattern': {
                'commands': ['DEAL_DAMAGE'],
                'same_source': True,
                'max_count': 1,  # Only one damage command
                'stop_on_different_source': True,
                'stop_on_other_trigger': True,
                'allow_interleaved': False
            }
        },

        'animation': {
            'use_template_system': True,
            'template_name': 'huntsman_arrow_shot',
            'bundle_type': 'huntsman_arrow',

            'duration': 800,
            'arrow_style': 'hunting',
            'embed_duration': 500
        }
    },

    'cabal_dark_bolt': {
        'description': 'Cabal fires dark bolts at lowest health enemies (multi-attack)',

        'detection': {
            'trigger_command': 'TRIGGER_CAST',

            'source_filter': {
                'name': 'Cabal'
            },

            'follow_up_pattern': {
                'commands': ['DEAL_DAMAGE', 'TRIGGER_CAST', 'ATTACK_CANCELLED'],  # Include cancelled attacks when target dies early
                'same_source': True,
                'max_count': 8,  # 4 attacks x 2 commands (cast + damage) = 8 max
                'stop_on_different_source': True,
                'stop_on_other_trigger': False,  # Don't stop on Cabal's own TRIGGER_CAST
                'allow_interleaved': True  # Allow cast/damage to interleave
            }
        },

        'animation': {
            'use_template_system': True,
            'template_name': 'cabal_dark_bolt',
            'bundle_type': 'cabal_dark_bolt',

            'duration': 800,
            'coordination': 'parallel'  # All bolts fire simultaneously
        }
    },

    # Template for adding new bundles - currently commented out
    #
    # 'necromancer_raise_dead': {
    #     'description': 'Necromancer raises skeleton(s) from the dead',
    #
    #     'detection': {
    #         'trigger_command': 'TRIGGER_DEATH_TOLL',
    #
    #         'source_filter': {
    #             'name': 'Necromancer'
    #         },
    #
    #         'follow_up_pattern': {
    #             'commands': ['SUMMON'],
    #             'same_source': True,
    #             'max_count': 3,
    #             'stop_on_different_source': True,
    #             'stop_on_other_trigger': True,
    #             'allow_interleaved': False
    #         }
    #     },
    #
    #     'animation': {
    #         'use_template_system': True,
    #         'template_name': 'necromancer_raise_dead',
    #         'bundle_type': 'necromancer_summon',
    #
    #         'duration': 1200,
    #         'summon_style': 'skeletal_rise',
    #         'coordination': 'sequence'
    #     }
    # },

    # 'chronomancer_cascade': {
    #     'description': 'Chronomancer forces another minion to cast and stuns them',
    #
    #     'detection': {
    #         'trigger_command': 'TRIGGER_ON_ANY_CAST',
    #
    #         'source_filter': {
    #             'name': 'Chronomancer'
    #         },
    #
    #         'follow_up_pattern': {
    #             'commands': ['FORCE_CAST', 'APPLY_STUN'],
    #             'same_source': True,
    #             'max_count': 2,
    #             'stop_on_different_source': True,
    #             'allow_interleaved': True  # Stun might come later
    #         }
    #     },
    #
    #     'animation': {
    #         'use_template_system': True,
    #         'template_name': 'chronomancer_cascade',
    #         'bundle_type': 'time_manipulation',
    #
    #         'duration': 1000,
    #         'effect_style': 'temporal',
    #         'coordination': 'sequence'
    #     }
    # },
}


def get_bundle_definition(bundle_type: str) -> Optional[Dict]:
    """Get bundle definition by type"""
    return BUNDLE_REGISTRY.get(bundle_type)


def get_all_bundle_types() -> List[str]:
    """Get list of all bundle types"""
    return list(BUNDLE_REGISTRY.keys())


def get_bundles_for_trigger(trigger_command: str) -> List[tuple]:
    """
    Get all bundle types that start with a specific trigger command

    Returns:
        List of (bundle_type, definition) tuples
    """
    matches = []
    for bundle_type, definition in BUNDLE_REGISTRY.items():
        if definition['detection']['trigger_command'] == trigger_command:
            matches.append((bundle_type, definition))
    return matches


def matches_source_filter(source_minion: Dict, source_filter: Dict) -> bool:
    """
    Check if a minion matches a source filter

    Args:
        source_minion: Minion to check
        source_filter: Filter criteria from bundle definition

    Returns:
        True if minion matches filter
    """
    if not source_filter:
        return True

    # Check name filter
    if 'name' in source_filter:
        if source_minion.get('name') != source_filter['name']:
            return False

    # Check type filter (could be added later)
    if 'type' in source_filter:
        minion_type = source_minion.get('type')
        filter_type = source_filter['type']

        # Handle multi-faction minions
        if isinstance(minion_type, list):
            if filter_type not in minion_type:
                return False
        else:
            if minion_type != filter_type:
                return False

    # Check keyword filter (could be added later)
    if 'has_keyword' in source_filter:
        from keywords import has_keyword
        if not has_keyword(source_minion, source_filter['has_keyword']):
            return False

    # Check golden filter (could be added later)
    if 'golden' in source_filter:
        if source_minion.get('golden', False) != source_filter['golden']:
            return False

    return True


def validate_bundle_registry():
    """Validate all bundle definitions"""
    required_fields = ['description', 'detection', 'animation']
    detection_fields = ['trigger_command', 'source_filter', 'follow_up_pattern']
    pattern_fields = ['commands', 'same_source', 'max_count']
    animation_fields = ['use_template_system', 'template_name', 'bundle_type']

    errors = []

    for bundle_type, definition in BUNDLE_REGISTRY.items():
        # Check top-level fields
        for field in required_fields:
            if field not in definition:
                errors.append(f"{bundle_type} missing field: {field}")

        # Check detection fields
        detection = definition.get('detection', {})
        for field in detection_fields:
            if field not in detection:
                errors.append(f"{bundle_type}.detection missing field: {field}")

        # Check pattern fields
        pattern = detection.get('follow_up_pattern', {})
        for field in pattern_fields:
            if field not in pattern:
                errors.append(f"{bundle_type}.detection.follow_up_pattern missing field: {field}")

        # Check animation fields
        animation = definition.get('animation', {})
        for field in animation_fields:
            if field not in animation:
                errors.append(f"{bundle_type}.animation missing field: {field}")

    if errors:
        raise ValueError(f"Bundle registry validation failed:\n" + "\n".join(errors))

    logger.debug(f"✓ Bundle registry validated: {len(BUNDLE_REGISTRY)} bundles")


# Validate on import
validate_bundle_registry()