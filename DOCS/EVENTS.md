# Event System

This document covers the event architecture, how events flow at runtime, and how to add new ones.

## Architecture Overview

The event system is split across six files:

| File | Purpose |
|------|---------|
| `game_engine/events/events.py` | **Event definitions** - every event as a dict |
| `game_engine/events/event_templates.py` | **Screen type registry** - what screen types exist and their parameters |
| `game_engine/events/event_helpers.py` | **Helpers** - formula resolution, tooltip substitution, condition evaluation |
| `game_engine/events/effect_actions.py` | **Effect registry** - declarative `on_select` handlers and action executors |
| `game_engine/events/event_system.py` | **Runtime engine** - `EventSystem.create_event_selection()` and `SelectionSystem.resolve_selection()` |
| `event_registry.py` | **Metadata catalog** - events organized by category with descriptions and flow diagrams |

Events validate on import. If you add a broken event, the server won't start.

## Event Structure

Every event is a Python dict with this shape:

```python
MY_EVENT = {
    'id': 'my_event',                    # Unique ID (snake_case)
    'visit_rule': 'repeatable',          # How often player can visit
    'title': 'My Event',                 # Display title
    'description': 'What this event is', # One-line summary
    'screens': [                         # Ordered list of screens
        {
            'id': 'screen_id',           # Unique within this event
            'type': 'screen_type',       # Must match EVENT_SCREEN_REGISTRY
            'parameters': { ... },       # Screen-type-specific params
            'on_continue': 'next_id',    # (optional) next screen within same event
        }
    ]
}
```

### Visit Rules

| Rule | Behavior |
|------|----------|
| `repeatable` | Player can visit unlimited times |
| `once_per_run` | Player can visit once per run |
| `once_per_ring` | Resets each ring, one visit per ring |

### Optional Top-Level Fields

| Field | Type | Purpose |
|-------|------|---------|
| `forced_event` | `bool` | Player cannot leave without choosing (no implicit Leave) |
| `check_active_boss` | `bool` | If `active_boss` is in event_state, force boss combat |
| `route_by_boss` | `bool` | Route to boss-specific victory event |
| `mark_event_complete` | on a choice | Remove the event from the pool after this choice is selected |
| `state_defaults` | `dict` | Default values for `event_state` keys this event uses (see below) |

### state_defaults

Events that track persistent state across visits (counters, seals, etc.) should declare their state keys and defaults at the top level:

```python
IVORY_TOWER = {
    'id': 'ivory_tower',
    'state_defaults': {
        'ivory_tower_seal': 4,   # Seal starts at 4, decremented each visit
    },
    ...
}
```

This serves two purposes:
1. **Tooltips** — `build_tooltip_context()` reads `state_defaults` and populates each key from the run's `event_state`, falling back to the declared default on first visit. Tooltips can reference `{ivory_tower_seal}` and it just works.
2. **Conditions** — Generic `>=` / `<=` comparisons use `state_defaults` as the fallback value, so `ivory_tower_seal <= 0` correctly evaluates to disabled (seal=4) on a fresh run without hardcoded init logic.


## Screen Types

Screens are the building blocks. Each type is defined in `event_templates.py`.

### Selection Screens

#### `make_choice`
The most common screen for general events. Presents a list of choices to the player.

```python
{
    'id': 'choice',
    'type': 'make_choice',
    'parameters': {
        'title': 'Event Title',
        'message': 'Flavor text describing the situation.',
        'choices': [
            {
                'name': 'Option Name',
                'description': 'Short label shown on the button',
                'tooltip': 'Detailed hover text. Supports {gold_cost}, {tier * N} templates.',
                'icon': generate_lucide_svg('icon-name', width=24, height=24),

                # --- Action (pick one or combine) ---
                'next_event': 'other_event_id',   # Chain to a different event
                'on_select': 'handler_name',       # Server-side effect
                'next_event': None,                # None = event ends

                # --- Optional modifiers ---
                'gold_cost': 'tier * 3',           # Formula, deducted on select
                'gold_reward': 'tier * 4',         # Formula, granted on select
                'health_cost': 7,                  # Static HP cost (respects Lichdom)
                'health_cost_tracker': 'name',     # Escalating HP cost key in event_state
                'condition': 'condition_string',   # Show but disable until met
                'disabled_until_met': True,        # Grey out when condition fails
                'mark_event_complete': True,       # Remove event from pool after select
            },
            # ... more choices
        ]
    }
}
```

