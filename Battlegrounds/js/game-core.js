// This replaces the original game-core.js file completely
// Copy this entire content to replace your existing js/game-core.js file

// Core game state and API communication
const API_BASE = '/api';
let currentRunId = null;
let currentRunToken = null; // Security token for run ownership verification
let gameData = null;
let eventLog = []; // Persistent event log
let lastEventCount = 0; // Track events to avoid duplicates

// Global state for selections and combat
let selectedOptions = [];
let currentSelectionEventType = null; // Track current selection type to detect changes
let currentSelectionLimits = { min: 0, max: 1 }; // Track current selection limits
let autoCombatInProgress = false;
let autoCombatInterval = null;
const AUTO_COMBAT_DELAY = 1500; // Base delay for auto combat
let autoCombatSpeed = 1; // Speed multiplier: 1, 2, or 3
let selectedMinionIndex = -1; // Minion selection state

// Tracks whether we've already announced the current ghost-battle-ready state.
// `ghost_battle_ready` is sticky on the server (true as long as a ghost is
// queued), so we only want the trumpet + intensity bump on the false→true edge.
let lastGhostBattleReady = false;

// Keyword definitions (matching backend) - UPDATED WITH ALL 34 KEYWORDS
// Icons are generated via generateLucideSVG() - fallback to emoji if function not available
const KEYWORDS = {
    'poke': {
        'name': 'Poke',
        'description': 'Does not take counter-attack damage when attacking',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('crosshair', 24, 24) : '🏹',
        'color': '#4CAF50'
    },
    'guard': {
        'name': 'Guard',
        'description': 'Other minions cannot be attacked until this minion is killed',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('shield', 24, 24) : '🛡️',
        'color': '#2196F3'
    },
    'assault': {
        'name': 'Assault',
        'description': 'When this minion attacks, a special effect triggers',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('zap', 24, 24) : '⚡',
        'color': '#FF5722'
    },
    'death_toll': {
        'name': 'Death Toll',
        'description': 'When this minion dies, a special effect triggers',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('skull', 24, 24) : '💀',
        'color': '#9C27B0'
    },
    'cast': {
        'name': 'Cast',
        'description': 'Instead of attacking normally, cast a spell',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('wand', 24, 24) : '🔮',
        'color': '#E91E63'
    },
    'rage': {
        'name': 'Rage',
        'description': 'Triggers when another minion attacks (doesn\'t trigger on casts)',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('frown', 24, 24) : '😡',
        'color': '#D32F2F'
    },
    'calm': {
        'name': 'Calm',
        'description': 'Triggers when any minion casts a spell',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('book-open', 24, 24) : '📖',
        'color': '#00BCD4'
    },
    'on_any_death': {
        'name': 'On Any Death',
        'description': 'Triggers when any minion dies',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('eye', 24, 24) : '👁️',
        'color': '#673AB7'
    },
    'on_any_cast': {
        'name': 'On Any Cast',
        'description': 'Triggers when any spell is cast',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('book-open', 24, 24) : '📖',
        'color': '#3F51B5'
    },
    'on_any_summon': {
        'name': 'On Any Summon',
        'description': 'Triggers when any minion is summoned',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('sparkles', 24, 24) : '🌟',
        'color': '#FFD700'
    },
    'on_adjacent_transform': {
        'name': 'On Adjacent Transform',
        'description': 'Triggers when an adjacent minion becomes a new minion',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('rotate-cw', 24, 24) : '🔄',
        'color': '#8BC34A'
    },
    'on_damage': {
        'name': 'On Damage',
        'description': 'Triggers when this minion takes damage',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('flame', 24, 24) : '💥',
        'color': '#FF6F00'
    },
    'cant_attack': {
        'name': "Can't Attack",
        'description': "This minion cannot attack normally (but can still cast)",
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('ban', 24, 24) : '🚫',
        'color': '#795548'
    },
    'cant_retaliate': {
        'name': "Can't Retaliate",
        'description': "This minion does not deal counter damage when attacked",
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('shield-off', 24, 24) : '🛑',
        'color': '#607D8B'
    },
    'multi_attack': {
        'name': 'Multi Attack',
        'description': 'Attacks 2 times per turn (1 additional attack)',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('swords', 24, 24) : '⚔️',
        'color': '#FFC107'
    },
    'multi_attack_2': {
        'name': 'Multi Attack 2',
        'description': 'Attacks 3 times per turn (2 additional attacks)',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('swords', 24, 24) : '⚔️⚔️',
        'color': '#FF9800'
    },
    'aura': {
        'name': 'Aura',
        'description': 'Provides passive buffs to adjacent allies at start of combat',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('sparkles', 24, 24) : '💫',
        'color': '#9C27B0'
    },
    'sacrifice': {
        'name': 'Sacrifice',
        'description': 'Dies instead of other allies under certain conditions',
        'descriptions': {
            'minion': 'Dies instead of other allies under certain conditions',
            'event': 'Remove a minion from your band'
        },
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('shield', 24, 24) : '🛡️',
        'color': '#795548'
    },
    'stun': {
        'name': 'Stun',
        'description': 'Skips 1 attack (reduces multi-attack count by 1)',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('pause', 24, 24) : '⏸️',
        'color': '#9E9E9E'
    },
    'hide': {
        'name': 'Hide',
        'description': "Can't be attacked for X attacks or until only target",
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('eye-off', 24, 24) : '🫥',
        'color': '#607D8B'
    },
    'ring': {
        'name': 'Ring',
        'description': 'Start of Combat: Trigger 1 random friendly death toll, decrease this by 1',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('bell', 24, 24) : '🔔',
        'color': '#FFA500'
    },
    'leap': {
        'name': 'Leap',
        'description': 'Moves right X spaces when attacking',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('move-right', 24, 24) : '🦘',
        'color': '#00BCD4'
    },
    'nobility': {
        'name': 'Nobility',
        'description': 'Immune to spell, ability, effect, and AOE damage',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('crown', 24, 24) : '👑',
        'color': '#9C27B0'
    },
    'rich': {
        'name': 'Rich',
        'description': 'Start of Combat: Gain +1/+1 per gold (doubled if golden)',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('coins', 24, 24) : '💰',
        'color': '#FFD700'
    },
    'fatigue_immune': {
        'name': 'Fatigue Immune',
        'description': "Can't take fatigue damage",
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('dumbbell', 24, 24) : '💪',
        'color': '#FF5722'
    },
    'start_of_combat': {
        'name': 'Start of Combat',
        'description': 'Triggers an effect at the start of combat',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('play-circle', 24, 24) : '🎬',
        'color': '#4CAF50'
    },
    'cleave': {
        'name': 'Cleave',
        'description': 'Attacks also hit enemies on either side of the defender',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('sword', 24, 24) : '🗡️',
        'color': '#F44336'
    },
    'obliterate': {
        'name': 'Obliterate',
        'description': 'When dealing damage, deal lethal damage instead',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('skull', 24, 24) : '💀⚡',
        'color': '#000000'
    },
    'fast': {
        'name': 'Fast',
        'description': 'Attacks at the start of combat',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('zap', 24, 24) : '⚡💨',
        'color': '#FFEB3B'
    },
    'savage': {
        'name': 'Savage',
        'description': 'Attacks and effects always target the lowest health enemy',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('target', 24, 24) : '🎯',
        'color': '#D32F2F'
    },
    'imperfect': {
        'name': 'Imperfect',
        'description': 'Can be combined unlimited times (stats sum instead of doubling)',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('settings', 24, 24) : '⚙️',
        'color': '#607D8B'
    },
    'on_any_leap': {
        'name': 'On Any Leap',
        'description': 'Triggers when any minion leaps',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('move-right', 24, 24) : '🦘👁️',
        'color': '#00BCD4'
    },
    'on_any_death_toll': {
        'name': 'On Any Death Toll',
        'description': 'Triggers when any death toll effect is triggered',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('skull', 24, 24) : '⚰️👁️',
        'color': '#9C27B0'
    },
    // Dynamic scope variants for tooltip chaining
    'on_ally_death': {
        'name': 'On Ally Death',
        'description': 'Triggers when a friendly minion dies',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('eye', 24, 24) : '👁️',
        'color': '#673AB7'
    },
    'on_ally_summon': {
        'name': 'On Ally Summon',
        'description': 'Triggers when a friendly minion is summoned',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('sparkles', 24, 24) : '🌟',
        'color': '#FFD700'
    },
    'on_ally_cast': {
        'name': 'On Ally Cast',
        'description': 'Triggers when a friendly minion casts',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('wand', 24, 24) : '🔮',
        'color': '#3F51B5'
    },
    'on_ally_leap': {
        'name': 'On Ally Leap',
        'description': 'Triggers when a friendly minion leaps',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('move-right', 24, 24) : '🦘',
        'color': '#00BCD4'
    },
    'on_ally_death_toll': {
        'name': 'On Ally Death Toll',
        'description': 'Triggers when a friendly death toll effect is triggered',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('skull', 24, 24) : '⚰️',
        'color': '#9C27B0'
    },
    'on_leap': {
        'name': 'On Leap',
        'description': 'Triggers when this minion leaps',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('move-right', 24, 24) : '🦘',
        'color': '#00BCD4'
    },
    'on_hide_lost': {
        'name': 'On Hide Lost',
        'description': 'Triggers when this minion loses its hide',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('eye', 24, 24) : '👁️⚡',
        'color': '#607D8B'
    },
    'ignoble': {
        'name': 'Ignoble',
        'description': 'Immune to combat and counter-attack damage',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('ban', 24, 24) : '🚫👑',
        'color': '#424242'
    },
    'rung': {
        'name': 'Rung',
        'description': 'The number of times you\'ve rung the Bell Tower bell this run. Need 4 to recruit Quasimodo.',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('bell-ring', 24, 24) : '🔔',
        'color': '#FFA500'
    },
    'step': {
        'name': 'Step',
        'description': 'Every 10 steps you fight a ghost battle',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('footprints', 24, 24) : '👣',
        'color': '#78909C'
    },
    'remove': {
        'name': 'Remove',
        'description': 'Removed minions don\'t trigger effects.',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('trash-2', 24, 24) : '🗑️',
        'color': '#795548'
    },
    'seal': {
        'name': 'Seal',
        'description': 'When seal is 0 you can get another minion slot.',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('lock', 24, 24) : '🔒',
        'color': '#9C27B0'
    },
    'scrap_curse': {
        'name': 'Scrap Curse',
        'description': 'Your next general event is guaranteed to be Scrap Heap.',
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('skull', 24, 24) : '💀',
        'color': '#4A4A4A'
    },
    'ethereal': {
        'name': 'Ethereal',
        'description': "Survives lethal damage until its condition is met. Ethereal minions don't work if there are multiple ethereal minions. Can never guard.",
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('ghost', 24, 24) : '👻',
        'color': '#1565C0'
    },
    'ethereal_left': {
        'name': 'Ethereal [Left]',
        'description': "Survives lethal damage until its condition is met. Ethereal minions don't work if there are multiple ethereal minions. Can never guard.",
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('ghost', 24, 24) : '👻',
        'color': '#1565C0'
    },
    'last': {
        'name': 'Last',
        'description': "Is allowed to die when it's the last friendly minion alive.",
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('user', 24, 24) : '👤',
        'color': '#1565C0'
    },
    'left': {
        'name': 'Left',
        'description': "Is allowed to die when it's the leftmost friendly minion alive.",
        'icon': typeof generateLucideSVG === 'function' ? generateLucideSVG('arrow-left', 24, 24) : '⬅️',
        'color': '#1565C0'
    }
};

