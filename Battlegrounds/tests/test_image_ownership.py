#!/usr/bin/env python3
"""
Test image ownership system - Player model methods and logic

Tests:
1. Player model methods for owned/equipped images (JSON serialization)
2. Ownership validation logic
3. Scalability considerations (minimal storage for defaults)
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import json


class MockPlayer:
    """
    Mock Player class that tests the same logic as the real Player model
    without requiring Flask/SQLAlchemy. This validates the algorithms work correctly.
    """

    def __init__(self, username='test'):
        self.username = username
        self.owned_images = '{}'
        self.equipped_images = '{}'

    def get_owned_images(self):
        """Return owned image variants as dict of minion_id -> set of variant names.
        Note: 'original' is always owned by everyone, so it's not stored."""
        if self.owned_images:
            try:
                data = json.loads(self.owned_images)
                # Convert lists to sets for efficient lookup
                return {k: set(v) for k, v in data.items()}
            except:
                return {}
        return {}

    def set_owned_images(self, owned_dict):
        """Store owned image variants. Only store non-original variants."""
        # Filter out empty lists and 'original' variant
        filtered = {}
        for minion_id, variants in owned_dict.items():
            # Remove 'original' if present (it's always owned)
            clean_variants = [v for v in variants if v != 'original']
            if clean_variants:
                filtered[minion_id] = clean_variants
        self.owned_images = json.dumps(filtered)

    def add_owned_image(self, minion_id, variant):
        """Add a specific image variant to owned collection."""
        if variant == 'original':
            return  # Original is always owned, don't store
        owned = self.get_owned_images()
        if minion_id not in owned:
            owned[minion_id] = set()
        owned[minion_id].add(variant)
        self.set_owned_images({k: list(v) for k, v in owned.items()})

    def get_equipped_images(self):
        """Return equipped image variants as dict of minion_id -> variant name.
        Note: Only stores non-original equipped variants."""
        if self.equipped_images:
            try:
                return json.loads(self.equipped_images)
            except:
                return {}
        return {}

    def set_equipped_images(self, equipped_dict):
        """Store equipped image variants. Only store non-original selections."""
        # Filter out 'original' selections (that's the default)
        filtered = {k: v for k, v in equipped_dict.items() if v != 'original'}
        self.equipped_images = json.dumps(filtered)

    def set_equipped_image(self, minion_id, variant):
        """Set the equipped image variant for a specific minion."""
        equipped = self.get_equipped_images()
        if variant == 'original':
            # Remove from dict (default to original)
            equipped.pop(minion_id, None)
        else:
            equipped[minion_id] = variant
        self.set_equipped_images(equipped)

    def get_minion_image_path(self, minion_id, default_image):
        """Get the equipped image path for a minion, or default if not customized."""
        equipped = self.get_equipped_images()
        variant = equipped.get(minion_id, 'original')
        # Return path based on variant
        return f'images/{variant}/{default_image}'


def test_default_owned_images_empty():
    """New player should have empty owned_images (original always owned by default)"""
    player = MockPlayer()
    owned = player.get_owned_images()
    assert owned == {}, f"Expected empty dict, got {owned}"
    print("✅ New player has empty owned_images dict")


def test_default_equipped_images_empty():
    """New player should have empty equipped_images (defaults to original)"""
    player = MockPlayer()
    equipped = player.get_equipped_images()
    assert equipped == {}, f"Expected empty dict, got {equipped}"
    print("✅ New player has empty equipped_images dict")


def test_add_owned_image_variant():
    """Adding an alt variant should store it"""
    player = MockPlayer()
    player.add_owned_image('goblin_warrior', 'alt_1')

    owned = player.get_owned_images()
    assert 'goblin_warrior' in owned, "goblin_warrior should be in owned"
    assert 'alt_1' in owned['goblin_warrior'], "alt_1 should be in goblin_warrior's variants"
    print("✅ Successfully added alt_1 variant to owned images")


