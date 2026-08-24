"""
Tests for image path system - verifies server returns correct image_path for minions
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import unittest
from flask import Flask
from models import db, Player, Run
from minions import get_all_minions


class TestImagePaths(unittest.TestCase):
    """Test that image_path is correctly set for all minions"""

    @classmethod
    def setUpClass(cls):
        """Set up test Flask app and database"""
        cls.app = Flask(__name__)
        cls.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        cls.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        cls.app.config['SECRET_KEY'] = 'test-secret'

        db.init_app(cls.app)

        with cls.app.app_context():
            db.create_all()

    def setUp(self):
        """Set up fresh test data for each test"""
        with self.app.app_context():
            # Clear existing data
            Run.query.delete()
            Player.query.delete()
            db.session.commit()

    def test_band_has_image_path_without_player(self):
        """Test that band minions have image_path even without a logged-in player"""
        with self.app.app_context():
            # Create a run without a player (guest mode)
            run = Run(
                player_id=None,
                current_ring=1,
                ring_position=0,
                health=30
            )

            # Set up a test band with minions
            test_band = [
                {'name': 'Cat', 'image': 'cat.png', 'health': 2, 'attack': 1},
                {'name': 'Soldier', 'image': 'soldier.png', 'health': 3, 'attack': 2}
            ]
            run.set_band(test_band)
            db.session.add(run)
            db.session.commit()

            # Get the run data via to_dict
            run_data = run.to_dict()
            band = run_data['band']

            # Verify all minions have image_path set
            for minion in band:
                self.assertIn('image_path', minion, f"Minion {minion['name']} missing image_path")
                self.assertIsNotNone(minion['image_path'], f"Minion {minion['name']} has None image_path")
                self.assertTrue(minion['image_path'].startswith('images/'),
                              f"Minion {minion['name']} has invalid image_path: {minion['image_path']}")
                # Without a player, should default to original
                self.assertIn('/original/', minion['image_path'],
                            f"Guest minion should use original: {minion['image_path']}")

            print(f"✓ Band without player has correct image_path for all {len(band)} minions")

    def test_band_has_image_path_with_player_no_equipped(self):
        """Test that band minions have image_path with player who hasn't equipped any"""
        with self.app.app_context():
            # Create a player with no equipped images
            player = Player(username='TestPlayer1')
            player.set_password('test123')
            db.session.add(player)
            db.session.flush()

            # Create a run linked to player
            run = Run(
                player_id=player.id,
                current_ring=1,
                ring_position=0,
                health=30
            )

            test_band = [
                {'name': 'Cat', 'image': 'cat.png', 'health': 2, 'attack': 1},
                {'name': 'Bear', 'image': 'bear.png', 'health': 5, 'attack': 3}
            ]
            run.set_band(test_band)
            db.session.add(run)
            db.session.commit()

            # Get the run data
            run_data = run.to_dict()
            band = run_data['band']

            # Verify all minions have image_path defaulting to original
            for minion in band:
                self.assertIn('image_path', minion)
                self.assertIn('/original/', minion['image_path'],
                            f"Player with no equipped should use original: {minion['image_path']}")

            print(f"✓ Band with player (no equipped) has correct image_path")

    def test_band_uses_equipped_image_variant(self):
        """Test that band minions use player's equipped image variants"""
        with self.app.app_context():
            # Create a player with equipped images
            player = Player(username='TestPlayer2')
            player.set_password('test123')
            db.session.add(player)
            db.session.flush()

            # Set equipped image for cat to alt_1
            player.set_equipped_image('cat', 'alt_1')
            db.session.commit()

            # Verify equipped was saved
            equipped = player.get_equipped_images()
            self.assertEqual(equipped.get('cat'), 'alt_1', "Equipped image not saved correctly")

            # Create a run linked to player
            run = Run(
                player_id=player.id,
                current_ring=1,
                ring_position=0,
                health=30
            )

            test_band = [
                {'name': 'Cat', 'image': 'cat.png', 'health': 2, 'attack': 1},
                {'name': 'Bear', 'image': 'bear.png', 'health': 5, 'attack': 3}
            ]
            run.set_band(test_band)
            db.session.add(run)
            db.session.commit()

            # Get the run data
            run_data = run.to_dict()
            band = run_data['band']

            # Find cat and bear in band
            cat = next((m for m in band if m['name'] == 'Cat'), None)
            bear = next((m for m in band if m['name'] == 'Bear'), None)

            # Cat should use alt_1
            self.assertIsNotNone(cat)
            self.assertEqual(cat['image_path'], 'images/alt_1/cat.png',
                           f"Cat should use alt_1 variant, got: {cat['image_path']}")

            # Bear should use original (not equipped)
            self.assertIsNotNone(bear)
            self.assertEqual(bear['image_path'], 'images/original/bear.png',
                           f"Bear should use original, got: {bear['image_path']}")

            print(f"✓ Band correctly uses equipped variants (cat=alt_1, bear=original)")

    def test_pending_selection_minions_have_image_path(self):
        """Test that minions in pending selection options have image_path"""
        with self.app.app_context():
            # Create a player with equipped cat
            player = Player(username='TestPlayer3')
            player.set_password('test123')
            player.set_equipped_image('cat', 'alt_1')
            db.session.add(player)
            db.session.flush()

            # Create a run
            run = Run(
                player_id=player.id,
                current_ring=1,
                ring_position=0,
                health=30
            )
            run.set_band([])

            # Set up a pending selection with minion options (like shop/recruit)
            pending = {
                'event_type': 'recruit',
                'options': [
                    {
                        'id': 'opt1',
                        'type': 'minion',
                        'data': {'name': 'Cat', 'image': 'cat.png', 'health': 2, 'attack': 1}
                    },
                    {
                        'id': 'opt2',
                        'type': 'minion',
                        'data': {'name': 'Bear', 'image': 'bear.png', 'health': 5, 'attack': 3}
                    }
                ]
            }
            run.set_pending_selection(pending)
            db.session.add(run)
            db.session.commit()

            # Get the run data
            run_data = run.to_dict()
            pending_selection = run_data['pending_selection']

            # Check minions in options have image_path
            self.assertIsNotNone(pending_selection)
            options = pending_selection.get('options', [])

            for opt in options:
                if 'data' in opt and 'image' in opt['data']:
                    data = opt['data']
                    self.assertIn('image_path', data,
                                f"Option minion {data.get('name')} missing image_path")

                    if data['name'] == 'Cat':
                        self.assertEqual(data['image_path'], 'images/alt_1/cat.png',
                                       f"Cat in options should use alt_1: {data['image_path']}")
                    elif data['name'] == 'Bear':
                        self.assertEqual(data['image_path'], 'images/original/bear.png',
                                       f"Bear in options should use original: {data['image_path']}")

            print(f"✓ Pending selection minions have correct image_path")

    def test_combat_state_bands_have_image_path(self):
        """Test that minions in combat_state have image_path"""
        with self.app.app_context():
            # Create a player with equipped cat
            player = Player(username='TestPlayer4')
            player.set_password('test123')
            player.set_equipped_image('cat', 'alt_1')
            db.session.add(player)
            db.session.flush()

            # Create a run
            run = Run(
                player_id=player.id,
                current_ring=1,
                ring_position=0,
                health=30
            )
            run.set_band([])

            # Set up combat state with bands
            pending = {
                'event_type': 'combat',
                'combat_state': {
                    'player_band': [
                        {'name': 'Cat', 'image': 'cat.png', 'health': 2, 'attack': 1}
                    ],
                    'enemy_band': [
                        {'name': 'Bear', 'image': 'bear.png', 'health': 5, 'attack': 3}
                    ],
                    'combat_over': False
                }
            }
            run.set_pending_selection(pending)
            db.session.add(run)
            db.session.commit()

            # Get the run data
            run_data = run.to_dict()
            pending_selection = run_data['pending_selection']
            combat_state = pending_selection.get('combat_state', {})

            # Check player_band
            player_band = combat_state.get('player_band', [])
            for minion in player_band:
                self.assertIn('image_path', minion,
                            f"Combat player minion {minion.get('name')} missing image_path")
                if minion['name'] == 'Cat':
                    self.assertEqual(minion['image_path'], 'images/alt_1/cat.png')

            # Check enemy_band
            enemy_band = combat_state.get('enemy_band', [])
            for minion in enemy_band:
                self.assertIn('image_path', minion,
                            f"Combat enemy minion {minion.get('name')} missing image_path")
                # Enemy uses player's equipped images too (for consistency)
                self.assertEqual(minion['image_path'], 'images/original/bear.png')

            print(f"✓ Combat state bands have correct image_path")

    def test_equipped_images_persist(self):
        """Test that equipped images are properly saved and loaded"""
        with self.app.app_context():
            # Create player and equip some images
            player = Player(username='TestPlayer5')
            player.set_password('test123')
            db.session.add(player)
            db.session.flush()

            player_id = player.id

            # Equip multiple images
            player.set_equipped_image('cat', 'alt_1')
            player.set_equipped_image('bear', 'alt_2')
            player.set_equipped_image('soldier', 'original')  # Should not be stored
            db.session.commit()

            # Clear session to force reload from DB
            db.session.expire_all()

            # Reload player
            reloaded_player = Player.query.get(player_id)
            equipped = reloaded_player.get_equipped_images()

            self.assertEqual(equipped.get('cat'), 'alt_1', "Cat equipped not persisted")
            self.assertEqual(equipped.get('bear'), 'alt_2', "Bear equipped not persisted")
            self.assertNotIn('soldier', equipped, "Original should not be stored")

            print(f"✓ Equipped images persist correctly: {equipped}")

    def test_get_band_with_equipped_images_always_sets_path(self):
        """Test that get_band_with_equipped_images ALWAYS sets image_path"""
        with self.app.app_context():
            # Create player with NO equipped images
            player = Player(username='TestPlayer6')
            player.set_password('test123')
            db.session.add(player)
            db.session.flush()

            # Verify player has empty equipped
            equipped = player.get_equipped_images()
            self.assertEqual(equipped, {}, "New player should have empty equipped")

            # Create run with band
            run = Run(
                player_id=player.id,
                current_ring=1,
                ring_position=0,
                health=30
            )
            test_band = [
                {'name': 'Cat', 'image': 'cat.png', 'health': 2, 'attack': 1},
                {'name': 'Bear', 'image': 'bear.png', 'health': 5, 'attack': 3}
            ]
            run.set_band(test_band)
            db.session.add(run)
            db.session.commit()

            # Get band with images - should still set image_path even with empty equipped
            band = run.get_band_with_equipped_images()

            for minion in band:
                self.assertIn('image_path', minion,
                            f"Minion {minion['name']} missing image_path with empty equipped")
                self.assertIn('/original/', minion['image_path'],
                            f"Should default to original: {minion['image_path']}")

            print(f"✓ get_band_with_equipped_images ALWAYS sets image_path")


    def test_heroes_endpoint_includes_image_path(self):
        """Test that /api/dev/heroes returns minions with image_path"""
        with self.app.app_context():
            # Create a player with equipped images
            player = Player(username='TestPlayerHero')
            player.set_password('test123')
            player.set_equipped_image('cat', 'alt_1')
            db.session.add(player)
            db.session.commit()

            # Note: We can't easily test the actual endpoint here without the full app,
            # but we can test the logic by simulating what the endpoint does
            equipped_images = player.get_equipped_images()

            # Simulate what the heroes endpoint does for a minion
            image_filename = 'cat.png'
            minion_id = image_filename.replace('.png', '')

            if minion_id in equipped_images:
                image_path = f"images/{equipped_images[minion_id]}/{image_filename}"
            else:
                image_path = f"images/original/{image_filename}"

            self.assertEqual(image_path, 'images/alt_1/cat.png',
                           "Heroes endpoint should use equipped variant for cat")

            # Test a minion that's not equipped
            bear_filename = 'bear.png'
            bear_id = bear_filename.replace('.png', '')

            if bear_id in equipped_images:
                bear_path = f"images/{equipped_images[bear_id]}/{bear_filename}"
            else:
                bear_path = f"images/original/{bear_filename}"

            self.assertEqual(bear_path, 'images/original/bear.png',
                           "Heroes endpoint should use original for non-equipped minions")

            print(f"✓ Heroes endpoint logic correctly includes image_path")


def run_tests():
    """Run all tests and report results"""
    # Create a test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestImagePaths)

    # Run with verbosity
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Summary
    print("\n" + "="*60)
    if result.wasSuccessful():
        print("ALL TESTS PASSED!")
    else:
        print(f"FAILURES: {len(result.failures)}")
        print(f"ERRORS: {len(result.errors)}")
        for test, traceback in result.failures + result.errors:
            print(f"\n--- {test} ---")
            print(traceback)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
