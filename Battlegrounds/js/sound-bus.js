// SoundBus - Core audio subsystem.
//
// Owns the single AudioContext, three channel gain nodes (music/sfx/ui) plus
// a master, and exposes three synthesised instruments (harp/trumpet/drum).
// All synthesis happens in JS — no audio files shipped. SOUND_MAP (sound-map.js)
// names these instruments; anything that wants a sound calls SoundBus.playAction
// or SoundBus.playInstrument.
//
// Browsers gate AudioContext behind a user gesture. We create it lazily on the
// first call that needs it, and resume() on every gesture-driven entry point
// just in case it was auto-suspended.

(function () {
    'use strict';

    const STORAGE_KEY = 'autobattler_sound_settings';

    const DEFAULT_SETTINGS = {
        master: 0.7,
        music: 0.5,
        sfx: 0.8,
        ui: 0.6,
        muted: false
    };

    // Cached, loaded lazily.
    let ctx = null;
    let masterGain = null;
    let channelGains = null;   // {music, sfx, ui}
    let musicDuckGain = null;  // sits between channelGains.music and master; SFX dip this
    let settings = loadSettings();
    let resumePromise = null;
    const gestureEvents = ['pointerdown', 'keydown', 'touchstart'];

    // Sidechain ducking defaults. When a non-music sound fires we dip the music
    // bus briefly so the SFX/UI punches through cleanly instead of fighting it.
    const DUCK_AMOUNT       = 0.55;   // music gain during a duck (roughly -5 dB)
    const DUCK_ATTACK_TAU   = 0.012;  // seconds — setTargetAtTime time-constant
    const DUCK_HOLD         = 0.09;   // seconds to stay ducked before releasing
    const DUCK_RELEASE_TAU  = 0.08;   // seconds — release time-constant

    function loadSettings() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            if (!raw) return Object.assign({}, DEFAULT_SETTINGS);
            const parsed = JSON.parse(raw);
            return Object.assign({}, DEFAULT_SETTINGS, parsed);
        } catch (e) {
            return Object.assign({}, DEFAULT_SETTINGS);
        }
    }

    function saveSettings() {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
        } catch (e) { /* quota or private-mode — ignore */ }
    }

    function ensureContext() {
        if (ctx) return ctx;
        const Ctor = window.AudioContext || window.webkitAudioContext;
        if (!Ctor) return null;                 // no Web Audio support
        ctx = new Ctor();

        masterGain = ctx.createGain();
        masterGain.connect(ctx.destination);

        // Music has an extra gain node in the chain (the "duck" bus) that SFX/UI
        // transiently pull down. SFX and UI go direct so they're never ducked.
        musicDuckGain = ctx.createGain();
        musicDuckGain.gain.value = 1.0;
        musicDuckGain.connect(masterGain);

        channelGains = {
            music: ctx.createGain(),
            sfx:   ctx.createGain(),
            ui:    ctx.createGain()
        };
        channelGains.music.connect(musicDuckGain);
        channelGains.sfx.connect(masterGain);
        channelGains.ui.connect(masterGain);

        applyAllGains();
        return ctx;
    }

    // Dip the music bus briefly so an SFX/UI sound can breathe. Chris Wilson /
    // broadcast-style sidechain: cancel in-flight automation, fast attack to
    // `amount`, hold, then exponential release back to unity.
    function duckMusic(amount, holdSeconds) {
        if (!ctx || !musicDuckGain) return;
        amount = (amount != null) ? amount : DUCK_AMOUNT;
        holdSeconds = (holdSeconds != null) ? holdSeconds : DUCK_HOLD;
        const now = ctx.currentTime;
        const g = musicDuckGain.gain;
        // cancelAndHoldAtTime is the clean API but not universal; cancel + hold
        // the latest value manually where it's missing.
        if (typeof g.cancelAndHoldAtTime === 'function') {
            g.cancelAndHoldAtTime(now);
        } else {
            const held = g.value;
            g.cancelScheduledValues(now);
            g.setValueAtTime(held, now);
        }
        g.setTargetAtTime(amount, now, DUCK_ATTACK_TAU);
        g.setTargetAtTime(1.0, now + holdSeconds, DUCK_RELEASE_TAU);
    }

    function applyAllGains() {
        if (!ctx) return;
        const effectiveMaster = settings.muted ? 0 : settings.master;
        masterGain.gain.setTargetAtTime(effectiveMaster, ctx.currentTime, 0.01);
        channelGains.music.gain.setTargetAtTime(settings.music, ctx.currentTime, 0.01);
        channelGains.sfx.gain.setTargetAtTime(settings.sfx,   ctx.currentTime, 0.01);
        channelGains.ui.gain.setTargetAtTime(settings.ui,     ctx.currentTime, 0.01);
    }

    // Must be called from within a user-gesture event handler at least once.
    function resume() {
        ensureContext();
        if (!ctx) return Promise.resolve();
        if (ctx.state === 'running') return Promise.resolve();
        if (resumePromise) return resumePromise;
        resumePromise = ctx.resume().then(() => { resumePromise = null; });
        return resumePromise;
    }

    // Auto-resume on the first page-wide gesture.
    function installGestureUnlock() {
        const unlock = () => {
            resume();
            gestureEvents.forEach(evt => document.removeEventListener(evt, unlock, true));
        };
        gestureEvents.forEach(evt => document.addEventListener(evt, unlock, true));
    }

    // ── Synthesis ──────────────────────────────────────────────────────────────
    // Each instrument returns a node graph that's already started/scheduled.
    // The caller hands us a destination gain node; everything is self-cleaning
    // via node.stop()/onended.

    // Convert semitone offset from concert A4 (440 Hz) to Hz.
    function semitonesToHz(semitones) {
        return 440 * Math.pow(2, semitones / 12);
    }

    // Harp: plucked sine stack. Fundamental + a couple of detuned harmonics,
    // fast attack, exponential decay. Pleasant, non-fatiguing.
    function synthHarp(when, semitones, gain, channel) {
        const freq = semitonesToHz(semitones);
        const dest = channelGains[channel] || channelGains.sfx;
        const env = ctx.createGain();
        env.gain.setValueAtTime(0, when);
        env.gain.linearRampToValueAtTime(gain, when + 0.005);
        env.gain.exponentialRampToValueAtTime(0.0001, when + 1.6);
        env.connect(dest);

        const partials = [
            { mult: 1.0,  level: 1.0  },
            { mult: 2.0,  level: 0.32 },
            { mult: 3.01, level: 0.10 },    // softer upper partials
            { mult: 4.02, level: 0.04 }
        ];
        const stopAt = when + 1.7;
        partials.forEach(p => {
            const osc = ctx.createOscillator();
            osc.type = 'sine';
            osc.frequency.value = freq * p.mult;
            const partialGain = ctx.createGain();
            partialGain.gain.value = p.level;
            osc.connect(partialGain).connect(env);
            osc.start(when);
            osc.stop(stopAt);
        });
    }

    // Trumpet: softened — triangle fundamental + a touch of sawtooth for bite,
    // through a gentle lowpass. Slow attack, short sustain, long release.
    // Much less "blunt" than a raw saw + high-Q bandpass.
    function synthTrumpet(when, semitones, gain, channel) {
        const freq = semitonesToHz(semitones);
        const dest = channelGains[channel] || channelGains.sfx;

        // Two oscillators: triangle for body, low-level sawtooth for a hint of brass.
        const tri = ctx.createOscillator();
        tri.type = 'triangle';
        tri.frequency.value = freq;
        const saw = ctx.createOscillator();
        saw.type = 'sawtooth';
        saw.frequency.value = freq;
        const sawGain = ctx.createGain();
        sawGain.gain.value = 0.18;           // keep the saw subtle

        // Lowpass + resonant bandpass in parallel for a muted formant.
        const lp = ctx.createBiquadFilter();
        lp.type = 'lowpass';
        lp.frequency.value = Math.min(2400, freq * 5);
        lp.Q.value = 0.6;

        const env = ctx.createGain();
        env.gain.setValueAtTime(0, when);
        env.gain.linearRampToValueAtTime(gain * 0.75, when + 0.14);    // slower attack
        env.gain.setValueAtTime(gain * 0.6, when + 0.45);              // gentler sustain
        env.gain.exponentialRampToValueAtTime(0.0001, when + 1.1);     // longer release

        tri.connect(env);
        saw.connect(sawGain).connect(env);
        env.connect(lp).connect(dest);
        tri.start(when); tri.stop(when + 1.15);
        saw.start(when); saw.stop(when + 1.15);
    }

    // Pad: pure ambient bed — detuned sine stack through a soft lowpass, very
    // long attack + release, no transient. Designed to sit under everything and
    // never draw attention. This is what the music engine uses for zone chords.
    //
    // Duration comfortably outlasts two bars at 88 BPM (~5.45 s) with a slow
    // release, so adjacent pads crossfade into each other instead of leaving
    // silent gaps between chords.
    function synthPad(when, semitones, gain, channel) {
        const freq = semitonesToHz(semitones);
        const dest = channelGains[channel] || channelGains.music;
        const dur  = 5.9;

        const lp = ctx.createBiquadFilter();
        lp.type = 'lowpass';
        lp.frequency.value = Math.min(1400, freq * 3.5);    // darker — less sharp
        lp.Q.value = 0.35;

        const env = ctx.createGain();
        env.gain.setValueAtTime(0, when);
        env.gain.linearRampToValueAtTime(gain, when + 0.8);            // slow swell
        env.gain.setValueAtTime(gain, when + dur - 1.2);
        env.gain.exponentialRampToValueAtTime(0.0001, when + dur);     // long tail overlaps into next chord

        env.connect(lp).connect(dest);

        // Three slightly detuned sines (beating = warmth) + one subtle octave.
        const voices = [
            { freq: freq,        detune: -6,  level: 0.45 },
            { freq: freq,        detune: +6,  level: 0.45 },
            { freq: freq,        detune:  0,  level: 0.32 },
            { freq: freq * 2,    detune:  0,  level: 0.12 }
        ];
        voices.forEach(v => {
            const osc = ctx.createOscillator();
            osc.type = 'sine';
            osc.frequency.value = v.freq;
            osc.detune.value = v.detune;
            const g = ctx.createGain();
            g.gain.value = v.level;
            osc.connect(g).connect(env);
            osc.start(when);
            osc.stop(when + dur + 0.1);
        });
    }

    // Drum: short filtered-noise burst + quick downward pitch sine for body.
    // Semitones shifts the body pitch so it can cover kick→tom→snare.
    function synthDrum(when, semitones, gain, channel) {
        const dest = channelGains[channel] || channelGains.sfx;

        // Body — sine dropping an octave in ~80ms.
        const bodyFreq = semitonesToHz(semitones - 24); // low
        const body = ctx.createOscillator();
        body.type = 'sine';
        body.frequency.setValueAtTime(bodyFreq * 2.5, when);
        body.frequency.exponentialRampToValueAtTime(bodyFreq, when + 0.08);
        const bodyEnv = ctx.createGain();
        bodyEnv.gain.setValueAtTime(0, when);
        bodyEnv.gain.linearRampToValueAtTime(gain * 0.9, when + 0.002);
        bodyEnv.gain.exponentialRampToValueAtTime(0.0001, when + 0.25);
        body.connect(bodyEnv).connect(dest);
        body.start(when);
        body.stop(when + 0.3);

        // Transient — short noise burst, band-limited so it reads as a soft
        // "thump" rather than a brittle crack. Lowpass caps the top end, a
        // gentle highpass removes the sub-rumble.
        const noiseDur = 0.12;
        const noiseBuf = ctx.createBuffer(1, Math.floor(ctx.sampleRate * noiseDur), ctx.sampleRate);
        const nd = noiseBuf.getChannelData(0);
        for (let i = 0; i < nd.length; i++) nd[i] = (Math.random() * 2 - 1);
        const noise = ctx.createBufferSource();
        noise.buffer = noiseBuf;
        const hp = ctx.createBiquadFilter();
        hp.type = 'highpass';
        hp.frequency.value = 500;
        const lp = ctx.createBiquadFilter();
        lp.type = 'lowpass';
        lp.frequency.value = 2200;
        const noiseEnv = ctx.createGain();
        noiseEnv.gain.setValueAtTime(gain * 0.22, when);    // was 0.45 — half as crisp
        noiseEnv.gain.exponentialRampToValueAtTime(0.0001, when + 0.09);
        noise.connect(hp).connect(lp).connect(noiseEnv).connect(dest);
        noise.start(when);
        noise.stop(when + noiseDur);
    }

    // UI: glassy mallet — sine fundamental + a quiet inharmonic partial, fast
    // attack, quick decay, highpass so it never muddies the music's midrange.
    // Deliberately thinner and brighter than `harp` so menu sounds occupy a
    // different frequency band than the pads/arpeggios underneath.
    function synthUI(when, semitones, gain, channel) {
        const freq = semitonesToHz(semitones);
        const dest = channelGains[channel] || channelGains.ui;
        const dur  = 0.32;

        const hp = ctx.createBiquadFilter();
        hp.type = 'highpass';
        hp.frequency.value = Math.max(220, freq * 0.85);
        hp.Q.value = 0.5;

        const env = ctx.createGain();
        env.gain.setValueAtTime(0, when);
        env.gain.linearRampToValueAtTime(gain, when + 0.004);
        env.gain.exponentialRampToValueAtTime(0.0001, when + dur);
        env.connect(hp).connect(dest);

        // Fundamental sine — clean, mallet-like body.
        const sine = ctx.createOscillator();
        sine.type = 'sine';
        sine.frequency.value = freq;
        sine.connect(env);
        sine.start(when); sine.stop(when + dur + 0.05);

        // Inharmonic sparkle — 3.01x partial, quiet. Slight detune prevents it
        // lining up with the music's harmonic series, so it reads as "UI tick"
        // rather than "another melody note".
        const spark = ctx.createOscillator();
        spark.type = 'sine';
        spark.frequency.value = freq * 3.01;
        const sparkGain = ctx.createGain();
        sparkGain.gain.value = 0.16;
        spark.connect(sparkGain).connect(env);
        spark.start(when); spark.stop(when + 0.22);
    }

    // Lute: plucked medieval string — stringier than the harp. Sawtooth
    // fundamental (rich in harmonics) run through a resonant lowpass that
    // tracks pitch, with a short noise "pluck" at the very front for the
    // fingernail attack. Fast decay like the harp but woodier overall.
    function synthLute(when, semitones, gain, channel) {
        const freq = semitonesToHz(semitones);
        const dest = channelGains[channel] || channelGains.sfx;
        const dur  = 1.8;

        // Body filter — resonant lowpass that opens briefly on the pluck
        // then closes. Gives the characteristic "twangy" attack.
        const lp = ctx.createBiquadFilter();
        lp.type = 'lowpass';
        lp.Q.value = 2.8;
        lp.frequency.setValueAtTime(Math.min(3200, freq * 6), when);
        lp.frequency.exponentialRampToValueAtTime(Math.max(420, freq * 1.8), when + 0.25);

        const env = ctx.createGain();
        env.gain.setValueAtTime(0, when);
        env.gain.linearRampToValueAtTime(gain, when + 0.006);
        env.gain.exponentialRampToValueAtTime(0.0001, when + dur);
        env.connect(lp).connect(dest);

        // Sawtooth fundamental + a quiet octave above for lute-like double stop.
        const saw = ctx.createOscillator();
        saw.type = 'sawtooth';
        saw.frequency.value = freq;
        saw.connect(env);
        saw.start(when); saw.stop(when + dur + 0.05);

        const octave = ctx.createOscillator();
        octave.type = 'triangle';
        octave.frequency.value = freq * 2;
        const octGain = ctx.createGain();
        octGain.gain.value = 0.22;
        octave.connect(octGain).connect(env);
        octave.start(when); octave.stop(when + dur * 0.7);

        // Fingernail click — tiny noise burst at the attack.
        const clickDur = 0.03;
        const buf = ctx.createBuffer(1, Math.max(1, Math.floor(ctx.sampleRate * clickDur)), ctx.sampleRate);
        const nd = buf.getChannelData(0);
        for (let i = 0; i < nd.length; i++) nd[i] = (Math.random() * 2 - 1);
        const click = ctx.createBufferSource();
        click.buffer = buf;
        const clickHP = ctx.createBiquadFilter();
        clickHP.type = 'highpass';
        clickHP.frequency.value = 1800;
        const clickEnv = ctx.createGain();
        clickEnv.gain.setValueAtTime(gain * 0.18, when);
        clickEnv.gain.exponentialRampToValueAtTime(0.0001, when + clickDur);
        click.connect(clickHP).connect(clickEnv).connect(dest);
        click.start(when); click.stop(when + clickDur);
    }

    // Recorder: wooden flute — triangle wave + a breath-noise shimmer + a
    // subtle vibrato. Slow attack (soft breath), long-ish sustain, gentle
    // release. Occupies the high-mid range and reads as medieval woodwind.
    function synthRecorder(when, semitones, gain, channel) {
        const freq = semitonesToHz(semitones);
        const dest = channelGains[channel] || channelGains.sfx;
        const dur  = 1.3;

        const lp = ctx.createBiquadFilter();
        lp.type = 'lowpass';
        lp.frequency.value = Math.min(3600, freq * 5);
        lp.Q.value = 0.6;

        const env = ctx.createGain();
        env.gain.setValueAtTime(0, when);
        env.gain.linearRampToValueAtTime(gain, when + 0.08);          // soft breath attack
        env.gain.setValueAtTime(gain, when + dur - 0.45);
        env.gain.exponentialRampToValueAtTime(0.0001, when + dur);
        env.connect(lp).connect(dest);

        // Triangle fundamental — the body of the flute tone.
        const tri = ctx.createOscillator();
        tri.type = 'triangle';
        tri.frequency.value = freq;
        tri.connect(env);
        tri.start(when); tri.stop(when + dur + 0.05);

        // 5 Hz vibrato on pitch — gives the living, wooden-flute feel.
        const lfo = ctx.createOscillator();
        lfo.type = 'sine';
        lfo.frequency.value = 5.0;
        const lfoGain = ctx.createGain();
        lfoGain.gain.value = freq * 0.006;              // ±0.6% pitch wobble
        lfo.connect(lfoGain).connect(tri.frequency);
        lfo.start(when); lfo.stop(when + dur + 0.05);

        // Breath noise — very quiet, band-passed around the fundamental's
        // second octave. Sells the "air" character of a recorder.
        const nDur = dur;
        const nBuf = ctx.createBuffer(1, Math.floor(ctx.sampleRate * nDur), ctx.sampleRate);
        const nd = nBuf.getChannelData(0);
        for (let i = 0; i < nd.length; i++) nd[i] = (Math.random() * 2 - 1);
        const noise = ctx.createBufferSource();
        noise.buffer = nBuf;
        const bp = ctx.createBiquadFilter();
        bp.type = 'bandpass';
        bp.frequency.value = freq * 2;
        bp.Q.value = 1.2;
        const nGain = ctx.createGain();
        nGain.gain.setValueAtTime(0, when);
        nGain.gain.linearRampToValueAtTime(gain * 0.06, when + 0.1);
        nGain.gain.exponentialRampToValueAtTime(0.0001, when + dur);
        noise.connect(bp).connect(nGain).connect(dest);
        noise.start(when); noise.stop(when + nDur);
    }

    const INSTRUMENTS = {
        harp:     synthHarp,
        trumpet:  synthTrumpet,
        drum:     synthDrum,
        pad:      synthPad,
        ui:       synthUI,
        lute:     synthLute,
        recorder: synthRecorder
    };

    // ── Throttle ───────────────────────────────────────────────────────────────
    // Prevents the same action spamming itself when the command stream rapid-fires
    // (e.g. an AoE that damages 5 minions in 50ms). Per-action key → last play time.
    const lastPlayedAt = Object.create(null);
    // Default minimum interval between identical playAction() calls, in ms.
    const DEFAULT_THROTTLE_MS = 70;
    // Per-action overrides for actions that fire in rapid bursts.
    const ACTION_THROTTLE_MS = {
        COMBAT_DAMAGE: 60,
        COUNTER_DAMAGE: 60,
        DECLARE_ATTACK: 40,
        DEAL_DAMAGE: 60,
        DEAL_AOE_DAMAGE: 120,
        MULTI_ATTACK: 50,
        AURA_RECALCULATION: 200,
        RECALCULATE_AURAS: 200,
        TRIGGER_ON_ANY_DEATH: 120,
        TRIGGER_ON_ANY_CAST: 120,
        TRIGGER_ON_ANY_SUMMON: 120,
        BUFF_STATS: 90,
        DEBUFF_STATS: 90,
        HEAL: 80,
        UI_HOVER: 100
    };

    // ── Public playback API ────────────────────────────────────────────────────

    function playInstrument(instrument, opts) {
        opts = opts || {};
        if (!ensureContext()) return;
        if (settings.muted) return;
        // We don't await resume() — if the context is still suspended the
        // scheduled sounds will just be silent, which is the expected browser
        // behaviour until the user interacts. The gesture-unlock handler will
        // flip it for all subsequent calls.
        const synth = INSTRUMENTS[instrument];
        if (!synth) return;
        const channel   = opts.channel   || 'sfx';
        const semitones = (opts.semitones || 0);
        const gain      = (opts.gain      != null) ? opts.gain : 0.8;
        const when      = ctx.currentTime + (opts.delay || 0);
        try {
            synth(when, semitones, gain, channel);
        } catch (e) {
            // Never let audio errors bubble into gameplay code.
            if (window.console) console.warn('[SoundBus] synth error', e);
        }
    }

    // Play a whole motif (sequence of notes) on one instrument, spaced by `step`
    // seconds. Used for quick arpeggios/fanfares on action triggers.
    function playMotif(instrument, motif, opts) {
        opts = opts || {};
        const step = opts.step || 0.07;
        (motif || []).forEach((semi, i) => {
            playInstrument(instrument, {
                channel:   opts.channel,
                gain:      opts.gain,
                semitones: semi,
                delay:     (opts.delay || 0) + i * step
            });
        });
    }

    // Resolve an action name against SOUND_MAP (if loaded) and play it.
    // Throttled per-action: identical calls within the minimum interval are
    // silently dropped, preventing bursty duplicates (5-target AoE, etc.)
    // from smearing into a muddy wall of sound.
    function playAction(actionName, overrides) {
        overrides = overrides || {};
        const map = window.SOUND_MAP;
        if (!map) return;
        const def = map[actionName];
        if (!def) return;
        if (def.musicOnly) return;   // music-only directives handled elsewhere

        const now = (typeof performance !== 'undefined' && performance.now)
                    ? performance.now() : Date.now();
        const minInterval = (ACTION_THROTTLE_MS[actionName] != null)
            ? ACTION_THROTTLE_MS[actionName]
            : DEFAULT_THROTTLE_MS;
        if (!overrides.bypassThrottle) {
            const last = lastPlayedAt[actionName] || 0;
            if (now - last < minInterval) return;
            lastPlayedAt[actionName] = now;
        }

        const instrument = overrides.instrument || def.instrument;
        if (!instrument) return;
        const channel = overrides.channel || def.channel || 'sfx';
        let motif = overrides.motif || def.motif || [0];

        // Key-lock: snap UI pitches onto the current zone's scale so menu
        // sounds never clash with the music underneath. Off by default for
        // SFX (drums don't care, pitched combat SFX want to keep their
        // intentional dissonance) but can be forced with def.keyLock.
        const wantsKeyLock = def.keyLock || (channel === 'ui' && def.keyLock !== false);
        if (wantsKeyLock && window.MusicEngine && typeof window.MusicEngine.snapToScale === 'function') {
            motif = motif.map(n => window.MusicEngine.snapToScale(n));
        }

        // Duck the music bus for a non-music sound so it sits atop the bed
        // instead of fighting the pads — but only for sounds loud enough to
        // need the space. Quiet flow-of-play ticks (e.g. every-step event
        // pings) skip the duck so they don't keep the music attenuated.
        const effectiveGain = overrides.gain != null ? overrides.gain : def.gain;
        if (channel !== 'music' && (effectiveGain == null || effectiveGain >= 0.3)) {
            duckMusic();
        }

        // Beat-quantize: defer playback to the next music beat so the sound
        // locks into the song's rhythm. Falls back to immediate when the
        // engine isn't running, so UI snappiness is preserved pre-game.
        let delay = overrides.delay || 0;
        const quantize = overrides.quantize || def.quantize;
        if (quantize === 'beat' && window.MusicEngine && typeof window.MusicEngine.nextBeatDelay === 'function') {
            delay += window.MusicEngine.nextBeatDelay();
        }

        playMotif(instrument, motif, {
            channel: channel,
            gain:    effectiveGain,
            delay:   delay,
            step:    overrides.step    || def.step || 0.07
        });
    }

    // ── Settings API ───────────────────────────────────────────────────────────
    function getSettings() {
        return Object.assign({}, settings);
    }

    function setSetting(key, value) {
        if (!(key in DEFAULT_SETTINGS)) return;
        if (key === 'muted') {
            settings.muted = !!value;
        } else {
            // Clamp 0..1.
            const v = Math.max(0, Math.min(1, Number(value)));
            if (Number.isNaN(v)) return;
            settings[key] = v;
        }
        applyAllGains();
        saveSettings();
    }

    function getContext() { return ctx; }
    function getChannelGain(channel) {
        ensureContext();
        return channelGains ? channelGains[channel] : null;
    }

    window.SoundBus = {
        resume: resume,
        playInstrument: playInstrument,
        playMotif: playMotif,
        playAction: playAction,
        duckMusic: duckMusic,
        getSettings: getSettings,
        setSetting: setSetting,
        getContext: getContext,
        getChannelGain: getChannelGain,
        // Exposed so the music engine can build its own layer graph.
        _ensureContext: ensureContext
    };

    installGestureUnlock();
})();
