"""
Sub Ring Controller - Handles branching sub-ring paths with simple fixed positioning
"""

import random


class SubRingController:
    """Handles all sub-ring navigation, creation, and management"""

    @staticmethod
    def create_sub_ring(template_name, entry_position):
        """Create a simple sub-ring with fixed positioning"""
        # Simple hardcoded sub-ring templates with new scaling event names
        templates = {
            'risky_path': {
                'name': 'Risky Path',
                'description': 'Face greater dangers for better rewards',
                'events': ['combat_event_hard', 'buff_event', 'combat_event_hard'],
                'exit_offset': 4,  # How many positions ahead to exit
                'icon': '⚡'
            }
        }

        if template_name not in templates:
            raise ValueError(f"Unknown sub-ring template: {template_name}")

        template = templates[template_name]

        # Calculate exit position using simple fixed offset
        exit_position = (entry_position + template['exit_offset']) % 12

        return {
            'template': template_name,
            'name': template['name'],
            'description': template['description'],
            'events': template['events'],
            'entry_position': entry_position,
            'exit_position': exit_position,
            'length': len(template['events']),
            'icon': template.get('icon', '❓')
        }

    @staticmethod
    def enter_sub_ring(run, sub_ring_data, entry_position):
        """Enter a sub-ring from main ring"""
        # Store main ring state
        run.current_ring_type = 'sub'
        run.current_sub_ring = sub_ring_data['template']
        run.sub_ring_position = 0  # Always start at beginning of sub-ring
        run.main_ring_return_position = entry_position  # Remember where we entered from

        # Store sub-ring data
        import json
        run.sub_ring_data = json.dumps(sub_ring_data)

    @staticmethod
    def exit_sub_ring(run, exit_direction='right'):
        """Exit sub-ring and return to main ring at fixed positions"""
        if not SubRingController.is_in_sub_ring(run):
            return False, "Not currently in a sub-ring"

        sub_ring_data = SubRingController.get_current_sub_ring_data(run)
        if not sub_ring_data:
            return False, "Sub-ring data not found"

        if exit_direction == 'left':
            # Exit back to entry position
            exit_position = sub_ring_data['entry_position']
        else:  # exit_direction == 'right'
            # Exit to fixed exit position
            exit_position = sub_ring_data['exit_position']

        # Clear sub-ring state
        run.current_ring_type = 'main'
        run.current_sub_ring = None
        run.sub_ring_position = 0
        run.main_ring_return_position = None
        run.sub_ring_data = None

        # Set new main ring position
        run.ring_position = exit_position

        return True, f"Exited sub-ring to main ring position {exit_position}"

    @staticmethod
    def is_in_sub_ring(run):
        """Check if run is currently in a sub-ring"""
        return getattr(run, 'current_ring_type', 'main') == 'sub'

    @staticmethod
    def get_current_sub_ring_data(run):
        """Get current sub-ring data"""
        if not SubRingController.is_in_sub_ring(run):
            return None

        if not hasattr(run, 'sub_ring_data') or not run.sub_ring_data:
            return None

        import json
        return json.loads(run.sub_ring_data)

    @staticmethod
    def get_current_sub_ring_event(run):
        """Get current event in sub-ring"""
        if not SubRingController.is_in_sub_ring(run):
            return None

        sub_ring_data = SubRingController.get_current_sub_ring_data(run)
        if not sub_ring_data:
            return None

        position = getattr(run, 'sub_ring_position', 0)
        events = sub_ring_data.get('events', [])

        if position >= len(events):
            return None

        return events[position]

    @staticmethod
    def move_in_sub_ring(run, direction):
        """Handle bidirectional movement within sub-ring with fixed exit positions"""
        if not SubRingController.is_in_sub_ring(run):
            return False, "Not in a sub-ring"

        sub_ring_data = SubRingController.get_current_sub_ring_data(run)
        if not sub_ring_data:
            return False, "Sub-ring data not found"

        events = sub_ring_data.get('events', [])
        current_position = getattr(run, 'sub_ring_position', 0)

        if direction == 'right':
            new_position = current_position + 1

            if new_position >= len(events):
                # Exit sub-ring to the right (fixed exit position)
                success, message = SubRingController.exit_sub_ring(run, 'right')
                if success:
                    run.events_count += 1  # Count the exit as an event
                    run.ring_upgrade_steps += 1  # Increment upgrade cost counter
                return success, message
            else:
                # Move to next position in sub-ring
                run.sub_ring_position = new_position
                run.events_count += 1  # Count movement as an event
                run.ring_upgrade_steps += 1  # Increment upgrade cost counter
                return True, f"Moved to sub-ring position {new_position}"

        elif direction == 'left':
            new_position = current_position - 1

            if new_position < 0:
                # Exit sub-ring to the left (back to entry position)
                success, message = SubRingController.exit_sub_ring(run, 'left')
                if success:
                    run.events_count += 1  # Count the exit as an event
                    run.ring_upgrade_steps += 1  # Increment upgrade cost counter
                return success, message
            else:
                # Move to previous position in sub-ring
                run.sub_ring_position = new_position
                run.events_count += 1  # Count movement as an event
                run.ring_upgrade_steps += 1  # Increment upgrade cost counter
                return True, f"Moved to sub-ring position {new_position}"

        return False, "Invalid direction"

    @staticmethod
    def validate_sub_ring_template(template_name, template_data):
        """Validate a sub-ring template configuration"""
        required_fields = ['name', 'description', 'events', 'exit_offset']

        for field in required_fields:
            if field not in template_data:
                return False, f"Missing required field: {field}"

        # Check if events list is valid
        if not isinstance(template_data['events'], list) or len(template_data['events']) == 0:
            return False, "Events must be a non-empty list"

        return True, "Valid template"

    @staticmethod
    def get_sub_ring_progress(run):
        """Get progress information for current sub-ring"""
        if not SubRingController.is_in_sub_ring(run):
            return None

        sub_ring_data = SubRingController.get_current_sub_ring_data(run)
        if not sub_ring_data:
            return None

        return {
            'name': sub_ring_data['name'],
            'description': sub_ring_data['description'],
            'current_position': getattr(run, 'sub_ring_position', 0),
            'total_length': len(sub_ring_data.get('events', [])),
            'events': sub_ring_data.get('events', []),
            'entry_position': sub_ring_data.get('entry_position', 0),
            'exit_position': sub_ring_data.get('exit_position', 0),
            'icon': sub_ring_data.get('icon', '❓')
        }

    @staticmethod
    def can_exit_sub_ring_left(run):
        """Check if player can exit sub-ring to the left"""
        if not SubRingController.is_in_sub_ring(run):
            return False
        return getattr(run, 'sub_ring_position', 0) == 0

    @staticmethod
    def can_exit_sub_ring_right(run):
        """Check if player can exit sub-ring to the right"""
        if not SubRingController.is_in_sub_ring(run):
            return False

        sub_ring_data = SubRingController.get_current_sub_ring_data(run)
        if not sub_ring_data:
            return False

        current_position = getattr(run, 'sub_ring_position', 0)
        events = sub_ring_data.get('events', [])

        return current_position == len(events) - 1