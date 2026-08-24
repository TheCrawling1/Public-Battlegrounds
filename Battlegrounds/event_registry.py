"""
Event Registry - Centralized registry of all events in Battleground

This file provides a clear index of all available events in the game,
organized by category for easy reference and lookup.

Similar to minions.py, this serves as the "source of truth" for what
events exist and how they're categorized.

Events are built from screen templates (defined in event_templates.py)
and event definitions (defined in events.py). This registry organizes
them for easy access.
"""

import logging

logger = logging.getLogger(__name__)

from game_engine.events.events import (
    # Basic gameplay events
    MINION_EVENT,
    BUFF_EVENT,
    COMBAT_EVENT,
    COMBAT_EVENT_HARD,
    SHOP_EVENT,
    STATUE_EVENT,
    ZONE_PORTAL_EVENT,

    # Bell tower event and sub-events
    BELL_TOWER,
    BELL_TOWER_BLESSING,
    BELL_TOWER_COMBAT,
    BELL_TOWER_QUASIMODO,

    # Crossroads events
    MERCENARY_CAMP,
    COLLAPSED_MINE,
    VAST_KENNELS,
    WATCHTOWER,

    # Crossroads sub-events
    MERCENARY_CAMP_HIRE_GUARD,
    MERCENARY_CAMP_DUEL,
    MERCENARY_CAMP_DUEL_VICTORY,
    MERCENARY_CAMP_TAKEOVER,
    MERCENARY_CAMP_TAKEOVER_VICTORY,
    KENNELS_BUY_HOUND,
    KENNELS_BUY_CAT,
    WATCHTOWER_STORM,
    WATCHTOWER_STORM_VICTORY,
    WATCHTOWER_AID,

    # Zone events
    IVORY_TOWER,
    GRAND_CITY,
    SCRAP_HEAP,

    # Cult zone events
    THE_RED_GATE,
    RED_GATE_ABANDON_STRENGTH,
    RED_GATE_ABANDON_VIGOR,
    RED_GATE_ABANDON_SKILL,
    RED_GATE_ABANDON_ALLEGIANCE,

    # Undead zone events
    THE_GREAT_WORK,
    GREAT_WORK_SEARCH_GRAVES,
    GREAT_WORK_MARK_SCROLLS,
    GREAT_WORK_COUNT_BLESSINGS,

    # Beast Wildlands events
    THE_GREAT_HUNT,
    GREAT_HUNT_FEED_SACRIFICE,
    GREAT_HUNT_FEED_TARGET,
    GREAT_HUNT_BOSS_ENCOUNTER,
    GREAT_HUNT_BOSS_VICTORY,
    GREAT_HUNT_VICTORY_DIRE_PACK,
    GREAT_HUNT_VICTORY_CONGREGATION,
    GREAT_HUNT_VICTORY_CHAINED_BEAST,
    GREAT_HUNT_VICTORY_BEHEMOTH,
    GREAT_HUNT_VICTORY_VENOMSPAWN,
    GREAT_HUNT_VICTORY_GREATER_POSSESSED,
)


# ==================== BASIC GAMEPLAY EVENTS ====================
# Single-screen events that are the building blocks of the game

BASIC_GAMEPLAY_EVENTS = {
    # Minion acquisition
    'minion_event': {
        'event': MINION_EVENT,
        'category': 'acquisition',
        'description': 'Choose a minion from 3 options',
        'screens': 1,
        'modular': True
    },

    # Buff event - scales with ring (+1 per ring)
    'buff_event': {
        'event': BUFF_EVENT,
        'category': 'buff',
        'description': 'Blessing: base +3 health, +2 attack, or +1/+1 (scales with ring)',
        'screens': 1,
        'modular': True
    },

    # Combat (2 difficulty levels - tier determined by ring + offset)
    'combat_event': {
        'event': COMBAT_EVENT,
        'category': 'combat',
        'description': 'Normal combat (tier = ring)',
        'screens': 1,
        'modular': True
    },
    'combat_event_hard': {
        'event': COMBAT_EVENT_HARD,
        'category': 'combat',
        'description': 'Hard combat (tier = ring + 1)',
        'screens': 1,
        'modular': True
    },

    # Services
    'shop_event': {
        'event': SHOP_EVENT,
        'category': 'service',
        'description': 'Buy minions with gold (repeating)',
        'screens': 1,
        'modular': True
    },
    'statue': {
        'event': STATUE_EVENT,
        'category': 'service',
        'description': 'Combine minions into golden versions (repeating)',
        'screens': 1,
        'modular': True
    },

    # Special
    'zone_portal': {
        'event': ZONE_PORTAL_EVENT,
        'category': 'special',
        'description': 'Portal to travel between zones',
        'screens': 1,
        'modular': True
    },
}


