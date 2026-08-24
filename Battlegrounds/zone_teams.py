"""
Zone Teams Configuration
Predefined teams for each zone and tier

Team Format:
- Each entry can be either a string (minion name) or a dict with custom stats
- String example: 'Scout'
- Dict example: {'name': 'Cat', 'health': 10, 'attack': 10}
"""

# Tier 1 Teams for Crossroads and Zones
# Crossroads teams are generally easier than zone-specific teams

ZONE_TEAMS = {
    'tier_1': {
        'starting_plains': [  # The Crossroads
            ['Scout', 'Iron Wall'],
            ['Scout', 'Scout', 'Scout', 'Scout'],
            ['Soldier', 'Farmer'],
            ['Rust Golem', 'Wisp'],
        ],
        'cult_sanctum': [
            ['Cultist', 'Chains', 'Skeleton', 'Chains'],
            ['Ritual Alter', 'Iron Wall', 'Ritual Alter', 'Chains'],
            ['Chains', 'Chains', 'Iron Wall', 'Scout'],
            ['Cultist', 'Cultist', 'Cultist', 'Cultist'],
        ],
        'beast_wildlands': [
            [{'name': 'Cat', 'health': 10, 'attack': 10}],  # Special buffed Cat
            ['Hound', 'Hound', 'Iron Wall', 'Sparrow'],
            ['Cat', 'Cat', 'Hound', 'Hound'],
            ['Sparrow', 'Hound', 'Hound', 'Huntsman'],
        ],
        'undead_crypts': [
            ['Skeleton', 'Ritual Alter', 'Skeleton', 'Iron Wall'],
            ['Skeleton', 'Skeleton', 'Skeleton', 'Skeleton'],
            ['Meat Pile', 'Ritual Alter', 'Meat Pile', 'Ritual Alter'],
            ['Zombie', 'Zombie', 'Zombie', 'Zombie', 'Zombie', 'Zombie'],
        ],
        'fey_grove': [
            ['Spriggan', 'Spriggan', 'Hound', 'Sparrow'],
            [{'name': 'Wisp', 'health': 6, 'attack': 2}],  # Special buffed Wisp
            ['Spriggan', 'Spriggan', 'Rust Golem', 'Iron Wall'],
            ['Pixie', 'Pixie', 'Pixie', 'Pixie'],
        ],
        'human_kingdom': [
            ['Huntsman', 'Farmer', 'Farmer', 'Farmer'],
            ['Huntsman', 'Hound', 'Soldier', 'Iron Wall'],
            ['Rust Golem', 'Soldier', 'Soldier', 'Hound'],
            ['Huntsman', 'Huntsman', 'Huntsman', 'Soldier'],
        ],
        'construct_foundry': [
            ['Rust Golem', 'Rust Golem', 'Rust Golem', 'Rust Golem'],
            ['Rust Golem', 'Chains', 'Scout', 'Iron Wall'],
            ['Spriggan', 'Iron Wall', 'Iron Wall', 'Iron Wall'],
            ['Gear Spider', 'Gear Spider', 'Iron Wall', 'Rust Golem'],
        ],
    },
    'tier_2': {
        'construct_foundry': [
            # Cat sacrifice engine
            [{'name': 'Cat', 'health': 14, 'attack': 14, 'golden': True}, 'Meat Packaging Plant', 'Quartermaster', 'Iron Wall', 'Tally Keeper', 'Clockwork'],
            # Rage scaling with anti-cast
            ['Bear', 'Clockwork', 'Clockwork', 'War Machine', 'Iron Wall', 'Tally Keeper'],
            # Anti-cast wall with death bomb
            [{'name': 'War Machine', 'health': 4, 'attack': 4, 'golden': True}, 'Tally Keeper', 'Tally Keeper', 'Iron Wall', 'Gravebomb', 'War Horse'],
            # Double death trigger defense
            ['Gravebomb', 'Clockwork', 'Clockwork', 'Iron Wall', 'War Machine', 'Gravebomb'],
        ],
        'undead_crypts': [
            # Skeleton spam engine
            ['Necromancer', 'Ritual Alter', 'Necromancer', 'Chronomancer', 'Quartermaster', 'Blood Bile'],
            # Mixed scaling and burst
            [{'name': 'Skeleton', 'health': 2, 'attack': 2, 'golden': True}, 'Wight', 'Tally Keeper', 'Iron Wall', 'Blood Bile', 'Gravebomb'],
            # Cast punishment with death bomb
            [{'name': 'Wight', 'health': 4, 'attack': 4, 'golden': True}, 'Clockwork', 'Tally Keeper', 'Tally Keeper', 'Gravebomb', 'Iron Wall'],
            # Death scaling stack team
            ['Gravebomb', 'Blood Bile', 'Blood Bile', 'Necromancer', 'Wight', 'Gravebomb'],
        ],
        'fey_grove': [
            # Guard wall spam
            ['Dryad', 'Meat Packaging Plant', 'Ritual Alter', 'Chronomancer', 'Quartermaster', 'Dryad'],
            # AOE + sustain combo
            ['Dryad', 'Ritual Alter', 'Wizard', 'Chronomancer', 'Wisp', 'Iron Wall'],
            # Disruption + pressure
            [{'name': 'Dryad', 'health': 6, 'attack': 2, 'golden': True}, 'Ram', 'Bear', 'Kelpie', 'Chronomancer', 'Dryad'],
            # Apprentice scaling with casters
            ['Wizard', 'Apprentice', 'Dryad', 'Chronomancer', 'Wisp', 'Iron Wall'],
        ],
        'beast_wildlands': [
            # Pure golden stat check
            [{'name': 'Bear', 'health': 8, 'attack': 8, 'golden': True}, {'name': 'Ram', 'health': 4, 'attack': 8, 'golden': True}, {'name': 'War Horse', 'health': 14, 'attack': 14, 'golden': True}],
            # Quad multi-attack
            ['Bear', 'Bear', 'Bear', 'Bear'],
            # Mixed aggro
            ['Kelpie', 'Ram', 'War Horse', 'Hound', 'Fanatic', 'Ram'],
            # Beast stats with Apprentice flex
            ['Bear', 'Ram', 'War Horse', 'Apprentice', 'Hound', 'Iron Wall'],
        ],
        'cult_sanctum': [
            # Cultist death → Fanatic scaling
            [{'name': 'Cultist', 'health': 2, 'attack': 2, 'golden': True}, 'Meat Packaging Plant', 'Fanatic', 'Fanatic', 'Tally Keeper', 'Iron Wall'],
            # Pure tribal exponential
            ['Cultist', 'Cultist', 'Cultist', 'Cultist', 'Cultist', 'Cultist'],
            # Sacrifice combo engine
            ['Necromancer', 'Meat Packaging Plant', 'Ritual Alter', 'Quartermaster', 'Chronomancer', 'Fanatic'],
            # Death bombs + Fanatic rage
            ['Gravebomb', 'Fanatic', 'Fanatic', 'Meat Packaging Plant', 'Gravebomb', 'Iron Wall'],
        ],
        'human_kingdom': [
            # Triple Wizard AOE
            ['Wizard', 'Wizard', 'Chronomancer', 'Paladin', 'Paladin', 'Iron Wall'],
            # Sustain + anti-cast
            ['Paladin', 'War Horse', 'Tally Keeper', 'Ram', 'Paladin', 'Iron Wall'],
            # AOE + guard hybrid
            ['Wizard', 'Dryad', 'Wizard', 'Dryad', 'Paladin', 'Chronomancer'],
            # Apprentice Academy (scales +3/+3+ per turn)
            ['Wizard', 'Apprentice', 'Chronomancer', 'Wizard', 'Paladin', 'Iron Wall'],
        ],
    },
    'tier_3': {
        'construct_foundry': [
            # Destroyer counter-attack engine
            [{'name': 'Destroyer', 'health': 14, 'attack': 2, 'golden': True}, 'Tally Keeper', 'War Machine', 'Clockwork', 'Ballista', 'Standing Stone'],
            # Ballista nuke with construct scaling
            ['Ballista', 'Dominus', 'Standing Stone', 'Tally Keeper', 'Clockwork', 'War Machine'],
            # Anti-cast wall with tier 4 power
            ['Destroyer', 'Tally Keeper', 'Tally Keeper', 'Ballista', 'Standing Stone', 'Dominus'],
            # Mixed construct aggro
            ['Dominus', 'Destroyer', 'Ballista', 'War Machine', 'Clockwork', 'Standing Stone'],
        ],
        'undead_crypts': [
            # Death scaling with Devouring Smog
            ['Devouring Smog', 'Accursed', 'Blood Bile', 'Necromancer', 'Wight', 'Gravebomb'],
            # Rich stacking with Accursed
            [{'name': 'Accursed', 'health': 4, 'attack': 4, 'golden': True}, 'Blood Bile', 'Blood Bile', 'Necromancer', 'Gravebomb', 'Wight'],
            # Hide + AOE control
            ['Devouring Smog', 'Necromancer', 'Necromancer', 'Wight', 'Blood Bile', 'Gravebomb'],
            # Death trigger overload
            ['Blood Bile', 'Death Avenger', 'Accursed', 'Necromancer', 'Gravebomb', 'Gravebomb'],
        ],
        'fey_grove': [
            # Stun control with Tooth Fairy
            ['Tooth Fairy', 'Alp', 'Brownie', 'Dryad', 'Wizard', 'Chronomancer'],
            # Cast spam with Brownie buffs
            ['Brownie', 'Wizard', 'Alp', 'Dryad', 'Chronomancer', 'Tooth Fairy'],
            # Mixed control and aggro
            [{'name': 'Tooth Fairy', 'health': 1, 'attack': 3, 'golden': True}, 'Brownie', 'Alp', 'Wizard', 'Dryad', 'Chronomancer'],
            # Double stun punishment
            ['Tooth Fairy', 'Tooth Fairy', 'Alp', 'Alp', 'Brownie', 'Wizard'],
        ],
        'beast_wildlands': [
            # Pure beast power
            [{'name': 'Queen Bee', 'health': 30, 'attack': 3, 'golden': True}, 'Basilisk', 'Paper Tiger', 'Bear', 'Ram', 'War Horse'],
            # Hide + poke control
            ['Paper Tiger', 'Basilisk', 'Bear', 'Bear', 'Ram', 'Houndmaster'],
            # Houndmaster synergy
            ['Houndmaster', 'Basilisk', 'Bear', 'Ram', 'War Horse', 'Queen Bee'],
            # Mixed beast aggro
            ['Basilisk', 'Paper Tiger', 'Bear', 'Bear', 'Ram', 'Ram'],
        ],
        'cult_sanctum': [
            # Cabal multi-attack spam
            [{'name': 'Cabal', 'health': 6, 'attack': 4, 'golden': True}, 'Emissary', 'Bishop', 'Fanatic', 'Fanatic', 'Meat Packaging Plant'],
            # Savage scaling with Emissary
            ['Emissary', 'Cabal', 'Bishop', 'Fanatic', 'Necromancer', 'Meat Packaging Plant'],
            # Ignoble wall with Bishop
            ['Bishop', 'Bishop', 'Cabal', 'Emissary', 'Fanatic', 'Amalgam'],
            # Amalgam perfect scaling
            ['Amalgam', 'Amalgam', 'Cabal', 'Emissary', 'Bishop', 'Fanatic'],
        ],
        'human_kingdom': [
            # Shinobi assassin with hide
            [{'name': 'Shinobi', 'health': 7, 'attack': 7, 'golden': True}, 'Warlord', 'Gangster', 'Wizard', 'Paladin', 'Chronomancer'],
            # Warlord tier 1 scaling
            ['Warlord', 'Gangster', 'Shinobi', 'Wizard', 'Paladin', 'Apprentice'],
            # Gangster summon engine
            ['Gangster', 'Warlord', 'Shinobi', 'Paladin', 'Wizard', 'Chronomancer'],
            # Mixed control and burst
            ['Shinobi', 'Cleaver', 'Warlord', 'Wizard', 'Paladin', 'Paladin'],
        ],
        'starting_plains': [
            # Balanced tier 3 intro
            ['Shinobi', 'Warlord', 'Basilisk', 'Dryad', 'Clockwork', 'Iron Wall'],
            # Mixed faction mid-game
            ['Gangster', 'Cabal', 'Paper Tiger', 'Brownie', 'Necromancer', 'Standing Stone'],
            # Control focused
            ['Tooth Fairy', 'Alp', 'Ballista', 'Tally Keeper', 'Wizard', 'Chronomancer'],
            # Aggro focused
            ['Basilisk', 'Bear', 'Shinobi', 'Cabal', 'Cleaver', 'Ram'],
        ],
    },
    'tier_4': {
        'construct_foundry': [
            # Destroyer legendary
            [{'name': 'Destroyer', 'health': 14, 'attack': 2, 'golden': True}, 'Ballista', 'Ballista', 'Tally Keeper', 'Standing Stone', 'Dominus'],
            # Double Destroyer wall
            ['Destroyer', 'Destroyer', 'Ballista', 'Tally Keeper', 'Tally Keeper', 'Standing Stone'],
            # Mixed legendary power
            ['Destroyer', 'King', 'Ballista', 'Dominus', 'Tally Keeper', 'Standing Stone'],
            # Pure construct end-game
            ['Destroyer', 'Ballista', 'Dominus', 'Standing Stone', 'War Machine', 'Clockwork'],
        ],
        'undead_crypts': [
            # Demilich obliterate
            [{'name': 'Demilich', 'health': 12, 'attack': 12, 'golden': True}, 'Bogeyman', 'Dullahan', 'Possessed', 'Blood Bile', 'Gravebomb'],
            # Possessed chain death toll
            ['Possessed', 'Possessed', 'Dullahan', 'Bogeyman', 'Blood Bile', 'Necromancer'],
            # Dullahan guard wall
            ['Dullahan', 'Dullahan', 'Demilich', 'Bogeyman', 'Blood Bile', 'Gravebomb'],
            # Bogeyman stun control
            ['Bogeyman', 'Bogeyman', 'Demilich', 'Possessed', 'Dullahan', 'Accursed'],
        ],
        'fey_grove': [
            # King nobility with fey support
            [{'name': 'King', 'health': 1, 'attack': 1, 'golden': True}, 'Tooth Fairy', 'Alp', 'Brownie', 'Wizard', 'Chronomancer'],
            # Stun lock combo
            ['Bogeyman', 'Tooth Fairy', 'Tooth Fairy', 'Alp', 'Alp', 'Brownie'],
            # Mixed legendary fey
            ['King', 'Tooth Fairy', 'Alp', 'Brownie', 'Wizard', 'Dryad'],
            # Cast spam legendary
            ['King', 'Brownie', 'Wizard', 'Wizard', 'Alp', 'Chronomancer'],
        ],
        'beast_wildlands': [
            # Old Cat Lady engine
            [{'name': 'Old Cat Lady', 'health': 6, 'attack': 1, 'golden': True}, 'Queen Bee', 'Basilisk', 'Paper Tiger', 'Bear', 'Houndmaster'],
            # Pure legendary beasts
            ['Old Cat Lady', 'Queen Bee', 'Basilisk', 'Paper Tiger', 'Bear', 'Bear'],
            # Cat death trigger scaling
            ['Old Cat Lady', 'Old Cat Lady', 'Houndmaster', 'Queen Bee', 'Basilisk', 'Ram'],
            # Mixed beast legendary
            ['Old Cat Lady', 'Queen Bee', 'Basilisk', 'Houndmaster', 'Bear', 'War Horse'],
        ],
        'cult_sanctum': [
            # Lookalike transformation
            [{'name': 'Lookalike', 'health': 4, 'attack': 4, 'golden': True}, 'Reprocessor', 'Cabal', 'Emissary', 'Bishop', 'Amalgam'],
            # Reprocessor cultist spam
            ['Reprocessor', 'Reprocessor', 'Lookalike', 'Cabal', 'Emissary', 'Bishop'],
            # Mixed cult legendary
            ['Lookalike', 'Reprocessor', 'Old Cat Lady', 'Cabal', 'Emissary', 'Bishop'],
            # Pure legendary cult
            ['Lookalike', 'Reprocessor', 'Old Cat Lady', 'Amalgam', 'Cabal', 'Emissary'],
        ],
        'human_kingdom': [
            # King nobility scaling
            [{'name': 'King', 'health': 1, 'attack': 1, 'golden': True}, 'Siegfried', 'Sellsword', 'Shinobi', 'Warlord', 'Wizard'],
            # Siegfried burst combo
            ['Siegfried', 'Siegfried', 'Sellsword', 'King', 'Shinobi', 'Paladin'],
            # Sellsword multi-target
            ['Sellsword', 'Sellsword', 'Siegfried', 'King', 'Warlord', 'Wizard'],
            # Mixed human legendary
            ['King', 'Siegfried', 'Sellsword', 'Shinobi', 'Warlord', 'Paladin'],
        ],
        'starting_plains': [
            # Balanced tier 4 showcase
            ['King', 'Siegfried', 'Dullahan', 'Destroyer', 'Basilisk', 'Tooth Fairy'],
            # Mixed legendary factions
            ['Demilich', 'Old Cat Lady', 'Lookalike', 'Sellsword', 'Bogeyman', 'Queen Bee'],
            # Control legendary
            ['Destroyer', 'Bogeyman', 'Tooth Fairy', 'King', 'Ballista', 'Dullahan'],
            # Aggro legendary
            ['Siegfried', 'Sellsword', 'Basilisk', 'Old Cat Lady', 'Possessed', 'Cabal'],
        ],
    },
    # Tier 5 can be added later
}


