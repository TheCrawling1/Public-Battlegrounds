"""
Effect Actions - on_select handler registry and executor for general events.

This module replaces the massive if/elif chain in selection_system.py with:
1. EFFECT_REGISTRY: Declarative effects defined as lists of action dicts
2. CUSTOM_HANDLERS: Complex handlers that need real code
3. execute_on_select(): Single entry point that dispatches to the right handler

ADDING A NEW HANDLER:
    Simple effects - add an entry to EFFECT_REGISTRY:
        'my_handler': [
            {'type': 'grant_gold', 'amount': '3 * tier'},
            {'type': 'message', 'text': 'You found gold!'},
        ]

    Complex logic - add a function and register it in CUSTOM_HANDLERS:
        def _handle_my_complex(ctx):
            # custom logic
            ctx['results'].append('Something happened')

        CUSTOM_HANDLERS['my_complex'] = _handle_my_complex

Available action types:
    grant_gold      {'amount': int|str}
    buff_all        {'attack': int|str, 'health': int|str, 'type_filter': str|None}
    buff_target     {'attack': int, 'health': int, 'add_keywords': [], 'set_properties': {}}
    set_type_target {'new_type': str}
    set_state       {'key': str, 'value': any}
    increment_state {'key': str, 'amount': int, 'default': int}
    decrement_state {'key': str, 'amount': int, 'default': int}
    init_state      {'key': str, 'default': any}
    add_steps       {'steps': int}
    remove_steps    {'steps': int}
    pay_health      {'cost': int}
    clear_curse     {}
    clear_boss      {'boss_id': str}
    mark_complete   {'event_id': str}
    message         {'text': str}  (supports {tier} format)

Message fields on any action support format variables:
    {amount}, {tier}, {count}, {attack}, {health}, {value}, {name}, {key},
    {payment_msg}, {target_name}
"""

import logging

logger = logging.getLogger(__name__)

from game_engine.events.event_helpers import resolve_formula


def _resolve(value, tier):
    """Resolve a value that may be a tier formula string."""
    if isinstance(value, (int, float)):
        return int(value)
    return resolve_formula(str(value), tier)


# ==================== ACTION EXECUTORS ====================


def _exec_grant_gold(ctx, action):
    amount = _resolve(action['amount'], ctx['tier'])
    ctx['resources']['gold'] = ctx['resources'].get('gold', 0) + amount
    ctx['run'].set_resources(ctx['resources'])
    if 'message' in action:
        ctx['results'].append(action['message'].format(amount=amount, tier=ctx['tier']))
    else:
        ctx['results'].append(f'Gained {amount} gold!')


def _exec_buff_all(ctx, action):
    attack = _resolve(action.get('attack', 0), ctx['tier'])
    health = _resolve(action.get('health', 0), ctx['tier'])
    type_filter = action.get('type_filter')
    count = 0
    for minion in ctx['band']:
        if type_filter and minion.get('type') != type_filter:
            continue
        if attack:
            minion['attack'] = minion.get('attack', 0) + attack
            minion['permanent_attack'] = minion.get('permanent_attack', 0) + attack
        if health:
            minion['health'] = minion.get('health', 0) + health
            minion['permanent_health'] = minion.get('permanent_health', 0) + health
        count += 1
    ctx['run'].set_band(ctx['band'])
    if 'message' in action:
        ctx['results'].append(action['message'].format(
            count=count, attack=attack, health=health, tier=ctx['tier']))
    else:
        type_label = f'{count} {type_filter}s' if type_filter else f'All {count} minions'
        if attack and health:
            ctx['results'].append(f'{type_label} gained +{attack}/+{health}!')
        elif attack:
            ctx['results'].append(f'{type_label} gained +{attack} attack!')
        else:
            ctx['results'].append(f'{type_label} gained +0/+{health}!')


