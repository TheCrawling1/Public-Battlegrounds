"""
Conditional Effects - Implements conditional logic for effects

This module allows effects to have if/then/else logic based on
various conditions about minions, game state, and combat context.

UPDATED: Added 'not_name' condition type to support Destroyer checking
if the trigger source is not named "Destroyer".
UPDATED: Added trigger_summoned and trigger_summoner target support for on_any_summon.
UPDATED: Added 'has_left_ally' condition type for Meat Packaging Plant.
UPDATED: Added support for effect lists in then_effect and else_effect.
FIXED: Multi-effect context - prevents individual queueing in effect arrays.
UPDATED: Fixed apply_effect_or_effects to use trigger processor for proper interpreter integration.
FIXED: stat_ratio should NOT be doubled for destroy_minion effects.
UPDATED: Added 'has_minion_named' condition for Houndmaster.
CRITICAL: Added metadata-based condition checking for dead minions in on_any_death triggers.
This allows Old Cat Lady to properly check if dying Cats are allies by using band_type metadata.
IMPORTANT: Ally checks compare band_type ('player' or 'enemy'), NOT band_id (unique per minion).
UPDATED: Made has_minion_named dynamic - finds all matching minions, uses GameRandom to select one,
and stores in context['condition_found_minion'] for effects to use.
UPDATED: Added 'not_self' and 'not_type' conditions for dynamic effect filtering.
UPDATED: Added 'is_tier' condition for Warlord to check minion tier.
UPDATED: Added 'has_minion_with_keyword' condition for Gangster to find minions with specific keywords.
"""

import logging

logger = logging.getLogger(__name__)

from typing import Dict, List, Tuple, Optional, Any
from keywords import has_keyword
from game_random import game_random, SelectionType


