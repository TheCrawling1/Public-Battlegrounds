"""
Combat Events System - Manages event emission and listening for reactive effects

This module enables minions to react to specific events like "spell cast",
"minion attacked", "damage dealt", etc. Critical for effects like Destroyer
and Spell Shield that need to know what just happened.
"""

import logging

logger = logging.getLogger(__name__)

from typing import Dict, List, Optional, Callable, Any, Set
from dataclasses import dataclass
from enum import Enum


class CombatEventType(Enum):
    """Types of combat events that can be emitted"""
    # Attack events
    ATTACK_DECLARED = "attack_declared"       # Before attack resolves
    ATTACK_COMPLETED = "attack_completed"      # After attack resolves
    COUNTER_ATTACK = "counter_attack"         # Counter-attack occurred
    MULTI_ATTACK = "multi_attack"             # Multi-attack triggered
    
    # Damage events
    DAMAGE_DEALT = "damage_dealt"             # Any damage dealt
    SPELL_DAMAGE_DEALT = "spell_damage_dealt" # Spell damage specifically
    ABILITY_DAMAGE_DEALT = "ability_damage_dealt"  # Ability damage
    COMBAT_DAMAGE_DEALT = "combat_damage_dealt"    # Normal attack damage
    
    # Spell events
    SPELL_CAST = "spell_cast"                 # Spell was cast
    SPELL_TARGET_SELECTED = "spell_target_selected"  # Spell target chosen
    
    # Death events
    MINION_DEATH = "minion_death"             # Minion died
    DEATH_PREVENTED = "death_prevented"       # Death was prevented
    
    # Summon events
    MINION_SUMMONED = "minion_summoned"       # New minion summoned
    MINION_TRANSFORMED = "minion_transformed" # Minion transformed
    
    # Stat events
    STATS_BUFFED = "stats_buffed"             # Stats increased
    STATS_DEBUFFED = "stats_debuffed"         # Stats decreased
    PERMANENT_STATS_GAINED = "permanent_stats_gained"  # Permanent stats
    
    # Healing events
    HEALING_RECEIVED = "healing_received"     # Minion was healed
    
    # Special events
    TRIGGER_ACTIVATED = "trigger_activated"   # Any trigger activated
    FATIGUE_DAMAGE = "fatigue_damage"         # Fatigue damage applied
    POSITION_CHANGED = "position_changed"     # Minion moved


@dataclass
class CombatEvent:
    """Represents a single combat event"""
    event_type: CombatEventType
    source: Optional[Dict]                    # Source minion (if any)
    target: Optional[Dict]                    # Target minion (if any)
    data: Dict[str, Any]                      # Event-specific data
    timestamp: int                             # Order of occurrence
    
    def involves(self, minion: Dict) -> bool:
        """Check if a minion is involved in this event"""
        return self.source == minion or self.target == minion
        
    def get_value(self, key: str, default=None):
        """Get a value from event data"""
        return self.data.get(key, default)


class EventListener:
    """Represents a listener for combat events"""
    
    def __init__(self, minion: Dict, event_types: List[CombatEventType],
                 condition: Optional[Callable] = None,
                 handler: Optional[Callable] = None,
                 priority: int = 0):
        """
        Create an event listener
        
        Args:
            minion: The minion that owns this listener
            event_types: Types of events to listen for
            condition: Optional condition function(event, minion) -> bool
            handler: Optional handler function(event, minion, context)
            priority: Higher priority listeners trigger first
        """
        self.minion = minion
        self.event_types = set(event_types)
        self.condition = condition
        self.handler = handler
        self.priority = priority
        self.active = True
        
    def should_trigger(self, event: CombatEvent) -> bool:
        """Check if this listener should trigger for an event"""
        if not self.active:
            return False
            
        if event.event_type not in self.event_types:
            return False
            
        # Check if minion is still alive
        if self.minion.get('health', 0) <= 0:
            return False
            
        # Check custom condition if provided
        if self.condition:
            return self.condition(event, self.minion)
            
        return True
        
    def handle_event(self, event: CombatEvent, context: Dict):
        """Handle the event if handler is provided"""
        if self.handler:
            return self.handler(event, self.minion, context)
        return None


