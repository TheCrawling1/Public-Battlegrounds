import logging

logger = logging.getLogger(__name__)

import os
from lucide_icons import generate_lucide_svg

# Database Configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///game.db')

# Game Configuration
EVENTS_FOR_GHOST_BATTLE = 10
MAX_RINGS = 5
MAX_RING_AVAILABLE = 4  # Maximum ring players can reach (for testing)
RING_SIZE = 12  # Number of events per ring (circular)
RING_START_POSITION = 5  # Starting position in the middle of the ring
MAX_BAND_SIZE = 6  # Maximum number of minions in a band
MAX_GHOST_WINS = 7  # Number of ghost battles to win for victory

# Ring Definitions - Simplified with scaling events
# Events now scale with ring level automatically
RING_EVENTS = {
    1: [
        'zone_portal',  # 0 - Zone Portal
        ['minion_event', 'buff_event'],  # 1 - Split: Minion OR Buff
        'buff_event',  # 2 - Buff
        'general_event',  # 3 - General Event (random from pool, becomes buff after visit)
        'shop_event',  # 4 - Shop
        'minion_event',  # 5 - START (Free minion)
        'buff_event',  # 6 - Buff
        'combat_event',  # 7 - Enemy
        'statue',  # 8 - Statue
        'general_event',  # 9 - General Event (random from pool, becomes buff after visit)
        'combat_event_hard',  # 10 - Hard Enemy
        'zone_portal'  # 11 - Zone Portal
    ],
    2: [
        'zone_portal',  # 0 - Zone Portal
        ['minion_event', 'buff_event'],  # 1 - Split: Minion OR stronger buff
        'buff_event',  # 2 - Strong Buff
        'general_event',  # 3 - General Event (random from pool, becomes buff after visit)
        'shop_event',  # 4 - Shop
        'minion_event',  # 5 - START (Free minion)
        'buff_event',  # 6 - Strong Buff
        'combat_event',  # 7 - Combat (tier scales with ring)
        'statue',  # 8 - Statue
        'general_event',  # 9 - General Event (random from pool, becomes buff after visit)
        'combat_event_hard',  # 10 - Hard Enemy
        'zone_portal'  # 11 - Zone Portal
    ],
    3: [
        'zone_portal',  # 0 - Zone Portal
        ['minion_event', 'buff_event'],  # 1 - Split: Minion OR major buff
        'buff_event',  # 2 - Major Buff
        'general_event',  # 3 - General Event (random from pool, becomes buff after visit)
        'shop_event',  # 4 - Shop
        'minion_event',  # 5 - START (Free minion)
        'buff_event',  # 6 - Major Buff
        'combat_event',  # 7 - Combat (tier scales with ring)
        'statue',  # 8 - Statue
        ['buff_event', 'minion_event'],  # 9 - Split: Ultimate buff OR minion
        'combat_event_hard',  # 10 - Hard Enemy
        'zone_portal'  # 11 - Zone Portal
    ]
}

# Default ring for higher levels
DEFAULT_RING_PATTERN = [
    'zone_portal',  # 0 - Zone Portal
    ['minion_event', 'buff_event'],  # 1 - Split: Minion OR buff
    'buff_event',  # 2 - Buff
    'general_event',  # 3 - General Event (random from pool, becomes buff after visit)
    'shop_event',  # 4 - Shop
    'minion_event',  # 5 - START (Free minion)
    'buff_event',  # 6 - Buff
    'combat_event',  # 7 - Combat (tier scales with ring)
    'statue',  # 8 - Statue
    'general_event',  # 9 - General Event (random from pool, becomes buff after visit)
    'combat_event_hard',  # 10 - Hard Enemy
    'zone_portal'  # 11 - Zone Portal
]

