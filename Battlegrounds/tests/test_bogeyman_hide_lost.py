#!/usr/bin/env python3
"""
Test Bogeyman's on_hide_lost effect - verify it stuns all other minions (except self)

Expected behavior:
- Bogeyman has Hide 2 (can't be attacked for 2 attacks)
- When Bogeyman's hide is lost, it triggers on_hide_lost_effect
- Effect: Stun all minions (except self) for 2 turns
- This should affect BOTH friendly and enemy minions
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


def test_bogeyman_hide_lost():
    """Test that Bogeyman's on_hide_lost stuns all other minions"""
    print("=" * 100)
    print("BOGEYMAN ON_HIDE_LOST EFFECT TEST")
    print("=" * 100)
    print()
    print("Expected behavior:")
    print("  - Bogeyman has Hide 2 (takes 2 attacks to reveal)")
    print("  - When hide is lost, ALL other minions get Stun 2")
    print("  - Bogeyman itself should NOT be stunned")
    print("  - Both friendly AND enemy minions should be stunned")
    print()

    # Setup: Bogeyman + ally vs multiple enemies
    # Using minions that won't die quickly to see the stun effect
    bogeyman = create_test_minion('Bogeyman')  # 8/8, Hide 2, on_hide_lost
    ally = create_test_minion('Farmer')  # 3/1 simple ally to check if it gets stunned

    # Enemies - need multiple to trigger the hide countdown
    enemy1 = create_test_minion('Soldier')  # 2/2
    enemy2 = create_test_minion('Soldier')  # 2/2
    enemy3 = create_test_minion('Soldier')  # 2/2

    print(f"Initial stats:")
    print(f"  Bogeyman: {bogeyman['attack']}/{bogeyman['health']} (Hide {bogeyman.get('hide_count', 'N/A')})")
    print(f"  Ally (Farmer): {ally['attack']}/{ally['health']}")
    print(f"  Enemy1: {enemy1['attack']}/{enemy1['health']}")
    print(f"  Enemy2: {enemy2['attack']}/{enemy2['health']}")
    print(f"  Enemy3: {enemy3['attack']}/{enemy3['health']}")
    print()

    player_band = [bogeyman, ally]
    enemy_band = [enemy1, enemy2, enemy3]

    # Run combat
    battle_result = CombatSystem.resolve_combat(player_band, enemy_band, run=None)

    # Get combat log
    combat_log = battle_result.get('combat_log', [])

    print(f"COMBAT LOG:")
    print("-" * 100)
    for i, log in enumerate(combat_log):
        print(f"{i+1}. {log}")
    print()

    # Analysis
    print("ANALYSIS:")
    print("-" * 100)

    # Check for hide lost trigger
    hide_lost_triggered = any('hide' in log.lower() and 'lost' in log.lower() for log in combat_log)
    print(f"Hide lost trigger fired: {'✅ YES' if hide_lost_triggered else '❌ NO'}")

    # Check for stun application
    stun_applied = any('stun' in log.lower() for log in combat_log)
    print(f"Stun effect applied: {'✅ YES' if stun_applied else '❌ NO'}")

    # Check that Bogeyman itself is NOT stunned (by looking at commands or state)
    bogeyman_stunned = any('Bogeyman' in log and 'stunned' in log.lower() for log in combat_log)
    print(f"Bogeyman stunned (should be NO): {'❌ YES - BUG!' if bogeyman_stunned else '✅ NO - Correct'}")

    # Check interpreter commands for stun applications
    interpreter_data = battle_result.get('interpreter_data', {})
    commands = interpreter_data.get('commands', [])

    print()
    print("STUN-RELATED COMMANDS:")
    print("-" * 100)
    stun_commands = [cmd for cmd in commands if 'STUN' in str(cmd).upper() or 'stun' in str(cmd)]
    for cmd in stun_commands:
        print(f"  {cmd}")

    if not stun_commands:
        print("  (No stun commands found)")

    print()
    print("=" * 100)
    print("TEST COMPLETE")
    print("=" * 100)

    return {
        'hide_lost_triggered': hide_lost_triggered,
        'stun_applied': stun_applied,
        'bogeyman_stunned': bogeyman_stunned,
        'combat_log': combat_log,
        'commands': commands
    }


def test_bogeyman_hide_countdown():
    """Test that Bogeyman's hide countdown works correctly"""
    print()
    print("=" * 100)
    print("BOGEYMAN HIDE COUNTDOWN TEST")
    print("=" * 100)
    print()
    print("Expected behavior:")
    print("  - Bogeyman starts with Hide 2")
    print("  - Each enemy attack that would target Bogeyman reduces hide by 1")
    print("  - After 2 attacks, hide is lost and on_hide_lost triggers")
    print()

    # Setup: Just Bogeyman vs one enemy to track hide countdown
    bogeyman = create_test_minion('Bogeyman')
    enemy = create_test_minion('War Horse')  # 7/7 - will survive to attack multiple times

    print(f"Initial stats:")
    print(f"  Bogeyman: {bogeyman['attack']}/{bogeyman['health']} (Hide {bogeyman.get('hide_count', 'N/A')})")
    print(f"  Enemy (War Horse): {enemy['attack']}/{enemy['health']}")
    print()

    player_band = [bogeyman]
    enemy_band = [enemy]

    # Run combat
    battle_result = CombatSystem.resolve_combat(player_band, enemy_band, run=None)

    # Get combat log
    combat_log = battle_result.get('combat_log', [])

    print(f"COMBAT LOG:")
    print("-" * 100)
    for i, log in enumerate(combat_log):
        print(f"{i+1}. {log}")
    print()

    return {
        'combat_log': combat_log
    }


if __name__ == '__main__':
    print("\n" + "=" * 100)
    print("RUNNING BOGEYMAN TESTS")
    print("=" * 100 + "\n")

    result1 = test_bogeyman_hide_lost()
    result2 = test_bogeyman_hide_countdown()

    print("\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)
    print(f"Hide lost triggered: {'✅' if result1['hide_lost_triggered'] else '❌'}")
    print(f"Stun applied: {'✅' if result1['stun_applied'] else '❌'}")
    print(f"Bogeyman NOT stunned: {'✅' if not result1['bogeyman_stunned'] else '❌'}")