def evaluate_conditional(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Evaluate a conditional effect

    Args:
        effect_data: Effect configuration with condition and then/else effects
        context: Combat context

    Returns:
        Tuple of (success, logs, changes)
    """
    condition = effect_data.get('condition', {})
    then_effect = effect_data.get('then_effect')
    else_effect = effect_data.get('else_effect')

    acting_minion = context.get('acting_minion')

    # Evaluate the condition
    condition_met = evaluate_condition(condition, context)

    # Debug logging
    if acting_minion:
        condition_desc = describe_condition(condition)
        logger.debug(f"[CONDITIONAL] {acting_minion.get('name')} evaluating: {condition_desc} = {condition_met}")

    # Apply the appropriate effect(s)
    if condition_met:
        if then_effect:
            # Apply golden doubling to the then effect if needed
            if acting_minion and acting_minion.get('golden', False):
                then_effect = apply_golden_doubling_to_effect(then_effect, acting_minion)

            return apply_effect_or_effects(then_effect, context)
        else:
            return True, ["Condition met but no then_effect specified"], {}
    else:
        if else_effect:
            # Apply golden doubling to the else effect if needed
            if acting_minion and acting_minion.get('golden', False):
                else_effect = apply_golden_doubling_to_effect(else_effect, acting_minion)

            return apply_effect_or_effects(else_effect, context)
        else:
            # No else effect, just return success with no action
            return True, ["Condition not met, no action taken"], {}


def apply_effect_or_effects(effect_data, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Apply a single effect or a list of effects

    UPDATED: Uses apply_effects_list for proper interpreter integration.
    The trigger_processor is passed through context and apply_effects_list handles
    sending individual effects to the interpreter automatically.

    Args:
        effect_data: Single effect dict or list of effect dicts
        context: Combat context

    Returns:
        Tuple of (success, logs, changes)
    """
    if isinstance(effect_data, list):
        # Apply multiple effects using the standard effects system
        # This already handles interpreter integration via trigger_processor in context
        logger.debug(f"[CONDITIONAL] Processing {len(effect_data)} effect array")

        # CRITICAL: Set multi-effect context to prevent individual queueing
        original_total_effects = context.get('total_array_effects', 0)
        context['total_array_effects'] = len(effect_data)
        context['processing_effect_array'] = True

        try:
            # Apply multiple effects using standard method
            # NOTE: apply_effects_list already checks for trigger_processor in context
            # and sends effects to interpreter automatically
            from game_engine.effects import apply_effects_list
            result = apply_effects_list(effect_data, context)
            return result
        finally:
            # Restore original context
            if original_total_effects > 0:
                context['total_array_effects'] = original_total_effects
            else:
                context.pop('total_array_effects', None)
            context.pop('processing_effect_array', None)
    else:
        # Apply single effect using standard approach
        from game_engine.effects import apply_effect
        return apply_effect(effect_data, context)


def evaluate_condition(condition: Dict, context: Dict) -> bool:
    """
    Evaluate a condition against the current context

    Args:
        condition: Condition specification
        context: Combat context

    Returns:
        bool: Whether the condition is met
    """
    if not condition:
        return True  # No condition means always true

    check_type = condition.get('check_type', 'simple')

    if check_type == 'simple':
        return evaluate_simple_condition(condition, context)
    elif check_type == 'compound':
        return evaluate_compound_condition(condition, context)
    else:
        logger.debug(f"[CONDITIONAL] Unknown check_type: {check_type}")
        return False


def evaluate_simple_condition(condition: Dict, context: Dict) -> bool:
    """
    Evaluate a simple single condition

    UPDATED: Now supports checking conditions via metadata when actual minion
    is not available (e.g., dead minions in on_any_death triggers)
    UPDATED: Added is_self_leaper condition for Frog Prince
    UPDATED: Added context-only conditions that don't require target resolution
    """
    condition_type = condition.get('type')

    # Context-only conditions that don't require a target minion
    if condition_type == 'not_additional_trigger':
        # Check if this is NOT an additional trigger (prevents infinite loops)
        is_additional = context.get('is_additional_trigger', False)
        result = not is_additional
        logger.debug(f"[CONDITIONAL] not_additional_trigger check: is_additional={is_additional}, result={result}")
        return result

    target_spec = condition.get('target', 'self')

    # Resolve the target minion
    target_minion = resolve_condition_target(target_spec, context)

    logger.debug(
        f"[CONDITIONAL DEBUG] Evaluating {condition_type} on target_spec={target_spec}, got minion: {target_minion.get('name') if target_minion else 'None'}")

    # CRITICAL: For trigger_dying targets, allow None and use metadata instead
    # This supports checking properties of dead minions in on_any_death triggers
    if not target_minion and target_spec == 'trigger_dying':
        metadata = context.get('trigger_dying_metadata')
        if metadata:
            logger.debug(f"[CONDITIONAL] Using metadata for trigger_dying checks: {metadata.get('name')}")
            # Use metadata for supported condition types
            if condition_type == 'is_name':
                minion_name = condition.get('minion_name')
                result = metadata.get('name') == minion_name
                logger.debug(f"[CONDITIONAL] is_name check via metadata: {metadata.get('name')} == {minion_name}? {result}")
                return result

            elif condition_type == 'is_ally':
                result = is_ally_minion(None, context)  # Pass None, will use metadata
                logger.debug(f"[CONDITIONAL] is_ally check via metadata: {result}")
                return result

            elif condition_type == 'is_enemy':
                # Enemy is opposite of ally
                result = not is_ally_minion(None, context)
                logger.debug(f"[CONDITIONAL] is_enemy check via metadata: {result}")
                return result

            elif condition_type == 'is_type':
                minion_type = condition.get('minion_type')
                metadata_type = metadata.get('type')
                # Handle multi-faction minions
                if isinstance(metadata_type, list):
                    return minion_type in metadata_type
                else:
                    return metadata_type == minion_type

            # For other condition types that need the actual minion, fail
            logger.debug(f"[CONDITIONAL] Condition type {condition_type} requires actual minion, not metadata")
            return False

    if not target_minion and condition_type not in ['combat_state_check', 'has_left_ally', 'has_minion_named',
                                                    'has_minion_with_keyword']:
        logger.debug(f"[CONDITIONAL] No target found for condition: {condition_type}")
        return False

    # Special ally position checks
    if condition_type == 'has_left_ally':
        return has_left_ally(context)

    # NEW: Check if target minion is the same as acting minion (Frog Prince, opposite of not_self)
    elif condition_type == 'is_self':
        acting_minion = context.get('acting_minion')
        if not acting_minion or not target_minion:
            logger.debug(f"[CONDITIONAL] is_self: Missing acting_minion or target_minion")
            return False

        result = target_minion.get('_combat_id') == acting_minion.get('_combat_id')
        logger.debug(
            f"[CONDITIONAL] is_self: {target_minion.get('name')} ({target_minion.get('_combat_id')}) == {acting_minion.get('name')} ({acting_minion.get('_combat_id')})? {result}")
        return result

    # FIXED: Check for specific minion name in band using Combat Registry
    elif condition_type == 'has_minion_named':
        minion_name = condition.get('minion_name')
        target = condition.get('target', 'all_allies')
        acting_minion = context.get('acting_minion')

        # CRITICAL: Use Combat Registry as single source of truth
        registry = context.get('combat_registry')
        if not registry:
            logger.debug(f"[CONDITIONAL] No registry for has_minion_named check")
            return False

        # Get the appropriate band
        if target == 'all_allies':
            band_type = registry.get_minion_band_type(acting_minion)
            if not band_type:
                return False
            candidates = registry.get_band_minions(band_type, alive_only=True)
        elif target == 'all_enemies':
            acting_band = registry.get_minion_band_type(acting_minion)
            enemy_band = 'player' if acting_band == 'enemy' else 'enemy'
            candidates = registry.get_band_minions(enemy_band, alive_only=True)
        else:
            logger.debug(f"[CONDITIONAL] Unknown target for has_minion_named: {target}")
            return False

        # Find all minions with the specified name
        found_minions = [m for m in candidates if m.get('name') == minion_name and m.get('health', 0) > 0]

        if not found_minions:
            logger.debug(f"[CONDITIONAL] has_minion_named: No {minion_name} found in {target}")
            return False

        # NEW: Randomly select one and store in context for subsequent effects
        if len(found_minions) > 1:
            random_context = {
                'combat_state': context.get('combat_state'),
                'acting_minion': acting_minion
            }
            selected = game_random.select_one(
                SelectionType.RANDOM_ENEMY,
                found_minions,
                context=random_context,
                description=f"Select {minion_name} for condition"
            )
            logger.debug(
                f"[CONDITIONAL] has_minion_named: Selected {selected.get('name')} (HP: {selected.get('health')}) from {len(found_minions)} options")
        else:
            selected = found_minions[0]
            logger.debug(f"[CONDITIONAL] has_minion_named: Found single {selected.get('name')} (HP: {selected.get('health')})")

        # CRITICAL: Store the selected minion in context for effects to use
        context['condition_found_minion'] = selected
        logger.debug(f"[CONDITIONAL] Stored {selected.get('name')} as condition_found_minion for subsequent effects")

        return True

    # NEW: Check for minion with specific keyword (Gangster)
    elif condition_type == 'has_minion_with_keyword':
        keyword = condition.get('keyword')
        target = condition.get('target', 'all_allies')
        acting_minion = context.get('acting_minion')

        registry = context.get('combat_registry')
        if not registry:
            logger.debug(f"[CONDITIONAL] No registry for has_minion_with_keyword check")
            return False

        # Get the appropriate band
        if target == 'all_allies':
            band_type = registry.get_minion_band_type(acting_minion)
            if not band_type:
                return False
            candidates = registry.get_band_minions(band_type, alive_only=True)
        elif target == 'all_enemies':
            acting_band = registry.get_minion_band_type(acting_minion)
            enemy_band = 'player' if acting_band == 'enemy' else 'enemy'
            candidates = registry.get_band_minions(enemy_band, alive_only=True)
        else:
            logger.debug(f"[CONDITIONAL] Unknown target for has_minion_with_keyword: {target}")
            return False

        # Find all minions with the specified keyword
        found_minions = [m for m in candidates if has_keyword(m, keyword) and m.get('health', 0) > 0]

        if not found_minions:
            logger.debug(f"[CONDITIONAL] has_minion_with_keyword: No minions with {keyword} found in {target}")
            return False

        # Randomly select one and store in context
        if len(found_minions) > 1:
            random_context = {
                'combat_state': context.get('combat_state'),
                'acting_minion': acting_minion
            }
            selected = game_random.select_one(
                SelectionType.RANDOM_ENEMY,
                found_minions,
                context=random_context,
                description=f"Select minion with {keyword} for condition"
            )
            logger.debug(
                f"[CONDITIONAL] has_minion_with_keyword: Selected {selected.get('name')} (HP: {selected.get('health')}) from {len(found_minions)} options")
        else:
            selected = found_minions[0]
            logger.debug(
                f"[CONDITIONAL] has_minion_with_keyword: Found single {selected.get('name')} with {keyword} (HP: {selected.get('health')})")

        # CRITICAL: Store the selected minion in context for effects to use
        context['condition_found_minion'] = selected
        logger.debug(f"[CONDITIONAL] Stored {selected.get('name')} as condition_found_minion for subsequent effects")

        return True

    # Band membership checks
    elif condition_type == 'is_enemy':
        result = is_enemy_minion(target_minion, context)
        logger.debug(f"[CONDITIONAL] is_enemy check for {target_minion.get('name')}: {result}")
        return result

    elif condition_type == 'is_ally':
        result = is_ally_minion(target_minion, context)
        logger.debug(f"[CONDITIONAL] is_ally check for {target_minion.get('name')}: {result}")
        return result

    elif condition_type == 'is_player_minion':
        registry = context.get('combat_registry')
        if registry:
            return registry.get_minion_band_type(target_minion) == 'player'
        return False

    # Name checks
    elif condition_type == 'is_name':
        minion_name = condition.get('minion_name')
        result = target_minion.get('name') == minion_name
        logger.debug(
            f"[CONDITIONAL] is_name check for {target_minion.get('name')}: {target_minion.get('name')} == {minion_name}? {result}")
        return result

    elif condition_type == 'not_name':
        minion_name = condition.get('minion_name')
        return target_minion.get('name') != minion_name

    elif condition_type == 'not_self':
        acting_minion = context.get('acting_minion')
        if not acting_minion:
            return False
        result = target_minion.get('_combat_id') != acting_minion.get('_combat_id')
        return result

    # Keyword checks
    elif condition_type == 'has_keyword':
        keyword = condition.get('keyword')
        return has_keyword(target_minion, keyword)

    elif condition_type == 'not_has_keyword':
        keyword = condition.get('keyword')
        return not has_keyword(target_minion, keyword)

    # Position checks
    elif condition_type == 'is_position':
        position = condition.get('position')
        return check_position(target_minion, position, context)

    # Stat checks
    elif condition_type == 'health_above':
        threshold = condition.get('value', 0)
        # Apply golden doubling to numeric threshold
        acting_minion = context.get('acting_minion')
        if acting_minion and acting_minion.get('golden', False):
            threshold *= 2
        return target_minion.get('health', 0) > threshold

    elif condition_type == 'health_below':
        threshold = condition.get('value', 0)
        acting_minion = context.get('acting_minion')
        if acting_minion and acting_minion.get('golden', False):
            threshold *= 2
        return target_minion.get('health', 0) < threshold

    elif condition_type == 'attack_above':
        threshold = condition.get('value', 0)
        acting_minion = context.get('acting_minion')
        if acting_minion and acting_minion.get('golden', False):
            threshold *= 2
        return target_minion.get('attack', 0) > threshold

    elif condition_type == 'attack_equals':
        value = condition.get('value', 0)
        acting_minion = context.get('acting_minion')
        if acting_minion and acting_minion.get('golden', False):
            value *= 2
        return target_minion.get('attack', 0) == value

    elif condition_type == 'attack_at_most':
        value = condition.get('value', 0)
        acting_minion = context.get('acting_minion')
        if acting_minion and acting_minion.get('golden', False):
            value *= 2
        result = target_minion.get('attack', 0) <= value
        logger.debug(f"[CONDITIONAL] attack_at_most: {target_minion.get('attack', 0)} <= {value}? {result}")
        return result

    # Type checks
    elif condition_type == 'is_type':
        minion_type = condition.get('minion_type')
        target_type = target_minion.get('type')
        # Handle multi-faction minions
        if isinstance(target_type, list):
            return minion_type in target_type
        else:
            return target_type == minion_type

    elif condition_type == 'not_type':
        minion_type = condition.get('minion_type')
        target_type = target_minion.get('type')
        # Handle multi-faction minions
        if isinstance(target_type, list):
            return minion_type not in target_type
        else:
            return target_type != minion_type

    # NEW: Tier checks (for Warlord)
    elif condition_type == 'is_tier':
        tier = condition.get('tier', 1)
        target_tier = target_minion.get('tier', 1)
        result = target_tier == tier
        logger.debug(f"[CONDITIONAL] is_tier check: {target_minion.get('name')} tier {target_tier} == {tier}? {result}")
        return result

    # State checks
    elif condition_type == 'is_golden':
        return target_minion.get('golden', False)

    elif condition_type == 'is_damaged':
        # Would need to track max health or check against template
        return target_minion.get('health', 0) < target_minion.get('max_health', target_minion.get('health', 1))

    elif condition_type == 'at_full_health':
        return target_minion.get('health', 0) >= target_minion.get('max_health', target_minion.get('health', 1))

    # Counter checks
    elif condition_type == 'times_attacked':
        required_count = condition.get('value', 0)
        acting_minion = context.get('acting_minion')
        if acting_minion and acting_minion.get('golden', False):
            required_count *= 2
        # This would need attack counter tracking in combat_state
        attack_count = context.get('combat_state', {}).get('minion_attack_counts', {}).get(
            target_minion.get('_combat_id', ''), 0
        )
        return attack_count >= required_count

    else:
        logger.debug(f"[CONDITIONAL] Unknown condition type: {condition_type}")
        return False


def has_left_ally(context: Dict) -> bool:
    """
    Check if the acting minion has any ally to its left

    Args:
        context: Combat context with acting_minion and ally_band

    Returns:
        bool: True if there's at least one alive ally to the left
    """
    acting_minion = context.get('acting_minion')
    if not acting_minion:
        return False

    ally_band = context.get('ally_band', [])
    acting_pos = acting_minion.get('position', 999)

    # Find alive allies to the left
    left_allies = [
        m for m in ally_band
        if m.get('health', 0) > 0
        and m != acting_minion  # Exclude self
        and m.get('position', 999) < acting_pos  # Must be to the left
    ]

    has_left = len(left_allies) > 0
    logger.debug(f"[CONDITIONAL] {acting_minion.get('name')} checking for left allies: {has_left} ({len(left_allies)} found)")

    return has_left


def evaluate_compound_condition(condition: Dict, context: Dict) -> bool:
    """Evaluate a compound condition with multiple checks"""
    checks = condition.get('checks', [])
    operator = condition.get('operator', 'AND')

    if not checks:
        return True

    results = []
    for check in checks:
        results.append(evaluate_simple_condition(check, context))

    if operator == 'AND':
        return all(results)
    elif operator == 'OR':
        return any(results)
    elif operator == 'NOT':
        # NOT applies to first check only
        return not results[0] if results else False
    else:
        logger.debug(f"[CONDITIONAL] Unknown operator: {operator}")
        return False


def resolve_condition_target(target_spec: str, context: Dict) -> Optional[Dict]:
    """
    Resolve a target specification to a minion for condition checking

    UPDATED: For trigger_dying, returns None if minion not available,
    but metadata will be used by condition checks instead
    UPDATED: Added target_minion support for effect filtering
    """
    if target_spec == 'self':
        return context.get('acting_minion')

    elif target_spec == 'trigger_source':
        return context.get('trigger_context_source')

    elif target_spec == 'trigger_target':
        return context.get('trigger_context_target')

    elif target_spec == 'defender':
        return context.get('defender')

    elif target_spec == 'attacker':
        return context.get('attacker')

    elif target_spec == 'trigger_attacker':
        return context.get('trigger_context_attacker')

    elif target_spec == 'trigger_defender':
        return context.get('trigger_context_defender')

    # NEW: Handle summon-specific trigger contexts
    elif target_spec == 'trigger_summoned':
        # FIXED: Use the actual field name from registry
        return context.get('summoned_minion')

    elif target_spec == 'trigger_summoner':
        # FIXED: Use the actual field name from registry
        return context.get('summoner')

    elif target_spec == 'trigger_dying':
        # FIXED: Use the actual field name from registry
        return context.get('dying_minion')

    # NEW: Support for target_minion (used in effect filtering)
    elif target_spec == 'target_minion':
        return context.get('target_minion')

    elif target_spec == 'all_allies':
        # Return None - will be handled specially in has_minion_named
        return None

    elif target_spec == 'all_enemies':
        # Return None - will be handled specially in has_minion_named
        return None

    else:
        logger.debug(f"[CONDITIONAL] Unknown target spec for condition: {target_spec}")
        return None


def is_enemy_minion(minion: Dict, context: Dict) -> bool:
    """Check if a minion is an enemy relative to the acting minion"""
    acting_minion = context.get('acting_minion')
    if not acting_minion:
        return False

    registry = context.get('combat_registry')
    if not registry:
        return False

    acting_band = registry.get_minion_band_type(acting_minion)
    target_band = registry.get_minion_band_type(minion)

    return acting_band != target_band


def is_ally_minion(minion: Dict, context: Dict) -> bool:
    """
    Check if a minion is an ally relative to the acting minion

    UPDATED: Now supports checking ally status via metadata for minions
    no longer in the band (e.g., dead minions in on_any_death triggers)

    CRITICAL: Uses band_type ('player' or 'enemy') for comparison, NOT band_id.
    band_id is a unique identifier per minion, so comparing band_ids would always fail.
    band_type indicates which side of combat the minion is on.
    """
    acting_minion = context.get('acting_minion')
    if not acting_minion:
        return False

    registry = context.get('combat_registry')
    if not registry:
        return False

    # Get acting minion's band type
    acting_band_type = registry.get_minion_band_type(acting_minion)
    if not acting_band_type:
        return False

    # CRITICAL: Check if we're dealing with metadata instead of a real minion
    # This happens when checking properties of dead minions in on_any_death triggers
    if minion is None:
        # Try to use metadata if available
        metadata = context.get('trigger_dying_metadata')
        if metadata:
            # Compare band_type (player/enemy) for ally status
            dying_band_type = metadata.get('band_type')

            if dying_band_type:
                is_ally = acting_band_type == dying_band_type
                logger.debug(f"[CONDITIONAL] Ally check via metadata: acting_band={acting_band_type}, dying_band={dying_band_type}, is_ally={is_ally}")
                return is_ally

        return False

    # Normal path: use registry for alive minions
    target_band_type = registry.get_minion_band_type(minion)

    # CRITICAL FIX: If registry lookup fails (minion removed from band), fall back to metadata
    if not target_band_type:
        # Try to use metadata as fallback for removed minions
        metadata = context.get('trigger_dying_metadata')
        if metadata and metadata.get('_combat_id') == minion.get('_combat_id'):
            # This is the dying minion - use its metadata
            dying_band_type = metadata.get('band_type')
            if dying_band_type:
                is_ally = acting_band_type == dying_band_type
                logger.debug(f"[CONDITIONAL] Ally check via metadata fallback: acting_band={acting_band_type}, dying_band={dying_band_type}, is_ally={is_ally}")
                return is_ally

        # No metadata available or doesn't match - fail the check
        logger.debug(f"[CONDITIONAL] Registry lookup failed and no metadata available for minion {minion.get('name')}")
        return False

    return acting_band_type == target_band_type


def check_position(minion: Dict, position: str, context: Dict) -> bool:
    """Check if a minion is in a specific position"""
    registry = context.get('combat_registry')
    if not registry:
        return False

    band_type = registry.get_minion_band_type(minion)
    if not band_type:
        return False

    band_minions = registry.get_band_minions(band_type, alive_only=True)

    if not band_minions:
        return False

    minion_pos = minion.get('position', -1)

    if position == 'leftmost':
        # Find the leftmost alive minion
        leftmost_pos = min(m.get('position', 999) for m in band_minions)
        return minion_pos == leftmost_pos

    elif position == 'rightmost':
        # Find the rightmost alive minion
        rightmost_pos = max(m.get('position', -1) for m in band_minions)
        return minion_pos == rightmost_pos

    elif position == 'middle':
        # Check if in middle positions (not edge)
        leftmost_pos = min(m.get('position', 999) for m in band_minions)
        rightmost_pos = max(m.get('position', -1) for m in band_minions)
        return minion_pos > leftmost_pos and minion_pos < rightmost_pos

    else:
        logger.debug(f"[CONDITIONAL] Unknown position type: {position}")
        return False


def describe_condition(condition: Dict) -> str:
    """Generate a human-readable description of a condition"""
    if not condition:
        return "no condition"

    check_type = condition.get('check_type', 'simple')

    if check_type == 'simple':
        condition_type = condition.get('type', 'unknown')
        target = condition.get('target', 'self')

        if condition_type == 'has_left_ally':
            return "has ally to the left"
        elif condition_type == 'has_minion_named':
            minion_name = condition.get('minion_name', 'unknown')
            return f"has friendly {minion_name}"
        elif condition_type == 'has_minion_with_keyword':
            keyword = condition.get('keyword', 'unknown')
            return f"has friendly minion with {keyword}"
        elif condition_type == 'is_enemy':
            return f"{target} is enemy"
        elif condition_type == 'is_ally':
            return f"{target} is ally"
        elif condition_type == 'is_name':
            return f"{target} is {condition.get('minion_name', 'unknown')}"
        elif condition_type == 'not_name':
            return f"{target} is not {condition.get('minion_name', 'unknown')}"
        elif condition_type == 'not_self':
            return f"{target} is not self"
        elif condition_type == 'not_type':
            return f"{target} is not {condition.get('minion_type', 'unknown')}"
        elif condition_type == 'has_keyword':
            return f"{target} has {condition.get('keyword', 'unknown')}"
        elif condition_type == 'not_has_keyword':
            return f"{target} doesn't have {condition.get('keyword', 'unknown')}"
        elif condition_type == 'is_position':
            return f"{target} is {condition.get('position', 'unknown')}"
        elif condition_type == 'health_above':
            return f"{target} health > {condition.get('value', 0)}"
        elif condition_type == 'is_tier':
            return f"{target} is tier {condition.get('tier', 1)}"
        else:
            return f"{condition_type} on {target}"

    elif check_type == 'compound':
        checks = condition.get('checks', [])
        operator = condition.get('operator', 'AND')
        descriptions = [describe_condition({'type': c.get('type'), 'target': c.get('target', 'self'),
                                          'minion_name': c.get('minion_name'), 'keyword': c.get('keyword')})
                       for c in checks]
        return f" {operator} ".join(descriptions)

    return "complex condition"


def apply_golden_doubling_to_effect(effect_data: Dict, golden_minion: Dict) -> Dict:
    """
    Apply golden doubling to numeric values in an effect

    FIXED: stat_ratio should NOT be doubled for destroy_minion effects
    FIXED: Prevent double-doubling in conditional effects
    """
    if not golden_minion.get('golden', False):
        return effect_data

    import copy
    modified = copy.deepcopy(effect_data)

    # Handle lists of effects (NEW)
    if isinstance(modified, list):
        return [apply_golden_doubling_to_effect(effect, golden_minion) for effect in modified]

    if not isinstance(modified, dict):
        return effect_data

    # CRITICAL FIX: Check for destroy_minion FIRST before any processing
    effect_type = modified.get('type')
    if effect_type == 'destroy_minion':
        logger.debug(f"[CONDITIONAL GOLDEN FIX] *** DESTROY_MINION DETECTED *** - stat_ratio should NOT be doubled")
        logger.debug(f"[CONDITIONAL GOLDEN FIX] Original stat_ratio: {effect_data.get('stat_ratio', 'NOT_SET')}")
        logger.debug(f"[CONDITIONAL GOLDEN FIX] Golden minions save same percentage but summon more minions")
        return effect_data  # Return completely unchanged - stat_ratio stays as-is

    # Apply standard golden doubling based on effect type
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

    elif effect_type in ['buff_stats', 'debuff_stats', 'buff_stats_tribe']:
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

    elif effect_type == 'permanent_stat_gain':
        if 'health' in modified:
            modified['health'] *= 2
        if 'attack' in modified:
            modified['attack'] *= 2
        if 'max_stacks' in modified and modified['max_stacks'] < 999:
            modified['max_stacks'] *= 2

    elif effect_type == 'modify_fatigue':
        if 'amount' in modified:
            modified['amount'] *= 2

    elif effect_type == 'damage_self':
        if 'amount' in modified:
            modified['amount'] *= 2

    elif effect_type == 'move_minion':
        if 'distance' in modified:
            modified['distance'] *= 2

    elif effect_type == 'destroy_and_transform':
        if 'summon_count' in modified:
            modified['summon_count'] *= 2

    elif effect_type == 'attack_target':
        # Attack_target doesn't have numeric values to double
        # The attack itself uses the minion's attack value which is already doubled
        pass

    elif effect_type == 'apply_stun':
        if 'stun_amount' in modified:
            modified['stun_amount'] *= 2

    elif effect_type == 'transfer_stun':
        # Transfer stun doesn't have doubling - it transfers what exists
        pass

    elif effect_type == 'modify_gold':
        if 'amount' in modified:
            modified['amount'] *= 2

    elif effect_type == 'scaling_damage':
        # Scaling damage doubling is handled in the effect itself
        pass

    elif effect_type == 'trigger_death_toll':
        # Trigger death toll doesn't double - it triggers existing effects
        pass

    return modified