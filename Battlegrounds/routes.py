import logging

logger = logging.getLogger(__name__)

from flask import Blueprint, request, jsonify, session as flask_session
from database import *
from game_logic import GameLogic
from rate_limit import rate_limit, localhost_only

api = Blueprint('api', __name__)


def get_authorized_run(run_id):
    """Fetch a run and verify the caller owns it via run_token or session.

    Returns (run, None) on success, or (None, error_response) on failure.

    Auth rules:
      - If a valid run_token is provided (header or query param), it must match.
      - Otherwise fall back to session: logged-in player must own the run,
        or anonymous caller can only access anonymous (player_id=None) runs.
    """
    run = get_run(run_id)
    if not run or not run.is_active:
        return None, (jsonify({'success': False, 'error': 'Run not found or inactive'}), 404)

    # Check run_token first (works for both logged-in and anonymous)
    token = request.headers.get('X-Run-Token') or request.args.get('run_token')
    if token:
        if run.run_token and token == run.run_token:
            return run, None
        return None, (jsonify({'success': False, 'error': 'Invalid run token'}), 403)

    # Fallback: session-based ownership
    player_id = flask_session.get('player_id')
    if run.player_id is not None:
        # Run belongs to a player — caller must be that player
        if player_id != run.player_id:
            return None, (jsonify({'success': False, 'error': 'Not your run'}), 403)
    else:
        # Anonymous run — run_token is REQUIRED (no session identity to verify).
        # Without this, any anonymous user could access any anonymous run by ID.
        return None, (jsonify({'success': False, 'error': 'Run token required for anonymous runs'}), 403)

    return run, None


def build_ui_state(run):
    """
    Build complete UI state object for client display

    This consolidates all UI control data that the client needs for proper display
    without doing any game logic calculations on the frontend.
    """
    from game_engine.sub_ring_controller import SubRingController
    from game_engine.zone_controller import ZoneController

    # Sub-ring state
    is_in_sub_ring = SubRingController.is_in_sub_ring(run)
    sub_ring_progress = SubRingController.get_sub_ring_progress(run) if is_in_sub_ring else None

    # Zone and portal state
    portal_positions = ZoneController.get_portal_positions(run)
    available_destinations = ZoneController.get_available_destinations(run)

    # Determine if player can use portal at current position
    can_use_portal = False
    if not is_in_sub_ring and portal_positions:
        current_position_portals = portal_positions.get(run.ring_position)
        can_use_portal = bool(current_position_portals and available_destinations)

    # Get next ghost milestone for step calculation
    ghost_milestone = None
    if run.upcoming_ghost_id:
        from models import GhostSnapshot
        upcoming_ghost = GhostSnapshot.query.get(run.upcoming_ghost_id)
        if upcoming_ghost:
            ghost_milestone = upcoming_ghost.events_milestone

    # Get visited general events for ring display
    event_state = run.get_event_state()
    visited_general_events = event_state.get('visited_general_events', {})

    # Effective max band size (base + extra slots from events like Ivory Tower)
    from config import MAX_BAND_SIZE
    extra_band_slots = event_state.get('extra_band_slots', 0)
    max_band_size = MAX_BAND_SIZE + extra_band_slots

    # DEBUG: Log UI state calculation
    logger.debug(f"[UI_STATE DEBUG] events_count={run.events_count}, upcoming_ghost_id={run.upcoming_ghost_id}, ghost_milestone={ghost_milestone}")

    return {
        'is_in_sub_ring': is_in_sub_ring,
        'sub_ring_progress': sub_ring_progress,
        'portal_positions': portal_positions,
        'available_destinations': available_destinations,
        'can_use_portal': can_use_portal,
        'ghost_milestone': ghost_milestone,
        'visited_general_events': visited_general_events,
        'max_band_size': max_band_size
    }


def get_current_event_and_ring_data(run):
    """Get current event and ring data, handling both main and sub-rings with complete UI state"""
    from game_engine.sub_ring_controller import SubRingController
    from game_engine.zone_controller import ZoneController

    # Always get main ring events for display (even when in sub-ring)
    zone = getattr(run, 'current_zone', None)
    ring_events = GameLogic.get_ring_events(run.current_ring, zone=zone)

    # Build complete UI state
    ui_state = build_ui_state(run)

    if ui_state['is_in_sub_ring']:
        # In sub-ring - get sub-ring event but keep main ring data for display
        current_event = SubRingController.get_current_sub_ring_event(run)
    else:
        # In main ring - get main ring event
        current_event = GameLogic.get_current_event(run)

    return {
        'current_event': current_event,
        'ring_events': ring_events,  # Always main ring events
        'ui_state': ui_state  # Complete UI state package
    }


