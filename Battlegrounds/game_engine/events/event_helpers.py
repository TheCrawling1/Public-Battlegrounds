"""
Event Helpers - Centralized utilities for general event choice processing

This module extracts the core logic for:
- Formula resolution (gold costs, rewards, stat bonuses)
- Tooltip template substitution
- Condition evaluation (keyword checks, tribe counts, etc.)
- Choice option validation

When adding a new general event, this module ensures consistent behavior
without modifying the core event processing code.
"""

import logging

logger = logging.getLogger(__name__)

import re


# ==================== FORMULA RESOLUTION ====================


def resolve_formula(formula, tier):
    """
    Resolve a tier-based formula to a concrete integer value.

    Handles:
        - Integer literals: '2', '25'
        - Simple tier formulas: 'tier * 3', 'tier * 6'
        - Raw integers passed directly: 2, 25

    Args:
        formula: A string formula or integer value
        tier: Current ring/tier level (int)

    Returns:
        Resolved integer value, or 0 if formula is None/empty

    Examples:
        resolve_formula('tier * 3', 2) -> 6
        resolve_formula('25', 1) -> 25
        resolve_formula(2, 1) -> 2
        resolve_formula(None, 1) -> 0
    """
    if formula is None:
        return 0

    if isinstance(formula, (int, float)):
        return int(formula)

    formula_str = str(formula).strip()
    if not formula_str:
        return 0

    # Replace 'tier' with actual value and evaluate safely
    if 'tier' in formula_str:
        expr = formula_str.replace('tier', str(tier))
        try:
            # Only allow simple arithmetic expressions
            result = _safe_eval_arithmetic(expr)
            return int(result)
        except (ValueError, SyntaxError):
            return 0
    else:
        try:
            return int(formula_str)
        except ValueError:
            return 0


def _safe_eval_arithmetic(expr):
    """
    Safely evaluate a simple arithmetic expression (no builtins, no imports).

    Only allows: digits, +, -, *, /, parentheses, and whitespace.
    """
    # Strip and validate - only allow safe characters
    cleaned = expr.strip()
    if not re.match(r'^[\d\s\+\-\*\/\(\)\.]+$', cleaned):
        raise ValueError(f"Unsafe expression: {expr}")
    # eval with empty globals/locals to prevent code injection
    return eval(cleaned, {"__builtins__": {}}, {})


# ==================== TOOLTIP RESOLUTION ====================


def resolve_tooltip(tooltip, tier, context=None):
    """
    Resolve all template variables in a tooltip string.

    Handles two patterns:
        1. Named variables: {gold_cost}, {gold_reward}, {tier}, {stat_bonus}
        2. Inline formulas: {tier * 3}, {tier * 5 + 2}

    The context dict provides values for named variables.
    Any remaining {tier ...} expressions are evaluated as formulas.

    Args:
        tooltip: Template string with {variable} placeholders
        tier: Current ring/tier level
        context: Dict of named variable values, e.g.
                 {'gold_cost': 6, 'gold_reward': 12}

    Returns:
        Fully resolved tooltip string

    Examples:
        resolve_tooltip('Pay ({gold_cost}) gold.', 2, {'gold_cost': 12})
        -> 'Pay (12) gold.'

        resolve_tooltip('Give all Beasts +{tier * 2} attack.', 3, {})
        -> 'Give all Beasts +6 attack.'
    """
    if not tooltip:
        return ''

    context = context or {}

    result = tooltip

    # Step 1: Replace named variables from context
    for key, value in context.items():
        result = result.replace('{' + key + '}', str(value))

    # Step 2: Replace any remaining {expressions} that contain 'tier'
    # This handles patterns like {tier * 3}, {tier * 2 + 1}, etc.
    def _replace_tier_expr(match):
        expr = match.group(1)
        if 'tier' in expr:
            resolved = resolve_formula(expr, tier)
            return str(resolved)
        return match.group(0)  # Leave non-tier expressions unchanged

    result = re.sub(r'\{([^}]+)\}', _replace_tier_expr, result)

    return result


# ==================== CONDITION EVALUATION ====================


# Registry of condition evaluators.
# Each entry maps a condition prefix/name to a function(run, event_state, condition_str) -> bool (disabled).
# Return True if the option should be DISABLED, False if enabled.

