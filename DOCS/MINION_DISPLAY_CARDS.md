# Minion Display Cards - Technical Documentation

This document describes how minion cards are rendered, styled, and interact with tooltips in the frontend.

---

## Overview

Minion cards are rendered client-side using a unified rendering system. The backend provides minion data via API, which is enriched with template data and rendered to HTML with dynamic styling.

The rendering code lives in the `js/ui/` module set (`display-minion.js`, `display-effects.js`, `display-tooltips.js`, `display-selection.js`), which together replaced the former monolithic `ui-display-desktop.js`.

**Data Flow:**
```
Backend API (/api/dev/minion-info)
    ↓
MINION_DATA cache (loaded on init)
    ↓
enrichCombatMinion() merges combat state + template
    ↓
generateUnifiedMinionCard() renders HTML
    ↓
generateAllEffectTags() adds keyword tags
    ↓
TooltipPortal handles hover interactions
```

---

## Card Structure

```
┌─────────────────────────────┐
│ [Name]             [Tier]   │  ← top row (name left, tier right)
│ [Keyword Tag]               │  ← stacked left, chevron shape
│ [Keyword Tag]               │
│                             │
│      (background image)     │
│                             │
│ [⚔️ ATK]          [Tribe]   │  ← bottom corners
│ [❤️ HP ]                    │
└─────────────────────────────┘
```

---

## 1. Core Rendering

### generateUnifiedMinionCard()

**File:** `js/ui/display-minion.js:89-200`

The main function that renders all minion cards throughout the game (band, combat, events, tooltips).

```javascript
function generateUnifiedMinionCard(minion, options = {}) {
    const {
        index = 0,
        showIndex = true,
        isClickable = false,
        isSelected = false,
        isDisabled = false,
        showAbandonButton = false,
        clickHandler = '',
        extraClasses = '',
        indicators = []
    } = options;

    // Build card HTML with:
    // - Background image from minion.image
    // - Dynamic CSS classes (golden, selected, disabled)
    // - Name with dynamic font size
    // - Tier in Roman numerals
    // - Effect tags via generateAllEffectTags()
    // - Stats box with attack/health
    // - Tribe display
    // - Optional indicators

    return `<div class="${cardClasses}" ...>...</div>`;
}
```

**Options:**
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `index` | number | 0 | Position index for display |
| `showIndex` | boolean | true | Show "#1" etc. after name |
| `isClickable` | boolean | false | Enable click handler |
| `isSelected` | boolean | false | Add selected styling |
| `isDisabled` | boolean | false | Add disabled styling |
| `showAbandonButton` | boolean | false | Show X instead of tier |
| `clickHandler` | string | '' | onclick attribute |
| `extraClasses` | string | '' | Additional CSS classes |
| `indicators` | array | [] | Badge indicators to show |
| `dataAttributes` | object | {} | Custom data-* attributes (e.g. `{'minion-id': '123'}`) |

### Legacy Wrapper

**File:** `js/ui/display-minion.js:203`

```javascript
function generateMinionCard(minion, index, hasSelection, cardType = 'band') {
    const enrichedMinion = enrichCombatMinion(minion);
    const options = { /* ... */ };
    return generateUnifiedMinionCard(enrichedMinion, options);
}
```

### Collection Cards

**File:** `js/collection.js:384`

Collection uses the unified card with collection-specific options. The function is
named `generateCollectionMinionCard` to avoid colliding with the game's
`generateMinionCard`:

```javascript
function generateCollectionMinionCard(minion) {
    const enrichedMinion = typeof enrichCombatMinion === 'function'
        ? enrichCombatMinion(minion)
        : minion;
    return generateUnifiedMinionCard(enrichedMinion, {
        showIndex: false,
        isClickable: true,
        showAbandonButton: false,
        clickHandler: `onclick="showMinionDetails('${minion.id}')"`,
        dataAttributes: { 'minion-id': minion.id || '' }
    });
}
```

Collection cards differ from band cards:
- No index display ("#1", "#2", etc.)
- No selection/disabled states
- No abandon button
- Custom click handler opens detail view
- Uses `data-minion-id` instead of `data-minion-index`

