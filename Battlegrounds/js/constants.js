// Game Constants and Configuration

// Keyword definitions for the UI
// Icons are generated via generateLucideSVG() for better cross-platform display
const KEYWORDS = {
    poke: {
        name: 'Poke',
        description: 'Does not take counter-attack damage when attacking',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('crosshair', 24, 24) : '🏹',
        color: '#4CAF50'
    },
    guard: {
        name: 'Guard',
        description: 'Other minions cannot be attacked until this minion is killed',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('shield', 24, 24) : '🛡️',
        color: '#2196F3'
    },
    assault: {
        name: 'Assault',
        description: 'When this minion attacks, a special effect triggers',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('zap', 24, 24) : '⚡',
        color: '#FF5722'
    },
    death_toll: {
        name: 'Death Toll',
        description: 'When this minion dies, a special effect triggers',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('skull', 24, 24) : '💀',
        color: '#9C27B0'
    },
    cast: {
        name: 'Cast',
        description: 'Instead of attacking normally, cast a spell',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('wand', 24, 24) : '🔮',
        color: '#E91E63'
    },
    rage: {
        name: 'Rage',
        description: 'Triggers when another minion attacks (doesn\'t trigger on casts)',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('frown', 24, 24) : '😡',
        color: '#D32F2F'
    },
    calm: {
        name: 'Calm',
        description: 'Triggers when any minion casts a spell',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('book-open', 24, 24) : '📖',
        color: '#00BCD4'
    },
    on_any_death: {
        name: 'On Any Death',
        description: 'Triggers when any minion dies',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('eye', 24, 24) : '👁️',
        color: '#673AB7'
    },
    on_any_cast: {
        name: 'On Any Cast',
        description: 'Triggers when any spell is cast',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('book-open', 24, 24) : '📖',
        color: '#3F51B5'
    },
    on_any_summon: {
        name: 'On Any Summon',
        description: 'Triggers when any minion is summoned',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('sparkles', 24, 24) : '🌟',
        color: '#FFD700'
    },
    on_adjacent_transform: {
        name: 'On Adjacent Transform',
        description: 'Triggers when an adjacent minion becomes a new minion',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('rotate-cw', 24, 24) : '🔄',
        color: '#8BC34A'
    },
    on_damage: {
        name: 'On Damage',
        description: 'Triggers when this minion takes damage',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('flame', 24, 24) : '💥',
        color: '#FF6F00'
    },
    cant_attack: {
        name: "Can't Attack",
        description: "This minion cannot attack normally (but can still cast)",
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('ban', 24, 24) : '🚫',
        color: '#795548'
    },
    cant_retaliate: {
        name: "Can't Retaliate",
        description: "This minion does not deal counter damage when attacked",
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('shield-off', 24, 24) : '🛑',
        color: '#607D8B'
    },
    multi_attack: {
        name: 'Multi Attack',
        description: 'Attacks 2 times per turn (1 additional attack)',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('swords', 24, 24) : '⚔️',
        color: '#FFC107'
    },
    multi_attack_2: {
        name: 'Multi Attack 2',
        description: 'Attacks 3 times per turn (2 additional attacks)',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('swords', 24, 24) : '⚔️⚔️',
        color: '#FF9800'
    },
    aura: {
        name: 'Aura',
        description: 'Provides passive buffs to adjacent allies at start of combat',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('sparkles', 24, 24) : '💫',
        color: '#9C27B0'
    },
    sacrifice: {
        name: 'Sacrifice',
        description: 'Dies instead of other allies under certain conditions',
        descriptions: {
            minion: 'Dies instead of other allies under certain conditions',
            event: 'Remove a minion from your band'
        },
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('shield', 24, 24) : '🛡️',
        color: '#795548'
    },
    stun: {
        name: 'Stun',
        description: 'Skips 1 attack (reduces multi-attack count by 1)',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('pause', 24, 24) : '⏸️',
        color: '#9E9E9E'
    },
    hide: {
        name: 'Hide',
        description: "Can't be attacked for X attacks or until only target",
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('eye-off', 24, 24) : '🫥',
        color: '#607D8B'
    },
    leap: {
        name: 'Leap',
        description: 'Moves right X spaces when attacking',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('move-right', 24, 24) : '🦘',
        color: '#00BCD4'
    },
    nobility: {
        name: 'Nobility',
        description: 'Immune to spell, ability, effect, and AOE damage',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('crown', 24, 24) : '👑',
        color: '#9C27B0'
    },
    rich: {
        name: 'Rich',
        description: 'Start of Combat: Gain +1/+1 per gold (doubled if golden)',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('coins', 24, 24) : '💰',
        color: '#FFD700'
    },
    fatigue_immune: {
        name: 'Fatigue Immune',
        description: "Can't take fatigue damage",
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('dumbbell', 24, 24) : '💪',
        color: '#FF5722'
    },
    start_of_combat: {
        name: 'Start of Combat',
        description: 'Triggers an effect at the start of combat',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('play-circle', 24, 24) : '🎬',
        color: '#4CAF50'
    },
    cleave: {
        name: 'Cleave',
        description: 'Attacks also hit enemies on either side of the defender',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('sword', 24, 24) : '🗡️',
        color: '#F44336'
    },
    obliterate: {
        name: 'Obliterate',
        description: 'Deals lethal damage to the target',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('skull', 24, 24) : '💀⚡',
        color: '#000000'
    },
    fast: {
        name: 'Fast',
        description: 'Attacks at the start of combat',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('zap', 24, 24) : '⚡💨',
        color: '#FFEB3B'
    },
    savage: {
        name: 'Savage',
        description: 'Attacks and effects always target the lowest health enemy',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('target', 24, 24) : '🎯',
        color: '#D32F2F'
    },
    imperfect: {
        name: 'Imperfect',
        description: 'Can be combined unlimited times (stats sum instead of doubling)',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('settings', 24, 24) : '⚙️',
        color: '#607D8B'
    },
    on_any_leap: {
        name: 'On Any Leap',
        description: 'Triggers when any minion leaps',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('move-right', 24, 24) : '🦘👁️',
        color: '#00BCD4'
    },
    on_any_death_toll: {
        name: 'On Any Death Toll',
        description: 'Triggers when any death toll effect is triggered',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('skull', 24, 24) : '⚰️👁️',
        color: '#9C27B0'
    },
    // Dynamic scope variants for tooltip chaining (when On Any X becomes On Ally X, etc.)
    on_ally_death: {
        name: 'On Ally Death',
        description: 'Triggers when a friendly minion dies',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('eye', 24, 24) : '👁️',
        color: '#673AB7'
    },
    on_ally_summon: {
        name: 'On Ally Summon',
        description: 'Triggers when a friendly minion is summoned',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('sparkles', 24, 24) : '🌟',
        color: '#FFD700'
    },
    on_ally_cast: {
        name: 'On Ally Cast',
        description: 'Triggers when a friendly minion casts',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('wand', 24, 24) : '🔮',
        color: '#3F51B5'
    },
    on_ally_leap: {
        name: 'On Ally Leap',
        description: 'Triggers when a friendly minion leaps',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('move-right', 24, 24) : '🦘',
        color: '#00BCD4'
    },
    on_ally_death_toll: {
        name: 'On Ally Death Toll',
        description: 'Triggers when a friendly death toll effect is triggered',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('skull', 24, 24) : '⚰️',
        color: '#9C27B0'
    },
    on_leap: {
        name: 'On Leap',
        description: 'Triggers when this minion leaps',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('move-right', 24, 24) : '🦘',
        color: '#00BCD4'
    },
    on_hide_lost: {
        name: 'On Ally Hide Lost',
        description: 'Triggers when a friendly minion loses its hide',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('eye', 24, 24) : '👁️⚡',
        color: '#607D8B'
    },
    ignoble: {
        name: 'Ignoble',
        description: 'Immune to combat and counter-attack damage',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('ban', 24, 24) : '🚫👑',
        color: '#424242'
    },
    step: {
        name: 'Step',
        description: 'Every 10 steps you fight a ghost battle',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('footprints', 24, 24) : '👣',
        color: '#78909C'
    },
    rung: {
        name: 'Rung',
        description: 'The number of times you\'ve rung the Bell Tower bell this run. Need 4 to recruit Quasimodo.',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('bell-ring', 24, 24) : '🔔',
        color: '#FFA500'
    },
    ring: {
        name: 'Ring',
        description: 'Start of Combat: Gain +1 Attack per Ring level. Stacks with multiple applications.',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('bell', 24, 24) : '🔔',
        color: '#FFD700'
    },
    lichdom: {
        name: 'Lichdom',
        description: 'Your health is set to 5 permanently. Effects that cost health instead cost gold.',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('crown', 24, 24) : '👑',
        color: '#4A148C'
    },
    ad_nauseam: {
        name: 'Ad Nauseam',
        description: 'Each use costs 1 more HP than the last time you used it this run.',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('repeat', 24, 24) : '🔁',
        color: '#8B0000'
    },
    quasimodo: {
        name: 'Quasimodo',
        description: 'A legendary minion who can be recruited at the Bell Tower after ringing the bell 4 times.',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('user', 24, 24) : '🔔',
        color: '#8B4513'
    },
    bounty: {
        name: 'Bounty',
        description: 'Mark an enemy type. Gain bonus gold when killing marked enemies in combat.',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('crosshair', 24, 24) : '🎯',
        color: '#FF6B35'
    },
    golden: {
        name: 'Golden',
        description: 'A golden minion has doubled base stats and can be made by combining 2 identical minions.',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('sparkles', 24, 24) : '✨',
        color: '#FFD700'
    },
    remove: {
        name: 'Remove',
        description: 'Removed minions don\'t trigger effects.',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('trash-2', 24, 24) : '🗑️',
        color: '#795548'
    },
    seal: {
        name: 'Seal',
        description: 'When seal is 0 you can get another minion slot.',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('lock', 24, 24) : '🔒',
        color: '#9C27B0'
    },
    scrap_curse: {
        name: 'Scrap Curse',
        description: 'Your next general event is guaranteed to be Scrap Heap.',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('skull', 24, 24) : '💀',
        color: '#4A4A4A'
    },
    ethereal: {
        name: 'Ethereal',
        description: "Survives lethal damage until its condition is met. Ethereal minions don't work if there are multiple ethereal minions. Can never guard.",
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('ghost', 24, 24) : '👻',
        color: '#1565C0'
    },
    ethereal_left: {
        name: 'Ethereal [Left]',
        description: "Survives lethal damage until its condition is met. Ethereal minions don't work if there are multiple ethereal minions. Can never guard.",
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('ghost', 24, 24) : '👻',
        color: '#1565C0'
    },
    last: {
        name: 'Last',
        description: "Is allowed to die when it's the last friendly minion alive.",
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('user', 24, 24) : '👤',
        color: '#1565C0'
    },
    left: {
        name: 'Left',
        description: "Is allowed to die when it's the leftmost friendly minion alive.",
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('arrow-left', 24, 24) : '⬅️',
        color: '#1565C0'
    }
};

