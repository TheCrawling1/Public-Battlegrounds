# Tooltip and Keyword System Documentation

This document details how the frontend tooltip and keyword systems work in the Battleground game.

## Overview

The game uses a recursive tooltip system that allows nested, interactive tooltips with automatic keyword and minion name linking. Keywords are defined in a central registry and displayed as colored effect tags on minion cards.

## File Locations

The frontend display code, formerly one large `ui-display-desktop.js`, now lives in the
`Battlegrounds/js/ui/` module set.

- **Tooltip System**: `Battlegrounds/js/ui/display-tooltips.js` (TooltipPortal IIFE, lines 4-678)
- **Keyword Definitions**: `Battlegrounds/js/constants.js` and `Battlegrounds/js/game-core.js`
- **Effect Registry**: `Battlegrounds/js/ui/display-effects.js` (lines 680-722)
- **Effect Tag Generation**: `Battlegrounds/js/ui/display-effects.js` (`generateAllEffectTags`, line 796)

---

## Keyword System

### KEYWORDS Object Structure

Keywords are defined in both `constants.js` and `game-core.js` with the following structure:

```javascript
const KEYWORDS = {
    keyword_key: {
        name: 'Display Name',           // Human-readable name
        description: 'What it does',    // Tooltip description
        icon: generateLucideSVG(...),   // SVG icon or emoji fallback
        color: '#HEXCOLOR'              // Theme color for display
    },
    // ... more keywords
};
```

### Keyword Categories

1. **Trigger Keywords** (have associated effect fields):
   - `assault` - Triggers on attack
   - `death_toll` - Triggers on death
   - `cast` - Replaces normal attack with spell
   - `rage` - Triggers when another minion attacks
   - `calm` - Triggers when any minion casts
   - `on_any_death` - Triggers when any minion dies
   - `on_any_summon` - Triggers when any minion is summoned
   - `on_any_cast` - Triggers when any spell is cast
   - `on_any_leap` - Triggers when any minion leaps
   - `on_any_death_toll` - Triggers when any death toll fires
   - `on_damage` - Triggers when this minion takes damage
   - `start_of_combat` - Triggers at combat start
   - `aura` - Passive buff to adjacent allies

2. **Passive Keywords** (no effect field, just modify behavior):
   - `poke` - No counter-attack damage when attacking
   - `guard` - Must be killed before other minions
   - `cant_attack` - Cannot attack normally
   - `cant_retaliate` - No counter damage when attacked
   - `multi_attack` - Attacks multiple times
   - `hide` - Cannot be targeted for X attacks
   - `leap` - Moves right when attacking
   - `nobility` - Immune to spell/ability damage
   - `savage` - Always targets lowest health enemy
   - `fast` - Attacks at start of combat
   - `cleave` - Hits adjacent enemies
   - And more...

### Dynamic Scope Detection

For `on_any_*` keywords, the system dynamically adjusts the display name based on effect conditions:

- `On Any Death` + `is_ally` condition → `On Ally Death`
- `On Any Death` + `is_enemy` condition → `On Enemy Death`
- `On Any Summon` + `is_ally` condition → `On Ally Summon`

This is handled by `detectEffectScope()` and `getAdjustedDisplayName()` in `js/ui/display-effects.js` (lines 726-795).

---

## Effect Registry (EFFECT_REGISTRY)

The `EFFECT_REGISTRY` array maps minion effect fields to display properties:

```javascript
const EFFECT_REGISTRY = [
    // Effects with associated data fields
    { field: 'assault_effect', keyword: 'assault', name: 'Assault', icon: '⚡', color: '#FF5722' },
    { field: 'death_toll_effect', keyword: 'death_toll', name: 'Death Toll', icon: '💀', color: '#9C27B0' },
    { field: 'cast_effect', keyword: 'cast', name: 'Cast', icon: '🔮', color: '#E91E63' },
    // ...

    // Passive keywords (no field, just keyword)
    { keyword: 'poke', name: 'Poke', icon: '🏹', color: '#4CAF50' },
    { keyword: 'guard', name: 'Guard', icon: '🛡️', color: '#2196F3' },
    // ...
];
```

### Effect Tag Generation

`generateAllEffectTags(minion)` iterates through `EFFECT_REGISTRY` and generates HTML tags for each effect/keyword the minion has:

1. Checks if minion has the effect field OR the keyword
2. Formats the effect description using `formatMinionSpecificEffect()`
3. Creates a colored tag with tooltip containing the description
4. Keywords in descriptions are recursively enriched for sub-tooltips

---

## TooltipPortal System

The `TooltipPortal` is an IIFE (Immediately Invoked Function Expression) that manages recursive, interactive tooltips.

### Key Constants

```javascript
const LOCK_DELAY = 3000;    // 3 seconds to auto-lock tooltip
const CLOSE_DELAY = 500;    // 0.5 seconds after mouse leaves to close
const MAX_DEPTH = 5;        // Maximum nesting depth
const BASE_Z_INDEX = 100000; // Starting z-index for tooltips
```

### Core Components

#### 1. Data Structures

```javascript
const tooltips = new Map();      // id -> TooltipNode
const rootTooltips = new Set();  // Top-level tooltips
let MINION_DATA = {};            // Loaded from API for minion sub-tooltips
```

#### 2. TooltipNode Structure

```javascript
{
    id: string,              // Unique identifier
    element: HTMLElement,    // The portal DOM element
    parent: TooltipNode,     // Parent tooltip (null for root)
    children: Set,           // Child tooltips
    level: number,           // Nesting depth
    triggerElement: Element, // The element that triggered this tooltip
    lockTimer: number,       // Timer for auto-lock
    closeTimer: number,      // Timer for auto-close
    unlockTimer: number,     // Timer for unlock transition
    isLocked: boolean        // Whether tooltip is locked open
}
```

