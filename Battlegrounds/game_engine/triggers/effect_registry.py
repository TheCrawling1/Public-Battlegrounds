"""
Effect Registry - Declarative definitions for all effect types

Each effect defines:
- What parameters it needs
- How to execute it
- What fields to double for golden minions
- How to send to interpreter

UPDATED: Added combat keyword effects (prevent_counter_damage, mark_obliterate, deal_cleave_damage)
"""


import logging

logger = logging.getLogger(__name__)

EFFECT_REGISTRY = {
    'deal_damage': {
        'category': 'damage',
        'parameters': {
            'amount': {'type': 'int', 'required': True, 'golden_double': True},
            'target': {'type': 'target_spec', 'required': True, 'golden_double': False},
            'target_count': {'type': 'int', 'required': False, 'golden_double': True, 'default': 1},
            'damage_type': {'type': 'string', 'required': False, 'default': 'ability'}
        },
        'executor': {
            'module': 'game_engine.effects.damage_effects',
            'function': 'deal_damage'
        },
        'interpreter': {
            'command': 'DEAL_DAMAGE',
            'field_map': {
                'target_id': 'changes.targets.0._combat_id',
                'target_name': 'changes.targets.0.name',
                'amount': 'changes.damage_dealt',
                'source_id': 'context.source._combat_id',
                'source_name': 'context.source.name',
                'damage_type': 'effect_data.damage_type'
            },
            'sync_check': {
                'multi_entity_key': 'targets',
                # damage_dealt is aggregate (amount * len(targets)); each per-target
                # command should carry amount, not the aggregate.
                'per_emit_from_effect_data': {'damage_dealt': 'amount'}
            }
        }
    },

    'heal': {
        'category': 'healing',
        'parameters': {
            'amount': {'type': 'int', 'required': True, 'golden_double': True},
            'target': {'type': 'target_spec', 'required': True, 'golden_double': False}
        },
        'executor': {
            'module': 'game_engine.effects.damage_effects',
            'function': 'heal'
        },
        'interpreter': {
            'command': 'HEAL',
            'field_map': {
                'target_id': 'changes.targets.0._combat_id',
                'target_name': 'changes.targets.0.name',
                'amount': 'changes.healing_done',
                'source_id': 'context.source._combat_id',
                'source_name': 'context.source.name'
            },
            'sync_check': {'multi_entity_key': 'targets'}
        }
    },

    'heal_self': {
        'category': 'healing',
        'parameters': {
            'amount': {'type': 'int', 'required': True, 'golden_double': True}
        },
        'executor': {
            'module': 'game_engine.effects.damage_effects',
            'function': 'heal_self'
        },
        'interpreter': {
            'command': 'HEAL',
            'field_map': {
                'target_id': 'context.acting_minion._combat_id',
                'amount': 'changes.healing_done'
            }
        }
    },

    'damage_self': {
        'category': 'damage',
        'parameters': {
            'amount': {'type': 'int', 'required': True, 'golden_double': True}
        },
        'executor': {
            'module': 'game_engine.effects.damage_effects',
            'function': 'damage_self'
        },
        'interpreter': {
            'command': 'DEAL_DAMAGE',
            'field_map': {
                'target_id': 'context.acting_minion._combat_id',
                'amount': 'changes.damage_dealt'
            }
        }
    },

    'deal_aoe_damage': {
        'category': 'damage',
        'parameters': {
            'amount': {'type': 'int', 'required': True, 'golden_double': True},
            'target': {'type': 'target_spec', 'required': True, 'golden_double': False},
            'max_targets': {'type': 'int', 'required': False, 'golden_double': True, 'default': 999}
        },
        'executor': {
            'module': 'game_engine.effects.damage_effects',
            'function': 'deal_aoe_damage'
        },
        'interpreter': {
            'command': 'DEAL_AOE_DAMAGE',
            'field_map': {
                'amount': 'effect_data.amount',
                'target_count': 'len(changes.targets)',
                'target_ids': 'changes.target_ids',
                'source_id': 'context.source._combat_id',
                'source_name': 'context.source.name'
            }
        }
    },

    'buff_stats': {
        'category': 'stats',
        'parameters': {
            'target': {'type': 'target_spec', 'required': True, 'golden_double': False},
            'attack': {'type': 'int', 'required': False, 'golden_double': True, 'default': 0},
            'health': {'type': 'int', 'required': False, 'golden_double': True, 'default': 0}
        },
        'executor': {
            'module': 'game_engine.effects.stat_effects',
            'function': 'buff_stats'
        },
        'interpreter': {
            'command': 'BUFF_STATS',
            'field_map': {
                'target_id': 'changes.targets.0._combat_id',
                'attack': 'changes.attack_buff',
                'health': 'changes.health_buff'
            },
            'sync_check': {'multi_entity_key': 'targets'}
        }
    },

    'buff_stats_tribe': {
        'category': 'stats',
        'parameters': {
            'target': {'type': 'target_spec', 'required': True, 'golden_double': False},
            'tribe': {'type': 'string', 'required': True, 'golden_double': False},
            'attack': {'type': 'int', 'required': False, 'golden_double': True, 'default': 0},
            'health': {'type': 'int', 'required': False, 'golden_double': True, 'default': 0}
        },
        'executor': {
            'module': 'game_engine.effects.stat_effects',
            'function': 'buff_stats_tribe'
        },
        'interpreter': {
            'command': 'BUFF_STATS',
            'field_map': {
                'target_id': 'changes.targets.0._combat_id',
                'attack': 'changes.attack_buff',
                'health': 'changes.health_buff'
            },
            'sync_check': {'multi_entity_key': 'targets'}
        }
    },

    'debuff_stats': {
        'category': 'stats',
        'parameters': {
            'target': {'type': 'target_spec', 'required': True, 'golden_double': False},
            'attack': {'type': 'int', 'required': False, 'golden_double': True, 'default': 0},
            'health': {'type': 'int', 'required': False, 'golden_double': True, 'default': 0}
        },
        'executor': {
            'module': 'game_engine.effects.stat_effects',
            'function': 'debuff_stats'
        },
        'interpreter': {
            'command': 'DEBUFF_STATS',
            'sync_check': {'multi_entity_key': 'targets'},
            'field_map': {
                'target_id': 'changes.targets.0._combat_id',
                'attack': 'changes.attack_debuff',
                'health': 'changes.health_debuff'
            }
        }
    },

    'permanent_stat_gain': {
        'category': 'stats',
        'parameters': {
            'target': {'type': 'target_spec', 'required': True, 'golden_double': False},
            'attack': {'type': 'int', 'required': False, 'golden_double': True, 'default': 0},
            'health': {'type': 'int', 'required': False, 'golden_double': True, 'default': 0}
        },
        'executor': {
            'module': 'game_engine.effects.stat_effects',
            'function': 'permanent_stat_gain'
        },
        'interpreter': {
            'command': 'PERMANENT_STAT_GAIN',
            'sync_check': {'multi_entity_key': 'targets'},
            'field_map': {
                'target_id': 'changes.targets.0._combat_id',
                'attack': 'changes.attack_gain',
                'health': 'changes.health_gain'
            }
        }
    },

    'summon_minion': {
        'category': 'summon',
        'parameters': {
            'minion_name': {'type': 'string', 'required': True, 'golden_double': False},
            'attack': {'type': 'int', 'required': False, 'golden_double': True, 'default': None},
            'health': {'type': 'int', 'required': False, 'golden_double': True, 'default': None},
            'summon_count': {'type': 'int', 'required': False, 'golden_double': True, 'default': 1},
            'inherit_attack': {'type': 'bool', 'required': False, 'golden_double': False, 'default': False},
            'inherit_health': {'type': 'bool', 'required': False, 'golden_double': False, 'default': False},
            'inherit_keywords': {'type': 'list', 'required': False, 'golden_double': False, 'default': []},
            'target': {'type': 'target_spec', 'required': False, 'golden_double': False, 'default': 'summon_position'}
        },
        'executor': {
            'module': 'game_engine.effects.summon_effects',
            'function': 'summon_minion'
        },
        'interpreter': {
            'command': 'SUMMON_MINION',
            'sync_check': {'multi_entity_key': 'summoned_minions'},
            'field_map': {
                'minion': 'changes.summoned_minions.0',
                'band': 'changes.summon_band',
                'position': 'changes.summoned_minions.0.position'
            }
        }
    },

    'destroy_minion': {
        'category': 'summon',
        'parameters': {
            'target': {'type': 'target_spec', 'required': True, 'golden_double': False},
            'stat_transfer_ratio': {'type': 'float', 'required': False, 'golden_double': False, 'default': 0.0}
        },
        'executor': {
            'module': 'game_engine.effects.summon_effects',
            'function': 'destroy_minion'
        },
        'interpreter': {
            'command': 'DESTROY_MINION',
            'field_map': {
                'target_id': 'changes.targets.0._combat_id'
            }
        }
    },

    'destroy_and_transform': {
        'category': 'summon',
        'parameters': {
            'target': {'type': 'target_spec', 'required': True, 'golden_double': False},
            'minion_name': {'type': 'string', 'required': True, 'golden_double': False},
            'attack': {'type': 'int', 'required': False, 'golden_double': True, 'default': None},
            'health': {'type': 'int', 'required': False, 'golden_double': True, 'default': None},
            'summon_count': {'type': 'int', 'required': False, 'golden_double': True, 'default': 1}
        },
        'executor': {
            'module': 'game_engine.effects.summon_effects',
            'function': 'destroy_and_transform'
        },
        'interpreter': {
            'command': 'TRANSFORM',
            'field_map': {
                'target_id': 'changes.targets.0._combat_id',
                'new_minion_name': 'effect_data.minion_name'
            }
        }
    },

    'move_minion': {
        'category': 'summon',
        'parameters': {
            'target': {'type': 'target_spec', 'required': True, 'golden_double': False},
            'direction': {'type': 'string', 'required': True, 'golden_double': False}
        },
        'executor': {
            'module': 'game_engine.effects.summon_effects',
            'function': 'move_minion'
        },
        'interpreter': {
            'command': 'MOVE_MINION',
            'field_map': {
                'target_id': 'changes.targets.0._combat_id',
                'old_position': 'changes.old_position',
                'new_position': 'changes.new_position'
            }
        }
    },

    'modify_fatigue': {
        'category': 'special',
        'parameters': {
            'amount': {'type': 'int', 'required': True, 'golden_double': True}
        },
        'executor': {
            'module': 'game_engine.effects.special_effects',
            'function': 'modify_fatigue'
        },
        'interpreter': {
            'command': 'MODIFY_FATIGUE',
            'field_map': {
                'amount': 'effect_data.amount',
                'fatigue_activated': 'changes.fatigue_activated'
            }
        }
    },

    'attack_target': {
        'category': 'special',
        'parameters': {
            'attacker': {'type': 'target_spec', 'required': False, 'golden_double': False, 'default': 'self'},
            'target_minion': {'type': 'minion_ref', 'required': False, 'golden_double': False, 'default': None}
        },
        'executor': {
            'module': 'game_engine.effects.special_effects',
            'function': 'attack_target'
        },
        'interpreter': {
            'command': None,  # attack_target generates its own combat commands
            'field_map': {}
        }
    },

    'redirect_damage': {
        'category': 'special',
        'parameters': {
            'amount': {'type': 'int', 'required': True, 'golden_double': True},
            'new_target': {'type': 'minion_ref', 'required': True, 'golden_double': False}
        },
        'executor': {
            'module': 'game_engine.effects.special_effects',
            'function': 'redirect_damage'
        },
        'interpreter': {
            'command': 'REDIRECT_DAMAGE',
            'field_map': {
                'amount': 'changes.damage_redirected',
                'target_id': 'changes.targets.0._combat_id'
            }
        }
    },

    'prevent_death': {
        'category': 'special',
        'parameters': {
            'target': {'type': 'target_spec', 'required': True, 'golden_double': False}
        },
        'executor': {
            'module': 'game_engine.effects.special_effects',
            'function': 'prevent_death'
        },
        'interpreter': {
            'command': 'PREVENT_DEATH',
            'field_map': {
                'target_id': 'changes.targets.0._combat_id'
            }
        }
    },

    'copy_stats': {
        'category': 'special',
        'parameters': {
            'source': {'type': 'target_spec', 'required': True, 'golden_double': False},
            'target': {'type': 'target_spec', 'required': True, 'golden_double': False},
            'copy_health': {'type': 'bool', 'required': False, 'golden_double': False, 'default': True},
            'copy_attack': {'type': 'bool', 'required': False, 'golden_double': False, 'default': True}
        },
        'executor': {
            'module': 'game_engine.effects.special_effects',
            'function': 'copy_stats'
        },
        'interpreter': {
            'command': 'COPY_STATS',
            'field_map': {
                'target_id': 'changes.targets.0._combat_id'
            }
        }
    },

    'grant_keyword': {
        'category': 'special',
        'parameters': {
            'target': {'type': 'target_spec', 'required': True, 'golden_double': False},
            'keyword': {'type': 'string', 'required': True, 'golden_double': False},
            'keyword_data': {'type': 'dict', 'required': False, 'golden_double': False, 'default': {}}
        },
        'executor': {
            'module': 'game_engine.effects.special_effects',
            'function': 'grant_keyword'
        },
        'interpreter': {
            'command': 'GRANT_KEYWORD',
            'sync_check': {'multi_entity_key': 'targets'},
            'field_map': {
                'target_id': 'changes.targets.0._combat_id',
                'keyword': 'changes.keyword_granted',
                'keyword_data': 'effect_data.keyword_data'
            }
        }
    },

    'remove_keyword': {
        'category': 'special',
        'parameters': {
            'target': {'type': 'target_spec', 'required': False, 'golden_double': False, 'default': 'self'},
            'keyword': {'type': 'string', 'required': True, 'golden_double': False},
            'scope': {'type': 'string', 'required': False, 'golden_double': False, 'default': 'both'}
        },
        'executor': {
            'module': 'game_engine.effects.special_effects',
            'function': 'remove_keyword'
        },
        'interpreter': {
            'command': 'REMOVE_KEYWORD',
            'field_map': {
                'target_id': 'changes.targets.0._combat_id',
                'keyword': 'changes.keyword_removed',
                'removed_from_combat': 'changes.removed_from_combat',
                'removed_from_band': 'changes.removed_from_band'
            }
        }
    },

    'chrono_cascade': {
        'category': 'special',
        'parameters': {
            'find_next_cast': {'type': 'bool', 'required': False, 'golden_double': False, 'default': True}
        },
        'executor': {
            'module': 'game_engine.effects.special_effects',
            'function': 'chrono_cascade'
        },
        'interpreter': {
            'command': None,  # Composite effect
            'field_map': {}
        }
    },

    'perform_cast': {
        'category': 'special',
        'parameters': {
            'target_minion': {'type': 'minion_ref', 'required': True, 'golden_double': False}
        },
        'executor': {
            'module': 'game_engine.effects.special_effects',
            'function': 'perform_cast'
        },
        'interpreter': {
            'command': 'FORCE_CAST',
            'field_map': {
                'target_id': 'effect_data.target_minion._combat_id'
            }
        }
    },

    'apply_stun': {
        'category': 'special',
        'parameters': {
            'target': {'type': 'target_spec', 'required': True, 'golden_double': False},
            'stun_amount': {'type': 'int', 'required': False, 'golden_double': True, 'default': 1}
        },
        'executor': {
            'module': 'game_engine.effects.special_effects',
            'function': 'apply_stun'
        },
        'interpreter': {
            'command': 'APPLY_STUN',
            'sync_check': {'multi_entity_key': 'targets'},
            'field_map': {
                'target_id': 'changes.targets.0._combat_id',
                'stun_amount': 'changes.stun_applied'
            }
        }
    },

    'recalculate_auras': {
        'category': 'special',
        'parameters': {},
        'executor': {
            'module': 'game_engine.effects.special_effects',
            'function': 'recalculate_auras'
        },
        'interpreter': {
            'command': 'RECALCULATE_AURAS',
            'field_map': {}
        }
    },

    'buff_adjacent': {
        'category': 'special',
        'parameters': {
            'attack': {'type': 'int', 'required': False, 'golden_double': True, 'default': 0},
            'health': {'type': 'int', 'required': False, 'golden_double': True, 'default': 0}
        },
        'executor': {
            'module': 'game_engine.effects.special_effects',
            'function': 'buff_adjacent'
        },
        'interpreter': {
            'command': None,  # Backend only - no interpreter command needed
            'field_map': {}
        }
    },

    'reduce_hide': {
        'category': 'special',
        'parameters': {
            'target': {'type': 'target_spec', 'required': False, 'golden_double': False, 'default': 'self'}
        },
        'executor': {
            'module': 'game_engine.effects.special_effects',
            'function': 'reduce_hide'
        },
        'interpreter': {
            'command': 'REDUCE_HIDE',
            'field_map': {
                'target_id': 'changes.targets.0._combat_id',
                'hide_remaining': 'changes.hide_remaining'
            }
        }
    },

    'reduce_ring': {
        'category': 'special',
        'parameters': {
            'target': {'type': 'target_spec', 'required': False, 'golden_double': False, 'default': 'self'}
        },
        'executor': {
            'module': 'game_engine.effects.special_effects',
            'function': 'reduce_ring'
        },
        'interpreter': {
            'command': 'REDUCE_RING',
            'field_map': {
                'target_id': 'changes.targets.0._combat_id',
                'permanent_ring_count': 'changes.permanent_ring_count'
            }
        }
    },

    'leap_move': {
        'category': 'special',
        'parameters': {
            'distance': {'type': 'int', 'required': False, 'golden_double': True, 'default': None}
        },
        'executor': {
            'module': 'game_engine.effects.special_effects',
            'function': 'leap_move'
        },
        'interpreter': {
            'command': 'LEAP_MOVE',
            'field_map': {
                'target_id': 'changes.targets.0._combat_id',
                'old_position': 'changes.old_position',
                'new_position': 'changes.new_position'
            }
        }
    },

    'divide_attack': {
        'category': 'special',
        'parameters': {
            'target': {'type': 'target_spec', 'required': False, 'golden_double': False, 'default': 'self'},
            'divisor': {'type': 'int', 'required': False, 'golden_double': False, 'default': 3}
        },
        'executor': {
            'module': 'game_engine.effects.special_effects',
            'function': 'divide_attack'
        },
        'interpreter': {
            'command': 'DIVIDE_ATTACK',
            'field_map': {
                'target_id': 'changes.targets.0._combat_id',
                'old_attack': 'changes.original_attack',
                'new_attack': 'changes.new_attack'
            }
        }
    },

    'rich_buff': {
        'category': 'special',
        'parameters': {
            'target': {'type': 'target_spec', 'required': False, 'golden_double': False, 'default': 'self'}
        },
        'executor': {
            'module': 'game_engine.effects.special_effects',
            'function': 'rich_buff'
        },
        'interpreter': {
            'command': 'BUFF_STATS',
            'field_map': {
                'target_id': 'changes.targets.0._combat_id',
                'attack': 'changes.buff_amount',
                'health': 'changes.buff_amount'
            }
        }
    },

    'modify_gold': {
        'category': 'special',
        'parameters': {
            'amount': {'type': 'int', 'required': True, 'golden_double': True}
        },
        'executor': {
            'module': 'game_engine.effects.special_effects',
            'function': 'modify_gold'
        },
        'interpreter': {
            'command': 'MODIFY_GOLD',
            'field_map': {
                'amount': 'changes.gold_change',
                'old_gold': 'changes.old_gold',
                'new_gold': 'changes.new_gold'
            }
        }
    },

    'transfer_stun': {
        'category': 'special',
        'parameters': {
            'from_targets': {'type': 'target_spec', 'required': True, 'golden_double': False},
            'to_target': {'type': 'target_spec', 'required': True, 'golden_double': False}
        },
        'executor': {
            'module': 'game_engine.effects.special_effects',
            'function': 'transfer_stun'
        },
        'interpreter': {
            'command': 'TRANSFER_STUN',
            'field_map': {
                'from_targets': 'changes.from_targets',
                'to_target': 'changes.to_target._combat_id',
                'stun_amount': 'changes.stun_transferred'
            }
        }
    },

    'scaling_damage': {
        'category': 'special',
        'parameters': {
            'target': {'type': 'target_spec', 'required': True, 'golden_double': False},
            'base_amount': {'type': 'int', 'required': True, 'golden_double': False},
            'increment': {'type': 'int', 'required': True, 'golden_double': False},
            'tracker_field': {'type': 'string', 'required': False, 'golden_double': False, 'default': 'cast_damage_current'}
        },
        'executor': {
            'module': 'game_engine.effects.special_effects',
            'function': 'scaling_damage'
        },
        'interpreter': {
            'command': 'DEAL_DAMAGE',
            'field_map': {
                'target_id': 'changes.targets.0._combat_id',
                'amount': 'changes.damage_dealt'
            }
        }
    },

    'trigger_death_toll': {
        'category': 'special',
        'parameters': {
            'target': {'type': 'target_spec', 'required': False, 'golden_double': False, 'default': 'all_allies'},
            'exclude_self': {'type': 'bool', 'required': False, 'golden_double': False, 'default': True}
        },
        'executor': {
            'module': 'game_engine.effects.special_effects',
            'function': 'trigger_death_toll'
        },
        'interpreter': {
            'command': 'TRIGGER_DEATH_TOLL',  # Displays trigger logs, child effects handle actual effects
            'field_map': {
                'source_id': 'source_minion._combat_id',
                'target_id': 'changes.triggered_minion._combat_id'
            }
        }
    },

    'trigger_start_of_combat': {
        'category': 'special',
        'parameters': {
            'target': {'type': 'target_spec', 'required': False, 'golden_double': False, 'default': 'all_allies'},
            'exclude_self': {'type': 'bool', 'required': False, 'golden_double': False, 'default': True}
        },
        'executor': {
            'module': 'game_engine.effects.special_effects',
            'function': 'trigger_start_of_combat'
        },
        'interpreter': {
            'command': 'TRIGGER_START_OF_COMBAT',
            'field_map': {
                'source_id': 'source_minion._combat_id',
                'target_id': 'changes.triggered_minion._combat_id'
            }
        }
    },

    'grant_effect_to_minion': {
        'category': 'special',
        'parameters': {
            'target': {'type': 'target_spec', 'required': True, 'golden_double': False},
            'exclude_name': {'type': 'string', 'required': False, 'golden_double': False, 'default': None},
            'effect_type': {'type': 'string', 'required': True, 'golden_double': False},
            'effect_data': {'type': 'effect_data', 'required': True, 'golden_double': False}
        },
        'executor': {
            'module': 'game_engine.effects.special_effects2',
            'function': 'grant_effect_to_minion'
        },
        'interpreter': {
            'command': 'GRANT_EFFECT',
            'field_map': {
                'target_id': 'changes.targets.0._combat_id',
                'effect_type': 'changes.effect_type',
                'keyword': 'changes.keyword_granted',
                'granted_effect_data': 'changes.granted_effect'
            }
        }
    },

    'conditional': {
        'category': 'special',
        'parameters': {
            'condition': {'type': 'condition', 'required': True, 'golden_double': False},
            'then_effect': {'type': 'effect_or_list', 'required': True, 'golden_double': False},
            'else_effect': {'type': 'effect_or_list', 'required': False, 'golden_double': False, 'default': None}
        },
        'executor': {
            'module': 'game_engine.effects.conditional_effects',
            'function': 'evaluate_conditional'
        },
        'interpreter': {
            'command': None,  # Conditionals delegate to their chosen effects
            'field_map': {}
        }
    },

    # ===== NEW: COMBAT KEYWORD EFFECTS =====

    'prevent_counter_damage': {
        'category': 'combat',
        'parameters': {},
        'executor': {
            'module': 'game_engine.effects.combat_effects',
            'function': 'prevent_counter_damage'
        },
        'interpreter': {
            'command': None,  # Sets context flag, no separate command
            'field_map': {}
        }
    },

    'mark_obliterate': {
        'category': 'combat',
        'parameters': {
            'target': {'type': 'target_spec', 'required': False, 'golden_double': False, 'default': 'defender'}
        },
        'executor': {
            'module': 'game_engine.effects.combat_effects',
            'function': 'mark_obliterate'
        },
        'interpreter': {
            'command': None,  # Sets context flag, no separate command
            'field_map': {}
        }
    },

    'deal_cleave_damage': {
        'category': 'combat',
        'parameters': {
            'adjacent_count': {'type': 'int', 'required': False, 'golden_double': True, 'default': 1}
        },
        'executor': {
            'module': 'game_engine.effects.combat_effects',
            'function': 'deal_cleave_damage'
        },
        'interpreter': {
            'command': None,  # Cleave logs are handled within effect
            'field_map': {}
        }
    },
}


def get_effect_definition(effect_type: str) -> dict:
    """Get effect definition from registry"""
    return EFFECT_REGISTRY.get(effect_type)


def get_golden_double_fields(effect_type: str) -> list:
    """Get list of fields that should be doubled for golden minions"""
    definition = EFFECT_REGISTRY.get(effect_type)
    if not definition:
        return []

    return [
        param_name
        for param_name, param_def in definition['parameters'].items()
        if param_def.get('golden_double', False)
    ]


def validate_effect_registry():
    """Validate all effect definitions"""
    required_fields = ['category', 'parameters', 'executor', 'interpreter']

    errors = []
    for effect_type, definition in EFFECT_REGISTRY.items():
        for field in required_fields:
            if field not in definition:
                errors.append(f"{effect_type} missing field: {field}")

    if errors:
        raise ValueError(f"Registry validation failed:\n" + "\n".join(errors))

    logger.debug(f"✓ Effect registry validated: {len(EFFECT_REGISTRY)} effects")


# Validate on import
validate_effect_registry()