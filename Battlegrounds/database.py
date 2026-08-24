import logging

logger = logging.getLogger(__name__)

from models import db, Run, GhostSnapshot, GhostBattle, Player, InviteCode
from config import STARTING_BAND, EVENTS_FOR_GHOST_BATTLE, RING_START_POSITION, DEFAULT_STARTING_ZONE
from game_logic import GameLogic
from keywords import validate_keywords
import random
import json


def _add_missing_columns():
    """Add missing columns to existing database tables"""
    from sqlalchemy import text
    
    try:
        # Check if current_zone column exists, if not add it
        db.session.execute(text("SELECT current_zone FROM runs LIMIT 1"))
        logger.debug("current_zone column already exists")
    except Exception:
        # Column doesn't exist, add it
        logger.debug("Adding current_zone column to runs table...")
        db.session.execute(text(f"ALTER TABLE runs ADD COLUMN current_zone VARCHAR(50) DEFAULT '{DEFAULT_STARTING_ZONE}'"))
        # Update any existing rows that might have NULL values
        db.session.execute(text(f"UPDATE runs SET current_zone = '{DEFAULT_STARTING_ZONE}' WHERE current_zone IS NULL"))
        
    try:
        # Check if unlocked_zones column exists, if not add it
        db.session.execute(text("SELECT unlocked_zones FROM runs LIMIT 1"))
        logger.debug("unlocked_zones column already exists")
    except Exception:
        # Column doesn't exist, add it
        logger.debug("Adding unlocked_zones column to runs table...")
        db.session.execute(text(f'ALTER TABLE runs ADD COLUMN unlocked_zones TEXT DEFAULT \'["{DEFAULT_STARTING_ZONE}"]\''))
        # Update any existing rows that might have NULL values
        db.session.execute(text(f'UPDATE runs SET unlocked_zones = \'["{DEFAULT_STARTING_ZONE}"]\' WHERE unlocked_zones IS NULL'))

    # Add player_id column for run persistence
    try:
        db.session.execute(text("SELECT player_id FROM runs LIMIT 1"))
        logger.debug("player_id column already exists")
    except Exception:
        logger.debug("Adding player_id column to runs table...")
        db.session.execute(text("ALTER TABLE runs ADD COLUMN player_id INTEGER"))
        db.session.execute(text("UPDATE runs SET player_id = NULL WHERE player_id IS NULL"))

    # Add is_ranked column
    try:
        db.session.execute(text("SELECT is_ranked FROM runs LIMIT 1"))
        logger.debug("is_ranked column already exists")
    except Exception:
        logger.debug("Adding is_ranked column to runs table...")
        db.session.execute(text("ALTER TABLE runs ADD COLUMN is_ranked BOOLEAN DEFAULT 0"))
        db.session.execute(text("UPDATE runs SET is_ranked = 0 WHERE is_ranked IS NULL"))

    # Add sub-ring columns
    sub_ring_columns = [
        ('current_ring_type', 'VARCHAR(20)', "'main'"),
        ('current_sub_ring', 'VARCHAR(50)', 'NULL'),
        ('sub_ring_position', 'INTEGER', '0'),
        ('main_ring_return_position', 'INTEGER', 'NULL'),
        ('sub_ring_data', 'TEXT', 'NULL')
    ]
    
    for column_name, column_type, default_value in sub_ring_columns:
        try:
            # Check if column exists
            db.session.execute(text(f"SELECT {column_name} FROM runs LIMIT 1"))
            logger.debug(f"{column_name} column already exists")
        except Exception:
            # Column doesn't exist, add it
            logger.debug(f"Adding {column_name} column to runs table...")
            if default_value == 'NULL':
                db.session.execute(text(f"ALTER TABLE runs ADD COLUMN {column_name} {column_type}"))
            else:
                db.session.execute(text(f"ALTER TABLE runs ADD COLUMN {column_name} {column_type} DEFAULT {default_value}"))
            
            # Update existing rows with appropriate defaults
            if column_name == 'current_ring_type':
                db.session.execute(text(f"UPDATE runs SET {column_name} = 'main' WHERE {column_name} IS NULL"))
            elif column_name == 'sub_ring_position':
                db.session.execute(text(f"UPDATE runs SET {column_name} = 0 WHERE {column_name} IS NULL"))

    # Add health column for player health system
    try:
        db.session.execute(text("SELECT health FROM runs LIMIT 1"))
        logger.debug("health column already exists")
    except Exception:
        logger.debug("Adding health column to runs table...")
        db.session.execute(text("ALTER TABLE runs ADD COLUMN health INTEGER DEFAULT 30"))
        db.session.execute(text("UPDATE runs SET health = 30 WHERE health IS NULL"))

    # Add upcoming_ghost_id column for pre-generated ghost battles
    try:
        db.session.execute(text("SELECT upcoming_ghost_id FROM runs LIMIT 1"))
        logger.debug("upcoming_ghost_id column already exists")
    except Exception:
        logger.debug("Adding upcoming_ghost_id column to runs table...")
        db.session.execute(text("ALTER TABLE runs ADD COLUMN upcoming_ghost_id INTEGER"))
        # Column is nullable, so no need to update existing rows

    # Add ring_upgrade_steps column for tracking upgrade cost
    try:
        db.session.execute(text("SELECT ring_upgrade_steps FROM runs LIMIT 1"))
        logger.debug("ring_upgrade_steps column already exists")
    except Exception:
        logger.debug("Adding ring_upgrade_steps column to runs table...")
        db.session.execute(text("ALTER TABLE runs ADD COLUMN ring_upgrade_steps INTEGER DEFAULT 0"))
        db.session.execute(text("UPDATE runs SET ring_upgrade_steps = 0 WHERE ring_upgrade_steps IS NULL"))

    # Add event_state column for event-specific state tracking (e.g., bells_rung)
    try:
        db.session.execute(text("SELECT event_state FROM runs LIMIT 1"))
        logger.debug("event_state column already exists")
    except Exception:
        logger.debug("Adding event_state column to runs table...")
        db.session.execute(text("ALTER TABLE runs ADD COLUMN event_state TEXT"))
        # Column is nullable, so no need to update existing rows

    # Add hero_id column for hero selection
    try:
        db.session.execute(text("SELECT hero_id FROM runs LIMIT 1"))
        logger.debug("hero_id column already exists")
    except Exception:
        logger.debug("Adding hero_id column to runs table...")
        db.session.execute(text("ALTER TABLE runs ADD COLUMN hero_id VARCHAR(50)"))
        # Column is nullable, so no need to update existing rows

    # Add image customization columns to players table
    try:
        db.session.execute(text("SELECT owned_images FROM players LIMIT 1"))
        logger.debug("owned_images column already exists")
    except Exception:
        logger.debug("Adding owned_images column to players table...")
        db.session.execute(text("ALTER TABLE players ADD COLUMN owned_images TEXT DEFAULT '{}'"))
        db.session.execute(text("UPDATE players SET owned_images = '{}' WHERE owned_images IS NULL"))

    try:
        db.session.execute(text("SELECT equipped_images FROM players LIMIT 1"))
        logger.debug("equipped_images column already exists")
    except Exception:
        logger.debug("Adding equipped_images column to players table...")
        db.session.execute(text("ALTER TABLE players ADD COLUMN equipped_images TEXT DEFAULT '{}'"))
        db.session.execute(text("UPDATE players SET equipped_images = '{}' WHERE equipped_images IS NULL"))

    # --- Player MMR/rank columns ---
    for col_name, col_type, col_default in [
        ('mmr', 'INTEGER', '1000'),
        ('rank', 'VARCHAR(20)', "'bronze'"),
    ]:
        try:
            db.session.execute(text(f"SELECT {col_name} FROM players LIMIT 1"))
            logger.debug(f"{col_name} column already exists in players")
        except Exception:
            logger.debug(f"Adding {col_name} column to players table...")
            db.session.execute(text(f"ALTER TABLE players ADD COLUMN {col_name} {col_type} DEFAULT {col_default}"))
            db.session.execute(text(f"UPDATE players SET {col_name} = {col_default} WHERE {col_name} IS NULL"))

    # --- Player is_tester column (for beta separation) ---
    try:
        db.session.execute(text("SELECT is_tester FROM players LIMIT 1"))
        logger.debug("is_tester column already exists in players")
    except Exception:
        logger.debug("Adding is_tester column to players table...")
        db.session.execute(text("ALTER TABLE players ADD COLUMN is_tester BOOLEAN DEFAULT 0 NOT NULL"))
        db.session.execute(text("UPDATE players SET is_tester = 0 WHERE is_tester IS NULL"))

    # --- GhostSnapshot new columns ---
    ghost_columns = [
        ('player_id', 'INTEGER', None),
        ('player_name', 'VARCHAR(50)', None),
        ('hero_id', 'VARCHAR(50)', None),
        ('hero_effects', 'TEXT', None),
        ('equipped_images', 'TEXT', None),
        ('current_ring', 'INTEGER', None),
        ('health', 'INTEGER', None),
        ('ghost_wins_at_capture', 'INTEGER', '0'),
        ('ghost_losses_at_capture', 'INTEGER', '0'),
        ('mmr', 'INTEGER', None),
        ('is_ranked', 'BOOLEAN', '0'),
    ]
    for col_name, col_type, col_default in ghost_columns:
        try:
            db.session.execute(text(f"SELECT {col_name} FROM ghost_snapshots LIMIT 1"))
            logger.debug(f"{col_name} column already exists in ghost_snapshots")
        except Exception:
            logger.debug(f"Adding {col_name} column to ghost_snapshots table...")
            if col_default is not None:
                db.session.execute(text(f"ALTER TABLE ghost_snapshots ADD COLUMN {col_name} {col_type} DEFAULT {col_default}"))
            else:
                db.session.execute(text(f"ALTER TABLE ghost_snapshots ADD COLUMN {col_name} {col_type}"))

    # --- GhostBattle new columns ---
    try:
        db.session.execute(text("SELECT ghost_player_name FROM ghost_battles LIMIT 1"))
        logger.debug("ghost_player_name column already exists in ghost_battles")
    except Exception:
        logger.debug("Adding ghost_player_name column to ghost_battles table...")
        db.session.execute(text("ALTER TABLE ghost_battles ADD COLUMN ghost_player_name VARCHAR(50)"))

    # Ghost snapshot source tag
    try:
        db.session.execute(text("SELECT source FROM ghost_snapshots LIMIT 1"))
        logger.debug("source column already exists in ghost_snapshots")
    except Exception:
        logger.debug("Adding source column to ghost_snapshots table...")
        db.session.execute(text("ALTER TABLE ghost_snapshots ADD COLUMN source VARCHAR(20) DEFAULT 'player'"))

    # Ghost snapshot actions log
    try:
        db.session.execute(text("SELECT actions_log FROM ghost_snapshots LIMIT 1"))
        logger.debug("actions_log column already exists in ghost_snapshots")
    except Exception:
        logger.debug("Adding actions_log column to ghost_snapshots table...")
        db.session.execute(text("ALTER TABLE ghost_snapshots ADD COLUMN actions_log TEXT"))

    # Ghost snapshot run_id for journey grouping
    try:
        db.session.execute(text("SELECT run_id FROM ghost_snapshots LIMIT 1"))
        logger.debug("run_id column already exists in ghost_snapshots")
    except Exception:
        logger.debug("Adding run_id column to ghost_snapshots table...")
        db.session.execute(text("ALTER TABLE ghost_snapshots ADD COLUMN run_id INTEGER REFERENCES runs(id)"))

    # --- Security: run_token for ownership verification ---
    try:
        db.session.execute(text("SELECT run_token FROM runs LIMIT 1"))
        logger.debug("run_token column already exists")
    except Exception:
        import uuid
        logger.debug("Adding run_token column to runs table...")
        db.session.execute(text("ALTER TABLE runs ADD COLUMN run_token VARCHAR(36)"))
        # Backfill existing runs with unique tokens
        existing_runs = db.session.execute(text("SELECT id FROM runs")).fetchall()
        for (run_id,) in existing_runs:
            db.session.execute(
                text("UPDATE runs SET run_token = :token WHERE id = :id"),
                {'token': str(uuid.uuid4()), 'id': run_id}
            )

    # --- Security: selection_version for optimistic locking ---
    try:
        db.session.execute(text("SELECT selection_version FROM runs LIMIT 1"))
        logger.debug("selection_version column already exists")
    except Exception:
        logger.debug("Adding selection_version column to runs table...")
        db.session.execute(text("ALTER TABLE runs ADD COLUMN selection_version INTEGER DEFAULT 0"))
        db.session.execute(text("UPDATE runs SET selection_version = 0 WHERE selection_version IS NULL"))

    # Commit the schema changes
    db.session.commit()
    logger.debug("Database schema migration completed!")


