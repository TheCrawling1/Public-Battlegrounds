# Game Design & Systems Reference

A design and feature reference for the auto-battler. For focused deep-dives see the
sibling docs: [`EVENTS.md`](EVENTS.md) (event system), [`SNAPSHOT_PLAYER.md`](SNAPSHOT_PLAYER.md)
(combat replay/testing), [`TOOLTIP_KEYWORD_SYSTEM.md`](TOOLTIP_KEYWORD_SYSTEM.md) and
[`MINION_DISPLAY_CARDS.md`](MINION_DISPLAY_CARDS.md) (frontend rendering).

## Game Overview

A turn-based auto-battler where you build a band of minions with keyword-driven
abilities. Each keyword changes how a minion behaves in combat, enabling strategic
combinations.

### Core Gameplay Loop

1. **Ring navigation** — move left/right around a circular event ring.
2. **Shopping / band building** — buy minions and shape your band composition.
3. **Combat** — your band auto-resolves battles with keyword interactions.
4. **Economy** — balance spending against future potential.
5. **Scaling** — grow power through golden upgrades and synergies.
6. **Ghost battles** — fight snapshots of other players' bands every 10 events.

## Key Features

### Combat System
- Priority-based trigger queue for deterministic effect resolution.
- Combat interpreter that decouples backend combat from frontend playback via a
  command + snapshot stream (see [`SNAPSHOT_PLAYER.md`](SNAPSHOT_PLAYER.md)).
- Modular effects architecture for complex keyword interactions.
- Round cap (`MAX_COMBAT_ROUNDS`) prevents infinite combat loops.
- Health reset after combat by default (`RESET_HEALTH_AFTER_COMBAT`).
- Three playback controls: Next (step), Auto (watch), End (skip to summary).

### Keyword System
The game has an extensive keyword system (60+ registry entries covering combat
keywords plus tooltip terms). Core combat keywords include:

- **Poke** — takes no counter-attack damage when attacking.
- **Guard** — other minions cannot be attacked until this one is killed.
- **Assault** — triggers an effect when this minion attacks (requires >0 attack).
- **Death Toll** — triggers an effect when this minion dies.
- **Cast** — casts a spell instead of attacking normally.
- **Rage** — triggers when other minions act.
- **On Any Death / On Any Cast / On Any Summon** — reactive triggers.
- **Can't Attack** — cannot attack (but can still cast).
- **Can't Retaliate** — deals no counter damage.
- **Multi Attack** — attacks multiple times per turn.
- **Cleave, Hide, Leap, Aura, Nobility, Savage, Fast**, and more.

Keyword definitions live in `js/constants.js` / `js/game-core.js` (display) and are
driven server-side by `keywords.py` and the trigger/effect registries.

### Ring, Zone & Sub-Ring Progression
- Circular ring of events (`RING_SIZE = 12` events per ring); move left or right.
- Ring upgrades advance difficulty and rewards (one-way progression).
- Seven zones with distinct minion pools and themes (see Configuration below).
- Zone portals for travel between areas.
- Sub-rings: short branching paths with higher risk/reward.

### Ghost Battles
- Triggered every 10 events (`EVENTS_FOR_GHOST_BATTLE`).
- Fight snapshots of other players' bands, with power-based matchmaking.
- Rewards for victory, lighter penalties for defeat.

### Multi-Platform
- Desktop and mobile web interfaces sharing one backend (responsive).

## Architecture

The game is **server-authoritative**: all game logic, rules, calculations, and
validation run in the Python/Flask backend, which also generates the UI state. The
JavaScript client is a pure renderer — it makes API calls and replays a server-authored
command stream, and never computes combat itself.

### Combat Interpreter
The interpreter bridges backend combat and frontend visualization. The backend resolves
a fight into an ordered list of commands, and emits a full band **snapshot after each
command**. The client plays the commands back as animations and overwrites its bands with
each snapshot. See [`SNAPSHOT_PLAYER.md`](SNAPSHOT_PLAYER.md) for the full contract and
its test harness.

### Modular Combat Effects
Combat triggers and effects are split into focused modules under `game_engine/`:

- `trigger_queue.py` — FIFO queue with priority management.
- `trigger_processor.py` — orchestrates trigger resolution and effect application.
- `combat_context.py` — combat state and band-context management.
- `combat_interpreter.py` — converts combat results into frontend command sequences.
- `combat_registry.py` — single source of truth for band membership (see below).
- `effects/` — modular effect implementations (`__init__.py` holds the
  `EFFECT_HANDLERS` dispatcher and `apply_effect()`; alongside `damage_effects.py`,
  `stat_effects.py`, `summon_effects.py`, `special_effects.py`, `special_effects2.py`,
  `conditional_effects.py`, `combat_effects.py`).
