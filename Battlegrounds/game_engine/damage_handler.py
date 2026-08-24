"""
Damage Handler - Centralized damage processing for all combat damage

This module serves as the single point of entry for ALL damage in the game.
By routing all damage through this handler, we can:
- Implement on_damage triggers (via registrar)
- Track damage statistics
- Apply defensive keywords (nobility, ignoble)
- Apply obliterate keyword (instant kill)
- Maintain consistent damage logging
- Enable future damage modification systems

CRITICAL: ALL damage sources must use this handler.
UPDATED: Now uses TriggerRegistrar instead of TriggerProcessor for on_damage triggers
UPDATED: Added Ignoble keyword support - blocks combat/counter damage (opposite of nobility)
"""

import logging

logger = logging.getLogger(__name__)

from typing import Dict, List, Tuple, Optional
from enum import Enum
from hero_definitions import get_scaled_effect_value


class DamageType(Enum):
    """Types of damage sources"""
    COMBAT = "combat"  # Normal attack damage
    COUNTER = "counter"  # Counter-attack damage
    SPELL = "spell"  # Spell/cast damage
    ABILITY = "ability"  # Assault/death toll/rage damage
    EFFECT = "effect"  # Generic effect damage
    FATIGUE = "fatigue"  # Fatigue damage
    AOE = "aoe"  # Area of effect damage


class DamageResult:
    """Result of a damage application"""

    def __init__(self):
        self.damage_applied = 0
        self.damage_blocked = 0
        self.target_killed = False
        self.blocked_by_nobility = False
        self.blocked_by_ignoble = False
        self.obliterate_kill = False
        self.damage_type = None
        self.source_minion = None
        self.target_minion = None
        self.logs = []

    def to_dict(self) -> Dict:
        """Convert to dictionary for changes tracking"""
        return {
            'damage_applied': self.damage_applied,
            'damage_blocked': self.damage_blocked,
            'target_killed': self.target_killed,
            'blocked_by_nobility': self.blocked_by_nobility,
            'blocked_by_ignoble': self.blocked_by_ignoble,
            'obliterate_kill': self.obliterate_kill,
            'damage_type': self.damage_type.value if self.damage_type else None,
            'source': self.source_minion.get('name') if self.source_minion else None,
            'target': self.target_minion.get('name') if self.target_minion else None
        }