def test_add_owned_original_ignored():
    """Adding 'original' variant should be ignored (always owned)"""
    player = MockPlayer()
    player.add_owned_image('goblin_warrior', 'original')

    owned = player.get_owned_images()
    # Should be empty because original is never stored
    assert owned == {}, f"Expected empty dict, got {owned}"
    print("✅ Adding 'original' variant is correctly ignored")


def test_set_equipped_image_alt():
    """Setting equipped to alt variant should store it"""
    player = MockPlayer()
    player.set_equipped_image('goblin_warrior', 'alt_1')

    equipped = player.get_equipped_images()
    assert equipped.get('goblin_warrior') == 'alt_1', f"Expected alt_1, got {equipped.get('goblin_warrior')}"
    print("✅ Successfully set equipped image to alt_1")


def test_set_equipped_image_original_removes():
    """Setting equipped to original should remove from dict"""
    player = MockPlayer()
    # First set to alt
    player.set_equipped_image('goblin_warrior', 'alt_1')
    # Then set back to original
    player.set_equipped_image('goblin_warrior', 'original')

    equipped = player.get_equipped_images()
    assert 'goblin_warrior' not in equipped, f"goblin_warrior should not be in equipped after setting to original"
    print("✅ Setting to 'original' correctly removes from equipped dict")


def test_multiple_minions_owned():
    """Multiple minions can have different owned variants"""
    player = MockPlayer()
    player.add_owned_image('goblin_warrior', 'alt_1')
    player.add_owned_image('goblin_warrior', 'alt_2')
    player.add_owned_image('soldier', 'alt_1')

    owned = player.get_owned_images()
    assert 'alt_1' in owned['goblin_warrior'], "alt_1 should be in goblin_warrior"
    assert 'alt_2' in owned['goblin_warrior'], "alt_2 should be in goblin_warrior"
    assert 'alt_1' in owned['soldier'], "alt_1 should be in soldier"
    print("✅ Multiple minions can have different owned variants")


def test_get_minion_image_path_default():
    """Default image path should use original variant"""
    player = MockPlayer()
    path = player.get_minion_image_path('goblin_warrior', 'goblin_warrior.png')
    assert path == 'images/original/goblin_warrior.png', f"Expected original path, got {path}"
    print("✅ Default image path uses original folder")


def test_get_minion_image_path_custom():
    """Custom equipped variant should change path"""
    player = MockPlayer()
    player.set_equipped_image('goblin_warrior', 'alt_1')

    path = player.get_minion_image_path('goblin_warrior', 'goblin_warrior.png')
    assert path == 'images/alt_1/goblin_warrior.png', f"Expected alt_1 path, got {path}"
    print("✅ Custom equipped variant changes image path")


def test_empty_storage_for_defaults():
    """Player with only default settings should have minimal storage"""
    player = MockPlayer()

    # Check that JSON is minimal
    assert player.owned_images == '{}', f"Expected '{{}}', got {player.owned_images}"
    assert player.equipped_images == '{}', f"Expected '{{}}', got {player.equipped_images}"
    print("✅ Default player has minimal JSON storage")


def test_storage_only_for_customized():
    """Only customized minions should have storage entries"""
    player = MockPlayer()

    # Customize only 3 minions out of potentially 87+
    player.add_owned_image('goblin_warrior', 'alt_1')
    player.add_owned_image('soldier', 'alt_1')
    player.add_owned_image('soldier', 'alt_2')
    player.set_equipped_image('goblin_warrior', 'alt_1')

    owned = json.loads(player.owned_images)
    equipped = json.loads(player.equipped_images)

    # Should only have 2 entries in owned (goblin_warrior, soldier)
    assert len(owned) == 2, f"Expected 2 owned entries, got {len(owned)}"
    # Should only have 1 entry in equipped (goblin_warrior)
    assert len(equipped) == 1, f"Expected 1 equipped entry, got {len(equipped)}"
    print(f"✅ Storage only contains {len(owned)} owned + {len(equipped)} equipped entries")


