"""
Zone Controller - Zone navigation, travel, and management system
"""

from config import ZONES, DEFAULT_STARTING_ZONE


class ZoneController:
    """Handles all zone navigation, travel, and unlock logic"""

    @staticmethod
    def get_zone_data(zone_key):
        """Get zone configuration data by key"""
        return ZONES.get(zone_key, ZONES.get(DEFAULT_STARTING_ZONE))

    @staticmethod
    def get_current_zone_data(run):
        """Get zone data for the run's current zone"""
        current_zone = getattr(run, 'current_zone', DEFAULT_STARTING_ZONE)
        return ZoneController.get_zone_data(current_zone)

    @staticmethod
    def get_unlocked_zones(run):
        """Get list of zones the player has unlocked"""
        if hasattr(run, 'unlocked_zones') and run.unlocked_zones:
            try:
                import json
                return json.loads(run.unlocked_zones)
            except:
                pass
        # Default fallback
        return [DEFAULT_STARTING_ZONE]

    @staticmethod
    def is_zone_unlocked(run, zone_key):
        """Check if a specific zone is unlocked for the player"""
        unlocked_zones = ZoneController.get_unlocked_zones(run)
        return zone_key in unlocked_zones

    @staticmethod
    def get_portal_positions(run):
        """Get all positions in the current ring that have zone portals"""
        from game_engine.game_controller import GameController
        zone = getattr(run, 'current_zone', None)
        ring_events = GameController.get_ring_events(run.current_ring, zone=zone)

        portal_positions = {}

        for i, event in enumerate(ring_events):
            # Check if this position has a zone portal event
            if isinstance(event, list):
                # Split event - check if any option is a zone portal
                if 'zone_portal' in event:
                    # Find connected zones for this portal
                    destinations = ZoneController._get_portal_destinations(run)
                    if destinations:
                        portal_positions[i] = destinations
            elif event == 'zone_portal':
                # Direct zone portal event
                destinations = ZoneController._get_portal_destinations(run)
                if destinations:
                    portal_positions[i] = destinations

        return portal_positions

    @staticmethod
    def _get_portal_destinations(run):
        """Get available portal destinations from current zone"""
        zone_data = ZoneController.get_current_zone_data(run)
        connects_to = zone_data.get('connects_to', [])

        destinations = []
        for zone_key in connects_to:
            if ZoneController.is_zone_unlocked(run, zone_key):
                zone_data = ZoneController.get_zone_data(zone_key)
                destinations.append({
                    'zone_key': zone_key,
                    'zone_data': zone_data
                })

        return destinations

    @staticmethod
    def check_portal_positions(run):
        """Check if positions should be portals in current zone (legacy method)"""
        # Updated to use new portal detection system
        portal_positions = ZoneController.get_portal_positions(run)

        # Convert to old format for backward compatibility
        legacy_portals = {}
        for position, destinations in portal_positions.items():
            if destinations:
                # Use first destination for legacy format
                legacy_portals[position] = destinations[0]['zone_key']

        return legacy_portals

    @staticmethod
    def get_available_destinations(run):
        """Get all zones the player can travel to from current position"""
        current_position = run.ring_position

        # Check if current position has a portal
        from game_engine.game_controller import GameController
        zone = getattr(run, 'current_zone', None)
        ring_events = GameController.get_ring_events(run.current_ring, zone=zone)

        if current_position >= len(ring_events):
            return []

        current_event = ring_events[current_position]

        # Check if current event is or contains a zone portal
        is_portal_position = False
        if isinstance(current_event, list):
            is_portal_position = 'zone_portal' in current_event
        else:
            is_portal_position = current_event == 'zone_portal'

        if not is_portal_position:
            return []

        # Return available destinations
        return ZoneController._get_portal_destinations(run)

    @staticmethod
    def is_portal_position(run, position):
        """Check if a specific position is a portal in the current zone"""
        from game_engine.game_controller import GameController
        zone = getattr(run, 'current_zone', None)
        ring_events = GameController.get_ring_events(run.current_ring, zone=zone)

        if position >= len(ring_events):
            return False

        event = ring_events[position]

        if isinstance(event, list):
            return 'zone_portal' in event
        else:
            return event == 'zone_portal'

    @staticmethod
    def can_travel_to_zone(run, target_zone):
        """Check if player can travel to target zone from current position"""
        # Must be at a portal position
        available_destinations = ZoneController.get_available_destinations(run)
        available_zone_keys = [dest['zone_key'] for dest in available_destinations]

        if target_zone not in available_zone_keys:
            return False, "No portal to that zone from current position"

        # Zone must be unlocked
        if not ZoneController.is_zone_unlocked(run, target_zone):
            return False, "Zone is not unlocked"

        # Zone must exist
        if target_zone not in ZONES:
            return False, "Zone does not exist"

        return True, "Can travel to zone"

    @staticmethod
    def travel_to_zone(run, target_zone):
        """Execute zone travel - move player to target zone at starting position"""
        can_travel, message = ZoneController.can_travel_to_zone(run, target_zone)

        if not can_travel:
            return {'error': message}

        # Get zone data to verify it exists
        zone_data = ZoneController.get_zone_data(target_zone)
        if not zone_data:
            return {'error': 'Invalid target zone'}

        # Execute the travel
        old_zone = getattr(run, 'current_zone', DEFAULT_STARTING_ZONE)
        run.current_zone = target_zone
        run.ring_position = 5  # Always start at position 5 in new zone

        # Reset visited_general_events when changing zones
        event_state = run.get_event_state()
        if 'visited_general_events' in event_state:
            event_state['visited_general_events'] = {}
        event_state['visited_general_events_zone'] = target_zone
        run.set_event_state(event_state)

        return {
            'success': True,
            'message': f"Traveled from {ZoneController.get_zone_data(old_zone)['name']} to {zone_data['name']}",
            'old_zone': old_zone,
            'new_zone': target_zone,
            'new_position': 5
        }

    @staticmethod
    def unlock_zone(run, zone_key):
        """Unlock a new zone for the player"""
        if zone_key not in ZONES:
            return False, "Zone does not exist"

        unlocked_zones = ZoneController.get_unlocked_zones(run)

        if zone_key in unlocked_zones:
            return False, "Zone already unlocked"

        # Add to unlocked zones
        unlocked_zones.append(zone_key)

        # Save back to run
        import json
        run.unlocked_zones = json.dumps(unlocked_zones)

        zone_data = ZoneController.get_zone_data(zone_key)
        return True, f"Unlocked {zone_data['name']}!"

    @staticmethod
    def get_zone_pool_modifiers(run):
        """Get the pool modifiers for the current zone"""
        zone_data = ZoneController.get_current_zone_data(run)
        return zone_data.get('pool_modifiers', None)

    @staticmethod
    def get_all_zones():
        """Get all available zone definitions"""
        return ZONES

    @staticmethod
    def get_zone_names():
        """Get list of all zone keys"""
        return list(ZONES.keys())

    @staticmethod
    def validate_zone_config():
        """Validate zone configuration for errors"""
        errors = []
        
        # Check that default starting zone exists
        if DEFAULT_STARTING_ZONE not in ZONES:
            errors.append(f"Default starting zone '{DEFAULT_STARTING_ZONE}' not found in ZONES")
        
        # Check each zone configuration
        for zone_key, zone_data in ZONES.items():
            # Required fields
            if 'name' not in zone_data:
                errors.append(f"Zone '{zone_key}' missing 'name' field")
            
            if 'connects_to' not in zone_data:
                errors.append(f"Zone '{zone_key}' missing 'connects_to' field")
            
            # Check connections are valid
            for connected_zone in zone_data.get('connects_to', []):
                if connected_zone not in ZONES:
                    errors.append(f"Zone '{zone_key}' connects to non-existent zone '{connected_zone}'")
        
        return errors

    @staticmethod
    def initialize_run_zones(run):
        """Initialize zone data for a new run"""
        run.current_zone = DEFAULT_STARTING_ZONE
        
        # Set initial unlocked zones
        initial_unlocked = []
        for zone_key, zone_data in ZONES.items():
            if zone_data.get('unlocked_by_default', False):
                initial_unlocked.append(zone_key)
        
        # Ensure starting zone is always unlocked
        if DEFAULT_STARTING_ZONE not in initial_unlocked:
            initial_unlocked.append(DEFAULT_STARTING_ZONE)
        
        import json
        run.unlocked_zones = json.dumps(initial_unlocked)

    @staticmethod
    def migrate_existing_run(run):
        """Add zone data to existing runs that don't have it"""
        if not hasattr(run, 'current_zone') or not run.current_zone:
            run.current_zone = DEFAULT_STARTING_ZONE
        
        if not hasattr(run, 'unlocked_zones') or not run.unlocked_zones:
            import json
            run.unlocked_zones = json.dumps([DEFAULT_STARTING_ZONE])