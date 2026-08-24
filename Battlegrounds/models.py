import logging

logger = logging.getLogger(__name__)

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json
from keywords import validate_keywords
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class Player(db.Model):
    __tablename__ = 'players'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    # Stats for ranked mode
    ranked_wins = db.Column(db.Integer, default=0)
    ranked_losses = db.Column(db.Integer, default=0)
    highest_ring = db.Column(db.Integer, default=0)

    # MMR and rank for matchmaking
    mmr = db.Column(db.Integer, default=1000)
    rank = db.Column(db.String(20), default='bronze')

    # Image customization (stores only non-defaults for efficiency)
    # owned_images: JSON dict of minion_id -> list of owned alt variants (original is always owned, not stored)
    # equipped_images: JSON dict of minion_id -> equipped variant (only stored if not 'original')
    owned_images = db.Column(db.Text, default='{}')
    equipped_images = db.Column(db.Text, default='{}')

    # Account classification — separates external testers from real players
    # so tester data (runs, ghost pool, MMR) never mixes with production players.
    is_tester = db.Column(db.Boolean, default=False, nullable=False)

    def set_password(self, password):
        """Hash and store password"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify password against hash"""
        return check_password_hash(self.password_hash, password)

    def get_owned_images(self):
        """Return owned image variants as dict of minion_id -> set of variant names.
        Note: 'original' is always owned by everyone, so it's not stored."""
        if self.owned_images:
            try:
                data = json.loads(self.owned_images)
                # Convert lists to sets for efficient lookup
                return {k: set(v) for k, v in data.items()}
            except:
                return {}
        return {}

    def set_owned_images(self, owned_dict):
        """Store owned image variants. Only store non-original variants."""
        # Filter out empty lists and 'original' variant
        filtered = {}
        for minion_id, variants in owned_dict.items():
            # Remove 'original' if present (it's always owned)
            clean_variants = [v for v in variants if v != 'original']
            if clean_variants:
                filtered[minion_id] = clean_variants
        self.owned_images = json.dumps(filtered)

    def add_owned_image(self, minion_id, variant):
        """Add a specific image variant to owned collection."""
        if variant == 'original':
            return  # Original is always owned, don't store
        owned = self.get_owned_images()
        if minion_id not in owned:
            owned[minion_id] = set()
        owned[minion_id].add(variant)
        self.set_owned_images({k: list(v) for k, v in owned.items()})

    def get_equipped_images(self):
        """Return equipped image variants as dict of minion_id -> variant name.
        Note: Only stores non-original equipped variants."""
        if self.equipped_images:
            try:
                return json.loads(self.equipped_images)
            except:
                return {}
        return {}

    def set_equipped_images(self, equipped_dict):
        """Store equipped image variants. Only store non-original selections."""
        # Filter out 'original' selections (that's the default)
        filtered = {k: v for k, v in equipped_dict.items() if v != 'original'}
        self.equipped_images = json.dumps(filtered)

    def set_equipped_image(self, minion_id, variant):
        """Set the equipped image variant for a specific minion."""
        equipped = self.get_equipped_images()
        if variant == 'original':
            # Remove from dict (default to original)
            equipped.pop(minion_id, None)
        else:
            equipped[minion_id] = variant
        self.set_equipped_images(equipped)

    def get_minion_image_path(self, minion_id, default_image):
        """Get the equipped image path for a minion, or default if not customized."""
        equipped = self.get_equipped_images()
        variant = equipped.get(minion_id, 'original')
        # Return path based on variant
        return f'images/{variant}/{default_image}'

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'ranked_wins': self.ranked_wins,
            'ranked_losses': self.ranked_losses,
            'highest_ring': self.highest_ring,
            'mmr': self.mmr,
            'rank': self.rank,
            'is_tester': bool(self.is_tester),
        }


class InviteCode(db.Model):
    """Single-use invite code for account signup.

    Admins mint codes via `python make_invite.py [--count N] [--player]`.
    The code is consumed atomically on successful signup and cannot be reused.
    `is_tester` on the code propagates to the created Player.
    """
    __tablename__ = 'invite_codes'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), unique=True, nullable=False, index=True)
    is_tester = db.Column(db.Boolean, default=True, nullable=False)
    note = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    used_by_player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=True)

    def is_used(self):
        return self.used_at is not None

    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'is_tester': bool(self.is_tester),
            'note': self.note,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'used_at': self.used_at.isoformat() if self.used_at else None,
            'used_by_player_id': self.used_by_player_id,
        }


