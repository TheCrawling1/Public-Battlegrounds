"""
Minion system for Auto Battler Arena

Defines all minion types, their stats, and utility functions for minion management.
Includes Assault effects for minions with the Assault keyword, Death Toll effects for minions with Death Toll,
Cast effects for minions with the Cast keyword, Summon effects, and Permanent stat tracking.

UPDATED: Added multi-faction support for minions
UPDATED: Added new tier 3 and tier 4 minions with complex effects
UPDATED: Added new keywords: Hide, Leap, Nobility, Rich, On_damage, Imperfect, Fast, Savage, On_any_leap, Ignoble
UPDATED: Fixed Old Cat Lady to properly summon cats with guard and NOT inherit band_id
UPDATED: Added multi-tier pool generation for cumulative tier system
UPDATED: Added tier tracking on minions for cost/reward calculations
UPDATED: King minion now has start_of_combat_effect for Rich keyword (+1/+1 per gold)
UPDATED: Added Accursed minion to tier 3 Undead with on_damage and modify_gold effects
UPDATED: Added new Tier 3 minions: Devouring Smog, Gravebomb, Alp, Tooth Fairy, Brownie, Ballista, Gangster, Warlord, Amalgam, Basilisk, Emissary, Bishop
UPDATED: Added new Tier 4 minions: Dullahan, Dullahan's Head, Bogeyman, Nymph, Railway Cannon, Railway Signal, Banshee, Thunderbird, Shaman, Reprocessor, Frog Prince, Siegfried
UPDATED: Moved Destroyer from Tier 3 to Tier 4 for balance
FIXED: Removed unnecessary empty conditional wrappers from Tooth Fairy, Ballista, and Gangster array effects
"""

import logging

logger = logging.getLogger(__name__)

import random
import threading
from keywords import validate_keywords

# Global counter for unique minion IDs (thread-safe)
_minion_id_counter = 0
_minion_id_lock = threading.Lock()

def generate_unique_minion_id():
    """Generate a unique ID for minions in player bands"""
    global _minion_id_counter
    with _minion_id_lock:
        _minion_id_counter += 1
        return f"minion_{_minion_id_counter}"