# ==================== STORY EVENTS ====================
# Multi-screen narrative events

STORY_EVENTS = {
    'bell_tower': {
        'event': BELL_TOWER,
        'visit_rule': 'repeatable',
        'description': 'Ring bells for blessings, unlock Quasimodo',
        'flow': 'choice → (pay: blessing) OR (break in: combat → blessing) OR (seek: quasimodo) OR (leave)',
        'screens': 1,
        'modular': True,
        'sub_events': ['bell_tower_blessing', 'bell_tower_combat', 'bell_tower_quasimodo'],
        'state_tracking': {
            'bells_rung': 'Counter incremented each time bell is rung',
            'unlock_condition': 'bells_rung >= 4 to unlock Quasimodo'
        }
    },
}


# ==================== BELL TOWER SUB-EVENTS ====================
# Modular components of the bell tower event

BELL_TOWER_SUB_EVENTS = {
    'bell_tower_blessing': {
        'event': BELL_TOWER_BLESSING,
        'parent_event': 'bell_tower',
        'description': 'Apply Ring X keyword to a minion',
        'screens': 1,
        'buff_type': 'ring',
        'details': 'Ring X where X = current ring level'
    },

    'bell_tower_combat': {
        'event': BELL_TOWER_COMBAT,
        'parent_event': 'bell_tower',
        'description': 'Fight Human tribe guardians',
        'screens': 1,
        'difficulty': 'normal',
        'special_rules': [
            'No gold rewards',
            'On victory: chains to bell_tower_blessing'
        ]
    },

    'bell_tower_quasimodo': {
        'event': BELL_TOWER_QUASIMODO,
        'parent_event': 'bell_tower',
        'description': 'Receive legendary minion Quasimodo',
        'screens': 1,
        'minion': 'Quasimodo',
        'tier': 5,
        'unlock_requirement': 'bells_rung >= 4'
    },
}


# ==================== CROSSROADS EVENTS ====================
# Choice-based events with multiple paths and conditional options

CROSSROADS_EVENTS = {
    'mercenary_camp': {
        'event': MERCENARY_CAMP,
        'category': 'crossroads',
        'description': 'Hire guards, duel warriors, or stage a hostile takeover',
        'flow': 'choice → (hire guard OR duel OR takeover OR alliance)',
        'screens': 1,
        'modular': True,
        'sub_events': ['mercenary_camp_hire_guard', 'mercenary_camp_duel', 'mercenary_camp_takeover'],
        'conditions': {
            'alliance': 'unique_tribes >= 4'
        }
    },

    'collapsed_mine': {
        'event': COLLAPSED_MINE,
        'category': 'crossroads',
        'description': 'Navigate a mine for gold with varying risk levels',
        'flow': 'choice → (slow: gold OR fast: gold + combat chance OR faster: requires Fast keyword)',
        'screens': 1,
        'modular': True,
        'conditions': {
            'faster': 'has_keyword_Fast'
        }
    },

    'vast_kennels': {
        'event': VAST_KENNELS,
        'category': 'crossroads',
        'description': 'Buy beast companions and treats',
        'flow': 'choice → (buy hound OR buy cat OR buy treat OR pack discount)',
        'screens': 1,
        'modular': True,
        'sub_events': ['kennels_buy_hound', 'kennels_buy_cat'],
        'conditions': {
            'pack_discount': 'beast_count >= 3'
        }
    },

    'watchtower': {
        'event': WATCHTOWER,
        'category': 'crossroads',
        'description': 'Strategic tower with multiple approaches',
        'flow': 'choice → (pay OR storm OR sneak OR request aid OR infiltrate)',
        'screens': 1,
        'modular': True,
        'sub_events': ['watchtower_storm', 'watchtower_aid'],
        'conditions': {
            'infiltrate': 'has_keyword_Hide'
        }
    },
}


