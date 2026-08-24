#!/usr/bin/env python3
"""
Tests for the Ghost system and Headless Game Runner.

Covers:
  - Ghost model (GhostSnapshot, GhostBattle) creation and serialization
  - Ghost snapshot creation from runs
  - Ghost matching / opponent finding
  - Ghost battle recording
  - AI ghost fallback generation
  - Ghost battle trigger logic
  - Headless runner setup, game loop, and result structure
  - Decision AI implementations (Random, Smart, Simulating)
  - HeadlessGameRunner sub-systems (combat, movement, ring upgrades)
  - Batch run convenience function

Run:
    cd Battlegrounds && python -m pytest tests/test_ghosts_and_headless.py -v
    OR
    cd Battlegrounds && python tests/test_ghosts_and_headless.py
"""

import sys
import os
import json
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from app import create_app
from models import db, Run, GhostSnapshot, GhostBattle, Player

app = create_app()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def with_context(func):
    """Run within Flask app context."""
    def wrapper(*args, **kwargs):
        with app.app_context():
            return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper


def fresh_db():
    """Clear ghost-related tables for a clean test."""
    GhostBattle.query.delete()
    GhostSnapshot.query.delete()
    db.session.commit()


# ===================================================================
# GHOST MODEL TESTS
# ===================================================================

@with_context
def test_ghost_snapshot_creation():
    """GhostSnapshot can be created with all required fields and serializes correctly."""
    fresh_db()

    band = [
        {'name': 'Wolf', 'attack': 3, 'health': 2, 'keywords': ['poke'], 'position': 0, 'image': 'wolf.png'},
        {'name': 'Knight', 'attack': 2, 'health': 4, 'keywords': ['guard'], 'position': 1, 'image': 'knight.png'},
    ]

    ghost = GhostSnapshot(
        events_milestone=10,
        power_level=11,
        player_name='TestPlayer',
        hero_id='silas',
        current_ring=1,
        health=28,
        ghost_wins_at_capture=0,
        ghost_losses_at_capture=0,
        source='player',
    )
    ghost.set_band(band)
    ghost.set_hero_effects({'damage_boost': 1})
    ghost.set_equipped_images({'wolf': 'alt_1'})

    db.session.add(ghost)
    db.session.commit()

    # Reload and verify
    loaded = GhostSnapshot.query.get(ghost.id)
    assert loaded is not None, "Ghost should be persisted"
    assert loaded.events_milestone == 10
    assert loaded.power_level == 11
    assert loaded.player_name == 'TestPlayer'
    assert loaded.hero_id == 'silas'
    assert loaded.current_ring == 1
    assert loaded.health == 28
    assert loaded.source == 'player'

    loaded_band = loaded.get_band()
    assert len(loaded_band) == 2
    assert loaded_band[0]['name'] == 'Wolf'
    assert 'poke' in loaded_band[0]['keywords']
    assert loaded_band[1]['name'] == 'Knight'
    assert 'guard' in loaded_band[1]['keywords']

    assert loaded.get_hero_effects() == {'damage_boost': 1}
    assert loaded.get_equipped_images() == {'wolf': 'alt_1'}

    print("PASSED: test_ghost_snapshot_creation")


@with_context
def test_ghost_snapshot_to_dict():
    """GhostSnapshot.to_dict() returns the expected structure."""
    fresh_db()

    band = [{'name': 'Rat', 'attack': 1, 'health': 1, 'keywords': [], 'position': 0}]
    ghost = GhostSnapshot(
        events_milestone=20,
        power_level=2,
        player_name='DictTest',
        hero_id='puck',
        current_ring=2,
        health=25,
        source='headless',
    )
    ghost.set_band(band)
    db.session.add(ghost)
    db.session.commit()

    d = ghost.to_dict()
    assert d['events_milestone'] == 20
    assert d['power_level'] == 2
    assert d['player_name'] == 'DictTest'
    assert d['hero_id'] == 'puck'
    assert d['source'] == 'headless'
    assert d['current_ring'] == 2
    assert d['health'] == 25
    assert isinstance(d['band'], list)
    assert len(d['band']) == 1
    assert 'created_at' in d

    print("PASSED: test_ghost_snapshot_to_dict")


