"""
Event Template Registry - Declarative definitions for reusable event screens

This system defines reusable screen templates that can be chained together to create
complex events. Each screen type has a consistent visual presentation and behavior.

Philosophy:
- Events are sequences of screens
- Screens are reusable UI components with specific purposes
- Complex events = simple screens chained together
- Consistent visuals for the same screen type across all events

Screen Categories:
- Selection: Player chooses something (minion, buff target, path)
- Action: Player performs an action (combat, shop, statue)
- Story: Player receives information (narrative, rewards)
- Flow: Controls event progression (choices, chains)
"""


import logging

logger = logging.getLogger(__name__)

EVENT_SCREEN_REGISTRY = {
    # ==================== SELECTION SCREENS ====================

    'select_minion': {
        'category': 'selection',
        'description': 'Choose one or more minions from a pool',
        'parameters': {
            'count': {
                'type': 'int',
                'required': False,
                'default': 3,
                'description': 'Number of minions to offer'
            },
            'tier_pool': {
                'type': 'string',
                'required': False,
                'default': 'multi_tier',
                'description': 'Tier pool to draw from: multi_tier, current_tier, or specific tier number'
            },
            'rarity_filter': {
                'type': 'string',
                'required': False,
                'default': None,
                'description': 'Filter by rarity: common, rare, epic, legendary'
            },
            'max_selections': {
                'type': 'int',
                'required': False,
                'default': 1,
                'description': 'Maximum minions player can select'
            },
            'allow_skip': {
                'type': 'bool',
                'required': False,
                'default': True,
                'description': 'Can player skip without selecting'
            },
            'title': {
                'type': 'string',
                'required': False,
                'default': 'Choose a Minion',
                'description': 'Screen title'
            },
            'message': {
                'type': 'string',
                'required': False,
                'default': 'Select a minion to add to your band',
                'description': 'Screen description'
            }
        },
        'executor': {
            'module': 'game_engine.event_system',
            'function': '_create_minion_selection'
        },
        'on_complete': {
            'type': 'screen_ref',
            'description': 'Next screen after selection'
        }
    },

    'select_buff_target': {
        'category': 'selection',
        'description': 'Choose which minion receives a buff',
        'parameters': {
            'buff_type': {
                'type': 'string',
                'required': True,
                'description': 'Type of buff: health, attack, or both'
            },
            'health_amount': {
                'type': 'int',
                'required': False,
                'default': 0,
                'description': 'Health buff amount'
            },
            'attack_amount': {
                'type': 'int',
                'required': False,
                'default': 0,
                'description': 'Attack buff amount'
            },
            'allow_skip': {
                'type': 'bool',
                'required': False,
                'default': True,
                'description': 'Can player skip the buff'
            },
            'title': {
                'type': 'string',
                'required': False,
                'default': 'Apply Blessing',
                'description': 'Screen title'
            },
            'message': {
                'type': 'string',
                'required': False,
                'default': 'Choose a minion to receive the blessing',
                'description': 'Screen description'
            }
        },
        'executor': {
            'module': 'game_engine.event_executors',
            'function': 'apply_buff_to_target'
        },
        'on_complete': {
            'type': 'screen_ref',
            'description': 'Next screen after buff applied'
        }
    },

    'select_buff_type': {
        'category': 'selection',
        'description': 'Choose which type of buff to receive (chains to select_buff_target)',
        'parameters': {
            'buff_power': {
                'type': 'string',
                'required': False,
                'default': 'normal',
                'description': 'Buff power level: normal, strong, major, ultimate'
            },
            'scale_with_ring': {
                'type': 'bool',
                'required': False,
                'default': True,
                'description': 'Scale buff values with ring level'
            },
            'allow_skip': {
                'type': 'bool',
                'required': False,
                'default': True,
                'description': 'Can player skip the buff'
            },
            'title': {
                'type': 'string',
                'required': False,
                'default': 'Choose Blessing Type',
                'description': 'Screen title'
            }
        },
        'executor': {
            'module': 'game_engine.event_system',
            'function': '_create_scaling_buff_selection'
        },
        'chains_to': 'select_buff_target',
        'description_note': 'This always chains to select_buff_target screen'
    },

    'make_choice': {
        'category': 'selection',
        'description': 'Choose between multiple paths or options',
        'parameters': {
            'choices': {
                'type': 'list',
                'required': True,
                'description': 'List of choice objects with: {name, description, icon, next_screen OR next_event, gold_cost, condition, on_select}'
            },
            'title': {
                'type': 'string',
                'required': True,
                'description': 'Screen title'
            },
            'message': {
                'type': 'string',
                'required': False,
                'default': 'Choose your path',
                'description': 'Screen description'
            }
        },
        'executor': {
            'module': 'game_engine.event_executors',
            'function': 'create_choice_screen'
        },
        'on_choice': {
            'type': 'screen_ref_or_event_ref',
            'description': 'Different screens (next_screen) or events (next_event) based on choice'
        }
    },

    # ==================== ACTION SCREENS ====================

    'combat': {
        'category': 'action',
        'description': 'Fight an enemy band',
        'parameters': {
            'difficulty': {
                'type': 'string',
                'required': False,
                'default': 'normal',
                'description': 'Combat difficulty: normal, hard, elite, champion, nightmare'
            },
            'band_size': {
                'type': 'int',
                'required': False,
                'default': None,
                'description': 'Override enemy band size (null = auto-scale with ring)'
            },
            'tier': {
                'type': 'int',
                'required': False,
                'default': None,
                'description': 'Override enemy tier (null = match ring)'
            },
            'pool_filter': {
                'type': 'string',
                'required': False,
                'default': None,
                'description': 'Filter enemy minions by tribe (e.g., "Human", "Beast")'
            },
            'disable_gold_reward': {
                'type': 'bool',
                'required': False,
                'default': False,
                'description': 'Disable gold reward for this combat'
            },
            'title': {
                'type': 'string',
                'required': False,
                'default': 'Combat',
                'description': 'Screen title'
            }
        },
        'executor': {
            'module': 'game_engine.event_system',
            'function': '_create_scaling_combat_selection'
        },
        'on_victory': {
            'type': 'screen_ref',
            'description': 'Next screen on victory (within same event)'
        },
        'on_victory_event': {
            'type': 'event_ref',
            'description': 'Next event on victory (transitions to different event)'
        },
        'on_defeat': {
            'type': 'screen_ref',
            'description': 'Next screen on defeat (usually null = run ends)'
        },
        'on_defeat_event': {
            'type': 'event_ref',
            'description': 'Next event on defeat (transitions to different event)'
        }
    },

    'shop': {
        'category': 'action',
        'description': 'Purchase minions with gold (repeating)',
        'parameters': {
            'title': {
                'type': 'string',
                'required': False,
                'default': 'Shop',
                'description': 'Screen title'
            }
        },
        'executor': {
            'module': 'game_engine.event_system',
            'function': '_create_shop_selection'
        },
        'repeating': True,
        'description_note': 'Shop is always repeating - refreshes after each purchase'
    },

    'statue': {
        'category': 'action',
        'description': 'Combine minions into golden versions (repeating)',
        'parameters': {
            'title': {
                'type': 'string',
                'required': False,
                'default': 'Golden Statue',
                'description': 'Screen title'
            }
        },
        'executor': {
            'module': 'game_engine.event_system',
            'function': '_create_combine_minions_selection'
        },
        'repeating': True,
        'description_note': 'Statue is always repeating - can combine multiple times'
    },

    # ==================== STORY SCREENS ====================

    'story': {
        'category': 'story',
        'description': 'Display narrative text with continue button',
        'parameters': {
            'title': {
                'type': 'string',
                'required': True,
                'description': 'Screen title'
            },
            'text': {
                'type': 'string',
                'required': True,
                'description': 'Story text to display'
            },
            'icon': {
                'type': 'string',
                'required': False,
                'default': 'book-open',
                'description': 'Lucide icon name'
            },
            'continue_text': {
                'type': 'string',
                'required': False,
                'default': 'Continue',
                'description': 'Text for continue button'
            }
        },
        'executor': {
            'module': 'game_engine.event_executors',
            'function': 'create_story_screen'
        },
        'on_continue': {
            'type': 'screen_ref',
            'description': 'Next screen after continue'
        }
    },

    'reward_info': {
        'category': 'story',
        'description': 'Display reward information (auto-granted)',
        'parameters': {
            'title': {
                'type': 'string',
                'required': True,
                'description': 'Screen title'
            },
            'rewards': {
                'type': 'list',
                'required': True,
                'description': 'List of rewards: {type: "gold"/"health"/"attack", amount: X, target: minion_id}'
            },
            'message': {
                'type': 'string',
                'required': False,
                'default': 'You received rewards!',
                'description': 'Screen description'
            }
        },
        'executor': {
            'module': 'game_engine.event_executors',
            'function': 'grant_rewards'
        },
        'on_continue': {
            'type': 'screen_ref',
            'description': 'Next screen after rewards shown'
        }
    },

    # ==================== SPECIAL SCREENS ====================

    'grant_gold': {
        'category': 'reward',
        'description': 'Instantly grant gold (no UI, auto-chains)',
        'parameters': {
            'amount': {
                'type': 'int',
                'required': True,
                'description': 'Gold amount to grant'
            }
        },
        'executor': {
            'module': 'game_engine.event_executors',
            'function': 'grant_gold'
        },
        'auto_chain': True,
        'description_note': 'This screen auto-executes and chains to next screen'
    },

    'grant_minion': {
        'category': 'reward',
        'description': 'Grant a specific minion to player (shows selection)',
        'parameters': {
            'minion_name': {
                'type': 'string',
                'required': True,
                'description': 'Name of minion to grant'
            },
            'tier': {
                'type': 'int',
                'required': False,
                'default': 1,
                'description': 'Tier level of the minion'
            },
            'title': {
                'type': 'string',
                'required': False,
                'default': 'New Ally',
                'description': 'Screen title'
            },
            'message': {
                'type': 'string',
                'required': False,
                'default': 'A minion joins your band!',
                'description': 'Screen description'
            }
        },
        'executor': {
            'module': 'game_engine.event_system',
            'function': '_create_specific_minion_selection'
        },
        'on_complete': {
            'type': 'screen_ref',
            'description': 'Next screen after minion granted'
        }
    },

    'apply_buff_random': {
        'category': 'reward',
        'description': 'Apply buff to random minion(s) (no UI, auto-chains)',
        'parameters': {
            'health_amount': {
                'type': 'int',
                'required': False,
                'default': 0,
                'description': 'Health buff amount'
            },
            'attack_amount': {
                'type': 'int',
                'required': False,
                'default': 0,
                'description': 'Attack buff amount'
            },
            'target_count': {
                'type': 'int',
                'required': False,
                'default': 1,
                'description': 'Number of minions to buff'
            },
            'filter': {
                'type': 'string',
                'required': False,
                'default': 'all',
                'description': 'Target filter: all, tribe:<name>, lowest_health, highest_attack'
            }
        },
        'executor': {
            'module': 'game_engine.event_executors',
            'function': 'apply_buff_random'
        },
        'auto_chain': True
    },

    'damage_band': {
        'category': 'penalty',
        'description': 'Deal damage to player band (no UI, auto-chains)',
        'parameters': {
            'amount': {
                'type': 'int',
                'required': True,
                'description': 'Damage amount'
            },
            'target_count': {
                'type': 'int',
                'required': False,
                'default': 1,
                'description': 'Number of minions to damage'
            },
            'distribution': {
                'type': 'string',
                'required': False,
                'default': 'random',
                'description': 'How to distribute: random, all, lowest_health'
            }
        },
        'executor': {
            'module': 'game_engine.event_executors',
            'function': 'damage_player_band'
        },
        'auto_chain': True
    }
}