// Event type icons and names for ring progress
// Each entry provides: icon (filled, for non-map use), mapIcon (stroke-only, for map flags),
// desc/hint (for structured map tooltips), accentType (for CSS color theming)
function _eventIcon(lucideName, emojiFallback) {
    const hasSvg = typeof generateLucideSVG === 'function';
    return {
        icon: hasSvg ? generateLucideSVG(lucideName, 24, 24) : emojiFallback,
        mapIcon: hasSvg ? generateLucideSVG(lucideName, 24, 24, 'currentColor', 'icon-map') : emojiFallback,
        lucide: lucideName
    };
}

const EVENT_ICONS = {
    'minion_event': {
        ..._eventIcon('gift', '🎁'),
        name: 'Free Minion',
        desc: 'Pick one of three minions for free.',
        hint: 'Tier-scaled selection',
        accentType: 'minion'
    },
    'minion_event_rare': {
        ..._eventIcon('sparkles', '✨'),
        name: 'Rare Minion',
        desc: 'Pick one of three rare minions for free.',
        hint: 'Higher-quality pool',
        accentType: 'minion'
    },
    'minion_event_epic': {
        ..._eventIcon('gem', '💎'),
        name: 'Epic Minion',
        desc: 'Pick one of three epic minions for free.',
        hint: 'Powerful selections',
        accentType: 'minion'
    },
    'minion_event_legendary': {
        ..._eventIcon('star', '🌟'),
        name: 'Legendary',
        desc: 'Pick one of three legendary minions for free.',
        hint: 'Top-tier selection',
        accentType: 'minion'
    },
    'buff_event': {
        ..._eventIcon('sparkles', '✨'),
        name: 'Blessing',
        desc: 'Buff a minion\'s attack, health, or both.',
        hint: 'Strength scales with tier',
        accentType: 'blessing'
    },
    'combat_event': {
        ..._eventIcon('swords', '⚔️'),
        name: 'Combat',
        desc: 'Fight a warband matching your tier.',
        hint: 'Victory awards gold',
        accentType: 'combat'
    },
    'combat_event_hard': {
        ..._eventIcon('skull', '💀'),
        name: 'Hard Combat',
        desc: 'Combat at +1 tier above current ring.',
        hint: 'Better rewards on victory',
        accentType: 'hard_combat'
    },
    'shop_event': {
        ..._eventIcon('store', '🏪'),
        name: 'Shop',
        desc: 'Spend gold to recruit minions.',
        hint: 'Reroll for new offers',
        accentType: 'shop'
    },
    'shop_event_legendary': {
        ..._eventIcon('landmark', '🏛️'),
        name: 'Legendary Shop',
        desc: 'Rare minions available for purchase.',
        hint: 'Premium selection',
        accentType: 'shop'
    },
    'shop_event_mythic': {
        ..._eventIcon('wand', '🔮'),
        name: 'Mythic Shop',
        desc: 'The rarest minions money can buy.',
        hint: 'Mythic-tier pool',
        accentType: 'shop'
    },
    'general_event': {
        ..._eventIcon('scroll', '📜'),
        name: 'General Event',
        desc: 'Random encounter with unique choices.',
        hint: 'Risk/reward trade-offs',
        accentType: 'general'
    },
    'statue': {
        ..._eventIcon('package', '🗿'),
        name: 'Statue',
        desc: 'Combine three copies into a golden minion.',
        hint: 'Doubled stats',
        accentType: 'statue'
    },
    'artifact': {
        ..._eventIcon('scroll', '⚱️'),
        name: 'Artifact',
        desc: 'A mysterious artifact with unknown power.',
        hint: 'Unique reward',
        accentType: 'statue'
    },
    'zone_portal': {
        ..._eventIcon('workflow', '🌀'),
        name: 'Portal',
        desc: 'Travel to a different zone.',
        hint: 'Choose destination on arrival',
        accentType: 'portal'
    },
    'split_event': {
        ..._eventIcon('rotate-cw', '🔄'),
        name: 'Choice',
        desc: 'Choose between two event paths.',
        hint: 'Pick one',
        accentType: 'general'
    },
    // Zone location events
    'bell_tower': {
        ..._eventIcon('bell', '🔔'),
        name: 'Bell Tower',
        desc: 'Ring the bells for blessings.',
        hint: 'Unlock Quasimodo after ringing 4 bells',
        accentType: 'zone_human'
    },
    'ivory_tower': {
        ..._eventIcon('crown', '👑'),
        name: 'Ivory Tower',
        desc: 'Weaken the seal for a powerful reward.',
        hint: 'Unlocks extra band slot',
        accentType: 'zone_fey'
    },
    'grand_city': {
        ..._eventIcon('landmark', '🏛️'),
        name: 'Grand City',
        desc: 'Powerful options with a curse.',
        hint: 'Rewards come at a cost',
        accentType: 'zone_construct'
    },
    'the_red_gate': {
        ..._eventIcon('flame', '🔥'),
        name: 'The Red Gate',
        desc: 'Strip a minion to gain Ethereal.',
        hint: 'Abandon everything for transcendence',
        accentType: 'zone_cult'
    },
    'the_great_work': {
        ..._eventIcon('book-open', '📖'),
        name: 'The Great Work',
        desc: 'Escalating costs for powerful effects.',
        hint: 'Costs increase each visit',
        accentType: 'zone_undead'
    },
    'the_great_hunt': {
        ..._eventIcon('crosshair', '🏹'),
        name: 'The Great Hunt',
        desc: 'Bounty board with tiered boss hunts.',
        hint: 'Defeat bosses for unique rewards',
        accentType: 'zone_beast'
    }
};