class DamageHandler:
    """
    Central damage processing system

    All damage in the game should flow through apply_damage().
    This enables reactive systems like on_damage and obliterate.
    """

    def __init__(self):
        self.damage_events = []  # Track all damage events for statistics

    def apply_damage(self,
                     target: Dict,
                     amount: int,
                     damage_type: DamageType,
                     source_minion: Optional[Dict] = None,
                     context: Optional[Dict] = None) -> DamageResult:
        """
        Apply damage to a target minion

        This is the ONLY method that should modify minion health for damage.

        UPDATED: Now uses registrar to generate on_damage triggers

        Args:
            target: The minion taking damage
            amount: Amount of damage to apply
            damage_type: Type of damage (combat, spell, etc.)
            source_minion: The minion dealing damage (if any)
            context: Combat context for additional information

        Returns:
            DamageResult with details about what happened
        """
        result = DamageResult()
        result.damage_type = damage_type
        result.source_minion = source_minion
        result.target_minion = target

        if amount <= 0:
            return result

        # Check for nobility (blocks non-combat damage)
        if self._check_nobility_block(target, damage_type):
            result.damage_blocked = amount
            result.blocked_by_nobility = True

            is_golden = target.get('golden', False)
            golden_prefix = "💎 Golden " if is_golden else ""
            result.logs.append(
                f"👑 {golden_prefix}{target['name']}'s Nobility blocks {amount} {damage_type.value} damage!"
            )

            # Track the event even if blocked
            self._track_damage_event(target, 0, damage_type, source_minion, blocked=True, block_type='nobility')

            # No damage applied means no on_damage triggers
            return result

        # Check for ignoble (blocks combat/counter damage)
        if self._check_ignoble_block(target, damage_type):
            result.damage_blocked = amount
            result.blocked_by_ignoble = True

            is_golden = target.get('golden', False)
            golden_prefix = "💎 Golden " if is_golden else ""
            result.logs.append(
                f"🛡️ {golden_prefix}{target['name']}'s Ignoble blocks {amount} {damage_type.value} damage!"
            )

            # Track the event even if blocked
            self._track_damage_event(target, 0, damage_type, source_minion, blocked=True, block_type='ignoble')

            # No damage applied means no on_damage triggers
            return result

        # Damage is not blocked by nobility or ignoble - apply it
        target_health_before = target.get('health', 0)

        # Check for obliterate (instant kill if source has obliterate keyword)
        from keywords import has_keyword
        obliterate_triggered = False

        if source_minion and has_keyword(source_minion, 'obliterate'):
            # Obliterate: instant kill regardless of damage amount
            target['health'] = 0
            result.damage_applied = target_health_before  # Count full health as damage dealt
            result.obliterate_kill = True
            obliterate_triggered = True

            # Generate obliterate log
            is_golden_source = source_minion.get('golden', False)
            golden_source_prefix = "💎 Golden " if is_golden_source else ""
            is_golden_target = target.get('golden', False)
            golden_target_prefix = "💎 Golden " if is_golden_target else ""

            result.logs.append(
                f"💀⚡ Obliterate! {golden_source_prefix}{source_minion['name']} destroys {golden_target_prefix}{target['name']} instantly!"
            )

            logger.debug(f"[DAMAGE HANDLER] OBLITERATE: {source_minion.get('name')} obliterates {target.get('name')} (would have taken {amount} damage, destroyed instead)")
        else:
            # Normal damage application
            target['health'] -= amount
            result.damage_applied = amount

        target_health_after = target.get('health', 0)
        result.target_killed = (target_health_after <= 0 and target_health_before > 0)

        # Track the damage event
        self._track_damage_event(target, result.damage_applied, damage_type, source_minion,
                                 blocked=False, obliterate=obliterate_triggered)

        # CRITICAL FIX: Use registrar to generate on_damage triggers
        # This is the registry-based approach instead of calling trigger_processor
        if result.damage_applied > 0 and context:
            registrar = context.get('registrar')
            if registrar:
                # Use registrar to automatically find and register on_damage triggers
                registrar.register_damage_triggers(
                    damaged_minion=target,
                    damage_amount=result.damage_applied,
                    damage_source=damage_type.value,
                    damage_dealer=source_minion
                )

                if target_health_after > 0:
                    logger.debug(f"[DAMAGE HANDLER] Generated on_damage trigger for {target.get('name')} (took {result.damage_applied} {damage_type.value} damage, {target_health_after} HP remaining)")
                else:
                    logger.debug(f"[DAMAGE HANDLER] Generated on_damage trigger for dying {target.get('name')} (took {result.damage_applied} {damage_type.value} damage, killed)")

        # Check for hero death replacement effects (e.g., Olimpia) - scales with power upgrades
        if result.target_killed and context:
            run = context.get('run')
            if run:
                hero_effects = run.get_hero_effects()
                if 'death_replacement' in hero_effects:
                    replacement = hero_effects['death_replacement']

                    # Check if target is a player minion
                    registry = context.get('combat_registry')
                    is_player_minion = False
                    if registry:
                        band_type = registry.get_minion_band_type(target)
                        is_player_minion = (band_type == 'player')

                    # Check if we have uses remaining (scales with power upgrades)
                    # Uses counter tracks how many times effect has been used this combat
                    combat_state = context.get('combat_state', {})
                    uses_count = combat_state.get('hero_death_replacement_count', 0)
                    base_max_uses = replacement.get('max_uses', 1)
                    max_uses = get_scaled_effect_value(hero_effects, 'death_replacement', base_max_uses)

                    if is_player_minion and uses_count < max_uses:
                        # Setup stun (don't modify health yet - do that after generating commands)
                        stun_turns = replacement.get('stun_turns', 1)
                        target['stun_count'] = stun_turns

                        # Add stun keyword if not present
                        if 'keywords' not in target:
                            target['keywords'] = []
                        if 'stun' not in target['keywords']:
                            target['keywords'].append('stun')

                        # Increment usage counter in combat_state (persists across turns)
                        combat_state['hero_death_replacement_count'] = uses_count + 1

                        # Update result
                        result.target_killed = False
                        golden_prefix = "💎 " if target.get('golden', False) else ""
                        olimpia_log = f"🦸 Hero Effect - Olimpia: {golden_prefix}{target['name']} is saved from death! Stunned for {stun_turns} turn{'s' if stun_turns > 1 else ''}."
                        # NOTE: Do NOT add olimpia_log to result.logs - it will be attached to APPLY_STUN command below

                        # CRITICAL FIX: Restore health and modify damage result
                        # The frontend is a recording - we "lie" and say no damage was dealt
                        # Calculate effective damage (difference from original to final health)
                        health_before_damage = target_health_before  # From line 140
                        desired_health = 1

                        # Restore health on backend
                        target['health'] = desired_health

                        # Modify result to show effective damage (health lost from original to final)
                        # If minion had 1 HP and ends at 1 HP, effective damage = 0
                        effective_damage = health_before_damage - desired_health
                        result.damage_applied = max(0, effective_damage)

                        logger.debug(f"[DAMAGE HANDLER] Olimpia protection: {target.get('name')} health {health_before_damage} -> {desired_health}, effective damage: {result.damage_applied}")

                        # Generate interpreter commands for frontend
                        interpreter = context.get('interpreter')
                        if interpreter:
                            # Only APPLY_STUN command - no HEAL needed
                            # The damage command will show the reduced/zero damage
                            interpreter.add_command({
                                'cmd': 'APPLY_STUN',
                                'target_id': target.get('_combat_id'),
                                'target_name': target.get('name'),
                                'stun_amount': stun_turns,
                                'source_name': 'Olimpia',
                                'log_message': olimpia_log  # Attach log to STUN command
                            })
                            logger.debug(f"[DAMAGE HANDLER] Added APPLY_STUN command for Olimpia: {stun_turns} turn(s) to {target.get('name')}")

                        # Move to back of band if requested using built-in leap effect
                        if replacement.get('leap_to_back'):
                            registry = context.get('combat_registry')
                            if registry:
                                band_type = registry.get_minion_band_type(target)
                                if band_type:
                                    if band_type == 'player':
                                        band = context.get('absolute_player_band', context.get('player_band', []))
                                    else:
                                        band = context.get('absolute_enemy_band', context.get('enemy_band', []))

                                    # Calculate distance to reach the back
                                    current_pos = target.get('position', 0)
                                    new_pos = len(band) - 1
                                    distance = new_pos - current_pos

                                    if distance > 0:
                                        # Temporarily add leap keyword so leap_move() works properly
                                        # This ensures on_any_leap triggers fire
                                        had_leap = 'leap' in target.get('keywords', [])
                                        if not had_leap:
                                            if 'keywords' not in target:
                                                target['keywords'] = []
                                            target['keywords'].append('leap')
                                            target['leap_distance'] = distance

                                        # Use built-in leap effect system
                                        from game_engine.effects.special_effects import leap_move

                                        # Create leap context with target as acting_minion
                                        # Ensure all necessary components are present for leap triggers
                                        leap_context = dict(context)
                                        leap_context['acting_minion'] = target

                                        # Explicitly ensure registrar is present for on_any_leap triggers
                                        if 'registrar' not in leap_context:
                                            leap_context['registrar'] = context.get('registrar')

                                        # Call leap_move with calculated distance
                                        leap_success, leap_logs, leap_changes = leap_move(
                                            {'distance': distance},
                                            leap_context
                                        )

                                        # Remove leap keyword if we added it temporarily
                                        if not had_leap and 'leap' in target.get('keywords', []):
                                            target['keywords'].remove('leap')
                                            if 'leap_distance' in target:
                                                del target['leap_distance']

                                        if leap_success:
                                            # NOTE: Do NOT add leap log to result.logs - it will create unwanted COMBAT_DAMAGE command
                                            logger.debug(f"[DAMAGE HANDLER] Olimpia leap successful - {target['name']} moved to position {new_pos}")

                                            # CRITICAL FIX: Generate LEAP_MOVE command for frontend
                                            if interpreter and leap_changes.get('old_position') is not None:
                                                old_pos = leap_changes.get('old_position')
                                                new_pos_actual = leap_changes.get('new_position')
                                                leap_log = f"↗️ {golden_prefix}{target['name']} leaps to the back!"
                                                interpreter.add_command({
                                                    'cmd': 'LEAP_MOVE',
                                                    'target_id': target.get('_combat_id'),
                                                    'old_position': old_pos,
                                                    'new_position': new_pos_actual,
                                                    'log_message': leap_log
                                                })
                                                logger.debug(f"[DAMAGE HANDLER] Added LEAP_MOVE command for Olimpia: {target.get('name')} from pos {old_pos} to {new_pos_actual}")
                                        else:
                                            logger.debug(f"[DAMAGE HANDLER] Olimpia leap failed for {target['name']}")

                        logger.debug(f"[DAMAGE HANDLER] Hero death replacement activated for {target.get('name')}")

        # Check for Ethereal [Last] keyword - prevents death if not the last friendly minion
        # IMPORTANT: Ethereal only works if this is the ONLY ethereal minion alive
        if result.target_killed and context:
            from keywords import has_keyword
            if has_keyword(target, 'ethereal'):
                registry = context.get('combat_registry')
                if registry:
                    band_type = registry.get_minion_band_type(target)
                    if band_type:
                        # Get the appropriate band
                        if band_type == 'player':
                            band = context.get('absolute_player_band', context.get('player_band', []))
                        else:
                            band = context.get('absolute_enemy_band', context.get('enemy_band', []))

                        # Count other alive minions (excluding the dying one)
                        other_alive = [m for m in band if m.get('health', 0) > 0 and m.get('_combat_id') != target.get('_combat_id')]
                        alive_count = len(other_alive)

                        # Count other ETHEREAL minions alive - Ethereal only works if this is the only one
                        other_ethereal_count = sum(1 for m in other_alive if has_keyword(m, 'ethereal'))

                        logger.debug(f"[DAMAGE HANDLER] Ethereal check for {target.get('name')}: {alive_count} other minions alive, {other_ethereal_count} other ethereal")

                        # Ethereal fails if there are other ethereal minions alive
                        if other_ethereal_count > 0:
                            logger.debug(f"[DAMAGE HANDLER] Ethereal [Last] failed for {target.get('name')}: other ethereal minions exist")
                        # Only save if there are other (non-ethereal) minions alive and no other ethereal
                        elif alive_count > 0:
                            # Save the minion at 1 health
                            health_before = target_health_before
                            target['health'] = 1

                            # Update result
                            result.target_killed = False
                            effective_damage = health_before - 1
                            result.damage_applied = max(0, effective_damage)

                            golden_prefix = "💎 " if target.get('golden', False) else ""
                            ethereal_log = f"✨ Ethereal: {golden_prefix}{target['name']} is saved from death! (not the last minion)"
                            result.logs.append(ethereal_log)

                            logger.debug(f"[DAMAGE HANDLER] Ethereal [Last] activated for {target.get('name')}: health {health_before} -> 1")

                            # Generate interpreter command for frontend
                            interpreter = context.get('interpreter')
                            if interpreter:
                                interpreter.add_command({
                                    'cmd': 'ETHEREAL_SAVE',
                                    'target_id': target.get('_combat_id'),
                                    'target_name': target.get('name'),
                                    'new_health': 1,
                                    'log_message': ethereal_log
                                })
                        else:
                            logger.debug(f"[DAMAGE HANDLER] Ethereal [Last] failed for {target.get('name')}: is the last minion alive")

            # Check for Ethereal [Left] keyword - prevents death unless in leftmost slot or last minion
            # Like regular ethereal, but can only die if at the leftmost position or is the last minion alive
            elif has_keyword(target, 'ethereal_left'):
                registry = context.get('combat_registry')
                if registry:
                    band_type = registry.get_minion_band_type(target)
                    if band_type:
                        # Get the appropriate band
                        if band_type == 'player':
                            band = context.get('absolute_player_band', context.get('player_band', []))
                        else:
                            band = context.get('absolute_enemy_band', context.get('enemy_band', []))

                        target_position = target.get('position', 0)

                        # Count other alive minions (excluding self)
                        other_alive = [m for m in band if m.get('health', 0) > 0
                                      and m.get('_combat_id') != target.get('_combat_id')]
                        is_last_minion = len(other_alive) == 0

                        # Find the leftmost position among alive minions (including self before death)
                        alive_positions = [m.get('position', 0) for m in band
                                          if m.get('health', 0) > 0 or m.get('_combat_id') == target.get('_combat_id')]
                        leftmost_position = min(alive_positions) if alive_positions else 0
                        is_leftmost = target_position == leftmost_position

                        logger.debug(f"[DAMAGE HANDLER] Ethereal [Left] check for {target.get('name')} at pos {target_position}: leftmost={is_leftmost}, last_minion={is_last_minion}")

                        # Can only die if leftmost OR last minion alive
                        # Save if NOT leftmost AND NOT last minion
                        if not is_leftmost and not is_last_minion:
                            # Save the minion at 1 health
                            health_before = target_health_before
                            target['health'] = 1

                            # Update result
                            result.target_killed = False
                            effective_damage = health_before - 1
                            result.damage_applied = max(0, effective_damage)

                            golden_prefix = "💎 " if target.get('golden', False) else ""
                            ethereal_log = f"✨ Ethereal: {golden_prefix}{target['name']} is saved from death! (not leftmost)"
                            result.logs.append(ethereal_log)

                            logger.debug(f"[DAMAGE HANDLER] Ethereal [Left] activated for {target.get('name')}: health {health_before} -> 1")

                            # Generate interpreter command for frontend
                            interpreter = context.get('interpreter')
                            if interpreter:
                                interpreter.add_command({
                                    'cmd': 'ETHEREAL_SAVE',
                                    'target_id': target.get('_combat_id'),
                                    'target_name': target.get('name'),
                                    'new_health': 1,
                                    'log_message': ethereal_log
                                })
                        else:
                            reason = "leftmost slot" if is_leftmost else "last minion"
                            logger.debug(f"[DAMAGE HANDLER] Ethereal [Left] failed for {target.get('name')}: is {reason}")

        return result

    def _check_nobility_block(self, target: Dict, damage_type: DamageType) -> bool:
        """
        Check if nobility blocks this damage

        Nobility blocks:
        - Spell damage
        - Ability damage (assault, death toll, rage)
        - Effect damage
        - AOE damage

        Nobility does NOT block:
        - Combat damage (attacks)
        - Counter damage
        - Fatigue damage

        NOTE: If nobility blocks damage, obliterate does not trigger
        (because no damage is dealt)
        """
        from keywords import has_nobility

        if not has_nobility(target):
            return False

        # Nobility blocks non-combat damage
        blocked_types = [
            DamageType.SPELL,
            DamageType.ABILITY,
            DamageType.EFFECT,
            DamageType.AOE
        ]

        return damage_type in blocked_types

    def _check_ignoble_block(self, target: Dict, damage_type: DamageType) -> bool:
        """
        Check if ignoble blocks this damage

        Ignoble blocks:
        - Combat damage (attacks)
        - Counter damage

        Ignoble does NOT block:
        - Spell damage
        - Ability damage (assault, death toll, rage)
        - Effect damage
        - AOE damage
        - Fatigue damage

        This is the opposite of nobility.
        """
        from keywords import has_keyword

        if not has_keyword(target, 'ignoble'):
            return False

        # Ignoble blocks combat damage
        blocked_types = [
            DamageType.COMBAT,
            DamageType.COUNTER
        ]

        return damage_type in blocked_types

    def _track_damage_event(self, target: Dict, amount: int, damage_type: DamageType,
                            source_minion: Optional[Dict], blocked: bool,
                            block_type: Optional[str] = None, obliterate: bool = False):
        """
        Track a damage event for statistics and future trigger generation

        Args:
            target: Minion taking damage
            amount: Damage amount
            damage_type: Type of damage
            source_minion: Source of damage
            blocked: Whether damage was blocked
            block_type: Type of block ('nobility' or 'ignoble')
            obliterate: Whether this was an obliterate kill
        """
        event = {
            'target': target,
            'target_name': target.get('name'),
            'target_id': target.get('_combat_id'),
            'amount': amount,
            'damage_type': damage_type.value,
            'source': source_minion,
            'source_name': source_minion.get('name') if source_minion else None,
            'source_id': source_minion.get('_combat_id') if source_minion else None,
            'blocked': blocked,
            'block_type': block_type,
            'obliterate': obliterate,
            'killed': target.get('health', 0) <= 0
        }

        self.damage_events.append(event)

        # Debug logging
        if blocked:
            block_reason = f"{block_type}" if block_type else "unknown"
            logger.debug(f"[DAMAGE] {amount} {damage_type.value} damage BLOCKED by {target.get('name')}'s {block_reason}")
        elif obliterate:
            logger.debug(f"[DAMAGE] {amount} {damage_type.value} damage → OBLITERATE KILL on {target.get('name')}" +
                  (f" by {source_minion.get('name')}" if source_minion else ""))
        else:
            logger.debug(f"[DAMAGE] {amount} {damage_type.value} damage dealt to {target.get('name')}" +
                  (f" by {source_minion.get('name')}" if source_minion else ""))

    def get_damage_statistics(self) -> Dict:
        """Get statistics about damage dealt this combat"""
        return {
            'total_events': len(self.damage_events),
            'total_damage': sum(e['amount'] for e in self.damage_events if not e['blocked']),
            'total_blocked': sum(e['amount'] for e in self.damage_events if e['blocked']),
            'kills': sum(1 for e in self.damage_events if e['killed']),
            'obliterate_kills': sum(1 for e in self.damage_events if e.get('obliterate', False)),
            'nobility_blocks': sum(1 for e in self.damage_events if e.get('block_type') == 'nobility'),
            'ignoble_blocks': sum(1 for e in self.damage_events if e.get('block_type') == 'ignoble'),
            'by_type': self._group_by_type()
        }

    def _group_by_type(self) -> Dict:
        """Group damage events by type"""
        by_type = {}
        for event in self.damage_events:
            dtype = event['damage_type']
            if dtype not in by_type:
                by_type[dtype] = {'count': 0, 'damage': 0, 'blocked': 0, 'obliterates': 0}

            by_type[dtype]['count'] += 1
            if event['blocked']:
                by_type[dtype]['blocked'] += event['amount']
            else:
                by_type[dtype]['damage'] += event['amount']

            if event.get('obliterate', False):
                by_type[dtype]['obliterates'] += 1

        return by_type

    def reset(self):
        """Reset the handler for a new combat"""
        self.damage_events = []


# Global damage handler instance
_damage_handler = DamageHandler()


def get_damage_handler() -> DamageHandler:
    """Get the global damage handler instance"""
    return _damage_handler


def apply_damage(target: Dict,
                 amount: int,
                 damage_type: DamageType,
                 source_minion: Optional[Dict] = None,
                 context: Optional[Dict] = None) -> DamageResult:
    """
    Convenience function to apply damage through the global handler

    This is the primary API for applying damage throughout the codebase.

    Args:
        target: The minion taking damage
        amount: Amount of damage to apply
        damage_type: Type of damage (combat, spell, etc.)
        source_minion: The minion dealing damage (if any)
        context: Combat context for additional information

    Returns:
        DamageResult with details about what happened
    """
    return _damage_handler.apply_damage(target, amount, damage_type, source_minion, context)


def reset_damage_handler():
    """Reset the damage handler for a new combat"""
    _damage_handler.reset()


def get_damage_statistics() -> Dict:
    """Get statistics about damage dealt this combat"""
    return _damage_handler.get_damage_statistics()