def init_database(app):
    """Initialize database with app context"""
    with app.app_context():
        # Try to create all tables first
        try:
            db.create_all()
            logger.debug("Database tables created/verified!")
        except Exception as e:
            logger.error(f"Error creating tables: {e}")

        # Then migrate existing data
        try:
            migrate_existing_data()
        except Exception as e:
            logger.error(f"Error during migration: {e}")
            # If migration fails, we can still continue with basic functionality

        # Initialize default admin user
        try:
            initialize_admin_user()
        except Exception as e:
            logger.error(f"Error initializing admin user: {e}")


def migrate_existing_data():
    """Migrate existing minions to include keywords field, golden field, zone data, and sub-ring data"""
    try:
        # First, add missing columns to the database schema if they don't exist
        _add_missing_columns()
        
        runs = Run.query.all()
        for run in runs:
            # Migrate zone data - ensure all runs have proper zone values
            if not hasattr(run, 'current_zone') or not run.current_zone:
                run.current_zone = DEFAULT_STARTING_ZONE
                logger.debug(f"Set current_zone for run {run.id}")

            if not hasattr(run, 'unlocked_zones') or not run.unlocked_zones:
                run.unlocked_zones = json.dumps([DEFAULT_STARTING_ZONE])
                logger.debug(f"Set unlocked_zones for run {run.id}")

            # Migrate sub-ring data - ensure all runs have proper sub-ring values
            if not hasattr(run, 'current_ring_type') or not run.current_ring_type:
                run.current_ring_type = 'main'
                logger.debug(f"Set current_ring_type for run {run.id}")
            
            if not hasattr(run, 'sub_ring_position') or run.sub_ring_position is None:
                run.sub_ring_position = 0
                logger.debug(f"Set sub_ring_position for run {run.id}")

            # Migrate band keywords and golden field
            band = run.get_band()
            updated = False

            for minion in band:
                if 'keywords' not in minion:
                    minion['keywords'] = []
                    updated = True

                    # Auto-assign keywords based on minion type for existing minions
                    if 'archer' in minion['name'].lower():
                        minion['keywords'] = ['poke']
                    elif 'ranger' in minion['name'].lower():
                        minion['keywords'] = ['poke']
                    elif 'assassin' in minion['name'].lower():
                        minion['keywords'] = ['poke']

                # Add golden field if missing
                if 'golden' not in minion:
                    minion['golden'] = False
                    updated = True

            # Migrate ring position if it's outside the new ring bounds
            if run.ring_position >= 12:  # Old 8-event rings, reset to start
                run.ring_position = RING_START_POSITION
                updated = True
                logger.debug(f"Migrated ring position for run {run.id} to new starting position")

            if updated:
                run.set_band(band)
                logger.debug(f"Migrated keywords and golden field for run {run.id}")

        # Migrate ghost snapshots
        ghosts = GhostSnapshot.query.all()
        for ghost in ghosts:
            band = ghost.get_band()
            updated = False

            for minion in band:
                if 'keywords' not in minion:
                    minion['keywords'] = []
                    updated = True

                    # Auto-assign keywords based on minion type for existing ghosts
                    if 'archer' in minion['name'].lower():
                        minion['keywords'] = ['poke']
                    elif 'ranger' in minion['name'].lower():
                        minion['keywords'] = ['poke']
                    elif 'assassin' in minion['name'].lower():
                        minion['keywords'] = ['poke']

                # Add golden field if missing
                if 'golden' not in minion:
                    minion['golden'] = False
                    updated = True

            if updated:
                ghost.set_band(band)
                logger.debug(f"Migrated keywords and golden field for ghost {ghost.id}")

        db.session.commit()
        logger.debug("Keyword, golden field, zone, and sub-ring migration completed successfully!")

    except Exception as e:
        logger.error(f"Error during migration: {e}")
        db.session.rollback()