def _exec_buff_target(ctx, action):
    """Buff a specific minion by target_index from the selected option."""
    target_index = ctx['selected_option'].get('target_index')
    band = ctx['band']
    if not band or target_index is None or target_index >= len(band):
        return
    target = band[target_index]
    attack = action.get('attack', 0)
    health = action.get('health', 0)
    if attack:
        target['attack'] = target.get('attack', 0) + attack
        target['permanent_attack'] = target.get('permanent_attack', 0) + attack
    if health:
        target['health'] = target.get('health', 0) + health
        target['permanent_health'] = target.get('permanent_health', 0) + health
    for kw in action.get('add_keywords', []):
        if 'keywords' not in target:
            target['keywords'] = []
        if kw not in target['keywords']:
            target['keywords'].append(kw)
    for key, value in action.get('set_properties', {}).items():
        target[key] = value
    ctx['run'].set_band(band)
    if 'message' in action:
        ctx['results'].append(action['message'].format(
            name=target['name'], attack=attack, health=health))
    else:
        ctx['results'].append(f"{target['name']} gained +{attack}/+{health}")


def _exec_set_type_target(ctx, action):
    """Change a target minion's type."""
    target_index = ctx['selected_option'].get('target_index')
    band = ctx['band']
    if not band or target_index is None or target_index >= len(band):
        return
    target = band[target_index]
    target['type'] = action['new_type']
    ctx['run'].set_band(band)
    if 'message' in action:
        ctx['results'].append(action['message'].format(name=target['name']))
    else:
        ctx['results'].append(f"{target['name']} is now a {action['new_type']} minion")


def _exec_set_state(ctx, action):
    key = action['key']
    value = action['value']
    if isinstance(value, str) and 'tier' in value:
        value = _resolve(value, ctx['tier'])
    ctx['event_state'][key] = value
    ctx['run'].set_event_state(ctx['event_state'])
    if 'message' in action:
        ctx['results'].append(action['message'].format(
            value=value, tier=ctx['tier'], key=key))


def _exec_increment_state(ctx, action):
    key = action['key']
    amount = action.get('amount', 1)
    default = action.get('default', 0)
    ctx['event_state'][key] = ctx['event_state'].get(key, default) + amount
    ctx['run'].set_event_state(ctx['event_state'])
    if 'message' in action:
        ctx['results'].append(action['message'].format(
            value=ctx['event_state'][key], key=key))


def _exec_decrement_state(ctx, action):
    key = action['key']
    amount = action.get('amount', 1)
    default = action.get('default', 0)
    if key not in ctx['event_state']:
        ctx['event_state'][key] = default
    ctx['event_state'][key] -= amount
    ctx['run'].set_event_state(ctx['event_state'])
    if 'message' in action:
        ctx['results'].append(action['message'].format(
            value=ctx['event_state'][key], key=key))


def _exec_init_state(ctx, action):
    key = action['key']
    default = action['default']
    if key not in ctx['event_state']:
        ctx['event_state'][key] = default
        ctx['run'].set_event_state(ctx['event_state'])


def _exec_add_steps(ctx, action):
    from game_engine.selection_system import SelectionSystem
    steps = action.get('steps', 1)
    SelectionSystem._increase_step_count(ctx['run'], steps)
    if 'message' in action:
        ctx['results'].append(action['message'])


def _exec_remove_steps(ctx, action):
    from game_engine.selection_system import SelectionSystem
    steps = action.get('steps', 1)
    SelectionSystem._decrease_step_count(ctx['run'], steps)
    if 'message' in action:
        ctx['results'].append(action['message'])
    else:
        ctx['results'].append(f'Gained {steps} step!')


def _exec_pay_health(ctx, action):
    from game_engine.selection_system import SelectionSystem
    cost = action['cost']
    payment = SelectionSystem._pay_health_cost(ctx['run'], cost)
    if not payment['success']:
        ctx['results'].append(payment['error'])
        ctx['run'].set_pending_selection(None)
        ctx['_failed'] = True
        ctx['_failure_result'] = {
            'success': False,
            'results': ctx['results'],
            'band_changes': [],
            'resource_changes': {}
        }
        return
    if 'message' in action:
        ctx['results'].append(action['message'].format(payment_msg=payment['message']))
    else:
        ctx['results'].append(payment['message'])