# ==================== VISIT RULES ====================

EVENT_VISIT_RULES = {
    'once_per_run': {
        'description': 'Can only visit this event once per run',
        'tracking': 'run.visited_events',
        'check': lambda run, event_id: event_id not in getattr(run, 'visited_events', [])
    },

    'once_per_ring': {
        'description': 'Can visit once per ring (resets each ring)',
        'tracking': 'run.ring_visited_events',
        'check': lambda run, event_id: event_id not in getattr(run, 'ring_visited_events', {}).get(run.current_ring, [])
    },

    'repeatable': {
        'description': 'Can visit this event unlimited times',
        'tracking': None,
        'check': lambda run, event_id: True
    },

    'conditional': {
        'description': 'Visit rule based on custom condition function',
        'tracking': None,
        'requires_condition': True
    }
}


# ==================== HELPER FUNCTIONS ====================

def get_screen_template(screen_type: str) -> dict:
    """Get screen template definition from registry"""
    return EVENT_SCREEN_REGISTRY.get(screen_type)


def get_all_screen_types() -> list:
    """Get list of all screen types"""
    return list(EVENT_SCREEN_REGISTRY.keys())


def get_screens_by_category(category: str) -> dict:
    """Get all screens of a specific category"""
    return {
        screen_type: definition
        for screen_type, definition in EVENT_SCREEN_REGISTRY.items()
        if definition.get('category') == category
    }