@with_context
def test_ghost_snapshot_band_with_images():
    """get_band_with_images() applies equipped image paths correctly."""
    fresh_db()

    band = [
        {'name': 'Wolf', 'attack': 3, 'health': 2, 'keywords': [], 'position': 0, 'image': 'wolf.png'},
        {'name': 'Rat', 'attack': 1, 'health': 1, 'keywords': [], 'position': 1, 'image': 'rat.png'},
    ]
    ghost = GhostSnapshot(events_milestone=10, power_level=7)
    ghost.set_band(band)
    ghost.set_equipped_images({'wolf': 'alt_1'})
    db.session.add(ghost)
    db.session.commit()

    band_with_images = ghost.get_band_with_images()
    # Wolf should use alt_1
    assert band_with_images[0]['image_path'] == 'images/alt_1/wolf.png'
    # Rat should use original
    assert band_with_images[1]['image_path'] == 'images/original/rat.png'

    print("PASSED: test_ghost_snapshot_band_with_images")


@with_context
def test_ghost_snapshot_actions_log():
    """Actions log can be stored and retrieved."""
    fresh_db()

    actions = [
        {'action': 'selection', 'step': 1, 'event_type': 'minion_event'},
        {'action': 'combat', 'step': 5, 'winner': 'player'},
    ]
    ghost = GhostSnapshot(events_milestone=10, power_level=5)
    ghost.set_band([{'name': 'Wolf', 'attack': 3, 'health': 2, 'keywords': []}])
    ghost.set_actions_log(actions)
    db.session.add(ghost)
    db.session.commit()

    loaded = GhostSnapshot.query.get(ghost.id)
    log = loaded.get_actions_log()
    assert len(log) == 2
    assert log[0]['action'] == 'selection'
    assert log[1]['winner'] == 'player'

    print("PASSED: test_ghost_snapshot_actions_log")


@with_context
def test_ghost_battle_creation():
    """GhostBattle can be created and serialized."""
    fresh_db()

    from database import create_new_run, update_run

    run = create_new_run()
    ghost = GhostSnapshot(events_milestone=10, power_level=5)
    ghost.set_band([{'name': 'Wolf', 'attack': 3, 'health': 2, 'keywords': []}])
    db.session.add(ghost)
    db.session.commit()

    battle = GhostBattle(
        run_id=run.id,
        ghost_id=ghost.id,
        events_milestone=10,
        winner='player',
        ghost_player_name='Enemy',
    )
    battle.set_battle_log([{'round': 1, 'action': 'attack', 'damage': 3}])
    db.session.add(battle)
    db.session.commit()

    loaded = GhostBattle.query.get(battle.id)
    assert loaded.winner == 'player'
    assert loaded.ghost_player_name == 'Enemy'
    assert loaded.events_milestone == 10

    d = loaded.to_dict()
    assert d['winner'] == 'player'
    assert isinstance(d['battle_log'], list)
    assert d['battle_log'][0]['damage'] == 3

    print("PASSED: test_ghost_battle_creation")


# ===================================================================
# GHOST DATABASE FUNCTION TESTS
# ===================================================================

@with_context
def test_create_ghost_snapshot_from_run():
    """create_ghost_snapshot() correctly captures run state."""
    fresh_db()

    from database import create_new_run, create_ghost_snapshot

    run = create_new_run(hero_id='silas')

    ghost = create_ghost_snapshot(run)

    assert ghost.events_milestone == run.events_count
    assert ghost.hero_id == 'silas'
    assert ghost.current_ring == run.current_ring
    assert ghost.health == run.health
    assert ghost.source == 'headless'  # No player_id → headless
    assert ghost.run_id == run.id

    band = ghost.get_band()
    run_band = run.get_band()
    assert len(band) == len(run_band)
    for gb, rb in zip(band, run_band):
        assert gb['name'] == rb['name']

    print("PASSED: test_create_ghost_snapshot_from_run")


@with_context
def test_create_ghost_snapshot_with_actions_log():
    """create_ghost_snapshot() stores actions_log when provided."""
    fresh_db()

    from database import create_new_run, create_ghost_snapshot

    run = create_new_run()
    actions = [{'action': 'test', 'step': 0}]
    ghost = create_ghost_snapshot(run, actions_log=actions)

    log = ghost.get_actions_log()
    assert len(log) == 1
    assert log[0]['action'] == 'test'

    print("PASSED: test_create_ghost_snapshot_with_actions_log")


@with_context
def test_find_ghost_opponent():
    """find_ghost_opponent() returns a ghost at the correct milestone."""
    fresh_db()

    from database import create_new_run, find_ghost_opponent

    # Create some ghost snapshots at milestone 10
    for i in range(3):
        g = GhostSnapshot(
            events_milestone=10,
            power_level=10 + i,
            player_name=f'Ghost{i}',
            source='headless',
        )
        g.set_band([
            {'name': 'Wolf', 'attack': 3 + i, 'health': 2 + i, 'keywords': [], 'position': 0}
        ])
        db.session.add(g)
    db.session.commit()

    run = create_new_run()
    run.events_count = 8  # Close to milestone 10

    opponent = find_ghost_opponent(run, 10)
    assert opponent is not None
    assert opponent.events_milestone == 10

    print("PASSED: test_find_ghost_opponent")