def _exec_clear_curse(ctx, action):
    ctx['event_state']['curse_level'] = 0
    ctx['event_state'].pop('curse_type', None)
    ctx['run'].set_event_state(ctx['event_state'])
    if 'message' in action:
        ctx['results'].append(action['message'])


def _exec_clear_boss(ctx, action):
    boss_id = action['boss_id']
    tier = ctx['tier']
    ctx['event_state']['active_boss'] = None
    if 'bosses_defeated' not in ctx['event_state']:
        ctx['event_state']['bosses_defeated'] = {}
    ctx['event_state']['bosses_defeated'][str(tier)] = boss_id
    ctx['run'].set_event_state(ctx['event_state'])
    logger.debug(f"[BOSS_REWARD] {boss_id}: Cleared active_boss, set bosses_defeated[{tier}]={boss_id}")


def _exec_mark_complete(ctx, action):
    event_id = action['event_id']
    completed = ctx['event_state'].get('completed_events', [])
    if event_id not in completed:
        completed.append(event_id)
    ctx['event_state']['completed_events'] = completed
    ctx['run'].set_event_state(ctx['event_state'])


def _exec_message(ctx, action):
    ctx['results'].append(action['text'].format(tier=ctx['tier']))


# Action type -> executor function
ACTION_EXECUTORS = {
    'grant_gold': _exec_grant_gold,
    'buff_all': _exec_buff_all,
    'buff_target': _exec_buff_target,
    'set_type_target': _exec_set_type_target,
    'set_state': _exec_set_state,
    'increment_state': _exec_increment_state,
    'decrement_state': _exec_decrement_state,
    'init_state': _exec_init_state,
    'add_steps': _exec_add_steps,
    'remove_steps': _exec_remove_steps,
    'pay_health': _exec_pay_health,
    'clear_curse': _exec_clear_curse,
    'clear_boss': _exec_clear_boss,
    'mark_complete': _exec_mark_complete,
    'message': _exec_message,
}


# ==================== DECLARATIVE EFFECT REGISTRY ====================