// =============================================================================
// MINION IMAGE PATH HELPER
// =============================================================================
// Server provides image_path for all minions. Client should use server-provided
// path directly. This helper creates the CSS background-image style.
//
// The server determines the correct image path based on the player's equipped
// images. The client just renders whatever path the server provides.
// =============================================================================

/**
 * Get the image path for a minion.
 * Uses server-provided image_path if available, falls back to original.
 * @param {Object} minion - Minion object with image_path and/or image properties
 * @returns {string|null} Image path or null if no image
 */
function getMinionImagePath(minion) {
    // Prefer server-provided image_path (already includes correct equipped variant)
    if (minion.image_path) {
        return minion.image_path;
    }

    // Fallback to original if no image_path provided
    if (minion.image) {
        return `images/original/${minion.image}`;
    }

    return null;
}

/**
 * Get the CSS background-image style for a minion.
 * Uses server-provided image_path if available, falls back to original.
 * @param {Object} minion - Minion object with image_path and/or image properties
 * @returns {string} CSS inline style string for background-image
 */
function getMinionImageStyle(minion) {
    const imagePath = getMinionImagePath(minion);

    if (!imagePath) {
        return '';
    }

    return `background-image: url('${imagePath}'); background-size: 100% 100%; background-repeat: no-repeat; background-position: center;`;
}