def _check_has_keyword(run, event_state, condition):
    """Check if any minion has a specific keyword: 'has_keyword_fast'"""
    keyword = condition.replace('has_keyword_', '')
    band = run.get_band()
    has_it = any(keyword in m.get('keywords', []) for m in band)
    return not has_it  # disabled if NOT found


def _check_unique_tribes(run, event_state, condition):
    """Check unique tribe count: 'unique_tribes >= 4'"""
    _, value = condition.split('>=')
    required = int(value.strip())
    band = run.get_band()
    all_types = []
    for m in band:
        t = m.get('type', '')
        if isinstance(t, list):
            all_types.extend(t)
        elif t:
            all_types.append(t)
    return len(set(all_types)) < required


def _check_beast_count(run, event_state, condition):
    """Check Beast minion count: 'beast_count >= 3'"""
    _, value = condition.split('>=')
    required = int(value.strip())
    band = run.get_band()
    beast_count = sum(1 for m in band if m.get('type') == 'Beast')
    return beast_count < required


def _check_band_size(run, event_state, condition):
    """Check band size: 'band_size >= 1'"""
    _, value = condition.split('>=')
    required = int(value.strip())
    band = run.get_band()
    return len(band) < required


def _check_scrap_heap_blind_luck(run, event_state, condition):
    """Blind Luck is always disabled unless unlocked by special means"""
    return True


def _check_not_has_lichdom(run, event_state, condition):
    """Check player doesn't already have Lichdom"""
    hero_effects = run.get_hero_effects()
    return hero_effects.get('lichdom', False)  # disabled if already has it


def _check_has_transcendence_candidate(run, event_state, condition):
    """Check for a minion meeting transcendence requirements:
    Tier 2+, 0 attack, 1 health, no types, no keywords"""
    band = run.get_band()
    for minion in band:
        tier = minion.get('tier', 1)
        attack = minion.get('attack', 0)
        health = minion.get('health', 1)
        types = minion.get('type', 'None')
        keywords = minion.get('keywords', [])

        is_tier_2_plus = tier >= 2
        is_zero_attack = attack == 0
        is_one_health = health == 1
        has_no_types = (types == 'None' or types is None or
                       (isinstance(types, list) and len(types) == 0))
        has_no_keywords = len(keywords) == 0

        if is_tier_2_plus and is_zero_attack and is_one_health and has_no_types and has_no_keywords:
            return False  # NOT disabled - candidate found
    return True  # disabled - no candidate


def _check_boss_not_defeated_this_tier(run, event_state, condition):
    """Check if a boss has already been defeated this tier"""
    bosses_defeated = event_state.get('bosses_defeated', {})
    current_tier = str(run.current_ring)
    return bosses_defeated.get(current_tier) is not None


def _check_has_beast_and_2_minions(run, event_state, condition):
    """Check for at least one Beast AND at least 2 minions total"""
    band = run.get_band()
    beast_count = sum(1 for m in band if m.get('type') == 'Beast')
    return len(band) < 2 or beast_count < 1


def _check_lte_comparison(run, event_state, condition, state_defaults=None):
    """Generic event_state <= comparison: 'ivory_tower_seal <= 0'"""
    var_name, value = condition.split('<=')
    var_name = var_name.strip()
    value = int(value.strip())
    fallback = (state_defaults or {}).get(var_name, 0)
    current_value = event_state.get(var_name, fallback)
    return current_value > value


def _check_gte_comparison(run, event_state, condition, state_defaults=None):
    """Generic event_state >= comparison: 'bells_rung >= 4'"""
    var_name, value = condition.split('>=')
    var_name = var_name.strip()
    value = int(value.strip())
    fallback = (state_defaults or {}).get(var_name, 0)
    current_value = event_state.get(var_name, fallback)
    return current_value < value


# Ordered list of (matcher, handler) pairs.
# Matcher can be a string prefix or a callable that takes the condition string.
CONDITION_HANDLERS = [
    ('has_keyword_', _check_has_keyword),
    ('unique_tribes', _check_unique_tribes),
    ('beast_count', _check_beast_count),
    ('band_size', _check_band_size),
    ('scrap_heap_blind_luck_available', _check_scrap_heap_blind_luck),
    ('not_has_lichdom', _check_not_has_lichdom),
    ('has_transcendence_candidate', _check_has_transcendence_candidate),
    ('boss_not_defeated_this_tier', _check_boss_not_defeated_this_tier),
    ('has_beast_and_2_minions', _check_has_beast_and_2_minions),
]