- `triggers/` — trigger registry, condition checker, generic processor, golden doubler.
- `interpreter/` — command/bundle builders and registries for the command stream.

### GameRandom
`game_random.py` provides centralized, type-safe random selection (`SelectionType`
enum) with a dev-mode override queue and selection history, enabling reproducible
snapshot-replay tests.

## Critical Architecture Requirements

### Combat Registry — single source of truth
`CombatRegistry` (`game_engine/combat_registry.py`) is the only authoritative source for
band membership during combat. Membership is queried via
`registry.get_minion_band_type(minion)` — never by checking array membership or by
inferring from whose turn it is. The registry persists membership even for dead minions,
which death-toll effects rely on.

### Absolute vs relative context
Combat contexts preserve both perspectives:

- **Absolute** — `absolute_player_band` / `absolute_enemy_band` always refer to the same
  bands. Used for summons and band modifications.
- **Relative** — `ally_band` / `enemy_band` are relative to the acting minion. Used for
  targeting (e.g. "heal random ally").

### Turn-independent effects
Effects must never determine behavior from whose turn it is. Resolve the acting minion's
band via the registry and choose the absolute band accordingly.

### Unified combat modes
Next, Auto, and End modes share identical logic — `CombatSystem.process_combat_step()` is
the single stepping primitive — so results are consistent across modes.

## Installation & Setup

### Prerequisites
- Python 3.11+
- Node.js (only for the frontend snapshot test)

### Quick start
```bash
cd Battlegrounds
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Minimum configuration (see Battlegrounds/.env.example for all options)
export SAFETY_PASSWORD=letmein
export SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_urlsafe(48))")

python app.py                 # http://localhost:5000
```

Enter the safety access code at `/safety-login` to reach the game (the console prints one
on first run if `SAFETY_PASSWORD` is unset).

### Production
Do not use the Flask dev server in production. Serve via a WSGI server behind a TLS
reverse proxy:
```bash
gunicorn -w 4 wsgi:app
```
Set a fixed `SECRET_KEY` and `SAFETY_PASSWORD`, and `SESSION_COOKIE_SECURE=true` once
HTTPS is in place. Developer tooling is disabled unless `ENABLE_DEV_ROUTES=true` — never
enable it in production.

### Project structure
```
Battlegrounds/
├── app.py                  # Flask app factory + entry point
├── wsgi.py                 # Production WSGI entry point
├── models.py               # SQLAlchemy models (SQLite)
├── database.py             # DB initialization and migration
├── config.py               # Game configuration constants
├── routes.py               # Main game API (server-authoritative)
├── auth_routes.py          # Auth API
├── safety_routes.py        # Safety-gate API
├── collection_routes.py    # Collection API
├── keywords.py             # Keyword system with targeting logic
├── minions.py              # Minion + boss definitions
├── game_random.py          # Centralized random with dev overrides
├── hero_definitions.py     # Hero definitions + starting bands
│
├── game_engine/            # Core game systems
│   ├── combat_system.py        # Combat processing (process_combat_step / resolve_combat)
│   ├── combat_registry.py      # Band-membership tracking (authoritative)
│   ├── combat_context.py       # Context management for effects
│   ├── combat_interpreter.py   # Command/snapshot stream for the frontend
│   ├── combat_actions.py / combat_action_registry.py
│   ├── damage_handler.py
│   ├── trigger_queue.py        # FIFO queue with priorities
│   ├── trigger_processor.py    # Orchestrates trigger resolution
│   ├── game_controller.py      # Game flow controller
│   ├── selection_system.py     # Choice handling with validation
│   ├── band_manager.py         # Minion band management
│   ├── zone_controller.py      # Zone system and travel
│   ├── sub_ring_controller.py  # Sub-ring adventures
│   ├── effects/                # Modular effect implementations
│   ├── triggers/               # Trigger registry + processors
│   ├── interpreter/            # Command-stream builders
│   ├── animations/             # Animation templates
│   └── events/                 # Event system (see EVENTS.md)
│
├── event_registry.py       # Event metadata catalog (see EVENTS.md)
├── index.html              # Main game interface
├── desktop.css / mobile.css / animations.css / collection.css
├── js/                     # Frontend (client renderer, UI only)
│   ├── game-core.js            # Core API calls and state
│   ├── combat.js               # Combat replay
│   ├── ui/                     # Rendering modules (display-*.js)
│   ├── ui-display-mobile.js    # Mobile UI rendering
│   ├── collection.js           # Collection / meta screens
│   ├── events.js               # Event handling (UI only)
│   └── constants.js            # UI constants and keyword display data
│
├── scripts/                # Admin CLIs (add_user.py, make_invite.py)
├── images/                 # Game assets
├── requirements.txt        # Python dependencies
└── tests/                  # Test suite
```