def test_many_players_independent():
    """Multiple players should have independent ownership"""
    players = [MockPlayer(f'player_{i}') for i in range(10)]

    # Give different players different ownership
    players[0].add_owned_image('goblin_warrior', 'alt_1')
    players[0].set_equipped_image('goblin_warrior', 'alt_1')

    players[5].add_owned_image('soldier', 'alt_2')
    players[5].set_equipped_image('soldier', 'alt_2')

    # Verify independence
    assert 'alt_1' in players[0].get_owned_images().get('goblin_warrior', set()), "Player 0 should own goblin alt_1"
    assert 'goblin_warrior' not in players[5].get_owned_images(), "Player 5 should not own goblin variants"

    assert players[0].get_equipped_images().get('goblin_warrior') == 'alt_1', "Player 0 should have goblin alt_1 equipped"
    assert players[5].get_equipped_images().get('goblin_warrior') is None, "Player 5 should not have goblin equipped"

    print("✅ 10 players have independent ownership data")


def test_ownership_check_original_always_owned():
    """Test that original variant is always considered owned (not stored)"""
    player = MockPlayer()

    # Original is always owned, never stored
    owned = player.get_owned_images()

    # To check if original is owned, we use the logic: variant == 'original' OR variant in owned_set
    def is_owned(minion_id, variant):
        if variant == 'original':
            return True
        return variant in owned.get(minion_id, set())

    assert is_owned('any_minion', 'original') == True, "Original should always be owned"
    assert is_owned('any_minion', 'alt_1') == False, "alt_1 should not be owned by default"

    # Now add alt_1
    player.add_owned_image('any_minion', 'alt_1')
    owned = player.get_owned_images()

    def is_owned_updated(minion_id, variant):
        if variant == 'original':
            return True
        return variant in owned.get(minion_id, set())

    assert is_owned_updated('any_minion', 'original') == True, "Original should still be owned"
    assert is_owned_updated('any_minion', 'alt_1') == True, "alt_1 should now be owned"
    assert is_owned_updated('any_minion', 'alt_2') == False, "alt_2 should still not be owned"

    print("✅ Original variant is always considered owned")


def test_equip_validation_logic():
    """Test the validation logic for equipping images"""
    player = MockPlayer()

    def can_equip(minion_id, variant):
        """Replicate the validation from the API endpoint"""
        if variant == 'original':
            return True  # Original is always owned
        owned = player.get_owned_images()
        return minion_id in owned and variant in owned[minion_id]

    # Can always equip original
    assert can_equip('goblin_warrior', 'original') == True, "Should be able to equip original"

    # Cannot equip unowned alt
    assert can_equip('goblin_warrior', 'alt_1') == False, "Should not be able to equip unowned alt_1"

    # Add ownership
    player.add_owned_image('goblin_warrior', 'alt_1')

    # Now can equip alt_1
    assert can_equip('goblin_warrior', 'alt_1') == True, "Should be able to equip owned alt_1"

    # Still cannot equip alt_2
    assert can_equip('goblin_warrior', 'alt_2') == False, "Should not be able to equip unowned alt_2"

    print("✅ Equip validation logic works correctly")


def run_all_tests():
    """Run all tests"""
    print("=" * 80)
    print("IMAGE OWNERSHIP SYSTEM TESTS")
    print("=" * 80)
    print()

    tests = [
        test_default_owned_images_empty,
        test_default_equipped_images_empty,
        test_add_owned_image_variant,
        test_add_owned_original_ignored,
        test_set_equipped_image_alt,
        test_set_equipped_image_original_removes,
        test_multiple_minions_owned,
        test_get_minion_image_path_default,
        test_get_minion_image_path_custom,
        test_empty_storage_for_defaults,
        test_storage_only_for_customized,
        test_many_players_independent,
        test_ownership_check_original_always_owned,
        test_equip_validation_logic,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"❌ {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ {test.__name__}: Unexpected error: {e}")
            failed += 1

    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Tests run: {len(tests)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Result: {'✅ ALL PASSED' if failed == 0 else '❌ SOME FAILED'}")

    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