EFFECT_REGISTRY = {
    # ---- Bell Tower ----
    'increment_bells_rung': [
        {'type': 'increment_state', 'key': 'bells_rung',
         'message': 'Bell rung! (Total: {value})'},
    ],

    # ---- Gold Grants ----
    'grant_gold_5x_tier': [
        {'type': 'grant_gold', 'amount': '5 * tier'},
    ],
    'collapsed_mine_fast': [
        {'type': 'grant_gold', 'amount': '3 * tier'},
    ],
    'collapsed_mine_fastest': [
        {'type': 'grant_gold', 'amount': '5 * tier'},
    ],
    'collapsed_mine_slow': [
        {'type': 'grant_gold', 'amount': '4 * tier'},
        {'type': 'add_steps', 'steps': 1,
         'message': 'Took extra time gathering gold. +1 step.'},
    ],
    'modify_gold_30': [
        {'type': 'grant_gold', 'amount': 30},
    ],

    # ---- Buff All ----
    'buff_all_per_tier': [
        {'type': 'buff_all', 'attack': 'tier', 'health': 'tier',
         'message': 'All minions gained +{attack}/+{health}!'},
    ],
    'buff_all_minions_3_3': [
        {'type': 'buff_all', 'attack': 3, 'health': 3,
         'message': 'All {count} minions gained +3/+3!'},
    ],
    'buff_beasts_attack': [
        {'type': 'buff_all', 'attack': '2 * tier', 'health': 0, 'type_filter': 'Beast',
         'message': '{count} Beasts gained +{attack} attack!'},
    ],
    'buff_all_beasts_1_1': [
        {'type': 'buff_all', 'attack': 1, 'health': 1, 'type_filter': 'Beast',
         'message': '{count} Beasts gained +1/+1!'},
    ],

    # ---- State Flags ----
    'sneak_debuff_next_combat': [
        {'type': 'set_state', 'key': 'sneak_debuff', 'value': 'tier',
         'message': 'Next combat: enemies start at -{value} HP!'},
    ],
    'tower_control_effect': [
        {'type': 'set_state', 'key': 'tower_control_ring', 'value': 'tier'},
        {'type': 'set_state', 'key': 'tower_control_debuff', 'value': '2 * tier',
         'message': 'Tower captured! Enemies in this ring start at -{value} HP!'},
    ],
    'unlock_next_special_options': [
        {'type': 'set_state', 'key': 'unlock_special_options', 'value': True,
         'message': 'Next event: special options unlocked!'},
    ],
    'enable_pack_discount': [
        {'type': 'message', 'text': 'Pack discount enabled! (Feature in progress)'},
    ],
    'set_double_gold_bounty': [
        {'type': 'set_state', 'key': 'double_gold_next_combat', 'value': True,
         'message': 'Bounty set! Your next combat awards double gold.'},
    ],
    'activate_boss_bounty': [
        {'type': 'set_state', 'key': 'boss_bounty_active', 'value': True,
         'message': 'Boss bounty active! Your next general event will be a boss encounter.'},
    ],
    'clear_boss_bounty': [
        {'type': 'set_state', 'key': 'boss_bounty_active', 'value': False,
         'message': 'Boss bounty completed!'},
    ],
    'set_bounty_mark': [
        {'type': 'message', 'text': 'Bounty mark set! Earn gold when you defeat this type.'},
    ],
    'watchtower_storm_effect': [
        {'type': 'increment_state', 'key': 'hard_combat_downgrades', 'amount': 2,
         'message': 'Next 2 hard combats are now normal combats!'},
    ],

    # ---- Step Manipulation ----
    'gain_step': [
        {'type': 'remove_steps', 'steps': 1},
    ],
    'gain_step_1': [
        {'type': 'remove_steps', 'steps': 1},
    ],

    # ---- Ivory Tower ----
    'ivory_tower_sacrifice_minion': [
        {'type': 'init_state', 'key': 'ivory_tower_seal', 'default': 4},
    ],
    'ivory_tower_take_damage': [
        {'type': 'pay_health', 'cost': 7},
        {'type': 'init_state', 'key': 'ivory_tower_seal', 'default': 4},
        {'type': 'decrement_state', 'key': 'ivory_tower_seal', 'default': 4,
         'message': 'Seal weakened to {value}'},
    ],
    'ivory_tower_lose_steps': [
        {'type': 'add_steps', 'steps': 2},
        {'type': 'init_state', 'key': 'ivory_tower_seal', 'default': 4},
        {'type': 'decrement_state', 'key': 'ivory_tower_seal', 'default': 4,
         'message': 'Lost 2 steps! Seal weakened to {value}'},
    ],
    'ivory_tower_decrease_seal': [
        {'type': 'init_state', 'key': 'ivory_tower_seal', 'default': 4},
        {'type': 'decrement_state', 'key': 'ivory_tower_seal', 'default': 4,
         'message': 'Seal weakened to {value}!'},
    ],

    # ---- Grand City ----
    'grand_city_portal': [
        {'type': 'increment_state', 'key': 'tier_cost_reduction', 'amount': 3},
        {'type': 'set_state', 'key': 'curse_level', 'value': 3},
        {'type': 'set_state', 'key': 'curse_type', 'value': 'scrap_heap'},
        {'type': 'message', 'text': 'Next tier costs 3 less! Scrap Curse (3) applied.'},
    ],
    'grand_city_make_golden': [
        {'type': 'set_state', 'key': 'curse_level', 'value': 3},
        {'type': 'set_state', 'key': 'curse_type', 'value': 'scrap_heap'},
        {'type': 'message', 'text': 'Scrap Curse (3) applied. Choose a minion to make golden...'},
    ],

    # ---- Scrap Heap ----
    'scrap_heap_suffer_waste': [
        {'type': 'pay_health', 'cost': 5},
        {'type': 'clear_curse'},
        {'type': 'message', 'text': 'Curse removed!'},
    ],
    'scrap_heap_blind_luck': [
        {'type': 'clear_curse'},
        {'type': 'message', 'text': 'A stroke of luck! Curse removed!'},
    ],

    # ---- Boss Rewards (all-minion buffs) ----
    'boss_reward_dire_pack_stats': [
        {'type': 'buff_all', 'attack': 2, 'health': 2,
         'message': 'All minions gained +2/+2'},
        {'type': 'clear_boss', 'boss_id': 'dire_pack'},
    ],
    'boss_reward_behemoth_all': [
        {'type': 'buff_all', 'attack': 0, 'health': 4,
         'message': 'All minions gained +0/+4'},
        {'type': 'clear_boss', 'boss_id': 'behemoth'},
    ],
    'boss_reward_venomspawn_attack': [
        {'type': 'buff_all', 'attack': 6, 'health': 0,
         'message': 'All minions gained +6 attack'},
        {'type': 'clear_boss', 'boss_id': 'venomspawn'},
    ],
    'boss_reward_possessed_gold': [
        {'type': 'grant_gold', 'amount': '10 * tier', 'message': 'Gained {amount} gold'},
        {'type': 'clear_boss', 'boss_id': 'greater_possessed'},
    ],

    # ---- Boss Rewards (targeted) ----
    'boss_reward_dire_pack_keyword': [
        {'type': 'buff_target', 'attack': 0, 'health': 0,
         'add_keywords': ['on_any_death'],
         'set_properties': {'on_any_death_effect': {
             'type': 'buff_stats', 'target': 'self', 'attack': 2, 'health': 2}},
         'message': "{name} gained 'On Any Death: +2/+2'"},
        {'type': 'clear_boss', 'boss_id': 'dire_pack'},
    ],
    'boss_reward_congregation_tribe': [
        {'type': 'set_type_target', 'new_type': 'Cult',
         'message': '{name} is now a Cult minion'},
        {'type': 'clear_boss', 'boss_id': 'congregation'},
    ],
    'boss_reward_congregation_ignoble': [
        {'type': 'buff_target', 'attack': 0, 'health': 0,
         'add_keywords': ['ignoble'],
         'message': '{name} gained Ignoble'},
        {'type': 'clear_boss', 'boss_id': 'congregation'},
    ],
    'boss_reward_chained_stats': [
        {'type': 'buff_target', 'attack': 8, 'health': 8,
         'add_keywords': ['leap'],
         'set_properties': {'leap_distance': 2},
         'message': '{name} gained +8/+8 and Leap 2'},
        {'type': 'clear_boss', 'boss_id': 'chained_beast'},
    ],
    'boss_reward_chained_ethereal': [
        {'type': 'buff_target', 'attack': 0, 'health': 0,
         'add_keywords': ['ethereal_left', 'cant_cast', 'cant_retaliate'],
         'message': "{name} gained Ethereal [Left], Can't Cast, Can't Retaliate"},
        {'type': 'clear_boss', 'boss_id': 'chained_beast'},
    ],
    'boss_reward_behemoth_tank': [
        {'type': 'buff_target', 'attack': 5, 'health': 12,
         'add_keywords': ['guard'],
         'message': '{name} gained Guard and +5/+12'},
        {'type': 'clear_boss', 'boss_id': 'behemoth'},
    ],
    'boss_reward_venomspawn_cast': [
        {'type': 'buff_target', 'attack': 0, 'health': 0,
         'add_keywords': ['cast'],
         'set_properties': {'cast_effect': {
             'type': 'damage', 'target': 'all_enemies', 'amount': 2}},
         'message': "{name} gained 'Cast: Deal 2 damage to all enemy minions'"},
        {'type': 'clear_boss', 'boss_id': 'venomspawn'},
    ],
    'boss_reward_possessed_deathtoll': [
        {'type': 'buff_target', 'attack': 0, 'health': 0,
         'add_keywords': ['death_toll'],
         'set_properties': {'death_toll_effect': {
             'type': 'summon', 'minion_name': 'Possessed', 'count': 1}},
         'message': "{name} gained 'Death Toll: Summon a Possessed'"},
        {'type': 'clear_boss', 'boss_id': 'greater_possessed'},
    ],
}


