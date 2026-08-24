"""
Dev Combat Routes - Enhanced with dual mode support and band state tracking

FIXED: Proper band setup for testing permanent band-scoped effects
ADDED: Post-combat band state retrieval to see permanent buffs
FIXED: Added set_band() method to MockRun class
"""

import logging

logger = logging.getLogger(__name__)

from flask import Blueprint, request, jsonify
from game_engine.combat_system import CombatSystem
from game_engine.combat_registry import CombatRegistry
from minions import get_all_minions, get_minion_by_name, create_minion_instance
from game_random import game_random, SelectionType
import copy
import uuid

DEV_COMBAT_SESSIONS = {}

dev_api = Blueprint('dev_api', __name__)
# Restrict all dev combat endpoints to localhost
from rate_limit import localhost_only
dev_api.before_request(localhost_only)


class MockRun:
    """
    Mock Run object for dev combat mode with proper band support

    FIXED: Now properly maintains a band that can receive permanent buffs
    FIXED: Added set_band() method for permanent stat effects
    """

    def __init__(self, gold=0, band=None, shop_band=None, recruit_options=None, band_history=None, hero_effects=None):
        self.gold = gold
        self.band = band or []  # The actual band that receives permanent buffs
        self.shop_band = shop_band or []
        self.recruit_options = recruit_options or []
        self.band_history = band_history or []
        self.hero_effects = hero_effects or {}  # Hero effects for testing

        self.ring_level = 1
        self.rings_completed = 0
        self.health = 100
        self.max_health = 100
        self._dev_mode_mock = True

    def get_resources(self):
        """Return resources dict (primarily gold)"""
        return {
            'gold': self.gold,
            'health': self.health,
            'max_health': self.max_health
        }

    def get_gold(self):
        return self.gold

    def set_gold(self, amount):
        self.gold = max(0, amount)

    def add_gold(self, amount):
        self.gold += amount

    def spend_gold(self, amount):
        if self.gold >= amount:
            self.gold -= amount
            return True
        return False

    def get_band(self):
        """Get current band - returns the band being tested"""
        return self.band

    def set_band(self, band):
        """Set the current band - CRITICAL for permanent stat effects"""
        self.band = band

    def get_band_history(self):
        return self.band_history

    def get_hero_effects(self):
        """Get hero effects for testing"""
        return self.hero_effects

    def set_hero_effects(self, effects):
        """Set hero effects for testing"""
        self.hero_effects = effects

    def is_dev_mode(self):
        return True

    def to_dict(self):
        """Convert to dictionary for serialization"""
        return {
            'gold': self.gold,
            'band': [self._serialize_minion(m) for m in self.band],
            'shop_band': self.shop_band,
            'recruit_options': self.recruit_options,
            'band_history': self.band_history,
            'hero_effects': self.hero_effects,
            'ring_level': self.ring_level,
            'rings_completed': self.rings_completed,
            'health': self.health,
            'max_health': self.max_health,
            '_dev_mode_mock': True
        }

    def _serialize_minion(self, minion):
        """Serialize a minion for JSON"""
        return {
            'name': minion.get('name'),
            'health': minion.get('health'),
            'attack': minion.get('attack'),
            'base_health': minion.get('base_health', minion.get('health')),
            'base_attack': minion.get('base_attack', minion.get('attack')),
            'permanent_health': minion.get('permanent_health', 0),
            'permanent_attack': minion.get('permanent_attack', 0),
            'golden': minion.get('golden', False),
            'keywords': minion.get('keywords', []),
            'band_id': minion.get('band_id'),
            'position': minion.get('position', 0),
            'image': minion.get('image')
        }


