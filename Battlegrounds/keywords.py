"""
Keywords System - Defines and manages minion keyword abilities with GameRandom integration

All keyword implementations in this file now use the centralized GameRandom system
for selections, enabling dev mode manual targeting overrides.

Updated to support trigger context targeting, allowing effects to target
the source or target of triggering actions.

UPDATED: Added Stun X keyword that causes minions to skip X attacks.
UPDATED: Added on_any_summon keyword and trigger_summoned/trigger_summoner targets.
UPDATED: Added Hide, Leap, Nobility, Rich keywords.
UPDATED: Added fatigue_immune, start_of_combat, on_adjacent_transform keywords.
UPDATED: Added on_damage keyword for reactive damage triggers.
UPDATED: Added has_nobility() helper function for nobility damage blocking.
UPDATED: Added Fast keyword (start of combat attack).
UPDATED: Added Savage keyword (always target lowest health enemy).
UPDATED: Added Imperfect keyword (unlimited combining with stat summing).
UPDATED: Added on_any_leap keyword for leap event reactions.
FIXED: Added defensive validation in resolve_target to prevent string returns
UPDATED: Replaced emoji icons with Lucide SVG icons for better scalability
"""

import logging

logger = logging.getLogger(__name__)

from game_random import game_random, SelectionType
from lucide_icons import get_icon_for_keyword


