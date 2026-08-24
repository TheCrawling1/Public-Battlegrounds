"""
Trigger Registry - Declarative definitions for all trigger types

This registry defines what triggers exist, when they fire, what conditions
must be met, and how to build their contexts.

UPDATED: Added combat keyword triggers (poke, obliterate, cleave)
These fire during combat and modify combat behavior through effects.
"""

from enum import Enum


class TriggerEvent(Enum):
    """When triggers fire"""
    ON_ATTACK_START = "on_attack_start"
    ON_ATTACK_END = "on_attack_end"
    ON_DEATH = "on_death"
    ON_ANY_DEATH = "on_any_death"
    ON_CAST = "on_cast"
    ON_ANY_CAST = "on_any_cast"
    ON_SUMMON = "on_summon"
    ON_ANY_SUMMON = "on_any_summon"
    ON_DAMAGE = "on_damage"
    START_OF_COMBAT = "start_of_combat"
    ON_ADJACENT_TRANSFORM = "on_adjacent_transform"
    ON_HIDE_LOST = "on_hide_lost"
    ON_LEAP = "on_leap"
    ON_ANY_LEAP = "on_any_leap"
    ON_COMBAT_DAMAGE_DECLARE = "on_combat_damage_declare"  # NEW: Before combat damage
    ON_ANY_DEATH_TOLL = "on_any_death_toll"  # NEW: When any death toll triggers


class ConditionType(Enum):
    """Types of conditions that can be checked"""
    NOT_HAS_KEYWORD = "not_has_keyword"
    POSITIVE_STAT = "positive_stat"
    IS_ALIVE = "is_alive"
    HAS_KEYWORD = "has_keyword"
    CAST_NOT_USED = "cast_not_used"
    # Add this line for identity checks (Frog Prince uses this):
    IS_SELF = "is_self"


