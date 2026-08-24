"""
Dev Events Routes - Event testing and spoofing for development

Allows developers to:
- Spoof any event type and test its display
- Preview event icons
- Test event selection screens
- Simulate different ring levels and positions
- Test story event flows
"""

from flask import Blueprint, request, jsonify
from event_registry import (
    ALL_EVENTS_REGISTRY,
    BASIC_GAMEPLAY_EVENTS,
    STORY_EVENTS,
    BELL_TOWER_SUB_EVENTS,
    CROSSROADS_EVENTS,
    CROSSROADS_SUB_EVENTS,
    FEY_ZONE_EVENTS,
    CONSTRUCT_ZONE_EVENTS,
    CULT_ZONE_EVENTS,
    CULT_ZONE_SUB_EVENTS,
    UNDEAD_ZONE_EVENTS,
    UNDEAD_ZONE_SUB_EVENTS,
    BEAST_WILDLANDS_EVENTS,
    BEAST_WILDLANDS_SUB_EVENTS,
    list_all_event_ids
)
from config import RING_EVENTS, DEFAULT_RING_PATTERN, ZONES, EVENT_SCALING, MAX_BAND_SIZE
from lucide_icons import generate_lucide_svg
from minions import get_all_minions, get_minion_by_name, create_minion_instance
import copy
import uuid

dev_events_api = Blueprint('dev_events_api', __name__)
# Restrict all dev event endpoints to localhost
from rate_limit import localhost_only
dev_events_api.before_request(localhost_only)

# Store active dev event sessions
DEV_EVENT_SESSIONS = {}