// Export for use in other files
window.getMinionImagePath = getMinionImagePath;
window.getMinionImageStyle = getMinionImageStyle;

// API call helper function
async function apiCall(endpoint, method = 'GET', data = null) {
    try {
        const headers = {
            'Content-Type': 'application/json',
        };
        // Send run token for ownership verification
        if (currentRunToken) {
            headers['X-Run-Token'] = currentRunToken;
        }
        const options = {
            method,
            headers,
            credentials: 'include' // Include session cookies
        };

        if (data) {
            options.body = JSON.stringify(data);
        }

        const response = await fetch(`${API_BASE}${endpoint}`, options);
        if (!response.ok) {
            let errorMsg = `HTTP ${response.status}`;
            try { const err = await response.json(); errorMsg = err.error || errorMsg; } catch {}
            throw new Error(errorMsg);
        }
        const result = await response.json();

        if (!result.success) {
            throw new Error(result.error || 'API call failed');
        }

        return result;
    } catch (error) {
        console.error('API Error:', error);
        alert('Error: ' + error.message);
        throw error;
    }
}

// Start a new game
async function startNewGame(isRanked = false, forceNew = false) {
    try {
        // Stop any ongoing auto combat and reset selection
        if (typeof stopAutoCombat === 'function') {
            stopAutoCombat();
        }
        selectedMinionIndex = -1;

        // Get selected hero from main menu (if available)
        const heroId = typeof selectedHeroId !== 'undefined' ? selectedHeroId : null;

        const result = await apiCall('/start-run', 'POST', {
            ranked: isRanked,
            force_new: forceNew,
            hero_id: heroId
        });
        currentRunId = result.run.id;
        currentRunToken = result.run.run_token; // Store security token
        gameData = result;
        eventLog = []; // Reset log for new game
        lastEventCount = 0;
        lastGhostBattleReady = !!result.ghost_battle_ready; // don't re-announce on first refresh
        updateDisplay();

        const gameMode = isRanked ? '🏆 RANKED' : '🎮 UNRANKED';
        const resumedText = result.resumed ? 'RESUMED' : 'started';
        addLogEntry(`${gameMode} game ${resumedText}! Ring ${result.run.current_ring}, Position ${result.run.ring_position}`, 'event');
        addLogEntry(`🌍 Starting in: ${result.current_zone.icon} ${result.current_zone.name}`, 'event');
        addLogEntry(`📍 Current event: ${formatEventName(result.current_event)}`, 'event');

        // Kick off ambient music on the zone the run is entering. MusicEngine.start()
        // is gesture-gated internally via SoundBus; the click that triggered
        // startNewGame satisfies that.
        if (window.MusicEngine && result.current_zone) {
            window.MusicEngine.setZone(result.current_zone.key || 'crossroads');
            window.MusicEngine.setBaselineIntensity(0.2);
            window.MusicEngine.setIntensity(0.2);
            window.MusicEngine.start();
        }
    } catch (error) {
        console.error('Failed to start game:', error);
    }
}