#### `select_minion`
Offer minions for the player to pick from.

```python
{
    'type': 'select_minion',
    'parameters': {
        'count': 3,                    # Number of minions offered
        'tier_pool': 'multi_tier',     # 'multi_tier', 'current_tier', or int
        'title': 'Choose a Minion',
        'message': 'Pick one.',
        'allow_skip': False,           # Can the player decline?
        'tribe_filter': 'Human',       # (optional) restrict to a tribe
        'minion_pool': ['Hound'],      # (optional) specific named minions
    }
}
```

#### `select_buff_type`
Let the player choose a buff category (health, attack, or mixed), then chain to target selection.

```python
{
    'type': 'select_buff_type',
    'parameters': {
        'buff_power': 'normal',   # 'normal', 'strong', 'major', 'ultimate'
        'title': 'Choose Blessing',
        'allow_skip': False
    }
}
```

#### `select_buff_target`
Choose which minion receives a buff/keyword.

```python
{
    'type': 'select_buff_target',
    'parameters': {
        'buff_type': 'keyword_guard',   # What to apply
        'title': 'Hire Guard',
        'message': 'Choose a minion to gain Guard',
        'tribe_filter': 'Beast',        # (optional) restrict targets
    }
}
```

### Action Screens

#### `combat`
Trigger a combat encounter.

```python
{
    'type': 'combat',
    'parameters': {
        'difficulty': 'normal',        # 'normal', 'hard', 'elite'
        'title': 'Combat Title',
        'pool_filter': 'Human',        # (optional) enemy tribe restriction
        'disable_gold_reward': True,   # (optional) no gold on win
    },
    'on_victory': 'screen_id',         # Next screen in same event
    'on_victory_event': 'event_id',    # OR chain to different event
    'on_defeat': None                  # None = run ends
}
```

#### `shop`
Repeating purchase screen.

```python
{ 'type': 'shop', 'parameters': { 'title': 'Tavern' } }
```

#### `statue`
Combine minions into golden versions. Repeating.

```python
{ 'type': 'statue', 'parameters': { 'title': 'Golden Statue' } }
```

### Story / Reward Screens

#### `story`
Narrative text with a Continue button.

```python
{
    'type': 'story',
    'parameters': {
        'title': 'Title',
        'text': 'Narrative paragraph.',
        'icon': 'church',               # Lucide icon name
        'continue_text': 'Continue'
    },
    'on_continue': 'next_screen_id'
}
```

#### `grant_gold`
Auto-execute: grant gold and move on.

```python
{ 'type': 'grant_gold', 'parameters': { 'amount': 10 } }
```

#### `grant_minion`
Grant a specific named minion.

```python
{
    'type': 'grant_minion',
    'parameters': {
        'minion_name': 'Quasimodo',
        'tier': 5,
        'title': 'The Bell Ringer Joins You',
        'message': 'Quasimodo joins your cause!'
    }
}
```


## Chaining Events

Events can chain to other events via **`next_event`** on choices or **`on_victory_event`** on combat screens. This is how complex multi-step flows work.

**Within same event** (screen-to-screen):
- `on_continue`: story -> next screen
- `on_complete`: after a selection -> next screen
- `on_victory` / `on_defeat`: combat outcome -> next screen

**Between events** (event-to-event):
- `next_event`: choice -> triggers a different event definition
- `on_victory_event`: combat victory -> triggers a different event

When an event chains via `next_event`, the `EventSystem` looks up the target event by ID in `ALL_CUSTOM_EVENTS` and creates a fresh selection from it. The run state (gold, band, event_state) persists across the chain.


## Formulas and Tooltips

### Tier-Based Formulas

Fields like `gold_cost`, `gold_reward` accept formulas that scale with the current ring:

```python
'gold_cost': 'tier * 3'      # Ring 1 = 3, Ring 2 = 6, Ring 3 = 9
'gold_cost': '25'             # Static cost
'gold_cost': 'tier * 3 + 2'  # Arithmetic expressions work
```

Resolved by `resolve_formula()` in `event_helpers.py`.

### Tooltip Templates

Tooltips can reference dynamic values with `{variable}` syntax:

```python
'tooltip': 'Pay ({gold_cost}) gold to give a minion Guard.'
# At tier 2 with gold_cost='tier * 6': "Pay (12) gold to give a minion Guard."

'tooltip': 'All Beasts gain +{tier * 2} attack.'
# At tier 3: "All Beasts gain +6 attack."
```

Available template variables (auto-populated by `build_tooltip_context()`):
- `{gold_cost}` - resolved from the choice's `gold_cost` formula
- `{gold_reward}` - resolved from the choice's `gold_reward` formula
- `{tier}` - current ring level
- `{tier * N}` - any inline tier formula
- `{ivory_tower_seal}` - from event_state
- `{bells_rung}` - from event_state
- `{health_cost_tracker_name}` - escalating cost from event_state


## Conditions

Conditions control when a choice is available. When `disabled_until_met: True`, the option shows but is greyed out until the condition is satisfied.

### Built-in Conditions

| Condition String | What It Checks |
|------------------|---------------|
| `has_keyword_fast` | Any minion has the `fast` keyword |
| `has_keyword_hide` | Any minion has the `hide` keyword |
| `unique_tribes >= 4` | Band has 4+ different tribes |
| `beast_count >= 3` | Band has 3+ Beast minions |
| `band_size >= 1` | Band has at least 1 minion |
| `bells_rung >= 4` | event_state counter check (generic `>=`) |
| `ivory_tower_seal <= 0` | event_state counter check (generic `<=`) |
| `boss_not_defeated_this_tier` | No boss defeated at current tier |
| `has_beast_and_2_minions` | At least 1 Beast and 2 total minions |
| `has_transcendence_candidate` | A Tier 2+ minion with 0 atk, 1 hp, no types, no keywords |
| `not_has_lichdom` | Player doesn't have Lichdom hero effect |
| `scrap_heap_blind_luck_available` | Always disabled (unlocked externally) |

### Adding a New Condition

1. Write a handler function in `event_helpers.py`:
   ```python
   def _check_my_condition(run, event_state, condition):
       """Return True if option should be DISABLED"""
       band = run.get_band()
       return not any(m.get('type') == 'Dragon' for m in band)
   ```

2. Register it in `CONDITION_HANDLERS`:
   ```python
   CONDITION_HANDLERS = [
       # ... existing handlers
       ('has_dragon', _check_my_condition),
   ]
   ```

3. Use it in your event:
   ```python
   'condition': 'has_dragon',
   'disabled_until_met': True,
   ```

For generic comparisons against `event_state` values, the `>=` and `<=` operators are handled automatically - no new handler needed:
```python
'condition': 'my_counter >= 5'  # checks event_state['my_counter'] >= 5
```


## on_select Handlers

The `on_select` field names a server-side handler that runs when the player picks that choice. All handlers are defined in `effect_actions.py` and dispatched by `execute_on_select()`.

There are two ways to define a handler:

### 1. Declarative (EFFECT_REGISTRY) - preferred for most handlers

Most handlers are just a list of action dicts. No code needed:

```python
# effect_actions.py
EFFECT_REGISTRY = {
    'collapsed_mine_slow': [
        {'type': 'grant_gold', 'amount': '4 * tier'},
        {'type': 'add_steps', 'steps': 1, 'message': 'Took extra time gathering gold. +1 step.'},
    ],
    'buff_beasts_attack': [
        {'type': 'buff_all', 'attack': '2 * tier', 'health': 0, 'type_filter': 'Beast',
         'message': '{count} Beasts gained +{attack} attack!'},
    ],
}
```

### 2. Custom (CUSTOM_HANDLERS) - for complex logic