# ==================== CUSTOM HANDLERS ====================
# For logic that can't be expressed as a simple action list.


def _handle_grant_gold_3x_tier_maybe_combat(ctx):
    gold_amount = 3 * ctx['tier']
    ctx['resources']['gold'] = ctx['resources'].get('gold', 0) + gold_amount
    ctx['run'].set_resources(ctx['resources'])
    ctx['results'].append(f'Gained {gold_amount} gold!')
    import random
    if random.random() < 0.3:
        from game_engine.events.event_system import EventSystem
        EventSystem._create_scaling_combat_selection(ctx['run'], 'combat_event_hard')
        ctx['results'].append('Cave-in! Combat triggered!')


def _handle_grand_city_upgrade_hero(ctx):
    hero_effects = ctx['run'].get_hero_effects()
    hero_effects['power_upgraded'] = hero_effects.get('power_upgraded', 0) + 1
    ctx['run'].set_hero_effects(hero_effects)
    ctx['event_state']['curse_level'] = 3
    ctx['event_state']['curse_type'] = 'scrap_heap'
    ctx['run'].set_event_state(ctx['event_state'])
    ctx['results'].append('Hero power upgraded! Scrap Curse (3) applied.')


def _handle_scrap_heap_brave_smog(ctx):
    stat_drain = ctx['tier']
    removed_count = 0
    surviving_band = []
    for minion in ctx['band']:
        minion['health'] = minion.get('health', 1) - stat_drain
        minion['attack'] = max(0, minion.get('attack', 0) - stat_drain)
        if minion['health'] > 0:
            surviving_band.append(minion)
        else:
            removed_count += 1
    ctx['run'].set_band(surviving_band)
    ctx['event_state']['curse_level'] = 0
    ctx['event_state'].pop('curse_type', None)
    ctx['run'].set_event_state(ctx['event_state'])
    ctx['results'].append(
        f'All minions lost -{stat_drain}/-{stat_drain}. {removed_count} removed. Curse removed!')