def evaluate_condition(condition, run, event_state, state_defaults=None):
    """
    Evaluate a condition string and return whether the option is DISABLED.

    This is the single entry point for all condition checks in general events.
    To add a new condition type, add a handler to CONDITION_HANDLERS above.

    Args:
        condition: Condition string (e.g. 'has_keyword_fast', 'beast_count >= 3')
        run: The current run object
        event_state: The current event state dict
        state_defaults: (optional) Dict of default values for event_state keys,
                        from the event's 'state_defaults' field. Used by generic
                        comparison operators so they fall back to the event's
                        declared default instead of 0 on first visit.

    Returns:
        True if the option should be DISABLED, False if enabled
    """
    if not condition:
        return False  # No condition = always enabled

    # Check named/prefix handlers first
    for prefix, handler in CONDITION_HANDLERS:
        if condition == prefix or condition.startswith(prefix):
            return handler(run, event_state, condition)

    # Fall back to generic comparison operators
    if '<=' in condition:
        return _check_lte_comparison(run, event_state, condition, state_defaults)
    elif '>=' in condition:
        return _check_gte_comparison(run, event_state, condition, state_defaults)

    # Unknown condition - default to enabled (not disabled)
    return False


# ==================== CHOICE OPTION VALIDATION ====================

# Required fields for a choice option in a make_choice screen
REQUIRED_CHOICE_FIELDS = ['name']

# Recommended fields (will warn if missing)
RECOMMENDED_CHOICE_FIELDS = ['tooltip', 'icon']


def validate_choice_option(choice, event_id='unknown', index=0):
    """
    Validate a single choice option has required and recommended fields.

    Args:
        choice: Dict representing a choice option
        event_id: Parent event ID for error messages
        index: Option index for error messages

    Returns:
        (is_valid, errors, warnings) tuple
    """
    errors = []
    warnings = []

    for field in REQUIRED_CHOICE_FIELDS:
        if field not in choice:
            errors.append(f"Event '{event_id}' choice {index}: missing required field '{field}'")

    for field in RECOMMENDED_CHOICE_FIELDS:
        if field not in choice:
            warnings.append(f"Event '{event_id}' choice {index} ('{choice.get('name', '?')}'): missing recommended field '{field}'")

    # Validate that the choice has either next_event, next_screen, or on_select
    # (or is a Leave option which has next_event=None explicitly)
    has_action = (
        'next_event' in choice or
        'next_screen' in choice or
        'on_select' in choice
    )
    if not has_action:
        warnings.append(
            f"Event '{event_id}' choice {index} ('{choice.get('name', '?')}'): "
            f"has no next_event, next_screen, or on_select"
        )

    return len(errors) == 0, errors, warnings


def validate_event_choices(event):
    """
    Validate all choices in an event's make_choice screens.

    Args:
        event: Event definition dict

    Returns:
        (is_valid, errors, warnings) tuple
    """
    all_errors = []
    all_warnings = []
    event_id = event.get('id', 'unknown')

    for screen in event.get('screens', []):
        if screen.get('type') == 'make_choice':
            choices = screen.get('parameters', {}).get('choices', [])
            for i, choice in enumerate(choices):
                valid, errors, warnings = validate_choice_option(choice, event_id, i)
                all_errors.extend(errors)
                all_warnings.extend(warnings)

    return len(all_errors) == 0, all_errors, all_warnings


