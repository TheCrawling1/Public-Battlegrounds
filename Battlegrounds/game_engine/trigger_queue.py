"""
Trigger Queue System - Manages the trigger resolution queue with strict FIFO processing

This module handles the queue mechanics, timing, and ordering of combat triggers.
Provides interception points for dev mode manual control.

UPDATED: Added DEATH priority for immediate death processing
"""

import logging

logger = logging.getLogger(__name__)

from collections import deque
from typing import Dict, List, Optional, Any, Callable
import uuid


class TriggerQueueInterceptor:
    """Handles dev mode interception of trigger processing"""

    def __init__(self):
        self.intercept_enabled = False
        self.intercept_callback: Optional[Callable] = None
        self.auto_process = True
        self.pending_trigger = None

    def enable_interception(self, callback: Optional[Callable] = None):
        """Enable trigger interception for dev mode"""
        self.intercept_enabled = True
        self.intercept_callback = callback
        self.auto_process = False

    def disable_interception(self):
        """Disable trigger interception"""
        self.intercept_enabled = False
        self.intercept_callback = None
        self.auto_process = True

    def should_intercept(self, trigger_data: Dict) -> bool:
        """Check if we should intercept this trigger"""
        if not self.intercept_enabled:
            return False

        # Store pending trigger for manual resolution
        self.pending_trigger = trigger_data

        # Notify callback if set
        if self.intercept_callback:
            self.intercept_callback(trigger_data)

        return not self.auto_process

    def resolve_interception(self, modified_trigger: Optional[Dict] = None):
        """Manually resolve an intercepted trigger"""
        if modified_trigger:
            self.pending_trigger = modified_trigger
        self.auto_process = True  # Allow this one to process
        return self.pending_trigger