def initialize_admin_user():
    """Seed the Admin account only when ADMIN_PASSWORD is explicitly set.

    Rationale: hardcoding Admin/Admin on an internet-exposed server is a root
    compromise waiting to happen. Set ADMIN_PASSWORD in the environment to
    bootstrap the admin; leave it unset and no default admin exists.
    """
    import os
    try:
        from minions import get_all_minions, get_all_image_variants

        admin_password = os.environ.get('ADMIN_PASSWORD', '').strip()

        admin = Player.query.filter_by(username='Admin').first()

        if not admin:
            if not admin_password:
                logger.debug("ℹ️  No Admin account. Set ADMIN_PASSWORD env var to create one.")
                return
            logger.debug("Creating Admin user from ADMIN_PASSWORD env var...")
            admin = Player(username='Admin')
            admin.set_password(admin_password)
            admin.is_tester = False  # Admin is not a tester
            db.session.add(admin)
            db.session.flush()
        elif admin_password:
            # Env var provided — rotate password on boot
            admin.set_password(admin_password)
            logger.debug("🔒  Admin password rotated from ADMIN_PASSWORD env var.")

        # Unlock all image variants for admin
        all_minions = get_all_minions()
        for minion in all_minions:
            if minion.get('tier', 1) == 0 or not minion.get('image'):
                continue
            minion_id = minion.get('image', '').replace('.png', '')
            variants = get_all_image_variants(minion_id)
            for variant_info in variants:
                variant = variant_info['variant']
                if variant != 'original':
                    admin.add_owned_image(minion_id, variant)

        db.session.commit()
        logger.debug("Admin user ready with all images unlocked.")

    except Exception as e:
        logger.error(f"Error creating admin user: {e}")
        db.session.rollback()


