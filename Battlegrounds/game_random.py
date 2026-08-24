"""
Game Random System - Centralized random selection with dev mode override support

This system provides context-aware random functions that can be overridden in dev mode
for testing and manual targeting. All random operations in the game should go through
this system instead of using Python's random module directly.

Usage:
    from game_random import game_random

    # Normal usage (production)
    target = game_random.select_one('combat_target', valid_targets)

    # With context information
    target = game_random.select_one('effect_target', allies,
                                   context={'effect': 'heal', 'source': 'priest'})

    # Multiple selection
    targets = game_random.select_multiple('aoe_targets', enemies, count=3)
"""

import logging

logger = logging.getLogger(__name__)

import random
import uuid
from typing import Any, List, Optional, Dict, Union, Callable
from dataclasses import dataclass
from collections import deque
from enum import Enum


class SelectionType(Enum):
    """Types of random selections in the game"""
    # Combat selections
    COMBAT_TARGET = 'combat_target'  # Main combat attack target
    COUNTER_TARGET = 'counter_target'  # Counter-attack target
    MULTI_ATTACK_TARGET = 'multi_attack_target'  # Multi-attack additional targets

    # Effect selections
    EFFECT_TARGET = 'effect_target'  # Generic effect target
    HEAL_TARGET = 'heal_target'  # Healing effect target
    BUFF_TARGET = 'buff_target'  # Buff effect target
    DAMAGE_TARGET = 'damage_target'  # Damage effect target
    SUMMON_POSITION = 'summon_position'  # Where to place summon

    # Special selections
    RANDOM_ALLY = 'random_ally'  # Random ally selection
    RANDOM_ENEMY = 'random_enemy'  # Random enemy selection
    DEATH_TOLL_TARGET = 'death_toll_target'  # Death toll effect target
    AOE_TARGETS = 'aoe_targets'  # Area of effect targets

    # Game mechanics
    RANDOM_NUMBER = 'random_number'  # Random number generation
    RANDOM_CHANCE = 'random_chance'  # Probability checks
    CARD_DRAW = 'card_draw'  # Drawing from deck/pool
    LOOT_ROLL = 'loot_roll'  # Loot determination


@dataclass
class SelectionContext:
    """Context information for a random selection"""
    selection_type: SelectionType
    options: List[Any]
    metadata: Dict[str, Any]
    source: Optional[str] = None  # What triggered this selection
    description: Optional[str] = None  # Human-readable description


@dataclass
class Override:
    """Manual override for a specific selection"""
    override_id: str
    selection_type: SelectionType
    target_filter: Optional[Callable] = None  # Function to identify target
    target_value: Optional[Any] = None  # Direct value override
    metadata_filter: Optional[Dict] = None  # Match specific metadata
    consumed: bool = False
    priority: int = 0  # Higher priority overrides first


