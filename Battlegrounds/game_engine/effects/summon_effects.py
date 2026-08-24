"""
Summon Effects - All summon and transformation related effects

This module contains implementations for summoning minions,
transformations, and related effects.

UPDATED: Added destroy_minion effect and individual summon trigger queueing
UPDATED: Enhanced context handling for conditional effects with saved stats
UPDATED: Improved stat inheritance from destroy effects for sequential processing
FIXED: Meat Packaging Plant now explicitly summons to the right
FIXED: Position calculation ensures summons always go to the right of summoner
FIXED: Atomic processing - prevents individual queueing within effect arrays
FIXED: Golden doubling cascade - prevent re-application of golden effects
UPDATED: Added support for adding keywords to summoned minions
UPDATED: Added inherit_band_id flag to control band_id inheritance for summons
NEW: Added criteria-based random minion selection system
"""

import logging

logger = logging.getLogger(__name__)

from typing import Dict, List, Tuple, Optional
import random
from keywords import resolve_target


def _select_random_minion_by_criteria(effect_data: Dict, context: Dict) -> Optional[Dict]:
    """
    Select a random minion matching the given criteria

    Args:
        effect_data: Effect data containing summon_criteria
        context: Combat context with run information

    Returns:
        Minion template dict or None if no matches found
    """
    from minions import filter_minions_by_modifiers, MINIONS

    # Get criteria object
    criteria = effect_data.get('summon_criteria', {})

    # Extract criteria parameters
    tier = criteria.get('tier', 1)
    tribe = criteria.get('tribe')  # optional
    rarity = criteria.get('rarity')  # optional
    exclude_names = criteria.get('exclude_names', [])
    pool_modifiers = criteria.get('pool_modifiers')

    # Get zone's pool modifiers if not specified and run available
    if pool_modifiers is None:
        run = context.get('run')
        if run and hasattr(run, 'current_zone'):
            zone_data = run.current_zone
            if isinstance(zone_data, dict):
                pool_modifiers = zone_data.get('pool_modifiers')

    # Handle tier as list or single value
    tiers_to_check = [tier] if isinstance(tier, int) else tier

    # Collect all matching minions from specified tiers
    available_minions = []
    for tier_level in tiers_to_check:
        tier_minions = filter_minions_by_modifiers(tier_level, pool_modifiers)
        available_minions.extend(tier_minions)

    # Filter by tribe if specified
    if tribe:
        filtered_by_tribe = []
        for minion in available_minions:
            minion_type = minion.get('type', 'None')
            # Handle multi-faction minions
            if isinstance(minion_type, list):
                if tribe in minion_type:
                    filtered_by_tribe.append(minion)
            else:
                if minion_type == tribe:
                    filtered_by_tribe.append(minion)
        available_minions = filtered_by_tribe

    # Filter by rarity if specified
    if rarity:
        available_minions = [m for m in available_minions
                           if m.get('rarity') == rarity]

    # Exclude specific names
    if exclude_names:
        available_minions = [m for m in available_minions
                           if m['name'] not in exclude_names]

    # Select randomly from matches
    if not available_minions:
        logger.debug(f"[CRITERIA] No minions found matching criteria: {criteria}")
        return None

    selected = random.choice(available_minions)
    logger.debug(f"[CRITERIA] Selected {selected['name']} from {len(available_minions)} matches (tier={tier}, tribe={tribe})")
    return selected


