#!/usr/bin/env python3
"""
Meat Packaging Plant repro test.

Bug: MPP's cast summons 2 Meat Cubes on the backend (both end up in the band),
but the interpreter only emits ONE SUMMON_MINION command — keyed to
`changes.summoned_minions.0` — so the frontend only ever animates in one cube.

This test drives a real combat with an MPP + a sacrificial ally and asserts:

  1. MPP's cast actually fires (condition met, left-ally destroyed).
  2. Two Meat Cubes end up alive in the player band after the cast.
  3. The interpreter stream contains TWO SUMMON_MINION commands for Meat Cube.
  4. Each SUMMON_MINION command has its own distinct _combat_id.

Run:
    cd Battlegrounds && python3 tests/test_meat_packing_plant.py
"""

import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from game_engine.combat_system import CombatSystem
from minions import get_minion_by_name, create_minion_instance


PASS = []
FAIL = []


def run_test(fn):
    name = fn.__name__
    try:
        fn()
        PASS.append(name)
        print(f"  PASS  {name}")
    except AssertionError as e:
        FAIL.append((name, str(e)))
        print(f"  FAIL  {name}: {e}")
    except Exception as e:
        FAIL.append((name, f"ERROR: {e}"))
        print(f"  FAIL  {name}: ERROR")
        traceback.print_exc()


def mk(name, *, health=None, attack=None, tier=1):
    m = create_minion_instance(get_minion_by_name(name), tier=tier, assign_band_id=False)
    if health is not None:
        m['health'] = health
    if attack is not None:
        m['attack'] = attack
    return m


def simulate(player_band, enemy_band):
    result = CombatSystem.resolve_combat(
        player_band=player_band,
        enemy_band=enemy_band,
        run=None
    )
    commands = result.get('interpreter_data', {}).get('commands', [])
    return result, commands


def build_mpp_band():
    """
    MPP at position 1, sacrificial ally at position 0 (to its left).
    Also add a small attacker so combat has something to do besides MPP's cast.
    """
    sacrifice = mk('Dryad', health=10, attack=4)
    mpp = mk('Meat Packaging Plant')
    tank = mk('Iron Wall', health=20, attack=2)
    return [sacrifice, mpp, tank]


# ── tests ──────────────────────────────────────────────────────────────────

def _count_mpp_casts(commands):
    """Count how many times MPP's cast trigger fired in the command stream."""
    return sum(
        1 for c in commands
        if c.get('cmd', '').startswith('DESTROY_MINION')
        and 'Meat Packaging Plant' in (c.get('log_message') or '')
    )


def test_mpp_summons_two_meat_cubes_per_cast():
    """
    The bug: MPP's cast summons 2 Meat Cubes on the backend, but the interpreter
    only emits ONE SUMMON_MINION command per cast (field_map only references
    summoned_minions.0), so the frontend sees one cube instead of two.

    Expect: for each MPP cast (destroy of Thorn), TWO Meat Cube SUMMON_MINION
    commands follow.
    """
    player = build_mpp_band()
    enemy = [mk('Iron Wall', health=30, attack=1)]
    _, commands = simulate(player, enemy)

    cast_count = _count_mpp_casts(commands)
    assert cast_count >= 1, f"MPP never cast — can't test. commands={len(commands)}"

    cube_cmds = [
        c for c in commands
        if c.get('cmd') == 'SUMMON_MINION'
        and (c.get('minion') or {}).get('name') == 'Meat Cube'
    ]

    expected = cast_count * 2
    assert len(cube_cmds) == expected, (
        f"Expected {expected} Meat Cube SUMMON_MINION commands "
        f"({cast_count} casts × 2 cubes), got {len(cube_cmds)}"
    )


def test_each_meat_cube_has_distinct_combat_id():
    """Every cube SUMMON command must carry a distinct _combat_id."""
    player = build_mpp_band()
    enemy = [mk('Iron Wall', health=30, attack=1)]
    _, commands = simulate(player, enemy)

    cube_ids = []
    for c in commands:
        if c.get('cmd') != 'SUMMON_MINION':
            continue
        m = c.get('minion') or {}
        if m.get('name') != 'Meat Cube':
            continue
        cid = m.get('_combat_id')
        assert cid, f"Meat Cube SUMMON_MINION has no _combat_id: {c}"
        cube_ids.append(cid)

    assert len(cube_ids) == len(set(cube_ids)), (
        f"Duplicate _combat_ids in cube SUMMON commands: {cube_ids}"
    )


def test_paired_cubes_adjacent_in_stream():
    """
    Both cubes from one cast should be emitted back-to-back in the stream, so
    the frontend renders them as a pair. Allow the batch's internal ordering
    but forbid unrelated commands from splitting the pair.
    """
    player = build_mpp_band()
    enemy = [mk('Iron Wall', health=30, attack=1)]
    _, commands = simulate(player, enemy)

    # Find indices of every Meat Cube SUMMON_MINION command
    cube_indices = [
        i for i, c in enumerate(commands)
        if c.get('cmd') == 'SUMMON_MINION'
        and (c.get('minion') or {}).get('name') == 'Meat Cube'
    ]

    assert len(cube_indices) >= 2, "Need at least 2 cube commands to test pairing"

    # Indices should come in adjacent pairs (i, i+1)
    for j in range(0, len(cube_indices), 2):
        a = cube_indices[j]
        b = cube_indices[j + 1] if j + 1 < len(cube_indices) else None
        assert b is not None, f"Odd number of cube commands — missing pair partner"
        assert b == a + 1, (
            f"Cube pair not adjacent in stream: indices {a} and {b}, "
            f"intervening cmd = {commands[a+1].get('cmd')}"
        )


# ── runner ─────────────────────────────────────────────────────────────────

TESTS = [
    test_mpp_summons_two_meat_cubes_per_cast,
    test_each_meat_cube_has_distinct_combat_id,
    test_paired_cubes_adjacent_in_stream,
]


def main():
    print("Running Meat Packaging Plant repro tests...\n")
    for t in TESTS:
        run_test(t)

    print("\n" + "=" * 60)
    print(f"Passed: {len(PASS)} / {len(TESTS)}")
    if FAIL:
        print(f"Failed: {len(FAIL)}")
        for name, err in FAIL:
            print(f"  - {name}: {err}")
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