---

## 2. Keywords & Effects

### EFFECT_REGISTRY

**File:** `js/ui/display-effects.js:680-722`

Maps effect fields and keywords to display properties:

```javascript
const EFFECT_REGISTRY = [
    // Keywords with effect fields (trigger-based)
    { field: 'assault_effect', keyword: 'assault', name: 'Assault', icon: '⚡', color: '#FF5722' },
    { field: 'death_toll_effect', keyword: 'death_toll', name: 'Death Toll', icon: '💀', color: '#9C27B0' },
    { field: 'cast_effect', keyword: 'cast', name: 'Cast', icon: '🔮', color: '#E91E63' },
    { field: 'rage_effect', keyword: 'rage', name: 'Rage', icon: '😡', color: '#D32F2F' },
    // ... more effect fields

    // Keywords without effect fields (passive abilities)
    { keyword: 'poke', name: 'Poke', icon: '🏹', color: '#4CAF50' },
    { keyword: 'guard', name: 'Guard', icon: '🛡️', color: '#2196F3' },
    // ... more keywords
];
```

### generateAllEffectTags()

**File:** `js/ui/display-effects.js:796-997`

Generates HTML for all keyword tags on a minion card:

```javascript
function generateAllEffectTags(minion) {
    const isGolden = minion.golden || false;
    const effectTags = [];
    const keywords = minion.keywords || [];

    EFFECT_REGISTRY.forEach(entry => {
        // Check if minion has this effect field or keyword
        // Format description via formatMinionSpecificEffect()
        // Handle special cases (stun count, hide count, multi-attack, etc.)
        // Push to effectTags array
    });

    // Render as chevron-shaped HTML tags
    return effectTags.map(effect => `
        <div class="effect-tag tooltip" style="background: linear-gradient(...)">
            ${effect.name}
            <span class="tooltiptext">${tooltip}</span>
        </div>
    `).join('');
}
```

**Special Cases Handled:**
- `rich` / `fast` - wrap `start_of_combat_effect`, skip showing both
- `multi_attack` - shows count (e.g., "Multi Attack 2")
- `stun` - shows remaining count
- `hide` - shows remaining count (doubled if golden)
- `ring` - shows trigger count
- `leap` - shows distance
- `cleave` - shows amount

### formatMinionSpecificEffect()

**File:** `js/ui/display-effects.js:3`

Converts effect data objects into readable text:

```javascript
function formatMinionSpecificEffect(effectData, isGolden = false, depth = 0) {
    const multiplier = isGolden ? 2 : 1;
    const amount = (effectData.amount || 0) * multiplier;

    switch (effectData.type) {
        case 'deal_damage':
            return `Deal ${amount} damage to ${target}`;
        case 'buff_stats':
            return `Gain +${attack}/+${health}`;
        case 'summon_minion':
            return `Summon ${count} minion(s)`;
        // ... 30+ effect types
    }
}
```

### KEYWORDS Constant

**File:** `js/constants.js:5`

Defines all keywords with name, description, icon, and color:

```javascript
const KEYWORDS = {
    poke: {
        name: 'Poke',
        description: 'Does not take counter-attack damage when attacking',
        icon: generateLucideSVG('crosshair', 24, 24),
        color: '#4CAF50'
    },
    guard: {
        name: 'Guard',
        description: 'Other minions cannot be attacked until this minion is killed',
        icon: generateLucideSVG('shield', 24, 24),
        color: '#2196F3'
    },
    // ... 60+ keywords and tooltip terms
};
```

---

## 3. Tooltip System

### TooltipPortal

**File:** `js/ui/display-tooltips.js:4-678`

IIFE that manages recursive tooltips with locking behavior:

