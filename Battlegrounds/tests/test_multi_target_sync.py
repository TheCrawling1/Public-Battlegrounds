#!/usr/bin/env python3
"""
Multi-target effect sync tests.

Same bug pattern as Meat Packaging Plant: effect affects >1 entity on the
backend, but the interpreter field_map reads `changes.targets.0.*`, so only
the first entity makes it into a command. Frontend desyncs.

Covered here:
  - Wight: `deal_damage` with target_count=2 → TWO DEAL_DAMAGE commands,
    each carrying per-target (not aggregate) damage.
  - Brownie: `buff_stats` on `all_allies` → one BUFF_STATS command per ally.
  - Registry sync_check metadata is present where expected.

Run:
    cd Battlegrounds && python3 tests/test_multi_target_sync.py
"""

import io
import os
import sys
import contextlib
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from game_engine.combat_system import CombatSystem
from game_engine.triggers.effect_registry import EFFECT_REGISTRY
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
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = CombatSystem.resolve_combat(
            player_band=player_band,
            enemy_band=enemy_band,
            run=None
        )
    commands = result.get('interpreter_data', {}).get('commands', [])
    return result, commands, buf.getvalue()


def collect_batches(commands, cmd_type, log_contains):
    """Group consecutive cmd_type commands into batches. A batch starts when
    a command has a non-empty log_message containing log_contains, and
    extends through subsequent commands of the same cmd_type whose log is
    empty (those are the 2..N emissions of the same ability firing).
    Returns list of batches, each a list of commands."""
    batches = []
    current = None
    for c in commands:
        if c.get('cmd') != cmd_type:
            # Non-matching command ends any open batch
            if current is not None:
                batches.append(current)
                current = None
            continue
        log = c.get('log_message') or ''
        if log_contains in log:
            # New batch
            if current is not None:
                batches.append(current)
            current = [c]
        elif current is not None and not log:
            # Continuation of current batch
            current.append(c)
        else:
            # Different source's command — end current batch
            if current is not None:
                batches.append(current)
                current = None
    if current is not None:
        batches.append(current)
    return batches


# ── Wight: deal_damage with target_count=2 ──────────────────────────────────

def test_wight_emits_two_damage_commands():
    """Wight assaults 2 random enemies for 3 damage. Each should get its own
    DEAL_DAMAGE command — not a single aggregated command attributed to one."""
    # Two fat enemies so neither dies on the first hit (keeps the test focused
    # on the SUMMON/DAMAGE emission, not downstream destroy commands).
    player = [mk('Wight', health=20, attack=1)]
    enemy = [mk('Iron Wall', health=30, attack=1),
             mk('Iron Wall', health=30, attack=1)]
    _, commands, _ = simulate(player, enemy)

    wight_damage = [
        c for c in commands
        if c.get('cmd') == 'DEAL_DAMAGE'
        and (c.get('source_name') == 'Wight' or 'Wight' in (c.get('log_message') or ''))
    ]

    assert len(wight_damage) >= 2, (
        f"Expected at least 2 DEAL_DAMAGE commands from Wight's first assault, "
        f"got {len(wight_damage)}. Commands: {[c.get('cmd') for c in commands[:20]]}"
    )


def test_wight_per_command_damage_is_three_not_six():
    """Aggregate `damage_dealt` is amount * len(targets) on the backend.
    Each per-target command must carry 3, not 6 (the sum)."""
    player = [mk('Wight', health=20, attack=1)]
    enemy = [mk('Iron Wall', health=30, attack=1),
             mk('Iron Wall', health=30, attack=1)]
    _, commands, _ = simulate(player, enemy)

    wight_damage = [
        c for c in commands
        if c.get('cmd') == 'DEAL_DAMAGE'
        and (c.get('source_name') == 'Wight' or 'Wight' in (c.get('log_message') or ''))
    ]
    assert wight_damage, "no Wight damage commands — can't check per-target amount"

    # The first two commands should each carry amount=3 (per-target), not 6 (aggregate)
    for c in wight_damage[:2]:
        amt = c.get('amount')
        assert amt == 3, (
            f"Wight DEAL_DAMAGE should carry per-target amount=3, got {amt}. "
            f"cmd={c}"
        )


def test_wight_damage_hits_both_enemies_over_combat():
    """Over a full combat, Wight's damage should reach both enemies (not the
    same one over and over). This ensures per-command target_ids track the
    actual hit and aren't stuck on a single id."""
    player = [mk('Wight', health=20, attack=1)]
    enemy = [mk('Iron Wall', health=30, attack=1),
             mk('Iron Wall', health=30, attack=1)]
    _, commands, _ = simulate(player, enemy)

    wight_damage_ids = {
        c.get('target_id') for c in commands
        if c.get('cmd') == 'DEAL_DAMAGE'
        and c.get('source_name') == 'Wight'
        and c.get('target_id')
    }
    assert len(wight_damage_ids) >= 2, (
        f"Wight damage only reached {len(wight_damage_ids)} unique enemy id(s); "
        f"expected at least 2 across combat. Ids: {wight_damage_ids}"
    )


