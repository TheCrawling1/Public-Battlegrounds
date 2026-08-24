"""
Special Effects - Miscellaneous and special combat effects

This module contains implementations for special effects like
fatigue modification, unique abilities, etc.

UPDATED: Fixed perform_cast to handle cast effects that are lists
UPDATED: Added reduce_hide and leap_move effects for Hide and Leap keywords
UPDATED: Added divide_attack effect for Queen Bee start of combat
UPDATED: Added nobility keyword support - redirect_damage now respects nobility,
but attack_target does not (it's a combat attack).
UPDATED: Added rich_buff effect for Rich keyword - grants +1/+1 per gold at start of combat
UPDATED: Added modify_gold effect for adjusting player gold during combat
UPDATED: Now routes damage through centralized damage_handler for attack_target and redirect_damage
UPDATED: Added support for condition_found_minion attacker spec in attack_target for dynamic minion finding
UPDATED: Added target_filters support to apply_stun for dynamic filtering
UPDATED: Added transfer_stun effect for Nymph
UPDATED: Added scaling_damage effect for Railway Cannon's incrementing damage
UPDATED: Added trigger_death_toll effect for Shaman to trigger friendly death tolls
"""

import logging

logger = logging.getLogger(__name__)

from typing import Dict, List, Tuple, Optional
from keywords import resolve_target, has_keyword, reduce_hide_count, reduce_ring_count, has_nobility
from game_engine.damage_handler import apply_damage, DamageType
from game_random import game_random, SelectionType


def _apply_target_filters(candidates: List[Dict], filters: List[Dict], context: Dict) -> List[Dict]:
    """
    Filter a list of candidate minions using condition checks

    This function enables dynamic effect filtering by leveraging the existing
    conditional system. Each candidate is evaluated against all filter conditions.

    Args:
        candidates: List of minion dicts to filter
        filters: List of condition dicts (same format as conditional conditions)
        context: Combat context for condition evaluation

    Returns:
        Filtered list of minions that pass all filter conditions
    """
    if not filters:
        return candidates

    from game_engine.effects.conditional_effects import evaluate_condition

    filtered = []
    for candidate in candidates:
        # Create a temporary context with this candidate as target
        filter_context = dict(context)
        filter_context['target_minion'] = candidate

        # Check all filters - candidate must pass ALL filters
        passes_all = True
        for filter_condition in filters:
            if not evaluate_condition(filter_condition, filter_context):
                passes_all = False
                break

        if passes_all:
            filtered.append(candidate)

    logger.debug(f"[FILTER] Filtered {len(candidates)} candidates down to {len(filtered)} targets")
    return filtered