class GameRandom:
    """
    Centralized random system with dev mode override support

    This class handles all random operations in the game and provides
    a mechanism for dev mode to override specific selections for testing.
    """

    def __init__(self, seed: Optional[int] = None):
        """
        Initialize the random system

        Args:
            seed: Optional random seed for reproducible results
        """
        self.rng = random.Random(seed) if seed else random.Random()
        self.dev_mode = False
        self.override_queue: deque[Override] = deque()
        self.selection_history: List[SelectionContext] = []
        self.pending_selections: List[SelectionContext] = []
        self.session_id: Optional[str] = None
        self.max_history = 1000

        # Callbacks for dev mode UI updates
        self.on_selection_pending: Optional[Callable] = None
        self.on_selection_made: Optional[Callable] = None

    def enable_dev_mode(self, session_id: str):
        """Enable dev mode for a specific session"""
        self.dev_mode = True
        self.session_id = session_id
        self.override_queue.clear()
        self.selection_history.clear()
        logger.debug(f"[GameRandom] Dev mode enabled for session {session_id}")

    def disable_dev_mode(self):
        """Disable dev mode"""
        self.dev_mode = False
        self.session_id = None
        self.override_queue.clear()
        logger.debug("[GameRandom] Dev mode disabled")

    def add_override(self, selection_type: Union[SelectionType, str],
                     target_filter: Optional[Callable] = None,
                     target_value: Optional[Any] = None,
                     metadata_filter: Optional[Dict] = None,
                     priority: int = 0) -> str:
        """
        Add a manual override for a future selection

        Args:
            selection_type: Type of selection to override
            target_filter: Function to identify the target (e.g., lambda x: x.get('name') == 'Skeleton')
            target_value: Direct value to return (e.g., specific index or object)
            metadata_filter: Match specific context metadata
            priority: Higher priority overrides are consumed first

        Returns:
            Override ID for tracking
        """
        if isinstance(selection_type, str):
            selection_type = SelectionType(selection_type)

        override = Override(
            override_id=str(uuid.uuid4()),
            selection_type=selection_type,
            target_filter=target_filter,
            target_value=target_value,
            metadata_filter=metadata_filter,
            priority=priority
        )

        # Insert based on priority
        inserted = False
        for i, existing in enumerate(self.override_queue):
            if existing.priority < override.priority:
                self.override_queue.insert(i, override)
                inserted = True
                break

        if not inserted:
            self.override_queue.append(override)

        logger.debug(f"[GameRandom] Added override {override.override_id} for {selection_type.value}")
        return override.override_id

    def clear_overrides(self, selection_type: Optional[SelectionType] = None):
        """Clear overrides, optionally for a specific type"""
        if selection_type:
            self.override_queue = deque(
                o for o in self.override_queue
                if o.selection_type != selection_type
            )
        else:
            self.override_queue.clear()

    def select_one(self, selection_type: Union[SelectionType, str],
                   options: List[Any],
                   context: Optional[Dict[str, Any]] = None,
                   description: Optional[str] = None) -> Optional[Any]:
        """
        Select one item from options with possible override

        Args:
            selection_type: Type of selection being made
            options: List of valid options to choose from
            context: Additional context about the selection
            description: Human-readable description

        Returns:
            Selected item or None if no options
        """
        if not options:
            return None

        if isinstance(selection_type, str):
            selection_type = SelectionType(selection_type)

        # Create selection context
        selection_ctx = SelectionContext(
            selection_type=selection_type,
            options=list(options),  # Copy to preserve original
            metadata=context or {},
            source=self._get_caller_info(),
            description=description
        )

        # Check for override if in dev mode
        if self.dev_mode:
            override_result = self._check_override(selection_ctx)
            if override_result is not None:
                self._record_selection(selection_ctx, override_result, overridden=True)
                return override_result

            # If manual targeting enabled and this is a targetable selection, pause for input
            if self._requires_manual_input(selection_type):
                self._notify_pending_selection(selection_ctx)
                # In a real implementation, this would wait for input
                # For now, continue with random selection

        # Normal random selection
        result = self.rng.choice(options)
        self._record_selection(selection_ctx, result, overridden=False)
        return result

    def select_multiple(self, selection_type: Union[SelectionType, str],
                        options: List[Any],
                        count: int,
                        context: Optional[Dict[str, Any]] = None,
                        description: Optional[str] = None,
                        unique: bool = True) -> List[Any]:
        """
        Select multiple items from options

        Args:
            selection_type: Type of selection being made
            options: List of valid options
            count: Number of items to select
            context: Additional context
            description: Human-readable description
            unique: Whether selections must be unique

        Returns:
            List of selected items
        """
        if not options or count <= 0:
            return []

        if isinstance(selection_type, str):
            selection_type = SelectionType(selection_type)

        # Limit count to available options if unique
        if unique:
            count = min(count, len(options))

        # Create selection context
        selection_ctx = SelectionContext(
            selection_type=selection_type,
            options=list(options),
            metadata={**(context or {}), 'count': count, 'unique': unique},
            source=self._get_caller_info(),
            description=description
        )

        # Check for override if in dev mode
        if self.dev_mode:
            override_result = self._check_override(selection_ctx)
            if override_result is not None:
                # Ensure override result is a list
                if not isinstance(override_result, list):
                    override_result = [override_result]
                self._record_selection(selection_ctx, override_result, overridden=True)
                return override_result[:count]

        # Normal random selection
        if unique:
            result = self.rng.sample(options, count)
        else:
            result = [self.rng.choice(options) for _ in range(count)]

        self._record_selection(selection_ctx, result, overridden=False)
        return result

    def random_int(self, min_val: int, max_val: int,
                   context: Optional[Dict[str, Any]] = None) -> int:
        """Generate a random integer with possible override"""
        selection_ctx = SelectionContext(
            selection_type=SelectionType.RANDOM_NUMBER,
            options=list(range(min_val, max_val + 1)),
            metadata={**(context or {}), 'min': min_val, 'max': max_val},
            source=self._get_caller_info()
        )

        if self.dev_mode:
            override_result = self._check_override(selection_ctx)
            if override_result is not None:
                self._record_selection(selection_ctx, override_result, overridden=True)
                return int(override_result)

        result = self.rng.randint(min_val, max_val)
        self._record_selection(selection_ctx, result, overridden=False)
        return result

    def random_chance(self, probability: float,
                      context: Optional[Dict[str, Any]] = None) -> bool:
        """Check if a random event occurs with given probability"""
        selection_ctx = SelectionContext(
            selection_type=SelectionType.RANDOM_CHANCE,
            options=[True, False],
            metadata={**(context or {}), 'probability': probability},
            source=self._get_caller_info()
        )

        if self.dev_mode:
            override_result = self._check_override(selection_ctx)
            if override_result is not None:
                self._record_selection(selection_ctx, override_result, overridden=True)
                return bool(override_result)

        result = self.rng.random() < probability
        self._record_selection(selection_ctx, result, overridden=False)
        return result

    def shuffle(self, sequence: List[Any],
                context: Optional[Dict[str, Any]] = None) -> List[Any]:
        """Shuffle a sequence with possible override"""
        if not sequence:
            return sequence

        # For override, we'd need a way to specify order
        # For now, just shuffle normally even in dev mode
        result = list(sequence)
        self.rng.shuffle(result)
        return result

    def _check_override(self, selection_ctx: SelectionContext) -> Optional[Any]:
        """Check if there's an override for this selection"""
        for i, override in enumerate(self.override_queue):
            if override.consumed:
                continue

            # Check if this override matches
            if override.selection_type != selection_ctx.selection_type:
                continue

            # Check metadata filter
            if override.metadata_filter:
                if not all(selection_ctx.metadata.get(k) == v
                           for k, v in override.metadata_filter.items()):
                    continue

            # Direct value override
            if override.target_value is not None:
                override.consumed = True
                logger.debug(f"[GameRandom] Override {override.override_id} consumed: direct value")
                return override.target_value

            # Filter-based override
            if override.target_filter:
                for option in selection_ctx.options:
                    try:
                        if override.target_filter(option):
                            override.consumed = True
                            logger.debug(f"[GameRandom] Override {override.override_id} consumed: filter match")
                            return option
                    except:
                        pass  # Filter didn't match this option

        return None

    def _record_selection(self, ctx: SelectionContext, result: Any, overridden: bool):
        """Record a selection for debugging"""
        ctx.metadata['result'] = result
        ctx.metadata['overridden'] = overridden

        self.selection_history.append(ctx)

        # Trim history if too long
        if len(self.selection_history) > self.max_history:
            self.selection_history = self.selection_history[-self.max_history:]

        # Notify callbacks if set
        if self.on_selection_made:
            self.on_selection_made(ctx, result, overridden)

    def _requires_manual_input(self, selection_type: SelectionType) -> bool:
        """Check if this selection type requires manual input in dev mode"""
        # These are the main types that should pause for manual selection
        return selection_type in [
            SelectionType.COMBAT_TARGET,
            SelectionType.MULTI_ATTACK_TARGET,
            SelectionType.EFFECT_TARGET,
            SelectionType.HEAL_TARGET,
            SelectionType.BUFF_TARGET,
            SelectionType.DAMAGE_TARGET,
        ]

    def _notify_pending_selection(self, ctx: SelectionContext):
        """Notify that a selection is pending (for dev UI)"""
        self.pending_selections.append(ctx)
        if self.on_selection_pending:
            self.on_selection_pending(ctx)

    def _get_caller_info(self) -> str:
        """Get information about what code is making this selection"""
        import traceback
        # Get the calling function name from stack
        stack = traceback.extract_stack()
        if len(stack) >= 3:
            # Skip this function and the select_* function
            caller = stack[-3]
            return f"{caller.filename}:{caller.lineno} in {caller.name}"
        return "unknown"

    def get_history(self, selection_type: Optional[SelectionType] = None,
                    limit: int = 100) -> List[SelectionContext]:
        """Get selection history, optionally filtered by type"""
        history = self.selection_history
        if selection_type:
            history = [h for h in history if h.selection_type == selection_type]
        return history[-limit:]

    def get_pending_overrides(self) -> List[Override]:
        """Get list of pending overrides"""
        return [o for o in self.override_queue if not o.consumed]

    def export_state(self) -> Dict:
        """Export current state for debugging"""
        return {
            'dev_mode': self.dev_mode,
            'session_id': self.session_id,
            'pending_overrides': len(self.get_pending_overrides()),
            'history_size': len(self.selection_history),
            'last_selections': [
                {
                    'type': ctx.selection_type.value,
                    'result': str(ctx.metadata.get('result')),
                    'overridden': ctx.metadata.get('overridden', False),
                    'source': ctx.source
                }
                for ctx in self.selection_history[-10:]
            ]
        }


# Global instance for the game to use
game_random = GameRandom()


# Convenience functions that use the global instance
def select_one(selection_type: Union[SelectionType, str],
               options: List[Any],
               context: Optional[Dict[str, Any]] = None,
               description: Optional[str] = None) -> Optional[Any]:
    """Global convenience function for single selection"""
    return game_random.select_one(selection_type, options, context, description)


def select_multiple(selection_type: Union[SelectionType, str],
                    options: List[Any],
                    count: int,
                    context: Optional[Dict[str, Any]] = None,
                    description: Optional[str] = None,
                    unique: bool = True) -> List[Any]:
    """Global convenience function for multiple selection"""
    return game_random.select_multiple(selection_type, options, count, context, description, unique)


def random_int(min_val: int, max_val: int,
               context: Optional[Dict[str, Any]] = None) -> int:
    """Global convenience function for random integer"""
    return game_random.random_int(min_val, max_val, context)


def random_chance(probability: float,
                  context: Optional[Dict[str, Any]] = None) -> bool:
    """Global convenience function for probability check"""
    return game_random.random_chance(probability, context)