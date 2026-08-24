#!/usr/bin/env python3
"""
Comprehensive pipeline verification for ALL general events.

Tests that every make_choice event actually produces correct:
1. Tooltips - no unresolved {variables}, correct values at every tier
2. Options - correct count, names, gold costs, health costs
3. Conditions - disabled/enabled states are correct
4. Chaining - next_event, next_screen, on_select are properly passed through
5. Icons - every choice has an icon

This is the "actually works" test - runs each event through the real
EventSystem.create_event_selection pipeline, not just the helpers.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from game_engine.events.event_system import EventSystem


class MockRun:
    """Lightweight mock for pipeline testing"""

    def __init__(self, ring=1, position=0, zone='starting_plains', gold=100, health=100, band=None):
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
        self._dev_mode_mock = True
        self.selection_version = 0

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


# Standard test band
def make_band(tier=1, types=None, keywords=None):
    """Create a test band with configurable types and keywords"""
    types = types or ['Human', 'Beast', 'Construct']
    keywords = keywords or [[], [], []]
    band = []
    for i, (t, kw) in enumerate(zip(types, keywords)):
        band.append({
            'name': f'Minion_{i}', 'health': 5, 'attack': 3, 'tier': tier,
            'type': t, 'keywords': kw, 'band_id': f'test_{i}', 'position': i
        })
    return band


def create_event_and_get_options(event_id, tier=1, band=None, event_state=None, hero_effects=None, gold=100):
    """Helper: create an event selection and return the options list"""
    if band is None:
        band = make_band(tier)
    run = MockRun(ring=tier, gold=gold, health=100, band=band)
    if event_state:
        run._event_state = event_state
    if hero_effects:
        run._hero_effects = hero_effects

    result = EventSystem.create_event_selection(run, event_id)
    assert result.get('selection_created'), \
        f"Failed to create '{event_id}' at tier {tier}: {result}"

    selection = run.get_pending_selection()
    assert selection is not None, f"No pending selection for '{event_id}'"
    return selection.get('options', []), selection, run


def assert_no_unresolved(options, event_id, tier):
    """Assert no option has unresolved {template} variables in its tooltip"""
    for opt in options:
        tooltip = opt.get('tooltip', '')
        if '{' in tooltip:
            # Allow escaped or non-template braces
            import re
            unresolved = re.findall(r'\{([^}]+)\}', tooltip)
            if unresolved:
                assert False, (
                    f"[{event_id}] Tier {tier}: Unresolved template(s) {unresolved} "
                    f"in '{opt['message']}' tooltip: {tooltip}"
                )


def assert_option_exists(options, name, event_id):
    """Assert an option with the given name exists"""
    match = next((o for o in options if o['message'] == name), None)
    assert match is not None, f"[{event_id}] Option '{name}' not found. Options: {[o['message'] for o in options]}"
    return match


# ==================== COLLAPSED MINE ====================


def test_collapsed_mine_full():
    """Verify Collapsed Mine: 4 options, correct tooltips, conditions, chaining"""
    for tier in [1, 2, 3, 4]:
        options, sel, run = create_event_and_get_options('collapsed_mine', tier,
            band=make_band(tier, keywords=[['fast'], [], []]))

        assert len(options) == 4, f"Tier {tier}: Expected 4 options, got {len(options)}"
        assert_no_unresolved(options, 'collapsed_mine', tier)

        # Go Slow: gold_reward = tier*4, on_select, no next_event
        slow = assert_option_exists(options, 'Go Slow', 'collapsed_mine')
        assert f'({tier * 4})' in slow['tooltip'], f"Tier {tier}: Go Slow tooltip wrong: {slow['tooltip']}"
        assert slow['on_select'] == 'collapsed_mine_slow', f"on_select wrong: {slow['on_select']}"
        assert not slow['disabled'], "Go Slow should be enabled"

        # Go Fast: gold_reward = tier*3
        fast = assert_option_exists(options, 'Go Fast', 'collapsed_mine')
        assert f'({tier * 3})' in fast['tooltip'], f"Tier {tier}: Go Fast tooltip wrong: {fast['tooltip']}"
        assert fast['on_select'] == 'collapsed_mine_fast'

        # Go Faster: gold_reward = tier*5, condition=has_keyword_fast
        faster = assert_option_exists(options, 'Go Faster', 'collapsed_mine')
        assert f'({tier * 5})' in faster['tooltip'], f"Tier {tier}: Go Faster tooltip wrong: {faster['tooltip']}"
        assert faster['on_select'] == 'collapsed_mine_fastest'
        assert not faster['disabled'], "Go Faster should be enabled (band has fast)"

        # Leave: no cost, no action
        leave = assert_option_exists(options, 'Leave', 'collapsed_mine')
        assert leave['gold_cost'] == 0, "Leave should have no gold cost"

    # Test condition: Go Faster disabled without fast keyword
    options, _, _ = create_event_and_get_options('collapsed_mine', 2,
        band=make_band(2, keywords=[['Guard'], [], []]))
    faster = assert_option_exists(options, 'Go Faster', 'collapsed_mine')
    assert faster['disabled'], "Go Faster should be disabled without fast keyword"


# ==================== MERCENARY CAMP ====================


def test_mercenary_camp_full():
    """Verify Mercenary Camp: 5 options, inline tier formulas, Joint Alliance condition"""
    for tier in [1, 2, 3, 4]:
        options, sel, run = create_event_and_get_options('mercenary_camp', tier,
            band=make_band(tier))

        assert len(options) == 5, f"Tier {tier}: Expected 5 options, got {len(options)}"
        assert_no_unresolved(options, 'mercenary_camp', tier)

        # Hire Guard: gold_cost = tier*6, next_event
        hire = assert_option_exists(options, 'Hire Guard', 'mercenary_camp')
        assert hire['gold_cost'] == tier * 6, \
            f"Tier {tier}: Hire Guard cost should be {tier * 6}, got {hire['gold_cost']}"
        assert hire['next_event'] == 'mercenary_camp_hire_guard', \
            f"next_event wrong: {hire['next_event']}"

        # Enter a Duel: tooltip has +{tier*3}/+{tier*3}
        duel = assert_option_exists(options, 'Enter a Duel', 'mercenary_camp')
        expected_buff = tier * 3
        assert f'+{expected_buff}/+{expected_buff}' in duel['tooltip'], \
            f"Tier {tier}: Duel tooltip should show +{expected_buff}/+{expected_buff}: {duel['tooltip']}"
        assert duel['next_event'] == 'mercenary_camp_duel'

        # Hostile Takeover: next_event only
        takeover = assert_option_exists(options, 'Hostile Takeover', 'mercenary_camp')
        assert takeover['next_event'] == 'mercenary_camp_takeover'

        # Joint Alliance: condition=unique_tribes >= 4, disabled with 3 types
        alliance = assert_option_exists(options, 'Joint Alliance', 'mercenary_camp')
        assert f'+{tier}/+{tier}' in alliance['tooltip'], \
            f"Tier {tier}: Alliance tooltip should show +{tier}/+{tier}: {alliance['tooltip']}"
        assert alliance['disabled'], "Joint Alliance should be disabled (only 3 unique tribes)"
        assert alliance['on_select'] == 'buff_all_per_tier'

        # Leave
        assert_option_exists(options, 'Leave', 'mercenary_camp')

    # Test: Joint Alliance enabled with 4+ tribes
    band_4_tribes = make_band(2, types=['Human', 'Beast', 'Construct', 'Fey'],
                               keywords=[[], [], [], []])
    band_4_tribes.append({'name': 'Extra', 'health': 1, 'attack': 1, 'tier': 2,
                          'type': 'Fey', 'keywords': [], 'band_id': 'test_4', 'position': 3})
    options, _, _ = create_event_and_get_options('mercenary_camp', 2, band=band_4_tribes)
    alliance = assert_option_exists(options, 'Joint Alliance', 'mercenary_camp')
    assert not alliance['disabled'], "Joint Alliance should be enabled with 4+ unique tribes"


# ==================== VAST KENNELS ====================


def test_vast_kennels_full():
    """Verify Vast Kennels: 5 options, Buy a Treat tier formula, Pack Discount condition"""
    for tier in [1, 2, 3, 4]:
        options, sel, run = create_event_and_get_options('vast_kennels', tier,
            band=make_band(tier))

        assert len(options) == 5, f"Tier {tier}: Expected 5 options, got {len(options)}"
        assert_no_unresolved(options, 'vast_kennels', tier)

        # Buy a Hound: static gold_cost=2
        hound = assert_option_exists(options, 'Buy a Hound', 'vast_kennels')
        assert hound['gold_cost'] == 2, f"Hound cost should be 2, got {hound['gold_cost']}"
        assert hound['next_event'] == 'kennels_buy_hound'

        # Buy a Cat: static gold_cost=2
        cat = assert_option_exists(options, 'Buy a Cat', 'vast_kennels')
        assert cat['gold_cost'] == 2, f"Cat cost should be 2, got {cat['gold_cost']}"
        assert cat['next_event'] == 'kennels_buy_cat'

        # Buy a Treat: gold_cost=tier*3, tooltip shows +{tier*2} attack
        treat = assert_option_exists(options, 'Buy a Treat', 'vast_kennels')
        assert treat['gold_cost'] == tier * 3, \
            f"Tier {tier}: Treat cost should be {tier * 3}, got {treat['gold_cost']}"
        assert f'({tier * 3})' in treat['tooltip'], \
            f"Tier {tier}: Treat tooltip should show ({tier * 3}): {treat['tooltip']}"
        assert f'+{tier * 2} attack' in treat['tooltip'], \
            f"Tier {tier}: Treat tooltip should show +{tier * 2} attack: {treat['tooltip']}"
        assert treat['on_select'] == 'buff_beasts_attack'

        # Pack Discount: condition=beast_count >= 3
        pack = assert_option_exists(options, 'Pack Discount', 'vast_kennels')
        assert pack['disabled'], "Pack Discount should be disabled (< 3 beasts)"

        # Leave
        assert_option_exists(options, 'Leave', 'vast_kennels')

    # Test: Pack Discount enabled with 3+ beasts
    beast_band = make_band(2, types=['Beast', 'Beast', 'Beast'], keywords=[[], [], []])
    options, _, _ = create_event_and_get_options('vast_kennels', 2, band=beast_band)
    pack = assert_option_exists(options, 'Pack Discount', 'vast_kennels')
    assert not pack['disabled'], "Pack Discount should be enabled with 3+ beasts"


# ==================== WATCHTOWER ====================


def test_watchtower_full():
    """Verify Watchtower: 6 options, gold costs, Infiltrate condition"""
    for tier in [1, 2, 3, 4]:
        options, sel, run = create_event_and_get_options('watchtower', tier,
            band=make_band(tier))

        assert len(options) == 6, f"Tier {tier}: Expected 6 options, got {len(options)}"
        assert_no_unresolved(options, 'watchtower', tier)

        # Pay for Help: gold_cost=tier*6
        pay = assert_option_exists(options, 'Pay for Help', 'watchtower')
        assert pay['gold_cost'] == tier * 6, \
            f"Tier {tier}: Pay cost should be {tier * 6}, got {pay['gold_cost']}"
        assert f'({tier * 6})' in pay['tooltip'], \
            f"Tier {tier}: Pay tooltip should show ({tier * 6}): {pay['tooltip']}"
        assert pay['on_select'] == 'unlock_next_special_options'

        # Storm Tower: next_event
        storm = assert_option_exists(options, 'Storm Tower', 'watchtower')
        assert storm['next_event'] == 'watchtower_storm'

        # Sneak Past: on_select
        sneak = assert_option_exists(options, 'Sneak Past', 'watchtower')
        assert sneak['on_select'] == 'gain_step'

        # Request Aid: gold_cost=tier*3, tooltip shows Tier {tier}
        aid = assert_option_exists(options, 'Request Aid', 'watchtower')
        assert aid['gold_cost'] == tier * 3, \
            f"Tier {tier}: Aid cost should be {tier * 3}, got {aid['gold_cost']}"
        assert f'({tier * 3})' in aid['tooltip'], \
            f"Tier {tier}: Aid tooltip should show ({tier * 3}): {aid['tooltip']}"
        assert f'Tier {tier}' in aid['tooltip'], \
            f"Tier {tier}: Aid tooltip should show 'Tier {tier}': {aid['tooltip']}"
        assert aid['next_event'] == 'watchtower_aid'

        # Infiltrate: condition=has_keyword_hide
        infiltrate = assert_option_exists(options, 'Infiltrate', 'watchtower')
        assert infiltrate['disabled'], "Infiltrate should be disabled (no hide keyword)"
        assert infiltrate['on_select'] == 'watchtower_storm_effect'

        # Leave
        assert_option_exists(options, 'Leave', 'watchtower')

    # Test: Infiltrate enabled with hide keyword
    hide_band = make_band(2, keywords=[['hide'], [], []])
    options, _, _ = create_event_and_get_options('watchtower', 2, band=hide_band)
    infiltrate = assert_option_exists(options, 'Infiltrate', 'watchtower')
    assert not infiltrate['disabled'], "Infiltrate should be enabled with hide keyword"


# ==================== BELL TOWER ====================


def test_bell_tower_full():
    """Verify Bell Tower: 4 options, gold cost formula, Quasimodo condition"""
    for tier in [1, 2, 3, 4]:
        options, sel, run = create_event_and_get_options('bell_tower', tier)

        assert len(options) == 4, f"Tier {tier}: Expected 4 options, got {len(options)}"
        assert_no_unresolved(options, 'bell_tower', tier)

        # Pay to Ring: gold_cost=tier*3, on_select + next_event chaining
        ring = assert_option_exists(options, 'Pay to Ring the Bell', 'bell_tower')
        assert ring['gold_cost'] == tier * 3, \
            f"Tier {tier}: Ring cost should be {tier * 3}, got {ring['gold_cost']}"
        assert f'({tier * 3})' in ring['tooltip'], \
            f"Tier {tier}: Ring tooltip should show ({tier * 3}): {ring['tooltip']}"
        assert f'Ring ({tier})' in ring['tooltip'], \
            f"Tier {tier}: Ring tooltip should show 'Ring ({tier})': {ring['tooltip']}"
        assert ring['on_select'] == 'increment_bells_rung'
        assert ring['next_event'] == 'bell_tower_blessing'

        # Break In: next_event only
        brk = assert_option_exists(options, 'Break In', 'bell_tower')
        assert f'Ring ({tier})' in brk['tooltip'], \
            f"Tier {tier}: Break In tooltip should show 'Ring ({tier})': {brk['tooltip']}"
        assert brk['next_event'] == 'bell_tower_combat'

        # Seek Quasimodo: disabled (bells_rung < 4)
        quasi = assert_option_exists(options, 'Seek Quasimodo', 'bell_tower')
        assert quasi['disabled'], "Seek Quasimodo should be disabled (bells_rung < 4)"
        assert quasi['next_event'] == 'bell_tower_quasimodo'
        assert quasi['mark_event_complete'], "Seek Quasimodo should mark event complete"

    # Test: Quasimodo enabled with 4+ bells
    options, _, _ = create_event_and_get_options('bell_tower', 2,
        event_state={'bells_rung': 4})
    quasi = assert_option_exists(options, 'Seek Quasimodo', 'bell_tower')
    assert not quasi['disabled'], "Seek Quasimodo should be enabled with 4+ bells rung"


# ==================== IVORY TOWER ====================


def test_ivory_tower_full():
    """Verify Ivory Tower: 5 options, seal tracking, health cost, conditions"""
    for tier in [1, 2, 3, 4]:
        options, sel, run = create_event_and_get_options('ivory_tower', tier,
            event_state={'ivory_tower_seal': 3})

        assert len(options) == 5, f"Tier {tier}: Expected 5 options, got {len(options)}"
        assert_no_unresolved(options, 'ivory_tower', tier)

        # Sacrifice: condition=band_size >= 1 (should be enabled with 3 minions)
        sacrifice = assert_option_exists(options, 'Sacrifice to weaken the seal', 'ivory_tower')
        assert not sacrifice['disabled'], "Sacrifice should be enabled (band has 3 minions)"
        assert '(3)' in sacrifice['tooltip'], \
            f"Tier {tier}: Sacrifice tooltip should show seal (3): {sacrifice['tooltip']}"
        assert sacrifice['next_event'] == 'ivory_tower_sacrifice'

        # Blood: health_cost=7, seal display
        blood = assert_option_exists(options, 'Use blood to weaken the seal', 'ivory_tower')
        assert blood['health_cost'] == 7, f"Blood health cost should be 7, got {blood['health_cost']}"
        assert '(3)' in blood['tooltip'], \
            f"Tier {tier}: Blood tooltip should show seal (3): {blood['tooltip']}"

        # Wait: on_select
        wait = assert_option_exists(options, 'Wait the Seal', 'ivory_tower')
        assert wait['on_select'] == 'ivory_tower_lose_steps'
        assert '(3)' in wait['tooltip'], \
            f"Tier {tier}: Wait tooltip should show seal (3): {wait['tooltip']}"

        # Climb: disabled (seal > 0)
        climb = assert_option_exists(options, 'Climb the Tower', 'ivory_tower')
        assert climb['disabled'], "Climb should be disabled (seal > 0)"
        assert climb['mark_event_complete'], "Climb should mark event complete"

    # Test: Climb enabled when seal = 0
    options, _, _ = create_event_and_get_options('ivory_tower', 2,
        event_state={'ivory_tower_seal': 0})
    climb = assert_option_exists(options, 'Climb the Tower', 'ivory_tower')
    assert not climb['disabled'], "Climb should be enabled when seal = 0"


# ==================== GRAND CITY ====================


def test_grand_city_full():
    """Verify Grand City: 4 options, static tooltips, on_select handlers"""
    for tier in [1, 2, 3, 4]:
        options, sel, run = create_event_and_get_options('grand_city', tier)

        assert len(options) == 4, f"Tier {tier}: Expected 4 options, got {len(options)}"
        assert_no_unresolved(options, 'grand_city', tier)

        # Portal Transit
        portal = assert_option_exists(options, 'Portal Transit', 'grand_city')
        assert portal['on_select'] == 'grand_city_portal'
        assert 'Scrap Curse' in portal['tooltip']

        # Upgrade Hero Power
        upgrade = assert_option_exists(options, 'Upgrade Hero Power', 'grand_city')
        assert upgrade['on_select'] == 'grand_city_upgrade_hero'

        # Golden Forge: next_event chaining
        forge = assert_option_exists(options, 'Golden Forge', 'grand_city')
        assert forge['on_select'] == 'grand_city_make_golden'
        assert forge['next_event'] == 'grand_city_golden_forge'

        # Leave
        assert_option_exists(options, 'Leave', 'grand_city')


# ==================== SCRAP HEAP ====================


def test_scrap_heap_full():
    """Verify Scrap Heap: 4 options, health cost, tier formula in tooltip, Blind Luck always disabled"""
    for tier in [1, 2, 3, 4]:
        options, sel, run = create_event_and_get_options('scrap_heap', tier)

        assert len(options) == 4, f"Tier {tier}: Expected 4 options, got {len(options)}"
        assert_no_unresolved(options, 'scrap_heap', tier)

        # Suffer Waste: health_cost=5
        waste = assert_option_exists(options, 'Suffer Waste', 'scrap_heap')
        assert waste['health_cost'] == 5, f"Waste health cost should be 5, got {waste['health_cost']}"
        assert waste['on_select'] == 'scrap_heap_suffer_waste'

        # Brave the Smog: tooltip has -{tier}/-{tier}
        smog = assert_option_exists(options, 'Brave the Smog', 'scrap_heap')
        assert f'-{tier}/-{tier}' in smog['tooltip'], \
            f"Tier {tier}: Smog tooltip should show -{tier}/-{tier}: {smog['tooltip']}"
        assert smog['on_select'] == 'scrap_heap_brave_smog'

        # Suffer Through
        through = assert_option_exists(options, 'Suffer Through', 'scrap_heap')
        assert through['on_select'] == 'scrap_heap_suffer_through'

        # Blind Luck: always disabled
        luck = assert_option_exists(options, 'Blind Luck', 'scrap_heap')
        assert luck['disabled'], "Blind Luck should always be disabled"


# ==================== THE RED GATE ====================


def test_the_red_gate_full():
    """Verify The Red Gate: 6 options, transcendence condition, next_event chaining"""
    for tier in [1, 2, 3, 4]:
        options, sel, run = create_event_and_get_options('the_red_gate', tier)

        assert len(options) == 6, f"Tier {tier}: Expected 6 options, got {len(options)}"
        assert_no_unresolved(options, 'the_red_gate', tier)

        # Abandon Strength: next_event
        strength = assert_option_exists(options, 'Abandon Strength', 'the_red_gate')
        assert strength['next_event'] == 'red_gate_abandon_strength'

        # Abandon Vigor: next_event
        vigor = assert_option_exists(options, 'Abandon Vigor', 'the_red_gate')
        assert vigor['next_event'] == 'red_gate_abandon_vigor'

        # Abandon Skill: next_event
        skill = assert_option_exists(options, 'Abandon Skill', 'the_red_gate')
        assert skill['next_event'] == 'red_gate_abandon_skill'

        # Abandon Allegiance: next_event
        allegiance = assert_option_exists(options, 'Abandon Allegiance', 'the_red_gate')
        assert allegiance['next_event'] == 'red_gate_abandon_allegiance'

        # Abandon Death: disabled (no transcendence candidate)
        death = assert_option_exists(options, 'Abandon Death', 'the_red_gate')
        assert death['disabled'], "Abandon Death should be disabled (no candidate)"
        assert death['mark_event_complete']

        # Leave
        assert_option_exists(options, 'Leave', 'the_red_gate')

    # Test: Abandon Death enabled with valid candidate
    candidate_band = [
        {'name': 'Husk', 'type': 'None', 'keywords': [], 'health': 1, 'attack': 0,
         'tier': 2, 'band_id': 'husk', 'position': 0},
        {'name': 'Guard', 'type': 'Human', 'keywords': [], 'health': 5, 'attack': 3,
         'tier': 2, 'band_id': 'guard', 'position': 1},
    ]
    options, _, _ = create_event_and_get_options('the_red_gate', 2, band=candidate_band)
    death = assert_option_exists(options, 'Abandon Death', 'the_red_gate')
    assert not death['disabled'], "Abandon Death should be enabled with transcendence candidate"


# ==================== THE GREAT WORK ====================


def test_the_great_work_full():
    """Verify The Great Work: 5 options, health_cost_tracker, Lichdom condition, ad_nauseam"""
    for tier in [1, 2, 3, 4]:
        options, sel, run = create_event_and_get_options('the_great_work', tier,
            event_state={
                'search_graves_cost': 2,
                'mark_scrolls_cost': 3,
                'count_blessings_cost': 1,
            })

        assert len(options) == 5, f"Tier {tier}: Expected 5 options, got {len(options)}"
        assert sel.get('ad_nauseam'), "Should have ad_nauseam flag set"
        assert_no_unresolved(options, 'the_great_work', tier)

        # Search the Graves: health_cost_tracker
        search = assert_option_exists(options, 'Search the Graves', 'the_great_work')
        assert search['health_cost'] == 2, f"Search health cost should be 2, got {search['health_cost']}"
        assert search['health_cost_tracker'] == 'search_graves_cost'
        assert search['next_event'] == 'great_work_search_graves'

        # Mark the Scrolls: health_cost_tracker + tooltip shows cost
        mark = assert_option_exists(options, 'Mark the Scrolls', 'the_great_work')
        assert mark['health_cost'] == 3, f"Mark health cost should be 3, got {mark['health_cost']}"
        assert '3' in mark['tooltip'], \
            f"Tier {tier}: Mark tooltip should show cost 3: {mark['tooltip']}"
        assert mark['next_event'] == 'great_work_mark_scrolls'

        # Count Your Blessings: health_cost_tracker
        bless = assert_option_exists(options, 'Count Your Blessings', 'the_great_work')
        assert bless['health_cost'] == 1, f"Bless health cost should be 1, got {bless['health_cost']}"
        assert '1' in bless['tooltip'], \
            f"Tier {tier}: Bless tooltip should show cost 1: {bless['tooltip']}"
        assert bless['next_event'] == 'great_work_count_blessings'

        # Lichdom: gold_cost=25, condition=not_has_lichdom
        lich = assert_option_exists(options, 'Lichdom', 'the_great_work')
        assert lich['gold_cost'] == 25, f"Lichdom gold cost should be 25, got {lich['gold_cost']}"
        assert not lich['disabled'], "Lichdom should be enabled (player doesn't have it)"
        assert lich['on_select'] == 'great_work_lichdom'
        assert lich['mark_event_complete']

        # Leave
        assert_option_exists(options, 'Leave', 'the_great_work')

    # Test: Lichdom disabled when already has lichdom
    options, _, _ = create_event_and_get_options('the_great_work', 2,
        hero_effects={'lichdom': True})
    lich = assert_option_exists(options, 'Lichdom', 'the_great_work')
    assert lich['disabled'], "Lichdom should be disabled when already has lichdom"

    # Test: default health_cost_tracker values (1) when not in event_state
    options, _, _ = create_event_and_get_options('the_great_work', 2)
    search = assert_option_exists(options, 'Search the Graves', 'the_great_work')
    assert search['health_cost'] == 1, \
        f"Default search health cost should be 1, got {search['health_cost']}"


# ==================== THE GREAT HUNT ====================


def test_the_great_hunt_full():
    """Verify The Great Hunt: 5 options, boss condition, beast conditions"""
    for tier in [1, 2, 3, 4]:
        options, sel, run = create_event_and_get_options('the_great_hunt', tier,
            band=make_band(tier))

        assert len(options) == 5, f"Tier {tier}: Expected 5 options, got {len(options)}"
        assert_no_unresolved(options, 'the_great_hunt', tier)

        # Take a Bounty: simple on_select
        bounty = assert_option_exists(options, 'Take a Bounty', 'the_great_hunt')
        assert bounty['on_select'] == 'set_double_gold_bounty'
        assert not bounty['disabled']

        # Take a Boss Bounty: disabled (no boss check - boss_not_defeated_this_tier enabled by default)
        boss = assert_option_exists(options, 'Take a Boss Bounty', 'the_great_hunt')
        assert not boss['disabled'], "Boss Bounty should be enabled (no boss defeated yet)"
        assert boss['next_event'] == 'great_hunt_boss_encounter'

        # Feed Your Pack: disabled (needs Beast + 2 minions, band has Human/Beast/Construct)
        feed = assert_option_exists(options, 'Feed Your Pack', 'the_great_hunt')
        assert feed['next_event'] == 'great_hunt_feed_sacrifice'

        # Call of the Wild: disabled (need 4+ beasts)
        wild = assert_option_exists(options, 'Call of the Wild', 'the_great_hunt')
        assert wild['disabled'], "Call of Wild should be disabled (< 4 beasts)"

        # Leave
        assert_option_exists(options, 'Leave', 'the_great_hunt')

    # Test: Boss Bounty disabled after defeating boss at current tier
    options, _, _ = create_event_and_get_options('the_great_hunt', 2,
        event_state={'bosses_defeated': {'2': 'dire_pack'}})
    boss = assert_option_exists(options, 'Take a Boss Bounty', 'the_great_hunt')
    assert boss['disabled'], "Boss Bounty should be disabled (boss already defeated at tier 2)"

    # Test: Call of Wild enabled with 4+ beasts
    beast_band = make_band(2, types=['Beast', 'Beast', 'Beast'], keywords=[[], [], []])
    beast_band.append({'name': 'Beast4', 'type': 'Beast', 'keywords': [], 'health': 1,
                       'attack': 1, 'tier': 2, 'band_id': 'b4', 'position': 3})
    options, _, _ = create_event_and_get_options('the_great_hunt', 2, band=beast_band)
    wild = assert_option_exists(options, 'Call of the Wild', 'the_great_hunt')
    assert not wild['disabled'], "Call of Wild should be enabled with 4+ beasts"


# ==================== GREAT HUNT VICTORY EVENTS ====================


def test_great_hunt_victory_events():
    """Verify all 6 Great Hunt victory events have correct options, icons, and chaining"""
    victory_events = {
        'great_hunt_victory_dire_pack': {
            'expected_count': 2,
            'choices': [
                ('All Minions +2/+2', 'on_select', 'boss_reward_dire_pack_stats'),
                ('One Minion: On Any Death +2/+2', 'next_event', 'great_hunt_reward_dire_pack_keyword'),
            ]
        },
        'great_hunt_victory_congregation': {
            'expected_count': 2,
            'choices': [
                ('One Minion: Gain Cult Tribe', 'next_event', 'great_hunt_reward_congregation_tribe'),
                ('One Minion: Gain Ignoble', 'next_event', 'great_hunt_reward_congregation_ignoble'),
            ]
        },
        'great_hunt_victory_chained_beast': {
            'expected_count': 2,
            'choices': [
                ('One Minion: +8/+8 and Leap 2', 'next_event', 'great_hunt_reward_chained_stats'),
                ('One Minion: Ethereal, No Cast/Retaliate', 'next_event', 'great_hunt_reward_chained_ethereal'),
            ]
        },
        'great_hunt_victory_behemoth': {
            'expected_count': 2,
            'choices': [
                ('One Minion: Guard and +5/+12', 'next_event', 'great_hunt_reward_behemoth_tank'),
                ('All Minions +0/+4', 'on_select', 'boss_reward_behemoth_all'),
            ]
        },
        'great_hunt_victory_venomspawn': {
            'expected_count': 2,
            'choices': [
                ('All Minions +6/+0', 'on_select', 'boss_reward_venomspawn_attack'),
                ('One Minion: Cast 2 damage to enemies', 'next_event', 'great_hunt_reward_venomspawn_cast'),
            ]
        },
        'great_hunt_victory_greater_possessed': {
            'expected_count': 2,
            'choices': [
                ('Tier x10 Gold', 'on_select', 'boss_reward_possessed_gold'),
                ('One Minion: Death Toll Summon Possessed', 'next_event', 'great_hunt_reward_possessed_deathtoll'),
            ]
        },
    }

    for event_id, spec in victory_events.items():
        options, sel, run = create_event_and_get_options(event_id, 2)

        assert len(options) == spec['expected_count'], \
            f"[{event_id}]: Expected {spec['expected_count']} options, got {len(options)}"
        assert_no_unresolved(options, event_id, 2)

        for name, chain_type, chain_value in spec['choices']:
            opt = assert_option_exists(options, name, event_id)
            assert opt.get(chain_type) == chain_value, \
                f"[{event_id}] '{name}': {chain_type} should be '{chain_value}', got '{opt.get(chain_type)}'"
            assert opt.get('icon', '') != '', \
                f"[{event_id}] '{name}': missing icon"


# ==================== UNLOCK SPECIAL OPTIONS (WATCHTOWER MECHANIC) ====================


def test_unlock_special_options():
    """Verify that unlock_special_options flag enables disabled conditions"""
    # When unlock_special_options is set, normally-disabled options should be enabled
    options, sel, run = create_event_and_get_options('collapsed_mine', 2,
        band=make_band(2, keywords=[['Guard'], [], []]),
        event_state={'unlock_special_options': True})

    # Go Faster should be enabled even without fast keyword
    faster = assert_option_exists(options, 'Go Faster', 'collapsed_mine')
    assert not faster['disabled'], \
        "Go Faster should be enabled with unlock_special_options (from Watchtower)"

    # After creation, the flag should be consumed
    new_state = run.get_event_state()
    assert not new_state.get('unlock_special_options'), \
        "unlock_special_options should be consumed after use"


# ==================== EVERY EVENT: NO UNRESOLVED TOOLTIPS ====================


def test_all_events_no_unresolved_tooltips():
    """Sweep ALL make_choice events at all tiers to check for unresolved tooltip variables"""
    all_event_ids = [
        # General event pool
        'collapsed_mine', 'mercenary_camp', 'vast_kennels', 'watchtower',
        # Zone events
        'bell_tower', 'ivory_tower', 'grand_city', 'scrap_heap',
        'the_red_gate', 'the_great_work', 'the_great_hunt',
        # Great Hunt victory events
        'great_hunt_victory_dire_pack', 'great_hunt_victory_congregation',
        'great_hunt_victory_chained_beast', 'great_hunt_victory_behemoth',
        'great_hunt_victory_venomspawn', 'great_hunt_victory_greater_possessed',
    ]

    for event_id in all_event_ids:
        for tier in [1, 2, 3, 4]:
            options, sel, run = create_event_and_get_options(event_id, tier)
            assert_no_unresolved(options, event_id, tier)


# ==================== EVERY EVENT: ALL OPTIONS HAVE ICONS ====================


def test_all_events_have_icons():
    """Verify that every choice option in every make_choice event has an icon"""
    all_event_ids = [
        'collapsed_mine', 'mercenary_camp', 'vast_kennels', 'watchtower',
        'bell_tower', 'ivory_tower', 'grand_city', 'scrap_heap',
        'the_red_gate', 'the_great_work', 'the_great_hunt',
        'great_hunt_victory_dire_pack', 'great_hunt_victory_congregation',
        'great_hunt_victory_chained_beast', 'great_hunt_victory_behemoth',
        'great_hunt_victory_venomspawn', 'great_hunt_victory_greater_possessed',
    ]

    for event_id in all_event_ids:
        options, sel, run = create_event_and_get_options(event_id, 2)
        for opt in options:
            icon = opt.get('icon', '')
            assert icon != '', \
                f"[{event_id}] '{opt['message']}': missing icon"


def test_all_icon_svgs_use_currentColor():
    """Verify that every choice icon SVG uses stroke=currentColor (not old stroke=#000 / fill:#fff style)"""
    all_event_ids = [
        'collapsed_mine', 'mercenary_camp', 'vast_kennels', 'watchtower',
        'bell_tower', 'ivory_tower', 'grand_city', 'scrap_heap',
        'the_red_gate', 'the_great_work', 'the_great_hunt',
        'great_hunt_victory_dire_pack', 'great_hunt_victory_congregation',
        'great_hunt_victory_chained_beast', 'great_hunt_victory_behemoth',
        'great_hunt_victory_venomspawn', 'great_hunt_victory_greater_possessed',
    ]

    for event_id in all_event_ids:
        options, sel, run = create_event_and_get_options(event_id, 2)
        for opt in options:
            icon = opt.get('icon', '')
            if not icon:
                continue
            assert 'stroke="#000"' not in icon, \
                f"[{event_id}] '{opt['message']}': icon uses old stroke=#000 style"
            assert 'fill: #fff' not in icon and 'fill:#fff' not in icon, \
                f"[{event_id}] '{opt['message']}': icon uses old fill:#fff style"
            assert 'fill="none"' in icon, \
                f"[{event_id}] '{opt['message']}': icon missing fill=none"
            assert 'stroke="currentColor"' in icon, \
                f"[{event_id}] '{opt['message']}': icon missing stroke=currentColor"


def test_all_event_icon_names_exist_in_lucide_paths():
    """Verify that every icon name used in event definitions exists in LUCIDE_PATHS (not falling back to help-circle)"""
    from lucide_icons import LUCIDE_PATHS, generate_lucide_svg

    all_event_ids = [
        'collapsed_mine', 'mercenary_camp', 'vast_kennels', 'watchtower',
        'bell_tower', 'ivory_tower', 'grand_city', 'scrap_heap',
        'the_red_gate', 'the_great_work', 'the_great_hunt',
        'great_hunt_victory_dire_pack', 'great_hunt_victory_congregation',
        'great_hunt_victory_chained_beast', 'great_hunt_victory_behemoth',
        'great_hunt_victory_venomspawn', 'great_hunt_victory_greater_possessed',
    ]

    # Get the help-circle fallback SVG to detect fallbacks
    fallback_svg = generate_lucide_svg('help-circle')
    fallback_path = LUCIDE_PATHS['help-circle']

    for event_id in all_event_ids:
        options, sel, run = create_event_and_get_options(event_id, 2)
        for opt in options:
            icon = opt.get('icon', '')
            if not icon:
                continue
            assert fallback_path not in icon or 'help-circle' in icon, \
                f"[{event_id}] '{opt['message']}': icon falls back to help-circle (missing icon name in LUCIDE_PATHS)"


# ==================== CHAINING VERIFICATION ====================
# These tests use _resolve_template_event_selection directly to bypass
# the Flask/SQLAlchemy dependency in SelectionSystem.resolve_selection.


def _resolve_template_choice(run, selection_id):
    """Helper: resolve a template choice using the internal resolver (no Flask needed)"""
    from game_engine.selection_system import SelectionSystem
    pending = run.get_pending_selection()
    return SelectionSystem._resolve_template_event_selection(run, pending, [selection_id])


def test_chaining_next_event_creates_new_selection():
    """Verify that choosing an option with next_event produces a new selection"""
    # Create Watchtower, pick "Storm Tower" which has next_event='watchtower_storm'
    run = MockRun(ring=2, gold=100, health=100, band=make_band(2))
    result = EventSystem.create_event_selection(run, 'watchtower')
    assert result.get('selection_created')

    selection = run.get_pending_selection()
    storm = next(o for o in selection['options'] if o['message'] == 'Storm Tower')
    assert storm['next_event'] == 'watchtower_storm', \
        f"Storm Tower next_event should be 'watchtower_storm', got '{storm['next_event']}'"

    # Resolve the selection
    resolve_result = _resolve_template_choice(run, storm['id'])

    # After resolving, should have a new pending selection (the chained event)
    new_selection = run.get_pending_selection()
    assert new_selection is not None, \
        "Resolving Storm Tower should chain to watchtower_storm event"


def test_chaining_on_select_gold_deduction():
    """Verify that on_select options properly deduct gold and execute effects"""
    # Create Collapsed Mine with 50 gold, pick "Go Slow" (on_select: collapsed_mine_slow)
    run = MockRun(ring=2, gold=50, health=100, band=make_band(2))
    result = EventSystem.create_event_selection(run, 'collapsed_mine')
    assert result.get('selection_created')

    selection = run.get_pending_selection()
    slow = next(o for o in selection['options'] if o['message'] == 'Go Slow')

    # Resolve
    resolve_result = _resolve_template_choice(run, slow['id'])
    assert resolve_result.get('success'), f"Resolution failed: {resolve_result}"

    # Should have gained tier*4 = 8 gold
    resources = run.get_resources()
    assert resources['gold'] == 58, \
        f"Gold should be 58 (50 + tier 2 * 4), got {resources['gold']}"


def test_chaining_gold_cost_deduction():
    """Verify that gold_cost is deducted when selecting a paid option"""
    # Create Bell Tower with 20 gold, pick "Pay to Ring the Bell" (gold_cost: tier*3 = 6)
    run = MockRun(ring=2, gold=20, health=100, band=make_band(2))
    result = EventSystem.create_event_selection(run, 'bell_tower')
    assert result.get('selection_created')

    selection = run.get_pending_selection()
    ring = next(o for o in selection['options'] if o['message'] == 'Pay to Ring the Bell')
    assert ring['gold_cost'] == 6

    # Resolve
    resolve_result = _resolve_template_choice(run, ring['id'])
    assert resolve_result.get('success'), f"Resolution failed: {resolve_result}"

    # Gold should be deducted
    resources = run.get_resources()
    assert resources['gold'] == 14, \
        f"Gold should be 14 (20 - 6), got {resources['gold']}"

    # bells_rung should have incremented
    event_state = run.get_event_state()
    assert event_state.get('bells_rung', 0) >= 1, \
        f"bells_rung should be >= 1 after ringing, got {event_state.get('bells_rung', 0)}"


def test_chaining_insufficient_gold_rejected():
    """Verify that selecting a paid option with insufficient gold is rejected"""
    # Create Bell Tower with only 2 gold, try "Pay to Ring the Bell" (cost: 6)
    run = MockRun(ring=2, gold=2, health=100, band=make_band(2))
    result = EventSystem.create_event_selection(run, 'bell_tower')
    assert result.get('selection_created')

    selection = run.get_pending_selection()
    ring = next(o for o in selection['options'] if o['message'] == 'Pay to Ring the Bell')

    resolve_result = _resolve_template_choice(run, ring['id'])
    assert resolve_result.get('error'), \
        "Should get error when trying to pay 6 gold with only 2"
    assert 'gold' in resolve_result['error'].lower(), \
        f"Error should mention gold: {resolve_result['error']}"


def test_chaining_leave_clears_selection():
    """Verify that Leave options with next_event=None clear the pending selection"""
    run = MockRun(ring=2, gold=50, health=100, band=make_band(2))
    result = EventSystem.create_event_selection(run, 'collapsed_mine')
    assert result.get('selection_created')

    selection = run.get_pending_selection()
    leave = next(o for o in selection['options'] if o['message'] == 'Leave')

    resolve_result = _resolve_template_choice(run, leave['id'])
    assert resolve_result.get('success'), f"Leave resolution failed: {resolve_result}"

    # Pending selection should be cleared (no chained event)
    assert run.get_pending_selection() is None, \
        "Leave should clear pending selection"


# ==================== DEV EVENTS ROUTE COMPATIBILITY ====================
# These tests verify that SelectionSystem.resolve_selection works with
# dev mode MockRuns (bypasses DB optimistic lock).


def test_dev_mode_resolve_selection_full_path():
    """Verify resolve_selection works with _dev_mode_mock (no Flask/DB needed)"""
    from game_engine.selection_system import SelectionSystem

    run = MockRun(ring=2, gold=50, health=100, band=make_band(2))
    result = EventSystem.create_event_selection(run, 'collapsed_mine')
    assert result.get('selection_created')

    selection = run.get_pending_selection()
    leave = next(o for o in selection['options'] if o['message'] == 'Leave')

    # This calls the full resolve_selection (not the internal _resolve method)
    # It should skip the DB lock because _dev_mode_mock=True
    resolve_result = SelectionSystem.resolve_selection(run, [leave['id']])
    assert resolve_result.get('success'), f"Dev mode resolve_selection failed: {resolve_result}"
    assert run.selection_version == 1, "selection_version should have incremented"


def test_dev_mode_resolve_with_gold_cost():
    """Verify full resolve_selection deducts gold in dev mode"""
    from game_engine.selection_system import SelectionSystem

    run = MockRun(ring=2, gold=20, health=100, band=make_band(2))
    result = EventSystem.create_event_selection(run, 'bell_tower')
    assert result.get('selection_created')

    selection = run.get_pending_selection()
    ring = next(o for o in selection['options'] if o['message'] == 'Pay to Ring the Bell')

    resolve_result = SelectionSystem.resolve_selection(run, [ring['id']])
    assert resolve_result.get('success'), f"Dev mode resolve failed: {resolve_result}"

    resources = run.get_resources()
    assert resources['gold'] == 14, f"Gold should be 14 (20 - 6), got {resources['gold']}"


def test_dev_mode_resolve_chaining():
    """Verify full resolve_selection chains to next_event in dev mode"""
    from game_engine.selection_system import SelectionSystem

    run = MockRun(ring=2, gold=100, health=100, band=make_band(2))
    result = EventSystem.create_event_selection(run, 'watchtower')
    assert result.get('selection_created')

    selection = run.get_pending_selection()
    storm = next(o for o in selection['options'] if o['message'] == 'Storm Tower')

    resolve_result = SelectionSystem.resolve_selection(run, [storm['id']])
    # Should have chained to watchtower_storm
    new_selection = run.get_pending_selection()
    assert new_selection is not None, "Should chain to watchtower_storm event"


# ==================== MAIN ====================


if __name__ == '__main__':
    import pytest
    sys.exit(pytest.main([__file__, '-v']))