def validate_screen_parameters(screen_type: str, parameters: dict) -> tuple[bool, list]:
    """
    Validate parameters for a screen type

    Returns:
        (is_valid, error_messages)
    """
    template = get_screen_template(screen_type)
    if not template:
        return False, [f"Unknown screen type: {screen_type}"]

    errors = []
    param_defs = template.get('parameters', {})

    # Check required parameters
    for param_name, param_def in param_defs.items():
        if param_def.get('required', False) and param_name not in parameters:
            errors.append(f"{screen_type} missing required parameter: {param_name}")

    # Check parameter types (basic validation)
    for param_name, param_value in parameters.items():
        if param_name not in param_defs:
            errors.append(f"{screen_type} has unknown parameter: {param_name}")

    return len(errors) == 0, errors


def can_visit_event(run, event_id: str, visit_rule: str, condition_func=None) -> bool:
    """
    Check if player can visit an event based on visit rules

    Args:
        run: Run object
        event_id: Unique event identifier
        visit_rule: Rule type (once_per_run, once_per_ring, repeatable, conditional)
        condition_func: Custom condition function for 'conditional' rule

    Returns:
        True if event can be visited
    """
    rule = EVENT_VISIT_RULES.get(visit_rule)
    if not rule:
        return True  # Unknown rule = allow visit

    if visit_rule == 'conditional':
        if not condition_func:
            return True  # No condition = allow
        return condition_func(run, event_id)

    return rule['check'](run, event_id)


