import random
import copy
from config import RING_EVENTS, DEFAULT_RING_PATTERN, RING_SIZE, MAX_COMBAT_ROUNDS, RESET_HEALTH_AFTER_COMBAT, \
    MAX_BAND_SIZE
from keywords import apply_combat_keywords, has_keyword, validate_keywords
from minions import generate_minion, create_golden_minion, can_combine_minions, validate_minion
from game_engine.game_controller import GameController
from game_engine.events.event_system import EventSystem
from game_engine.selection_system import SelectionSystem
from game_engine.combat_system import CombatSystem
from game_engine.band_manager import BandManager
from game_engine.zone_controller import ZoneController
from game_engine.sub_ring_controller import SubRingController


class GameLogic:

    @staticmethod
    def get_ring_events(ring_level, zone=None):
        """Get the event sequence for a given ring"""
        return GameController.get_ring_events(ring_level, zone=zone)

    @staticmethod
    def get_current_event(run):
        """Get the current event type based on ring and position, including zone portals and sub-rings"""
        # Check if we're in a sub-ring
        if SubRingController.is_in_sub_ring(run):
            return SubRingController.get_current_sub_ring_event(run)

        # Check if current position is a portal in this zone
        if ZoneController.is_portal_position(run, run.ring_position):
            return 'zone_portal'

        # Otherwise get regular ring event
        zone = getattr(run, 'current_zone', None)
        events = GameController.get_ring_events(run.current_ring, zone=zone)
        event = events[run.ring_position % len(events)]

        # Check if it's a branching choice
        if isinstance(event, dict) and event.get('type') == 'branching_choice':
            return 'branching_choice'

        # Check if it's a split event (list of events)
        if isinstance(event, list):
            return 'split_event'

        return event

    @staticmethod
    def create_event_selection(run, event_type):
        """Create a selection for an event instead of immediately processing it"""
        # Handle zone portal events
        if event_type == 'zone_portal':
            return GameLogic._create_zone_portal_selection(run)

        # Handle branching choice events
        if event_type == 'branching_choice':
            return GameLogic._create_branching_choice_selection(run)

        return EventSystem.create_event_selection(run, event_type)

    @staticmethod
    def _create_branching_choice_selection(run):
        """Create a selection for branching choice events"""
        return EventSystem._create_branching_choice_selection(run)

    @staticmethod
    def _create_zone_portal_selection(run):
        """Create a selection for zone portal travel"""
        available_destinations = ZoneController.get_available_destinations(run)

        if not available_destinations:
            # Shouldn't happen, but fallback to regular event
            return {
                'event_type': 'zone_portal',
                'message': 'Portal is inactive.',
                'band_changes': [],
                'resource_changes': {}
            }

        # Create portal selection
        options = []
        for destination in available_destinations:
            zone_key = destination['zone_key']
            zone_data = destination['zone_data']

            options.append({
                'type': 'travel_to_zone',
                'zone_key': zone_key,
                'zone_data': zone_data,
                'message': f"Travel to {zone_data['name']}",
                'description': zone_data.get('description', 'A mysterious land...'),
                'id': f'travel_{zone_key}'
            })

        # Add option to stay in current zone (continue around ring)
        current_zone_data = ZoneController.get_current_zone_data(run)
        options.append({
            'type': 'stay_in_zone',
            'message': f"Stay in {current_zone_data['name']}",
            'description': 'Continue exploring this area',
            'id': 'stay'
        })

        selection = {
            'event_type': 'zone_portal',
            'title': 'Zone Portal',
            'message': 'A shimmering portal appears before you. Where will you go?',
            'current_zone': run.current_zone,
            'available_destinations': available_destinations,
            'options': options,
            'min_selections': 1,
            'max_selections': 1
        }

        run.set_pending_selection(selection)
        return {
            'event_type': 'zone_portal',
            'message': 'Zone portal discovered!',
            'selection_created': True,
            'band_changes': [],
            'resource_changes': {}
        }

    @staticmethod
    def _find_combinable_pairs(band):
        """Find pairs of minions that can be combined (same name, both not golden)"""
        return EventSystem._find_combinable_pairs(band)

    @staticmethod
    def _create_golden_minion(minion1, minion2):
        """Create a golden minion by combining two identical minions"""
        return EventSystem._create_golden_minion(minion1, minion2)

    @staticmethod
    def _validate_combine_selection(band, selected_indices):
        """Validate that the selected minions can be combined"""
        return EventSystem._validate_combine_selection(band, selected_indices)

    @staticmethod
    def _get_event_title(event_type):
        """Get user-friendly title for event"""
        return EventSystem._get_event_title(event_type)

    @staticmethod
    def _get_event_display_name(event_type):
        """Get display name for events in split selections"""
        return EventSystem._get_event_display_name(event_type)

    @staticmethod
    def _get_event_description(event_type):
        """Get description for events in split selections"""
        return EventSystem._get_event_description(event_type)

    @staticmethod
    def _get_combat_title(event_type):
        """Get combat title based on difficulty"""
        return EventSystem._get_combat_title(event_type)

    @staticmethod
    def resolve_selection(run, selection_ids):
        """Resolve player's selection choices, including zone travel and branching choices"""
        pending = run.get_pending_selection()

        # Handle zone portal selections
        if pending and pending.get('event_type') == 'zone_portal':
            return GameLogic._resolve_zone_portal_selection(run, selection_ids)

        # Handle branching choice selections
        if pending and pending.get('event_type') == 'branching_choice':
            return GameLogic._resolve_branching_choice_selection(run, selection_ids)

        return SelectionSystem.resolve_selection(run, selection_ids)

    @staticmethod
    def _resolve_branching_choice_selection(run, selection_ids):
        """Resolve branching choice selection with fixed sub-ring positioning"""
        if len(selection_ids) != 1:
            return {'error': 'Must select exactly one choice'}

        pending = run.get_pending_selection()
        selection_id = selection_ids[0]

        # Find the selected option
        selected_option = None
        for option in pending['options']:
            if option['id'] == selection_id:
                selected_option = option
                break

        if not selected_option:
            return {'error': 'Invalid selection'}

        choice_data = selected_option['choice_data']
        choice_type = selected_option['choice_type']

        if choice_type == 'immediate':
            # Immediate event - process it right now and stay on main ring
            immediate_event = choice_data['event']

            # Clear the choice selection
            run.set_pending_selection(None)

            # Create the immediate event selection
            event_result = EventSystem.create_event_selection(run, immediate_event)

            return {
                'success': True,
                'results': [f'Chose: {choice_data["name"]} - {choice_data["description"]}'],
                'event_result': event_result,
                'immediate_event': immediate_event,
                'band_changes': [],
                'resource_changes': {}
            }

        elif choice_type == 'sub_ring':
            # Sub-ring path - enter a sub-ring with fixed positioning
            template_name = choice_data['template']

            try:
                # Create the sub-ring with current position as entry point
                entry_position = run.ring_position
                sub_ring_data = SubRingController.create_sub_ring(template_name, entry_position)

                # Enter the sub-ring
                SubRingController.enter_sub_ring(run, sub_ring_data, entry_position)

                # Clear the choice selection
                run.set_pending_selection(None)

                # Create selection for first sub-ring event
                first_event = SubRingController.get_current_sub_ring_event(run)
                event_result = EventSystem.create_event_selection(run, first_event)

                return {
                    'success': True,
                    'results': [f'Chose: {choice_data["name"]} - Entering {sub_ring_data["name"]}!'],
                    'event_result': event_result,
                    'sub_ring_entered': sub_ring_data,
                    'band_changes': [],
                    'resource_changes': {}
                }

            except Exception as e:
                return {'error': f'Failed to create sub-ring: {str(e)}'}

        return {'error': 'Unknown choice type'}

    @staticmethod
    def _resolve_zone_portal_selection(run, selection_ids):
        """Resolve zone portal travel selection"""
        if len(selection_ids) != 1:
            return {'error': 'Must select exactly one option'}

        pending = run.get_pending_selection()
        selection_id = selection_ids[0]

        # Find the selected option
        selected_option = None
        for option in pending['options']:
            if option['id'] == selection_id:
                selected_option = option
                break

        if not selected_option:
            return {'error': 'Invalid selection'}

        if selected_option['type'] == 'travel_to_zone':
            # Execute zone travel
            target_zone = selected_option['zone_key']
            travel_result = ZoneController.travel_to_zone(run, target_zone)

            if 'error' in travel_result:
                return travel_result

            # Clear the portal selection
            run.set_pending_selection(None)

            return {
                'success': True,
                'zone_travel': True,
                'results': [travel_result['message']],
                'band_changes': [],
                'resource_changes': {},
                'new_zone': target_zone,
                'new_position': 5
            }

        elif selected_option['type'] == 'stay_in_zone':
            # Continue in current zone - clear selection and continue normally
            run.set_pending_selection(None)

            current_zone_data = ZoneController.get_current_zone_data(run)
            return {
                'success': True,
                'results': [f"Continued exploring {current_zone_data['name']}"],
                'band_changes': [],
                'resource_changes': {}
            }

        return {'error': 'Unknown portal option'}

    @staticmethod
    def swap_minion_positions(run, index1, index2):
        """Swap positions of two minions in the band"""
        return BandManager.swap_minion_positions(run, index1, index2)

    @staticmethod
    def abandon_minion(run, index):
        """Remove a minion from the band"""
        return BandManager.abandon_minion(run, index)

    @staticmethod
    def _create_combat_selection(run, event_type):
        """Create an interactive combat selection"""
        return EventSystem._create_combat_selection(run, event_type)

    @staticmethod
    def process_combat_step(combat_state):
        """Process one step of combat and return updated state"""
        return CombatSystem.process_combat_step(combat_state)

    @staticmethod
    def resolve_combat_selection(run, selection_id):
        """Resolve combat selection choice"""
        return CombatSystem.resolve_combat_selection(run, selection_id)

    @staticmethod
    def process_event(run, event_type):
        """Process an event and return the result"""
        return GameController.process_event(run, event_type)

    @staticmethod
    def _generate_minion(tier, pool_modifiers=None):
        """Generate a random minion based on tier and zone pool modifiers"""
        # If no pool modifiers specified, use current zone's modifiers
        if pool_modifiers is None:
            # This is a bit of a hack - we need the run context here
            # In practice, this should be called from BandManager.generate_minion
            pass

        return BandManager.generate_minion(tier)

    @staticmethod
    def _generate_npc_band(ring_level, difficulty):
        """Generate an NPC band for battle using appropriate tiers"""
        return BandManager.generate_npc_band(ring_level, difficulty)

    @staticmethod
    def auto_battle(player_band, enemy_band):
        """Simulate auto-battle between two bands"""
        return GameController.auto_battle(player_band, enemy_band)

    @staticmethod
    def calculate_band_power(band):
        """Calculate total power level of a band"""
        return BandManager.calculate_band_power(band)