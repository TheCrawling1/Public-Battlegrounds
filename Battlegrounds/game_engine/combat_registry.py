"""
Combat Registry - Centralized combat state tracking system

This system maintains a clear registry of all minions in combat with unique IDs,
explicit band membership, and position tracking. This solves the issue of minions
not being able to determine their band membership during combat effects.

IMPORTANT: The registry maintains band membership even for dead minions to ensure
death toll effects work correctly.
"""

import logging

logger = logging.getLogger(__name__)

import uuid
from typing import Dict, List, Optional, Any


class CombatRegistry:
    """
    Manages combat state with explicit band tracking and unique combat IDs.

    This registry is created for each combat instance and maintains:
    - Unique combat IDs for each minion
    - Explicit band membership (player/enemy)
    - Position information
    - Minion lookup by combat ID
    - Band membership queries
    - Persistent tracking even for dead minions
    """

    def __init__(self):
        """Initialize an empty combat registry"""
        self.combat_minions = {}  # combat_id -> minion reference
        self.band_membership = {}  # combat_id -> 'player' or 'enemy'
        self.position_map = {}  # combat_id -> position in band
        self.band_ids_map = {}  # combat_id -> original band_id (for player minions)
        self.player_combat_ids = []  # Ordered list of player combat IDs
        self.enemy_combat_ids = []  # Ordered list of enemy combat IDs

        # Debug tracking
        self.debug_enabled = True

    def register_band(self, band: List[Dict], band_type: str) -> List[str]:
        """
        Register an entire band with the combat registry

        Args:
            band: List of minion dictionaries
            band_type: 'player' or 'enemy'

        Returns:
            List of combat IDs assigned to the band
        """
        combat_ids = []

        if self.debug_enabled:
            logger.debug(f"[REGISTRY] Registering {band_type} band with {len(band)} minions")

        for position, minion in enumerate(band):
            combat_id = self.register_minion(minion, band_type, position)
            combat_ids.append(combat_id)

        return combat_ids

    def register_minion(self, minion: Dict, band_type: str, position: int) -> str:
        """
        Register a single minion with the combat registry

        Args:
            minion: Minion dictionary
            band_type: 'player' or 'enemy'
            position: Position in the band

        Returns:
            Unique combat ID assigned to the minion
        """
        # Generate unique combat ID
        combat_id = str(uuid.uuid4())

        # Store the minion reference
        self.combat_minions[combat_id] = minion

        # Store band membership - THIS IS PERMANENT
        self.band_membership[combat_id] = band_type

        # Store position
        self.position_map[combat_id] = position
        minion['position'] = position  # Also set on minion dict for direct access

        # Store original band_id if it exists (for player minions)
        if 'band_id' in minion:
            self.band_ids_map[combat_id] = minion['band_id']

        # Add combat_id to the minion for easy reference
        minion['_combat_id'] = combat_id

        # Add to appropriate band list
        if band_type == 'player':
            self.player_combat_ids.append(combat_id)
        else:
            self.enemy_combat_ids.append(combat_id)

        if self.debug_enabled:
            logger.debug(f"[REGISTRY] Registered {minion['name']} (combat_id: {combat_id}) to {band_type} band at position {position}")

        return combat_id

    def get_minion_by_combat_id(self, combat_id: str) -> Optional[Dict]:
        """Get a minion by its combat ID"""
        return self.combat_minions.get(combat_id)

    def get_minion_band_type(self, minion: Dict) -> Optional[str]:
        """
        Determine which band a minion belongs to
        This MUST work even for dead minions

        Args:
            minion: The minion dictionary (must have _combat_id)

        Returns:
            'player' or 'enemy', or None if not found
        """
        combat_id = minion.get('_combat_id')
        if not combat_id:
            if self.debug_enabled:
                logger.error(f"[REGISTRY ERROR] Minion {minion.get('name', 'unknown')} has no _combat_id!")
            return None

        band_type = self.band_membership.get(combat_id)

        if self.debug_enabled and not band_type:
            logger.error(f"[REGISTRY ERROR] Combat ID {combat_id} not found in band_membership!")
            logger.debug(f"[REGISTRY] Current band_membership keys: {list(self.band_membership.keys())}")

        return band_type

    def get_band_minions(self, band_type: str, alive_only: bool = False) -> List[Dict]:
        """
        Get all minions in a specific band

        Args:
            band_type: 'player' or 'enemy'
            alive_only: If True, only return minions with health > 0

        Returns:
            List of minion dictionaries
        """
        if band_type == 'player':
            combat_ids = self.player_combat_ids
        elif band_type == 'enemy':
            combat_ids = self.enemy_combat_ids
        else:
            return []

        minions = []
        for combat_id in combat_ids:
            minion = self.combat_minions.get(combat_id)
            if minion:
                if not alive_only or minion.get('health', 0) > 0:
                    minions.append(minion)

        return minions

    def get_ally_band(self, minion: Dict, alive_only: bool = False) -> List[Dict]:
        """
        Get all allies of a minion (same band including self)

        Args:
            minion: The minion whose allies to find
            alive_only: If True, only return living allies

        Returns:
            List of ally minions
        """
        band_type = self.get_minion_band_type(minion)
        if not band_type:
            if self.debug_enabled:
                logger.warning(f"[REGISTRY WARNING] Could not determine band for {minion.get('name', 'unknown')}")
            return []
        return self.get_band_minions(band_type, alive_only)

    def get_enemy_band(self, minion: Dict, alive_only: bool = False) -> List[Dict]:
        """
        Get all enemies of a minion (opposite band)

        Args:
            minion: The minion whose enemies to find
            alive_only: If True, only return living enemies

        Returns:
            List of enemy minions
        """
        band_type = self.get_minion_band_type(minion)
        if not band_type:
            if self.debug_enabled:
                logger.warning(f"[REGISTRY WARNING] Could not determine band for {minion.get('name', 'unknown')}")
            return []

        enemy_type = 'enemy' if band_type == 'player' else 'player'
        return self.get_band_minions(enemy_type, alive_only)

    def get_minion_position(self, minion: Dict) -> Optional[int]:
        """Get the position of a minion in its band"""
        combat_id = minion.get('_combat_id')
        if not combat_id:
            return None
        return self.position_map.get(combat_id)

    def update_minion_position(self, minion: Dict, new_position: int):
        """Update the position of a minion in its band"""
        combat_id = minion.get('_combat_id')
        if combat_id:
            self.position_map[combat_id] = new_position

    def get_original_band_id(self, minion: Dict) -> Optional[str]:
        """Get the original band_id for a minion (if it's a player minion)"""
        combat_id = minion.get('_combat_id')
        if not combat_id:
            return None
        return self.band_ids_map.get(combat_id)

    def add_summoned_minion(self, minion: Dict, summoner: Dict, position: int) -> str:
        """
        Add a summoned minion to combat

        Args:
            minion: The summoned minion dictionary
            summoner: The minion that summoned it
            position: Position to insert in the band

        Returns:
            Combat ID of the summoned minion
        """
        # Determine which band to add to based on summoner
        band_type = self.get_minion_band_type(summoner)

        if self.debug_enabled:
            logger.debug(f"[REGISTRY] Adding summoned {minion['name']} from {summoner['name']} (combat_id: {summoner.get('_combat_id')}) to {band_type} band")

        if not band_type:
            raise ValueError(f"Summoner {summoner.get('name', 'unknown')} not found in combat registry")

        # Generate unique combat ID
        combat_id = str(uuid.uuid4())

        # Store the minion reference
        self.combat_minions[combat_id] = minion

        # Store band membership - PERMANENT
        self.band_membership[combat_id] = band_type

        # Store position
        self.position_map[combat_id] = position

        # Store original band_id if it exists (for player minions)
        if 'band_id' in minion:
            self.band_ids_map[combat_id] = minion['band_id']

        # Add combat_id to the minion for easy reference
        minion['_combat_id'] = combat_id

        # Insert combat_id at the correct position in the band list (not at the end!)
        if band_type == 'player':
            # Insert at the correct position, not append
            self.player_combat_ids.insert(position, combat_id)
            # Update positions for all minions after the insertion point
            for i in range(position + 1, len(self.player_combat_ids)):
                cid = self.player_combat_ids[i]
                self.position_map[cid] = i
                shifted_minion = self.combat_minions.get(cid)
                if shifted_minion:
                    shifted_minion['position'] = i
        else:
            # Insert at the correct position, not append
            self.enemy_combat_ids.insert(position, combat_id)
            # Update positions for all minions after the insertion point
            for i in range(position + 1, len(self.enemy_combat_ids)):
                cid = self.enemy_combat_ids[i]
                self.position_map[cid] = i
                shifted_minion = self.combat_minions.get(cid)
                if shifted_minion:
                    shifted_minion['position'] = i

        if self.debug_enabled:
            logger.debug(f"[REGISTRY] Successfully added summoned {minion['name']} (combat_id: {combat_id}) to {band_type} band at position {position}")

        return combat_id

    def remove_dead_minions(self):
        """
        Remove dead minions from tracking (optional cleanup)
        NOTE: We typically DON'T call this to preserve band membership for death toll effects
        """
        pass

    def get_bands_for_context(self, acting_minion: Dict) -> Dict[str, List[Dict]]:
        """
        Get ally and enemy bands relative to an acting minion

        Args:
            acting_minion: The minion performing an action

        Returns:
            Dictionary with 'ally_band' and 'enemy_band' keys
        """
        return {
            'ally_band': self.get_ally_band(acting_minion, alive_only=False),
            'enemy_band': self.get_enemy_band(acting_minion, alive_only=False)
        }

    def debug_state(self) -> str:
        """Get a debug string representation of the registry state"""
        lines = ["=== Combat Registry State ==="]

        lines.append(f"Band Membership: {len(self.band_membership)} entries")
        for combat_id, band_type in self.band_membership.items():
            minion = self.combat_minions.get(combat_id)
            if minion:
                lines.append(f"  - {combat_id[:8]}... -> {band_type}: {minion['name']} (HP: {minion.get('health', 0)})")

        lines.append(f"\nPlayer minions ({len(self.player_combat_ids)}):")
        for combat_id in self.player_combat_ids:
            minion = self.combat_minions.get(combat_id)
            if minion:
                lines.append(f"  - {minion['name']} (HP:{minion.get('health', 0)}) @ pos {self.position_map.get(combat_id)}")

        lines.append(f"\nEnemy minions ({len(self.enemy_combat_ids)}):")
        for combat_id in self.enemy_combat_ids:
            minion = self.combat_minions.get(combat_id)
            if minion:
                lines.append(f"  - {minion['name']} (HP:{minion.get('health', 0)}) @ pos {self.position_map.get(combat_id)}")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the registry to a JSON-serializable dictionary

        Returns:
            dict: JSON-serializable representation of the registry
        """
        return {
            'band_membership': self.band_membership,
            'position_map': self.position_map,
            'band_ids_map': self.band_ids_map,
            'player_combat_ids': self.player_combat_ids,
            'enemy_combat_ids': self.enemy_combat_ids
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], player_band: List[Dict], enemy_band: List[Dict]) -> 'CombatRegistry':
        """
        Reconstruct a registry from a dictionary and the current bands

        Args:
            data: Dictionary representation of the registry
            player_band: Current player band (with _combat_id fields)
            enemy_band: Current enemy band (with _combat_id fields)

        Returns:
            CombatRegistry: Reconstructed registry instance
        """
        registry = cls()

        # Restore the registry fields
        registry.band_membership = data.get('band_membership', {})
        registry.position_map = data.get('position_map', {})
        registry.band_ids_map = data.get('band_ids_map', {})
        registry.player_combat_ids = data.get('player_combat_ids', [])
        registry.enemy_combat_ids = data.get('enemy_combat_ids', [])

        # Rebuild combat_minions map from the bands
        for minion in player_band:
            combat_id = minion.get('_combat_id')
            if combat_id:
                registry.combat_minions[combat_id] = minion
                # Ensure band membership is preserved
                if combat_id not in registry.band_membership:
                    registry.band_membership[combat_id] = 'player'
                    if registry.debug_enabled:
                        logger.debug(f"[REGISTRY RECOVERY] Added missing band membership for player minion {minion['name']}")

        for minion in enemy_band:
            combat_id = minion.get('_combat_id')
            if combat_id:
                registry.combat_minions[combat_id] = minion
                # Ensure band membership is preserved
                if combat_id not in registry.band_membership:
                    registry.band_membership[combat_id] = 'enemy'
                    if registry.debug_enabled:
                        logger.debug(f"[REGISTRY RECOVERY] Added missing band membership for enemy minion {minion['name']}")

        if registry.debug_enabled:
            logger.debug(f"[REGISTRY] Reconstructed from dict with {len(registry.combat_minions)} minions")

        return registry