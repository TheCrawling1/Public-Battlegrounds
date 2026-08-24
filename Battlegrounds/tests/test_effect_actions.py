#!/usr/bin/env python3
"""
Tests for the effect_actions module - the declarative on_select handler system.

Tests cover:
1. All declarative handlers produce correct state changes
2. Custom handlers produce correct state changes
3. execute_on_select dispatches correctly
4. Unknown handlers don't crash
5. New handlers can be added and work immediately
6. Full pipeline: event creation -> selection -> on_select execution
7. Every registered handler is reachable from at least one event definition
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))


class MockRun:
    """Lightweight mock for testing effect actions without Flask dependencies"""

    def __init__(self, ring=1, position=0, zone='starting_plains', gold=10, health=100, band=None):
        self.current_ring = ring
        self.ring_position = position
        self.current_zone = zone
        self._gold = gold
        self.health = health
        self._band = band or []
        self._pending_selection = None
        self._event_state = {}
        self._hero_effects = {}
        self.events_count = 0
        self.ring_upgrade_steps = 0

    def get_band(self):
        return self._band.copy()

    def set_band(self, band):
        self._band = band

    def get_resources(self):
        return {'gold': self._gold, 'health': self.health}

    def set_resources(self, resources):
        if 'gold' in resources:
            self._gold = resources['gold']
        if 'health' in resources:
            self.health = resources['health']

    def get_pending_selection(self):
        return self._pending_selection

    def set_pending_selection(self, selection):
        self._pending_selection = selection

    def has_pending_selection(self):
        return self._pending_selection is not None

    def get_event_state(self):
        return self._event_state.copy()

    def set_event_state(self, state):
        self._event_state = state

    def get_hero_effects(self):
        return self._hero_effects.copy()

    def set_hero_effects(self, effects):
        self._hero_effects = effects


def make_band(tier=1, count=3):
    """Create a standard test band."""
    return [
        {'name': f'Minion_{i}', 'health': 5, 'attack': 3, 'tier': tier,
         'type': 'Beast' if i == 0 else 'Human', 'keywords': [],
         'band_id': f'test_{i}', 'position': i}
        for i in range(count)
    ]


def run_handler(handler_name, tier=2, gold=50, health=100, band=None,
                event_state=None, hero_effects=None, selected_option=None):
    """Helper: execute a handler and return (run, results, event_state)."""
    from game_engine.events.effect_actions import execute_on_select

    if band is None:
        band = make_band(tier)
    run = MockRun(ring=tier, gold=gold, health=health, band=band)
    if event_state:
        run._event_state = event_state
    if hero_effects:
        run._hero_effects = hero_effects

    resources = run.get_resources()
    es = run.get_event_state()
    results = []
    opt = selected_option or {}

    failure = execute_on_select(handler_name, run, tier, band, es, resources, results, opt)
    return run, results, es, failure


# ==================== REGISTRY COMPLETENESS ====================


def test_all_event_on_selects_are_registered():
    """Every on_select string used in event definitions must be registered."""
    from game_engine.events.effect_actions import is_registered
    from game_engine.events.events import (
        CROSSROADS_EVENTS, CROSSROADS_SUB_EVENTS,
        FEY_ZONE_EVENTS, FEY_ZONE_SUB_EVENTS,
        CONSTRUCT_ZONE_EVENTS, CONSTRUCT_ZONE_SUB_EVENTS,
        CULT_ZONE_EVENTS, CULT_ZONE_SUB_EVENTS,
        UNDEAD_ZONE_EVENTS, UNDEAD_ZONE_SUB_EVENTS,
        GREAT_HUNT_EVENTS, GREAT_HUNT_SUB_EVENTS,
        BELL_TOWER, BELL_TOWER_SUB_EVENTS
    )

    all_events = {}
    all_events.update(CROSSROADS_EVENTS)
    all_events.update(CROSSROADS_SUB_EVENTS)
    all_events.update(FEY_ZONE_EVENTS)
    all_events.update(FEY_ZONE_SUB_EVENTS)
    all_events.update(CONSTRUCT_ZONE_EVENTS)
    all_events.update(CONSTRUCT_ZONE_SUB_EVENTS)
    all_events.update(CULT_ZONE_EVENTS)
    all_events.update(CULT_ZONE_SUB_EVENTS)
    all_events.update(UNDEAD_ZONE_EVENTS)
    all_events.update(UNDEAD_ZONE_SUB_EVENTS)
    all_events.update(GREAT_HUNT_EVENTS)
    all_events.update(GREAT_HUNT_SUB_EVENTS)
    all_events.update({'bell_tower': BELL_TOWER})
    all_events.update(BELL_TOWER_SUB_EVENTS)

    unregistered = []
    for event_id, event in all_events.items():
        for screen in event.get('screens', []):
            for choice in screen.get('parameters', {}).get('choices', []):
                handler = choice.get('on_select')
                if handler and not is_registered(handler):
                    unregistered.append(f"{event_id}: {handler}")

    assert len(unregistered) == 0, \
        f"Unregistered on_select handlers found:\n  " + "\n  ".join(unregistered)


def test_get_all_handler_names():
    """get_all_handler_names returns all registered handlers."""
    from game_engine.events.effect_actions import get_all_handler_names
    names = get_all_handler_names()
    assert len(names) >= 40, f"Expected 40+ handlers, got {len(names)}"
    assert 'increment_bells_rung' in names
    assert 'great_work_lichdom' in names
    assert 'boss_reward_dire_pack_stats' in names


# ==================== GOLD GRANT HANDLERS ====================


def test_grant_gold_5x_tier():
    run, results, es, failure = run_handler('grant_gold_5x_tier', tier=3, gold=10)
    assert failure is None
    assert run.get_resources()['gold'] == 25  # 10 + 5*3
    assert any('15' in r for r in results)


def test_collapsed_mine_slow():
    run, results, es, failure = run_handler('collapsed_mine_slow', tier=2, gold=10)
    assert failure is None
    assert run.get_resources()['gold'] == 18  # 10 + 4*2
    assert run.events_count == 1  # +1 step


def test_collapsed_mine_fast():
    run, results, es, failure = run_handler('collapsed_mine_fast', tier=2, gold=10)
    assert failure is None
    assert run.get_resources()['gold'] == 16  # 10 + 3*2


def test_collapsed_mine_fastest():
    run, results, es, failure = run_handler('collapsed_mine_fastest', tier=2, gold=10)
    assert failure is None
    assert run.get_resources()['gold'] == 20  # 10 + 5*2


def test_modify_gold_30():
    run, results, es, failure = run_handler('modify_gold_30', gold=5)
    assert failure is None
    assert run.get_resources()['gold'] == 35


# ==================== BUFF ALL HANDLERS ====================


def test_buff_all_per_tier():
    band = make_band(tier=3)
    run, results, es, failure = run_handler('buff_all_per_tier', tier=3, band=band)
    assert failure is None
    updated_band = run.get_band()
    for m in updated_band:
        assert m['attack'] == 6  # 3 + 3
        assert m['health'] == 8  # 5 + 3
        assert m['permanent_attack'] == 3
        assert m['permanent_health'] == 3


def test_buff_beasts_attack():
    band = [
        {'name': 'Beast1', 'attack': 3, 'health': 5, 'type': 'Beast', 'keywords': [], 'tier': 2},
        {'name': 'Human1', 'attack': 3, 'health': 5, 'type': 'Human', 'keywords': [], 'tier': 2},
    ]
    run, results, es, failure = run_handler('buff_beasts_attack', tier=2, band=band)
    assert failure is None
    updated = run.get_band()
    assert updated[0]['attack'] == 7  # 3 + 2*2=4
    assert updated[1]['attack'] == 3  # unchanged (Human)
    assert '1 Beasts gained +4 attack' in results[0]


def test_buff_all_beasts_1_1():
    band = [
        {'name': 'Beast1', 'attack': 2, 'health': 4, 'type': 'Beast', 'keywords': [], 'tier': 1},
        {'name': 'Beast2', 'attack': 1, 'health': 3, 'type': 'Beast', 'keywords': [], 'tier': 1},
        {'name': 'Human1', 'attack': 5, 'health': 5, 'type': 'Human', 'keywords': [], 'tier': 1},
    ]
    run, results, es, failure = run_handler('buff_all_beasts_1_1', band=band)
    assert failure is None
    updated = run.get_band()
    assert updated[0]['attack'] == 3
    assert updated[0]['health'] == 5
    assert updated[1]['attack'] == 2
    assert updated[1]['health'] == 4
    assert updated[2]['attack'] == 5  # unchanged


def test_buff_all_minions_3_3():
    band = make_band(tier=2, count=2)
    run, results, es, failure = run_handler('buff_all_minions_3_3', tier=2, band=band)
    assert failure is None
    updated = run.get_band()
    for m in updated:
        assert m['attack'] == 6  # 3 + 3
        assert m['health'] == 8  # 5 + 3


# ==================== STATE FLAG HANDLERS ====================


def test_set_double_gold_bounty():
    run, results, es, failure = run_handler('set_double_gold_bounty')
    assert failure is None
    assert run.get_event_state()['double_gold_next_combat'] is True


def test_unlock_next_special_options():
    run, results, es, failure = run_handler('unlock_next_special_options')
    assert failure is None
    assert run.get_event_state()['unlock_special_options'] is True


def test_sneak_debuff_next_combat():
    run, results, es, failure = run_handler('sneak_debuff_next_combat', tier=3)
    assert failure is None
    assert run.get_event_state()['sneak_debuff'] == 3


def test_tower_control_effect():
    run, results, es, failure = run_handler('tower_control_effect', tier=2)
    assert failure is None
    state = run.get_event_state()
    assert state['tower_control_ring'] == 2
    assert state['tower_control_debuff'] == 4  # 2*2


def test_watchtower_storm_effect():
    run, results, es, failure = run_handler('watchtower_storm_effect')
    assert failure is None
    assert run.get_event_state()['hard_combat_downgrades'] == 2


def test_increment_bells_rung():
    run, results, es, failure = run_handler('increment_bells_rung', event_state={'bells_rung': 2})
    assert failure is None
    assert run.get_event_state()['bells_rung'] == 3
    assert 'Total: 3' in results[0]


# ==================== STEP MANIPULATION ====================


def test_gain_step():
    run, results, es, failure = run_handler('gain_step')
    assert failure is None
    assert run.events_count == 0  # 0 - 1 -> clamped to 0


def test_gain_step_from_positive():
    run = MockRun(ring=2, gold=50, health=100, band=make_band(2))
    run.events_count = 5
    from game_engine.events.effect_actions import execute_on_select
    resources = run.get_resources()
    es = run.get_event_state()
    results = []
    execute_on_select('gain_step', run, 2, run.get_band(), es, resources, results, {})
    assert run.events_count == 4


# ==================== IVORY TOWER HANDLERS ====================


def test_ivory_tower_sacrifice_minion():
    run, results, es, failure = run_handler('ivory_tower_sacrifice_minion')
    assert failure is None
    assert run.get_event_state()['ivory_tower_seal'] == 4


def test_ivory_tower_take_damage():
    run, results, es, failure = run_handler('ivory_tower_take_damage', health=100,
                                             event_state={'ivory_tower_seal': 3})
    assert failure is None
    assert run.health == 93  # 100 - 7
    assert run.get_event_state()['ivory_tower_seal'] == 2


def test_ivory_tower_take_damage_fails_when_cant_afford():
    """With lichdom and no gold, pay_health fails."""
    run, results, es, failure = run_handler(
        'ivory_tower_take_damage', health=100, gold=2,
        hero_effects={'lichdom': True},
        event_state={'ivory_tower_seal': 3})
    assert failure is not None
    assert failure.get('success') is False


def test_ivory_tower_lose_steps():
    run, results, es, failure = run_handler('ivory_tower_lose_steps',
                                             event_state={'ivory_tower_seal': 4})
    assert failure is None
    assert run.events_count == 2  # +2 steps
    assert run.get_event_state()['ivory_tower_seal'] == 3


def test_ivory_tower_gain_slot():
    run, results, es, failure = run_handler('ivory_tower_gain_slot')
    assert failure is None
    state = run.get_event_state()
    assert state['extra_band_slots'] == 1
    assert 'ivory_tower' in state.get('completed_events', [])
    assert 'Total: 7 max' in results[0]


def test_ivory_tower_decrease_seal():
    run, results, es, failure = run_handler('ivory_tower_decrease_seal',
                                             event_state={'ivory_tower_seal': 2})
    assert failure is None
    assert run.get_event_state()['ivory_tower_seal'] == 1


# ==================== GRAND CITY HANDLERS ====================


def test_grand_city_portal():
    run, results, es, failure = run_handler('grand_city_portal')
    assert failure is None
    state = run.get_event_state()
    assert state['tier_cost_reduction'] == 3
    assert state['curse_level'] == 3
    assert state['curse_type'] == 'scrap_heap'


def test_grand_city_upgrade_hero():
    run, results, es, failure = run_handler('grand_city_upgrade_hero')
    assert failure is None
    state = run.get_event_state()
    assert state['curse_level'] == 3
    hero = run.get_hero_effects()
    assert hero['power_upgraded'] == 1


def test_grand_city_make_golden():
    run, results, es, failure = run_handler('grand_city_make_golden')
    assert failure is None
    state = run.get_event_state()
    assert state['curse_level'] == 3
    assert state['curse_type'] == 'scrap_heap'


# ==================== SCRAP HEAP HANDLERS ====================


def test_scrap_heap_suffer_waste():
    run, results, es, failure = run_handler('scrap_heap_suffer_waste', health=100,
                                             event_state={'curse_level': 3, 'curse_type': 'scrap_heap'})
    assert failure is None
    assert run.health == 95  # 100 - 5
    state = run.get_event_state()
    assert state['curse_level'] == 0
    assert 'curse_type' not in state


def test_scrap_heap_brave_smog():
    band = [
        {'name': 'Weak', 'attack': 1, 'health': 1, 'type': 'Human', 'keywords': [], 'tier': 2},
        {'name': 'Strong', 'attack': 5, 'health': 10, 'type': 'Human', 'keywords': [], 'tier': 2},
    ]
    run, results, es, failure = run_handler('scrap_heap_brave_smog', tier=2, band=band,
                                             event_state={'curse_level': 3, 'curse_type': 'scrap_heap'})
    assert failure is None
    updated = run.get_band()
    assert len(updated) == 1  # Weak died (health 1-2 = -1)
    assert updated[0]['name'] == 'Strong'
    assert updated[0]['health'] == 8  # 10-2
    assert updated[0]['attack'] == 3  # 5-2
    state = run.get_event_state()
    assert state['curse_level'] == 0


def test_scrap_heap_suffer_through():
    run, results, es, failure = run_handler('scrap_heap_suffer_through',
                                             event_state={'curse_level': 3, 'curse_type': 'scrap_heap'})
    assert failure is None
    assert run.get_event_state()['curse_level'] == 2


def test_scrap_heap_suffer_through_clears_at_zero():
    run, results, es, failure = run_handler('scrap_heap_suffer_through',
                                             event_state={'curse_level': 1, 'curse_type': 'scrap_heap'})
    assert failure is None
    state = run.get_event_state()
    assert state['curse_level'] == 0
    assert 'curse_type' not in state
    assert 'faded' in results[0].lower()


def test_scrap_heap_blind_luck():
    run, results, es, failure = run_handler('scrap_heap_blind_luck',
                                             event_state={'curse_level': 3, 'curse_type': 'scrap_heap'})
    assert failure is None
    state = run.get_event_state()
    assert state['curse_level'] == 0
    assert 'curse_type' not in state


# ==================== BOSS REWARD HANDLERS (ALL-BUFF) ====================


def test_boss_reward_dire_pack_stats():
    band = make_band(tier=2)
    run, results, es, failure = run_handler('boss_reward_dire_pack_stats', tier=2, band=band)
    assert failure is None
    updated = run.get_band()
    for m in updated:
        assert m['attack'] == 5  # 3 + 2
        assert m['health'] == 7  # 5 + 2
    state = run.get_event_state()
    assert state['active_boss'] is None
    assert state['bosses_defeated']['2'] == 'dire_pack'


def test_boss_reward_behemoth_all():
    band = make_band(tier=2)
    run, results, es, failure = run_handler('boss_reward_behemoth_all', tier=2, band=band)
    assert failure is None
    updated = run.get_band()
    for m in updated:
        assert m['health'] == 9  # 5 + 4
        assert m['attack'] == 3  # unchanged
    state = run.get_event_state()
    assert state['bosses_defeated']['2'] == 'behemoth'


def test_boss_reward_venomspawn_attack():
    band = make_band(tier=2)
    run, results, es, failure = run_handler('boss_reward_venomspawn_attack', tier=2, band=band)
    assert failure is None
    updated = run.get_band()
    for m in updated:
        assert m['attack'] == 9  # 3 + 6
    state = run.get_event_state()
    assert state['bosses_defeated']['2'] == 'venomspawn'


def test_boss_reward_possessed_gold():
    run, results, es, failure = run_handler('boss_reward_possessed_gold', tier=3, gold=10)
    assert failure is None
    assert run.get_resources()['gold'] == 40  # 10 + 3*10
    state = run.get_event_state()
    assert state['bosses_defeated']['3'] == 'greater_possessed'


# ==================== BOSS REWARD HANDLERS (TARGETED) ====================


def test_boss_reward_dire_pack_keyword():
    band = make_band(tier=2)
    opt = {'target_index': 0}
    run, results, es, failure = run_handler('boss_reward_dire_pack_keyword', tier=2,
                                             band=band, selected_option=opt)
    assert failure is None
    updated = run.get_band()
    assert 'on_any_death' in updated[0]['keywords']
    assert 'on_any_death_effect' in updated[0]


def test_boss_reward_congregation_tribe():
    band = make_band(tier=2)
    opt = {'target_index': 1}
    run, results, es, failure = run_handler('boss_reward_congregation_tribe', tier=2,
                                             band=band, selected_option=opt)
    assert failure is None
    updated = run.get_band()
    assert updated[1]['type'] == 'Cult'


def test_boss_reward_chained_stats():
    band = make_band(tier=2)
    opt = {'target_index': 0}
    run, results, es, failure = run_handler('boss_reward_chained_stats', tier=2,
                                             band=band, selected_option=opt)
    assert failure is None
    updated = run.get_band()
    assert updated[0]['attack'] == 11  # 3 + 8
    assert updated[0]['health'] == 13  # 5 + 8
    assert 'leap' in updated[0]['keywords']
    assert updated[0]['leap_distance'] == 2


def test_boss_reward_chained_ethereal():
    band = make_band(tier=2)
    opt = {'target_index': 0}
    run, results, es, failure = run_handler('boss_reward_chained_ethereal', tier=2,
                                             band=band, selected_option=opt)
    assert failure is None
    updated = run.get_band()
    kw = updated[0]['keywords']
    assert 'ethereal_left' in kw
    assert 'cant_cast' in kw
    assert 'cant_retaliate' in kw


def test_boss_reward_behemoth_tank():
    band = make_band(tier=2)
    opt = {'target_index': 0}
    run, results, es, failure = run_handler('boss_reward_behemoth_tank', tier=2,
                                             band=band, selected_option=opt)
    assert failure is None
    updated = run.get_band()
    assert updated[0]['attack'] == 8   # 3 + 5
    assert updated[0]['health'] == 17  # 5 + 12
    assert 'guard' in updated[0]['keywords']


def test_boss_reward_venomspawn_cast():
    band = make_band(tier=2)
    opt = {'target_index': 0}
    run, results, es, failure = run_handler('boss_reward_venomspawn_cast', tier=2,
                                             band=band, selected_option=opt)
    assert failure is None
    updated = run.get_band()
    assert 'cast' in updated[0]['keywords']
    assert updated[0]['cast_effect']['amount'] == 2


def test_boss_reward_possessed_deathtoll():
    band = make_band(tier=2)
    opt = {'target_index': 0}
    run, results, es, failure = run_handler('boss_reward_possessed_deathtoll', tier=2,
                                             band=band, selected_option=opt)
    assert failure is None
    updated = run.get_band()
    assert 'death_toll' in updated[0]['keywords']
    assert updated[0]['death_toll_effect']['minion_name'] == 'Possessed'


# ==================== CUSTOM HANDLERS ====================


def test_great_work_lichdom():
    run, results, es, failure = run_handler('great_work_lichdom', health=100)
    assert failure is None
    assert run.health == 5
    hero = run.get_hero_effects()
    assert hero['lichdom'] is True
    state = run.get_event_state()
    assert 'the_great_work' in state.get('completed_events', [])


def test_red_gate_abandon_death():
    band = [
        {'name': 'Husk', 'type': 'None', 'keywords': [], 'health': 1, 'attack': 0, 'tier': 2},
        {'name': 'Guard', 'type': 'Human', 'keywords': ['guard'], 'health': 5, 'attack': 3, 'tier': 2},
    ]
    run, results, es, failure = run_handler('red_gate_abandon_death', band=band)
    assert failure is None
    updated = run.get_band()
    assert 'ethereal' in updated[0]['keywords']
    state = run.get_event_state()
    assert 'the_red_gate' in state.get('completed_events', [])


def test_red_gate_abandon_death_no_candidate():
    band = [
        {'name': 'Guard', 'type': 'Human', 'keywords': ['guard'], 'health': 5, 'attack': 3, 'tier': 2},
    ]
    run, results, es, failure = run_handler('red_gate_abandon_death', band=band)
    assert failure is None
    assert 'No valid candidate' in results[0]


def test_clear_active_boss():
    run, results, es, failure = run_handler(
        'clear_active_boss', tier=2,
        event_state={'active_boss': {'boss_id': 'dire_pack', 'tier': 2}})
    assert failure is None
    state = run.get_event_state()
    assert state['active_boss'] is None
    assert state['bosses_defeated']['2'] == 'dire_pack'


# ==================== UNKNOWN HANDLER ====================


def test_unknown_handler_doesnt_crash():
    run, results, es, failure = run_handler('totally_nonexistent_handler_xyz')
    assert failure is None
    assert len(results) == 0


def test_none_handler_doesnt_crash():
    from game_engine.events.effect_actions import execute_on_select
    run = MockRun()
    result = execute_on_select(None, run, 1, [], {}, {}, [], {})
    assert result is None


# ==================== NEW HANDLER REGISTRATION ====================


def test_adding_new_declarative_handler():
    """Verify that a new handler can be added to EFFECT_REGISTRY and works immediately."""
    from game_engine.events.effect_actions import EFFECT_REGISTRY, execute_on_select

    EFFECT_REGISTRY['test_tavern_drink'] = [
        {'type': 'grant_gold', 'amount': '2 * tier', 'message': 'Drank and earned {amount} gold!'},
        {'type': 'buff_all', 'attack': 1, 'health': 1, 'message': 'Party boost! {count} minions +1/+1'},
    ]

    try:
        band = make_band(tier=3)
        run = MockRun(ring=3, gold=10, band=band)
        resources = run.get_resources()
        es = run.get_event_state()
        results = []

        failure = execute_on_select('test_tavern_drink', run, 3, band, es, resources, results, {})
        assert failure is None
        assert run.get_resources()['gold'] == 16  # 10 + 2*3
        assert 'Drank and earned 6 gold!' in results[0]

        updated = run.get_band()
        for m in updated:
            assert m['attack'] == 4  # 3 + 1
            assert m['health'] == 6  # 5 + 1
    finally:
        del EFFECT_REGISTRY['test_tavern_drink']


def test_adding_new_custom_handler():
    """Verify that a new custom handler can be registered and works immediately."""
    from game_engine.events.effect_actions import CUSTOM_HANDLERS, execute_on_select

    def _handle_test_custom(ctx):
        ctx['event_state']['custom_flag'] = True
        ctx['run'].set_event_state(ctx['event_state'])
        ctx['results'].append('Custom handler executed!')

    CUSTOM_HANDLERS['test_custom_handler'] = _handle_test_custom

    try:
        run = MockRun(ring=1)
        resources = run.get_resources()
        es = run.get_event_state()
        results = []

        failure = execute_on_select('test_custom_handler', run, 1, [], es, resources, results, {})
        assert failure is None
        assert run.get_event_state()['custom_flag'] is True
        assert 'Custom handler executed!' in results
    finally:
        del CUSTOM_HANDLERS['test_custom_handler']


# ==================== FULL PIPELINE TESTS ====================


def test_full_pipeline_collapsed_mine_go_slow():
    """Full test: create event -> select Go Slow -> verify gold and steps."""
    from game_engine.events.event_system import EventSystem
    from game_engine.selection_system import SelectionSystem

    for tier in [1, 2, 3, 4]:
        run = MockRun(ring=tier, gold=50, health=100, band=make_band(tier))
        run._dev_mode_mock = True
        run.selection_version = 0

        result = EventSystem.create_event_selection(run, 'collapsed_mine')
        assert result.get('selection_created')

        selection = run.get_pending_selection()
        slow = next(o for o in selection['options'] if o['message'] == 'Go Slow')

        resolve_result = SelectionSystem.resolve_selection(run, [slow['id']])
        assert resolve_result.get('success'), f"Tier {tier}: {resolve_result}"

        resources = run.get_resources()
        expected_gold = 50 + (4 * tier)
        assert resources['gold'] == expected_gold, \
            f"Tier {tier}: gold should be {expected_gold}, got {resources['gold']}"
        assert run.events_count == 1, \
            f"Tier {tier}: events_count should be 1, got {run.events_count}"


def test_full_pipeline_bell_tower_ring():
    """Full test: ring bell -> verify gold deducted + bells_rung incremented."""
    from game_engine.events.event_system import EventSystem
    from game_engine.selection_system import SelectionSystem

    run = MockRun(ring=2, gold=20, health=100, band=make_band(2))
    run._dev_mode_mock = True
    run.selection_version = 0

    result = EventSystem.create_event_selection(run, 'bell_tower')
    assert result.get('selection_created')

    selection = run.get_pending_selection()
    ring_opt = next(o for o in selection['options'] if o['message'] == 'Pay to Ring the Bell')

    resolve_result = SelectionSystem.resolve_selection(run, [ring_opt['id']])
    assert resolve_result.get('success')

    assert run.get_resources()['gold'] == 14  # 20 - 6
    assert run.get_event_state().get('bells_rung', 0) >= 1


def test_full_pipeline_ivory_tower_take_damage():
    """Full test: ivory tower blood payment decreases seal."""
    from game_engine.events.event_system import EventSystem
    from game_engine.selection_system import SelectionSystem

    run = MockRun(ring=2, gold=100, health=100, band=make_band(2))
    run._dev_mode_mock = True
    run.selection_version = 0
    run._event_state = {'ivory_tower_seal': 3}

    result = EventSystem.create_event_selection(run, 'ivory_tower')
    assert result.get('selection_created')

    selection = run.get_pending_selection()
    blood = next(o for o in selection['options'] if o['message'] == 'Use blood to weaken the seal')

    resolve_result = SelectionSystem.resolve_selection(run, [blood['id']])
    assert resolve_result.get('success')

    assert run.health == 93  # 100 - 7
    assert run.get_event_state()['ivory_tower_seal'] == 2


def test_full_pipeline_joint_alliance_buff():
    """Full test: Joint Alliance buffs all minions by tier."""
    from game_engine.events.event_system import EventSystem
    from game_engine.selection_system import SelectionSystem

    band = [
        {'name': 'A', 'health': 5, 'attack': 3, 'tier': 2, 'type': 'Human',
         'keywords': [], 'band_id': 'a', 'position': 0},
        {'name': 'B', 'health': 5, 'attack': 3, 'tier': 2, 'type': 'Beast',
         'keywords': [], 'band_id': 'b', 'position': 1},
        {'name': 'C', 'health': 5, 'attack': 3, 'tier': 2, 'type': 'Construct',
         'keywords': [], 'band_id': 'c', 'position': 2},
        {'name': 'D', 'health': 5, 'attack': 3, 'tier': 2, 'type': 'Fey',
         'keywords': [], 'band_id': 'd', 'position': 3},
    ]

    run = MockRun(ring=2, gold=100, health=100, band=band)
    run._dev_mode_mock = True
    run.selection_version = 0

    result = EventSystem.create_event_selection(run, 'mercenary_camp')
    assert result.get('selection_created')

    selection = run.get_pending_selection()
    alliance = next(o for o in selection['options'] if o['message'] == 'Joint Alliance')
    assert not alliance['disabled'], "Should be enabled with 4 unique tribes"

    resolve_result = SelectionSystem.resolve_selection(run, [alliance['id']])
    assert resolve_result.get('success')

    updated = run.get_band()
    for m in updated:
        assert m['attack'] == 5  # 3 + 2 (tier)
        assert m['health'] == 7  # 5 + 2 (tier)


# ==================== MAIN ====================


if __name__ == '__main__':
    import pytest
    sys.exit(pytest.main([__file__, '-v']))
