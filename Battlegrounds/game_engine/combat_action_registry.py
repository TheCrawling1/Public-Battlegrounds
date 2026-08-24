"""
Combat Action Registry - Declarative definitions for combat actions

Defines all combat-specific actions (damage, attacks, turns) as data.
Similar to trigger_registry and effect_registry but for combat mechanics.

Each action defines:
- What parameters it needs
- How to execute it (handler reference)
- How to send it to interpreter (field map)
"""


import logging

logger = logging.getLogger(__name__)

COMBAT_ACTION_REGISTRY = {
    'combat_damage': {
        'description': 'Normal attack damage with poke/obliterate/counter logic',
        'parameters': {
            'attacker': {'type': 'minion', 'required': True},
            'defender': {'type': 'minion', 'required': True},
            'base_damage': {'type': 'int', 'required': True},
            'base_counter': {'type': 'int', 'required': True},
            'has_poke': {'type': 'bool', 'required': False, 'default': False},
            'defender_cant_retaliate': {'type': 'bool', 'required': False, 'default': False}
        },
        'handler': {
            'module': 'game_engine.combat_actions',
            'function': 'process_combat_damage'
        },
        'generates_commands': ['COMBAT_DAMAGE', 'COUNTER_DAMAGE'],  # Can generate multiple
        'interpreter': {
            'command': 'COMBAT_DAMAGE',
            'field_map': {
                'target_id': 'changes.defender._combat_id',
                'target_name': 'changes.defender.name',
                'amount': 'changes.damage_dealt',
                'source_id': 'changes.attacker._combat_id',
                'source_name': 'changes.attacker.name',
                'obliterate_kill': 'changes.obliterate_kill'
            }
        }
    },

    'declare_attack': {
        'description': 'Declare an attack between attacker and defender',
        'parameters': {
            'attacker': {'type': 'minion', 'required': True},
            'defender': {'type': 'minion', 'required': True},
            'attacker_index': {'type': 'int', 'required': True}
        },
        'handler': {
            'module': 'game_engine.combat_actions',
            'function': 'process_declare_attack'
        },
        'generates_commands': ['DECLARE_ATTACK'],
        'interpreter': {
            'command': 'DECLARE_ATTACK',
            'field_map': {
                'attacker_id': 'changes.attacker._combat_id',
                'attacker_name': 'changes.attacker.name',
                'defender_id': 'changes.defender._combat_id',
                'defender_name': 'changes.defender.name'
            }
        }
    },

    'turn_start': {
        'description': 'Start of a minion\'s turn',
        'parameters': {
            'minion': {'type': 'minion', 'required': True},
            'side': {'type': 'string', 'required': True}  # 'player' or 'enemy'
        },
        'handler': {
            'module': 'game_engine.combat_actions',
            'function': 'process_turn_start'
        },
        'generates_commands': ['TURN_START'],
        'interpreter': {
            'command': 'TURN_START',
            'field_map': {
                'minion_id': 'changes.minion._combat_id',
                'minion_name': 'changes.minion.name',
                'side': 'changes.side'
            }
        }
    },

    'stun_skip': {
        'description': 'Minion skips turn due to stun',
        'parameters': {
            'minion': {'type': 'minion', 'required': True},
            'stun_count': {'type': 'int', 'required': True},
            'minion_index': {'type': 'int', 'required': True}
        },
        'handler': {
            'module': 'game_engine.combat_actions',
            'function': 'process_stun_skip'
        },
        'generates_commands': ['STUN_SKIP'],
        'interpreter': {
            'command': 'STUN_SKIP',
            'field_map': {
                'minion_id': 'changes.minion._combat_id',
                'minion_name': 'changes.minion.name',
                'stun_count': 'changes.stun_count'
            }
        }
    },

    'round_start': {
        'description': 'Start of a new combat round',
        'parameters': {
            'round': {'type': 'int', 'required': True}
        },
        'handler': {
            'module': 'game_engine.combat_actions',
            'function': 'process_round_start'
        },
        'generates_commands': ['ROUND_START'],
        'interpreter': {
            'command': 'ROUND_START',
            'field_map': {
                'round': 'changes.round'
            }
        }
    },

    'attack_cancelled': {
        'description': 'Attack cancelled due to target death or other reason',
        'parameters': {
            'attacker': {'type': 'minion', 'required': True},
            'defender': {'type': 'minion', 'required': False},  # May be None if attacker died
            'reason': {'type': 'string', 'required': True},  # 'defender_died', 'attacker_died', etc.
            'cast_used': {'type': 'bool', 'required': False, 'default': False}
        },
        'handler': {
            'module': 'game_engine.combat_actions',
            'function': 'process_attack_cancelled'
        },
        'generates_commands': ['ATTACK_CANCELLED'],
        'interpreter': {
            'command': 'ATTACK_CANCELLED',
            'field_map': {
                'reason': 'changes.reason',
                'source_id': 'changes.attacker._combat_id',
                'source_name': 'changes.attacker.name',
                'target_id': 'changes.defender._combat_id',
                'target_name': 'changes.defender.name'
            }
        }
    },

    'no_attack_skip': {
        'description': 'Minion skips turn due to 0 attack or can\'t attack',
        'parameters': {
            'minion': {'type': 'minion', 'required': True},
            'reason': {'type': 'string', 'required': True},  # 'cant_attack', 'zero_attack'
            'minion_index': {'type': 'int', 'required': True}
        },
        'handler': {
            'module': 'game_engine.combat_actions',
            'function': 'process_no_attack_skip'
        },
        'generates_commands': ['LOG'],
        'interpreter': {
            'command': 'LOG',
            'field_map': {
                'message': 'changes.log_message'
            }
        }
    },

    'cast_finished': {
        'description': 'Cast finished, no normal attack',
        'parameters': {
            'caster': {'type': 'minion', 'required': True},
            'caster_index': {'type': 'int', 'required': True}
        },
        'handler': {
            'module': 'game_engine.combat_actions',
            'function': 'process_cast_finished'
        },
        'generates_commands': ['LOG'],
        'interpreter': {
            'command': 'LOG',
            'field_map': {
                'message': 'changes.log_message'
            }
        }
    }
}


def get_action_definition(action_type: str) -> dict:
    """Get action definition from registry"""
    return COMBAT_ACTION_REGISTRY.get(action_type)


def get_all_action_types() -> list:
    """Get list of all action types"""
    return list(COMBAT_ACTION_REGISTRY.keys())


def validate_combat_action_registry():
    """Validate all action definitions have required fields"""
    required_fields = ['description', 'parameters', 'handler', 'generates_commands', 'interpreter']
    handler_fields = ['module', 'function']
    interpreter_fields = ['command', 'field_map']

    errors = []

    for action_type, definition in COMBAT_ACTION_REGISTRY.items():
        # Check top-level fields
        for field in required_fields:
            if field not in definition:
                errors.append(f"{action_type} missing field: {field}")

        # Check handler fields
        handler = definition.get('handler', {})
        for field in handler_fields:
            if field not in handler:
                errors.append(f"{action_type}.handler missing field: {field}")

        # Check interpreter fields
        interpreter = definition.get('interpreter', {})
        for field in interpreter_fields:
            if field not in interpreter:
                errors.append(f"{action_type}.interpreter missing field: {field}")

    if errors:
        raise ValueError(f"Combat action registry validation failed:\n" + "\n".join(errors))

    logger.debug(f"✓ Combat action registry validated: {len(COMBAT_ACTION_REGISTRY)} actions")


# Validate on import
validate_combat_action_registry()