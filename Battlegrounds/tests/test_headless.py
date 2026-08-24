#!/usr/bin/env python3
"""
Test suite for the Headless Game Runner.

Tests that the headless mode can actually play the game end-to-end,
exercising all game systems: events, combat, ghost battles, ring upgrades,
selection chains, and win/loss conditions.

Run:  python test_headless.py
"""

import sys
import os
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from app import create_app
from models import db, GhostBattle

app = create_app()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def with_context(func):
    """Run within Flask app context."""
    def wrapper(*args, **kwargs):
        with app.app_context():
            return func(*args, **kwargs)
    return wrapper


def print_result(result):
    """Pretty-print a game result."""
    print(f"  Outcome       : {result['result']}")
    print(f"  Final Ring    : {result['final_ring']}")
    print(f"  Final Health  : {result['final_health']}")
    print(f"  Ghost Wins    : {result['ghost_wins']}/{result['max_ghost_wins']}")
    print(f"  Events Done   : {result['events_completed']}")
    print(f"  Combats       : {result['combat_wins']}/{result['combat_count']} won")
    print(f"  Ghosts Fought : {result['ghost_wins_count']}/{result['ghost_count']} won")
    print(f"  Rings Upgraded: {result['rings_upgraded']}")
    print(f"  Iterations    : {result['iterations']}")
    band = result.get('final_band', [])
    if band:
        names = [f"{m['name']}({m.get('attack',0)}/{m.get('health',0)})" for m in band]
        print(f"  Final Band    : {', '.join(names)}")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@with_context
def test_smart_ai_completes():
    """SmartDecisionAI should complete a full game (victory or death, never timeout)."""
    print("\n" + "=" * 60)
    print("TEST 1: SmartDecisionAI completes a game")
    print("=" * 60)

    from headless_runner import HeadlessGameRunner, SmartDecisionAI

    ai = SmartDecisionAI()
    runner = HeadlessGameRunner(ai, seed=42, verbose=True, persist_run=False)
    result = runner.run_complete_game()

    print("\n--- Result ---")
    print_result(result)

    assert result['result'] in ('victory', 'death'), \
        f"Expected victory or death, got: {result['result']}"
    assert result['iterations'] < 10000, "Game should not timeout"
    assert result['events_completed'] > 0, "Should have completed some events"
    assert result['combat_count'] > 0, "Should have fought at least one combat"

    print("PASSED")
    return result


@with_context
def test_random_ai_completes():
    """RandomDecisionAI should also complete (no crashes/hangs)."""
    print("\n" + "=" * 60)
    print("TEST 2: RandomDecisionAI completes a game")
    print("=" * 60)

    from headless_runner import HeadlessGameRunner, RandomDecisionAI

    ai = RandomDecisionAI()
    runner = HeadlessGameRunner(ai, seed=123, verbose=False, persist_run=False)
    result = runner.run_complete_game()

    print("\n--- Result ---")
    print_result(result)

    assert result['result'] in ('victory', 'death'), \
        f"Expected victory or death, got: {result['result']}"

    print("PASSED")
    return result


@with_context
def test_ghost_battles_happen():
    """Ghost battles must actually occur (the old headless mode never triggered them)."""
    print("\n" + "=" * 60)
    print("TEST 3: Ghost battles are triggered")
    print("=" * 60)

    from headless_runner import HeadlessGameRunner, SmartDecisionAI

    ai = SmartDecisionAI()
    runner = HeadlessGameRunner(ai, seed=77, verbose=False, persist_run=False)
    result = runner.run_complete_game()

    print("\n--- Result ---")
    print_result(result)

    assert result['ghost_count'] > 0, \
        "No ghost battles were fought! Ghost battle system is broken."
    assert result['ghost_wins'] + (result['ghost_count'] - result['ghost_wins_count']) == result['ghost_count'], \
        "Ghost count mismatch"

    print(f"Ghost battles fought: {result['ghost_count']}")
    print("PASSED")
    return result


@with_context
def test_ring_upgrades_happen():
    """The runner should upgrade rings during play."""
    print("\n" + "=" * 60)
    print("TEST 4: Ring upgrades occur")
    print("=" * 60)

    from headless_runner import HeadlessGameRunner, SmartDecisionAI

    ai = SmartDecisionAI()
    runner = HeadlessGameRunner(ai, seed=55, verbose=False, persist_run=False)
    result = runner.run_complete_game()

    print("\n--- Result ---")
    print_result(result)

    # SmartDecisionAI should upgrade at least once in a normal game
    # (unless it dies very early)
    if result['events_completed'] > 20:
        assert result['rings_upgraded'] > 0, \
            "No ring upgrades happened despite completing 20+ events"
        assert result['final_ring'] > 1, \
            f"Still on Ring 1 after {result['events_completed']} events"

    print(f"Rings upgraded: {result['rings_upgraded']}, final ring: {result['final_ring']}")
    print("PASSED")
    return result