# Keyword definitions with descriptions and power values
KEYWORDS = {
    'poke': {
        'name': 'Poke',
        'description': 'Does not take counter-attack damage when attacking',
        'power_value': 5,
        'icon': get_icon_for_keyword('poke', width=24, height=24)
    },
    'guard': {
        'name': 'Guard',
        'description': 'Other minions cannot be attacked until this minion is killed',
        'power_value': 8,
        'icon': get_icon_for_keyword('guard', width=24, height=24)
    },
    'assault': {
        'name': 'Assault',
        'description': 'When this minion attacks, a special effect triggers',
        'power_value': 6,
        'icon': get_icon_for_keyword('assault', width=24, height=24)
    },
    'death_toll': {
        'name': 'Death Toll',
        'description': 'When this minion dies, a special effect triggers',
        'power_value': 4,
        'icon': get_icon_for_keyword('death_toll', width=24, height=24)
    },
    'cast': {
        'name': 'Cast',
        'description': 'Instead of attacking normally, cast a spell',
        'power_value': 7,
        'icon': get_icon_for_keyword('cast', width=24, height=24)
    },
    'rage': {
        'name': 'Rage',
        'description': 'Triggers when other minions attack normally (not cast)',
        'power_value': 5,
        'icon': get_icon_for_keyword('rage', width=24, height=24)
    },
    'calm': {
        'name': 'Calm',
        'description': 'Triggers when any minion casts a spell',
        'power_value': 5,
        'icon': get_icon_for_keyword('calm', width=24, height=24)
    },
    'on_any_death': {
        'name': 'On Any Death',
        'description': 'Triggers when any minion dies',
        'power_value': 4,
        'icon': get_icon_for_keyword('on_any_death', width=24, height=24)
    },
    'on_any_cast': {
        'name': 'On Any Cast',
        'description': 'Triggers when any spell is cast',
        'power_value': 3,
        'icon': get_icon_for_keyword('on_any_cast', width=24, height=24)
    },
    'on_any_summon': {
        'name': 'On Any Summon',
        'description': 'Triggers when any minion is summoned',
        'power_value': 4,
        'icon': get_icon_for_keyword('on_any_summon', width=24, height=24)
    },
    'on_adjacent_transform': {
        'name': 'On Adjacent Transform',
        'description': 'Triggers when an adjacent minion becomes a new minion',
        'power_value': 4,
        'icon': get_icon_for_keyword('on_adjacent_transform', width=24, height=24)
    },
    'on_damage': {
        'name': 'On Damage',
        'description': 'Triggers when this minion takes damage',
        'power_value': 5,
        'icon': get_icon_for_keyword('on_damage', width=24, height=24)
    },
    'cant_attack': {
        'name': "Can't Attack",
        'description': 'This minion cannot attack normally (but can still cast)',
        'power_value': -3,
        'icon': get_icon_for_keyword('cant_attack', width=24, height=24)
    },
    'cant_retaliate': {
        'name': "Can't Retaliate",
        'description': 'This minion does not deal counter damage when attacked',
        'power_value': -2,
        'icon': get_icon_for_keyword('cant_retaliate', width=24, height=24)
    },
    'cant_cast': {
        'name': "Can't Cast",
        'description': 'This minion cannot use cast abilities',
        'power_value': -2,
        'icon': get_icon_for_keyword('cant_cast', width=24, height=24)
    },
    'multi_attack': {
        'name': 'Multi Attack',
        'description': 'This minion attacks multiple times per turn',
        'power_value': 10,
        'icon': get_icon_for_keyword('multi_attack', width=24, height=24)
    },
    'multi_attack_2': {
        'name': 'Multi Attack 2',
        'description': 'This minion attacks 2 additional times',
        'power_value': 15,
        'icon': get_icon_for_keyword('multi_attack_2', width=24, height=24)
    },
    'aura': {
        'name': 'Aura',
        'description': 'Provides passive effects to adjacent allies',
        'power_value': 7,
        'icon': get_icon_for_keyword('aura', width=24, height=24)
    },
    'sacrifice': {
        'name': 'Sacrifice',
        'description': 'Dies instead of other allies under certain conditions',
        'power_value': 4,
        'icon': get_icon_for_keyword('sacrifice', width=24, height=24)
    },
    'stun': {
        'name': 'Stun',
        'description': 'This minion skips attacks (reduced multi-attacks)',
        'power_value': -4,
        'icon': get_icon_for_keyword('stun', width=24, height=24)
    },
    'hide': {
        'name': 'Hide',
        'description': "Can't be attacked for X attacks or until only target",
        'power_value': 7,
        'icon': get_icon_for_keyword('hide', width=24, height=24)
    },
    'leap': {
        'name': 'Leap',
        'description': 'Moves right X spaces when attacking',
        'power_value': 3,
        'icon': get_icon_for_keyword('leap', width=24, height=24)
    },
    'nobility': {
        'name': 'Nobility',
        'description': 'Only takes damage from direct combat',
        'power_value': 15,
        'icon': get_icon_for_keyword('nobility', width=24, height=24)
    },
    'rich': {
        'name': 'Rich',
        'description': 'Start of Combat: Gain +1/+1 per gold',
        'power_value': 5,
        'icon': get_icon_for_keyword('rich', width=24, height=24)
    },
    'fatigue_immune': {
        'name': 'Fatigue Immune',
        'description': "Can't take fatigue damage",
        'power_value': 8,
        'icon': get_icon_for_keyword('fatigue_immune', width=24, height=24)
    },
    'start_of_combat': {
        'name': 'Start of Combat',
        'description': 'Triggers an effect at the start of combat',
        'power_value': 4,
        'icon': get_icon_for_keyword('start_of_combat', width=24, height=24)
    },
    'cleave': {
        'name': 'Cleave',
        'description': 'Hits 1 adjacent minion on each side of the defender',
        'power_value': 6,
        'icon': get_icon_for_keyword('cleave', width=24, height=24)
    },
    'obliterate': {
        'name': 'Obliterate',
        'description': 'Any damage dealt by this minion destroys the target',
        'power_value': 25,  # Extremely powerful - instant kill on any damage
        'icon': get_icon_for_keyword('obliterate', width=24, height=24)
    },
    'fast': {
        'name': 'Fast',
        'description': 'Attacks at the start of combat',
        'power_value': 8,
        'icon': get_icon_for_keyword('fast', width=24, height=24)
    },
    'savage': {
        'name': 'Savage',
        'description': 'Always attacks the lowest health enemy',
        'power_value': 6,
        'icon': get_icon_for_keyword('savage', width=24, height=24)
    },
    'imperfect': {
        'name': 'Imperfect',
        'description': 'Can be combined unlimited times (stats sum instead of doubling)',
        'power_value': 3,
        'icon': get_icon_for_keyword('imperfect', width=24, height=24)
    },
    'on_any_leap': {
        'name': 'On Any Leap',
        'description': 'Triggers when any minion leaps',
        'power_value': 5,
        'icon': get_icon_for_keyword('on_any_leap', width=24, height=24)
    },
    'on_any_death_toll': {
        'name': 'On Any Death Toll',
        'description': 'Triggers when any death toll effect is triggered',
        'power_value': 6,
        'icon': get_icon_for_keyword('on_any_death_toll', width=24, height=24)
    },
    'ethereal': {
        'name': 'Ethereal',
        'description': "Survives lethal damage until its condition is met. Ethereal minions don't work if there are multiple ethereal minions. Can never guard.",
        'power_value': 20,
        'prevents_guard': True,  # Flag to prevent Guard being added
        'icon': get_icon_for_keyword('ethereal', width=24, height=24)
    },
    'ethereal_left': {
        'name': 'Ethereal [Left]',
        'description': "Survives lethal damage until its condition is met. Ethereal minions don't work if there are multiple ethereal minions. Can never guard.",
        'power_value': 20,
        'prevents_guard': True,
        'icon': get_icon_for_keyword('ethereal', width=24, height=24)
    },
    'last': {
        'name': 'Last',
        'description': "Is allowed to die when it's the last friendly minion alive.",
        'power_value': 0,  # Modifier, not standalone keyword
        'icon': get_icon_for_keyword('last', width=24, height=24)
    },
    'left': {
        'name': 'Left',
        'description': "Is allowed to die when it's the leftmost friendly minion alive.",
        'power_value': 0,  # Modifier, not standalone keyword
        'icon': get_icon_for_keyword('left', width=24, height=24)
    },
    'lichdom': {
        'name': 'Lichdom',
        'description': 'Effects that cost health instead cost that much gold.',
        'power_value': 25,
        'hero_power': True,  # This is a hero power, not minion keyword
        'icon': get_icon_for_keyword('lichdom', width=24, height=24)
    },
    'on_hide_lost': {
        'name': 'On Hide Lost',
        'description': 'Triggers when this minion loses its hide',
        'power_value': 6,
        'icon': get_icon_for_keyword('on_hide_lost', width=24, height=24)
    },
    'ignoble': {
        'name': 'Ignoble',
        'description': 'Cannot take combat damage or counter damage',
        'power_value': 8,
        'icon': get_icon_for_keyword('ignoble', width=24, height=24)
    },
    'ring': {
        'name': 'Ring',
        'description': 'Start of combat: Trigger 1 random friendly death toll. Decrease this by 1.',
        'power_value': 10,
        'wrapper': True,  # Ring X where X is the value
        'permanent': True,  # Survives combat like Cat
        'icon': get_icon_for_keyword('ring', width=24, height=24)
    }
}