def create_new_run(player_id=None, is_ranked=False, hero_id=None):
    """Create a new game run with starting band at the center of the ring"""
    import uuid
    try:
        run = Run(
            run_token=str(uuid.uuid4()),  # Unique token for ownership verification
            player_id=player_id,  # Link to player account
            is_ranked=is_ranked,  # Whether this is a ranked or unranked run
            current_ring=1,
            ring_position=RING_START_POSITION,  # Start in the middle of the ring
            current_zone=DEFAULT_STARTING_ZONE,  # Start in default zone
            events_count=0,
            is_active=True,
            hero_id=hero_id  # Selected hero ID
        )

        # Set sub-ring fields explicitly after creation (in case of migration issues)
        run.current_ring_type = 'main'
        run.current_sub_ring = None
        run.sub_ring_position = 0
        run.main_ring_return_position = None

        # Initialize zone data
        from game_engine.zone_controller import ZoneController
        ZoneController.initialize_run_zones(run)

        # Set hero effects
        if hero_id:
            from hero_definitions import get_hero
            hero = get_hero(hero_id)
            if hero:
                run.set_hero_effects(hero.get('effects', {}))
                logger.debug(f"[DATABASE] Run created with hero: {hero.get('name')} ({hero_id})")
            else:
                run.set_hero_effects({})
        else:
            run.set_hero_effects({})

        # Get hero-specific starting band
        if hero_id:
            from config import get_starting_band_for_hero
            starting_band_raw = get_starting_band_for_hero(hero_id)
        else:
            starting_band_raw = STARTING_BAND

        # Ensure starting band has keywords
        starting_band = []
        for minion_data in starting_band_raw:
            minion = minion_data.copy()
            if 'keywords' not in minion:
                minion['keywords'] = []
            starting_band.append(minion)

        run.set_band(starting_band)
        run.set_resources({'gold': 3, 'rerolls': 1})
        run.set_sub_ring_data(None)  # No sub-ring data initially

        db.session.add(run)
        db.session.commit()

        # Pre-generate the first ghost opponent (for event 10)
        pre_generate_ghost_opponent(run)

        # Trigger the starting event selection
        from game_logic import GameLogic
        starting_event = GameLogic.get_current_event(run)
        GameLogic.create_event_selection(run, starting_event)
        db.session.commit()

        return run

    except Exception as e:
        logger.error(f"Error creating run: {e}")
        db.session.rollback()
        
        # Fallback: create a minimal run without sub-ring fields
        try:
            run = Run()
            run.current_ring = 1
            run.ring_position = RING_START_POSITION
            run.current_zone = DEFAULT_STARTING_ZONE
            run.events_count = 0
            run.is_active = True
            
            # Try to set sub-ring fields if they exist
            try:
                run.current_ring_type = 'main'
                run.current_sub_ring = None
                run.sub_ring_position = 0
                run.main_ring_return_position = None
            except:
                logger.debug("Sub-ring fields not available, continuing without them")
            
            from game_engine.zone_controller import ZoneController
            ZoneController.initialize_run_zones(run)
            
            starting_band = []
            for minion_data in STARTING_BAND:
                minion = minion_data.copy()
                if 'keywords' not in minion:
                    minion['keywords'] = []
                starting_band.append(minion)

            run.set_band(starting_band)
            run.set_resources({'gold': 3, 'rerolls': 1})
            
            db.session.add(run)
            db.session.commit()
            
            return run
        except Exception as e2:
            logger.debug(f"Fallback creation also failed: {e2}")
            raise e


