"""
Event Definitions - Declarative event instances using the event template system

This file contains all custom event definitions that can be placed in rings.
Events are built by chaining screen templates from event_templates.py.

Events can be:
- Simple (single screen): Just a screen type string
- Templated (using new system): Dictionary with screens, visit rules, etc.
- Legacy (for compatibility): Existing event strings like 'minion_event', 'combat_event'

Event Structure:
{
    'id': 'unique_event_id',  # For visit tracking
    'visit_rule': 'once_per_run' | 'once_per_ring' | 'repeatable',
    'screens': [
        {
            'type': 'screen_type',
            'parameters': {...},
            'on_complete': 'next_screen_id' | None
        }
    ]
}
"""

import logging

logger = logging.getLogger(__name__)

from lucide_icons import generate_lucide_svg


# ==================== STORY EVENTS ====================

ANCIENT_SHRINE = {
    'id': 'ancient_shrine',
    'visit_rule': 'once_per_run',
    'title': 'Ancient Shrine',
    'description': 'A mysterious shrine offers power to those who pray',
    'screens': [
        {
            'id': 'story',
            'type': 'story',
            'parameters': {
                'title': 'Ancient Shrine',
                'text': 'You discover an ancient shrine radiating mystical energy. The air hums with power as you approach.',
                'icon': 'church',
                'continue_text': 'Pray at the shrine'
            },
            'on_continue': 'choice'
        },
        {
            'id': 'choice',
            'type': 'make_choice',
            'parameters': {
                'title': 'Choose Your Prayer',
                'message': 'The shrine responds to your intention. What do you seek?',
                'choices': [
                    {
                        'name': 'Pray for Strength',
                        'description': 'Request a powerful blessing for your companions',
                        'icon': generate_lucide_svg('flame', width=24, height=24),
                        'next_screen': 'buff_reward'
                    },
                    {
                        'name': 'Pray for Allies',
                        'description': 'Request a new companion to join your cause',
                        'icon': generate_lucide_svg('users', width=24, height=24),
                        'next_screen': 'minion_reward'
                    }
                ]
            }
        },
        {
            'id': 'buff_reward',
            'type': 'select_buff_type',
            'parameters': {
                'buff_power': 'major',
                'title': 'Divine Blessing',
                'allow_skip': False
            }
        },
        {
            'id': 'minion_reward',
            'type': 'select_minion',
            'parameters': {
                'count': 3,
                'tier_pool': 'current_tier',
                'title': 'Sacred Companion',
                'message': 'The shrine summons powerful allies',
                'allow_skip': False
            }
        }
    ]
}


MYSTERIOUS_MERCHANT = {
    'id': 'mysterious_merchant',
    'visit_rule': 'once_per_ring',
    'title': 'Mysterious Merchant',
    'description': 'A traveling merchant offers rare goods',
    'screens': [
        {
            'id': 'story',
            'type': 'story',
            'parameters': {
                'title': 'Mysterious Merchant',
                'text': 'A cloaked figure appears from the mist, their cart laden with curious items. "Looking for something special?" they ask with a knowing smile.',
                'icon': 'store',
                'continue_text': 'Browse their wares'
            },
            'on_continue': 'shop'
        },
        {
            'id': 'shop',
            'type': 'shop',
            'parameters': {
                'title': 'Merchant\'s Wares'
            }
        }
    ]
}


GUARDIAN_TRIAL = {
    'id': 'guardian_trial',
    'visit_rule': 'once_per_run',
    'title': 'Guardian Trial',
    'description': 'Defeat a powerful guardian for great rewards',
    'screens': [
        {
            'id': 'story_intro',
            'type': 'story',
            'parameters': {
                'title': 'The Guardian Awaits',
                'text': 'A massive stone guardian blocks your path. Its eyes glow with ancient power. "Only the worthy may pass," it rumbles. "Prove your strength."',
                'icon': 'shield',
                'continue_text': 'Accept the challenge'
            },
            'on_continue': 'combat'
        },
        {
            'id': 'combat',
            'type': 'combat',
            'parameters': {
                'difficulty': 'elite',
                'title': 'Guardian Battle'
            },
            'on_victory': 'victory_story',
            'on_defeat': None  # Run ends
        },
        {
            'id': 'victory_story',
            'type': 'story',
            'parameters': {
                'title': 'Victory',
                'text': 'The guardian crumbles to dust, revealing a hidden chamber filled with treasures. "You are worthy," echoes its final words.',
                'icon': 'trophy',
                'continue_text': 'Claim your reward'
            },
            'on_continue': 'reward_choice'
        },
        {
            'id': 'reward_choice',
            'type': 'make_choice',
            'parameters': {
                'title': 'Choose Your Reward',
                'message': 'The chamber offers multiple treasures. You can only carry one.',
                'choices': [
                    {
                        'name': 'Sacred Relic',
                        'description': 'A powerful blessing for your band',
                        'icon': generate_lucide_svg('sparkles', width=24, height=24),
                        'next_screen': 'buff_reward'
                    },
                    {
                        'name': 'Ancient Companion',
                        'description': 'A legendary minion joins your cause',
                        'icon': generate_lucide_svg('gem', width=24, height=24),
                        'next_screen': 'minion_reward'
                    },
                    {
                        'name': 'Gold Hoard',
                        'description': 'A fortune in gold coins',
                        'icon': generate_lucide_svg('coins', width=24, height=24),
                        'next_screen': 'gold_reward'
                    }
                ]
            }
        },
        {
            'id': 'buff_reward',
            'type': 'select_buff_type',
            'parameters': {
                'buff_power': 'ultimate',
                'title': 'Sacred Relic',
                'allow_skip': False
            }
        },
        {
            'id': 'minion_reward',
            'type': 'select_minion',
            'parameters': {
                'count': 3,
                'tier_pool': 'current_tier',
                'rarity_filter': 'rare',
                'title': 'Ancient Companion',
                'message': 'A powerful ally appears',
                'allow_skip': False
            }
        },
        {
            'id': 'gold_reward',
            'type': 'grant_gold',
            'parameters': {
                'amount': 50
            }
        }
    ]
}


CURSED_FOUNTAIN = {
    'id': 'cursed_fountain',
    'visit_rule': 'once_per_run',
    'title': 'Cursed Fountain',
    'description': 'Risk damage for potential great reward',
    'screens': [
        {
            'id': 'story',
            'type': 'story',
            'parameters': {
                'title': 'Cursed Fountain',
                'text': 'A dark fountain bubbles with strange liquid. Ancient runes warn: "Power demands sacrifice." Do you dare drink?',
                'icon': 'droplet',
                'continue_text': 'Make your choice'
            },
            'on_continue': 'choice'
        },
        {
            'id': 'choice',
            'type': 'make_choice',
            'parameters': {
                'title': 'The Fountain\'s Offer',
                'message': 'Will you risk the curse?',
                'choices': [
                    {
                        'name': 'Drink from the fountain',
                        'description': 'Risk harm for potential power',
                        'icon': generate_lucide_svg('flask-conical', width=24, height=24),
                        'next_screen': 'penalty'
                    },
                    {
                        'name': 'Walk away',
                        'description': 'Leave the fountain undisturbed',
                        'icon': generate_lucide_svg('footprints', width=24, height=24),
                        'next_screen': None  # Event ends
                    }
                ]
            }
        },
        {
            'id': 'penalty',
            'type': 'damage_band',
            'parameters': {
                'amount': 5,
                'target_count': 2,
                'distribution': 'random'
            },
            'on_complete': 'reward'
        },
        {
            'id': 'reward',
            'type': 'select_buff_type',
            'parameters': {
                'buff_power': 'ultimate',
                'title': 'Cursed Power',
                'allow_skip': False
            }
        }
    ]
}


GOLDEN_STATUE_EVENT = {
    'id': 'golden_statue',
    'visit_rule': 'repeatable',
    'title': 'Golden Statue',
    'description': 'Combine minions into powerful golden versions',
    'screens': [
        {
            'id': 'statue',
            'type': 'statue',
            'parameters': {
                'title': '✨ Golden Statue'
            }
        }
    ]
}


TRAVELING_MERCHANT = {
    'id': 'traveling_merchant',
    'visit_rule': 'repeatable',
    'title': 'Traveling Merchant',
    'description': 'Buy minions with gold',
    'screens': [
        {
            'id': 'shop',
            'type': 'shop',
            'parameters': {
                'title': 'Traveling Merchant'
            }
        }
    ]
}


# ==================== COMBAT CHAIN EVENTS ====================

BANDIT_AMBUSH = {
    'id': 'bandit_ambush',
    'visit_rule': 'repeatable',
    'title': 'Bandit Ambush',
    'description': 'Fight bandits for gold reward',
    'screens': [
        {
            'id': 'combat',
            'type': 'combat',
            'parameters': {
                'difficulty': 'normal',
                'title': '⚔️ Bandit Ambush'
            },
            'on_victory': 'gold_reward',
            'on_defeat': None
        },
        {
            'id': 'gold_reward',
            'type': 'grant_gold',
            'parameters': {
                'amount': 10
            }
        }
    ]
}