```javascript
const TooltipPortal = (function() {
    const tooltips = new Map();      // id -> TooltipNode
    const rootTooltips = new Set();  // Top-level tooltips
    let MINION_DATA = {};            // Loaded from API

    const LOCK_DELAY = 3000;   // 3 seconds to lock
    const CLOSE_DELAY = 500;   // 0.5 seconds after leaving
    const MAX_DEPTH = 5;       // Maximum nesting depth
    const BASE_Z_INDEX = 100000;

    // Public methods exposed via return object
    return {
        cleanup,        // Close all tooltips
        getMinionData   // Returns loaded minion data
    };
})();
```

**Tooltip Node Structure:**
```javascript
{
    id: string,
    element: HTMLElement,
    parent: TooltipNode | null,
    children: Set<TooltipNode>,
    level: number,
    triggerElement: HTMLElement,
    lockTimer: number,
    closeTimer: number,
    isLocked: boolean
}
```

### showTooltip()

**File:** `js/ui/display-tooltips.js:386`

Creates and positions a tooltip:

1. Check max depth (5 levels)
2. Get `.tooltiptext` content from trigger
3. Create portal element with unique ID
4. Enrich content with sub-tooltips (minion names become clickable)
5. Calculate position via `calculatePosition()`
6. Append to document.body
7. Start lock timer (3 seconds)
8. Set up hover handlers for locking/closing

### calculatePosition()

**File:** `js/ui/display-tooltips.js:247`

Viewport-aware positioning:

```javascript
function calculatePosition(triggerRect, parentNode, level, triggerElement) {
    // Root level (level 0): below trigger, or above if no room
    // Nested levels: right of parent, or left if no room
    // Always keeps within viewport bounds
    return { x, y, placement };
}
```

**Positioning Logic:**
- Level 0: Below trigger (preferred) or above
- Level 1+: Right of parent (preferred) or left
- Respects viewport margins

### generateMinionCardForTooltip()

**File:** `js/ui/display-tooltips.js:43`

Renders minion card specifically for tooltip display:

```javascript
function generateMinionCardForTooltip(minion) {
    const enriched = enrichCombatMinion(minion);
    return generateUnifiedMinionCard(enriched, {
        index: 0,
        showIndex: false,
        isClickable: false,
        extraClasses: 'tooltip-minion-card'
    });
}
```

---

## 4. Data Enrichment

### enrichCombatMinion()

**File:** `js/ui/display-selection.js:559`

Merges combat state with template data:

```javascript
function enrichCombatMinion(minion) {
    const template = getMinionTemplate(minion.name);

    // If minion already has effect fields, just fill missing display data
    if (minion.cast_effect || minion.assault_effect || minion.death_toll_effect) {
        // Fill tier, type from template if missing
        return minion;
    }

    if (template) {
        // Merge: start with template, overlay combat state
        const enriched = { ...template };
        for (const key in minion) {
            if (minion[key] !== undefined) {
                enriched[key] = minion[key];
            }
        }
        return enriched;
    }

    return minion;
}
```

### getMinionTemplate()

**File:** `js/ui/display-selection.js:549`

```javascript
function getMinionTemplate(minionName) {
    const minionData = TooltipPortal.getMinionData();
    return minionData?.[minionName] || null;
}
```

### loadMinionData()

**File:** `js/ui/display-tooltips.js:16`

Fetches minion templates from backend on init:

```javascript
async function loadMinionData() {
    const response = await fetch('/api/dev/minion-info');
    const data = await response.json();
    if (data.success) {
        MINION_DATA = data.minions;
    }
}
```

---

## 5. Dynamic Font Sizing

**File:** `js/ui/display-minion.js:31-88`

Functions that calculate font sizes based on content length:

### getStatFontSize()
```javascript
function getStatFontSize(attack, health) {
    const digits = Math.max(attack, health).toString().length;
    if (digits <= 2) return '0.85rem';
    if (digits === 3) return '0.75rem';
    return '0.65rem';
}
```

### getMinionNameFontSize()
```javascript
function getMinionNameFontSize(name) {
    const len = name.length;
    if (len <= 10) return '0.7rem';
    if (len <= 14) return '0.6rem';
    if (len <= 18) return '0.5rem';
    return '0.45rem';
}
```

