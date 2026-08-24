"""
Combat Context System - Manages combat context and effect history

This module tracks all effect contexts, enabling complex chained reactions
and providing a queryable history for reactive effects.
"""

import logging

logger = logging.getLogger(__name__)

from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
import copy


class EffectType(Enum):
    """Types of effects for categorization"""
    DAMAGE = "damage"
    HEAL = "heal"
    BUFF = "buff"
    DEBUFF = "debuff"
    SUMMON = "summon"
    DEATH = "death"
    ATTACK = "attack"
    SPELL = "spell"
    ABILITY = "ability"
    MOVEMENT = "movement"
    TRANSFORM = "transform"
    TRIGGER = "trigger"


class DamageSource(Enum):
    """Source types for damage"""
    ATTACK = "attack"           # Normal combat attack
    SPELL = "spell"             # Spell damage (cast effects)
    ABILITY = "ability"         # Ability damage (assault, death toll)
    COUNTER = "counter"         # Counter-attack damage
    FATIGUE = "fatigue"         # Fatigue damage
    EFFECT = "effect"           # Generic effect damage
    SELF = "self"               # Self-inflicted damage


@dataclass
class EffectContext:
    """
    Represents the context of a single effect
    
    This is saved for each effect that occurs, enabling
    other effects to query what happened and react accordingly.
    """
    effect_id: str                          # Unique ID for this effect
    effect_type: EffectType                 # Type of effect
    source_minion: Optional[Dict]           # Minion that caused the effect
    target_minions: List[Dict]              # Minions affected
    trigger_source: str                     # What triggered this (assault, cast, etc.)
    
    # Effect details
    damage_dealt: int = 0                   # Total damage dealt
    healing_done: int = 0                   # Total healing done
    stats_changed: Dict[str, int] = field(default_factory=dict)  # Stat changes applied
    minions_summoned: List[Dict] = field(default_factory=list)    # Summoned minions
    
    # Metadata for complex interactions
    damage_source: Optional[DamageSource] = None  # Source type for damage
    is_spell_damage: bool = False           # Was this spell damage?
    is_attack_damage: bool = False          # Was this attack damage?
    prevented_death: bool = False           # Did this prevent a death?
    caused_death: List[Dict] = field(default_factory=list)  # Minions killed by this effect
    
    # Chain tracking
    parent_effect_id: Optional[str] = None  # Effect that triggered this
    child_effect_ids: List[str] = field(default_factory=list)  # Effects triggered by this
    
    # Tags for special conditions
    tags: Set[str] = field(default_factory=set)  # Custom tags for special cases
    
    def add_tag(self, tag: str):
        """Add a tag to this effect context"""
        self.tags.add(tag)
        
    def has_tag(self, tag: str) -> bool:
        """Check if this effect has a tag"""
        return tag in self.tags
        
    def involves_minion(self, minion: Dict) -> bool:
        """Check if a minion was involved in this effect"""
        if self.source_minion == minion:
            return True
        return minion in self.target_minions
        
    def get_damage_to_minion(self, minion: Dict) -> int:
        """Get damage dealt to a specific minion"""
        if minion in self.target_minions and self.damage_dealt > 0:
            # Simple case: divide damage among targets
            # More complex tracking could be added
            return self.damage_dealt // len(self.target_minions)
        return 0