ELITE_ENCOUNTER = {
    'id': 'elite_encounter',
    'visit_rule': 'repeatable',
    'title': 'Elite Enemy',
    'description': 'Difficult combat with choice of reward',
    'screens': [
        {
            'id': 'combat',
            'type': 'combat',
            'parameters': {
                'difficulty': 'elite',
                'title': '⚔️ Elite Encounter'
            },
            'on_victory': 'reward_choice',
            'on_defeat': None
        },
        {
            'id': 'reward_choice',
            'type': 'make_choice',
            'parameters': {
                'title': 'Victory Spoils',
                'message': 'Choose your reward',
                'choices': [
                    {
                        'name': 'New Recruit',
                        'description': 'Add a powerful minion',
                        'icon': generate_lucide_svg('user-plus', width=24, height=24),
                        'next_screen': 'minion_reward'
                    },
                    {
                        'name': 'Battle Blessing',
                        'description': 'Strengthen your band',
                        'icon': generate_lucide_svg('zap', width=24, height=24),
                        'next_screen': 'buff_reward'
                    }
                ]
            }
        },
        {
            'id': 'minion_reward',
            'type': 'select_minion',
            'parameters': {
                'count': 3,
                'tier_pool': 'current_tier',
                'allow_skip': False
            }
        },
        {
            'id': 'buff_reward',
            'type': 'select_buff_type',
            'parameters': {
                'buff_power': 'strong',
                'allow_skip': False
            }
        }
    ]
}


# ==================== BASIC GAMEPLAY EVENTS ====================
# These are the core events used in ring configurations

# Minion Events
MINION_EVENT = {
    'id': 'minion_event',
    'visit_rule': 'repeatable',
    'title': 'Recruit Ally',
    'description': 'Choose a minion to join your band',
    'screens': [
        {
            'id': 'select',
            'type': 'select_minion',
            'parameters': {
                'count': 3,
                'tier_pool': 'multi_tier',
                'title': 'Free Minion',
                'message': 'Choose a minion to add to your band',
                'allow_skip': False
            }
        }
    ]
}

# Buff Events (4 power levels)
BUFF_EVENT = {
    'id': 'buff_event',
    'visit_rule': 'repeatable',
    'title': 'Blessing',
    'description': 'Receive a blessing for your band',
    'screens': [
        {
            'id': 'select_buff',
            'type': 'select_buff_type',
            'parameters': {
                'buff_power': 'normal',
                'title': 'Choose Blessing',
                'allow_skip': False
            }
        }
    ]
}


# Combat Events (5 difficulty levels)
COMBAT_EVENT = {
    'id': 'combat_event',
    'visit_rule': 'repeatable',
    'title': 'Combat',
    'description': 'Face an enemy band',
    'screens': [
        {
            'id': 'combat',
            'type': 'combat',
            'parameters': {
                'difficulty': 'normal',
                'title': '⚔️ Combat'
            },
            'on_victory': None,
            'on_defeat': None
        }
    ]
}

COMBAT_EVENT_HARD = {
    'id': 'combat_event_hard',
    'visit_rule': 'repeatable',
    'title': 'Hard Combat',
    'description': 'Face a difficult enemy band',
    'screens': [
        {
            'id': 'combat',
            'type': 'combat',
            'parameters': {
                'difficulty': 'hard',
                'title': '⚔️ Hard Combat'
            },
            'on_victory': None,
            'on_defeat': None
        }
    ]
}

# Shop Event (same as TRAVELING_MERCHANT but with consistent ID)
SHOP_EVENT = {
    'id': 'shop_event',
    'visit_rule': 'repeatable',
    'title': 'Shop',
    'description': 'Buy minions with gold',
    'screens': [
        {
            'id': 'shop',
            'type': 'shop',
            'parameters': {
                'title': 'Tavern'
            }
        }
    ]
}

# Statue Event (same as GOLDEN_STATUE_EVENT but with consistent ID)
STATUE_EVENT = {
    'id': 'statue',
    'visit_rule': 'repeatable',
    'title': 'Golden Statue',
    'description': 'Combine minions into powerful golden versions',
    'screens': [
        {
            'id': 'statue',
            'type': 'statue',
            'parameters': {
                'title': '✨ Golden Statue'
            }
        }
    ]
}

# Zone Portal Event (placeholder for zone transitions)
ZONE_PORTAL_EVENT = {
    'id': 'zone_portal',
    'visit_rule': 'repeatable',
    'title': 'Zone Portal',
    'description': 'Travel to a new zone',
    'screens': [
        {
            'id': 'story',
            'type': 'story',
            'parameters': {
                'title': 'Zone Portal',
                'text': 'A shimmering portal offers passage to distant lands.',
                'icon': 'portal',
                'continue_text': 'Continue'
            },
            'on_continue': None
        }
    ]
}


# ==================== GENERAL EVENT POOL ====================
# Random events that can appear at general_event positions
# Scrap Heap is NOT in this pool - it's forced by the scrap curse

GENERAL_EVENT_POOL = [
    'collapsed_mine',
    'mercenary_camp',
    'vast_kennels',
    'watchtower'
]


# ==================== THE GREAT HUNT (Beast Wildlands) ====================
# Bounty hunting event with boss encounters, feeding beasts, and beast synergies
# REWORKED: One boss per tier, unique boss rewards, simplified bounty system

THE_GREAT_HUNT = {
    'id': 'the_great_hunt',
    'visit_rule': 'repeatable',
    'title': 'The Great Hunt',
    'description': 'Hunt bounties and track prey in the wilds',
    'check_active_boss': True,  # If active_boss exists, force to boss combat
    'screens': [
        {
            'id': 'hunt_choices',
            'type': 'make_choice',
            'parameters': {
                'title': 'The Great Hunt',
                'message': 'The hunting lodge awaits. What will you do?',
                'choices': [
                    # Option 1: Take a Bounty (free) - simplified: double gold next combat
                    {
                        'name': 'Take a Bounty',
                        'tooltip': 'Your next combat awards double gold.',
                        'icon': generate_lucide_svg('crosshair', width=24, height=24),
                        'on_select': 'set_double_gold_bounty',
                        'next_event': None
                    },
                    # Option 2: Take a Boss Bounty (one per tier)
                    {
                        'name': 'Take a Boss Bounty',
                        'tooltip': 'Challenge a powerful boss. Only one boss hunt per tier. Boss damage persists across attempts. Each boss has unique rewards.',
                        'icon': generate_lucide_svg('skull', width=24, height=24),
                        'condition': 'boss_not_defeated_this_tier',
                        'disabled_until_met': True,
                        'on_select': 'start_boss_hunt',
                        'next_event': 'great_hunt_boss_encounter'
                    },
                    # Option 3: Feed Your Pack (sacrifice minion to buff a beast)
                    {
                        'name': 'Feed Your Pack',
                        'tooltip': 'Sacrifice a minion. Add its stats to a Beast in your band.',
                        'icon': generate_lucide_svg('utensils', width=24, height=24),
                        'condition': 'has_beast_and_2_minions',
                        'disabled_until_met': True,
                        'next_event': 'great_hunt_feed_sacrifice'
                    },
                    # Option 4: Call of the Wild (requires 4+ Beasts)
                    {
                        'name': 'Call of the Wild',
                        'tooltip': 'The wilds answer to those who belong. Recruit a random Beast from tier+1 for free.',
                        'icon': generate_lucide_svg('trees', width=24, height=24),
                        'condition': 'beast_count >= 4',
                        'disabled_until_met': True,
                        'on_select': 'recruit_random_beast_tier_plus_1',
                        'next_event': None
                    },
                    # Leave option
                    {
                        'name': 'Leave',
                        'tooltip': 'Return later',
                        'icon': generate_lucide_svg('door-open', width=24, height=24),
                        'next_event': None
                    }
                ]
            }
        }
    ]
}

# === Feed Your Pack - Sacrifice a minion ===
GREAT_HUNT_FEED_SACRIFICE = {
    'id': 'great_hunt_feed_sacrifice',
    'visit_rule': 'repeatable',
    'title': 'Feed Your Pack',
    'screens': [
        {
            'id': 'select_sacrifice',
            'type': 'select_sacrifice_target',
            'parameters': {
                'title': 'Choose Sacrifice',
                'message': 'Select a minion to sacrifice. Its stats will be consumed by a Beast.',
                'on_sacrifice': 'store_feed_sacrifice'
            },
            'on_complete': 'great_hunt_feed_target'
        }
    ]
}

# === Feed Your Pack - Select Beast to receive stats ===
GREAT_HUNT_FEED_TARGET = {
    'id': 'great_hunt_feed_target',
    'visit_rule': 'repeatable',
    'title': 'Feed the Beast',
    'screens': [
        {
            'id': 'select_beast',
            'type': 'select_buff_target',
            'parameters': {
                'title': 'Choose Beast to Feed',
                'message': 'Select a Beast to receive the sacrificed stats.',
                'buff_type': 'feed_sacrifice',
                'tribe_filter': 'Beast',
                'on_select': 'apply_feed_to_beast'
            }
        }
    ]
}

# === Boss Encounter (uses active_boss from event_state) ===
GREAT_HUNT_BOSS_ENCOUNTER = {
    'id': 'great_hunt_boss_encounter',
    'visit_rule': 'repeatable',
    'forced_event': True,
    'title': 'Boss Encounter',
    'description': 'Your quarry awaits',
    'screens': [
        {
            'id': 'boss_combat',
            'type': 'boss_combat',
            'parameters': {
                'title': 'Boss Encounter',
                'message': 'The hunt is on! Defeat the boss to claim your reward.',
                'use_active_boss': True,  # Use event_state['active_boss'] instead of random
                'persistent_damage_key': 'boss_bounty_damage'
            },
            'on_victory_event': 'great_hunt_boss_victory',
            'on_defeat_event': None
        }
    ]
}