// Refresh game state
async function refreshGame() {
    if (!currentRunId) return;

    try {
        const result = await apiCall(`/run/${currentRunId}`);
        gameData = result;
        updateDisplay();
    } catch (error) {
        console.error('Failed to refresh game:', error);
    }
}

// Movement functions
async function movePlayer(direction) {
    if (!currentRunId) return;

    try {
        console.log('Moving player:', direction);
        const result = await apiCall(`/run/${currentRunId}/move`, 'POST', { direction });
        console.log('Move result:', result);

        gameData = result;
        updateDisplay();

        // Log the movement
        addLogEntry(`🚶 Moved ${direction}`, 'event');
        if (window.MusicEngine) window.MusicEngine.bumpIntensity(0.05);

        // Handle event result or selection
        if (result.has_selection) {
            console.log('Selection created!');
            addLogEntry(`📍 Selection available: Choose your path!`, 'event');
        } else if (result.event_result) {
            const event = result.event_result;
            addLogEntry(`✨ ${event.message}`, 'event');

            if (event.band_changes && event.band_changes.length > 0) {
                event.band_changes.forEach(change => {
                    addLogEntry(`🔧 ${change}`, 'event');
                });
            }

            if (event.resource_changes && Object.keys(event.resource_changes).length > 0) {
                Object.entries(event.resource_changes).forEach(([resource, change]) => {
                    addLogEntry(`💰 ${resource}: ${change}`, 'event');
                });
            }
        }

        // Check for ghost battle — only announce on the transition into ready.
        if (result.ghost_battle_ready && !lastGhostBattleReady) {
            addLogEntry('👻 GHOST BATTLE READY! 10 events completed!', 'battle');
            if (window.SoundBus) window.SoundBus.playAction('GHOST_READY');
            if (window.MusicEngine) window.MusicEngine.setIntensity(0.85);
        }
        lastGhostBattleReady = !!result.ghost_battle_ready;

        // Log next event if no selection
        if (!result.has_selection && result.next_event) {
            addLogEntry(`📍 Next event: ${formatEventName(result.next_event)}`, 'event');
        }
    } catch (error) {
        console.error('Failed to move:', error);
    }
}