# Minion definitions by tier and type
# Tier 0 contains boss minions - used for testing and boss encounters
MINIONS = {
    0: [
        # Boss minions for The Great Hunt
        {'name': 'Alpha Direwolf', 'health': 2, 'attack': 2, 'type': 'Beast',
         'keywords': ['assault', 'on_any_death'], 'rarity': 'boss',
         'assault_effect': {'type': 'buff_stats', 'target': 'self', 'attack': 4, 'health': 0},
         'on_any_death_effect': {'type': 'buff_stats', 'target': 'self', 'attack': 0, 'health': 4},
         'image': 'alpha_direwolf.png'},
        {'name': 'Dire Wolf', 'health': 3, 'attack': 3, 'type': 'Beast',
         'keywords': ['savage'], 'rarity': 'boss',
         'image': 'dire_wolf.png'},
        {'name': 'Congregation', 'health': 30, 'attack': 0, 'type': 'Cult',
         'keywords': ['cant_attack', 'cast'], 'rarity': 'boss',
         'cast_count': 2,
         'cast_effect': {'type': 'summon_minion', 'target': 'summon_position', 'minion_name': 'Cultist', 'health': 1, 'attack': 1, 'summon_count': 2},
         'image': 'congregation.png'},
        {'name': 'Chain', 'health': 12, 'attack': 2, 'type': 'Beast',
         'keywords': ['hide'], 'rarity': 'boss',
         'hide_count': 2,
         'image': 'chain.png'},
        {'name': 'Chained Beast', 'health': 22, 'attack': 22, 'type': 'Beast',
         'keywords': ['ethereal_left', 'leap'], 'rarity': 'boss',
         'leap_distance': 1,
         'image': 'chained_beast.png'},
        {'name': 'Ancient Behemoth', 'health': 40, 'attack': 12, 'type': 'Beast',
         'keywords': ['guard', 'on_damage'], 'rarity': 'boss',
         'on_damage_effect': {'type': 'deal_aoe_damage', 'target': 'all_enemies', 'amount': 2},
         'image': 'ancient_behemoth.png'},
        {'name': 'Broodmother', 'health': 20, 'attack': 6, 'type': 'Beast',
         'keywords': ['death_toll'], 'rarity': 'boss',
         'death_toll_effect': {'type': 'summon_minion', 'target': 'summon_position', 'minion_name': 'Venomling', 'summon_count': 2},
         'image': 'broodmother.png'},
        {'name': 'Venomling', 'health': 2, 'attack': 2, 'type': 'Beast',
         'keywords': ['death_toll'], 'rarity': 'boss',
         'death_toll_effect': {'type': 'deal_damage', 'target': 'random_enemy', 'amount': 3},
         'image': 'venomling.png'},
        {'name': 'Greater Possessed', 'health': 1, 'attack': 6, 'type': 'Undead',
         'keywords': ['death_toll', 'cast'], 'rarity': 'boss',
         'death_toll_effect': {
             'type': 'grant_effect_to_minion',
             'target': 'random_ally',
             'exclude_name': 'Greater Possessed',
             'effect_type': 'death_toll_effect',
             'effect_data': {
                 'type': 'summon_minion',
                 'minion_name': 'Greater Possessed',
                 'health': 1,
                 'attack': 6,
                 'copy_cast_from_self': True
             }
         },
         'cast_effect': {
             'type': 'destroy_and_absorb',
             'target': 'self',
             'transfer_stats_to': 'Greater Possessed'
         },
         'image': 'greater_possessed.png'},
    ],
    1: [
        # Human
        {'name': 'Huntsman', 'health': 1, 'attack': 1, 'type': 'Human', 'keywords': ['assault'], 'rarity': 'common',
         'assault_effect': {'type': 'deal_damage', 'target': 'defender', 'amount': 1},
         'image': 'huntsman.png'},
        {'name': 'Soldier', 'health': 2, 'attack': 2, 'type': 'Human', 'keywords': [], 'rarity': 'common',
         'image': 'soldier.png'},
        {'name': 'Farmer', 'health': 3, 'attack': 1, 'type': 'Human', 'keywords': [], 'rarity': 'common',
         'image': 'Farmer.png'},

        # Undead
        {'name': 'Skeleton', 'health': 1, 'attack': 1, 'type': 'Undead', 'keywords': ['death_toll'], 'rarity': 'common',
         'death_toll_effect': {'type': 'summon_minion', 'target': 'summon_position', 'minion_name': 'Bone', 'health': 1, 'attack': 1},
         'image': 'skeleton.png'},
        {'name': 'Meat Pile', 'health': 1, 'attack': 0, 'type': ['Undead'], 'keywords': ['cast', 'death_toll'], 'rarity': 'common',
         'cast_effect': {'type': 'summon_minion', 'target': 'summon_position', 'minion_name': 'Meat Cube', 'health': 1, 'attack': 0},
         'death_toll_effect': {'type': 'summon_minion', 'target': 'summon_position', 'minion_name': 'Meat Cube', 'health': 1, 'attack': 0},
         'image': 'meat_pile.png'},
        {'name': 'Zombie', 'health': 1, 'attack': 2, 'type': 'Undead', 'keywords': [], 'rarity': 'common',
         'image': 'zombie.png'},

        # Beast
        {'name': 'Hound', 'health': 1, 'attack': 2, 'type': 'Beast', 'keywords': ['poke'], 'rarity': 'common',
         'image': 'hound.png'},
        {'name': 'Cat', 'health': 1, 'attack': 1, 'type': 'Beast', 'keywords': ['death_toll'], 'rarity': 'common',
         'death_toll_effect': {'type': 'permanent_stat_gain', 'target': 'self', 'scope': 'band_only', 'qualifiers': False, 'health': 1, 'attack': 1},
         'image': 'cat.png'},
        {'name': 'Sparrow', 'health': 1, 'attack': 3, 'type': 'Beast', 'keywords': [], 'rarity': 'common',
         'image': 'sparrow.png'},

        # Fey
        {'name': 'Spriggan', 'health': 1, 'attack': 1, 'type': 'Fey', 'keywords': ['cast'], 'rarity': 'common',
         'cast_effect': {'type': 'deal_damage', 'target': 'random_enemy', 'amount': 1},
         'image': 'spriggan.png'},
        {'name': 'Wisp', 'health': 2, 'attack': 0, 'type': 'Fey', 'keywords': ['cast'], 'rarity': 'common',
         'cast_effect': {'type': 'heal', 'target': 'random_ally', 'amount': 2},
         'image': 'Wisp.png'},
        {'name': 'Pixie', 'health': 1, 'attack': 1, 'type': 'Fey', 'keywords': ['cast'], 'rarity': 'common',
         'cast_effect': {'type': 'buff_stats', 'target': 'self', 'attack': 1},
         'image': 'pixie.png'},

        # Construct
        {'name': 'Rust Golem', 'health': 3, 'attack': 3, 'type': 'Construct', 'keywords': ['cant_attack'], 'rarity': 'common',
         'image': 'rust_golem.png'},
        {'name': 'Iron Wall', 'health': 4, 'attack': 0, 'type': 'Construct', 'keywords': ['guard'], 'rarity': 'common',
         'image': 'iron_wall.png'},
        {'name': 'Gear Spider', 'health': 1, 'attack': 1, 'type': 'Construct', 'keywords': ['assault'], 'rarity': 'common',
         'assault_effect': {'type': 'buff_stats', 'target': 'self', 'attack': 1},
         'image': 'gear_spider.png'},

        # Cult (New Tribe)
        {'name': 'Cultist', 'health': 1, 'attack': 1, 'type': 'Cult', 'keywords': ['death_toll'], 'rarity': 'common',
         'death_toll_effect': {'type': 'buff_stats_tribe', 'target': 'all_allies', 'tribe': 'Cult', 'health': 1, 'attack': 1},
         'image': 'cultist.png'},
        {'name': 'Ritual Alter', 'health': 3, 'attack': 0, 'type': 'Cult', 'keywords': ['cant_attack', 'start_of_combat', 'on_any_summon'], 'rarity': 'common',
         'start_of_combat_effect': {'type': 'buff_adjacent', 'attack': 1},
         'on_any_summon_effect': {
             'type': 'conditional',
             'condition': {
                 'check_type': 'compound',
                 'checks': [
                     {'type': 'is_ally', 'target': 'summoned_minion'},
                     {'type': 'is_adjacent', 'target': 'summoned_minion'}
                 ],
                 'operator': 'AND'
             },
             'then_effect': {'type': 'buff_stats', 'target': 'summoned_minion', 'attack': 1}
         },
         'image': 'ritual_alter.png'},
        {'name': 'Chains', 'health': 3, 'attack': 0, 'type': 'Cult', 'keywords': ['cast'], 'rarity': 'common',
         'cast_effect': {'type': 'debuff_stats', 'target': 'random_enemy', 'attack': -1},
         'image': 'chains.png'},

        # No Type
        {'name': 'Scout', 'health': 1, 'attack': 1, 'type': 'None', 'keywords': ['poke'], 'rarity': 'common',
         'image': 'scout.png'},

        # Special summoned minions (not in normal pools)
        {'name': 'Bone', 'health': 1, 'attack': 1, 'type': 'Undead', 'keywords': [], 'rarity': 'token', 'summon_only': True,
         'image': 'bone.png'},
        {'name': 'Thorn', 'health': 2, 'attack': 0, 'type': 'Fey', 'keywords': ['guard'], 'rarity': 'token', 'summon_only': True,
         'image': 'thorn.png'},
        {'name': 'Meat Cube', 'health': 1, 'attack': 0, 'type': 'Cult', 'keywords': [], 'rarity': 'token', 'summon_only': True,
         'image': 'meat_cube.png'}
    ],
    2: [
        # Human
        {'name': 'Wizard', 'health': 4, 'attack': 0, 'type': 'Human', 'keywords': ['cast'], 'rarity': 'rare',
         'cast_effect': {'type': 'deal_aoe_damage', 'target': 'all_enemies', 'amount': 1, 'max_targets': 999},
         'image': 'wizard.png'},
        {'name': 'Paladin', 'health': 3, 'attack': 2, 'type': 'Human', 'keywords': ['assault'], 'rarity': 'rare',
         'assault_effect': {'type': 'heal_self', 'amount': 2},
         'image': 'paladin.png'},
        {'name': 'Apprentice', 'health': 2, 'attack': 2, 'type': 'Human', 'keywords': ['calm'], 'rarity': 'rare',
         'calm_effect': {'type': 'buff_stats', 'target': 'self', 'health': 1, 'attack': 1},
         'image': 'Apprentice.png'},

        # Chronomancer - Multi-faction: Fey + Beast
        {'name': 'Chronomancer', 'health': 7, 'attack': 0, 'type': ['Fey', 'Beast'], 'keywords': ['on_any_cast'], 'rarity': 'rare',
         'on_any_cast_effect': {
             'type': 'conditional',
             'condition': {
                 'type': 'is_ally',
                 'target': 'trigger_source'
             },
             'then_effect': {
                 'type': 'chrono_cascade',
                 'find_next_cast': True
             }
         },
         'image': 'Chronomancer.png'},

        # Quartermaster
        {'name': 'Quartermaster', 'health': 4, 'attack': 4, 'type': 'Human', 'keywords': ['on_any_summon'], 'rarity': 'rare',
         'on_any_summon_effect': {
             'type': 'conditional',
             'condition': {
                 'type': 'is_ally',
                 'target': 'trigger_summoned'
             },
             'then_effect': {
                 'type': 'attack_target',
                 'attacker': 'trigger_summoned',
                 'target_minion': None
             }
         },
         'image': 'Quatermaster.png'},

        # Undead
        {'name': 'Blood Bile', 'health': 2, 'attack': 2, 'type': 'Undead', 'keywords': ['on_any_death'], 'rarity': 'rare',
         'on_any_death_effect': {'type': 'buff_stats', 'target': 'self', 'health': 1, 'attack': 1},
         'image': 'blood_bile.png'},
        {'name': 'Necromancer', 'health': 3, 'attack': 2, 'type': 'Undead', 'keywords': ['cast'], 'rarity': 'rare',
         'cast_effect': {'type': 'summon_minion', 'target': 'summon_position', 'minion_name': 'Skeleton', 'health': 1, 'attack': 1},
         'image': 'necromancer.png'},
        {'name': 'Wight', 'health': 2, 'attack': 2, 'type': 'Undead', 'keywords': ['poke', 'assault'], 'rarity': 'rare',
         'assault_effect': {'type': 'deal_damage', 'target': 'random_enemy', 'amount': 3, 'target_count': 2},
         'image': 'wight.png'},
        # Beast
        {'name': 'War Horse', 'health': 7, 'attack': 7, 'type': 'Beast', 'keywords': [], 'rarity': 'rare',
         'image': 'war_horse.png'},
        {'name': 'Bear', 'health': 4, 'attack': 4, 'type': 'Beast', 'keywords': ['multi_attack'], 'rarity': 'rare',
         'multi_attack_count': 1,
         'image': 'bear.png'},
        {'name': 'Ram', 'health': 2, 'attack': 4, 'type': 'Beast', 'keywords': ['poke'], 'rarity': 'rare',
         'image': 'ram.png'},

        # Fey
        {'name': 'Dryad', 'health': 3, 'attack': 1, 'type': 'Fey', 'keywords': ['cast'], 'rarity': 'rare',
         'cast_effect': {'type': 'summon_minion', 'target': 'summon_position', 'minion_name': 'Thorn', 'health': 2, 'attack': 0},
         'image': 'dryad.png'},
        {'name': 'Boggart', 'health': 5, 'attack': 0, 'type': 'Fey', 'keywords': ['cast'], 'rarity': 'rare',
         'cast_effect': {'type': 'modify_fatigue', 'amount': 20},
         'image': 'boggart.png'},
        {'name': 'Kelpie', 'health': 3, 'attack': 4, 'type': 'Fey', 'keywords': ['assault'], 'rarity': 'rare',
         'assault_effect': {'type': 'move_minion', 'target': 'defender', 'direction': 'right', 'distance': 1},
         'image': 'kelpie.png'},

        # Construct
        {'name': 'War Machine', 'health': 2, 'attack': 2, 'type': 'Construct', 'keywords': ['assault'], 'rarity': 'rare',
         'assault_effect': {'type': 'deal_aoe_damage', 'target': 'all_enemies', 'amount': 1},
         'image': 'war_machine.png'},
        {'name': 'Tally Keeper', 'health': 6, 'attack': 0, 'type': ['Human', 'Construct'], 'keywords': ['on_any_cast'], 'rarity': 'rare',
         'on_any_cast_effect': {'type': 'deal_damage', 'target': 'trigger_source', 'amount': 2},
         'image': 'tally_keeper.png'},
        {'name': 'Clockwork', 'health': 2, 'attack': 2, 'type': 'Construct', 'keywords': ['rage'], 'rarity': 'rare',
         'rage_effect': {'type': 'buff_stats', 'target': 'self', 'health': 1, 'attack': 1},
         'image': 'clockwork.png'},

        # Cult
        {'name': 'Fanatic', 'health': 4, 'attack': 0, 'type': 'Cult', 'keywords': ['rage'], 'rarity': 'rare',
         'rage_effect': {'type': 'buff_stats', 'target': 'self', 'attack': 3},
         'image': 'fanatic.png'},
        {'name': 'Devote', 'health': 1, 'attack': 1, 'type': 'Cult', 'keywords': ['sacrifice'], 'rarity': 'rare',
         'sacrifice_effect': {'type': 'redirect_death', 'condition': 'higher_stats'},
         'image': 'devote.png'},

        # Meat Packaging Plant - Multi-faction: Cult + Construct
        {'name': 'Meat Packaging Plant', 'health': 10, 'attack': 0, 'type': ['Cult', 'Construct'], 'keywords': ['cant_attack', 'cast'], 'rarity': 'rare',
         'cast_effect': {
             'type': 'conditional',
             'condition': {
                 'type': 'has_left_ally'
             },
             'then_effect': [
                 {
                     'type': 'destroy_minion',
                     'target': 'left_ally',
                     'save_stats': True,
                     'stat_ratio': 0.5
                 },
                 {
                     'type': 'summon_minion',
                     'minion_name': 'Meat Cube',
                     'summon_count': 2,
                     'use_saved_stats': True,
                     'queue_individual': True
                 }
             ],
             'else_effect': {
                 'type': 'deal_damage',
                 'target': 'self',
                 'amount': 0
             }
         },
         'image': 'meat_packaging_plant.png'},

        # Gravebomb - 4/4: Death Toll: Deal 4 damage to random enemy
        {'name': 'Gravebomb', 'health': 4, 'attack': 4, 'type': ['Undead', 'Construct'], 'keywords': ['death_toll'], 'rarity': 'epic',
         'death_toll_effect': {
             'type': 'deal_damage',
             'target': 'random_enemy',
             'amount': 4
         },
         'image': 'Gravebomb.png'},
    ],
    3: [
        # Updated Shinobi with Hide, Leap, and attack on start of combat
        {'name': 'Shinobi', 'health': 7, 'attack': 7, 'type': 'Human', 'keywords': ['hide', 'leap', 'assault', 'start_of_combat'], 'rarity': 'epic',
         'hide_count': 2,
         'leap_distance': 1,
         'start_of_combat_effect': {
             'type': 'conditional',
             'condition': {
                 'type': 'is_position',
                 'target': 'self',
                 'position': 'leftmost'
             },
             'then_effect': [
                 {
                     'type': 'grant_keyword',
                     'target': 'self',
                     'keyword': 'poke'
                 },
                 {
                     'type': 'attack_target'
                 }
             ]
         },
         'assault_effect': {
             'type': 'conditional',
             'condition': {
                 'check_type': 'compound',
                 'operator': 'AND',
                 'checks': [
                     {
                         'type': 'is_position',
                         'target': 'self',
                         'position': 'rightmost'
                     },
                     {
                         'type': 'not_has_keyword',
                         'target': 'self',
                         'keyword': 'cleave'
                     }
                 ]
             },
             'then_effect': {
                 'type': 'grant_keyword',
                 'target': 'self',
                 'keyword': 'cleave',
                 'keyword_data': {'amount': 1}
             }
         },
         'image': 'shinobi.png'},

        # Undead
        # Accursed - Rich, Can't retaliate 4/4: On damage: gain 2 gold
        {'name': 'Accursed', 'health': 4, 'attack': 4, 'type': 'Undead', 'keywords': ['rich', 'cant_retaliate', 'on_damage', 'start_of_combat'], 'rarity': 'epic',
         'on_damage_effect': {'type': 'modify_gold', 'amount': 2},
         'start_of_combat_effect': {'type': 'rich_buff', 'target': 'self'},
         'image': 'accursed.png'},

        # Devouring Smog - 12/0: Hide 3, Cast: Deal 2 damage to all non-undead
        {'name': 'Devouring Smog', 'health': 12, 'attack': 0, 'type': 'Undead', 'keywords': ['hide', 'cast'], 'rarity': 'epic',
         'hide_count': 3,
         'cast_effect': {
             'type': 'deal_aoe_damage',
             'target': 'all_enemies',
             'amount': 2,
             'exclude_type': 'Undead'
         },
         'image': 'devouring_smog.png'},
        # Cult
        {'name': 'Cabal', 'health': 6, 'attack': 4, 'type': 'Cult', 'keywords': ['multi_attack', 'cast', 'savage'], 'rarity': 'epic',
         'multi_attack_count': 3,
         'cast_effect': {
             'type': 'deal_damage',
             'target': 'random_enemy',
             'amount': 1
         },
         'image': 'Cabal.png'},

        # Emissary - 10/1: Savage
        {'name': 'Emissary', 'health': 10, 'attack': 1, 'type': 'Cult', 'keywords': ['savage'], 'rarity': 'epic',
         'image': 'emissary.png'},

        # Bishop - 9/3: Ignoble (Can't take combat damage), Can't attack, Guard
        {'name': 'Bishop', 'health': 9, 'attack': 3, 'type': 'Cult', 'keywords': ['ignoble', 'cant_attack', 'guard'], 'rarity': 'epic',
         'image': 'bishop.png'},

        # Construct
        {'name': 'Dominus', 'health': 7, 'attack': 7, 'type': 'Construct', 'keywords': ['cant_attack', 'fatigue_immune'], 'rarity': 'epic',
         'image': 'Dominus.png'},

        # Beast
        {'name': 'Paper Tiger', 'health': 4, 'attack': 5, 'type': 'Beast', 'keywords': ['hide', 'poke', 'leap'], 'rarity': 'epic',
         'hide_count': 3,
         'leap_distance': 1,
         'image': 'paper_tiger.png'},

        {'name': 'Queen Bee', 'health': 30, 'attack': 3, 'type': 'Beast', 'keywords': ['start_of_combat'], 'rarity': 'epic',
         'start_of_combat_effect': {
             'type': 'divide_attack',
             'target': 'self',
             'divisor': 3
         },
         'image': 'queen_bee.png'},

        # Mixed faction minion (Human + Beast)
        {'name': 'Houndmaster', 'health': 4, 'attack': 4, 'type': ['Human', 'Beast'], 'keywords': ['cast'], 'rarity': 'epic',
         'cast_effect': {
             'type': 'conditional',
             'condition': {
                 'type': 'has_minion_named',
                 'target': 'all_allies',
                 'minion_name': 'Hound'
             },
             'then_effect': {
                 'type': 'attack_target',
                 'attacker': 'condition_found_minion',
                 'target_minion': None
             },
             'else_effect': {
                 'type': 'summon_minion',
                 'minion_name': 'Hound',
                 'health': 1,
                 'attack': 2,
                 'summon_count': 1
             }
         },
         'image': 'houndmaster.png'},

        # NEW FEY MINIONS
        # Alp - 5/0: Cast: Give a random enemy stun 1, then deal 3 damage to all stunned enemies
        {'name': 'Alp', 'health': 5, 'attack': 0, 'type': 'Fey', 'keywords': ['cast'], 'rarity': 'epic',
         'cast_effect': [
             {
                 'type': 'apply_stun',
                 'target': 'random_enemy',
                 'stun_amount': 1
             },
             {
                 'type': 'deal_aoe_damage',
                 'target': 'all_enemies',
                 'amount': 3,
                 'target_filters': [
                     {
                         'type': 'has_keyword',
                         'target': 'target_minion',
                         'keyword': 'stun'
                     }
                 ]
             }
         ],
         'image': 'alp.png'},

        # Tooth Fairy - 1/3: Poke, Assault: Decrease target's attack by 3, if 0 or less stun them
        {'name': 'Tooth Fairy', 'health': 1, 'attack': 3, 'type': 'Fey', 'keywords': ['poke', 'assault'], 'rarity': 'epic',
         'assault_effect': [
             {
                 'type': 'debuff_stats',
                 'target': 'defender',
                 'attack': -3
             },
             {
                 'type': 'conditional',
                 'condition': {
                     'type': 'attack_at_most',
                     'target': 'defender',
                     'value': 0
                 },
                 'then_effect': {
                     'type': 'apply_stun',
                     'target': 'defender',
                     'stun_amount': 1
                 }
             }
         ],
         'image': 'tooth_fairy.png'},

        # Brownie - 2/4: Cast: All friendly minions gain +2/+0
        {'name': 'Brownie', 'health': 2, 'attack': 4, 'type': 'Fey', 'keywords': ['cast'], 'rarity': 'epic',
         'cast_effect': {
             'type': 'buff_stats',
             'target': 'all_allies',
             'attack': 2,
             'health': 0
         },
         'image': 'brownie.png'},

        # NEW TIER 3 MINIONS

        # Ballista - 14/14: Can't retaliate, Cast: Deal 14 damage + gain 1 stun
        {'name': 'Ballista', 'health': 14, 'attack': 14, 'type': 'Construct', 'keywords': ['cant_retaliate', 'cast'], 'rarity': 'epic',
         'cast_effect': [
             {
                 'type': 'deal_damage',
                 'target': 'random_enemy',
                 'amount': 14
             },
             {
                 'type': 'apply_stun',
                 'target': 'self',
                 'stun_amount': 1
             }
         ],
         'image': 'ballista.png'},

        # Gangster - 5/5: Start of combat: Lose 3 gold, summon tier 1 minion with guard
        # Assault: If there's a minion with guard, make it attack
        {'name': 'Gangster', 'health': 5, 'attack': 5, 'type': 'Human',
         'keywords': ['start_of_combat', 'assault'], 'rarity': 'epic',
         'start_of_combat_effect': [
             {
                 'type': 'modify_gold',
                 'amount': -3
             },
             {
                 'type': 'summon_minion',
                 'summon_criteria': {
                     'tier': 1,  # Select from tier 1
                     'pool_modifiers': None  # Use zone's pool modifiers
                 },
                 'summon_count': 1,
                 'keywords': ['guard']  # Add guard keyword to summoned minion
             }
         ],
         'assault_effect': {
             'type': 'conditional',
             'condition': {
                 'type': 'has_minion_with_keyword',
                 'target': 'all_allies',
                 'keyword': 'guard'
             },
             'then_effect': {
                 'type': 'attack_target',
                 'attacker': 'condition_found_minion',
                 'target_minion': None
             }
         },
         'image': 'gangster.png'},

        # Warlord - 6/6: Rage: If attacker is friendly tier 1, they gain 3/3 and this gains 1/1
        {'name': 'Warlord', 'health': 6, 'attack': 6, 'type': 'Human', 'keywords': ['rage'], 'rarity': 'epic',
         'rage_effect': {
             'type': 'conditional',
             'condition': {
                 'check_type': 'compound',
                 'checks': [
                     {'type': 'is_ally', 'target': 'trigger_source'},
                     {'type': 'is_tier', 'target': 'trigger_source', 'tier': 1}
                 ],
                 'operator': 'AND'
             },
             'then_effect': [
                 {
                     'type': 'buff_stats',
                     'target': 'trigger_source',
                     'attack': 3,
                     'health': 3
                 },
                 {
                     'type': 'buff_stats',
                     'target': 'self',
                     'attack': 1,
                     'health': 1
                 }
             ]
         },
         'image': 'warlord.png'},

        # Amalgam - 5/5: Imperfect (can be combined unlimited times)
        {'name': 'Amalgam', 'health': 5, 'attack': 5, 'type': 'Cult', 'keywords': ['imperfect'], 'rarity': 'epic',
         'image': 'amalgam.png'},

        # Basilisk - 3/8: Poke, Assault: If defender has 3 or less attack, destroy it
        {'name': 'Basilisk', 'health': 3, 'attack': 8, 'type': 'Beast', 'keywords': ['poke', 'assault'], 'rarity': 'epic',
         'assault_effect': {
             'type': 'conditional',
             'condition': {
                 'type': 'attack_at_most',
                 'target': 'defender',
                 'value': 3
             },
             'then_effect': {
                 'type': 'destroy_minion',
                 'target': 'defender'
             }
         },
         'image': 'basilisk.png'}
    ],
    4: [
        # Destroyer - Moved from tier 3 to tier 4 for balance
        {'name': 'Destroyer', 'health': 14, 'attack': 2, 'type': 'Construct', 'keywords': ['poke', 'rage'], 'rarity': 'legendary',
         'rage_effect': {
             'type': 'conditional',
             'condition': {
                 'check_type': 'compound',
                 'checks': [
                     {'type': 'is_enemy', 'target': 'trigger_source'},
                     {'type': 'not_name', 'target': 'trigger_source', 'minion_name': 'Destroyer'}
                 ],
                 'operator': 'AND'
             },
             'then_effect': {
                 'type': 'attack_target',
                 'target_minion': 'trigger_source'
             }
         },
         'image': 'destroyer.png'},

        # Tier 4 Human minions
        {'name': 'King', 'health': 1, 'attack': 1, 'type': 'Human', 'keywords': ['nobility', 'rich', 'start_of_combat'], 'rarity': 'legendary',
         'start_of_combat_effect': {'type': 'rich_buff', 'target': 'self'},
         'image': 'king.png'},

        {'name': 'Sellsword', 'health': 6, 'attack': 2, 'type': 'Human', 'keywords': ['poke', 'savage', 'multi_attack'], 'rarity': 'legendary',
         'multi_attack_count': 1,
         'image': 'sellsword.png'},

        # Siegfried - 4/10: Poke, Assault: Gain 30 attack
        {'name': 'Siegfried', 'health': 4, 'attack': 10, 'type': 'Dragon Slayer', 'keywords': ['poke', 'assault'], 'rarity': 'legendary',
         'assault_effect': {
             'type': 'buff_stats',
             'target': 'self',
             'attack': 30,
             'health': 0
         },
         'image': 'siegfried.png'},

        # Tier 4 Cult minion
        {'name': 'Lookalike', 'health': 4, 'attack': 4, 'type': 'Cult', 'keywords': ['assault'], 'rarity': 'legendary',
         'assault_trigger_count': 0,
         'assault_effect': {
             'type': 'conditional',
             'condition': {
                 'type': 'trigger_count_equals',
                 'target': 'self',
                 'count': 2
             },
             'then_effect': {
                 'type': 'transform_all_minions',
                 'target': 'all_minions',
                 'transform_to': 'self'
             }
         },
         'image': 'lookalike.png'},

        # Reprocessor - 6/6: On_ally_death: If it's not a cultist summon a 1/1 cultist
        {'name': 'Reprocessor', 'health': 6, 'attack': 6, 'type': 'Cult', 'keywords': ['on_any_death'], 'rarity': 'legendary',
         'on_any_death_effect': {
             'type': 'conditional',
             'condition': {
                 'check_type': 'compound',
                 'checks': [
                     {'type': 'is_ally', 'target': 'trigger_dying'},
                     {'type': 'not_name', 'target': 'trigger_dying', 'minion_name': 'Cultist'}
                 ],
                 'operator': 'AND'
             },
             'then_effect': {
                 'type': 'summon_minion',
                 'minion_name': 'Cultist',
                 'health': 1,
                 'attack': 1,
                 'summon_count': 1
             }
         },
         'image': 'reprocessor.png'},

        # Tier 4 Undead minions
        {'name': 'Demilich', 'health': 12, 'attack': 12, 'type': 'Undead',
         'keywords': ['cant_attack', 'obliterate'], 'rarity': 'legendary',
         'image': 'demilich.png'},

        {'name': 'Possessed', 'health': 1, 'attack': 6, 'type': 'Undead', 'keywords': ['death_toll'],
         'rarity': 'legendary',
         'death_toll_effect': {
             'type': 'grant_effect_to_minion',
             'target': 'random_ally',
             'exclude_name': 'Possessed',
             'effect_type': 'death_toll_effect',
             'effect_data': {
                 'type': 'summon_minion',
                 'minion_name': 'Possessed',
                 'health': 1,
                 'attack': 6
             }
         },
         'image': 'possessed.png'},

        # Dullahan - 10/10: Guard, Start of Combat: Summon Dullahan's Head
        {'name': 'Dullahan', 'health': 10, 'attack': 10, 'type': 'Undead', 'keywords': ['guard', 'start_of_combat'], 'rarity': 'legendary',
         'start_of_combat_effect': {
             'type': 'summon_minion',
             'minion_name': "Dullahan's Head",
             'health': 3,
             'attack': 0,
             'summon_count': 1,
             'position': 'right'
         },
         'image': 'dullahan.png'},

        # Dullahan's Head - 3/0: Nobility, Can't Attack, Cast: If no Dullahan, summon one, else make it attack
        {'name': "Dullahan's Head", 'health': 3, 'attack': 0, 'type': 'Undead', 'keywords': ['nobility', 'cant_attack', 'cast'], 'rarity': 'legendary',
         'cast_effect': {
             'type': 'conditional',
             'condition': {
                 'type': 'has_minion_named',
                 'target': 'all_allies',
                 'minion_name': 'Dullahan'
             },
             'then_effect': {
                 'type': 'attack_target',
                 'attacker': 'condition_found_minion',
                 'target_minion': None
             },
             'else_effect': {
                 'type': 'summon_minion',
                 'minion_name': 'Dullahan',
                 'health': 10,
                 'attack': 10,
                 'summon_count': 1
             }
         },
         'summon_only': True,
         'image': 'dullahans_head.png'},

        # Bogeyman - 8/8: Hide 2, On Ally Hide Lost: Stun all other minions for 2
        {'name': 'Bogeyman', 'health': 8, 'attack': 8, 'type': 'Undead', 'keywords': ['hide', 'on_hide_lost'], 'rarity': 'legendary',
         'hide_count': 2,
         'on_hide_lost_effect': {
             'type': 'apply_stun',
             'target': 'all_minions',
             'exclude_self': True,
             'stun_amount': 2
         },
         'image': 'bogeyman.png'},

        # Tier 4 Mixed faction minions
        # Old Cat Lady - Cult + Beast
        {'name': 'Old Cat Lady', 'health': 6, 'attack': 1, 'type': ['Cult', 'Beast'], 'keywords': ['assault', 'on_any_death'], 'rarity': 'legendary',
         'assault_effect': {
             'type': 'summon_minion',
             'minion_name': 'Cat',
             'health': 1,
             'attack': 1,
             'summon_count': 1,
             'keywords': ['guard'],
             'inherit_band_id': False
         },
         'on_any_death_effect': {
             'type': 'conditional',
             'condition': {
                 'check_type': 'compound',
                 'checks': [
                     {'type': 'is_name', 'target': 'trigger_dying', 'minion_name': 'Cat'},
                     {'type': 'is_ally', 'target': 'trigger_dying'}
                 ],
                 'operator': 'AND'
             },
             'then_effect': {
                 'type': 'permanent_stat_gain',
                 'target': 'self',
                 'scope': 'band_only',
                 'health': 1,
                 'attack': 1
             }
         },
         'image': 'old_cat_lady.png'},

        {'name': 'Shock Trooper', 'health': 5, 'attack': 5, 'type': ['Cult', 'Construct', 'Human'], 'keywords': ['poke', 'assault'], 'rarity': 'legendary',
         'assault_effect': {
             'type': 'apply_stun',
             'target': 'defender',
             'stun_amount': 1
         },
         'image': 'shock_trooper.png'},

        # NEW FEY MINION
        # Nymph - 7/2: Cast: Remove all stun from friendly minions, add it to random enemy
        {'name': 'Nymph', 'health': 7, 'attack': 2, 'type': 'Fey', 'keywords': ['cast'], 'rarity': 'legendary',
         'cast_effect': {
             'type': 'transfer_stun',
             'from_targets': 'all_allies',
             'to_target': 'random_enemy'
         },
         'image': 'nymph.png'},

        # NEW TIER 4 MINIONS

        # Railway Cannon - 18/8: Leap 1, Cast: Deal damage (scales +4 each cast)
        {'name': 'Railway Cannon', 'health': 18, 'attack': 8, 'type': 'Construct', 'keywords': ['leap', 'cast'], 'rarity': 'legendary',
         'leap_distance': 1,
         'cast_damage_current': 4,
         'cast_damage_increment': 4,
         'cast_effect': {
             'type': 'scaling_damage',
             'target': 'random_enemy',
             'base_amount': 4,
             'increment': 4,
             'tracker_field': 'cast_damage_current'
         },
         'image': 'railway_cannon.png'},

        # Railway Signal - 8/2: Can't attack, On_any_leap: If friendly, give them 4/4
        {'name': 'Railway Signal', 'health': 8, 'attack': 2, 'type': 'Construct',
         'keywords': ['cant_attack', 'on_any_leap'], 'rarity': 'legendary',
         'on_any_leap_effect': {
             'type': 'conditional',
             'condition': {
                 'type': 'is_ally',
                 'target': 'trigger_source'
             },
             'then_effect': {
                 'type': 'buff_stats',
                 'target': 'trigger_source',
                 'attack': 4,
                 'health': 4
             }
         },
         'image': 'railway_signal.png'},

        # Banshee - 7/7: Poke, Start of combat: deal 1 damage to all enemies, On_any_death: gain 2/2
        {'name': 'Banshee', 'health': 7, 'attack': 7, 'type': ['Fey', 'Undead'], 'keywords': ['poke', 'start_of_combat', 'on_any_death'], 'rarity': 'legendary',
         'start_of_combat_effect': {
             'type': 'deal_aoe_damage',
             'target': 'all_enemies',
             'amount': 1,
             'max_targets': 999
         },
         'on_any_death_effect': {
             'type': 'buff_stats',
             'target': 'self',
             'attack': 2,
             'health': 2
         },
         'image': 'banshee.png'},

        # Thunderbird - 9/9: Poke, Fast, Savage
        {'name': 'Thunderbird', 'health': 9, 'attack': 9, 'type': 'Beast', 'keywords': ['poke', 'fast', 'savage'], 'rarity': 'legendary',
         'image': 'thunderbird.png'},

        # Shaman - 5/8: Cast: Trigger a random friendly start of combat
        {'name': 'Shaman', 'health': 5, 'attack': 8, 'type': ['Beast', 'Fey'], 'keywords': ['cast'], 'rarity': 'legendary',
         'cast_effect': {
             'type': 'trigger_start_of_combat',
             'target': 'all_allies',
             'exclude_self': True
         },
         'image': 'shaman.png'},

        # Frog Prince - 1/1: Nobility, Start of combat: Gain 1 stun (to itself), Leap 10
        # NOTE: "For each minion leaped over gain 10/10" functionality not yet implemented
        {'name': 'Frog Prince', 'health': 1, 'attack': 1, 'type': 'Beast',
         'keywords': ['nobility', 'start_of_combat', 'leap', 'on_any_leap'],
         'rarity': 'legendary',
         'leap_distance': 10,
         'start_of_combat_effect': {
             'type': 'apply_stun',
             'target': 'self',
             'stun_amount': 1
         },
         'on_any_leap_effect': {
             'type': 'conditional',
             'condition': {
                 'type': 'is_self',
                 'target': 'trigger_source'  # Is leaping_minion the same as acting_minion?
             },
             'then_effect': {
                 'type': 'buff_stats',
                 'target': 'self',
                 'attack': 10,
                 'health': 10,
                 'multiply_by_context': 'minions_jumped'
             }
         },
         'image': 'frog_prince.png'},

        # Rust Beetle - 3/3 Beast: Assault: Give defender 'can't retaliate', if they already have it give them 'can't attack'
        {'name': 'Rust Beetle', 'health': 3, 'attack': 3, 'type': 'Beast',
         'keywords': ['assault'],
         'rarity': 'epic',
         'assault_effect': {
             'type': 'conditional',
             'condition': {
                 'type': 'has_keyword',
                 'target': 'defender',
                 'keyword': 'cant_retaliate'
             },
             'then_effect': {
                 'type': 'grant_keyword',
                 'target': 'defender',
                 'keyword': 'cant_attack'
             },
             'else_effect': {
                 'type': 'grant_keyword',
                 'target': 'defender',
                 'keyword': 'cant_retaliate'
             }
         },
         'image': 'rust_beetle.png'},

        # Werewolf - 6/6 Beast: Assault: Gain 3/3, On_any_leap: Attack
        {'name': 'Werewolf', 'health': 6, 'attack': 6, 'type': 'Beast',
         'keywords': ['assault', 'on_any_leap'],
         'rarity': 'epic',
         'assault_effect': {
             'type': 'buff_stats',
             'target': 'self',
             'health': 3,
             'attack': 3
         },
         'on_any_leap_effect': {
             'type': 'conditional',
             'condition': {
                 'type': 'is_ally',
                 'target': 'trigger_source'  # leaping_minion
             },
             'then_effect': {
                 'type': 'attack_target',
                 'attacker': 'self',
                 'target_minion': None  # Auto-select
             }
         },
         'image': 'werewolf.png'},
    ],

    5: [
        # Quasimodo - 8/0 Non-typed: Nobility, Can't attack, On_any_death_toll: If friendly it triggers 1 more time
        {'name': 'Quasimodo', 'health': 8, 'attack': 0, 'type': 'None',
         'keywords': ['nobility', 'cant_attack', 'on_any_death_toll'],
         'rarity': 'legendary',
         'on_any_death_toll_effect': {
             'type': 'conditional',
             'condition': {
                 'check_type': 'compound',
                 'checks': [
                     {'type': 'is_ally', 'target': 'trigger_source'},
                     {'type': 'not_additional_trigger'}
                 ],
                 'operator': 'AND'
             },
             'then_effect': {
                 'type': 'trigger_death_toll',
                 'target': 'trigger_source',
                 'exclude_self': False
             }
         },
         'image': 'quasimodo.png'},

        # Bell Ringer - 1/1 Human: Ring 2
        {'name': 'Bell Ringer', 'health': 1, 'attack': 1, 'type': 'Human',
         'keywords': ['ring'],
         'ring_count': 2,
         'rarity': 'legendary',
         'image': 'bell_ringer.png'},

        # Vestige - 1/1 Ethereal [Last]: Survives lethal if not the last friendly minion (and only ethereal)
        {'name': 'Vestige', 'health': 1, 'attack': 1, 'type': 'None',
         'keywords': ['ethereal'],
         'rarity': 'common',
         'image': 'vestige.png'},
    ]
}