def get_run(run_id):
    """Get a run by ID"""
    return Run.query.get(run_id)


def update_run(run):
    """Update run in database"""
    db.session.commit()


def move_in_ring(run, direction):
    """Move player in current ring (left=-1, right=+1) in circular fashion"""
    # This function only handles main ring movement
    # Sub-ring movement is handled by SubRingController
    if hasattr(run, 'current_ring_type') and run.current_ring_type != 'main':
        return False  # Don't move main ring position if in sub-ring

    zone = getattr(run, 'current_zone', None)
    ring_events = GameLogic.get_ring_events(run.current_ring, zone=zone)
    ring_size = len(ring_events)

    if direction == 'left':
        run.ring_position = (run.ring_position - 1) % ring_size
    elif direction == 'right':
        run.ring_position = (run.ring_position + 1) % ring_size

    run.events_count += 1
    run.ring_upgrade_steps += 1  # Increment upgrade cost counter
    update_run(run)
    return True


def upgrade_ring(run):
    """Upgrade player to next ring (one-way) and reset to center position"""
    from config import MAX_RING_AVAILABLE

    # Prevent going above max ring
    if run.current_ring >= MAX_RING_AVAILABLE:
        logger.warning(f"[WARNING] Attempted to upgrade beyond MAX_RING_AVAILABLE ({MAX_RING_AVAILABLE})")
        return

    run.current_ring += 1
    run.ring_position = RING_START_POSITION  # Always start at center of new ring
    run.ring_upgrade_steps = 0  # Reset upgrade cost counter
    update_run(run)