When you need conditionals, randomness, or multi-step logic that can't be expressed as a simple action list:

```python
def _handle_my_complex(ctx):
    if some_condition:
        ctx['results'].append('Something happened')
    ctx['run'].set_event_state(ctx['event_state'])

CUSTOM_HANDLERS['my_complex'] = _handle_my_complex
```

Custom handlers receive a `ctx` dict with: `run`, `tier`, `band`, `event_state`, `resources`, `results`, `selected_option`, `_failed`.

### Available Action Types

| Action Type | Parameters | Description |
|-------------|-----------|-------------|
| `grant_gold` | `amount` (int\|formula) | Add gold to player resources |
| `buff_all` | `attack`, `health` (int\|formula), `type_filter` (optional) | Buff all minions (or filtered by type) |
| `buff_target` | `attack`, `health`, `add_keywords` (list), `set_properties` (dict) | Buff a specific minion by `target_index` |
| `set_type_target` | `new_type` (str) | Change a target minion's tribe type |
| `set_state` | `key`, `value` | Set an `event_state` key |
| `increment_state` | `key`, `amount` (default 1), `default` (default 0) | Increment an `event_state` counter |
| `decrement_state` | `key`, `amount` (default 1), `default` (default 0) | Decrement an `event_state` counter |
| `init_state` | `key`, `default` | Set an `event_state` key only if it doesn't exist |
| `add_steps` | `steps` (int) | Add steps to the player's path (costs movement) |
| `remove_steps` | `steps` (int) | Remove steps from the player's path (saves movement) |
| `pay_health` | `cost` (int) | Pay HP (respects Lichdom). Stops action chain on failure |
| `clear_curse` | — | Remove curse_level and curse_type from event_state |
| `clear_boss` | `boss_id` (str) | Clear active_boss and record boss as defeated |
| `mark_complete` | `event_id` (str) | Add event to completed_events list |
| `message` | `text` (str) | Append a message to results. Supports `{tier}` |

Every action supports an optional `message` field for custom result text. Messages support format variables: `{amount}`, `{tier}`, `{count}`, `{attack}`, `{health}`, `{value}`, `{name}`, `{key}`, `{payment_msg}`, `{target_name}`.

Formula fields (like `amount`, `attack`, `health`) accept tier-scaling strings like `'3 * tier'` that resolve at runtime.

### Adding a New on_select Handler

**Simple effect (declarative)** - add to `EFFECT_REGISTRY` in `effect_actions.py`:
```python
'my_handler': [
    {'type': 'grant_gold', 'amount': '3 * tier'},
    {'type': 'set_state', 'key': 'my_flag', 'value': True},
    {'type': 'message', 'text': 'Something happened!'},
]
```

**Complex logic** - add a function and register in `CUSTOM_HANDLERS`:
```python
def _handle_my_complex(ctx):
    import random
    if random.random() < 0.5:
        ctx['resources']['gold'] += 10
        ctx['run'].set_resources(ctx['resources'])
        ctx['results'].append('Lucky! Gained 10 gold!')
    else:
        ctx['results'].append('Unlucky! Nothing happened.')

CUSTOM_HANDLERS['my_complex'] = _handle_my_complex
```

That's it. No need to touch `selection_system.py` or any other file - the dispatch happens automatically.

### Existing Handlers

**Declarative (41 handlers):** `increment_bells_rung`, `grant_gold_5x_tier`, `collapsed_mine_fast`, `collapsed_mine_fastest`, `collapsed_mine_slow`, `modify_gold_30`, `buff_all_per_tier`, `buff_all_minions_3_3`, `buff_beasts_attack`, `buff_all_beasts_1_1`, `sneak_debuff_next_combat`, `tower_control_effect`, `unlock_next_special_options`, `enable_pack_discount`, `set_double_gold_bounty`, `activate_boss_bounty`, `clear_boss_bounty`, `set_bounty_mark`, `watchtower_storm_effect`, `gain_step`, `gain_step_1`, `ivory_tower_sacrifice_minion`, `ivory_tower_take_damage`, `ivory_tower_lose_steps`, `ivory_tower_decrease_seal`, `grand_city_portal`, `grand_city_make_golden`, `scrap_heap_suffer_waste`, `scrap_heap_blind_luck`, and boss reward handlers.

