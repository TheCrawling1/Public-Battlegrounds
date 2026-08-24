"""
Selection System - Selection resolution, validation, and multi-step flows
"""

import logging

logger = logging.getLogger(__name__)

from config import MAX_BAND_SIZE
from minions import generate_unique_minion_id
from lucide_icons import format_minion_stats


def get_effective_max_band_size(run):
    """Get the effective max band size including extra slots from events"""
    event_state = run.get_event_state()
    extra_slots = event_state.get('extra_band_slots', 0)
    return MAX_BAND_SIZE + extra_slots


class SelectionSystem:
    """Handles all selection resolution, validation, and multi-step selection logic"""

    @staticmethod
    def validate_selection_limits(pending_selection, selection_ids):
        """
        Validate selection counts against min/max limits and option validity

        Returns:
            dict: {'valid': bool, 'error': str or None}
        """
        if not pending_selection:
            return {'valid': False, 'error': 'No pending selection'}

        min_sel = pending_selection.get('min_selections', 0)
        max_sel = pending_selection.get('max_selections', 1)
        count = len(selection_ids)

        # Check selection count limits
        if count < min_sel:
            return {'valid': False, 'error': f'Must select at least {min_sel} option(s)'}
        if count > max_sel:
            return {'valid': False, 'error': f'Cannot select more than {max_sel} option(s)'}

        # Check that all selected IDs exist in options
        available_option_ids = [opt['id'] for opt in pending_selection.get('options', [])]

        # Debug logging for replacement events
        if not available_option_ids or any(sid not in available_option_ids for sid in selection_ids):
            logger.debug(f"DEBUG: Selection validation issue")
            logger.debug(f"  Event type: {pending_selection.get('event_type')}")
            logger.debug(f"  Selected IDs: {selection_ids}")
            logger.debug(f"  Available IDs: {available_option_ids}")
            logger.debug(f"  Options count: {len(pending_selection.get('options', []))}")
            if pending_selection.get('options'):
                logger.debug(f"  First option: {pending_selection['options'][0]}")

        for selection_id in selection_ids:
            if selection_id not in available_option_ids:
                return {'valid': False, 'error': f'Invalid selection ID: {selection_id}'}

        # Check for duplicate selections
        if len(selection_ids) != len(set(selection_ids)):
            return {'valid': False, 'error': 'Cannot select the same option multiple times'}

        # Check that no disabled options are selected
        for selection_id in selection_ids:
            for opt in pending_selection.get('options', []):
                if opt['id'] == selection_id and opt.get('disabled', False):
                    return {'valid': False, 'error': f'Cannot select disabled option: {opt.get("message", selection_id)}'}

        return {'valid': True, 'error': None}

    @staticmethod
    def validate_selection_state(run, pending_selection, selection_ids):
        """
        Validate that the game state hasn't changed in ways that invalidate the selection

        Returns:
            dict: {'valid': bool, 'error': str or None}
        """
        if not pending_selection or not selection_ids:
            return {'valid': True, 'error': None}

        band = run.get_band()
        resources = run.get_resources()
        options = pending_selection.get('options', [])

        for selection_id in selection_ids:
            # Find the selected option
            option = None
            for opt in options:
                if opt['id'] == selection_id:
                    option = opt
                    break

            if not option:
                continue  # Already checked in validate_selection_limits

            # Validate specific option types
            if option['type'] in ['purchase', 'shop_replacement']:
                # Re-validate affordability
                cost = option.get('cost', 0)
                if resources.get('gold', 0) < cost:
                    return {'valid': False, 'error': f'Cannot afford {option.get("message", "item")} - insufficient gold'}

            elif option['type'] in ['apply_targeted_effect', 'replace_with', 'shop_replace_with', 'select_champion_target']:
                # Validate target index is still valid
                target_index = option.get('target_index') or option.get('replace_index')
                if target_index is not None:
                    if target_index < 0 or target_index >= len(band):
                        return {'valid': False, 'error': f'Invalid target - minion no longer exists'}

            elif option['type'] == 'select_minion_for_combine':
                # Validate minion index for combining
                minion_index = option.get('minion_index')
                if minion_index is not None:
                    if minion_index < 0 or minion_index >= len(band):
                        return {'valid': False, 'error': f'Cannot combine - minion no longer exists'}

        return {'valid': True, 'error': None}

    @staticmethod
    def validate_combine_selection_logic(run, pending_selection, selected_indices):
        """
        Validate minion combining logic specifically

        Returns:
            dict: {'valid': bool, 'error': str or None}
        """
        if len(selected_indices) != 2:
            return {'valid': False, 'error': 'Must select exactly 2 minions to combine'}

        band = run.get_band()
        idx1, idx2 = selected_indices

        # Validate indices
        if idx1 < 0 or idx1 >= len(band) or idx2 < 0 or idx2 >= len(band):
            return {'valid': False, 'error': 'Invalid minion indices for combining'}

        minion1 = band[idx1]
        minion2 = band[idx2]

        # Validate minions can be combined
        from minions import can_combine_minions
        if not can_combine_minions(minion1, minion2):
            if minion1['name'] != minion2['name']:
                return {'valid': False, 'error': f'Cannot combine different minions: {minion1["name"]} and {minion2["name"]}'}
            elif minion1.get('golden', False):
                return {'valid': False, 'error': f'{minion1["name"]} is already golden'}
            elif minion2.get('golden', False):
                return {'valid': False, 'error': f'{minion2["name"]} is already golden'}
            else:
                return {'valid': False, 'error': 'These minions cannot be combined'}

        return {'valid': True, 'error': None}

    @staticmethod
    def _create_amount_selector(target_index, target_minion, stat, min_value, current_value,
                                  max_reduction, selected_amount, on_complete, template_event):
        """Create an amount selector screen with -5/-1/+1/+5/Finish/Cancel buttons"""
        amount_options = []

        # Decrease buttons: -5, -1
        can_decrease = selected_amount > 0
        decrease_5 = min(5, selected_amount) if can_decrease else 0
        decrease_1 = min(1, selected_amount) if can_decrease else 0

        amount_options.append({
            'type': 'adjust_stat_amount',
            'render_as': 'button',
            'adjustment': -decrease_5 if can_decrease else 0,
            'target_index': target_index,
            'stat': stat,
            'min_value': min_value,
            'current_value': current_value,
            'max_reduction': max_reduction,
            'on_complete': on_complete,
            'message': '-5',
            'id': 'decrease_5',
            'disabled': not can_decrease
        })
        amount_options.append({
            'type': 'adjust_stat_amount',
            'render_as': 'button',
            'adjustment': -decrease_1 if can_decrease else 0,
            'target_index': target_index,
            'stat': stat,
            'min_value': min_value,
            'current_value': current_value,
            'max_reduction': max_reduction,
            'on_complete': on_complete,
            'message': '-1',
            'id': 'decrease_1',
            'disabled': not can_decrease
        })

        # Increase buttons: +1, +5
        remaining = max_reduction - selected_amount
        can_increase = remaining > 0
        increase_1 = min(1, remaining) if can_increase else 0
        increase_5 = min(5, remaining) if can_increase else 0

        amount_options.append({
            'type': 'adjust_stat_amount',
            'render_as': 'button',
            'adjustment': increase_1 if can_increase else 0,
            'target_index': target_index,
            'stat': stat,
            'min_value': min_value,
            'current_value': current_value,
            'max_reduction': max_reduction,
            'on_complete': on_complete,
            'message': '+1',
            'id': 'increase_1',
            'disabled': not can_increase
        })
        amount_options.append({
            'type': 'adjust_stat_amount',
            'render_as': 'button',
            'adjustment': increase_5 if can_increase else 0,
            'target_index': target_index,
            'stat': stat,
            'min_value': min_value,
            'current_value': current_value,
            'max_reduction': max_reduction,
            'on_complete': on_complete,
            'message': '+5',
            'id': 'increase_5',
            'disabled': not can_increase
        })

        # Finish button (applies the reduction)
        amount_options.append({
            'type': 'apply_stat_reduction',
            'render_as': 'button',
            'target_index': target_index,
            'stat': stat,
            'reduction_amount': selected_amount,
            'new_value': current_value - selected_amount,
            'on_complete': on_complete,
            'message': 'Finish',
            'id': 'finish'
        })

        # Cancel button
        amount_options.append({
            'type': 'back_to_parent',
            'render_as': 'button',
            'message': 'Cancel',
            'id': 'cancel'
        })

        new_value = current_value - selected_amount

        # Create a safe copy of minion data for frontend rendering
        minion_copy = {
            'name': target_minion.get('name', 'Unknown'),
            'attack': target_minion.get('attack', 0),
            'health': target_minion.get('health', 0),
            'tier': target_minion.get('tier', 1),
            'type': target_minion.get('type', 'None'),
            'keywords': list(target_minion.get('keywords', [])),
            'image': target_minion.get('image', ''),
            'band_id': target_minion.get('band_id', '')
        }

        return {
            'event_type': 'amount_selector',
            'title': f'Reduce {stat.title()}',
            'message': f"Reducing {target_minion['name']}'s {stat}",
            'minion': minion_copy,
            'stat': stat,
            'current_value': current_value,
            'new_value': new_value,
            'selected_amount': selected_amount,
            'max_reduction': max_reduction,
            'options': amount_options,
            'min_selections': 1,
            'max_selections': 1,
            'repeating': False,
            'leaveable': True,
            'template_event': template_event
        }

    @staticmethod
    def _resolve_template_event_selection(run, pending, selection_ids):
        """Resolve selections from template-based events (story, make_choice screens)"""
        if len(selection_ids) != 1:
            return {'error': 'Must select exactly one option'}

        # Find the selected option
        selected_option = None
        for option in pending['options']:
            if option['id'] == selection_ids[0]:
                selected_option = option
                break

        if not selected_option:
            return {'error': 'Invalid selection'}

        template_event = pending.get('template_event')
        next_screen_id = selected_option.get('next_screen')
        next_event_id = selected_option.get('next_event')

        # Process option actions
        resources = run.get_resources()
        event_state = run.get_event_state()
        results = []

        # Deduct gold cost if any
        gold_cost = selected_option.get('gold_cost', 0)
        if gold_cost > 0:
            if resources.get('gold', 0) < gold_cost:
                return {'error': f'Not enough gold (need {gold_cost}, have {resources.get("gold", 0)})'}
            resources['gold'] -= gold_cost
            run.set_resources(resources)
            results.append(f'Paid {gold_cost} gold')

        # Handle special option types that need direct processing
        option_type = selected_option.get('type')
        band = run.get_band()

        if option_type == 'golden_target':
            # Make a minion golden
            target_index = selected_option['target_index']

            if target_index >= len(band):
                return {'error': f'Invalid golden target: {target_index}'}

            target_minion = band[target_index]

            # Check if already golden
            if target_minion.get('golden', False):
                return {'error': f'{target_minion["name"]} is already golden!'}

            # Make the minion golden - double stats
            target_minion['golden'] = True
            target_minion['health'] = target_minion.get('health', 1) * 2
            target_minion['attack'] = target_minion.get('attack', 1) * 2

            run.set_band(band)
            run.set_pending_selection(None)
            return {
                'success': True,
                'results': [f'{target_minion["name"]} has been transformed into a golden version!'],
                'band_changes': [{'type': 'golden', 'minion': target_minion['name']}],
                'resource_changes': {}
            }

        elif option_type == 'back_to_parent':
            # Cancel and return to parent event
            run.set_pending_selection(None)
            # Check if we should return to a specific event
            return_to = selected_option.get('return_to_event') or pending.get('return_to_event')
            if return_to:
                from game_engine.events.event_system import EventSystem
                EventSystem.create_event_selection(run, return_to)
                return {
                    'success': True,
                    'back_navigation': True,
                    'message': 'Returned',
                    'results': ['Returned to main event'],
                    'band_changes': [],
                    'resource_changes': {},
                    'returned_to_event': return_to
                }
            return {
                'success': True,
                'back_navigation': True,
                'message': 'Cancelled',
                'results': ['Selection cancelled'],
                'band_changes': [],
                'resource_changes': {}
            }

        elif option_type == 'scry_keep':
            # Keep the scried event - set it as next forced event
            scried_event = pending.get('scried_event', {})
            event_state['forced_next_event'] = scried_event.get('id')
            run.set_event_state(event_state)
            run.set_pending_selection(None)

            # Return to parent event
            return_to = selected_option.get('return_to_event') or pending.get('return_to_event')
            if return_to:
                from game_engine.events.event_system import EventSystem
                EventSystem.create_event_selection(run, return_to)
                return {
                    'success': True,
                    'results': [f'Kept "{scried_event.get("title", "event")}" as your next event'],
                    'band_changes': [],
                    'resource_changes': {},
                    'returned_to_event': return_to
                }
            return {
                'success': True,
                'results': [f'Kept "{scried_event.get("title", "event")}" as your next event'],
                'band_changes': [],
                'resource_changes': {}
            }

        elif option_type == 'scry_discard':
            # Discard the scried event - mark it as skipped
            scried_event = pending.get('scried_event', {})
            skipped_events = event_state.get('skipped_events', [])
            if scried_event.get('id') not in skipped_events:
                skipped_events.append(scried_event.get('id'))
            event_state['skipped_events'] = skipped_events
            run.set_event_state(event_state)
            run.set_pending_selection(None)

            # Return to parent event
            return_to = selected_option.get('return_to_event') or pending.get('return_to_event')
            if return_to:
                from game_engine.events.event_system import EventSystem
                EventSystem.create_event_selection(run, return_to)
                return {
                    'success': True,
                    'results': [f'Discarded "{scried_event.get("title", "event")}"'],
                    'band_changes': [],
                    'resource_changes': {},
                    'returned_to_event': return_to
                }
            return {
                'success': True,
                'results': [f'Discarded "{scried_event.get("title", "event")}"'],
                'band_changes': [],
                'resource_changes': {}
            }

        elif option_type == 'select_for_number_choice':
            # Minion selected for stat reduction - show amount selector with -5/-1/+1/+5/Finish
            target_index = selected_option['target_index']
            stat = selected_option['stat']
            min_value = selected_option['min_value']
            current_value = selected_option['current_value']
            max_reduction = selected_option['max_reduction']
            on_complete = selected_option.get('on_complete')
            target_minion = band[target_index]

            # Initialize selected amount to 0
            event_state['stat_reduction_amount'] = 0
            run.set_event_state(event_state)

            # Create the amount selector screen
            amount_selection = SelectionSystem._create_amount_selector(
                target_index, target_minion, stat, min_value, current_value,
                max_reduction, 0, on_complete, template_event
            )

            run.set_pending_selection(amount_selection)
            return {
                'success': True,
                'amount_selection': True,
                'message': f'Adjust reduction amount for {target_minion["name"]}',
                'results': [],
                'band_changes': [],
                'resource_changes': {}
            }

        elif option_type == 'adjust_stat_amount':
            # Adjust the selected amount and re-show the selector
            adjustment = selected_option.get('adjustment', 0)
            current_amount = event_state.get('stat_reduction_amount', 0)
            max_reduction = selected_option.get('max_reduction', 0)

            # Apply adjustment, clamping to valid range
            new_amount = max(0, min(max_reduction, current_amount + adjustment))
            event_state['stat_reduction_amount'] = new_amount
            run.set_event_state(event_state)

            # Re-create the amount selector with new amount
            target_index = selected_option['target_index']
            stat = selected_option['stat']
            min_value = selected_option['min_value']
            current_value = selected_option['current_value']
            on_complete = selected_option.get('on_complete')
            target_minion = band[target_index]

            amount_selection = SelectionSystem._create_amount_selector(
                target_index, target_minion, stat, min_value, current_value,
                max_reduction, new_amount, on_complete, template_event
            )

            run.set_pending_selection(amount_selection)
            return {
                'success': True,
                'amount_adjusted': True,
                'new_amount': new_amount,
                'message': f'Amount set to {new_amount}',
                'results': [],
                'band_changes': [],
                'resource_changes': {}
            }

        elif option_type == 'apply_stat_reduction':
            # Actually apply the stat reduction
            target_index = selected_option['target_index']
            stat = selected_option['stat']
            reduction_amount = selected_option['reduction_amount']

            if target_index >= len(band):
                return {'error': f'Invalid target index: {target_index}'}

            target_minion = band[target_index]
            old_value = target_minion.get(stat, 0)
            new_value = old_value - reduction_amount

            target_minion[stat] = new_value
            # Also update permanent stats
            permanent_stat = f'permanent_{stat}'
            target_minion[permanent_stat] = target_minion.get(permanent_stat, old_value) - reduction_amount

            run.set_band(band)
            run.set_pending_selection(None)
            return {
                'success': True,
                'results': [f"{target_minion['name']}'s {stat} reduced from {old_value} to {new_value}!"],
                'band_changes': [{'type': 'stat_reduction', 'minion': target_minion['name'], 'stat': stat, 'amount': reduction_amount}],
                'resource_changes': {}
            }

        elif option_type == 'select_for_choice_list':
            # Minion selected for keyword/type removal
            target_index = selected_option['target_index']
            choice_source = selected_option['choice_source']
            available_items = selected_option['available_items']
            on_complete = selected_option.get('on_complete')
            all_or_nothing = selected_option.get('all_or_nothing', False)
            target_minion = band[target_index]
            total_items = len(available_items)

            item_options = []
            source_label = 'keywords' if choice_source == 'keywords' else 'types'

            if all_or_nothing:
                # All-or-nothing mode: Only "Remove All" or "Leave"
                if total_items > 0:
                    item_options.append({
                        'type': 'remove_items_from_minion',
                        'target_index': target_index,
                        'choice_source': choice_source,
                        'available_items': available_items,
                        'remove_count': total_items,
                        'on_complete': on_complete,
                        'message': f"Remove All {source_label.title()}",
                        'id': 'remove_all'
                    })

                # Add "Leave" option to cancel
                item_options.append({
                    'type': 'back_to_parent',
                    'message': 'Leave',
                    'id': 'leave'
                })

                message = f"Remove all {source_label} from {target_minion['name']}? ({', '.join(available_items)})"
            else:
                # Standard mode: Show 1/3/5/all/none options
                preset_amounts = [1, 3, 5]

                for amount in preset_amounts:
                    if amount <= total_items:
                        item_options.append({
                            'type': 'remove_items_from_minion',
                            'target_index': target_index,
                            'choice_source': choice_source,
                            'available_items': available_items,
                            'remove_count': amount,
                            'on_complete': on_complete,
                            'message': f"{amount}",
                            'id': f'remove_{amount}'
                        })

                # Add "All" option
                if total_items > 0:
                    item_options.append({
                        'type': 'remove_items_from_minion',
                        'target_index': target_index,
                        'choice_source': choice_source,
                        'available_items': available_items,
                        'remove_count': total_items,
                        'on_complete': on_complete,
                        'message': f"All ({total_items})",
                        'id': 'remove_all'
                    })

                # Add "None" option to cancel
                item_options.append({
                    'type': 'back_to_parent',
                    'message': 'None',
                    'id': 'none'
                })

                message = f"How many {source_label} to remove from {target_minion['name']}? (has: {', '.join(available_items)})"

            item_selection = {
                'event_type': 'item_selection',
                'title': f'Remove {choice_source.title()}',
                'message': message,
                'options': item_options,
                'min_selections': 1,
                'max_selections': 1,
                'repeating': False,
                'leaveable': True,
                'template_event': template_event
            }

            run.set_pending_selection(item_selection)
            return {
                'success': True,
                'item_selection': True,
                'message': f'Choose how many to remove from {target_minion["name"]}',
                'results': [],
                'band_changes': [],
                'resource_changes': {}
            }

        elif option_type == 'remove_items_from_minion':
            # Remove multiple keywords or types based on count
            target_index = selected_option['target_index']
            choice_source = selected_option['choice_source']
            available_items = selected_option['available_items']
            remove_count = selected_option['remove_count']

            if target_index >= len(band):
                return {'error': f'Invalid target index: {target_index}'}

            target_minion = band[target_index]
            items_to_remove = available_items[:remove_count]

            if choice_source == 'keywords':
                keywords = target_minion.get('keywords', [])
                removed = []
                for item in items_to_remove:
                    if item in keywords:
                        keywords.remove(item)
                        removed.append(item)
                target_minion['keywords'] = keywords
                result_msg = f"Removed {', '.join(removed)} from {target_minion['name']}!" if removed else "Nothing removed."
            else:  # types
                minion_type = target_minion.get('type', 'None')
                removed = []
                if isinstance(minion_type, list):
                    for item in items_to_remove:
                        if item in minion_type:
                            minion_type.remove(item)
                            removed.append(item)
                    target_minion['type'] = minion_type if minion_type else 'None'
                elif minion_type in items_to_remove:
                    removed.append(minion_type)
                    target_minion['type'] = 'None'
                result_msg = f"Removed {', '.join(removed)} type(s) from {target_minion['name']}!" if removed else "Nothing removed."

            run.set_band(band)
            run.set_pending_selection(None)
            return {
                'success': True,
                'results': [result_msg],
                'band_changes': [{'type': 'item_removal', 'minion': target_minion['name'], 'items': removed}],
                'resource_changes': {}
            }

        elif option_type == 'sacrifice_target':
            # Remove a minion from the band (sacrifice)
            # NOTE: Sacrifice does NOT trigger death_toll, on_death, or any other death effects
            # It's a clean removal, not a combat death
            target_index = selected_option['target_index']
            on_sacrifice = selected_option.get('on_sacrifice')

            if target_index >= len(band):
                return {'error': f'Invalid sacrifice target: {target_index}'}

            sacrificed_minion = band[target_index]
            sacrificed_name = sacrificed_minion['name']
            sacrificed_attack = sacrificed_minion.get('attack', 0)
            sacrificed_health = sacrificed_minion.get('health', 0)

            # For Feed Your Pack, defer the actual removal until a beast is selected
            # so cancelling restores the minion automatically
            if on_sacrifice == 'store_feed_sacrifice':
                event_state['feed_sacrifice_stats'] = {
                    'name': sacrificed_name,
                    'attack': sacrificed_attack,
                    'health': sacrificed_health,
                    'index': target_index
                }
                run.set_event_state(event_state)
                results = [f'{sacrificed_name} selected for sacrifice (+{sacrificed_attack}/+{sacrificed_health})!']
            else:
                # Remove the minion from band immediately (no death triggers)
                band.pop(target_index)

                # Update positions for remaining minions
                for i, minion in enumerate(band):
                    minion['position'] = i

                run.set_band(band)
                results = [f'{sacrificed_name} was sacrificed!']

                # Handle on_sacrifice callback (e.g., ivory_tower_decrease_seal)
                if on_sacrifice == 'ivory_tower_decrease_seal':
                    if 'ivory_tower_seal' not in event_state:
                        event_state['ivory_tower_seal'] = 4
                    event_state['ivory_tower_seal'] = event_state.get('ivory_tower_seal', 4) - 1
                    run.set_event_state(event_state)
                    results.append(f'Seal weakened to {event_state["ivory_tower_seal"]}!')

            run.set_pending_selection(None)

            # Check for chaining: return_to_event in parameters, or on_complete on the screen
            return_to_event = None
            if template_event:
                for screen in template_event.get('screens', []):
                    rte = screen.get('parameters', {}).get('return_to_event') or screen.get('on_complete')
                    if rte:
                        return_to_event = rte
                        break

            if return_to_event:
                from game_engine.events.event_system import EventSystem
                EventSystem.create_event_selection(run, return_to_event)
                results.append(f'Returning to {return_to_event}...')

            return {
                'success': True,
                'results': results,
                'band_changes': [{'type': 'sacrifice', 'minion': sacrificed_name}],
                'resource_changes': {}
            }

        elif option_type == 'bounty_target':
            # Player selected a bounty target - store in event_state
            bounty_minion_name = selected_option.get('message', 'Unknown')
            bounty_gold = selected_option.get('bounty_gold', 5)

            event_state['bounty_mark'] = {
                'minion_name': bounty_minion_name,
                'gold_reward': bounty_gold
            }
            run.set_event_state(event_state)

            run.set_pending_selection(None)
            return {
                'success': True,
                'results': [f'Bounty set on {bounty_minion_name}! Earn {bounty_gold} gold per kill.'],
                'band_changes': [],
                'resource_changes': {}
            }

        # Process on_select actions via the effect registry
        on_select = selected_option.get('on_select')
        tier = run.current_ring
        band = run.get_band()

        if on_select:
            from game_engine.events.effect_actions import execute_on_select
            failure = execute_on_select(
                on_select, run, tier, band, event_state, resources,
                results, selected_option)
            if failure:
                return failure

        # Clear current selection
        run.set_pending_selection(None)

        # Check if event should be marked complete
        if selected_option.get('mark_event_complete'):
            # TODO: Implement event pool removal
            results.append('Event completed!')

        # Chain to next event (modular event-to-event transitions)
        if next_event_id:
            from game_engine.events.event_system import EventSystem
            # Store back context for the chained event based on how we got here
            # If gold was paid, the back option should refund that gold and return to parent
            if gold_cost > 0:
                event_state['pending_back_label'] = 'Go back to selection'
                event_state['pending_back_refund'] = gold_cost
                # Store the parent event ID so we can return to it
                event_state['pending_back_event'] = template_event.get('id')
                run.set_event_state(event_state)
            else:
                # No gold paid - back returns to parent event to re-choose
                event_state['pending_back_label'] = 'Back'
                event_state['pending_back_refund'] = 0
                event_state['pending_back_event'] = template_event.get('id')  # Return to choice screen
                run.set_event_state(event_state)
            EventSystem.create_event_selection(run, next_event_id)
            results.append(f'Transitioning to {next_event_id}...')

        # Chain to next screen or end event
        elif next_screen_id:
            # Find the next screen in the template
            next_screen = None
            for screen in template_event.get('screens', []):
                if screen.get('id') == next_screen_id:
                    next_screen = screen
                    break

            if next_screen:
                # Create the next screen's selection using the specific screen handler
                from game_engine.events.event_system import EventSystem
                screen_type = next_screen.get('type')
                parameters = next_screen.get('parameters', {})

                if screen_type == 'select_buff_target':
                    # Chain to blessing screen
                    # Check both buff_type and buff_power for backwards compatibility
                    buff_type = parameters.get('buff_type') or parameters.get('buff_power')

                    if buff_type == 'ring':
                        # Special Ring X keyword blessing
                        ring_value = parameters.get('ring_value', 'tier')
                        if ring_value == 'tier':
                            ring_value = run.current_ring

                        # Create selection to apply Ring X keyword
                        band = run.get_band()
                        target_options = []

                        for i, minion in enumerate(band):
                            target_options.append({
                                'type': 'apply_ring_keyword',
                                'ring_value': ring_value,
                                'target_index': i,
                                'data': minion,  # Include full minion data for UI rendering
                                'message': f"Give Ring {ring_value} to {minion['name']}",
                                'id': f'target_{i}'
                            })

                        ring_selection = {
                            'event_type': 'ring_blessing',
                            'title': parameters.get('title', 'Blessing of the Bell Tower'),
                            'message': parameters.get('message', f'Choose a minion to receive Ring {ring_value}'),
                            'current_band': band,
                            'options': target_options,
                            'min_selections': 1,
                            'max_selections': 1
                        }

                        run.set_pending_selection(ring_selection)
                        results.append(f'Choose a minion for Ring {ring_value}...')

                    elif buff_type.startswith('keyword_'):
                        # Grant a keyword to a minion
                        keyword = buff_type.replace('keyword_', '')
                        band = run.get_band()
                        target_options = []

                        for i, minion in enumerate(band):
                            # Check if minion already has this keyword
                            has_keyword = keyword in minion.get('keywords', [])
                            target_options.append({
                                'type': 'apply_keyword',
                                'keyword': keyword,
                                'target_index': i,
                                'data': minion,  # Include full minion data for UI rendering
                                'message': f"Give {keyword.title()} to {minion['name']}" + (" (already has)" if has_keyword else ""),
                                'id': f'target_{i}',
                                'disabled': has_keyword
                            })

                        keyword_selection = {
                            'event_type': 'keyword_grant',
                            'title': parameters.get('title', f'Grant {keyword.title()}'),
                            'message': parameters.get('message', f'Choose a minion to receive {keyword.title()}'),
                            'current_band': band,
                            'options': target_options,
                            'min_selections': 1,
                            'max_selections': 1
                        }

                        run.set_pending_selection(keyword_selection)
                        results.append(f'Choose a minion for {keyword.title()}...')

                    else:
                        # Normal buff event (all use buff_event now, scales with ring)
                        EventSystem._create_scaling_buff_selection(run, 'buff_event')
                        results.append('Choose a blessing...')

                elif screen_type == 'combat':
                    # Chain to combat screen
                    difficulty = parameters.get('difficulty', 'normal')
                    event_type_map = {
                        'normal': 'combat_event',
                        'hard': 'combat_event_hard'
                    }
                    mapped_event_type = event_type_map.get(difficulty, 'combat_event')
                    EventSystem._create_scaling_combat_selection(run, mapped_event_type)
                    results.append('Entering combat...')

                elif screen_type == 'grant_minion':
                    # Chain to minion grant screen
                    EventSystem._create_specific_minion_selection(
                        run,
                        minion_name=parameters.get('minion_name'),
                        tier=parameters.get('tier', 1),
                        title=parameters.get('title', 'New Ally'),
                        message=parameters.get('message', 'A minion joins your band!')
                    )
                    results.append('A new ally appears!')

                else:
                    # Unknown screen type - just end the event
                    results.append(f'Screen type {screen_type} not yet implemented')

        return {
            'success': True,
            'results': results,
            'band_changes': [],
            'resource_changes': {}
        }

    @staticmethod
    def resolve_selection(run, selection_ids):
        """Resolve player's selection choices with full backend validation"""
        pending = run.get_pending_selection()
        if not pending:
            return {'error': 'No pending selection'}

        # Optimistic lock: prevent concurrent selection resolution
        # Skip DB lock for dev/mock runs (no real DB row)
        if getattr(run, '_dev_mode_mock', False):
            run.selection_version = getattr(run, 'selection_version', 0) + 1
        else:
            from models import db
            from sqlalchemy import text
            expected_version = run.selection_version or 0
            rows = db.session.execute(
                text("UPDATE runs SET selection_version = selection_version + 1 "
                     "WHERE id = :id AND selection_version = :ver"),
                {'id': run.id, 'ver': expected_version}
            ).rowcount
            if rows == 0:
                return {'error': 'Selection already processed'}
            run.selection_version = expected_version + 1

        # Debug logging
        logger.debug(f"DEBUG resolve_selection: event_type={pending.get('event_type')}, selection_ids={selection_ids}")
        logger.debug(f"  Options in pending: {[opt.get('id') for opt in pending.get('options', [])]}")

        # STEP 1: Validate selection limits and basic validity
        limits_validation = SelectionSystem.validate_selection_limits(pending, selection_ids)
        if not limits_validation['valid']:
            return {'error': limits_validation['error']}

        # STEP 2: Validate current game state hasn't invalidated selections
        state_validation = SelectionSystem.validate_selection_state(run, pending, selection_ids)
        if not state_validation['valid']:
            return {'error': state_validation['error']}

        # Handle split event selection
        if pending.get('event_type') == 'split_event':
            if len(selection_ids) != 1:
                return {'error': 'Must choose exactly one event'}

            # Find the chosen event
            chosen_option = None
            for option in pending['options']:
                if option['id'] == selection_ids[0]:
                    chosen_option = option
                    break

            if not chosen_option:
                return {'error': 'Invalid event choice'}

            # Clear the split selection
            run.set_pending_selection(None)

            # Create the chosen event selection
            chosen_event_type = chosen_option['event_type']
            from game_engine.events.event_system import EventSystem
            event_result = EventSystem.create_event_selection(run, chosen_event_type)

            return {
                'success': True,
                'results': [f'Chose: {chosen_option["message"]}'],
                'event_result': event_result,
                'chosen_event': chosen_event_type,
                'band_changes': [],
                'resource_changes': {}
            }

        # Handle branching choice selection (delegated to GameLogic)
        if pending.get('event_type') == 'branching_choice':
            # This should be handled by GameLogic._resolve_branching_choice_selection
            # But we include a fallback here
            return {'error': 'Branching choice should be handled by GameLogic'}

        # Handle template event screen chaining (continue buttons and choices)
        if 'template_event' in pending:
            return SelectionSystem._resolve_template_event_selection(run, pending, selection_ids)

        band = run.get_band()
        resources = run.get_resources()
        results = []
        selected_for_combine = []  # Initialize list for combine selections

        for selection_id in selection_ids:
            # Find the selected option
            option = None
            for opt in pending['options']:
                if opt['id'] == selection_id:
                    option = opt
                    break

            if not option:
                continue

            elif option['type'] == 'branching_choice_option':
                # This shouldn't happen here - should be handled by GameLogic
                results.append(f"Branching choice handling error: {option.get('message', 'Unknown choice')}")

            elif option['type'] == 'choose_buff':
                # Create target minion selection for buff application
                buff_data = option['buff_data']

                # Create target selection options
                target_options = []
                for i, minion in enumerate(band):
                    target_options.append({
                        'type': 'apply_targeted_effect',
                        'render_as': 'apply_targeted_effect',
                        'effect_type': 'buff',
                        'effect_data': buff_data,
                        'target_index': i,
                        'data': minion,  # Include full minion data for UI rendering
                        'message': f"Apply to {minion['name']} ({format_minion_stats(minion['health'], minion['attack'])})",
                        'id': f'target_{i}'
                    })

                # Only add back button if the event is leaveable (has skip option)
                if pending.get('leaveable', True):
                    target_options.append({
                        'type': 'back',
                        'message': 'Back to blessing selection',
                        'id': 'back'
                    })

                target_selection = {
                    'event_type': 'target_minion',
                    'title': 'Blessing',
                    'effect_preview': {
                        'name': buff_data['name'],
                        'description': buff_data['description'],
                        'type': 'buff'  # Use 'buff' type for stat buffs
                    },
                    'current_band': band,
                    'previous_selection': pending,  # Store previous state for back navigation
                    'return_to_event': pending.get('return_to_event'),  # Pass along return_to_event
                    'options': target_options,
                    'min_selections': 1,  # Must target exactly 1 minion
                    'max_selections': 1,
                    'repeating': False,
                    'leaveable': pending.get('leaveable', True)
                }

                run.set_pending_selection(target_selection)
                return {
                    'success': True,
                    'target_selection': True,
                    'message': f'Choose target for {buff_data["name"]}',
                    'results': []
                }

            elif option['type'] == 'apply_targeted_effect':
                # Apply the targeted effect to the chosen minion
                effect_type = option['effect_type']
                effect_data = option['effect_data']
                target_index = option['target_index']

                # Additional validation for targeted effects
                if target_index >= len(band):
                    return {'error': f'Invalid target index: {target_index}'}

                if effect_type == 'buff' and target_index < len(band):
                    target_minion = band[target_index]

                    if effect_data['type'] == 'ring':
                        # Apply Ring X keyword (keyword is 'ring', value stored in permanent_ring_count like Cat)
                        ring_value = effect_data['ring_value']

                        if 'keywords' not in target_minion:
                            target_minion['keywords'] = []

                        # Check if minion already has Ring keyword
                        if 'ring' in target_minion['keywords']:
                            # Add to existing permanent_ring_count
                            current_count = target_minion.get('permanent_ring_count', 0)
                            target_minion['permanent_ring_count'] = current_count + ring_value
                            results.append(f"{target_minion['name']}'s Ring increased to {target_minion['permanent_ring_count']}!")
                        else:
                            # Add the ring keyword
                            target_minion['keywords'].append('ring')
                            # Set permanent_ring_count field (like Cat's permanent stats)
                            target_minion['permanent_ring_count'] = ring_value
                            results.append(f"{target_minion['name']} received Ring {ring_value}!")

                    elif effect_data['type'] == 'health':
                        target_minion['health'] += effect_data['amount']
                        # Track as permanent stat so it persists after combat
                        target_minion['permanent_health'] = target_minion.get('permanent_health', 0) + effect_data['amount']
                        results.append(f"{target_minion['name']} gained +{effect_data['amount']} health!")
                    elif effect_data['type'] == 'attack':
                        target_minion['attack'] += effect_data['amount']
                        # Track as permanent stat so it persists after combat
                        target_minion['permanent_attack'] = target_minion.get('permanent_attack', 0) + effect_data['amount']
                        results.append(f"{target_minion['name']} gained +{effect_data['amount']} attack!")
                    elif effect_data['type'] == 'both':
                        target_minion['health'] += effect_data['health']
                        target_minion['attack'] += effect_data['attack']
                        # Track as permanent stats so they persist after combat
                        target_minion['permanent_health'] = target_minion.get('permanent_health', 0) + effect_data['health']
                        target_minion['permanent_attack'] = target_minion.get('permanent_attack', 0) + effect_data['attack']
                        results.append(
                            f"{target_minion['name']} gained +{effect_data['health']} health and +{effect_data['attack']} attack!")
                    elif effect_data['type'] == 'keyword':
                        # Apply a keyword to the target minion
                        keyword = effect_data['keyword']
                        if 'keywords' not in target_minion:
                            target_minion['keywords'] = []
                        if keyword not in target_minion['keywords']:
                            target_minion['keywords'].append(keyword)
                            results.append(f"{target_minion['name']} gained {keyword.title()}!")
                        else:
                            results.append(f"{target_minion['name']} already has {keyword.title()}!")
                    elif effect_data['type'] in ['boss_reward', 'boss_keyword']:
                        # Boss reward effect - apply the effect based on on_select handler
                        on_select = option.get('on_select')
                        if on_select:
                            # Get event state and tier from run
                            event_state = run.get_event_state()
                            tier = run.current_ring

                            # === DIRE PACK ===
                            if on_select == 'boss_reward_dire_pack_keyword':
                                if 'keywords' not in target_minion:
                                    target_minion['keywords'] = []
                                if 'on_any_death' not in target_minion['keywords']:
                                    target_minion['keywords'].append('on_any_death')
                                target_minion['on_any_death_effect'] = {'type': 'buff_stats', 'target': 'self', 'attack': 2, 'health': 2}
                                results.append(f"{target_minion['name']} gained 'On Any Death: +2/+2'")
                                event_state['active_boss'] = None
                                if 'bosses_defeated' not in event_state:
                                    event_state['bosses_defeated'] = {}
                                event_state['bosses_defeated'][str(tier)] = 'dire_pack'

                            # === CONGREGATION ===
                            elif on_select == 'boss_reward_congregation_tribe':
                                target_minion['type'] = 'Cult'
                                results.append(f"{target_minion['name']} is now a Cult minion")
                                event_state['active_boss'] = None
                                if 'bosses_defeated' not in event_state:
                                    event_state['bosses_defeated'] = {}
                                event_state['bosses_defeated'][str(tier)] = 'congregation'

                            elif on_select == 'boss_reward_congregation_ignoble':
                                if 'keywords' not in target_minion:
                                    target_minion['keywords'] = []
                                if 'ignoble' not in target_minion['keywords']:
                                    target_minion['keywords'].append('ignoble')
                                results.append(f"{target_minion['name']} gained Ignoble")
                                event_state['active_boss'] = None
                                if 'bosses_defeated' not in event_state:
                                    event_state['bosses_defeated'] = {}
                                event_state['bosses_defeated'][str(tier)] = 'congregation'

                            # === CHAINED BEAST ===
                            elif on_select == 'boss_reward_chained_stats':
                                target_minion['attack'] = target_minion.get('attack', 0) + 8
                                target_minion['health'] = target_minion.get('health', 0) + 8
                                target_minion['permanent_attack'] = target_minion.get('permanent_attack', 0) + 8
                                target_minion['permanent_health'] = target_minion.get('permanent_health', 0) + 8
                                if 'keywords' not in target_minion:
                                    target_minion['keywords'] = []
                                if 'leap' not in target_minion['keywords']:
                                    target_minion['keywords'].append('leap')
                                target_minion['leap_distance'] = 2
                                results.append(f"{target_minion['name']} gained +8/+8 and Leap 2")
                                event_state['active_boss'] = None
                                if 'bosses_defeated' not in event_state:
                                    event_state['bosses_defeated'] = {}
                                event_state['bosses_defeated'][str(tier)] = 'chained_beast'

                            elif on_select == 'boss_reward_chained_ethereal':
                                if 'keywords' not in target_minion:
                                    target_minion['keywords'] = []
                                if 'ethereal_left' not in target_minion['keywords']:
                                    target_minion['keywords'].append('ethereal_left')
                                if 'cant_cast' not in target_minion['keywords']:
                                    target_minion['keywords'].append('cant_cast')
                                if 'cant_retaliate' not in target_minion['keywords']:
                                    target_minion['keywords'].append('cant_retaliate')
                                results.append(f"{target_minion['name']} gained Ethereal [Left], Can't Cast, Can't Retaliate")
                                event_state['active_boss'] = None
                                if 'bosses_defeated' not in event_state:
                                    event_state['bosses_defeated'] = {}
                                event_state['bosses_defeated'][str(tier)] = 'chained_beast'

                            # === BEHEMOTH ===
                            elif on_select == 'boss_reward_behemoth_tank':
                                target_minion['attack'] = target_minion.get('attack', 0) + 5
                                target_minion['health'] = target_minion.get('health', 0) + 12
                                target_minion['permanent_attack'] = target_minion.get('permanent_attack', 0) + 5
                                target_minion['permanent_health'] = target_minion.get('permanent_health', 0) + 12
                                if 'keywords' not in target_minion:
                                    target_minion['keywords'] = []
                                if 'guard' not in target_minion['keywords']:
                                    target_minion['keywords'].append('guard')
                                results.append(f"{target_minion['name']} gained Guard and +5/+12")
                                event_state['active_boss'] = None
                                if 'bosses_defeated' not in event_state:
                                    event_state['bosses_defeated'] = {}
                                event_state['bosses_defeated'][str(tier)] = 'behemoth'

                            # === VENOMSPAWN ===
                            elif on_select == 'boss_reward_venomspawn_cast':
                                if 'keywords' not in target_minion:
                                    target_minion['keywords'] = []
                                if 'cast' not in target_minion['keywords']:
                                    target_minion['keywords'].append('cast')
                                target_minion['cast_effect'] = {'type': 'damage', 'target': 'all_enemies', 'amount': 2}
                                results.append(f"{target_minion['name']} gained 'Cast: Deal 2 damage to all enemy minions'")
                                event_state['active_boss'] = None
                                if 'bosses_defeated' not in event_state:
                                    event_state['bosses_defeated'] = {}
                                event_state['bosses_defeated'][str(tier)] = 'venomspawn'

                            # === GREATER POSSESSED ===
                            elif on_select == 'boss_reward_possessed_deathtoll':
                                if 'keywords' not in target_minion:
                                    target_minion['keywords'] = []
                                if 'death_toll' not in target_minion['keywords']:
                                    target_minion['keywords'].append('death_toll')
                                target_minion['death_toll_effect'] = {'type': 'summon', 'minion_name': 'Possessed', 'count': 1}
                                results.append(f"{target_minion['name']} gained 'Death Toll: Summon a Possessed'")
                                event_state['active_boss'] = None
                                if 'bosses_defeated' not in event_state:
                                    event_state['bosses_defeated'] = {}
                                event_state['bosses_defeated'][str(tier)] = 'greater_possessed'

                            # Save the band and event state
                            run.set_band(band)
                            run.set_event_state(event_state)
                    elif effect_data['type'] == 'feed_sacrifice':
                        # Feed Your Pack - sacrifice the minion now and apply its stats to target
                        event_state = run.get_event_state()
                        feed_stats = event_state.get('feed_sacrifice_stats', {})
                        atk = feed_stats.get('attack', 0)
                        hp = feed_stats.get('health', 0)
                        name = feed_stats.get('name', 'minion')
                        sacrifice_index = feed_stats.get('index')

                        # Now actually remove the sacrificed minion from band
                        band = run.get_band()
                        if sacrifice_index is not None and sacrifice_index < len(band):
                            band.pop(sacrifice_index)
                            for i, m in enumerate(band):
                                m['position'] = i
                            # Adjust target_index if it was after the sacrificed minion
                            if target_index > sacrifice_index:
                                target_index -= 1
                            target_minion = band[target_index]

                        target_minion['attack'] = target_minion.get('attack', 0) + atk
                        target_minion['health'] = target_minion.get('health', 0) + hp
                        target_minion['permanent_attack'] = target_minion.get('permanent_attack', 0) + atk
                        target_minion['permanent_health'] = target_minion.get('permanent_health', 0) + hp

                        run.set_band(band)

                        # Clear the feed sacrifice stats
                        event_state.pop('feed_sacrifice_stats', None)
                        run.set_event_state(event_state)

                        results.append(f"{name} was sacrificed!")
                        results.append(f"{target_minion['name']} consumed {name}'s essence: +{atk}/+{hp}!")
                    elif effect_data['type'] == 'duel':
                        # Chain to duel combat - store champion index and create combat
                        event_state = run.get_event_state()
                        event_state['champion_index'] = target_index
                        event_state['duel_buff_per_tier'] = effect_data.get('buff_per_tier', 3)
                        run.set_event_state(event_state)

                        # Create duel combat selection
                        from game_engine.events.event_system import EventSystem
                        EventSystem._create_duel_combat_selection(
                            run,
                            champion_index=target_index,
                            on_victory_event=None,  # Handle buff inline after combat
                            title='⚔️ Duel'
                        )
                        return {
                            'success': True,
                            'duel_combat': True,
                            'message': f'{target_minion["name"]} enters the duel!',
                            'results': [f'{target_minion["name"]} enters the duel!'],
                            'band_changes': [],
                            'resource_changes': {}
                        }

                    # After applying buff, check if we should return to parent event
                    return_to_event = pending.get('return_to_event')
                    if return_to_event:
                        from game_engine.events.event_system import EventSystem
                        run.set_pending_selection(None)
                        EventSystem.create_event_selection(run, return_to_event)
                        return {
                            'success': True,
                            'results': results,
                            'band_changes': results,
                            'resource_changes': {},
                            'returned_to_event': return_to_event
                        }

            elif option['type'] == 'buff':
                # Legacy buff handling (keep for compatibility)
                target_idx = option['target_index']
                if target_idx >= len(band):
                    return {'error': f'Invalid target index: {target_idx}'}

                if target_idx < len(band):
                    stat = option['stat']
                    amount = option['amount']
                    band[target_idx][stat] += amount
                    # Track as permanent stat so it persists after combat
                    permanent_stat = f'permanent_{stat}'
                    band[target_idx][permanent_stat] = band[target_idx].get(permanent_stat, 0) + amount
                    results.append(f"{band[target_idx]['name']} gained +{amount} {stat}!")

            elif option['type'] == 'minion':
                # Add minion to band (should have space) - ensure band ID is assigned
                effective_max = get_effective_max_band_size(run)
                if len(band) >= effective_max:
                    return {'error': 'Band is full, cannot add minion'}

                minion = option['data'].copy()
                minion['position'] = len(band)
                # Ensure keywords and golden fields exist
                if 'keywords' not in minion:
                    minion['keywords'] = []
                if 'golden' not in minion:
                    minion['golden'] = False
                # Ensure minion has a band_id
                if 'band_id' not in minion:
                    minion['band_id'] = generate_unique_minion_id()
                band.append(minion)
                results.append(f"Added {minion['name']} to your band!")

            elif option['type'] == 'replacement':
                # Handle replacement selection - this needs special handling
                # The actual replacement happens in a follow-up selection
                new_minion = option['data'].copy()

                # Create replacement choice selection
                replacement_options = []
                for i, existing_minion in enumerate(band):
                    replacement_options.append({
                        'type': 'replace_with',
                        'render_as': 'replace_with',
                        'new_minion': new_minion,
                        'replace_index': i,
                        'message': f"Replace {existing_minion['name']} ({format_minion_stats(existing_minion['health'], existing_minion['attack'])})",
                        'id': f'replace_with_{i}'
                    })

                replacement_options.append({
                    'type': 'back',
                    'message': 'Back to minion selection',
                    'id': 'back'
                })

                replacement_selection = {
                    'event_type': 'confirm_replacement',
                    'title': f'Replace Minion',
                    'message': f'Choose which minion to replace with {new_minion["name"]} ({format_minion_stats(new_minion["health"], new_minion["attack"])}):',
                    'new_minion': new_minion,
                    'previous_selection': pending,  # Store previous state for back navigation
                    'options': replacement_options,
                    'min_selections': 1,  # Must choose exactly 1 minion to replace
                    'max_selections': 1,
                    'repeating': False,
                    'leaveable': True
                }

                run.set_pending_selection(replacement_selection)
                return {
                    'success': True,
                    'replacement_choice': True,
                    'message': f'Choose which minion to replace with {new_minion["name"]}',
                    'results': []
                }

            elif option['type'] == 'replace_with':
                # Actually perform the replacement - preserve band_id from replaced minion
                new_minion = option['new_minion']
                replace_index = option['replace_index']

                if replace_index >= len(band):
                    return {'error': f'Invalid replacement index: {replace_index}'}

                if replace_index < len(band):
                    old_minion = band[replace_index]
                    new_minion['position'] = replace_index
                    # Preserve the band_id from the old minion
                    if 'band_id' in old_minion:
                        new_minion['band_id'] = old_minion['band_id']
                    else:
                        # Fallback: assign new band_id if old minion somehow doesn't have one
                        new_minion['band_id'] = generate_unique_minion_id()
                    # Ensure keywords and golden fields exist
                    if 'keywords' not in new_minion:
                        new_minion['keywords'] = []
                    if 'golden' not in new_minion:
                        new_minion['golden'] = False
                    band[replace_index] = new_minion
                    results.append(f"Replaced {old_minion['name']} with {new_minion['name']}!")

            elif option['type'] == 'purchase':
                # Buy minion if affordable and space available - ensure band ID is assigned
                cost = option['cost']

                # Re-validate affordability
                if resources['gold'] < cost:
                    return {'error': f'Cannot afford {option["data"]["name"]} - insufficient gold'}

                effective_max = get_effective_max_band_size(run)
                if len(band) >= effective_max:
                    return {'error': f'Band is full! Cannot buy {option["data"]["name"]}'}

                minion = option['data'].copy()
                minion['position'] = len(band)
                # Ensure keywords and golden fields exist
                if 'keywords' not in minion:
                    minion['keywords'] = []
                if 'golden' not in minion:
                    minion['golden'] = False
                # Ensure minion has a band_id
                if 'band_id' not in minion:
                    minion['band_id'] = generate_unique_minion_id()
                band.append(minion)
                resources['gold'] -= cost
                results.append(f"Bought {minion['name']} for {cost} gold!")

            elif option['type'] == 'shop_replacement':
                # Shop purchase requiring replacement
                cost = option['cost']

                # Re-validate affordability
                if resources['gold'] < cost:
                    return {'error': f'Cannot afford {option["data"]["name"]} - insufficient gold'}

                new_minion = option['data'].copy()

                # Create replacement choice selection
                replacement_options = []
                for i, existing_minion in enumerate(band):
                    replacement_options.append({
                        'type': 'shop_replace_with',
                        'render_as': 'shop_replace_with',
                        'new_minion': new_minion,
                        'replace_index': i,
                        'cost': cost,
                        'message': f"Replace {existing_minion['name']} ({format_minion_stats(existing_minion['health'], existing_minion['attack'])})",
                        'id': f'shop_replace_with_{i}'
                    })

                replacement_options.append({
                    'type': 'back',
                    'message': 'Back to shop',
                    'id': 'back'
                })

                replacement_selection = {
                    'event_type': 'confirm_shop_replacement',
                    'title': f'Replace Minion',
                    'message': f'Choose which minion to replace with {new_minion["name"]} ({format_minion_stats(new_minion["health"], new_minion["attack"])}) for {cost} gold:',
                    'new_minion': new_minion,
                    'cost': cost,
                    'previous_selection': pending,  # Store previous state for back navigation
                    'options': replacement_options,
                    'min_selections': 1,  # Must choose exactly 1 minion to replace
                    'max_selections': 1,
                    'repeating': False,
                    'leaveable': True,
                    'return_to_event': pending.get('return_to_event')  # Pass through return event
                }

                run.set_pending_selection(replacement_selection)
                return {
                    'success': True,
                    'replacement_choice': True,
                    'message': f'Choose which minion to replace with {new_minion["name"]} for {cost} gold',
                    'results': []
                }

            elif option['type'] == 'shop_replace_with':
                # Actually perform the shop replacement - preserve band_id from replaced minion
                new_minion = option['new_minion']
                replace_index = option['replace_index']
                cost = option['cost']

                # Re-validate affordability and index
                if resources['gold'] < cost:
                    return {'error': f'Cannot afford replacement - insufficient gold'}
                if replace_index >= len(band):
                    return {'error': f'Invalid replacement index: {replace_index}'}

                if replace_index < len(band):
                    old_minion = band[replace_index]
                    new_minion['position'] = replace_index
                    # Preserve the band_id from the old minion
                    if 'band_id' in old_minion:
                        new_minion['band_id'] = old_minion['band_id']
                    else:
                        # Fallback: assign new band_id if old minion somehow doesn't have one
                        new_minion['band_id'] = generate_unique_minion_id()
                    # Ensure keywords and golden fields exist
                    if 'keywords' not in new_minion:
                        new_minion['keywords'] = []
                    if 'golden' not in new_minion:
                        new_minion['golden'] = False
                    band[replace_index] = new_minion
                    resources['gold'] -= cost
                    run.set_band(band)
                    run.set_resources(resources)
                    results.append(f"Replaced {old_minion['name']} with {new_minion['name']} for {cost} gold!")

                    # Check if we should return to a parent event
                    return_to_event = pending.get('return_to_event')
                    if return_to_event:
                        from game_engine.events.event_system import EventSystem
                        run.set_pending_selection(None)
                        EventSystem.create_event_selection(run, return_to_event)
                        return {
                            'success': True,
                            'results': results,
                            'band_changes': [{'type': 'replace', 'old': old_minion['name'], 'new': new_minion['name']}],
                            'resource_changes': {'gold': -cost},
                            'returned_to_event': return_to_event
                        }

            elif option['type'] == 'back':
                # Navigate back to previous selection
                if pending.get('previous_selection'):
                    previous_selection = pending['previous_selection']
                    run.set_pending_selection(previous_selection)
                    return {
                        'success': True,
                        'back_navigation': True,
                        'message': 'Returned to previous selection',
                        'results': ['Returned to previous selection']
                    }
                else:
                    # No previous selection stored - this shouldn't happen
                    results.append("No previous selection available.")

            elif option['type'] == 'back_with_refund':
                # Back option that refunds gold (used for paid events like bell tower)
                refund_amount = option.get('refund_amount', 0)
                return_to_event = option.get('return_to_event')

                # Refund gold if there was a cost
                if refund_amount > 0:
                    resources['gold'] = resources.get('gold', 0) + refund_amount
                    run.set_resources(resources)
                    results.append(f'Refunded {refund_amount} gold')

                # Clear current selection first
                run.set_pending_selection(None)

                # Return to parent event if specified, otherwise just end
                if return_to_event:
                    from game_engine.events.event_system import EventSystem
                    EventSystem.create_event_selection(run, return_to_event)
                    results.append(f'Returned to {return_to_event}')

                return {
                    'success': True,
                    'back_navigation': True,
                    'message': option.get('message', 'Cancelled'),
                    'results': results,
                    'band_changes': [],
                    'resource_changes': {'gold': refund_amount} if refund_amount > 0 else {}
                }

            elif option['type'] == 'select_minion_for_combine':
                # Track selected minions for combining
                minion_index = option['minion_index']

                # Additional validation for combine selection
                if minion_index >= len(band):
                    return {'error': f'Invalid minion index for combining: {minion_index}'}

                selected_for_combine.append(minion_index)

            elif option['type'] == 'apply_ring_keyword':
                # Apply Ring X keyword to the target minion
                target_index = option['target_index']
                ring_value = option['ring_value']

                if target_index >= len(band):
                    return {'error': f'Invalid target index: {target_index}'}

                target_minion = band[target_index]

                # Initialize keywords if needed
                if 'keywords' not in target_minion:
                    target_minion['keywords'] = []

                # Check if minion already has Ring keyword
                if 'ring' in target_minion['keywords']:
                    # Add to existing permanent_ring_count
                    current_count = target_minion.get('permanent_ring_count', 0)
                    target_minion['permanent_ring_count'] = current_count + ring_value
                    logger.debug(f"[BELL_TOWER] {target_minion['name']} already has ring, increased permanent_ring_count: {current_count} -> {target_minion['permanent_ring_count']}")
                    results.append(f"{target_minion['name']}'s Ring increased to {target_minion['permanent_ring_count']}!")
                else:
                    # Add the ring keyword
                    target_minion['keywords'].append('ring')
                    # Set permanent_ring_count field (like Cat's permanent stats)
                    target_minion['permanent_ring_count'] = ring_value
                    logger.debug(f"[BELL_TOWER] {target_minion['name']} received ring keyword, set permanent_ring_count to {ring_value}")
                    logger.debug(f"[BELL_TOWER] Band minion keywords: {target_minion.get('keywords')}")
                    logger.debug(f"[BELL_TOWER] Band minion permanent_ring_count: {target_minion.get('permanent_ring_count')}")
                    results.append(f"{target_minion['name']} received Ring {ring_value}!")

            elif option['type'] == 'apply_keyword':
                # Apply a keyword to the target minion
                target_index = option['target_index']
                keyword = option['keyword']

                if target_index >= len(band):
                    return {'error': f'Invalid target index: {target_index}'}

                target_minion = band[target_index]

                # Initialize keywords if needed
                if 'keywords' not in target_minion:
                    target_minion['keywords'] = []

                # Check if minion already has this keyword
                if keyword in target_minion['keywords']:
                    results.append(f"{target_minion['name']} already has {keyword.title()}!")
                else:
                    target_minion['keywords'].append(keyword)
                    results.append(f"{target_minion['name']} received {keyword.title()}!")

            elif option['type'] == 'select_champion_target':
                # Store champion index and chain to duel combat
                champion_index = option['target_index']
                champion = band[champion_index]

                # Store champion_index in event_state for the duel combat
                event_state = run.get_event_state()
                event_state['champion_index'] = champion_index
                run.set_event_state(event_state)

                results.append(f"{champion['name']} steps forward as your champion!")

                # Chain to duel_combat screen (look for it in duel_template_event)
                template_event = pending.get('duel_template_event')
                if template_event:
                    # Find the duel_combat screen in the template
                    for screen in template_event.get('screens', []):
                        if screen.get('type') == 'duel_combat':
                            from game_engine.events.event_system import EventSystem
                            # Create the duel combat using the helper
                            on_victory_event = screen.get('on_victory_event')
                            on_defeat_event = screen.get('on_defeat_event')
                            parameters = screen.get('parameters', {})
                            title = parameters.get('title', '⚔️ Duel')
                            disable_gold_reward = parameters.get('disable_gold_reward', True)
                            disable_health_loss = parameters.get('disable_health_loss', True)

                            EventSystem._create_duel_combat_selection(
                                run,
                                champion_index=champion_index,
                                on_victory_event=on_victory_event,
                                on_defeat_event=on_defeat_event,
                                disable_gold_reward=disable_gold_reward,
                                disable_health_loss=disable_health_loss,
                                title=title
                            )
                            return {
                                'success': True,
                                'champion_selected': True,
                                'message': f'{champion["name"]} enters the duel!',
                                'results': results,
                                'band_changes': [],
                                'resource_changes': {}
                            }

                # Fallback: no duel_combat screen found
                return {'error': 'No duel combat screen configured'}

            elif option['type'] == 'sacrifice_target':
                # Remove a minion from the band (sacrifice)
                target_index = option['target_index']
                on_sacrifice = option.get('on_sacrifice')

                if target_index >= len(band):
                    return {'error': f'Invalid sacrifice target: {target_index}'}

                sacrificed_minion = band[target_index]
                sacrificed_name = sacrificed_minion['name']

                # Remove the minion from band
                band.pop(target_index)

                # Update positions for remaining minions
                for i, minion in enumerate(band):
                    minion['position'] = i

                run.set_band(band)
                results.append(f'{sacrificed_name} was sacrificed!')

                # Process on_sacrifice handler (e.g., ivory_tower_decrease_seal)
                event_state = run.get_event_state()
                if on_sacrifice == 'ivory_tower_decrease_seal':
                    if 'ivory_tower_seal' not in event_state:
                        event_state['ivory_tower_seal'] = 4
                    event_state['ivory_tower_seal'] = event_state.get('ivory_tower_seal', 4) - 1
                    run.set_event_state(event_state)
                    results.append(f'Seal weakened to {event_state["ivory_tower_seal"]}!')

            elif option['type'] == 'golden_target':
                # Make a minion golden
                target_index = option['target_index']

                if target_index >= len(band):
                    return {'error': f'Invalid golden target: {target_index}'}

                target_minion = band[target_index]

                # Check if already golden
                if target_minion.get('golden', False):
                    return {'error': f'{target_minion["name"]} is already golden!'}

                # Make the minion golden - double stats
                target_minion['golden'] = True
                target_minion['health'] = target_minion.get('health', 1) * 2
                target_minion['attack'] = target_minion.get('attack', 1) * 2

                run.set_band(band)
                results.append(f'{target_minion["name"]} has been transformed into a golden version!')

            elif option['type'] == 'select_for_number_choice':
                # Minion selected for stat reduction - show 1/3/5/all/none options
                target_index = option['target_index']
                stat = option['stat']
                min_value = option['min_value']
                current_value = option['current_value']
                max_reduction = option['max_reduction']
                on_complete = option.get('on_complete')
                target_minion = band[target_index]

                # Create 1/3/5/all/none selection options
                number_options = []
                preset_amounts = [1, 3, 5]

                for amount in preset_amounts:
                    if amount <= max_reduction:
                        new_value = current_value - amount
                        number_options.append({
                            'type': 'apply_stat_reduction',
                            'target_index': target_index,
                            'stat': stat,
                            'reduction_amount': amount,
                            'new_value': new_value,
                            'on_complete': on_complete,
                            'message': f"{amount}",
                            'id': f'reduce_{amount}'
                        })

                # Add "All" option (reduce to min_value)
                if max_reduction > 0:
                    all_reduction = max_reduction  # This brings stat down to min_value
                    new_value = current_value - all_reduction
                    number_options.append({
                        'type': 'apply_stat_reduction',
                        'target_index': target_index,
                        'stat': stat,
                        'reduction_amount': all_reduction,
                        'new_value': new_value,
                        'on_complete': on_complete,
                        'message': f"All ({all_reduction})",
                        'id': 'reduce_all'
                    })

                # Add "None" option to cancel
                number_options.append({
                    'type': 'back_to_parent',
                    'message': 'None',
                    'id': 'none'
                })

                number_selection = {
                    'event_type': 'number_selection',
                    'title': f'Reduce {stat.title()}',
                    'message': f"How much {stat} to remove from {target_minion['name']}? (current: {current_value})",
                    'options': number_options,
                    'min_selections': 1,
                    'max_selections': 1,
                    'repeating': False,
                    'leaveable': True
                }

                run.set_pending_selection(number_selection)
                return {
                    'success': True,
                    'number_selection': True,
                    'message': f'Choose reduction amount',
                    'results': []
                }

            elif option['type'] == 'apply_stat_reduction':
                # Actually apply the stat reduction
                target_index = option['target_index']
                stat = option['stat']
                reduction_amount = option['reduction_amount']

                if target_index >= len(band):
                    return {'error': f'Invalid target index: {target_index}'}

                target_minion = band[target_index]
                old_value = target_minion.get(stat, 0)
                new_value = old_value - reduction_amount

                target_minion[stat] = new_value
                # Also update permanent stats
                permanent_stat = f'permanent_{stat}'
                target_minion[permanent_stat] = target_minion.get(permanent_stat, 0) - reduction_amount

                run.set_band(band)
                results.append(f"{target_minion['name']}'s {stat} reduced from {old_value} to {new_value}!")

            elif option['type'] == 'select_for_choice_list':
                # Minion selected for keyword/type removal
                target_index = option['target_index']
                choice_source = option['choice_source']
                available_items = option['available_items']
                on_complete = option.get('on_complete')
                all_or_nothing = option.get('all_or_nothing', False)
                target_minion = band[target_index]
                total_items = len(available_items)

                item_options = []
                source_label = 'keywords' if choice_source == 'keywords' else 'types'

                if all_or_nothing:
                    # All-or-nothing mode: Only "Remove All" or "Leave"
                    if total_items > 0:
                        item_options.append({
                            'type': 'remove_items_from_minion',
                            'target_index': target_index,
                            'choice_source': choice_source,
                            'available_items': available_items,
                            'remove_count': total_items,
                            'on_complete': on_complete,
                            'message': f"Remove All {source_label.title()}",
                            'id': 'remove_all'
                        })

                    item_options.append({
                        'type': 'back_to_parent',
                        'message': 'Leave',
                        'id': 'leave'
                    })

                    message = f"Remove all {source_label} from {target_minion['name']}? ({', '.join(available_items)})"
                else:
                    # Standard mode: Show 1/3/5/all/none options
                    preset_amounts = [1, 3, 5]

                    for amount in preset_amounts:
                        if amount <= total_items:
                            item_options.append({
                                'type': 'remove_items_from_minion',
                                'target_index': target_index,
                                'choice_source': choice_source,
                                'available_items': available_items,
                                'remove_count': amount,
                                'on_complete': on_complete,
                                'message': f"{amount}",
                                'id': f'remove_{amount}'
                            })

                    # Add "All" option
                    if total_items > 0:
                        item_options.append({
                            'type': 'remove_items_from_minion',
                            'target_index': target_index,
                            'choice_source': choice_source,
                            'available_items': available_items,
                            'remove_count': total_items,
                            'on_complete': on_complete,
                            'message': f"All ({total_items})",
                            'id': 'remove_all'
                        })

                    # Add "None" option to cancel
                    item_options.append({
                        'type': 'back_to_parent',
                        'message': 'None',
                        'id': 'none'
                    })

                    message = f"How many {source_label} to remove from {target_minion['name']}? (has: {', '.join(available_items)})"

                item_selection = {
                    'event_type': 'item_selection',
                    'title': f'Remove {choice_source.title()}',
                    'message': message,
                    'options': item_options,
                    'min_selections': 1,
                    'max_selections': 1,
                    'repeating': False,
                    'leaveable': True
                }

                run.set_pending_selection(item_selection)
                return {
                    'success': True,
                    'item_selection': True,
                    'message': f'Choose how many to remove',
                    'results': []
                }

            elif option['type'] == 'remove_item_from_minion':
                # Actually remove a single keyword or type (legacy support)
                target_index = option['target_index']
                choice_source = option['choice_source']
                item_to_remove = option['item_to_remove']

                if target_index >= len(band):
                    return {'error': f'Invalid target index: {target_index}'}

                target_minion = band[target_index]

                if choice_source == 'keywords':
                    keywords = target_minion.get('keywords', [])
                    if item_to_remove in keywords:
                        keywords.remove(item_to_remove)
                        target_minion['keywords'] = keywords
                        results.append(f"Removed {item_to_remove} from {target_minion['name']}!")
                    else:
                        results.append(f"{target_minion['name']} doesn't have {item_to_remove}!")
                else:  # types
                    minion_type = target_minion.get('type', 'None')
                    if isinstance(minion_type, list):
                        if item_to_remove in minion_type:
                            minion_type.remove(item_to_remove)
                            target_minion['type'] = minion_type if minion_type else 'None'
                    elif minion_type == item_to_remove:
                        target_minion['type'] = 'None'
                    results.append(f"Removed {item_to_remove} type from {target_minion['name']}!")

                run.set_band(band)

            elif option['type'] == 'remove_items_from_minion':
                # Remove multiple keywords or types based on count
                target_index = option['target_index']
                choice_source = option['choice_source']
                available_items = option['available_items']
                remove_count = option['remove_count']

                if target_index >= len(band):
                    return {'error': f'Invalid target index: {target_index}'}

                target_minion = band[target_index]
                items_to_remove = available_items[:remove_count]  # Take first N items

                if choice_source == 'keywords':
                    keywords = target_minion.get('keywords', [])
                    removed = []
                    for item in items_to_remove:
                        if item in keywords:
                            keywords.remove(item)
                            removed.append(item)
                    target_minion['keywords'] = keywords
                    if removed:
                        results.append(f"Removed {', '.join(removed)} from {target_minion['name']}!")
                else:  # types
                    minion_type = target_minion.get('type', 'None')
                    removed = []
                    if isinstance(minion_type, list):
                        for item in items_to_remove:
                            if item in minion_type:
                                minion_type.remove(item)
                                removed.append(item)
                        target_minion['type'] = minion_type if minion_type else 'None'
                    elif minion_type in items_to_remove:
                        removed.append(minion_type)
                        target_minion['type'] = 'None'
                    if removed:
                        results.append(f"Removed {', '.join(removed)} type(s) from {target_minion['name']}!")

                run.set_band(band)

            elif option['type'] == 'back_to_parent':
                # Cancel and return to parent event
                run.set_pending_selection(None)
                # Check if we should return to a specific event
                return_to = option.get('return_to_event') or pending.get('return_to_event')
                if return_to:
                    from game_engine.events.event_system import EventSystem
                    EventSystem.create_event_selection(run, return_to)
                    return {
                        'success': True,
                        'back_navigation': True,
                        'message': 'Returned',
                        'results': ['Returned to main event'],
                        'band_changes': [],
                        'resource_changes': {},
                        'returned_to_event': return_to
                    }
                return {
                    'success': True,
                    'back_navigation': True,
                    'message': 'Cancelled',
                    'results': ['Selection cancelled'],
                    'band_changes': [],
                    'resource_changes': {}
                }

            elif option['type'] == 'skip':
                results.append("Skipped the event.")
                # Check if we should return to a parent event
                return_to = option.get('return_to_event') or pending.get('return_to_event')
                if return_to:
                    from game_engine.events.event_system import EventSystem
                    run.set_pending_selection(None)  # Clear current selection first
                    EventSystem.create_event_selection(run, return_to)
                    return {
                        'success': True,
                        'results': results,
                        'band_changes': [],
                        'resource_changes': {},
                        'returned_to_event': return_to
                    }

        # Handle minion combining if this was a combine selection
        if pending.get('event_type') == 'combine_minions' and len(selected_for_combine) > 0:
            # Validate exactly 2 minions selected for combining
            combine_validation = SelectionSystem.validate_combine_selection_logic(run, pending, selected_for_combine)
            if not combine_validation['valid']:
                return {'error': combine_validation['error']}

            idx1, idx2 = selected_for_combine
            minion1 = band[idx1]
            minion2 = band[idx2]

            try:
                # Create golden minion - preserve band_id from first minion
                from game_engine.events.event_system import EventSystem
                golden_minion = EventSystem._create_golden_minion(minion1, minion2)

                # Preserve band_id from the first minion
                if 'band_id' in minion1:
                    golden_minion['band_id'] = minion1['band_id']
                elif 'band_id' in minion2:
                    golden_minion['band_id'] = minion2['band_id']
                else:
                    # Fallback: assign new band_id
                    golden_minion['band_id'] = generate_unique_minion_id()

                # Remove the two original minions (remove higher index first)
                if idx1 > idx2:
                    band.pop(idx1)
                    band.pop(idx2)
                else:
                    band.pop(idx2)
                    band.pop(idx1)

                # Add golden minion at the position of the first minion
                golden_minion['position'] = min(idx1, idx2)
                band.insert(min(idx1, idx2), golden_minion)

                # Update positions of all minions
                for i, minion in enumerate(band):
                    minion['position'] = i

                from lucide_icons import generate_lucide_svg
                results.append(f"{generate_lucide_svg('sparkles', width=24, height=24)} Combined two {minion1['name']} into a Golden {golden_minion['name']}!")
                results.append(
                    f"Golden {golden_minion['name']}: {format_minion_stats(golden_minion['health'], golden_minion['attack'])}")

            except ValueError as e:
                return {'error': f'Combination failed: {str(e)}'}

        # Update game state
        run.set_band(band)
        run.set_resources(resources)

        # Check if we handled back navigation (don't clear selection)
        for selection_id in selection_ids:
            option = None
            for opt in pending['options']:
                if opt['id'] == selection_id:
                    option = opt
                    break

            if option and option['type'] == 'back':
                # Don't clear selection - we've restored previous selection
                return {
                    'success': True,
                    'back_navigation': True,
                    'results': results,
                    'band_changes': results,
                    'resource_changes': {}
                }

        # Check if we're creating a target selection or replacement choice (don't clear selection)
        for selection_id in selection_ids:
            option = None
            for opt in pending['options']:
                if opt['id'] == selection_id:
                    option = opt
                    break

            if option and option['type'] in ['replacement', 'shop_replacement', 'choose_buff']:
                # Don't clear selection yet - target/replacement choice is coming
                return {
                    'success': True,
                    'target_selection': True,
                    'results': results,
                    'band_changes': results,
                    'resource_changes': {}
                }

        # Handle repeating events
        is_repeating = pending.get('repeating', False)

        # Skip events should end the selection regardless of repeating flag
        skip_selected = any(
            selection_id for selection_id in selection_ids
            if any(opt['id'] == selection_id and opt['type'] == 'skip' for opt in pending['options'])
        )

        if is_repeating and not skip_selected:
            # Refresh the repeating event selection with updated state
            from game_engine.events.event_system import EventSystem
            event_type = pending.get('event_type')

            if event_type == 'combine_minions':
                # Refresh statue selection
                refresh_result = EventSystem._create_combine_minions_selection(run, 'statue')
                if refresh_result.get('selection_created'):
                    return {
                        'success': True,
                        'repeating_refresh': True,
                        'results': results,
                        'band_changes': results,
                        'resource_changes': {},
                        'message': 'Selection refreshed - you can combine more minions!'
                    }
            elif event_type in ['minion_shop', 'premium_shop', 'legendary_shop', 'mythic_shop']:
                # Refresh shop selection
                refresh_result = EventSystem._create_shop_selection(run, event_type)
                if refresh_result.get('selection_created'):
                    return {
                        'success': True,
                        'repeating_refresh': True,
                        'results': results,
                        'band_changes': results,
                        'resource_changes': {},
                        'message': 'Shop refreshed - you can buy more items!'
                    }

        # Check if we should return to a parent event after this action
        return_to_event = pending.get('return_to_event')
        if return_to_event:
            from game_engine.events.event_system import EventSystem
            run.set_pending_selection(None)  # Clear current selection first
            EventSystem.create_event_selection(run, return_to_event)
            return {
                'success': True,
                'results': results,
                'band_changes': results,
                'resource_changes': {},
                'returned_to_event': return_to_event
            }

        # Clear selection for normal cases (skip, completed actions, non-repeating events)
        run.set_pending_selection(None)

        return {
            'success': True,
            'results': results,
            'band_changes': results,
            'resource_changes': {}
        }

    @staticmethod
    def swap_minion_positions(run, index1, index2):
        """Swap positions of two minions in the band"""
        band = run.get_band()

        if 0 <= index1 < len(band) and 0 <= index2 < len(band) and index1 != index2:
            # Swap the minions
            band[index1], band[index2] = band[index2], band[index1]

            # Update their position values
            band[index1]['position'] = index1
            band[index2]['position'] = index2

            run.set_band(band)
            return {
                'success': True,
                'message': f"Swapped {band[index1]['name']} and {band[index2]['name']} positions",
                'band': band
            }

        return {'error': 'Invalid swap indices'}

    @staticmethod
    def abandon_minion(run, index):
        """Remove a minion from the band"""
        band = run.get_band()

        if 0 <= index < len(band):
            abandoned_minion = band.pop(index)

            # Update positions of remaining minions
            for i, minion in enumerate(band):
                minion['position'] = i

            run.set_band(band)
            return {
                'success': True,
                'message': f"Abandoned {abandoned_minion['name']}",
                'band': band
            }

        return {'error': 'Invalid minion index'}

    @staticmethod
    def _increase_step_count(run, steps=1):
        """
        Increase the step/event count without triggering additional events.
        This moves the player closer to the next ghost battle.

        Steps track progress toward ghost battles (every 10 steps = ghost battle).

        Args:
            run: The current run object
            steps: Number of extra steps to add (default 1)
        """
        old_count = run.events_count
        run.events_count += steps

        return {
            'success': True,
            'old_count': old_count,
            'new_count': run.events_count,
            'steps_added': steps
        }

    @staticmethod
    def _decrease_step_count(run, steps=1):
        """
        Decrease the step/event count (gain steps = skip ahead).
        This moves the player further from the next ghost battle.

        Args:
            run: The current run object
            steps: Number of steps to subtract (default 1)
        """
        old_count = run.events_count
        run.events_count = max(0, run.events_count - steps)

        return {
            'success': True,
            'old_count': old_count,
            'new_count': run.events_count,
            'steps_removed': steps
        }

    @staticmethod
    def _can_afford_health_cost(run, cost):
        """
        Check if player can afford a health cost.
        With Lichdom, health costs become gold costs.

        Args:
            run: The current run object
            cost: The health cost amount

        Returns:
            bool: True if player can afford the cost
        """
        hero_effects = run.get_hero_effects()
        has_lichdom = hero_effects.get('lichdom', False)

        if has_lichdom:
            resources = run.get_resources()
            return resources.get('gold', 0) >= cost
        else:
            return run.health >= cost

    @staticmethod
    def _pay_health_cost(run, cost):
        """
        Pay a health cost, respecting Lichdom (converts to gold).

        Args:
            run: The current run object
            cost: The health cost amount

        Returns:
            dict: {
                'success': bool,
                'message': str describing what was paid,
                'error': str if failed (optional)
            }
        """
        hero_effects = run.get_hero_effects()
        has_lichdom = hero_effects.get('lichdom', False)

        if has_lichdom:
            # Pay gold instead of health
            resources = run.get_resources()
            current_gold = resources.get('gold', 0)
            if current_gold < cost:
                return {
                    'success': False,
                    'error': f'Not enough gold! Need {cost}, have {current_gold}.'
                }
            resources['gold'] = current_gold - cost
            run.set_resources(resources)
            return {
                'success': True,
                'message': f'Paid {cost} gold'
            }
        else:
            # Pay health
            run.health = max(0, run.health - cost)
            return {
                'success': True,
                'message': f'Took {cost} damage'
            }