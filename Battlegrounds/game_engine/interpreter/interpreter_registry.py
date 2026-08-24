"""
Interpreter Command Registry - Metadata for all interpreter commands

Defines what the frontend needs for each command type:
- Default duration for animations
- Animation priority for ordering
- Required and optional fields
- Command categories

This is the API specification between backend and frontend.
"""

import logging

logger = logging.getLogger(__name__)

from enum import Enum


class CommandCategory(Enum):
    """Command categories for organization"""
    FLOW = 'flow'  # START, END, ROUND_START, TURN_START
    ATTACK = 'attack'  # DECLARE_ATTACK, COMBAT_DAMAGE, COUNTER_DAMAGE
    TRIGGER = 'trigger'  # TRIGGER_ASSAULT, TRIGGER_CAST, etc.
    EFFECT = 'effect'  # DEAL_DAMAGE, HEAL, BUFF_STATS, etc.
    SPECIAL = 'special'  # MULTI_ATTACK, FATIGUE_DAMAGE, etc.
    LOG = 'log'  # LOG messages


INTERPRETER_COMMAND_REGISTRY = {
    # ===== FLOW COMMANDS =====
    'START': {
        'category': CommandCategory.FLOW,
        'default_duration': 0,
        'animation_priority': 100,
        'required_fields': [],
        'optional_fields': ['player_band', 'enemy_band']
    },

    'END': {
        'category': CommandCategory.FLOW,
        'default_duration': 0,
        'animation_priority': 0,
        'required_fields': ['winner'],
        'optional_fields': ['rounds', 'attacks', 'final_player_band', 'final_enemy_band']
    },

    'ROUND_START': {
        'category': CommandCategory.FLOW,
        'default_duration': 200,
        'animation_priority': 90,
        'required_fields': ['round'],
        'optional_fields': []
    },

    'TURN_START': {
        'category': CommandCategory.FLOW,
        'default_duration': 100,
        'animation_priority': 85,
        'required_fields': [],
        'optional_fields': ['minion_name', 'side']
    },

    # ===== ATTACK COMMANDS =====
    'DECLARE_ATTACK': {
        'category': CommandCategory.ATTACK,
        'default_duration': 300,
        'animation_priority': 100,
        'required_fields': ['attacker_id', 'attacker_name', 'defender_id', 'defender_name'],
        'optional_fields': []
    },

    'ATTACK_CANCELLED': {
        'category': CommandCategory.ATTACK,
        'default_duration': 200,
        'animation_priority': 95,
        'required_fields': ['source_id', 'source_name', 'reason'],
        'optional_fields': ['target_id', 'target_name']  # Target may be None if attacker died
    },

    'COMBAT_DAMAGE': {
        'category': CommandCategory.ATTACK,
        'default_duration': 500,
        'animation_priority': 70,
        'required_fields': ['target_id', 'target_name', 'amount', 'source_id', 'source_name'],
        'optional_fields': ['obliterate_kill']
    },

    'COUNTER_DAMAGE': {
        'category': CommandCategory.ATTACK,
        'default_duration': 400,
        'animation_priority': 60,
        'required_fields': ['target_id', 'target_name', 'amount', 'source_id', 'source_name'],
        'optional_fields': ['obliterate_kill']
    },

    # ===== TRIGGER COMMANDS =====
    'TRIGGER_RAGE': {
        'category': CommandCategory.TRIGGER,
        'default_duration': 250,
        'animation_priority': 90,
        'required_fields': ['source_id', 'source_name'],
        'optional_fields': ['golden']
    },

    'TRIGGER_CALM': {
        'category': CommandCategory.TRIGGER,
        'default_duration': 250,
        'animation_priority': 90,
        'required_fields': ['source_id', 'source_name'],
        'optional_fields': ['golden']
    },

    'TRIGGER_ASSAULT': {
        'category': CommandCategory.TRIGGER,
        'default_duration': 250,
        'animation_priority': 80,
        'required_fields': ['source_id', 'source_name'],
        'optional_fields': ['golden']
    },

    'TRIGGER_CAST': {
        'category': CommandCategory.TRIGGER,
        'default_duration': 300,
        'animation_priority': 80,
        'required_fields': ['source_id', 'source_name'],
        'optional_fields': ['golden']
    },

    'TRIGGER_DEATH_TOLL': {
        'category': CommandCategory.TRIGGER,
        'default_duration': 300,
        'animation_priority': 40,
        'required_fields': ['source_id', 'source_name'],
        'optional_fields': ['golden']
    },

    'TRIGGER_ON_ANY_DEATH': {
        'category': CommandCategory.TRIGGER,
        'default_duration': 200,
        'animation_priority': 35,
        'required_fields': ['source_id', 'source_name'],
        'optional_fields': ['golden']
    },

    'TRIGGER_ON_ANY_CAST': {
        'category': CommandCategory.TRIGGER,
        'default_duration': 200,
        'animation_priority': 30,
        'required_fields': ['source_id', 'source_name'],
        'optional_fields': ['golden']
    },

    'TRIGGER_ON_ANY_SUMMON': {
        'category': CommandCategory.TRIGGER,
        'default_duration': 200,
        'animation_priority': 30,
        'required_fields': ['source_id', 'source_name'],
        'optional_fields': ['golden']
    },

    'TRIGGER_ON_ANY_DEATH_TOLL': {
        'category': CommandCategory.TRIGGER,
        'default_duration': 200,
        'animation_priority': 35,
        'required_fields': ['source_id', 'source_name'],
        'optional_fields': ['golden']
    },

    'TRIGGER_START_OF_COMBAT': {
        'category': CommandCategory.TRIGGER,
        'default_duration': 300,
        'animation_priority': 95,
        'required_fields': ['source_id', 'source_name'],
        'optional_fields': ['golden', 'band_type']
    },

    'TRIGGER_ON_DAMAGE': {
        'category': CommandCategory.TRIGGER,
        'default_duration': 250,
        'animation_priority': 75,
        'required_fields': ['source_id', 'source_name'],
        'optional_fields': ['golden', 'damage_amount', 'damage_source']
    },

    'TRIGGER_ON_ANY_LEAP': {
        'category': CommandCategory.TRIGGER,
        'default_duration': 200,
        'animation_priority': 30,
        'required_fields': ['source_id', 'source_name'],
        'optional_fields': ['golden', 'leaping_minion_id', 'minions_jumped']
    },

    # ===== EFFECT COMMANDS =====
    'DEAL_DAMAGE': {
        'category': CommandCategory.EFFECT,
        'default_duration': 400,
        'animation_priority': 65,
        'required_fields': ['target_id', 'target_name', 'amount', 'source_id', 'source_name'],
        'optional_fields': ['damage_type', 'trigger_type', 'golden', 'trigger_context'],
        'animation_overrides': {
            # Minion-specific damage animations
            'Wizard': {
                'animation_type': 'arcane_blast',
                'duration': 500
            }
        }
    },

    'HEAL': {
        'category': CommandCategory.EFFECT,
        'default_duration': 400,
        'animation_priority': 65,
        'required_fields': ['target_id', 'target_name', 'amount'],
        'optional_fields': ['source_id', 'source_name', 'is_self_heal', 'trigger_type', 'golden']
    },

    'BUFF_STATS': {
        'category': CommandCategory.EFFECT,
        'default_duration': 300,
        'animation_priority': 55,
        'required_fields': ['target_id', 'target_name'],
        'optional_fields': ['attack', 'health', 'source_id', 'source_name', 'is_temporary', 'trigger_type', 'golden']
    },

    'DEBUFF_STATS': {
        'category': CommandCategory.EFFECT,
        'default_duration': 300,
        'animation_priority': 55,
        'required_fields': ['target_id', 'target_name'],
        'optional_fields': ['attack', 'health', 'source_id', 'source_name', 'trigger_type', 'golden']
    },

    'SUMMON_MINION': {
        'category': CommandCategory.EFFECT,
        'default_duration': 600,
        'animation_priority': 30,
        'required_fields': ['minion', 'band', 'position'],
        'optional_fields': ['source_name', 'source_golden', 'trigger_type', 'summoned_name'],
        'animation_overrides': {
            # Minion-specific summon animations
            'Necromancer': {
                'animation_type': 'necromancer_raise_dead',
                'duration': 1200
            },
            'Dryad': {
                'animation_type': 'nature_growth',
                'duration': 800
            },
            'Old Cat Lady': {
                'animation_type': 'cat_meow_summon',
                'duration': 500
            }
        }
    },

    'DESTROY_MINION': {
        'category': CommandCategory.EFFECT,
        'default_duration': 500,
        'animation_priority': 75,
        'required_fields': ['target_id', 'target_name'],
        'optional_fields': ['source_id', 'source_name', 'saved_stats', 'stat_ratio', 'trigger_type']
    },

    'DEATH': {
        'category': CommandCategory.EFFECT,
        'default_duration': 500,
        'animation_priority': 50,
        'required_fields': ['minion_id', 'minion_name'],
        'optional_fields': ['band', 'position']
    },

    'REMOVE_FROM_BAND': {
        'category': CommandCategory.EFFECT,
        'default_duration': 200,
        'animation_priority': 20,
        'required_fields': ['minion_id', 'minion_name', 'band'],
        'optional_fields': ['position']
    },

    'MOVE_MINION': {
        'category': CommandCategory.EFFECT,
        'default_duration': 400,
        'animation_priority': 25,
        'required_fields': ['minion_id', 'minion_name', 'from_position', 'to_position'],
        'optional_fields': ['band', 'source_name', 'trigger_type']
    },

    'PERMANENT_STAT_GAIN': {
        'category': CommandCategory.EFFECT,
        'default_duration': 300,
        'animation_priority': 35,
        'required_fields': ['target_id', 'target_name'],
        'optional_fields': ['attack', 'health', 'source_name', 'trigger_type', 'golden']
    },

    'STUN': {
        'category': CommandCategory.EFFECT,
        'default_duration': 300,
        'animation_priority': 45,
        'required_fields': ['target_id', 'target_name', 'stun_count'],
        'optional_fields': ['source_name', 'trigger_type', 'golden']
    },

    'GIVE_KEYWORD': {
        'category': CommandCategory.EFFECT,
        'default_duration': 300,
        'animation_priority': 40,
        'required_fields': ['target_id', 'target_name', 'keyword'],
        'optional_fields': ['source_name', 'trigger_type', 'golden', 'effect_description']
    },

    'LEAP_MOVE': {
        'category': CommandCategory.EFFECT,
        'default_duration': 400,
        'animation_priority': 60,
        'required_fields': ['target_id', 'target_name'],
        'optional_fields': ['old_position', 'new_position', 'minions_jumped', 'source_name', 'trigger_type', 'golden']
    },

    'DEAL_AOE_DAMAGE': {
        'category': CommandCategory.EFFECT,
        'default_duration': 500,
        'animation_priority': 65,
        'required_fields': ['amount'],
        'optional_fields': ['target_count', 'source_id', 'source_name', 'damage_type', 'trigger_type', 'golden']
    },

    'APPLY_STUN': {
        'category': CommandCategory.EFFECT,
        'default_duration': 300,
        'animation_priority': 45,
        'required_fields': ['target_id', 'target_name'],
        'optional_fields': ['stun_amount', 'source_name', 'trigger_type', 'golden']
    },

    'GRANT_KEYWORD': {
        'category': CommandCategory.EFFECT,
        'default_duration': 300,
        'animation_priority': 40,
        'required_fields': ['target_id', 'target_name', 'keyword'],
        'optional_fields': ['source_name', 'trigger_type', 'golden']
    },

    'GRANT_EFFECT': {
        'category': CommandCategory.EFFECT,
        'default_duration': 300,
        'animation_priority': 40,
        'required_fields': ['target_id', 'target_name'],
        'optional_fields': ['effect_type', 'keyword', 'source_name', 'trigger_type', 'golden']
    },

    'TRANSFORM': {
        'category': CommandCategory.EFFECT,
        'default_duration': 600,
        'animation_priority': 50,
        'required_fields': ['target_id', 'target_name', 'new_minion_name'],
        'optional_fields': ['source_name', 'trigger_type', 'golden']
    },

    # ===== SPECIAL COMMANDS =====
    'MULTI_ATTACK': {
        'category': CommandCategory.SPECIAL,
        'default_duration': 200,
        'animation_priority': 80,
        'required_fields': ['attacker_id', 'attack_count'],
        'optional_fields': []
    },

    'FATIGUE_DAMAGE': {
        'category': CommandCategory.SPECIAL,
        'default_duration': 800,
        'animation_priority': 70,
        'required_fields': ['amount'],
        'optional_fields': ['affected_minions']
    },

    'STUN_SKIP': {
        'category': CommandCategory.SPECIAL,
        'default_duration': 400,
        'animation_priority': 50,
        'required_fields': ['minion_id', 'minion_name'],
        'optional_fields': ['stun_count']
    },

    'STUN_REDUCED': {
        'category': CommandCategory.SPECIAL,
        'default_duration': 200,
        'animation_priority': 40,
        'required_fields': [],
        'optional_fields': []
    },

    'AURA_RECALCULATION': {
        'category': CommandCategory.SPECIAL,
        'default_duration': 100,
        'animation_priority': 10,
        'required_fields': [],
        'optional_fields': ['reason']
    },

    'MODIFY_FATIGUE': {
        'category': CommandCategory.SPECIAL,
        'default_duration': 300,
        'animation_priority': 50,
        'required_fields': ['amount'],
        'optional_fields': ['fatigue_activated', 'source_name', 'trigger_type', 'golden']
    },

    'REDIRECT_DAMAGE': {
        'category': CommandCategory.SPECIAL,
        'default_duration': 400,
        'animation_priority': 60,
        'required_fields': ['amount', 'target_id', 'target_name'],
        'optional_fields': ['source_id', 'source_name', 'original_target_id', 'trigger_type', 'golden']
    },

    'PREVENT_DEATH': {
        'category': CommandCategory.SPECIAL,
        'default_duration': 500,
        'animation_priority': 80,
        'required_fields': ['target_id', 'target_name'],
        'optional_fields': ['source_name', 'trigger_type', 'golden']
    },

    'COPY_STATS': {
        'category': CommandCategory.SPECIAL,
        'default_duration': 400,
        'animation_priority': 45,
        'required_fields': ['target_id', 'target_name'],
        'optional_fields': ['source_id', 'source_name', 'attack', 'health', 'trigger_type', 'golden']
    },

    'FORCE_CAST': {
        'category': CommandCategory.SPECIAL,
        'default_duration': 300,
        'animation_priority': 70,
        'required_fields': ['target_id', 'target_name'],
        'optional_fields': ['source_name', 'trigger_type', 'golden']
    },

    'RECALCULATE_AURAS': {
        'category': CommandCategory.SPECIAL,
        'default_duration': 100,
        'animation_priority': 10,
        'required_fields': [],
        'optional_fields': ['reason', 'source_name']
    },

    'REDUCE_HIDE': {
        'category': CommandCategory.SPECIAL,
        'default_duration': 200,
        'animation_priority': 40,
        'required_fields': ['target_id', 'target_name'],
        'optional_fields': ['hide_remaining', 'source_name', 'trigger_type', 'golden']
    },

    'REDUCE_RING': {
        'category': CommandCategory.SPECIAL,
        'default_duration': 200,
        'animation_priority': 40,
        'required_fields': ['target_id', 'target_name'],
        'optional_fields': ['permanent_ring_count', 'source_name', 'trigger_type', 'golden']
    },

    'REMOVE_KEYWORD': {
        'category': CommandCategory.SPECIAL,
        'default_duration': 200,
        'animation_priority': 40,
        'required_fields': ['target_id', 'keyword'],
        'optional_fields': ['removed_from_combat', 'removed_from_band', 'source_name', 'trigger_type', 'golden']
    },

    'DIVIDE_ATTACK': {
        'category': CommandCategory.SPECIAL,
        'default_duration': 300,
        'animation_priority': 45,
        'required_fields': ['target_id', 'target_name'],
        'optional_fields': ['old_attack', 'new_attack', 'divisor', 'source_name', 'trigger_type', 'golden']
    },

    'MODIFY_GOLD': {
        'category': CommandCategory.SPECIAL,
        'default_duration': 300,
        'animation_priority': 50,
        'required_fields': ['amount'],
        'optional_fields': ['old_gold', 'new_gold', 'source_name', 'trigger_type', 'golden']
    },

    'TRANSFER_STUN': {
        'category': CommandCategory.SPECIAL,
        'default_duration': 400,
        'animation_priority': 50,
        'required_fields': ['to_target', 'stun_amount'],
        'optional_fields': ['from_targets', 'source_name', 'trigger_type', 'golden']
    },

    # ===== LOG COMMANDS =====
    'LOG': {
        'category': CommandCategory.LOG,
        'default_duration': 0,
        'animation_priority': 0,
        'required_fields': [],
        'optional_fields': ['message', 'log_type']
    }
}


