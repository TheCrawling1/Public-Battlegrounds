#!/usr/bin/env python3
"""
Test suite for event_helpers.py - the centralized helpers for general event processing.

Tests cover:
1. Formula resolution (resolve_formula)
2. Tooltip template substitution (resolve_tooltip)
3. Condition evaluation (evaluate_condition)
4. Choice option validation (validate_choice_option, validate_event_choices)
5. Tooltip context building (build_tooltip_context)
6. Integration: full choice processing pipeline
7. All general events have valid tooltips after resolution
8. New event creation: verifies a brand-new event works "out of the box"
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))


class MockRun:
    """Lightweight mock for testing event helpers without Flask dependencies"""

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


# ==================== FORMULA RESOLUTION TESTS ====================


def test_resolve_formula_basic():
    """Test basic formula resolution"""
    from game_engine.events.event_helpers import resolve_formula

    # Integer literals
    assert resolve_formula(5, 1) == 5, "Direct int should pass through"
    assert resolve_formula('5', 1) == 5, "String int should parse"
    assert resolve_formula('25', 3) == 25, "Static string should ignore tier"

    # Tier formulas
    assert resolve_formula('tier * 3', 1) == 3, "tier * 3 at tier 1 = 3"
    assert resolve_formula('tier * 3', 2) == 6, "tier * 3 at tier 2 = 6"
    assert resolve_formula('tier * 3', 4) == 12, "tier * 3 at tier 4 = 12"
    assert resolve_formula('tier * 6', 3) == 18, "tier * 6 at tier 3 = 18"
    assert resolve_formula('tier * 5', 2) == 10, "tier * 5 at tier 2 = 10"

    # None and empty
    assert resolve_formula(None, 1) == 0, "None should return 0"
    assert resolve_formula('', 1) == 0, "Empty string should return 0"

    # Float input
    assert resolve_formula(3.7, 1) == 3, "Float should truncate to int"


def test_resolve_formula_complex():
    """Test more complex formula patterns"""
    from game_engine.events.event_helpers import resolve_formula

    # Formulas with addition
    assert resolve_formula('tier * 2 + 1', 3) == 7, "tier * 2 + 1 at tier 3 = 7"

    # Just 'tier'
    assert resolve_formula('tier', 4) == 4, "bare 'tier' should equal tier value"

    # Edge: tier 0 (shouldn't happen in game, but don't crash)
    assert resolve_formula('tier * 3', 0) == 0, "tier * 3 at tier 0 = 0"


def test_resolve_formula_safety():
    """Test that formula resolution rejects dangerous expressions"""
    from game_engine.events.event_helpers import resolve_formula

    # Should return 0 for unsafe expressions (not crash)
    assert resolve_formula('__import__("os")', 1) == 0, "Import attempts should return 0"
    assert resolve_formula('open("/etc/passwd")', 1) == 0, "File access should return 0"


# ==================== TOOLTIP RESOLUTION TESTS ====================


def test_resolve_tooltip_named_vars():
    """Test tooltip resolution with named variables"""
    from game_engine.events.event_helpers import resolve_tooltip

    # Basic named variable substitution
    result = resolve_tooltip('Pay ({gold_cost}) gold.', 2, {'gold_cost': 12})
    assert result == 'Pay (12) gold.', f"Expected 'Pay (12) gold.' got '{result}'"

    # Multiple named variables
    result = resolve_tooltip(
        'Gain ({gold_reward}) gold. Costs {gold_cost} gold.',
        2,
        {'gold_reward': 8, 'gold_cost': 12}
    )
    assert 'Gain (8) gold' in result, f"gold_reward not substituted: {result}"
    assert 'Costs 12 gold' in result, f"gold_cost not substituted: {result}"

    # Tier variable
    result = resolve_tooltip('Tier {tier} minion.', 3, {'tier': 3})
    assert result == 'Tier 3 minion.', f"Expected 'Tier 3 minion.' got '{result}'"


def test_resolve_tooltip_inline_formulas():
    """Test tooltip resolution with inline tier formulas (the key fix)"""
    from game_engine.events.event_helpers import resolve_tooltip

    # {tier * 3} pattern - this was BROKEN before the refactor
    result = resolve_tooltip('Pay {tier * 3} gold.', 2, {})
    assert result == 'Pay 6 gold.', f"Expected 'Pay 6 gold.' got '{result}'"

    # {tier * 2} pattern
    result = resolve_tooltip('Give all Beasts +{tier * 2} attack.', 3, {})
    assert result == 'Give all Beasts +6 attack.', f"Expected '+6 attack' got '{result}'"

    # Mixed named and inline
    result = resolve_tooltip(
        'Pay ({gold_cost}) gold to give all Beasts +{tier * 2} attack.',
        3,
        {'gold_cost': 9}
    )
    assert result == 'Pay (9) gold to give all Beasts +6 attack.', f"Mixed failed: {result}"

    # Multiple inline formulas
    result = resolve_tooltip(
        'Gain +{tier * 3}/+{tier * 3}.',
        2,
        {}
    )
    assert result == 'Gain +6/+6.', f"Multiple inline failed: {result}"


def test_resolve_tooltip_empty():
    """Test tooltip resolution with empty/None input"""
    from game_engine.events.event_helpers import resolve_tooltip

    assert resolve_tooltip('', 1, {}) == '', "Empty string should return empty"
    assert resolve_tooltip(None, 1, {}) == '', "None should return empty"

    # No substitutions needed
    result = resolve_tooltip('Leave without doing anything.', 1, {})
    assert result == 'Leave without doing anything.', f"Plain text mangled: {result}"


# ==================== CONDITION EVALUATION TESTS ====================


def test_evaluate_condition_keywords():
    """Test keyword-based conditions"""
    from game_engine.events.event_helpers import evaluate_condition

    # Band with fast keyword (lowercase, matching event condition strings)
    run_with_fast = MockRun(band=[
        {'name': 'Test', 'health': 5, 'attack': 3, 'tier': 1, 'type': 'Human',
         'keywords': ['fast'], 'band_id': 'test_1', 'position': 0}
    ])

    # has_keyword_fast -> should NOT be disabled
    disabled = evaluate_condition('has_keyword_fast', run_with_fast, {})
    assert not disabled, "has_keyword_fast should be enabled when fast minion exists"

    # has_keyword_hide -> should be disabled (no hide)
    disabled = evaluate_condition('has_keyword_hide', run_with_fast, {})
    assert disabled, "has_keyword_hide should be disabled when no hide minion"

    # Band with Hide keyword
    run_with_hide = MockRun(band=[
        {'name': 'Test', 'health': 5, 'attack': 3, 'tier': 1, 'type': 'Human',
         'keywords': ['hide'], 'band_id': 'test_1', 'position': 0}
    ])
    disabled = evaluate_condition('has_keyword_hide', run_with_hide, {})
    assert not disabled, "has_keyword_hide should be enabled when Hide minion exists"


def test_evaluate_condition_tribes():
    """Test tribe-count conditions"""
    from game_engine.events.event_helpers import evaluate_condition

    # Band with 4 unique tribes
    run_diverse = MockRun(band=[
        {'name': 'A', 'type': 'Human', 'keywords': [], 'health': 1, 'attack': 1},
        {'name': 'B', 'type': 'Beast', 'keywords': [], 'health': 1, 'attack': 1},
        {'name': 'C', 'type': 'Construct', 'keywords': [], 'health': 1, 'attack': 1},
        {'name': 'D', 'type': 'Fey', 'keywords': [], 'health': 1, 'attack': 1},
    ])
    disabled = evaluate_condition('unique_tribes >= 4', run_diverse, {})
    assert not disabled, "4 unique tribes should satisfy >= 4"

    # Band with only 2 unique tribes
    run_few = MockRun(band=[
        {'name': 'A', 'type': 'Human', 'keywords': [], 'health': 1, 'attack': 1},
        {'name': 'B', 'type': 'Human', 'keywords': [], 'health': 1, 'attack': 1},
        {'name': 'C', 'type': 'Beast', 'keywords': [], 'health': 1, 'attack': 1},
    ])
    disabled = evaluate_condition('unique_tribes >= 4', run_few, {})
    assert disabled, "2 unique tribes should fail >= 4"

    # Multi-tribe minions (list type)
    run_multi = MockRun(band=[
        {'name': 'A', 'type': ['Human', 'Beast'], 'keywords': [], 'health': 1, 'attack': 1},
        {'name': 'B', 'type': 'Construct', 'keywords': [], 'health': 1, 'attack': 1},
        {'name': 'C', 'type': 'Fey', 'keywords': [], 'health': 1, 'attack': 1},
    ])
    disabled = evaluate_condition('unique_tribes >= 4', run_multi, {})
    assert not disabled, "Multi-tribe list should count properly"


def test_evaluate_condition_beast_count():
    """Test beast count conditions"""
    from game_engine.events.event_helpers import evaluate_condition

    run_beasts = MockRun(band=[
        {'name': 'A', 'type': 'Beast', 'keywords': [], 'health': 1, 'attack': 1},
        {'name': 'B', 'type': 'Beast', 'keywords': [], 'health': 1, 'attack': 1},
        {'name': 'C', 'type': 'Beast', 'keywords': [], 'health': 1, 'attack': 1},
    ])
    disabled = evaluate_condition('beast_count >= 3', run_beasts, {})
    assert not disabled, "3 beasts should satisfy >= 3"

    run_few = MockRun(band=[
        {'name': 'A', 'type': 'Beast', 'keywords': [], 'health': 1, 'attack': 1},
        {'name': 'B', 'type': 'Human', 'keywords': [], 'health': 1, 'attack': 1},
    ])
    disabled = evaluate_condition('beast_count >= 3', run_few, {})
    assert disabled, "1 beast should fail >= 3"


def test_evaluate_condition_event_state():
    """Test event_state comparison conditions"""
    from game_engine.events.event_helpers import evaluate_condition

    run = MockRun()

    # bells_rung >= 4 with bells_rung = 5
    disabled = evaluate_condition('bells_rung >= 4', run, {'bells_rung': 5})
    assert not disabled, "bells_rung 5 >= 4 should be enabled"

    # bells_rung >= 4 with bells_rung = 2
    disabled = evaluate_condition('bells_rung >= 4', run, {'bells_rung': 2})
    assert disabled, "bells_rung 2 >= 4 should be disabled"

    # ivory_tower_seal <= 0 with seal = 0
    disabled = evaluate_condition('ivory_tower_seal <= 0', run, {'ivory_tower_seal': 0})
    assert not disabled, "seal 0 <= 0 should be enabled"

    # ivory_tower_seal <= 0 with seal = 3
    disabled = evaluate_condition('ivory_tower_seal <= 0', run, {'ivory_tower_seal': 3})
    assert disabled, "seal 3 <= 0 should be disabled"


def test_evaluate_condition_special():
    """Test special conditions (blind luck, lichdom, transcendence, boss)"""
    from game_engine.events.event_helpers import evaluate_condition

    run = MockRun()

    # Blind luck - always disabled
    disabled = evaluate_condition('scrap_heap_blind_luck_available', run, {})
    assert disabled, "Blind luck should always be disabled"

    # not_has_lichdom without lichdom
    disabled = evaluate_condition('not_has_lichdom', run, {})
    assert not disabled, "Without lichdom, not_has_lichdom should be enabled"

    # not_has_lichdom with lichdom
    run_lichdom = MockRun()
    run_lichdom._hero_effects = {'lichdom': True}
    disabled = evaluate_condition('not_has_lichdom', run_lichdom, {})
    assert disabled, "With lichdom, not_has_lichdom should be disabled"

    # boss_not_defeated_this_tier - no boss defeated
    disabled = evaluate_condition('boss_not_defeated_this_tier', run, {})
    assert not disabled, "No boss defeated should be enabled"

    # boss_not_defeated_this_tier - boss defeated at current tier
    disabled = evaluate_condition('boss_not_defeated_this_tier', run, {
        'bosses_defeated': {'1': 'dire_pack'}
    })
    assert disabled, "Boss defeated at tier 1 should disable for tier 1 run"

    # has_beast_and_2_minions
    run_beast = MockRun(band=[
        {'name': 'A', 'type': 'Beast', 'keywords': [], 'health': 1, 'attack': 1},
        {'name': 'B', 'type': 'Human', 'keywords': [], 'health': 1, 'attack': 1},
    ])
    disabled = evaluate_condition('has_beast_and_2_minions', run_beast, {})
    assert not disabled, "1 beast + 2 minions total should be enabled"

    run_no_beast = MockRun(band=[
        {'name': 'A', 'type': 'Human', 'keywords': [], 'health': 1, 'attack': 1},
        {'name': 'B', 'type': 'Human', 'keywords': [], 'health': 1, 'attack': 1},
    ])
    disabled = evaluate_condition('has_beast_and_2_minions', run_no_beast, {})
    assert disabled, "No beasts should be disabled"


def test_evaluate_condition_transcendence():
    """Test transcendence candidate condition"""
    from game_engine.events.event_helpers import evaluate_condition

    # Valid candidate: tier 2+, 0 attack, 1 health, no types, no keywords
    run_candidate = MockRun(band=[
        {'name': 'Husk', 'type': 'None', 'keywords': [], 'health': 1, 'attack': 0, 'tier': 2},
    ])
    disabled = evaluate_condition('has_transcendence_candidate', run_candidate, {})
    assert not disabled, "Valid transcendence candidate should enable option"

    # Invalid: has keywords
    run_keywords = MockRun(band=[
        {'name': 'Husk', 'type': 'None', 'keywords': ['Guard'], 'health': 1, 'attack': 0, 'tier': 2},
    ])
    disabled = evaluate_condition('has_transcendence_candidate', run_keywords, {})
    assert disabled, "Minion with keywords should disable"

    # Invalid: too low tier
    run_low_tier = MockRun(band=[
        {'name': 'Husk', 'type': 'None', 'keywords': [], 'health': 1, 'attack': 0, 'tier': 1},
    ])
    disabled = evaluate_condition('has_transcendence_candidate', run_low_tier, {})
    assert disabled, "Tier 1 minion should disable"

    # Invalid: has attack
    run_attack = MockRun(band=[
        {'name': 'Husk', 'type': 'None', 'keywords': [], 'health': 1, 'attack': 3, 'tier': 2},
    ])
    disabled = evaluate_condition('has_transcendence_candidate', run_attack, {})
    assert disabled, "Minion with attack should disable"


def test_evaluate_condition_none():
    """Test that no condition = always enabled"""
    from game_engine.events.event_helpers import evaluate_condition

    run = MockRun()
    disabled = evaluate_condition(None, run, {})
    assert not disabled, "None condition should be enabled"

    disabled = evaluate_condition('', run, {})
    assert not disabled, "Empty condition should be enabled"


def test_evaluate_condition_state_defaults():
    """Test that state_defaults provides correct fallbacks for fresh runs"""
    from game_engine.events.event_helpers import evaluate_condition

    run = MockRun()
    defaults = {'ivory_tower_seal': 4, 'bells_rung': 0}

    # Fresh run (empty event_state): seal defaults to 4, so 4 <= 0 is False → disabled
    disabled = evaluate_condition('ivory_tower_seal <= 0', run, {}, state_defaults=defaults)
    assert disabled, "Fresh run: seal=4 (default), should be disabled (4 > 0)"

    # After weakening seal to 0: enabled
    disabled = evaluate_condition('ivory_tower_seal <= 0', run, {'ivory_tower_seal': 0}, state_defaults=defaults)
    assert not disabled, "Seal=0, should be enabled"

    # Fresh run: bells_rung defaults to 0, so 0 >= 4 is False → disabled
    disabled = evaluate_condition('bells_rung >= 4', run, {}, state_defaults=defaults)
    assert disabled, "Fresh run: bells=0 (default), should be disabled (0 < 4)"

    # After ringing 4 bells: enabled
    disabled = evaluate_condition('bells_rung >= 4', run, {'bells_rung': 4}, state_defaults=defaults)
    assert not disabled, "Bells=4, should be enabled"


# ==================== CHOICE VALIDATION TESTS ====================


def test_validate_choice_option():
    """Test choice option validation"""
    from game_engine.events.event_helpers import validate_choice_option

    # Valid choice with all fields
    valid_choice = {
        'name': 'Test Choice',
        'tooltip': 'This is a tooltip',
        'icon': '<svg>...</svg>',
        'next_event': None
    }
    is_valid, errors, warnings = validate_choice_option(valid_choice, 'test_event', 0)
    assert is_valid, f"Valid choice should pass: {errors}"
    assert len(errors) == 0, f"Should have no errors: {errors}"

    # Missing name (required)
    bad_choice = {'tooltip': 'test', 'icon': '<svg>'}
    is_valid, errors, warnings = validate_choice_option(bad_choice, 'test_event', 0)
    assert not is_valid, "Missing name should fail"
    assert any("'name'" in e for e in errors), f"Error should mention 'name': {errors}"

    # Missing tooltip (recommended - warning, not error)
    no_tooltip = {'name': 'Test', 'icon': '<svg>', 'next_event': None}
    is_valid, errors, warnings = validate_choice_option(no_tooltip, 'test_event', 0)
    assert is_valid, "Missing tooltip should still pass (it's a warning)"
    assert any("'tooltip'" in w for w in warnings), f"Should warn about tooltip: {warnings}"

    # Missing icon (recommended - warning, not error)
    no_icon = {'name': 'Test', 'tooltip': 'test', 'next_event': None}
    is_valid, errors, warnings = validate_choice_option(no_icon, 'test_event', 0)
    assert is_valid, "Missing icon should still pass (it's a warning)"
    assert any("'icon'" in w for w in warnings), f"Should warn about icon: {warnings}"


def test_validate_event_choices():
    """Test full event choice validation"""
    from game_engine.events.event_helpers import validate_event_choices

    # Valid event
    valid_event = {
        'id': 'test_event',
        'screens': [{
            'type': 'make_choice',
            'parameters': {
                'choices': [
                    {'name': 'Option A', 'tooltip': 'Do A', 'icon': '<svg>', 'next_event': None},
                    {'name': 'Option B', 'tooltip': 'Do B', 'icon': '<svg>', 'on_select': 'handler'}
                ]
            }
        }]
    }
    is_valid, errors, warnings = validate_event_choices(valid_event)
    assert is_valid, f"Valid event should pass: {errors}"

    # Event with no make_choice screens (should pass - nothing to validate)
    no_choice_event = {
        'id': 'shop_event',
        'screens': [{'type': 'shop', 'parameters': {}}]
    }
    is_valid, errors, warnings = validate_event_choices(no_choice_event)
    assert is_valid, "Event without make_choice should pass"


def test_validate_all_general_events():
    """Test that all existing general events pass validation"""
    from game_engine.events.event_helpers import validate_all_general_event_choices

    passed = validate_all_general_event_choices()
    assert passed, "All existing general events should pass validation"


# ==================== TOOLTIP CONTEXT BUILDER TESTS ====================


def test_build_tooltip_context():
    """Test tooltip context building with state_defaults from event definition"""
    from game_engine.events.event_helpers import build_tooltip_context

    run = MockRun(ring=2)

    choice = {
        'gold_cost': 'tier * 3',
        'gold_reward': 'tier * 4',
    }

    # Without event_def, only formula fields are resolved
    ctx = build_tooltip_context(choice, 2, {}, run)
    assert ctx['gold_cost'] == 6, f"gold_cost should be 6, got {ctx['gold_cost']}"
    assert ctx['gold_reward'] == 8, f"gold_reward should be 8, got {ctx['gold_reward']}"
    assert ctx['tier'] == 2, f"tier should be 2, got {ctx['tier']}"
    assert 'ivory_tower_seal' not in ctx, "No state keys without event_def"

    # With event_def declaring state_defaults, values come from event_state
    event_def = {'state_defaults': {'ivory_tower_seal': 4, 'bells_rung': 0}}
    event_state = {'ivory_tower_seal': 3, 'bells_rung': 2}
    ctx = build_tooltip_context(choice, 2, event_state, run, event_def=event_def)
    assert ctx['ivory_tower_seal'] == 3, f"seal should be 3 (from event_state), got {ctx['ivory_tower_seal']}"
    assert ctx['bells_rung'] == 2, f"bells should be 2 (from event_state), got {ctx['bells_rung']}"

    # On first visit (empty event_state), falls back to declared defaults
    ctx = build_tooltip_context(choice, 2, {}, run, event_def=event_def)
    assert ctx['ivory_tower_seal'] == 4, f"seal should be 4 (default), got {ctx['ivory_tower_seal']}"
    assert ctx['bells_rung'] == 0, f"bells should be 0 (default), got {ctx['bells_rung']}"


# ==================== INTEGRATION TESTS ====================


def test_collapsed_mine_tooltips():
    """Test that Collapsed Mine tooltips resolve correctly at various tiers"""
    from game_engine.events.event_helpers import resolve_tooltip, resolve_formula, build_tooltip_context

    for tier in [1, 2, 3, 4]:
        run = MockRun(ring=tier)

        # Go Slow: gold_reward = tier * 4
        choice = {'gold_reward': 'tier * 4', 'tooltip': 'Gain ({gold_reward}) gold. Costs 1 extra Step.'}
        ctx = build_tooltip_context(choice, tier, {}, run)
        ctx['gold_reward'] = resolve_formula('tier * 4', tier)
        result = resolve_tooltip(choice['tooltip'], tier, ctx)
        expected_gold = tier * 4
        assert f'({expected_gold})' in result, f"Tier {tier} Go Slow: expected ({expected_gold}) in '{result}'"

        # Go Faster: gold_reward = tier * 5
        choice2 = {'gold_reward': 'tier * 5', 'tooltip': 'Gain ({gold_reward}) gold. Requires a minion with Fast.'}
        ctx2 = build_tooltip_context(choice2, tier, {}, run)
        ctx2['gold_reward'] = resolve_formula('tier * 5', tier)
        result2 = resolve_tooltip(choice2['tooltip'], tier, ctx2)
        expected_gold2 = tier * 5
        assert f'({expected_gold2})' in result2, f"Tier {tier} Go Faster: expected ({expected_gold2}) in '{result2}'"


def test_vast_kennels_tooltips():
    """Test that Vast Kennels tooltips resolve correctly (the key bug fix)"""
    from game_engine.events.event_helpers import resolve_tooltip, resolve_formula, build_tooltip_context

    for tier in [1, 2, 3, 4]:
        run = MockRun(ring=tier)

        # Buy a Treat: gold_cost = tier * 3, tooltip has {tier * 2} inline
        choice = {
            'gold_cost': 'tier * 3',
            'tooltip': 'Pay ({gold_cost}) gold to give all Beasts +{tier * 2} attack.'
        }
        ctx = build_tooltip_context(choice, tier, {}, run)
        ctx['gold_cost'] = resolve_formula('tier * 3', tier)
        result = resolve_tooltip(choice['tooltip'], tier, ctx)

        expected_cost = tier * 3
        expected_attack = tier * 2
        assert f'({expected_cost})' in result, \
            f"Tier {tier}: expected gold_cost ({expected_cost}) in '{result}'"
        assert f'+{expected_attack} attack' in result, \
            f"Tier {tier}: expected +{expected_attack} attack in '{result}'"
        assert '{' not in result, \
            f"Tier {tier}: unresolved template variable in '{result}'"


def test_watchtower_tooltips():
    """Test Watchtower tooltip resolution"""
    from game_engine.events.event_helpers import resolve_tooltip, resolve_formula, build_tooltip_context

    for tier in [1, 2, 3, 4]:
        run = MockRun(ring=tier)

        # Pay for Help: gold_cost = tier * 6
        choice = {
            'gold_cost': 'tier * 6',
            'tooltip': 'Pay ({gold_cost}) gold. Next general event: special options are unlocked even without meeting conditions.'
        }
        ctx = build_tooltip_context(choice, tier, {}, run)
        ctx['gold_cost'] = resolve_formula('tier * 6', tier)
        result = resolve_tooltip(choice['tooltip'], tier, ctx)

        expected_cost = tier * 6
        assert f'({expected_cost})' in result, \
            f"Tier {tier}: expected ({expected_cost}) in '{result}'"
        assert '{' not in result, \
            f"Tier {tier}: unresolved template variable in '{result}'"

        # Request Aid: gold_cost = tier * 3
        choice2 = {
            'gold_cost': 'tier * 3',
            'tooltip': 'Pay ({gold_cost}) gold to gain a random Tier {tier} Human minion.'
        }
        ctx2 = build_tooltip_context(choice2, tier, {}, run)
        ctx2['gold_cost'] = resolve_formula('tier * 3', tier)
        result2 = resolve_tooltip(choice2['tooltip'], tier, ctx2)

        expected_cost2 = tier * 3
        assert f'({expected_cost2})' in result2, \
            f"Tier {tier}: expected ({expected_cost2}) in '{result2}'"
        assert f'Tier {tier}' in result2, \
            f"Tier {tier}: expected 'Tier {tier}' in '{result2}'"


def test_mercenary_camp_tooltips():
    """Test Mercenary Camp tooltip resolution with inline tier formulas"""
    from game_engine.events.event_helpers import resolve_tooltip, resolve_formula, build_tooltip_context

    for tier in [1, 2, 3, 4]:
        run = MockRun(ring=tier)

        # Enter a Duel: tooltip has {tier * 3} inline formula
        choice = {
            'tooltip': 'Choose 1 minion to fight alone against a scaled enemy. Win: That minion gains +{tier * 3}/+{tier * 3}.'
        }
        ctx = build_tooltip_context(choice, tier, {}, run)
        result = resolve_tooltip(choice['tooltip'], tier, ctx)

        expected_buff = tier * 3
        assert f'+{expected_buff}/+{expected_buff}' in result, \
            f"Tier {tier}: expected +{expected_buff}/+{expected_buff} in '{result}'"
        assert '{' not in result, \
            f"Tier {tier}: unresolved template variable in '{result}'"

        # Joint Alliance: tooltip has {tier} inline
        choice2 = {
            'tooltip': 'If you have 4+ different tribes, all minions gain +{tier}/+{tier}.'
        }
        ctx2 = build_tooltip_context(choice2, tier, {}, run)
        result2 = resolve_tooltip(choice2['tooltip'], tier, ctx2)

        assert f'+{tier}/+{tier}' in result2, \
            f"Tier {tier}: expected +{tier}/+{tier} in '{result2}'"


def test_full_choice_processing_pipeline():
    """Test the full pipeline: event definition -> choice processing -> resolved options"""

    from game_engine.events.event_system import EventSystem

    for tier in [1, 2, 3, 4]:
        run = MockRun(
            ring=tier, position=3, zone='human_kingdom',
            gold=50, health=100,
            band=[
                {'name': 'Test', 'health': 5, 'attack': 3, 'tier': tier, 'type': 'Human',
                 'keywords': ['fast'], 'band_id': 'test_1', 'position': 0}
            ]
        )

        # Create the collapsed mine event
        result = EventSystem.create_event_selection(run, 'collapsed_mine')
        assert result.get('selection_created'), f"Tier {tier}: Failed to create collapsed_mine: {result}"

        selection = run.get_pending_selection()
        options = selection.get('options', [])

        # Verify Go Slow option
        go_slow = next((o for o in options if o['message'] == 'Go Slow'), None)
        assert go_slow, f"Tier {tier}: Go Slow option missing"
        expected_gold = tier * 4
        assert f'({expected_gold})' in go_slow['tooltip'], \
            f"Tier {tier}: Go Slow tooltip wrong: {go_slow['tooltip']}"

        # Verify Go Fast option
        go_fast = next((o for o in options if o['message'] == 'Go Fast'), None)
        assert go_fast, f"Tier {tier}: Go Fast option missing"
        expected_gold_fast = tier * 3
        assert f'({expected_gold_fast})' in go_fast['tooltip'], \
            f"Tier {tier}: Go Fast tooltip wrong: {go_fast['tooltip']}"

        # Verify Go Faster (should be enabled because band has 'fast' keyword)
        go_faster = next((o for o in options if o['message'] == 'Go Faster'), None)
        assert go_faster, f"Tier {tier}: Go Faster option missing"
        assert not go_faster['disabled'], f"Tier {tier}: Go Faster should be enabled (has fast)"
        expected_gold_faster = tier * 5
        assert f'({expected_gold_faster})' in go_faster['tooltip'], \
            f"Tier {tier}: Go Faster tooltip wrong: {go_faster['tooltip']}"

        # Verify no unresolved template variables in any tooltip
        for opt in options:
            tooltip = opt.get('tooltip', '')
            assert '{' not in tooltip, \
                f"Tier {tier}: Unresolved variable in '{opt['message']}' tooltip: {tooltip}"


def test_disabled_option_with_fast_keyword():
    """Test that Go Faster is disabled when band has no Fast keyword"""

    from game_engine.events.event_system import EventSystem

    run = MockRun(
        ring=2, position=3, zone='human_kingdom',
        gold=50, health=100,
        band=[
            {'name': 'Test', 'health': 5, 'attack': 3, 'tier': 2, 'type': 'Human',
             'keywords': ['Guard'], 'band_id': 'test_1', 'position': 0}
        ]
    )

    result = EventSystem.create_event_selection(run, 'collapsed_mine')
    assert result.get('selection_created'), f"Failed to create collapsed_mine: {result}"

    selection = run.get_pending_selection()
    options = selection.get('options', [])

    go_faster = next((o for o in options if o['message'] == 'Go Faster'), None)
    assert go_faster, "Go Faster option missing"
    assert go_faster['disabled'], "Go Faster should be disabled (no fast keyword)"


def test_watchtower_full_pipeline():
    """Test Watchtower event processes correctly through the full pipeline"""

    from game_engine.events.event_system import EventSystem

    run = MockRun(
        ring=3, position=5, zone='human_kingdom',
        gold=50, health=100,
        band=[
            {'name': 'Test', 'health': 5, 'attack': 3, 'tier': 3, 'type': 'Human',
             'keywords': [], 'band_id': 'test_1', 'position': 0}
        ]
    )

    result = EventSystem.create_event_selection(run, 'watchtower')
    assert result.get('selection_created'), f"Failed to create watchtower: {result}"

    selection = run.get_pending_selection()
    options = selection.get('options', [])

    # Pay for Help should show cost of tier * 6 = 18
    pay = next((o for o in options if o['message'] == 'Pay for Help'), None)
    assert pay, "Pay for Help option missing"
    assert pay['gold_cost'] == 18, f"Gold cost should be 18, got {pay['gold_cost']}"
    assert '(18)' in pay['tooltip'], f"Tooltip should show (18): {pay['tooltip']}"

    # Request Aid should show cost of tier * 3 = 9
    aid = next((o for o in options if o['message'] == 'Request Aid'), None)
    assert aid, "Request Aid option missing"
    assert aid['gold_cost'] == 9, f"Gold cost should be 9, got {aid['gold_cost']}"
    assert '(9)' in aid['tooltip'], f"Tooltip should show (9): {aid['tooltip']}"

    # Infiltrate should be disabled (no Hide keyword)
    infiltrate = next((o for o in options if o['message'] == 'Infiltrate'), None)
    assert infiltrate, "Infiltrate option missing"
    assert infiltrate['disabled'], "Infiltrate should be disabled (no Hide keyword)"

    # Verify no unresolved variables
    for opt in options:
        tooltip = opt.get('tooltip', '')
        assert '{' not in tooltip, \
            f"Unresolved variable in '{opt['message']}' tooltip: {tooltip}"


def test_vast_kennels_full_pipeline():
    """Test Vast Kennels event processes correctly (the previously broken event)"""

    from game_engine.events.event_system import EventSystem

    run = MockRun(
        ring=3, position=5, zone='human_kingdom',
        gold=50, health=100,
        band=[
            {'name': 'Test', 'health': 5, 'attack': 3, 'tier': 3, 'type': 'Beast',
             'keywords': [], 'band_id': 'test_1', 'position': 0}
        ]
    )

    result = EventSystem.create_event_selection(run, 'vast_kennels')
    assert result.get('selection_created'), f"Failed to create vast_kennels: {result}"

    selection = run.get_pending_selection()
    options = selection.get('options', [])

    # Buy a Treat should show dynamic gold cost and buff amount
    treat = next((o for o in options if o['message'] == 'Buy a Treat'), None)
    assert treat, "Buy a Treat option missing"
    assert treat['gold_cost'] == 9, f"Gold cost should be 9 (tier 3 * 3), got {treat['gold_cost']}"

    # THIS WAS THE BUG: tooltip should NOT contain {tier * 2} or {tier * 3}
    assert '{' not in treat['tooltip'], \
        f"REGRESSION: Unresolved template in Buy a Treat tooltip: {treat['tooltip']}"
    assert '+6 attack' in treat['tooltip'], \
        f"Should show +6 attack (tier 3 * 2): {treat['tooltip']}"
    assert '(9)' in treat['tooltip'], \
        f"Should show (9) gold cost: {treat['tooltip']}"

    # Pack Discount should be disabled (only 1 beast)
    pack = next((o for o in options if o['message'] == 'Pack Discount'), None)
    assert pack, "Pack Discount option missing"
    assert pack['disabled'], "Pack Discount should be disabled (< 3 beasts)"


def test_mercenary_camp_full_pipeline():
    """Test Mercenary Camp event processes correctly"""

    from game_engine.events.event_system import EventSystem

    run = MockRun(
        ring=2, position=5, zone='human_kingdom',
        gold=50, health=100,
        band=[
            {'name': 'A', 'health': 5, 'attack': 3, 'tier': 2, 'type': 'Human',
             'keywords': [], 'band_id': 'test_1', 'position': 0},
            {'name': 'B', 'health': 5, 'attack': 3, 'tier': 2, 'type': 'Beast',
             'keywords': [], 'band_id': 'test_2', 'position': 1},
        ]
    )

    result = EventSystem.create_event_selection(run, 'mercenary_camp')
    assert result.get('selection_created'), f"Failed to create mercenary_camp: {result}"

    selection = run.get_pending_selection()
    options = selection.get('options', [])

    # Hire Guard: gold_cost = tier * 6 = 12
    hire = next((o for o in options if o['message'] == 'Hire Guard'), None)
    assert hire, "Hire Guard option missing"
    assert hire['gold_cost'] == 12, f"Gold cost should be 12, got {hire['gold_cost']}"

    # Enter a Duel: tooltip should show +6/+6 (tier 2 * 3)
    duel = next((o for o in options if o['message'] == 'Enter a Duel'), None)
    assert duel, "Enter a Duel option missing"
    assert '+6/+6' in duel['tooltip'], f"Duel tooltip should show +6/+6: {duel['tooltip']}"
    assert '{' not in duel['tooltip'], f"Unresolved variable: {duel['tooltip']}"

    # Joint Alliance: should be disabled (only 2 unique tribes)
    alliance = next((o for o in options if o['message'] == 'Joint Alliance'), None)
    assert alliance, "Joint Alliance option missing"
    assert alliance['disabled'], "Joint Alliance should be disabled (< 4 unique tribes)"
    # Tooltip should show +2/+2 (tier 2)
    assert '+2/+2' in alliance['tooltip'], f"Alliance tooltip should show +2/+2: {alliance['tooltip']}"


# ==================== NEW EVENT CREATION TESTS ====================


def test_new_event_works_out_of_the_box():
    """
    Verify that a brand new event defined using the standard format
    works correctly through the full pipeline without any code changes.

    This is the "add events easily and have tooltips right out the box" test.
    """
    from game_engine.events.event_system import EventSystem
    from game_engine.events.events import ALL_CUSTOM_EVENTS

    # Define a completely new event using the standard format
    NEW_TEST_EVENT = {
        'id': 'test_tavern',
        'visit_rule': 'repeatable',
        'title': 'The Crossroads Tavern',
        'description': 'A bustling tavern at the crossroads.',
        'screens': [
            {
                'id': 'main',
                'type': 'make_choice',
                'parameters': {
                    'title': 'The Crossroads Tavern',
                    'message': 'What would you like to do?',
                    'choices': [
                        {
                            'name': 'Buy a Drink',
                            'tooltip': 'Pay ({gold_cost}) gold. Gain +{tier * 2}/+{tier * 2} to a random minion.',
                            'icon': '<svg>drink</svg>',
                            'gold_cost': 'tier * 2',
                            'on_select': 'test_buy_drink',
                        },
                        {
                            'name': 'Arm Wrestle',
                            'tooltip': 'Win ({gold_reward}) gold. Requires a minion with fast.',
                            'icon': '<svg>arm</svg>',
                            'gold_reward': 'tier * 5',
                            'condition': 'has_keyword_fast',
                            'on_select': 'test_arm_wrestle',
                        },
                        {
                            'name': 'Recruit Mercenary',
                            'tooltip': 'Pay ({gold_cost}) gold to gain a Tier {tier} mercenary.',
                            'icon': '<svg>merc</svg>',
                            'gold_cost': 'tier * 4',
                            'condition': 'band_size >= 1',
                            'next_event': 'test_recruit',
                        },
                        {
                            'name': 'Leave',
                            'tooltip': 'Leave the tavern.',
                            'icon': '<svg>leave</svg>',
                            'next_event': None,
                            'mark_event_complete': True,
                        }
                    ]
                }
            }
        ]
    }

    # Register it temporarily
    ALL_CUSTOM_EVENTS['test_tavern'] = NEW_TEST_EVENT

    try:
        for tier in [1, 2, 3, 4]:
            # Test with a band that has 'fast' keyword
            run = MockRun(
                ring=tier, position=0, zone='human_kingdom',
                gold=100, health=100,
                band=[
                    {'name': 'Speedy', 'health': 3, 'attack': 2, 'tier': tier, 'type': 'Human',
                     'keywords': ['fast'], 'band_id': 'test_1', 'position': 0},
                ]
            )

            result = EventSystem.create_event_selection(run, 'test_tavern')
            assert result.get('selection_created'), \
                f"Tier {tier}: Failed to create test_tavern event: {result}"

            selection = run.get_pending_selection()
            options = selection.get('options', [])
            assert len(options) == 4, f"Tier {tier}: Expected 4 options, got {len(options)}"

            # Verify Buy a Drink
            drink = next((o for o in options if o['message'] == 'Buy a Drink'), None)
            assert drink, f"Tier {tier}: Buy a Drink option missing"
            expected_cost = tier * 2
            expected_buff = tier * 2
            assert drink['gold_cost'] == expected_cost, \
                f"Tier {tier}: Drink cost should be {expected_cost}, got {drink['gold_cost']}"
            assert f'({expected_cost})' in drink['tooltip'], \
                f"Tier {tier}: Drink tooltip should show ({expected_cost}): {drink['tooltip']}"
            assert f'+{expected_buff}/+{expected_buff}' in drink['tooltip'], \
                f"Tier {tier}: Drink tooltip should show +{expected_buff}/+{expected_buff}: {drink['tooltip']}"
            assert '{' not in drink['tooltip'], \
                f"Tier {tier}: Unresolved variable in drink tooltip: {drink['tooltip']}"

            # Verify Arm Wrestle (enabled, has fast keyword)
            wrestle = next((o for o in options if o['message'] == 'Arm Wrestle'), None)
            assert wrestle, f"Tier {tier}: Arm Wrestle option missing"
            assert not wrestle['disabled'], \
                f"Tier {tier}: Arm Wrestle should be enabled (has fast keyword)"
            expected_reward = tier * 5
            assert f'({expected_reward})' in wrestle['tooltip'], \
                f"Tier {tier}: Wrestle tooltip should show ({expected_reward}): {wrestle['tooltip']}"

            # Verify Recruit Mercenary
            recruit = next((o for o in options if o['message'] == 'Recruit Mercenary'), None)
            assert recruit, f"Tier {tier}: Recruit option missing"
            assert not recruit['disabled'], \
                f"Tier {tier}: Recruit should be enabled (band_size >= 1)"
            expected_recruit_cost = tier * 4
            assert f'({expected_recruit_cost})' in recruit['tooltip'], \
                f"Tier {tier}: Recruit tooltip should show ({expected_recruit_cost}): {recruit['tooltip']}"
            assert f'Tier {tier}' in recruit['tooltip'], \
                f"Tier {tier}: Recruit tooltip should show Tier {tier}: {recruit['tooltip']}"

            # Verify Leave
            leave = next((o for o in options if o['message'] == 'Leave'), None)
            assert leave, f"Tier {tier}: Leave option missing"
            assert not leave['disabled'], f"Tier {tier}: Leave should always be enabled"

        # Test with NO fast keyword - Arm Wrestle should be disabled
        run_no_fast = MockRun(
            ring=2, position=0, zone='human_kingdom',
            gold=100, health=100,
            band=[
                {'name': 'Slow', 'health': 3, 'attack': 2, 'tier': 2, 'type': 'Human',
                 'keywords': ['Guard'], 'band_id': 'test_1', 'position': 0},
            ]
        )
        result = EventSystem.create_event_selection(run_no_fast, 'test_tavern')
        selection = run_no_fast.get_pending_selection()
        options = selection.get('options', [])
        wrestle = next((o for o in options if o['message'] == 'Arm Wrestle'), None)
        assert wrestle['disabled'], "Arm Wrestle should be disabled without fast keyword"

    finally:
        # Clean up - remove the test event
        del ALL_CUSTOM_EVENTS['test_tavern']


def test_new_event_validation():
    """Test that a well-formed new event passes validation, and a bad one fails"""
    from game_engine.events.event_helpers import validate_event_choices

    # Well-formed event with all recommended fields
    good_event = {
        'id': 'test_good_event',
        'screens': [{
            'type': 'make_choice',
            'parameters': {
                'choices': [
                    {
                        'name': 'Option A',
                        'tooltip': 'Do something cool.',
                        'icon': '<svg>icon</svg>',
                        'gold_cost': 'tier * 3',
                        'on_select': 'handler_a',
                    },
                    {
                        'name': 'Leave',
                        'tooltip': 'Walk away.',
                        'icon': '<svg>leave</svg>',
                        'next_event': None,
                    }
                ]
            }
        }]
    }
    is_valid, errors, warnings = validate_event_choices(good_event)
    assert is_valid, f"Well-formed event should pass: {errors}"
    assert len(warnings) == 0, f"Should have no warnings: {warnings}"

    # Bad event missing required 'name' field
    bad_event = {
        'id': 'test_bad_event',
        'screens': [{
            'type': 'make_choice',
            'parameters': {
                'choices': [
                    {
                        'tooltip': 'Do something.',
                        'icon': '<svg>icon</svg>',
                        'on_select': 'handler',
                    }
                ]
            }
        }]
    }
    is_valid, errors, warnings = validate_event_choices(bad_event)
    assert not is_valid, "Event missing 'name' should fail validation"


def test_lichdom_health_cost_conversion():
    """Test that health costs are properly disabled when player has Lichdom and insufficient gold"""
    from game_engine.events.event_system import EventSystem
    from game_engine.events.events import ALL_CUSTOM_EVENTS

    # Create an event with a health cost
    HEALTH_EVENT = {
        'id': 'test_health_event',
        'visit_rule': 'repeatable',
        'title': 'Test Health Cost',
        'screens': [{
            'id': 'main',
            'type': 'make_choice',
            'parameters': {
                'title': 'Test',
                'choices': [
                    {
                        'name': 'Sacrifice',
                        'tooltip': 'Pay {health_cost} health.',
                        'icon': '<svg>heart</svg>',
                        'health_cost': 5,
                        'on_select': 'test_sacrifice',
                    },
                    {
                        'name': 'Leave',
                        'tooltip': 'Leave.',
                        'icon': '<svg>leave</svg>',
                        'next_event': None,
                    }
                ]
            }
        }]
    }

    ALL_CUSTOM_EVENTS['test_health_event'] = HEALTH_EVENT

    try:
        # With lichdom and enough gold - should be enabled
        run_rich = MockRun(ring=1, gold=50, health=100)
        run_rich._hero_effects = {'lichdom': True}
        run_rich._band = [{'name': 'A', 'type': 'Human', 'keywords': [], 'health': 1, 'attack': 1}]
        result = EventSystem.create_event_selection(run_rich, 'test_health_event')
        options = run_rich.get_pending_selection()['options']
        sacrifice = next(o for o in options if o['message'] == 'Sacrifice')
        assert not sacrifice['disabled'], "Sacrifice with lichdom + enough gold should be enabled"
        assert sacrifice['lichdom'], "Should flag lichdom=True"

        # With lichdom and NOT enough gold - should be disabled
        run_poor = MockRun(ring=1, gold=2, health=100)
        run_poor._hero_effects = {'lichdom': True}
        run_poor._band = [{'name': 'A', 'type': 'Human', 'keywords': [], 'health': 1, 'attack': 1}]
        result = EventSystem.create_event_selection(run_poor, 'test_health_event')
        options = run_poor.get_pending_selection()['options']
        sacrifice = next(o for o in options if o['message'] == 'Sacrifice')
        assert sacrifice['disabled'], "Sacrifice with lichdom + insufficient gold should be disabled"

    finally:
        del ALL_CUSTOM_EVENTS['test_health_event']


# ==================== MAIN ====================


if __name__ == '__main__':
    import pytest
    sys.exit(pytest.main([__file__, '-v']))
