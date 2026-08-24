"""
Damage Effects - All damage and healing related effects

This module contains implementations for damage dealing, healing,
and related combat effects.

UPDATED: Now routes all damage through centralized damage_handler
UPDATED: Fixed log message generation to properly handle all trigger sources
including on_any_cast, on_any_death, and other reactive triggers.
UPDATED: Added nobility keyword support - nobility minions can only take damage
from direct combat (attacks/counters), not from spell/effect damage.
UPDATED: Added target_filters support for dynamic filtering using conditional system.
"""

import logging

logger = logging.getLogger(__name__)

from typing import Dict, List, Tuple, Optional
from game_random import game_random, SelectionType
from keywords import resolve_target, has_nobility
from game_engine.damage_handler import apply_damage, DamageType


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


def deal_damage(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Deal direct damage to target(s)

    UPDATED: Now routes through damage_handler for centralized damage processing
    UPDATED: Added convenience parameters that auto-convert to filters

    Args:
        effect_data: Effect configuration with target, amount, target_count, exclude_type, require_keyword
        context: Combat context with bands, registry, etc.

    Returns:
        Tuple of (success, logs, changes)
    """
    target_spec = effect_data.get('target', 'defender')
    amount = effect_data.get('amount', 1)
    target_count = effect_data.get('target_count', 1)
    acting_minion = context.get('acting_minion', context.get('attacker'))

    # NEW: Auto-convert convenience parameters to filters (for multi-target damage)
    target_filters = None
    if target_count > 1:
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
        if convenience_filters:
            target_filters = convenience_filters

    targets_hit = []
    nobility_blocked = []

    # Handle multi-target damage
    if target_count > 1:
        # Get all potential targets
        success, all_targets, error = resolve_target(target_spec, context, acting_minion)

        if not success or not all_targets:
            return False, [f"🎯 No targets for multi-damage: {error}"], {}

        # Ensure all_targets is a list
        if not isinstance(all_targets, list):
            all_targets = [all_targets]

        # NEW: Apply filters if present
        if target_filters:
            logger.debug(f"[DEAL DAMAGE] Applying {len(target_filters)} filters to {len(all_targets)} candidates")
            all_targets = _apply_target_filters(all_targets, target_filters, context)

            if not all_targets:
                is_golden = acting_minion.get('golden', False)
                golden_prefix = "💎 Golden " if is_golden else ""
                return True, [f"✨ {golden_prefix}{acting_minion['name']}'s damage found no valid targets after filtering"], {}

        # Select targets using GameRandom
        actual_count = min(target_count, len(all_targets))

        random_context = {
            'effect_type': 'deal_damage',
            'damage_amount': amount,
            'acting_minion': acting_minion.get('name', 'Unknown'),
            'acting_minion_band_id': acting_minion.get('band_id'),
            'acting_minion_combat_id': acting_minion.get('_combat_id')
        }

        actual_targets = game_random.select_multiple(
            SelectionType.DAMAGE_TARGET,
            all_targets,
            actual_count,
            context=random_context,
            description=f"Select {actual_count} targets for {amount} damage each",
            unique=True
        )

        # Deal damage to each target through damage handler
        for target in actual_targets:
            damage_result = apply_damage(
                target=target,
                amount=amount,
                damage_type=DamageType.ABILITY,
                source_minion=acting_minion,
                context=context
            )

            if damage_result.blocked_by_nobility:
                nobility_blocked.append(target)
            else:
                targets_hit.append(target)

            # Track in effect context if available
            effect_context = context.get('effect_context')
            if effect_context:
                effect_context.target_minions.append(target)
                effect_context.damage_dealt += damage_result.damage_applied

    else:
        # Single target damage
        success, target, error = resolve_target(target_spec, context, acting_minion)

        if not success:
            return False, [f"🎯 Targeting failed: {error}"], {}

        # Apply damage through damage handler
        damage_result = apply_damage(
            target=target,
            amount=amount,
            damage_type=DamageType.ABILITY,
            source_minion=acting_minion,
            context=context
        )

        if damage_result.blocked_by_nobility:
            nobility_blocked.append(target)
        else:
            targets_hit.append(target)

        # Track in effect context
        effect_context = context.get('effect_context')
        if effect_context:
            effect_context.target_minions.append(target)
            effect_context.damage_dealt += damage_result.damage_applied

    # Generate logs
    logs = []

    # Log successful damage
    if targets_hit:
        log_entry = _generate_damage_log(acting_minion, targets_hit, amount, context)
        logs.append(log_entry)

    # Add nobility block logs from damage handler
    for noble in nobility_blocked:
        damage_result = apply_damage(noble, amount, DamageType.ABILITY, acting_minion, context)
        logs.extend(damage_result.logs)

    # Return success if at least one target was damaged
    if not targets_hit and not nobility_blocked:
        return False, ["🎯 No valid targets for damage"], {}

    return True, logs, {
        'damage_dealt': amount * len(targets_hit),
        'targets': targets_hit,
        'nobility_blocked': len(nobility_blocked)
    }


def heal(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Heal a target

    Args:
        effect_data: Effect configuration with target and amount
        context: Combat context

    Returns:
        Tuple of (success, logs, changes)
    """
    target_spec = effect_data.get('target', 'self')
    amount = effect_data.get('amount', 1)
    acting_minion = context.get('acting_minion', context.get('attacker'))

    # Resolve target
    success, target, error = resolve_target(target_spec, context, acting_minion)

    if not success:
        return False, [f"🎯 Targeting failed: {error}"], {}

    # Apply healing
    target['health'] += amount

    # Track in effect context
    effect_context = context.get('effect_context')
    if effect_context:
        effect_context.target_minions.append(target)
        effect_context.healing_done += amount

    # Generate log
    log_entry = _generate_heal_log(acting_minion, target, amount, context)

    return True, [log_entry], {
        'healing_done': amount,
        'targets': [target]
    }


def heal_self(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Heal self

    Args:
        effect_data: Effect configuration with amount
        context: Combat context

    Returns:
        Tuple of (success, logs, changes)
    """
    amount = effect_data.get('amount', 1)
    acting_minion = context.get('acting_minion', context.get('attacker'))

    # Apply healing to self
    acting_minion['health'] += amount

    # Track in effect context
    effect_context = context.get('effect_context')
    if effect_context:
        effect_context.target_minions.append(acting_minion)
        effect_context.healing_done += amount

    # Generate log
    trigger_source = context.get('trigger_source', 'assault')
    is_golden = acting_minion.get('golden', False)
    golden_prefix = "💎 Golden " if is_golden else ""

    if trigger_source == 'cast':
        log_entry = f"🔮 Cast: {golden_prefix}{acting_minion['name']} heals self for {amount}"
    elif trigger_source == 'rage':
        log_entry = f"😡 Rage: {golden_prefix}{acting_minion['name']} heals self for {amount}"
    else:
        log_entry = f"⚡ Assault: {golden_prefix}{acting_minion['name']} heals self for {amount}"

    return True, [log_entry], {
        'healing_done': amount,
        'targets': [acting_minion]
    }


def damage_self(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Damage self

    UPDATED: Now routes through damage_handler for centralized damage processing

    Args:
        effect_data: Effect configuration with amount
        context: Combat context

    Returns:
        Tuple of (success, logs, changes)
    """
    amount = effect_data.get('amount', 1)
    acting_minion = context.get('acting_minion')

    # Apply damage through damage handler
    damage_result = apply_damage(
        target=acting_minion,
        amount=amount,
        damage_type=DamageType.EFFECT,
        source_minion=acting_minion,  # Self-damage
        context=context
    )

    # Check if blocked by nobility
    if damage_result.blocked_by_nobility:
        return True, damage_result.logs, {
            'damage_dealt': 0,
            'nobility_blocked': True
        }

    # Track in effect context
    effect_context = context.get('effect_context')
    if effect_context:
        effect_context.target_minions.append(acting_minion)
        effect_context.damage_dealt += damage_result.damage_applied

    # Generate log
    trigger_source = context.get('trigger_source', 'on_any_cast')
    is_golden = acting_minion.get('golden', False)
    golden_prefix = "💎 Golden " if is_golden else ""

    if trigger_source == 'on_any_cast':
        log_entry = f"📖 Spell Watch: {golden_prefix}{acting_minion['name']} takes {amount} damage from spell cast"
    else:
        log_entry = f"💥 {golden_prefix}{acting_minion['name']} takes {amount} self-damage"

    return True, [log_entry], {
        'damage_dealt': damage_result.damage_applied,
        'targets': [acting_minion]
    }


def deal_aoe_damage(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Deal AoE damage to multiple targets

    UPDATED: Now routes through damage_handler for centralized damage processing
    UPDATED: Added target_filters support for dynamic filtering
    UPDATED: Added convenience parameters (exclude_type, require_keyword) that auto-convert to filters

    Args:
        effect_data: Effect configuration with target, amount, max_targets, target_filters, exclude_type, require_keyword
        context: Combat context

    Returns:
        Tuple of (success, logs, changes)
    """
    target_spec = effect_data.get('target', 'all_enemies')
    amount = effect_data.get('amount', 1)
    max_targets = effect_data.get('max_targets', 999)
    target_filters = effect_data.get('target_filters')  # NEW: Optional filtering
    acting_minion = context.get('acting_minion', context.get('attacker'))

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

    # Combine explicit filters with convenience filters
    if convenience_filters:
        if target_filters:
            target_filters = target_filters + convenience_filters
        else:
            target_filters = convenience_filters

    # Resolve targets
    success, targets, error = resolve_target(target_spec, context, acting_minion)

    if not success:
        return False, [f"🎯 AoE targeting failed: {error}"], {}

    if not targets:
        return False, ["🎯 No valid targets for AoE damage"], {}

    # Ensure targets is a list
    if not isinstance(targets, list):
        targets = [targets]

    # NEW: Apply filters if provided
    if target_filters:
        logger.debug(f"[AOE DAMAGE] Applying {len(target_filters)} filters to {len(targets)} candidates")
        targets = _apply_target_filters(targets, target_filters, context)

        if not targets:
            is_golden = acting_minion.get('golden', False)
            golden_prefix = "💎 Golden " if is_golden else ""
            return True, [f"✨ {golden_prefix}{acting_minion['name']}'s AoE found no valid targets after filtering"], {}

    # Limit number of targets if needed
    if len(targets) > max_targets:
        random_context = {
            'effect_type': 'deal_aoe_damage',
            'damage_amount': amount,
            'acting_minion': acting_minion.get('name', 'Unknown'),
            'max_targets': max_targets
        }

        targets = game_random.select_multiple(
            SelectionType.AOE_TARGETS,
            targets,
            max_targets,
            context=random_context,
            description=f"Select {max_targets} targets for AoE damage",
            unique=True
        )

    # Apply damage to all targets through damage handler
    damaged_names = []
    nobility_blocked = []

    for target in targets:
        damage_result = apply_damage(
            target=target,
            amount=amount,
            damage_type=DamageType.AOE,
            source_minion=acting_minion,
            context=context
        )

        if damage_result.blocked_by_nobility:
            nobility_blocked.append(target)
        else:
            damaged_names.append(target['name'])

    # Track in effect context
    effect_context = context.get('effect_context')
    if effect_context:
        # Only add damaged targets to context
        damaged_targets = [t for t in targets if t['name'] in damaged_names]
        effect_context.target_minions.extend(damaged_targets)
        effect_context.damage_dealt += amount * len(damaged_names)

    # Generate logs
    logs = []
    trigger_source = context.get('trigger_source', 'assault')
    is_golden = acting_minion.get('golden', False)
    golden_prefix = "💎 Golden " if is_golden else ""

    # Log successful damage
    if damaged_names:
        if trigger_source == 'cast':
            log_entry = f"🔮 Cast: {golden_prefix}{acting_minion['name']} deals {amount} AoE damage to {', '.join(damaged_names)}"
        elif trigger_source == 'death_toll':
            dying_minion = context.get('dying_minion', acting_minion)
            log_entry = f"💀 Death Toll: {golden_prefix}{dying_minion['name']}'s death deals {amount} AoE damage to {', '.join(damaged_names)}"
        elif trigger_source == 'rage':
            log_entry = f"😡 Rage: {golden_prefix}{acting_minion['name']} deals {amount} AoE damage to {', '.join(damaged_names)}"
        else:
            log_entry = f"⚡ Assault: {golden_prefix}{acting_minion['name']} deals {amount} AoE damage to {', '.join(damaged_names)}"
        logs.append(log_entry)

    # Add nobility block logs from damage handler
    for noble in nobility_blocked:
        damage_result = apply_damage(noble, amount, DamageType.AOE, acting_minion, context)
        logs.extend(damage_result.logs)

    # Return success if at least one target took damage
    if not damaged_names and not nobility_blocked:
        return False, ["🎯 No valid targets for AoE damage"], {}

    # Collect target IDs for bundle detection
    damaged_targets = [t for t in targets if t['name'] in damaged_names]
    target_ids = [t.get('_combat_id') for t in damaged_targets if t.get('_combat_id')]

    return True, logs, {
        'damage_dealt': amount * len(damaged_names),
        'targets': damaged_targets,
        'target_ids': target_ids,
        'nobility_blocked': len(nobility_blocked)
    }


def _generate_damage_log(acting_minion: Dict, targets: List[Dict], amount: int, context: Dict) -> str:
    """Generate appropriate damage log message"""
    trigger_source = context.get('trigger_source', 'assault')
    is_golden = acting_minion.get('golden', False)
    golden_prefix = "💎 Golden " if is_golden else ""

    if len(targets) > 1:
        targets_text = ', '.join(t['name'] for t in targets)
        damage_text = f"deals {amount} damage to {targets_text}"
    else:
        damage_text = f"deals {amount} damage to {targets[0]['name']}"

    # Handle all trigger sources with appropriate icons and prefixes
    if trigger_source == 'cast':
        return f"🔮 Cast: {golden_prefix}{acting_minion['name']} {damage_text}"
    elif trigger_source == 'death_toll':
        dying_minion = context.get('dying_minion', acting_minion)
        return f"💀 Death Toll: {golden_prefix}{dying_minion['name']}'s death {damage_text}"
    elif trigger_source == 'rage':
        return f"😡 Rage: {golden_prefix}{acting_minion['name']} {damage_text}"
    elif trigger_source == 'on_any_death':
        return f"👁️ Death Watch: {golden_prefix}{acting_minion['name']} {damage_text}"
    elif trigger_source == 'on_any_cast':
        return f"📖 Spell Watch: {golden_prefix}{acting_minion['name']} {damage_text}"
    elif trigger_source == 'assault':
        return f"⚡ Assault: {golden_prefix}{acting_minion['name']} {damage_text}"
    else:
        # Generic effect if trigger source is unknown
        return f"✨ Effect: {golden_prefix}{acting_minion['name']} {damage_text}"


def _generate_heal_log(acting_minion: Dict, target: Dict, amount: int, context: Dict) -> str:
    """Generate appropriate healing log message"""
    trigger_source = context.get('trigger_source', 'assault')
    is_golden = acting_minion.get('golden', False)
    golden_prefix = "💎 Golden " if is_golden else ""

    # Handle all trigger sources with appropriate icons and prefixes
    if trigger_source == 'cast':
        return f"🔮 Cast: {golden_prefix}{acting_minion['name']} heals {target['name']} for {amount}"
    elif trigger_source == 'death_toll':
        dying_minion = context.get('dying_minion', acting_minion)
        return f"💀 Death Toll: {golden_prefix}{dying_minion['name']}'s death heals {target['name']} for {amount}"
    elif trigger_source == 'rage':
        return f"😡 Rage: {golden_prefix}{acting_minion['name']} heals {target['name']} for {amount}"
    elif trigger_source == 'on_any_death':
        return f"👁️ Death Watch: {golden_prefix}{acting_minion['name']} heals {target['name']} for {amount}"
    elif trigger_source == 'on_any_cast':
        return f"📖 Spell Watch: {golden_prefix}{acting_minion['name']} heals {target['name']} for {amount}"
    elif trigger_source == 'assault':
        return f"⚡ Assault: {golden_prefix}{acting_minion['name']} heals {target['name']} for {amount}"
    else:
        # Generic effect if trigger source is unknown
        return f"✨ Effect: {golden_prefix}{acting_minion['name']} heals {target['name']} for {amount}"