class MockRun:
    """
    Mock Run object for dev event mode

    Simulates a game run with configurable state for testing events
    """

    def __init__(self, ring=1, position=5, zone='starting_plains', gold=10, health=100, band=None):
        self.id = str(uuid.uuid4())
        self.current_ring = ring
        self.ring_position = position
        self.current_zone = zone
        self.health = health
        self.max_health = 100
        self.events_count = 0
        self.ghost_wins = 0
        self.is_active = True
        self._dev_mode_mock = True
        self.selection_version = 0

        # Ghost battle tracking (for combat compatibility)
        self.upcoming_ghost_id = None
        self.ring_upgrade_steps = 0

        # Resources
        self._gold = gold
        self._rerolls = 0

        # Band
        self._band = band or []

        # Event state for story events
        self._event_state = {}

        # Pending selection
        self._pending_selection = None

        # Hero effects
        self._hero_effects = {}

    def get_resources(self):
        return {
            'gold': self._gold,
            'rerolls': self._rerolls,
            'health': self.health,
            'max_health': self.max_health
        }

    def set_resources(self, resources):
        if 'gold' in resources:
            self._gold = resources['gold']
        if 'rerolls' in resources:
            self._rerolls = resources['rerolls']
        if 'health' in resources:
            self.health = resources['health']

    def get_gold(self):
        return self._gold

    def set_gold(self, amount):
        self._gold = max(0, amount)

    def add_gold(self, amount):
        self._gold += amount

    def spend_gold(self, amount):
        if self._gold >= amount:
            self._gold -= amount
            return True
        return False

    def get_band(self):
        return self._band

    def set_band(self, band):
        self._band = band

    def get_event_state(self):
        return self._event_state

    def set_event_state(self, state):
        self._event_state = state

    def get_pending_selection(self):
        return self._pending_selection

    def set_pending_selection(self, selection):
        self._pending_selection = selection

    def has_pending_selection(self):
        return self._pending_selection is not None

    def get_hero_effects(self):
        return self._hero_effects

    def set_hero_effects(self, effects):
        self._hero_effects = effects

    def to_dict(self):
        from config import EVENTS_FOR_GHOST_BATTLE
        next_ghost_milestone = ((self.events_count // EVENTS_FOR_GHOST_BATTLE) + 1) * EVENTS_FOR_GHOST_BATTLE
        return {
            'id': self.id,
            'current_ring': self.current_ring,
            'ring_position': self.ring_position,
            'current_zone': self.current_zone,
            'health': self.health,
            'max_health': self.max_health,
            'gold': self._gold,
            'rerolls': self._rerolls,
            'events_count': self.events_count,
            'ghost_wins': self.ghost_wins,
            'upcoming_ghost_milestone': next_ghost_milestone,
            'steps_until_ghost': next_ghost_milestone - self.events_count,
            'band': self._band,
            'band_size': len(self._band),
            'event_state': self._event_state,
            'hero_effects': self._hero_effects
        }


class DevEventSession:
    """Dev event testing session"""

    def __init__(self, session_id):
        self.id = session_id
        self.mock_run = None
        self.current_event_type = None
        self.event_result = None
        self.selection_data = None

    def create_mock_run(self, config):
        """Create a mock run with specified configuration"""
        band = []
        if config.get('band'):
            for minion_config in config['band']:
                minion = create_dev_minion(minion_config)
                band.append(minion)

        self.mock_run = MockRun(
            ring=config.get('ring', 1),
            position=config.get('position', 5),
            zone=config.get('zone', 'starting_plains'),
            gold=config.get('gold', 10),
            health=config.get('health', 100),
            band=band
        )

        # Set hero effects if provided
        if config.get('hero_effects'):
            self.mock_run.set_hero_effects(config['hero_effects'])

        # Set event state if provided (for story events like bell tower)
        if config.get('event_state'):
            self.mock_run.set_event_state(config['event_state'])

        return self.mock_run


def create_dev_minion(minion_config):
    """Create a minion for dev event testing"""
    name = minion_config.get('name')
    template = get_minion_by_name(name)

    if not template:
        # Create a placeholder minion
        return {
            'name': name or 'Unknown',
            'health': minion_config.get('health', 5),
            'attack': minion_config.get('attack', 3),
            'golden': minion_config.get('golden', False),
            'keywords': minion_config.get('keywords', []),
            'tier': minion_config.get('tier', 1),
            'type': minion_config.get('type', 'Unknown'),
            'band_id': str(uuid.uuid4()),
            'position': 0
        }

    minion = create_minion_instance(template, assign_band_id=True)

    # Apply overrides
    if 'health' in minion_config:
        minion['health'] = minion_config['health']
    if 'attack' in minion_config:
        minion['attack'] = minion_config['attack']
    if 'golden' in minion_config:
        minion['golden'] = minion_config['golden']
        if minion_config['golden'] and not minion_config.get('skip_golden_bonus'):
            minion['health'] *= 2
            minion['attack'] *= 2

    return minion


# ==================== API ENDPOINTS ====================

@dev_events_api.route('/events/list', methods=['GET'])
def list_events():
    """Get all available events organized by category"""
    try:
        # Build comprehensive event list
        events = {
            'basic_gameplay': {},
            'story': {},
            'crossroads': {},
            'fey_zone': {},
            'construct_zone': {},
            'cult_zone': {},
            'undead_zone': {},
            'beast_wildlands': {},
        }

        # Basic gameplay events
        for event_id, entry in BASIC_GAMEPLAY_EVENTS.items():
            events['basic_gameplay'][event_id] = {
                'id': event_id,
                'category': entry.get('category', 'unknown'),
                'description': entry.get('description', ''),
                'screens': entry.get('screens', 1),
                'modular': entry.get('modular', False),
                'icon': get_event_icon(event_id)
            }

        # Story events (bell_tower)
        for event_id, entry in STORY_EVENTS.items():
            events['story'][event_id] = {
                'id': event_id,
                'visit_rule': entry.get('visit_rule', 'repeatable'),
                'description': entry.get('description', ''),
                'flow': entry.get('flow', ''),
                'screens': entry.get('screens', 1),
                'modular': entry.get('modular', False),
                'sub_events': entry.get('sub_events', []),
                'state_tracking': entry.get('state_tracking', {}),
                'icon': get_event_icon(event_id)
            }

        # Crossroads events
        for event_id, entry in CROSSROADS_EVENTS.items():
            events['crossroads'][event_id] = {
                'id': event_id,
                'category': entry.get('category', 'crossroads'),
                'description': entry.get('description', ''),
                'flow': entry.get('flow', ''),
                'screens': entry.get('screens', 1),
                'modular': entry.get('modular', False),
                'sub_events': entry.get('sub_events', []),
                'conditions': entry.get('conditions', {}),
                'icon': get_event_icon(event_id)
            }

        # Fey zone events
        for event_id, entry in FEY_ZONE_EVENTS.items():
            events['fey_zone'][event_id] = {
                'id': event_id,
                'category': entry.get('category', 'zone_fey'),
                'visit_rule': entry.get('visit_rule', 'repeatable'),
                'description': entry.get('description', ''),
                'flow': entry.get('flow', ''),
                'screens': entry.get('screens', 1),
                'modular': entry.get('modular', False),
                'state_tracking': entry.get('state_tracking', {}),
                'icon': get_event_icon(event_id)
            }

        # Construct zone events
        for event_id, entry in CONSTRUCT_ZONE_EVENTS.items():
            events['construct_zone'][event_id] = {
                'id': event_id,
                'category': entry.get('category', 'zone_construct'),
                'visit_rule': entry.get('visit_rule', 'repeatable'),
                'forced_event': entry.get('forced_event', False),
                'description': entry.get('description', ''),
                'flow': entry.get('flow', ''),
                'screens': entry.get('screens', 1),
                'modular': entry.get('modular', False),
                'conditions': entry.get('conditions', {}),
                'icon': get_event_icon(event_id)
            }

        # Cult zone events
        for event_id, entry in CULT_ZONE_EVENTS.items():
            events['cult_zone'][event_id] = {
                'id': event_id,
                'category': entry.get('category', 'zone_cult'),
                'visit_rule': entry.get('visit_rule', 'repeatable'),
                'description': entry.get('description', ''),
                'flow': entry.get('flow', ''),
                'screens': entry.get('screens', 1),
                'modular': entry.get('modular', False),
                'sub_events': entry.get('sub_events', []),
                'state_tracking': entry.get('state_tracking', {}),
                'icon': get_event_icon(event_id)
            }

        # Undead zone events
        for event_id, entry in UNDEAD_ZONE_EVENTS.items():
            events['undead_zone'][event_id] = {
                'id': event_id,
                'category': entry.get('category', 'zone_undead'),
                'visit_rule': entry.get('visit_rule', 'repeatable'),
                'description': entry.get('description', ''),
                'flow': entry.get('flow', ''),
                'screens': entry.get('screens', 1),
                'modular': entry.get('modular', False),
                'sub_events': entry.get('sub_events', []),
                'state_tracking': entry.get('state_tracking', {}),
                'icon': get_event_icon(event_id)
            }

        # Beast Wildlands zone events
        for event_id, entry in BEAST_WILDLANDS_EVENTS.items():
            events['beast_wildlands'][event_id] = {
                'id': event_id,
                'category': entry.get('category', 'zone_beast'),
                'visit_rule': entry.get('visit_rule', 'repeatable'),
                'description': entry.get('description', ''),
                'flow': entry.get('flow', ''),
                'screens': entry.get('screens', 1),
                'modular': entry.get('modular', False),
                'sub_events': entry.get('sub_events', []),
                'state_tracking': entry.get('state_tracking', {}),
                'icon': get_event_icon(event_id)
            }

        # Beast Wildlands sub-events
        for event_id, entry in BEAST_WILDLANDS_SUB_EVENTS.items():
            events['beast_wildlands'][event_id] = {
                'id': event_id,
                'parent_event': entry.get('parent_event', ''),
                'description': entry.get('description', ''),
                'boss_id': entry.get('boss_id', ''),
                'tier': entry.get('tier', 1),
                'icon': get_event_icon(event_id)
            }

        return jsonify({
            'success': True,
            'events': events,
            'all_event_ids': list_all_event_ids(),
            'total': len(list_all_event_ids())
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@dev_events_api.route('/events/icons', methods=['GET'])
def get_all_event_icons():
    """Get all event icons for preview"""
    try:
        icons = {}

        # Event type to icon mapping
        event_icons = {
            'minion_event': ('gift', 'Free Minion'),
            'buff_event': ('sparkles', 'Blessing'),
            'combat_event': ('swords', 'Combat'),
            'combat_event_hard': ('skull', 'Hard Combat'),
            'shop_event': ('store', 'Tavern'),
            'statue': ('ferris-wheel', 'Ancient Statue'),
            'zone_portal': ('signpost', 'Zone Portal'),
            'bell_tower': ('bell', 'Bell Tower'),
            'ancient_shrine': ('church', 'Ancient Shrine'),
            'mysterious_merchant': ('shopping-cart', 'Mysterious Merchant'),
            'guardian_trial': ('shield', 'Guardian Trial'),
            'cursed_fountain': ('droplet', 'Cursed Fountain'),
            'split_event': ('git-branch', 'Split Path'),
            'branching_choice': ('git-merge', 'Branching Choice'),
        }

        for event_id, (icon_name, display_name) in event_icons.items():
            icons[event_id] = {
                'icon_name': icon_name,
                'display_name': display_name,
                'svg': generate_lucide_svg(icon_name, width=32, height=32),
                'svg_small': generate_lucide_svg(icon_name, width=24, height=24)
            }

        return jsonify({
            'success': True,
            'icons': icons
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@dev_events_api.route('/events/create', methods=['POST'])
def create_dev_event():
    """Create a dev event session and trigger a specific event

    If session_id is provided, reuses existing session's MockRun (state persists).
    Otherwise creates a new session with fresh MockRun.
    """
    try:
        data = request.get_json()
        event_type = data.get('event_type')
        run_config = data.get('run_config', {})
        existing_session_id = data.get('session_id')  # Optional: reuse existing session

        if not event_type:
            return jsonify({'success': False, 'error': 'event_type required'}), 400

        # Check if we should reuse an existing session
        if existing_session_id and existing_session_id in DEV_EVENT_SESSIONS:
            # Reuse existing session - state persists across events
            session = DEV_EVENT_SESSIONS[existing_session_id]
            session_id = existing_session_id
            mock_run = session.mock_run

            # Clear any pending selection from previous event
            mock_run.set_pending_selection(None)
        else:
            # Create new session with fresh MockRun
            session_id = str(uuid.uuid4())
            session = DevEventSession(session_id)
            mock_run = session.create_mock_run(run_config)

        # Store current event type
        session.current_event_type = event_type

        # Create the event selection
        from game_engine.events.event_system import EventSystem
        result = EventSystem.create_event_selection(mock_run, event_type)

        session.event_result = result
        session.selection_data = mock_run.get_pending_selection()

        DEV_EVENT_SESSIONS[session_id] = session

        return jsonify({
            'success': True,
            'session_id': session_id,
            'event_type': event_type,
            'event_result': result,
            'selection_data': session.selection_data,
            'run_state': mock_run.to_dict(),
            'continued_session': existing_session_id is not None,
            'message': f'Event {event_type} created successfully'
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@dev_events_api.route('/events/<session_id>/select', methods=['POST'])
def resolve_event_selection(session_id):
    """Resolve a selection in a dev event session"""
    try:
        session = DEV_EVENT_SESSIONS.get(session_id)
        if not session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        data = request.get_json()
        selections = data.get('selections', [])

        # Check if this is a combat selection (regular or boss combat)
        pending = session.mock_run.get_pending_selection()
        if pending and pending.get('event_type') in ('combat', 'boss_combat'):
            # Handle combat selection using CombatSystem
            from game_engine.combat_system import CombatSystem

            if len(selections) != 1:
                return jsonify({'success': False, 'error': 'Must select exactly one combat option'}), 400

            result = CombatSystem.resolve_combat_selection(session.mock_run, selections[0])
        else:
            # Use the selection system to resolve non-combat events
            from game_engine.selection_system import SelectionSystem
            result = SelectionSystem.resolve_selection(session.mock_run, selections)

        # Get updated selection data (for multi-step events)
        new_selection = session.mock_run.get_pending_selection()

        return jsonify({
            'success': True,
            'result': result,
            'new_selection': new_selection,
            'run_state': session.mock_run.to_dict(),
            'has_pending_selection': new_selection is not None
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@dev_events_api.route('/events/<session_id>/state', methods=['GET'])
def get_event_state(session_id):
    """Get current state of a dev event session"""
    try:
        session = DEV_EVENT_SESSIONS.get(session_id)
        if not session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        return jsonify({
            'success': True,
            'event_type': session.current_event_type,
            'selection_data': session.mock_run.get_pending_selection(),
            'run_state': session.mock_run.to_dict()
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@dev_events_api.route('/events/<session_id>/update-run', methods=['POST'])
def update_run_state(session_id):
    """Update the mock run state"""
    try:
        session = DEV_EVENT_SESSIONS.get(session_id)
        if not session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        data = request.get_json()

        # Update run properties
        if 'ring' in data:
            session.mock_run.current_ring = data['ring']
        if 'position' in data:
            session.mock_run.ring_position = data['position']
        if 'zone' in data:
            session.mock_run.current_zone = data['zone']
        if 'gold' in data:
            session.mock_run.set_gold(data['gold'])
        if 'health' in data:
            session.mock_run.health = data['health']
        if 'event_state' in data:
            session.mock_run.set_event_state(data['event_state'])

        return jsonify({
            'success': True,
            'run_state': session.mock_run.to_dict()
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@dev_events_api.route('/events/ring-preview', methods=['GET'])
def get_ring_preview():
    """Get a preview of events on a ring at a given level"""
    try:
        ring = request.args.get('ring', 1, type=int)
        zone = request.args.get('zone', 'starting_plains')

        # Get ring events
        from config import ZONE_RING_EVENTS

        # Check for zone-specific events first
        if zone in ZONE_RING_EVENTS and ring in ZONE_RING_EVENTS[zone]:
            events = ZONE_RING_EVENTS[zone][ring]
        elif ring in RING_EVENTS:
            events = RING_EVENTS[ring]
        else:
            events = DEFAULT_RING_PATTERN

        # Build preview data for each position
        ring_preview = []
        for position, event in enumerate(events):
            preview = {
                'position': position,
                'raw_event': event if isinstance(event, str) else str(type(event).__name__)
            }

            if isinstance(event, str):
                # Simple event type
                preview['type'] = 'simple'
                preview['event_type'] = event
                preview['icon'] = get_event_icon(event)
                preview['display_name'] = get_event_display_name(event)

            elif isinstance(event, list):
                # Split event
                preview['type'] = 'split'
                preview['options'] = [
                    {
                        'event_type': e,
                        'icon': get_event_icon(e),
                        'display_name': get_event_display_name(e)
                    }
                    for e in event
                ]
                preview['icon'] = get_event_icon('split_event')
                preview['display_name'] = 'Split Path'

            elif isinstance(event, dict) and event.get('type') == 'branching_choice':
                # Branching choice
                preview['type'] = 'branching_choice'
                preview['title'] = event.get('title', 'Choose Your Path')
                preview['description'] = event.get('description', '')
                preview['choices'] = event.get('choices', [])
                preview['icon'] = get_event_icon('branching_choice')
                preview['display_name'] = event.get('title', 'Branching Choice')

            ring_preview.append(preview)

        return jsonify({
            'success': True,
            'ring': ring,
            'zone': zone,
            'positions': ring_preview,
            'total_positions': len(ring_preview)
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@dev_events_api.route('/events/scaling-preview', methods=['GET'])
def get_event_scaling_preview():
    """Preview how an event scales across different rings"""
    try:
        event_type = request.args.get('event_type', 'buff_event')

        scaling_preview = []

        for ring in range(1, 5):
            preview = {
                'ring': ring,
                'event_type': event_type
            }

            # Get scaling config
            scaling_config = EVENT_SCALING.get(event_type, {})

            if 'health_options' in scaling_config:
                # Buff event scaling
                ring_bonus = ring - 1
                health_opts = scaling_config.get('health_options', [3, 0, 1])
                attack_opts = scaling_config.get('attack_options', [0, 2, 1])

                preview['buff_options'] = [
                    {
                        'name': f'+{health_opts[0] + ring_bonus} Health',
                        'type': 'health',
                        'amount': health_opts[0] + ring_bonus
                    },
                    {
                        'name': f'+{attack_opts[1] + ring_bonus} Attack',
                        'type': 'attack',
                        'amount': attack_opts[1] + ring_bonus
                    },
                    {
                        'name': f'+{health_opts[2] + ring_bonus}/+{attack_opts[2] + ring_bonus}',
                        'type': 'both',
                        'health': health_opts[2] + ring_bonus,
                        'attack': attack_opts[2] + ring_bonus
                    }
                ]

            elif 'band_size_base' in scaling_config:
                # Combat event scaling
                band_size_base = scaling_config.get('band_size_base', 2)
                band_size_per_ring = scaling_config.get('band_size_per_ring', 0.5)
                enemy_band_size = int(band_size_base + (ring - 1) * band_size_per_ring)

                preview['combat_info'] = {
                    'difficulty': scaling_config.get('difficulty', 'normal'),
                    'enemy_band_size': enemy_band_size,
                    'tier': min(ring, 3)
                }

            elif 'base_cost' in scaling_config:
                # Shop event scaling
                base_cost = scaling_config.get('base_cost', 5)
                cost_per_ring = scaling_config.get('cost_per_ring', 3)

                preview['shop_info'] = {
                    'cost_range': f'{base_cost} - {base_cost + cost_per_ring * ring}',
                    'num_offers': scaling_config.get('num_offers', 4),
                    'uses_multi_tier': scaling_config.get('uses_multi_tier', True)
                }

            scaling_preview.append(preview)

        return jsonify({
            'success': True,
            'event_type': event_type,
            'scaling_config': EVENT_SCALING.get(event_type, {}),
            'ring_previews': scaling_preview
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@dev_events_api.route('/zones', methods=['GET'])
def get_zones():
    """Get all available zones"""
    try:
        zones_data = {}
        for zone_id, zone_info in ZONES.items():
            zones_data[zone_id] = {
                'id': zone_id,
                'name': zone_info.get('name', zone_id),
                'description': zone_info.get('description', ''),
                'pool_modifiers': zone_info.get('pool_modifiers'),
                'connects_to': zone_info.get('connects_to', []),
                'theme_color': zone_info.get('theme_color', '#888888'),
                'icon': zone_info.get('icon', '')
            }

        return jsonify({
            'success': True,
            'zones': zones_data
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@dev_events_api.route('/minions', methods=['GET'])
def get_minions_for_band():
    """Get all minions for band setup"""
    try:
        all_minions = get_all_minions()
        minion_list = []

        for minion in all_minions:
            minion_list.append({
                'name': minion['name'],
                'health': minion['health'],
                'attack': minion['attack'],
                'keywords': minion.get('keywords', []),
                'tier': minion.get('tier', 1),
                'type': minion.get('type', 'Unknown')
            })

        minion_list.sort(key=lambda x: (x['tier'], x['name']))

        return jsonify({
            'success': True,
            'minions': minion_list,
            'total': len(minion_list)
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== HELPER FUNCTIONS ====================

def get_event_icon(event_type):
    """Get the icon name for an event type"""
    icon_map = {
        'minion_event': 'gift',
        'buff_event': 'sparkles',
        'combat_event': 'swords',
        'combat_event_hard': 'skull',
        'shop_event': 'store',
        'statue': 'ferris-wheel',
        'zone_portal': 'signpost',
        'bell_tower': 'bell',
        'ancient_shrine': 'church',
        'mysterious_merchant': 'shopping-cart',
        'guardian_trial': 'shield',
        'cursed_fountain': 'droplet',
        'bell_tower_blessing': 'bell',
        'bell_tower_combat': 'swords',
        'bell_tower_quasimodo': 'user',
        'golden_statue': 'ferris-wheel',
        'traveling_merchant': 'shopping-cart',
        'bandit_ambush': 'swords',
        'elite_encounter': 'star',
        'split_event': 'git-branch',
        'branching_choice': 'git-merge',
        # Crossroads events
        'mercenary_camp': 'tent',
        'collapsed_mine': 'pickaxe',
        'vast_kennels': 'paw-print',
        'watchtower': 'tower-control',
        # Crossroads sub-events
        'mercenary_camp_hire_guard': 'shield-plus',
        'mercenary_camp_duel': 'sword',
        'mercenary_camp_duel_victory': 'coins',
        'mercenary_camp_takeover': 'swords',
        'mercenary_camp_takeover_victory': 'trophy',
        'kennels_buy_hound': 'dog',
        'kennels_buy_cat': 'cat',
        'watchtower_storm': 'swords',
        'watchtower_storm_victory': 'sparkles',
        'watchtower_aid': 'hand-helping',
        # Fey zone events
        'ivory_tower': 'castle',
        'ivory_tower_sacrifice': 'trash-2',
        # Construct zone events
        'grand_city': 'building',
        'grand_city_golden_forge': 'sparkles',
        'scrap_heap': 'trash',
        # Cult zone events
        'the_red_gate': 'door-open',
        'red_gate_abandon_strength': 'sword-off',
        'red_gate_abandon_vigor': 'heart-off',
        'red_gate_abandon_skill': 'zap-off',
        'red_gate_abandon_allegiance': 'users-minus',
        # Undead zone events
        'the_great_work': 'skull',
        'great_work_search_graves': 'search',
        'great_work_mark_scrolls': 'scroll',
        'great_work_count_blessings': 'sparkles',
        # Beast Wildlands zone events
        'the_great_hunt': 'crosshair',
        'great_hunt_take_bounty': 'target',
        'great_hunt_boss_encounter': 'skull',
        'great_hunt_boss_victory': 'trophy',
    }
    return icon_map.get(event_type, 'help-circle')


def get_event_display_name(event_type):
    """Get the display name for an event type"""
    name_map = {
        'minion_event': 'Free Minion',
        'buff_event': 'Blessing',
        'combat_event': 'Combat',
        'combat_event_hard': 'Hard Combat',
        'shop_event': 'Tavern',
        'statue': 'Ancient Statue',
        'zone_portal': 'Zone Portal',
        'bell_tower': 'Bell Tower',
        'ancient_shrine': 'Ancient Shrine',
        'mysterious_merchant': 'Mysterious Merchant',
        'guardian_trial': 'Guardian Trial',
        'cursed_fountain': 'Cursed Fountain',
        'bell_tower_blessing': 'Bell Blessing',
        'bell_tower_combat': 'Bell Combat',
        'bell_tower_quasimodo': 'Quasimodo',
        'golden_statue': 'Golden Statue',
        'traveling_merchant': 'Traveling Merchant',
        'bandit_ambush': 'Bandit Ambush',
        'elite_encounter': 'Elite Encounter',
        # Crossroads events
        'mercenary_camp': 'Mercenary Camp',
        'collapsed_mine': 'Collapsed Mine',
        'vast_kennels': 'Vast Kennels',
        'watchtower': 'Watchtower',
        # Crossroads sub-events
        'mercenary_camp_hire_guard': 'Hire Guard',
        'mercenary_camp_duel': 'Mercenary Duel',
        'mercenary_camp_duel_victory': 'Duel Victory',
        'mercenary_camp_takeover': 'Hostile Takeover',
        'mercenary_camp_takeover_victory': 'Takeover Victory',
        'kennels_buy_hound': 'Buy War Hound',
        'kennels_buy_cat': 'Buy Alley Cat',
        'watchtower_storm': 'Storm Tower',
        'watchtower_storm_victory': 'Tower Victory',
        'watchtower_aid': 'Request Aid',
        # Fey zone events
        'ivory_tower': 'Ivory Tower',
        'ivory_tower_sacrifice': 'Sacrifice to Seal',
        # Construct zone events
        'grand_city': 'Grand City',
        'grand_city_golden_forge': 'Golden Forge',
        'scrap_heap': 'Scrap Heap',
        # Cult zone events
        'the_red_gate': 'The Red Gate',
        'red_gate_abandon_strength': 'Abandon Strength',
        'red_gate_abandon_vigor': 'Abandon Vigor',
        'red_gate_abandon_skill': 'Abandon Skill',
        'red_gate_abandon_allegiance': 'Abandon Allegiance',
        # Undead zone events
        'the_great_work': 'The Great Work',
        'great_work_search_graves': 'Search the Graves',
        'great_work_mark_scrolls': 'Mark the Scrolls',
        'great_work_count_blessings': 'Count Your Blessings',
        # Beast Wildlands zone events
        'the_great_hunt': 'The Great Hunt',
        'great_hunt_take_bounty': 'Take Bounty',
        'great_hunt_boss_encounter': 'Boss Encounter',
        'great_hunt_boss_victory': 'Boss Victory',
    }
    return name_map.get(event_type, event_type.replace('_', ' ').title())