**Custom (12 handlers):** `grant_gold_3x_tier_maybe_combat` (random combat trigger), `grand_city_upgrade_hero`, `scrap_heap_brave_smog`, `scrap_heap_suffer_through`, `ivory_tower_gain_slot`, `start_boss_hunt`, `clear_active_boss`, `store_feed_sacrifice`, `apply_feed_to_beast`, `recruit_random_beast_tier_plus_1`, `red_gate_abandon_death`, `great_work_lichdom`.


## Event Categories

### Basic Gameplay Events
Single-screen events used as building blocks in ring configurations.

| ID | Type | Description |
|----|------|-------------|
| `minion_event` | select_minion | Choose from 3 minions |
| `buff_event` | select_buff_type | Choose a blessing |
| `combat_event` | combat | Normal difficulty combat |
| `combat_event_hard` | combat | Hard difficulty combat |
| `shop_event` | shop | Buy minions with gold |
| `statue` | statue | Combine minions into golden versions |
| `zone_portal` | story | Zone transition |

### General Event Pool
Random events that appear at `general_event` positions on rings. Defined in `GENERAL_EVENT_POOL`:

```python
GENERAL_EVENT_POOL = [
    'collapsed_mine',
    'mercenary_camp',
    'vast_kennels',
    'watchtower'
]
```

### Zone Events
Events unique to specific zones:

| Zone | Event | Description |
|------|-------|-------------|
| Fey | `ivory_tower` | Sacrifice to weaken seal, unlock extra band slot |
| Construct | `grand_city` | Powerful options with Scrap Curse side-effect |
| Construct | `scrap_heap` | Forced event to deal with Scrap Curse |
| Cult | `the_red_gate` | Strip a minion of everything to gain Ethereal [Last] |
| Undead | `the_great_work` | Ad Nauseam mechanic with escalating HP costs, Lichdom |
| Beast Wildlands | `the_great_hunt` | Bounty board with boss hunts |

### Story Events
Multi-screen narrative events:

| ID | Description |
|----|-------------|
| `bell_tower` | Ring bells for blessings, unlock Quasimodo after 4 rings |
| `ancient_shrine` | Choose prayer for buff or minion |
| `mysterious_merchant` | Story intro into shop |
| `guardian_trial` | Boss fight with reward choice |
| `cursed_fountain` | Risk/reward: take damage for ultimate buff |


## Registries

Events must be registered in two places:

### 1. `events.py` - Bottom section registries

```python
# Add to the appropriate category dict
CROSSROADS_EVENTS = {
    'my_event': MY_EVENT,
    ...
}

# If it has sub-events
CROSSROADS_SUB_EVENTS = {
    'my_event_sub': MY_EVENT_SUB,
    ...
}

# All events are merged into ALL_CUSTOM_EVENTS
ALL_CUSTOM_EVENTS = {
    **CROSSROADS_EVENTS,
    **CROSSROADS_SUB_EVENTS,
    ...
}
```

### 2. `event_registry.py` - Metadata catalog

```python
CROSSROADS_EVENTS = {
    'my_event': {
        'event': MY_EVENT,
        'category': 'crossroads',
        'description': 'What it does',
        'flow': 'choice -> (option A OR option B)',
        'screens': 1,
        'modular': True,
        'sub_events': ['my_event_sub'],
        'conditions': {
            'special_option': 'condition_string'
        }
    },
}
```


---

# How to Add a New Event

## Step-by-Step: Adding a General Event

This walkthrough adds a hypothetical "Dragon's Hoard" event.

### 1. Define the event in `events.py`