## API Reference

The main game API is registered under the `/api` prefix.

### Core game endpoints
```
POST /api/start-run                       # Start new game
GET  /api/run/<id>                         # Get game state with UI data
POST /api/run/<id>/move                    # Move left/right
POST /api/run/<id>/select                  # Submit a selection (validated)
GET  /api/run/<id>/selection               # Get current pending selection
POST /api/run/<id>/upgrade-ring            # Advance to next ring
POST /api/run/<id>/travel-zone             # Travel to a different zone
POST /api/run/<id>/combat/interpreter/step # Step the combat interpreter
POST /api/run/<id>/abandon                 # Abandon the run
POST /api/run/<id>/end                     # End the run
GET  /api/check-active-run                 # Check for an active run
```

### Ghost battles
```
POST /api/run/<id>/ghost-battle       # Start scheduled ghost battle
POST /api/run/<id>/preview-ghost      # Preview a ghost matchup
POST /api/run/<id>/fight-ghost-early  # Fight a ghost ahead of schedule
```

### Band management
```
POST /api/run/<id>/swap-minions       # Swap minion positions
POST /api/run/<id>/abandon-minion     # Remove a minion from the band
```

### Debug endpoints (under `/api/debug`)
```
GET /api/debug/runs
GET /api/debug/ghost-battles
GET /api/debug/ghosts
GET /api/debug/keywords
GET /api/debug/ring-events/<ring_level>
GET /api/debug/sub-rings
GET /api/debug/zones
```

### Developer tooling (optional)
Developer blueprints mount only when `ENABLE_DEV_ROUTES=true`, exposing the combat
simulator (`/api/dev`, page `dev-combat.html`), event tester (`/api/dev-events`, page
`dev-events.html`), and ghost editor (`/api/dev-ghosts`, page `dev-ghosts.html`). These
are for local development only.

## Configuration

Key constants in `config.py`:
```python
MAX_BAND_SIZE = 6                     # Maximum minions per band
EVENTS_FOR_GHOST_BATTLE = 10          # Events between ghost battles
RING_SIZE = 12                        # Events per ring (circular)
RESET_HEALTH_AFTER_COMBAT = True      # Reset minion health after combat
AUTO_COMBAT_DELAY_MS = 1500           # Auto-combat step delay
MAX_COMBAT_ROUNDS = 60                # Round cap before combat auto-ends
DEFAULT_STARTING_ZONE = 'starting_plains'
```

### Zones
`config.py`'s `ZONES` defines seven zones: `starting_plains`, `beast_wildlands`,
`human_kingdom`, `undead_crypts`, `fey_grove`, `construct_foundry`, `cult_sanctum`. Each
zone can override the default ring event pattern with its own.

### Heroes & starting bands
Heroes are defined in `hero_definitions.py`, each with its own two-minion starting band
(e.g. Silas → Scout + Soldier). `config.get_starting_band_for_hero()` instantiates real
minion definitions for the chosen hero.

## Game Flow

1. Start a run with your hero's starting band.
2. Choose a direction and navigate the ring.
3. Make selections — minions, buffs, purchases.
4. Manage your band — swap positions, abandon weak minions.
5. Fight battles with the Next / Auto / End controls.
6. Face a ghost battle roughly every 10 events.

### Event types
- **Minion events** — choose from a set of random minions; smart replacement when the
  band is full.
- **Blessing events** — choose a buff type and target a minion.
- **Shop events** — buy minions with gold; affordability validated server-side.
- **Combat events** — NPC battles with victory rewards and defeat penalties.
- **Zone portal events** — travel between zones with different minion pools.
- **Branching / sub-ring events** — choose immediate events or enter a sub-ring.

For how events are defined, chained, and added, see [`EVENTS.md`](EVENTS.md).

## Testing

The maintained suite is a snapshot-replay harness verifying that the backend combat
engine and the frontend replayer produce identical state step by step:
```bash
npm run test:snapshot     # backend (Python) + frontend (jsdom)
```
Individual backend modules under `Battlegrounds/tests/` run as standalone scripts. See
[`SNAPSHOT_PLAYER.md`](SNAPSHOT_PLAYER.md) for details.