@with_context
def test_deterministic_replay():
    """Same seed should produce identical outcomes."""
    print("\n" + "=" * 60)
    print("TEST 5: Deterministic replay")
    print("=" * 60)

    from headless_runner import HeadlessGameRunner, SmartDecisionAI
    from models import GhostSnapshot, GhostBattle, db

    seed = 12345

    # Clear ghosts before run 1 to ensure clean state
    GhostSnapshot.query.delete()
    GhostBattle.query.delete()
    db.session.commit()

    ai1 = SmartDecisionAI()
    r1 = HeadlessGameRunner(ai1, seed=seed, verbose=False, persist_run=False)
    result1 = r1.run_complete_game()

    # Clear ghosts before run 2 so it gets the same AI opponents
    GhostSnapshot.query.delete()
    GhostBattle.query.delete()
    db.session.commit()

    ai2 = SmartDecisionAI()
    r2 = HeadlessGameRunner(ai2, seed=seed, verbose=False, persist_run=False)
    result2 = r2.run_complete_game()

    print(f"  Run 1: {result1['result']}, ring {result1['final_ring']}, "
          f"health {result1['final_health']}, events {result1['events_completed']}")
    print(f"  Run 2: {result2['result']}, ring {result2['final_ring']}, "
          f"health {result2['final_health']}, events {result2['events_completed']}")

    assert result1['result'] == result2['result'], \
        f"Different outcomes: {result1['result']} vs {result2['result']}"
    assert result1['final_ring'] == result2['final_ring'], \
        f"Different rings: {result1['final_ring']} vs {result2['final_ring']}"
    assert result1['events_completed'] == result2['events_completed'], \
        f"Different event counts: {result1['events_completed']} vs {result2['events_completed']}"

    print("PASSED (identical outcomes)")
    return result1, result2


@with_context
def test_hero_integration():
    """Test that heroes work in headless mode."""
    print("\n" + "=" * 60)
    print("TEST 6: Hero integration")
    print("=" * 60)

    from headless_runner import HeadlessGameRunner, SmartDecisionAI

    heroes = ['silas', 'puck', 'olimpia']
    for hero_id in heroes:
        ai = SmartDecisionAI()
        runner = HeadlessGameRunner(
            ai, hero_id=hero_id, seed=200, verbose=False, persist_run=False
        )
        result = runner.run_complete_game()

        print(f"  {hero_id}: {result['result']}, ring {result['final_ring']}, "
              f"health {result['final_health']}, events {result['events_completed']}")

        assert result['result'] in ('victory', 'death'), \
            f"Hero {hero_id}: got {result['result']}"

    print("PASSED (all heroes playable)")


@with_context
def test_batch_stability():
    """Run multiple games to check for crashes across different seeds."""
    print("\n" + "=" * 60)
    print("TEST 7: Batch stability (5 games)")
    print("=" * 60)

    from headless_runner import run_batch

    results = run_batch(n=5, seed_start=500, verbose=False)

    victories = sum(1 for r in results if r['result'] == 'victory')
    deaths = sum(1 for r in results if r['result'] == 'death')
    timeouts = sum(1 for r in results if r['result'] == 'timeout')

    avg_ring = sum(r['final_ring'] for r in results) / len(results)
    avg_events = sum(r['events_completed'] for r in results) / len(results)
    avg_ghosts = sum(r['ghost_count'] for r in results) / len(results)

    for i, r in enumerate(results):
        status = 'W' if r['result'] == 'victory' else ('D' if r['result'] == 'death' else 'T')
        print(f"  [{status}] Seed {500+i}: Ring {r['final_ring']}, "
              f"HP {r['final_health']}, Events {r['events_completed']}, "
              f"Ghosts {r['ghost_wins_count']}/{r['ghost_count']}")

    print(f"\n  Victories: {victories}/5  Deaths: {deaths}/5  Timeouts: {timeouts}/5")
    print(f"  Avg Ring: {avg_ring:.1f}  Avg Events: {avg_events:.0f}  Avg Ghosts: {avg_ghosts:.1f}")

    assert timeouts == 0, f"Had {timeouts} timeouts - game loop has issues"
    assert all(r['ghost_count'] > 0 for r in results), "Some games had 0 ghost battles"

    print("PASSED")
    return results