def _handle_scrap_heap_suffer_through(ctx):
    ctx['event_state']['curse_level'] = max(0, ctx['event_state'].get('curse_level', 3) - 1)
    if ctx['event_state']['curse_level'] == 0:
        ctx['event_state'].pop('curse_type', None)
        ctx['results'].append('Curse has faded!')
    else:
        ctx['results'].append(f'Curse decreased to [{ctx["event_state"]["curse_level"]}]')
    ctx['run'].set_event_state(ctx['event_state'])


def _handle_ivory_tower_gain_slot(ctx):
    ctx['event_state']['extra_band_slots'] = ctx['event_state'].get('extra_band_slots', 0) + 1
    completed_events = ctx['event_state'].get('completed_events', [])
    if 'ivory_tower' not in completed_events:
        completed_events.append('ivory_tower')
    ctx['event_state']['completed_events'] = completed_events
    ctx['run'].set_event_state(ctx['event_state'])
    total = 6 + ctx['event_state']['extra_band_slots']
    ctx['results'].append(f'Gained 1 extra band slot! (Total: {total} max)')


def _handle_start_boss_hunt(ctx):
    import random
    boss_pool = ['dire_pack', 'congregation', 'chained_beast',
                 'behemoth', 'venomspawn', 'greater_possessed']
    bosses_defeated = ctx['event_state'].get('bosses_defeated', {})
    current_tier = str(ctx['tier'])
    if bosses_defeated.get(current_tier):
        ctx['results'].append('You have already defeated a boss this tier!')
    else:
        boss_id = random.choice(boss_pool)
        ctx['event_state']['active_boss'] = {
            'boss_id': boss_id,
            'tier': ctx['tier']
        }
        ctx['run'].set_event_state(ctx['event_state'])
        ctx['results'].append(
            f'The hunt begins! Tracking: {boss_id.replace("_", " ").title()}')