# ==================== CROSSROADS SUB-EVENTS ====================
# Modular components of crossroads events

CROSSROADS_SUB_EVENTS = {
    'mercenary_camp_hire_guard': {
        'event': MERCENARY_CAMP_HIRE_GUARD,
        'parent_event': 'mercenary_camp',
        'description': 'Apply Guard keyword to a minion',
        'screens': 1,
        'buff_type': 'keyword_guard'
    },

    'mercenary_camp_duel': {
        'event': MERCENARY_CAMP_DUEL,
        'parent_event': 'mercenary_camp',
        'description': '1v1 combat for gold reward',
        'screens': 1,
        'difficulty': 'scaled'
    },

    'mercenary_camp_duel_victory': {
        'event': MERCENARY_CAMP_DUEL_VICTORY,
        'parent_event': 'mercenary_camp',
        'description': 'Gold reward after duel victory',
        'screens': 1
    },

    'mercenary_camp_takeover': {
        'event': MERCENARY_CAMP_TAKEOVER,
        'parent_event': 'mercenary_camp',
        'description': 'Hard combat to take over the camp',
        'screens': 1,
        'difficulty': 'hard'
    },

    'mercenary_camp_takeover_victory': {
        'event': MERCENARY_CAMP_TAKEOVER_VICTORY,
        'parent_event': 'mercenary_camp',
        'description': 'Choose buff type after takeover victory',
        'screens': 1
    },

    'kennels_buy_hound': {
        'event': KENNELS_BUY_HOUND,
        'parent_event': 'vast_kennels',
        'description': 'Add War Hound to band',
        'screens': 1,
        'minion': 'War Hound'
    },

    'kennels_buy_cat': {
        'event': KENNELS_BUY_CAT,
        'parent_event': 'vast_kennels',
        'description': 'Add Alley Cat to band',
        'screens': 1,
        'minion': 'Alley Cat'
    },

    'watchtower_storm': {
        'event': WATCHTOWER_STORM,
        'parent_event': 'watchtower',
        'description': 'Combat encounter at the watchtower',
        'screens': 1,
        'difficulty': 'normal'
    },

    'watchtower_storm_victory': {
        'event': WATCHTOWER_STORM_VICTORY,
        'parent_event': 'watchtower',
        'description': 'Choose buff after storming the tower',
        'screens': 1
    },

    'watchtower_aid': {
        'event': WATCHTOWER_AID,
        'parent_event': 'watchtower',
        'description': 'Receive blessing for 4+ tribe alliance',
        'screens': 1,
        'requirement': 'unique_tribes >= 4'
    },
}


# ==================== FEY ZONE EVENTS ====================
# Events specific to the Fey zone

FEY_ZONE_EVENTS = {
    'ivory_tower': {
        'event': IVORY_TOWER,
        'category': 'zone_fey',
        'visit_rule': 'repeatable',
        'description': 'Sealed tower - weaken seal for powerful reward',
        'flow': 'choice → (take damage to weaken seal OR lose steps to weaken seal) → unlock band slot when seal breaks',
        'screens': 1,
        'modular': True,
        'state_tracking': {
            'ivory_tower_seal': 'Counter starts at 3, decreases with choices',
            'unlock_condition': 'ivory_tower_seal <= 0 to unlock extra band slot'
        }
    },
}


# ==================== CONSTRUCT ZONE EVENTS ====================
# Events specific to the Construct zone