// Ring upgrade
async function upgradeRing() {
    if (!currentRunId) return;

    try {
        const result = await apiCall(`/run/${currentRunId}/upgrade-ring`, 'POST');
        gameData = result;
        updateDisplay();
        addLogEntry(`🔥 ${result.message}`, 'event');
        addLogEntry(`📍 New event: ${formatEventName(result.current_event)}`, 'event');
        if (window.SoundBus) window.SoundBus.playAction('RING_UPGRADE');
    } catch (error) {
        console.error('Failed to upgrade ring:', error);
    }
}

// Zone travel
async function travelToZone(targetZone) {
    if (!currentRunId) return;

    try {
        addLogEntry(`🌀 Attempting to travel to ${targetZone}...`, 'event');
        const result = await apiCall(`/run/${currentRunId}/travel-zone`, 'POST', { zone: targetZone });
        gameData = result;
        updateDisplay();

        if (result.travel_result) {
            addLogEntry(`✈️ ${result.travel_result.message}`, 'event');
            addLogEntry(`📍 Arrived at position ${result.travel_result.new_position}`, 'event');
            if (window.SoundBus) window.SoundBus.playAction('ZONE_TRAVEL');
            if (window.MusicEngine && gameData && gameData.current_zone) {
                window.MusicEngine.setZone(gameData.current_zone.key || targetZone);
            }
        }

        addLogEntry(`📍 Current event: ${formatEventName(gameData.current_event)}`, 'event');
    } catch (error) {
        console.error('Failed to travel to zone:', error);
    }
}

// Preview ghost
async function previewGhost() {
    if (!currentRunId) return;

    try {
        addLogEntry('👁️ Opening ghost preview...', 'info');
        const result = await apiCall(`/run/${currentRunId}/preview-ghost`, 'POST');
        gameData = result;

        // Preview creates a selection UI, so update display to show preview screen
        addLogEntry('👻 Ghost preview opened', 'info');
        updateDisplay();
    } catch (error) {
        console.error('Failed to preview ghost:', error);
        addLogEntry('❌ Failed to preview ghost', 'error');
    }
}

// Fight ghost early
async function fightGhostEarly() {
    if (!currentRunId) return;

    try {
        addLogEntry('⚔️ Starting early ghost battle...', 'info');
        const result = await apiCall(`/run/${currentRunId}/fight-ghost-early`, 'POST');
        gameData = result;

        // Early ghost battle creates a combat selection
        addLogEntry('👻 Ghost battle started - win to skip ahead!', 'info');
        updateDisplay();
    } catch (error) {
        console.error('Failed to start early ghost battle:', error);
        addLogEntry('❌ Failed to start early ghost battle', 'error');
    }
}

// Ghost battle
async function ghostBattle() {
    if (!currentRunId) return;

    try {
        addLogEntry('👻 Initiating ghost battle...', 'battle');
        const result = await apiCall(`/run/${currentRunId}/ghost-battle`, 'POST');
        gameData = result;

        // Ghost battles now create a combat selection, so update display to show combat UI
        addLogEntry('⚔️ Entering combat...', 'battle');
        updateDisplay();
    } catch (error) {
        console.error('Failed to start ghost battle:', error);
        addLogEntry('❌ Failed to start ghost battle', 'error');
    }
}

// Selection handling
async function submitSelection(forceSelection = null) {
    if (!currentRunId) return;

    const selectionsToSubmit = forceSelection ? [forceSelection] : selectedOptions;

    if (selectionsToSubmit.length === 0) {
        alert('Please make a selection first.');
        return;
    }

    try {
        const result = await apiCall(`/run/${currentRunId}/select`, 'POST', {
            selections: selectionsToSubmit
        });

        gameData = result;
        updateDisplay();

        // Clear selections after successful submission
        selectedOptions = [];

        // Update selection UI
        document.querySelectorAll('.selection-option').forEach(option => {
            option.classList.remove('selected');
        });

        // Log selection results
        if (result.selection_result) {
            const selection = result.selection_result;

            if (selection.results && selection.results.length > 0) {
                selection.results.forEach(message => {
                    addLogEntry(`✅ ${message}`, 'event');
                });
            }

            if (selection.band_changes && selection.band_changes.length > 0) {
                selection.band_changes.forEach(change => {
                    addLogEntry(`👥 Band: ${change}`, 'band');
                });
            }

            if (selection.resource_changes && Object.keys(selection.resource_changes).length > 0) {
                Object.entries(selection.resource_changes).forEach(([resource, change]) => {
                    addLogEntry(`💰 ${resource}: ${change}`, 'event');
                });
            }
        }

        // Check for ghost battle
        if (result.ghost_battle_ready) {
            addLogEntry('👻 GHOST BATTLE READY! 10 events completed!', 'battle');
        }
    } catch (error) {
        console.error('Failed to submit selection:', error);
    }
}