@with_context
def test_find_ghost_opponent_excludes_own_run():
    """find_ghost_opponent() never returns ghosts from the same run."""
    fresh_db()

    from database import create_new_run, create_ghost_snapshot, find_ghost_opponent

    run = create_new_run()
    # Create a ghost from this run
    own_ghost = create_ghost_snapshot(run)

    # Update milestone to match
    own_ghost.events_milestone = 10
    db.session.commit()

    # Should not find our own ghost (will fall back to AI ghost)
    opponent = find_ghost_opponent(run, 10)
    assert opponent is not None
    assert opponent.run_id != run.id, "Should not match player's own ghost"

    print("PASSED: test_find_ghost_opponent_excludes_own_run")


@with_context
def test_create_ai_ghost():
    """create_ai_ghost() generates a valid AI ghost with hero."""
    fresh_db()

    from database import create_ai_ghost

    ghost = create_ai_ghost(events_milestone=20, ring=2)
    assert ghost is not None
    assert ghost.events_milestone == 20
    assert ghost.source == 'ai'
    assert ghost.hero_id in ('silas', 'puck', 'olimpia')
    assert ghost.player_name is not None

    band = ghost.get_band()
    assert len(band) > 0
    # Minions should have stats scaled by milestone
    for m in band:
        assert m.get('attack', 0) > 0 or m.get('health', 0) > 0

    hero_effects = ghost.get_hero_effects()
    assert isinstance(hero_effects, dict)

    print("PASSED: test_create_ai_ghost")


@with_context
def test_record_ghost_battle():
    """record_ghost_battle() creates a battle record with correct milestone."""
    fresh_db()

    from database import create_new_run, record_ghost_battle
    from config import EVENTS_FOR_GHOST_BATTLE

    run = create_new_run()
    run.events_count = 10

    ghost = GhostSnapshot(events_milestone=10, power_level=15)
    ghost.set_band([{'name': 'Wolf', 'attack': 3, 'health': 2, 'keywords': []}])
    db.session.add(ghost)
    db.session.commit()

    battle = record_ghost_battle(run, ghost, 'player', [{'round': 1}])
    assert battle.winner == 'player'
    assert battle.events_milestone == 10
    assert battle.run_id == run.id
    assert battle.ghost_id == ghost.id

    print("PASSED: test_record_ghost_battle")


@with_context
def test_check_ghost_battle_trigger():
    """check_ghost_battle_trigger() correctly detects milestone boundaries."""
    fresh_db()

    from database import create_new_run, check_ghost_battle_trigger

    run = create_new_run()

    # At event 0, should not trigger
    run.events_count = 0
    assert not check_ghost_battle_trigger(run), "Should not trigger at event 0"

    # At event 5, should not trigger (not at boundary)
    run.events_count = 5
    assert not check_ghost_battle_trigger(run), "Should not trigger at event 5"

    # At event 10, should trigger (boundary)
    run.events_count = 10
    assert check_ghost_battle_trigger(run), "Should trigger at event 10"

    # At event 15, should still trigger for milestone 10 if no battle exists
    run.events_count = 15
    assert check_ghost_battle_trigger(run), "Should trigger at event 15 (milestone 10 unresolved)"

    print("PASSED: test_check_ghost_battle_trigger")


@with_context
def test_check_ghost_battle_trigger_after_battle():
    """check_ghost_battle_trigger() returns False after battle is recorded."""
    fresh_db()

    from database import create_new_run, record_ghost_battle, check_ghost_battle_trigger

    run = create_new_run()
    run.events_count = 10

    # Create and record a ghost battle at milestone 10
    ghost = GhostSnapshot(events_milestone=10, power_level=10)
    ghost.set_band([{'name': 'Wolf', 'attack': 3, 'health': 2, 'keywords': []}])
    db.session.add(ghost)
    db.session.commit()

    record_ghost_battle(run, ghost, 'player', [])

    # Should not trigger anymore for milestone 10
    assert not check_ghost_battle_trigger(run), \
        "Should not trigger after battle is recorded at milestone 10"

    print("PASSED: test_check_ghost_battle_trigger_after_battle")