class Run(db.Model):
    __tablename__ = 'runs'

    id = db.Column(db.Integer, primary_key=True)
    run_token = db.Column(db.String(36), unique=True, nullable=True)  # UUID token for ownership verification
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=True)  # Link to player account
    is_ranked = db.Column(db.Boolean, default=False)  # True for ranked, False for unranked
    selection_version = db.Column(db.Integer, default=0)  # Optimistic lock for concurrent selection requests
    current_ring = db.Column(db.Integer, default=1)
    ring_position = db.Column(db.Integer, default=0)
    current_zone = db.Column(db.String(50), default='starting_plains')  # Current zone
    unlocked_zones = db.Column(db.Text, default='["starting_plains"]')  # JSON list of unlocked zones
    
    # Sub-ring fields
    current_ring_type = db.Column(db.String(20), default='main')  # 'main' or 'sub'
    current_sub_ring = db.Column(db.String(50), nullable=True)  # Sub-ring template name
    sub_ring_position = db.Column(db.Integer, default=0)  # Current position in sub-ring
    main_ring_return_position = db.Column(db.Integer, nullable=True)  # Where to return on main ring
    sub_ring_data = db.Column(db.Text, nullable=True)  # JSON data for current sub-ring
    
    events_count = db.Column(db.Integer, default=0)
    ring_upgrade_steps = db.Column(db.Integer, default=0)  # Steps since last ring upgrade (for cost calculation)
    is_active = db.Column(db.Boolean, default=True)
    health = db.Column(db.Integer, default=30)  # Player health
    band_data = db.Column(db.Text)  # JSON string of band
    resources = db.Column(db.Text)  # JSON string of resources (gold, etc.)
    pending_selection = db.Column(db.Text)  # JSON string of current selection options
    event_state = db.Column(db.Text)  # JSON string of event-specific state (e.g., bells_rung)
    upcoming_ghost_id = db.Column(db.Integer, db.ForeignKey('ghost_snapshots.id'), nullable=True)  # Pre-generated ghost for next battle
    hero_id = db.Column(db.String(50), nullable=True)  # Selected hero ID (e.g., 'silas', 'puck', 'olimpia')
    hero_effects = db.Column(db.Text, default='{}')  # JSON string of hero effects/modifiers
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_band(self):
        """Return band as Python object with keyword validation"""
        if self.band_data:
            band = json.loads(self.band_data)
            # Ensure all minions have keywords field and validate them
            for minion in band:
                if 'keywords' not in minion:
                    minion['keywords'] = []
                elif not validate_keywords(minion['keywords']):
                    logger.warning(f"Warning: Invalid keywords in {minion.get('name', 'Unknown')}: {minion['keywords']}")
                    minion['keywords'] = [kw for kw in minion['keywords'] if validate_keywords([kw])]
            return band
        return []

    def set_band(self, band):
        """Store band as JSON string with keyword validation"""
        # Validate and clean keywords before storing
        for minion in band:
            if 'keywords' not in minion:
                minion['keywords'] = []
            elif not validate_keywords(minion['keywords']):
                logger.warning(f"Warning: Cleaning invalid keywords for {minion.get('name', 'Unknown')}")
                minion['keywords'] = [kw for kw in minion['keywords'] if validate_keywords([kw])]

        self.band_data = json.dumps(band)

    def get_resources(self):
        """Return resources as Python object"""
        if self.resources:
            return json.loads(self.resources)
        return {'gold': 3, 'rerolls': 1}

    def set_resources(self, resources):
        """Store resources as JSON string"""
        self.resources = json.dumps(resources)

    def get_pending_selection(self):
        """Return pending selection as Python object"""
        if self.pending_selection:
            loaded = json.loads(self.pending_selection)

            # DEBUG: Log combat state after loading
            if loaded.get('event_type') == 'combat' and 'combat_state' in loaded:
                cs = loaded['combat_state']
                pb = cs.get('player_band', [])
                eb = cs.get('enemy_band', [])
                combat_over = cs.get('combat_over', False)
                logger.debug(f"[DEBUG] Loading combat_state: player_band={len(pb)} minions, enemy_band={len(eb)} minions, combat_over={combat_over}")
                # Empty bands are normal when combat is over (one side lost)
                if not combat_over and (len(pb) == 0 or len(eb) == 0):
                    logger.error(f"[ERROR] DATA LOSS DETECTED IN get_pending_selection! (combat not over but band empty)")
                    logger.error(f"[ERROR] combat_state keys: {list(cs.keys())}")

            return loaded
        return None

    def set_pending_selection(self, selection):
        """Store pending selection as JSON string"""
        if selection is None:
            self.pending_selection = None
        else:
            # Validate keywords in selection options if they contain minion data
            if 'options' in selection:
                for option in selection['options']:
                    if 'data' in option and isinstance(option['data'], dict) and 'keywords' in option['data']:
                        keywords = option['data']['keywords']
                        if not validate_keywords(keywords):
                            logger.warning(f"Warning: Invalid keywords in selection option: {keywords}")
                            option['data']['keywords'] = [kw for kw in keywords if validate_keywords([kw])]

            # DEBUG: Log combat state before serialization
            if selection.get('event_type') == 'combat' and 'combat_state' in selection:
                cs = selection['combat_state']
                pb = cs.get('player_band', [])
                eb = cs.get('enemy_band', [])
                combat_over = cs.get('combat_over', False)
                logger.debug(f"[DEBUG] Saving combat_state: player_band={len(pb)} minions, enemy_band={len(eb)} minions, combat_over={combat_over}")

            self.pending_selection = json.dumps(selection)

            # DEBUG: Verify it can be loaded back
            try:
                test_load = json.loads(self.pending_selection)
                if selection.get('event_type') == 'combat' and 'combat_state' in test_load:
                    cs = test_load['combat_state']
                    pb = cs.get('player_band', [])
                    eb = cs.get('enemy_band', [])
                    combat_over = cs.get('combat_over', False)
                    logger.debug(f"[DEBUG] After roundtrip: player_band={len(pb)} minions, enemy_band={len(eb)} minions, combat_over={combat_over}")
                    # Empty bands are normal when combat is over
                    if not combat_over and (len(pb) == 0 or len(eb) == 0):
                        logger.error(f"[ERROR] DATA LOSS DETECTED IN set_pending_selection! (combat not over but band empty)")
            except Exception as e:
                logger.error(f"[ERROR] Failed to verify pending_selection roundtrip: {e}")

    def has_pending_selection(self):
        """Check if there's a pending selection"""
        return self.pending_selection is not None

    def get_unlocked_zones(self):
        """Return unlocked zones as Python list"""
        if self.unlocked_zones:
            try:
                return json.loads(self.unlocked_zones)
            except:
                return ['starting_plains']  # Fallback to default
        return ['starting_plains']

    def set_unlocked_zones(self, zones):
        """Store unlocked zones as JSON string"""
        self.unlocked_zones = json.dumps(zones)

    def get_event_state(self):
        """Return event state as Python object"""
        if self.event_state:
            return json.loads(self.event_state)
        return {}

    def set_event_state(self, state):
        """Store event state as JSON string"""
        self.event_state = json.dumps(state)

    def get_sub_ring_data(self):
        """Return sub-ring data as Python object"""
        if self.sub_ring_data:
            try:
                return json.loads(self.sub_ring_data)
            except:
                return None
        return None

    def set_sub_ring_data(self, data):
        """Store sub-ring data as JSON string"""
        if data is None:
            self.sub_ring_data = None
        else:
            self.sub_ring_data = json.dumps(data)

    def get_hero_effects(self):
        """Return hero effects as Python object"""
        if self.hero_effects:
            try:
                return json.loads(self.hero_effects)
            except:
                return {}
        return {}

    def set_hero_effects(self, effects):
        """Store hero effects as JSON string"""
        self.hero_effects = json.dumps(effects)

    def _apply_image_path_to_minion(self, minion, equipped):
        """Apply image_path to a single minion dict based on equipped images."""
        if minion.get('image'):
            minion_id = minion['image'].replace('.png', '')
            if minion_id in equipped:
                variant = equipped[minion_id]
                minion['image_path'] = f"images/{variant}/{minion['image']}"
            else:
                minion['image_path'] = f"images/original/{minion['image']}"
        else:
            minion['image_path'] = None

    def _get_equipped_images_dict(self):
        """Get the equipped images dict for this run's player."""
        if not self.player_id:
            return {}
        player = Player.query.get(self.player_id)
        if not player:
            return {}
        return player.get_equipped_images()

    def get_pending_selection_with_images(self):
        """Get pending selection with image_path applied to all minions in options."""
        pending = self.get_pending_selection()
        if not pending:
            return None

        equipped = self._get_equipped_images_dict()

        # Process options to add image_path to any minion data
        if 'options' in pending:
            for option in pending['options']:
                # Check for minion data in 'data' field
                if 'data' in option and isinstance(option['data'], dict):
                    data = option['data']
                    # If data looks like a minion (has 'image' key), apply image_path
                    if 'image' in data:
                        self._apply_image_path_to_minion(data, equipped)

        # Process combat_state bands if present
        if 'combat_state' in pending:
            combat_state = pending['combat_state']
            for band_key in ['player_band', 'enemy_band']:
                if band_key in combat_state:
                    for minion in combat_state[band_key]:
                        self._apply_image_path_to_minion(minion, equipped)

        return pending

    def to_dict(self):
        from database import check_ghost_battle_available

        # Get the upcoming ghost's milestone if available
        upcoming_ghost_milestone = None
        if self.upcoming_ghost_id:
            upcoming_ghost = GhostSnapshot.query.get(self.upcoming_ghost_id)
            if upcoming_ghost:
                upcoming_ghost_milestone = upcoming_ghost.events_milestone

        # Get band with player's equipped image paths applied
        band = self.get_band_with_equipped_images()

        # Get pending selection with image paths applied to minions
        pending_selection = self.get_pending_selection_with_images()

        # Count ghost wins for this run
        ghost_wins = GhostBattle.query.filter_by(run_id=self.id, winner='player').count()

        return {
            'id': self.id,
            'run_token': self.run_token,
            'player_id': self.player_id,
            'is_ranked': self.is_ranked,
            'current_ring': self.current_ring,
            'ring_position': self.ring_position,
            'current_zone': self.current_zone,
            'unlocked_zones': self.get_unlocked_zones(),
            'current_ring_type': self.current_ring_type,
            'current_sub_ring': self.current_sub_ring,
            'sub_ring_position': self.sub_ring_position,
            'main_ring_return_position': self.main_ring_return_position,
            'events_count': self.events_count,
            'ring_upgrade_steps': self.ring_upgrade_steps if self.ring_upgrade_steps is not None else 0,
            'is_active': self.is_active,
            'health': self.health if self.health is not None else 30,
            'band': band,
            'resources': self.get_resources(),
            'pending_selection': pending_selection,
            'hero_id': self.hero_id,
            'hero_effects': self.get_hero_effects(),
            'ghost_battle_available': check_ghost_battle_available(self),
            'upcoming_ghost_id': self.upcoming_ghost_id,
            'upcoming_ghost_milestone': upcoming_ghost_milestone,  # Send actual ghost milestone
            'ghost_wins': ghost_wins,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

    def get_band_with_equipped_images(self):
        """Get band with player's equipped image paths applied to each minion.
        ALWAYS sets image_path for every minion - never returns minions without image_path."""
        band = self.get_band()
        equipped = self._get_equipped_images_dict()

        # ALWAYS apply image paths to all band minions
        for minion in band:
            self._apply_image_path_to_minion(minion, equipped)

        return band


class GhostSnapshot(db.Model):
    __tablename__ = 'ghost_snapshots'

    id = db.Column(db.Integer, primary_key=True)
    events_milestone = db.Column(db.Integer)  # 10, 20, 30, etc.
    band_snapshot = db.Column(db.Text)  # JSON string of band state
    power_level = db.Column(db.Integer)  # Calculated band strength
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Player identity
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=True)
    player_name = db.Column(db.String(50), nullable=True)  # Denormalized for fast display

    # Hero snapshot (frozen at capture time)
    hero_id = db.Column(db.String(50), nullable=True)
    hero_effects = db.Column(db.Text, nullable=True)  # JSON: full hero_effects including power_upgraded

    # Image snapshot (frozen at capture time so ghost keeps the player's cosmetics)
    equipped_images = db.Column(db.Text, nullable=True)  # JSON: player's equipped image dict

    # Run state at capture
    current_ring = db.Column(db.Integer, nullable=True)
    health = db.Column(db.Integer, nullable=True)

    # Win/loss path tracking - how many ghost wins/losses the player had at this point
    ghost_wins_at_capture = db.Column(db.Integer, default=0)
    ghost_losses_at_capture = db.Column(db.Integer, default=0)

    # Ranked matchmaking
    mmr = db.Column(db.Integer, nullable=True)  # Player's MMR at capture
    is_ranked = db.Column(db.Boolean, default=False)

    # Source tag: 'player' (real human), 'headless' (AI-driven headless run), 'ai' (generated fallback)
    source = db.Column(db.String(20), default='player')

    # Run ID for grouping snapshots from the same game (for journey analysis)
    run_id = db.Column(db.Integer, db.ForeignKey('runs.id'), nullable=True)

    # Detailed action log from headless runs (JSON list of actions taken during the run)
    actions_log = db.Column(db.Text, nullable=True)

    def get_actions_log(self):
        """Return actions log as Python list"""
        if self.actions_log:
            try:
                return json.loads(self.actions_log)
            except:
                return []
        return []

    def set_actions_log(self, actions):
        """Store actions log as JSON"""
        self.actions_log = json.dumps(actions) if actions else None

    def get_band(self):
        """Return band snapshot as Python object with keyword validation"""
        if self.band_snapshot:
            band = json.loads(self.band_snapshot)
            for minion in band:
                if 'keywords' not in minion:
                    minion['keywords'] = []
                elif not validate_keywords(minion['keywords']):
                    logger.warning(f"Warning: Invalid keywords in ghost {minion.get('name', 'Unknown')}: {minion['keywords']}")
                    minion['keywords'] = [kw for kw in minion['keywords'] if validate_keywords([kw])]
            return band
        return []

    def get_band_with_images(self):
        """Return band with image_path applied from the ghost's equipped_images snapshot."""
        band = self.get_band()
        equipped = self.get_equipped_images()
        for minion in band:
            if minion.get('image'):
                minion_id = minion['image'].replace('.png', '')
                if minion_id in equipped:
                    variant = equipped[minion_id]
                    minion['image_path'] = f"images/{variant}/{minion['image']}"
                else:
                    minion['image_path'] = f"images/original/{minion['image']}"
            else:
                minion['image_path'] = None
        return band

    def set_band(self, band):
        """Store band snapshot as JSON string with keyword validation"""
        for minion in band:
            if 'keywords' not in minion:
                minion['keywords'] = []
            elif not validate_keywords(minion['keywords']):
                logger.warning(f"Warning: Cleaning invalid keywords for ghost {minion.get('name', 'Unknown')}")
                minion['keywords'] = [kw for kw in minion['keywords'] if validate_keywords([kw])]
        self.band_snapshot = json.dumps(band)

    def get_hero_effects(self):
        """Return hero effects snapshot as Python object"""
        if self.hero_effects:
            try:
                return json.loads(self.hero_effects)
            except:
                return {}
        return {}

    def set_hero_effects(self, effects):
        """Store hero effects as JSON"""
        self.hero_effects = json.dumps(effects) if effects else None

    def get_equipped_images(self):
        """Return equipped images snapshot as Python dict"""
        if self.equipped_images:
            try:
                return json.loads(self.equipped_images)
            except:
                return {}
        return {}

    def set_equipped_images(self, images):
        """Store equipped images as JSON"""
        self.equipped_images = json.dumps(images) if images else None

    def to_dict(self):
        return {
            'id': self.id,
            'events_milestone': self.events_milestone,
            'band': self.get_band(),
            'power_level': self.power_level,
            'player_id': self.player_id,
            'player_name': self.player_name,
            'hero_id': self.hero_id,
            'current_ring': self.current_ring,
            'health': self.health,
            'ghost_wins_at_capture': self.ghost_wins_at_capture,
            'ghost_losses_at_capture': self.ghost_losses_at_capture,
            'mmr': self.mmr,
            'is_ranked': self.is_ranked,
            'source': self.source or 'player',
            'has_actions_log': bool(self.actions_log),
            'created_at': self.created_at.isoformat()
        }


class GhostBattle(db.Model):
    __tablename__ = 'ghost_battles'

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey('runs.id'))
    ghost_id = db.Column(db.Integer, db.ForeignKey('ghost_snapshots.id'))
    events_milestone = db.Column(db.Integer)
    winner = db.Column(db.String(10))  # 'player' or 'ghost'
    ghost_player_name = db.Column(db.String(50), nullable=True)  # Denormalized for display
    battle_log = db.Column(db.Text)  # JSON string of combat log
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def get_battle_log(self):
        """Return battle log as Python object"""
        if self.battle_log:
            return json.loads(self.battle_log)
        return []

    def set_battle_log(self, log):
        """Store battle log as JSON string"""
        self.battle_log = json.dumps(log)

    def to_dict(self):
        return {
            'id': self.id,
            'run_id': self.run_id,
            'ghost_id': self.ghost_id,
            'events_milestone': self.events_milestone,
            'winner': self.winner,
            'ghost_player_name': self.ghost_player_name,
            'battle_log': self.get_battle_log(),
            'created_at': self.created_at.isoformat()
        }