@api.route('/start-run', methods=['POST'])
@rate_limit(max_requests=10, window_seconds=60)
def start_run():
    """Start a new game run or resume existing"""
    from flask import session
    from models import Run

    try:
        data = request.get_json() or {}
        is_ranked = data.get('ranked', False)
        force_new = data.get('force_new', False)  # Force creation of new run
        hero_id = data.get('hero_id', None)  # Selected hero ID

        # Validate hero_id against known heroes to prevent XSS/injection
        if hero_id is not None:
            from hero_definitions import get_hero
            if not isinstance(hero_id, str) or not get_hero(hero_id):
                hero_id = None  # Silently ignore invalid hero

        # Always use player_id if logged in (for both ranked and unranked)
        player_id = session.get('player_id')

        # Check for existing active run (both ranked and unranked are saved)
        if player_id and not force_new:
            existing_run = Run.query.filter_by(
                player_id=player_id,
                is_ranked=is_ranked,  # Match the mode (ranked or unranked)
                is_active=True
            ).first()

            if existing_run:
                # Resume existing run
                event_data = get_current_event_and_ring_data(existing_run)
                from game_engine.zone_controller import ZoneController
                current_zone_data = ZoneController.get_current_zone_data(existing_run)

                return jsonify({
                    'success': True,
                    'run': existing_run.to_dict(),
                    'current_event': event_data['current_event'],
                    'ring_events': event_data['ring_events'],
                    'current_zone': current_zone_data,
                    'ui_state': event_data['ui_state'],
                    'portal_positions': event_data['ui_state']['portal_positions'],
                    'available_destinations': event_data['ui_state']['available_destinations'],
                    'sub_ring_progress': event_data['ui_state']['sub_ring_progress'],
                    'message': 'Resumed existing run!',
                    'resumed': True
                })

        # Create new run
        run = create_new_run(player_id=player_id, is_ranked=is_ranked, hero_id=hero_id)

        # Clear any leftover combat session for this run ID (shouldn't exist but just in case)
        from game_engine.combat_interpreter import clear_session
        clear_session(run.id)

        # Get current event and ring data with UI state
        event_data = get_current_event_and_ring_data(run)

        # Get zone information
        from game_engine.zone_controller import ZoneController
        current_zone_data = ZoneController.get_current_zone_data(run)

        return jsonify({
            'success': True,
            'run': run.to_dict(),
            'current_event': event_data['current_event'],
            'ring_events': event_data['ring_events'],
            'current_zone': current_zone_data,
            'ui_state': event_data['ui_state'],
            'portal_positions': event_data['ui_state']['portal_positions'],
            'available_destinations': event_data['ui_state']['available_destinations'],
            'sub_ring_progress': event_data['ui_state']['sub_ring_progress'],
            'message': 'New run started!',
            'resumed': False
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api.route('/run/<int:run_id>', methods=['GET'])
def get_run_state(run_id):
    """Get current state of a run"""
    try:
        run, err = get_authorized_run(run_id)
        if err:
            return err

        # Get current event and ring data with UI state
        event_data = get_current_event_and_ring_data(run)

        # Get zone information
        from game_engine.zone_controller import ZoneController
        current_zone_data = ZoneController.get_current_zone_data(run)

        # Check for interpreter data in pending selection
        interpreter_data = None
        if run.has_pending_selection():
            pending = run.get_pending_selection()
            if pending.get('interpreter_data'):
                interpreter_data = pending['interpreter_data']

        response = {
            'success': True,
            'run': run.to_dict(),
            'current_event': event_data['current_event'],
            'ring_events': event_data['ring_events'],
            'ghost_battle_ready': check_ghost_battle_available(run),
            'ghost_battle_required': check_ghost_battle_trigger(run),
            'current_zone': current_zone_data,
            'ui_state': event_data['ui_state'],  # Include complete UI state
            'portal_positions': event_data['ui_state']['portal_positions'],  # Backward compatibility
            'available_destinations': event_data['ui_state']['available_destinations'],  # Backward compatibility
            'sub_ring_progress': event_data['ui_state']['sub_ring_progress']  # Backward compatibility
        }

        # Include interpreter data if available
        if interpreter_data:
            response['interpreter_data'] = interpreter_data

        return jsonify(response)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api.route('/run/<int:run_id>/move', methods=['POST'])
@rate_limit(max_requests=20, window_seconds=10)
def move_player(run_id):
    """Move player left or right in current ring or sub-ring"""
    try:
        data = request.get_json()
        direction = data.get('direction')

        if direction not in ['left', 'right']:
            return jsonify({'success': False, 'error': 'Invalid direction'}), 400

        run, err = get_authorized_run(run_id)
        if err:
            return err

        # Check if there's a pending selection and if it's leaveable
        if run.has_pending_selection():
            pending_selection = run.get_pending_selection()
            is_leaveable = pending_selection.get('leaveable', False)

            if not is_leaveable:
                return jsonify({
                    'success': False,
                    'error': 'Must complete current selection before moving'
                }), 400
            else:
                # Clear leaveable selection when moving
                run.set_pending_selection(None)
                update_run(run)

        from game_engine.sub_ring_controller import SubRingController

        # Handle movement based on current ring type
        if SubRingController.is_in_sub_ring(run):
            # Sub-ring movement (bidirectional)
            success, message = SubRingController.move_in_sub_ring(run, direction)
            if not success:
                return jsonify({'success': False, 'error': message}), 400

            # Check if we exited the sub-ring
            if not SubRingController.is_in_sub_ring(run):
                # Exited sub-ring, now get main ring event
                current_event = GameLogic.get_current_event(run)
                event_result = GameLogic.create_event_selection(run, current_event)
            else:
                # Still in sub-ring, get sub-ring event
                current_event = SubRingController.get_current_sub_ring_event(run)
                event_result = GameLogic.create_event_selection(run, current_event)
        else:
            # Main ring movement
            move_in_ring(run, direction)
            current_event = GameLogic.get_current_event(run)
            event_result = GameLogic.create_event_selection(run, current_event)

        # Save changes
        update_run(run)

        # Check if ghost battle is available
        ghost_battle_ready = check_ghost_battle_available(run)

        # Get current event and ring data with UI state
        event_data = get_current_event_and_ring_data(run)

        # Get zone information
        from game_engine.zone_controller import ZoneController
        current_zone_data = ZoneController.get_current_zone_data(run)

        response = {
            'success': True,
            'run': run.to_dict(),
            'event_result': event_result,
            'next_event': event_data['current_event'],
            'ring_events': event_data['ring_events'],
            'ghost_battle_ready': ghost_battle_ready,
            'ghost_battle_required': check_ghost_battle_trigger(run),
            'has_selection': run.has_pending_selection(),
            'current_zone': current_zone_data,
            'ui_state': event_data['ui_state'],  # Include complete UI state
            'portal_positions': event_data['ui_state']['portal_positions'],  # Backward compatibility
            'available_destinations': event_data['ui_state']['available_destinations'],  # Backward compatibility
            'sub_ring_progress': event_data['ui_state']['sub_ring_progress']  # Backward compatibility
        }

        return jsonify(response)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api.route('/run/<int:run_id>/select', methods=['POST'])
@rate_limit(max_requests=30, window_seconds=10)
def make_selection(run_id):
    """Submit player's selection choice(s)"""
    try:
        data = request.get_json()
        selection_ids = data.get('selections', [])

        if not isinstance(selection_ids, list):
            selection_ids = [selection_ids] if selection_ids else []

        run, err = get_authorized_run(run_id)
        if err:
            return err

        if not run.has_pending_selection():
            return jsonify({'success': False, 'error': 'No pending selection'}), 400

        # Check if this is a combat selection (regular or boss combat)
        pending = run.get_pending_selection()
        if pending and pending.get('event_type') in ('combat', 'boss_combat'):
            # Handle combat selection
            if len(selection_ids) != 1:
                return jsonify({'success': False, 'error': 'Must select exactly one combat option'}), 400

            selection_result = GameLogic.resolve_combat_selection(run, selection_ids[0])
        else:
            # Handle regular selection (including branching choices)
            selection_result = GameLogic.resolve_selection(run, selection_ids)

        if 'error' in selection_result:
            return jsonify({'success': False, 'error': selection_result['error']}), 400

        # Save changes
        update_run(run)

        # Check if run should end (victory or defeat conditions)
        from models import GhostBattle
        from config import MAX_GHOST_WINS

        ghost_battles = GhostBattle.query.filter_by(run_id=run_id).all()
        ghosts_won = len([b for b in ghost_battles if b.winner == 'player'])

        logger.debug(f"[END CHECK] Run {run_id}: Ghosts won: {ghosts_won}/{MAX_GHOST_WINS}, Health: {run.health}")

        run_should_end = False
        run_victory = False
        end_reason = None

        if ghosts_won >= MAX_GHOST_WINS:
            run_should_end = True
            run_victory = True
            end_reason = f'Victory! Defeated {MAX_GHOST_WINS} ghosts!'
            logger.debug(f"[END CHECK] VICTORY CONDITION MET for run {run_id}")
        elif run.health <= 0:
            run_should_end = True
            run_victory = False
            end_reason = 'Defeat! Health reached zero.'
            logger.debug(f"[END CHECK] DEFEAT CONDITION MET for run {run_id}")

        # Check if ghost battle is available
        ghost_battle_ready = check_ghost_battle_available(run)

        # Get current event and ring data with UI state
        event_data = get_current_event_and_ring_data(run)

        # Get zone information
        from game_engine.zone_controller import ZoneController
        current_zone_data = ZoneController.get_current_zone_data(run)

        response = {
            'success': True,
            'run': run.to_dict(),
            'selection_result': selection_result,
            'next_event': event_data['current_event'] if not run.has_pending_selection() else None,
            'ring_events': event_data['ring_events'],
            'ghost_battle_ready': ghost_battle_ready,
            'ghost_battle_required': check_ghost_battle_trigger(run),
            'has_selection': run.has_pending_selection(),
            'current_zone': current_zone_data,
            'ui_state': event_data['ui_state'],  # Include complete UI state
            'portal_positions': event_data['ui_state']['portal_positions'],  # Backward compatibility
            'available_destinations': event_data['ui_state']['available_destinations'],  # Backward compatibility
            'sub_ring_progress': event_data['ui_state']['sub_ring_progress'],  # Backward compatibility
            'run_should_end': run_should_end,  # Victory or defeat condition met
            'run_victory': run_victory,  # True for victory, False for defeat
            'end_reason': end_reason,  # Human-readable reason for ending
            'ghost_wins': ghosts_won  # Current ghost win count
        }

        # Include interpreter data if available
        if 'interpreter_data' in selection_result:
            response['interpreter_data'] = selection_result['interpreter_data']

        return jsonify(response)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api.route('/run/<int:run_id>/selection', methods=['GET'])
def get_pending_selection(run_id):
    """Get current pending selection details"""
    try:
        run, err = get_authorized_run(run_id)
        if err:
            return err

        pending = run.get_pending_selection()

        response = {
            'success': True,
            'has_selection': run.has_pending_selection(),
            'selection': pending
        }

        # Include interpreter data if available
        if pending and pending.get('interpreter_data'):
            response['interpreter_data'] = pending['interpreter_data']

        return jsonify(response)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api.route('/run/<int:run_id>/upgrade-ring', methods=['POST'])
@rate_limit(max_requests=10, window_seconds=10)
def upgrade_player_ring(run_id):
    """Upgrade player to next ring"""
    try:
        run, err = get_authorized_run(run_id)
        if err:
            return err

        # Cannot upgrade ring while in sub-ring
        from game_engine.sub_ring_controller import SubRingController
        if SubRingController.is_in_sub_ring(run):
            return jsonify({'success': False, 'error': 'Cannot upgrade ring while in a sub-ring'}), 400

        # Check if there's a non-leaveable pending selection
        if run.has_pending_selection():
            pending_selection = run.get_pending_selection()
            is_leaveable = pending_selection.get('leaveable', False)

            if not is_leaveable:
                return jsonify({
                    'success': False,
                    'error': 'Must complete current selection before upgrading ring'
                }), 400
            else:
                # Clear leaveable selection when upgrading
                run.set_pending_selection(None)

        old_ring = run.current_ring

        # Check if already at max ring
        from config import MAX_RING_AVAILABLE, EVENTS_FOR_GHOST_BATTLE
        if run.current_ring >= MAX_RING_AVAILABLE:
            return jsonify({
                'success': False,
                'error': f'Already at maximum ring ({MAX_RING_AVAILABLE})'
            }), 400

        # Calculate upgrade cost (starts at 15, decreases by 1 each step, min 0)
        # Apply tier_cost_reduction from Grand City Portal Transit
        event_state = run.get_event_state()
        tier_cost_reduction = event_state.get('tier_cost_reduction', 0)
        upgrade_cost = max(0, 15 - run.ring_upgrade_steps - tier_cost_reduction)

        # Calculate steps available until next REQUIRED ghost battle
        # Check if there's an upcoming ghost and use its milestone
        from config import EVENTS_FOR_GHOST_BATTLE
        if run.upcoming_ghost_id:
            from models import GhostSnapshot
            upcoming_ghost = GhostSnapshot.query.get(run.upcoming_ghost_id)
            if upcoming_ghost:
                next_ghost_milestone = upcoming_ghost.events_milestone
            else:
                # Fallback to next 10-step milestone
                current_cycle = run.events_count // EVENTS_FOR_GHOST_BATTLE
                next_ghost_milestone = (current_cycle + 1) * EVENTS_FOR_GHOST_BATTLE
        else:
            # No ghost available yet, use next 10-step milestone
            current_cycle = run.events_count // EVENTS_FOR_GHOST_BATTLE
            next_ghost_milestone = (current_cycle + 1) * EVENTS_FOR_GHOST_BATTLE

        steps_available = next_ghost_milestone - run.events_count

        # DEBUG: Log upgrade calculation
        logger.debug(f"[UPGRADE DEBUG] events_count={run.events_count}, ring_upgrade_steps={run.ring_upgrade_steps}, upgrade_cost={upgrade_cost}, next_ghost_milestone={next_ghost_milestone}, steps_available={steps_available}, upcoming_ghost_id={run.upcoming_ghost_id}")

        if steps_available < upgrade_cost:
            logger.debug(f"[UPGRADE DEBUG] REJECTED: Not enough steps ({steps_available} < {upgrade_cost})")
            return jsonify({
                'success': False,
                'error': f'Not enough steps to upgrade ring. Need {upgrade_cost} steps, have {steps_available} available.'
            }), 400

        # Ensure upgrade doesn't push events_count past the next ghost battle trigger
        if run.events_count + upgrade_cost > next_ghost_milestone:
            return jsonify({
                'success': False,
                'error': f'Cannot upgrade: would trigger ghost battle.'
            }), 400

        # Consume the cost from the ghost battle cycle
        run.events_count += upgrade_cost

        # Clear any sub-ring state when upgrading rings (safety measure)
        run.current_ring_type = 'main'
        run.current_sub_ring = None
        run.sub_ring_position = 0
        run.main_ring_return_position = None
        run.set_sub_ring_data(None)

        upgrade_ring(run)

        # Clear tier_cost_reduction after upgrade (one-time use)
        if tier_cost_reduction > 0:
            event_state.pop('tier_cost_reduction', None)
            run.set_event_state(event_state)

        # Get current event and ring data with UI state
        event_data = get_current_event_and_ring_data(run)

        # Get zone information
        from game_engine.zone_controller import ZoneController
        current_zone_data = ZoneController.get_current_zone_data(run)

        # Build appropriate message based on cost
        if upgrade_cost > 0:
            message = f'Upgraded from Ring {old_ring} to Ring {run.current_ring}! (Cost: {upgrade_cost} steps)'
        else:
            message = f'Upgraded from Ring {old_ring} to Ring {run.current_ring}! (Free)'

        return jsonify({
            'success': True,
            'run': run.to_dict(),
            'message': message,
            'steps_spent': upgrade_cost,
            'current_event': event_data['current_event'],
            'ring_events': event_data['ring_events'],
            'ghost_battle_ready': check_ghost_battle_available(run),
            'ghost_battle_required': check_ghost_battle_trigger(run),
            'current_zone': current_zone_data,
            'ui_state': event_data['ui_state'],  # Include complete UI state
            'portal_positions': event_data['ui_state']['portal_positions'],  # Backward compatibility
            'sub_ring_progress': event_data['ui_state']['sub_ring_progress']  # Backward compatibility
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api.route('/run/<int:run_id>/travel-zone', methods=['POST'])
@rate_limit(max_requests=10, window_seconds=10)
def travel_to_zone_endpoint(run_id):
    """Travel to a different zone"""
    try:
        data = request.get_json()
        target_zone = data.get('zone')

        if not target_zone:
            return jsonify({'success': False, 'error': 'Target zone required'}), 400

        run, err = get_authorized_run(run_id)
        if err:
            return err

        # Check if there's a non-leaveable pending selection
        if run.has_pending_selection():
            pending_selection = run.get_pending_selection()
            is_leaveable = pending_selection.get('leaveable', False)

            if not is_leaveable:
                return jsonify({
                    'success': False,
                    'error': 'Must complete current selection before traveling'
                }), 400
            else:
                # Clear leaveable selection when traveling
                run.set_pending_selection(None)

        # Zone travel is only available from main ring
        from game_engine.sub_ring_controller import SubRingController
        if SubRingController.is_in_sub_ring(run):
            return jsonify({'success': False, 'error': 'Cannot travel between zones while in a sub-ring'}), 400

        # Execute zone travel
        travel_result = travel_to_zone(run, target_zone)

        if 'error' in travel_result:
            return jsonify({'success': False, 'error': travel_result['error']}), 400

        # Get current event and ring data with UI state
        event_data = get_current_event_and_ring_data(run)

        # Get zone information
        from game_engine.zone_controller import ZoneController
        zone_data = ZoneController.get_current_zone_data(run)

        response = {
            'success': True,
            'run': run.to_dict(),
            'travel_result': travel_result,
            'next_event': event_data['current_event'],
            'ring_events': event_data['ring_events'],
            'current_zone': zone_data,
            'ui_state': event_data['ui_state'],  # Include complete UI state
            'portal_positions': event_data['ui_state']['portal_positions'],  # Backward compatibility
            'sub_ring_progress': event_data['ui_state']['sub_ring_progress'],  # Backward compatibility
            'message': travel_result['message']
        }

        return jsonify(response)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api.route('/run/<int:run_id>/ghost-battle', methods=['POST'])
@rate_limit(max_requests=10, window_seconds=10)
def initiate_ghost_battle(run_id):
    """Start a ghost battle - now triggers an actual combat instead of auto-battle"""
    try:
        run, err = get_authorized_run(run_id)
        if err:
            return err

        # Check if there's a pre-generated ghost available
        if not run.upcoming_ghost_id:
            return jsonify({'success': False, 'error': 'No ghost battle available'}), 400

        # Check if there's a non-leaveable pending selection
        if run.has_pending_selection():
            pending_selection = run.get_pending_selection()
            is_leaveable = pending_selection.get('leaveable', False)

            if not is_leaveable:
                return jsonify({
                    'success': False,
                    'error': 'Must complete current selection before starting ghost battle'
                }), 400
            else:
                # Clear leaveable selection when starting ghost battle
                run.set_pending_selection(None)

        # Create ghost snapshot for this player (for matchmaking other players)
        player_ghost = create_ghost_snapshot(run)

        # Get player band
        player_band = run.get_band()

        # Get the pre-generated ghost opponent
        from models import GhostSnapshot
        opponent_ghost = GhostSnapshot.query.get(run.upcoming_ghost_id)
        if not opponent_ghost:
            return jsonify({'success': False, 'error': 'Ghost opponent not found'}), 404

        # Get enemy band with the ghost's equipped images applied
        enemy_band = opponent_ghost.get_band_with_images()

        # Determine who goes first
        player_goes_first = len(player_band) >= len(enemy_band)

        # Pre-generate combat so interpreter data is available immediately
        # Pass ghost hero effects so they apply during combat
        from game_engine.combat_system import CombatSystem
        battle_result = CombatSystem.resolve_combat(
            player_band, enemy_band, run=run,
            enemy_hero_effects=opponent_ghost.get_hero_effects()
        )
        interpreter_data = battle_result.get('interpreter_data')

        # Use INITIAL state for combat_state (so UI starts from beginning)
        # but store interpreter_data for playback
        combat_state = {
            'player_band': [minion.copy() for minion in player_band],
            'enemy_band': [minion.copy() for minion in enemy_band],
            'player_turn': player_goes_first,
            'current_player_unit': 0,
            'current_enemy_unit': 0,
            'combat_log': [],
            'round_number': 1,
            'combat_over': False,
            'winner': None
        }

        # Ghost opponent display info
        ghost_name = opponent_ghost.player_name or 'Ghost'
        ghost_hero = opponent_ghost.hero_id

        # Create combat selection
        from lucide_icons import generate_lucide_svg
        selection = {
            'event_type': 'combat',
            'combat_type': 'ghost_battle',
            'ghost_id': opponent_ghost.id,
            'ghost_player_name': ghost_name,
            'ghost_hero_id': ghost_hero,
            'title': f'{generate_lucide_svg("ghost", width=24, height=24)} Ghost Battle vs {ghost_name} (Event {run.events_count})',
            'message': f'Fighting {ghost_name}\'s band:',
            'combat_state': combat_state,
            'interpreter_data': interpreter_data,
            'options': [
                {
                    'type': 'combat_next',
                    'message': 'Next Attack',
                    'description': 'Execute one attack and see the result',
                    'id': 'next'
                },
                {
                    'type': 'combat_auto',
                    'message': 'Auto Combat',
                    'description': 'Run combat automatically to completion',
                    'id': 'auto'
                },
                {
                    'type': 'combat_end',
                    'message': 'End Combat',
                    'description': 'Skip to final combat result immediately',
                    'id': 'end'
                }
            ],
            'min_selections': 1,
            'max_selections': 1,
            'repeating': False,
            'leaveable': False
        }

        run.set_pending_selection(selection)
        update_run(run)

        return jsonify({
            'success': True,
            'message': f'Ghost battle vs {ghost_name} initiated!',
            'run': run.to_dict()
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@api.route('/run/<int:run_id>/preview-ghost', methods=['POST'])
def preview_ghost(run_id):
    """Preview the upcoming ghost opponent band - creates a view-only selection"""
    try:
        run, err = get_authorized_run(run_id)
        if err:
            return err

        # Check if there's a pre-generated ghost
        if not run.upcoming_ghost_id:
            return jsonify({'success': False, 'error': 'No upcoming ghost available'}), 400

        # Check if there's a non-leaveable pending selection
        if run.has_pending_selection():
            pending_selection = run.get_pending_selection()
            is_leaveable = pending_selection.get('leaveable', False)

            if not is_leaveable:
                return jsonify({
                    'success': False,
                    'error': 'Must complete current selection before previewing ghost'
                }), 400
            else:
                # Clear leaveable selection when previewing ghost
                run.set_pending_selection(None)

        # Get the ghost opponent
        from models import GhostSnapshot
        ghost = GhostSnapshot.query.get(run.upcoming_ghost_id)
        if not ghost:
            return jsonify({'success': False, 'error': 'Ghost not found'}), 404

        # Use the ghost's actual milestone (important after early fights!)
        ghost_milestone = ghost.events_milestone

        # Render both bands with their respective equipped-image variants so the
        # preview cards are pixel-accurate to what combat will show.
        ghost_band = ghost.get_band_with_images()
        player_band = run.get_band_with_equipped_images()

        ghost_name = ghost.player_name or 'AI Opponent'
        ghost_hero_effects = ghost.get_hero_effects() or {}

        # Pull hero definition snapshot so the UI can render the ghost's hero
        # badge without re-querying HEROES client-side for a non-current run.
        try:
            from hero_definitions import get_hero
            ghost_hero_def = get_hero(ghost.hero_id) if ghost.hero_id else None
        except Exception:
            ghost_hero_def = None
        ghost_hero_name = ghost_hero_def['name'] if ghost_hero_def else None

        # Create a preview selection (similar to combat but view-only)
        from lucide_icons import generate_lucide_svg
        selection = {
            'event_type': 'ghost_preview',
            'title': f'{generate_lucide_svg("eye", width=24, height=24)} Ghost Preview - {ghost_name} (Event {ghost_milestone})',
            'message': f'Preview of {ghost_name}\'s band (Power: {ghost.power_level})',
            'preview_data': {
                'player_band': player_band,
                'ghost_band': ghost_band,
                'power_level': ghost.power_level,
                'milestone': ghost_milestone,
                'ghost_player_name': ghost_name,
                'ghost_hero_id': ghost.hero_id,
                'ghost_hero_name': ghost_hero_name,
                'ghost_hero_effects': ghost_hero_effects,
                'ghost_ring': ghost.current_ring,
                'ghost_health': ghost.health,
                'ghost_wins_at_capture': ghost.ghost_wins_at_capture or 0,
                'ghost_losses_at_capture': ghost.ghost_losses_at_capture or 0,
                'ghost_mmr': ghost.mmr,
                'ghost_is_ranked': bool(ghost.is_ranked),
                'ghost_source': ghost.source or 'player',
            },
            'options': [
                {
                    'type': 'skip',
                    'message': 'Close Preview',
                    'description': 'Return to main game',
                    'id': 'close'
                }
            ],
            'min_selections': 1,
            'max_selections': 1,
            'repeating': False,
            'leaveable': True
        }

        # Set the pending selection to trigger preview UI
        run.set_pending_selection(selection)
        update_run(run)

        # Include the full UI state so the ring progress bar, zone info, and
        # status bar all render correctly on top of the preview (previously
        # the response was minimal and the UI fell back to 'Ring Progress
        # Unavailable').
        event_data = get_current_event_and_ring_data(run)
        from game_engine.zone_controller import ZoneController
        current_zone_data = ZoneController.get_current_zone_data(run)

        return jsonify({
            'success': True,
            'message': 'Ghost preview opened',
            'run': run.to_dict(),
            'current_event': event_data['current_event'],
            'ring_events': event_data['ring_events'],
            'ghost_battle_ready': check_ghost_battle_available(run),
            'ghost_battle_required': check_ghost_battle_trigger(run),
            'current_zone': current_zone_data,
            'ui_state': event_data['ui_state'],
            'portal_positions': event_data['ui_state']['portal_positions'],
            'available_destinations': event_data['ui_state']['available_destinations'],
            'sub_ring_progress': event_data['ui_state']['sub_ring_progress'],
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@api.route('/run/<int:run_id>/fight-ghost-early', methods=['POST'])
@rate_limit(max_requests=10, window_seconds=10)
def fight_ghost_early(run_id):
    """Fight the upcoming ghost early - skips to next milestone on victory"""
    try:
        run, err = get_authorized_run(run_id)
        if err:
            return err

        # Check if there's a pre-generated ghost
        if not run.upcoming_ghost_id:
            return jsonify({'success': False, 'error': 'No upcoming ghost available'}), 400

        # Check if there's a non-leaveable pending selection
        if run.has_pending_selection():
            pending_selection = run.get_pending_selection()
            is_leaveable = pending_selection.get('leaveable', False)

            if not is_leaveable:
                return jsonify({
                    'success': False,
                    'error': 'Must complete current selection before fighting ghost'
                }), 400
            else:
                # Clear leaveable selection when starting ghost battle
                run.set_pending_selection(None)

        # Create ghost snapshot for this player (for matchmaking other players)
        player_ghost = create_ghost_snapshot(run)

        # Get player band
        player_band = run.get_band()

        # Get the pre-generated ghost opponent
        from models import GhostSnapshot
        opponent_ghost = GhostSnapshot.query.get(run.upcoming_ghost_id)
        if not opponent_ghost:
            return jsonify({'success': False, 'error': 'Ghost opponent not found'}), 404

        # Get enemy band with the ghost's equipped images applied
        enemy_band = opponent_ghost.get_band_with_images()

        # Use the ghost's actual milestone (important after early fights!)
        ghost_milestone = opponent_ghost.events_milestone

        # Determine who goes first
        player_goes_first = len(player_band) >= len(enemy_band)

        # Pre-generate combat with ghost hero effects
        from game_engine.combat_system import CombatSystem
        battle_result = CombatSystem.resolve_combat(
            player_band, enemy_band, run=run,
            enemy_hero_effects=opponent_ghost.get_hero_effects()
        )
        interpreter_data = battle_result.get('interpreter_data')

        combat_state = {
            'player_band': [minion.copy() for minion in player_band],
            'enemy_band': [minion.copy() for minion in enemy_band],
            'player_turn': player_goes_first,
            'current_player_unit': 0,
            'current_enemy_unit': 0,
            'combat_log': [],
            'round_number': 1,
            'combat_over': False,
            'winner': None
        }

        ghost_name = opponent_ghost.player_name or 'Ghost'
        ghost_hero = opponent_ghost.hero_id

        from lucide_icons import generate_lucide_svg
        selection = {
            'event_type': 'combat',
            'combat_type': 'ghost_battle_early',
            'ghost_id': opponent_ghost.id,
            'ghost_player_name': ghost_name,
            'ghost_hero_id': ghost_hero,
            'original_milestone': ghost_milestone,
            'title': f'{generate_lucide_svg("swords", width=24, height=24)} Early Ghost Battle vs {ghost_name} (Event {ghost_milestone})',
            'message': f'Fighting {ghost_name}\'s band early! Win to skip ahead to event {ghost_milestone + EVENTS_FOR_GHOST_BATTLE}!',
            'combat_state': combat_state,
            'interpreter_data': interpreter_data,
            'options': [
                {
                    'type': 'combat_next',
                    'message': 'Next Attack',
                    'description': 'Execute one attack and see the result',
                    'id': 'next'
                },
                {
                    'type': 'combat_auto',
                    'message': 'Auto Combat',
                    'description': 'Run combat automatically to completion',
                    'id': 'auto'
                },
                {
                    'type': 'combat_end',
                    'message': 'End Combat',
                    'description': 'Skip to final combat result immediately',
                    'id': 'end'
                }
            ],
            'min_selections': 1,
            'max_selections': 1,
            'repeating': False,
            'leaveable': False
        }

        run.set_pending_selection(selection)
        update_run(run)

        return jsonify({
            'success': True,
            'message': f'Early ghost battle vs {ghost_name} started!',
            'run': run.to_dict()
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@api.route('/run/<int:run_id>/swap-minions', methods=['POST'])
def swap_minions(run_id):
    """Swap positions of two minions in the band"""
    try:
        data = request.get_json()
        index1 = data.get('index1')
        index2 = data.get('index2')

        if index1 is None or index2 is None:
            return jsonify({'success': False, 'error': 'Missing minion indices'}), 400

        run, err = get_authorized_run(run_id)
        if err:
            return err

        # Don't allow swapping during non-leaveable selections
        if run.has_pending_selection():
            pending_selection = run.get_pending_selection()
            is_leaveable = pending_selection.get('leaveable', False)

            if not is_leaveable:
                return jsonify({'success': False, 'error': 'Cannot swap minions during this selection'}), 400

        result = GameLogic.swap_minion_positions(run, index1, index2)

        if 'error' in result:
            return jsonify({'success': False, 'error': result['error']}), 400

        update_run(run)

        return jsonify({
            'success': True,
            'run': run.to_dict(),
            'message': result['message']
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api.route('/run/<int:run_id>/abandon-minion', methods=['POST'])
def abandon_minion(run_id):
    """Remove a minion from the band"""
    try:
        data = request.get_json()
        index = data.get('index')

        if index is None:
            return jsonify({'success': False, 'error': 'Missing minion index'}), 400

        run, err = get_authorized_run(run_id)
        if err:
            return err

        # Don't allow abandoning during non-leaveable selections
        if run.has_pending_selection():
            pending_selection = run.get_pending_selection()
            is_leaveable = pending_selection.get('leaveable', False)

            if not is_leaveable:
                return jsonify({'success': False, 'error': 'Cannot abandon minions during this selection'}), 400

        result = GameLogic.abandon_minion(run, index)

        if 'error' in result:
            return jsonify({'success': False, 'error': result['error']}), 400

        update_run(run)

        return jsonify({
            'success': True,
            'run': run.to_dict(),
            'message': result['message']
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# Interpreter-specific endpoint for getting command steps
@api.route('/run/<int:run_id>/combat/interpreter/step', methods=['POST'])
def step_combat_interpreter(run_id):
    """Step through combat interpreter commands"""
    try:
        data = request.get_json()
        step_count = data.get('steps', 1)

        run, err = get_authorized_run(run_id)
        if err:
            return err

        # Get pending selection (supports both regular and boss combat)
        pending = run.get_pending_selection()
        if not pending or pending.get('event_type') not in ('combat', 'boss_combat'):
            return jsonify({'success': False, 'error': 'No combat in progress'}), 400

        # Get interpreter data
        interpreter_data = pending.get('interpreter_data')
        if not interpreter_data:
            return jsonify({'success': False, 'error': 'No interpreter data available'}), 400

        # Get current position
        current_position = pending.get('interpreter_position', 0)
        commands = interpreter_data.get('commands', [])

        # Get next commands
        next_commands = []
        for i in range(step_count):
            if current_position + i < len(commands):
                next_commands.append(commands[current_position + i])

        # Update position
        new_position = min(current_position + step_count, len(commands))
        pending['interpreter_position'] = new_position

        # Check if combat is complete
        is_complete = new_position >= len(commands)

        # Update pending selection
        run.set_pending_selection(pending)
        update_run(run)

        return jsonify({
            'success': True,
            'commands': next_commands,
            'current_position': new_position,
            'total_commands': len(commands),
            'is_complete': is_complete
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api.route('/debug/runs', methods=['GET'])
def debug_runs():
    """Debug endpoint to see all active runs"""
    blocked = localhost_only()
    if blocked:
        return blocked
    try:
        runs = get_active_runs()
        # Strip sensitive run_token from debug output to prevent IDOR
        sanitized = []
        for run in runs:
            d = run.to_dict()
            d.pop('run_token', None)
            sanitized.append(d)
        return jsonify({
            'success': True,
            'runs': sanitized
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api.route('/debug/ghost-battles', methods=['GET'])
def debug_ghost_battles():
    """Debug endpoint to see recent ghost battles"""
    blocked = localhost_only()
    if blocked:
        return blocked
    try:
        battles = get_recent_ghost_battles()
        return jsonify({
            'success': True,
            'battles': [battle.to_dict() for battle in battles]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api.route('/debug/keywords', methods=['GET'])
def debug_keywords():
    """Debug endpoint to test keyword system"""
    blocked = localhost_only()
    if blocked:
        return blocked
    try:
        from keywords import KEYWORDS, get_all_keywords, apply_combat_keywords, has_keyword

        # Test basic keyword functionality
        test_archer = {'name': 'Test Archer', 'health': 5, 'attack': 6, 'keywords': ['poke']}
        test_guard = {'name': 'Test Guardian', 'health': 10, 'attack': 2, 'keywords': ['guard']}
        test_warrior = {'name': 'Test Warrior', 'health': 10, 'attack': 4, 'keywords': []}

        # Test poke keyword
        base_counter = 8
        actual_counter, logs = apply_combat_keywords(test_archer, test_warrior, base_counter)

        return jsonify({
            'success': True,
            'keyword_definitions': KEYWORDS,
            'available_keywords': get_all_keywords(),
            'poke_test': {
                'archer_has_poke': has_keyword(test_archer, 'poke'),
                'warrior_has_poke': has_keyword(test_warrior, 'poke'),
                'base_counter_damage': base_counter,
                'actual_counter_damage': actual_counter,
                'combat_logs': logs
            },
            'guard_test': {
                'guard_has_guard': has_keyword(test_guard, 'guard'),
                'warrior_has_guard': has_keyword(test_warrior, 'guard')
            },
            'power_test': {
                'archer_power': GameLogic.calculate_band_power([test_archer]),
                'guard_power': GameLogic.calculate_band_power([test_guard]),
                'warrior_power': GameLogic.calculate_band_power([test_warrior])
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api.route('/debug/ring-events/<int:ring_level>', methods=['GET'])
def debug_ring_events(ring_level):
    """Debug endpoint to see ring events for a specific ring"""
    blocked = localhost_only()
    if blocked:
        return blocked
    try:
        ring_events = GameLogic.get_ring_events(ring_level)
        return jsonify({
            'success': True,
            'ring_level': ring_level,
            'events': ring_events,
            'event_count': len(ring_events)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api.route('/debug/sub-rings', methods=['GET'])
def debug_sub_rings():
    """Debug endpoint to see simplified sub-ring system"""
    blocked = localhost_only()
    if blocked:
        return blocked
    try:
        from game_engine.sub_ring_controller import SubRingController

        # Test the simple sub-ring generation
        test_generation = {}
        try:
            test_sub_ring = SubRingController.create_sub_ring('risky_path', entry_position=3)
            test_generation['risky_path'] = test_sub_ring
        except Exception as e:
            test_generation['risky_path'] = {'error': str(e)}

        return jsonify({
            'success': True,
            'simplified_system': {
                'risky_path': {
                    'name': 'Risky Path',
                    'description': 'Face greater dangers for better rewards',
                    'events': ['strong_npc', 'strong_buff', 'hard_npc'],
                    'exit_offset': 4,
                    'icon': '⚡'
                }
            },
            'test_generation': test_generation,
            'positioning_example': {
                'entry_at_3': {
                    'sub_ring_path': [3, 's1', 's2', 's3', 7],
                    'exit_left': 3,
                    'exit_right': 7,
                    'description': 'Enter at 3, exit left back to 3, exit right to 7'
                }
            },
            'new_features': [
                'Simplified positioning: fixed entry/exit points',
                'Only one sub-ring type for now (risky_path)',
                'Shows actual sub-ring events instead of "unknown"',
                'Fixed 3-event linear path: Strong Enemy → Strong Buff → Hard Enemy',
                'Exit positions calculated with simple offset (+4 from entry)'
            ]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api.route('/debug/zones', methods=['GET'])
def debug_zones():
    """Debug endpoint to see zone configuration"""
    blocked = localhost_only()
    if blocked:
        return blocked
    try:
        from game_engine.zone_controller import ZoneController

        # Validate zone configuration
        errors = ZoneController.validate_zone_config()

        return jsonify({
            'success': True,
            'zones': ZoneController.get_all_zones(),
            'zone_names': ZoneController.get_zone_names(),
            'config_errors': errors
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api.route('/debug/ghosts', methods=['GET'])
def debug_ghosts():
    """Debug endpoint to see ghost snapshots (updated for keywords)"""
    blocked = localhost_only()
    if blocked:
        return blocked
    try:
        ghosts = GhostSnapshot.query.order_by(GhostSnapshot.created_at.desc()).limit(10).all()
        return jsonify({
            'success': True,
            'ghosts': [ghost.to_dict() for ghost in ghosts]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ========================================
# Run Persistence Routes
# ========================================

@api.route('/check-active-run', methods=['GET'])
def check_active_run():
    """Check if the logged-in player has active runs (ranked and/or unranked)"""
    from flask import session
    from models import Run

    try:
        player_id = session.get('player_id')

        if not player_id:
            return jsonify({
                'success': True,
                'has_ranked_run': False,
                'has_unranked_run': False
            })

        # Check for ranked run
        ranked_run = Run.query.filter_by(
            player_id=player_id,
            is_ranked=True,
            is_active=True
        ).first()

        # Check for unranked run
        unranked_run = Run.query.filter_by(
            player_id=player_id,
            is_ranked=False,
            is_active=True
        ).first()

        # Strip run_token from responses — the client already has it from start-run
        def _safe_run_dict(run_obj):
            if not run_obj:
                return None
            d = run_obj.to_dict()
            d.pop('run_token', None)
            return d

        return jsonify({
            'success': True,
            'has_ranked_run': ranked_run is not None,
            'has_unranked_run': unranked_run is not None,
            'ranked_run': _safe_run_dict(ranked_run),
            'unranked_run': _safe_run_dict(unranked_run)
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api.route('/run/<int:run_id>/abandon', methods=['POST'])
def abandon_run(run_id):
    """Abandon/end the current run"""
    from models import Run

    try:
        run, err = get_authorized_run(run_id)
        if err:
            return err

        # Mark run as inactive
        run.is_active = False
        update_run(run)

        # Clear any cached combat session for this run
        from game_engine.combat_interpreter import clear_session
        clear_session(run_id)

        return jsonify({
            'success': True,
            'message': 'Run abandoned successfully'
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api.route('/run/<int:run_id>/end', methods=['POST'])
def end_run(run_id):
    """
    End a run and calculate final statistics

    Returns comprehensive run statistics including:
    - Victory/defeat status
    - Ghosts defeated
    - Events completed
    - Final band state
    - Resources
    """
    from models import Run, GhostBattle, Player
    from config import MAX_GHOST_WINS

    try:
        run, err = get_authorized_run(run_id)
        if err:
            return err

        logger.debug(f"[END RUN] Run found, is_active: {run.is_active}, health: {run.health}")

        # Calculate statistics
        # Count ghost battles
        ghost_battles = GhostBattle.query.filter_by(run_id=run_id).all()
        ghosts_won = len([b for b in ghost_battles if b.winner == 'player'])
        ghosts_lost = len([b for b in ghost_battles if b.winner == 'ghost'])

        logger.debug(f"[END RUN] Ghosts won: {ghosts_won}, lost: {ghosts_lost}")

        # Determine victory
        victory = ghosts_won >= MAX_GHOST_WINS

        # Get resources
        resources = run.get_resources()

        # Get final band
        band = run.get_band()

        # Calculate time played
        time_played_seconds = (run.updated_at - run.created_at).total_seconds()
        time_played_minutes = int(time_played_seconds / 60)

        # Mark run as inactive
        run.is_active = False

        # Update player stats if ranked
        if run.is_ranked and run.player_id:
            player = Player.query.get(run.player_id)
            if player:
                if victory:
                    player.ranked_wins += 1
                else:
                    player.ranked_losses += 1

                # Update highest ring
                if run.current_ring > player.highest_ring:
                    player.highest_ring = run.current_ring

        update_run(run)

        # Clear any cached combat session for this run
        from game_engine.combat_interpreter import clear_session
        clear_session(run_id)

        # Return comprehensive statistics
        return jsonify({
            'success': True,
            'victory': victory,
            'stats': {
                'ghostsDefeated': ghosts_won,
                'ghostsLost': ghosts_lost,
                'eventsCompleted': run.events_count,
                'highestRing': run.current_ring,
                'finalHealth': run.health,
                'bandSize': len(band),
                'goldRemaining': resources.get('gold', 0),
                'timePlayedMinutes': time_played_minutes,
                'band': band,
                'isRanked': run.is_ranked,
                'mode': 'ranked' if run.is_ranked else 'unranked'
            }
        })

    except Exception as e:
        logger.error(f"Error ending run: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500