CONSTRUCT_ZONE_EVENTS = {
    'grand_city': {
        'event': GRAND_CITY,
        'category': 'zone_construct',
        'visit_rule': 'repeatable',
        'description': 'Powerful options with curse mechanic',
        'flow': 'choice → (portal to fey OR hero buff OR golden minion) - all options apply curse',
        'screens': 1,
        'modular': True,
        'state_tracking': {
            'curse_level': 'Amount of curse applied',
            'curse_type': 'stat_drain - minions lose stats during combat'
        }
    },
    'scrap_heap': {
        'event': SCRAP_HEAP,
        'category': 'zone_construct',
        'forced_event': True,
        'description': 'Forced event to deal with curse (stat drain mechanic)',
        'flow': 'forced → (suffer waste OR brave smog OR suffer through OR blind luck if hero has no keywords)',
        'screens': 1,
        'modular': True,
        'conditions': {
            'blind_luck': 'hero has no keywords (removes curse completely)'
        }
    },
}


# ==================== CULT ZONE EVENTS ====================
# Events specific to the Cult Sanctum zone

CULT_ZONE_EVENTS = {
    'the_red_gate': {
        'event': THE_RED_GATE,
        'category': 'zone_cult',
        'visit_rule': 'repeatable',
        'description': 'Strip minion of everything to gain Ethereal [Last]',
        'flow': 'choice → (abandon strength OR abandon vigor OR abandon skill OR abandon allegiance) → when minion is 0/1 with no types/keywords, gain Ethereal',
        'screens': 1,
        'modular': True,
        'sub_events': ['red_gate_abandon_strength', 'red_gate_abandon_vigor', 'red_gate_abandon_skill', 'red_gate_abandon_allegiance'],
        'state_tracking': {
            'unlock_condition': 'Tier 3+ minion with 0 attack, 1 health, no types, no keywords'
        }
    },
}


# ==================== CULT ZONE SUB-EVENTS ====================
# Modular components of cult zone events

CULT_ZONE_SUB_EVENTS = {
    'red_gate_abandon_strength': {
        'event': RED_GATE_ABANDON_STRENGTH,
        'parent_event': 'the_red_gate',
        'description': 'Reduce a minion\'s attack',
        'screens': 1,
    },
    'red_gate_abandon_vigor': {
        'event': RED_GATE_ABANDON_VIGOR,
        'parent_event': 'the_red_gate',
        'description': 'Reduce a minion\'s health (min 1)',
        'screens': 1,
    },
    'red_gate_abandon_skill': {
        'event': RED_GATE_ABANDON_SKILL,
        'parent_event': 'the_red_gate',
        'description': 'Remove a minion\'s keywords',
        'screens': 1,
    },
    'red_gate_abandon_allegiance': {
        'event': RED_GATE_ABANDON_ALLEGIANCE,
        'parent_event': 'the_red_gate',
        'description': 'Remove a minion\'s types',
        'screens': 1,
    },
}


# ==================== UNDEAD ZONE EVENTS ====================
# Events specific to the Undead Crypts zone

UNDEAD_ZONE_EVENTS = {
    'the_great_work': {
        'event': THE_GREAT_WORK,
        'category': 'zone_undead',
        'visit_rule': 'repeatable',
        'description': 'Ad Nauseam event - all effects cost more each use',
        'flow': 'choice → (search graves OR mark scrolls OR count blessings) - each costs escalating health. Lichdom transforms hero.',
        'screens': 1,
        'modular': True,
        'sub_events': ['great_work_search_graves', 'great_work_mark_scrolls', 'great_work_count_blessings'],
        'state_tracking': {
            'search_graves_cost': 'Escalating cost for Search the Graves',
            'mark_scrolls_cost': 'Escalating cost for Mark the Scrolls',
            'count_blessings_cost': 'Escalating cost for Count Your Blessings',
            'lichdom': 'Hero power - health costs become gold costs'
        }
    },
}


# ==================== UNDEAD ZONE SUB-EVENTS ====================
# Modular components of undead zone events

UNDEAD_ZONE_SUB_EVENTS = {
    'great_work_search_graves': {
        'event': GREAT_WORK_SEARCH_GRAVES,
        'parent_event': 'the_great_work',
        'description': 'Roll 3 random minions, buy or reroll',
        'screens': 1,
    },
    'great_work_mark_scrolls': {
        'event': GREAT_WORK_MARK_SCROLLS,
        'parent_event': 'the_great_work',
        'description': 'See next event, keep/discard/reroll',
        'screens': 1,
    },
    'great_work_count_blessings': {
        'event': GREAT_WORK_COUNT_BLESSINGS,
        'parent_event': 'the_great_work',
        'description': 'Receive a blessing (standard buff)',
        'screens': 1,
    },
}