```python
# -------------------- DRAGON'S HOARD --------------------

DRAGONS_HOARD = {
    'id': 'dragons_hoard',
    'visit_rule': 'repeatable',
    'title': "Dragon's Hoard",
    'description': 'A sleeping dragon guards a mountain of gold',
    'screens': [
        {
            'id': 'choice',
            'type': 'make_choice',
            'parameters': {
                'title': "Dragon's Hoard",
                'message': 'A dragon sleeps atop a mountain of gold. What do you do?',
                'choices': [
                    {
                        'name': 'Steal Gold',
                        'description': 'Quietly take some gold',
                        'tooltip': 'Gain ({gold_reward}) gold.',
                        'icon': generate_lucide_svg('coins', width=24, height=24),
                        'gold_reward': 'tier * 5',
                        'on_select': 'dragons_hoard_steal',
                        'next_event': None
                    },
                    {
                        'name': 'Fight the Dragon',
                        'description': 'Wake the beast and fight',
                        'tooltip': 'Fight a hard combat. Win: all minions gain +{tier * 2}/+{tier * 2}.',
                        'icon': generate_lucide_svg('swords', width=24, height=24),
                        'next_event': 'dragons_hoard_combat'
                    },
                    {
                        'name': 'Leave',
                        'description': 'Best not to disturb it',
                        'tooltip': 'Leave without doing anything.',
                        'icon': generate_lucide_svg('footprints', width=24, height=24),
                        'next_event': None
                    },
                    {
                        'name': 'Tame the Dragon',
                        'description': 'Only a true Beast master can attempt this',
                        'tooltip': 'Requires 4+ Beasts. Gain a Dragon minion for free.',
                        'icon': generate_lucide_svg('heart-handshake', width=24, height=24),
                        'condition': 'beast_count >= 4',
                        'disabled_until_met': True,
                        'on_select': 'dragons_hoard_tame',
                        'next_event': None
                    }
                ]
            }
        }
    ]
}

# Sub-event: combat encounter
DRAGONS_HOARD_COMBAT = {
    'id': 'dragons_hoard_combat',
    'visit_rule': 'repeatable',
    'title': 'Dragon Fight',
    'screens': [
        {
            'id': 'combat',
            'type': 'combat',
            'parameters': {
                'difficulty': 'hard',
                'title': 'Dragon Fight',
                'disable_gold_reward': True
            },
            'on_victory_event': None,  # Could chain to reward event
            'on_defeat': None
        }
    ]
}
```

### 2. Register in event registries (`events.py` bottom)

Add to the appropriate category dict:

```python
CROSSROADS_EVENTS = {
    # ... existing events
    'dragons_hoard': DRAGONS_HOARD,
}

CROSSROADS_SUB_EVENTS = {
    # ... existing sub-events
    'dragons_hoard_combat': DRAGONS_HOARD_COMBAT,
}
```

This automatically includes them in `ALL_CUSTOM_EVENTS` via the spread at the bottom of the file.

### 3. Add to the general event pool (if it should appear randomly)

```python
GENERAL_EVENT_POOL = [
    'collapsed_mine',
    'mercenary_camp',
    'vast_kennels',
    'watchtower',
    'dragons_hoard',     # <-- add here
]
```

### 4. Add the `on_select` handler in `effect_actions.py`

Add entries to `EFFECT_REGISTRY` for simple effects, or `CUSTOM_HANDLERS` for complex logic:

```python
# Simple handler - just data, no code needed
EFFECT_REGISTRY['dragons_hoard_steal'] = [
    {'type': 'grant_gold', 'amount': '5 * tier'},
]

# Complex handler - needs custom logic (recruiting a minion)
def _handle_dragons_hoard_tame(ctx):
    from minions import get_minion_by_name, create_minion_instance
    dragon = get_minion_by_name('Dragon')
    if dragon:
        instance = create_minion_instance(dragon, ctx['tier'])
        ctx['band'].append(instance)
        ctx['run'].set_band(ctx['band'])
        ctx['results'].append(f'{instance["name"]} joins your band!')

CUSTOM_HANDLERS['dragons_hoard_tame'] = _handle_dragons_hoard_tame
```

No changes needed in `selection_system.py` - dispatch is automatic.

### 5. Register metadata in `event_registry.py`