# ==================== BOSS MINIONS ====================
# Special boss minions for The Great Hunt event (Beast Wildlands)
# These are NOT part of the normal tier pool - used only for boss encounters

BOSS_MINIONS = {
    # === THE DIRE PACK ===
    'Alpha Direwolf': {
        'name': 'Alpha Direwolf', 'health': 2, 'attack': 2, 'type': 'Beast',
        'keywords': ['assault', 'on_any_death'], 'rarity': 'boss',
        'assault_effect': {'type': 'buff_stats', 'target': 'self', 'attack': 4, 'health': 0},
        'on_any_death_effect': {'type': 'buff_stats', 'target': 'self', 'attack': 0, 'health': 4},
        'image': 'alpha_direwolf.png'
    },
    'Dire Wolf': {
        'name': 'Dire Wolf', 'health': 3, 'attack': 3, 'type': 'Beast',
        'keywords': ['savage'], 'rarity': 'boss',
        'image': 'dire_wolf.png'
    },

    # === CONGREGATION ===
    'Congregation': {
        'name': 'Congregation', 'health': 30, 'attack': 0, 'type': 'Cult',
        'keywords': ['cant_attack', 'cast'], 'rarity': 'boss',
        'cast_count': 2,  # Casts twice per turn
        'cast_effect': {'type': 'summon_minion', 'target': 'summon_position', 'minion_name': 'Cultist', 'health': 1, 'attack': 1, 'summon_count': 2},
        'image': 'congregation.png'
    },

    # === CHAINED BEAST ===
    'Chain': {
        'name': 'Chain', 'health': 12, 'attack': 2, 'type': 'Beast',
        'keywords': ['hide'], 'rarity': 'boss',
        'hide_count': 2,
        'image': 'chain.png'
    },
    'Chained Beast': {
        'name': 'Chained Beast', 'health': 22, 'attack': 22, 'type': 'Beast',
        'keywords': ['ethereal_left', 'leap'], 'rarity': 'boss',
        'leap_distance': 1,
        'image': 'chained_beast.png'
    },

    # === BEHEMOTH ===
    'Ancient Behemoth': {
        'name': 'Ancient Behemoth', 'health': 40, 'attack': 12, 'type': 'Beast',
        'keywords': ['guard', 'on_damage'], 'rarity': 'boss',
        'on_damage_effect': {'type': 'deal_aoe_damage', 'target': 'all_enemies', 'amount': 2},
        'image': 'ancient_behemoth.png'
    },

    # === VENOMSPAWN ===
    'Broodmother': {
        'name': 'Broodmother', 'health': 20, 'attack': 6, 'type': 'Beast',
        'keywords': ['death_toll'], 'rarity': 'boss',
        'death_toll_effect': {'type': 'summon_minion', 'target': 'summon_position', 'minion_name': 'Venomling', 'summon_count': 2},
        'image': 'broodmother.png'
    },
    'Venomling': {
        'name': 'Venomling', 'health': 2, 'attack': 2, 'type': 'Beast',
        'keywords': ['death_toll'], 'rarity': 'boss',
        'death_toll_effect': {'type': 'deal_damage', 'target': 'random_enemy', 'amount': 3},
        'image': 'venomling.png'
    },

    # === GREATER POSSESSED ===
    'Greater Possessed': {
        'name': 'Greater Possessed', 'health': 1, 'attack': 6, 'type': 'Undead',
        'keywords': ['death_toll', 'cast'], 'rarity': 'boss',
        'death_toll_effect': {
            'type': 'grant_effect_to_minion',
            'target': 'random_ally',
            'exclude_name': 'Greater Possessed',
            'effect_type': 'death_toll_effect',
            'effect_data': {
                'type': 'summon_minion',
                'minion_name': 'Greater Possessed',
                'health': 1,
                'attack': 6,
                'copy_cast_from_self': True  # Also grants the cast effect
            }
        },
        'cast_effect': {
            'type': 'destroy_and_absorb',
            'target': 'self',
            'transfer_stats_to': 'Greater Possessed'
        },
        'image': 'greater_possessed.png'
    },
}