# Registry of all trigger definitions
TRIGGER_REGISTRY = {
    'assault': {
        'keyword': 'assault',
        'event': TriggerEvent.ON_ATTACK_START,
        'conditions': [
            {'type': ConditionType.NOT_HAS_KEYWORD, 'keyword': 'cant_attack'},
            {'type': ConditionType.POSITIVE_STAT, 'stat': 'attack'}
        ],
        'priority': 'HIGH',
        'context_fields': {
            'defender': 'event.defender',
            'attacker': 'event.attacker',
            'acting_minion': 'source_minion',
            'trigger_context_source': 'source_minion',
            'trigger_context_target': 'event.defender'
        },
        'effect_field': 'assault_effect',
        'interpreter_command': 'TRIGGER_ASSAULT',
        'log_template': '⚡ {source_name} triggers Assault!',
        'is_watcher': False
    },

    'cast': {
    'keyword': 'cast',
    'event': TriggerEvent.ON_ATTACK_START,
    'conditions': [
        {'type': ConditionType.CAST_NOT_USED, 'cast_used_ref': 'cast_used'},
        {'type': ConditionType.NOT_HAS_KEYWORD, 'keyword': 'cant_cast'}
    ],  # Only check if cast hasn't been used yet and minion can cast,
        'priority': 'HIGH',
        'context_fields': {
            'defender': 'event.defender',
            'attacker': 'event.attacker',
            'acting_minion': 'source_minion',
            'caster': 'source_minion',
            'trigger_context_source': 'source_minion',
            'trigger_context_target': 'event.defender'
        },
        'effect_field': 'cast_effect',
        'interpreter_command': 'TRIGGER_CAST',
        'log_template': '🔮 {source_name} casts a spell!',
        'is_watcher': False
    },

    'rage': {
        'keyword': 'rage',
        'event': TriggerEvent.ON_ATTACK_START,
        'conditions': [
            {'type': ConditionType.CAST_NOT_USED, 'cast_used_ref': 'cast_used'}
        ],
        'priority': 'NORMAL',
        'context_fields': {
            'defender': 'event.defender',
            'attacker': 'event.attacker',
            'raging_minion': 'source_minion',
            'acting_minion': 'source_minion',
            'trigger_context_source': 'event.attacker',
            'trigger_context_target': 'event.defender'
        },
        'effect_field': 'rage_effect',
        'interpreter_command': 'TRIGGER_RAGE',
        'log_template': '😡 {source_name} triggers Rage!',
        'is_watcher': True,
        'exclude_self': True
    },

    'calm': {
        'keyword': 'calm',
        'event': TriggerEvent.ON_ANY_CAST,
        'conditions': [
            {'type': ConditionType.IS_ALIVE, 'target': 'source_minion'}
        ],
        'priority': 'NORMAL',
        'context_fields': {
            'caster': 'event.caster',
            'acting_minion': 'source_minion',
            'trigger_context_source': 'event.caster',
            'trigger_context_target': 'source_minion'
        },
        'effect_field': 'calm_effect',
        'interpreter_command': 'TRIGGER_CALM',
        'log_template': '🧘 {source_name} triggers Calm!',
        'is_watcher': True
    },

    'death_toll': {
        'keyword': 'death_toll',
        'event': TriggerEvent.ON_DEATH,
        'conditions': [],
        'priority': 'NORMAL',
        'context_fields': {
            'dying_minion': 'source_minion',
            'acting_minion': 'source_minion',
            'summoner': 'source_minion'
        },
        'effect_field': 'death_toll_effect',
        'interpreter_command': 'TRIGGER_DEATH_TOLL',
        'log_template': '💀 {source_name} triggers Death Toll!',
        'is_watcher': False
    },

    'on_any_death': {
        'keyword': 'on_any_death',
        'event': TriggerEvent.ON_ANY_DEATH,
        'conditions': [
            {'type': ConditionType.IS_ALIVE, 'target': 'source_minion'}
        ],
        'priority': 'NORMAL',
        'context_fields': {
            'dying_minion': 'event.dying_minion',
            'acting_minion': 'source_minion',
            'trigger_context_source': 'event.dying_minion',
            'trigger_context_target': 'source_minion'
        },
        'effect_field': 'on_any_death_effect',
        'interpreter_command': 'TRIGGER_ON_ANY_DEATH',
        'log_template': '👁️ {source_name} witnesses death!',
        'is_watcher': True
    },

    'on_any_cast': {
        'keyword': 'on_any_cast',
        'event': TriggerEvent.ON_ANY_CAST,
        'conditions': [
            {'type': ConditionType.IS_ALIVE, 'target': 'source_minion'}
        ],
        'priority': 'NORMAL',
        'context_fields': {
            'caster': 'event.caster',
            'acting_minion': 'source_minion',
            'trigger_context_source': 'event.caster',
            'trigger_context_target': 'source_minion'
        },
        'effect_field': 'on_any_cast_effect',
        'interpreter_command': 'TRIGGER_ON_ANY_CAST',
        'log_template': '📖 {source_name} reacts to spell!',
        'is_watcher': True
    },

    'on_any_summon': {
        'keyword': 'on_any_summon',
        'event': TriggerEvent.ON_ANY_SUMMON,
        'conditions': [
            {'type': ConditionType.IS_ALIVE, 'target': 'source_minion'}
        ],
        'priority': 'NORMAL',
        'context_fields': {
            'summoned_minion': 'event.summoned_minion',
            'summoner': 'event.summoner',
            'acting_minion': 'source_minion',
            'trigger_context_source': 'event.summoner',
            'trigger_context_target': 'event.summoned_minion'
        },
        'effect_field': 'on_any_summon_effect',
        'interpreter_command': 'TRIGGER_ON_ANY_SUMMON',
        'log_template': '👁️ {source_name} witnesses summon!',
        'is_watcher': True
    },

    'on_damage': {
        'keyword': 'on_damage',
        'event': TriggerEvent.ON_DAMAGE,
        'conditions': [
            {'type': ConditionType.IS_ALIVE, 'target': 'source_minion'}
        ],
        'priority': 'NORMAL',
        'context_fields': {
            'damaged_minion': 'source_minion',
            'acting_minion': 'source_minion',
            'damage_amount': 'event.damage_amount',
            'damage_source': 'event.damage_source',
            'damage_dealer': 'event.damage_dealer',
            'trigger_context_source': 'source_minion',
            'trigger_context_target': 'event.damage_dealer'
        },
        'effect_field': 'on_damage_effect',
        'interpreter_command': 'TRIGGER_ON_DAMAGE',
        'log_template': '🩸 {source_name} reacts to damage!',
        'is_watcher': False
    },

    'start_of_combat': {
        'keyword': None,
        'event': TriggerEvent.START_OF_COMBAT,
        'conditions': [],
        'priority': 'NORMAL',
        'context_fields': {
            'acting_minion': 'source_minion',
            'trigger_context_source': 'source_minion'
        },
        'effect_field': 'start_of_combat_effect',
        'requires_effect_field': True,
        'interpreter_command': 'TRIGGER_START_OF_COMBAT',
        'log_template': '🎬 {source_name} triggers start of combat!',
        'is_watcher': False
    },

    'on_adjacent_transform': {
        'keyword': 'on_adjacent_transform',
        'event': TriggerEvent.ON_ADJACENT_TRANSFORM,
        'conditions': [
            {'type': ConditionType.IS_ALIVE, 'target': 'source_minion'}
        ],
        'priority': 'NORMAL',
        'context_fields': {
            'transformed_minion': 'event.transformed_minion',
            'acting_minion': 'source_minion',
            'trigger_context_source': 'event.transformed_minion',
            'trigger_context_target': 'source_minion'
        },
        'effect_field': 'on_adjacent_transform_effect',
        'interpreter_command': 'TRIGGER_ON_ADJACENT_TRANSFORM',
        'log_template': '🔄 {source_name} reacts to transformation!',
        'is_watcher': True
    },

    'on_hide_lost': {
        'keyword': 'on_hide_lost',
        'event': TriggerEvent.ON_HIDE_LOST,
        'conditions': [
            {'type': ConditionType.IS_ALIVE, 'target': 'source_minion'}
        ],
        'priority': 'NORMAL',
        'context_fields': {
            'acting_minion': 'source_minion',
            'trigger_context_source': 'source_minion'
        },
        'effect_field': 'on_hide_lost_effect',
        'interpreter_command': 'TRIGGER_ON_HIDE_LOST',
        'log_template': '👁️ {source_name} loses hide!',
        'is_watcher': False
    },

    'on_any_leap': {
        'keyword': 'on_any_leap',
        'event': TriggerEvent.ON_ANY_LEAP,
        'conditions': [
            {'type': ConditionType.IS_ALIVE, 'target': 'source_minion'}
        ],
        'priority': 'NORMAL',
        'context_fields': {
            'leaping_minion': 'event.leaping_minion',
            'acting_minion': 'source_minion',
            'trigger_context_source': 'event.leaping_minion',
            'trigger_context_target': 'source_minion',
            'minions_jumped': 'event.minions_jumped',
            'starting_position': 'event.starting_position',
            'ending_position': 'event.ending_position'
        },
        'effect_field': 'on_any_leap_effect',
        'interpreter_command': 'TRIGGER_ON_ANY_LEAP',
        'log_template': '👁️ {source_name} witnesses leap!',
        'is_watcher': True
    },

    'on_any_death_toll': {
        'keyword': 'on_any_death_toll',
        'event': TriggerEvent.ON_ANY_DEATH_TOLL,
        'conditions': [
            {'type': ConditionType.IS_ALIVE, 'target': 'source_minion'}
        ],
        'priority': 'NORMAL',
        'context_fields': {
            'death_toll_minion': 'event.death_toll_minion',
            'acting_minion': 'source_minion',
            'trigger_context_source': 'event.death_toll_minion',
            'trigger_context_target': 'source_minion',
            'is_additional_trigger': 'event.is_additional_trigger'
        },
        'effect_field': 'on_any_death_toll_effect',
        'interpreter_command': 'TRIGGER_ON_ANY_DEATH_TOLL',
        'log_template': '⚰️ {source_name} witnesses death toll!',
        'is_watcher': True
    },

    # ===== NEW: COMBAT KEYWORD TRIGGERS =====
    # These fire during combat damage to modify combat behavior

    'combat_poke': {
        'keyword': 'poke',
        'event': TriggerEvent.ON_COMBAT_DAMAGE_DECLARE,
        'conditions': [
            {'type': ConditionType.NOT_HAS_KEYWORD, 'keyword': 'cant_attack'},
            {'type': ConditionType.POSITIVE_STAT, 'stat': 'attack'}
        ],
        'priority': 'IMMEDIATE',  # Must happen before damage calculation
        'context_fields': {
            'attacker': 'event.attacker',
            'defender': 'event.defender',
            'acting_minion': 'source_minion'
        },
        'effect_field': 'poke_effect',
        'default_effect': {
            'type': 'prevent_counter_damage'
        },
        'interpreter_command': None,  # No separate interpreter command
        'log_template': '🏹 {source_name} uses Poke!',
        'is_watcher': False
    },

    'combat_obliterate': {
        'keyword': 'obliterate',
        'event': TriggerEvent.ON_COMBAT_DAMAGE_DECLARE,
        'conditions': [
            {'type': ConditionType.NOT_HAS_KEYWORD, 'keyword': 'cant_attack'},
            {'type': ConditionType.POSITIVE_STAT, 'stat': 'attack'}
        ],
        'priority': 'IMMEDIATE',  # Must happen before damage calculation
        'context_fields': {
            'attacker': 'event.attacker',
            'defender': 'event.defender',
            'acting_minion': 'source_minion'
        },
        'effect_field': 'obliterate_effect',
        'default_effect': {
            'type': 'mark_obliterate',
            'target': 'defender'
        },
        'interpreter_command': None,  # No separate interpreter command
        'log_template': '💀⚡ {source_name} will obliterate!',
        'is_watcher': False
    },

    'combat_cleave': {
        'keyword': 'cleave',
        'event': TriggerEvent.ON_COMBAT_DAMAGE_DECLARE,
        'conditions': [
            {'type': ConditionType.NOT_HAS_KEYWORD, 'keyword': 'cant_attack'},
            {'type': ConditionType.POSITIVE_STAT, 'stat': 'attack'}
        ],
        'priority': 'LOW',  # Happens after main damage
        'context_fields': {
            'attacker': 'event.attacker',
            'defender': 'event.defender',
            'acting_minion': 'source_minion',
            'damage_dealt': 'event.damage_dealt'
        },
        'effect_field': 'cleave_effect',
        'default_effect': {
            'type': 'deal_cleave_damage',
            'adjacent_count': 1
        },
        'interpreter_command': None,  # No separate interpreter command
        'log_template': '🗡️ {source_name} cleaves!',
        'is_watcher': False
    }
}