```python
from game_engine.events.events import DRAGONS_HOARD, DRAGONS_HOARD_COMBAT

CROSSROADS_EVENTS = {
    # ... existing entries
    'dragons_hoard': {
        'event': DRAGONS_HOARD,
        'category': 'crossroads',
        'description': 'Risk/reward encounter with a sleeping dragon',
        'flow': 'choice -> (steal gold OR fight OR tame if 4+ Beasts)',
        'screens': 1,
        'modular': True,
        'sub_events': ['dragons_hoard_combat'],
        'conditions': {
            'tame': 'beast_count >= 4'
        }
    },
}

CROSSROADS_SUB_EVENTS = {
    # ... existing entries
    'dragons_hoard_combat': {
        'event': DRAGONS_HOARD_COMBAT,
        'parent_event': 'dragons_hoard',
        'description': 'Hard combat against the dragon',
        'screens': 1,
        'difficulty': 'hard'
    },
}
```

### 6. Write tests in `tests/test_event_pipeline.py`

```python
def test_dragons_hoard_full():
    """Dragon's Hoard: all tiers, all options"""
    for tier in range(1, 6):
        options, sel, run = create_event_and_get_options('dragons_hoard', tier=tier)

        # Should have 4 options
        assert len(options) == 4

        # Check tooltips resolve cleanly
        assert_no_unresolved(options, 'dragons_hoard', tier)

        # Steal Gold should show correct gold amount
        steal = next(o for o in options if o['message'] == 'Steal Gold')
        assert str(tier * 5) in steal['tooltip']

        # Tame should be disabled (default band has no 4 Beasts)
        tame = next(o for o in options if o['message'] == 'Tame the Dragon')
        assert tame.get('disabled') is True
```

### 7. Test with Dev Events panel

1. Start the server: `python app.py`
2. Open `http://127.0.0.1:5000/dev-events.html`
3. Find "dragons_hoard" in the event list on the left
4. Set a ring level and click "Trigger Event"
5. Test each choice path and verify tooltips, gold costs, and chaining

### Summary Checklist

| Step | File | What |
|------|------|------|
| 1 | `game_engine/events/events.py` | Define event dict + sub-event dicts |
| 2 | `game_engine/events/events.py` | Register in category dict (bottom of file) |
| 3 | `game_engine/events/events.py` | Add to `GENERAL_EVENT_POOL` if random |
| 4 | `game_engine/events/effect_actions.py` | Add `on_select` handlers (declarative or custom) |
| 5 | `event_registry.py` | Add metadata entry + import |
| 6 | `tests/test_effect_actions.py` | Write handler tests |
| 7 | Dev panel | Manual testing at `dev-events.html` |

If you need a new **condition**, also add a handler in `event_helpers.py` (see Conditions section above).

If you need a new **screen type** (not just a new event using existing screens), add it to `event_templates.py` and implement its executor in `event_system.py`.

If you need a new **action type** (not just a new handler), add an executor function and register it in `ACTION_EXECUTORS` in `effect_actions.py`.


## Dev Events Panel

The dev events panel (`dev-events.html`) lets you test any event locally without running a real game.

**Access:** `http://127.0.0.1:5000/dev-events.html` (localhost only)

**API base:** `/api/dev-events`

### Key Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/events/list` | GET | List all events by category |
| `/events/create` | POST | Create a test event session |
| `/events/<id>/select` | POST | Submit a choice |
| `/events/<id>/state` | GET | Get current session state |
| `/events/<id>/update-run` | POST | Change ring/zone/gold/health mid-test |
| `/events/ring-preview` | GET | See all events at a ring level |
| `/events/scaling-preview` | GET | See how an event scales across rings |

### How Dev Sessions Work

1. **Create:** POST to `/events/create` with `event_type` and optional `run_config` (ring, zone, band, gold, health)
2. **View:** The panel renders the event using the same code as the real game
3. **Interact:** Click choices, the panel POSTs to `/events/<session_id>/select`
4. **Chain:** If the choice triggers a `next_event`, the panel automatically loads the next event
5. **Repeat:** Same session preserves run state (gold, band, event_state) across chains

Sessions are in-memory only, nothing is persisted to the database.