class TriggerQueue:
    """
    Manages the trigger resolution queue with strict FIFO processing

    Features:
    - FIFO queue processing
    - Priority system for special triggers
    - Dev mode interception points
    - Trigger metadata tracking
    - Queue size limits for infinite loop prevention
    """

    def __init__(self, max_size: int = 100):
        self.queue = deque()
        self.max_size = max_size
        self.interceptor = TriggerQueueInterceptor()
        self.processed_triggers: List[Dict] = []  # History for debugging/animation
        self.trigger_id_counter = 0

    def add_trigger(self, trigger_data: Dict, priority: int = 0) -> str:
        """
        Add a trigger to the queue

        Args:
            trigger_data: Dictionary containing trigger information
            priority: Higher priority triggers process first (default 0)

        Returns:
            Trigger ID for tracking
        """
        if len(self.queue) >= self.max_size:
            logger.warning(f"[TRIGGER QUEUE WARNING] Queue at max size ({self.max_size}), dropping trigger")
            return None

        # Generate unique trigger ID
        trigger_id = f"trigger_{self.trigger_id_counter}_{trigger_data.get('type', 'unknown')}"
        self.trigger_id_counter += 1

        # Add metadata
        trigger_data['trigger_id'] = trigger_id
        trigger_data['priority'] = priority
        trigger_data['queued_at'] = self.trigger_id_counter

        # Insert based on priority (higher priority first, then FIFO)
        if priority > 0:
            # Find insertion point
            insert_idx = 0
            for i, existing in enumerate(self.queue):
                if existing.get('priority', 0) < priority:
                    insert_idx = i
                    break
                else:
                    insert_idx = i + 1

            # Insert at the appropriate position
            if insert_idx >= len(self.queue):
                self.queue.append(trigger_data)
            else:
                # Convert deque to list, insert, convert back
                queue_list = list(self.queue)
                queue_list.insert(insert_idx, trigger_data)
                self.queue = deque(queue_list)
        else:
            # Normal FIFO
            self.queue.append(trigger_data)

        logger.debug(f"[TRIGGER QUEUE] Added {trigger_data.get('type')} trigger (ID: {trigger_id}, Priority: {priority})")
        return trigger_id

    def has_triggers(self) -> bool:
        """Check if there are triggers waiting to be processed"""
        return len(self.queue) > 0

    def get_next_trigger(self) -> Optional[Dict]:
        """
        Get the next trigger from the queue

        Returns:
            Trigger data or None if queue is empty
        """
        if not self.queue:
            return None

        trigger = self.queue.popleft()

        # Check for interception
        if self.interceptor.should_intercept(trigger):
            # Trigger is intercepted, wait for manual resolution
            logger.debug(f"[TRIGGER QUEUE] Intercepted trigger: {trigger.get('type')} (ID: {trigger.get('trigger_id')})")
            return None  # Don't process yet

        # Add to processed history
        self.processed_triggers.append(trigger)

        # Limit history size
        if len(self.processed_triggers) > 100:
            self.processed_triggers = self.processed_triggers[-100:]

        return trigger

    def peek_next_trigger(self) -> Optional[Dict]:
        """Peek at the next trigger without removing it"""
        if self.queue:
            return self.queue[0]
        return None

    def clear(self):
        """Clear all triggers from the queue"""
        cleared_count = len(self.queue)
        self.queue.clear()
        logger.debug(f"[TRIGGER QUEUE] Cleared {cleared_count} triggers")

    def size(self) -> int:
        """Get the current queue size"""
        return len(self.queue)

    def get_queue_state(self) -> Dict:
        """Get the current queue state for debugging"""
        return {
            'size': self.size(),
            'triggers': list(self.queue),
            'interceptor_enabled': self.interceptor.intercept_enabled,
            'pending_interception': self.interceptor.pending_trigger is not None,
            'processed_count': len(self.processed_triggers)
        }

    def get_processed_triggers(self, limit: int = 10) -> List[Dict]:
        """Get recently processed triggers for debugging/animation"""
        return self.processed_triggers[-limit:] if self.processed_triggers else []

    def enable_dev_mode_interception(self, callback: Optional[Callable] = None):
        """Enable dev mode trigger interception"""
        self.interceptor.enable_interception(callback)
        logger.debug("[TRIGGER QUEUE] Dev mode interception enabled")

    def disable_dev_mode_interception(self):
        """Disable dev mode trigger interception"""
        self.interceptor.disable_interception()
        logger.debug("[TRIGGER QUEUE] Dev mode interception disabled")

    def resolve_intercepted_trigger(self, modified_trigger: Optional[Dict] = None):
        """
        Resolve an intercepted trigger and continue processing

        Args:
            modified_trigger: Optional modified trigger data

        Returns:
            The trigger that will be processed
        """
        trigger = self.interceptor.resolve_interception(modified_trigger)
        if trigger:
            # Add back to front of queue for immediate processing
            self.queue.appendleft(trigger)
        return trigger

    def add_triggers_batch(self, triggers: List[Dict], priority: int = 0) -> List[str]:
        """
        Add multiple triggers at once

        Args:
            triggers: List of trigger dictionaries
            priority: Priority for all triggers

        Returns:
            List of trigger IDs
        """
        trigger_ids = []
        for trigger in triggers:
            trigger_id = self.add_trigger(trigger, priority)
            if trigger_id:
                trigger_ids.append(trigger_id)
        return trigger_ids

    def remove_triggers_by_source(self, source_minion: Dict):
        """Remove all pending triggers from a specific source"""
        original_size = len(self.queue)
        self.queue = deque(
            t for t in self.queue
            if t.get('source_minion') != source_minion
        )
        removed = original_size - len(self.queue)
        if removed > 0:
            logger.debug(f"[TRIGGER QUEUE] Removed {removed} triggers from {source_minion.get('name', 'unknown')}")

    def get_triggers_by_type(self, trigger_type: str) -> List[Dict]:
        """Get all pending triggers of a specific type"""
        return [t for t in self.queue if t.get('type') == trigger_type]

    def prioritize_trigger(self, trigger_id: str):
        """Move a specific trigger to the front of the queue"""
        for i, trigger in enumerate(self.queue):
            if trigger.get('trigger_id') == trigger_id:
                # Remove and re-add at front
                self.queue.remove(trigger)
                self.queue.appendleft(trigger)
                logger.debug(f"[TRIGGER QUEUE] Prioritized trigger {trigger_id}")
                return True
        return False


class TriggerPriority:
    """Standard priority levels for triggers"""
    DEATH = 150      # Process deaths before everything else
    IMMEDIATE = 100  # Must process before anything else
    HIGH = 50        # Process before normal triggers
    NORMAL = 0       # Default priority
    LOW = -50        # Process after normal triggers

    @staticmethod
    def get_priority_for_type(trigger_type: str) -> int:
        """Get the standard priority for a trigger type"""
        priority_map = {
            'process_death': TriggerPriority.DEATH,           # Deaths process first
            'on_death_immediate': TriggerPriority.IMMEDIATE,  # Must process before other deaths
            'prevent_death': TriggerPriority.IMMEDIATE,       # Must check before death
            'aura_recalculation': TriggerPriority.IMMEDIATE,  # Auras recalculate immediately
            'assault': TriggerPriority.HIGH,                  # Process before damage
            'cast': TriggerPriority.HIGH,                     # Process before damage
            'death_toll': TriggerPriority.NORMAL,             # Normal death processing
            'rage': TriggerPriority.NORMAL,                   # Normal reaction
            'on_any_death': TriggerPriority.LOW,              # After specific death effects
            'on_any_cast': TriggerPriority.LOW,               # After cast effects
        }
        return priority_map.get(trigger_type, TriggerPriority.NORMAL)