# === Boss Victory - Routes to boss-specific reward ===
GREAT_HUNT_BOSS_VICTORY = {
    'id': 'great_hunt_boss_victory',
    'visit_rule': 'repeatable',
    'title': 'Boss Defeated!',
    'route_by_boss': True,  # Routes to boss-specific victory event
    'screens': [
        {
            'id': 'reward',
            'type': 'boss_reward_router',
            'parameters': {
                'title': 'The Hunt is Complete!',
                'on_select': 'clear_active_boss'
            }
        }
    ]
}

# === Boss-Specific Victory Events ===

GREAT_HUNT_VICTORY_DIRE_PACK = {
    'id': 'great_hunt_victory_dire_pack',
    'visit_rule': 'repeatable',
    'title': 'Dire Pack Defeated',
    'screens': [
        {
            'id': 'reward',
            'type': 'make_choice',
            'parameters': {
                'title': 'Dire Pack Reward',
                'choices': [
                    {
                        'name': 'All Minions +2/+2',
                        'tooltip': 'Grant +2/+2 to all minions in your band.',
                        'icon': generate_lucide_svg('sparkles', width=24, height=24),
                        'on_select': 'boss_reward_dire_pack_stats'
                    },
                    {
                        'name': 'One Minion: On Any Death +2/+2',
                        'tooltip': 'Choose a minion to gain "On Any Death: This minion gains +2/+2".',
                        'icon': generate_lucide_svg('skull', width=24, height=24),
                        'next_event': 'great_hunt_reward_dire_pack_keyword'
                    }
                ]
            }
        }
    ]
}

GREAT_HUNT_VICTORY_CONGREGATION = {
    'id': 'great_hunt_victory_congregation',
    'visit_rule': 'repeatable',
    'title': 'Congregation Defeated',
    'screens': [
        {
            'id': 'reward',
            'type': 'make_choice',
            'parameters': {
                'title': 'Congregation Reward',
                'choices': [
                    {
                        'name': 'One Minion: Gain Cult Tribe',
                        'tooltip': 'Choose a minion to become a Cult minion.',
                        'icon': generate_lucide_svg('users', width=24, height=24),
                        'next_event': 'great_hunt_reward_congregation_tribe'
                    },
                    {
                        'name': 'One Minion: Gain Ignoble',
                        'tooltip': 'Choose a minion to gain Ignoble (cannot take combat damage).',
                        'icon': generate_lucide_svg('shield', width=24, height=24),
                        'next_event': 'great_hunt_reward_congregation_ignoble'
                    }
                ]
            }
        }
    ]
}

GREAT_HUNT_VICTORY_CHAINED_BEAST = {
    'id': 'great_hunt_victory_chained_beast',
    'visit_rule': 'repeatable',
    'title': 'Chained Beast Defeated',
    'screens': [
        {
            'id': 'reward',
            'type': 'make_choice',
            'parameters': {
                'title': 'Chained Beast Reward',
                'choices': [
                    {
                        'name': 'One Minion: +8/+8 and Leap 2',
                        'tooltip': 'Choose a minion to gain +8/+8 and Leap 2.',
                        'icon': generate_lucide_svg('zap', width=24, height=24),
                        'next_event': 'great_hunt_reward_chained_stats'
                    },
                    {
                        'name': 'One Minion: Ethereal, No Cast/Retaliate',
                        'tooltip': 'Choose a minion to gain Ethereal [Left], Can\'t Cast, Can\'t Retaliate.',
                        'icon': generate_lucide_svg('ghost', width=24, height=24),
                        'next_event': 'great_hunt_reward_chained_ethereal'
                    }
                ]
            }
        }
    ]
}

GREAT_HUNT_VICTORY_BEHEMOTH = {
    'id': 'great_hunt_victory_behemoth',
    'visit_rule': 'repeatable',
    'title': 'Behemoth Defeated',
    'screens': [
        {
            'id': 'reward',
            'type': 'make_choice',
            'parameters': {
                'title': 'Behemoth Reward',
                'choices': [
                    {
                        'name': 'One Minion: Guard and +5/+12',
                        'tooltip': 'Choose a minion to gain Guard and +5/+12.',
                        'icon': generate_lucide_svg('shield', width=24, height=24),
                        'next_event': 'great_hunt_reward_behemoth_tank'
                    },
                    {
                        'name': 'All Minions +0/+4',
                        'tooltip': 'All minions gain +0/+4 health.',
                        'icon': generate_lucide_svg('heart', width=24, height=24),
                        'on_select': 'boss_reward_behemoth_all'
                    }
                ]
            }
        }
    ]
}

GREAT_HUNT_VICTORY_VENOMSPAWN = {
    'id': 'great_hunt_victory_venomspawn',
    'visit_rule': 'repeatable',
    'title': 'Venomspawn Defeated',
    'screens': [
        {
            'id': 'reward',
            'type': 'make_choice',
            'parameters': {
                'title': 'Venomspawn Reward',
                'choices': [
                    {
                        'name': 'All Minions +6/+0',
                        'tooltip': 'All minions gain +6 attack.',
                        'icon': generate_lucide_svg('swords', width=24, height=24),
                        'on_select': 'boss_reward_venomspawn_attack'
                    },
                    {
                        'name': 'One Minion: Cast 2 damage to enemies',
                        'tooltip': 'Choose a minion to gain "Cast: Deal 2 damage to all enemy minions".',
                        'icon': generate_lucide_svg('flame', width=24, height=24),
                        'next_event': 'great_hunt_reward_venomspawn_cast'
                    }
                ]
            }
        }
    ]
}

GREAT_HUNT_VICTORY_GREATER_POSSESSED = {
    'id': 'great_hunt_victory_greater_possessed',
    'visit_rule': 'repeatable',
    'title': 'Greater Possessed Defeated',
    'screens': [
        {
            'id': 'reward',
            'type': 'make_choice',
            'parameters': {
                'title': 'Greater Possessed Reward',
                'choices': [
                    {
                        'name': 'Tier x10 Gold',
                        'tooltip': 'Gain tier x 10 gold.',
                        'icon': generate_lucide_svg('coins', width=24, height=24),
                        'on_select': 'boss_reward_possessed_gold'
                    },
                    {
                        'name': 'One Minion: Death Toll Summon Possessed',
                        'tooltip': 'Choose a minion to gain "Death Toll: Summon a Possessed".',
                        'icon': generate_lucide_svg('skull', width=24, height=24),
                        'next_event': 'great_hunt_reward_possessed_deathtoll'
                    }
                ]
            }
        }
    ]
}

# === Boss Reward Sub-Events (Target Selection) ===

GREAT_HUNT_REWARD_DIRE_PACK_KEYWORD = {
    'id': 'great_hunt_reward_dire_pack_keyword',
    'visit_rule': 'repeatable',
    'title': 'Pack Bond',
    'screens': [
        {
            'id': 'select_target',
            'type': 'select_buff_target',
            'parameters': {
                'title': 'Pack Bond',
                'message': 'Choose a minion to gain "On Any Death: +2/+2"',
                'buff_type': 'boss_dire_pack_keyword',
                'on_select': 'boss_reward_dire_pack_keyword'
            }
        }
    ]
}

GREAT_HUNT_REWARD_CONGREGATION_TRIBE = {
    'id': 'great_hunt_reward_congregation_tribe',
    'visit_rule': 'repeatable',
    'title': 'Convert',
    'screens': [
        {
            'id': 'select_target',
            'type': 'select_buff_target',
            'parameters': {
                'title': 'Convert',
                'message': 'Choose a minion to become a Cult minion',
                'buff_type': 'boss_congregation_tribe',
                'on_select': 'boss_reward_congregation_tribe'
            }
        }
    ]
}

GREAT_HUNT_REWARD_CONGREGATION_IGNOBLE = {
    'id': 'great_hunt_reward_congregation_ignoble',
    'visit_rule': 'repeatable',
    'title': 'Ignoble',
    'screens': [
        {
            'id': 'select_target',
            'type': 'select_buff_target',
            'parameters': {
                'title': 'Ignoble',
                'message': 'Choose a minion to gain Ignoble',
                'buff_type': 'boss_congregation_ignoble',
                'on_select': 'boss_reward_congregation_ignoble'
            }
        }
    ]
}

GREAT_HUNT_REWARD_CHAINED_STATS = {
    'id': 'great_hunt_reward_chained_stats',
    'visit_rule': 'repeatable',
    'title': 'Unbound',
    'screens': [
        {
            'id': 'select_target',
            'type': 'select_buff_target',
            'parameters': {
                'title': 'Unbound',
                'message': 'Choose a minion to gain +8/+8 and Leap 2',
                'buff_type': 'boss_chained_beast',
                'on_select': 'boss_reward_chained_stats'
            }
        }
    ]
}

GREAT_HUNT_REWARD_CHAINED_ETHEREAL = {
    'id': 'great_hunt_reward_chained_ethereal',
    'visit_rule': 'repeatable',
    'title': 'Cursed Freedom',
    'screens': [
        {
            'id': 'select_target',
            'type': 'select_buff_target',
            'parameters': {
                'title': 'Cursed Freedom',
                'message': 'Choose a minion to gain Ethereal [Left], Can\'t Cast, Can\'t Retaliate',
                'buff_type': 'boss_chained_ethereal',
                'on_select': 'boss_reward_chained_ethereal'
            }
        }
    ]
}