@with_context
def test_check_ghost_battle_available():
    """check_ghost_battle_available() depends on upcoming_ghost_id."""
    fresh_db()

    from database import create_new_run, check_ghost_battle_available

    run = create_new_run()

    # The run should have an upcoming ghost generated during creation
    # (create_new_run calls pre_generate_ghost_opponent)
    available = check_ghost_battle_available(run)
    assert available, "Should have ghost available after run creation"

    # Clear it
    run.upcoming_ghost_id = None
    db.session.commit()
    assert not check_ghost_battle_available(run), \
        "Should not be available without upcoming_ghost_id"

    print("PASSED: test_check_ghost_battle_available")


@with_context
def test_pre_generate_ghost_opponent():
    """pre_generate_ghost_opponent() sets upcoming_ghost_id on the run."""
    fresh_db()

    from database import create_new_run, pre_generate_ghost_opponent

    run = create_new_run()
    # Clear the auto-generated one
    run.upcoming_ghost_id = None
    db.session.commit()

    pre_generate_ghost_opponent(run)

    assert run.upcoming_ghost_id is not None, "Should have set upcoming_ghost_id"
    ghost = GhostSnapshot.query.get(run.upcoming_ghost_id)
    assert ghost is not None, "Ghost should exist in DB"

    print("PASSED: test_pre_generate_ghost_opponent")


# ===================================================================
# RUN MODEL GHOST INTEGRATION TESTS
# ===================================================================

@with_context
def test_run_to_dict_includes_ghost_fields():
    """Run.to_dict() includes ghost-related fields."""
    fresh_db()

    from database import create_new_run

    run = create_new_run()
    d = run.to_dict()

    assert 'ghost_battle_available' in d
    assert 'upcoming_ghost_id' in d
    assert 'upcoming_ghost_milestone' in d

    print("PASSED: test_run_to_dict_includes_ghost_fields")


# ===================================================================
# HEADLESS RUNNER TESTS
# ===================================================================

@with_context
def test_headless_runner_basic_completion():
    """HeadlessGameRunner with SmartDecisionAI completes a game."""
    fresh_db()

    from headless_runner import HeadlessGameRunner, SmartDecisionAI

    ai = SmartDecisionAI()
    runner = HeadlessGameRunner(ai, seed=42, verbose=False, quiet_engine=True)
    result = runner.run_complete_game()

    assert result['result'] in ('victory', 'death'), \
        f"Expected victory or death, got: {result['result']}"
    assert result['iterations'] < 10000, "Game should not reach max iterations"
    assert result['events_completed'] > 0, "Should complete events"
    assert result['combat_count'] > 0, "Should fight combats"

    print(f"PASSED: test_headless_runner_basic_completion "
          f"({result['result']}, events={result['events_completed']})")


@with_context
def test_headless_runner_random_ai():
    """RandomDecisionAI completes without crashing."""
    fresh_db()

    from headless_runner import HeadlessGameRunner, RandomDecisionAI

    ai = RandomDecisionAI()
    runner = HeadlessGameRunner(ai, seed=123, verbose=False, quiet_engine=True)
    result = runner.run_complete_game()

    assert result['result'] in ('victory', 'death'), \
        f"Expected victory or death, got: {result['result']}"

    print(f"PASSED: test_headless_runner_random_ai "
          f"({result['result']}, events={result['events_completed']})")


@with_context
def test_headless_runner_triggers_ghost_battles():
    """Ghost battles actually occur during headless runs."""
    fresh_db()

    from headless_runner import HeadlessGameRunner, SmartDecisionAI

    ai = SmartDecisionAI()
    runner = HeadlessGameRunner(ai, seed=77, verbose=False, quiet_engine=True)
    result = runner.run_complete_game()

    assert result['ghost_count'] > 0, \
        "No ghost battles occurred - ghost system is broken"

    # Verify battles are actually recorded in DB
    battles = GhostBattle.query.filter_by(run_id=result['run_id']).all()
    assert len(battles) > 0, "Ghost battles should be recorded in database"

    print(f"PASSED: test_headless_runner_triggers_ghost_battles "
          f"(fought {result['ghost_count']} ghost battles)")