# ==================== BEAST WILDLANDS EVENTS ====================
# Events specific to the Beast Wildlands zone

BEAST_WILDLANDS_EVENTS = {
    'the_great_hunt': {
        'event': THE_GREAT_HUNT,
        'category': 'zone_beast',
        'visit_rule': 'repeatable',
        'description': 'Bounty board with tiered boss hunts for unique rewards',
        'flow': 'bounty board → choose hunt → boss_combat → choose reward buff',
        'screens': 1,
        'modular': True,
        'sub_events': [
            'great_hunt_dire_pack', 'great_hunt_congregation',
            'great_hunt_chained_beast', 'great_hunt_behemoth',
            'great_hunt_venomspawn', 'great_hunt_greater_possessed'
        ],
        'state_tracking': {
            'great_hunt_tier1_complete': 'Counter for T1 bounties completed',
            'great_hunt_tier2_complete': 'Counter for T2 bounties completed',
            'unlock_condition': 'T1 complete >= 1 unlocks T2, T2 complete >= 2 unlocks T3'
        }
    },
}


# ==================== BEAST WILDLANDS SUB-EVENTS ====================
# Sub-events for The Great Hunt

BEAST_WILDLANDS_SUB_EVENTS = {
    'great_hunt_feed_sacrifice': {
        'event': GREAT_HUNT_FEED_SACRIFICE,
        'parent_event': 'the_great_hunt',
        'description': 'Sacrifice a minion for Feed Your Pack',
    },
    'great_hunt_feed_target': {
        'event': GREAT_HUNT_FEED_TARGET,
        'parent_event': 'the_great_hunt',
        'description': 'Select Beast to receive sacrificed stats',
    },
    'great_hunt_boss_encounter': {
        'event': GREAT_HUNT_BOSS_ENCOUNTER,
        'parent_event': 'the_great_hunt',
        'description': 'Boss encounter with persistent damage',
        'forced_event': True,
    },
    'great_hunt_boss_victory': {
        'event': GREAT_HUNT_BOSS_VICTORY,
        'parent_event': 'the_great_hunt',
        'description': 'Routes to boss-specific victory event',
    },
    'great_hunt_victory_dire_pack': {
        'event': GREAT_HUNT_VICTORY_DIRE_PACK,
        'parent_event': 'the_great_hunt',
        'description': 'Reward: All minions +2/+2, one gains Assault',
    },
    'great_hunt_victory_congregation': {
        'event': GREAT_HUNT_VICTORY_CONGREGATION,
        'parent_event': 'the_great_hunt',
        'description': 'Reward: Recruit 2 Cultists, all Cult +3/+3',
    },
    'great_hunt_victory_chained_beast': {
        'event': GREAT_HUNT_VICTORY_CHAINED_BEAST,
        'parent_event': 'the_great_hunt',
        'description': 'Reward: Choose minion for +8/+8 and Leap',
    },
    'great_hunt_victory_behemoth': {
        'event': GREAT_HUNT_VICTORY_BEHEMOTH,
        'parent_event': 'the_great_hunt',
        'description': 'Reward: Choose minion for Guard and +5/+12',
    },
    'great_hunt_victory_venomspawn': {
        'event': GREAT_HUNT_VICTORY_VENOMSPAWN,
        'parent_event': 'the_great_hunt',
        'description': 'Reward: All Beasts +2/+2 and Poke',
    },
    'great_hunt_victory_greater_possessed': {
        'event': GREAT_HUNT_VICTORY_GREATER_POSSESSED,
        'parent_event': 'the_great_hunt',
        'description': 'Reward: tier × 10 gold, all minions +2/+0',
    },
}


# ==================== COMPLETE REGISTRY ====================
# All events combined for lookup