GREAT_HUNT_REWARD_BEHEMOTH_TANK = {
    'id': 'great_hunt_reward_behemoth_tank',
    'visit_rule': 'repeatable',
    'title': 'Thick Hide',
    'screens': [
        {
            'id': 'select_target',
            'type': 'select_buff_target',
            'parameters': {
                'title': 'Thick Hide',
                'message': 'Choose a minion to gain Guard and +5/+12',
                'buff_type': 'boss_behemoth',
                'on_select': 'boss_reward_behemoth_tank'
            }
        }
    ]
}

GREAT_HUNT_REWARD_VENOMSPAWN_CAST = {
    'id': 'great_hunt_reward_venomspawn_cast',
    'visit_rule': 'repeatable',
    'title': 'Venom Spit',
    'screens': [
        {
            'id': 'select_target',
            'type': 'select_buff_target',
            'parameters': {
                'title': 'Venom Spit',
                'message': 'Choose a minion to gain "Cast: Deal 2 damage to all enemies"',
                'buff_type': 'boss_venomspawn_cast',
                'on_select': 'boss_reward_venomspawn_cast'
            }
        }
    ]
}

GREAT_HUNT_REWARD_POSSESSED_DEATHTOLL = {
    'id': 'great_hunt_reward_possessed_deathtoll',
    'visit_rule': 'repeatable',
    'title': 'Dark Pact',
    'screens': [
        {
            'id': 'select_target',
            'type': 'select_buff_target',
            'parameters': {
                'title': 'Dark Pact',
                'message': 'Choose a minion to gain "Death Toll: Summon a Possessed"',
                'buff_type': 'boss_possessed_deathtoll',
                'on_select': 'boss_reward_possessed_deathtoll'
            }
        }
    ]
}


# ==================== EVENT REGISTRY ====================
# Organized by type for easy lookup

# ==================== BELL TOWER EVENT ====================

# Bell Tower Sub-Events (Modular Components)

BELL_TOWER_BLESSING = {
    'id': 'bell_tower_blessing',
    'visit_rule': 'repeatable',
    'title': 'Bell Tower Blessing',
    'description': 'Receive the Ring blessing from the bell tower',
    'screens': [
        {
            'id': 'blessing',
            'type': 'select_buff_target',
            'parameters': {
                'buff_type': 'ring',
                'ring_value': 'tier',
                'title': 'Bell Tower Blessing'
            }
        }
    ]
}

BELL_TOWER_COMBAT = {
    'id': 'bell_tower_combat',
    'visit_rule': 'repeatable',
    'title': 'Tower Guardians',
    'description': 'Fight the guardians of the bell tower',
    'screens': [
        {
            'id': 'combat',
            'type': 'combat',
            'parameters': {
                'difficulty': 'normal',
                'pool_filter': 'Human',  # Only Human tribe minions
                'disable_gold_reward': True,  # No gold from this fight
                'title': '⚔️ Tower Guardians'
            },
            'on_victory_event': 'bell_tower_blessing',  # Chain to blessing event after combat victory
            'on_defeat': None
        }
    ]
}

BELL_TOWER_QUASIMODO = {
    'id': 'bell_tower_quasimodo',
    'visit_rule': 'repeatable',
    'title': 'The Bell Ringer',
    'description': 'Quasimodo joins your cause',
    'screens': [
        {
            'id': 'quasimodo',
            'type': 'grant_minion',
            'parameters': {
                'minion_name': 'Quasimodo',
                'tier': 5,  # He's a legendary tier 5
                'title': 'The Bell Ringer Joins You',
                'message': 'Quasimodo, the devoted bell ringer, agrees to join your cause!'
            }
        }
    ]
}

# Bell Tower Main Event (Choice Screen)

BELL_TOWER = {
    'id': 'bell_tower',
    'visit_rule': 'repeatable',  # Can visit multiple times to ring more bells
    'title': 'Bell Tower',
    'description': 'An ancient bell tower with a mysterious power',
    'state_defaults': {
        'bells_rung': 0,
    },
    'screens': [
        {
            'id': 'choice',
            'type': 'make_choice',
            'parameters': {
                'title': 'Bell Tower',
                'message': 'You approach an ancient bell tower. The massive bell gleams in the light.',
                'choices': [
                    {
                        'name': 'Pay to Ring the Bell',
                        'description': 'Pay gold to ring the bell and receive a blessing',
                        'tooltip': 'Pay ({gold_cost}) gold to ring the bell and give a minion Ring ({tier}). After the bell has been Rung 4 times you can get Quasimodo.',
                        'icon': generate_lucide_svg('piggy-bank', width=24, height=24),
                        'gold_cost': 'tier * 3',  # Dynamic cost formula
                        'on_select': 'increment_bells_rung',  # Increment run.event_state['bells_rung']
                        'next_event': 'bell_tower_blessing'
                    },
                    {
                        'name': 'Break In',
                        'description': 'Force your way in and face the tower\'s guardians',
                        'tooltip': 'Fight a combat 1 tier higher. If you win you don\'t get gold but get to ring the bell and give a minion Ring ({tier}). After the bell has been Rung 4 times you can get Quasimodo.',
                        'icon': generate_lucide_svg('swords', width=24, height=24),
                        'next_event': 'bell_tower_combat'
                    },
                    {
                        'name': 'Seek Quasimodo',
                        'description': 'The bell ringer may join those who have shown true devotion',
                        'tooltip': 'If you\'ve Rung the bell 4+ times you can get Quasimodo for free.',
                        'icon': generate_lucide_svg('user-plus', width=24, height=24),
                        'condition': 'bells_rung >= 4',  # Only available after 4 bell rings
                        'disabled_until_met': True,  # Show but greyed out
                        'next_event': 'bell_tower_quasimodo',
                        'mark_event_complete': True  # Remove event from pool after this
                    },
                    {
                        'name': 'Leave',
                        'description': 'Walk away from the bell tower',
                        'tooltip': 'Leave without doing anything. You can return to the Bell Tower later.',
                        'icon': generate_lucide_svg('footprints', width=24, height=24),
                        'next_event': None
                    }
                ]
            }
        }
    ]
}


# ==================== CROSSROADS EVENTS (DEV TESTING) ====================
# These events are for dev testing and can be rolled at crossroads

# -------------------- MERCENARY CAMP --------------------

MERCENARY_CAMP_HIRE_GUARD = {
    'id': 'mercenary_camp_hire_guard',
    'visit_rule': 'repeatable',
    'title': 'Hire Guard',
    'description': 'A mercenary teaches your minion defensive tactics',
    'screens': [
        {
            'id': 'select_target',
            'type': 'select_buff_target',
            'parameters': {
                'buff_type': 'keyword_guard',
                'title': 'Hire Guard',
                'message': 'Choose a minion to gain Guard'
            }
        }
    ]
}

MERCENARY_CAMP_DUEL = {
    'id': 'mercenary_camp_duel',
    'visit_rule': 'repeatable',
    'title': 'Duel',
    'description': 'Your champion faces a mercenary in single combat',
    'screens': [
        {
            'id': 'select_champion',
            'type': 'select_buff_target',
            'parameters': {
                'buff_type': 'duel',
                'title': 'Choose Your Champion',
                'message': 'Select a minion to fight in the duel. Victory: +3/+3 per tier.'
            }
        }
    ]
}

MERCENARY_CAMP_DUEL_VICTORY = {
    'id': 'mercenary_camp_duel_victory',
    'visit_rule': 'repeatable',
    'title': 'Duel Victory',
    'description': 'Your champion proved their worth',
    'screens': [
        {
            'id': 'victory_buff',
            'type': 'duel_victory',
            'parameters': {
                'title': 'Victory!',
                'buff_per_tier': 3  # +3/+3 per tier to the champion
            }
        }
    ]
}

MERCENARY_CAMP_TAKEOVER = {
    'id': 'mercenary_camp_takeover',
    'visit_rule': 'repeatable',
    'title': 'Hostile Takeover',
    'description': 'Storm the mercenary camp',
    'screens': [
        {
            'id': 'combat',
            'type': 'combat',
            'parameters': {
                'difficulty': 'hard',
                'title': '⚔️ Hostile Takeover',
                'disable_gold_reward': True
            },
            'on_victory_event': 'mercenary_camp_takeover_victory',
            'on_defeat': None
        }
    ]
}

MERCENARY_CAMP_TAKEOVER_VICTORY = {
    'id': 'mercenary_camp_takeover_victory',
    'visit_rule': 'repeatable',
    'title': 'Camp Conquered',
    'description': 'A warlord joins your cause',
    'screens': [
        {
            'id': 'recruit',
            'type': 'select_minion',
            'parameters': {
                'minion_pool': ['Quartermaster', 'Warlord'],
                'title': 'A Warlord Joins',
                'message': 'The mercenary warlord swears loyalty to your cause!',
                'allow_skip': False
            }
        }
    ]
}