### How Tooltips Work

#### Trigger Structure

Tooltips are triggered by elements with class `tooltip` containing a hidden `.tooltiptext` span:

```html
<span class="tooltip">
    Hover Text
    <span class="tooltiptext" style="display: none;">
        Tooltip content here
    </span>
</span>
```

#### Enrichment Process

When a tooltip is shown, `enrichTooltipContent()` processes the content:

1. **Minion Name Linking**: Scans for minion names in `MINION_DATA` and wraps them in sub-tooltip triggers that show the full minion card
2. **Keyword Linking**: Scans for keyword names from `KEYWORDS` and wraps them in sub-tooltip triggers with the keyword description
3. **Recursion Prevention**: Tracks visited terms to prevent circular references
4. **HTML Safety**: Uses regex to avoid matching inside HTML tags or existing tooltips

#### Positioning Logic

`calculatePosition()` handles tooltip placement:

- **Root level (level 0)**: Below trigger by default, above if no room
- **Nested levels**: To the right of parent, to the left if no room
- Respects viewport boundaries
- Uses `data-tooltip-position="top"` attribute for explicit positioning

#### Locking Behavior

1. **Auto-lock**: After `LOCK_DELAY` (3s), tooltip locks and gets golden border
2. **Hover-lock**: Immediately locks when user hovers over tooltip
3. **Locked State**: Tooltip stays open, allowing interaction with nested tooltips
4. **Unlock**: On mouse leave, removes lock and starts close timer

### Visual States (CSS Classes)

- `.tooltip-locking` - Transitioning to locked state (golden border fading in)
- `.tooltip-locked` - Fully locked (solid golden border)
- `.portal-tooltip` - The portal container element
- `.tooltip-level-{n}` - Indicates nesting depth
- `.minion-card-tooltip` - Special styling for minion card sub-tooltips

### Event Handling

Global event delegation on `document`:

```javascript
document.addEventListener('mouseover', function(e) {
    const tooltip = e.target.closest('.tooltip');
    // ... show tooltip logic
});

document.addEventListener('mouseout', function(e) {
    // ... close tooltip logic
});

window.addEventListener('scroll', () => {
    cleanup(); // Close all tooltips on scroll
}, { passive: true });
```

### Public API

```javascript
TooltipPortal = {
    cleanup: function(),           // Close all tooltips
    getMinionData: function()      // Returns loaded minion data
};
```

---

## Minion Data Loading

The tooltip system loads minion data from the API for sub-tooltips:

```javascript
async function loadMinionData() {
    const response = await fetch('/api/dev/minion-info');
    const data = await response.json();
    if (data.success) {
        MINION_DATA = data.minions;
    }
}
```

Note: `/api/dev/minion-info` is a developer-only endpoint (mounted only when
`ENABLE_DEV_ROUTES=true`). The fetch is wrapped in try/catch, so minion sub-tooltips
degrade gracefully when the data is unavailable.

This enables tooltips to show full minion cards when hovering over minion names in descriptions.

---

## Effect Description Formatting

`formatMinionSpecificEffect(effectData, isGolden, depth)` converts effect data to human-readable text:

### Supported Effect Types

- `deal_damage` - "Deal X damage to target"
- `buff_stats` - "Give target +X/+Y"
- `grant_keyword` - "Give target Keyword"
- `summon_minion` - "Summon X A/H MinionName"
- `conditional` - "If condition: then_effect"
- `apply_stun` - "Stun target for X turns"
- `heal` - "Heal X health"
- `transform` - "Transform into MinionName"
- And many more...

### Condition Formatting

`formatCondition(condition)` handles condition display:

- `has_keyword` - "target has KeywordName"
- `has_type` - "target is TypeName"
- `is_ally` / `is_enemy` / `is_self` - Filtered from display (used for scope detection)
- `compound` - Multiple conditions joined with "and" / "or"

---

## Integration Points

### With Minion Cards

The `generateUnifiedMinionCard()` function calls `generateAllEffectTags()` to create the effect tag section of minion cards.

### With Collection

Collection page generates minion cards that include effect tags with tooltips.

### With Combat

Combat display uses the same card rendering, enriching tooltips with minion and keyword links.

### With Events

Event option tooltips are enriched to link keywords and minion names.

---

## Adding New Keywords

1. Add to `KEYWORDS` in both `constants.js` and `game-core.js`:
   ```javascript
   new_keyword: {
       name: 'New Keyword',
       description: 'What it does',
       icon: generateLucideSVG('icon-name', 24, 24),
       color: '#COLOR'
   }
   ```

2. If it has an effect field, add to `EFFECT_REGISTRY`:
   ```javascript
   { field: 'new_keyword_effect', keyword: 'new_keyword', name: 'New Keyword', icon: '🆕', color: '#COLOR' }
   ```

3. If it's passive only, add just the keyword entry:
   ```javascript
   { keyword: 'new_keyword', name: 'New Keyword', icon: '🆕', color: '#COLOR' }
   ```

---

## Debugging Tips

1. **Console Logging**: The system logs enrichment activity:
   - "Loaded X minions for tooltips"
   - "Enriching tooltip with minion data"
   - "Enriched minion: MinionName"

2. **Special Debug Cases**: Skeleton and Bone minions have extra logging for effect tag generation.

3. **Inspect Tooltips**: Portal tooltips are appended to `document.body` with class `.portal-tooltip`.

4. **Check MINION_DATA**: `TooltipPortal.getMinionData()` returns the loaded minion data.