def get_all_keywords():
    """Get list of all available keywords"""
    return list(KEYWORDS.keys())


def get_keyword_info(keyword):
    """Get information about a specific keyword"""
    return KEYWORDS.get(keyword.lower(), {})


def has_keyword(minion, keyword):
    """Check if a minion has a specific keyword"""
    if not minion:
        return False
    keywords = minion.get('keywords', [])
    return keyword in keywords


def has_nobility(minion):
    """
    Check if a minion has the nobility keyword

    Nobility means the minion can only take damage from direct combat
    (attacks and counter-attacks), not from spells or effects.
    Fatigue damage still works on nobility minions.

    Args:
        minion: The minion to check

    Returns:
        bool: True if minion has nobility
    """
    return has_keyword(minion, 'nobility')


def get_keyword_power_value(keyword):
    """Get the power value contribution of a keyword"""
    info = get_keyword_info(keyword)
    return info.get('power_value', 0)


def get_multi_attack_count(minion):
    """
    Get the number of additional attacks for a multi_attack minion
    Takes stun into account - stun reduces the number of attacks

    Args:
        minion: The minion to check

    Returns:
        int: Number of additional attacks (0 if no multi_attack or fully stunned)
    """
    if not minion:
        return 0

    # Check for specific multi_attack variants
    if has_keyword(minion, 'multi_attack_2'):
        base_count = 2
    elif has_keyword(minion, 'multi_attack'):
        # Check for multi_attack_count field
        base_count = minion.get('multi_attack_count', 1)
    else:
        return 0

    # Double for golden minions
    if minion.get('golden', False):
        base_count = base_count * 2

    # Reduce by stun count
    stun_count = minion.get('stun_count', 0)
    remaining_attacks = max(0, base_count - stun_count)

    return remaining_attacks


def is_stunned(minion):
    """
    Check if a minion is currently stunned

    Args:
        minion: The minion to check

    Returns:
        bool: True if minion has stun count > 0
    """
    if not minion:
        return False
    return minion.get('stun_count', 0) > 0


def reduce_stun(minion):
    """
    Reduce stun count by 1 when a minion's turn is skipped

    Args:
        minion: The minion whose stun to reduce

    Returns:
        int: Remaining stun count
    """
    if not minion:
        return 0

    current_stun = minion.get('stun_count', 0)
    if current_stun > 0:
        minion['stun_count'] = current_stun - 1

        # Remove stun keyword if no longer stunned
        if minion['stun_count'] == 0 and 'stun' in minion.get('keywords', []):
            minion['keywords'].remove('stun')

    return minion.get('stun_count', 0)


def is_hidden(minion):
    """
    Check if a minion is currently hidden

    Args:
        minion: The minion to check

    Returns:
        bool: True if minion is hidden
    """
    if not minion:
        return False
    return minion.get('is_hidden', False) and has_keyword(minion, 'hide')