class DevCombatSession:
    """Enhanced dev combat session with proper band state tracking"""

    def __init__(self, session_id):
        self.id = session_id
        self.mode = 'step'

        # Combat state
        self.combat_state = None
        self.step_count = 0
        self.combat_log_full = []

        # Playback state
        self.interpreter_data = None
        self.final_combat_result = None

        # Configuration
        self.settings = {}
        self.original_player_band = []
        self.original_enemy_band = []

        # Manual targeting
        self.manual_targeting_enabled = False
        self.selection_history = []

        # Spoofed game state
        self.spoofed_gold = 0
        self.spoofed_band_data = {
            'shop_band': [],
            'recruit_options': [],
            'band_history': []
        }
        self.spoofed_hero_effects = {}

        # CRITICAL: Store the mock run to access post-combat band state
        self.mock_run = None

    def create_mock_run(self, player_band_minions):
        """
        Create a mock run with proper band setup

        CRITICAL: The player_band_minions are added to the run's band
        so that band-scoped effects can find their targets
        """
        # Create deep copies of the minions for the band
        band_minions = []
        for minion in player_band_minions:
            band_copy = copy.deepcopy(minion)
            # Ensure band_id is set
            if not band_copy.get('band_id'):
                band_copy['band_id'] = str(uuid.uuid4())
            band_minions.append(band_copy)

        self.mock_run = MockRun(
            gold=self.spoofed_gold,
            band=band_minions,  # The band that will receive permanent buffs
            shop_band=copy.deepcopy(self.spoofed_band_data.get('shop_band', [])),
            recruit_options=copy.deepcopy(self.spoofed_band_data.get('recruit_options', [])),
            band_history=copy.deepcopy(self.spoofed_band_data.get('band_history', [])),
            hero_effects=self.spoofed_hero_effects
        )

        logger.debug(f"[DevCombat] Created MockRun with {len(band_minions)} band minions, gold={self.mock_run.gold}, hero_effects={self.spoofed_hero_effects}")
        return self.mock_run

    def get_post_combat_band(self):
        """
        Get the band state after combat to see permanent buffs

        Returns the band from the mock run which has accumulated all permanent effects
        """
        if not self.mock_run:
            return []

        return self.mock_run.band

    def set_gold(self, amount: int):
        self.spoofed_gold = max(0, amount)
        logger.debug(f"[DevCombat] Spoofed gold set to {self.spoofed_gold}")

    def set_band_data(self, band_data: dict):
        if 'shop_band' in band_data:
            self.spoofed_band_data['shop_band'] = band_data['shop_band']
        if 'recruit_options' in band_data:
            self.spoofed_band_data['recruit_options'] = band_data['recruit_options']
        if 'band_history' in band_data:
            self.spoofed_band_data['band_history'] = band_data['band_history']
        logger.debug(f"[DevCombat] Spoofed band data updated")

    def set_hero_effects(self, hero_effects: dict):
        self.spoofed_hero_effects = hero_effects
        logger.debug(f"[DevCombat] Hero effects set to {hero_effects}")

    def set_mode(self, mode):
        if mode not in ['step', 'playback']:
            raise ValueError(f"Invalid mode: {mode}")
        old_mode = self.mode
        self.mode = mode
        logger.debug(f"[DevCombatSession] Switched from {old_mode} to {mode} mode")

    def enable_manual_targeting(self):
        self.manual_targeting_enabled = True
        game_random.enable_dev_mode(self.id)

    def disable_manual_targeting(self):
        self.manual_targeting_enabled = False
        game_random.disable_dev_mode()

    def add_target_override(self, selection_type, target_identifier, metadata_filter=None):
        if isinstance(target_identifier, dict):
            def target_filter(option):
                for key, value in target_identifier.items():
                    if not hasattr(option, 'get'):
                        return False
                    if option.get(key) != value:
                        return False
                return True
        else:
            def target_filter(option):
                if not hasattr(option, 'get'):
                    return False
                return (option.get('band_id') == target_identifier or
                       option.get('name') == target_identifier or
                       option.get('_combat_id') == target_identifier)

        override_id = game_random.add_override(
            selection_type=selection_type,
            target_filter=target_filter,
            metadata_filter=metadata_filter,
            priority=10
        )

        return {
            'override_id': override_id,
            'selection_type': selection_type,
            'target': target_identifier,
            'metadata_filter': metadata_filter
        }

    def get_selection_history(self, limit=20):
        history = game_random.get_history(limit=limit)
        return [
            {
                'type': ctx.selection_type.value,
                'options_count': len(ctx.options),
                'result': str(ctx.metadata.get('result')),
                'overridden': ctx.metadata.get('overridden', False),
                'source': ctx.source,
                'description': ctx.description
            }
            for ctx in history
        ]

    def reset_to_initial_state(self):
        self.combat_state = None
        self.step_count = 0
        self.combat_log_full = []
        self.interpreter_data = None
        self.final_combat_result = None
        game_random.clear_overrides()
        if self.manual_targeting_enabled:
            game_random.enable_dev_mode(self.id)
        logger.debug(f"[DevCombatSession] Reset to initial state in {self.mode} mode")


def create_dev_minion(minion_config):
    """Create a minion for dev combat from configuration"""
    if minion_config.get('is_custom'):
        minion = {
            'name': minion_config.get('name', 'Custom Minion'),
            'health': minion_config.get('health', 1),
            'attack': minion_config.get('attack', 1),
            'golden': minion_config.get('golden', False),
            'keywords': minion_config.get('keywords', []),
            'tier': minion_config.get('tier', 1),
            'type': minion_config.get('type', 'Custom'),
            'position': 0
        }

        for keyword in minion['keywords']:
            effect_key = f'{keyword}_effect'
            if effect_key in minion_config:
                minion[effect_key] = minion_config[effect_key]

        if minion_config.get('is_player_minion', True):
            minion['band_id'] = str(uuid.uuid4())

    else:
        name = minion_config.get('name')
        template = get_minion_by_name(name)
        if not template:
            raise ValueError(f"Unknown minion: {name}")

        assign_band_id = minion_config.get('is_player_minion', True)
        minion = create_minion_instance(template, assign_band_id=assign_band_id)

        if 'health' in minion_config:
            minion['health'] = minion_config['health']
        if 'attack' in minion_config:
            minion['attack'] = minion_config['attack']
        if 'golden' in minion_config:
            minion['golden'] = minion_config['golden']
        if 'keywords' in minion_config:
            minion['keywords'] = minion_config['keywords']

        for keyword in minion.get('keywords', []):
            effect_key = f'{keyword}_effect'
            if effect_key in minion_config:
                minion[effect_key] = minion_config[effect_key]

    # Support for add_possessed_death_toll flag (for Greater Possessed boss testing)
    if minion_config.get('add_possessed_death_toll'):
        if 'death_toll' not in minion.get('keywords', []):
            minion['keywords'] = minion.get('keywords', []) + ['death_toll']
        # Possessed's death_toll effect - grants random ally the same death_toll
        minion['death_toll_effect'] = {
            'type': 'grant_effect_to_minion',
            'target': 'random_ally',
            'exclude_name': 'Possessed',
            'effect_type': 'death_toll_effect',
            'effect_data': {
                'type': 'summon_minion',
                'minion_name': 'Possessed',
                'health': 1,
                'attack': 6
            }
        }

    if minion.get('golden', False) and not minion_config.get('skip_golden_bonus'):
        minion['health'] = minion['health'] * 2
        minion['attack'] = minion['attack'] * 2

    return minion