def get_trigger_definition(trigger_type: str) -> dict:
    """Get trigger definition from registry"""
    return TRIGGER_REGISTRY.get(trigger_type)


def get_all_triggers_for_event(event: TriggerEvent) -> dict:
    """Get all triggers that fire on a specific event"""
    return {
        trigger_type: definition
        for trigger_type, definition in TRIGGER_REGISTRY.items()
        if definition['event'] == event
    }


def validate_trigger_registry():
    """Validate all trigger definitions"""
    for trigger_type, definition in TRIGGER_REGISTRY.items():
        # Validate required fields
        required = ['event', 'priority', 'context_fields', 'is_watcher']
        for field in required:
            if field not in definition:
                raise ValueError(f"Trigger '{trigger_type}' missing required field: {field}")

        # Validate keyword or effect_field
        if not definition.get('requires_effect_field'):
            if 'keyword' not in definition:
                raise ValueError(f"Trigger '{trigger_type}' must have 'keyword' or 'requires_effect_field'")

        # Validate priority
        valid_priorities = ['IMMEDIATE', 'DEATH', 'HIGH', 'NORMAL', 'LOW']
        if definition['priority'] not in valid_priorities:
            raise ValueError(f"Trigger '{trigger_type}' has invalid priority: {definition['priority']}")


# Validate on import
validate_trigger_registry()