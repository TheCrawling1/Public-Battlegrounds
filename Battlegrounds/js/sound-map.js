// SOUND_MAP - central action → sound mapping.
//
// Every named game action maps to one entry. Entries have:
//   instrument: 'harp' | 'trumpet' | 'drum'
//   motif:      [semitones…] (offsets from A4=0; e.g. 0=A4, 12=A5, -5=E4)
//   gain:       0..1 (default 0.8)
//   step:       seconds between motif notes (default 0.07)
//   channel:    'sfx' | 'ui' | 'music' (default 'sfx')
//   musicOnly:  true → this entry is handled by MusicEngine, not SoundBus
//               (e.g. zone changes, intensity bumps)
//
// Keys for combat commands match CombatCommand strings from combat_interpreter.py.
// Keys for UI actions are UPPERCASE_SNAKE names chosen here.
//
// Everything here is data — the Sound Studio (dev-sounds) enumerates this
// object to build its UI, so adding a new action = add a line.

(function () {
    'use strict';

    const SOUND_MAP = {
        // ── Combat: attack / damage ────────────────────────────────────────────
        DECLARE_ATTACK:      { instrument: 'drum',    motif: [0],        gain: 0.4,  channel: 'sfx' },
        COMBAT_DAMAGE:       { instrument: 'drum',    motif: [-2],       gain: 0.65, channel: 'sfx' },
        COUNTER_DAMAGE:      { instrument: 'drum',    motif: [-4],       gain: 0.55, channel: 'sfx' },
        MULTI_ATTACK:        { instrument: 'drum',    motif: [0, 2],     gain: 0.45, channel: 'sfx', step: 0.06 },
        FATIGUE_DAMAGE:      { instrument: 'drum',    motif: [-7],       gain: 0.4,  channel: 'sfx' },
        DEAL_DAMAGE:         { instrument: 'drum',    motif: [-1, -3],   gain: 0.55, channel: 'sfx', step: 0.05 },
        DEAL_AOE_DAMAGE:     { instrument: 'drum',    motif: [0, -4, -7],gain: 0.6,  channel: 'sfx', step: 0.04 },

        // ── Combat: life / death ───────────────────────────────────────────────
        DEATH:               { instrument: 'trumpet', motif: [-5, -10],  gain: 0.4,  channel: 'sfx', step: 0.14 },
        DESTROY_MINION:      { instrument: 'trumpet', motif: [-7, -12],  gain: 0.4,  channel: 'sfx', step: 0.12 },
        REMOVE_FROM_BAND:    { instrument: 'harp',    motif: [-3, -7],   gain: 0.35, channel: 'sfx', step: 0.06 },
        HEAL:                { instrument: 'harp',    motif: [0, 4, 7],  gain: 0.7,  channel: 'sfx', step: 0.06 },
        PREVENT_DEATH:       { instrument: 'harp',    motif: [7, 12, 16],gain: 0.7,  channel: 'sfx', step: 0.05 },
        ETHEREAL_SAVE:       { instrument: 'harp',    motif: [12, 14],   gain: 0.6,  channel: 'sfx', step: 0.05 },

        // ── Combat: buffs / stats ──────────────────────────────────────────────
        BUFF_STATS:          { instrument: 'harp',    motif: [4, 7],     gain: 0.55, channel: 'sfx', step: 0.06 },
        DEBUFF_STATS:        { instrument: 'harp',    motif: [-2, -5],   gain: 0.45, channel: 'sfx', step: 0.07 },
        PERMANENT_STAT_GAIN: { instrument: 'harp',    motif: [0, 4, 7, 12], gain: 0.6, channel: 'sfx', step: 0.05 },
        COPY_STATS:          { instrument: 'harp',    motif: [0, 5],     gain: 0.5,  channel: 'sfx', step: 0.06 },
        DIVIDE_ATTACK:       { instrument: 'harp',    motif: [2, -2],    gain: 0.5,  channel: 'sfx', step: 0.06 },

        // ── Combat: status effects ─────────────────────────────────────────────
        STUN:                { instrument: 'trumpet', motif: [-10],      gain: 0.45, channel: 'sfx' },
        APPLY_STUN:          { instrument: 'trumpet', motif: [-10, -12], gain: 0.5,  channel: 'sfx', step: 0.08 },
        STUN_SKIP:           { instrument: 'drum',    motif: [-12],      gain: 0.3,  channel: 'sfx' },
        STUN_REDUCED:        { instrument: 'harp',    motif: [-2],       gain: 0.35, channel: 'sfx' },
        TRANSFER_STUN:       { instrument: 'harp',    motif: [-4, -2],   gain: 0.4,  channel: 'sfx', step: 0.05 },
        GIVE_KEYWORD:        { instrument: 'harp',    motif: [5, 9],     gain: 0.5,  channel: 'sfx', step: 0.06 },
        GRANT_KEYWORD:       { instrument: 'harp',    motif: [5, 9],     gain: 0.5,  channel: 'sfx', step: 0.06 },
        GRANT_EFFECT:        { instrument: 'harp',    motif: [7, 11],    gain: 0.5,  channel: 'sfx', step: 0.06 },
        REMOVE_KEYWORD:      { instrument: 'harp',    motif: [9, 5],     gain: 0.4,  channel: 'sfx', step: 0.06 },
        REDUCE_HIDE:         { instrument: 'harp',    motif: [2],        gain: 0.4,  channel: 'sfx' },
        REDUCE_RING:         { instrument: 'harp',    motif: [-1],       gain: 0.4,  channel: 'sfx' },

        // ── Combat: summon / transform / move ──────────────────────────────────
        SUMMON_MINION:       { instrument: 'trumpet', motif: [7, 12],    gain: 0.55, channel: 'sfx', step: 0.08 },
        TRANSFORM:           { instrument: 'harp',    motif: [0, 4, 7, 12], gain: 0.55, channel: 'sfx', step: 0.05 },
        MOVE_MINION:         { instrument: 'harp',    motif: [2],        gain: 0.35, channel: 'sfx' },
        LEAP_MOVE:           { instrument: 'harp',    motif: [5, 9],     gain: 0.45, channel: 'sfx', step: 0.05 },
        REDIRECT_DAMAGE:     { instrument: 'harp',    motif: [-3, 2],    gain: 0.5,  channel: 'sfx', step: 0.05 },
        MODIFY_FATIGUE:      { instrument: 'drum',    motif: [-5],       gain: 0.35, channel: 'sfx' },
        MODIFY_GOLD:         { instrument: 'harp',    motif: [12, 14],   gain: 0.5,  channel: 'sfx', step: 0.05 },
        FORCE_CAST:          { instrument: 'harp',    motif: [7, 12, 14],gain: 0.5,  channel: 'sfx', step: 0.05 },
        RECALCULATE_AURAS:   { instrument: 'harp',    motif: [4],        gain: 0.25, channel: 'sfx' },
        AURA_RECALCULATION:  { instrument: 'harp',    motif: [4],        gain: 0.25, channel: 'sfx' },

        // ── Combat: trigger keywords (subtle chime to punctuate) ──────────────
        TRIGGER_RAGE:            { instrument: 'trumpet', motif: [0, 3],   gain: 0.45, channel: 'sfx', step: 0.06 },
        TRIGGER_ASSAULT:         { instrument: 'trumpet', motif: [0, 5],   gain: 0.45, channel: 'sfx', step: 0.06 },
        TRIGGER_CAST:            { instrument: 'harp',    motif: [7, 12],  gain: 0.6,  channel: 'sfx', step: 0.05 },
        TRIGGER_DEATH_TOLL:      { instrument: 'trumpet', motif: [-2, -5], gain: 0.5,  channel: 'sfx', step: 0.07 },
        TRIGGER_ON_ANY_DEATH:    { instrument: 'trumpet', motif: [-3],     gain: 0.4,  channel: 'sfx' },
        TRIGGER_ON_ANY_CAST:     { instrument: 'harp',    motif: [9],      gain: 0.4,  channel: 'sfx' },
        TRIGGER_ON_ANY_SUMMON:   { instrument: 'trumpet', motif: [5],      gain: 0.4,  channel: 'sfx' },
        TRIGGER_START_OF_COMBAT: { instrument: 'trumpet', motif: [0, 4, 7],gain: 0.55, channel: 'sfx', step: 0.1 },
        TRIGGER_ON_DAMAGE:       { instrument: 'drum',    motif: [-4],     gain: 0.35, channel: 'sfx' },
        TRIGGER_ON_ANY_LEAP:     { instrument: 'harp',    motif: [7],      gain: 0.4,  channel: 'sfx' },
        TRIGGER_ON_ANY_DEATH_TOLL:{instrument: 'trumpet', motif: [-5],     gain: 0.4,  channel: 'sfx' },

        // ── Combat flow ────────────────────────────────────────────────────────
        COMBAT_START:        { instrument: 'trumpet', motif: [0, 4, 7, 12], gain: 0.7, channel: 'sfx', step: 0.12 },
        COMBAT_END_WIN:      { instrument: 'trumpet', motif: [0, 4, 7, 12, 16], gain: 0.75, channel: 'sfx', step: 0.13 },
        COMBAT_END_LOSS:     { instrument: 'trumpet', motif: [0, -3, -7, -12], gain: 0.6, channel: 'sfx', step: 0.15 },
        ROUND_START:         { instrument: 'drum',    motif: [0, 0],     gain: 0.35, channel: 'sfx', step: 0.1 },
        TURN_START:          { musicOnly: true },   // intentionally silent — too frequent
        ATTACK_CANCELLED:    { instrument: 'harp',    motif: [-5],       gain: 0.3,  channel: 'sfx' },

        // ── UI: clicks / navigation ────────────────────────────────────────────
        // Use the dedicated `ui` instrument (bright, thin mallet) so menu
        // sounds sit above the music in both timbre and frequency band.
        // All `ui` channel entries are auto-snapped to the current zone's scale.
        UI_CLICK:            { instrument: 'ui',      motif: [12],       gain: 0.32, channel: 'ui' },
        UI_BACK:             { instrument: 'ui',      motif: [7],        gain: 0.28, channel: 'ui' },
        UI_HOVER:            { instrument: 'ui',      motif: [14],       gain: 0.14, channel: 'ui' },
        UI_ERROR:            { instrument: 'ui',      motif: [-5, -7],   gain: 0.4,  channel: 'ui', step: 0.08, keyLock: false },
        UI_CONFIRM:          { instrument: 'ui',      motif: [7, 12],    gain: 0.4,  channel: 'ui', step: 0.05 },
        UI_SELECT:           { instrument: 'ui',      motif: [9],        gain: 0.36, channel: 'ui' },
        UI_DESELECT:         { instrument: 'ui',      motif: [4],        gain: 0.28, channel: 'ui' },

        // ── Event flow ─────────────────────────────────────────────────────────
        // Ring movement, event arrival, and event resolution deliberately have
        // no SOUND_MAP entries — the background music carries the ambience.
        // The callers in game-core.js / events.js no longer dispatch sounds
        // for these moments; only MusicEngine intensity bumps remain.
        SELECTION_TOGGLE:    { instrument: 'ui',      motif: [9],        gain: 0.22, channel: 'ui' },
        SHOP_BUY:            { instrument: 'harp',    motif: [12, 14],   gain: 0.35, channel: 'sfx', step: 0.05 },
        MINION_SWAP:         { instrument: 'ui',      motif: [4, 0],     gain: 0.28, channel: 'ui', step: 0.05 },
        MINION_ABANDON:      { instrument: 'pad',     motif: [-5],       gain: 0.25, channel: 'ui', keyLock: false },
        RING_UPGRADE:        { instrument: 'ui',      motif: [7, 12],    gain: 0.32, channel: 'ui', step: 0.05 },
        ZONE_TRAVEL:         { instrument: 'pad',     motif: [0, 7],     gain: 0.35, channel: 'sfx', step: 0.25 },
        GHOST_READY:         { instrument: 'trumpet', motif: [-5, 0],    gain: 0.4,  channel: 'sfx', step: 0.18 },
        RUN_VICTORY:         { instrument: 'trumpet', motif: [0, 4, 7, 12], gain: 0.55, channel: 'sfx', step: 0.16 },
        RUN_DEFEAT:          { instrument: 'pad',     motif: [0, -3, -7],gain: 0.45, channel: 'sfx', step: 0.35 },

        // ── Music-engine directives (handled by music-engine.js) ──────────────
        MUSIC_INTENSITY_UP:   { musicOnly: true },
        MUSIC_INTENSITY_DOWN: { musicOnly: true },
        MUSIC_ZONE_CHANGE:    { musicOnly: true }
    };

    window.SOUND_MAP = SOUND_MAP;
})();