def scaling_damage(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Deal damage that scales up each time (for Railway Cannon)

    Tracks damage in a minion field and increments it after each use.

    Args:
        effect_data: Effect configuration with:
            - base_amount: Starting damage value
            - increment: Amount to increase by each cast
            - tracker_field: Field name on minion to track current damage
            - target: Target specification (default 'random_enemy')
        context: Combat context

    Returns:
        Tuple of (success, logs, changes)
    """
    base_amount = effect_data.get('base_amount', 4)
    increment = effect_data.get('increment', 4)
    tracker_field = effect_data.get('tracker_field', 'cast_damage_current')
    target_spec = effect_data.get('target', 'random_enemy')
    acting_minion = context.get('acting_minion')

    if not acting_minion:
        return False, ["❌ No acting minion for scaling damage"], {}

    # Get current damage value from minion (initialize if needed)
    if tracker_field not in acting_minion:
        acting_minion[tracker_field] = base_amount
        logger.debug(f"[SCALING] Initialized {tracker_field} to {base_amount} for {acting_minion['name']}")

    current_damage = acting_minion[tracker_field]

    # Apply golden doubling to the current damage
    if acting_minion.get('golden', False):
        current_damage *= 2
        logger.debug(f"[SCALING] Golden doubling: {acting_minion[tracker_field]} → {current_damage}")

    # Resolve target
    success, target, error = resolve_target(target_spec, context, acting_minion)
    if not success:
        return False, [f"❌ Scaling damage targeting failed: {error}"], {}

    # Apply damage through damage handler
    damage_result = apply_damage(
        target=target,
        amount=current_damage,
        damage_type=DamageType.ABILITY,
        source_minion=acting_minion,
        context=context
    )

    # Increment the tracker for next time (base value, not golden-doubled)
    # Apply golden doubling to the increment
    actual_increment = increment
    if acting_minion.get('golden', False):
        actual_increment *= 2

    acting_minion[tracker_field] += actual_increment

    logger.debug(f"[SCALING] {acting_minion['name']}'s {tracker_field}: dealt {current_damage}, next will be {acting_minion[tracker_field]}")

    # Track in effect context
    effect_context = context.get('effect_context')
    if effect_context:
        effect_context.target_minions.append(target)
        effect_context.damage_dealt = damage_result.damage_applied
        effect_context.add_tag('scaling_damage')

    # Generate logs
    is_golden = acting_minion.get('golden', False)
    golden_prefix = "💎 Golden " if is_golden else ""

    logs = []

    if damage_result.blocked_by_nobility:
        logs.append(f"🔮⚡ Cast: {golden_prefix}{acting_minion['name']} fires for {current_damage} damage at {target['name']}")
        logs.extend(damage_result.logs)

        return True, logs, {
            'damage_dealt': 0,
            'nobility_blocked': True,
            'scaling_value': acting_minion[tracker_field],
            'targets': []
        }
    else:
        logs.append(f"🔮⚡ Cast: {golden_prefix}{acting_minion['name']} fires for {current_damage} damage at {target['name']}! (Next cast: {acting_minion[tracker_field]})")

        return True, logs, {
            'damage_dealt': damage_result.damage_applied,
            'scaling_value': acting_minion[tracker_field],
            'targets': [target]
        }


def trigger_death_toll(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Trigger a random friendly minion's death toll effect without killing them (for Shaman)
    Or trigger a specific minion's death toll (for Quasimodo)

    This effect finds minions with death_toll keyword and triggers their death_toll_effect
    as if they had died, but they remain alive.

    Args:
        effect_data: Effect configuration with:
            - target: Which allies to consider (default 'all_allies') or specific minion
            - exclude_self: Whether to exclude the caster (default True)
        context: Combat context

    Returns:
        Tuple of (success, logs, changes)
    """
    target_spec = effect_data.get('target', 'all_allies')
    exclude_self = effect_data.get('exclude_self', True)
    acting_minion = context.get('acting_minion')

    if not acting_minion:
        return False, ["❌ No acting minion for trigger death toll"], {}

    # Special case: If target is 'trigger_source', get the minion directly from context
    # This handles dead minions (like for Quasimodo triggering a dead minion's death toll again)
    if target_spec == 'trigger_source':
        target_minion = context.get('trigger_context_source')
        if target_minion and has_keyword(target_minion, 'death_toll'):
            death_toll_minions = [target_minion]
            logger.debug(f"[TRIGGER_DEATH_TOLL] Using trigger_source directly: {target_minion.get('name')}")
        else:
            if not target_minion:
                return False, ["❌ No trigger source in context"], {}
            else:
                return False, [f"❌ {target_minion.get('name')} has no death_toll keyword"], {}
    else:
        # Get all potential targets
        success, all_allies, error = resolve_target(target_spec, context, acting_minion)

        if not success or not all_allies:
            return False, [f"❌ Could not find allies: {error}"], {}

        # Ensure it's a list
        if not isinstance(all_allies, list):
            all_allies = [all_allies]

        # Filter to only minions with death_toll keyword
        death_toll_minions = [m for m in all_allies if has_keyword(m, 'death_toll')]

        # Exclude self if specified
        if exclude_self:
            death_toll_minions = [m for m in death_toll_minions if m != acting_minion]

        if not death_toll_minions:
            is_golden = acting_minion.get('golden', False)
            golden_prefix = "💎 Golden " if is_golden else ""
            return True, [f"🔮 Cast: {golden_prefix}{acting_minion['name']} finds no death toll effects to trigger"], {}

    # Select one randomly (or use the specific one if only one in list)
    random_context = {
        'effect_type': 'trigger_death_toll',
        'caster_name': acting_minion.get('name', 'Unknown'),
        'candidate_count': len(death_toll_minions)
    }

    target_minion = game_random.select_one(
        SelectionType.RANDOM_ALLY,
        death_toll_minions,
        context=random_context,
        description=f"Select minion for death toll trigger"
    )

    # Get the death toll effect
    death_toll_effect = target_minion.get('death_toll_effect')

    if not death_toll_effect:
        return False, [f"❌ {target_minion['name']} has death_toll keyword but no death_toll_effect"], {}

    logger.debug(f"[TRIGGER_DEATH_TOLL] {acting_minion['name']} triggering {target_minion['name']}'s death toll")

    # Apply golden doubling if the TARGET minion is golden (not the caster)
    if target_minion.get('golden', False):
        # Function is defined later in this same file (no import needed)
        death_toll_effect = apply_golden_doubling_to_cast(death_toll_effect, target_minion)
        logger.debug(f"[TRIGGER_DEATH_TOLL] Applied golden doubling to {target_minion['name']}'s death toll effect")

    # Create context for the death toll effect
    # The target minion is treated as the "dying minion" but stays alive
    death_toll_context = dict(context)
    death_toll_context['dying_minion'] = target_minion
    death_toll_context['acting_minion'] = target_minion  # Death toll effects use acting_minion
    death_toll_context['trigger_source'] = 'death_toll'

    # Store registry info for the "dying" minion
    registry = context.get('combat_registry')
    if registry:
        band_type = registry.get_minion_band_type(target_minion)
        death_toll_context['trigger_dying_metadata'] = {
            'name': target_minion.get('name'),
            'band_type': band_type,
            '_combat_id': target_minion.get('_combat_id')
        }

    # CRITICAL: Send TRIGGER_DEATH_TOLL command BEFORE executing child effects
    # This ensures correct log order: trigger announcement, then actual effects
    trigger_processor = context.get('trigger_processor')
    if trigger_processor:
        # Build logs for the trigger command
        is_golden_caster = acting_minion.get('golden', False)
        golden_caster_prefix = "💎 Golden " if is_golden_caster else ""
        is_golden_target = target_minion.get('golden', False)
        golden_target_prefix = "💎 Golden " if is_golden_target else ""
        target_alive = target_minion.get('health', 0) > 0

        trigger_logs = []
        if acting_minion != target_minion:
            trigger_logs.append(f"⚰️ {golden_caster_prefix}{acting_minion['name']} triggers {golden_target_prefix}{target_minion['name']}'s death toll!")

        if target_alive:
            trigger_logs.append(f"💀⚡ {golden_target_prefix}{target_minion['name']}'s death toll triggers (but stays alive):")
        else:
            trigger_logs.append(f"💀⚡ {golden_target_prefix}{target_minion['name']}'s death toll triggers again:")

        # Send command now (before child effects) - bypass the skip check by calling interpreter directly
        interpreter = context.get('interpreter')
        if interpreter:
            from game_engine.interpreter import CommandBuilder
            command_builder = CommandBuilder()

            # Build TRIGGER_DEATH_TOLL command
            command = command_builder.build_effect_command(
                effect_type='trigger_death_toll',
                effect_data={'type': 'trigger_death_toll'},
                changes={'triggered_minion': target_minion},
                source_minion=acting_minion,
                trigger_type=None,
                log_message='\n'.join(trigger_logs) if trigger_logs else None
            )

            if command:
                interpreter.add_command(command)
                logger.debug(f"[TRIGGER_DEATH_TOLL] Sent command directly before executing child effects")
        else:
            logger.debug(f"[TRIGGER_DEATH_TOLL] No interpreter available, skipping command")

    # Execute the death toll effect
    from game_engine.effects import apply_effects_list

    # CRITICAL: Always use apply_effects_list so child effects send their own commands to interpreter
    # This ensures the frontend sees the actual death toll effects (summon, buff, damage, etc.)
    # with all correct values, not a generic trigger_death_toll command
    if not isinstance(death_toll_effect, list):
        death_toll_effect = [death_toll_effect]

    effect_success, effect_logs, effect_changes = apply_effects_list(death_toll_effect, death_toll_context)

    # Register ON_ANY_DEATH_TOLL triggers (for Quasimodo)
    if effect_success and registry:
        registrar = context.get('registrar')
        if registrar:
            logger.debug(f"[TRIGGER_DEATH_TOLL] Registering death toll triggers for {target_minion['name']}")
            registrar.register_death_toll_triggers(target_minion, is_additional_trigger=True)

    # Track in effect context
    effect_context = context.get('effect_context')
    if effect_context:
        effect_context.target_minions.append(target_minion)
        effect_context.add_tag('death_toll_triggered')

    # Build logs for combat_log (used by dev mode and backend logs)
    # We already sent the TRIGGER_DEATH_TOLL command manually with these logs,
    # but we still need to return them for the combat_log
    is_golden_caster = acting_minion.get('golden', False)
    golden_caster_prefix = "💎 Golden " if is_golden_caster else ""
    is_golden_target = target_minion.get('golden', False)
    golden_target_prefix = "💎 Golden " if is_golden_target else ""
    target_alive = target_minion.get('health', 0) > 0

    logs = []
    if acting_minion != target_minion:
        logs.append(f"⚰️ {golden_caster_prefix}{acting_minion['name']} triggers {golden_target_prefix}{target_minion['name']}'s death toll!")

    if target_alive:
        logs.append(f"💀⚡ {golden_target_prefix}{target_minion['name']}'s death toll triggers (but stays alive):")
    else:
        logs.append(f"💀⚡ {golden_target_prefix}{target_minion['name']}'s death toll triggers again:")

    # Include child effect logs for combat_log
    logs.extend(effect_logs)

    return True, logs, {
        'death_toll_triggered': True,
        'triggered_minion': target_minion,
        'targets': [target_minion],
        **effect_changes
    }


def trigger_start_of_combat(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Trigger a random friendly minion's start_of_combat effect (for Shaman)

    This effect finds minions with start_of_combat keyword and triggers their
    start_of_combat_effect as if combat just started.

    Args:
        effect_data: Effect configuration with:
            - target: Which allies to consider (default 'all_allies')
            - exclude_self: Whether to exclude the caster (default True)
        context: Combat context

    Returns:
        Tuple of (success, logs, changes)
    """
    target_spec = effect_data.get('target', 'all_allies')
    exclude_self = effect_data.get('exclude_self', True)
    acting_minion = context.get('acting_minion')

    if not acting_minion:
        return False, ["❌ No acting minion for trigger start of combat"], {}

    # Get all potential targets
    success, all_allies, error = resolve_target(target_spec, context, acting_minion)

    if not success or not all_allies:
        return False, [f"❌ Could not find allies: {error}"], {}

    # Ensure it's a list
    if not isinstance(all_allies, list):
        all_allies = [all_allies]

    # Filter to only minions with start_of_combat keyword AND start_of_combat_effect
    start_of_combat_minions = [
        m for m in all_allies
        if has_keyword(m, 'start_of_combat') and m.get('start_of_combat_effect')
    ]

    # Exclude self if specified
    if exclude_self:
        start_of_combat_minions = [m for m in start_of_combat_minions if m != acting_minion]

    if not start_of_combat_minions:
        is_golden = acting_minion.get('golden', False)
        golden_prefix = "💎 Golden " if is_golden else ""
        return True, [f"🔮 Cast: {golden_prefix}{acting_minion['name']} finds no start of combat effects to trigger"], {}

    # Select one randomly
    random_context = {
        'effect_type': 'trigger_start_of_combat',
        'caster_name': acting_minion.get('name', 'Unknown'),
        'candidate_count': len(start_of_combat_minions)
    }

    target_minion = game_random.select_one(
        SelectionType.RANDOM_ALLY,
        start_of_combat_minions,
        context=random_context,
        description=f"Select minion for start of combat trigger"
    )

    # Get the start_of_combat effect
    start_of_combat_effect = target_minion.get('start_of_combat_effect')

    if not start_of_combat_effect:
        return False, [f"❌ {target_minion['name']} has start_of_combat keyword but no start_of_combat_effect"], {}

    logger.debug(f"[TRIGGER_START_OF_COMBAT] {acting_minion['name']} triggering {target_minion['name']}'s start of combat")

    # Apply golden doubling if the TARGET minion is golden (not the caster)
    if target_minion.get('golden', False):
        start_of_combat_effect = apply_golden_doubling_to_cast(start_of_combat_effect, target_minion)
        logger.debug(f"[TRIGGER_START_OF_COMBAT] Applied golden doubling to {target_minion['name']}'s start of combat effect")

    # Create context for the start_of_combat effect
    soc_context = dict(context)
    soc_context['acting_minion'] = target_minion  # The target's effect uses them as acting_minion
    soc_context['trigger_source'] = 'start_of_combat'

    # CRITICAL: Send TRIGGER_START_OF_COMBAT command BEFORE executing child effects
    trigger_processor = context.get('trigger_processor')
    if trigger_processor:
        is_golden_caster = acting_minion.get('golden', False)
        golden_caster_prefix = "💎 Golden " if is_golden_caster else ""
        is_golden_target = target_minion.get('golden', False)
        golden_target_prefix = "💎 Golden " if is_golden_target else ""

        trigger_logs = []
        if acting_minion != target_minion:
            trigger_logs.append(f"🎬 {golden_caster_prefix}{acting_minion['name']} triggers {golden_target_prefix}{target_minion['name']}'s start of combat!")
        trigger_logs.append(f"🎬⚡ {golden_target_prefix}{target_minion['name']}'s start of combat triggers:")

        # Send command before child effects
        interpreter = context.get('interpreter')
        if interpreter:
            from game_engine.interpreter import CommandBuilder
            command_builder = CommandBuilder()

            command = command_builder.build_effect_command(
                effect_type='trigger_start_of_combat',
                effect_data={'type': 'trigger_start_of_combat'},
                changes={'triggered_minion': target_minion},
                source_minion=acting_minion,
                trigger_type=None,
                log_message='\n'.join(trigger_logs) if trigger_logs else None
            )

            if command:
                interpreter.add_command(command)
                logger.debug(f"[TRIGGER_START_OF_COMBAT] Sent command directly before executing child effects")

    # Execute the start_of_combat effect
    from game_engine.effects import apply_effects_list

    if not isinstance(start_of_combat_effect, list):
        start_of_combat_effect = [start_of_combat_effect]

    effect_success, effect_logs, effect_changes = apply_effects_list(start_of_combat_effect, soc_context)

    # Track in effect context
    effect_context = context.get('effect_context')
    if effect_context:
        effect_context.target_minions.append(target_minion)
        effect_context.add_tag('start_of_combat_triggered')

    # Build logs
    is_golden_caster = acting_minion.get('golden', False)
    golden_caster_prefix = "💎 Golden " if is_golden_caster else ""
    is_golden_target = target_minion.get('golden', False)
    golden_target_prefix = "💎 Golden " if is_golden_target else ""

    logs = []
    if acting_minion != target_minion:
        logs.append(f"🎬 {golden_caster_prefix}{acting_minion['name']} triggers {golden_target_prefix}{target_minion['name']}'s start of combat!")
    logs.append(f"🎬⚡ {golden_target_prefix}{target_minion['name']}'s start of combat triggers:")
    logs.extend(effect_logs)

    return True, logs, {
        'start_of_combat_triggered': True,
        'triggered_minion': target_minion,
        'targets': [target_minion],
        **effect_changes
    }


def transfer_stun(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Transfer stun from one set of minions to another

    Collects total stun from source minions, clears it, then applies total to target.
    This effect is used by Nymph to remove all friendly stun and give it to an enemy.

    Args:
        effect_data: Effect configuration with from_targets and to_target
        context: Combat context

    Returns:
        Tuple of (success, logs, changes)
    """
    from_spec = effect_data.get('from_targets', 'all_allies')
    to_spec = effect_data.get('to_target', 'random_enemy')
    acting_minion = context.get('acting_minion')

    # Get source minions
    success, from_minions, error = resolve_target(from_spec, context, acting_minion)
    if not success:
        return False, [f"❌ Transfer stun source failed: {error}"], {}

    if not isinstance(from_minions, list):
        from_minions = [from_minions]

    # Collect total stun
    total_stun = 0
    cleared_minions = []
    for minion in from_minions:
        stun_count = minion.get('stun_count', 0)
        if stun_count > 0:
            total_stun += stun_count
            minion['stun_count'] = 0
            # Remove stun keyword if no longer stunned
            if 'stun' in minion.get('keywords', []):
                minion['keywords'].remove('stun')
            cleared_minions.append(minion)

    if total_stun == 0:
        is_golden = acting_minion.get('golden', False)
        golden_prefix = "💎 Golden " if is_golden else ""
        return True, [f"✨ {golden_prefix}{acting_minion['name']} has no stun to transfer"], {}

    # Apply to target
    success, to_minion, error = resolve_target(to_spec, context, acting_minion)
    if not success:
        return False, [f"❌ Transfer stun target failed: {error}"], {}

    # Apply the collected stun
    if 'stun_count' not in to_minion:
        to_minion['stun_count'] = 0
    to_minion['stun_count'] += total_stun

    # Add stun keyword
    if 'stun' not in to_minion.get('keywords', []):
        if 'keywords' not in to_minion:
            to_minion['keywords'] = []
        to_minion['keywords'].append('stun')

    # Track in effect context
    effect_context = context.get('effect_context')
    if effect_context:
        effect_context.target_minions.append(to_minion)
        effect_context.add_tag('stun_transferred')

    # Generate logs
    is_golden = acting_minion.get('golden', False)
    golden_prefix = "💎 Golden " if is_golden else ""

    cleared_names = [m['name'] for m in cleared_minions]

    logs = [
        f"🔮 Cast: {golden_prefix}{acting_minion['name']} transfers stun!",
        f"✨ Cleared {total_stun} stun from {', '.join(cleared_names)}",
        f"⏸️ {to_minion['name']} receives {total_stun} stun!"
    ]

    return True, logs, {
        'stun_transferred': total_stun,
        'cleared_from': cleared_minions,
        'applied_to': to_minion,
        'targets': [to_minion]
    }


def modify_gold(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Modify player gold during combat (add or subtract)

    FIXED: Now handles both real Run objects and MockRun objects properly

    Args:
        effect_data: Effect configuration with amount (positive to add, negative to subtract)
        context: Combat context with run object

    Returns:
        Tuple of (success, logs, changes)
    """
    amount = effect_data.get('amount', 0)
    acting_minion = context.get('acting_minion')

    if amount == 0:
        return False, ["❌ No gold amount specified"], {}

    # Get run object to access gold
    run = context.get('run')
    if not run:
        # No run context (e.g., enemy minions or dev mode) - can't modify gold
        return False, ["❌ No run context to modify gold"], {}

    # Get current resources - works for both Run and MockRun
    resources = run.get_resources()
    current_gold = resources.get('gold', 0)

    # Apply golden doubling if minion is golden
    golden_effects_applied = context.get('golden_effects_applied', False)
    if acting_minion and acting_minion.get('golden', False) and not golden_effects_applied:
        amount *= 2

    # Determine if adding or subtracting
    if amount > 0:
        # Adding gold
        new_gold = current_gold + amount
        action_text = "gains"
    else:
        # Subtracting gold (make sure we don't go below 0)
        new_gold = max(0, current_gold + amount)  # amount is negative
        action_text = "loses"
        amount = abs(amount)  # For display purposes

    # FIXED: Update gold - handle both Run and MockRun
    # Method 1: Try direct attribute access (real Run objects)
    if hasattr(run, 'resources') and isinstance(getattr(run, 'resources', None), dict):
        run.resources['gold'] = new_gold
        logger.debug(f"[GOLD] Updated via run.resources: {current_gold} → {new_gold}")
    # Method 2: Modify the returned dict (MockRun and others)
    else:
        resources['gold'] = new_gold
        logger.debug(f"[GOLD] Updated via resources dict: {current_gold} → {new_gold}")

    # Track in effect context
    effect_context = context.get('effect_context')
    if effect_context:
        if acting_minion:
            effect_context.target_minions.append(acting_minion)
        effect_context.add_tag('gold_modified')

    # Generate log
    is_golden = acting_minion.get('golden', False) if acting_minion else False
    golden_prefix = "💎 Golden " if is_golden else ""

    trigger_source = context.get('trigger_source', 'effect')

    if trigger_source == 'on_damage':
        log_entry = f"💥💰 {golden_prefix}{acting_minion['name'] if acting_minion else 'Effect'} {action_text} {amount} gold from taking damage! ({current_gold} → {new_gold})"
    else:
        log_entry = f"💰 {golden_prefix}{acting_minion['name'] if acting_minion else 'Effect'} {action_text} {amount} gold! ({current_gold} → {new_gold})"

    return True, [log_entry], {
        'gold_modified': True,
        'gold_change': amount if action_text == "gains" else -amount,
        'old_gold': current_gold,
        'new_gold': new_gold
    }


def rich_buff(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Rich keyword effect - grant +1/+1 per gold at start of combat

    Args:
        effect_data: Effect configuration with target
        context: Combat context with run object

    Returns:
        Tuple of (success, logs, changes)
    """
    target_spec = effect_data.get('target', 'self')
    acting_minion = context.get('acting_minion')

    # Resolve target
    success, target, error = resolve_target(target_spec, context, acting_minion)
    if not success:
        return False, [f"❌ Rich buff targeting failed: {error}"], {}

    if not target:
        return False, ["❌ No target for rich buff"], {}

    # Determine which gold source to use based on minion ownership
    # Player minions have band_id, enemy minions don't
    gold = 0

    if 'band_id' in target:
        # Player minion - use actual player gold from run
        run = context.get('run')
        if run:
            resources = run.get_resources()
            gold = resources.get('gold', 0)
        else:
            # No run context available for player minion
            gold = 0
    else:
        # Enemy minion - use spoofed gold
        gold = target.get('spoofed_gold', 0)

    if gold <= 0:
        # No gold, no buff
        is_golden = target.get('golden', False)
        golden_prefix = "💎 Golden " if is_golden else ""
        return True, [f"💰 Rich: {golden_prefix}{target['name']} has no gold to benefit from"], {}

    # Calculate buff amount (doubled for golden)
    buff_amount = gold
    if target.get('golden', False):
        buff_amount *= 2

    # Apply the buff
    target['health'] += buff_amount
    target['attack'] += buff_amount

    # Track in effect context
    effect_context = context.get('effect_context')
    if effect_context:
        effect_context.target_minions.append(target)
        effect_context.stats_changed['health'] = buff_amount
        effect_context.stats_changed['attack'] = buff_amount

    # Generate log
    is_golden = target.get('golden', False)
    golden_prefix = "💎 Golden " if is_golden else ""

    return True, [
        f"💰 Rich: {golden_prefix}{target['name']} gains +{buff_amount}/+{buff_amount} from {gold} gold"
    ], {
        'rich_buff_applied': True,
        'buff_amount': buff_amount,
        'gold_used': gold,
        'targets': [target]
    }


def divide_attack(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Divide a minion's attack by a specified divisor (for Queen Bee's start of combat)

    Args:
        effect_data: Effect configuration with target and divisor
        context: Combat context

    Returns:
        Tuple of (success, logs, changes)
    """
    target_spec = effect_data.get('target', 'self')
    divisor = effect_data.get('divisor', 3)
    acting_minion = context.get('acting_minion')

    # Resolve target
    success, target, error = resolve_target(target_spec, context, acting_minion)
    if not success:
        return False, [f"❌ Divide attack targeting failed: {error}"], {}

    if not target:
        return False, ["❌ No target for divide attack"], {}

    # Store original attack
    original_attack = target.get('attack', 0)

    # Divide attack (round down)
    new_attack = original_attack // divisor

    # Update the minion's attack
    target['attack'] = new_attack

    # Calculate reduction
    reduction = original_attack - new_attack

    # Track in effect context
    effect_context = context.get('effect_context')
    if effect_context:
        effect_context.target_minions.append(target)
        effect_context.add_tag('attack_divided')

    # Generate log
    is_golden = target.get('golden', False)
    golden_prefix = "💎 Golden " if is_golden else ""

    return True, [
        f"➗ Start of Combat: {golden_prefix}{target['name']}'s attack divided by {divisor}: {original_attack} → {new_attack}"
    ], {
        'attack_divided': True,
        'original_attack': original_attack,
        'new_attack': new_attack,
        'reduction': reduction,
        'targets': [target]
    }


def recalculate_auras(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Recalculate all aura effects for the current board state

    This effect is triggered whenever positions change (combat start, summon, death, move).
    It clears all existing aura buffs and reapplies them based on current positions.

    Args:
        effect_data: Effect configuration (usually empty)
        context: Combat context with bands and registry

    Returns:
        Tuple of (success, logs, changes)
    """
    registry = context.get('combat_registry')
    if not registry:
        return False, ["❌ No combat registry for aura recalculation"], {}

    # Get both bands
    player_band = context.get('absolute_player_band', context.get('player_band', []))
    enemy_band = context.get('absolute_enemy_band', context.get('enemy_band', []))
    all_minions = player_band + enemy_band

    # First pass: Remove old aura buffs and clear for recalculation
    for minion in all_minions:
        # Store base stats if not already stored
        if 'base_attack' not in minion:
            minion['base_attack'] = minion['attack']
        if 'base_health' not in minion:
            minion['base_health'] = minion['health']

        # Remove previous aura buffs from current stats
        if 'aura_buffs' in minion:
            old_attack_buff = minion['aura_buffs'].get('attack', 0)
            old_health_buff = minion['aura_buffs'].get('health', 0)
            minion['attack'] -= old_attack_buff
            minion['health'] -= old_health_buff

        # Reset aura buffs
        minion['aura_buffs'] = {
            'attack': 0,
            'health': 0,
            'sources': []
        }

    # Second pass: Find all aura providers and apply their effects
    aura_applications = []

    for minion in all_minions:
        if minion.get('health', 0) <= 0:
            continue  # Skip dead minions

        if has_keyword(minion, 'aura'):
            # This minion provides an aura
            aura_effect = minion.get('aura_effect')
            if not aura_effect:
                continue

            # Determine which band this minion is in
            band_type = registry.get_minion_band_type(minion)
            if band_type == 'player':
                band = player_band
            else:
                band = enemy_band

            # Get adjacent minions
            minion_pos = minion.get('position', -1)
            adjacent_minions = []

            for other in band:
                if other == minion:
                    continue  # Don't buff self
                if other.get('health', 0) <= 0:
                    continue  # Skip dead minions

                other_pos = other.get('position', -1)
                if abs(other_pos - minion_pos) == 1:
                    # This minion is adjacent
                    adjacent_minions.append(other)

            # Apply aura effects to adjacent minions
            if adjacent_minions:
                # Apply the buff_adjacent effect
                for adjacent in adjacent_minions:
                    # Apply golden doubling if aura provider is golden
                    attack_buff = aura_effect.get('attack', 0)
                    health_buff = aura_effect.get('health', 0)

                    if minion.get('golden', False):
                        attack_buff *= 2
                        health_buff *= 2

                    # Add to existing aura buffs
                    adjacent['aura_buffs']['attack'] += attack_buff
                    adjacent['aura_buffs']['health'] += health_buff
                    adjacent['aura_buffs']['sources'].append(minion.get('_combat_id', minion['name']))

                    # Track for logging
                    aura_applications.append({
                        'provider': minion,
                        'target': adjacent,
                        'attack': attack_buff,
                        'health': health_buff
                    })

    # Generate logs
    logs = []
    if aura_applications:
        # Group by provider for cleaner logging
        providers = {}
        for app in aura_applications:
            provider_name = app['provider']['name']
            if app['provider'].get('golden', False):
                provider_name = f"💎 Golden {provider_name}"

            if provider_name not in providers:
                providers[provider_name] = []

            target_name = app['target']['name']
            buff_text = []
            if app['attack'] > 0:
                buff_text.append(f"+{app['attack']} attack")
            if app['health'] > 0:
                buff_text.append(f"+{app['health']} health")

            providers[provider_name].append(f"{target_name} ({', '.join(buff_text)})")

        # Create log entries
        for provider, targets in providers.items():
            logs.append(f"💫 Aura: {provider} buffs {', '.join(targets)}")

    # Third pass: Apply the aura buffs to actual stats
    for minion in all_minions:
        if minion.get('health', 0) <= 0:
            continue  # Skip dead minions

        aura_buffs = minion.get('aura_buffs', {})
        attack_buff = aura_buffs.get('attack', 0)
        health_buff = aura_buffs.get('health', 0)

        if attack_buff != 0 or health_buff != 0:
            minion['attack'] += attack_buff
            minion['health'] += health_buff

    # Track in effect context
    effect_context = context.get('effect_context')
    if effect_context:
        effect_context.add_tag('auras_recalculated')

    return True, logs, {
        'auras_recalculated': True,
        'aura_applications': len(aura_applications)
    }


def buff_adjacent(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Buff adjacent minions (one-time effect, not aura)

    Used by effects like Ritual Altar's start_of_combat.
    Finds minions adjacent to the acting minion and buffs them.
    Adds BUFF_STATS commands for each buffed minion for frontend display.

    Args:
        effect_data: Effect configuration with attack/health buffs
        context: Combat context

    Returns:
        Tuple of (success, logs, changes)
    """
    acting_minion = context.get('acting_minion')
    if not acting_minion:
        return False, ["❌ No acting minion for buff_adjacent"], {}

    attack_buff = effect_data.get('attack', 0)
    health_buff = effect_data.get('health', 0)

    # Apply golden doubling
    if acting_minion.get('golden', False):
        attack_buff *= 2
        health_buff *= 2

    # Get the band this minion is in
    registry = context.get('combat_registry')
    if not registry:
        return False, ["❌ No combat registry"], {}

    band_type = registry.get_minion_band_type(acting_minion)
    if band_type == 'player':
        band = context.get('absolute_player_band', context.get('player_band', []))
    else:
        band = context.get('absolute_enemy_band', context.get('enemy_band', []))

    # Find position of acting minion
    try:
        acting_pos = band.index(acting_minion)
    except ValueError:
        return False, [f"❌ {acting_minion['name']} not found in band"], {}

    # Find adjacent minions
    adjacent_minions = []
    if acting_pos > 0:
        left_minion = band[acting_pos - 1]
        if left_minion.get('health', 0) > 0:
            adjacent_minions.append(left_minion)

    if acting_pos < len(band) - 1:
        right_minion = band[acting_pos + 1]
        if right_minion.get('health', 0) > 0:
            adjacent_minions.append(right_minion)

    if not adjacent_minions:
        return True, [], {'no_adjacent_targets': True}

    # Apply buffs to adjacent minions AND add interpreter commands
    buffed_names = []
    interpreter = context.get('interpreter')

    for minion in adjacent_minions:
        minion['attack'] += attack_buff
        minion['health'] += health_buff
        buffed_names.append(minion['name'])

        # Add BUFF_STATS command for frontend
        if interpreter:
            buff_cmd = {
                'cmd': 'BUFF_STATS',
                'target_id': minion.get('_combat_id'),
                'target_name': minion.get('name'),
                'attack': attack_buff,
                'health': health_buff,
                'source_id': acting_minion.get('_combat_id'),
                'source_name': acting_minion.get('name'),
                'trigger_type': 'start_of_combat',
                'golden': acting_minion.get('golden', False)
            }
            interpreter.add_command(buff_cmd)

    # Generate log
    log_parts = []
    if attack_buff > 0:
        log_parts.append(f"+{attack_buff} attack")
    if health_buff > 0:
        log_parts.append(f"+{health_buff} health")

    is_golden = acting_minion.get('golden', False)
    golden_prefix = "💎 Golden " if is_golden else ""

    log_entry = f"✨ {golden_prefix}{acting_minion['name']} buffs adjacent minions {', '.join(buffed_names)} ({', '.join(log_parts)})"

    return True, [log_entry], {
        'targets': adjacent_minions,
        'attack_buff': attack_buff,
        'health_buff': health_buff,
        'buffed_count': len(adjacent_minions)
    }


def reduce_hide(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Reduce hide count when a minion attacks

    This effect is automatically applied when a hidden minion attacks.

    Args:
        effect_data: Effect configuration (usually empty or with target)
        context: Combat context with acting_minion

    Returns:
        Tuple of (success, logs, changes)
    """
    target_spec = effect_data.get('target', 'self')
    acting_minion = context.get('acting_minion')

    # Resolve target (usually self for attacking minion)
    if target_spec == 'self':
        target = acting_minion
    else:
        success, target, error = resolve_target(target_spec, context, acting_minion)
        if not success:
            return False, [f"❌ Hide reduction targeting failed: {error}"], {}

    if not target:
        return False, ["❌ No target for hide reduction"], {}

    # Check if target has hide
    if not has_keyword(target, 'hide'):
        return True, [], {}  # No hide to reduce

    # Get current hide state
    hide_remaining = target.get('hide_remaining', 0)
    is_hidden = target.get('is_hidden', False)

    if not is_hidden or hide_remaining <= 0:
        return True, [], {}  # Already unhidden

    # Reduce hide count
    new_hide_count = reduce_hide_count(target)

    # Track in effect context
    effect_context = context.get('effect_context')
    if effect_context:
        effect_context.target_minions.append(target)
        effect_context.add_tag('hide_reduced')

    # Generate log
    is_golden = target.get('golden', False)
    golden_prefix = "💎 Golden " if is_golden else ""

    if new_hide_count > 0:
        return True, [
            f"🫥 {golden_prefix}{target['name']} loses 1 hide ({new_hide_count} remaining)"
        ], {
            'hide_reduced': True,
            'hide_remaining': new_hide_count,
            'targets': [target]
        }
    else:
        return True, [
            f"👁️ {golden_prefix}{target['name']} is no longer hidden!"
        ], {
            'hide_reduced': True,
            'hide_remaining': 0,
            'unhidden': True,
            'targets': [target]
        }


def reduce_ring(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Reduce ring count after triggering at start of combat

    This effect is automatically applied after Ring triggers a death toll.
    When ring count reaches 0, calls remove_keyword to permanently remove the keyword.

    Args:
        effect_data: Effect configuration (usually empty or with target)
        context: Combat context with acting_minion

    Returns:
        Tuple of (success, logs, changes)
    """
    target_spec = effect_data.get('target', 'self')
    acting_minion = context.get('acting_minion')

    # Resolve target (usually self for the ring minion)
    if target_spec == 'self':
        target = acting_minion
    else:
        success, target, error = resolve_target(target_spec, context, acting_minion)
        if not success:
            return False, [f"❌ Ring reduction targeting failed: {error}"], {}

    if not target:
        return False, ["❌ No target for ring reduction"], {}

    # Check if target has ring
    if not has_keyword(target, 'ring'):
        return True, [], {}  # No ring to reduce

    # Get current permanent ring count (like Cat's permanent stats)
    ring_count = target.get('permanent_ring_count', 0)

    if ring_count <= 0:
        return True, [], {}  # Already exhausted

    # Reduce ring count (decreases by 1)
    new_ring_count = reduce_ring_count(target)

    # CRITICAL: Save the decreased permanent_ring_count back to the band (like permanent_stat_gain does)
    band_id = target.get('band_id')
    run = context.get('run')
    if run and band_id is not None:
        current_band = run.get_band()
        for band_minion in current_band:
            if band_minion.get('band_id') == band_id:
                band_minion['permanent_ring_count'] = new_ring_count
                run.set_band(current_band)
                logger.debug(f"[REDUCE_RING] Saved permanent_ring_count={new_ring_count} to band minion {band_minion.get('name')}")
                break

    # Track in effect context
    effect_context = context.get('effect_context')
    if effect_context:
        effect_context.target_minions.append(target)
        effect_context.add_tag('ring_reduced')
        if new_ring_count <= 0:
            effect_context.add_tag('ring_exhausted')

    # Generate log
    is_golden = target.get('golden', False)
    golden_prefix = "💎 Golden " if is_golden else ""

    if new_ring_count <= 0:
        # Ring exhausted - keyword removal will be handled by next effect in sequence
        return True, [
            f"🔔 {golden_prefix}{target['name']}'s Ring has been exhausted!"
        ], {
            'ring_reduced': True,
            'permanent_ring_count': 0,
            'ring_exhausted': True,
            'targets': [target]
        }
    else:
        return True, [
            f"🔔 {golden_prefix}{target['name']}'s Ring decreased to {new_ring_count}"
        ], {
            'ring_reduced': True,
            'permanent_ring_count': new_ring_count,
            'targets': [target]
        }


def leap_move(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Move a minion to the right when it attacks (Leap keyword effect)

    This effect is automatically applied when a minion with Leap attacks.

    NEW: Now emits leap events for on_any_leap triggers (Railway Signal, Frog Prince)
    UPDATED: Passes minions_jumped, starting_position, and ending_position to triggers

    Args:
        effect_data: Effect configuration with distance (or uses minion's leap_distance)
        context: Combat context with acting_minion

    Returns:
        Tuple of (success, logs, changes)
    """
    acting_minion = context.get('acting_minion')

    if not acting_minion:
        return False, ["❌ No acting minion for leap"], {}

    # Check if minion has leap
    if not has_keyword(acting_minion, 'leap'):
        return True, [], {}  # No leap keyword

    # Get leap distance from minion or effect data
    distance = effect_data.get('distance')
    if distance is None:
        distance = acting_minion.get('leap_distance', 1)

    # Apply golden doubling
    if acting_minion.get('golden', False):
        distance *= 2

    # Get the registry to update positions
    registry = context.get('combat_registry')
    if not registry:
        return False, ["❌ No registry for leap position updates"], {}

    # Get acting minion's band
    band_type = registry.get_minion_band_type(acting_minion)
    if not band_type:
        return False, ["❌ Cannot determine leaping minion's band"], {}

    # Get the appropriate band
    if band_type == 'player':
        band = context.get('absolute_player_band', context.get('player_band', []))
    else:
        band = context.get('absolute_enemy_band', context.get('enemy_band', []))

    # Find minion's current position
    current_pos = acting_minion.get('position', 0)

    # Calculate new position (leap is always to the right)
    new_pos = min(current_pos + distance, len(band) - 1)

    # If position changes, perform the leap
    if new_pos != current_pos:
        # Find all minions between current and new position
        minions_to_shift = []
        for other in band:
            other_pos = other.get('position', 0)
            if other_pos > current_pos and other_pos <= new_pos:
                minions_to_shift.append(other)

        # Shift all minions to the left by 1
        for other in minions_to_shift:
            other['position'] -= 1
            registry.update_minion_position(other, other['position'])

        # Move the leaping minion to its new position
        acting_minion['position'] = new_pos
        registry.update_minion_position(acting_minion, new_pos)

        # Rearrange the band array to match new positions
        band.sort(key=lambda m: m.get('position', 0))

        # Track in effect context
        effect_context = context.get('effect_context')
        if effect_context:
            effect_context.target_minions.append(acting_minion)
            effect_context.add_tag('leap_performed')
            effect_context.add_tag('position_changed')

        # Generate log
        is_golden = acting_minion.get('golden', False)
        golden_prefix = "💎 Golden " if is_golden else ""

        # Calculate minions jumped
        minions_jumped = len(minions_to_shift)

        # NEW: Register leap triggers for watchers (like Railway Signal and Frog Prince)
        registrar = context.get('registrar')
        if registrar:
            logger.debug(f"[LEAP] Registering leap triggers for {acting_minion['name']} - jumped {minions_jumped} minions from pos {current_pos} to {new_pos}")
            registrar.register_leap_triggers(
                leaping_minion=acting_minion,
                minions_jumped=minions_jumped,
                starting_position=current_pos,
                ending_position=new_pos
            )

        return True, [
            f"🦘 {golden_prefix}{acting_minion['name']} leaps {distance} space(s) to the right!"
        ], {
            'targets': [acting_minion],
            'old_position': current_pos,
            'new_position': new_pos,
            'minions_jumped': minions_jumped
        }

    return True, [], {}  # No position change


def modify_fatigue(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Modify the fatigue counter (for Boggart's cast)

    Args:
        effect_data: Effect configuration with amount
        context: Combat context with combat_state

    Returns:
        Tuple of (success, logs, changes)
    """
    amount = effect_data.get('amount', 20)
    acting_minion = context.get('acting_minion')

    # Modify the combat state's attack count to accelerate fatigue
    combat_state = context.get('combat_state')
    if not combat_state:
        return False, ["❌ No combat state for fatigue modification"], {}

    current_count = combat_state.get('attack_count', 0)
    combat_state['attack_count'] = current_count + amount

    # Check if this triggers fatigue
    if combat_state['attack_count'] >= 100 and not combat_state.get('fatigue_active', False):
        combat_state['fatigue_active'] = True

        # Generate log
        is_golden = acting_minion.get('golden', False)
        golden_prefix = "💎 Golden " if is_golden else ""

        # Track in effect context
        effect_context = context.get('effect_context')
        if effect_context:
            effect_context.add_tag('fatigue_activated')

        return True, [
            f"🔮 Cast: {golden_prefix}{acting_minion['name']} accelerates fatigue by {amount} attacks!",
            "💀⚡ Fatigue activated early! All minions will take increasing damage!"
        ], {
            'fatigue_modified': amount,
            'fatigue_activated': True
        }
    else:
        # Generate log
        is_golden = acting_minion.get('golden', False)
        golden_prefix = "💎 Golden " if is_golden else ""

        attacks_until_fatigue = max(0, 100 - combat_state['attack_count'])

        # Track in effect context
        effect_context = context.get('effect_context')
        if effect_context:
            effect_context.add_tag('fatigue_accelerated')

        return True, [
            f"🔮 Cast: {golden_prefix}{acting_minion['name']} accelerates fatigue by {amount} attacks!",
            f"⏰ Fatigue will begin in {attacks_until_fatigue} attacks"
        ], {
            'fatigue_modified': amount,
            'fatigue_activated': False
        }


def chrono_cascade(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Chronomancer's effect - force the next cast minion to cast and apply stun

    Args:
        effect_data: Effect configuration (find_next_cast should be True)
        context: Combat context with trigger information

    Returns:
        Tuple of (success, logs, changes)
    """
    acting_minion = context.get('acting_minion')  # Chronomancer
    trigger_source = context.get('trigger_context_source')  # The original caster

    if not acting_minion or not trigger_source:
        return False, ["❌ No acting minion or trigger source for chrono cascade"], {}

    # Get the registry to find band minions
    registry = context.get('combat_registry')
    if not registry:
        return False, ["❌ No combat registry for chrono cascade"], {}

    # Get ally band (minions in same band as Chronomancer)
    ally_band = registry.get_ally_band(acting_minion, alive_only=True)

    # Sort by position to maintain order
    ally_band.sort(key=lambda m: m.get('position', 999))

    # Find the position of the trigger source (the original caster)
    trigger_pos = trigger_source.get('position', -1)

    logger.debug(f"[CHRONO] Looking for next cast minion after position {trigger_pos}")
    ally_list = [f"{m.get('name')} at pos {m.get('position')}" for m in ally_band]
    logger.debug(f"[CHRONO] Allies: {ally_list}")

    # Find the next minion with 'cast' keyword after the trigger source
    next_cast_minion = None
    for minion in ally_band:
        minion_pos = minion.get('position', -1)
        # Must be after trigger source position and have cast keyword
        if minion_pos > trigger_pos and has_keyword(minion, 'cast'):
            # Check if this minion is already stunned (skip if stunned)
            if minion.get('stun_count', 0) > 0:
                continue
            next_cast_minion = minion
            break

    if not next_cast_minion:
        # No valid cast minion found after the trigger source
        is_golden = acting_minion.get('golden', False)
        golden_prefix = "💎 Golden " if is_golden else ""
        return False, [f"⏰ {golden_prefix}{acting_minion['name']} finds no cast minion after {trigger_source['name']}"], {}

    # Now force this minion to cast
    perform_result = perform_cast({'target_minion': next_cast_minion}, context)

    if not perform_result[0]:
        return perform_result  # Pass through the failure

    # Apply stun 1 to the minion that was forced to cast
    stun_amount = 1
    if acting_minion.get('golden', False):
        stun_amount = 2  # Golden doubles the stun

    apply_stun_result = apply_stun({'target': 'specific', 'target_minion': next_cast_minion, 'stun_amount': stun_amount}, context)

    # Combine logs
    all_logs = []
    is_golden = acting_minion.get('golden', False)
    golden_prefix = "💎 Golden " if is_golden else ""

    all_logs.append(f"⏰ {golden_prefix}{acting_minion['name']} triggers time cascade!")
    all_logs.extend(perform_result[1])
    all_logs.extend(apply_stun_result[1])

    # Combine changes
    combined_changes = perform_result[2]
    combined_changes.update(apply_stun_result[2])
    combined_changes['chrono_triggered'] = True

    return True, all_logs, combined_changes


def perform_cast(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Force a minion to perform their cast effect immediately

    Args:
        effect_data: Effect configuration with target_minion
        context: Combat context

    Returns:
        Tuple of (success, logs, changes)
    """
    target_minion = effect_data.get('target_minion')
    acting_minion = context.get('acting_minion')

    if not target_minion:
        return False, ["❌ No target minion for perform_cast"], {}

    # Check if target has cast keyword
    if not has_keyword(target_minion, 'cast'):
        return False, [f"❌ {target_minion['name']} has no cast ability"], {}

    # Check if target is alive
    if target_minion.get('health', 0) <= 0:
        return False, [f"❌ {target_minion['name']} is dead"], {}

    # Get the cast effect from the target minion
    cast_effect = target_minion.get('cast_effect')
    if not cast_effect:
        return False, [f"❌ {target_minion['name']} has cast keyword but no cast_effect"], {}

    # Apply golden doubling if the forced caster is golden
    if target_minion.get('golden', False):
        import copy
        cast_effect = apply_golden_doubling_to_cast(cast_effect, target_minion)

    # Generate appropriate log
    is_golden_caster = target_minion.get('golden', False)
    golden_caster_prefix = "💎 Golden " if is_golden_caster else ""

    # CRITICAL: Send FORCE_CAST and TRIGGER_CAST interpreter commands BEFORE executing child effects
    # FORCE_CAST shows the forcing animation, TRIGGER_CAST enables bundle detection for the cast
    interpreter = context.get('interpreter')
    if interpreter:
        from game_engine.interpreter import CommandBuilder
        command_builder = CommandBuilder()

        force_cast_log = f"🔮⏰ Forced Cast: {golden_caster_prefix}{target_minion['name']} is compelled to cast!"

        # Build FORCE_CAST command (shows the forcing animation)
        command = command_builder.build_effect_command(
            effect_type='perform_cast',
            effect_data={'type': 'perform_cast', 'target_minion': target_minion},
            changes={'targets': [target_minion]},
            source_minion=acting_minion,
            trigger_type=None,
            log_message=force_cast_log
        )

        if command:
            interpreter.add_command(command)
            logger.debug(f"[PERFORM_CAST] Sent FORCE_CAST command for {target_minion['name']}")

        # Build TRIGGER_CAST command for the forced minion (enables animation bundle detection)
        trigger_cast_log = f"🔮 {golden_caster_prefix}{target_minion['name']} casts a spell!"
        trigger_command = command_builder.build_trigger_command(
            trigger_type='cast',
            source_minion=target_minion,
            log_message=trigger_cast_log
        )

        if trigger_command:
            interpreter.add_command(trigger_command)
            logger.debug(f"[PERFORM_CAST] Sent TRIGGER_CAST command for {target_minion['name']}")

    # Create a new context for the forced cast with the target as acting minion
    cast_context = dict(context)  # Copy context
    cast_context['acting_minion'] = target_minion
    cast_context['trigger_source'] = 'forced_cast'

    # CRITICAL: Always use apply_effects_list so child effects send their own commands to interpreter
    # This ensures the frontend sees the actual cast effects (damage, summon, etc.)
    from game_engine.effects import apply_effects_list
    if not isinstance(cast_effect, list):
        cast_effect = [cast_effect]
    success, logs, changes = apply_effects_list(cast_effect, cast_context)

    # Register on_any_cast watchers (just like normal casts do)
    # A forced cast is still fundamentally a cast and should trigger watchers
    registrar = context.get('registrar')
    if registrar:
        # Get spell target from the cast's changes (if any)
        spell_target = changes.get('targets', [None])[0] if changes.get('targets') else None

        # Register watchers for this cast
        registrar.register_spell_cast_triggers(target_minion, spell_target)
        logger.debug(f"[PERFORM_CAST] Registered on_any_cast watchers for forced cast by {target_minion['name']}")
    else:
        logger.warning(f"[PERFORM_CAST] WARNING: No registrar in context, cannot register on_any_cast watchers")

    # Emit spell cast event for other watchers
    from game_engine.events.combat_events import CombatEventType
    event_system = context.get('event_system')
    if event_system:
        event_system.emit_event(
            CombatEventType.SPELL_CAST,
            source=target_minion
        )

    cast_logs = logs  # Child effects already generated their own logs

    # Track in effect context
    effect_context = context.get('effect_context')
    if effect_context:
        effect_context.add_tag('forced_cast')
        effect_context.target_minions.append(target_minion)

    return True, cast_logs, changes


def apply_stun(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Apply stun to a target minion or multiple targets with optional filtering

    UPDATED: Added target_filters support for dynamic filtering
    UPDATED: Added convenience parameters (exclude_self, exclude_type) that auto-convert to filters

    Args:
        effect_data: Effect configuration with target, stun_amount, target_filters, exclude_self, exclude_type
        context: Combat context

    Returns:
        Tuple of (success, logs, changes)
    """
    target_spec = effect_data.get('target', 'specific')
    stun_amount = effect_data.get('stun_amount', 1)
    target_filters = effect_data.get('target_filters')  # NEW: Optional filtering
    acting_minion = context.get('acting_minion')

    # NEW: Auto-convert convenience parameters to filters
    convenience_filters = []
    if effect_data.get('exclude_self'):
        convenience_filters.append({
            'type': 'not_self',
            'target': 'target_minion'
        })
    if 'exclude_type' in effect_data:
        convenience_filters.append({
            'type': 'not_type',
            'target': 'target_minion',
            'minion_type': effect_data['exclude_type']
        })

    # Combine explicit filters with convenience filters
    if convenience_filters:
        if target_filters:
            target_filters = target_filters + convenience_filters
        else:
            target_filters = convenience_filters

    # Handle specific target (for chrono_cascade and similar)
    if target_spec == 'specific':
        target = effect_data.get('target_minion')
        if not target:
            return False, ["❌ No specific target for stun"], {}
        targets = [target]
    else:
        # Resolve target normally - might return multiple targets
        success, targets, error = resolve_target(target_spec, context, acting_minion)
        if not success:
            return False, [f"❌ Stun targeting failed: {error}"], {}

        # Ensure list
        if not isinstance(targets, list):
            targets = [targets]

    # NEW: Apply filters if provided
    if target_filters:
        logger.debug(f"[APPLY STUN] Applying {len(target_filters)} filters to {len(targets)} candidates")
        targets = _apply_target_filters(targets, target_filters, context)

        if not targets:
            is_golden = acting_minion.get('golden', False) if acting_minion else False
            golden_prefix = "💎 Golden " if is_golden else ""
            return True, [f"✨ {golden_prefix}{acting_minion['name'] if acting_minion else 'Effect'} found no valid targets for stun after filtering"], {}

    # Apply stun to all filtered targets
    logs = []
    stunned_minions = []

    for target in targets:
        # Initialize stun_count if not present
        if 'stun_count' not in target:
            target['stun_count'] = 0

        # Apply stun
        target['stun_count'] += stun_amount

        # Add stun keyword if not present
        if 'stun' not in target.get('keywords', []):
            if 'keywords' not in target:
                target['keywords'] = []
            target['keywords'].append('stun')

        stunned_minions.append(target)

        # Send APPLY_STUN interpreter command for frontend
        interpreter = context.get('interpreter')
        if interpreter:
            from game_engine.interpreter import CommandBuilder
            command_builder = CommandBuilder()

            is_golden = acting_minion.get('golden', False) if acting_minion else False
            golden_prefix = "💎 Golden " if is_golden else ""
            stun_log = f"⏸️ {golden_prefix}{acting_minion['name'] if acting_minion else 'Effect'} stuns {target['name']} for {stun_amount} attack(s)!"

            command = command_builder.build_effect_command(
                effect_type='apply_stun',
                effect_data={'type': 'apply_stun', 'stun_amount': stun_amount},
                changes={'targets': [target], 'stun_applied': stun_amount},
                source_minion=acting_minion,
                trigger_type=None,
                log_message=stun_log
            )

            if command:
                interpreter.add_command(command)
                logger.debug(f"[APPLY_STUN] Sent APPLY_STUN command for {target['name']}")

    # Track in effect context
    effect_context = context.get('effect_context')
    if effect_context:
        effect_context.target_minions.extend(stunned_minions)
        effect_context.add_tag('stun_applied')

    # Generate logs
    trigger_source = context.get('trigger_source', 'effect')
    is_golden = acting_minion.get('golden', False) if acting_minion else False
    golden_prefix = "💎 Golden " if is_golden else ""

    if len(stunned_minions) == 1:
        target = stunned_minions[0]
        if trigger_source == 'forced_cast':
            log_entry = f"⏸️ {target['name']} is stunned for {stun_amount} attack(s)!"
        else:
            log_entry = f"⏸️ {golden_prefix}{acting_minion['name'] if acting_minion else 'Unknown'} stuns {target['name']} for {stun_amount} attacks"
        logs.append(log_entry)
    else:
        # Multiple targets
        target_names = ', '.join(t['name'] for t in stunned_minions)
        log_entry = f"⏸️ {golden_prefix}{acting_minion['name'] if acting_minion else 'Unknown'} stuns {target_names} for {stun_amount} attacks each"
        logs.append(log_entry)

    return True, logs, {
        'stun_applied': stun_amount,
        'targets': stunned_minions,
        'target_count': len(stunned_minions)
    }


def apply_golden_doubling_to_cast(cast_effect, golden_minion):
    """Apply golden doubling to a cast effect (handles both single and list of effects)"""
    import copy

    # If it's a list of effects, apply doubling to each
    if isinstance(cast_effect, list):
        modified_effects = []
        for effect in cast_effect:
            modified_effects.append(apply_golden_doubling_to_single_effect(effect, golden_minion))
        return modified_effects
    else:
        # Single effect
        return apply_golden_doubling_to_single_effect(cast_effect, golden_minion)


def apply_golden_doubling_to_single_effect(effect, golden_minion):
    """Apply golden doubling to a single effect"""
    import copy
    modified = copy.deepcopy(effect)

    effect_type = modified.get('type')

    # Apply standard doubling based on effect type
    if effect_type in ['deal_damage', 'heal', 'heal_self', 'damage_self']:
        if 'amount' in modified:
            modified['amount'] *= 2
        if 'target_count' in modified:
            modified['target_count'] *= 2

    elif effect_type == 'deal_aoe_damage':
        if 'amount' in modified:
            modified['amount'] *= 2
        if 'max_targets' in modified:
            modified['max_targets'] *= 2

    elif effect_type in ['buff_stats', 'debuff_stats']:
        if 'health' in modified:
            modified['health'] *= 2
        if 'attack' in modified:
            modified['attack'] *= 2

    elif effect_type == 'summon_minion':
        if 'summon_count' in modified:
            modified['summon_count'] *= 2
        else:
            modified['summon_count'] = 2
        if 'health' in modified:
            modified['health'] *= 2
        if 'attack' in modified:
            modified['attack'] *= 2

    elif effect_type == 'destroy_and_transform':
        if 'summon_count' in modified:
            modified['summon_count'] *= 2

    elif effect_type == 'destroy_minion':
        # Stat ratio doesn't change for destroy
        pass

    elif effect_type == 'modify_fatigue':
        if 'amount' in modified:
            modified['amount'] *= 2

    elif effect_type == 'divide_attack':
        # Divisor doesn't change for divide_attack
        pass

    elif effect_type == 'rich_buff':
        # Rich buff doubling is handled in the effect itself
        pass

    elif effect_type == 'modify_gold':
        # Gold modification gets doubled
        if 'amount' in modified:
            modified['amount'] *= 2

    elif effect_type == 'apply_stun':
        if 'stun_amount' in modified:
            modified['stun_amount'] *= 2

    elif effect_type == 'transfer_stun':
        # Transfer stun doesn't double - transfers what exists
        pass

    elif effect_type == 'scaling_damage':
        # Scaling damage doubling is handled in the effect itself (doubles current and increment)
        pass

    elif effect_type == 'trigger_death_toll':
        # Trigger death toll doesn't double - it triggers existing effects
        # The triggered effect itself may be golden and handle its own doubling
        pass

    return modified


def attack_target(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Perform an attack on a target

    FIXED: resolve_all_triggers returns only logs, not (success, logs) tuple
    """
    all_logs = []

    # ===== PHASE 1: Get attacking minion =====
    attacker_spec = effect_data.get('attacker', 'self')  # Default to 'self' if not specified

    # Handle different attacker specifications
    if isinstance(attacker_spec, str):
        if attacker_spec == 'self' or attacker_spec == 'acting_minion':
            # 'self' and 'acting_minion' both mean the minion performing the action
            attacking_minion = context.get('acting_minion')
        elif attacker_spec == 'condition_found_minion':
            attacking_minion = context.get('condition_found_minion')
        elif attacker_spec == 'trigger_summoned':
            # FIXED: Use trigger_context_target for on_any_summon
            attacking_minion = context.get('trigger_context_target')
        else:
            # Try to resolve as a target spec (e.g., 'random_ally', 'lowest_health_ally')
            success, attacking_minion, error = resolve_target(attacker_spec, context, context.get('acting_minion'))
            if not success:
                return False, [f"❌ Attacker resolution failed: {error}"], {}
    elif isinstance(attacker_spec, dict):
        # Direct minion dict reference
        attacking_minion = attacker_spec
    else:
        return False, ["❌ Invalid attacker specification in attack_target effect"], {}

    if not attacking_minion:
        return False, ["❌ No attacking minion found for attack_target"], {}

    if attacking_minion.get('health', 0) <= 0:
        return False, ["❌ Attacking minion is already dead"], {}

    # ===== PHASE 2: Check if attacker can attack =====
    if has_keyword(attacking_minion, 'cant_attack'):
        is_golden = attacking_minion.get('golden', False)
        golden_prefix = "💎 Golden " if is_golden else ""
        return True, [f"🚫 {golden_prefix}{attacking_minion['name']} can't attack"], {}

    attack_value = attacking_minion.get('attack', 0)
    if attack_value <= 0:
        is_golden = attacking_minion.get('golden', False)
        golden_prefix = "💎 Golden " if is_golden else ""
        return True, [f"🚫 {golden_prefix}{attacking_minion['name']} has no attack"], {}

    # ===== PHASE 3: Resolve target =====
    target_spec = effect_data.get('target_minion')

    if target_spec is None:
        # AUTO-TARGET: Use centralized targeting logic (respects savage, guard, hide)
        from keywords import select_combat_target

        registry = context.get('combat_registry')
        if not registry:
            return False, ["❌ No combat registry for attack_target"], {}

        enemy_band = registry.get_enemy_band(attacking_minion, alive_only=True)
        if not enemy_band:
            return False, ["❌ No alive enemies to attack"], {}

        # Use select_combat_target to respect savage keyword and other targeting rules
        target_minion = select_combat_target(attacking_minion, enemy_band)

    elif isinstance(target_spec, str):
        if target_spec == 'condition_found_minion':
            target_minion = context.get('condition_found_minion')
        else:
            success, target_minion, error = resolve_target(target_spec, context, attacking_minion)
            if not success:
                return False, [f"❌ Attack target resolution failed: {error}"], {}

    elif isinstance(target_spec, dict):
        # EXPLICIT MINION DICT: Direct minion reference
        target_minion = target_spec
    else:
        return False, ["❌ Invalid target_minion in attack_target effect"], {}

    if not target_minion:
        return False, ["❌ No target minion found for attack_target"], {}

    if target_minion.get('health', 0) <= 0:
        return False, ["❌ Target is already dead"], {}

    # ===== PHASE 4: Register attack-triggered effects BEFORE attack =====
    # Mirror the regular attack pipeline (combat_system.process_attack →
    # trigger_processor.add_initial_triggers) so triggered attacks — Shinobi's
    # start-of-combat, Houndmaster's cast-summoned Hound, etc. — fire the same
    # hide reduction, leap movement, and assault/cast/rage triggers as a normal
    # turn-order attack. The only thing a triggered attack doesn't do is
    # advance turn order.
    pre_attack_logs = []
    trigger_processor = context.get('trigger_processor')
    if trigger_processor:
        trigger_processor.add_initial_triggers(attacking_minion, target_minion)
        pre_attack_logs.extend(trigger_processor.resolve_all_triggers())
    else:
        # Fallback for contexts without a trigger_processor (should not happen
        # in real combat, but some unit tests wire only the registrar).
        registrar = context.get('registrar')
        if registrar:
            registrar.register_attack_triggers(attacking_minion, target_minion)

    all_logs.extend(pre_attack_logs)

    # ===== PHASE 5: Check if attacker still alive =====
    if attacking_minion.get('health', 0) <= 0:
        is_golden = attacking_minion.get('golden', False)
        golden_prefix = "💎 Golden " if is_golden else ""
        all_logs.append(f"🚫 {golden_prefix}{attacking_minion['name']} died before completing their attack!")
        return True, all_logs, {'attacker_killed': True}

    # ===== PHASE 6: Route through the normal combat-action handlers =====
    # Rather than duplicating damage + log logic, dispatch DECLARE_ATTACK and
    # COMBAT_DAMAGE through the same handlers normal combat uses. The result is
    # a real attack (lunge animation, correct log format, cleave/poke/counter
    # all handled) that does NOT advance the turn order, because we never call
    # into process_combat_step — we just enqueue the commands inline.
    from game_engine.combat_actions import process_declare_attack, process_combat_damage
    from game_engine.combat_system import CombatSystem
    from minions import get_minion_attack_with_aura

    registry = context.get('combat_registry')
    combat_state = context.get('combat_state')
    attacker_index = 0
    if registry is not None:
        attacker_index = registry.position_map.get(attacking_minion.get('_combat_id'), 0) or 0

    # DECLARE_ATTACK — this is what queues the attack lunge on the frontend.
    declare_data = {
        'attacker': attacking_minion,
        'defender': target_minion,
        'attacker_index': attacker_index,
    }
    ok, declare_logs, declare_changes = process_declare_attack(declare_data, context)
    if ok:
        all_logs.extend(declare_logs)
        if combat_state is not None:
            CombatSystem._add_action_command(combat_state, 'declare_attack', declare_data, declare_changes, declare_logs)

    # COMBAT_DAMAGE — handles damage, counter, poke, cant_retaliate, cleave,
    # nobility/ignoble, obliterate, and emits the correct log format.
    base_damage = get_minion_attack_with_aura(attacking_minion)
    base_counter = get_minion_attack_with_aura(target_minion)
    has_cleave = has_keyword(attacking_minion, 'cleave')
    damage_action = {
        'attacker': attacking_minion,
        'defender': target_minion,
        'base_damage': base_damage,
        'base_counter': base_counter,
        'has_poke': has_keyword(attacking_minion, 'poke'),
        'defender_cant_retaliate': has_keyword(target_minion, 'cant_retaliate'),
        'attacker_index': attacker_index,
        'has_cleave': has_cleave,
        'cleave_amount': attacking_minion.get('cleave_amount', 1) if has_cleave else 0,
    }
    dmg_ok, dmg_logs, dmg_changes = process_combat_damage(damage_action, context)
    if dmg_ok:
        all_logs.extend(dmg_logs)
        if combat_state is not None:
            CombatSystem._add_action_command(combat_state, 'combat_damage', damage_action, dmg_changes, dmg_logs)

    cleave_targets = dmg_changes.get('cleave_targets', []) if dmg_ok else []
    total_cleave_damage = sum(
        (t.get('damage_taken_this_attack', 0) or 0) for t in cleave_targets
    ) if cleave_targets else 0

    return True, all_logs, {
        'damage_dealt': dmg_changes.get('damage_dealt', 0) if dmg_ok else 0,
        'counter_damage': dmg_changes.get('counter_damage_dealt', 0) if dmg_ok else 0,
        'cleave_damage': total_cleave_damage,
        'cleave_targets': cleave_targets,
        'target_killed': target_minion.get('health', 0) <= 0,
        'attacker_killed': attacking_minion.get('health', 0) <= 0,
        'targets': [target_minion] + list(cleave_targets),
        'attacker': attacking_minion,
    }


def redirect_damage(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Redirect damage to another target (for Spell Shield-like effects)

    UPDATED: Now routes through damage_handler for centralized damage processing

    Args:
        effect_data: Effect configuration with damage_amount, new_target
        context: Combat context

    Returns:
        Tuple of (success, logs, changes)
    """
    damage_amount = effect_data.get('damage_amount', 0)
    new_target = effect_data.get('new_target')
    acting_minion = context.get('acting_minion')

    if not new_target or damage_amount <= 0:
        return False, ["❌ Invalid damage redirect configuration"], {}

    # Apply damage through damage handler (SPELL type damage, respects nobility)
    damage_result = apply_damage(
        target=new_target,
        amount=damage_amount,
        damage_type=DamageType.SPELL,
        source_minion=acting_minion,
        context=context
    )

    # Track in effect context
    effect_context = context.get('effect_context')
    if effect_context:
        if damage_result.damage_applied > 0:
            effect_context.target_minions.append(new_target)
            effect_context.damage_dealt = damage_result.damage_applied
        effect_context.add_tag('damage_redirected')

    # Generate logs
    logs = []
    is_golden = acting_minion.get('golden', False)
    golden_prefix = "💎 Golden " if is_golden else ""

    if damage_result.blocked_by_nobility:
        logs.append(f"🛡️ {golden_prefix}{acting_minion['name']} tries to redirect {damage_amount} spell damage to {new_target['name']}")
        logs.extend(damage_result.logs)

        return True, logs, {
            'damage_redirected': 0,
            'nobility_blocked': True,
            'targets': []
        }
    else:
        logs.append(f"🛡️ Spell Shield: {golden_prefix}{acting_minion['name']} redirects {damage_amount} spell damage to {new_target['name']}!")

        return True, logs, {
            'damage_redirected': damage_result.damage_applied,
            'targets': [new_target]
        }


def prevent_death(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Prevent a minion from dying (set health to 1 if would die)

    Args:
        effect_data: Effect configuration with target
        context: Combat context

    Returns:
        Tuple of (success, logs, changes)
    """
    target_spec = effect_data.get('target', 'self')
    acting_minion = context.get('acting_minion')

    # Resolve target
    success, target, error = resolve_target(target_spec, context, acting_minion)

    if not success:
        return False, [f"❌ {error}"], {}

    # Check if target would die
    if target['health'] <= 0:
        # Prevent death by setting health to 1
        target['health'] = 1

        # Track in effect context
        effect_context = context.get('effect_context')
        if effect_context:
            effect_context.target_minions.append(target)
            effect_context.prevented_death = True
            effect_context.add_tag('death_prevented')

        # Generate log
        is_golden = acting_minion.get('golden', False)
        golden_prefix = "💎 Golden " if is_golden else ""

        return True, [
            f"✨ {golden_prefix}{acting_minion['name']} prevents {target['name']} from dying!"
        ], {
            'death_prevented': True,
            'targets': [target]
        }

    return False, [f"{target['name']} is not dying"], {}


def copy_stats(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Copy stats from one minion to another

    Args:
        effect_data: Effect configuration with source and target
        context: Combat context

    Returns:
        Tuple of (success, logs, changes)
    """
    source_spec = effect_data.get('source', 'trigger_source')
    target_spec = effect_data.get('target', 'self')
    copy_health = effect_data.get('copy_health', True)
    copy_attack = effect_data.get('copy_attack', True)
    acting_minion = context.get('acting_minion')

    # Resolve source
    success, source, error = resolve_target(source_spec, context, acting_minion)
    if not success:
        return False, [f"❌ Source error: {error}"], {}

    # Resolve target
    success, target, error = resolve_target(target_spec, context, acting_minion)
    if not success:
        return False, [f"❌ Target error: {error}"], {}

    # Copy stats
    if copy_health:
        target['health'] = source['health']
    if copy_attack:
        target['attack'] = source['attack']

    # Track in effect context
    effect_context = context.get('effect_context')
    if effect_context:
        effect_context.target_minions.append(target)
        if copy_health:
            effect_context.stats_changed['health'] = source['health']
        if copy_attack:
            effect_context.stats_changed['attack'] = source['attack']
        effect_context.add_tag('stats_copied')

    # Generate log
    is_golden = acting_minion.get('golden', False)
    golden_prefix = "💎 Golden " if is_golden else ""

    stats_copied = []
    if copy_health:
        stats_copied.append(f"{source['health']} health")
    if copy_attack:
        stats_copied.append(f"{source['attack']} attack")

    return True, [
        f"📋 {golden_prefix}{acting_minion['name']} copies {', '.join(stats_copied)} from {source['name']} to {target['name']}"
    ], {
        'stats_copied': True,
        'targets': [target]
    }


def grant_keyword(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Grant a keyword to a minion

    Args:
        effect_data: Effect configuration with target and keyword
        context: Combat context

    Returns:
        Tuple of (success, logs, changes)
    """
    target_spec = effect_data.get('target', 'self')
    keyword = effect_data.get('keyword')
    keyword_data = effect_data.get('keyword_data', {})  # Additional data for the keyword
    acting_minion = context.get('acting_minion')

    if not keyword:
        return False, ["❌ No keyword specified"], {}

    # Resolve target
    success, target, error = resolve_target(target_spec, context, acting_minion)

    if not success:
        return False, [f"❌ {error}"], {}

    # Add keyword if not already present
    if 'keywords' not in target:
        target['keywords'] = []

    if keyword not in target['keywords']:
        target['keywords'].append(keyword)

        # Add any keyword-specific data
        if keyword == 'cleave' and 'amount' in keyword_data:
            target['cleave_amount'] = keyword_data['amount']

        # Track in effect context
        effect_context = context.get('effect_context')
        if effect_context:
            effect_context.target_minions.append(target)
            effect_context.add_tag('keyword_granted')
            effect_context.add_tag(f'granted_{keyword}')

        # Generate log
        is_golden = acting_minion.get('golden', False)
        golden_prefix = "💎 Golden " if is_golden else ""

        keyword_desc = keyword
        if keyword == 'cleave' and 'amount' in keyword_data:
            keyword_desc = f"Cleave {keyword_data['amount']}"

        return True, [
            f"🎯 {golden_prefix}{acting_minion['name']} grants {keyword_desc} to {target['name']}"
        ], {
            'keyword_granted': keyword,
            'targets': [target]
        }

    return False, [f"{target['name']} already has {keyword}"], {}


def remove_keyword(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Remove a keyword from a minion (can affect combat minion, band minion, or both)

    This effect enables permanent keyword removal that persists to the band.
    Used by Ring keyword to remove itself when count reaches 0.

    Args:
        effect_data: Effect configuration with:
            - target: Target specification (default 'self')
            - keyword: Keyword to remove
            - scope: Where to remove from - 'combat_only', 'band_only', or 'both' (default 'both')
            - only_if_zero: If True, only remove if permanent_ring_count is 0 (for ring keyword)
        context: Combat context

    Returns:
        Tuple of (success, logs, changes)
    """
    target_spec = effect_data.get('target', 'self')
    keyword = effect_data.get('keyword')
    scope = effect_data.get('scope', 'both')  # 'combat_only', 'band_only', or 'both'
    only_if_zero = effect_data.get('only_if_zero', False)
    acting_minion = context.get('acting_minion')

    if not keyword:
        return False, ["❌ No keyword specified for removal"], {}

    # Resolve target (combat minion)
    logger.debug(f"[REMOVE_KEYWORD] Starting - keyword={keyword}, only_if_zero={only_if_zero}, target_spec={target_spec}")
    success, target, error = resolve_target(target_spec, context, acting_minion)
    if not success:
        logger.error(f"[REMOVE_KEYWORD] FAILED - Could not resolve target: {error}")
        return False, [f"❌ {error}"], {}

    logger.debug(f"[REMOVE_KEYWORD] Target resolved: {target.get('name')}, permanent_ring_count={target.get('permanent_ring_count')}")

    # Check if we should only remove when permanent_ring_count is 0
    if only_if_zero and keyword == 'ring':
        ring_count = target.get('permanent_ring_count', 0)
        logger.debug(f"[REMOVE_KEYWORD] Checking only_if_zero: ring_count={ring_count}")
        if ring_count > 0:
            # Don't remove yet - count is still positive
            logger.debug(f"[REMOVE_KEYWORD] Skipping removal - permanent_ring_count={ring_count} (only_if_zero=True)")
            return True, [], {}  # Success but no action taken
        logger.debug(f"[REMOVE_KEYWORD] ring_count is 0, proceeding with removal")

    removed_from_combat = False
    removed_from_band = False

    # Remove from combat minion
    if scope in ['combat_only', 'both']:
        if 'keywords' in target and keyword in target['keywords']:
            target['keywords'] = [kw for kw in target['keywords'] if kw != keyword]
            removed_from_combat = True
            logger.debug(f"[REMOVE_KEYWORD] Removed '{keyword}' from combat minion {target.get('name')}")

    # Remove from band minion
    if scope in ['band_only', 'both']:
        band_id = target.get('band_id')
        logger.debug(f"[REMOVE_KEYWORD] Target band_id: {band_id}")

        if band_id is not None:
            # Get the run to access band
            run = context.get('run')
            logger.debug(f"[REMOVE_KEYWORD] Run from context: {run}")

            if run:
                # Get the current band using run.get_band() (works for both MockRun and real Run)
                current_band = run.get_band()
                logger.debug(f"[REMOVE_KEYWORD] Band size: {len(current_band)}")

                # Find the band minion
                for band_minion in current_band:
                    if band_minion.get('band_id') == band_id:
                        logger.debug(f"[REMOVE_KEYWORD] Found band minion {band_minion.get('name')} with band_id {band_id}")
                        if 'keywords' in band_minion and keyword in band_minion['keywords']:
                            band_minion['keywords'] = [kw for kw in band_minion['keywords'] if kw != keyword]
                            removed_from_band = True
                            logger.debug(f"[REMOVE_KEYWORD] Removed '{keyword}' from band minion {band_minion.get('name')} (band_id: {band_id})")
                            logger.debug(f"[REMOVE_KEYWORD] Band minion keywords now: {band_minion.get('keywords')}")

                            # CRITICAL: Save the modified band back to persist changes (like permanent_stat_gain does)
                            run.set_band(current_band)
                            logger.debug(f"[REMOVE_KEYWORD] Saved modified band back to run")
                        else:
                            logger.debug(f"[REMOVE_KEYWORD] Keyword '{keyword}' not found in band minion keywords: {band_minion.get('keywords')}")
                        break
                else:
                    logger.debug(f"[REMOVE_KEYWORD] Band minion with band_id {band_id} not found in band")
            else:
                logger.debug(f"[REMOVE_KEYWORD] Cannot access run from context")

    # Check if anything was removed
    if not removed_from_combat and not removed_from_band:
        return True, [], {}  # Nothing to remove (keyword not present)

    # Track in effect context
    effect_context = context.get('effect_context')
    if effect_context:
        effect_context.target_minions.append(target)
        effect_context.add_tag('keyword_removed')
        effect_context.add_tag(f'removed_{keyword}')

    # Generate log
    is_golden = target.get('golden', False)
    golden_prefix = "💎 Golden " if is_golden else ""

    scope_description = ""
    if scope == 'combat_only':
        scope_description = " (combat only)"
    elif scope == 'band_only':
        scope_description = " (band only)"

    return True, [
        f"🔔 {golden_prefix}{target['name']}'s {keyword} keyword removed{scope_description}"
    ], {
        'keyword_removed': keyword,
        'removed_from_combat': removed_from_combat,
        'removed_from_band': removed_from_band,
        'targets': [target]
    }