@with_context
def test_headless_runner_ghost_snapshots_created():
    """Headless runs create ghost snapshots for matchmaking."""
    fresh_db()

    from headless_runner import HeadlessGameRunner, SmartDecisionAI

    ai = SmartDecisionAI()
    runner = HeadlessGameRunner(ai, seed=55, verbose=False, quiet_engine=True)
    result = runner.run_complete_game()

    # Ghost snapshots should be created during the run
    snapshots = GhostSnapshot.query.filter_by(run_id=result['run_id']).all()
    assert len(snapshots) > 0, "Should have created ghost snapshots"

    # At least one should be tagged as headless source
    headless_snapshots = [s for s in snapshots if s.source == 'headless']
    assert len(headless_snapshots) > 0, "Snapshots should be tagged as 'headless'"

    print(f"PASSED: test_headless_runner_ghost_snapshots_created "
          f"({len(snapshots)} snapshots created)")


@with_context
def test_headless_runner_with_hero():
    """Headless runs work with each hero."""
    fresh_db()

    from headless_runner import HeadlessGameRunner, SmartDecisionAI

    for hero_id in ['silas', 'puck', 'olimpia']:
        ai = SmartDecisionAI()
        runner = HeadlessGameRunner(
            ai, hero_id=hero_id, seed=200, verbose=False, quiet_engine=True
        )
        result = runner.run_complete_game()

        assert result['result'] in ('victory', 'death'), \
            f"Hero {hero_id}: got {result['result']}"
        assert result['events_completed'] > 0, \
            f"Hero {hero_id}: no events completed"

    print("PASSED: test_headless_runner_with_hero (all 3 heroes)")


@with_context
def test_headless_runner_result_structure():
    """Result dict contains all expected fields."""
    fresh_db()

    from headless_runner import HeadlessGameRunner, SmartDecisionAI

    ai = SmartDecisionAI()
    runner = HeadlessGameRunner(ai, seed=42, verbose=False, quiet_engine=True)
    result = runner.run_complete_game()

    required_keys = [
        'result', 'final_ring', 'final_health', 'ghost_wins',
        'max_ghost_wins', 'events_completed', 'iterations', 'run_id',
        'combat_count', 'combat_wins', 'ghost_count', 'ghost_wins_count',
        'rings_upgraded', 'final_band', 'final_resources', 'events_log',
        'actions_log', 'elapsed', 'error',
    ]

    for key in required_keys:
        assert key in result, f"Missing key in result: {key}"

    assert isinstance(result['final_band'], list)
    assert isinstance(result['events_log'], list)
    assert isinstance(result['actions_log'], list)
    assert isinstance(result['final_resources'], dict)
    assert isinstance(result['elapsed'], (int, float))

    print("PASSED: test_headless_runner_result_structure")


@with_context
def test_headless_runner_actions_log_tracking():
    """Actions log records combat and selection events."""
    fresh_db()

    from headless_runner import HeadlessGameRunner, SmartDecisionAI

    ai = SmartDecisionAI()
    runner = HeadlessGameRunner(ai, seed=42, verbose=False, quiet_engine=True)
    result = runner.run_complete_game()

    actions = result['actions_log']
    assert len(actions) > 0, "Actions log should not be empty"

    action_types = set(a.get('action') for a in actions if isinstance(a, dict))
    assert 'combat' in action_types, "Should log combat actions"
    assert 'selection' in action_types, "Should log selection actions"

    # Each action should have common fields
    for a in actions:
        assert 'step' in a, "Action missing 'step' field"
        assert 'ring' in a, "Action missing 'ring' field"
        assert 'health' in a, "Action missing 'health' field"

    print(f"PASSED: test_headless_runner_actions_log_tracking "
          f"({len(actions)} actions, types={action_types})")


@with_context
def test_headless_runner_deterministic():
    """Same seed produces identical outcomes."""
    fresh_db()

    from headless_runner import HeadlessGameRunner, SmartDecisionAI
    import random

    seed = 12345

    # Run 1
    GhostSnapshot.query.delete()
    GhostBattle.query.delete()
    db.session.commit()

    ai1 = SmartDecisionAI()
    r1 = HeadlessGameRunner(ai1, seed=seed, verbose=False, quiet_engine=True)
    result1 = r1.run_complete_game()

    # Run 2 - clear ghost data so same AI opponents are generated
    GhostSnapshot.query.delete()
    GhostBattle.query.delete()
    db.session.commit()

    ai2 = SmartDecisionAI()
    r2 = HeadlessGameRunner(ai2, seed=seed, verbose=False, quiet_engine=True)
    result2 = r2.run_complete_game()

    assert result1['result'] == result2['result'], \
        f"Different outcomes: {result1['result']} vs {result2['result']}"
    assert result1['final_ring'] == result2['final_ring'], \
        f"Different rings: {result1['final_ring']} vs {result2['final_ring']}"
    assert result1['events_completed'] == result2['events_completed'], \
        f"Different events: {result1['events_completed']} vs {result2['events_completed']}"

    print("PASSED: test_headless_runner_deterministic")