def get_boss_minion(name):
    """Get a boss minion template by name

    Args:
        name: Name of the boss minion

    Returns:
        Copy of the boss minion template, or None if not found
    """
    if name in BOSS_MINIONS:
        return BOSS_MINIONS[name].copy()
    return None


def get_minion_image_path(minion, variant='original'):
    """Get the image path for a minion, returns None if no image

    Args:
        minion: Minion dict with 'image' key
        variant: Image variant - 'original', 'alt_1', 'alt_2', 'alt_3'

    Returns:
        Path string like 'images/original/cat.png' or None
    """
    image_filename = minion.get('image')
    if image_filename:
        return f'images/{variant}/{image_filename}'
    return None


def get_all_image_variants(minion_id):
    """Get all available image variants for a minion

    Returns list of dicts with variant info.
    Handles case-insensitive matching and spaces in filenames.
    """
    import os

    variants = []
    variant_folders = ['original', 'alt_1', 'alt_2', 'alt_3']
    base_dir = os.path.dirname(__file__)

    for variant in variant_folders:
        variant_dir = os.path.join(base_dir, 'images', variant)

        if not os.path.exists(variant_dir):
            continue

        # Find matching file (case-insensitive, handle spaces/underscores)
        actual_filename = None
        minion_id_normalized = minion_id.lower().replace(' ', '_').replace('-', '_')

        for filename in os.listdir(variant_dir):
            if not filename.endswith('.png'):
                continue
            # Normalize filename for comparison
            file_base = filename[:-4].lower().replace(' ', '_').replace('-', '_')
            if file_base == minion_id_normalized:
                actual_filename = filename
                break

        if actual_filename:
            path = f'images/{variant}/{actual_filename}'
            variants.append({
                'variant': variant,
                'path': path,
                'label': 'Original' if variant == 'original' else f'Alt {variant.split("_")[1]}',
                'display_name': 'Original' if variant == 'original' else f'Alt #{variant.split("_")[1]}'
            })

    return variants


def get_enhanced_keyword_tooltip(minion, keyword):
    """Get enhanced tooltip combining general keyword info with minion-specific effect"""
    from keywords import KEYWORDS

    # Get general keyword info
    keyword_info = KEYWORDS.get(keyword.lower())
    if not keyword_info:
        return f"{keyword}: Unknown keyword"

    # SPECIAL CASE: Skip start_of_combat if minion has rich or fast
    # (rich/fast are wrappers and will display the start_of_combat effect themselves)
    minion_keywords = minion.get('keywords', [])
    if keyword.lower() == 'start_of_combat' and ('rich' in minion_keywords or 'fast' in minion_keywords):
        return None  # Signal to skip this keyword

    # Start with general description
    tooltip = f"{keyword_info['name']}: {keyword_info['description']}"

    # SPECIAL CASE: Rich and Fast are wrappers around Start of Combat
    # Display as "Rich: Start of Combat: <effect>" instead of just the generic description
    if keyword.lower() in ['rich', 'fast'] and 'start_of_combat_effect' in minion:
        start_of_combat_effect = minion['start_of_combat_effect']
        effect_desc = format_minion_specific_effect(start_of_combat_effect, minion.get('golden', False))
        return f"{keyword_info['name']}: Start of Combat: {effect_desc}"

    # Add multi-attack count if applicable
    if keyword.lower() == 'multi_attack':
        multi_count = minion.get('multi_attack_count', 1)
        if minion.get('golden', False):
            multi_count *= 2
        tooltip += f"<br>Attacks {multi_count} additional time(s)"
        return tooltip

    # Add stun information if applicable
    if keyword.lower().startswith('stun'):
        # During combat, use stun_remaining; outside combat, use stun_count
        stun_count = minion.get('stun_remaining', minion.get('stun_count', 1))
        tooltip += f"<br>Skips {stun_count} attack(s)"
        return tooltip

    # Add hide information
    if keyword.lower() == 'hide':
        # During combat, use hide_remaining; outside combat, use hide_count
        hide_count = minion.get('hide_remaining', minion.get('hide_count', 1))
        tooltip += f"<br>Can't be attacked until {hide_count} attack(s) or is only target"
        return tooltip

    # Add leap information
    if keyword.lower() == 'leap':
        leap_distance = minion.get('leap_distance', 1)
        if minion.get('golden', False):
            leap_distance *= 2
        tooltip += f"<br>Moves right {leap_distance} space(s) when attacking"
        return tooltip

    # Add minion-specific effect if available
    effect_key = f"{keyword.lower()}_effect"
    if effect_key in minion:
        effect_data = minion[effect_key]
        specific_effect = format_minion_specific_effect(effect_data, minion.get('golden', False))
        if specific_effect:
            tooltip += f"<br>Effect: {specific_effect}"

    return tooltip


