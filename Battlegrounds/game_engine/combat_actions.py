"""
Combat Action Handlers - Process combat-specific actions

Each handler:
- Takes action_data and context
- Returns (success, logs, changes)
- Generates formatted log messages with combat context

UPDATED: Combat keywords now processed via trigger system
- Poke/obliterate set flags in context that we read here
- Cleave fires as separate LOW priority trigger after main damage
"""

import logging

logger = logging.getLogger(__name__)

from typing import Dict, List, Tuple


def process_combat_damage(action_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Process combat damage with poke/obliterate/counter/CLEAVE/nobility/ignoble logic

    Args:
        action_data: {
            'attacker': minion,
            'defender': minion,
            'base_damage': int,
            'base_counter': int,
            'has_poke': bool,  # HARDCODED - SHOULD BE REMOVED
            'defender_cant_retaliate': bool,
            'has_cleave': bool,  # HARDCODED - SHOULD BE REMOVED
            'cleave_amount': int  # HARDCODED - SHOULD BE REMOVED
        }
        context: Combat context

    Returns:
        (success, logs, changes)
    """
    attacker = action_data['attacker']
    defender = action_data['defender']
    base_damage = action_data['base_damage']
    base_counter = action_data['base_counter']
    has_poke = action_data.get('has_poke', False)  # HARDCODED - SHOULD READ FROM CONTEXT
    defender_cant_retaliate = action_data.get('defender_cant_retaliate', False)
    has_cleave = action_data.get('has_cleave', False)  # HARDCODED - SHOULD BE REMOVED
    cleave_amount = action_data.get('cleave_amount', 0)  # HARDCODED - SHOULD BE REMOVED

    # Determine actual counter damage
    actual_counter = 0
    if not has_poke and not defender_cant_retaliate:
        actual_counter = base_counter

    # Apply damage through damage handler
    from game_engine.damage_handler import apply_damage, DamageType

    damage_context = {
        'combat_registry': context.get('combat_registry'),
        'combat_state': context.get('combat_state'),
        'trigger_processor': context.get('trigger_processor'),
        'registrar': context.get('registrar'),  # For hero effects that trigger on_any_leap
        'run': context.get('run'),
        'absolute_player_band': context.get('absolute_player_band'),
        'absolute_enemy_band': context.get('absolute_enemy_band'),
        'interpreter': context.get('interpreter')  # CRITICAL FIX: For Olimpia commands
    }

    target_result = apply_damage(
        target=defender,
        amount=base_damage,
        damage_type=DamageType.COMBAT,
        source_minion=attacker,
        context=damage_context
    )

    # NEW: Process cleave damage - HARDCODED - SHOULD BE TRIGGER-BASED
    cleave_targets = []
    if has_cleave and cleave_amount > 0:
        combat_registry = context.get('combat_registry')

        if combat_registry:
            defender_band_type = combat_registry.get_minion_band_type(defender)

            if defender_band_type == 'player':
                defender_band = context.get('absolute_player_band', [])
            else:
                defender_band = context.get('absolute_enemy_band', [])

            if defender_band:
                defender_pos = defender.get('position', -1)
                logger.debug(f"[CLEAVE] Processing cleave - defender at position {defender_pos}")

                adjacent_targets = []

                # Check left adjacent
                for left_steps in range(1, cleave_amount + 1):
                    left_pos = defender_pos - left_steps
                    logger.debug(f"[CLEAVE] Checking left position {left_pos}")

                    for m in defender_band:
                        if m.get('position') == left_pos and m.get('health', 0) > 0:
                            adjacent_targets.append(m)
                            logger.debug(f"[CLEAVE] Found left target: {m['name']} at position {left_pos}")
                            break

                # Check right adjacent
                for right_steps in range(1, cleave_amount + 1):
                    right_pos = defender_pos + right_steps
                    logger.debug(f"[CLEAVE] Checking right position {right_pos}")

                    for m in defender_band:
                        if m.get('position') == right_pos and m.get('health', 0) > 0:
                            adjacent_targets.append(m)
                            logger.debug(f"[CLEAVE] Found right target: {m['name']} at position {right_pos}")
                            break

                logger.debug(f"[CLEAVE] Found {len(adjacent_targets)} adjacent targets")

                # Deal damage to each adjacent target
                for cleave_target in adjacent_targets:
                    cleave_result = apply_damage(
                        target=cleave_target,
                        amount=base_damage,
                        damage_type=DamageType.COMBAT,
                        source_minion=attacker,
                        context=damage_context
                    )
                    cleave_targets.append(cleave_target)
                    logger.debug(
                        f"[CLEAVE] Dealt {base_damage} damage to {cleave_target['name']}, result: {cleave_result.damage_applied} applied")

    # Apply counter damage to attacker
    counter_result = apply_damage(
        target=attacker,
        amount=actual_counter,
        damage_type=DamageType.COUNTER,
        source_minion=defender,
        context=damage_context
    )

    # Build logs based on obliterate, nobility, ignoble, and damage patterns
    logs = []
    attacker_name = f"{attacker['name']} #{action_data.get('attacker_index', 0) + 1}"
    is_multi_attack = context.get('combat_state', {}).get('in_multi_attack', False)

    # Add any special logs from damage handler (e.g., hero effects like Olimpia)
    logs.extend(target_result.logs)
    logs.extend(counter_result.logs)

    # CRITICAL: Add nobility/ignoble block logs from damage handler
    if target_result.blocked_by_nobility:
        logs.append(f"🛡️ {defender['name']} blocks {base_damage} damage with Nobility!")
    if target_result.blocked_by_ignoble:
        logs.append(f"⚔️ {defender['name']} is Ignoble and takes full damage from {attacker['name']}!")

    # Main combat log
    # Use counter_result.damage_applied instead of actual_counter for accurate logs
    applied_counter = counter_result.damage_applied

    if target_result.blocked_by_nobility:
        # No damage log if blocked
        log = f"🛡️ {attacker_name} attacks {defender['name']} but damage is blocked by Nobility"
    elif target_result.obliterate_kill:
        # Attack obliterates
        if applied_counter > 0:
            log = f"💀⚡ {attacker_name} deals {base_damage} damage and obliterates {defender['name']}, takes {applied_counter} counter damage"
        else:
            log = f"💀⚡ {attacker_name} deals {base_damage} damage and obliterates {defender['name']}"
    elif counter_result.obliterate_kill:
        # Counter obliterates
        log = f"💀⚡ {attacker_name} attacks {defender['name']} for {base_damage} damage and is obliterated by counter-attack!"
    else:
        # Normal combat (no obliterate or blocking)
        log = f"🗡️ {attacker_name} attacks {defender['name']} for {base_damage} damage"
        if applied_counter > 0:
            log += f", takes {applied_counter} counter damage"
            if is_multi_attack:
                log += " (multi-attack)"
        elif base_counter > 0 and has_poke:
            log += f", avoids {base_counter} counter damage (Poke)"
        elif base_counter > 0 and defender_cant_retaliate:
            log += f", takes no counter damage (defender can't retaliate)"

    logs.append(log)

    # NEW: Add cleave damage logs - HARDCODED - SHOULD BE IN TRIGGER
    if cleave_targets:
        for cleave_target in cleave_targets:
            if cleave_target.get('health', 0) <= 0:
                # Target was killed by cleave
                logs.append(f"  🗡️💀 Cleave obliterates {cleave_target['name']}!")
            else:
                # Target survived cleave
                logs.append(f"  🗡️ Cleave hits {cleave_target['name']} for {base_damage} damage")

    changes = {
        'attacker': attacker,
        'defender': defender,
        'damage_dealt': target_result.damage_applied,
        'counter_damage_dealt': counter_result.damage_applied,
        'obliterate_kill': target_result.obliterate_kill,
        'counter_obliterate_kill': counter_result.obliterate_kill,
        'blocked_by_nobility': target_result.blocked_by_nobility or counter_result.blocked_by_nobility,
        'blocked_by_ignoble': target_result.blocked_by_ignoble or counter_result.blocked_by_ignoble,
        'cleave_targets': cleave_targets  # HARDCODED - SHOULD BE REMOVED
    }

    return True, logs, changes


def process_declare_attack(action_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Process attack declaration

    Args:
        action_data: {
            'attacker': minion,
            'defender': minion,
            'attacker_index': int
        }
        context: Combat context

    Returns:
        (success, logs, changes)
    """
    attacker = action_data['attacker']
    defender = action_data['defender']
    attacker_index = action_data.get('attacker_index', 0)

    attacker_name = f"{attacker['name']} #{attacker_index + 1}"
    log = f"⚔️ {attacker_name} prepares to attack {defender['name']}"

    return True, [log], {
        'attacker': attacker,
        'defender': defender
    }


def process_turn_start(action_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Process turn start announcement

    Args:
        action_data: {
            'minion': minion,
            'is_enemy': bool,
            'minion_index': int
        }
        context: Combat context

    Returns:
        (success, logs, changes)
    """
    minion = action_data['minion']
    is_enemy = action_data.get('is_enemy', False)
    minion_index = action_data.get('minion_index', 0)

    side = "Enemy" if is_enemy else "Player"
    minion_name = f"{minion['name']} #{minion_index + 1}"

    log = f"--- {side}: {minion_name}'s Turn ---"

    return True, [log], {
        'minion': minion,
        'is_enemy': is_enemy
    }


def process_stun_skip(action_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Process stun skip turn

    Args:
        action_data: {
            'minion': minion,
            'stun_remaining': int,
            'minion_index': int,
            'is_enemy': bool
        }
        context: Combat context

    Returns:
        (success, logs, changes)
    """
    minion = action_data['minion']
    stun_remaining = action_data.get('stun_remaining', 0)
    minion_index = action_data.get('minion_index', 0)

    minion_name = f"{minion['name']} #{minion_index + 1}"
    log = f"⏸️ {minion_name} is stunned ({stun_remaining} attack(s) remaining)"

    return True, [log], {
        'minion': minion,
        'stun_reduced': True
    }


def process_round_start(action_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Process round start announcement

    Args:
        action_data: {
            'round_number': int
        }
        context: Combat context

    Returns:
        (success, logs, changes)
    """
    round_number = action_data.get('round_number', 1)

    log = f"═══ Round {round_number} ═══"

    return True, [log], {
        'round_number': round_number
    }


def process_attack_cancelled(action_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Process cancelled attack (defender died before damage)

    Args:
        action_data: {
            'attacker': minion,
            'defender': minion (optional),
            'reason': str,
            'cast_used': bool,
            'attacker_index': int
        }
        context: Combat context

    Returns:
        (success, logs, changes)
    """
    attacker = action_data['attacker']
    defender = action_data.get('defender')  # May be None if attacker died
    reason = action_data.get('reason', 'unknown')
    cast_used = action_data.get('cast_used', False)
    attacker_index = action_data.get('attacker_index', 0)

    attacker_name = f"{attacker['name']} #{attacker_index + 1}"

    # Only log for melee attacks - cast animations are purely cosmetic
    if cast_used:
        logs = []  # No log for cast-based cancelled attacks
    else:
        logs = [f"⚔️ {attacker_name}'s target died before attack"]

    changes = {
        'attacker': attacker,
        'attack_cancelled': True,
        'reason': reason
    }

    # Include defender if available (for animation targeting)
    if defender:
        changes['defender'] = defender

    return True, logs, changes


def process_no_attack_skip(action_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Process turn skip for minion that cannot attack

    Args:
        action_data: {
            'minion': minion,
            'reason': str ('cant_attack' or 'zero_attack'),
            'minion_index': int,
            'is_enemy': bool
        }
        context: Combat context

    Returns:
        (success, logs, changes)
    """
    minion = action_data['minion']
    reason = action_data.get('reason', 'cant_attack')
    minion_index = action_data.get('minion_index', 0)

    minion_name = f"{minion['name']} #{minion_index + 1}"

    if reason == 'cant_attack':
        log = f"🚫 {minion_name} can't attack"
    else:
        log = f"⚠️ {minion_name} has 0 attack"

    return True, [log], {
        'minion': minion,
        'turn_skipped': True,
        'reason': reason
    }


def process_cast_finished(action_data: Dict, context: Dict) -> Tuple[bool, List[str], Dict]:
    """
    Process cast spell completion

    Args:
        action_data: {
            'caster': minion,
            'caster_index': int
        }
        context: Combat context

    Returns:
        (success, logs, changes)
    """
    caster = action_data['caster']
    caster_index = action_data.get('caster_index', 0)

    caster_name = f"{caster['name']} #{caster_index + 1}"
    log = f"🔮 {caster_name} completes cast"

    return True, [log], {
        'caster': caster,
        'cast_completed': True
    }