def _handle_clear_active_boss(ctx):
    active_boss = ctx['event_state'].get('active_boss', {})
    boss_id = active_boss.get('boss_id')
    boss_tier = active_boss.get('tier', ctx['tier'])
    if boss_id:
        bosses_defeated = ctx['event_state'].get('bosses_defeated', {})
        bosses_defeated[str(boss_tier)] = boss_id
        ctx['event_state']['bosses_defeated'] = bosses_defeated
        ctx['event_state']['active_boss'] = None
        if 'boss_bounty_damage' in ctx['event_state']:
            del ctx['event_state']['boss_bounty_damage']
        ctx['run'].set_event_state(ctx['event_state'])
        ctx['results'].append(
            f'Boss defeated! {boss_id.replace("_", " ").title()} conquered.')


def _handle_store_feed_sacrifice(ctx):
    sacrificed_stats = ctx['selected_option'].get('sacrificed_stats', {})
    if sacrificed_stats:
        ctx['event_state']['feed_sacrifice_stats'] = sacrificed_stats
        ctx['run'].set_event_state(ctx['event_state'])


def _handle_apply_feed_to_beast(ctx):
    feed_stats = ctx['event_state'].get('feed_sacrifice_stats', {})
    target_index = ctx['selected_option'].get('target_index', 0)
    band = ctx['band']
    if feed_stats and target_index < len(band):
        target = band[target_index]
        atk_gain = feed_stats.get('attack', 0)
        hp_gain = feed_stats.get('health', 0)
        sacrificed_name = feed_stats.get('name', 'minion')
        target['attack'] = target.get('attack', 0) + atk_gain
        target['health'] = target.get('health', 0) + hp_gain
        target['permanent_attack'] = target.get('permanent_attack', 0) + atk_gain
        target['permanent_health'] = target.get('permanent_health', 0) + hp_gain
        ctx['run'].set_band(band)
        del ctx['event_state']['feed_sacrifice_stats']
        ctx['run'].set_event_state(ctx['event_state'])
        ctx['results'].append(
            f"{target['name']} consumed {sacrificed_name}'s essence! +{atk_gain}/+{hp_gain}")


def _handle_recruit_random_beast(ctx):
    import random
    from minions import MINIONS
    tier = ctx['tier']
    next_tier = min(tier + 1, 6)
    all_minions = MINIONS.get(next_tier, [])
    beasts = [m for m in all_minions
              if m.get('type') == 'Beast' and m.get('rarity') != 'boss']
    band = ctx['band']
    if beasts:
        chosen = random.choice(beasts)
        new_minion = {
            'name': chosen['name'],
            'health': chosen.get('health', 1),
            'attack': chosen.get('attack', 0),
            'type': chosen.get('type', 'Beast'),
            'keywords': chosen.get('keywords', []).copy(),
            'tier': next_tier
        }
        band.append(new_minion)
        ctx['run'].set_band(band)
        ctx['results'].append(f'Recruited {new_minion["name"]} from the wilds!')
    else:
        ctx['results'].append('No beasts found in the higher tier.')


def _handle_red_gate_abandon_death(ctx):
    band = ctx['band']
    candidate = None
    for minion in band:
        minion_tier = minion.get('tier', 1)
        minion_attack = minion.get('attack', 0)
        minion_health = minion.get('health', 1)
        minion_types = minion.get('type', 'None')
        minion_keywords = minion.get('keywords', [])
        is_tier_2_plus = minion_tier >= 2
        is_zero_attack = minion_attack == 0
        is_one_health = minion_health == 1
        has_no_types = (minion_types == 'None' or minion_types is None or
                       (isinstance(minion_types, list) and len(minion_types) == 0))
        has_no_keywords = len(minion_keywords) == 0
        if (is_tier_2_plus and is_zero_attack and is_one_health
                and has_no_types and has_no_keywords):
            candidate = minion
            break
    if candidate:
        if 'keywords' not in candidate:
            candidate['keywords'] = []
        candidate['keywords'].append('ethereal')
        ctx['run'].set_band(band)
        completed_events = ctx['event_state'].get('completed_events', [])
        if 'the_red_gate' not in completed_events:
            completed_events.append('the_red_gate')
        ctx['event_state']['completed_events'] = completed_events
        ctx['run'].set_event_state(ctx['event_state'])
        ctx['results'].append(
            f'{candidate["name"]} has transcended! Gained Ethereal [Last]!')
    else:
        ctx['results'].append('No valid candidate found for transcendence.')