def format_minion_specific_effect(effect_data, is_golden=False):
    """Format minion-specific effect data into readable text, accounting for golden doubling"""
    if not effect_data:
        return ""

    # Handle list of effects (like Meat Packaging Plant)
    if isinstance(effect_data, list):
        effect_parts = []
        for effect in effect_data:
            part = format_minion_specific_effect(effect, is_golden)
            if part:
                effect_parts.append(part)
        return " then ".join(effect_parts)

    if not isinstance(effect_data, dict):
        return ""

    effect_type = effect_data.get('type', '')
    target = effect_data.get('target', '')

    # Apply golden doubling to displayed values
    multiplier = 2 if is_golden else 1
    amount = effect_data.get('amount', 0) * multiplier

    # Handle conditional effects
    if effect_type == 'conditional':
        condition = effect_data.get('condition', {})
        then_effect = effect_data.get('then_effect', {})
        else_effect = effect_data.get('else_effect')

        # Format condition
        condition_text = format_condition_text(condition, is_golden)

        # Format then effect
        then_text = format_minion_specific_effect(then_effect, is_golden)

        # Replace repeated target descriptions with "it" for better readability
        # This handles cases like "If the summoned minion is adjacent: Give the summoned minion +1 attack"
        # Should become: "If the summoned minion is adjacent: Give it +1 attack"
        trigger_phrases = [
            "the summoned minion",
            "the triggering minion",
            "the dying minion",
            "the killer",
            "the summoner",
            "the transformed minion",
            "the leaping minion",
            "the target",
            "the attacker",
            "the defender"
        ]

        for phrase in trigger_phrases:
            if phrase in condition_text.lower():
                # Check if this phrase also appears in then_text after "Give "
                give_pattern = f"Give {phrase}"
                if give_pattern in then_text:
                    then_text = then_text.replace(give_pattern, "Give it", 1)
                    break

        # Format else effect if present
        if else_effect:
            else_text = format_minion_specific_effect(else_effect, is_golden)
            return f"If {condition_text}: {then_text}, otherwise: {else_text}"
        else:
            return f"If {condition_text}: {then_text}"

    # Handle trigger context targets
    if target == 'trigger_source':
        target_desc = "the triggering minion"
    elif target == 'trigger_target':
        target_desc = "the trigger's target"
    elif target == 'trigger_killer':
        target_desc = "the killer"
    elif target == 'trigger_dying':
        target_desc = "the dying minion"
    elif target == 'trigger_summoned' or target == 'summoned_minion':
        target_desc = "the summoned minion"
    elif target == 'trigger_summoner':
        target_desc = "the summoner"
    elif target == 'trigger_transformed':
        target_desc = "the transformed minion"
    elif target == 'trigger_leaper':
        target_desc = "the leaping minion"
    elif target == 'lowest_health_enemy':
        target_desc = "the lowest health enemy"
    elif target == 'friendly_hound':
        target_desc = "a friendly Hound"
    elif target == 'friendly_dullahan':
        target_desc = "a friendly Dullahan"
    else:
        target_desc = target

    # Add new effect type descriptions
    if effect_type == 'transfer_stun':
        return f"Transfer all friendly stun to a random enemy"

    if effect_type == 'modify_gold':
        if amount > 0:
            return f"Gain {amount} gold"
        else:
            return f"Lose {abs(amount)} gold"

    if effect_type == 'rich_buff':
        if is_golden:
            return "Gain +2/+2 per gold at start of combat"
        return "Gain +1/+1 per gold at start of combat"

    if effect_type == 'divide_attack':
        divisor = effect_data.get('divisor', 3)
        return f"Divide attack by {divisor} (round down)"

    if effect_type == 'scaling_damage':
        base = effect_data.get('base_amount', 4) * multiplier
        increment = effect_data.get('increment', 4) * multiplier
        return f"Deal {base} damage (increases by {increment} each cast)"

    if effect_type == 'trigger_death_toll':
        count = effect_data.get('count', 1)
        if target == 'all_allies' or target == 'random_ally':
            return f"Trigger {count} random friendly death toll without killing them"
        return f"Trigger death toll on {target_desc} without killing them"

    if effect_type == 'make_minion_attack':
        return f"Make {target_desc} attack"

    if effect_type == 'has_friendly_minion_named':
        minion_name = effect_data.get('minion_name', 'unknown')
        return f"Check for friendly {minion_name}"

    if effect_type == 'has_minion_with_keyword':
        keyword = effect_data.get('keyword', 'unknown')
        return f"Check for friendly minion with {keyword}"

    if effect_type == 'transform_all_minions':
        return f"Transform all minions into copies of this"

    if effect_type == 'steal_cat_buffs':
        return f"Gain all friendly Cats' buffs"

    if effect_type == 'trigger_count_equals':
        count = effect_data.get('count', 0)
        return f"Check if triggered {count} times"

    if effect_type == 'buff_stats_per_leap':
        attack_buff = effect_data.get('attack', 0) * multiplier
        health_buff = effect_data.get('health', 0) * multiplier
        return f"Gain +{attack_buff}/+{health_buff} per minion leaped over"

    # Add chrono_cascade effect description
    if effect_type == 'chrono_cascade':
        return f"Make the next friendly minion with Cast cast immediately, then stun it for 1 attack"

    # Add immediate_attack effect description
    if effect_type == 'immediate_attack':
        attacker = effect_data.get('attacker', 'unknown')
        if attacker == 'trigger_summoned':
            return f"Make the summoned minion attack immediately"
        else:
            return f"Make {attacker} attack immediately"

    # Add buff_adjacent effect description (aura)
    if effect_type == 'buff_adjacent':
        attack_buff = effect_data.get('attack', 0) * multiplier
        health_buff = effect_data.get('health', 0) * multiplier
        buff_parts = []
        if attack_buff > 0:
            buff_parts.append(f"+{attack_buff} attack")
        if health_buff > 0:
            buff_parts.append(f"+{health_buff} health")
        return f"Adjacent allies have {', '.join(buff_parts)}"

    # Add destroy_minion effect description
    if effect_type == 'destroy_minion':
        stat_ratio = effect_data.get('stat_ratio', 1.0)
        if target == 'left_ally':
            return f"Destroy left ally (save {int(stat_ratio * 100)}% of stats)"
        else:
            return f"Destroy {target_desc} (save {int(stat_ratio * 100)}% of stats)"

    if effect_type == 'deal_damage':
        target_count = effect_data.get('target_count', 1) * multiplier
        if target_count > 1:
            return f"Deal {amount} damage to {target_count} {target_desc}s"
        elif target == 'defender':
            return f"Deal {amount} damage to the defender"
        elif target == 'random_enemy':
            return f"Deal {amount} damage to a random enemy"
        elif target == 'trigger_source':
            return f"Deal {amount} damage to the caster/attacker"
        elif target == 'trigger_target':
            return f"Deal {amount} damage to the spell's target"
        elif target == 'trigger_killer':
            return f"Deal {amount} damage to the killer"
        else:
            return f"Deal {amount} damage to {target_desc}"

    elif effect_type == 'deal_aoe_damage':
        max_targets = effect_data.get('max_targets', 1) * multiplier
        exclude_type = effect_data.get('exclude_type')
        target_filters = effect_data.get('target_filters')

        target_desc = ""
        if exclude_type:
            target_desc = f"all enemies except {exclude_type}"
        elif target_filters:
            # Check for stunned filter
            has_stun_filter = any(f.get('keyword') == 'stun' for f in target_filters if f.get('type') == 'has_keyword')
            if has_stun_filter:
                target_desc = "all stunned enemies"
            else:
                target_desc = "filtered enemies"
        elif max_targets >= 999:
            target_desc = "all enemies"
        else:
            target_desc = f"up to {max_targets} enemies"

        return f"Deal {amount} damage to {target_desc}"

    elif effect_type == 'heal':
        if target == 'random_ally':
            return f"Give a random ally {amount} health"
        else:
            return f"Give {target_desc} {amount} health"

    elif effect_type == 'heal_self':
        return f"Give self {amount} health"

    elif effect_type == 'buff_stats':
        attack_buff = effect_data.get('attack', 0) * multiplier
        health_buff = effect_data.get('health', 0) * multiplier
        buff_parts = []
        if attack_buff > 0:
            buff_parts.append(f"+{attack_buff} attack")
        if health_buff > 0:
            buff_parts.append(f"+{health_buff} health")

        if target == 'self':
            return f"Gain {', '.join(buff_parts)}"
        elif target == 'random_ally':
            return f"Give a random ally {', '.join(buff_parts)}"
        elif target == 'all_allies':
            return f"Give all allies {', '.join(buff_parts)}"
        elif target == 'trigger_target':
            return f"Give the spell's target {', '.join(buff_parts)}"
        elif target == 'trigger_summoned' or target == 'summoned_minion':
            return f"Give the summoned minion {', '.join(buff_parts)}"
        elif target == 'trigger_leaper':
            return f"Give the leaping minion {', '.join(buff_parts)}"
        else:
            return f"Give {target_desc} {', '.join(buff_parts)}"

    elif effect_type == 'buff_stats_tribe':
        tribe = effect_data.get('tribe', 'Unknown')
        attack_buff = effect_data.get('attack', 0) * multiplier
        health_buff = effect_data.get('health', 0) * multiplier
        buff_parts = []
        if attack_buff > 0:
            buff_parts.append(f"+{attack_buff} attack")
        if health_buff > 0:
            buff_parts.append(f"+{health_buff} health")
        return f"Give all friendly {tribe} minions {', '.join(buff_parts)}"

    elif effect_type == 'summon_minion':
        # Check for summon_criteria first (dynamic minion selection)
        summon_criteria = effect_data.get('summon_criteria')
        if summon_criteria:
            tier = summon_criteria.get('tier', 1)
            summon_count = effect_data.get('summon_count', 1) * multiplier
            keywords = effect_data.get('keywords', [])
            keywords_text = f" with {', '.join(keywords)}" if keywords else ""
            if summon_count > 1:
                return f"Summon {summon_count} random tier {tier} minions{keywords_text}"
            else:
                return f"Summon a random tier {tier} minion{keywords_text}"

        minion_name = effect_data.get('minion_name', 'unknown')
        summon_count = effect_data.get('summon_count', 1) * multiplier
        use_saved_stats = effect_data.get('use_saved_stats', False)
        keywords = effect_data.get('keywords', [])

        keywords_text = f" with {', '.join(keywords)}" if keywords else ""

        if minion_name == 'random_tier_1':
            if summon_count > 1:
                return f"Summon {summon_count} random tier 1 minions{keywords_text}"
            else:
                return f"Summon a random tier 1 minion{keywords_text}"

        if use_saved_stats:
            if summon_count > 1:
                return f"Summon {summon_count} {minion_name}s with saved stats{keywords_text}"
            else:
                return f"Summon a {minion_name} with saved stats{keywords_text}"
        else:
            health = effect_data.get('health', 1) * multiplier
            attack = effect_data.get('attack', 1) * multiplier
            if summon_count > 1:
                return f"Summon {summon_count} {minion_name}s ({health}/{attack} each){keywords_text}"
            else:
                return f"Summon a {minion_name} ({health}/{attack}){keywords_text}"

    elif effect_type == 'permanent_stat_gain':
        attack_gain = effect_data.get('attack', 0) * multiplier
        health_gain = effect_data.get('health', 0) * multiplier
        max_stacks = effect_data.get('max_stacks')
        if max_stacks and max_stacks < 999:
            max_stacks = max_stacks * multiplier

        gain_parts = []
        if attack_gain > 0:
            gain_parts.append(f"+{attack_gain} attack")
        if health_gain > 0:
            gain_parts.append(f"+{health_gain} health")

        gain_text = ', '.join(gain_parts)
        if max_stacks and max_stacks < 999:
            return f"Permanently gain {gain_text} (max {max_stacks} times)"
        else:
            return f"Permanently gain {gain_text}"

    elif effect_type == 'modify_fatigue':
        return f"Accelerate fatigue by {amount} attacks"

    elif effect_type == 'move_minion':
        direction = effect_data.get('direction', 'right')
        distance = effect_data.get('distance', 1) * multiplier
        return f"Move target {distance} position(s) {direction}"

    elif effect_type == 'debuff_stats':
        attack_debuff = effect_data.get('attack', 0) * multiplier
        if attack_debuff < 0:
            return f"Reduce a random enemy's attack by {-attack_debuff}"

    elif effect_type == 'damage_self':
        return f"Take {amount} damage"

    elif effect_type == 'redirect_death':
        condition = effect_data.get('condition', '')
        if condition == 'higher_stats':
            return f"Dies instead of friendly minions with higher stats"

    elif effect_type == 'destroy_and_transform':
        summon_count = effect_data.get('summon_count', 2) * multiplier
        minion_name = effect_data.get('minion_name', 'Meat Cube')
        stat_ratio = effect_data.get('stat_ratio', 0.5)
        return f"Destroy left ally, summon {summon_count} {minion_name}s with {int(stat_ratio * 100)}% of its stats"

    elif effect_type == 'attack_target':
        attacker = effect_data.get('attacker', 'self')
        if attacker == 'condition_found_minion':
            return f"Make it attack"
        elif attacker == 'trigger_summoned':
            return f"Make the summoned minion attack immediately"
        elif attacker == 'self':
            return f"Attack {target_desc}"
        else:
            return f"Make {attacker} attack"

    elif effect_type == 'grant_keyword':
        keyword = effect_data.get('keyword', 'unknown')
        return f"Gain {keyword}"

    elif effect_type == 'apply_stun':
        stun_amount = effect_data.get('stun_amount', 1) * multiplier
        exclude_type = effect_data.get('exclude_type')
        exclude_self = effect_data.get('exclude_self', False)

        if target == 'all_minions':
            target_desc = "all minions"
            if exclude_self:
                target_desc = "all other minions"
            if exclude_type:
                target_desc = f"all other non-{exclude_type} minions" if exclude_self else f"all non-{exclude_type} minions"
        else:
            target_desc = target

        return f"Stun {target_desc} for {stun_amount} attacks"

    elif effect_type == 'perform_cast':
        return f"Force target to cast their spell"

    return f"Unknown effect: {effect_type}"