def summon_minion(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Summon a minion during combat

    UPDATED: Now supports queueing individual summon triggers when queue_individual=True
    UPDATED: Enhanced handling of saved stats from destroy effects
    UPDATED: Added support for adding keywords to summoned minions
    UPDATED: Added inherit_band_id flag to control band_id inheritance
    NEW: Added criteria-based random minion selection
    FIXED: Always ensures summons go to the right of the summoner
    FIXED: Prevents individual queueing within atomic effect arrays
    FIXED: Golden doubling cascade - prevents re-application of golden effects

    Args:
        effect_data: Effect configuration with minion_name OR summon_criteria, health, attack, summon_count, queue_individual, keywords, inherit_band_id
        context: Combat context with registry

    Returns:
        Tuple of (success, logs, changes)
    """
    summon_count = effect_data.get('summon_count', 1)
    queue_individual = effect_data.get('queue_individual', False)

    # CRITICAL FIX: Check if we're processing an effect array atomically
    # If so, disable individual queueing to prevent breaking atomicity
    if context.get('processing_effect_array', False):
        queue_individual = False
        logger.debug(f"[SUMMON] Disabled individual queueing - processing within atomic effect array")

    # ADDITIONAL FIX: For conditional effects with multiple effects, also disable individual queueing
    # This handles cases where conditional effects process lists without the array context
    elif context.get('total_array_effects', 0) > 1:
        queue_individual = False
        logger.debug(f"[SUMMON] Disabled individual queueing - part of multi-effect conditional")

    # If we should queue individual triggers and count > 1, queue them instead of processing
    if queue_individual and summon_count > 1:
        return _queue_individual_summons(effect_data, context)

    # Otherwise, process a single summon (or batch if not using individual queueing)
    return _process_summon(effect_data, context)


def _queue_individual_summons(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Queue individual summon triggers instead of processing them all at once

    Args:
        effect_data: Effect configuration
        context: Combat context

    Returns:
        Tuple indicating triggers were queued
    """
    summon_count = effect_data.get('summon_count', 1)
    acting_minion = context.get('acting_minion', context.get('dying_minion'))

    # Get the trigger processor to queue triggers
    from game_engine.trigger_queue import TriggerPriority
    trigger_processor = context.get('trigger_processor')

    if not trigger_processor:
        # Fall back to direct processing if no processor available
        logger.debug(f"[SUMMON] No trigger processor available, falling back to direct processing")
        return _process_summon(effect_data, context)

    # Preserve saved stats from destroy effects for all individual summons
    saved_stats = context.get('saved_stats')

    # FIXED: Determine if golden effects have been applied
    # For golden minions, if we're in a trigger context, golden effects have been applied
    # This is because the main trigger (cast/assault/death_toll) applies golden doubling first
    is_golden_minion = acting_minion.get('golden', False)
    in_trigger_context = context.get('trigger_source') in ['cast', 'assault', 'death_toll', 'rage', 'on_any_death', 'on_any_cast', 'on_any_summon']

    # For golden minions in trigger contexts, effects have already been applied at trigger level
    golden_effects_applied = is_golden_minion and in_trigger_context

    logger.debug(f"[QUEUE INDIVIDUAL] Golden: {is_golden_minion}, Trigger context: {in_trigger_context}, Effects applied: {golden_effects_applied}")

    # Determine minion name for logging (might be criteria-based)
    if 'summon_criteria' in effect_data:
        minion_name = "random minion"
    else:
        minion_name = effect_data.get('minion_name', 'unknown')

    # Create individual summon triggers
    for i in range(summon_count):
        # Create a copy of the effect data for this individual summon
        individual_effect = dict(effect_data)
        individual_effect['summon_count'] = 1  # Each trigger summons one
        individual_effect['queue_individual'] = False  # Don't re-queue
        individual_effect['summon_index'] = i  # Track which summon this is

        # CRITICAL: Ensure position is explicitly set to 'right' for MPP
        individual_effect['position'] = 'right'

        # If using saved stats from destroy effect, pass them through
        if saved_stats:
            individual_effect['use_saved_stats'] = True

        # Create the trigger
        summon_trigger = {
            'type': 'individual_summon',
            'source_minion': acting_minion,
            'effect_data': individual_effect,
            'saved_stats': saved_stats,  # Pass saved stats if available
            'golden_effects_applied': golden_effects_applied  # FIXED: Proper golden effects status
        }

        # Queue with HIGH priority
        trigger_processor.trigger_queue.add_trigger(summon_trigger, TriggerPriority.HIGH)

    # Generate log
    is_golden = acting_minion.get('golden', False)
    golden_prefix = "💎 Golden " if is_golden else ""

    return True, [f"✨ {golden_prefix}{acting_minion['name']} queues {summon_count} {minion_name} summons"], {
        'summons_queued': summon_count
    }


def _process_summon(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Process actual summon (single or batch)

    This is the original summon logic, now extracted to a helper function.
    UPDATED: Enhanced saved stats handling for conditional effects
    UPDATED: Added support for adding keywords to summoned minions
    UPDATED: Added inherit_band_id flag to control band_id inheritance
    NEW: Added criteria-based random minion selection
    FIXED: Explicitly ensures summons go to the right of the summoner
    FIXED: Golden doubling cascade - prevent re-application of golden effects
    """
    from minions import create_summon_minion

    # NEW: Check if using criteria-based selection
    if 'summon_criteria' in effect_data:
        minion_template = _select_random_minion_by_criteria(effect_data, context)
        if not minion_template:
            acting_minion = context.get('acting_minion', context.get('dying_minion'))
            is_golden = acting_minion.get('golden', False) if acting_minion else False
            golden_prefix = "💎 Golden " if is_golden else ""
            return False, [f"❌ {golden_prefix}No minions match summon criteria"], {}

        minion_name = minion_template['name']
        # Get base stats from template (will be modified by golden/saved stats)
        base_health = minion_template['health']
        base_attack = minion_template['attack']
    else:
        # Traditional name-based summoning
        minion_name = effect_data.get('minion_name', 'Bone')
        base_health = effect_data.get('health', 1)
        base_attack = effect_data.get('attack', 1)

    health = base_health
    attack = base_attack
    summon_count = effect_data.get('summon_count', 1)
    position = effect_data.get('position', 'right')  # Default to right for MPP
    use_saved_stats = effect_data.get('use_saved_stats', False)
    keywords_to_add = effect_data.get('keywords', [])  # Keywords to add to summoned minions
    inherit_band_id = effect_data.get('inherit_band_id', True)  # Control band_id inheritance (default True for backward compatibility)

    # CRITICAL FIX: Force position to right for Meat Packaging Plant
    acting_minion = context.get('acting_minion', context.get('dying_minion'))
    if acting_minion and acting_minion.get('name') == 'Meat Packaging Plant':
        position = 'right'
        logger.debug(f"[SUMMON] Forcing Meat Packaging Plant to summon to the right")

    if not acting_minion:
        return False, ["🎯 No acting minion for summon"], {}

    # ENHANCED: Handle saved stats from destroy effects (critical for conditional effects)
    if use_saved_stats:
        saved_stats = context.get('saved_stats')
        if saved_stats:
            health = saved_stats.get('health', health)
            attack = saved_stats.get('attack', attack)
            logger.debug(f"[SUMMON] Using saved stats: {health} health, {attack} attack")
        else:
            logger.warning(f"[SUMMON WARNING] use_saved_stats=True but no saved_stats in context")

    # CRITICAL FIX: Only apply golden doubling if not already applied
    golden_effects_applied = context.get('golden_effects_applied', False)
    is_golden = acting_minion.get('golden', False)

    logger.debug(f"[SUMMON DEBUG] Minion: {acting_minion['name']}, Golden: {is_golden}, Effects applied: {golden_effects_applied}")
    logger.debug(f"[SUMMON DEBUG] Before doubling - health: {health}, attack: {attack}, summon_count: {summon_count}")

    if is_golden and not golden_effects_applied:
        # Apply golden doubling to the final stats (after saved stats are applied)
        health *= 2
        attack *= 2
        summon_count *= 2
        logger.debug(f"[SUMMON] Applied golden doubling: {health} health, {attack} attack, {summon_count} count")
    elif is_golden and golden_effects_applied:
        # Golden effects already applied at trigger level, don't double again
        logger.debug(f"[SUMMON] Golden effects already applied, skipping re-application")
    else:
        logger.debug(f"[SUMMON] No golden doubling needed: golden={is_golden}, applied={golden_effects_applied}")

    logger.debug(f"[SUMMON DEBUG] After doubling - health: {health}, attack: {attack}, summon_count: {summon_count}")

    # Get registry from context
    registry = context.get('combat_registry')

    if not registry:
        logger.error("[SUMMON ERROR] No combat registry for summon!")
        return False, ["❌ No combat registry for summon"], {}

    # Determine which band to summon to using registry
    band_type = registry.get_minion_band_type(acting_minion)

    logger.debug(f"[SUMMON] Acting minion {acting_minion.get('name')} (combat_id: {acting_minion.get('_combat_id', 'NO_ID')}) has band type: {band_type}")

    if not band_type:
        logger.error(f"[SUMMON ERROR] Registry cannot determine band for summoner {acting_minion.get('name')}")
        return False, ["🎯 Could not determine summoner's band from registry"], {}

    # Use absolute band references from context
    absolute_player_band = context.get('absolute_player_band')
    absolute_enemy_band = context.get('absolute_enemy_band')

    if absolute_player_band is None:
        absolute_player_band = context.get('player_band', [])
        logger.warning(f"[SUMMON WARNING] No absolute_player_band in context")
    if absolute_enemy_band is None:
        absolute_enemy_band = context.get('enemy_band', [])
        logger.warning(f"[SUMMON WARNING] No absolute_enemy_band in context")

    # Get the correct band to summon to
    if band_type == 'player':
        target_band = absolute_player_band
    else:
        target_band = absolute_enemy_band

    logger.debug(f"[SUMMON] Summoning to {band_type} band which has {len(target_band)} minions")

    # CRITICAL: Get current summoner position for accurate positioning
    current_summoner_position = registry.get_minion_position(acting_minion)
    if current_summoner_position is None:
        # Fallback: find summoner in band
        if acting_minion in target_band:
            current_summoner_position = target_band.index(acting_minion)
        else:
            current_summoner_position = 0
        logger.warning(f"[SUMMON] Warning: Registry position lookup failed, using fallback position {current_summoner_position}")

    logger.debug(f"[SUMMON] Summoner {acting_minion['name']} is at position {current_summoner_position}")

    # Summon multiple minions if needed
    summoned_minions = []
    summoned_names = []

    # For individual summons, use the stored summon_index instead of loop index
    summon_index = effect_data.get('summon_index', 0)
    is_individual_summon = 'summon_index' in effect_data

    for i in range(summon_count):
        # Create the summoned minion with band ID inheritance based on flag
        inherit_band_id_value = None
        if inherit_band_id and band_type == 'player' and 'band_id' in acting_minion:
            inherit_band_id_value = acting_minion['band_id']
            logger.debug(f"[SUMMON] Summoned minion will inherit band_id: {inherit_band_id_value}")
        elif not inherit_band_id:
            logger.debug(f"[SUMMON] Summoned minion will NOT inherit band_id (inherit_band_id=False)")

        summoned_minion = create_summon_minion(minion_name, {
            'health': health,
            'attack': attack
        }, inherit_band_id=inherit_band_id_value)

        # NEW: Add keywords to the summoned minion
        if keywords_to_add:
            if 'keywords' not in summoned_minion:
                summoned_minion['keywords'] = []
            for keyword in keywords_to_add:
                if keyword not in summoned_minion['keywords']:
                    summoned_minion['keywords'].append(keyword)
                    logger.debug(f"[SUMMON] Added keyword '{keyword}' to summoned {minion_name}")

        # CRITICAL FIX: Calculate proper insert position
        if is_individual_summon:
            # For individual summons, recalculate summoner position each time
            # as previous summons may have shifted positions
            updated_summoner_position = registry.get_minion_position(acting_minion)
            if updated_summoner_position is None:
                # Fallback
                if acting_minion in target_band:
                    updated_summoner_position = target_band.index(acting_minion)
                else:
                    updated_summoner_position = current_summoner_position

            # Use summon_index for individual summons to get correct offset
            position_offset = summon_index
            base_position = updated_summoner_position
        else:
            # For batch summons, use original position and loop index
            position_offset = i
            base_position = current_summoner_position

        # Calculate insert position - ALWAYS to the right for MPP
        if position == 'right':
            insert_position = base_position + 1 + position_offset
        elif position == 'left':
            insert_position = max(0, base_position - position_offset)
        else:
            # Default to right
            insert_position = base_position + 1 + position_offset

        # Ensure we don't exceed band size
        insert_position = min(insert_position, len(target_band))

        # Set the summoned minion's position field BEFORE inserting
        summoned_minion['position'] = insert_position

        # Insert into the band at the correct position
        target_band.insert(insert_position, summoned_minion)

        # CRITICAL: Immediately fix all positions after insertion to prevent gaps
        for idx, minion in enumerate(target_band):
            minion['position'] = idx
            # Update registry as well
            registry.update_minion_position(minion, idx)

        # Register the summoned minion with registry at its final position
        final_position = target_band.index(summoned_minion)
        registry.add_summoned_minion(summoned_minion, acting_minion, final_position)

        summoned_minions.append(summoned_minion)

        # Include keywords in the name display if any were added
        keywords_text = f" with {', '.join(keywords_to_add)}" if keywords_to_add else ""
        summoned_names.append(f"{minion_name} ({health}/{attack}){keywords_text}")

        # Enhanced debug logging
        if is_individual_summon:
            logger.debug(f"[SUMMON] Individual summon #{summon_index + 1}: {minion_name} at final position {final_position} to {band_type} band")
        else:
            logger.debug(f"[SUMMON] Batch summon #{i + 1}: {minion_name} at final position {final_position} to {band_type} band")

        # Update current_summoner_position for next iteration in batch summons
        if not is_individual_summon:
            current_summoner_position = registry.get_minion_position(acting_minion)

    # Track in effect context
    effect_context = context.get('effect_context')
    if effect_context:
        effect_context.minions_summoned.extend(summoned_minions)

    # CRITICAL FIX: Deep copy summoned minions for command generation
    # This creates a snapshot of minions at summon-time, not a reference to live objects
    # If minions are damaged/killed later in the turn, commands still show correct summon stats
    import copy
    summoned_minions_snapshot = [copy.deepcopy(minion) for minion in summoned_minions]

    # Generate log
    trigger_source = context.get('trigger_source', 'effect')
    is_golden = acting_minion.get('golden', False)
    golden_prefix = "💎 Golden " if is_golden else ""

    if summon_count > 1:
        summon_text = f"{summon_count} {minion_name}s"
    else:
        summon_text = f"a {minion_name}"

    # Include keywords in log if any were added
    keywords_text = f" with {', '.join(keywords_to_add)}" if keywords_to_add else ""

    # Enhanced logging for conditional effects with saved stats
    if use_saved_stats and context.get('saved_stats'):
        saved_stats = context['saved_stats']
        original_name = saved_stats.get('original_name', 'unknown')
        if trigger_source == 'cast':
            log_entry = f"🔮 Cast: {golden_prefix}{acting_minion['name']} transforms {original_name} into {summon_text} ({health}/{attack} each){keywords_text}"
        else:
            log_entry = f"✨ {golden_prefix}{acting_minion['name']} transforms {original_name} into {summon_text} ({health}/{attack} each){keywords_text}"
    elif trigger_source == 'death_toll':
        log_entry = f"💀 Death Toll: {golden_prefix}{acting_minion['name']}'s death summons {summon_text} ({health}/{attack} each){keywords_text}"
    elif trigger_source == 'cast':
        log_entry = f"🔮 Cast: {golden_prefix}{acting_minion['name']} summons {summon_text} ({health}/{attack} each){keywords_text}"
    elif trigger_source == 'assault':
        log_entry = f"⚡ Assault: {golden_prefix}{acting_minion['name']} summons {summon_text} ({health}/{attack} each){keywords_text}"
    elif trigger_source == 'individual_summon':
        summon_index = effect_data.get('summon_index', 0)
        log_entry = f"✨ Summoning {minion_name} #{summon_index + 1} ({health}/{attack}){keywords_text}"
    else:
        log_entry = f"✨ {golden_prefix}{acting_minion['name']} summons {summon_text} ({health}/{attack} each){keywords_text}"

    return True, [log_entry], {
        'minions_summoned': summoned_names,
        'targets': summoned_minions,
        'summoner': acting_minion,  # Include summoner for trigger generation
        'summoned_minions': summoned_minions_snapshot,  # Snapshot at summon-time (not live references)
        'summon_occurred': True  # Flag for trigger processor
    }


def destroy_minion(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Destroy a minion and optionally save its stats for later use

    UPDATED: Enhanced for conditional effects - stats are saved to context for immediate use
    FIXED: Golden doubling prevention - only apply stat_ratio adjustments if not already applied

    Args:
        effect_data: Effect configuration with target, save_stats, stat_ratio
        context: Combat context

    Returns:
        Tuple of (success, logs, changes)
    """
    target_spec = effect_data.get('target', 'left_ally')
    save_stats = effect_data.get('save_stats', False)
    stat_ratio = effect_data.get('stat_ratio', 1.0)
    acting_minion = context.get('acting_minion')

    # Special handling for left_ally - need to exclude self
    if target_spec == 'left_ally':
        # Get ally band from context
        ally_band = context.get('ally_band', [])

        # Get alive allies to the left of the acting minion
        acting_pos = acting_minion.get('position', 999)
        left_allies = [
            m for m in ally_band
            if m.get('health', 0) > 0
            and m != acting_minion  # Exclude self
            and m.get('position', 999) < acting_pos  # Must be to the left
        ]

        if not left_allies:
            # Generate appropriate failure log
            is_golden = acting_minion.get('golden', False)
            golden_prefix = "💎 Golden " if is_golden else ""
            return False, [
                f"🔮 Cast Failed: {golden_prefix}{acting_minion['name']} has no ally to its left to destroy"
            ], {}

        # Sort by position and get the rightmost of the left allies (closest to acting minion)
        left_allies.sort(key=lambda m: m.get('position', 0), reverse=True)
        target = left_allies[0]

    else:
        # Use normal targeting for other target specs
        success, target, error = resolve_target(target_spec, context, acting_minion)

        if not success:
            return False, [f"🎯 No target to destroy: {error}"], {}

        # Still check if target is self (safety check for other target specs)
        if target == acting_minion:
            is_golden = acting_minion.get('golden', False)
            golden_prefix = "💎 Golden " if is_golden else ""
            return False, [
                f"🔮 Cast Failed: {golden_prefix}{acting_minion['name']} cannot destroy itself"
            ], {}

    # CRITICAL FIX: Golden effects should NOT double stat_ratio
    # The stat_ratio determines what percentage of stats to save
    # Golden minions should still save the same percentage, but summon more minions
    # stat_ratio has already been correctly handled in trigger processor (NOT doubled)

    logger.debug(f"[DESTROY DEBUG] Target: {target['name']}, Health: {target['health']}, Attack: {target['attack']}")
    logger.debug(f"[DESTROY DEBUG] Acting minion: {acting_minion['name']}, Golden: {acting_minion.get('golden', False)}")
    logger.debug(f"[DESTROY DEBUG] stat_ratio: {stat_ratio} (should be 0.5 for MPP, even if golden)")

    # Store target's stats before destruction if requested
    saved_stats = {}
    if save_stats:
        saved_stats = {
            'health': max(1, int(target['health'] * stat_ratio)),
            'attack': max(0, int(target['attack'] * stat_ratio)),
            'original_name': target['name'],
            'original_type': target.get('type', 'None')
        }
        # Save to context for subsequent effects (CRITICAL for conditional effects)
        context['saved_stats'] = saved_stats
        logger.debug(f"[DESTROY] Saved stats for {target['name']}: {saved_stats}")

    logger.debug(f"[DESTROY DEBUG] Final saved stats: health={saved_stats.get('health', 'N/A')}, attack={saved_stats.get('attack', 'N/A')}")

    target_name = target['name']

    # Mark target as dead (but don't set _marked_dead to allow death toll)
    target['health'] = 0

    # Track in effect context
    effect_context = context.get('effect_context')
    if effect_context:
        effect_context.target_minions.append(target)
        effect_context.caused_death.append(target)
        if save_stats:
            effect_context.add_tag('stats_saved')

    # Generate log
    trigger_source = context.get('trigger_source', 'cast')
    is_golden = acting_minion.get('golden', False)
    golden_prefix = "💎 Golden " if is_golden else ""

    logs = []
    if trigger_source == 'cast':
        logs.append(f"🔮 Cast: {golden_prefix}{acting_minion['name']} destroys {target_name}!")
    else:
        logs.append(f"💀 {golden_prefix}{acting_minion['name']} destroys {target_name}!")

    if save_stats:
        logs.append(f"📊 Saved stats: {saved_stats['health']} health, {saved_stats['attack']} attack")

    return True, logs, {
        'destroyed': target_name,
        'saved_stats': saved_stats if save_stats else None,
        'targets': [target]
    }


def destroy_and_transform(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Legacy effect - now uses destroy_minion and summon_minion separately
    Kept for backward compatibility

    Args:
        effect_data: Effect configuration with target, summon_count, minion_name, stat_ratio
        context: Combat context

    Returns:
        Tuple of (success, logs, changes)
    """
    # Convert to the new two-effect system
    stat_ratio = effect_data.get('stat_ratio', 0.5)

    # First destroy the minion
    destroy_effect = {
        'type': 'destroy_minion',
        'target': effect_data.get('target', 'left_ally'),
        'save_stats': True,
        'stat_ratio': stat_ratio
    }

    destroy_success, destroy_logs, destroy_changes = destroy_minion(destroy_effect, context)

    if not destroy_success:
        return destroy_success, destroy_logs, destroy_changes

    # Then summon the minions using saved stats (explicitly to the right)
    summon_effect = {
        'type': 'summon_minion',
        'minion_name': effect_data.get('minion_name', 'Meat Cube'),
        'summon_count': effect_data.get('summon_count', 2),
        'use_saved_stats': True,
        'queue_individual': True,  # Use individual queueing for proper trigger resolution
        'position': 'right'  # Explicitly to the right
    }

    summon_success, summon_logs, summon_changes = summon_minion(summon_effect, context)

    # Combine results
    all_logs = destroy_logs + summon_logs
    all_changes = {**destroy_changes, **summon_changes}

    return summon_success, all_logs, all_changes


def move_minion(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Move a minion's position in its band

    Args:
        effect_data: Effect configuration with target, direction, distance
        context: Combat context

    Returns:
        Tuple of (success, logs, changes)
    """
    target_spec = effect_data.get('target', 'defender')
    direction = effect_data.get('direction', 'right')
    distance = effect_data.get('distance', 1)
    acting_minion = context.get('acting_minion')

    # Apply golden doubling to distance only if not already applied
    golden_effects_applied = context.get('golden_effects_applied', False)

    if acting_minion and acting_minion.get('golden', False) and not golden_effects_applied:
        distance *= 2

    # Resolve target
    success, target, error = resolve_target(target_spec, context, acting_minion)

    if not success:
        return False, [f"🎯 Move targeting failed: {error}"], {}

    # Get the registry to update positions
    registry = context.get('combat_registry')
    if not registry:
        return False, ["❌ No registry for position updates"], {}

    # Get target's band
    band_type = registry.get_minion_band_type(target)
    if not band_type:
        return False, ["❌ Cannot determine target's band"], {}

    # Get the appropriate band
    if band_type == 'player':
        band = context.get('absolute_player_band', context.get('player_band', []))
    else:
        band = context.get('absolute_enemy_band', context.get('enemy_band', []))

    # Find target's current position
    current_pos = target.get('position', 0)

    # Calculate new position
    if direction == 'right':
        new_pos = min(current_pos + distance, len(band) - 1)
    else:  # left
        new_pos = max(current_pos - distance, 0)

    # If position changes, swap minions
    if new_pos != current_pos:
        # Find minion at new position
        for other in band:
            if other.get('position') == new_pos:
                # Swap positions
                other['position'] = current_pos
                target['position'] = new_pos

                # Update registry positions
                registry.update_minion_position(target, new_pos)
                registry.update_minion_position(other, current_pos)

                # Swap in band array (find by identity, not position index)
                current_idx = next((i for i, m in enumerate(band) if m is target), None)
                new_idx = next((i for i, m in enumerate(band) if m is other), None)
                if current_idx is not None and new_idx is not None:
                    band[current_idx], band[new_idx] = band[new_idx], band[current_idx]

                # Track in effect context
                effect_context = context.get('effect_context')
                if effect_context:
                    effect_context.target_minions.append(target)
                    effect_context.add_tag('position_changed')

                # Generate log
                is_golden = acting_minion.get('golden', False)
                golden_prefix = "💎 Golden " if is_golden else ""

                return True, [
                    f"⚡ Assault: {golden_prefix}{acting_minion['name']} moves {target['name']} {distance} position(s) {direction}",
                    f"🔄 {target['name']} swaps positions with {other['name']}"
                ], {
                    'position_changed': True,
                    'targets': [target],
                    'old_position': current_pos,
                    'new_position': new_pos,
                    'band': band_type
                }

    # No position change
    is_golden = acting_minion.get('golden', False)
    golden_prefix = "💎 Golden " if is_golden else ""

    return True, [
        f"⚡ Assault: {golden_prefix}{acting_minion['name']} tries to move {target['name']} but they're already at the edge"
    ], {
        'targets': [target]
    }