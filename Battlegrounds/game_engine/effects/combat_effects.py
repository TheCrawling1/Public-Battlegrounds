"""
Combat Effects - Effects that modify combat behavior

These effects handle combat keywords (poke, obliterate, cleave) by setting
flags in context that combat_actions.py respects.

This moves combat keywords into the trigger system, making them work like
any other trigger/effect combination.
"""

import logging

logger = logging.getLogger(__name__)

from typing import Dict, List, Tuple
from keywords import resolve_target
from game_engine.damage_handler import apply_damage, DamageType


def prevent_counter_damage(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Poke effect - prevents counter damage

    Sets a flag in context that combat_actions reads to skip counter damage.

    Args:
        effect_data: Effect configuration (usually empty for poke)
        context: Combat context with attacker/defender

    Returns:
        Tuple of (success, logs, changes)
    """
    acting_minion = context.get('acting_minion')

    # Set flag in context to prevent counter
    context['counter_damage_prevented'] = True

    # Generate log
    is_golden = acting_minion.get('golden', False) if acting_minion else False
    golden_prefix = "💎 Golden " if is_golden else ""

    minion_name = acting_minion.get('name', 'Unknown') if acting_minion else 'Unknown'

    return True, [f"🏹 {golden_prefix}{minion_name} pokes, avoiding counter damage!"], {
        'counter_prevented': True
    }


def mark_obliterate(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Obliterate effect - marks target for instant kill on any damage

    Sets a flag in context that damage_handler respects to kill target instantly.

    Args:
        effect_data: Effect configuration with optional target
        context: Combat context with attacker/defender

    Returns:
        Tuple of (success, logs, changes)
    """
    acting_minion = context.get('acting_minion')
    target_spec = effect_data.get('target', 'defender')

    # Resolve target
    success, target, error = resolve_target(target_spec, context, acting_minion)
    if not success:
        return False, [f"❌ Obliterate targeting failed: {error}"], {}

    if not target:
        return False, ["❌ No target for obliterate"], {}

    # Set flag in context for damage_handler to read
    context['obliterate_mode'] = True
    context['obliterate_target'] = target

    # Generate log
    is_golden = acting_minion.get('golden', False) if acting_minion else False
    golden_prefix = "💎 Golden " if is_golden else ""

    minion_name = acting_minion.get('name', 'Unknown') if acting_minion else 'Unknown'
    target_name = target.get('name', 'Unknown')

    return True, [f"💀⚡ {golden_prefix}{minion_name} will obliterate {target_name}!"], {
        'obliterate_marked': True,
        'target': target
    }


def deal_cleave_damage(effect_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Cleave effect - damages adjacent enemies

    Finds adjacent enemies to the primary target and deals damage to them.

    Args:
        effect_data: Effect configuration with adjacent_count
        context: Combat context with attacker/defender/damage_dealt

    Returns:
        Tuple of (success, logs, changes)
    """
    acting_minion = context.get('acting_minion')
    primary_target = context.get('defender')

    if not acting_minion or not primary_target:
        return False, ["❌ Missing attacker or defender for cleave"], {}

    # Get base damage from attacker's attack stat
    base_damage = acting_minion.get('attack', 0)

    if base_damage <= 0:
        return True, [], {}  # No damage to cleave with

    # Get adjacent count (how many minions to hit on each side)
    adjacent_count = effect_data.get('adjacent_count', 1)

    # Apply golden doubling
    if acting_minion.get('golden', False):
        adjacent_count *= 2

    # Get combat registry to find adjacent enemies
    registry = context.get('combat_registry')
    if not registry:
        return False, ["❌ No combat registry for cleave"], {}

    # Get defender's band
    defender_band_type = registry.get_minion_band_type(primary_target)
    if not defender_band_type:
        return False, ["❌ Cannot determine target's band"], {}

    # Get the appropriate band
    if defender_band_type == 'player':
        defender_band = context.get('absolute_player_band', context.get('player_band', []))
    else:
        defender_band = context.get('absolute_enemy_band', context.get('enemy_band', []))

    # Find primary target's position
    target_pos = primary_target.get('position', -1)
    if target_pos < 0:
        return False, ["❌ Cannot find target position"], {}

    logger.debug(f"[CLEAVE] Primary target {primary_target['name']} at position {target_pos}")
    logger.debug(f"[CLEAVE] Defender band has {len(defender_band)} minions")
    for m in defender_band:
        logger.debug(f"[CLEAVE]   - {m['name']} at position {m.get('position', -1)}, health: {m.get('health', 0)}")

    # Find adjacent enemies (both left and right of primary target)
    adjacent_targets = []

    # Left adjacent targets
    for i in range(1, adjacent_count + 1):
        left_pos = target_pos - i
        logger.debug(f"[CLEAVE] Checking left position {left_pos}")
        if left_pos >= 0:
            # Find minion at this position
            for minion in defender_band:
                if minion.get('position') == left_pos and minion.get('health', 0) > 0:
                    adjacent_targets.append(minion)
                    logger.debug(f"[CLEAVE] Found left target: {minion['name']} at position {left_pos}")
                    break

    # Right adjacent targets
    for i in range(1, adjacent_count + 1):
        right_pos = target_pos + i
        logger.debug(f"[CLEAVE] Checking right position {right_pos}")
        if right_pos < len(defender_band):
            # Find minion at this position
            for minion in defender_band:
                if minion.get('position') == right_pos and minion.get('health', 0) > 0:
                    adjacent_targets.append(minion)
                    logger.debug(f"[CLEAVE] Found right target: {minion['name']} at position {right_pos}")
                    break

    logger.debug(f"[CLEAVE] Found {len(adjacent_targets)} total adjacent targets")

    if not adjacent_targets:
        return True, [], {}  # No adjacent targets to cleave

    # Deal damage to each adjacent target
    logs = []
    cleave_kills = []

    # CRITICAL: Create a clean damage context without obliterate flags
    # Cleave should deal normal combat damage, not obliterate
    cleave_context = {
        'combat_registry': context.get('combat_registry'),
        'absolute_player_band': context.get('absolute_player_band'),
        'absolute_enemy_band': context.get('absolute_enemy_band'),
        'combat_state': context.get('combat_state'),
        'registrar': context.get('registrar'),
        'trigger_processor': context.get('trigger_processor')
    }

    for target in adjacent_targets:
        damage_result = apply_damage(
            target=target,
            amount=base_damage,
            damage_type=DamageType.COMBAT,
            source_minion=acting_minion,
            context=cleave_context  # Use clean context
        )

        # Check if target died from cleave
        target_health = target.get('health', 0)
        logger.debug(f"[CLEAVE] After damage, {target['name']} has {target_health} health")

        if target_health <= 0:
            cleave_kills.append(target)
            logs.append(f"  🗡️💀 Cleave deals {base_damage} damage and kills {target['name']}!")
        else:
            logs.append(f"  🗡️ Cleave deals {base_damage} damage to {target['name']} ({target_health} HP remaining)")

    # Track in effect context
    effect_context = context.get('effect_context')
    if effect_context:
        effect_context.target_minions.extend(adjacent_targets)
        effect_context.damage_dealt += base_damage * len(adjacent_targets)

    return True, logs, {
        'cleave_targets': adjacent_targets,
        'cleave_kills': cleave_kills,
        'cleave_damage': base_damage * len(adjacent_targets)
    }