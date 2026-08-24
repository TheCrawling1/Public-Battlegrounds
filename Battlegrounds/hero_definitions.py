"""
Hero Definitions - Persistent run-wide effects

Heroes provide modifiers that apply throughout an entire run.
Effects are stored as JSON in Run.hero_effects and applied at decision points.

Hero powers can be upgraded via Grand City, increasing their effectiveness.
The 'power_upgraded' field tracks how many times the power has been upgraded.
"""

HERO_DEFINITIONS = {
    'silas': {
        'id': 'silas',
        'name': 'Silas',
        'description': 'Shops cost {power_level} less (minimum 0)',
        'base_description': 'Shops cost 1 less (minimum 0)',
        'effects': {
            'cost_reduction': 1  # Base value, scales with power_level
        },
        'icon': 'silas.svg',
        'starting_minions': ['Scout', 'Soldier']
    },

    'puck': {
        'id': 'puck',
        'name': 'Puck',
        'description': 'When combat starts your first {puck_minions} minions take their turns',
        'base_description': 'When combat starts your first 2 minions take their turns instead of first 1',
        'effects': {
            'extra_starting_turns': 1  # Base: 2 minions (1 normal + 1 extra), scales with power_level
        },
        'icon': 'puck.svg',
        'starting_minions': ['Hound', 'Cat']
    },

    'olimpia': {
        'id': 'olimpia',
        'name': 'Olimpia',
        'description': 'Your first {power_level} minion(s) to die are instead stunned and leaped to the rightmost position',
        'base_description': 'Your first minion to die is instead stunned and leaped to the rightmost position',
        'effects': {
            'death_replacement': {
                'stun_turns': 1,
                'leap_to_back': True,
                'max_uses': 1  # Base value, scales with power_level
            }
        },
        'icon': 'olimpia.svg',
        'starting_minions': ['Gear Spider', 'Rust Golem']
    }
}

def get_hero(hero_id):
    """Get hero definition by ID"""
    return HERO_DEFINITIONS.get(hero_id)

def get_all_heroes():
    """Get all available heroes"""
    return list(HERO_DEFINITIONS.values())

def get_hero_effect(hero_id, effect_key):
    """Get a specific effect from a hero"""
    hero = get_hero(hero_id)
    if hero and 'effects' in hero:
        return hero['effects'].get(effect_key)
    return None

def get_scaled_effect_value(hero_effects, effect_key, base_value):
    """
    Get the scaled value of an effect based on power upgrades.

    Args:
        hero_effects: The hero_effects dict from the run
        effect_key: The effect being scaled (for future per-effect scaling)
        base_value: The base value of the effect

    Returns:
        The scaled value (base + power_upgraded)
    """
    power_upgraded = hero_effects.get('power_upgraded', 0)
    return base_value + power_upgraded

def get_hero_description(hero_id, hero_effects):
    """
    Get the hero description with current power level values.

    Args:
        hero_id: The hero ID
        hero_effects: The hero_effects dict from the run

    Returns:
        Description string with values filled in
    """
    hero = get_hero(hero_id)
    if not hero:
        return ""

    power_upgraded = hero_effects.get('power_upgraded', 0)
    power_level = 1 + power_upgraded
    puck_minions = 2 + power_upgraded  # Puck starts at 2 minions

    description = hero.get('description', hero.get('base_description', ''))
    description = description.replace('{power_level}', str(power_level))
    description = description.replace('{puck_minions}', str(puck_minions))

    return description

def get_hero_starting_minions(hero_id):
    """Get the list of starting minion names for a hero"""
    hero = get_hero(hero_id)
    if hero:
        return hero.get('starting_minions', ['Scout', 'Soldier'])
    return ['Scout', 'Soldier']  # Default fallback