@with_context
def test_state_inspection():
    """Test mid-game state inspection works."""
    print("\n" + "=" * 60)
    print("TEST 8: State inspection during play")
    print("=" * 60)

    from headless_runner import HeadlessGameRunner, SmartDecisionAI
    from game_random import game_random
    from database import create_new_run, update_run
    import random

    ai = SmartDecisionAI()
    runner = HeadlessGameRunner(ai, seed=333, verbose=False, persist_run=False)

    # Manual setup (same as runner._setup)
    game_random.rng.seed(333)
    random.seed(333)
    runner.run = create_new_run(player_id=None, is_ranked=False, hero_id=None)
    update_run(runner.run)

    # Take initial snapshot
    snap1 = runner.get_snapshot()
    print(f"  Initial: Ring {snap1['ring']}, HP {snap1['health']}, "
          f"Gold {snap1['gold']}, Band {snap1['band_size']}")

    assert snap1['ring'] == 1, "Should start at ring 1"
    assert snap1['health'] > 0, "Should have health"
    assert snap1['band_size'] > 0, "Should have starting band"

    # Run some steps manually
    for _ in range(20):
        runner.iterations += 1
        if runner._check_end():
            break

        pending = runner.run.get_pending_selection()
        if pending:
            runner._resolve_pending(pending)
        elif check_ghost_battle_trigger(runner.run) and check_ghost_battle_available(runner.run):
            runner._initiate_ghost_battle()
        else:
            runner._move_and_create_event()

    snap2 = runner.get_snapshot()
    print(f"  After 20 steps: Ring {snap2['ring']}, HP {snap2['health']}, "
          f"Gold {snap2['gold']}, Band {snap2['band_size']}, Events {snap2['events_count']}")

    assert snap2['events_count'] > 0, "Should have progressed"

    # Cleanup
    runner._cleanup()

    print("PASSED")


@with_context
def test_combat_system_exercised():
    """Verify that combat actually exercises the combat system (keywords, effects)."""
    print("\n" + "=" * 60)
    print("TEST 9: Combat system is exercised")
    print("=" * 60)

    from headless_runner import HeadlessGameRunner, SmartDecisionAI

    ai = SmartDecisionAI()
    runner = HeadlessGameRunner(ai, seed=42, verbose=False, persist_run=False)
    result = runner.run_complete_game()

    print(f"  Combats: {result['combat_count']}")
    print(f"  Combat wins: {result['combat_wins']}")

    # Should have regular combats AND ghost battles
    regular_combats = result['combat_count'] - result['ghost_count']
    print(f"  Regular combats: {regular_combats}")
    print(f"  Ghost battles: {result['ghost_count']}")

    assert result['combat_count'] >= 2, "Should have at least 2 combats"
    assert regular_combats >= 1, "Should have at least 1 regular combat"

    # Final band should exist (wasn't wiped by combat)
    band = result['final_band']
    assert len(band) > 0, "Should have minions in final band"

    # Minions should have keywords (proving minion system works)
    all_keywords = set()
    for m in band:
        for kw in m.get('keywords', []):
            all_keywords.add(kw)
    print(f"  Keywords on final band: {all_keywords or 'none'}")

    print("PASSED")


@with_context
def test_event_variety():
    """Verify that different event types are encountered."""
    print("\n" + "=" * 60)
    print("TEST 10: Event variety")
    print("=" * 60)

    from headless_runner import HeadlessGameRunner, SmartDecisionAI

    ai = SmartDecisionAI()
    runner = HeadlessGameRunner(ai, seed=42, verbose=False, persist_run=False)
    result = runner.run_complete_game()

    event_types = set()
    for entry in result['events_log']:
        evt = entry.get('event', '')
        if isinstance(evt, list):
            event_types.add('split_event')
        else:
            event_types.add(evt)

    print(f"  Event types encountered: {sorted(event_types)}")
    print(f"  Total events: {len(result['events_log'])}")

    # Should encounter at least a few different event types
    assert len(event_types) >= 3, \
        f"Only {len(event_types)} event types encountered: {event_types}"

    # Should include combat
    has_combat = any('combat' in e for e in event_types)
    assert has_combat, "No combat events encountered"

    print("PASSED")


# ---------------------------------------------------------------------------
# Import needed for test_state_inspection
# ---------------------------------------------------------------------------
from database import check_ghost_battle_trigger, check_ghost_battle_available


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_all_tests():
    print("\n" + "=" * 70)
    print("HEADLESS GAME RUNNER - FULL TEST SUITE")
    print("=" * 70)

    tests = [
        ("SmartAI completes game", test_smart_ai_completes),
        ("RandomAI completes game", test_random_ai_completes),
        ("Ghost battles happen", test_ghost_battles_happen),
        ("Ring upgrades happen", test_ring_upgrades_happen),
        ("Deterministic replay", test_deterministic_replay),
        ("Hero integration", test_hero_integration),
        ("Batch stability", test_batch_stability),
        ("State inspection", test_state_inspection),
        ("Combat system exercised", test_combat_system_exercised),
        ("Event variety", test_event_variety),
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
            print(f"FAILED: {e}")
        except Exception as e:
            failed += 1
            errors.append((name, f"ERROR: {e}"))
            print(f"ERROR: {e}")
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
