"""
Generic Trigger Processor - ONE method to process ALL trigger types

Replaces custom _process_assault_trigger, _process_cast_trigger, etc.
Uses registry definitions to handle all trigger types generically.

UPDATED: Now uses CommandBuilder for interpreter commands (lazy import to avoid circular dependency)!
UPDATED: Passes formatted logs to interpreter commands for frontend display
FIXED: Trigger commands now include log messages!
FIXED: Now sets relative ally_band and enemy_band based on source_minion's perspective
"""

import logging

logger = logging.getLogger(__name__)

from typing import Dict, List, Tuple
from game_engine.triggers.trigger_registry import get_trigger_definition, TRIGGER_REGISTRY
from game_engine.triggers.effect_registry import EFFECT_REGISTRY
from game_engine.triggers.context_builder import ContextBuilder
from game_engine.triggers.golden_doubler import GoldenDoubler
from game_engine.trigger_queue import TriggerPriority


class GenericTriggerProcessor:
    """
    Processes triggers using registry definitions

    UPDATED: Now uses CommandBuilder for interpreter commands instead of manual construction.
    UPDATED: Passes formatted logs to interpreter for frontend display.
    FIXED: Trigger commands now include log messages!
    FIXED: Sets relative bands based on acting minion's perspective
    """

    def __init__(self, context_manager, interpreter=None, registrar=None):
        """
        Args:
            context_manager: CombatContextManager instance
            interpreter: Optional combat interpreter for frontend commands
            registrar: Optional TriggerRegistrar for generating nested triggers
        """
        self.context_manager = context_manager
        self.interpreter = interpreter
        self.registrar = registrar
        self.context_builder = ContextBuilder(context_manager)
        self.golden_doubler = GoldenDoubler()
        # DO NOT store trigger_processor as instance variable
        # Following trigger guide: "Context-Driven Communication"

    def process_trigger(self, trigger_data: Dict) -> Tuple[bool, List[str], Dict]:
        """
        Process ANY trigger type using its registry definition

        UPDATED: Automatic context enrichment - all standard components added to context.
        This ensures nested effects always have access to registrar, trigger_processor, etc.

        Args:
            trigger_data: Trigger data with keys:
                - type: Trigger type (e.g., 'assault')
                - source_minion: Minion with the trigger
                - effect_data: Effect to execute
                - event_data: Event context (defender, summoned, etc.)
                - registrar: Optional registrar (passed from trigger_processor)
                - trigger_processor: Optional processor (passed from trigger_processor)

        Returns:
            Tuple of (success, logs, changes)
        """
        trigger_type = trigger_data.get('type')
        source_minion = trigger_data.get('source_minion')
        effect_data = trigger_data.get('effect_data')
        event_data = trigger_data.get('event_data', {})

        logger.debug(f"[GENERIC] Processing {trigger_type} trigger for {source_minion.get('name')}")

        # ===== STEP 1: GET DEFINITION FROM REGISTRY =====
        definition = get_trigger_definition(trigger_type)
        if not definition:
            return False, [f"❌ Unknown trigger type: {trigger_type}"], {}

        # ===== STEP 2: APPLY GOLDEN DOUBLING =====
        effect_data = self._apply_golden_to_effect(effect_data, source_minion)

        # ===== STEP 3: SEND TRIGGER COMMAND TO INTERPRETER =====
        trigger_log = self._generate_trigger_log(definition, source_minion)
        self._send_trigger_command_to_interpreter(trigger_type, source_minion, trigger_log)

        # ===== STEP 4: BUILD CONTEXT =====
        context = self.context_builder.build_trigger_context(
            definition,
            source_minion,
            event_data
        )

        # Add standard context fields
        context['golden_effects_applied'] = True
        context['trigger_type'] = trigger_type  # For effect list logging

        # ===== STEP 4.5: AUTOMATIC CONTEXT ENRICHMENT =====
        # CRITICAL: Add all standard components that effects might need
        # This ensures nested effects (like Siegfried's cascading assault) work correctly

        # Always add registrar (from instance variable)
        if self.registrar:
            context['registrar'] = self.registrar
            logger.debug(f"[GENERIC] Auto-added registrar to context")

        # Add trigger_processor if passed in trigger_data
        # This is needed for nested trigger resolution (e.g., rage triggers during attack_target)
        if 'trigger_processor' in trigger_data:
            context['trigger_processor'] = trigger_data['trigger_processor']
            logger.debug(f"[GENERIC] Auto-added trigger_processor to context for nested resolution")

        # Add combat_registry for target resolution and band queries
        if self.context_manager.combat_registry:
            context['combat_registry'] = self.context_manager.combat_registry

        # Add combat_state for broader game state access
        if self.context_manager.combat_state:
            context['combat_state'] = self.context_manager.combat_state

        # ===== STEP 4.6: ADD RELATIVE BANDS =====
        # CRITICAL: Set ally_band and enemy_band relative to source_minion's perspective
        # This ensures 'all_enemies' and 'all_allies' target correctly for both player and enemy minions
        registry = self.context_manager.combat_registry
        if registry and source_minion:
            band_type = registry.get_minion_band_type(source_minion)
            if band_type == 'player':
                context['ally_band'] = self.context_manager.player_band
                context['enemy_band'] = self.context_manager.enemy_band
                logger.debug(f"[GENERIC] Set relative bands: ally=player, enemy=enemy (source is player minion)")
            elif band_type == 'enemy':
                context['ally_band'] = self.context_manager.enemy_band
                context['enemy_band'] = self.context_manager.player_band
                logger.debug(f"[GENERIC] Set relative bands: ally=enemy, enemy=player (source is enemy minion)")

        # Preserve any additional context from trigger_data
        # This allows for future extensibility without code changes
        for key in ['damage_handler', 'interpreter', 'run']:
            if key in trigger_data:
                context[key] = trigger_data[key]

        logger.debug(f"[GENERIC] Context enriched with standard components")

        # ===== STEP 5: EXECUTE EFFECT =====
        success, logs, changes = self._execute_effect(effect_data, context)

        # ===== STEP 5.5: REGISTER DEATH TOLL TRIGGERS =====
        # If this was a death_toll trigger, register ON_ANY_DEATH_TOLL event
        if success and trigger_type == 'death_toll' and self.registrar:
            logger.debug(f"[GENERIC] Registering death toll triggers for {source_minion.get('name')}")
            self.registrar.register_death_toll_triggers(source_minion, is_additional_trigger=False)

        # ===== STEP 6: SEND EFFECT RESULTS TO INTERPRETER =====
        # SKIP if effect_data is a list - apply_effects_list already sent each sub-effect
        if success and self.interpreter and not isinstance(effect_data, list):
            self._send_effect_results_to_interpreter(effect_data, changes, source_minion, trigger_type, logs)
        elif isinstance(effect_data, list):
            logger.debug(f"[GENERIC] Skipping interpreter for effect list - sub-effects already sent")

        # ===== STEP 7: COMBINE LOGS =====
        all_logs = [trigger_log] + logs

        logger.debug(f"[GENERIC] {trigger_type} completed: success={success}, logs={len(all_logs)}")

        return success, all_logs, changes

    def _apply_golden_to_effect(self, effect_data, minion: Dict):
        """Apply golden doubling to effect using registry"""
        if isinstance(effect_data, list):
            return self.golden_doubler.apply_golden_doubling_to_list(effect_data, minion)
        else:
            return self.golden_doubler.apply_golden_doubling(effect_data, minion)

    def _send_trigger_command_to_interpreter(self, trigger_type: str, source_minion: Dict,
                                            trigger_log: str):
        """
        Send trigger command to interpreter

        UPDATED: Now uses CommandBuilder with lazy import to avoid circular dependency!
        FIXED: Now passes trigger_log to command builder!
        """
        if not self.interpreter:
            return

        # Lazy import to avoid circular dependency
        from game_engine.interpreter import CommandBuilder
        command_builder = CommandBuilder()

        # FIXED: Build trigger command WITH log message
        command = command_builder.build_trigger_command(trigger_type, source_minion,
                                                       log_message=trigger_log)

        if command:
            self.interpreter.add_command(command)
            logger.debug(f"[GENERIC] Sent interpreter command via builder: {command['cmd']} with log")

    def _execute_effect(self, effect_data, context: Dict) -> Tuple[bool, List[str], Dict]:
        """
        Execute the effect using the effects system

        UPDATED: Context is now automatically enriched before calling this
        """
        from game_engine.effects import apply_effect

        # Effect data might be a list (for destroy_and_transform, etc.)
        if isinstance(effect_data, list):
            from game_engine.effects import apply_effects_list
            return apply_effects_list(effect_data, context)
        else:
            return apply_effect(effect_data, context)

    def _send_effect_results_to_interpreter(self, effect_data: Dict, changes: Dict,
                                           source_minion: Dict, trigger_type: str,
                                           effect_logs: List[str]):
        """
        Send effect results to interpreter

        UPDATED: Now accepts effect_logs and passes them to commands for frontend display!
        UPDATED: Now uses CommandBuilder with lazy import to avoid circular dependency!
        UPDATED: Handles conditionals by detecting child effect from changes!
        UPDATED: Adds band info for summons from registry!
        This simplifies the code and ensures consistency with add_effect_command().
        """
        if not self.interpreter:
            return

        # Handle effect lists (from conditionals and array effects like Tooth Fairy)
        if isinstance(effect_data, list):
            for i, effect in enumerate(effect_data):
                # Extract log for this specific effect if available
                effect_log = effect_logs[i] if i < len(effect_logs) else None
                self._send_effect_results_to_interpreter(effect, changes, source_minion, trigger_type, [effect_log] if effect_log else [])
            return

        effect_type = effect_data.get('type')

        # SPECIAL HANDLING: trigger_death_toll sends its command manually before child effects
        # Skip it here to avoid duplicate commands
        if effect_type == 'trigger_death_toll':
            logger.debug(f"[GENERIC] Skipping trigger_death_toll (command already sent manually)")
            return

        # SPECIAL HANDLING: chrono_cascade is a composite effect that sends FORCE_CAST and APPLY_STUN
        # manually, and its child effects (perform_cast) also send their own commands
        if effect_type == 'chrono_cascade':
            logger.debug(f"[GENERIC] Skipping chrono_cascade (composite effect with manual commands)")
            return

        # SPECIAL HANDLING: Conditionals don't create commands themselves
        # Instead, detect what child effect executed and send that command
        if effect_type == 'conditional':
            logger.debug(f"[GENERIC] Conditional detected, inspecting changes to determine executed effect")

            # CRITICAL FIX: Check if child effects are lists - if so, they already sent their own commands
            # This happens when then_effect or else_effect is an array of effects (like Shinobi's start_of_combat)
            then_effect = effect_data.get('then_effect')
            else_effect = effect_data.get('else_effect')

            if isinstance(then_effect, list) or isinstance(else_effect, list):
                logger.debug(f"[GENERIC] Conditional has effect array(s) - child effects already sent commands, skipping parent")
                return

            # Check if child effect is a composite effect that handles its own commands
            child_effect_type = None
            if then_effect and isinstance(then_effect, dict):
                child_effect_type = then_effect.get('type')
            elif else_effect and isinstance(else_effect, dict):
                child_effect_type = else_effect.get('type')

            if child_effect_type in ['chrono_cascade', 'trigger_death_toll', 'perform_cast', 'attack_target']:
                # attack_target routes through the normal combat-action
                # handlers (DECLARE_ATTACK + COMBAT_DAMAGE), so it has already
                # emitted its commands and we must not emit another here.
                logger.debug(f"[GENERIC] Conditional has composite child effect ({child_effect_type}) - already sent commands, skipping")
                return

            # Check what actually happened by inspecting changes
            # Try to use the actual child effect from then_effect/else_effect if available
            child_effect = then_effect if then_effect and not isinstance(then_effect, list) else else_effect if else_effect and not isinstance(else_effect, list) else None

            if changes.get('summon_occurred') or changes.get('summoned_minions'):
                # A summon happened!
                logger.debug(f"[GENERIC] Conditional executed a summon - creating SUMMON command")
                effect_type = 'summon_minion'
                # Use actual child effect if it's a summon, otherwise reconstruct
                if child_effect and child_effect.get('type') == 'summon_minion':
                    effect_data = child_effect
                else:
                    effect_data = {
                        'type': 'summon_minion',
                        'minion_name': changes.get('summoned_minions', [{}])[0].get('name', 'Unknown') if changes.get('summoned_minions') else 'Unknown'
                    }
            elif changes.get('keyword_granted'):
                # Keyword granted (like Shinobi's assault granting cleave)
                logger.debug(f"[GENERIC] Conditional executed grant_keyword - creating GRANT_KEYWORD command")
                # Use the actual grant_keyword effect to preserve keyword_data
                if child_effect and child_effect.get('type') == 'grant_keyword':
                    effect_data = child_effect
                    effect_type = 'grant_keyword'
                else:
                    effect_type = 'grant_keyword'
                    effect_data = {'type': 'grant_keyword'}
            elif changes.get('damage_dealt') is not None:
                # Damage happened
                logger.debug(f"[GENERIC] Conditional executed damage - creating DEAL_DAMAGE command")
                effect_type = 'deal_damage'
                effect_data = {'type': 'deal_damage'}
            else:
                # Unknown conditional result, skip command
                logger.debug(f"[GENERIC] Conditional result unclear, no command sent")
                return

        # SPECIAL HANDLING: Add band info for summons
        # The effect doesn't return this, but we can get it from the registry
        if effect_type == 'summon_minion' and 'summon_band' not in changes:
            # Determine band from registry
            registry = self.context_manager.combat_registry
            if registry and source_minion:
                band_type = registry.get_minion_band_type(source_minion)
                if band_type:
                    changes['summon_band'] = band_type
                    logger.debug(f"[GENERIC] Added summon_band={band_type} to changes for interpreter")

        # Lazy import to avoid circular dependency
        from game_engine.interpreter import CommandBuilder
        command_builder = CommandBuilder()

        # Extract the primary log message for this effect
        log_message = effect_logs[0] if effect_logs and len(effect_logs) > 0 else None

        # Registry-driven sync check: some effects can affect >1 entity per
        # invocation (multi-target damage, AoE buffs, batch summons). Their
        # field_map collapses the entity list to `.0`, so a single command
        # would only describe the first entity — the frontend never sees the
        # others and desyncs from backend state. When sync_check declares a
        # `multi_entity_key`, we emit one command per entity.
        interp_def = EFFECT_REGISTRY.get(effect_type, {}).get('interpreter', {})
        sync_check = interp_def.get('sync_check') or {}
        multi_entity_key = sync_check.get('multi_entity_key')
        entities = changes.get(multi_entity_key) if multi_entity_key else None
        entities = entities if isinstance(entities, list) else []

        if multi_entity_key and len(entities) > 1:
            per_emit_overrides = sync_check.get('per_emit_from_effect_data') or {}
            emitted = 0
            for idx, entity in enumerate(entities):
                per_changes = dict(changes)
                per_changes[multi_entity_key] = [entity]
                # Aggregate fields (e.g. damage_dealt = amount * N) are wrong
                # per-command; override with the per-target value from effect_data.
                for change_key, ed_key in per_emit_overrides.items():
                    per_changes[change_key] = effect_data.get(ed_key, 0)
                # Only the first command carries the formatted log so the combat
                # log doesn't repeat N times; 2..N still carry full minion state.
                per_log = log_message if idx == 0 else None
                cmd = command_builder.build_effect_command(
                    effect_type, effect_data, per_changes, source_minion,
                    trigger_type, log_message=per_log
                )
                if cmd:
                    self.interpreter.add_command(cmd)
                    emitted += 1
                    logger.debug(f"[GENERIC] Sent batch {cmd['cmd']} {idx+1}/{len(entities)}: "
                          f"{entity.get('name','?')} id={str(entity.get('_combat_id',''))[:8]}")

            if emitted != len(entities):
                logger.warning(f"[SYNC WARNING] effect={effect_type} "
                      f"affected={len(entities)} emitted={emitted} "
                      f"source={source_minion.get('name') if source_minion else '?'} "
                      f"— frontend will miss {len(entities) - emitted} update(s)")
            return

        # Use CommandBuilder to create effect command WITH log message
        command = command_builder.build_effect_command(
            effect_type,
            effect_data,
            changes,
            source_minion,
            trigger_type,
            log_message=log_message  # ← Pass the formatted log!
        )

        if command:
            self.interpreter.add_command(command)
            logger.debug(f"[GENERIC] Sent effect interpreter command via builder: {command['cmd']} with log: {log_message[:50] if log_message else 'None'}...")

        # Desync flag: effect changed multiple entities but only one command went out.
        # Shouldn't trigger with the batch path above, but catches future regressions
        # (e.g. someone adding a new multi-target effect without sync_check metadata).
        if multi_entity_key and len(entities) > 1 and command:
            logger.warning(f"[SYNC WARNING] effect={effect_type} "
                  f"affected={len(entities)} emitted=1 "
                  f"source={source_minion.get('name') if source_minion else '?'} "
                  f"— sync_check batch path was bypassed")

    def _generate_trigger_log(self, definition: Dict, source_minion: Dict) -> str:
        """Generate log message from registry template"""
        template = definition.get('log_template', '✨ {source_name} triggers!')

        is_golden = source_minion.get('golden', False)
        source_name = source_minion.get('name', 'Unknown')

        if is_golden:
            source_name = f"💎 Golden {source_name}"

        return template.format(source_name=source_name)