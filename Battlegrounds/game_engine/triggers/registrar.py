"""
Trigger Registrar - Automatically registers triggers when events occur

Replaces all manual trigger registration code.
When an event happens (attack, summon, death), this system:
1. Finds all minions with relevant triggers from registry
2. Checks their conditions
3. Registers them to the trigger queue

NO MORE HARDCODED TRIGGER CHECKS!

FIXED: Handles triggers without keywords that check for effect fields only
NEW: Added register_leap_triggers for on_any_leap trigger (Railway Signal)
NEW: Added 'fast' keyword support for start_of_combat attacks (Thunderbird)
NEW: Added register_combat_damage_triggers for combat keywords (poke, obliterate, cleave)
"""

import logging

logger = logging.getLogger(__name__)

from typing import Dict, List, Optional
from .trigger_registry import get_all_triggers_for_event, TriggerEvent, TRIGGER_REGISTRY
from .condition_checker import ConditionChecker
from game_engine.trigger_queue import TriggerQueue, TriggerPriority
from keywords import has_keyword


class TriggerRegistrar:
    """
    Automatically registers triggers based on events

    This is the magic that makes the registry system work!
    """

    def __init__(self, trigger_queue: TriggerQueue, combat_registry):
        """
        Args:
            trigger_queue: Queue to add triggers to
            combat_registry: Registry to find minions
        """
        self.trigger_queue = trigger_queue
        self.combat_registry = combat_registry
        self.condition_checker = ConditionChecker()

    def register_triggers_for_event(self, event: TriggerEvent, event_data: Dict):
        """
        Find and register ALL triggers that fire on this event

        This ONE method replaces all the manual trigger registration!

        Args:
            event: The event that occurred
            event_data: Context data for the event
        """
        # Get all trigger definitions for this event
        trigger_definitions = get_all_triggers_for_event(event)

        if not trigger_definitions:
            return

        logger.debug(f"[REGISTRAR] Event {event.value}: checking {len(trigger_definitions)} trigger types")

        for trigger_type, definition in trigger_definitions.items():
            self._maybe_register_trigger(trigger_type, definition, event_data)

    def _maybe_register_trigger(self, trigger_type: str, definition: Dict, event_data: Dict):
        """
        Check if a trigger should be registered and register it

        Args:
            trigger_type: Type of trigger (e.g., 'assault')
            definition: Trigger definition from registry
            event_data: Event context
        """
        is_watcher = definition.get('is_watcher', False)

        if is_watcher:
            # Watcher triggers - look at ALL minions
            self._register_watcher_triggers(trigger_type, definition, event_data)
        else:
            # Self triggers - only check the acting minion
            self._register_self_trigger(trigger_type, definition, event_data)

    def _register_self_trigger(self, trigger_type: str, definition: Dict, event_data: Dict):
        """
        Register a self-trigger (assault, cast, death_toll, start_of_combat, combat keywords, etc.)

        These fire on the minion's own actions.

        FIXED: Handles triggers that check effect field instead of keyword
        FIXED: For start_of_combat, checks both effect field AND keywords that grant it
        NEW: Handles combat keywords with default_effect fallback
        """
        # For self triggers, the source minion is usually the 'attacker' or 'dying_minion'
        source_minion = self._get_source_minion_for_trigger(trigger_type, event_data)

        if not source_minion:
            return

        # Get effect field for this trigger
        effect_field = definition['effect_field']

        # FIXED: Check if this trigger requires effect field instead of keyword
        requires_effect_field = definition.get('requires_effect_field', False)

        if requires_effect_field:
            # For effect field triggers (like start_of_combat), we need to:
            # 1. Check if minion has the effect field directly
            # 2. OR check if minion has keywords that grant start_of_combat effects

            effect_data = source_minion.get(effect_field)

            if not effect_data:
                # No direct effect field - check for keywords that grant this effect
                # For start_of_combat: rich, aura, divide_attack, fast grant start_of_combat effects

                if trigger_type == 'start_of_combat':
                    # Check for keywords that have start_of_combat effects
                    keywords_with_start_effects = ['rich', 'aura', 'divide_attack', 'fast', 'ring']

                    has_start_keyword = False
                    for kw in keywords_with_start_effects:
                        if has_keyword(source_minion, kw):
                            has_start_keyword = True
                            logger.debug(f"[REGISTRAR] {source_minion.get('name')} has '{kw}' keyword which grants start_of_combat effect")

                            # Get the effect from the keyword's definition
                            effect_data = self._get_keyword_start_of_combat_effect(source_minion, kw)
                            if effect_data:
                                break

                    if not has_start_keyword or not effect_data:
                        # No effect field and no keyword that grants it
                        return
                else:
                    # Other effect field triggers must have the field
                    return
            else:
                logger.debug(f"[REGISTRAR] {source_minion.get('name')} has {effect_field} field directly")
        else:
            # Normal keyword check
            keyword = definition.get('keyword')
            if not keyword:
                logger.error(f"[REGISTRAR ERROR] Trigger {trigger_type} has no keyword and no requires_effect_field flag")
                return

            if not has_keyword(source_minion, keyword):
                return

            # Get effect data - check for explicit effect field OR use default_effect
            effect_data = source_minion.get(effect_field)

            if not effect_data:
                # NEW: Check if trigger has a default_effect (for combat keywords)
                effect_data = definition.get('default_effect')

                if not effect_data:
                    logger.debug(f"[REGISTRAR] {source_minion.get('name')} has keyword but no {effect_field} and no default_effect")
                    return
                else:
                    logger.debug(f"[REGISTRAR] {source_minion.get('name')} using default_effect for {trigger_type}")

        # Check conditions
        conditions = definition.get('conditions', [])
        if not self.condition_checker.check_all_conditions(conditions, source_minion, event_data):
            logger.debug(f"[REGISTRAR] {source_minion.get('name')} has {trigger_type} but conditions not met")
            return

        # Create trigger data
        trigger_data = {
            'type': trigger_type,
            'source_minion': source_minion,
            'effect_data': effect_data,
            'event_data': event_data
        }

        # Add to queue with priority from definition
        priority = getattr(TriggerPriority, definition['priority'])
        self.trigger_queue.add_trigger(trigger_data, priority)

        logger.debug(f"[REGISTRAR] Registered {trigger_type} for {source_minion.get('name')}")

    def _get_keyword_start_of_combat_effect(self, minion: Dict, keyword: str) -> Optional[Dict]:
        """
        Get the start_of_combat effect for a keyword

        This builds the effect data for keywords that grant start_of_combat effects

        NEW: Added 'fast' keyword support - grants attack_target effect at start of combat
        """
        if keyword == 'rich':
            return {
                'type': 'rich_buff',
                'target': 'self'
            }
        elif keyword == 'aura':
            # Aura effects are in minion.aura_effect
            return minion.get('aura_effect')
        elif keyword == 'divide_attack':
            return {
                'type': 'divide_attack',
                'target': 'self',
                'divisor': minion.get('divide_by', 3)
            }
        elif keyword == 'fast':
            # NEW: Fast keyword - attack at start of combat
            return {
                'type': 'attack_target',
                'attacker': 'self',
                'target_minion': None  # Auto-target using normal combat targeting
            }
        elif keyword == 'ring':
            # Ring keyword - trigger 1 death toll, reduce count, then remove if exhausted
            # The count determines how many COMBATS Ring lasts, not how many triggers per combat
            return [
                {
                    'type': 'trigger_death_toll',
                    'target': 'all_allies',
                    'exclude_self': False  # Ring CAN trigger its own death toll
                },
                {
                    'type': 'reduce_ring',
                    'target': 'self'
                },
                {
                    # Always call remove_keyword, but it only removes if count is 0
                    'type': 'remove_keyword',
                    'target': 'self',
                    'keyword': 'ring',
                    'scope': 'both',
                    'only_if_zero': True  # Only remove if permanent_ring_count is 0
                }
            ]

        return None

    def _register_watcher_triggers(self, trigger_type: str, definition: Dict, event_data: Dict):
        """
        Register watcher triggers (rage, on_any_death, on_any_cast, on_any_leap, etc.)

        These watch events from OTHER minions.
        """
        # Get all alive minions
        all_minions = self._get_all_alive_minions()

        keyword = definition.get('keyword')
        if not keyword:
            return

        effect_field = definition['effect_field']
        conditions = definition.get('conditions', [])
        exclude_self = definition.get('exclude_self', False)

        # Check each minion to see if it has this watcher
        for minion in all_minions:
            # Skip if doesn't have keyword
            if not has_keyword(minion, keyword):
                continue

            # Skip if should exclude self and this is the acting minion
            if exclude_self:
                acting_minion = self._get_source_minion_for_trigger(trigger_type, event_data)
                if acting_minion and minion == acting_minion:
                    continue

            # Skip if doesn't have effect
            effect_data = minion.get(effect_field)
            if not effect_data:
                continue

            # Check conditions
            if not self.condition_checker.check_all_conditions(conditions, minion, event_data):
                continue

            # Register the trigger
            trigger_data = {
                'type': trigger_type,
                'source_minion': minion,
                'effect_data': effect_data,
                'event_data': event_data
            }

            # Add to queue
            priority = getattr(TriggerPriority, definition['priority'])
            self.trigger_queue.add_trigger(trigger_data, priority)

            logger.debug(f"[REGISTRAR] Registered {trigger_type} for {minion.get('name')} (watcher)")

    def _get_source_minion_for_trigger(self, trigger_type: str, event_data: Dict) -> Optional[Dict]:
        """
        Get the source minion for a trigger based on trigger type

        Different triggers have different source minion locations in event_data
        """
        source_map = {
            'assault': 'attacker',
            'cast': 'attacker',
            'death_toll': 'dying_minion',
            'start_of_combat': 'minion',
            'on_damage': 'damaged_minion',
            'rage': 'attacker',  # For exclusion check
            'combat_poke': 'attacker',
            'combat_obliterate': 'attacker',
            'combat_cleave': 'attacker'
        }

        key = source_map.get(trigger_type)
        return event_data.get(key) if key else None

    def _get_all_alive_minions(self) -> List[Dict]:
        """Get all alive minions from both bands"""
        if not self.combat_registry:
            return []

        player_minions = self.combat_registry.get_band_minions('player', alive_only=True)
        enemy_minions = self.combat_registry.get_band_minions('enemy', alive_only=True)

        return player_minions + enemy_minions

    # ===== CONVENIENCE METHODS FOR COMMON EVENTS =====

    def register_attack_triggers(self, attacker: Dict, defender: Dict):
        """
        Register triggers for attack events

        Finds: assault, cast, rage

        Args:
            attacker: Attacking minion
            defender: Defending minion
        """
        event_data = {
            'attacker': attacker,
            'defender': defender
        }

        self.register_triggers_for_event(TriggerEvent.ON_ATTACK_START, event_data)

    def register_death_triggers(self, dying_minion: Dict):
        """
        Register triggers for death events

        Finds: death_toll, on_any_death

        Args:
            dying_minion: Minion that died
        """
        event_data = {
            'dying_minion': dying_minion
        }

        self.register_triggers_for_event(TriggerEvent.ON_DEATH, event_data)
        self.register_triggers_for_event(TriggerEvent.ON_ANY_DEATH, event_data)

    def register_summon_triggers(self, summoner: Dict, summoned_minion: Dict):
        """
        Register triggers for summon events

        Finds: on_any_summon

        Args:
            summoner: Minion that summoned
            summoned_minion: Minion that was summoned
        """
        event_data = {
            'summoner': summoner,
            'summoned_minion': summoned_minion
        }

        self.register_triggers_for_event(TriggerEvent.ON_ANY_SUMMON, event_data)

    def register_spell_cast_triggers(self, caster: Dict, spell_target: Optional[Dict] = None):
        """
        Register triggers for spell cast events

        Finds: on_any_cast

        Args:
            caster: Minion casting the spell
            spell_target: Target of the spell (if any)
        """
        event_data = {
            'caster': caster,
            'spell_target': spell_target
        }

        self.register_triggers_for_event(TriggerEvent.ON_ANY_CAST, event_data)

    def register_leap_triggers(self, leaping_minion: Dict, minions_jumped: int = 0,
                               starting_position: int = 0, ending_position: int = 0):
        """
        Register triggers for leap events

        Finds: on_any_leap (Railway Signal, Frog Prince)

        NEW: Added for leap movement detection
        UPDATED: Now passes minions_jumped count, starting_position, and ending_position

        Args:
            leaping_minion: Minion that performed the leap
            minions_jumped: Number of minions jumped over (default 0)
            starting_position: Position before leap (default 0)
            ending_position: Position after leap (default 0)
        """
        event_data = {
            'leaping_minion': leaping_minion,
            'minions_jumped': minions_jumped,
            'starting_position': starting_position,
            'ending_position': ending_position
        }

        self.register_triggers_for_event(TriggerEvent.ON_ANY_LEAP, event_data)

    def register_death_toll_triggers(self, death_toll_minion: Dict, is_additional_trigger: bool = False):
        """
        Register triggers for death toll events

        Finds: on_any_death_toll

        Args:
            death_toll_minion: Minion whose death toll is being triggered
            is_additional_trigger: Whether this is an additional trigger (from Quasimodo)
        """
        event_data = {
            'death_toll_minion': death_toll_minion,
            'is_additional_trigger': is_additional_trigger
        }

        self.register_triggers_for_event(TriggerEvent.ON_ANY_DEATH_TOLL, event_data)

    def register_start_of_combat_triggers(self, all_minions: List[Dict]):
        """
        Register start of combat triggers for all minions

        Finds: start_of_combat (checks for effect field, not keyword)

        FIXED: Now properly checks for start_of_combat_effect field

        Args:
            all_minions: All minions in combat (in the correct alternating order)
        """
        for minion in all_minions:
            event_data = {
                'minion': minion
            }
            self.register_triggers_for_event(TriggerEvent.START_OF_COMBAT, event_data)

    def register_damage_triggers(self, damaged_minion: Dict, damage_amount: int,
                                 damage_source: str, damage_dealer: Optional[Dict] = None):
        """
        Register triggers for damage taken events

        Finds: on_damage

        Args:
            damaged_minion: Minion that took damage
            damage_amount: Amount of damage taken
            damage_source: Source of damage (combat, spell, etc.)
            damage_dealer: Minion that dealt the damage (if any)
        """
        event_data = {
            'damaged_minion': damaged_minion,
            'damage_amount': damage_amount,
            'damage_source': damage_source,
            'damage_dealer': damage_dealer
        }

        self.register_triggers_for_event(TriggerEvent.ON_DAMAGE, event_data)

    def register_adjacent_transform_triggers(self, transformer: Dict, transformed_minion: Dict):
        """
        Register triggers for adjacent transformation events

        Finds: on_adjacent_transform

        Args:
            transformer: Minion that caused the transformation
            transformed_minion: Minion that was transformed
        """
        event_data = {
            'transformer': transformer,
            'transformed_minion': transformed_minion
        }

        self.register_triggers_for_event(TriggerEvent.ON_ADJACENT_TRANSFORM, event_data)

    def register_combat_damage_triggers(self, attacker: Dict, defender: Dict):
        """
        Register PRE-DAMAGE combat keyword triggers (poke, obliterate)

        These fire BEFORE main damage calculation to set flags.

        Args:
            attacker: Attacking minion
            defender: Defending minion
        """
        event_data = {
            'attacker': attacker,
            'defender': defender
        }

        self.register_triggers_for_event(TriggerEvent.ON_COMBAT_DAMAGE_DECLARE, event_data)

    def register_post_damage_triggers(self, attacker: Dict, defender: Dict):
        """
        Register POST-DAMAGE combat keyword triggers (cleave)

        These fire AFTER main damage to handle secondary effects.

        Args:
            attacker: Attacking minion
            defender: Defending minion (who just took damage)
        """
        event_data = {
            'attacker': attacker,
            'defender': defender
        }

        self.register_triggers_for_event(TriggerEvent.AFTER_COMBAT_DAMAGE, event_data)