# ── Brownie: buff_stats on all_allies ───────────────────────────────────────

def test_brownie_emits_one_buff_per_ally():
    """Brownie's cast buffs all allies +2/0. Expect one BUFF_STATS command
    per living ally in the band (not one command for the whole board)."""
    allies = [
        mk('Iron Wall', health=10, attack=1),
        mk('Iron Wall', health=10, attack=1),
        mk('Iron Wall', health=10, attack=1),
        mk('Brownie'),
    ]
    enemy = [mk('Iron Wall', health=40, attack=1)]
    _, commands, _ = simulate(allies, enemy)

    batches = collect_batches(commands, 'BUFF_STATS', 'Brownie')
    assert batches, "Brownie never fired a buff"
    # First batch is the initial cast: should cover all 4 allies
    first = batches[0]
    assert len(first) == 4, (
        f"Brownie's first cast should emit 4 BUFF_STATS (one per ally), got {len(first)}. "
        f"Batch logs: {[c.get('log_message') for c in first]}"
    )


def test_brownie_buffs_have_distinct_target_ids():
    """Within one Brownie cast, every buff command targets a different ally."""
    allies = [
        mk('Iron Wall', health=10, attack=1),
        mk('Iron Wall', health=10, attack=1),
        mk('Iron Wall', health=10, attack=1),
        mk('Brownie'),
    ]
    enemy = [mk('Iron Wall', health=40, attack=1)]
    _, commands, _ = simulate(allies, enemy)

    batches = collect_batches(commands, 'BUFF_STATS', 'Brownie')
    assert batches
    for b in batches:
        ids = [c.get('target_id') for c in b]
        assert len(set(ids)) == len(ids), (
            f"Brownie buff batch has duplicate target_ids: {ids}"
        )


# ── Registry metadata ───────────────────────────────────────────────────────

def test_registry_declares_sync_check_for_multi_target_effects():
    """The known-vulnerable effects must carry sync_check metadata so the
    generic processor knows to batch-emit."""
    must_have = {
        'summon_minion': 'summoned_minions',
        'deal_damage': 'targets',
        'buff_stats': 'targets',
        'buff_stats_tribe': 'targets',
        'heal': 'targets',
    }
    for effect_type, expected_key in must_have.items():
        entry = EFFECT_REGISTRY.get(effect_type, {})
        sync = entry.get('interpreter', {}).get('sync_check')
        assert sync, f"{effect_type} missing sync_check in registry"
        assert sync.get('multi_entity_key') == expected_key, (
            f"{effect_type} sync_check should declare multi_entity_key={expected_key!r}, "
            f"got {sync.get('multi_entity_key')!r}"
        )


def test_deal_damage_declares_aggregate_override():
    """deal_damage aggregates damage_dealt = amount * N. The registry must
    declare the per-emit override so per-target commands show correct damage."""
    sync = EFFECT_REGISTRY['deal_damage']['interpreter']['sync_check']
    overrides = sync.get('per_emit_from_effect_data') or {}
    assert overrides.get('damage_dealt') == 'amount', (
        f"deal_damage needs per_emit override for damage_dealt → amount, "
        f"got {overrides}"
    )


# ── Sync-warning flag ────────────────────────────────────────────────────────

def test_sync_warning_flag_does_not_fire_in_clean_run():
    """No [SYNC WARNING] lines should appear in a clean Wight/Brownie combat.
    This is the inverse of the bug: after the fix, the flag must stay quiet."""
    player = [mk('Wight', health=20, attack=1), mk('Brownie')]
    enemy = [mk('Iron Wall', health=30, attack=1),
             mk('Iron Wall', health=30, attack=1)]
    _, _, stdout = simulate(player, enemy)
    assert '[SYNC WARNING]' not in stdout, (
        f"sync warning fired despite fix being in place:\n"
        f"{[ln for ln in stdout.splitlines() if 'SYNC WARNING' in ln]}"
    )


# ── runner ──────────────────────────────────────────────────────────────────

TESTS = [
    test_wight_emits_two_damage_commands,
    test_wight_per_command_damage_is_three_not_six,
    test_wight_damage_hits_both_enemies_over_combat,
    test_brownie_emits_one_buff_per_ally,
    test_brownie_buffs_have_distinct_target_ids,
    test_registry_declares_sync_check_for_multi_target_effects,
    test_deal_damage_declares_aggregate_override,
    test_sync_warning_flag_does_not_fire_in_clean_run,
]


def main():
    print("Running multi-target effect sync tests...\n")
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
