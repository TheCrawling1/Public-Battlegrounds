"""
Effects System - Main dispatcher for all combat effects

This module acts as the central dispatcher for all effect types,
routing to the appropriate implementation based on effect type.

UPDATED: Added destroy_minion effect registration
UPDATED: Enhanced apply_effects_list to send effects to interpreter when trigger processor available
FIXED: Proper interpreter integration for effect arrays and conditional effects
UPDATED: Added reduce_hide and leap_move effects for Hide and Leap keywords
UPDATED: Added divide_attack effect for Queen Bee's start of combat
UPDATED: Added rich_buff effect for Rich keyword
UPDATED: Added modify_gold effect for adjusting player gold during combat
UPDATED: Added grant_effect_to_minion effect for dynamically granting abilities
UPDATED: Added transfer_stun effect for Nymph
UPDATED: Added scaling_damage effect for Railway Cannon
UPDATED: Added trigger_death_toll effect for Shaman
UPDATED: Added combat keyword effects (prevent_counter_damage, mark_obliterate, deal_cleave_damage)
"""

import logging

logger = logging.getLogger(__name__)

from typing import Dict, List, Tuple, Optional

# Import all effect implementations
from game_engine.effects.damage_effects import (
    deal_damage, heal, heal_self, damage_self, deal_aoe_damage
)
from game_engine.effects.stat_effects import (
    buff_stats, buff_stats_tribe, debuff_stats, permanent_stat_gain
)
from game_engine.effects.summon_effects import (
    summon_minion, destroy_and_transform, move_minion, destroy_minion
)
from game_engine.effects.special_effects import (
    modify_fatigue, attack_target, redirect_damage, prevent_death,
    copy_stats, grant_keyword, remove_keyword, chrono_cascade, perform_cast, apply_stun,
    recalculate_auras, buff_adjacent, reduce_hide, reduce_ring, leap_move, divide_attack,
    rich_buff, modify_gold, transfer_stun, scaling_damage, trigger_death_toll,
    trigger_start_of_combat
)
from game_engine.effects.special_effects2 import (
    grant_effect_to_minion
)
from game_engine.effects.conditional_effects import (
    evaluate_conditional
)
# Import combat keyword effects
from game_engine.effects.combat_effects import (
    prevent_counter_damage, mark_obliterate, deal_cleave_damage
)


# Effect type mapping to implementation functions
EFFECT_HANDLERS = {
    # Damage effects
    'deal_damage': deal_damage,
    'heal': heal,
    'heal_self': heal_self,
    'damage_self': damage_self,
    'deal_aoe_damage': deal_aoe_damage,

    # Stat effects
    'buff_stats': buff_stats,
    'buff_stats_tribe': buff_stats_tribe,
    'debuff_stats': debuff_stats,
    'permanent_stat_gain': permanent_stat_gain,

    # Summon effects
    'summon_minion': summon_minion,
    'destroy_minion': destroy_minion,
    'destroy_and_transform': destroy_and_transform,
    'move_minion': move_minion,

    # Special effects
    'modify_fatigue': modify_fatigue,
    'attack_target': attack_target,
    'redirect_damage': redirect_damage,
    'prevent_death': prevent_death,
    'copy_stats': copy_stats,
    'grant_keyword': grant_keyword,
    'remove_keyword': remove_keyword,
    'modify_gold': modify_gold,
    'transfer_stun': transfer_stun,

    # Chronomancer effects
    'chrono_cascade': chrono_cascade,
    'perform_cast': perform_cast,
    'apply_stun': apply_stun,

    # Aura effects
    'recalculate_auras': recalculate_auras,
    'buff_adjacent': buff_adjacent,

    # Hide, Ring, and Leap effects
    'reduce_hide': reduce_hide,
    'reduce_ring': reduce_ring,
    'leap_move': leap_move,

    # Start of combat effects
    'divide_attack': divide_attack,
    'rich_buff': rich_buff,

    # Effect granting
    'grant_effect_to_minion': grant_effect_to_minion,

    # New effects for tier 3/4 minions
    'scaling_damage': scaling_damage,
    'trigger_death_toll': trigger_death_toll,
    'trigger_start_of_combat': trigger_start_of_combat,

    # Combat keyword effects
    'prevent_counter_damage': prevent_counter_damage,
    'mark_obliterate': mark_obliterate,
    'deal_cleave_damage': deal_cleave_damage,

    # Conditional effect
    'conditional': evaluate_conditional,
}


