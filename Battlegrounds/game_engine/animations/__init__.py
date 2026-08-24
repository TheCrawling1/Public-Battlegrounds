"""
Animation System - Central dispatcher for game animations

This module provides the interface between combat effects and animation definitions.
Animations are purely presentational and do not affect game logic.

The system works by:
1. Combat effects request animations through get_animation_for_effect()
2. Animation definitions provide metadata for frontend playback
3. Frontend receives animation metadata in interpreter commands
4. animations.js handles the actual visual playback

DESIGN PRINCIPLES:
- Animations are metadata only - no game logic
- Flexible and configurable through parameters
- Can be disabled/modified without affecting combat
- Support start/stop/resume functionality

UPDATED: Added template animation support for complex multi-element animations
"""

import logging

logger = logging.getLogger(__name__)

from typing import Dict, List, Optional, Any
from game_engine.animations.simple_animations import SimpleAnimations
from game_engine.animations.template_animations import TemplateAnimations


class AnimationDispatcher:
    """
    Central dispatcher for all game animations

    Routes effect types to appropriate animation definitions
    and combines multiple animations when needed.

    UPDATED: Now supports both simple animations and template-based animations
    """

    def __init__(self):
        self.simple_animations = SimpleAnimations()
        self.template_animations = TemplateAnimations()

        # Map effect types to animation providers
        self.animation_providers = {
            'simple': self.simple_animations,
            'template': self.template_animations,
        }

    def get_animation_for_effect(self, effect_type: str, **context) -> Optional[Dict]:
        """
        Get animation metadata for a specific effect

        Args:
            effect_type: Type of effect (heal, deal_damage, etc.)
            **context: Additional context (source_golden, trigger_type, etc.)

        Returns:
            Animation metadata dict or None if no animation
        """
        # Start with simple animations for basic effects
        animation = self.simple_animations.get_animation(effect_type, **context)

        if animation:
            # Add common metadata
            animation['system'] = 'simple'
            animation['effect_type'] = effect_type

        return animation

    def get_animation_for_trigger(self, trigger_type: str, **context) -> Optional[Dict]:
        """
        Get animation metadata for a trigger type

        Args:
            trigger_type: Type of trigger (assault, cast, etc.)
            **context: Additional context (source_golden, etc.)

        Returns:
            Animation metadata dict or None if no animation
        """
        # Map trigger types to effect types for animation purposes
        trigger_to_effect_map = {
            'assault': 'trigger_assault',
            'cast': 'trigger_cast',
            'death_toll': 'trigger_death_toll',
            'rage': 'trigger_rage',
            'on_any_death': 'trigger_on_any_death',
            'on_any_cast': 'trigger_on_any_cast',
            'on_any_summon': 'trigger_on_any_summon'
        }

        effect_type = trigger_to_effect_map.get(trigger_type)
        if effect_type:
            return self.get_animation_for_effect(effect_type, **context)

        return None

    def get_template_animation(self, template_name: str, **context) -> Optional[Dict]:
        """
        Get a template-based animation

        Args:
            template_name: Name of the template (e.g., 'wizard_spell_barrage')
            **context: Context parameters for template customization

        Returns:
            Template animation metadata dict or None if template not found
        """
        template = self.template_animations.get_template(template_name, **context)

        if template:
            # Add system metadata
            template['system'] = 'template'
            template['template_name'] = template_name

        return template

    def get_animation_for_bundle(self, bundle_type: str, **context) -> Optional[Dict]:
        """
        Get animation for a bundle type, preferring templates over hardcoded bundles

        Args:
            bundle_type: Type of bundle (e.g., 'wizard_spell_barrage')
            **context: Additional context for customization

        Returns:
            Animation metadata dict (template or fallback) or None
        """
        # Try to get a template animation first
        template_animation = self.get_template_animation(bundle_type, **context)
        if template_animation:
            logger.debug(f"[ANIMATIONS] Using template for bundle: {bundle_type}")
            return template_animation

        # Fallback to legacy bundle handling if no template found
        logger.debug(f"[ANIMATIONS] No template found for bundle: {bundle_type}, using legacy handling")
        return None

    def combine_animations(self, animations: List[Dict]) -> Dict:
        """
        Combine multiple animations into a single animation metadata

        Args:
            animations: List of animation metadata dicts

        Returns:
            Combined animation metadata
        """
        if not animations:
            return None

        if len(animations) == 1:
            return animations[0]

        # Combine multiple animations
        combined = {
            'type': 'combined',
            'animations': animations,
            'duration': max(anim.get('duration', 0) for anim in animations),
            'parallel': True  # Run all animations in parallel
        }

        return combined

    def get_template_list(self) -> List[str]:
        """Get list of all available animation templates"""
        return self.template_animations.get_all_template_names()

    def template_exists(self, template_name: str) -> bool:
        """Check if a template exists"""
        return self.template_animations.template_exists(template_name)

    def get_template_info(self, template_name: str) -> Optional[Dict]:
        """Get basic info about a template"""
        return self.template_animations.get_template_info(template_name)


# Global animation dispatcher instance
_animation_dispatcher = AnimationDispatcher()


def get_animation_for_effect(effect_type: str, **context) -> Optional[Dict]:
    """
    Main interface for getting effect animations

    Args:
        effect_type: Type of effect requesting animation
        **context: Additional context for animation selection

    Returns:
        Animation metadata dict or None
    """
    return _animation_dispatcher.get_animation_for_effect(effect_type, **context)


def get_animation_for_trigger(trigger_type: str, **context) -> Optional[Dict]:
    """
    Main interface for getting trigger animations

    Args:
        trigger_type: Type of trigger requesting animation
        **context: Additional context for animation selection

    Returns:
        Animation metadata dict or None
    """
    return _animation_dispatcher.get_animation_for_trigger(trigger_type, **context)


def get_template_animation(template_name: str, **context) -> Optional[Dict]:
    """
    Main interface for getting template animations

    Args:
        template_name: Name of the template
        **context: Context parameters for template customization

    Returns:
        Template animation metadata dict or None
    """
    return _animation_dispatcher.get_template_animation(template_name, **context)


def get_animation_for_bundle(bundle_type: str, **context) -> Optional[Dict]:
    """
    Main interface for getting bundle animations (template-first)

    Args:
        bundle_type: Type of bundle requesting animation
        **context: Additional context for animation selection

    Returns:
        Animation metadata dict or None
    """
    return _animation_dispatcher.get_animation_for_bundle(bundle_type, **context)


def combine_animations(animations: List[Dict]) -> Dict:
    """
    Combine multiple animations into one

    Args:
        animations: List of animation metadata dicts

    Returns:
        Combined animation metadata
    """
    return _animation_dispatcher.combine_animations(animations)


def get_available_templates() -> List[str]:
    """Get list of all available animation templates"""
    return _animation_dispatcher.get_template_list()


def template_exists(template_name: str) -> bool:
    """Check if an animation template exists"""
    return _animation_dispatcher.template_exists(template_name)


def get_template_info(template_name: str) -> Optional[Dict]:
    """Get basic info about an animation template"""
    return _animation_dispatcher.get_template_info(template_name)