def reduce_hide_count(minion):
    """
    Reduce hide count by 1 when minion attacks

    Args:
        minion: The minion whose hide to reduce

    Returns:
        int: Remaining hide count
    """
    if not minion:
        return 0

    if not has_keyword(minion, 'hide'):
        return 0

    hide_remaining = minion.get('hide_remaining', 0)
    if hide_remaining > 0:
        minion['hide_remaining'] = hide_remaining - 1

        # Unhide if count reaches 0
        if minion['hide_remaining'] == 0:
            minion['is_hidden'] = False

    return minion['hide_remaining']


def reduce_ring_count(minion):
    """
    Reduce ring count by 1 after triggering at start of combat

    Ring is a simple permanent counter: Ring 3 -> Ring 2 -> Ring 1 -> removed
    Uses permanent_ring_count field (like Cat's permanent_health) - never reset from template.

    Args:
        minion: The minion whose ring to reduce

    Returns:
        int: Remaining ring count
    """
    if not minion:
        return 0

    if not has_keyword(minion, 'ring'):
        return 0

    # Get current permanent ring count (like Cat's permanent stats)
    ring_count = minion.get('permanent_ring_count', 0)

    # Decrease by 1
    if ring_count > 0:
        minion['permanent_ring_count'] = ring_count - 1

    # Ensure it doesn't go negative
    if minion.get('permanent_ring_count', 0) < 0:
        minion['permanent_ring_count'] = 0

    # NOTE: Keyword removal is handled by remove_keyword effect (not here)
    # This ensures removal persists to the band minion, not just combat copy

    return minion.get('permanent_ring_count', 0)


def apply_combat_keywords(attacker, defender, base_counter_damage):
    """
    Apply keyword modifications to combat

    Args:
        attacker: The attacking minion
        defender: The defending minion
        base_counter_damage: The base counter damage before modifications

    Returns:
        tuple: (modified_counter_damage, log_entries)
    """
    counter_damage = base_counter_damage
    logs = []

    # Poke - no counter damage
    if has_keyword(attacker, 'poke'):
        counter_damage = 0
        if base_counter_damage > 0:
            logs.append(f"Poke prevents {base_counter_damage} counter damage")

    # Can't Retaliate - defender can't counter
    if has_keyword(defender, 'cant_retaliate'):
        counter_damage = 0
        if base_counter_damage > 0:
            logs.append(f"{defender['name']} can't retaliate")

    # Nobility - only takes damage from direct combat (handled elsewhere)
    # This function only handles counter damage modifiers

    return counter_damage, logs


def select_combat_target(attacker, valid_targets):
    """
    Select a target for combat using GameRandom system

    UPDATED: Savage keyword now checked FIRST - ignores guard and hide completely

    Args:
        attacker: The attacking minion
        valid_targets: List of valid target minions

    Returns:
        Selected target minion or None
    """
    if not valid_targets:
        return None

    # CHECK SAVAGE FIRST - ignores all targeting rules (guard, hide)
    if has_keyword(attacker, 'savage'):
        # Find the lowest health enemy from ALL targets
        min_health = min(t.get('health', 0) for t in valid_targets)
        lowest_health_targets = [t for t in valid_targets if t.get('health', 0) == min_health]

        if len(lowest_health_targets) == 1:
            # Only one lowest health target
            logger.debug(
                f"[SAVAGE] {attacker.get('name')} targets lowest health: {lowest_health_targets[0].get('name')} ({min_health} HP)")
            return lowest_health_targets[0]
        else:
            # Multiple targets with same lowest health - pick randomly among them
            context = {
                'attacker_name': attacker.get('name', 'Unknown'),
                'attacker_band_id': attacker.get('band_id'),
                'attacker_combat_id': attacker.get('_combat_id'),
                'savage_targeting': True,
                'lowest_health': min_health,
                'target_count': len(lowest_health_targets)
            }

            description = f"{attacker.get('name', 'Unknown')} selecting savage target (lowest health: {min_health})"

            target = game_random.select_one(
                SelectionType.COMBAT_TARGET,
                lowest_health_targets,
                context=context,
                description=description
            )

            logger.debug(
                f"[SAVAGE] {attacker.get('name')} targets {target.get('name')} ({min_health} HP) from {len(lowest_health_targets)} tied targets")
            return target

    # NORMAL TARGETING (no savage keyword)

    # First filter out hidden minions unless they're the only targets
    non_hidden = [t for t in valid_targets if not is_hidden(t)]

    # If all targets are hidden, we can target them
    if not non_hidden:
        non_hidden = valid_targets

    # Then check for guard keyword
    # NOTE: Ethereal minions (both [Last] and [Left]) cannot provide Guard protection
    guards = [t for t in non_hidden if has_keyword(t, 'guard') and not has_keyword(t, 'ethereal') and not has_keyword(t, 'ethereal_left')]
    if guards:
        # If hidden minions have guard but are hidden, guard doesn't apply
        # Only non-hidden guards force targeting
        non_hidden_guards = [g for g in guards if not is_hidden(g)]
        if non_hidden_guards:
            valid_targets = non_hidden_guards
        else:
            valid_targets = non_hidden
    else:
        valid_targets = non_hidden

    # Use GameRandom for selection with context
    context = {
        'attacker_name': attacker.get('name', 'Unknown'),
        'attacker_band_id': attacker.get('band_id'),
        'attacker_combat_id': attacker.get('_combat_id'),
        'has_guard': len(guards) > 0,
        'has_hidden': any(is_hidden(t) for t in valid_targets),
        'target_count': len(valid_targets)
    }

    description = f"{attacker.get('name', 'Unknown')} selecting combat target"

    return game_random.select_one(
        SelectionType.COMBAT_TARGET,
        valid_targets,
        context=context,
        description=description
    )