// Event type information
const EVENT_TYPES = {
    minion: {
        name: 'Minion',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('swords', 24, 24) : '⚔️',
        description: 'Add a new minion to your band'
    },
    buff: {
        name: 'Buff',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('sparkles', 24, 24) : '✨',
        description: 'Enhance your minions'
    },
    shop: {
        name: 'Shop',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('store', 24, 24) : '🛒',
        description: 'Purchase powerful upgrades'
    },
    strong_minion: {
        name: 'Strong Minion',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('muscle', 24, 24) : '💪',
        description: 'Powerful minion option'
    },
    strong_buff: {
        name: 'Strong Buff',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('star', 24, 24) : '⭐',
        description: 'Powerful enhancement'
    },
    tough_enemy: {
        name: 'Tough Enemy',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('skull', 24, 24) : '👹',
        description: 'Face a challenging foe'
    },
    boss: {
        name: 'Boss',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('skull', 24, 24) : '💀',
        description: 'Face a powerful boss'
    },
    curse: {
        name: 'Curse',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('wand', 24, 24) : '🔮',
        description: 'A mysterious curse'
    },
    treasure: {
        name: 'Treasure',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('gem', 24, 24) : '💎',
        description: 'Valuable rewards'
    },
    portal: {
        name: 'Portal',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('workflow', 24, 24) : '🌀',
        description: 'Travel to another zone'
    },
    sub_ring: {
        name: 'Sub-ring',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('git-branch', 24, 24) : '🔀',
        description: 'Enter a dangerous sub-ring'
    }
};

// Zone colors for UI
const ZONE_COLORS = {
    starting_plains: '#4CAF50',
    fiery_depths: '#FF5722',
    arctic_expanse: '#2196F3',
    shadow_realm: '#9C27B0',
    crystal_caverns: '#00BCD4',
    thunderous_peaks: '#FFC107'
};

// Combat fatigue constants
const COMBAT_FATIGUE_START = 100;
const COMBAT_FATIGUE_END = 200;

// Game state constants
const GHOST_BATTLE_INTERVAL = 10;
const MAX_BAND_SIZE = 7;
const STARTING_GOLD = 10;