ALL_EVENTS_REGISTRY = {
    **BASIC_GAMEPLAY_EVENTS,
    **STORY_EVENTS,
    **BELL_TOWER_SUB_EVENTS,
    **CROSSROADS_EVENTS,
    **CROSSROADS_SUB_EVENTS,
    **FEY_ZONE_EVENTS,
    **CONSTRUCT_ZONE_EVENTS,
    **CULT_ZONE_EVENTS,
    **CULT_ZONE_SUB_EVENTS,
    **UNDEAD_ZONE_EVENTS,
    **UNDEAD_ZONE_SUB_EVENTS,
    **BEAST_WILDLANDS_EVENTS,
    **BEAST_WILDLANDS_SUB_EVENTS,
}


# ==================== HELPER FUNCTIONS ====================

def get_event_by_id(event_id: str):
    """Get event registry entry by ID"""
    return ALL_EVENTS_REGISTRY.get(event_id)


def get_events_by_category(category: str):
    """Get all events in a specific category"""
    return {
        event_id: entry
        for event_id, entry in ALL_EVENTS_REGISTRY.items()
        if entry.get('category') == category
    }


def get_modular_events():
    """Get all modular events (can be used as sub-events)"""
    return {
        event_id: entry
        for event_id, entry in ALL_EVENTS_REGISTRY.items()
        if entry.get('modular', False)
    }


def get_story_events():
    """Get all story events"""
    return STORY_EVENTS


def get_combat_events():
    """Get all combat events by difficulty"""
    return get_events_by_category('combat')


def get_buff_events():
    """Get all buff events by power level"""
    return get_events_by_category('buff')


def list_all_event_ids():
    """Get list of all event IDs"""
    return list(ALL_EVENTS_REGISTRY.keys())


def print_event_summary():
    """Print a summary of all events"""
    logger.debug("=" * 60)
    logger.debug("BATTLEGROUND EVENT REGISTRY")
    logger.debug("=" * 60)

    logger.debug(f"\nBasic Gameplay Events: {len(BASIC_GAMEPLAY_EVENTS)}")
    for event_id in BASIC_GAMEPLAY_EVENTS:
        entry = BASIC_GAMEPLAY_EVENTS[event_id]
        logger.debug(f"  - {event_id}: {entry['description']}")

    logger.debug(f"\nStory Events: {len(STORY_EVENTS)}")
    for event_id in STORY_EVENTS:
        entry = STORY_EVENTS[event_id]
        visit = entry.get('visit_rule', 'repeatable')
        logger.debug(f"  - {event_id} ({visit}): {entry['description']}")

    logger.debug(f"\nBell Tower Sub-Events: {len(BELL_TOWER_SUB_EVENTS)}")
    for event_id in BELL_TOWER_SUB_EVENTS:
        entry = BELL_TOWER_SUB_EVENTS[event_id]
        logger.debug(f"  - {event_id}: {entry['description']}")

    logger.debug(f"\nCrossroads Events: {len(CROSSROADS_EVENTS)}")
    for event_id in CROSSROADS_EVENTS:
        entry = CROSSROADS_EVENTS[event_id]
        logger.debug(f"  - {event_id}: {entry['description']}")

    logger.debug(f"\nCrossroads Sub-Events: {len(CROSSROADS_SUB_EVENTS)}")
    for event_id in CROSSROADS_SUB_EVENTS:
        entry = CROSSROADS_SUB_EVENTS[event_id]
        logger.debug(f"  - {event_id}: {entry['description']}")

    logger.debug(f"\nFey Zone Events: {len(FEY_ZONE_EVENTS)}")
    for event_id in FEY_ZONE_EVENTS:
        entry = FEY_ZONE_EVENTS[event_id]
        visit = entry.get('visit_rule', 'repeatable')
        logger.debug(f"  - {event_id} ({visit}): {entry['description']}")

    logger.debug(f"\nConstruct Zone Events: {len(CONSTRUCT_ZONE_EVENTS)}")
    for event_id in CONSTRUCT_ZONE_EVENTS:
        entry = CONSTRUCT_ZONE_EVENTS[event_id]
        forced = '(forced)' if entry.get('forced_event') else ''
        logger.debug(f"  - {event_id} {forced}: {entry['description']}")

    logger.debug(f"\nTotal Events: {len(ALL_EVENTS_REGISTRY)}")
    logger.debug("=" * 60)


# Validate registry on import
if __name__ == '__main__':
    print_event_summary()