def has_minion_named(ally_band, minion_name):
    """Check if there's a living minion with the specified name in the band"""
    return any(m.get('name') == minion_name and m.get('health', 0) > 0 for m in ally_band)


def format_condition_text(condition, is_golden=False):
    """Format a condition into readable text"""
    if not condition:
        return "always"

    check_type = condition.get('check_type', 'simple')
    multiplier = 2 if is_golden else 1

    if check_type == 'simple':
        condition_type = condition.get('type', 'unknown')
        target = condition.get('target', 'self')

        # Handle trigger context targets - make them user-friendly
        if target == 'trigger_source':
            target = "the triggering minion"
        elif target == 'trigger_summoned' or target == 'summoned_minion':
            target = "the summoned minion"
        elif target == 'trigger_summoner':
            target = "the summoner"
        elif target == 'trigger_dying':
            target = "the dying minion"
        elif target == 'trigger_leaper':
            target = "the leaping minion"
        elif target == 'trigger_target':
            target = "the target"
        elif target == 'trigger_attacker':
            target = "the attacker"
        elif target == 'trigger_defender':
            target = "the defender"

        if condition_type == 'has_left_ally':
            return "there is an ally to the left"
        elif condition_type == 'has_minion_named':
            minion_name = condition.get('minion_name', 'unknown')
            return f"there is a friendly {minion_name}"
        elif condition_type == 'has_minion_with_keyword':
            keyword = condition.get('keyword', 'unknown')
            return f"there is a friendly minion with {keyword}"
        elif condition_type == 'is_enemy':
            return f"{target} is an enemy"
        elif condition_type == 'is_ally':
            return f"{target} is an ally"
        elif condition_type == 'is_name':
            minion_name = condition.get('minion_name', 'unknown')
            return f"{target} is {minion_name}"
        elif condition_type == 'not_name':
            minion_name = condition.get('minion_name', 'unknown')
            return f"{target} is not {minion_name}"
        elif condition_type == 'not_has_type':
            minion_type = condition.get('minion_type', 'unknown')
            return f"{target} is not {minion_type}"
        elif condition_type == 'has_keyword':
            keyword = condition.get('keyword', 'unknown')
            return f"{target} has {keyword}"
        elif condition_type == 'not_has_keyword':
            keyword = condition.get('keyword', 'unknown')
            return f"{target} doesn't have {keyword}"
        elif condition_type == 'is_self':
            return f"{target} is this minion"
        elif condition_type == 'is_position':
            position = condition.get('position', 'unknown')
            return f"this is the {position} minion"
        elif condition_type == 'is_tier':
            tier = condition.get('tier', 1)
            return f"{target} is tier {tier}"
        elif condition_type == 'health_above':
            value = condition.get('value', 0) * multiplier
            return f"{target} has more than {value} health"
        elif condition_type == 'health_at_most':
            value = condition.get('value', 0) * multiplier
            return f"{target} has at most {value} health"
        elif condition_type == 'attack_above':
            value = condition.get('value', 0) * multiplier
            return f"{target} has more than {value} attack"
        elif condition_type == 'attack_at_most':
            value = condition.get('value', 0) * multiplier
            return f"{target} has at most {value} attack"
        elif condition_type == 'times_attacked':
            value = condition.get('value', 0) * multiplier
            return f"this has attacked {value} times"
        elif condition_type == 'trigger_count_equals':
            count = condition.get('count', 0) * multiplier
            return f"this has triggered {count} times"
        elif condition_type == 'not_additional_trigger':
            return "this is the original trigger"
        elif condition_type == 'is_adjacent':
            return f"{target} is adjacent"
        else:
            return f"{condition_type}"

    elif check_type == 'compound':
        checks = condition.get('checks', [])
        operator = condition.get('operator', 'AND')

        check_texts = []
        for check in checks:
            check_texts.append(format_condition_text(check, is_golden))

        if operator == 'AND':
            return ' and '.join(check_texts)
        elif operator == 'OR':
            return ' or '.join(check_texts)
        else:
            return f"{operator}({', '.join(check_texts)})"

    return "complex condition"


def filter_minions_by_modifiers(tier, pool_modifiers=None):
    """Filter minions by pool modifiers (types), excluding summon-only minions"""
    tier_minions = MINIONS.get(tier, [])

    # Exclude summon-only minions from normal pools
    available_minions = [m for m in tier_minions if not m.get('summon_only', False)]

    if not pool_modifiers:
        return available_minions

    # Filter by types in pool_modifiers
    filtered_minions = []
    for minion in available_minions:
        minion_type = minion.get('type', 'None')

        # Handle multi-faction minions
        if isinstance(minion_type, list):
            # Check if ANY of the minion's types are in the pool modifiers
            if any(t in pool_modifiers for t in minion_type):
                filtered_minions.append(minion)
        else:
            # Single type minion
            if minion_type in pool_modifiers:
                filtered_minions.append(minion)

    return filtered_minions


def generate_minion(tier, pool_modifiers=None):
    """Generate a random minion of the specified tier, optionally filtered by pool modifiers"""
    tier = min(max(tier, 1), 4)  # Clamp between 1-4

    # Filter pool first
    available_minions = filter_minions_by_modifiers(tier, pool_modifiers)

    # If no minions match modifiers, fall back to full tier
    if not available_minions:
        available_minions = filter_minions_by_modifiers(tier, None)

    if not available_minions:
        # Fallback to tier 1 if somehow empty
        available_minions = filter_minions_by_modifiers(1, None)

    minion_template = random.choice(available_minions)
    minion = create_minion_instance(minion_template, tier=tier)

    return minion


def generate_minion_multi_tier(ring_level, pool_modifiers=None):
    """
    Generate a random minion from a cumulative tier pool based on ring level.

    Ring 1: 100% tier 1
    Ring 2: 50% tier 1, 50% tier 2
    Ring 3: 33.3% tier 1, 33.3% tier 2, 33.3% tier 3
    Ring 4+: 25% tier 1, 25% tier 2, 25% tier 3, 25% tier 4

    Args:
        ring_level: Current ring level
        pool_modifiers: Optional type filtering (e.g. ['Human', 'Beast'])

    Returns:
        Minion instance
    """
    # Determine which tiers are available based on ring level
    if ring_level <= 1:
        tier_weights = {1: 1.0}
    elif ring_level == 2:
        tier_weights = {1: 0.5, 2: 0.5}
    elif ring_level == 3:
        tier_weights = {1: 1/3, 2: 1/3, 3: 1/3}
    else:  # ring_level >= 4
        tier_weights = {1: 0.25, 2: 0.25, 3: 0.25, 4: 0.25}

    # Build weighted list of all available minions from all tiers
    weighted_minions = []
    for tier, weight in tier_weights.items():
        tier_minions = filter_minions_by_modifiers(tier, pool_modifiers)

        # If no minions match modifiers for this tier, try without modifiers
        if not tier_minions:
            tier_minions = filter_minions_by_modifiers(tier, None)

        # Add each minion with its weight and tier info
        for minion in tier_minions:
            weighted_minions.append((minion, weight, tier))

    # If somehow no minions available, fallback to tier 1
    if not weighted_minions:
        return generate_minion(1, pool_modifiers)

    # Select a random minion based on weights
    minions, weights, tiers = zip(*weighted_minions)
    selected_index = random.choices(range(len(minions)), weights=weights, k=1)[0]
    minion_template = minions[selected_index]
    selected_tier = tiers[selected_index]

    return create_minion_instance(minion_template, tier=selected_tier)


def create_minion_instance(minion_template, tier=1, assign_band_id=True):
    """Create a minion instance from a template with all required fields"""
    minion = minion_template.copy()

    # Add tier tracking
    minion['tier'] = tier

    # Add required fields
    minion['golden'] = False
    minion['position'] = 0  # Will be set when added to band

    # Add unique band ID for player minions (not for enemies or summons by default)
    if assign_band_id:
        minion['band_id'] = generate_unique_minion_id()

    # Add permanent stat tracking
    minion['permanent_health'] = 0
    minion['permanent_attack'] = 0
    minion['permanent_stacks'] = {}  # Track stacks by effect source

    # Initialize permanent ring count (like Cat's permanent stats - never reset from template)
    if 'ring' in minion.get('keywords', []):
        # Only initialize if not already set (bell tower sets this directly)
        if 'permanent_ring_count' not in minion:
            minion['permanent_ring_count'] = minion.get('ring_count', 1)

    # Initialize aura buff tracking
    minion['aura_buffs'] = {
        'attack': 0,
        'health': 0,
        'sources': []  # List of minion IDs providing auras
    }

    # Copy over multi_attack_count if present in template
    if 'multi_attack_count' in minion_template:
        minion['multi_attack_count'] = minion_template['multi_attack_count']

    # Initialize stun tracking
    minion['stun_count'] = 0

    # Initialize hide tracking if minion has hide keyword
    if 'hide' in minion.get('keywords', []):
        if 'hide_count' not in minion:
            minion['hide_count'] = 1
        minion['hide_remaining'] = minion['hide_count']
        minion['is_hidden'] = True

    # Initialize leap distance if minion has leap keyword
    if 'leap' in minion.get('keywords', []):
        if 'leap_distance' not in minion:
            minion['leap_distance'] = 1

    # Initialize trigger counters for minions that need them
    if minion.get('name') == 'Lookalike':
        minion['assault_trigger_count'] = 0

    # Initialize scaling tracker for Railway Cannon
    if minion.get('name') == 'Railway Cannon':
        if 'cast_damage_current' not in minion:
            minion['cast_damage_current'] = 4
        if 'cast_damage_increment' not in minion:
            minion['cast_damage_increment'] = 4

    # Filter keywords to only include implemented ones
    keywords = minion.get('keywords', [])
    implemented_keywords = ['poke', 'guard', 'assault', 'death_toll', 'cast', 'cant_attack', 'cant_retaliate', 'multi_attack',
                           'rage', 'on_any_death', 'on_any_cast', 'on_any_summon', 'aura', 'sacrifice',
                           'stun', 'hide', 'leap', 'nobility', 'rich', 'ring', 'fatigue_immune', 'start_of_combat',
                           'on_adjacent_transform', 'on_damage', 'on_hide_lost', 'imperfect', 'fast', 'savage', 'on_any_leap', 'obliterate', 'ignoble', 'on_any_death_toll',
                           'ethereal', 'ethereal_left', 'left']  # Ethereal variants - [Last] saves if not last, [Left] saves if leftmost
    functional_keywords = []

    for keyword in keywords:
        if keyword in implemented_keywords:
            functional_keywords.append(keyword)

    minion['keywords'] = functional_keywords
    minion['all_keywords'] = keywords  # Store all keywords for future use

    # Validate functional keywords only
    if not validate_keywords(minion['keywords']):
        logger.warning(f"Warning: Invalid functional keywords for {minion['name']}: {minion['keywords']}")
        minion['keywords'] = []

    # Apply any existing permanent stats to base stats
    apply_permanent_stats(minion)

    return minion