@dev_api.route('/combat/create', methods=['POST'])
def create_dev_combat():
    """Create a new dev combat session with proper band state tracking"""
    try:
        data = request.get_json()
        player_band_config = data.get('player_band', [])
        enemy_band_config = data.get('enemy_band', [])
        settings = data.get('settings', {})
        spoofed_gold = data.get('spoofed_gold', 0)
        spoofed_band_data = data.get('spoofed_band_data', {})
        hero_effects = data.get('hero_effects', {})

        if not player_band_config or not enemy_band_config:
            return jsonify({'success': False, 'error': 'Both bands required'}), 400

        session_id = str(uuid.uuid4())
        session = DevCombatSession(session_id)
        session.settings = settings
        session.set_gold(spoofed_gold)
        session.set_band_data(spoofed_band_data)
        session.set_hero_effects(hero_effects)

        mode = settings.get('mode', 'step')
        session.set_mode(mode)

        if settings.get('manual_targeting', False):
            session.enable_manual_targeting()

        # Create player band
        player_band = []
        for i, minion_config in enumerate(player_band_config):
            minion_config['is_player_minion'] = True
            minion = create_dev_minion(minion_config)
            minion['position'] = i
            player_band.append(minion)

        # Create enemy band
        enemy_band = []
        for i, minion_config in enumerate(enemy_band_config):
            minion_config['is_player_minion'] = False
            minion = create_dev_minion(minion_config)
            minion['position'] = i
            enemy_band.append(minion)

        session.original_player_band = copy.deepcopy(player_band)
        session.original_enemy_band = copy.deepcopy(enemy_band)

        # CRITICAL: Create mock run with player band
        mock_run = session.create_mock_run(player_band)

        # Initialize based on mode
        if mode == 'step':
            combat_state = CombatSystem.create_initial_combat_state(player_band, enemy_band, run=mock_run)
            session.combat_state = combat_state
        elif mode == 'playback':
            battle_result = CombatSystem.resolve_combat(player_band, enemy_band, run=mock_run)
            session.final_combat_result = battle_result
            session.interpreter_data = battle_result.get('interpreter_data')

        DEV_COMBAT_SESSIONS[session_id] = session

        response_data = {
            'success': True,
            'session_id': session_id,
            'mode': mode,
            'manual_targeting_enabled': session.manual_targeting_enabled,
            'spoofed_gold': session.spoofed_gold,
            'hero_effects': session.spoofed_hero_effects,
            'message': f'Dev combat created in {mode} mode: {len(player_band)} vs {len(enemy_band)} minions (Gold: {session.spoofed_gold}, Hero: {session.spoofed_hero_effects})'
        }

        if mode == 'step':
            step_combat_state = copy.deepcopy(combat_state)
            if 'interpreter' in step_combat_state:
                del step_combat_state['interpreter']
            if 'run' in step_combat_state:
                step_combat_state['run'] = mock_run.to_dict()
            response_data['combat_state'] = step_combat_state

            if settings.get('debug_mode', False):
                registry_data = combat_state.get('combat_registry_data')
                if registry_data:
                    registry = CombatRegistry.from_dict(
                        registry_data,
                        combat_state['player_band'],
                        combat_state['enemy_band']
                    )
                    response_data['debug_info'] = {
                        'registry_state': registry.to_dict(),
                        'random_state': game_random.export_state(),
                        'step_count': 0,
                        'mock_run': mock_run.to_dict()
                    }

        elif mode == 'playback':
            response_data['interpreter_data'] = session.interpreter_data
            response_data['final_result'] = {
                'winner': battle_result['winner'],
                'rounds': battle_result['rounds'],
                'attacks': battle_result['attacks']
            }

        return jsonify(response_data)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@dev_api.route('/combat/<session_id>/post-combat-band', methods=['GET'])