# Zone-Specific Ring Events
# Zones can override the default RING_EVENTS with their own patterns
ZONE_RING_EVENTS = {
    'human_kingdom': {
        1: [
            'zone_portal',  # 0 - Zone Portal
            ['minion_event', 'buff_event'],  # 1 - Split: Minion OR Buff
            'buff_event',  # 2 - Buff
            'general_event',  # 3 - General Event (random from pool, becomes buff after visit)
            'shop_event',  # 4 - Shop
            'minion_event',  # 5 - START (Free minion)
            'buff_event',  # 6 - Buff
            'combat_event',  # 7 - Enemy
            'bell_tower',  # 8 - Bell Tower (Human Kingdom special event)
            'general_event',  # 9 - General Event (random from pool, becomes buff after visit)
            'combat_event_hard',  # 10 - Hard Enemy
            'zone_portal'  # 11 - Zone Portal
        ],
        2: [
            'zone_portal',  # 0 - Zone Portal
            ['minion_event', 'buff_event'],  # 1 - Split: Minion OR stronger buff
            'buff_event',  # 2 - Strong Buff
            'general_event',  # 3 - General Event (random from pool, becomes buff after visit)
            'shop_event',  # 4 - Shop
            'minion_event',  # 5 - START (Free minion)
            'buff_event',  # 6 - Strong Buff
            'combat_event',  # 7 - Combat (tier scales with ring)
            'bell_tower',  # 8 - Bell Tower (Human Kingdom special event)
            'general_event',  # 9 - General Event (random from pool, becomes buff after visit)
            'combat_event_hard',  # 10 - Hard Enemy
            'zone_portal'  # 11 - Zone Portal
        ],
        3: [
            'zone_portal',  # 0 - Zone Portal
            ['minion_event', 'buff_event'],  # 1 - Split: Minion OR major buff
            'buff_event',  # 2 - Major Buff
            'general_event',  # 3 - General Event (random from pool, becomes buff after visit)
            'shop_event',  # 4 - Shop
            'minion_event',  # 5 - START (Free minion)
            'buff_event',  # 6 - Major Buff
            'combat_event',  # 7 - Combat (tier scales with ring)
            'bell_tower',  # 8 - Bell Tower (Human Kingdom special event)
            'general_event',  # 9 - General Event (random from pool, becomes buff after visit)
            'combat_event_hard',  # 10 - Hard Enemy
            'zone_portal'  # 11 - Zone Portal
        ]
    },
    'fey_grove': {
        1: [
            'zone_portal',  # 0 - Zone Portal
            ['minion_event', 'buff_event'],  # 1 - Split: Minion OR Buff
            'buff_event',  # 2 - Buff
            'general_event',  # 3 - General Event (random from pool, becomes buff after visit)
            'shop_event',  # 4 - Shop
            'minion_event',  # 5 - START (Free minion)
            'buff_event',  # 6 - Buff
            'combat_event',  # 7 - Enemy
            'ivory_tower',  # 8 - Ivory Tower (Fey Grove special event)
            'general_event',  # 9 - General Event (random from pool, becomes buff after visit)
            'combat_event_hard',  # 10 - Hard Enemy
            'zone_portal'  # 11 - Zone Portal
        ],
        2: [
            'zone_portal',  # 0 - Zone Portal
            ['minion_event', 'buff_event'],  # 1 - Split
            'buff_event',  # 2 - Buff
            'general_event',  # 3 - General Event (random from pool, becomes buff after visit)
            'shop_event',  # 4 - Shop
            'minion_event',  # 5 - START (Free minion)
            'buff_event',  # 6 - Buff
            'combat_event',  # 7 - Enemy
            'ivory_tower',  # 8 - Ivory Tower (Fey Grove special event)
            'general_event',  # 9 - General Event (random from pool, becomes buff after visit)
            'combat_event_hard',  # 10 - Hard Enemy
            'zone_portal'  # 11 - Zone Portal
        ],
        3: [
            'zone_portal',  # 0 - Zone Portal
            ['minion_event', 'buff_event'],  # 1 - Split
            'buff_event',  # 2 - Buff
            'general_event',  # 3 - General Event (random from pool, becomes buff after visit)
            'shop_event',  # 4 - Shop
            'minion_event',  # 5 - START (Free minion)
            'buff_event',  # 6 - Buff
            'combat_event',  # 7 - Enemy
            'ivory_tower',  # 8 - Ivory Tower (Fey Grove special event)
            'general_event',  # 9 - General Event (random from pool, becomes buff after visit)
            'combat_event_hard',  # 10 - Hard Enemy
            'zone_portal'  # 11 - Zone Portal
        ]
    },
    'construct_foundry': {
        1: [
            'zone_portal',  # 0 - Zone Portal
            ['minion_event', 'buff_event'],  # 1 - Split: Minion OR Buff
            'buff_event',  # 2 - Buff
            'general_event',  # 3 - General Event (random from pool, becomes buff after visit)
            'shop_event',  # 4 - Shop
            'minion_event',  # 5 - START (Free minion)
            'buff_event',  # 6 - Buff
            'combat_event',  # 7 - Enemy
            'grand_city',  # 8 - Grand City (Construct Foundry special event)
            'general_event',  # 9 - General Event (random from pool, becomes buff after visit)
            'combat_event_hard',  # 10 - Hard Enemy
            'zone_portal'  # 11 - Zone Portal
        ],
        2: [
            'zone_portal',  # 0 - Zone Portal
            ['minion_event', 'buff_event'],  # 1 - Split
            'buff_event',  # 2 - Buff
            'general_event',  # 3 - General Event (random from pool, becomes buff after visit)
            'shop_event',  # 4 - Shop
            'minion_event',  # 5 - START (Free minion)
            'buff_event',  # 6 - Buff
            'combat_event',  # 7 - Enemy
            'grand_city',  # 8 - Grand City (Construct Foundry special event)
            'general_event',  # 9 - General Event (random from pool, becomes buff after visit)
            'combat_event_hard',  # 10 - Hard Enemy
            'zone_portal'  # 11 - Zone Portal
        ],
        3: [
            'zone_portal',  # 0 - Zone Portal
            ['minion_event', 'buff_event'],  # 1 - Split
            'buff_event',  # 2 - Buff
            'general_event',  # 3 - General Event (random from pool, becomes buff after visit)
            'shop_event',  # 4 - Shop
            'minion_event',  # 5 - START (Free minion)
            'buff_event',  # 6 - Buff
            'combat_event',  # 7 - Enemy
            'grand_city',  # 8 - Grand City (Construct Foundry special event)
            'general_event',  # 9 - General Event (random from pool, becomes buff after visit)
            'combat_event_hard',  # 10 - Hard Enemy
            'zone_portal'  # 11 - Zone Portal
        ]
    },
    'cult_sanctum': {
        1: [
            'zone_portal',  # 0 - Zone Portal
            ['minion_event', 'buff_event'],  # 1 - Split: Minion OR Buff
            'buff_event',  # 2 - Buff
            'general_event',  # 3 - General Event (random from pool, becomes buff after visit)
            'shop_event',  # 4 - Shop
            'minion_event',  # 5 - START (Free minion)
            'buff_event',  # 6 - Buff
            'combat_event',  # 7 - Enemy
            'the_red_gate',  # 8 - The Red Gate (Cult Sanctum special event)
            'general_event',  # 9 - General Event (random from pool, becomes buff after visit)
            'combat_event_hard',  # 10 - Hard Enemy
            'zone_portal'  # 11 - Zone Portal
        ],
        2: [
            'zone_portal',  # 0 - Zone Portal
            ['minion_event', 'buff_event'],  # 1 - Split
            'buff_event',  # 2 - Buff
            'general_event',  # 3 - General Event (random from pool, becomes buff after visit)
            'shop_event',  # 4 - Shop
            'minion_event',  # 5 - START (Free minion)
            'buff_event',  # 6 - Buff
            'combat_event',  # 7 - Enemy
            'the_red_gate',  # 8 - The Red Gate (Cult Sanctum special event)
            'general_event',  # 9 - General Event (random from pool, becomes buff after visit)
            'combat_event_hard',  # 10 - Hard Enemy
            'zone_portal'  # 11 - Zone Portal
        ],
        3: [
            'zone_portal',  # 0 - Zone Portal
            ['minion_event', 'buff_event'],  # 1 - Split
            'buff_event',  # 2 - Buff
            'general_event',  # 3 - General Event (random from pool, becomes buff after visit)
            'shop_event',  # 4 - Shop
            'minion_event',  # 5 - START (Free minion)
            'buff_event',  # 6 - Buff
            'combat_event',  # 7 - Enemy
            'the_red_gate',  # 8 - The Red Gate (Cult Sanctum special event)
            'general_event',  # 9 - General Event (random from pool, becomes buff after visit)
            'combat_event_hard',  # 10 - Hard Enemy
            'zone_portal'  # 11 - Zone Portal
        ]
    },
    'undead_crypts': {
        1: [
            'zone_portal',  # 0 - Zone Portal
            ['minion_event', 'buff_event'],  # 1 - Split: Minion OR Buff
            'buff_event',  # 2 - Buff
            'general_event',  # 3 - General Event (random from pool, becomes buff after visit)
            'shop_event',  # 4 - Shop
            'minion_event',  # 5 - START (Free minion)
            'buff_event',  # 6 - Buff
            'combat_event',  # 7 - Enemy
            'the_great_work',  # 8 - The Great Work (Undead Crypts special event)
            'general_event',  # 9 - General Event (random from pool, becomes buff after visit)
            'combat_event_hard',  # 10 - Hard Enemy
            'zone_portal'  # 11 - Zone Portal
        ],
        2: [
            'zone_portal',  # 0 - Zone Portal
            ['minion_event', 'buff_event'],  # 1 - Split
            'buff_event',  # 2 - Buff
            'general_event',  # 3 - General Event (random from pool, becomes buff after visit)
            'shop_event',  # 4 - Shop
            'minion_event',  # 5 - START (Free minion)
            'buff_event',  # 6 - Buff
            'combat_event',  # 7 - Enemy
            'the_great_work',  # 8 - The Great Work (Undead Crypts special event)
            'general_event',  # 9 - General Event (random from pool, becomes buff after visit)
            'combat_event_hard',  # 10 - Hard Enemy
            'zone_portal'  # 11 - Zone Portal
        ],
        3: [
            'zone_portal',  # 0 - Zone Portal
            ['minion_event', 'buff_event'],  # 1 - Split
            'buff_event',  # 2 - Buff
            'general_event',  # 3 - General Event (random from pool, becomes buff after visit)
            'shop_event',  # 4 - Shop
            'minion_event',  # 5 - START (Free minion)
            'buff_event',  # 6 - Buff
            'combat_event',  # 7 - Enemy
            'the_great_work',  # 8 - The Great Work (Undead Crypts special event)
            'general_event',  # 9 - General Event (random from pool, becomes buff after visit)
            'combat_event_hard',  # 10 - Hard Enemy
            'zone_portal'  # 11 - Zone Portal
        ]
    },
    'beast_wildlands': {
        1: [
            'zone_portal',  # 0 - Zone Portal
            ['minion_event', 'buff_event'],  # 1 - Split: Minion OR Buff
            'buff_event',  # 2 - Buff
            'general_event',  # 3 - General Event (random from pool, becomes buff after visit)
            'shop_event',  # 4 - Shop
            'minion_event',  # 5 - START (Free minion)
            'buff_event',  # 6 - Buff
            'combat_event',  # 7 - Enemy
            'the_great_hunt',  # 8 - The Great Hunt (Beast Wildlands special event)
            'general_event',  # 9 - General Event (random from pool, becomes buff after visit)
            'combat_event_hard',  # 10 - Hard Enemy
            'zone_portal'  # 11 - Zone Portal
        ],
        2: [
            'zone_portal',  # 0 - Zone Portal
            ['minion_event', 'buff_event'],  # 1 - Split
            'buff_event',  # 2 - Buff
            'general_event',  # 3 - General Event (random from pool, becomes buff after visit)
            'shop_event',  # 4 - Shop
            'minion_event',  # 5 - START (Free minion)
            'buff_event',  # 6 - Buff
            'combat_event',  # 7 - Enemy
            'the_great_hunt',  # 8 - The Great Hunt (Beast Wildlands special event)
            'general_event',  # 9 - General Event (random from pool, becomes buff after visit)
            'combat_event_hard',  # 10 - Hard Enemy
            'zone_portal'  # 11 - Zone Portal
        ],
        3: [
            'zone_portal',  # 0 - Zone Portal
            ['minion_event', 'buff_event'],  # 1 - Split
            'buff_event',  # 2 - Buff
            'general_event',  # 3 - General Event (random from pool, becomes buff after visit)
            'shop_event',  # 4 - Shop
            'minion_event',  # 5 - START (Free minion)
            'buff_event',  # 6 - Buff
            'combat_event',  # 7 - Enemy
            'the_great_hunt',  # 8 - The Great Hunt (Beast Wildlands special event)
            'general_event',  # 9 - General Event (random from pool, becomes buff after visit)
            'combat_event_hard',  # 10 - Hard Enemy
            'zone_portal'  # 11 - Zone Portal
        ]
    }
}

