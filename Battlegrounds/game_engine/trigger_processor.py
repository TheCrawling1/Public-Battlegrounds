"""
Trigger Processor - Orchestrates trigger resolution with full context tracking

UPDATED: Now uses registry-driven generic processor for all trigger types.
FIXED: Death commands now include log messages!
"""

import logging

logger = logging.getLogger(__name__)

from typing import Dict, List, Optional, Tuple, Any
from game_engine.trigger_queue import TriggerQueue, TriggerPriority
from game_engine.combat_context import CombatContextManager, EffectType, DamageSource, EffectContext
from game_engine.events.combat_events import CombatEventSystem, CombatEventType
from game_engine.combat_interpreter import CombatCommand
from game_random import game_random, SelectionType
from keywords import has_keyword

# NEW: Import from triggers package
from game_engine.triggers import GenericTriggerProcessor, TriggerRegistrar, TriggerEvent


class TriggerProcessor:
    """
    Main processor for combat triggers

    UPDATED: Now delegates to generic processor for all trigger processing.
    Custom logic is only for queue management and death checking.
    FIXED: Death commands now include log messages!
    """

    def __init__(self):
        self.trigger_queue = TriggerQueue()
        self.context_manager = CombatContextManager()
        self.event_system = CombatEventSystem()
        self.max_death_check_cycles = 50

        # Generic processor handles all trigger types
        self.generic_processor = None  # Initialized in initialize_combat
        self.registrar = None  # Initialized in initialize_combat

        # Dev mode settings
        self.dev_mode_enabled = False
        self.pause_on_trigger = False
        self.pause_on_effect = False

        # Effect tracking for cohesive display
        self.current_trigger_source = None
        self.current_trigger_type = None

    def initialize_combat(self, combat_state: Dict, player_band: List[Dict],
                          enemy_band: List[Dict], registry=None, run=None):
        """
        Initialize the processor for a new combat

        UNCHANGED: Initialization remains the same
        """
        self.context_manager.initialize_combat(
            combat_state, player_band, enemy_band, registry, run
        )

        # Register standard listeners for all minions
        for minion in player_band + enemy_band:
            self.event_system.register_standard_listeners(minion)

        # Initialize registry system components
        interpreter = combat_state.get('interpreter') if combat_state else None
        self.registrar = TriggerRegistrar(self.trigger_queue, registry)

        # Pass registrar to generic processor
        # GenericProcessor will automatically add it to all contexts
        self.generic_processor = GenericTriggerProcessor(
            self.context_manager,
            interpreter,
            registrar=self.registrar
        )

        # Add initial aura recalculation trigger at combat start
        self.trigger_queue.add_trigger({
            'type': 'aura_recalculation',
            'reason': 'combat_start'
        }, TriggerPriority.IMMEDIATE)

    def enable_dev_mode(self, pause_on_trigger: bool = True,
                       pause_on_effect: bool = False):
        """Enable dev mode with interception points"""
        self.dev_mode_enabled = True
        self.pause_on_trigger = pause_on_trigger
        self.pause_on_effect = pause_on_effect

        # Enable queue interception
        if pause_on_trigger:
            self.trigger_queue.enable_dev_mode_interception()

        logger.debug("[PROCESSOR] Dev mode enabled")

    def disable_dev_mode(self):
        """Disable dev mode"""
        self.dev_mode_enabled = False
        self.pause_on_trigger = False
        self.pause_on_effect = False
        self.trigger_queue.disable_dev_mode_interception()
        logger.debug("[PROCESSOR] Dev mode disabled")

    def generate_on_damage_trigger(self, damaged_minion: Dict, damage_amount: int,
                                   damage_source: str = 'unknown',
                                   damage_dealer: Optional[Dict] = None):
        """
        Generate an on_damage trigger for a minion that just took damage

        Uses registrar to automatically find and register on_damage triggers.
        """
        # Use registrar instead of manual registration
        self.registrar.register_damage_triggers(
            damaged_minion,
            damage_amount,
            damage_source,
            damage_dealer
        )

    def resolve_all_triggers(self, cast_used: Optional[List[bool]] = None) -> List[str]:
        """
        Resolve all triggers in the queue until empty and no deaths

        This is the main entry point for trigger resolution.

        Args:
            cast_used: Optional list containing boolean for cast usage

        Returns:
            List of log entries from all resolutions
        """
        all_logs = []
        death_check_count = 0

        while death_check_count < self.max_death_check_cycles:
            # Phase 1: Process all triggers currently in queue
            if self.trigger_queue.has_triggers():
                cycle_logs = self._process_trigger_cycle(cast_used)
                all_logs.extend(cycle_logs)
                continue

            # Phase 2: Check for any remaining unprocessed deaths
            death_occurred, death_logs, death_triggers = self._check_deaths_and_generate_triggers()
            all_logs.extend(death_logs)

            # Phase 3: Add death triggers to queue
            for trigger in death_triggers:
                priority = TriggerPriority.get_priority_for_type(trigger.get('type'))
                self.trigger_queue.add_trigger(trigger, priority)

            # Phase 4: Check if we're done
            if not death_occurred and not self.trigger_queue.has_triggers():
                break

            death_check_count += 1

        if death_check_count >= self.max_death_check_cycles:
            all_logs.append("⚠️ Maximum trigger iterations reached - stopping to prevent infinite loop")

        return all_logs

    def _check_and_queue_deaths(self) -> List[str]:
        """
        Check for any minions that have died and queue death triggers for them

        Uses registrar to automatically find and register death triggers.
        """
        logs = []
        registry = self.context_manager.combat_registry

        if not registry:
            return logs

        # Get all minions
        all_minions = registry.get_band_minions('player', alive_only=False) + \
                     registry.get_band_minions('enemy', alive_only=False)

        for minion in all_minions:
            # Check if minion is dead but not yet processed AND not already queued
            if (minion.get('health', 0) <= 0 and
                not minion.get('_death_processed', False) and
                not minion.get('_death_queued', False)):

                # Queue a death trigger for this minion
                death_trigger = {
                    'type': 'process_death',
                    'dying_minion': minion
                }

                # Add with DEATH priority (highest)
                self.trigger_queue.add_trigger(death_trigger, TriggerPriority.DEATH)

                # Mark that we've queued death processing for this minion
                minion['_death_queued'] = True

                logger.debug(f"[PROCESSOR] Queued death trigger for {minion['name']}")

        return logs

    def _process_trigger_cycle(self, cast_used: Optional[List[bool]] = None) -> List[str]:
        """
        Process one cycle through all queued triggers

        UPDATED: Now uses standard context component passing.
        Generic processor will automatically enrich context with these components.

        Returns:
            List of log entries from this cycle
        """
        cycle_logs = []

        while self.trigger_queue.has_triggers():
            # Check for dev mode interception
            if self.dev_mode_enabled and self.pause_on_trigger:
                trigger_data = self.trigger_queue.get_next_trigger()
                if trigger_data is None:
                    # Trigger was intercepted, wait for manual resolution
                    break
            else:
                trigger_data = self.trigger_queue.get_next_trigger()

            if trigger_data:
                # ===== STANDARD CONTEXT COMPONENT PASSING =====
                # Add components needed for nested effects
                # GenericProcessor will automatically add these to effect contexts
                self._enrich_trigger_data(trigger_data)

                # Process the trigger
                success, logs, changes = self._process_single_trigger(trigger_data, cast_used)
                cycle_logs.extend(logs)

                # After processing any trigger, check for deaths
                self._check_and_queue_deaths()

                # Check if summons occurred and generate on_any_summon triggers
                if changes.get('summon_occurred'):
                    # Add aura recalculation trigger first (IMMEDIATE priority)
                    self.trigger_queue.add_trigger({
                        'type': 'aura_recalculation',
                        'reason': 'summon'
                    }, TriggerPriority.IMMEDIATE)

                    # Use registrar to find on_any_summon watchers
                    summoned_minions = changes.get('summoned_minions', [])
                    summoner = changes.get('summoner')

                    if summoned_minions and summoner:
                        for summoned_minion in summoned_minions:
                            self.registrar.register_summon_triggers(summoner, summoned_minion)

                # Check if position changed (from move_minion effect)
                if changes.get('position_changed'):
                    # Add aura recalculation trigger for position change
                    self.trigger_queue.add_trigger({
                        'type': 'aura_recalculation',
                        'reason': 'position_change'
                    }, TriggerPriority.IMMEDIATE)

        return cycle_logs

    def _process_single_trigger(self, trigger_data: Dict,
                               cast_used: Optional[List[bool]] = None) -> Tuple[bool, List[str], Dict]:
        """
        Process a single trigger

        NEW: Uses generic processor for all standard triggers.
        Only special triggers (death processing, aura recalc) use custom logic.

        Returns:
            Tuple of (success, log_entries, changes)
        """
        trigger_type = trigger_data.get('type')

        # Set current trigger context for effect tracking
        source_minion = trigger_data.get('source_minion')
        self.current_trigger_source = source_minion
        self.current_trigger_type = trigger_type

        # SPECIAL TRIGGERS: Handle with custom logic
        if trigger_type == 'process_death':
            result = self._process_death_trigger(trigger_data)
            self._clear_trigger_context()
            return result

        if trigger_type == 'aura_recalculation':
            result = self._process_aura_recalculation_trigger(trigger_data)
            self._clear_trigger_context()
            return result

        if trigger_type == 'individual_summon':
            result = self._process_individual_summon_trigger(trigger_data)
            self._clear_trigger_context()
            return result

        # STANDARD TRIGGERS: Use generic processor
        # This handles: assault, cast, death_toll, rage, on_any_death, on_any_cast,
        #               on_any_summon, start_of_combat, on_damage, on_adjacent_transform

        logger.debug(f"[PROCESSOR] Delegating {trigger_type} to generic processor")

        try:
            result = self.generic_processor.process_trigger(trigger_data)

            # Special handling for cast triggers - mark cast as used
            if trigger_type == 'cast' and cast_used is not None:
                cast_used[0] = True

            # Special handling for cast - generate on_any_cast watchers
            if trigger_type == 'cast':
                result = self._handle_post_cast(trigger_data, result)

            return result

        finally:
            self._clear_trigger_context()

    def _handle_post_cast(self, trigger_data: Dict,
                         result: Tuple[bool, List[str], Dict]) -> Tuple[bool, List[str], Dict]:
        """
        Handle post-cast logic (on_any_cast watchers)

        Args:
            trigger_data: Original cast trigger data
            result: Result from processing the cast

        Returns:
            Modified result with on_any_cast logs appended
        """
        success, logs, changes = result

        if not success:
            return result

        # Get the caster and spell target
        caster = trigger_data.get('source_minion')
        spell_target = changes.get('targets', [None])[0] if changes.get('targets') else None

        # Use registrar to find on_any_cast watchers
        self.registrar.register_spell_cast_triggers(caster, spell_target)

        # Count how many watchers were registered
        watcher_count = 0
        # Peek at queue to count on_any_cast triggers
        queue_state = self.trigger_queue.get_queue_state()
        for trigger in queue_state.get('triggers', []):
            if trigger.get('type') == 'on_any_cast':
                watcher_count += 1

        if watcher_count > 0:
            logs.append(f"📖 {watcher_count} spell watcher(s) triggered")

        return success, logs, changes

    def _clear_trigger_context(self):
        """Clear current trigger context after processing"""
        self.current_trigger_source = None
        self.current_trigger_type = None

    def _process_death_trigger(self, trigger_data: Dict) -> Tuple[bool, List[str], Dict]:
        """
        Process a death trigger - remove minion from combat and generate death toll triggers

        This is a special trigger that handles death mechanics, not a standard keyword trigger.
        FIXED: Now attaches log message to DEATH command!
        """
        dying_minion = trigger_data.get('dying_minion')

        if not dying_minion:
            return False, ["[ERROR] No dying minion in death trigger"], {}

        # GUARD: Skip if already processed
        if dying_minion.get('_death_processed', False):
            logger.debug(f"[PROCESSOR] Skipping already processed death for {dying_minion['name']}")
            return True, [], {}

        # Mark as death processed to avoid duplicate processing
        dying_minion['_death_processed'] = True

        logs = []
        registry = self.context_manager.combat_registry

        if not registry:
            return False, ["[ERROR] No combat registry for death processing"], {}

        # Get band type before removal
        band_type = registry.get_minion_band_type(dying_minion)

        logger.debug(f"[PROCESSOR] Processing death of {dying_minion['name']} (band: {band_type})")

        # Capture dying minion metadata BEFORE removing from band
        dying_minion_metadata = {
            'name': dying_minion.get('name'),
            'band_type': band_type,
            'band_id': dying_minion.get('band_id'),
            'type': dying_minion.get('type'),
            '_combat_id': dying_minion.get('_combat_id'),
            'golden': dying_minion.get('golden', False)
        }

        # Generate death log
        death_log = f"💀 {dying_minion['name']} is defeated!"

        # FIXED: Add death command WITH log message
        self._add_interpreter_command({
            'cmd': CombatCommand.DEATH,
            'minion_id': dying_minion.get('_combat_id'),
            'minion_name': dying_minion.get('name'),
            'band': band_type,
            'position': dying_minion.get('position', 0),
            'log_message': death_log  # ← FIXED: Attach the log!
        })

        # Emit death event
        self.event_system.emit_event(
            CombatEventType.MINION_DEATH,
            target=dying_minion
        )

        logs.append(death_log)

        # Use registrar to generate death triggers
        # NEW
        self.registrar.register_death_triggers(dying_minion)

        # Now remove the minion from its band and fix positions
        position = dying_minion.get('position', 0)

        if band_type == 'player':
            player_band = self.context_manager.player_band
            if dying_minion in player_band:
                position = player_band.index(dying_minion)
                player_band.remove(dying_minion)
                self._fix_band_positions(player_band)
                logger.debug(f"[PROCESSOR] Removed {dying_minion['name']} from player band at position {position}")

        elif band_type == 'enemy':
            enemy_band = self.context_manager.enemy_band
            if dying_minion in enemy_band:
                position = enemy_band.index(dying_minion)
                enemy_band.remove(dying_minion)
                self._fix_band_positions(enemy_band)
                logger.debug(f"[PROCESSOR] Removed {dying_minion['name']} from enemy band at position {position}")

        # Add remove from band command to interpreter
        self._add_interpreter_command({
            'cmd': CombatCommand.REMOVE_FROM_BAND,
            'minion_id': dying_minion.get('_combat_id'),
            'minion_name': dying_minion.get('name'),
            'band': band_type,
            'position': position
        })

        # Queue aura recalculation after death
        self.trigger_queue.add_trigger({
            'type': 'aura_recalculation',
            'reason': 'death'
        }, TriggerPriority.IMMEDIATE)

        return True, logs, {
            'death_processed': True,
            'dead_minion': dying_minion
        }

    def _fix_band_positions(self, band: List[Dict]):
        """Fix position fields in a band to be sequential starting from 0"""
        for idx, minion in enumerate(band):
            old_position = minion.get('position', -1)
            minion['position'] = idx

            # Update the registry as well
            registry = self.context_manager.combat_registry
            if registry:
                registry.update_minion_position(minion, idx)

            if old_position != idx:
                logger.debug(f"[PROCESSOR] Fixed position for {minion['name']}: {old_position} -> {idx}")

    def _process_aura_recalculation_trigger(self, trigger_data: Dict) -> Tuple[bool, List[str], Dict]:
        """Process an aura recalculation trigger"""
        reason = trigger_data.get('reason', 'unknown')

        logger.debug(f"[PROCESSOR] Processing aura recalculation (reason: {reason})")

        # Add aura recalculation command to interpreter
        self._add_interpreter_command({
            'cmd': CombatCommand.AURA_RECALCULATION,
            'reason': reason
        })

        # Create context for aura recalculation
        context = self.context_manager.create_combat_context_dict()

        # Add registrar to context
        if self.registrar:
            context['registrar'] = self.registrar

        # Apply the recalculate_auras effect
        from game_engine.effects import apply_effect
        effect_data = {'type': 'recalculate_auras'}

        success, logs, changes = apply_effect(effect_data, context)

        return success, logs, changes

    def _process_individual_summon_trigger(self, trigger_data: Dict) -> Tuple[bool, List[str], Dict]:
        """
        Process an individual summon trigger

        This is used when summon_minion queues individual triggers for each summon.
        """
        source_minion = trigger_data.get('source_minion')
        effect_data = trigger_data.get('effect_data')
        saved_stats = trigger_data.get('saved_stats')
        golden_effects_applied = trigger_data.get('golden_effects_applied', False)

        logger.debug(f"[PROCESSOR] Processing individual summon from {source_minion.get('name', 'Unknown') if source_minion else 'System'}")

        # Create effect context
        effect_context = self.context_manager.create_effect_context(
            effect_type=EffectType.SUMMON,
            source_minion=source_minion,
            trigger_source='individual_summon'
        )

        # Begin effect chain tracking
        self.context_manager.begin_effect_chain(effect_context.effect_id)

        # Create context
        context = self.context_manager.create_combat_context_dict(acting_minion=source_minion)
        context['trigger_source'] = 'individual_summon'
        context['effect_context'] = effect_context
        context['golden_effects_applied'] = golden_effects_applied

        # Add registrar to context
        if self.registrar:
            context['registrar'] = self.registrar

        # Pass saved stats if available
        if saved_stats:
            context['saved_stats'] = saved_stats

        # Apply the summon effect
        from game_engine.effects import apply_effect
        success, logs, changes = apply_effect(effect_data, context)

        # Send effect results to interpreter if generic processor available
        if success and self.generic_processor:
            self.generic_processor._send_effect_results_to_interpreter(effect_data, changes, source_minion, 'individual_summon', logs)

        # Update effect context
        effect_context.minions_summoned = changes.get('summoned_minions', [])

        # Record the effect context
        self.context_manager.record_effect(effect_context)

        # End effect chain tracking
        self.context_manager.end_effect_chain()

        # Fix band positions after individual summons
        if changes.get('summoned_minions'):
            summoned_minion = changes['summoned_minions'][0]
            registry = self.context_manager.combat_registry
            if registry:
                band_type = registry.get_minion_band_type(summoned_minion)
                if band_type == 'player':
                    self._fix_band_positions(self.context_manager.player_band)
                elif band_type == 'enemy':
                    self._fix_band_positions(self.context_manager.enemy_band)

        return success, logs, changes

    def _check_deaths_and_generate_triggers(self) -> Tuple[bool, List[str], List[Dict]]:
        """
        Check for deaths and generate death toll triggers

        NOTE: This should rarely find anything now that deaths are processed immediately
        """
        death_logs = []
        death_triggers = []
        death_occurred = False

        registry = self.context_manager.combat_registry
        if not registry:
            return False, ["[ERROR] No combat registry available"], []

        # Get all minions
        all_minions = registry.get_band_minions('player', alive_only=False) + \
                     registry.get_band_minions('enemy', alive_only=False)

        for minion in all_minions:
            # Skip if already processed
            if minion.get('_death_processed', False):
                continue

            if minion['health'] <= 0 and not minion.get('_marked_dead', False):
                logger.warning(f"[PROCESSOR WARNING] Found unprocessed death: {minion['name']}")

                # Queue a death trigger
                death_trigger = {
                    'type': 'process_death',
                    'dying_minion': minion
                }
                self.trigger_queue.add_trigger(death_trigger, TriggerPriority.DEATH)

                minion['_marked_dead'] = True
                death_occurred = True

        return death_occurred, death_logs, death_triggers

    def _add_interpreter_command(self, command: Dict):
        """Add a command to the interpreter if available"""
        combat_state = self.context_manager.combat_state
        if combat_state and 'interpreter' in combat_state:
            interpreter = combat_state['interpreter']
            if interpreter:
                interpreter.add_command(command)

    def add_initial_triggers(self, attacker: Dict, defender: Optional[Dict] = None):
        """
        Add initial triggers for an attack

        NEW: Uses registrar to automatically find and register all attack-related triggers.
        This includes: assault, cast, rage, hide reduction, leap movement
        """
        from minions import get_minion_attack_with_aura

        # Add automatic hide reduction if attacker has hide
        if has_keyword(attacker, 'hide') and attacker.get('is_hidden', False):
            hide_effect = {'type': 'reduce_hide', 'target': 'self'}
            self.trigger_queue.add_trigger({
                'type': 'assault',  # Treat as assault for priority
                'source_minion': attacker,
                'effect_data': hide_effect,
                'event_data': {'attacker': attacker, 'defender': defender},
                'auto_effect': True
            }, TriggerPriority.HIGH)

        # Add automatic leap movement if attacker has leap
        if has_keyword(attacker, 'leap'):
            leap_effect = {'type': 'leap_move', 'target': 'self'}
            self.trigger_queue.add_trigger({
                'type': 'assault',  # Treat as assault for priority
                'source_minion': attacker,
                'effect_data': leap_effect,
                'event_data': {'attacker': attacker, 'defender': defender},
                'auto_effect': True
            }, TriggerPriority.LOW)  # LOW priority so it happens after attack

        # NEW: Use registrar to find and register attack triggers
        # This automatically handles: assault, cast, rage
        self.registrar.register_attack_triggers(attacker, defender)

    def _send_effect_results_to_interpreter(self, effect_data: Dict, changes: Dict,
                                            source_minion: Dict, trigger_type: str = None,
                                            effect_logs: List[str] = None):
        """
        Send effect results to interpreter

        Delegates to generic processor which has the actual implementation.
        This method exists so effects can call it on the trigger processor.
        """
        if self.generic_processor:
            # Call with all parameters if provided, otherwise minimal
            if trigger_type is not None and effect_logs is not None:
                self.generic_processor._send_effect_results_to_interpreter(
                    effect_data, changes, source_minion, trigger_type, effect_logs
                )
            else:
                # Minimal call for backwards compatibility
                self.generic_processor._send_effect_results_to_interpreter(
                    effect_data, changes, source_minion, '', []
                )

    def _enrich_trigger_data(self, trigger_data: Dict):
        """
        Add standard context components to trigger_data

        NEW METHOD: Centralizes context component passing.
        GenericProcessor will automatically add these to effect contexts.

        This ensures all effects have access to:
        - registrar: For registering new triggers (nested effects)
        - trigger_processor: For immediately resolving nested triggers
        - combat_registry: For band queries and target resolution
        - interpreter: For sending commands to frontend
        - run: For game state access

        Args:
            trigger_data: Trigger data to enrich (modified in place)
        """
        # Add registrar for nested trigger generation
        if self.registrar:
            trigger_data['registrar'] = self.registrar

        # Add trigger processor for nested trigger resolution
        # This is critical for effects like Siegfried's cascading assault
        trigger_data['trigger_processor'] = self

        # Add combat registry for target resolution
        if self.context_manager.combat_registry:
            trigger_data['combat_registry'] = self.context_manager.combat_registry

        # Add interpreter for frontend commands
        if self.context_manager.combat_state:
            interpreter = self.context_manager.combat_state.get('interpreter')
            if interpreter:
                trigger_data['interpreter'] = interpreter

        # Add run for game state access
        run = getattr(self.context_manager, 'run', None)
        if run:
            trigger_data['run'] = run

    def get_animation_events(self) -> List[Dict]:
        """Get animation events for processed effects"""
        return self.context_manager.get_animation_events()

    def get_debug_state(self) -> Dict:
        """Get debug information about the processor state"""
        return {
            'queue_state': self.trigger_queue.get_queue_state(),
            'context_state': self.context_manager.debug_state(),
            'event_state': self.event_system.debug_state(),
            'dev_mode': self.dev_mode_enabled,
            'pause_settings': {
                'on_trigger': self.pause_on_trigger,
                'on_effect': self.pause_on_effect
            }
        }