def get_post_combat_band(session_id):
    """
    Get the post-combat band state showing permanent buffs

    This retrieves the band from the MockRun after combat has finished,
    showing all permanent stat gains accumulated during the fight
    """
    try:
        session = DEV_COMBAT_SESSIONS.get(session_id)
        if not session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        # Get the post-combat band state
        post_combat_band = session.get_post_combat_band()

        # Check if combat is actually over
        combat_over = False
        if session.mode == 'step' and session.combat_state:
            combat_over = session.combat_state.get('combat_over', False)
        elif session.mode == 'playback' and session.final_combat_result:
            combat_over = True

        return jsonify({
            'success': True,
            'combat_over': combat_over,
            'post_combat_band': [
                {
                    'name': m.get('name'),
                    'health': m.get('health'),
                    'attack': m.get('attack'),
                    'base_health': m.get('base_health', m.get('health')),
                    'base_attack': m.get('base_attack', m.get('attack')),
                    'permanent_health': m.get('permanent_health', 0),
                    'permanent_attack': m.get('permanent_attack', 0),
                    'golden': m.get('golden', False),
                    'keywords': m.get('keywords', []),
                    'band_id': m.get('band_id'),
                    'position': m.get('position', 0),
                    'image': m.get('image')
                }
                for m in post_combat_band
            ],
            'band_size': len(post_combat_band)
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@dev_api.route('/combat/<session_id>/step', methods=['POST'])
def step_dev_combat(session_id):
    """Process one combat step with band state tracking"""
    try:
        session = DEV_COMBAT_SESSIONS.get(session_id)
        if not session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        if session.mode != 'step':
            return jsonify({'success': False, 'error': 'Step function only available in step mode'}), 400

        combat_state = session.combat_state
        if combat_state.get('combat_over', False):
            return jsonify({
                'success': False,
                'error': 'Combat already over',
                'winner': combat_state.get('winner')
            }), 400

        if 'run' not in combat_state or combat_state['run'] is None:
            combat_state['run'] = session.mock_run
        elif isinstance(combat_state['run'], dict):
            # Shouldn't happen but handle it
            logger.warning("[WARNING] Run was a dict, recreating MockRun")
            combat_state['run'] = session.mock_run

        combat_state = CombatSystem.process_combat_step(combat_state, run=combat_state['run'])
        session.combat_state = combat_state
        session.step_count += 1

        new_logs = combat_state.get('combat_log', [])
        if session.combat_log_full:
            existing_count = len(session.combat_log_full)
            if len(new_logs) > existing_count:
                session.combat_log_full.extend(new_logs[existing_count:])
        else:
            session.combat_log_full = new_logs.copy()

        debug_info = {}
        if session.settings.get('debug_mode', False):
            registry_data = combat_state.get('combat_registry_data')
            if registry_data:
                registry = CombatRegistry.from_dict(
                    registry_data,
                    combat_state['player_band'],
                    combat_state['enemy_band']
                )
                debug_info = {
                    'registry_state': registry.debug_state(),
                    'step_count': session.step_count,
                    'selection_history': session.get_selection_history(10),
                    'random_state': game_random.export_state(),
                    'mock_run': session.mock_run.to_dict() if session.mock_run else None
                }

        next_action = get_next_combat_action(combat_state)

        step_combat_state = copy.deepcopy(combat_state)
        if 'interpreter' in step_combat_state:
            del step_combat_state['interpreter']
        if 'run' in step_combat_state and hasattr(step_combat_state['run'], 'to_dict'):
            step_combat_state['run'] = step_combat_state['run'].to_dict()

        return jsonify({
            'success': True,
            'mode': 'step',
            'combat_state': step_combat_state,
            'step_count': session.step_count,
            'combat_over': combat_state.get('combat_over', False),
            'winner': combat_state.get('winner'),
            'debug_info': debug_info,
            'next_action': next_action
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@dev_api.route('/combat/<session_id>/regenerate-playback', methods=['POST'])
def regenerate_playback_data(session_id):
    """Regenerate interpreter data for playback mode with band state"""
    try:
        session = DEV_COMBAT_SESSIONS.get(session_id)
        if not session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        player_band = copy.deepcopy(session.original_player_band)
        enemy_band = copy.deepcopy(session.original_enemy_band)

        game_random.clear_overrides()
        if session.manual_targeting_enabled:
            game_random.enable_dev_mode(session.id)

        # Create fresh mock run with player band
        mock_run = session.create_mock_run(player_band)

        battle_result = CombatSystem.resolve_combat(player_band, enemy_band, run=mock_run)
        session.final_combat_result = battle_result
        session.interpreter_data = battle_result.get('interpreter_data')

        return jsonify({
            'success': True,
            'mode': session.mode,
            'interpreter_data': session.interpreter_data,
            'final_result': {
                'winner': battle_result['winner'],
                'rounds': battle_result['rounds'],
                'attacks': battle_result['attacks']
            },
            'spoofed_gold': session.spoofed_gold,
            'message': 'Playback data regenerated'
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@dev_api.route('/combat/<session_id>/reset', methods=['POST'])
def reset_dev_combat(session_id):
    """Reset combat to initial state with band tracking"""
    try:
        session = DEV_COMBAT_SESSIONS.get(session_id)
        if not session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        session.reset_to_initial_state()

        if session.mode == 'step':
            player_band = copy.deepcopy(session.original_player_band)
            enemy_band = copy.deepcopy(session.original_enemy_band)
            mock_run = session.create_mock_run(player_band)
            combat_state = CombatSystem.create_initial_combat_state(player_band, enemy_band, run=mock_run)
            session.combat_state = combat_state

            step_combat_state = copy.deepcopy(combat_state)
            if 'interpreter' in step_combat_state:
                del step_combat_state['interpreter']
            if 'run' in step_combat_state:
                step_combat_state['run'] = mock_run.to_dict()

            return jsonify({
                'success': True,
                'mode': 'step',
                'message': 'Combat reset to initial state',
                'combat_state': step_combat_state,
                'spoofed_gold': session.spoofed_gold
            })

        elif session.mode == 'playback':
            player_band = copy.deepcopy(session.original_player_band)
            enemy_band = copy.deepcopy(session.original_enemy_band)
            mock_run = session.create_mock_run(player_band)
            battle_result = CombatSystem.resolve_combat(player_band, enemy_band, run=mock_run)
            session.final_combat_result = battle_result
            session.interpreter_data = battle_result.get('interpreter_data')

            return jsonify({
                'success': True,
                'mode': 'playback',
                'message': 'Combat reset and regenerated',
                'interpreter_data': session.interpreter_data,
                'final_result': {
                    'winner': battle_result['winner'],
                    'rounds': battle_result['rounds'],
                    'attacks': battle_result['attacks']
                },
                'spoofed_gold': session.spoofed_gold
            })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# Helper function for next action
def get_next_combat_action(combat_state):
    """Analyze what the next combat action will be"""
    if combat_state.get('combat_over'):
        return None

    is_player_turn = combat_state.get('player_turn', True)
    player_band = combat_state.get('player_band', [])
    enemy_band = combat_state.get('enemy_band', [])

    multi_attack_queue = combat_state.get('multi_attack_queue', [])
    if multi_attack_queue:
        next_multi = multi_attack_queue[0]
        attacker = next_multi['attacker']

        if attacker in player_band:
            attacker_side = 'player'
            valid_targets = [m for m in enemy_band if m.get('health', 0) > 0]
        else:
            attacker_side = 'enemy'
            valid_targets = [m for m in player_band if m.get('health', 0) > 0]

        return {
            'action_type': 'multi_attack',
            'attack_number': next_multi.get('attack_number', 2),
            'attacker': {
                'name': attacker.get('name'),
                'band_id': attacker.get('band_id'),
                '_combat_id': attacker.get('_combat_id'),
                'position': attacker.get('position'),
                'side': attacker_side,
                'health': attacker.get('health'),
                'attack': attacker.get('attack')
            },
            'valid_targets': format_targets_for_ui(valid_targets)
        }

    if is_player_turn:
        attacker_band = player_band
        defender_band = enemy_band
        attacker_side = 'player'
    else:
        attacker_band = enemy_band
        defender_band = player_band
        attacker_side = 'enemy'

    current_unit = combat_state.get(f'current_{attacker_side}_unit', 0)
    attacker = None
    for i in range(len(attacker_band)):
        check_index = (current_unit + i) % len(attacker_band)
        if attacker_band[check_index].get('health', 0) > 0:
            attacker = attacker_band[check_index]
            break

    if not attacker:
        return None

    valid_targets = [m for m in defender_band if m.get('health', 0) > 0]

    from keywords import has_keyword
    guards = [m for m in valid_targets if has_keyword(m, 'guard')]
    if guards:
        valid_targets = guards

    keywords = attacker.get('keywords', [])
    abilities = []
    if has_keyword(attacker, 'assault'):
        abilities.append('assault')
    if has_keyword(attacker, 'cast'):
        abilities.append('cast')

    return {
        'action_type': 'combat_attack',
        'attacker': {
            'name': attacker.get('name'),
            'band_id': attacker.get('band_id'),
            '_combat_id': attacker.get('_combat_id'),
            'position': attacker.get('position'),
            'side': attacker_side,
            'health': attacker.get('health'),
            'attack': attacker.get('attack'),
            'keywords': keywords,
            'abilities': abilities
        },
        'valid_targets': format_targets_for_ui(valid_targets)
    }


def format_targets_for_ui(targets):
    """Format target list for UI display"""
    return [
        {
            'name': t.get('name'),
            'band_id': t.get('band_id'),
            '_combat_id': t.get('_combat_id'),
            'position': t.get('position'),
            'health': t.get('health'),
            'attack': t.get('attack'),
            'keywords': t.get('keywords', [])
        }
        for t in targets
    ]


# Remaining endpoints remain the same
@dev_api.route('/combat/<session_id>/set-gold', methods=['POST'])
def set_combat_gold(session_id):
    try:
        session = DEV_COMBAT_SESSIONS.get(session_id)
        if not session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404
        data = request.get_json()
        gold_amount = data.get('gold', 0)
        session.set_gold(gold_amount)
        return jsonify({'success': True, 'gold': session.spoofed_gold, 'message': f'Gold set to {session.spoofed_gold}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@dev_api.route('/minions', methods=['GET'])
def get_available_minions():
    try:
        all_minions = get_all_minions()
        minion_list = []
        for minion in all_minions:
            minion_info = {
                'name': minion['name'],
                'health': minion['health'],
                'attack': minion['attack'],
                'keywords': minion.get('keywords', []),
                'tier': minion.get('tier', 1),
                'type': minion.get('type', 'Unknown'),
                'effects': {}
            }
            for keyword in minion.get('keywords', []):
                effect_key = f'{keyword}_effect'
                if effect_key in minion:
                    minion_info['effects'][keyword] = minion[effect_key]
            minion_list.append(minion_info)
        minion_list.sort(key=lambda x: (x['tier'], x['name']))
        return jsonify({
            'success': True,
            'minions': minion_list,
            'total': len(minion_list),
            'selection_types': [t.value for t in SelectionType]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@dev_api.route('/combat/presets', methods=['GET'])
def get_combat_presets():
    presets = [
        {
            'name': 'Cat Death Toll Test',
            'description': 'Test Cat giving permanent +1/+1 to band when it dies',
            'player_band': [
                {'name': 'Cat', 'golden': False},
                {'name': 'Cat', 'golden': False},
                {'name': 'Wolf', 'golden': False}
            ],
            'enemy_band': [
                {'name': 'Archer', 'golden': False},
                {'name': 'Soldier', 'golden': False}
            ],
            'notes': 'Cats give +1/+1 to all band minions when they die. Check post-combat band to see permanent buffs!'
        },
        {
            'name': 'Rich Keyword Test',
            'description': 'Test King with Rich keyword - requires spoofed gold',
            'player_band': [
                {'name': 'King', 'golden': False},
                {'name': 'King', 'golden': True}
            ],
            'enemy_band': [
                {'name': 'Soldier', 'golden': False},
                {'name': 'Farmer', 'golden': False}
            ],
            'recommended_gold': 50,
            'notes': 'Set gold to 50+ to see King buff properly'
        },
        # ===== COMBAT TEST PRESETS =====
        {
            'name': 'Beast Pack Test',
            'description': 'Test combat against a pack of beasts with Savage keyword',
            'player_band': [
                {'name': 'Paladin', 'golden': False},
                {'name': 'Soldier', 'golden': False},
                {'name': 'Soldier', 'golden': False}
            ],
            'enemy_band': [
                {'name': 'Hound', 'golden': False},
                {'name': 'Hound', 'golden': False},
                {'name': 'Bear', 'golden': False},
                {'name': 'Hound', 'golden': False}
            ],
            'notes': 'Tests Savage keyword interactions. Bear is a T2 Beast.'
        },
        {
            'name': 'Cultist Swarm Test',
            'description': 'Test against cult minions with summoning mechanics',
            'player_band': [
                {'name': 'Wizard', 'golden': False},
                {'name': 'Soldier', 'golden': False},
                {'name': 'Soldier', 'golden': False}
            ],
            'enemy_band': [
                {'name': 'Cultist', 'golden': False},
                {'name': 'Cultist', 'golden': False},
                {'name': 'Fanatic', 'golden': False},
                {'name': 'Cultist', 'golden': False},
                {'name': 'Cultist', 'golden': False}
            ],
            'notes': 'Tests cultist mechanics. Fanatic is a T2 Cult minion.'
        },
        {
            'name': 'Guard Wall Test',
            'description': 'Test against minions with Guard keyword',
            'player_band': [
                {'name': 'Wizard', 'golden': True},
                {'name': 'Wizard', 'golden': False},
                {'name': 'Soldier', 'golden': False}
            ],
            'enemy_band': [
                {'name': 'Iron Wall', 'golden': False},
                {'name': 'Iron Wall', 'golden': False},
                {'name': 'Gear Spider', 'golden': False}
            ],
            'notes': 'Tests Guard keyword. Iron Wall has Guard, forces attacks on it.'
        },
        {
            'name': 'Undead Horde Test',
            'description': 'Test against undead minions with death effects',
            'player_band': [
                {'name': 'Paladin', 'golden': True},
                {'name': 'Paladin', 'golden': False},
                {'name': 'Wizard', 'golden': False}
            ],
            'enemy_band': [
                {'name': 'Skeleton', 'golden': False},
                {'name': 'Zombie', 'golden': False},
                {'name': 'Necromancer', 'golden': False},
                {'name': 'Wight', 'golden': False}
            ],
            'notes': 'Tests undead mechanics. Necromancer summons, Wight has Death Toll.'
        },
        {
            'name': 'Fey Tricksters Test',
            'description': 'Test against Fey minions with utility keywords',
            'player_band': [
                {'name': 'Soldier', 'golden': True},
                {'name': 'Soldier', 'golden': True},
                {'name': 'Huntsman', 'golden': False}
            ],
            'enemy_band': [
                {'name': 'Pixie', 'golden': False},
                {'name': 'Spriggan', 'golden': False},
                {'name': 'Boggart', 'golden': False},
                {'name': 'Dryad', 'golden': False}
            ],
            'notes': 'Tests Fey mechanics with various keywords like Hide and Cast.'
        },
        {
            'name': 'Construct Army Test',
            'description': 'Test against construct minions with buffs',
            'player_band': [
                {'name': 'Wizard', 'golden': True},
                {'name': 'Paladin', 'golden': True},
                {'name': 'Soldier', 'golden': True}
            ],
            'enemy_band': [
                {'name': 'Rust Golem', 'golden': False},
                {'name': 'Gear Spider', 'golden': False},
                {'name': 'War Machine', 'golden': False},
                {'name': 'Clockwork', 'golden': False},
                {'name': 'Iron Wall', 'golden': False}
            ],
            'notes': 'Tests Construct mechanics. War Machine and Clockwork are T2 Constructs.'
        },
        # ===== BOSS COMBAT PRESETS (The Great Hunt) =====
        {
            'name': 'Boss: Dire Pack',
            'description': 'Alpha Direwolf 8/8 (Assault +3/+3, on_any_death +3/+3) + 4 Dire Wolves 3/3 (Savage)',
            'player_band': [
                {'name': 'Paladin', 'golden': True},
                {'name': 'Paladin', 'golden': True},
                {'name': 'Wizard', 'golden': True},
                {'name': 'Wizard', 'golden': True}
            ],
            'enemy_band': [
                {'name': 'Dire Wolf', 'golden': False},
                {'name': 'Dire Wolf', 'golden': False},
                {'name': 'Alpha Direwolf', 'golden': False},
                {'name': 'Dire Wolf', 'golden': False},
                {'name': 'Dire Wolf', 'golden': False}
            ],
            'notes': 'Boss encounter. Alpha buffs +3/+3 on assault and when any minion dies. Wolves have Savage.'
        },
        {
            'name': 'Boss: Congregation',
            'description': 'Congregation 0/30 (Cast x2 summon Cultist) + 4 Cultists',
            'player_band': [
                {'name': 'Wizard', 'golden': True},
                {'name': 'Wizard', 'golden': True},
                {'name': 'Paladin', 'golden': True},
                {'name': 'Soldier', 'golden': True}
            ],
            'enemy_band': [
                {'name': 'Cultist', 'golden': False},
                {'name': 'Cultist', 'golden': False},
                {'name': 'Congregation', 'golden': False},
                {'name': 'Cultist', 'golden': False},
                {'name': 'Cultist', 'golden': False}
            ],
            'notes': 'Boss encounter. Congregation summons 2 Cultists per turn. Cannot attack.'
        },
        {
            'name': 'Boss: Chained Beast',
            'description': '5 Chains 12/2 (Hide 2) + Chained Beast 22/22 (Ethereal [Last], Leap 1)',
            'player_band': [
                {'name': 'Wizard', 'golden': True},
                {'name': 'Wizard', 'golden': True},
                {'name': 'Paladin', 'golden': True},
                {'name': 'Paladin', 'golden': True}
            ],
            'enemy_band': [
                {'name': 'Chain', 'golden': False},
                {'name': 'Chain', 'golden': False},
                {'name': 'Chain', 'golden': False},
                {'name': 'Chain', 'golden': False},
                {'name': 'Chain', 'golden': False},
                {'name': 'Chained Beast', 'golden': False}
            ],
            'notes': 'Boss encounter. Chains have Hide 2. Beast is Ethereal [Last] and Leaps 1. Kill chains first!'
        },
        {
            'name': 'Boss: Ancient Behemoth',
            'description': 'Ancient Behemoth 12/40 (Guard, on_damage: Deal 2 to all enemies)',
            'player_band': [
                {'name': 'Wizard', 'golden': True},
                {'name': 'Wizard', 'golden': True},
                {'name': 'Wizard', 'golden': True},
                {'name': 'Paladin', 'golden': True}
            ],
            'enemy_band': [
                {'name': 'Ancient Behemoth', 'golden': False}
            ],
            'notes': 'Boss encounter. Guard forces you to attack it. Deals 2 damage to all enemies when damaged!'
        },
        {
            'name': 'Boss: Venomspawn',
            'description': 'Broodmother 6/20 (Death Toll: summon 2 Venomlings) + 3 Venomlings 2/2 (Death Toll: 3 dmg)',
            'player_band': [
                {'name': 'Paladin', 'golden': True},
                {'name': 'Paladin', 'golden': True},
                {'name': 'Wizard', 'golden': True},
                {'name': 'Wizard', 'golden': True}
            ],
            'enemy_band': [
                {'name': 'Venomling', 'golden': False},
                {'name': 'Venomling', 'golden': False},
                {'name': 'Broodmother', 'golden': False},
                {'name': 'Venomling', 'golden': False}
            ],
            'notes': 'Boss encounter. Broodmother summons 2 Venomlings when any enemy dies. Venomlings deal 3 damage on death.'
        },
        {
            'name': 'Boss: Greater Possessed',
            'description': '5 random minions each possessed (Death Toll spreads)',
            'player_band': [
                {'name': 'Wizard', 'golden': True},
                {'name': 'Wizard', 'golden': True},
                {'name': 'Paladin', 'golden': True},
                {'name': 'Paladin', 'golden': True},
                {'name': 'Soldier', 'golden': True}
            ],
            'enemy_band': [
                {'name': 'Soldier', 'golden': False, 'add_possessed_death_toll': True},
                {'name': 'Paladin', 'golden': False, 'add_possessed_death_toll': True},
                {'name': 'Huntsman', 'golden': False, 'add_possessed_death_toll': True},
                {'name': 'Farmer', 'golden': False, 'add_possessed_death_toll': True},
                {'name': 'Wizard', 'golden': False, 'add_possessed_death_toll': True}
            ],
            'notes': 'Boss encounter. 5 different minions each possessed by a Possessed. Death spreads possession to allies.'
        }
    ]
    return jsonify({'success': True, 'presets': presets})


# ===== TOOLTIP REVIEW ENDPOINTS =====

@dev_api.route('/tooltip-review/minions', methods=['GET'])
def get_minions_for_tooltip_review():
    """Get all minions with full raw data for tooltip review"""
    try:
        all_minions = get_all_minions()
        # Return minions with full data, sorted by tier then name
        sorted_minions = sorted(all_minions, key=lambda x: (x.get('tier', 1), x['name']))
        return jsonify({
            'success': True,
            'minions': sorted_minions,
            'total': len(sorted_minions)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@dev_api.route('/minion-info', methods=['GET'])
def get_minion_info():
    """Get FULL minion data for tooltips - includes all fields and summon-only tokens"""
    try:
        from minions import MINIONS
        import copy
        minion_info = {}

        # Include ALL minions with ALL fields, even summon-only tokens
        for tier, tier_minions in MINIONS.items():
            for minion in tier_minions:
                name = minion['name']
                # Deep copy the entire minion dict to preserve all effect fields
                minion_copy = copy.deepcopy(minion)
                # Ensure tier is set (some minions might not have it)
                minion_copy['tier'] = tier
                minion_info[name] = minion_copy

        return jsonify({
            'success': True,
            'minions': minion_info,
            'total': len(minion_info)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@dev_api.route('/tooltip-review/save', methods=['POST'])
def save_tooltip_review():
    """Save tooltip review to file"""
    try:
        import datetime
        import os

        data = request.json
        minion_name = data.get('minion_name')
        tier = data.get('tier')
        tooltip_reviews = data.get('tooltip_reviews', [])  # List of {keyword, status, correction}
        raw_data = data.get('raw_data', {})

        # Create reviews directory if it doesn't exist
        reviews_dir = os.path.join(os.path.dirname(__file__), 'tooltip_reviews')
        os.makedirs(reviews_dir, exist_ok=True)

        # Append to reviews file
        review_file = os.path.join(reviews_dir, 'tooltip_reviews.txt')

        with open(review_file, 'a', encoding='utf-8') as f:
            timestamp = datetime.datetime.now().isoformat()
            f.write(f"\n{'='*80}\n")
            f.write(f"Timestamp: {timestamp}\n")
            f.write(f"Minion: {minion_name} (Tier {tier})\n")
            f.write(f"\n--- Tooltip Reviews ---\n")

            for review in tooltip_reviews:
                keyword = review.get('keyword', 'Unknown')
                status = review.get('status', 'unknown')
                correction = review.get('correction', '')

                f.write(f"\n  {keyword.upper()}: {status.upper()}\n")
                if correction:
                    f.write(f"  Correction: {correction}\n")

            f.write(f"\n--- Raw Minion Data ---\n")
            f.write(f"{raw_data}\n")
            f.write(f"{'='*80}\n")

        return jsonify({
            'success': True,
            'message': f'Review saved for {minion_name}',
            'file': review_file
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@dev_api.route('/heroes', methods=['GET'])
def get_heroes():
    """Get all available heroes with starting minion data for display"""
    try:
        from flask import session
        from hero_definitions import get_all_heroes, get_hero_starting_minions
        from minions import get_minion_by_name
        from models import Player

        # Get player's equipped images if logged in
        equipped_images = {}
        player_id = session.get('player_id')
        if player_id:
            player = Player.query.get(player_id)
            if player:
                equipped_images = player.get_equipped_images()

        heroes = get_all_heroes()
        enriched_heroes = []

        for hero in heroes:
            hero_copy = hero.copy()
            minion_names = get_hero_starting_minions(hero['id'])

            # Get minion details for display
            starting_minions = []
            for name in minion_names:
                template = get_minion_by_name(name)
                if template:
                    image_filename = template.get('image', '')
                    # Determine image_path based on player's equipped images
                    if image_filename:
                        minion_id = image_filename.replace('.png', '')
                        if minion_id in equipped_images:
                            image_path = f"images/{equipped_images[minion_id]}/{image_filename}"
                        else:
                            image_path = f"images/original/{image_filename}"
                    else:
                        image_path = None

                    starting_minions.append({
                        'name': template['name'],
                        'attack': template['attack'],
                        'health': template['health'],
                        'type': template.get('type', 'None'),
                        'image': image_filename,
                        'image_path': image_path,
                        'keywords': template.get('keywords', []),
                        'tier': template.get('tier', 1),
                        'rarity': template.get('rarity', 'common')
                    })

            hero_copy['starting_minions'] = starting_minions
            enriched_heroes.append(hero_copy)

        return jsonify({
            'success': True,
            'heroes': enriched_heroes,
            'total': len(enriched_heroes)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500