# ==================== BOSS TEAMS ====================
# Predefined boss encounters for The Great Hunt event (Beast Wildlands)
# Each team uses minions from BOSS_MINIONS in minions.py

BOSS_TEAMS = {
    'dire_pack': [
        'Dire Wolf',
        'Dire Wolf',
        'Alpha Direwolf',
        'Dire Wolf',
        'Dire Wolf'
    ],
    'congregation': [
        'Cultist',
        'Cultist',
        'Congregation',
        'Cultist',
        'Cultist'
    ],
    'chained_beast': [
        'Chain',
        'Chain',
        'Chain',
        'Chain',
        'Chain',
        'Chained Beast'
    ],
    'behemoth': [
        'Ancient Behemoth'
    ],
    'venomspawn': [
        'Venomling',
        'Venomling',
        'Broodmother',
        'Venomling'
    ],
    'greater_possessed': [
        # Special handling - 5 random tier minions each possessed by a Possessed
        # No minions in the team definition - all generated at runtime by generate_boss_band()
    ]
}


# ==================== BOSS REWARDS ====================
# Unique rewards for defeating each boss in The Great Hunt
# Each boss has a specific reward rather than generic choices

BOSS_REWARDS = {
    'dire_pack': {
        'name': 'Pack Tactics',
        'description': 'All minions gain +2/+2. One random minion gains Assault.',
        'handler': 'boss_reward_dire_pack',
        'requires_target': False
    },
    'congregation': {
        'name': 'Convert the Masses',
        'description': 'Recruit 2 Cultists. All Cult minions gain +3/+3.',
        'handler': 'boss_reward_congregation',
        'requires_target': False
    },
    'chained_beast': {
        'name': 'Unbound',
        'description': 'One minion gains +8/+8 and Leap.',
        'handler': 'boss_reward_chained_beast',
        'requires_target': True
    },
    'behemoth': {
        'name': 'Thick Hide',
        'description': 'One minion gains Guard and +5/+12.',
        'handler': 'boss_reward_behemoth',
        'requires_target': True
    },
    'venomspawn': {
        'name': 'Venom Glands',
        'description': 'All Beasts gain +2/+2 and Poke.',
        'handler': 'boss_reward_venomspawn',
        'requires_target': False
    },
    'greater_possessed': {
        'name': "Corruption's Gift",
        'description': 'Gain tier × 10 gold. All minions gain +2/+0.',
        'handler': 'boss_reward_greater_possessed',
        'requires_target': False
    }
}