def validate_all_general_event_choices():
    """
    Validate choices for all general events and their sub-events.
    Prints results and returns success/failure.

    Returns:
        True if all events pass validation (no errors)
    """
    from game_engine.events.events import (
        CROSSROADS_EVENTS, CROSSROADS_SUB_EVENTS,
        FEY_ZONE_EVENTS, FEY_ZONE_SUB_EVENTS,
        CONSTRUCT_ZONE_EVENTS, CONSTRUCT_ZONE_SUB_EVENTS,
        CULT_ZONE_EVENTS, CULT_ZONE_SUB_EVENTS,
        UNDEAD_ZONE_EVENTS, UNDEAD_ZONE_SUB_EVENTS,
        GREAT_HUNT_EVENTS, GREAT_HUNT_SUB_EVENTS,
        BELL_TOWER, BELL_TOWER_SUB_EVENTS
    )

    all_events = {}
    all_events.update(CROSSROADS_EVENTS)
    all_events.update(CROSSROADS_SUB_EVENTS)
    all_events.update(FEY_ZONE_EVENTS)
    all_events.update(FEY_ZONE_SUB_EVENTS)
    all_events.update(CONSTRUCT_ZONE_EVENTS)
    all_events.update(CONSTRUCT_ZONE_SUB_EVENTS)
    all_events.update(CULT_ZONE_EVENTS)
    all_events.update(CULT_ZONE_SUB_EVENTS)
    all_events.update(UNDEAD_ZONE_EVENTS)
    all_events.update(UNDEAD_ZONE_SUB_EVENTS)
    all_events.update(GREAT_HUNT_EVENTS)
    all_events.update(GREAT_HUNT_SUB_EVENTS)
    all_events.update({'bell_tower': BELL_TOWER})
    all_events.update(BELL_TOWER_SUB_EVENTS)

    total_errors = []
    total_warnings = []

    for event_id, event in all_events.items():
        valid, errors, warnings = validate_event_choices(event)
        total_errors.extend(errors)
        total_warnings.extend(warnings)

    if total_errors:
        logger.error(f"✗ Choice validation found {len(total_errors)} errors:")
        for err in total_errors:
            logger.error(f"  ERROR: {err}")

    if total_warnings:
        logger.warning(f"  {len(total_warnings)} warnings (non-blocking):")
        for warn in total_warnings:
            logger.warning(f"  WARN: {warn}")

    if not total_errors:
        logger.debug(f"✓ All general event choices validated ({len(all_events)} events checked)")

    return len(total_errors) == 0


# ==================== TOOLTIP CONTEXT BUILDER ====================


def build_tooltip_context(choice, tier, event_state, run, event_def=None):
    """
    Build the full context dict for tooltip substitution from a choice option.

    This extracts all dynamic values (gold_cost, gold_reward, stat_bonus, etc.)
    and resolves their formulas, providing a ready-to-use context for resolve_tooltip().

    Event state values are populated from the event's 'state_defaults' dict.
    Each key declared there is added to the context using its current value
    from event_state (falling back to the declared default for new runs).
    This keeps stateful tooltip variables co-located with their event definition
    instead of hardcoded here.

    Args:
        choice: The choice option dict
        tier: Current ring/tier
        event_state: Current event state
        run: The current run
        event_def: (optional) The parent event definition dict.
                   If it has a 'state_defaults' key, those values are
                   pulled from event_state into the tooltip context.

    Returns:
        Dict of resolved tooltip variables
    """
    ctx = {'tier': tier}

    # Gold cost
    gold_cost_formula = choice.get('gold_cost')
    if gold_cost_formula is not None:
        ctx['gold_cost'] = resolve_formula(gold_cost_formula, tier)

    # Gold reward
    gold_reward_formula = choice.get('gold_reward')
    if gold_reward_formula is not None:
        ctx['gold_reward'] = resolve_formula(gold_reward_formula, tier)

    # Stat bonus
    stat_bonus_formula = choice.get('stat_bonus')
    if stat_bonus_formula is not None:
        ctx['stat_bonus'] = resolve_formula(stat_bonus_formula, tier)

    # Health cost (static or tracked)
    health_cost_tracker = choice.get('health_cost_tracker')
    static_health_cost = choice.get('health_cost')
    if health_cost_tracker:
        ctx['health_cost'] = event_state.get(health_cost_tracker, 1)
        ctx[health_cost_tracker] = ctx['health_cost']
    elif static_health_cost:
        ctx['health_cost'] = static_health_cost

    # Event state values from the event's declared state_defaults.
    # Each event declares which keys it uses and their defaults, e.g.:
    #   'state_defaults': {'ivory_tower_seal': 4}
    # At tooltip time we read the live value from event_state (persisted
    # per-run), falling back to the default for first-visit display.
    if event_def:
        for key, default in event_def.get('state_defaults', {}).items():
            ctx[key] = event_state.get(key, default)

    return ctx
