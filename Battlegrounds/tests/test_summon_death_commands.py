#!/usr/bin/env python3
"""
Combat-command tests for the "stuck dead greyed-out summon" bug.

The suspected bug was: when a summoned minion (e.g. Dryad's Thorn) died, the
frontend saw a DEATH (grey it out) but never saw REMOVE_FROM_BAND, so the
greyed corpse stayed pinned on the combat display forever.

These tests drive real combats end-to-end through `CombatSystem.resolve_combat`
and inspect the interpreter command stream to assert:

  1. Every DEATH has a matching REMOVE_FROM_BAND with the same _combat_id.
  2. REMOVE_FROM_BAND always comes *after* the DEATH for that id.
  3. No later command (damage / buff / attack / trigger) references the id
     once REMOVE_FROM_BAND has fired — the "zombie references" case.
  4. The specific Dryad → Thorn flow: Thorn is summoned, Thorn dies, both
     commands fire for it, and the id formula in combat_registry does not
     collide with any prior live minion.
  5. Summoned minion's _combat_id is set before SUMMON_MINION is emitted,
     so the frontend can find it.

Run:
    cd Battlegrounds && python3 tests/test_summon_death_commands.py
"""

import os
import sys
import traceback
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from game_engine.combat_system import CombatSystem
from minions import get_minion_by_name, create_minion_instance


PASS = []
FAIL = []


# ── helpers ────────────────────────────────────────────────────────────────

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
    """Run a combat and return (result_dict, interpreter_commands)."""
    result = CombatSystem.resolve_combat(
        player_band=player_band,
        enemy_band=enemy_band,
        run=None
    )
    commands = result.get('interpreter_data', {}).get('commands', [])
    return result, commands


def initial_band_ids(commands):
    """Pull _combat_id -> name map from the START command's initial bands."""
    mapping = {}
    for cmd in commands:
        if cmd.get('cmd') == 'START':
            for side in ('player_band', 'enemy_band'):
                for m in cmd.get(side, []):
                    cid = m.get('_combat_id')
                    if cid:
                        mapping[cid] = m.get('name')
            break
    return mapping


def index_by_cid(commands):
    """For each _combat_id reference found anywhere, list (index, cmd_type)."""
    refs = defaultdict(list)
    ID_FIELDS = ('minion_id', 'target_id', 'attacker_id', 'defender_id', 'source_id')
    for i, cmd in enumerate(commands):
        for field in ID_FIELDS:
            cid = cmd.get(field)
            if cid:
                refs[cid].append((i, cmd.get('cmd'), field))
        # SUMMON_MINION nests its minion object
        if cmd.get('cmd') == 'SUMMON_MINION':
            inner = cmd.get('minion') or {}
            cid = inner.get('_combat_id')
            if cid:
                refs[cid].append((i, 'SUMMON_MINION', 'minion._combat_id'))
    return refs


def find_all(commands, cmd_type):
    return [(i, c) for i, c in enumerate(commands) if c.get('cmd') == cmd_type]


# ── tests ──────────────────────────────────────────────────────────────────

def test_every_death_has_matching_remove_from_band():
    """For every DEATH, a REMOVE_FROM_BAND with the same _combat_id must follow."""
    # Huntsman vs a heavy hitter → several deaths will occur
    player = [mk('Huntsman', health=1, attack=1),
              mk('Soldier'),
              mk('Farmer')]
    enemy = [mk('Soldier', attack=20)]

    _, commands = simulate(player, enemy)

    deaths = find_all(commands, 'DEATH')
    removes = find_all(commands, 'REMOVE_FROM_BAND')
    assert deaths, "no DEATH commands emitted — combat didn't produce any kills"

    death_ids = [c.get('minion_id') for _, c in deaths]
    remove_ids = [c.get('minion_id') for _, c in removes]

    for did in death_ids:
        assert did in remove_ids, (
            f"DEATH for {did!r} has NO matching REMOVE_FROM_BAND — "
            f"frontend would leave this minion greyed out forever.\n"
            f"  deaths:  {death_ids}\n  removes: {remove_ids}"
        )


