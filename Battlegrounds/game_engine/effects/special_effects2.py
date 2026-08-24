"""
Special Effects 2 - Additional special combat effects

This module contains additional special effect implementations that
don't fit in the main special_effects.py file.

INCLUDES:
- grant_effect_to_minion: Dynamically grant combat effects to other minions

CREATED: Split from special_effects.py as effects modules were getting large
"""

import logging

logger = logging.getLogger(__name__)

from typing import Dict, List, Tuple, Optional
from keywords import resolve_target
from game_random import game_random, SelectionType


def grant_effect_to_minion(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Grant a combat effect to another minion dynamically

    This allows minions to spread or share their abilities with others.
    The granted effect becomes a permanent part of the target minion.

    Example usage (Possessed):
    {
        'type': 'grant_effect_to_minion',
        'target': 'random_ally',
        'exclude_name': 'Possessed',
        'effect_type': 'death_toll_effect',
        'effect_data': {
            'type': 'summon_minion',
            'minion_name': 'Possessed',
            'health': 1,
            'attack': 6
        }
    }

    Args:
        effect_data: Effect configuration with:
            - target: Target specification (e.g., 'random_ally')
            - exclude_name: Optional minion name to exclude from targeting
            - effect_type: Type of effect to grant (e.g., 'death_toll_effect')
            - effect_data: The actual effect definition to grant
        context: Combat context

    Returns:
        Tuple of (success, logs, changes)
    """
    target_spec = effect_data.get('target', 'random_ally')
    exclude_name = effect_data.get('exclude_name')
    effect_type = effect_data.get('effect_type')
    granted_effect = effect_data.get('effect_data')
    acting_minion = context.get('acting_minion', context.get('dying_minion'))

    if not effect_type or not granted_effect:
        return False, ["❌ No effect type or effect data to grant"], {}

    # Resolve target
    success, targets, error = resolve_target(target_spec, context, acting_minion)

    if not success:
        return False, [f"❌ Targeting failed: {error}"], {}

    # Ensure targets is a list
    if not isinstance(targets, list):
        targets = [targets]

    # Filter out excluded names if specified
    if exclude_name:
        original_count = len(targets)
        targets = [t for t in targets if t.get('name') != exclude_name]
        filtered_count = original_count - len(targets)
        if filtered_count > 0:
            logger.debug(f"[GRANT_EFFECT] Filtered out {filtered_count} {exclude_name} minion(s)")

    if not targets:
        is_golden = acting_minion.get('golden', False) if acting_minion else False
        golden_prefix = "💎 Golden " if is_golden else ""
        return False, [f"✨ {golden_prefix}{acting_minion['name'] if acting_minion else 'Unknown'} has no valid targets to grant effect to"], {}

    # Select one target using GameRandom
    random_context = {
        'effect_type': 'grant_effect_to_minion',
        'granting_minion': acting_minion.get('name', 'Unknown') if acting_minion else 'Unknown',
        'effect_being_granted': effect_type,
        'excluded_name': exclude_name
    }

    target = game_random.select_one(
        SelectionType.RANDOM_ALLY,
        targets,
        context=random_context,
        description=f"Select target for effect grant (excluding {exclude_name})"
    )

    # Apply golden doubling to the granted effect if granting minion is golden
    if acting_minion and acting_minion.get('golden', False):
        granted_effect = _apply_golden_doubling_to_granted_effect(granted_effect)
        logger.debug(f"[GRANT_EFFECT] Applied golden doubling to granted effect")

    # Map effect type to keyword
    keyword = _effect_type_to_keyword(effect_type)

    if not keyword:
        return False, [f"❌ Unknown effect type: {effect_type}"], {}

    # Add the keyword if not already present
    if 'keywords' not in target:
        target['keywords'] = []

    keyword_granted = False
    if keyword not in target['keywords']:
        target['keywords'].append(keyword)
        keyword_granted = True
        logger.debug(f"[GRANT_EFFECT] Added keyword '{keyword}' to {target['name']}")

    # Store the effect on the target minion
    # If they already have an effect of this type, add to array instead of replacing
    existing_effect = target.get(effect_type)

    if existing_effect:
        # Convert to array if not already
        if isinstance(existing_effect, list):
            existing_effect.append(granted_effect)
            logger.debug(f"[GRANT_EFFECT] Appended {effect_type} to {target['name']}'s existing array (now {len(existing_effect)} effects)")
        else:
            # Convert single effect to array with both effects
            target[effect_type] = [existing_effect, granted_effect]
            logger.debug(f"[GRANT_EFFECT] Converted {target['name']}'s {effect_type} to array with 2 effects")
    else:
        # No existing effect, store normally
        target[effect_type] = granted_effect
        logger.debug(f"[GRANT_EFFECT] Stored {effect_type} on {target['name']}")

    # Track in effect context
    effect_context = context.get('effect_context')
    if effect_context:
        effect_context.target_minions.append(target)
        effect_context.add_tag('effect_granted')
        effect_context.add_tag(f'granted_{keyword}')

    # Generate logs
    logs = []
    trigger_source = context.get('trigger_source', 'effect')
    is_golden = acting_minion.get('golden', False) if acting_minion else False
    golden_prefix = "💎 Golden " if is_golden else ""

    # Format the effect description
    effect_desc = _format_granted_effect_description(granted_effect, effect_type)

    if trigger_source == 'death_toll':
        dying_minion = context.get('dying_minion', acting_minion)
        logs.append(f"💀👻 Death Toll: {golden_prefix}{dying_minion['name'] if dying_minion else 'Unknown'} spreads its curse to {target['name']}!")
        logs.append(f"✨ {target['name']} gains {keyword.replace('_', ' ').title()}: {effect_desc}")
    else:
        logs.append(f"✨ Effect Grant: {golden_prefix}{acting_minion['name'] if acting_minion else 'Unknown'} grants {keyword.replace('_', ' ').title()} to {target['name']}!")
        logs.append(f"📜 {target['name']} now has: {effect_desc}")

    return True, logs, {
        'effect_granted': True,
        'keyword_granted': keyword_granted,
        'effect_type': effect_type,
        'targets': [target],
        'granted_effect': granted_effect
    }


def _effect_type_to_keyword(effect_type: str) -> Optional[str]:
    """
    Map an effect type to its corresponding keyword

    Args:
        effect_type: The effect type string (e.g., 'death_toll_effect')

    Returns:
        The corresponding keyword (e.g., 'death_toll') or None
    """
    effect_to_keyword_map = {
        'death_toll_effect': 'death_toll',
        'assault_effect': 'assault',
        'cast_effect': 'cast',
        'rage_effect': 'rage',
        'on_any_death_effect': 'on_any_death',
        'on_any_cast_effect': 'on_any_cast',
        'on_any_summon_effect': 'on_any_summon',
        'on_adjacent_transform_effect': 'on_adjacent_transform',
        'on_damage_effect': 'on_damage',
        'start_of_combat_effect': 'start_of_combat',
        'sacrifice_effect': 'sacrifice'
    }

    return effect_to_keyword_map.get(effect_type)


def _apply_golden_doubling_to_granted_effect(effect: Dict) -> Dict:
    """
    Apply golden doubling to numeric values in a granted effect

    Only doubles numeric values, not target specifications.
    Target specs like 'random_ally' stay as strings.
    Target counts like 'target_count: 1' would double to 2.

    Args:
        effect: The effect data to double

    Returns:
        Effect with doubled numeric values
    """
    import copy
    doubled = copy.deepcopy(effect)

    # Handle effect arrays
    if isinstance(doubled, list):
        return [_apply_golden_doubling_to_granted_effect(e) for e in doubled]

    effect_type = doubled.get('type')

    # Double numeric values based on effect type
    if effect_type in ['deal_damage', 'heal', 'heal_self', 'damage_self']:
        if 'amount' in doubled:
            doubled['amount'] *= 2
        if 'target_count' in doubled:
            doubled['target_count'] *= 2

    elif effect_type == 'deal_aoe_damage':
        if 'amount' in doubled:
            doubled['amount'] *= 2
        if 'max_targets' in doubled:
            doubled['max_targets'] *= 2

    elif effect_type in ['buff_stats', 'debuff_stats', 'buff_stats_tribe']:
        if 'health' in doubled:
            doubled['health'] *= 2
        if 'attack' in doubled:
            doubled['attack'] *= 2

    elif effect_type == 'summon_minion':
        if 'summon_count' in doubled:
            doubled['summon_count'] *= 2
        if 'health' in doubled:
            doubled['health'] *= 2
        if 'attack' in doubled:
            doubled['attack'] *= 2

    elif effect_type == 'permanent_stat_gain':
        if 'health' in doubled:
            doubled['health'] *= 2
        if 'attack' in doubled:
            doubled['attack'] *= 2
        if 'max_stacks' in doubled and doubled['max_stacks'] < 999:
            doubled['max_stacks'] *= 2

    elif effect_type == 'move_minion':
        if 'distance' in doubled:
            doubled['distance'] *= 2

    elif effect_type == 'modify_fatigue':
        if 'amount' in doubled:
            doubled['amount'] *= 2

    elif effect_type == 'destroy_and_transform':
        if 'summon_count' in doubled:
            doubled['summon_count'] *= 2

    elif effect_type == 'modify_gold':
        if 'amount' in doubled:
            doubled['amount'] *= 2

    elif effect_type == 'apply_stun':
        if 'stun_amount' in doubled:
            doubled['stun_amount'] *= 2

    elif effect_type == 'conditional':
        # Double condition numeric values but not then/else effects
        # The then/else effects are already part of the granted effect
        # and will be processed when they actually trigger
        if 'condition' in doubled:
            condition = doubled['condition']
            if 'value' in condition:
                condition['value'] *= 2
            # Handle compound conditions
            if 'checks' in condition:
                for check in condition['checks']:
                    if 'value' in check:
                        check['value'] *= 2

    return doubled


def _format_granted_effect_description(effect: Dict, effect_type: str) -> str:
    """
    Format a granted effect into a readable description

    Args:
        effect: The effect data
        effect_type: The type of effect being granted

    Returns:
        Human-readable description
    """
    if isinstance(effect, list):
        # Multiple effects
        return "complex ability"

    eff_type = effect.get('type')

    if eff_type == 'summon_minion':
        minion_name = effect.get('minion_name', 'Unknown')
        health = effect.get('health', 1)
        attack = effect.get('attack', 1)
        summon_count = effect.get('summon_count', 1)

        if summon_count > 1:
            return f"Summon {summon_count} {minion_name}s ({health}/{attack} each)"
        else:
            return f"Summon {minion_name} ({health}/{attack})"

    elif eff_type == 'deal_damage':
        amount = effect.get('amount', 1)
        target = effect.get('target', 'unknown')
        target_count = effect.get('target_count', 1)
        if target_count > 1:
            return f"Deal {amount} damage to {target_count} {target}s"
        return f"Deal {amount} damage to {target}"

    elif eff_type == 'deal_aoe_damage':
        amount = effect.get('amount', 1)
        max_targets = effect.get('max_targets', 999)
        if max_targets >= 999:
            return f"Deal {amount} AoE damage to all enemies"
        return f"Deal {amount} damage to up to {max_targets} enemies"

    elif eff_type == 'heal':
        amount = effect.get('amount', 1)
        target = effect.get('target', 'unknown')
        return f"Heal {target} for {amount}"

    elif eff_type == 'heal_self':
        amount = effect.get('amount', 1)
        return f"Heal self for {amount}"

    elif eff_type == 'buff_stats':
        attack = effect.get('attack', 0)
        health = effect.get('health', 0)
        target = effect.get('target', 'unknown')
        buff_text = []
        if attack > 0:
            buff_text.append(f"+{attack} attack")
        if health > 0:
            buff_text.append(f"+{health} health")
        return f"Give {target} {', '.join(buff_text)}"

    elif eff_type == 'buff_stats_tribe':
        attack = effect.get('attack', 0)
        health = effect.get('health', 0)
        tribe = effect.get('tribe', 'unknown')
        buff_text = []
        if attack > 0:
            buff_text.append(f"+{attack} attack")
        if health > 0:
            buff_text.append(f"+{health} health")
        return f"Give all friendly {tribe} {', '.join(buff_text)}"

    elif eff_type == 'permanent_stat_gain':
        attack = effect.get('attack', 0)
        health = effect.get('health', 0)
        buff_text = []
        if attack > 0:
            buff_text.append(f"+{attack} attack")
        if health > 0:
            buff_text.append(f"+{health} health")
        return f"Permanently gain {', '.join(buff_text)}"

    elif eff_type == 'attack_target':
        return "Attack an enemy"

    elif eff_type == 'modify_gold':
        amount = effect.get('amount', 0)
        if amount > 0:
            return f"Gain {amount} gold"
        else:
            return f"Lose {abs(amount)} gold"

    else:
        # Generic description
        keyword = _effect_type_to_keyword(effect_type)
        return f"{keyword.replace('_', ' ').title()} ability" if keyword else "special ability"