def mark_event_visited(run, event_id: str, visit_rule: str):
    """
    Mark an event as visited based on visit rule

    Args:
        run: Run object
        event_id: Unique event identifier
        visit_rule: Rule type
    """
    if visit_rule == 'once_per_run':
        if not hasattr(run, 'visited_events'):
            run.visited_events = []
        if event_id not in run.visited_events:
            run.visited_events.append(event_id)

    elif visit_rule == 'once_per_ring':
        if not hasattr(run, 'ring_visited_events'):
            run.ring_visited_events = {}
        if run.current_ring not in run.ring_visited_events:
            run.ring_visited_events[run.current_ring] = []
        if event_id not in run.ring_visited_events[run.current_ring]:
            run.ring_visited_events[run.current_ring].append(event_id)


def validate_event_template_registry():
    """Validate all screen template definitions have required fields"""
    required_fields = ['category', 'description', 'parameters', 'executor']
    executor_fields = ['module', 'function']

    errors = []

    for screen_type, definition in EVENT_SCREEN_REGISTRY.items():
        # Check top-level fields
        for field in required_fields:
            if field not in definition:
                errors.append(f"{screen_type} missing field: {field}")

        # Check executor fields
        executor = definition.get('executor', {})
        for field in executor_fields:
            if field not in executor:
                errors.append(f"{screen_type}.executor missing field: {field}")

        # Validate parameters structure
        parameters = definition.get('parameters', {})
        for param_name, param_def in parameters.items():
            if 'type' not in param_def:
                errors.append(f"{screen_type}.parameters.{param_name} missing 'type' field")

    if errors:
        raise ValueError(f"Event template registry validation failed:\n" + "\n".join(errors))

    logger.debug(f"✓ Event template registry validated: {len(EVENT_SCREEN_REGISTRY)} screen types")


# Validate on import
validate_event_template_registry()