def travel_to_zone(run, target_zone):
    """Travel to a different zone using ZoneController"""
    from game_engine.zone_controller import ZoneController
    return ZoneController.travel_to_zone(run, target_zone)


def check_ghost_battle_available(run):
    """Check if ghost battle buttons should be available (throughout the section)"""
    # Ghost battle is available if we have an upcoming ghost generated
    return run.upcoming_ghost_id is not None


def check_ghost_battle_trigger(run):
    """Check if ghost battle should trigger (at end of section when forced).

    Uses current milestone boundary (rounded down) instead of exact events_count.
    This handles cases where events_count skips past a milestone boundary
    (e.g., events that advance the counter, ring upgrades, sub-ring exits).
    """
    if run.events_count <= 0:
        return False

    # Find the current milestone boundary
    current_milestone = (run.events_count // EVENTS_FOR_GHOST_BATTLE) * EVENTS_FOR_GHOST_BATTLE
    if current_milestone <= 0:
        return False

    # Check if ghost battle has already been completed for this milestone
    from models import GhostBattle
    existing_battle = GhostBattle.query.filter_by(
        run_id=run.id,
        events_milestone=current_milestone
    ).first()

    # Return True only if no battle exists for this milestone
    return existing_battle is None


def create_ghost_snapshot(run, source=None, actions_log=None):
    """Create a ghost snapshot capturing the full player state for matchmaking.

    Stores: band, hero, images, ring, health, win/loss path, MMR.
    This becomes the ghost that OTHER players will fight against.

    source: 'player' (real human), 'headless' (AI headless run), 'ai' (fallback)
    actions_log: optional list of actions taken during the run (for headless analysis)
    """
    band = run.get_band()

    for minion in band:
        if 'keywords' not in minion:
            minion['keywords'] = []

    power_level = GameLogic.calculate_band_power(band)

    # Count ghost wins/losses so far in this run
    ghost_wins = GhostBattle.query.filter_by(run_id=run.id, winner='player').count()
    ghost_losses = GhostBattle.query.filter_by(run_id=run.id, winner='ghost').count()

    # Get player info if logged in
    player_name = None
    player_mmr = None
    equipped_images = None
    if run.player_id:
        from models import Player
        player = Player.query.get(run.player_id)
        if player:
            player_name = player.username
            player_mmr = player.mmr
            equipped_images = player.get_equipped_images()
    else:
        # Headless/anonymous runs: use hero name so ghosts have personality
        if run.hero_id:
            from hero_definitions import get_hero
            hero = get_hero(run.hero_id)
            if hero:
                player_name = hero.get('name', run.hero_id.capitalize())

    # Auto-detect source if not specified
    if source is None:
        source = 'player' if run.player_id else 'headless'

    ghost = GhostSnapshot(
        events_milestone=run.events_count,
        power_level=power_level,
        player_id=run.player_id,
        player_name=player_name,
        hero_id=run.hero_id,
        current_ring=run.current_ring,
        health=run.health,
        ghost_wins_at_capture=ghost_wins,
        ghost_losses_at_capture=ghost_losses,
        mmr=player_mmr,
        is_ranked=run.is_ranked or False,
        source=source,
        run_id=run.id,
    )
    ghost.set_band(band)
    ghost.set_hero_effects(run.get_hero_effects())
    ghost.set_equipped_images(equipped_images)
    if actions_log:
        ghost.set_actions_log(actions_log)

    db.session.add(ghost)
    db.session.commit()
    return ghost


def find_ghost_opponent(run, target_milestone):
    """Find a suitable ghost opponent matching the player's progression path.

    Matching priority:
    1. Same milestone, similar win/loss path, similar MMR (ranked only)
    2. Same milestone, similar win/loss path
    3. Same milestone, any path
    4. Fallback: generate an AI ghost

    Never returns the player's own ghosts. Tester and non-tester players are
    isolated from each other so beta data never pollutes a real leaderboard,
    and vice-versa. AI / headless ghosts (no player_id) match anyone — they
    exist precisely to backfill sparse pools.
    """
    from models import Player
    from flask import current_app

    # NOTE: This is called at the START of a section to pre-generate for the END.
    # The player's band will be stronger by the time they actually fight, so we use
    # wider power ranges to account for growth during the section.
    player_power = GameLogic.calculate_band_power(run.get_band())

    # Count player's current ghost wins/losses
    player_ghost_wins = GhostBattle.query.filter_by(run_id=run.id, winner='player').count()
    player_ghost_losses = GhostBattle.query.filter_by(run_id=run.id, winner='ghost').count()

    # Determine tester-affinity of this run. Anonymous runs inherit BETA_MODE.
    if run.player_id:
        owner = Player.query.get(run.player_id)
        run_is_tester = bool(owner and owner.is_tester)
    else:
        try:
            run_is_tester = bool(current_app.config.get('BETA_MODE', False))
        except RuntimeError:
            # Outside app context (shouldn't happen in normal flow)
            run_is_tester = False

    # Base query: correct milestone, not our own ghosts
    base_query = GhostSnapshot.query.filter_by(events_milestone=target_milestone)
    # Exclude ghosts from the same run (prevents fighting your own snapshots)
    base_query = base_query.filter(GhostSnapshot.run_id != run.id)
    # Also exclude by player_id for logged-in players (prevents fighting any of your ghosts)
    if run.player_id:
        base_query = base_query.filter(GhostSnapshot.player_id != run.player_id)

    # Tester/non-tester isolation. Use an OUTER JOIN so ghosts with NULL player_id
    # (AI / headless) pass through the filter — only ghosts tied to a real player
    # on the *opposite* side are rejected.
    base_query = base_query.outerjoin(Player, GhostSnapshot.player_id == Player.id).filter(
        (Player.id.is_(None)) | (Player.is_tester == run_is_tester)
    )

    # Try 1: Match win/loss path (±1) + power range (±50%)
    # Wide power range because ghost is pre-generated before the player's band grows
    path_query = base_query.filter(
        GhostSnapshot.ghost_wins_at_capture.between(
            max(0, player_ghost_wins - 1), player_ghost_wins + 1
        ),
        GhostSnapshot.ghost_losses_at_capture.between(
            max(0, player_ghost_losses - 1), player_ghost_losses + 1
        ),
    )
    if player_power > 0:
        power_range = max(player_power * 0.5, 5)
        path_query = path_query.filter(
            GhostSnapshot.power_level.between(
                int(player_power - power_range),
                int(player_power + power_range)
            )
        )

    # For ranked: also try MMR matching
    if run.is_ranked and run.player_id:
        player = Player.query.get(run.player_id)
        if player:
            mmr_range = 200
            ranked_ghosts = path_query.filter(
                GhostSnapshot.is_ranked == True,
                GhostSnapshot.mmr.between(player.mmr - mmr_range, player.mmr + mmr_range)
            ).all()
            if ranked_ghosts:
                return random.choice(ranked_ghosts)

    # Try with path matching
    path_ghosts = path_query.all()
    if path_ghosts:
        return random.choice(path_ghosts)

    # Try 2: Same milestone, any path, power range (±75%)
    if player_power > 0:
        power_range = max(player_power * 0.75, 10)
        wider = base_query.filter(
            GhostSnapshot.power_level.between(
                int(player_power - power_range),
                int(player_power + power_range)
            )
        ).all()
        if wider:
            return random.choice(wider)

    # Try 3: Same milestone, anything
    any_ghosts = base_query.all()
    if any_ghosts:
        return random.choice(any_ghosts)

    # Fallback: generate AI ghost
    return create_ai_ghost(target_milestone, run.current_ring)


def create_ai_ghost(events_milestone, ring=None):
    """Create an AI ghost when no player ghosts are available.
    Always assigns a random hero so AI ghosts have proper typing and effects."""
    estimated_ring = ring or min((events_milestone // 10) + 1, 4)
    hero_id = random.choice(['silas', 'puck', 'olimpia'])

    # Get the hero's base effects so AI ghosts have real hero powers
    from hero_definitions import get_hero
    hero = get_hero(hero_id)
    hero_effects = hero.get('effects', {}) if hero else {}
    hero_name = hero.get('name', hero_id.capitalize()) if hero else 'AI Opponent'

    ai_band = []
    for i in range(min(2 + estimated_ring, 6)):
        minion = GameLogic._generate_minion(estimated_ring)
        minion['health'] += events_milestone // 5
        minion['attack'] += events_milestone // 10
        minion['position'] = i
        if 'keywords' not in minion:
            minion['keywords'] = []
        ai_band.append(minion)

    power_level = GameLogic.calculate_band_power(ai_band)

    ghost = GhostSnapshot(
        events_milestone=events_milestone,
        power_level=power_level,
        player_name=hero_name,
        hero_id=hero_id,
        current_ring=estimated_ring,
        health=30,
        ghost_wins_at_capture=0,
        ghost_losses_at_capture=0,
        source='ai',
    )
    ghost.set_band(ai_band)
    ghost.set_hero_effects(hero_effects)

    db.session.add(ghost)
    db.session.commit()
    return ghost


def pre_generate_ghost_opponent(run):
    """Pre-generate ghost opponent for the next milestone.
    Called at start of each section (events 0, 10, 20, etc.)
    """
    return pre_generate_ghost_opponent_for_milestone(run, None)


def pre_generate_ghost_opponent_for_milestone(run, target_milestone=None):
    """Pre-generate ghost opponent for a specific milestone.

    Uses real ghost matching: finds a player ghost from the pool that
    matches the current player's progression path. Falls back to AI ghost.
    """
    if target_milestone is None:
        next_milestone = ((run.events_count // EVENTS_FOR_GHOST_BATTLE) + 1) * EVENTS_FOR_GHOST_BATTLE
    else:
        next_milestone = target_milestone

    logger.debug(f"[GHOST] Generating opponent for milestone {next_milestone} "
          f"(events={run.events_count}, ring={run.current_ring})")

    ghost = find_ghost_opponent(run, next_milestone)

    run.upcoming_ghost_id = ghost.id
    db.session.commit()

    logger.debug(f"[GHOST] Matched ghost {ghost.id} "
          f"(player={ghost.player_name or 'AI'}, power={ghost.power_level}, "
          f"hero={ghost.hero_id or 'none'}, ring={ghost.current_ring})")
    return ghost


def record_ghost_battle(run, ghost, winner, battle_log):
    """Record the results of a ghost battle.

    Records at max(ghost milestone, current milestone boundary).
    - Normal fight at MS 20 with ghost MS 20 → records at 20
    - Skipped MS: fight at MS 20 with ghost MS 10 → records at 20 (prevents infinite re-trigger)
    - Early fight at events 5 with ghost MS 10 → records at 10 (blocks trigger when MS 10 is reached)
    """
    current_milestone = (run.events_count // EVENTS_FOR_GHOST_BATTLE) * EVENTS_FOR_GHOST_BATTLE
    battle_milestone = max(ghost.events_milestone, current_milestone)

    battle = GhostBattle(
        run_id=run.id,
        ghost_id=ghost.id,
        events_milestone=battle_milestone,
        winner=winner,
        ghost_player_name=ghost.player_name,
    )
    battle.set_battle_log(battle_log)

    db.session.add(battle)
    db.session.commit()
    return battle


def get_active_runs():
    """Get all active runs (for debugging)"""
    return Run.query.filter_by(is_active=True).all()


def get_recent_ghost_battles(limit=10):
    """Get recent ghost battles (for debugging)"""
    return GhostBattle.query.order_by(GhostBattle.created_at.desc()).limit(limit).all()


def validate_band_keywords(band):
    """Validate all keywords in a band are properly defined"""
    for minion in band:
        keywords = minion.get('keywords', [])
        if not validate_keywords(keywords):
            logger.warning(f"Warning: Invalid keywords found in minion {minion.get('name', 'Unknown')}: {keywords}")
            # Clean invalid keywords
            minion['keywords'] = [kw for kw in keywords if validate_keywords([kw])]
    return band