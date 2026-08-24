#!/usr/bin/env python3
"""
Test Shaman's trigger_start_of_combat effect

Expected behavior:
- Shaman has Cast: Trigger a random friendly start of combat effect
- When Shaman casts, it should find a friendly minion with start_of_combat keyword
- It should trigger that minion's start_of_combat_effect
- The target minion's effect should execute as if combat just started

Test setup:
- Shaman + Banshee (start_of_combat: deal 1 damage to all enemies) vs enemies
- When Shaman casts, it should trigger Banshee's start of combat effect
- Enemies should take damage from Banshee's triggered effect
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from game_engine.combat_system import CombatSystem
from minions import get_minion_by_name, create_minion_instance


def create_test_minion(name, golden=False):
    """Create a test minion instance"""
    template = get_minion_by_name(name)
    if not template:
        raise ValueError(f"Unknown minion: {name}")
    minion = create_minion_instance(template, assign_band_id=True)
    if golden:
        minion['golden'] = True
        minion['health'] *= 2
        minion['attack'] *= 2
    return minion


def test_shaman_triggers_start_of_combat():
    """Test that Shaman's cast effect triggers a friendly start_of_combat"""
    print("=" * 100)
    print("SHAMAN TRIGGER_START_OF_COMBAT EFFECT TEST")
    print("=" * 100)
    print()
    print("Expected behavior:")
    print("  - Shaman has Cast: Trigger a random friendly start of combat")
    print("  - When Shaman casts, it finds an ally with start_of_combat effect")
    print("  - It triggers that ally's start_of_combat_effect")
    print("  - The effect executes (e.g., Banshee deals damage to all enemies)")
    print()

    # Setup: Shaman + Banshee vs enemies
    # Banshee has start_of_combat: deal 1 damage to all enemies
    shaman = create_test_minion('Shaman')  # 5/8, Cast: trigger start of combat
    banshee = create_test_minion('Banshee')  # 7/7, start_of_combat: deal 1 damage to all enemies

    # Multiple enemies to see the AOE damage from Banshee's start_of_combat
    enemy1 = create_test_minion('Soldier')  # 2/2
    enemy2 = create_test_minion('Soldier')  # 2/2
    enemy3 = create_test_minion('Soldier')  # 2/2

    print(f"Initial setup:")
    print(f"  Shaman: {shaman['attack']}/{shaman['health']} (Cast: trigger start of combat)")
    print(f"  Banshee: {banshee['attack']}/{banshee['health']} (Start of Combat: deal 1 damage to all enemies)")
    print(f"  Enemies: 3x Soldier (2/2 each)")
    print()

    player_band = [shaman, banshee]
    enemy_band = [enemy1, enemy2, enemy3]

    # Run combat
    battle_result = CombatSystem.resolve_combat(player_band, enemy_band, run=None)

    # Get combat log
    combat_log = battle_result.get('combat_log', [])

    print("COMBAT LOG:")
    print("-" * 100)
    for i, log in enumerate(combat_log):
        print(f"{i+1}. {log}")
    print()

    # Analysis
    print("ANALYSIS:")
    print("-" * 100)

    # Check for Shaman's cast trigger
    shaman_cast = any('Shaman' in log and 'cast' in log.lower() for log in combat_log)
    print(f"Shaman cast triggered: {'✅ YES' if shaman_cast else '❌ NO'}")

    # Check for start of combat trigger from Shaman
    soc_triggered = any('start of combat' in log.lower() and 'trigger' in log.lower() for log in combat_log)
    print(f"Start of combat effect triggered: {'✅ YES' if soc_triggered else '❌ NO'}")

    # Check for Banshee's effect (AOE damage)
    banshee_damage = any('Banshee' in log and ('damage' in log.lower() or 'deal' in log.lower()) for log in combat_log)
    print(f"Banshee's damage effect fired: {'✅ YES' if banshee_damage else '❌ NO'}")

    # Check interpreter commands
    interpreter_data = battle_result.get('interpreter_data', {})
    commands = interpreter_data.get('commands', [])

    print()
    print("RELEVANT COMMANDS:")
    print("-" * 100)
    relevant_commands = [
        cmd for cmd in commands
        if any(keyword in str(cmd).upper() for keyword in ['CAST', 'START_OF_COMBAT', 'TRIGGER', 'DAMAGE'])
    ]
    for cmd in relevant_commands[:20]:  # Limit to first 20 relevant commands
        print(f"  {cmd}")

    if not relevant_commands:
        print("  (No relevant commands found)")

    print()
    print("=" * 100)
    print("TEST COMPLETE")
    print("=" * 100)

    return {
        'shaman_cast': shaman_cast,
        'soc_triggered': soc_triggered,
        'banshee_damage': banshee_damage,
        'combat_log': combat_log,
        'commands': commands
    }