MERCENARY_CAMP = {
    'id': 'mercenary_camp',
    'visit_rule': 'repeatable',
    'title': 'Mercenary Camp',
    'description': 'A camp of sellswords offers their services',
    'screens': [
        {
            'id': 'choice',
            'type': 'make_choice',
            'parameters': {
                'title': 'Mercenary Camp',
                'message': 'A camp of sellswords offers their services... for a price.',
                'choices': [
                    {
                        'name': 'Hire Guard',
                        'description': 'Pay a mercenary to train one of your minions',
                        'tooltip': 'Pay {gold_cost} gold to give a minion the Guard keyword.',
                        'icon': generate_lucide_svg('shield', width=24, height=24),
                        'gold_cost': 'tier * 6',
                        'next_event': 'mercenary_camp_hire_guard'
                    },
                    {
                        'name': 'Enter a Duel',
                        'description': 'Your champion fights a mercenary one-on-one',
                        'tooltip': 'Choose 1 minion to fight alone against a scaled enemy. Win: That minion gains +{tier * 3}/+{tier * 3}.',
                        'icon': generate_lucide_svg('swords', width=24, height=24),
                        'next_event': 'mercenary_camp_duel'
                    },
                    {
                        'name': 'Hostile Takeover',
                        'description': 'Storm the camp and claim it for yourself',
                        'tooltip': 'Fight hard combat. Win: Recruit a Quartermaster or Warlord.',
                        'icon': generate_lucide_svg('flame', width=24, height=24),
                        'next_event': 'mercenary_camp_takeover'
                    },
                    {
                        'name': 'Leave',
                        'description': 'Walk away from the camp',
                        'tooltip': 'Leave without doing anything.',
                        'icon': generate_lucide_svg('footprints', width=24, height=24),
                        'next_event': None
                    },
                    {
                        'name': 'Joint Alliance',
                        'description': 'Your diverse band impresses the mercenaries',
                        'tooltip': 'If you have 4+ different tribes, all minions gain +{tier}/+{tier}.',
                        'icon': generate_lucide_svg('users', width=24, height=24),
                        'condition': 'unique_tribes >= 4',
                        'disabled_until_met': True,
                        'on_select': 'buff_all_per_tier',
                        'next_event': None
                    }
                ]
            }
        }
    ]
}

# -------------------- COLLAPSED MINE --------------------

COLLAPSED_MINE = {
    'id': 'collapsed_mine',
    'visit_rule': 'repeatable',
    'title': 'Collapsed Mine',
    'description': 'A shortcut through an old gold mine begins to collapse',
    'screens': [
        {
            'id': 'choice',
            'type': 'make_choice',
            'parameters': {
                'title': 'Collapsed Mine',
                'message': 'Having taken a shortcut through a gold mine, it starts to collapse as your soldiers are gathering gold.',
                'choices': [
                    {
                        'name': 'Go Slow',
                        'description': 'Take your time and gather more gold',
                        'tooltip': 'Gain ({gold_reward}) gold. Costs 1 extra Step.',
                        'icon': generate_lucide_svg('snail', width=24, height=24),
                        'gold_reward': 'tier * 4',
                        'on_select': 'collapsed_mine_slow',
                        'next_event': None
                    },
                    {
                        'name': 'Go Fast',
                        'description': 'Rush through with whatever you can grab',
                        'tooltip': 'Gain ({gold_reward}) gold.',
                        'icon': generate_lucide_svg('zap', width=24, height=24),
                        'gold_reward': 'tier * 3',
                        'on_select': 'collapsed_mine_fast',
                        'next_event': None
                    },
                    {
                        'name': 'Leave',
                        'description': 'Turn back without entering the mine',
                        'tooltip': 'Leave without gaining anything.',
                        'icon': generate_lucide_svg('footprints', width=24, height=24),
                        'next_event': None
                    },
                    {
                        'name': 'Go Faster',
                        'description': 'Your fast minions lead the way',
                        'tooltip': 'Gain ({gold_reward}) gold. Requires a minion with Fast.',
                        'icon': generate_lucide_svg('rabbit', width=24, height=24),
                        'gold_reward': 'tier * 5',
                        'condition': 'has_keyword_fast',
                        'disabled_until_met': True,
                        'on_select': 'collapsed_mine_fastest',
                        'next_event': None
                    }
                ]
            }
        }
    ]
}

# -------------------- VAST KENNELS --------------------

KENNELS_BUY_HOUND = {
    'id': 'kennels_buy_hound',
    'visit_rule': 'repeatable',
    'title': 'Buy Hound',
    'description': 'A loyal hound joins your band',
    'screens': [
        {
            'id': 'grant',
            'type': 'grant_minion',
            'parameters': {
                'minion_name': 'Hound',
                'tier': 1,
                'title': 'New Companion',
                'message': 'A loyal hound joins your band!'
            }
        }
    ]
}

KENNELS_BUY_CAT = {
    'id': 'kennels_buy_cat',
    'visit_rule': 'repeatable',
    'title': 'Buy Cat',
    'description': 'A cunning cat joins your band',
    'screens': [
        {
            'id': 'grant',
            'type': 'grant_minion',
            'parameters': {
                'minion_name': 'Cat',
                'tier': 1,
                'title': 'New Companion',
                'message': 'A cunning cat joins your band!'
            }
        }
    ]
}

VAST_KENNELS = {
    'id': 'vast_kennels',
    'visit_rule': 'repeatable',
    'title': 'Vast Kennels',
    'description': 'Rows of cages house various creatures for sale',
    'screens': [
        {
            'id': 'choice',
            'type': 'make_choice',
            'parameters': {
                'title': 'Vast Kennels',
                'message': 'Rows of cages house various creatures for sale.',
                'choices': [
                    {
                        'name': 'Buy a Hound',
                        'description': 'A loyal hunting dog',
                        'tooltip': 'Pay 2 gold to gain a Hound (1/2 Beast with Poke).',
                        'icon': generate_lucide_svg('dog', width=24, height=24),
                        'gold_cost': '2',
                        'next_event': 'kennels_buy_hound'
                    },
                    {
                        'name': 'Buy a Cat',
                        'description': 'A cunning feline',
                        'tooltip': 'Pay 2 gold to gain a Cat (1/1 Beast with Death Toll).',
                        'icon': generate_lucide_svg('cat', width=24, height=24),
                        'gold_cost': '2',
                        'next_event': 'kennels_buy_cat'
                    },
                    {
                        'name': 'Buy a Treat',
                        'description': 'Premium food for your beasts',
                        'tooltip': 'Pay ({gold_cost}) gold to give all Beasts +{tier * 2} attack.',
                        'icon': generate_lucide_svg('beef', width=24, height=24),
                        'gold_cost': 'tier * 3',
                        'on_select': 'buff_beasts_attack',
                        'next_event': None
                    },
                    {
                        'name': 'Leave',
                        'description': 'Walk away from the kennels',
                        'tooltip': 'Leave without buying anything.',
                        'icon': generate_lucide_svg('footprints', width=24, height=24),
                        'next_event': None
                    },
                    {
                        'name': 'Pack Discount',
                        'description': 'The kennel master offers a bulk deal',
                        'tooltip': 'If you have 3+ Beasts, all purchases cost 1 gold instead.',
                        'icon': generate_lucide_svg('percent', width=24, height=24),
                        'condition': 'beast_count >= 3',
                        'disabled_until_met': True,
                        'on_select': 'enable_pack_discount',
                        'next_event': None
                    }
                ]
            }
        }
    ]
}

# -------------------- WATCHTOWER --------------------

WATCHTOWER_STORM_VICTORY = {
    'id': 'watchtower_storm_victory',
    'visit_rule': 'repeatable',
    'title': 'Tower Captured',
    'description': 'You control the watchtower',
    'screens': [
        {
            'id': 'story',
            'type': 'story',
            'parameters': {
                'title': 'Tower Captured!',
                'text': 'You now control the watchtower. The next 2 hard combats are instead normal combats.',
                'icon': 'castle',
                'on_select': 'watchtower_storm_effect'
            }
        }
    ]
}

WATCHTOWER_AID = {
    'id': 'watchtower_aid',
    'visit_rule': 'repeatable',
    'title': 'Request Aid',
    'description': 'The guards send reinforcements',
    'screens': [
        {
            'id': 'select',
            'type': 'select_minion',
            'parameters': {
                'count': 1,
                'tribe_filter': 'Human',
                'title': 'Reinforcements',
                'message': 'A human soldier joins your cause!',
                'allow_skip': False
            }
        }
    ]
}

WATCHTOWER = {
    'id': 'watchtower',
    'visit_rule': 'repeatable',
    'title': 'Watchtower',
    'description': 'A strategic vantage point overlooking the region',
    'screens': [
        {
            'id': 'choice',
            'type': 'make_choice',
            'parameters': {
                'title': 'Watchtower',
                'message': 'A strategic vantage point overlooking the region.',
                'choices': [
                    {
                        'name': 'Pay for Help',
                        'description': 'Bribe the guards for future assistance',
                        'tooltip': 'Pay ({gold_cost}) gold. Next general event: special options are unlocked even without meeting conditions.',
                        'icon': generate_lucide_svg('coins', width=24, height=24),
                        'gold_cost': 'tier * 6',
                        'on_select': 'unlock_next_special_options',
                        'next_event': None
                    },
                    {
                        'name': 'Storm Tower',
                        'description': 'Take the tower by force',
                        'tooltip': 'Fight a hard combat. Win: the next 2 hard combats are instead normal combats.',
                        'icon': generate_lucide_svg('swords', width=24, height=24),
                        'next_event': 'watchtower_storm'
                    },
                    {
                        'name': 'Sneak Past',
                        'description': 'Slip by unnoticed',
                        'tooltip': 'Gain 1 step.',
                        'icon': generate_lucide_svg('eye-off', width=24, height=24),
                        'on_select': 'gain_step',
                        'next_event': None
                    },
                    {
                        'name': 'Request Aid',
                        'description': 'Ask for reinforcements',
                        'tooltip': 'Pay ({gold_cost}) gold to gain a random Tier {tier} Human minion.',
                        'icon': generate_lucide_svg('hand-helping', width=24, height=24),
                        'gold_cost': 'tier * 3',
                        'next_event': 'watchtower_aid'
                    },
                    {
                        'name': 'Leave',
                        'description': 'Walk away from the tower',
                        'tooltip': 'Leave without doing anything.',
                        'icon': generate_lucide_svg('footprints', width=24, height=24),
                        'next_event': None
                    },
                    {
                        'name': 'Infiltrate',
                        'description': 'Your hidden minion takes the tower quietly',
                        'tooltip': 'If you have a minion with Hide: Storm the tower without fighting.',
                        'icon': generate_lucide_svg('ghost', width=24, height=24),
                        'condition': 'has_keyword_hide',
                        'disabled_until_met': True,
                        'on_select': 'watchtower_storm_effect',
                        'next_event': None
                    }
                ]
            }
        }
    ]
}