def get_command_metadata(command_type: str) -> dict:
    """Get metadata for a command type"""
    return INTERPRETER_COMMAND_REGISTRY.get(command_type)


def get_default_duration(command_type: str) -> int:
    """Get default duration for a command type"""
    metadata = get_command_metadata(command_type)
    return metadata.get('default_duration', 200) if metadata else 200


def get_animation_priority(command_type: str) -> int:
    """Get animation priority for a command type"""
    metadata = get_command_metadata(command_type)
    return metadata.get('animation_priority', 50) if metadata else 50


def get_required_fields(command_type: str) -> list:
    """Get required fields for a command type"""
    metadata = get_command_metadata(command_type)
    return metadata.get('required_fields', []) if metadata else []


def get_optional_fields(command_type: str) -> list:
    """Get optional fields for a command type"""
    metadata = get_command_metadata(command_type)
    return metadata.get('optional_fields', []) if metadata else []


def get_animation_override(command_type: str, minion_name: str) -> dict:
    """Get animation override for a specific minion"""
    metadata = get_command_metadata(command_type)
    if not metadata:
        return None

    overrides = metadata.get('animation_overrides', {})
    return overrides.get(minion_name)


def validate_command(command: dict) -> tuple:
    """
    Validate that a command has all required fields

    Returns:
        Tuple of (is_valid, error_message)
    """
    cmd_type = command.get('cmd')
    if not cmd_type:
        return False, "Missing 'cmd' field"

    metadata = get_command_metadata(cmd_type)
    if not metadata:
        return False, f"Unknown command type: {cmd_type}"

    # Check required fields
    required = metadata.get('required_fields', [])
    for field in required:
        if field not in command:
            return False, f"Command {cmd_type} missing required field: {field}"

    return True, None


def validate_interpreter_registry():
    """Validate the interpreter command registry"""
    required_metadata_fields = ['category', 'default_duration', 'animation_priority',
                                'required_fields', 'optional_fields']

    errors = []
    for cmd_type, metadata in INTERPRETER_COMMAND_REGISTRY.items():
        for field in required_metadata_fields:
            if field not in metadata:
                errors.append(f"{cmd_type} missing metadata field: {field}")

    if errors:
        raise ValueError(f"Interpreter registry validation failed:\n" + "\n".join(errors))

    logger.debug(f"✓ Interpreter registry validated: {len(INTERPRETER_COMMAND_REGISTRY)} commands")


# Validate on import
validate_interpreter_registry()