# Event Scaling Configuration
EVENT_SCALING = {
    # Minion events - use multi-tier pool based on ring
    'minion_event': {
        'choices': 3,  # Number of minions to choose from
        'uses_multi_tier': True  # Uses cumulative tier pool
    },

    # Buff events - base values, ring bonus adds +1 per ring
    'buff_event': {
        'health_options': [3, 0, 1],  # [health only, attack only, both]
        'attack_options': [0, 2, 1]
    },

    # Shop events - use multi-tier pool based on ring
    'shop_event': {
        'base_cost': 5,
        'cost_per_ring': 3,
        'num_offers': 4,
        'uses_multi_tier': True  # Uses cumulative tier pool
    },

    # Combat events - tier_offset determines minion tier relative to current ring
    # combat = same tier as ring, hard = tier+1
    'combat_event': {
        'difficulty': 'normal',
        'band_size_base': 2,
        'band_size_per_ring': 0.5,
        'tier_offset': 0  # tier = ring
    },
    'combat_event_hard': {
        'difficulty': 'hard',
        'band_size_base': 3,
        'band_size_per_ring': 0.5,
        'tier_offset': 1  # tier = ring + 1
    }
}


# Starting Band Configuration - Now uses real minion definitions
def get_starting_band():
    """Get the starting band with real minion instances"""
    from minions import get_minion_by_name, create_minion_instance

    # Get minion templates from the actual minion definitions
    soldier_template = get_minion_by_name('Soldier')
    scout_template = get_minion_by_name('Scout')

    # Create proper minion instances with band IDs
    starting_band = []

    if soldier_template:
        soldier = create_minion_instance(soldier_template, tier=1, assign_band_id=True)
        soldier['position'] = 0
        starting_band.append(soldier)

    if scout_template:
        scout = create_minion_instance(scout_template, tier=1, assign_band_id=True)
        scout['position'] = 1
        starting_band.append(scout)

    return starting_band