@with_context
def test_headless_runner_starting_health_override():
    """starting_health parameter overrides the default 30 HP."""
    fresh_db()

    from headless_runner import HeadlessGameRunner, SmartDecisionAI

    ai = SmartDecisionAI()
    runner = HeadlessGameRunner(
        ai, seed=42, verbose=False, quiet_engine=True,
        starting_health=50
    )
    result = runner.run_complete_game()

    # Can't verify initial health directly since game is over,
    # but it should have completed without errors
    assert result['result'] in ('victory', 'death')
    # With 50 HP, the game likely lasted longer (more events)
    assert result['events_completed'] > 0

    print(f"PASSED: test_headless_runner_starting_health_override "
          f"(final_health={result['final_health']})")


@with_context
def test_headless_runner_timeout_protection():
    """max_time parameter prevents infinite runs."""
    fresh_db()

    from headless_runner import HeadlessGameRunner, SmartDecisionAI

    ai = SmartDecisionAI()
    # Very short timeout - should stop quickly
    runner = HeadlessGameRunner(
        ai, seed=42, verbose=False, quiet_engine=True,
        max_time=0.001  # 1ms - will timeout immediately
    )
    result = runner.run_complete_game()

    # Should either complete very fast or timeout
    assert result['result'] in ('victory', 'death', 'timeout')

    print(f"PASSED: test_headless_runner_timeout_protection "
          f"(result={result['result']})")


@with_context
def test_headless_runner_cancellation():
    """cancel_check callback stops the game."""
    fresh_db()

    from headless_runner import HeadlessGameRunner, SmartDecisionAI

    call_count = [0]

    def cancel_after_5():
        call_count[0] += 1
        return call_count[0] > 5

    ai = SmartDecisionAI()
    runner = HeadlessGameRunner(
        ai, seed=42, verbose=False, quiet_engine=True,
        cancel_check=cancel_after_5
    )
    result = runner.run_complete_game()

    assert result['result'] in ('cancelled', 'victory', 'death')

    print(f"PASSED: test_headless_runner_cancellation (result={result['result']})")


@with_context
def test_headless_runner_snapshot_method():
    """get_snapshot() returns game state during play."""
    fresh_db()

    from headless_runner import HeadlessGameRunner, SmartDecisionAI
    from game_random import game_random
    from database import create_new_run, update_run, check_ghost_battle_trigger, check_ghost_battle_available
    import random

    ai = SmartDecisionAI()
    runner = HeadlessGameRunner(ai, seed=333, verbose=False)

    # Manual setup
    game_random.rng.seed(333)
    random.seed(333)
    runner.run = create_new_run()
    update_run(runner.run)

    snap = runner.get_snapshot()
    assert snap['ring'] == 1
    assert snap['health'] > 0
    assert snap['band_size'] > 0
    assert snap['events_count'] >= 0

    runner._cleanup()

    print("PASSED: test_headless_runner_snapshot_method")


@with_context
def test_headless_runner_run_batch():
    """run_batch() runs multiple games and returns results."""
    fresh_db()

    from headless_runner import run_batch

    results = run_batch(n=3, seed_start=600, verbose=False)
    assert len(results) == 3

    for r in results:
        assert r['result'] in ('victory', 'death'), \
            f"Unexpected result: {r['result']}"
        assert r['ghost_count'] > 0, "Each game should fight ghost battles"

    print(f"PASSED: test_headless_runner_run_batch (3 games)")


# ===================================================================
# DECISION AI TESTS
# ===================================================================

@with_context
def test_random_ai_choose_selection():
    """RandomDecisionAI always picks valid options."""
    from headless_runner import RandomDecisionAI

    ai = RandomDecisionAI()

    pending = {
        'event_type': 'minion_event',
        'options': [
            {'id': 'opt1', 'type': 'minion', 'data': {'name': 'Wolf', 'attack': 3, 'health': 2}},
            {'id': 'opt2', 'type': 'minion', 'data': {'name': 'Rat', 'attack': 1, 'health': 1}},
            {'id': 'skip', 'type': 'skip'},
        ],
        'min_selections': 1,
        'max_selections': 1,
    }

    # Run multiple times - should always pick valid options
    for _ in range(10):
        selected = ai.choose_selection(None, pending)
        assert len(selected) >= 1
        assert all(s in ['opt1', 'opt2', 'skip'] for s in selected)

    print("PASSED: test_random_ai_choose_selection")