def test_remove_from_band_always_after_death():
    """The frontend plays DEATH visual then REMOVE_FROM_BAND evicts the DOM.
    If REMOVE_FROM_BAND comes first, the DEATH fires on a nonexistent element.
    """
    player = [mk('Soldier', health=1), mk('Farmer', health=1)]
    enemy = [mk('Soldier', attack=15)]
    _, commands = simulate(player, enemy)

    # Build per-id index-lists
    per_id_deaths = defaultdict(list)
    per_id_removes = defaultdict(list)
    for i, c in enumerate(commands):
        if c.get('cmd') == 'DEATH':
            per_id_deaths[c.get('minion_id')].append(i)
        elif c.get('cmd') == 'REMOVE_FROM_BAND':
            per_id_removes[c.get('minion_id')].append(i)

    assert per_id_deaths, "no DEATH commands produced"

    for cid, death_indices in per_id_deaths.items():
        remove_indices = per_id_removes.get(cid, [])
        assert remove_indices, f"id={cid} has DEATH but no REMOVE_FROM_BAND"
        assert min(remove_indices) > min(death_indices), (
            f"id={cid}: REMOVE_FROM_BAND at {remove_indices} is before "
            f"DEATH at {death_indices} — frontend would evict then try to grey."
        )


def test_no_zombie_references_after_remove_from_band():
    """After REMOVE_FROM_BAND for id X, no later command should reference X.
    A zombie reference means the backend kept a stale handle and is still
    computing with a "dead" minion — exactly the class of bug that leaves
    a greyed-out corpse wired up to ongoing triggers.
    """
    player = [mk('Soldier'), mk('Farmer'), mk('Huntsman', health=1)]
    enemy = [mk('Soldier', attack=20), mk('Farmer')]
    _, commands = simulate(player, enemy)

    # Earliest REMOVE_FROM_BAND index per id
    first_remove = {}
    for i, c in enumerate(commands):
        if c.get('cmd') == 'REMOVE_FROM_BAND':
            cid = c.get('minion_id')
            if cid not in first_remove:
                first_remove[cid] = i

    zombie_hits = []
    ID_FIELDS = ('minion_id', 'target_id', 'attacker_id', 'defender_id', 'source_id')
    # Commands that are *expected* to reference a dead minion (death-related or end-of-combat)
    ALLOWED_POST_REMOVE = {
        'DEATH', 'REMOVE_FROM_BAND', 'TRIGGER_DEATH_TOLL', 'TRIGGER_ON_ANY_DEATH',
        'END', 'LOG', 'TRIGGER_ON_ANY_DEATH_TOLL'
    }
    for cid, remove_idx in first_remove.items():
        for j in range(remove_idx + 1, len(commands)):
            cmd = commands[j]
            ctype = cmd.get('cmd')
            if ctype in ALLOWED_POST_REMOVE:
                continue
            for field in ID_FIELDS:
                if cmd.get(field) == cid:
                    zombie_hits.append((cid, remove_idx, j, ctype, field))
                    break

    assert not zombie_hits, (
        "Zombie references to removed minions found — backend kept stale handles:\n"
        + "\n".join(f"  id={cid} removed@{r} but referenced again at {j} "
                    f"by {ct}.{field}" for cid, r, j, ct, field in zombie_hits[:10])
    )


def test_dryad_summons_thorn_with_combat_id():
    """SUMMON_MINION for Thorn must carry a non-empty _combat_id — otherwise
    the frontend can't key the new DOM node and can't match future DEATH/
    REMOVE_FROM_BAND for it.
    """
    dryad = mk('Dryad')
    soldier = mk('Soldier')
    player = [dryad, soldier]
    # Something the Dryad can survive against long enough for cast to fire
    enemy = [mk('Farmer'), mk('Farmer')]
    _, commands = simulate(player, enemy)

    summons = [c for _, c in find_all(commands, 'SUMMON_MINION')
               if (c.get('minion') or {}).get('name') == 'Thorn']
    assert summons, "Dryad never cast its summon — check the combat setup"

    for cmd in summons:
        m = cmd.get('minion') or {}
        cid = m.get('_combat_id')
        assert cid, (
            "SUMMON_MINION for Thorn has no _combat_id on the minion payload — "
            f"frontend addMinionToBand would insert with data-combat-id='' "
            f"and every later command targeting it would miss. Payload: {m}"
        )
        assert cmd.get('band') in ('player', 'enemy'), (
            f"SUMMON_MINION for Thorn has band={cmd.get('band')!r} — "
            f"frontend removeMinionFromBand can't match either branch."
        )