def get_starting_band_for_hero(hero_id):
    """Get the starting band for a specific hero with real minion instances"""
    from minions import get_minion_by_name, create_minion_instance
    from hero_definitions import get_hero_starting_minions

    # Get minion names for this hero
    minion_names = get_hero_starting_minions(hero_id)

    # Create proper minion instances with band IDs
    starting_band = []

    for position, minion_name in enumerate(minion_names):
        template = get_minion_by_name(minion_name)
        if template:
            minion = create_minion_instance(template, tier=1, assign_band_id=True)
            minion['position'] = position
            starting_band.append(minion)
        else:
            logger.warning(f"[CONFIG] Warning: Could not find minion template for '{minion_name}'")

    # Fallback to default band if no minions were created
    if not starting_band:
        return get_starting_band()

    return starting_band


# Starting Band Configuration - Maintain backward compatibility
STARTING_BAND = get_starting_band()

# Combat Configuration
MAX_COMBAT_ROUNDS = 60
AUTO_COMBAT_DELAY_MS = 1500  # 1.5 seconds between auto attacks
RESET_HEALTH_AFTER_COMBAT = True  # Whether to reset minion health after combat

# Zone Configuration
ZONES = {
    'starting_plains': {
        'name': 'The Crossroads',
        'description': 'A mystical nexus where all paths converge. Creatures from every tribe gather here.',
        'pool_modifiers': None,  # All creature types available
        'connects_to': ['beast_wildlands', 'human_kingdom', 'undead_crypts', 'fey_grove', 'construct_foundry', 'cult_sanctum'],
        'unlocked_by_default': True,
        'theme_color': '#4CAF50',
        'icon': generate_lucide_svg('compass', width=24, height=24)
    },
    'beast_wildlands': {
        'name': 'Beast Wildlands',
        'description': 'Untamed wilderness where beasts roam free',
        'pool_modifiers': ['Beast'],  # Only Beast creatures appear
        'connects_to': ['starting_plains'],
        'unlocked_by_default': True,
        'theme_color': '#8BC34A',
        'icon': generate_lucide_svg('rabbit', width=24, height=24)
    },
    'human_kingdom': {
        'name': 'Human Kingdom',
        'description': 'Fortified cities and training grounds where soldiers and warriors gather',
        'pool_modifiers': ['Human'],  # Only Human creatures appear
        'connects_to': ['starting_plains'],
        'unlocked_by_default': True,
        'theme_color': '#2196F3',
        'icon': generate_lucide_svg('shield', width=24, height=24)
    },
    'undead_crypts': {
        'name': 'Undead Crypts',
        'description': 'Dark tombs and cursed graveyards where the dead refuse to rest',
        'pool_modifiers': ['Undead'],  # Only Undead creatures appear
        'connects_to': ['starting_plains'],
        'unlocked_by_default': True,
        'theme_color': '#9C27B0',
        'icon': generate_lucide_svg('skull', width=24, height=24)
    },
    'fey_grove': {
        'name': 'Fey Grove',
        'description': 'An enchanted forest where magic flows freely and the fey dance beneath moonlight',
        'pool_modifiers': ['Fey'],  # Only Fey creatures appear
        'connects_to': ['starting_plains'],
        'unlocked_by_default': True,
        'theme_color': '#E91E63',
        'icon': generate_lucide_svg('sparkles', width=24, height=24)
    },
    'construct_foundry': {
        'name': 'Construct Foundry',
        'description': 'Ancient workshops filled with mechanical wonders and arcane machinery',
        'pool_modifiers': ['Construct'],  # Only Construct creatures appear
        'connects_to': ['starting_plains'],
        'unlocked_by_default': True,
        'theme_color': '#FF9800',
        'icon': generate_lucide_svg('cog', width=24, height=24)
    },
    'cult_sanctum': {
        'name': 'Cult Sanctum',
        'description': 'Forbidden temples where dark rituals summon twisted followers',
        'pool_modifiers': ['Cult'],  # Only Cult creatures appear
        'connects_to': ['starting_plains'],
        'unlocked_by_default': True,
        'theme_color': '#F44336',
        'icon': generate_lucide_svg('flame', width=24, height=24)
    }
}

DEFAULT_STARTING_ZONE = 'starting_plains'