def _handle_great_work_lichdom(ctx):
    ctx['run'].health = 5
    hero_effects = ctx['run'].get_hero_effects()
    hero_effects['lichdom'] = True
    ctx['run'].set_hero_effects(hero_effects)
    completed_events = ctx['event_state'].get('completed_events', [])
    if 'the_great_work' not in completed_events:
        completed_events.append('the_great_work')
    ctx['event_state']['completed_events'] = completed_events
    ctx['run'].set_event_state(ctx['event_state'])
    ctx['results'].append(
        'You have achieved Lichdom! Health set to 5. Health costs now use gold instead.')


CUSTOM_HANDLERS = {
    'grant_gold_3x_tier_maybe_combat': _handle_grant_gold_3x_tier_maybe_combat,
    'grand_city_upgrade_hero': _handle_grand_city_upgrade_hero,
    'scrap_heap_brave_smog': _handle_scrap_heap_brave_smog,
    'scrap_heap_suffer_through': _handle_scrap_heap_suffer_through,
    'ivory_tower_gain_slot': _handle_ivory_tower_gain_slot,
    'start_boss_hunt': _handle_start_boss_hunt,
    'clear_active_boss': _handle_clear_active_boss,
    'store_feed_sacrifice': _handle_store_feed_sacrifice,
    'apply_feed_to_beast': _handle_apply_feed_to_beast,
    'recruit_random_beast_tier_plus_1': _handle_recruit_random_beast,
    'red_gate_abandon_death': _handle_red_gate_abandon_death,
    'great_work_lichdom': _handle_great_work_lichdom,
}


# ==================== MAIN EXECUTOR ====================


def execute_on_select(on_select, run, tier, band, event_state, resources,
                      results, selected_option):
    """
    Execute an on_select handler. Single entry point replacing the if/elif chain.

    Args:
        on_select: Handler name string (e.g., 'increment_bells_rung')
        run: Current run object
        tier: Current ring/tier
        band: Current band (mutable list)
        event_state: Current event state (mutable dict)
        resources: Current resources (mutable dict)
        results: Results list to append messages to
        selected_option: The selected option dict

    Returns:
        None on success, or a failure result dict if a pay_health action fails
    """
    if not on_select:
        return None

    ctx = {
        'run': run,
        'tier': tier,
        'band': band,
        'event_state': event_state,
        'resources': resources,
        'results': results,
        'selected_option': selected_option,
        '_failed': False,
    }

    # Check declarative registry first
    if on_select in EFFECT_REGISTRY:
        actions = EFFECT_REGISTRY[on_select]
        for action in actions:
            action_type = action['type']
            executor = ACTION_EXECUTORS.get(action_type)
            if executor:
                executor(ctx, action)
                if ctx.get('_failed'):
                    return ctx['_failure_result']
            else:
                logger.warning(f"[WARN] Unknown action type: {action_type}")
        return None

    # Check custom handlers
    if on_select in CUSTOM_HANDLERS:
        CUSTOM_HANDLERS[on_select](ctx)
        if ctx.get('_failed'):
            return ctx['_failure_result']
        return None

    # Unknown handler - warn but don't crash
    logger.warning(f"[WARN] Unknown on_select handler: {on_select}")
    return None


def is_registered(handler_name):
    """Check if a handler name is registered (useful for validation)."""
    return handler_name in EFFECT_REGISTRY or handler_name in CUSTOM_HANDLERS


def get_all_handler_names():
    """Get all registered handler names (useful for validation/testing)."""
    return sorted(set(list(EFFECT_REGISTRY.keys()) + list(CUSTOM_HANDLERS.keys())))