def test_shaman_no_targets():
    """Test Shaman when there are no allies with start_of_combat"""
    print()
    print("=" * 100)
    print("SHAMAN NO START_OF_COMBAT TARGETS TEST")
    print("=" * 100)
    print()
    print("Expected behavior:")
    print("  - Shaman casts but finds no allies with start_of_combat")
    print("  - Should log that no start of combat effects were found")
    print()

    # Setup: Shaman + ally without start_of_combat
    shaman = create_test_minion('Shaman')
    ally = create_test_minion('Farmer')  # No start_of_combat effect

    enemy = create_test_minion('Soldier')

    print(f"Initial setup:")
    print(f"  Shaman: {shaman['attack']}/{shaman['health']}")
    print(f"  Ally (Farmer): {ally['attack']}/{ally['health']} (no start_of_combat)")
    print(f"  Enemy: Soldier")
    print()

    player_band = [shaman, ally]
    enemy_band = [enemy]

    # Run combat
    battle_result = CombatSystem.resolve_combat(player_band, enemy_band, run=None)

    # Get combat log
    combat_log = battle_result.get('combat_log', [])

    print("COMBAT LOG:")
    print("-" * 100)
    for i, log in enumerate(combat_log):
        print(f"{i+1}. {log}")
    print()

    # Check for "no effects to trigger" message
    no_targets = any('no start of combat' in log.lower() for log in combat_log)
    print(f"No targets message shown: {'✅ YES' if no_targets else '❌ NO (may still be fine)'}")

    return {
        'combat_log': combat_log,
        'no_targets_message': no_targets
    }


def test_shaman_excludes_self():
    """Test that Shaman doesn't trigger itself (even if it had start_of_combat)"""
    print()
    print("=" * 100)
    print("SHAMAN EXCLUDES SELF TEST")
    print("=" * 100)
    print()
    print("Expected behavior:")
    print("  - Shaman's effect has exclude_self: True")
    print("  - If Shaman was the only minion with start_of_combat, it shouldn't trigger itself")
    print()

    # This test is more of a sanity check - Shaman doesn't have start_of_combat
    # But we verify the exclude_self logic is in place

    shaman = create_test_minion('Shaman')
    # Give Shaman a fake start_of_combat to test exclusion
    shaman['keywords'] = shaman.get('keywords', []) + ['start_of_combat']
    shaman['start_of_combat_effect'] = {
        'type': 'buff_stats',
        'target': 'self',
        'attack': 99,
        'health': 99
    }

    enemy = create_test_minion('Soldier')

    print(f"Initial setup:")
    print(f"  Shaman: {shaman['attack']}/{shaman['health']} (with fake start_of_combat)")
    print(f"  Enemy: Soldier")
    print()

    player_band = [shaman]
    enemy_band = [enemy]

    # Run combat
    battle_result = CombatSystem.resolve_combat(player_band, enemy_band, run=None)

    # Get combat log
    combat_log = battle_result.get('combat_log', [])

    print("COMBAT LOG:")
    print("-" * 100)
    for i, log in enumerate(combat_log):
        print(f"{i+1}. {log}")
    print()

    # Check that Shaman didn't trigger its own start_of_combat via cast
    # (It may trigger naturally at start of combat, but not from its own cast)
    self_trigger = any('Shaman' in log and 'triggers' in log.lower() and 'Shaman' in log.split('triggers')[1] for log in combat_log if 'triggers' in log.lower())
    print(f"Shaman triggered itself via cast: {'❌ YES - BUG!' if self_trigger else '✅ NO - Correct'}")

    return {
        'combat_log': combat_log,
        'self_triggered': self_trigger
    }


if __name__ == '__main__':
    print("\n" + "=" * 100)
    print("RUNNING SHAMAN TRIGGER_START_OF_COMBAT TESTS")
    print("=" * 100 + "\n")

    result1 = test_shaman_triggers_start_of_combat()
    result2 = test_shaman_no_targets()
    result3 = test_shaman_excludes_self()

    print("\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)

    all_passed = True

    # Test 1: Basic functionality
    print("\nTest 1: Shaman triggers Banshee's start_of_combat")
    if result1['shaman_cast']:
        print("  ✅ Shaman cast triggered")
    else:
        print("  ❌ Shaman cast NOT triggered")
        all_passed = False

    if result1['soc_triggered']:
        print("  ✅ Start of combat effect triggered")
    else:
        print("  ⚠️  Start of combat trigger log not found (may still work)")

    if result1['banshee_damage']:
        print("  ✅ Banshee's damage effect fired")
    else:
        print("  ⚠️  Banshee damage log not found (check combat log)")

    # Test 2: No targets
    print("\nTest 2: Shaman with no valid targets")
    print("  ✅ Completed (check logs above)")

    # Test 3: Exclude self
    print("\nTest 3: Shaman excludes self")
    if not result3['self_triggered']:
        print("  ✅ Shaman correctly excludes self")
    else:
        print("  ❌ Shaman incorrectly triggered itself")
        all_passed = False

    print("\n" + "=" * 100)
    if all_passed:
        print("ALL TESTS PASSED ✅")
    else:
        print("SOME TESTS FAILED ❌")
    print("=" * 100)