def create_summon_minion(minion_name, override_stats=None, inherit_band_id=None):
    """Create a summoned minion instance by name with optional stat overrides and band ID inheritance"""
    # Find minion template by name across all tiers
    minion_template = None
    summon_tier = 1  # Default tier for summons
    for tier_level, tier_minions in MINIONS.items():
        for minion in tier_minions:
            if minion['name'].lower() == minion_name.lower():
                minion_template = minion
                summon_tier = tier_level
                break
        if minion_template:
            break

    if not minion_template:
        # Create a generic minion if template not found
        minion_template = {
            'name': minion_name,
            'health': 1,
            'attack': 1,
            'type': 'None',
            'keywords': [],
            'rarity': 'token'
        }

    # Create instance without auto-assigning band ID, with tier
    minion = create_minion_instance(minion_template, tier=summon_tier, assign_band_id=False)

    # Inherit band ID from summoner if provided (for linking to band)
    if inherit_band_id:
        minion['band_id'] = inherit_band_id

    # Apply stat overrides if provided (these are already golden-doubled if applicable)
    if override_stats:
        if 'health' in override_stats:
            minion['health'] = override_stats['health']
        if 'attack' in override_stats:
            minion['attack'] = override_stats['attack']
        if 'type' in override_stats:
            minion['type'] = override_stats['type']
        if 'keywords' in override_stats:
            minion['keywords'] = override_stats['keywords']

    return minion


def apply_permanent_stats(minion):
    """Apply permanent stat bonuses to a minion's base stats"""
    if 'permanent_health' in minion and minion['permanent_health'] > 0:
        minion['health'] += minion['permanent_health']
    if 'permanent_attack' in minion and minion['permanent_attack'] > 0:
        minion['attack'] += minion['permanent_attack']


def add_permanent_stats(minion, health_gain, attack_gain, source_id="default", max_stacks=None):
    """
    Add permanent stats to a minion with stack tracking

    Args:
        minion: Target minion
        health_gain: Health to add permanently
        attack_gain: Attack to add permanently
        source_id: Unique identifier for the source (e.g., "cat_death_toll")
        max_stacks: Maximum number of times this source can apply (None for unlimited)

    Returns:
        bool: True if stats were applied, False if max stacks reached
    """
    # Initialize permanent stat fields if they don't exist
    if 'permanent_health' not in minion:
        minion['permanent_health'] = 0
    if 'permanent_attack' not in minion:
        minion['permanent_attack'] = 0
    if 'permanent_stacks' not in minion:
        minion['permanent_stacks'] = {}

    # Check stack limit
    current_stacks = minion['permanent_stacks'].get(source_id, 0)
    if max_stacks is not None and current_stacks >= max_stacks:
        return False  # Max stacks reached

    # Apply the permanent gains
    minion['permanent_health'] += health_gain
    minion['permanent_attack'] += attack_gain

    # Also apply to current stats immediately
    minion['health'] += health_gain
    minion['attack'] += attack_gain

    # Track stacks
    minion['permanent_stacks'][source_id] = current_stacks + 1

    return True


def get_permanent_stack_count(minion, source_id):
    """Get the current stack count for a specific source"""
    return minion.get('permanent_stacks', {}).get(source_id, 0)


def get_minion_by_name(name, tier=None, include_bosses=True):
    """Get a minion template by name, optionally from specific tier

    Args:
        name: Name of the minion to find
        tier: Optional tier to search in (None searches all tiers)
        include_bosses: If True, also searches BOSS_MINIONS as fallback

    Returns:
        Copy of the minion template, or None if not found
    """
    if tier:
        tiers_to_search = [tier]
    else:
        tiers_to_search = MINIONS.keys()

    for tier_level in tiers_to_search:
        for minion in MINIONS[tier_level]:
            if minion['name'].lower() == name.lower():
                return minion.copy()

    # Also check boss minions as fallback
    if include_bosses:
        boss_minion = get_boss_minion(name)
        if boss_minion:
            return boss_minion

    return None


def get_all_minions():
    """Get all minion templates as a flat list, excluding summon-only minions"""
    all_minions = []
    for tier, tier_minions in MINIONS.items():
        for minion in tier_minions:
            if not minion.get('summon_only', False):
                # Add tier to minion if not already set
                if 'tier' not in minion:
                    minion['tier'] = tier
                all_minions.append(minion)
    return all_minions


def validate_minion(minion):
    """Validate that a minion has all required fields"""
    required_fields = ['name', 'health', 'attack', 'keywords', 'golden', 'position', 'tier']

    for field in required_fields:
        if field not in minion:
            return False, f"Missing required field: {field}"

    # Validate field types
    if not isinstance(minion['name'], str):
        return False, "Name must be a string"

    if not isinstance(minion['health'], int) or minion['health'] < 0:
        return False, "Health must be a non-negative integer"

    if not isinstance(minion['attack'], int) or minion['attack'] < 0:
        return False, "Attack must be a non-negative integer"

    if not isinstance(minion['keywords'], list):
        return False, "Keywords must be a list"

    if not isinstance(minion['golden'], bool):
        return False, "Golden must be a boolean"

    if not isinstance(minion['position'], int) or minion['position'] < 0:
        return False, "Position must be a non-negative integer"

    if not isinstance(minion['tier'], int) or minion['tier'] < 1:
        return False, "Tier must be a positive integer"

    # Validate functional keywords only
    if not validate_keywords(minion['keywords']):
        return False, f"Invalid functional keywords: {minion['keywords']}"

    return True, "Valid minion"


def get_minions_by_type(minion_type):
    """Get all minions of a specific type across all tiers"""
    minions_of_type = []
    for tier_minions in MINIONS.values():
        for minion in tier_minions:
            minion_types = minion.get('type', 'None')

            # Handle multi-faction minions
            if isinstance(minion_types, list):
                if minion_type in minion_types:
                    if not minion.get('summon_only', False):
                        minions_of_type.append(minion.copy())
            else:
                # Single type minion
                if minion_types == minion_type and not minion.get('summon_only', False):
                    minions_of_type.append(minion.copy())
    return minions_of_type


def get_minion_types():
    """Get all available minion types"""
    types = set()
    for tier_minions in MINIONS.values():
        for minion in tier_minions:
            if not minion.get('summon_only', False):
                minion_types = minion.get('type', 'None')

                # Handle multi-faction minions
                if isinstance(minion_types, list):
                    for t in minion_types:
                        types.add(t)
                else:
                    types.add(minion_types)
    return sorted(list(types))


def generate_minion_of_type(tier, minion_type, pool_modifiers=None):
    """Generate a random minion of specified tier and type"""
    tier = min(max(tier, 1), 4)  # Updated to support tier 4

    # Start with filtered pool if modifiers provided
    if pool_modifiers:
        available_minions = filter_minions_by_modifiers(tier, pool_modifiers)
    else:
        available_minions = filter_minions_by_modifiers(tier, None)

    # Further filter by specific type
    type_minions = []
    for m in available_minions:
        minion_types = m.get('type', 'None')

        # Handle multi-faction minions
        if isinstance(minion_types, list):
            if minion_type in minion_types:
                type_minions.append(m)
        else:
            if minion_types == minion_type:
                type_minions.append(m)

    if not type_minions:
        # Fallback to any minion of that tier if no type match
        return generate_minion(tier, pool_modifiers)

    minion_template = random.choice(type_minions)
    minion = create_minion_instance(minion_template, tier=tier)

    return minion


def prepare_band_for_combat(band):
    """Prepare a band for combat by ensuring all minions have proper stats including permanent bonuses and aura tracking"""
    for minion in band:
        # Ensure tier exists
        if 'tier' not in minion:
            minion['tier'] = 1  # Default to tier 1 for old minions

        # Ensure permanent stat fields exist
        if 'permanent_health' not in minion:
            minion['permanent_health'] = 0
        if 'permanent_attack' not in minion:
            minion['permanent_attack'] = 0
        if 'permanent_stacks' not in minion:
            minion['permanent_stacks'] = {}

        # Ensure aura buff tracking exists
        if 'aura_buffs' not in minion:
            minion['aura_buffs'] = {
                'attack': 0,
                'health': 0,
                'sources': []
            }

        # Ensure multi_attack_count exists if minion has multi_attack keyword
        if 'multi_attack' in minion.get('keywords', []) and 'multi_attack_count' not in minion:
            minion['multi_attack_count'] = 1  # Default to 1 additional attack

        # Ensure stun_count exists
        if 'stun_count' not in minion:
            minion['stun_count'] = 0

        # Initialize hide state if needed
        if 'hide' in minion.get('keywords', []) and 'is_hidden' not in minion:
            minion['is_hidden'] = True
            minion['hide_remaining'] = minion.get('hide_count', 1)

        # Initialize scaling tracker for Railway Cannon
        if minion.get('name') == 'Railway Cannon':
            if 'cast_damage_current' not in minion:
                minion['cast_damage_current'] = 4

        # Apply rich keyword bonus based on gold
        if 'rich' in minion.get('keywords', []):
            # This would need access to player gold from context
            pass


def restore_band_after_combat(band):
    """Restore a band after combat, maintaining permanent stat gains and clearing aura buffs"""
    for minion in band:
        # Get the original template to restore base stats
        original_template = get_minion_by_name(minion['name'])
        if original_template:
            # Restore base health and attack
            base_health = original_template['health']
            base_attack = original_template['attack']

            # Golden minions have doubled base stats
            if minion.get('golden'):
                base_health *= 2
                base_attack *= 2

            # Apply permanent bonuses to the restored stats
            permanent_health = minion.get('permanent_health', 0)
            permanent_attack = minion.get('permanent_attack', 0)

            minion['health'] = base_health + permanent_health
            minion['attack'] = base_attack + permanent_attack

        # Clear stun on combat end
        minion['stun_count'] = 0

        # Reset hide state
        if 'hide' in minion.get('keywords', []):
            minion['is_hidden'] = True
            minion['hide_remaining'] = minion.get('hide_count', 1)

        # Clear aura buffs after combat
        minion['aura_buffs'] = {
            'attack': 0,
            'health': 0,
            'sources': []
        }

        # Reset Railway Cannon scaling
        if minion.get('name') == 'Railway Cannon':
            minion['cast_damage_current'] = 4


def ensure_permanent_stats_integrity(band):
    """Ensure all minions in the band have proper permanent stat tracking"""
    for minion in band:
        # Initialize missing tier
        if 'tier' not in minion:
            minion['tier'] = 1

        # Initialize missing permanent stat fields
        if 'permanent_health' not in minion:
            minion['permanent_health'] = 0
        if 'permanent_attack' not in minion:
            minion['permanent_attack'] = 0
        if 'permanent_stacks' not in minion:
            minion['permanent_stacks'] = {}

        # Initialize aura buff tracking
        if 'aura_buffs' not in minion:
            minion['aura_buffs'] = {
                'attack': 0,
                'health': 0,
                'sources': []
            }

        # Initialize stun tracking
        if 'stun_count' not in minion:
            minion['stun_count'] = 0

        # Initialize hide tracking
        if 'hide' in minion.get('keywords', []):
            if 'hide_count' not in minion:
                minion['hide_count'] = 1
            if 'is_hidden' not in minion:
                minion['is_hidden'] = True
                minion['hide_remaining'] = minion['hide_count']

        # Initialize ring tracking
        if 'ring' in minion.get('keywords', []):
            # Initialize permanent_ring_count if not present (like Cat's permanent stats)
            if 'permanent_ring_count' not in minion:
                # Use ring_count from template if available, otherwise default to 1
                template = get_minion_by_name(minion['name'])
                minion['permanent_ring_count'] = template.get('ring_count', 1) if template else 1

        # Initialize scaling tracker for Railway Cannon
        if minion.get('name') == 'Railway Cannon':
            if 'cast_damage_current' not in minion:
                minion['cast_damage_current'] = 4

        # Ensure current stats include permanent bonuses
        original_template = get_minion_by_name(minion['name'])
        if original_template:
            base_health = original_template['health']
            base_attack = original_template['attack']

            expected_health = base_health + minion['permanent_health']
            expected_attack = base_attack + minion['permanent_attack']

            # Only update if current stats are less than expected (preserving damage)
            if minion['health'] > expected_health:
                minion['health'] = expected_health
            elif minion['health'] > 0 and minion['health'] < base_health:
                # Minion is damaged, maintain the damage ratio with permanent bonus
                damage_ratio = minion['health'] / max(1, base_health)
                minion['health'] = int(expected_health * damage_ratio)

            # Attack should always match expected (no damage concept for attack)
            minion['attack'] = expected_attack


