"""
Template Animations - Template-based animation system for complex multi-element animations

This module defines animation templates that can be assembled from building blocks
in the frontend. Templates define the structure and coordination of complex animations
without hardcoding specific visual implementations.

Templates consist of:
- Primitives: Basic visual elements (line, glow, particle, flash, number)
- Targeting: How to find source/target positions
- Coordination: How elements are timed relative to each other
- Properties: Customizable parameters for each element
"""

from typing import Dict, List, Optional, Any


class TemplatePrimitives:
    """Defines the basic building blocks available for animation templates"""

    # Existing primitives
    LINE = 'line'  # Line from point A to point B (can be jagged for lightning)
    GLOW = 'glow'  # Glow effect on target element
    PARTICLE = 'particle'  # Particle effect (explosion, sparkle, etc.)
    FLASH = 'flash'  # Flash effect on target element
    NUMBER = 'number'  # Floating number display (damage, heal, etc.)
    PULSE = 'pulse'  # Pulse/scale effect on target
    FADE = 'fade'  # Fade in/out effect

    # New generic primitives
    PROJECTILE = 'projectile'  # Straight-line projectile (arrow, bullet, magic missile)
    ARC = 'arc'  # Curved/arcing projectile (thrown rock, lobbed bomb, healing orb)
    EXPLOSION = 'explosion'  # Radial burst effect (AoE damage, bomb, death burst)
    SLASH = 'slash'  # Arc/slash motion (melee attack, cleave, swipe)
    BEAM = 'beam'  # Sustained beam that stays connected (laser, drain, tether)
    SHOCKWAVE = 'shockwave'  # Expanding ring effect (ground slam, stun wave)
    SPRAY = 'spray'  # Multiple projectiles in a spread pattern (shotgun, cone)
    CHAIN = 'chain'  # Effect that jumps between targets (chain lightning, bouncing)


class TemplateTargeting:
    """Defines targeting types for template elements"""

    SOURCE_CENTER = 'source_center'  # Center of source minion
    TARGET_CENTER = 'target_center'  # Center of target minion
    EACH_TARGET_CENTER = 'each_target_center'  # Center of each target (iterator)
    SCREEN_POSITION = 'screen_position'  # Absolute screen coordinates
    RELATIVE_TO_SOURCE = 'relative_to_source'  # Offset from source
    RELATIVE_TO_TARGET = 'relative_to_target'  # Offset from target


class TemplateCoordination:
    """Defines how template elements are coordinated in time"""

    SEQUENCE = 'sequence'  # Elements play one after another
    PARALLEL = 'parallel'  # Elements play simultaneously
    STAGGER = 'stagger'  # Elements play with delays between them