### getTribeFontSize()
```javascript
function getTribeFontSize(tribeName) {
    const len = tribeName.length;
    if (len <= 4) return '0.7rem';
    if (len <= 6) return '0.6rem';
    if (len <= 8) return '0.5rem';
    return '0.45rem';
}
```

### getKeywordFontSize()
```javascript
function getKeywordFontSize(keyword) {
    const len = keyword.length;
    if (len <= 5) return '0.6rem';
    if (len <= 8) return '0.55rem';
    if (len <= 12) return '0.45rem';
    return '0.38rem';
}
```

---

## 6. CSS Styling

**File:** `desktop.css`

### Minion Card Base
**Line 1487+**

```css
.minion-card {
    border-radius: 5px;
    position: relative;
    aspect-ratio: 1 / 1;
    width: 100%;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    border: 2px solid var(--brass-mid);
    background: linear-gradient(180deg, #151210 0%, #0d0b08 100%);
    box-shadow: 0 4px 12px rgba(0,0,0,0.5);
    transition: all 0.3s ease;
    cursor: pointer;
}

.minion-card:hover {
    transform: translateY(-5px) scale(1.02);
    box-shadow: 0 8px 20px rgba(0,0,0,0.6);
    border-color: var(--brass-light);
}

.minion-card.golden {
    border-color: var(--gold-glow);
    box-shadow: 0 0 15px rgba(255, 215, 0, 0.4);
}

.minion-card.selected {
    border-color: #6090c0;
    box-shadow: 0 0 20px rgba(79, 172, 254, 0.6);
}
```

### Minion Name
**Line 1607+**

```css
.minion-name {
    position: absolute;
    top: 0;
    left: 0;
    font-family: 'Cinzel', serif;
    font-weight: 700;
    color: var(--parchment);
    text-transform: uppercase;
    z-index: 12;
    max-width: 65%;
    background: rgba(13, 11, 8, 0.95);
    border: 1px solid var(--brass-mid);
    border-top: none;
    border-left: none;
    border-radius: 0 0 4px 0;
    padding: 3px 8px;
}
```

### Effect Tags (Keywords)
**Lines 1652-1687** (`.minion-tags` and `.effect-tag`)

```css
.minion-tags {
    position: absolute;
    top: 20px;
    left: 0;
    max-width: 60%;
    display: flex;
    flex-direction: column;
    gap: 2px;
    z-index: 3;
}

.effect-tag {
    padding: 3px 12px 3px 6px;
    font-family: 'Cinzel', serif;
    font-size: 0.6rem;
    font-weight: 700;
    text-transform: uppercase;
    color: white;
    clip-path: polygon(0 0, calc(100% - 8px) 0, 100% 50%, calc(100% - 8px) 100%, 0 100%);
    cursor: help;
}
```

### Stats Box
**Line 1689+**

```css
.minion-stats-box {
    position: absolute;
    bottom: 0;
    left: 0;
    z-index: 12;
    background: linear-gradient(180deg, #0d0b08 0%, #080604 100%);
    border-top: 1px solid var(--brass-mid);
    border-right: 1px solid var(--brass-mid);
    border-radius: 0 4px 0 3px;
}

.stat.attack { color: var(--brass-light); }
.stat.health { color: var(--damage-red); }
```

### Tribes
**Line 1735+**

```css
.minion-tribes {
    position: absolute;
    bottom: 0;
    right: 0;
    z-index: 12;
    background: linear-gradient(180deg, #0d0b08 0%, #080604 100%);
    border-top: 1px solid var(--brass-mid);
    border-left: 1px solid var(--brass-mid);
    border-radius: 4px 0 3px 0;
}

.minion-tribe {
    color: var(--gold-glow);
    font-family: 'Cinzel', serif;
    text-transform: uppercase;
}
```

### Portal Tooltips
**Line 2836+**