def get_minion_attack_with_aura(minion):
    """Get a minion's attack value including aura buffs"""
    base_attack = minion.get('attack', 0)
    aura_attack = minion.get('aura_buffs', {}).get('attack', 0)
    return base_attack + aura_attack


def get_minion_health_with_aura(minion):
    """Get a minion's health value including aura buffs"""
    base_health = minion.get('health', 0)
    aura_health = minion.get('aura_buffs', {}).get('health', 0)
    return base_health + aura_health


def create_golden_minion(base_minion):
    """
    Create a golden version of a minion with enhanced stats

    Golden minions have:
    - Double health and attack
    - Golden flag set to true
    - All keyword effects are doubled (handled by combat_effects.py)
    - Multi-attack count is doubled
    """
    import copy
    golden = copy.deepcopy(base_minion)

    # Double health and attack for golden minions
    golden['health'] *= 2
    golden['attack'] *= 2
    golden['golden'] = True

    # Preserve permanent stats if they exist
    if 'permanent_health' in base_minion:
        golden['permanent_health'] = base_minion['permanent_health'] * 2
    if 'permanent_attack' in base_minion:
        golden['permanent_attack'] = base_minion['permanent_attack'] * 2

    # Double hide count for golden minions
    if 'hide_count' in base_minion:
        golden['hide_count'] = base_minion['hide_count'] * 2
        golden['hide_remaining'] = golden['hide_count']

    # Double leap distance for golden minions
    if 'leap_distance' in base_minion:
        golden['leap_distance'] = base_minion['leap_distance'] * 2

    # Double scaling damage increment for Railway Cannon
    if 'cast_damage_increment' in base_minion:
        golden['cast_damage_increment'] = base_minion['cast_damage_increment'] * 2

    # Note: Multi-attack count doubling is handled by get_multi_attack_count in keywords.py
    # We don't modify the base count here

    return golden


def can_combine_minions(minion1, minion2):
    """Check if two minions can be combined into a golden minion"""
    # Must be same name and neither already golden
    return (minion1['name'] == minion2['name'] and
            not minion1.get('golden', False) and
            not minion2.get('golden', False))


def _combine_wrapper_keyword(golden, minion1, minion2, template,
                              keyword, count_field, template_field, default=1):
    """
    Helper: Combine wrapper keyword counts for golden minions

    Golden minion rules:
    - Base keywords (in template): double base value + sum any extras from both minions
    - Added keywords (not in template): sum values from both minions

    Args:
        golden: The golden minion being created
        minion1, minion2: The two minions being combined
        template: The original minion template
        keyword: The keyword to check (e.g., 'ring', 'hide', 'leap')
        count_field: Field storing the count on minion (e.g., 'permanent_ring_count')
        template_field: Field in template storing base value (e.g., 'ring_count')
        default: Default value if not present in template
    """
    if keyword not in golden.get('keywords', []):
        return

    template_keywords = template.get('keywords', [])
    is_base = keyword in template_keywords

    if is_base:
        # Base keyword: double the base value, sum any extras
        base_value = template.get(template_field, default)
        current1 = minion1.get(count_field, base_value)
        current2 = minion2.get(count_field, base_value)
        extra1 = current1 - base_value
        extra2 = current2 - base_value
        golden[count_field] = (base_value * 2) + extra1 + extra2
        logger.debug(f"[GOLDEN] {keyword} is BASE: base={base_value}, doubled={base_value*2}, extra1={extra1}, extra2={extra2}, total={golden[count_field]}")
    else:
        # Added keyword: sum the values
        value1 = minion1.get(count_field, 0)
        value2 = minion2.get(count_field, 0)
        golden[count_field] = value1 + value2
        logger.debug(f"[GOLDEN] {keyword} is ADDED: value1={value1}, value2={value2}, total={golden[count_field]}")


def combine_minions_into_golden(minion1, minion2):
    """
    Combine two identical minions into a golden minion

    Args:
        minion1: First minion to combine
        minion2: Second minion to combine

    Returns:
        Golden minion with combined stats, or None if cannot combine
    """
    if not can_combine_minions(minion1, minion2):
        return None

    # Use the first minion as the base for the golden
    # But sum certain stats from both minions
    import copy
    golden = copy.deepcopy(minion1)

    # Get base stats from template
    original_template = get_minion_by_name(minion1['name'])
    if original_template:
        # Golden gets double the base stats
        golden['health'] = original_template['health'] * 2
        golden['attack'] = original_template['attack'] * 2
    else:
        # Fallback if template not found
        golden['health'] = minion1['health'] + minion2['health']
        golden['attack'] = minion1['attack'] + minion2['attack']

    # Combine permanent stats from both minions
    perm_health1 = minion1.get('permanent_health', 0)
    perm_health2 = minion2.get('permanent_health', 0)
    perm_attack1 = minion1.get('permanent_attack', 0)
    perm_attack2 = minion2.get('permanent_attack', 0)

    golden['permanent_health'] = perm_health1 + perm_health2
    golden['permanent_attack'] = perm_attack1 + perm_attack2

    # Apply permanent stats to current stats
    golden['health'] += golden['permanent_health']
    golden['attack'] += golden['permanent_attack']

    # Combine permanent stacks tracking
    stacks1 = minion1.get('permanent_stacks', {})
    stacks2 = minion2.get('permanent_stacks', {})
    combined_stacks = {}

    for source_id in set(list(stacks1.keys()) + list(stacks2.keys())):
        combined_stacks[source_id] = stacks1.get(source_id, 0) + stacks2.get(source_id, 0)

    golden['permanent_stacks'] = combined_stacks

    # Combine keywords from both minions using union
    # If either minion has a keyword, the golden minion gets it
    keywords1 = set(minion1.get('keywords', []))
    keywords2 = set(minion2.get('keywords', []))
    combined_keywords = keywords1 | keywords2  # Union
    golden['keywords'] = list(combined_keywords)

    # Set golden flag
    golden['golden'] = True

    # Handle wrapper keywords with counts
    # These need special logic: base keywords (in template) are doubled, added keywords are summed
    if original_template:
        # Ring keyword
        if 'ring' in golden['keywords']:
            _combine_wrapper_keyword(golden, minion1, minion2, original_template,
                                     'ring', 'permanent_ring_count', 'ring_count', default=1)

        # Hide keyword
        if 'hide' in golden['keywords']:
            _combine_wrapper_keyword(golden, minion1, minion2, original_template,
                                     'hide', 'hide_count', 'hide_count', default=1)
            if 'hide_count' in golden:
                golden['hide_remaining'] = golden['hide_count']

        # Leap keyword
        if 'leap' in golden['keywords']:
            _combine_wrapper_keyword(golden, minion1, minion2, original_template,
                                     'leap', 'leap_distance', 'leap_distance', default=1)

        # Cleave keyword (has cleave_amount associated)
        if 'cleave' in golden['keywords']:
            template_keywords = original_template.get('keywords', [])
            is_base = 'cleave' in template_keywords

            if is_base:
                base_cleave = original_template.get('cleave_amount', 1)
                current1 = minion1.get('cleave_amount', base_cleave)
                current2 = minion2.get('cleave_amount', base_cleave)
                extra1 = current1 - base_cleave
                extra2 = current2 - base_cleave
                golden['cleave_amount'] = (base_cleave * 2) + extra1 + extra2
            else:
                # Added cleave: sum
                golden['cleave_amount'] = minion1.get('cleave_amount', 0) + minion2.get('cleave_amount', 0)

    # Double scaling increment for Railway Cannon (special case, always doubles)
    if 'cast_damage_increment' in golden:
        golden['cast_damage_increment'] *= 2

    # Keep the band_id from the first minion
    if 'band_id' in minion1:
        golden['band_id'] = minion1['band_id']

    return golden


def generate_minions_same_type(tier, count, pool_modifiers=None):
    """Generate multiple minions of the same type"""
    if count <= 0:
        return []

    # Generate first minion to determine type
    first_minion = generate_minion(tier, pool_modifiers)
    first_type = first_minion.get('type', 'None')

    # Generate rest as same type
    minions = [first_minion]
    for _ in range(count - 1):
        # Handle multi-faction minions
        if isinstance(first_type, list):
            # For multi-faction, just generate from same tier for simplicity
            minions.append(generate_minion(tier, pool_modifiers))
        else:
            minions.append(generate_minion_of_type(tier, first_type, pool_modifiers))

    return minions


def generate_minions_different_types(tier, count, pool_modifiers=None):
    """Generate minions trying to get different types"""
    if count <= 0:
        return []

    minions = []
    used_types = set()

    for _ in range(count):
        # Try to get a minion of unused type
        attempts = 0
        max_attempts = 20

        while attempts < max_attempts:
            minion = generate_minion(tier, pool_modifiers)
            minion_type = minion.get('type', 'None')

            # Handle multi-faction minions
            if isinstance(minion_type, list):
                # For multi-faction, consider it different if any type is new
                type_key = tuple(sorted(minion_type))
            else:
                type_key = minion_type

            if type_key not in used_types or attempts >= max_attempts - 1:
                minions.append(minion)
                used_types.add(type_key)
                break

            attempts += 1

    return minions


def generate_minions_with_preference(tier, count, preference='random', pool_modifiers=None):
    """
    Generate minions with type preference

    Args:
        tier: Minion tier
        count: Number of minions
        preference: 'same_type', 'different_types', or 'random'
        pool_modifiers: Optional type filtering (e.g. ['Human', 'Beast'])

    Returns:
        list: Generated minions
    """
    if preference == 'same_type':
        return generate_minions_same_type(tier, count, pool_modifiers)
    elif preference == 'different_types':
        return generate_minions_different_types(tier, count, pool_modifiers)
    else:
        # Random preference - just generate individually
        minions = []
        for _ in range(count):
            minions.append(generate_minion(tier, pool_modifiers))
        return minions


def calculate_minion_power(minion):
    """Calculate the power level of a single minion including permanent bonuses, aura buffs, and golden status"""
    # Use current stats which include permanent bonuses and aura buffs
    base_power = get_minion_health_with_aura(minion) + (get_minion_attack_with_aura(minion) * 2)

    # Keyword bonuses
    keyword_bonus = 0
    for keyword in minion.get('keywords', []):
        if keyword == 'poke':
            keyword_bonus += 5
        elif keyword == 'guard':
            keyword_bonus += 8
        elif keyword == 'assault':
            keyword_bonus += 6
        elif keyword == 'death_toll':
            keyword_bonus += 4
        elif keyword == 'cast':
            keyword_bonus += 7
        elif keyword == 'cant_attack':
            keyword_bonus -= 3
        elif keyword == 'cant_retaliate':
            keyword_bonus -= 2
        elif keyword == 'multi_attack':
            multi_count = minion.get('multi_attack_count', 1)
            if minion.get('golden', False):
                multi_count *= 2
            keyword_bonus += 10 * multi_count
        elif keyword == 'rage':
            keyword_bonus += 6
        elif keyword == 'on_any_death':
            keyword_bonus += 8
        elif keyword == 'on_any_cast':
            keyword_bonus += 5
        elif keyword == 'on_any_summon':
            keyword_bonus += 6
        elif keyword == 'on_damage':
            keyword_bonus += 5
        elif keyword == 'aura':
            keyword_bonus += 10
        elif keyword == 'sacrifice':
            keyword_bonus += 4
        elif keyword == 'stun':
            keyword_bonus -= 4
        elif keyword == 'hide':
            keyword_bonus += 7
        elif keyword == 'leap':
            keyword_bonus += 3
        elif keyword == 'nobility':
            keyword_bonus += 15
        elif keyword == 'rich':
            keyword_bonus += 5
        elif keyword == 'fatigue_immune':
            keyword_bonus += 8
        elif keyword == 'on_hide_lost':
            keyword_bonus += 6
        elif keyword == 'imperfect':
            keyword_bonus += 3
        elif keyword == 'fast':
            keyword_bonus += 8
        elif keyword == 'savage':
            keyword_bonus += 6
        elif keyword == 'on_any_leap':
            keyword_bonus += 5
        elif keyword == 'obliterate':
            keyword_bonus += 25
        elif keyword == 'ignoble':
            keyword_bonus += 12

    # Stun penalty
    stun_count = minion.get('stun_count', 0)
    if stun_count > 0:
        keyword_bonus -= stun_count * 3

    total_power = base_power + keyword_bonus

    # Golden multiplier (stats are already doubled, but add extra value for effect doubling)
    if minion.get('golden', False):
        total_power = int(total_power * 1.5)

    return total_power