def apply_effect(effect_data, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Apply a single combat effect using the appropriate handler

    This is the main entry point for effect application. It routes
    to the appropriate effect handler based on the effect type.

    Args:
        effect_data: Dictionary defining the effect (or List of effects)
        context: Combat context with registry, bands, etc.

    Returns:
        Tuple of (success, log_entries, changes_dict)
    """
    # Handle arrays of effects (like Tooth Fairy's assault)
    if isinstance(effect_data, list):
        all_logs = []
        all_changes = {}
        all_success = True

        for effect in effect_data:
            success, logs, changes = apply_effect(effect, context)
            all_logs.extend(logs)
            # Merge changes
            for key, value in changes.items():
                if key in all_changes:
                    # Handle merging lists
                    if isinstance(all_changes[key], list) and isinstance(value, list):
                        all_changes[key].extend(value)
                    else:
                        all_changes[key] = value
                else:
                    all_changes[key] = value
            all_success = all_success and success

        return all_success, all_logs, all_changes

    effect_type = effect_data.get('type')

    if not effect_type:
        return False, ["⚠️ No effect type specified"], {}

    # Get the handler for this effect type
    handler = EFFECT_HANDLERS.get(effect_type)

    if not handler:
        return False, [f"⚠️ Unknown effect type: {effect_type}"], {}

    try:
        # Call the appropriate handler
        return handler(effect_data, context)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, [f"❌ Error applying {effect_type}: {str(e)}"], {}


def apply_effects_list(effects_list: List[Dict], context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Apply multiple effects in sequence

    UPDATED: Now sends individual effects to interpreter when trigger processor available
    for proper frontend visualization of effect arrays and conditional effects.

    Args:
        effects_list: List of effect dictionaries
        context: Combat context

    Returns:
        Tuple of (overall_success, combined_logs, combined_changes)
    """
    all_logs = []
    all_changes = {}
    overall_success = True

    # Get trigger processor for interpreter integration
    trigger_processor = context.get('trigger_processor')
    acting_minion = context.get('acting_minion', context.get('dying_minion'))

    for i, effect in enumerate(effects_list):
        logger.debug(f"[EFFECTS_LIST] Processing effect {i+1}/{len(effects_list)}: {effect.get('type')}")
        success, logs, changes = apply_effect(effect, context)

        logger.debug(f"[EFFECTS_LIST] Effect {i+1} result: success={success}, logs_count={len(logs)}")

        if not success:
            overall_success = False
            logger.debug(f"[EFFECTS_LIST] Effect {i+1} failed - continuing with remaining effects")

        all_logs.extend(logs)

        # Merge changes
        for key, value in changes.items():
            if key in all_changes:
                # Combine values based on type
                if isinstance(value, list):
                    all_changes[key].extend(value)
                elif isinstance(value, dict):
                    all_changes[key].update(value)
                elif isinstance(value, (int, float)):
                    all_changes[key] += value
                else:
                    all_changes[key] = value
            else:
                all_changes[key] = value

        # ENHANCED: Send individual effect results to interpreter
        # This ensures that effect arrays from conditional effects are properly visualized
        # SKIP: trigger_death_toll and trigger_start_of_combat (already sent command manually before child effects)
        effect_type = effect.get('type')
        skip_effects = ['trigger_death_toll', 'trigger_start_of_combat']
        if trigger_processor and success and acting_minion and effect_type not in skip_effects:
            logger.debug(f"[EFFECTS] Sending effect {i+1}/{len(effects_list)} to interpreter: {effect_type}")
            # Pass logs for this specific effect to the interpreter
            # Get trigger_type from context if available, otherwise use None
            trigger_type = context.get('trigger_type')
            trigger_processor._send_effect_results_to_interpreter(effect, changes, acting_minion,
                                                                 trigger_type=trigger_type,
                                                                 effect_logs=logs)
        elif effect_type in skip_effects:
            logger.debug(f"[EFFECTS] Skipping interpreter for {effect_type} (already sent manually)")

        # CRITICAL: Preserve context between effects for stat inheritance
        # This is especially important for destroy → summon sequences
        if effect.get('type') == 'destroy_minion' and changes.get('saved_stats'):
            context['saved_stats'] = changes['saved_stats']
            logger.debug(f"[EFFECTS] Preserved destroyed stats for inheritance: {changes['saved_stats']}")

    return overall_success, all_logs, all_changes


def get_effect_description(effect_type: str) -> str:
    """Get human-readable description of an effect type"""
    descriptions = {
        'deal_damage': "Deal damage to a target",
        'heal': "Heal a target",
        'heal_self': "Heal self",
        'damage_self': "Deal damage to self",
        'deal_aoe_damage': "Deal damage to multiple targets",
        'buff_stats': "Increase attack and/or health",
        'buff_stats_tribe': "Increase stats of specific tribe",
        'debuff_stats': "Decrease attack and/or health",
        'permanent_stat_gain': "Permanently increase stats",
        'summon_minion': "Summon a minion",
        'destroy_minion': "Destroy a minion",
        'destroy_and_transform': "Destroy and replace with new minion",
        'move_minion': "Move a minion to a new position",
        'modify_fatigue': "Accelerate or delay fatigue",
        'attack_target': "Perform an attack on a target",
        'redirect_damage': "Redirect damage to a different target",
        'prevent_death': "Prevent a minion from dying",
        'copy_stats': "Copy stats from one minion to another",
        'grant_keyword': "Grant a keyword to a minion",
        'chrono_cascade': "Force cast and stun all other casters",
        'perform_cast': "Force a minion to cast",
        'apply_stun': "Apply stun to a target",
        'recalculate_auras': "Recalculate all aura effects",
        'buff_adjacent': "Buff adjacent minions",
        'reduce_hide': "Reduce hide count when attacking",
        'reduce_ring': "Reduce ring count after triggering",
        'leap_move': "Move to the right when attacking",
        'divide_attack': "Divide minion's attack by a divisor",
        'rich_buff': "Gain +1/+1 per gold at start of combat",
        'grant_effect_to_minion': "Grant a combat effect to another minion",
        'scaling_damage': "Deal increasing damage that scales each use",
        'trigger_death_toll': "Trigger a friendly minion's death toll effect",
        'trigger_start_of_combat': "Trigger a friendly minion's start of combat effect",
        'prevent_counter_damage': "Prevent counter damage (Poke)",
        'mark_obliterate': "Mark target for instant kill (Obliterate)",
        'deal_cleave_damage': "Deal damage to adjacent enemies (Cleave)",
        'conditional': "Apply effects based on conditions",
    }

    return descriptions.get(effect_type, f"Unknown effect: {effect_type}")


def validate_effect_data(effect_data) -> Tuple[bool, Optional[str]]:
    """
    Validate effect data structure

    Args:
        effect_data: Effect dictionary to validate (or List of effects)

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not effect_data:
        return False, "Effect data is empty"

    # Handle arrays of effects (like Tooth Fairy's assault)
    if isinstance(effect_data, list):
        for i, effect in enumerate(effect_data):
            is_valid, error = validate_effect_data(effect)
            if not is_valid:
                return False, f"Effect {i} in array: {error}"
        return True, None

    effect_type = effect_data.get('type')
    if not effect_type:
        return False, "Effect type is required"

    if effect_type not in EFFECT_HANDLERS:
        return False, f"Unknown effect type: {effect_type}"

    # Type-specific validation
    if effect_type in ['deal_damage', 'heal', 'damage_self', 'heal_self']:
        if 'amount' not in effect_data:
            return False, f"{effect_type} requires 'amount' field"

    if effect_type == 'summon_minion':
        if 'minion_name' not in effect_data:
            return False, "summon_minion requires 'minion_name' field"

    if effect_type == 'destroy_minion':
        if 'target' not in effect_data:
            return False, "destroy_minion requires 'target' field"

    if effect_type in ['buff_stats', 'debuff_stats']:
        if 'health' not in effect_data and 'attack' not in effect_data:
            return False, f"{effect_type} requires 'health' or 'attack' field"

    if effect_type == 'apply_stun':
        if 'stun_amount' not in effect_data:
            return False, "apply_stun requires 'stun_amount' field"

    if effect_type == 'divide_attack':
        if 'divisor' not in effect_data:
            return False, "divide_attack requires 'divisor' field"

    if effect_type == 'modify_gold':
        if 'amount' not in effect_data:
            return False, "modify_gold requires 'amount' field"

    if effect_type == 'transfer_stun':
        if 'from_targets' not in effect_data:
            return False, "transfer_stun requires 'from_targets' field"
        if 'to_target' not in effect_data:
            return False, "transfer_stun requires 'to_target' field"

    if effect_type == 'grant_effect_to_minion':
        if 'effect_type' not in effect_data:
            return False, "grant_effect_to_minion requires 'effect_type' field"
        if 'effect_data' not in effect_data:
            return False, "grant_effect_to_minion requires 'effect_data' field"

    if effect_type == 'scaling_damage':
        if 'base_amount' not in effect_data:
            return False, "scaling_damage requires 'base_amount' field"
        if 'increment' not in effect_data:
            return False, "scaling_damage requires 'increment' field"

    if effect_type == 'trigger_death_toll':
        # No required fields - has defaults for target
        pass

    if effect_type == 'deal_cleave_damage':
        # adjacent_count has default
        pass

    if effect_type == 'mark_obliterate':
        # target has default
        pass

    if effect_type == 'prevent_counter_damage':
        # No required fields
        pass

    if effect_type == 'conditional':
        if 'condition' not in effect_data:
            return False, "conditional requires 'condition' field"
        if 'then_effect' not in effect_data:
            return False, "conditional requires 'then_effect' field"

    return True, None


def get_available_effect_types() -> List[str]:
    """Get list of all available effect types"""
    return list(EFFECT_HANDLERS.keys())


def register_custom_effect(effect_type: str, handler: callable):
    """
    Register a custom effect handler

    This allows extensions to add new effect types without
    modifying the core system.

    Args:
        effect_type: Name for the new effect type
        handler: Function to handle the effect
    """
    if effect_type in EFFECT_HANDLERS:
        logger.warning(f"[WARNING] Overriding existing effect handler for {effect_type}")

    EFFECT_HANDLERS[effect_type] = handler
    logger.debug(f"[EFFECTS] Registered custom effect handler for {effect_type}")


# Re-export key functions for backward compatibility
__all__ = [
    'apply_effect',
    'apply_effects_list',
    'get_effect_description',
    'validate_effect_data',
    'get_available_effect_types',
    'register_custom_effect',
]