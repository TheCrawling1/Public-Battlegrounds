"""
Simple Animations - Basic visual effects for combat

This module defines simple, reusable animations that can be applied to minions
and combat elements. All animations are defined as metadata that the frontend
animation system can interpret and play.

Each animation definition includes:
- type: Animation type identifier
- duration: How long the animation should run (ms)
- properties: Animation-specific parameters
- controllable: Whether the animation can be paused/resumed
- autoCleanup: Whether the animation auto-cleans up when duration expires (FIXED for death animations)
"""

import logging

logger = logging.getLogger(__name__)

from typing import Dict, Optional, Any


class SimpleAnimations:
    """
    Provider for simple visual animations

    Focuses on basic effects like glows, flashes, and color changes
    that can be applied to any minion or game element.
    """

    def __init__(self):
        # Define color schemes for different effect types
        self.effect_colors = {
            # Damage effects
            'deal_damage': '#FF4444',      # Red
            'combat_damage': '#FF6666',    # Light red
            'counter_damage': '#FF8888',   # Lighter red

            # Healing effects
            'heal': '#44FF44',             # Green
            'heal_self': '#66FF66',        # Light green

            # Buff effects
            'buff_stats': '#4444FF',       # Blue
            'permanent_stat_gain': '#6644FF', # Purple-blue

            # Debuff effects
            'debuff_stats': '#AA44AA',     # Purple

            # Trigger effects
            'trigger_assault': '#FF8844',  # Orange
            'trigger_cast': '#AA44FF',     # Purple
            'trigger_death_toll': '#444444', # Dark gray
            'trigger_rage': '#FF4444',     # Red
            'trigger_on_any_death': '#666666', # Gray
            'trigger_on_any_cast': '#8844FF',  # Light purple
            'trigger_on_any_summon': '#44AA44', # Dark green

            # Special effects
            'summon': '#FFFF44',           # Yellow
            'death': '#222222',            # Very dark
            'stun': '#FFAA44',            # Orange-yellow
            'move_minion': '#44AAFF',      # Cyan
        }

    def get_animation(self, effect_type: str, **context) -> Optional[Dict]:
        """
        Get animation metadata for an effect type

        Args:
            effect_type: The type of effect requesting animation
            **context: Additional context (target_id, source_golden, etc.)

        Returns:
            Animation metadata dict or None if no animation
        """
        logger.debug(f"[SIMPLE_ANIMATIONS] Requesting animation for effect_type: {effect_type}")

        # Get base animation based on effect type
        if effect_type in ['deal_damage', 'combat_damage', 'counter_damage']:
            return self._create_damage_glow_animation(effect_type, **context)

        elif effect_type in ['heal', 'heal_self']:
            return self._create_heal_glow_animation(effect_type, **context)

        elif effect_type in ['buff_stats', 'permanent_stat_gain']:
            return self._create_buff_glow_animation(effect_type, **context)

        elif effect_type == 'debuff_stats':
            return self._create_debuff_glow_animation(effect_type, **context)

        elif effect_type.startswith('trigger_'):
            logger.debug(f"[SIMPLE_ANIMATIONS] Creating trigger animation for: {effect_type}")
            return self._create_trigger_glow_animation(effect_type, **context)

        elif effect_type == 'summon':
            return self._create_summon_glow_animation(effect_type, **context)

        elif effect_type == 'death':
            return self._create_death_animation(effect_type, **context)

        elif effect_type == 'stun':
            return self._create_stun_glow_animation(effect_type, **context)

        elif effect_type == 'move_minion':
            return self._create_move_animation(effect_type, **context)

        logger.debug(f"[SIMPLE_ANIMATIONS] No animation found for effect_type: {effect_type}")
        # No animation for this effect type
        return None

    def _create_glow_animation(self, effect_type: str, color: str = None,
                              duration: int = 800, intensity: str = 'medium',
                              **context) -> Dict:
        """
        Create a basic glow animation

        Args:
            effect_type: Type of effect for identification
            color: Glow color (hex color code)
            duration: Animation duration in milliseconds
            intensity: Glow intensity ('low', 'medium', 'high')
            **context: Additional context (target_id, etc.)

        Returns:
            Glow animation metadata
        """
        if color is None:
            color = self.effect_colors.get(effect_type, '#FFFFFF')

        # Adjust intensity based on golden status
        if context.get('source_golden', False):
            intensity = 'high'
            duration = int(duration * 1.2)  # Golden effects last longer

        return {
            'type': 'glow',
            'duration': duration,
            'controllable': True,  # Can be paused/resumed
            'autoCleanup': True,   # Glow effects auto-cleanup when duration expires
            'properties': {
                'color': color,
                'intensity': intensity,
                'fade_in': 200,   # Fade in duration (ms)
                'fade_out': 300,  # Fade out duration (ms)
                'pulse': False,   # Whether to pulse the glow
                'target_id': context.get('target_id'),
                'effect_type': effect_type
            }
        }

    def _create_damage_glow_animation(self, effect_type: str, **context) -> Dict:
        """Create glow animation for damage effects"""
        return self._create_glow_animation(
            effect_type=effect_type,
            duration=600,
            intensity='high',
            **context
        )

    def _create_heal_glow_animation(self, effect_type: str, **context) -> Dict:
        """Create glow animation for healing effects"""
        return self._create_glow_animation(
            effect_type=effect_type,
            duration=800,
            intensity='medium',
            **context
        )

    def _create_buff_glow_animation(self, effect_type: str, **context) -> Dict:
        """Create glow animation for buff effects"""
        glow = self._create_glow_animation(
            effect_type=effect_type,
            duration=1000,
            intensity='medium',
            **context
        )
        # Buffs pulse to show positive effect
        glow['properties']['pulse'] = True
        return glow

    def _create_debuff_glow_animation(self, effect_type: str, **context) -> Dict:
        """Create glow animation for debuff effects"""
        return self._create_glow_animation(
            effect_type=effect_type,
            duration=800,
            intensity='medium',
            **context
        )

    def _create_trigger_glow_animation(self, effect_type: str, **context) -> Dict:
        """Create glow animation for trigger effects"""
        glow = self._create_glow_animation(
            effect_type=effect_type,
            duration=1200,
            intensity='high',
            **context
        )
        # Triggers pulse to show activation
        glow['properties']['pulse'] = True
        glow['properties']['pulse_speed'] = 'fast'
        return glow

    def _create_summon_glow_animation(self, effect_type: str, **context) -> Dict:
        """Create glow animation for summon effects"""
        glow = self._create_glow_animation(
            effect_type=effect_type,
            duration=1500,
            intensity='high',
            **context
        )
        # Summons have a special appear effect
        glow['properties']['appear_effect'] = True
        return glow

    def _create_death_animation(self, effect_type: str, **context) -> Dict:
        """
        Create animation for death effects - FIXED: Persistent until manual cleanup

        Args:
            effect_type: Type of effect for identification
            **context: Additional context (target_id, etc.)

        Returns:
            Death animation metadata with autoCleanup disabled
        """
        return {
            'type': 'death_fade',
            'duration': 1000,
            'controllable': True,
            'autoCleanup': False,  # FIXED: Death animations persist until manually cleaned up
            'properties': {
                'fade_out_duration': 800,
                'color_shift': '#222222',
                'target_id': context.get('target_id'),
                'effect_type': effect_type
            }
        }

    def _create_stun_glow_animation(self, effect_type: str, **context) -> Dict:
        """Create glow animation for stun effects"""
        glow = self._create_glow_animation(
            effect_type=effect_type,
            duration=1000,
            intensity='medium',
            **context
        )
        # Stun has a special pulsing pattern
        glow['properties']['pulse'] = True
        glow['properties']['pulse_pattern'] = 'stun'  # Special stun pulse pattern
        return glow

    def _create_move_animation(self, effect_type: str, **context) -> Dict:
        """Create animation for movement effects"""
        return {
            'type': 'move_highlight',
            'duration': 600,
            'controllable': True,
            'autoCleanup': True,  # Move animations auto-cleanup normally
            'properties': {
                'color': self.effect_colors.get(effect_type, '#44AAFF'),
                'target_id': context.get('target_id'),
                'from_position': context.get('from_position'),
                'to_position': context.get('to_position'),
                'effect_type': effect_type
            }
        }

    def create_custom_glow(self, target_id: str, color: str, duration: int = 800,
                          intensity: str = 'medium', pulse: bool = False) -> Dict:
        """
        Create a custom glow animation with specific parameters

        Args:
            target_id: ID of the target element
            color: Hex color code for the glow
            duration: Animation duration in milliseconds
            intensity: Glow intensity ('low', 'medium', 'high')
            pulse: Whether the glow should pulse

        Returns:
            Custom glow animation metadata
        """
        return {
            'type': 'glow',
            'duration': duration,
            'controllable': True,
            'autoCleanup': True,  # Custom glows auto-cleanup by default
            'properties': {
                'color': color,
                'intensity': intensity,
                'fade_in': 200,
                'fade_out': 300,
                'pulse': pulse,
                'target_id': target_id,
                'effect_type': 'custom'
            }
        }