class CombatContextManager:
    """
    Manages the combat context throughout a battle
    
    This tracks all effects, maintains relationships between them,
    and provides querying capabilities for reactive effects.
    """
    
    def __init__(self):
        self.effect_history: List[EffectContext] = []
        self.effect_by_id: Dict[str, EffectContext] = {}
        self.current_chain: List[str] = []  # Current effect chain being processed
        self.effect_counter = 0
        
        # Context data that persists across effects
        self.combat_state: Optional[Dict] = None
        self.player_band: List[Dict] = []
        self.enemy_band: List[Dict] = []
        self.combat_registry = None
        self.run = None
        
    def initialize_combat(self, combat_state: Dict, player_band: List[Dict], 
                         enemy_band: List[Dict], registry=None, run=None):
        """Initialize the context manager for a new combat"""
        self.combat_state = combat_state
        self.player_band = player_band
        self.enemy_band = enemy_band
        self.combat_registry = registry
        self.run = run
        self.effect_history.clear()
        self.effect_by_id.clear()
        self.current_chain.clear()
        self.effect_counter = 0
        
    def create_effect_context(self, effect_type: EffectType, source_minion: Optional[Dict] = None,
                             trigger_source: str = "unknown") -> EffectContext:
        """Create a new effect context"""
        self.effect_counter += 1
        effect_id = f"effect_{self.effect_counter}_{effect_type.value}"
        
        # Set parent if we're in a chain
        parent_id = self.current_chain[-1] if self.current_chain else None
        
        context = EffectContext(
            effect_id=effect_id,
            effect_type=effect_type,
            source_minion=source_minion,
            target_minions=[],
            trigger_source=trigger_source,
            parent_effect_id=parent_id
        )
        
        # Link to parent
        if parent_id and parent_id in self.effect_by_id:
            self.effect_by_id[parent_id].child_effect_ids.append(effect_id)
            
        return context
        
    def record_effect(self, context: EffectContext):
        """Record an effect context in history"""
        self.effect_history.append(context)
        self.effect_by_id[context.effect_id] = context
        
        # Limit history size
        if len(self.effect_history) > 500:
            # Remove oldest effects
            removed = self.effect_history[:100]
            self.effect_history = self.effect_history[100:]
            for effect in removed:
                del self.effect_by_id[effect.effect_id]
                
        logger.debug(f"[CONTEXT] Recorded {context.effect_type.value} effect: {context.effect_id}")
        
    def begin_effect_chain(self, effect_id: str):
        """Begin tracking an effect chain"""
        self.current_chain.append(effect_id)
        
    def end_effect_chain(self):
        """End tracking the current effect chain"""
        if self.current_chain:
            self.current_chain.pop()
            
    def get_recent_effects(self, count: int = 10, 
                          effect_type: Optional[EffectType] = None,
                          involving_minion: Optional[Dict] = None) -> List[EffectContext]:
        """Get recent effects with optional filtering"""
        effects = self.effect_history[-count*2:]  # Get more than needed for filtering
        
        if effect_type:
            effects = [e for e in effects if e.effect_type == effect_type]
            
        if involving_minion:
            effects = [e for e in effects if e.involves_minion(involving_minion)]
            
        return effects[-count:]
        
    def get_last_spell_damage(self) -> Optional[EffectContext]:
        """Get the most recent spell damage effect"""
        for effect in reversed(self.effect_history):
            if effect.is_spell_damage and effect.damage_dealt > 0:
                return effect
        return None
        
    def get_last_attack(self, attacker: Optional[Dict] = None) -> Optional[EffectContext]:
        """Get the most recent attack effect"""
        for effect in reversed(self.effect_history):
            if effect.effect_type == EffectType.ATTACK:
                if attacker is None or effect.source_minion == attacker:
                    return effect
        return None
        
    def get_minion_death_count(self, minion_type: Optional[str] = None,
                               band_type: Optional[str] = None) -> int:
        """Count deaths matching criteria"""
        count = 0
        for effect in self.effect_history:
            for dead_minion in effect.caused_death:
                if minion_type and dead_minion.get('type') != minion_type:
                    continue
                    
                if band_type and self.combat_registry:
                    minion_band = self.combat_registry.get_minion_band_type(dead_minion)
                    if minion_band != band_type:
                        continue
                        
                count += 1
        return count
        
    def check_minion_cast_spell(self, minion: Dict) -> bool:
        """Check if a specific minion has cast a spell this combat"""
        for effect in self.effect_history:
            if (effect.trigger_source == 'cast' and 
                effect.source_minion == minion):
                return True
        return False
        
    def get_effects_by_source(self, source_minion: Dict) -> List[EffectContext]:
        """Get all effects caused by a specific minion"""
        return [e for e in self.effect_history if e.source_minion == source_minion]
        
    def get_damage_dealt_by_minion(self, minion: Dict) -> int:
        """Get total damage dealt by a minion"""
        total = 0
        for effect in self.get_effects_by_source(minion):
            total += effect.damage_dealt
        return total
        
    def get_effect_chain(self, effect_id: str) -> List[EffectContext]:
        """Get the full chain of effects starting from an effect"""
        chain = []
        to_process = [effect_id]
        
        while to_process:
            current_id = to_process.pop(0)
            if current_id in self.effect_by_id:
                effect = self.effect_by_id[current_id]
                chain.append(effect)
                to_process.extend(effect.child_effect_ids)
                
        return chain
        
    def create_combat_context_dict(self, attacker: Optional[Dict] = None, 
                                  defender: Optional[Dict] = None,
                                  acting_minion: Optional[Dict] = None) -> Dict:
        """
        Create a combat context dictionary for effect processing
        
        This maintains backward compatibility with the existing system while
        properly implementing the Absolute vs Relative Context requirement.

        Per the README:
        - Absolute Context: player_band/enemy_band always refer to actual player/enemy
        - Relative Context: ally_band/enemy_band refer to bands relative to acting minion
        """
        # Determine the acting minion (the one performing the action)
        acting = acting_minion or attacker

        # Start with absolute references
        context = {
            'attacker': attacker,
            'defender': defender,
            'acting_minion': acting,
            'player_band': self.player_band,  # Absolute player band
            'enemy_band': self.enemy_band,    # Absolute enemy band (NOTE: This is overridden below for relative!)
            'absolute_player_band': self.player_band,  # Explicit absolute
            'absolute_enemy_band': self.enemy_band,    # Explicit absolute
            'combat_registry': self.combat_registry,
            'combat_state': self.combat_state,
            'run': self.run,
            'context_manager': self  # Include self for effect tracking
        }

        # Now add RELATIVE bands based on the acting minion
        if acting and self.combat_registry:
            # Determine which band the acting minion belongs to
            band_type = self.combat_registry.get_minion_band_type(acting)

            if band_type == 'player':
                # Acting minion is in player band
                context['ally_band'] = self.player_band  # Allies are player band
                context['enemy_band'] = self.enemy_band  # Enemies are enemy band (relative)

            elif band_type == 'enemy':
                # Acting minion is in enemy band
                context['ally_band'] = self.enemy_band   # Allies are enemy band
                context['enemy_band'] = self.player_band # Enemies are player band (relative)

            else:
                # Fallback if band type cannot be determined
                logger.warning(f"[CONTEXT WARNING] Could not determine band for {acting.get('name', 'unknown')}")
                # Use absolute bands as fallback
                context['ally_band'] = self.player_band
                context['enemy_band'] = self.enemy_band
        else:
            # No acting minion or registry, use absolute bands as fallback
            context['ally_band'] = self.player_band
            # enemy_band already set to absolute enemy band above

        # Debug print to verify context setup
        if acting:
            logger.debug(f"[CONTEXT] Created context for {acting.get('name', 'unknown')}: "
                  f"ally_band has {len(context.get('ally_band', []))} minions, "
                  f"enemy_band has {len(context.get('enemy_band', []))} minions (relative)")

        return context
        
    def get_animation_events(self, since_effect_id: Optional[str] = None) -> List[Dict]:
        """
        Get animation events for all effects since a given effect
        
        This prepares data for the frontend animation system.
        """
        events = []
        start_index = 0
        
        if since_effect_id:
            for i, effect in enumerate(self.effect_history):
                if effect.effect_id == since_effect_id:
                    start_index = i + 1
                    break
                    
        for effect in self.effect_history[start_index:]:
            event = {
                'id': effect.effect_id,
                'type': effect.effect_type.value,
                'source': effect.source_minion.get('name') if effect.source_minion else None,
                'targets': [m.get('name') for m in effect.target_minions],
                'trigger': effect.trigger_source,
                'damage': effect.damage_dealt,
                'healing': effect.healing_done,
                'tags': list(effect.tags)
            }
            events.append(event)
            
        return events
        
    def debug_state(self) -> str:
        """Get a debug string of the current context state"""
        lines = ["=== Combat Context State ==="]
        lines.append(f"Effects recorded: {len(self.effect_history)}")
        lines.append(f"Current chain depth: {len(self.current_chain)}")
        
        if self.effect_history:
            lines.append("\nRecent effects:")
            for effect in self.effect_history[-5:]:
                source = effect.source_minion.get('name') if effect.source_minion else 'Unknown'
                targets = ', '.join(m.get('name') for m in effect.target_minions) or 'None'
                lines.append(f"  - {effect.effect_type.value} by {source} -> {targets}")
                
        return "\n".join(lines)