def _validate_minion_return(minion, target_spec):
    """
    DEFENSIVE: Validate that a resolved target is actually a minion dict, not a string

    Args:
        minion: The value to validate
        target_spec: The target specification that was resolved (for error messages)

    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    if minion is None:
        return True, None  # None is valid (indicates not found)

    if isinstance(minion, str):
        return False, f"INTERNAL ERROR: resolve_target returned string '{minion}' instead of minion dict for target_spec '{target_spec}'"

    if not isinstance(minion, dict):
        return False, f"INTERNAL ERROR: resolve_target returned {type(minion).__name__} instead of minion dict for target_spec '{target_spec}'"

    return True, None


def resolve_target(target_spec, context, acting_minion=None):
    """
    Resolve a target specification to actual target(s) using GameRandom

    This is the main targeting function used by the combat effects system.
    Now fully integrated with GameRandom for dev mode override support.

    UPDATED: Now supports trigger context targeting to reference participants
    in triggering actions (trigger_source, trigger_target, trigger_summoned, trigger_summoner)
    UPDATED: Added support for lowest_health_enemy and other new targets
    FIXED: Added defensive validation to prevent returning strings instead of minion dicts

    Args:
        target_spec: String specifying the target type
        context: Combat context with bands and combat state
        acting_minion: The minion performing the action

    Returns:
        tuple: (success: bool, target(s): minion or list, error_message: str)
    """
    # Get bands from context
    ally_band = context.get('ally_band', [])
    enemy_band = context.get('enemy_band', [])

    # Helper to create context for GameRandom
    def make_random_context(selection_type_suffix=""):
        ctx = {
            'target_spec': target_spec,
            'trigger_source': context.get('trigger_source', 'unknown')
        }
        if acting_minion:
            ctx.update({
                'acting_minion_name': acting_minion.get('name', 'Unknown'),
                'acting_minion_band_id': acting_minion.get('band_id'),
                'acting_minion_combat_id': acting_minion.get('_combat_id')
            })
        return ctx

    # === NEW SUMMON TRIGGER CONTEXT TARGETING ===
    if target_spec == 'trigger_summoned':
        # The minion that was summoned
        trigger_summoned = context.get('trigger_context_summoned')
        if not trigger_summoned:
            return False, None, "No summoned minion in trigger context"

        # DEFENSIVE: Validate it's actually a dict
        is_valid, error = _validate_minion_return(trigger_summoned, target_spec)
        if not is_valid:
            return False, None, error

        # Summoned minion should be alive (just summoned)
        if trigger_summoned.get('health', 0) <= 0:
            return False, None, "Summoned minion is dead"
        return True, trigger_summoned, None

    elif target_spec == 'trigger_summoner':
        # The minion that performed the summon
        trigger_summoner = context.get('trigger_context_summoner')
        if not trigger_summoner:
            return False, None, "No summoner in trigger context"

        # DEFENSIVE: Validate it's actually a dict
        is_valid, error = _validate_minion_return(trigger_summoner, target_spec)
        if not is_valid:
            return False, None, error

        # Summoner might be dead (from death toll)
        # Don't check health for summoner as they could be dead from death toll
        return True, trigger_summoner, None

    elif target_spec == 'trigger_transformed':
        # The minion that was transformed
        trigger_transformed = context.get('trigger_context_transformed')
        if not trigger_transformed:
            return False, None, "No transformed minion in trigger context"

        # DEFENSIVE: Validate it's actually a dict
        is_valid, error = _validate_minion_return(trigger_transformed, target_spec)
        if not is_valid:
            return False, None, error

        return True, trigger_transformed, None

    # === LEAP TRIGGER CONTEXT TARGETING ===
    elif target_spec == 'trigger_leaper':
        # The minion that performed the leap
        trigger_leaper = context.get('trigger_context_leaper')
        if not trigger_leaper:
            return False, None, "No leaper in trigger context"

        # DEFENSIVE: Validate it's actually a dict
        is_valid, error = _validate_minion_return(trigger_leaper, target_spec)
        if not is_valid:
            return False, None, error

        # Check if leaper is still alive
        if trigger_leaper.get('health', 0) <= 0:
            return False, None, "Leaper is dead"
        return True, trigger_leaper, None

    # === ORIGINAL TRIGGER CONTEXT TARGETING ===
    elif target_spec == 'trigger_source':
        # The minion that caused the trigger (e.g., the spell caster for on_any_cast)
        trigger_source = context.get('trigger_context_source')
        if not trigger_source:
            return False, None, "No trigger source in context"

        # DEFENSIVE: Validate it's actually a dict
        is_valid, error = _validate_minion_return(trigger_source, target_spec)
        if not is_valid:
            return False, None, error

        # Check if trigger source is still alive
        if trigger_source.get('health', 0) <= 0:
            return False, None, "Trigger source is dead"
        return True, trigger_source, None

    elif target_spec == 'trigger_target':
        # The target of the triggering action (e.g., spell target)
        trigger_target = context.get('trigger_context_target')
        if not trigger_target:
            return False, None, "No trigger target in context"

        # DEFENSIVE: Validate it's actually a dict
        is_valid, error = _validate_minion_return(trigger_target, target_spec)
        if not is_valid:
            return False, None, error

        # Check if trigger target is still alive
        if trigger_target.get('health', 0) <= 0:
            return False, None, "Trigger target is dead"
        return True, trigger_target, None

    elif target_spec == 'trigger_attacker':
        # For combat-based triggers, the attacker
        trigger_attacker = context.get('trigger_context_attacker')
        if not trigger_attacker:
            return False, None, "No trigger attacker in context"

        # DEFENSIVE: Validate it's actually a dict
        is_valid, error = _validate_minion_return(trigger_attacker, target_spec)
        if not is_valid:
            return False, None, error

        if trigger_attacker.get('health', 0) <= 0:
            return False, None, "Trigger attacker is dead"
        return True, trigger_attacker, None

    elif target_spec == 'trigger_defender':
        # For combat-based triggers, the defender
        trigger_defender = context.get('trigger_context_defender')
        if not trigger_defender:
            return False, None, "No trigger defender in context"

        # DEFENSIVE: Validate it's actually a dict
        is_valid, error = _validate_minion_return(trigger_defender, target_spec)
        if not is_valid:
            return False, None, error

        if trigger_defender.get('health', 0) <= 0:
            return False, None, "Trigger defender is dead"
        return True, trigger_defender, None

    elif target_spec == 'trigger_dying':
        # For death-based triggers, the dying minion
        trigger_dying = context.get('trigger_context_dying')
        if not trigger_dying:
            return False, None, "No dying minion in trigger context"

        # DEFENSIVE: Validate it's actually a dict
        is_valid, error = _validate_minion_return(trigger_dying, target_spec)
        if not is_valid:
            return False, None, error

        # Note: Dying minion might already be dead, that's okay
        return True, trigger_dying, None

    elif target_spec == 'trigger_killer':
        # For death-based triggers, what killed the minion (if tracked)
        trigger_killer = context.get('trigger_context_killer')
        if not trigger_killer:
            return False, None, "No killer tracked in trigger context"

        # DEFENSIVE: Validate it's actually a dict
        is_valid, error = _validate_minion_return(trigger_killer, target_spec)
        if not is_valid:
            return False, None, error

        if trigger_killer.get('health', 0) <= 0:
            return False, None, "Trigger killer is dead"
        return True, trigger_killer, None

    # === ORIGINAL TARGETING OPTIONS ===

    elif target_spec == 'self':
        if not acting_minion:
            return False, None, "No acting minion for self target"
        return True, acting_minion, None

    elif target_spec == 'defender':
        defender = context.get('defender')
        if not defender:
            return False, None, "No defender in context"

        # DEFENSIVE: Validate it's actually a dict
        is_valid, error = _validate_minion_return(defender, target_spec)
        if not is_valid:
            return False, None, error

        return True, defender, None

    elif target_spec == 'attacker':
        attacker = context.get('attacker')
        if not attacker:
            return False, None, "No attacker in context"

        # DEFENSIVE: Validate it's actually a dict
        is_valid, error = _validate_minion_return(attacker, target_spec)
        if not is_valid:
            return False, None, error

        return True, attacker, None

    elif target_spec == 'random_ally':
        alive_allies = [m for m in ally_band if m.get('health', 0) > 0]
        if not alive_allies:
            return False, None, "No alive allies"

        target = game_random.select_one(
            SelectionType.RANDOM_ALLY,
            alive_allies,
            context=make_random_context(),
            description=f"Select random ally for {acting_minion.get('name', 'effect') if acting_minion else 'effect'}"
        )
        return True, target, None

    elif target_spec == 'random_enemy':
        alive_enemies = [m for m in enemy_band if m.get('health', 0) > 0]
        if not alive_enemies:
            return False, None, "No alive enemies"

        # Check if acting minion has savage - targets lowest health instead of random
        if acting_minion and has_keyword(acting_minion, 'savage'):
            min_health = min(e.get('health', 0) for e in alive_enemies)
            lowest_health_enemies = [e for e in alive_enemies if e.get('health', 0) == min_health]

            if len(lowest_health_enemies) == 1:
                target = lowest_health_enemies[0]
                logger.debug(f"[SAVAGE] {acting_minion.get('name')} effect targets lowest health: {target.get('name')} ({min_health} HP)")
            else:
                # Multiple targets with same lowest health - pick randomly among them
                target = game_random.select_one(
                    SelectionType.RANDOM_ENEMY,
                    lowest_health_enemies,
                    context=make_random_context(),
                    description=f"Savage select lowest health enemy for {acting_minion.get('name', 'effect')}"
                )
                logger.debug(f"[SAVAGE] {acting_minion.get('name')} effect targets {target.get('name')} ({min_health} HP) from {len(lowest_health_enemies)} tied targets")
            return True, target, None

        target = game_random.select_one(
            SelectionType.RANDOM_ENEMY,
            alive_enemies,
            context=make_random_context(),
            description=f"Select random enemy for {acting_minion.get('name', 'effect') if acting_minion else 'effect'}"
        )
        return True, target, None

    elif target_spec == 'all_allies':
        alive_allies = [m for m in ally_band if m.get('health', 0) > 0]
        if not alive_allies:
            return False, [], "No alive allies"
        return True, alive_allies, None

    elif target_spec == 'all_enemies':
        alive_enemies = [m for m in enemy_band if m.get('health', 0) > 0]
        if not alive_enemies:
            return False, [], "No alive enemies"
        return True, alive_enemies, None

    elif target_spec == 'all_minions':
        all_alive = [m for m in ally_band + enemy_band if m.get('health', 0) > 0]
        if not all_alive:
            return False, [], "No alive minions"
        return True, all_alive, None

    elif target_spec == 'lowest_health_ally':
        alive_allies = [m for m in ally_band if m.get('health', 0) > 0]
        if not alive_allies:
            return False, None, "No alive allies"

        # Find all allies with the lowest health
        min_health = min(m.get('health', 0) for m in alive_allies)
        lowest_health_allies = [m for m in alive_allies if m.get('health', 0) == min_health]

        # If multiple have the same lowest health, pick randomly
        if len(lowest_health_allies) > 1:
            target = game_random.select_one(
                SelectionType.HEAL_TARGET,
                lowest_health_allies,
                context={**make_random_context(), 'reason': 'tie_breaker', 'health': min_health},
                description=f"Break tie for lowest health ally ({min_health} HP)"
            )
        else:
            target = lowest_health_allies[0]

        return True, target, None

    elif target_spec == 'lowest_health_enemy':
        alive_enemies = [m for m in enemy_band if m.get('health', 0) > 0]
        if not alive_enemies:
            return False, None, "No alive enemies"

        # Find all enemies with the lowest health
        min_health = min(m.get('health', 0) for m in alive_enemies)
        lowest_health_enemies = [m for m in alive_enemies if m.get('health', 0) == min_health]

        # If multiple have the same lowest health, pick randomly
        if len(lowest_health_enemies) > 1:
            target = game_random.select_one(
                SelectionType.DAMAGE_TARGET,
                lowest_health_enemies,
                context={**make_random_context(), 'reason': 'tie_breaker', 'health': min_health},
                description=f"Break tie for lowest health enemy ({min_health} HP)"
            )
        else:
            target = lowest_health_enemies[0]

        return True, target, None

    elif target_spec == 'highest_attack_enemy':
        alive_enemies = [m for m in enemy_band if m.get('health', 0) > 0]
        if not alive_enemies:
            return False, None, "No alive enemies"

        # Find all enemies with the highest attack
        max_attack = max(m.get('attack', 0) for m in alive_enemies)
        highest_attack_enemies = [m for m in alive_enemies if m.get('attack', 0) == max_attack]

        # If multiple have the same highest attack, pick randomly
        if len(highest_attack_enemies) > 1:
            target = game_random.select_one(
                SelectionType.DAMAGE_TARGET,
                highest_attack_enemies,
                context={**make_random_context(), 'reason': 'tie_breaker', 'attack': max_attack},
                description=f"Break tie for highest attack enemy ({max_attack} ATK)"
            )
        else:
            target = highest_attack_enemies[0]

        return True, target, None

    elif target_spec == 'left_ally':
        # Get leftmost (position 0) alive ally
        alive_allies = [m for m in ally_band if m.get('health', 0) > 0]
        if not alive_allies:
            return False, None, "No alive allies"

        # Sort by position and get leftmost
        alive_allies.sort(key=lambda m: m.get('position', 999))
        return True, alive_allies[0], None

    elif target_spec == 'right_ally':
        # Get rightmost (highest position) alive ally
        alive_allies = [m for m in ally_band if m.get('health', 0) > 0]
        if not alive_allies:
            return False, None, "No alive allies"

        # Sort by position and get rightmost
        alive_allies.sort(key=lambda m: m.get('position', 0), reverse=True)
        return True, alive_allies[0], None

    elif target_spec == 'adjacent_allies':
        # Get allies adjacent to acting minion
        if not acting_minion:
            return False, [], "No acting minion for adjacent targeting"

        acting_pos = acting_minion.get('position', 0)
        adjacent = []

        for m in ally_band:
            if m.get('health', 0) > 0 and m != acting_minion:
                pos = m.get('position', 0)
                if abs(pos - acting_pos) == 1:
                    adjacent.append(m)

        if not adjacent:
            return False, [], "No adjacent allies"
        return True, adjacent, None

    elif target_spec == 'friendly_hound':
        # Find a friendly hound
        hounds = [m for m in ally_band if m.get('health', 0) > 0 and m.get('name') == 'Hound']
        if not hounds:
            return False, None, "No friendly Hound found"

        # Pick first hound (or random if multiple)
        if len(hounds) > 1:
            target = game_random.select_one(
                SelectionType.RANDOM_ALLY,
                hounds,
                context=make_random_context(),
                description="Select a Hound"
            )
        else:
            target = hounds[0]

        return True, target, None

    elif target_spec == 'summon_position':
        # Special target for summon effects - returns position not minion
        # This is handled specially by summon effects
        return True, 'summon_position', None

    elif target_spec == 'condition_found_minion':
        # Minion found by a condition check (e.g., has_minion_named)
        condition_found = context.get('condition_found_minion')
        if not condition_found:
            return False, None, "No condition_found_minion in context"

        # DEFENSIVE: Validate it's actually a dict
        is_valid, error = _validate_minion_return(condition_found, target_spec)
        if not is_valid:
            return False, None, error

        return True, condition_found, None

    else:
        return False, None, f"Unknown target specification: {target_spec}"


def validate_keywords(keywords):
    """
    Validate a list of keywords

    Args:
        keywords: List of keyword strings to validate

    Returns:
        bool: True if all keywords are valid
    """
    if not keywords:
        return True

    if not isinstance(keywords, list):
        return False

    valid_keywords = set(KEYWORDS.keys())
    for keyword in keywords:
        if keyword not in valid_keywords:
            return False

    return True


def calculate_keyword_power(minion):
    """
    Calculate the total power value contribution from keywords

    Args:
        minion: Minion dictionary with keywords

    Returns:
        int: Total power value from keywords
    """
    keywords = minion.get('keywords', [])
    total_power = 0

    for keyword in keywords:
        total_power += get_keyword_power_value(keyword)

    # Add multi-attack bonus if applicable
    if 'multi_attack' in keywords:
        multi_count = get_multi_attack_count(minion)
        total_power += multi_count * 5  # Extra value per additional attack

    # Subtract for stun
    stun_count = minion.get('stun_count', 0)
    if stun_count > 0:
        total_power -= stun_count * 3  # Penalty per stun stack

    # Add for hide remaining
    if has_keyword(minion, 'hide'):
        hide_remaining = minion.get('hide_remaining', 0)
        total_power += hide_remaining * 2  # Value for protection

    return total_power