WATCHTOWER_STORM = {
    'id': 'watchtower_storm',
    'visit_rule': 'repeatable',
    'title': 'Storm the Tower',
    'description': 'Fight for control of the watchtower',
    'screens': [
        {
            'id': 'combat',
            'type': 'combat',
            'parameters': {
                'difficulty': 'hard',
                'title': '⚔️ Storm the Tower',
                'disable_gold_reward': True
            },
            'on_victory_event': 'watchtower_storm_victory'
        }
    ]
}

# ==================== FEY ZONE EVENTS ====================

# -------------------- IVORY TOWER --------------------

IVORY_TOWER = {
    'id': 'ivory_tower',
    'visit_rule': 'repeatable',  # Can visit multiple times to weaken the seal
    'title': 'Ivory Tower',
    'description': 'A grand sealed tower radiates imposing power',
    'state_defaults': {
        'ivory_tower_seal': 4,
    },
    'screens': [
        {
            'id': 'choice',
            'type': 'make_choice',
            'parameters': {
                'title': 'Ivory Tower',
                'message': 'A grand tower looms in front of you, sealed with ancient magic. Yet its power is imposing.',
                'choices': [
                    {
                        'name': 'Sacrifice to weaken the seal',
                        'description': 'Remove 1 friendly minion',
                        'tooltip': 'Remove 1 friendly minion from your band. The seal ({ivory_tower_seal}) weakens by 1. Removed minions don\'t trigger effects.',
                        'icon': generate_lucide_svg('skull', width=24, height=24),
                        'condition': 'band_size >= 1',
                        'on_select': 'ivory_tower_sacrifice_minion',
                        'next_event': 'ivory_tower_sacrifice'
                    },
                    {
                        'name': 'Use blood to weaken the seal',
                        'description': 'Take 7 damage',
                        'tooltip': 'Take 7 damage (or pay 7 gold with Lichdom). Seal ({ivory_tower_seal}) drops by 1.',
                        'icon': generate_lucide_svg('heart-crack', width=24, height=24),
                        'health_cost': 7,  # Static health cost (respects Lichdom)
                        'on_select': 'ivory_tower_take_damage',
                        'next_event': 'ivory_tower'  # Chain back to show updated seal
                    },
                    {
                        'name': 'Wait the Seal',
                        'description': 'Wait 2 extra steps',
                        'tooltip': 'Wait 2 extra steps. Seal ({ivory_tower_seal}) drops by 1.',
                        'icon': generate_lucide_svg('hourglass', width=24, height=24),
                        'on_select': 'ivory_tower_lose_steps',
                        'next_event': 'ivory_tower'  # Chain back to show updated seal
                    },
                    {
                        'name': 'Leave',
                        'description': 'Walk away from the tower',
                        'tooltip': 'Leave without doing anything.',
                        'icon': generate_lucide_svg('footprints', width=24, height=24),
                        'next_event': None
                    },
                    {
                        'name': 'Climb the Tower',
                        'description': 'The seal is broken! Claim the tower\'s power',
                        'tooltip': 'Gain 1 extra band slot permanently. This event can\'t be returned to.',
                        'icon': generate_lucide_svg('castle', width=24, height=24),
                        'condition': 'ivory_tower_seal <= 0',
                        'disabled_until_met': True,
                        'on_select': 'ivory_tower_gain_slot',
                        'mark_event_complete': True,
                        'next_event': None
                    }
                ]
            }
        }
    ]
}

IVORY_TOWER_SACRIFICE = {
    'id': 'ivory_tower_sacrifice',
    'visit_rule': 'repeatable',
    'title': 'Sacrifice to the Seal',
    'description': 'Choose a minion to sacrifice',
    'screens': [
        {
            'id': 'select',
            'type': 'select_sacrifice_target',
            'parameters': {
                'title': 'Sacrifice to the Seal',
                'message': 'Choose a minion to sacrifice. They will be removed from your band.',
                'on_sacrifice': 'ivory_tower_decrease_seal',
                'return_to_event': 'ivory_tower'  # Chain back after sacrifice
            }
        }
    ]
}

# ==================== CONSTRUCT ZONE EVENTS ====================

# -------------------- GRAND CITY --------------------

GRAND_CITY = {
    'id': 'grand_city',
    'visit_rule': 'repeatable',
    'title': 'Grand City',
    'description': 'A sprawling mechanical metropolis offers powerful boons',
    'screens': [
        {
            'id': 'choice',
            'type': 'make_choice',
            'parameters': {
                'title': 'Grand City',
                'message': 'The gears and cogs of this vast mechanical city offer powerful boons... for a price.',
                'choices': [
                    {
                        'name': 'Portal Transit',
                        'description': 'Reduce your next tier cost',
                        'tooltip': 'The next tier costs 3 less. Gain Scrap Curse (3).',
                        'icon': generate_lucide_svg('zap', width=24, height=24),
                        'on_select': 'grand_city_portal',
                        'next_event': None
                    },
                    {
                        'name': 'Upgrade Hero Power',
                        'description': 'Enhance your hero\'s abilities',
                        'tooltip': 'Upgrade your hero power permanently. Gain Scrap Curse (3).',
                        'icon': generate_lucide_svg('crown', width=24, height=24),
                        'on_select': 'grand_city_upgrade_hero',
                        'next_event': None
                    },
                    {
                        'name': 'Golden Forge',
                        'description': 'Transform a minion into a golden version',
                        'tooltip': 'Make one of your minions golden. Gain Scrap Curse (3).',
                        'icon': generate_lucide_svg('sparkles', width=24, height=24),
                        'on_select': 'grand_city_make_golden',
                        'next_event': 'grand_city_golden_forge'
                    },
                    {
                        'name': 'Leave',
                        'description': 'Walk away from the city',
                        'tooltip': 'Leave without doing anything.',
                        'icon': generate_lucide_svg('footprints', width=24, height=24),
                        'next_event': None
                    }
                ]
            }
        }
    ]
}

GRAND_CITY_GOLDEN_FORGE = {
    'id': 'grand_city_golden_forge',
    'visit_rule': 'repeatable',
    'title': 'Golden Forge',
    'description': 'Choose a minion to make golden',
    'screens': [
        {
            'id': 'select',
            'type': 'select_golden_target',
            'parameters': {
                'title': 'Golden Forge',
                'message': 'Choose a minion to transform into a golden version.'
            }
        }
    ]
}

# -------------------- SCRAP HEAP --------------------

SCRAP_HEAP = {
    'id': 'scrap_heap',
    'visit_rule': 'repeatable',
    'title': 'Scrap Heap',
    'description': 'A toxic wasteland of discarded machinery - you must deal with the curse',
    'forced_event': True,  # Cannot leave without choosing
    'screens': [
        {
            'id': 'choice',
            'type': 'make_choice',
            'parameters': {
                'title': 'Scrap Heap',
                'message': 'The curse has led you to this toxic wasteland. You must deal with it.',
                'choices': [
                    {
                        'name': 'Suffer Waste',
                        'description': 'Take 5 damage',
                        'tooltip': 'Take 5 damage (or pay 5 gold with Lichdom). Removes scrap curse.',
                        'icon': generate_lucide_svg('heart-crack', width=24, height=24),
                        'health_cost': 5,  # Static health cost (respects Lichdom)
                        'on_select': 'scrap_heap_suffer_waste',
                        'next_event': None
                    },
                    {
                        'name': 'Brave the Smog',
                        'description': 'Your minions suffer stat drain',
                        'tooltip': 'All minions take -{tier}/-{tier} in stat drain. Removes scrap curse.',
                        'icon': generate_lucide_svg('cloud', width=24, height=24),
                        'on_select': 'scrap_heap_brave_smog',
                        'next_event': None
                    },
                    {
                        'name': 'Suffer Through',
                        'description': 'Endure the curse a little longer',
                        'tooltip': 'Decrease scrap curse by 1. When at 0 remove it.',
                        'icon': generate_lucide_svg('clock', width=24, height=24),
                        'on_select': 'scrap_heap_suffer_through',
                        'next_event': None
                    },
                    {
                        'name': 'Blind Luck',
                        'description': 'A fortunate discovery',
                        'tooltip': 'Removes the curse completely. Cannot be chosen normally.',
                        'icon': generate_lucide_svg('dice-5', width=24, height=24),
                        'condition': 'scrap_heap_blind_luck_available',
                        'disabled_until_met': True,
                        'on_select': 'scrap_heap_blind_luck',
                        'next_event': None
                    }
                ]
            }
        }
    ]
}