class CombatEventSystem:
    """
    Manages combat event emission and listener registration
    
    This system allows effects to emit events and minions to listen
    for specific events to trigger reactions.
    """
    
    def __init__(self):
        self.listeners: List[EventListener] = []
        self.event_history: List[CombatEvent] = []
        self.event_counter = 0
        self.suppressed_events: Set[CombatEventType] = set()
        
    def register_listener(self, listener: EventListener):
        """Register an event listener"""
        self.listeners.append(listener)
        # Sort by priority (highest first)
        self.listeners.sort(key=lambda l: l.priority, reverse=True)
        
    def unregister_listener(self, listener: EventListener):
        """Unregister an event listener"""
        if listener in self.listeners:
            self.listeners.remove(listener)
            
    def unregister_minion_listeners(self, minion: Dict):
        """Remove all listeners for a specific minion"""
        self.listeners = [l for l in self.listeners if l.minion != minion]
        
    def emit_event(self, event_type: CombatEventType, 
                  source: Optional[Dict] = None,
                  target: Optional[Dict] = None,
                  data: Optional[Dict] = None) -> List[Dict]:
        """
        Emit a combat event
        
        Returns:
            List of triggers generated by listeners
        """
        if event_type in self.suppressed_events:
            return []
            
        # Create event
        self.event_counter += 1
        event = CombatEvent(
            event_type=event_type,
            source=source,
            target=target,
            data=data or {},
            timestamp=self.event_counter
        )
        
        # Add to history
        self.event_history.append(event)
        if len(self.event_history) > 200:
            self.event_history = self.event_history[-200:]
            
        logger.debug(f"[EVENT] Emitted {event_type.value}: {source.get('name') if source else 'None'} -> {target.get('name') if target else 'None'}")
        
        # Collect triggers from listeners
        triggers = []
        for listener in self.listeners:
            if listener.should_trigger(event):
                # Create trigger for this listener
                trigger = self._create_listener_trigger(event, listener)
                if trigger:
                    triggers.append(trigger)
                    
        return triggers
        
    def _create_listener_trigger(self, event: CombatEvent, listener: EventListener) -> Optional[Dict]:
        """Create a trigger from a listener reaction"""
        minion = listener.minion
        
        # Check for specific reaction types based on minion keywords
        # This would be extended based on actual minion abilities
        
        # Example: Destroyer - attacks non-destroyer attackers
        if 'destroyer' in minion.get('keywords', []):
            if event.event_type == CombatEventType.ATTACK_DECLARED:
                if event.source and event.source != minion:
                    # Check if attacker is not a destroyer
                    if 'destroyer' not in event.source.get('keywords', []):
                        return {
                            'type': 'rage_attack',
                            'source_minion': minion,
                            'target': event.source,
                            'effect_data': {
                                'type': 'attack_target',
                                'target_minion': event.source
                            }
                        }
                        
        # Example: Spell Shield - redirects spell damage
        if 'spell_shield' in minion.get('keywords', []):
            if event.event_type == CombatEventType.SPELL_DAMAGE_DEALT:
                if event.source and event.source != minion:
                    damage_amount = event.data.get('damage', 0)
                    if damage_amount > 0:
                        return {
                            'type': 'spell_redirect',
                            'source_minion': minion,
                            'target': event.source,
                            'effect_data': {
                                'type': 'deal_damage',
                                'target': 'specific',
                                'target_minion': event.source,
                                'amount': damage_amount
                            }
                        }
                        
        # Use custom handler if provided
        if listener.handler:
            return listener.handler(event, minion, {})
            
        return None
        
    def suppress_event_type(self, event_type: CombatEventType):
        """Temporarily suppress an event type"""
        self.suppressed_events.add(event_type)
        
    def unsuppress_event_type(self, event_type: CombatEventType):
        """Remove suppression for an event type"""
        self.suppressed_events.discard(event_type)
        
    def clear_suppressions(self):
        """Clear all event suppressions"""
        self.suppressed_events.clear()
        
    def get_recent_events(self, count: int = 10,
                         event_type: Optional[CombatEventType] = None,
                         involving_minion: Optional[Dict] = None) -> List[CombatEvent]:
        """Get recent events with optional filtering"""
        events = self.event_history[-count*2:]
        
        if event_type:
            events = [e for e in events if e.event_type == event_type]
            
        if involving_minion:
            events = [e for e in events if e.involves(involving_minion)]
            
        return events[-count:]
        
    def count_events(self, event_type: CombatEventType,
                     source: Optional[Dict] = None,
                     target: Optional[Dict] = None) -> int:
        """Count events matching criteria"""
        count = 0
        for event in self.event_history:
            if event.event_type != event_type:
                continue
            if source and event.source != source:
                continue
            if target and event.target != target:
                continue
            count += 1
        return count
        
    def register_standard_listeners(self, minion: Dict):
        """
        Register standard listeners based on minion keywords
        
        This sets up the basic reactive abilities for minions.
        """
        keywords = minion.get('keywords', [])
        
        # Rage keyword - react to attacks/spells
        if 'rage' in keywords:
            listener = EventListener(
                minion=minion,
                event_types=[
                    CombatEventType.ATTACK_COMPLETED,
                    CombatEventType.SPELL_CAST,
                    CombatEventType.ABILITY_DAMAGE_DEALT
                ],
                condition=lambda e, m: e.source != m,  # Not from self
                priority=10
            )
            self.register_listener(listener)
            
        # Death watch - react to any death
        if 'on_any_death' in keywords:
            listener = EventListener(
                minion=minion,
                event_types=[CombatEventType.MINION_DEATH],
                priority=5
            )
            self.register_listener(listener)
            
        # Spell watch - react to any spell
        if 'on_any_cast' in keywords:
            listener = EventListener(
                minion=minion,
                event_types=[CombatEventType.SPELL_CAST],
                priority=5
            )
            self.register_listener(listener)
            
    def clear_dead_minion_listeners(self):
        """Remove listeners for dead minions"""
        self.listeners = [
            l for l in self.listeners 
            if l.minion.get('health', 0) > 0
        ]
        
    def debug_state(self) -> str:
        """Get debug string of event system state"""
        lines = ["=== Combat Event System ==="]
        lines.append(f"Active listeners: {len(self.listeners)}")
        lines.append(f"Events in history: {len(self.event_history)}")
        lines.append(f"Suppressed types: {', '.join(e.value for e in self.suppressed_events)}")
        
        if self.event_history:
            lines.append("\nRecent events:")
            for event in self.event_history[-5:]:
                source = event.source.get('name') if event.source else 'None'
                target = event.target.get('name') if event.target else 'None'
                lines.append(f"  - {event.event_type.value}: {source} -> {target}")
                
        return "\n".join(lines)