// Selection option handling
function selectOption(optionId) {
    const option = document.querySelector(`[data-option-id="${optionId}"]`);
    if (!option) return;

    const isCurrentlySelected = selectedOptions.includes(optionId);

    if (isCurrentlySelected) {
        // Deselect
        selectedOptions = selectedOptions.filter(id => id !== optionId);
        option.classList.remove('selected');
    } else {
        // Check if we can select more
        if (selectedOptions.length >= currentSelectionLimits.max) {
            // Remove oldest selection if at max
            const oldestId = selectedOptions.shift();
            const oldestOption = document.querySelector(`[data-option-id="${oldestId}"]`);
            if (oldestOption) {
                oldestOption.classList.remove('selected');
            }
        }

        // Select
        selectedOptions.push(optionId);
        option.classList.add('selected');
    }

    updateSelectionControls();
}

// Update selection controls visibility
function updateSelectionControls() {
    const submitBtn = document.getElementById('submitSelectionBtn');
    if (submitBtn) {
        const canSubmit = selectedOptions.length >= currentSelectionLimits.min &&
                         selectedOptions.length <= currentSelectionLimits.max;
        submitBtn.disabled = !canSubmit;

        // Update button text with selection count
        const selectionText = selectedOptions.length === 1 ?
            '1 selection' : `${selectedOptions.length} selections`;
        submitBtn.textContent = `✅ Submit (${selectionText})`;
    }
}

// Minion management
async function swapMinions(index1, index2) {
    if (!currentRunId) return;

    try {
        const result = await apiCall(`/run/${currentRunId}/swap-minions`, 'POST', {
            index1: index1,
            index2: index2
        });

        gameData = result;
        updateDisplay();

        if (result.success) {
            addLogEntry(`🔄 Swapped minions at positions ${index1 + 1} and ${index2 + 1}`, 'band');
        }
    } catch (error) {
        console.error('Failed to swap minions:', error);
    }
}

async function abandonMinion(index) {
    if (!currentRunId) return;

    const minion = gameData.run.band[index];
    if (!confirm(`Really abandon ${minion.name}? This cannot be undone.`)) {
        return;
    }

    try {
        const result = await apiCall(`/run/${currentRunId}/abandon-minion`, 'POST', {
            index: index
        });

        gameData = result;
        updateDisplay();

        if (result.success) {
            addLogEntry(`👋 Abandoned ${minion.name}`, 'band');
        }
    } catch (error) {
        console.error('Failed to abandon minion:', error);
    }
}

// Minion selection for swapping/abandoning
function selectMinion(index) {
    if (selectedMinionIndex === -1) {
        // First selection
        selectedMinionIndex = index;
        updateDisplay();
        addLogEntry(`🎯 Selected minion ${index + 1}. Click another to swap, or click buttons below.`, 'band');
    } else if (selectedMinionIndex === index) {
        // Deselect same minion
        selectedMinionIndex = -1;
        updateDisplay();
        addLogEntry(`❌ Deselected minion ${index + 1}`, 'band');
    } else {
        // Swap with selected minion
        swapMinions(selectedMinionIndex, index);
        selectedMinionIndex = -1; // Reset selection after swap
    }
}

// Utility functions - UPDATED FOR SCALING EVENTS
function formatEventName(eventType) {
    // Use SVG icons instead of emojis
    const giftIcon = typeof generateLucideSVG === 'function' ? generateLucideSVG('gift', 18, 18) : '';
    const sparklesIcon = typeof generateLucideSVG === 'function' ? generateLucideSVG('sparkles', 18, 18) : '';
    const swordIcon = typeof generateLucideSVG === 'function' ? generateLucideSVG('swords', 18, 18) : '';
    const storeIcon = typeof generateLucideSVG === 'function' ? generateLucideSVG('store', 18, 18) : '';
    const monumentIcon = typeof generateLucideSVG === 'function' ? generateLucideSVG('monument', 18, 18) : '';
    const portalIcon = typeof generateLucideSVG === 'function' ? generateLucideSVG('circle-dot', 18, 18) : '';
    const pathIcon = typeof generateLucideSVG === 'function' ? generateLucideSVG('git-branch', 18, 18) : '';

    const eventNames = {
        // Scaling minion events
        'minion_event': `${giftIcon} Wandering Recruit`,
        'minion_event_rare': `${sparklesIcon} Rare Recruit`,
        'minion_event_epic': `${sparklesIcon} Epic Recruit`,
        'minion_event_legendary': `${sparklesIcon} Legendary Recruit`,

        // Buff event - scales with ring
        'buff_event': `${sparklesIcon} Shrine of Blessing`,

        // Scaling combat events
        'combat_event': `${swordIcon} Battle`,
        'combat_event_hard': `${swordIcon} Hard Battle`,

        // Scaling shop events
        'shop_event': `${storeIcon} Tavern`,
        'shop_event_legendary': `${storeIcon} Grand Tavern`,
        'shop_event_mythic': `${storeIcon} Mythic Emporium`,

        // Static events
        'statue': `${monumentIcon} Ancient Statue`,
        'artifact': `${sparklesIcon} Mysterious Artifact`,
        'zone_portal': `${portalIcon} Zone Portal`,
        'split_event': `${pathIcon} Crossroads`
    };

    return eventNames[eventType] || eventType;
}