# ==================== CULT ZONE EVENTS ====================

# -------------------- THE RED GATE --------------------

RED_GATE_ABANDON_STRENGTH = {
    'id': 'red_gate_abandon_strength',
    'visit_rule': 'repeatable',
    'title': 'Abandon Strength',
    'description': 'Strip away a minion\'s attack power',
    'screens': [
        {
            'id': 'select',
            'type': 'select_minion_and_number',
            'parameters': {
                'stat': 'attack',
                'title': 'Abandon Strength',
                'message': 'Choose a minion to reduce attack.',
                'min_value': 0  # Can reduce to 0
            }
        }
    ]
}

RED_GATE_ABANDON_VIGOR = {
    'id': 'red_gate_abandon_vigor',
    'visit_rule': 'repeatable',
    'title': 'Abandon Vigor',
    'description': 'Strip away a minion\'s health',
    'screens': [
        {
            'id': 'select',
            'type': 'select_minion_and_number',
            'parameters': {
                'stat': 'health',
                'title': 'Abandon Vigor',
                'message': 'Choose a minion to reduce health. Cannot reduce below 1.',
                'min_value': 1  # Cannot reduce below 1
            }
        }
    ]
}

RED_GATE_ABANDON_SKILL = {
    'id': 'red_gate_abandon_skill',
    'visit_rule': 'repeatable',
    'title': 'Abandon Skill',
    'description': 'Strip away a minion\'s keywords',
    'screens': [
        {
            'id': 'select',
            'type': 'select_minion_and_choice',
            'parameters': {
                'choice_source': 'keywords',
                'all_or_nothing': True,  # Only show "Remove All" or "Leave"
                'title': 'Abandon Skill',
                'message': 'Choose a minion to remove ALL keywords from.'
            }
        }
    ]
}

RED_GATE_ABANDON_ALLEGIANCE = {
    'id': 'red_gate_abandon_allegiance',
    'visit_rule': 'repeatable',
    'title': 'Abandon Allegiance',
    'description': 'Strip away a minion\'s types',
    'screens': [
        {
            'id': 'select',
            'type': 'select_minion_and_choice',
            'parameters': {
                'choice_source': 'types',
                'all_or_nothing': True,  # Only show "Remove All" or "Leave"
                'title': 'Abandon Allegiance',
                'message': 'Choose a minion to remove ALL types from.'
            }
        }
    ]
}

THE_RED_GATE = {
    'id': 'the_red_gate',
    'visit_rule': 'repeatable',
    'title': 'The Red Gate',
    'description': 'Offer everything to gain something greater',
    'screens': [
        {
            'id': 'choice',
            'type': 'make_choice',
            'parameters': {
                'title': 'The Red Gate',
                'message': 'The gate pulses with dark energy. Offer everything to gain something greater.',
                'choices': [
                    {
                        'name': 'Abandon Strength',
                        'description': 'Choose a minion and reduce its attack',
                        'tooltip': 'Select a minion, then choose how much attack to remove.',
                        'icon': generate_lucide_svg('sword-off', width=24, height=24),
                        'next_event': 'red_gate_abandon_strength'
                    },
                    {
                        'name': 'Abandon Vigor',
                        'description': 'Choose a minion and reduce its health',
                        'tooltip': 'Select a minion, then choose how much health to remove. Cannot reduce below 1.',
                        'icon': generate_lucide_svg('heart-off', width=24, height=24),
                        'next_event': 'red_gate_abandon_vigor'
                    },
                    {
                        'name': 'Abandon Skill',
                        'description': 'Choose a minion and remove keywords',
                        'tooltip': 'Select a minion, then choose which keywords to strip away.',
                        'icon': generate_lucide_svg('sparkles-off', width=24, height=24),
                        'next_event': 'red_gate_abandon_skill'
                    },
                    {
                        'name': 'Abandon Allegiance',
                        'description': 'Choose a minion and remove types',
                        'tooltip': 'Select a minion, then choose which types to strip away.',
                        'icon': generate_lucide_svg('users-x', width=24, height=24),
                        'next_event': 'red_gate_abandon_allegiance'
                    },
                    {
                        'name': 'Abandon Death',
                        'description': 'Transcend mortality itself',
                        'tooltip': 'Requires a Tier 2+ minion with 0 attack, 1 health, no types, and no keywords. That minion gains Ethereal [Last].',
                        'icon': generate_lucide_svg('infinity', width=24, height=24),
                        'condition': 'has_transcendence_candidate',
                        'disabled_until_met': True,
                        'on_select': 'red_gate_abandon_death',
                        'mark_event_complete': True,
                        'next_event': None
                    },
                    {
                        'name': 'Leave',
                        'description': 'Walk away from the gate',
                        'tooltip': 'Leave without doing anything.',
                        'icon': generate_lucide_svg('footprints', width=24, height=24),
                        'next_event': None
                    }
                ]
            }
        }
    ]
}

# ==================== UNDEAD ZONE EVENTS ====================

# -------------------- THE GREAT WORK --------------------

GREAT_WORK_SEARCH_GRAVES = {
    'id': 'great_work_search_graves',
    'visit_rule': 'repeatable',
    'title': 'Search the Graves',
    'description': 'Browse the offerings of the dead',
    'screens': [
        {
            'id': 'shop',
            'type': 'ad_nauseam',
            'parameters': {
                'inner_type': 'shop',
                'title': 'Search the Graves',
                'cost_tracker': 'search_graves_cost',
                'return_to_event': 'the_great_work'
            }
        }
    ]
}

GREAT_WORK_MARK_SCROLLS = {
    'id': 'great_work_mark_scrolls',
    'visit_rule': 'repeatable',
    'title': 'Mark the Scrolls',
    'description': 'Divine your future path',
    'screens': [
        {
            'id': 'scry',
            'type': 'ad_nauseam',
            'parameters': {
                'inner_type': 'scry',
                'title': 'Mark the Scrolls',
                'cost_tracker': 'mark_scrolls_cost',
                'return_to_event': 'the_great_work'
            }
        }
    ]
}

GREAT_WORK_COUNT_BLESSINGS = {
    'id': 'great_work_count_blessings',
    'visit_rule': 'repeatable',
    'title': 'Count Your Blessings',
    'description': 'Receive a blessing from beyond',
    'screens': [
        {
            'id': 'blessing',
            'type': 'ad_nauseam',
            'parameters': {
                'inner_type': 'blessing',
                'title': 'Count Your Blessings',
                'cost_tracker': 'count_blessings_cost',
                'return_to_event': 'the_great_work'
            }
        }
    ]
}

THE_GREAT_WORK = {
    'id': 'the_great_work',
    'visit_rule': 'repeatable',
    'title': 'The Great Work',
    'description': 'The cacophonous city stands out, alive as it is dead',
    'screens': [
        {
            'id': 'choice',
            'type': 'make_choice',
            'parameters': {
                'title': 'The Great Work',
                'message': 'The cacophonous city stands out, alive as it is dead.',
                'warning_text': 'All effects cost 1 more life each time used.',
                'ad_nauseam': True,  # Flag for the Ad Nauseam mechanic
                'choices': [
                    {
                        'name': 'Search the Graves',
                        'description': '3 random minions. Buy or roll again.',
                        'tooltip': 'Roll 3 random minions. You can buy them for normal price.',
                        'icon': generate_lucide_svg('search', width=24, height=24),
                        'health_cost_tracker': 'search_graves_cost',
                        'next_event': 'great_work_search_graves'
                    },
                    {
                        'name': 'Mark the Scrolls',
                        'description': 'See your next event. Keep, discard, or reroll.',
                        'tooltip': 'Your next general event is displayed. Keep it, discard it, or roll again. Cost: {mark_scrolls_cost} HP',
                        'icon': generate_lucide_svg('scroll', width=24, height=24),
                        'health_cost_tracker': 'mark_scrolls_cost',
                        'next_event': 'great_work_mark_scrolls'
                    },
                    {
                        'name': 'Count Your Blessings',
                        'description': 'Receive a blessing',
                        'tooltip': 'Functions as a standard blessing. Cost: {count_blessings_cost} HP',
                        'icon': generate_lucide_svg('sparkles', width=24, height=24),
                        'health_cost_tracker': 'count_blessings_cost',
                        'next_event': 'great_work_count_blessings'
                    },
                    {
                        'name': 'Lichdom',
                        'description': 'Transcend the mortal coil',
                        'tooltip': 'Cost: 25 gold. Set health to 5. Gain second hero power: Effects that cost health instead cost gold.',
                        'icon': generate_lucide_svg('crown', width=24, height=24),
                        'gold_cost': '25',
                        'condition': 'not_has_lichdom',
                        'on_select': 'great_work_lichdom',
                        'mark_event_complete': True,
                        'next_event': None
                    },
                    {
                        'name': 'Leave',
                        'description': 'Walk away from the city',
                        'tooltip': 'Leave without doing anything.',
                        'icon': generate_lucide_svg('footprints', width=24, height=24),
                        'next_event': None
                    }
                ]
            }
        }
    ]
}

# -------------------- ZONE EVENT REGISTRIES --------------------