def test_dryad_thorn_dies_cleanly():
    """End-to-end: Dryad summons Thorn, Thorn dies. Assert both DEATH and
    REMOVE_FROM_BAND fire for the Thorn's _combat_id.
    """
    dryad = mk('Dryad')
    player = [dryad]
    # Enemy that out-damages Thorn (2 hp, 0 atk) and Dryad
    enemy = [mk('Soldier', attack=10, health=10), mk('Soldier', attack=10, health=10)]
    _, commands = simulate(player, enemy)

    # Find Thorn's _combat_id from the first SUMMON_MINION that produced it
    thorn_cid = None
    for _, c in find_all(commands, 'SUMMON_MINION'):
        m = c.get('minion') or {}
        if m.get('name') == 'Thorn':
            thorn_cid = m.get('_combat_id')
            break
    assert thorn_cid, "Dryad did not summon a Thorn in this combat"

    death_hit = any(
        c.get('minion_id') == thorn_cid for _, c in find_all(commands, 'DEATH')
    )
    remove_hit = any(
        c.get('minion_id') == thorn_cid for _, c in find_all(commands, 'REMOVE_FROM_BAND')
    )
    assert death_hit, (
        f"Thorn ({thorn_cid}) never received a DEATH command — it would stay "
        f"visible forever on the frontend."
    )
    assert remove_hit, (
        f"Thorn ({thorn_cid}) received DEATH but no REMOVE_FROM_BAND — this is "
        f"the greyed-out-forever bug. Frontend would apply .dead class but never "
        f"evict from frontendCombatState.player_band."
    )


def test_combat_ids_are_unique_across_lifetime():
    """combat_registry.add_summoned_minion builds ids as
    f'{band}_{summoner._combat_id}_{len(player_combat_ids)}'.
    After a death shrinks the list, the next summon could collide with an
    already-retired id, causing ghost DOM nodes to take over.
    """
    # Dryad that casts each round summons Thorns repeatedly.
    # Pair with a slow enemy so we get multiple summons and deaths.
    player = [mk('Dryad'), mk('Dryad')]
    enemy = [mk('Farmer'), mk('Farmer'), mk('Farmer')]
    _, commands = simulate(player, enemy)

    seen_ids = set()
    collisions = []
    for _, c in find_all(commands, 'SUMMON_MINION'):
        cid = (c.get('minion') or {}).get('_combat_id')
        if not cid:
            continue
        if cid in seen_ids:
            collisions.append(cid)
        seen_ids.add(cid)

    # Also gather ids from the START initial state
    starts = initial_band_ids(commands)
    for start_cid in starts:
        if start_cid in seen_ids:
            collisions.append(start_cid)

    assert not collisions, (
        f"_combat_id reused for multiple summons / initial minions: {collisions} — "
        f"frontend would route death/damage commands to the wrong DOM element."
    )


def test_remove_from_band_carries_valid_band():
    """Frontend removeMinionFromBand only filters if band === 'player' or 'enemy'.
    A REMOVE_FROM_BAND with band=None / missing would silently leave the array
    untouched while the DEATH command still greyed the DOM.
    """
    player = [mk('Dryad'), mk('Soldier', health=1)]
    enemy = [mk('Soldier', attack=10)]
    _, commands = simulate(player, enemy)

    bad = [(i, c) for i, c in enumerate(commands)
           if c.get('cmd') == 'REMOVE_FROM_BAND' and c.get('band') not in ('player', 'enemy')]

    assert not bad, (
        "REMOVE_FROM_BAND emitted with missing/invalid band field — frontend "
        "filter would no-op and minion would stay greyed forever:\n"
        + "\n".join(f"  idx={i} cmd={c}" for i, c in bad[:5])
    )


# ── runner ─────────────────────────────────────────────────────────────────

TESTS = [
    test_every_death_has_matching_remove_from_band,
    test_remove_from_band_always_after_death,
    test_no_zombie_references_after_remove_from_band,
    test_dryad_summons_thorn_with_combat_id,
    test_dryad_thorn_dies_cleanly,
    test_combat_ids_are_unique_across_lifetime,
    test_remove_from_band_carries_valid_band,
]


if __name__ == '__main__':
    print(f"\nRunning {len(TESTS)} summon / death command-stream tests...\n")
    for t in TESTS:
        run_test(t)
    print(f"\n{'='*60}")
    print(f"  Passed: {len(PASS)} / {len(TESTS)}")
    if FAIL:
        print(f"  Failed ({len(FAIL)}):")
        for name, why in FAIL:
            print(f"    - {name}: {why}")
    print('='*60)
    sys.exit(0 if not FAIL else 1)