function calculateBandPower(band) {
    return band.reduce((total, minion) => {
        let basePower = minion.health + (minion.attack * 2);

        // Add keyword power bonuses
        const keywords = minion.keywords || [];
        let keywordBonus = 0;
        keywords.forEach(keyword => {
            if (keyword.toLowerCase() === 'poke') {
                keywordBonus += 5; // Poke adds defensive value
            }
            if (keyword.toLowerCase() === 'guard') {
                keywordBonus += 8; // Guard adds high defensive value
            }
            if (keyword.toLowerCase() === 'assault') {
                keywordBonus += 6; // Assault adds offensive value
            }
            if (keyword.toLowerCase() === 'death_toll') {
                keywordBonus += 4; // Death toll adds utility value
            }
            if (keyword.toLowerCase() === 'cast') {
                keywordBonus += 7; // Cast adds spell value
            }
            if (keyword.toLowerCase() === 'cant_attack') {
                keywordBonus -= 3; // Penalty for not being able to attack
            }
            if (keyword.toLowerCase() === 'cant_retaliate') {
                keywordBonus -= 2; // Small penalty for vulnerability
            }
            if (keyword.toLowerCase() === 'multi_attack') {
                // Multi-attack is very powerful
                const multiCount = minion.multi_attack_count || 1;
                const goldenMultiplier = minion.golden ? 2 : 1;
                keywordBonus += 10 * multiCount * goldenMultiplier;
            }
        });

        // Golden minions have higher power value
        let goldenBonus = 0;
        if (minion.golden) {
            goldenBonus = Math.floor(basePower * 0.5); // 50% bonus for golden minions
        }

        return total + basePower + keywordBonus + goldenBonus;
    }, 0);
}

function addLogEntry(message, type = 'event') {
    const timestamp = new Date().toLocaleTimeString();
    eventLog.push({
        message: message,
        type: type,
        timestamp: timestamp
    });

    // Keep log size manageable
    if (eventLog.length > 100) {
        eventLog = eventLog.slice(-80); // Keep last 80 entries
    }

    updateLogDisplay();
}

function updateLogDisplay() {
    const logContainer = document.getElementById('logEntries');
    if (!logContainer) return;

    // Show recent entries (reversed for newest first)
    const recentEntries = eventLog.slice(-15).reverse();

    logContainer.innerHTML = recentEntries.map(entry => {
        const typeClass = `log-entry ${entry.type}`;
        return `
            <div class="${typeClass}">
                <span class="log-time">[${entry.timestamp}]</span>
                <span class="log-message">${entry.message}</span>
            </div>
        `;
    }).join('');

    // Auto-scroll to newest (top)
    logContainer.scrollTop = 0;
}

function updateEventLog() {
    // Alias for backward compatibility
    updateLogDisplay();
}

function displayBattleLog(battleLog) {
    if (!battleLog || battleLog.length === 0) return;

    // Add battle log entries to main event log
    battleLog.forEach(logEntry => {
        addLogEntry(`⚔️ ${logEntry}`, 'battle');
    });
}

// Format keywords for display
function formatKeywords(keywords) {
    // Safety check: ensure keywords is an array
    if (!keywords) return '';
    if (!Array.isArray(keywords)) {
        console.warn('formatKeywords received non-array:', keywords);
        return '';
    }
    if (keywords.length === 0) return '';

    return keywords.map(keyword => {
        const keywordInfo = KEYWORDS[keyword.toLowerCase()];
        if (keywordInfo) {
            return `<span class="keyword" style="color: ${keywordInfo.color}" title="${keywordInfo.description}">
                ${keywordInfo.icon} ${keywordInfo.name}
            </span>`;
        }
        return keyword;
    }).join(' ');
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', function() {
    console.log('Auto Battler Arena loaded');
    // Main menu system will handle initial display
});