# -------------------- CROSSROADS EVENTS REGISTRY --------------------

CROSSROADS_EVENTS = {
    'mercenary_camp': MERCENARY_CAMP,
    'collapsed_mine': COLLAPSED_MINE,
    'vast_kennels': VAST_KENNELS,
    'watchtower': WATCHTOWER
}

# -------------------- FEY ZONE EVENTS REGISTRY --------------------

FEY_ZONE_EVENTS = {
    'ivory_tower': IVORY_TOWER
}

FEY_ZONE_SUB_EVENTS = {
    'ivory_tower_sacrifice': IVORY_TOWER_SACRIFICE
}

# -------------------- CONSTRUCT ZONE EVENTS REGISTRY --------------------

CONSTRUCT_ZONE_EVENTS = {
    'grand_city': GRAND_CITY,
    'scrap_heap': SCRAP_HEAP
}

CONSTRUCT_ZONE_SUB_EVENTS = {
    'grand_city_golden_forge': GRAND_CITY_GOLDEN_FORGE
}

# -------------------- CULT ZONE EVENTS REGISTRY --------------------

CULT_ZONE_EVENTS = {
    'the_red_gate': THE_RED_GATE
}

CULT_ZONE_SUB_EVENTS = {
    'red_gate_abandon_strength': RED_GATE_ABANDON_STRENGTH,
    'red_gate_abandon_vigor': RED_GATE_ABANDON_VIGOR,
    'red_gate_abandon_skill': RED_GATE_ABANDON_SKILL,
    'red_gate_abandon_allegiance': RED_GATE_ABANDON_ALLEGIANCE
}

# -------------------- UNDEAD ZONE EVENTS REGISTRY --------------------

UNDEAD_ZONE_EVENTS = {
    'the_great_work': THE_GREAT_WORK
}

UNDEAD_ZONE_SUB_EVENTS = {
    'great_work_search_graves': GREAT_WORK_SEARCH_GRAVES,
    'great_work_mark_scrolls': GREAT_WORK_MARK_SCROLLS,
    'great_work_count_blessings': GREAT_WORK_COUNT_BLESSINGS
}

CROSSROADS_SUB_EVENTS = {
    'mercenary_camp_hire_guard': MERCENARY_CAMP_HIRE_GUARD,
    'mercenary_camp_duel': MERCENARY_CAMP_DUEL,
    'mercenary_camp_duel_victory': MERCENARY_CAMP_DUEL_VICTORY,
    'mercenary_camp_takeover': MERCENARY_CAMP_TAKEOVER,
    'mercenary_camp_takeover_victory': MERCENARY_CAMP_TAKEOVER_VICTORY,
    'kennels_buy_hound': KENNELS_BUY_HOUND,
    'kennels_buy_cat': KENNELS_BUY_CAT,
    'watchtower_storm': WATCHTOWER_STORM,
    'watchtower_storm_victory': WATCHTOWER_STORM_VICTORY,
    'watchtower_aid': WATCHTOWER_AID
}

STORY_EVENTS = {
    'ancient_shrine': ANCIENT_SHRINE,
    'mysterious_merchant': MYSTERIOUS_MERCHANT,
    'guardian_trial': GUARDIAN_TRIAL,
    'cursed_fountain': CURSED_FOUNTAIN,
    'bell_tower': BELL_TOWER
}

BELL_TOWER_SUB_EVENTS = {
    'bell_tower_blessing': BELL_TOWER_BLESSING,
    'bell_tower_combat': BELL_TOWER_COMBAT,
    'bell_tower_quasimodo': BELL_TOWER_QUASIMODO
}

BASIC_EVENTS = {
    'minion_event': MINION_EVENT,
    'buff_event': BUFF_EVENT,
    'combat_event': COMBAT_EVENT,
    'combat_event_hard': COMBAT_EVENT_HARD,
    'shop_event': SHOP_EVENT,
    'statue': STATUE_EVENT,
    'zone_portal': ZONE_PORTAL_EVENT
}

REPEATABLE_EVENTS = {
    'golden_statue': GOLDEN_STATUE_EVENT,
    'traveling_merchant': TRAVELING_MERCHANT,
    'bandit_ambush': BANDIT_AMBUSH,
    'elite_encounter': ELITE_ENCOUNTER
}

# The Great Hunt (Beast Wildlands zone event)
GREAT_HUNT_EVENTS = {
    'the_great_hunt': THE_GREAT_HUNT
}

GREAT_HUNT_SUB_EVENTS = {
    'great_hunt_feed_sacrifice': GREAT_HUNT_FEED_SACRIFICE,
    'great_hunt_feed_target': GREAT_HUNT_FEED_TARGET,
    'great_hunt_boss_encounter': GREAT_HUNT_BOSS_ENCOUNTER,
    'great_hunt_boss_victory': GREAT_HUNT_BOSS_VICTORY,
    'great_hunt_victory_dire_pack': GREAT_HUNT_VICTORY_DIRE_PACK,
    'great_hunt_victory_congregation': GREAT_HUNT_VICTORY_CONGREGATION,
    'great_hunt_victory_chained_beast': GREAT_HUNT_VICTORY_CHAINED_BEAST,
    'great_hunt_victory_behemoth': GREAT_HUNT_VICTORY_BEHEMOTH,
    'great_hunt_victory_venomspawn': GREAT_HUNT_VICTORY_VENOMSPAWN,
    'great_hunt_victory_greater_possessed': GREAT_HUNT_VICTORY_GREATER_POSSESSED,
    # Boss reward target selection sub-events
    'great_hunt_reward_dire_pack_keyword': GREAT_HUNT_REWARD_DIRE_PACK_KEYWORD,
    'great_hunt_reward_congregation_tribe': GREAT_HUNT_REWARD_CONGREGATION_TRIBE,
    'great_hunt_reward_congregation_ignoble': GREAT_HUNT_REWARD_CONGREGATION_IGNOBLE,
    'great_hunt_reward_chained_stats': GREAT_HUNT_REWARD_CHAINED_STATS,
    'great_hunt_reward_chained_ethereal': GREAT_HUNT_REWARD_CHAINED_ETHEREAL,
    'great_hunt_reward_behemoth_tank': GREAT_HUNT_REWARD_BEHEMOTH_TANK,
    'great_hunt_reward_venomspawn_cast': GREAT_HUNT_REWARD_VENOMSPAWN_CAST,
    'great_hunt_reward_possessed_deathtoll': GREAT_HUNT_REWARD_POSSESSED_DEATHTOLL,
}

# All events combined
ALL_CUSTOM_EVENTS = {
    **BASIC_EVENTS,
    **STORY_EVENTS,
    **REPEATABLE_EVENTS,
    **BELL_TOWER_SUB_EVENTS,
    **CROSSROADS_EVENTS,
    **CROSSROADS_SUB_EVENTS,
    **FEY_ZONE_EVENTS,
    **FEY_ZONE_SUB_EVENTS,
    **CONSTRUCT_ZONE_EVENTS,
    **CONSTRUCT_ZONE_SUB_EVENTS,
    **CULT_ZONE_EVENTS,
    **CULT_ZONE_SUB_EVENTS,
    **UNDEAD_ZONE_EVENTS,
    **UNDEAD_ZONE_SUB_EVENTS,
    **GREAT_HUNT_EVENTS,
    **GREAT_HUNT_SUB_EVENTS
}


# ==================== HELPER FUNCTIONS ====================

def get_event(event_id: str) -> dict:
    """Get an event definition by ID"""
    return ALL_CUSTOM_EVENTS.get(event_id)


def get_events_by_visit_rule(visit_rule: str) -> dict:
    """Get all events with a specific visit rule"""
    return {
        event_id: event
        for event_id, event in ALL_CUSTOM_EVENTS.items()
        if event.get('visit_rule') == visit_rule
    }


def get_story_events() -> dict:
    """Get all one-time story events"""
    return STORY_EVENTS


def get_repeatable_events() -> dict:
    """Get all repeatable events"""
    return REPEATABLE_EVENTS


def validate_event(event: dict) -> tuple[bool, list]:
    """
    Validate an event definition

    Returns:
        (is_valid, error_messages)
    """
    errors = []

    # Check required fields
    if 'id' not in event:
        errors.append("Event missing 'id' field")
    if 'visit_rule' not in event:
        errors.append("Event missing 'visit_rule' field")
    if 'screens' not in event or not isinstance(event['screens'], list):
        errors.append("Event missing 'screens' list")

    # Validate screens
    screens = event.get('screens', [])
    if len(screens) == 0:
        errors.append("Event has no screens")

    for i, screen in enumerate(screens):
        if 'type' not in screen:
            errors.append(f"Screen {i} missing 'type' field")
        if 'parameters' not in screen:
            errors.append(f"Screen {i} missing 'parameters' field")

    return len(errors) == 0, errors


def validate_all_events():
    """Validate all event definitions"""
    errors = []

    for event_id, event in ALL_CUSTOM_EVENTS.items():
        is_valid, event_errors = validate_event(event)
        if not is_valid:
            errors.append(f"Event '{event_id}' validation failed:")
            errors.extend([f"  - {error}" for error in event_errors])

    if errors:
        raise ValueError(f"Event validation failed:\n" + "\n".join(errors))

    logger.debug(f"✓ All events validated: {len(ALL_CUSTOM_EVENTS)} events")


# Validate on import
validate_all_events()