def get_boss_reward(boss_id):
    """
    Get the reward definition for a boss

    Args:
        boss_id: String identifier for the boss

    Returns:
        Reward dict or None if not found
    """
    return BOSS_REWARDS.get(boss_id)


def get_boss_team(boss_id):
    """
    Get a predefined boss team by ID

    Args:
        boss_id: String identifier for the boss (e.g., 'dire_pack', 'congregation')

    Returns:
        Team list (list of minion names) or None if not found
    """
    return BOSS_TEAMS.get(boss_id)


def get_zone_teams(tier, zone):
    """
    Get all predefined teams for a specific zone and tier

    Args:
        tier: Integer tier level (1-5)
        zone: Zone identifier string (e.g., 'starting_plains', 'beast_wildlands')

    Returns:
        List of teams (each team is a list of minion names or dicts), or empty list if not found
    """
    tier_key = f'tier_{tier}'
    if tier_key not in ZONE_TEAMS:
        return []

    if zone not in ZONE_TEAMS[tier_key]:
        return []

    return ZONE_TEAMS[tier_key][zone]


def get_random_team(tier, zone):
    """
    Get a random predefined team for a zone and tier

    Args:
        tier: Integer tier level (1-5)
        zone: Zone identifier string

    Returns:
        Team list (list of minion names/dicts) or None if not found
    """
    import random

    teams = get_zone_teams(tier, zone)
    if not teams:
        return None

    team_index = random.randint(0, len(teams) - 1)
    team = teams[team_index]

    return team