```css
.portal-tooltip {
    min-width: 200px;
    max-width: 300px;
    background: linear-gradient(180deg, #1a1815 0%, #0d0b08 100%);
    color: var(--parchment);
    border: 2px solid var(--brass-mid);
    border-radius: 4px;
    padding: 10px 12px;
    font-family: 'Crimson Text', Georgia, serif;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.8);
    transition: border 0.3s, box-shadow 0.3s;
}

.portal-tooltip.tooltip-locked {
    border: 2px solid var(--brass-light);
    box-shadow: 0 0 15px rgba(201, 165, 92, 0.5);
}

.portal-tooltip.minion-card-tooltip {
    background: transparent;
    border: none;
    padding: 0;
    box-shadow: none;
    width: 180px;
}
```

---

## 7. Backend API

### /api/dev/minion-info

**File:** `dev_combat_routes.py:1113-1134` (dev-only; mounted only when `ENABLE_DEV_ROUTES=true`)

Returns full minion data for tooltip enrichment:

```python
@dev_api.route('/minion-info', methods=['GET'])
def get_minion_info():
    from minions import MINIONS
    minion_info = {}

    for tier, tier_minions in MINIONS.items():
        for minion in tier_minions:
            name = minion['name']
            minion_copy = copy.deepcopy(minion)
            minion_copy['tier'] = tier
            minion_info[name] = minion_copy

    return jsonify({
        'success': True,
        'minions': minion_info,
        'total': len(minion_info)
    })
```

**Response Structure:**
```json
{
    "success": true,
    "minions": {
        "Soldier": {
            "name": "Soldier",
            "attack": 2,
            "health": 2,
            "tier": 1,
            "type": "Human",
            "keywords": ["poke"],
            "image": "minions/soldier.png",
            "assault_effect": null,
            "death_toll_effect": null,
            "cast_effect": null
        }
    },
    "total": 95
}
```

---

## 8. Minion Data Structures

### Combat Minion (from game state)
```javascript
{
    name: "Soldier",
    attack: 2,
    health: 2,
    _combat_id: "combat_123",
    stun_remaining: 0,
    golden: false
}
```

### Template Minion (from API)
```javascript
{
    name: "Soldier",
    attack: 2,
    health: 2,
    tier: 1,
    type: "Human",
    keywords: ["poke"],
    image: "minions/soldier.png",
    assault_effect: null,
    death_toll_effect: null,
    cast_effect: null,
    start_of_combat_effect: null
}
```

### Enriched Minion (after enrichCombatMinion)
```javascript
{
    // All template fields +
    _combat_id: "combat_123",
    stun_remaining: 0,
    golden: false
    // Combat state overrides template values
}
```

---

## File Reference

| File | Line | Component |
|------|------|-----------|
| `js/ui/display-minion.js` | 89 | `generateUnifiedMinionCard()` |
| `js/ui/display-minion.js` | 203 | `generateMinionCard()` (legacy wrapper) |
| `js/ui/display-minion.js` | 31-88 | Font size functions |
| `js/ui/display-effects.js` | 680 | `EFFECT_REGISTRY` |
| `js/ui/display-effects.js` | 796 | `generateAllEffectTags()` |
| `js/ui/display-effects.js` | 3 | `formatMinionSpecificEffect()` |
| `js/ui/display-tooltips.js` | 4 | `TooltipPortal` |
| `js/ui/display-tooltips.js` | 386 | `showTooltip()` |
| `js/ui/display-tooltips.js` | 247 | `calculatePosition()` |
| `js/ui/display-tooltips.js` | 16 | `loadMinionData()` |
| `js/ui/display-selection.js` | 559 | `enrichCombatMinion()` |
| `js/ui/display-selection.js` | 549 | `getMinionTemplate()` |
| `js/constants.js` | 5 | `KEYWORDS` |
| `js/collection.js` | 384 | `generateCollectionMinionCard()` (thin wrapper) |
| `desktop.css` | 1487 | `.minion-card` |
| `desktop.css` | 1607 | `.minion-name` |
| `desktop.css` | 1666 | `.effect-tag` |
| `desktop.css` | 1689 | `.minion-stats-box` |
| `desktop.css` | 1735 | `.minion-tribes` |
| `desktop.css` | 2836 | `.portal-tooltip` |
| `dev_combat_routes.py` | 1113 | `/api/dev/minion-info` (dev-only) |
