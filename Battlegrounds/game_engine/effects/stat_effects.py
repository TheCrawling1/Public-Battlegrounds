"""
Stat Effects - All stat modification related effects

This module contains implementations for buffing, debuffing,
and permanent stat modifications.

UPDATED: Added target_filters support for dynamic filtering using conditional system.
"""

import logging

logger = logging.getLogger(__name__)

from typing import Dict, List, Tuple, Optional
from game_random import game_random, SelectionType
from keywords import resolve_target
from minions import add_permanent_stats, get_permanent_stack_count


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


def buff_stats(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Buff a target's stats

    UPDATED: Added target_filters support for dynamic filtering
    UPDATED: Added convenience parameters that auto-convert to filters
    UPDATED: Added multiply_by_context for dynamic stat multiplication (Frog Prince)

    Args:
        effect_data: Effect configuration with target, health, attack, target_filters, exclude_type, require_keyword, multiply_by_context
        context: Combat context

    Returns:
        Tuple of (success, logs, changes)
    """
    target_spec = effect_data.get('target', 'self')
    health_buff = effect_data.get('health', 0)
    attack_buff = effect_data.get('attack', 0)
    target_filters = effect_data.get('target_filters')  # NEW: Optional filtering
    acting_minion = context.get('acting_minion', context.get('attacker'))

    # NEW: Support for dynamic multiplication based on context values (Frog Prince)
    multiply_by_context = effect_data.get('multiply_by_context')
    if multiply_by_context:
        multiplier = context.get(multiply_by_context, 1)
        health_buff *= multiplier
        attack_buff *= multiplier
        logger.debug(f"[BUFF STATS] Multiplying by context['{multiply_by_context}'] = {multiplier}: attack={attack_buff}, health={health_buff}")

    # NEW: Auto-convert convenience parameters to filters
    convenience_filters = []
    if 'exclude_type' in effect_data:
        convenience_filters.append({
            'type': 'not_type',
            'target': 'target_minion',
            'minion_type': effect_data['exclude_type']
        })
    if 'require_keyword' in effect_data:
        convenience_filters.append({
            'type': 'has_keyword',
            'target': 'target_minion',
            'keyword': effect_data['require_keyword']
        })
    if effect_data.get('exclude_self'):
        convenience_filters.append({
            'type': 'not_self',
            'target': 'target_minion'
        })

    # Combine explicit filters with convenience filters
    if convenience_filters:
        if target_filters:
            target_filters = target_filters + convenience_filters
        else:
            target_filters = convenience_filters

    # Resolve target
    success, target, error = resolve_target(target_spec, context, acting_minion)

    if not success:
        return False, [f"🎯 Targeting failed: {error}"], {}

    # Handle multiple targets (e.g., all_allies)
    if isinstance(target, list):
        targets = target

        # NEW: Apply filters if provided
        if target_filters:
            logger.debug(f"[BUFF STATS] Applying {len(target_filters)} filters to {len(targets)} candidates")
            targets = _apply_target_filters(targets, target_filters, context)

            if not targets:
                is_golden = acting_minion.get('golden', False)
                golden_prefix = "💎 Golden " if is_golden else ""
                return True, [f"✨ {golden_prefix}{acting_minion['name']} found no valid targets for buff after filtering"], {}

        # Apply buffs to all targets
        buffed_names = []
        for minion in targets:
            minion['health'] += health_buff
            minion['attack'] += attack_buff
            buffed_names.append(minion['name'])

        # Track in effect context
        effect_context = context.get('effect_context')
        if effect_context:
            effect_context.target_minions.extend(targets)
            effect_context.stats_changed['health'] = health_buff
            effect_context.stats_changed['attack'] = attack_buff

        # Generate log
        log_parts = []
        if health_buff > 0:
            log_parts.append(f"+{health_buff} health")
        if attack_buff > 0:
            log_parts.append(f"+{attack_buff} attack")

        trigger_source = context.get('trigger_source', 'assault')
        is_golden = acting_minion.get('golden', False)
        golden_prefix = "💎 Golden " if is_golden else ""

        if trigger_source == 'cast':
            log_entry = f"🔮 Cast: {golden_prefix}{acting_minion['name']} gives all allies {', '.join(log_parts)}"
        else:
            log_entry = f"✨ {golden_prefix}{acting_minion['name']} gives {', '.join(buffed_names)} {', '.join(log_parts)}"

        return True, [log_entry], {
            'stats_buffed': {name: log_parts for name in buffed_names},
            'targets': targets,
            'attack_buff': attack_buff,
            'health_buff': health_buff
        }

    # Single target
    else:
        # Apply buffs
        target['health'] += health_buff
        target['attack'] += attack_buff

        # Track in effect context
        effect_context = context.get('effect_context')
        if effect_context:
            effect_context.target_minions.append(target)
            effect_context.stats_changed['health'] = health_buff
            effect_context.stats_changed['attack'] = attack_buff

        # Generate log
        log_parts = []
        if health_buff > 0:
            log_parts.append(f"+{health_buff} health")
        if attack_buff > 0:
            log_parts.append(f"+{attack_buff} attack")

        trigger_source = context.get('trigger_source', 'assault')
        is_golden = acting_minion.get('golden', False)
        golden_prefix = "💎 Golden " if is_golden else ""

        if trigger_source == 'cast':
            log_entry = f"🔮 Cast: {golden_prefix}{acting_minion['name']} buffs {target['name']} ({', '.join(log_parts)})"
        elif trigger_source == 'death_toll':
            dying_minion = context.get('dying_minion', acting_minion)
            log_entry = f"💀 Death Toll: {golden_prefix}{dying_minion['name']}'s death buffs {target['name']} ({', '.join(log_parts)})"
        elif trigger_source == 'rage':
            # Check if buffing self or another minion
            if target.get('_combat_id') == acting_minion.get('_combat_id'):
                log_entry = f"😡 Rage: {golden_prefix}{acting_minion['name']} gains {', '.join(log_parts)}"
            else:
                log_entry = f"😡 Rage: {golden_prefix}{acting_minion['name']} buffs {target['name']} ({', '.join(log_parts)})"
        elif trigger_source == 'calm':
            log_entry = f"🧘 Calm: {golden_prefix}{acting_minion['name']} gains {', '.join(log_parts)}"
        elif trigger_source == 'on_any_death':
            log_entry = f"👁️ Death Watch: {golden_prefix}{acting_minion['name']} gains {', '.join(log_parts)}"
        elif trigger_source == 'on_any_leap':
            # Check if buffing self or the leaping minion
            if target.get('_combat_id') == acting_minion.get('_combat_id'):
                log_entry = f"🦘 Leap Watch: {golden_prefix}{acting_minion['name']} gains {', '.join(log_parts)}"
            else:
                log_entry = f"🦘 Leap Watch: {golden_prefix}{acting_minion['name']} buffs {target['name']} ({', '.join(log_parts)})"
        else:
            log_entry = f"⚡ Assault: {golden_prefix}{acting_minion['name']} buffs {target['name']} ({', '.join(log_parts)})"

        return True, [log_entry], {
            'stats_buffed': {target['name']: log_parts},
            'targets': [target],
            'attack_buff': attack_buff,
            'health_buff': health_buff
        }


def buff_stats_tribe(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Buff all allies of a specific tribe

    Args:
        effect_data: Effect configuration with tribe, health, attack
        context: Combat context

    Returns:
        Tuple of (success, logs, changes)
    """
    tribe = effect_data.get('tribe', 'Unknown')
    health_buff = effect_data.get('health', 0)
    attack_buff = effect_data.get('attack', 0)
    acting_minion = context.get('acting_minion', context.get('attacker'))

    # Get ally band from context
    ally_band = context.get('ally_band', [])

    # Filter for alive allies of the specified tribe
    tribe_allies = [m for m in ally_band if m['health'] > 0 and m.get('type') == tribe]

    if not tribe_allies:
        return False, [f"No alive {tribe} allies to buff"], {}

    # Apply buffs to all tribe members
    buffed_names = []
    for minion in tribe_allies:
        minion['health'] += health_buff
        minion['attack'] += attack_buff
        buffed_names.append(minion['name'])

    # Track in effect context
    effect_context = context.get('effect_context')
    if effect_context:
        effect_context.target_minions.extend(tribe_allies)
        effect_context.stats_changed['health'] = health_buff
        effect_context.stats_changed['attack'] = attack_buff

    # Generate log
    log_parts = []
    if health_buff > 0:
        log_parts.append(f"+{health_buff} health")
    if attack_buff > 0:
        log_parts.append(f"+{attack_buff} attack")

    trigger_source = context.get('trigger_source', 'death_toll')
    is_golden = acting_minion.get('golden', False)
    golden_prefix = "💎 Golden " if is_golden else ""

    if trigger_source == 'death_toll':
        dying_minion = context.get('dying_minion', acting_minion)
        log_entry = f"💀 Death Toll: {golden_prefix}{dying_minion['name']}'s death buffs all {tribe} allies ({', '.join(log_parts)})"
    else:
        log_entry = f"✨ {golden_prefix}{acting_minion['name']} buffs all {tribe} allies ({', '.join(log_parts)})"

    return True, [log_entry], {
        'tribal_buffs': [f"{len(buffed_names)} {tribe} minions buffed"],
        'targets': tribe_allies,
        'attack_buff': attack_buff,
        'health_buff': health_buff
    }


def debuff_stats(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Debuff a target's stats

    Args:
        effect_data: Effect configuration with target, attack debuff
        context: Combat context

    Returns:
        Tuple of (success, logs, changes)
    """
    target_spec = effect_data.get('target', 'random_enemy')
    attack_debuff = effect_data.get('attack', 0)
    acting_minion = context.get('acting_minion', context.get('attacker'))

    # Resolve target
    success, target, error = resolve_target(target_spec, context, acting_minion)

    if not success:
        return False, [f"🎯 Targeting failed: {error}"], {}

    # Apply debuff (ensure it doesn't go below 0)
    target['attack'] = max(0, target['attack'] + attack_debuff)

    # Track in effect context
    effect_context = context.get('effect_context')
    if effect_context:
        effect_context.target_minions.append(target)
        effect_context.stats_changed['attack'] = attack_debuff

    # Generate log
    trigger_source = context.get('trigger_source', 'cast')
    is_golden = acting_minion.get('golden', False)
    golden_prefix = "💎 Golden " if is_golden else ""

    debuff_amount = abs(attack_debuff)

    if trigger_source == 'cast':
        log_entry = f"🔮 Cast: {golden_prefix}{acting_minion['name']} reduces {target['name']}'s attack by {debuff_amount}"
    elif trigger_source == 'assault':
        log_entry = f"⚡ Assault: {golden_prefix}{acting_minion['name']} reduces {target['name']}'s attack by {debuff_amount}"
    else:
        log_entry = f"⚡ {golden_prefix}{acting_minion['name']} reduces {target['name']}'s attack by {debuff_amount}"
        
    return True, [log_entry], {
        'debuffs_applied': [f"{target['name']}: -{debuff_amount} attack"],
        'targets': [target],
        'attack_debuff': attack_debuff,
        'health_debuff': 0
    }


def permanent_stat_gain(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Apply permanent stat gain with scope support
    
    Args:
        effect_data: Effect configuration with target, scope, health/attack gains
        context: Combat context
        
    Returns:
        Tuple of (success, logs, changes)
    """
    target_spec = effect_data.get('target', 'random_ally')
    health_gain = effect_data.get('health', 0)
    attack_gain = effect_data.get('attack', 0)
    max_stacks = effect_data.get('max_stacks', None)
    scope = effect_data.get('scope', 'both_qualified')
    
    acting_minion = context.get('acting_minion', context.get('dying_minion'))
    is_golden = acting_minion.get('golden', False)
    golden_prefix = "💎 Golden " if is_golden else ""
    
    # Handle band_only scope
    if scope == 'band_only':
        return _apply_band_only_permanent_stats(
            acting_minion, health_gain, attack_gain, max_stacks, context, golden_prefix
        )
        
    # Handle combat_only scope
    elif scope == 'combat_only':
        return _apply_combat_only_permanent_stats(
            target_spec, acting_minion, health_gain, attack_gain, max_stacks, context, golden_prefix
        )
        
    # Handle both scopes
    elif scope in ['both_qualified', 'both_unqualified']:
        # Apply to both combat and band minion
        # This would need implementation based on the original logic
        return _apply_both_permanent_stats(
            target_spec, acting_minion, health_gain, attack_gain, max_stacks, scope, context, golden_prefix
        )
        
    else:
        return False, [f"⚠️ Unknown permanent stat scope: {scope}"], {}


def _apply_band_only_permanent_stats(acting_minion: Dict, health_gain: int, attack_gain: int,
                                    max_stacks: Optional[int], context: Dict, 
                                    golden_prefix: str) -> Tuple[bool, List[str], Dict]:
    """Apply permanent stats to band minion only"""
    band_id = acting_minion.get('band_id')
    if not band_id:
        return False, [f"💀 Death Toll: {acting_minion['name']} has no band_id for band-only effect"], {}
        
    run = context.get('run')
    if not run:
        return False, [f"💀 Death Toll: No run context available for band-only effect"], {}
        
    # Get the current band and find the corresponding band minion
    current_band = run.get_band()
    band_minion = None
    for minion in current_band:
        if minion.get('band_id') == band_id:
            band_minion = minion
            break
            
    if not band_minion:
        return False, [f"💀 Death Toll: Could not find band minion with ID {band_id}"], {}
        
    # Create a unique source ID
    source_id = f"{acting_minion.get('name', 'unknown')}_permanent_gain"
    
    # Check if we can apply more stacks
    current_stacks = get_permanent_stack_count(band_minion, source_id)
    if max_stacks is not None and current_stacks >= max_stacks:
        return False, [f"💀 Death Toll: Band {band_minion['name']} already has max {max_stacks} permanent stats"], {}
        
    # Apply permanent stats
    applied = add_permanent_stats(band_minion, health_gain, attack_gain, source_id, max_stacks)
    
    if not applied:
        return False, ["❌ Failed to apply band-only permanent stats"], {}
        
    # Save the modified band
    run.set_band(current_band)
    
    # Generate log
    log_parts = []
    if health_gain > 0:
        log_parts.append(f"+{health_gain} permanent health")
    if attack_gain > 0:
        log_parts.append(f"+{attack_gain} permanent attack")
        
    new_stack_count = get_permanent_stack_count(band_minion, source_id)
    stack_info = f" ({new_stack_count}"
    if max_stacks is not None:
        stack_info += f"/{max_stacks}"
    stack_info += ")"
    
    trigger_source = context.get('trigger_source', 'effect')
    if trigger_source == 'death_toll':
        log_entry = f"💀 Death Toll: {golden_prefix}{acting_minion['name']}'s death grants band {band_minion['name']} {', '.join(log_parts)}{stack_info}"
    else:
        log_entry = f"⚡ {golden_prefix}{acting_minion['name']} grants band {band_minion['name']} {', '.join(log_parts)}{stack_info}"
        
    return True, [log_entry], {
        'band_only_stat_gain': [f"{band_minion['name']}: {log_parts}"],
        'targets': []
    }


def _apply_combat_only_permanent_stats(target_spec: str, acting_minion: Dict, health_gain: int,
                                      attack_gain: int, max_stacks: Optional[int], context: Dict,
                                      golden_prefix: str) -> Tuple[bool, List[str], Dict]:
    """Apply permanent stats to combat minion only"""
    # For death toll effects with random_ally, exclude the dying minion
    if context.get('trigger_source') == 'death_toll' and target_spec == 'random_ally':
        ally_band = context.get('ally_band', [])
        filtered_allies = [m for m in ally_band if m['health'] > 0 and m is not acting_minion]
        
        if not filtered_allies:
            return False, [f"💀 Death Toll: {golden_prefix}{acting_minion['name']}'s death finds no living allies"], {}
            
        # Use GameRandom for selection
        random_context = {
            'effect_type': 'permanent_stat_gain',
            'trigger_source': 'death_toll',
            'acting_minion': acting_minion.get('name', 'Unknown')
        }
        
        target = game_random.select_one(
            SelectionType.BUFF_TARGET,
            filtered_allies,
            context=random_context,
            description=f"Select random ally for permanent stats"
        )
    else:
        # Use normal targeting
        success, target, error = resolve_target(target_spec, context, acting_minion)
        
        if not success:
            return False, [f"🎯 Combat-only targeting failed: {error}"], {}
            
    # Create a unique source ID
    source_id = f"{acting_minion.get('name', 'unknown')}_permanent_gain"
    
    # Check if we can apply more stacks
    current_stacks = get_permanent_stack_count(target, source_id)
    if max_stacks is not None and current_stacks >= max_stacks:
        return False, [f"⚡ {golden_prefix}{acting_minion['name']} cannot grant more permanent stats (max {max_stacks})"], {}
        
    # Apply permanent stats
    applied = add_permanent_stats(target, health_gain, attack_gain, source_id, max_stacks)
    
    if not applied:
        return False, ["❌ Failed to apply combat-only permanent stats"], {}
        
    # Track in effect context
    effect_context = context.get('effect_context')
    if effect_context:
        effect_context.target_minions.append(target)
        effect_context.stats_changed['permanent_health'] = health_gain
        effect_context.stats_changed['permanent_attack'] = attack_gain
        
    # Generate log
    log_parts = []
    if health_gain > 0:
        log_parts.append(f"+{health_gain} permanent health")
    if attack_gain > 0:
        log_parts.append(f"+{attack_gain} permanent attack")
        
    new_stack_count = get_permanent_stack_count(target, source_id)
    stack_info = f" ({new_stack_count}"
    if max_stacks is not None:
        stack_info += f"/{max_stacks}"
    stack_info += ")"
    
    trigger_source = context.get('trigger_source', 'effect')
    if trigger_source == 'death_toll':
        log_entry = f"💀 Death Toll: {golden_prefix}{acting_minion['name']}'s death grants {target['name']} {', '.join(log_parts)}{stack_info} (combat only)"
    else:
        log_entry = f"⚡ {golden_prefix}{acting_minion['name']} grants {target['name']} {', '.join(log_parts)}{stack_info} (combat only)"
        
    return True, [log_entry], {
        'combat_only_stat_gain': [f"{target['name']}: {log_parts}"],
        'targets': [target]
    }


def _apply_both_permanent_stats(target_spec: str, acting_minion: Dict, health_gain: int,
                               attack_gain: int, max_stacks: Optional[int], scope: str,
                               context: Dict, golden_prefix: str) -> Tuple[bool, List[str], Dict]:
    """Apply permanent stats to both combat and band minion"""
    # This would implement the logic for applying to both combat and band minions
    # For brevity, returning a placeholder
    return False, ["Both scope permanent stats not fully implemented"], {}