class TemplateAnimations:
    """
    Provider for template-based animations

    Templates define complex animations as combinations of primitives
    with coordination and timing information.
    """

    def __init__(self):
        # Define all available animation templates
        self.templates = {
            'wizard_spell_barrage': self._create_wizard_spell_barrage_template(),
            'huntsman_arrow_shot': self._create_huntsman_arrow_shot_template(),
            'multi_shot_arrows': self._create_multi_shot_arrows_template(),
            'chain_lightning': self._create_chain_lightning_template(),
            'healing_beams': self._create_healing_beams_template(),
            'buff_rays': self._create_buff_rays_template(),
            'cabal_dark_bolt': self._create_cabal_dark_bolt_template()
        }

    def get_template(self, template_name: str, **context) -> Optional[Dict]:
        """
        Get a template definition by name with context parameters

        Args:
            template_name: Name of the template to retrieve
            **context: Context parameters for template customization

        Returns:
            Template definition dict or None if not found
        """
        template = self.templates.get(template_name)
        if not template:
            return None

        # Apply context parameters to customize the template
        return self._apply_context_to_template(template, context)

    def _apply_context_to_template(self, template: Dict, context: Dict) -> Dict:
        """Apply context parameters to customize a template"""
        import copy
        customized = copy.deepcopy(template)

        # Apply golden modifications if source is golden
        if context.get('source_golden', False):
            customized['duration'] = int(customized.get('duration', 1000) * 1.2)

            # Enhance visual properties for golden effects
            for element in customized.get('elements', []):
                if 'properties' in element:
                    if 'thickness' in element['properties']:
                        element['properties']['thickness'] *= 1.5
                    if 'intensity' in element['properties'] and element['properties']['intensity'] != 'high':
                        element['properties']['intensity'] = 'high'
                    # Golden lightning bolts have enhanced jaggedness
                    if element['properties'].get('jagged'):
                        element['properties']['jaggedness_intensity'] = 'high'

        # Apply any custom properties from context
        custom_properties = context.get('properties', {})
        if custom_properties:
            for element in customized.get('elements', []):
                if 'properties' in element:
                    element['properties'].update(custom_properties)

        return customized

    def _create_wizard_spell_barrage_template(self) -> Dict:
        """
        Create the wizard spell barrage template - UPDATED for lightning bolts

        This replaces the hardcoded wizard bolt animation with a template that:
        1. Shows a cast glow on the wizard
        2. Creates jagged lightning bolts from wizard to each target simultaneously
        3. Shows impact effects on targets
        """
        return {
            'name': 'wizard_spell_barrage',
            'type': 'template',
            'description': 'Wizard casts multiple lightning bolts to targets',
            'duration': 1200,  # Total template duration
            'coordination': TemplateCoordination.SEQUENCE,
            'elements': [
                {
                    'id': 'cast_glow',
                    'primitive': TemplatePrimitives.GLOW,
                    'target': TemplateTargeting.SOURCE_CENTER,
                    'properties': {
                        'color': '#FFFFFF',  # Bright white for lightning theme
                        'intensity': 'high',
                        'pulse': True,
                        'pulse_speed': 'fast'
                    },
                    'timing': {
                        'delay': 0,
                        'duration': 300
                    }
                },
                {
                    'id': 'lightning_bolts',
                    'primitive': TemplatePrimitives.LINE,
                    'from': TemplateTargeting.SOURCE_CENTER,
                    'to': TemplateTargeting.EACH_TARGET_CENTER,  # Multi-target iterator
                    'properties': {
                        'style': 'lightning',  # Lightning style instead of arcane_bolt
                        'color': '#FFFFFF',    # Bright white
                        'thickness': 2,        # Slightly thinner for lightning
                        'jagged': True,        # Enable jagged rendering
                        'jaggedness_intensity': 'medium',  # How jagged the lines are
                        'flicker': True,       # Add flickering effect
                        'glow': True,
                        'glow_color': '#DDDDFF',  # Subtle blue-white glow
                        'travel_speed': 'fast',
                        'randomize_path': True  # Different jagged path each time
                    },
                    'coordination': 'simultaneous',  # All bolts fire at once
                    'timing': {
                        'delay': 200,  # Start after cast glow
                        'duration': 400  # Lightning bolt travel time
                    }
                },
                {
                    'id': 'impact_effects',
                    'primitive': TemplatePrimitives.FLASH,
                    'target': TemplateTargeting.EACH_TARGET_CENTER,
                    'properties': {
                        'color': '#FFFFFF',    # White lightning impact
                        'intensity': 'high',   # Bright impact
                        'flash_type': 'lightning_impact'
                    },
                    'timing': {
                        'delay': 600,  # Start when bolts arrive (200 + 400)
                        'duration': 200
                    }
                }
            ]
        }

    def _create_huntsman_arrow_shot_template(self) -> Dict:
        """
        Create the huntsman arrow shot template

        Single arrow object that:
        1. Appears at huntsman position
        2. Flies straight to target
        3. Loses head on impact and embeds for 500ms
        """
        return {
            'name': 'huntsman_arrow_shot',
            'type': 'template',
            'description': 'Huntsman fires an arrow that embeds in target',
            'duration': 800,  # Flight time + embedding time
            'coordination': TemplateCoordination.SEQUENCE,
            'elements': [
                {
                    'id': 'arrow_shot',
                    'primitive': TemplatePrimitives.LINE,
                    'from': TemplateTargeting.SOURCE_CENTER,
                    'to': TemplateTargeting.TARGET_CENTER,
                    'properties': {
                        'style': 'arrow',
                        'color': '#8B4513',  # Brown arrow shaft
                        'thickness': 2,
                        'arrow_head_color': '#666666',  # Gray arrowhead
                        'fletching_color': '#654321',  # Darker brown fletching
                        'travel_speed': 'medium',
                        'embed_on_impact': True,
                        'embed_duration': 500  # Half a second embedded
                    },
                    'timing': {
                        'delay': 0,
                        'duration': 800  # Total including embedding time
                    }
                }
            ]
        }

    def _create_multi_shot_arrows_template(self) -> Dict:
        """Template for archer-style multi-shot attacks"""
        return {
            'name': 'multi_shot_arrows',
            'type': 'template',
            'description': 'Archer fires multiple arrows at targets',
            'duration': 1000,
            'coordination': TemplateCoordination.SEQUENCE,
            'elements': [
                {
                    'id': 'draw_glow',
                    'primitive': TemplatePrimitives.GLOW,
                    'target': TemplateTargeting.SOURCE_CENTER,
                    'properties': {
                        'color': '#8B4513',
                        'intensity': 'medium'
                    },
                    'timing': {
                        'delay': 0,
                        'duration': 200
                    }
                },
                {
                    'id': 'arrow_lines',
                    'primitive': TemplatePrimitives.LINE,
                    'from': TemplateTargeting.SOURCE_CENTER,
                    'to': TemplateTargeting.EACH_TARGET_CENTER,
                    'properties': {
                        'style': 'arrow',
                        'color': '#8B4513',
                        'thickness': 2,
                        'travel_speed': 'medium'
                    },
                    'coordination': 'stagger',  # Arrows fire with slight delays
                    'timing': {
                        'delay': 150,
                        'duration': 300,
                        'stagger_delay': 100  # 100ms between each arrow
                    }
                }
            ]
        }

    def _create_chain_lightning_template(self) -> Dict:
        """Template for chain lightning effects"""
        return {
            'name': 'chain_lightning',
            'type': 'template',
            'description': 'Lightning chains between targets',
            'duration': 800,
            'coordination': TemplateCoordination.SEQUENCE,
            'elements': [
                {
                    'id': 'lightning_chain',
                    'primitive': TemplatePrimitives.LINE,
                    'from': TemplateTargeting.SOURCE_CENTER,
                    'to': TemplateTargeting.EACH_TARGET_CENTER,
                    'properties': {
                        'style': 'lightning',
                        'color': '#FFFF00',
                        'thickness': 2,
                        'jagged': True,
                        'flicker': True
                    },
                    'coordination': 'sequence',  # Chain one after another
                    'timing': {
                        'delay': 100,
                        'duration': 500,
                        'sequence_delay': 150  # 150ms between each chain link
                    }
                }
            ]
        }

    def _create_healing_beams_template(self) -> Dict:
        """Template for healing beam effects"""
        return {
            'name': 'healing_beams',
            'type': 'template',
            'description': 'Gentle healing beams to targets',
            'duration': 1000,
            'coordination': TemplateCoordination.PARALLEL,
            'elements': [
                {
                    'id': 'heal_beams',
                    'primitive': TemplatePrimitives.LINE,
                    'from': TemplateTargeting.SOURCE_CENTER,
                    'to': TemplateTargeting.EACH_TARGET_CENTER,
                    'properties': {
                        'style': 'beam',
                        'color': '#44FF44',
                        'thickness': 4,
                        'soft_glow': True,
                        'travel_speed': 'slow'
                    },
                    'coordination': 'simultaneous',
                    'timing': {
                        'delay': 0,
                        'duration': 600
                    }
                },
                {
                    'id': 'heal_sparkles',
                    'primitive': TemplatePrimitives.PARTICLE,
                    'target': TemplateTargeting.EACH_TARGET_CENTER,
                    'properties': {
                        'particle_type': 'sparkle',
                        'color': '#66FF66',
                        'count': 8,
                        'spread': 'medium'
                    },
                    'timing': {
                        'delay': 500,  # Start when beams arrive
                        'duration': 400
                    }
                }
            ]
        }

    def _create_buff_rays_template(self) -> Dict:
        """Template for buff ray effects"""
        return {
            'name': 'buff_rays',
            'type': 'template',
            'description': 'Buff rays emanating to targets',
            'duration': 800,
            'coordination': TemplateCoordination.PARALLEL,
            'elements': [
                {
                    'id': 'buff_rays',
                    'primitive': TemplatePrimitives.LINE,
                    'from': TemplateTargeting.SOURCE_CENTER,
                    'to': TemplateTargeting.EACH_TARGET_CENTER,
                    'properties': {
                        'style': 'ray',
                        'color': '#4444FF',
                        'thickness': 3,
                        'pulsing': True,
                        'travel_speed': 'medium'
                    },
                    'coordination': 'simultaneous',
                    'timing': {
                        'delay': 0,
                        'duration': 500
                    }
                },
                {
                    'id': 'buff_aura',
                    'primitive': TemplatePrimitives.GLOW,
                    'target': TemplateTargeting.EACH_TARGET_CENTER,
                    'properties': {
                        'color': '#6666FF',
                        'intensity': 'medium',
                        'pulse': True
                    },
                    'timing': {
                        'delay': 400,
                        'duration': 300
                    }
                }
            ]
        }

    def _create_cabal_dark_bolt_template(self) -> Dict:
        """
        Create the Cabal dark bolt template

        A single red glowing arc projectile from Cabal to its target.
        The arc curves upward slightly before hitting the target.
        """
        return {
            'name': 'cabal_dark_bolt',
            'type': 'template',
            'description': 'Cabal fires a dark red bolt at target',
            'duration': 600,
            'coordination': TemplateCoordination.SEQUENCE,
            'elements': [
                {
                    'id': 'cast_glow',
                    'primitive': TemplatePrimitives.GLOW,
                    'target': TemplateTargeting.SOURCE_CENTER,
                    'properties': {
                        'color': '#FF2222',
                        'intensity': 'high',
                        'pulse': True,
                        'pulse_speed': 'fast'
                    },
                    'timing': {
                        'delay': 0,
                        'duration': 150
                    }
                },
                {
                    'id': 'dark_bolt',
                    'primitive': TemplatePrimitives.ARC,
                    'from': TemplateTargeting.SOURCE_CENTER,
                    'to': TemplateTargeting.EACH_TARGET_CENTER,  # Multi-target iterator
                    'properties': {
                        'color': '#FF3333',
                        'size': 12,
                        'arcHeight': 60,
                        'glow': True
                    },
                    'coordination': 'simultaneous',  # All bolts fire at once
                    'timing': {
                        'delay': 100,
                        'duration': 400
                    }
                },
                {
                    'id': 'impact_flash',
                    'primitive': TemplatePrimitives.FLASH,
                    'target': TemplateTargeting.EACH_TARGET_CENTER,  # Multi-target iterator
                    'properties': {
                        'color': '#FF4444',
                        'intensity': 'high'
                    },
                    'timing': {
                        'delay': 500,
                        'duration': 100
                    }
                }
            ]
        }

    def get_all_template_names(self) -> List[str]:
        """Get list of all available template names"""
        return list(self.templates.keys())

    def template_exists(self, template_name: str) -> bool:
        """Check if a template exists"""
        return template_name in self.templates

    def get_template_info(self, template_name: str) -> Optional[Dict]:
        """Get basic info about a template without full definition"""
        template = self.templates.get(template_name)
        if not template:
            return None

        return {
            'name': template.get('name'),
            'description': template.get('description'),
            'duration': template.get('duration'),
            'element_count': len(template.get('elements', []))
        }