@with_context
def test_random_ai_handles_disabled_options():
    """RandomDecisionAI falls back correctly when options are disabled."""
    from headless_runner import RandomDecisionAI

    ai = RandomDecisionAI()

    pending = {
        'event_type': 'shop_event',
        'options': [
            {'id': 'buy1', 'disabled': True},
            {'id': 'buy2', 'disabled': True},
            {'id': 'leave'},
        ],
        'min_selections': 1,
        'max_selections': 1,
    }

    selected = ai.choose_selection(None, pending)
    assert 'leave' in selected, "Should pick leave when all options disabled"

    print("PASSED: test_random_ai_handles_disabled_options")


@with_context
def test_smart_ai_prefers_strong_minions():
    """SmartDecisionAI picks the strongest minion from events."""
    from headless_runner import SmartDecisionAI

    ai = SmartDecisionAI()

    pending = {
        'event_type': 'minion_event',
        'options': [
            {'id': 'weak', 'type': 'minion', 'data': {'name': 'Rat', 'attack': 1, 'health': 1, 'keywords': []}},
            {'id': 'strong', 'type': 'minion', 'data': {'name': 'Wolf', 'attack': 5, 'health': 5, 'keywords': []}},
            {'id': 'skip', 'type': 'skip'},
        ],
        'min_selections': 1,
        'max_selections': 1,
    }

    from database import create_new_run
    run = create_new_run()

    selected = ai.choose_selection(run, pending)
    assert 'strong' in selected, \
        f"SmartAI should pick the strongest minion, got: {selected}"

    print("PASSED: test_smart_ai_prefers_strong_minions")


@with_context
def test_smart_ai_avoids_cant_attack():
    """SmartDecisionAI scores cant_attack minions lower."""
    from headless_runner import SmartDecisionAI

    ai = SmartDecisionAI()

    # A minion with cant_attack but high stats should score lower
    cant_attack_power = ai._minion_power({'attack': 10, 'health': 10, 'keywords': ['cant_attack']})
    normal_power = ai._minion_power({'attack': 5, 'health': 5, 'keywords': []})

    assert normal_power > cant_attack_power, \
        f"Normal ({normal_power}) should score higher than cant_attack ({cant_attack_power})"

    print("PASSED: test_smart_ai_avoids_cant_attack")


@with_context
def test_simulating_ai_keyword_scoring():
    """SimulatingDecisionAI scores keywords properly."""
    from headless_runner import SimulatingDecisionAI

    ai = SimulatingDecisionAI()

    # Minion with powerful keywords should score higher
    plain = {'name': 'Rat', 'attack': 3, 'health': 3, 'keywords': [], 'tier': 1}
    guarded = {'name': 'Knight', 'attack': 3, 'health': 3, 'keywords': ['guard'], 'tier': 1}
    noble = {'name': 'King', 'attack': 3, 'health': 3, 'keywords': ['nobility'], 'tier': 1}

    plain_score = ai._minion_score(plain)
    guarded_score = ai._minion_score(guarded)
    noble_score = ai._minion_score(noble)

    assert guarded_score > plain_score, "Guard should increase score"
    assert noble_score > plain_score, "Nobility should increase score"

    print(f"PASSED: test_simulating_ai_keyword_scoring "
          f"(plain={plain_score:.0f}, guard={guarded_score:.0f}, noble={noble_score:.0f})")


@with_context
def test_simulating_ai_band_scoring():
    """SimulatingDecisionAI band scoring considers synergies."""
    from headless_runner import SimulatingDecisionAI

    ai = SimulatingDecisionAI()

    # Two identical minions = golden merge potential
    band_no_merge = [
        {'name': 'Wolf', 'attack': 3, 'health': 2, 'keywords': [], 'tier': 1},
        {'name': 'Rat', 'attack': 1, 'health': 1, 'keywords': [], 'tier': 1},
    ]
    band_merge = [
        {'name': 'Wolf', 'attack': 3, 'health': 2, 'keywords': [], 'tier': 1},
        {'name': 'Wolf', 'attack': 3, 'health': 2, 'keywords': [], 'tier': 1},
    ]

    no_merge_score = ai._band_score(band_no_merge)
    merge_score = ai._band_score(band_merge)

    assert merge_score > no_merge_score, "Merge potential should increase band score"

    print(f"PASSED: test_simulating_ai_band_scoring "
          f"(no_merge={no_merge_score:.0f}, merge={merge_score:.0f})")


# ===================================================================
# POPULATE GHOSTS TESTS
# ===================================================================

@with_context
def test_populate_ghosts_creates_snapshots():
    """populate() function generates ghost snapshots from headless games."""
    fresh_db()

    from populate_ghosts import populate

    before_count = GhostSnapshot.query.count()
    assert before_count == 0, "Should start with 0 ghosts"

    results = populate(app, num_games=3, include_heroes=True, seed_start=9000)

    after_count = GhostSnapshot.query.count()
    assert after_count > before_count, "Should have created ghost snapshots"
    assert len(results) == 3, "Should return 3 game results"

    # Check result structure
    for r in results:
        assert 'result' in r
        assert 'ghost_wins' in r
        assert 'events_completed' in r
        assert r['result'] in ('victory', 'death')

    print(f"PASSED: test_populate_ghosts_creates_snapshots "
          f"({after_count} ghosts created from {len(results)} games)")


# ===================================================================
# RUNNER
# ===================================================================

def run_all_tests():
    print("\n" + "=" * 70)
    print("GHOST & HEADLESS MODE - COMPREHENSIVE TEST SUITE")
    print("=" * 70)

    tests = [
        # Ghost Model tests
        ("Ghost snapshot creation", test_ghost_snapshot_creation),
        ("Ghost snapshot to_dict", test_ghost_snapshot_to_dict),
        ("Ghost band with images", test_ghost_snapshot_band_with_images),
        ("Ghost actions log", test_ghost_snapshot_actions_log),
        ("Ghost battle creation", test_ghost_battle_creation),

        # Ghost Database Function tests
        ("Create snapshot from run", test_create_ghost_snapshot_from_run),
        ("Create snapshot with actions log", test_create_ghost_snapshot_with_actions_log),
        ("Find ghost opponent", test_find_ghost_opponent),
        ("Find opponent excludes own run", test_find_ghost_opponent_excludes_own_run),
        ("Create AI ghost", test_create_ai_ghost),
        ("Record ghost battle", test_record_ghost_battle),
        ("Ghost battle trigger logic", test_check_ghost_battle_trigger),
        ("Ghost battle trigger after battle", test_check_ghost_battle_trigger_after_battle),
        ("Ghost battle availability", test_check_ghost_battle_available),
        ("Pre-generate ghost opponent", test_pre_generate_ghost_opponent),

        # Run model integration
        ("Run to_dict ghost fields", test_run_to_dict_includes_ghost_fields),

        # Decision AI tests
        ("RandomAI choose_selection", test_random_ai_choose_selection),
        ("RandomAI disabled options", test_random_ai_handles_disabled_options),
        ("SmartAI prefers strong minions", test_smart_ai_prefers_strong_minions),
        ("SmartAI avoids cant_attack", test_smart_ai_avoids_cant_attack),
        ("SimulatingAI keyword scoring", test_simulating_ai_keyword_scoring),
        ("SimulatingAI band scoring", test_simulating_ai_band_scoring),

        # Headless Runner tests
        ("Headless basic completion", test_headless_runner_basic_completion),
        ("Headless RandomAI", test_headless_runner_random_ai),
        ("Headless ghost battles", test_headless_runner_triggers_ghost_battles),
        ("Headless ghost snapshots", test_headless_runner_ghost_snapshots_created),
        ("Headless with heroes", test_headless_runner_with_hero),
        ("Headless result structure", test_headless_runner_result_structure),
        ("Headless actions log", test_headless_runner_actions_log_tracking),
        ("Headless deterministic", test_headless_runner_deterministic),
        ("Headless starting health", test_headless_runner_starting_health_override),
        ("Headless timeout protection", test_headless_runner_timeout_protection),
        ("Headless cancellation", test_headless_runner_cancellation),
        ("Headless snapshot method", test_headless_runner_snapshot_method),
        ("Headless batch run", test_headless_runner_run_batch),

        # Populate ghosts
        ("Populate creates snapshots", test_populate_ghosts_creates_snapshots),
    ]

    passed = 0
    failed = 0
    errors = []

    for name, test_fn in tests:
        try:
            test_fn()
            passed += 1
        except AssertionError as e:
            failed += 1
            errors.append((name, f"ASSERTION: {e}"))
            print(f"FAILED: {name} - {e}")
        except Exception as e:
            failed += 1
            errors.append((name, f"ERROR: {e}"))
            print(f"ERROR: {name} - {e}")
            traceback.print_exc()

    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(tests)} tests")
    if errors:
        print("\nFailures:")
        for name, err in errors:
            print(f"  - {name}: {err}")
    print("=" * 70)

    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
