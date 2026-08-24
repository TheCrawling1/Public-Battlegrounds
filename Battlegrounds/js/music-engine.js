// MusicEngine - bar-quantised ambient music layered on top of SoundBus.
//
// Runs a simple scheduler (Chris Wilson "two clocks" style) that every bar
// decides what each layer should play. All layers are plucked / bowed
// notes whose decays overlap — there is no sustained synth. Polyphony
// emerges from many short notes at different rates bleeding into each
// other, like a small medieval ensemble.
//
// Layers:
//   - bass:    lute on the chord root / fifth, always on
//   - arp:     harp arpeggio, fades in with intensity
//   - counter: sparse recorder phrase on a 5-bar rotation
//   - drum:    heartbeat pulse, fades in with intensity
//
// Callers push things at it:
//   MusicEngine.start()                - begin the scheduler (gesture-gated)
//   MusicEngine.stop()                 - halt, silence layers
//   MusicEngine.setZone(zoneKey)       - crossfade to that zone's palette
//   MusicEngine.setIntensity(level)    - 0..1, scales drum+harp layer gains
//   MusicEngine.bumpIntensity(delta)   - convenience: setIntensity(current+delta)
//   MusicEngine.enqueueMotif(args)     - schedules a one-off motif on the next bar
//
// The engine is idempotent — calling start() while running is a no-op. It
// tolerates SoundBus absence (silent fallback).

(function () {
    'use strict';

    const BPM = 88;                           // brisk ambient — quick enough to feel alive
    const SECONDS_PER_BEAT = 60 / BPM;
    const BEATS_PER_BAR = 4;
    const SECONDS_PER_BAR = SECONDS_PER_BEAT * BEATS_PER_BAR;
    const LOOKAHEAD_MS = 25;                  // scheduler tick
    const SCHEDULE_AHEAD = 0.2;               // seconds of future to schedule

    // Zone palettes — fundamental note (semitones from A4) + a 4-chord
    // progression (each an interval set over `root`). Progression steps once
    // every 2 bars, so one full cycle = 8 bars. That's short enough to feel
    // familiar, long enough to not feel like a looping ringtone.
    // Keys match config.py ZONES. Unknown keys fall back to DEFAULT_PALETTE.
    //
    // Progressions pick 4 diatonic triads per palette — I / V / vi / IV is the
    // evergreen pop cycle; minor zones use i / VI / III / VII etc.
    // Scale masks — pitch-classes (0..11) that count as "in key" for the palette.
    // snapToScale() uses these to pull UI sounds onto the current tonality so
    // menus don't clash with the music beneath them.
    const SCALE_MAJOR      = [0, 2, 4, 5, 7, 9, 11];
    const SCALE_MINOR      = [0, 2, 3, 5, 7, 8, 10];
    const SCALE_LYDIAN     = [0, 2, 4, 6, 7, 9, 11];
    const SCALE_MIXOLYDIAN = [0, 2, 4, 5, 7, 9, 10];
    const SCALE_LOCRIAN    = [0, 1, 3, 5, 6, 8, 10];

    const DEFAULT_PALETTE = {
        root: -9, name: 'Default', scale: SCALE_MAJOR,
        progression: [ [0,4,7], [7,11,14], [9,12,16], [5,9,12] ] // C / G / Am / F
    };
    const ZONE_PALETTES = {
        crossroads: {
            root: -9, name: 'Crossroads', scale: SCALE_MAJOR,              // C major
            progression: [ [0,4,7], [7,11,14], [9,12,16], [5,9,12] ]        // I  V  vi  IV
        },
        beast_wildlands: {
            root: -14, name: 'Wildlands', scale: SCALE_MINOR,              // G minor
            progression: [ [0,3,7], [8,12,15], [3,7,10], [10,14,17] ]       // i  VI  III  VII
        },
        human_kingdom: {
            root: -2, name: 'Kingdom', scale: SCALE_MAJOR,                 // G major (bright)
            progression: [ [0,4,7,11], [5,9,12], [9,12,16], [7,11,14] ]     // Imaj7 IV vi V
        },
        undead_crypts: {
            root: -16, name: 'Crypts', scale: SCALE_MINOR,                 // F minor
            progression: [ [0,3,7], [5,8,12], [-4,0,3], [7,10,14] ]         // i  iv  VI  v
        },
        fey_grove: {
            root: -7, name: 'Fey Grove', scale: SCALE_LYDIAN,              // D lydian-ish
            progression: [ [0,4,7,14], [7,11,14], [2,6,9], [9,12,16] ]      // I(add9) V ii vi
        },
        construct_foundry: {
            root: -12, name: 'Foundry', scale: SCALE_MIXOLYDIAN,           // A suspended / modal
            progression: [ [0,5,7], [5,10,12], [7,12,14], [2,7,9] ]         // sus cycles
        },
        cult_sanctum: {
            root: -17, name: 'Sanctum', scale: SCALE_LOCRIAN,              // E half-diminished, ominous
            progression: [ [0,3,6,10], [-2,1,5], [3,6,10], [5,8,12] ]
        }
    };

    // Harp arpeggio templates — the pool the engine picks from each bar. Size
    // (7) is chosen to be coprime with pad progression (8 bars) and drum cycle
    // (11 bars) so the three layers almost never re-align into the same combo.
    // LCM(7,8,11) = 616 bars ≈ 4½ minutes before an exact re-alignment.
    const ARP_PATTERNS = [
        [0, 2, 1, 2],           // up-and-back
        [2, 1, 0, 1],           // reverse
        [0, 1, 2, 3],           // straight up
        [2, 0, 1, 0],           // bell-like
        [0, 3, 1, 2],           // angular
        [1, 0, 2, 3],           // wavering
        [3, 2, 1, 0]            // descending
    ];

    // Drum cycle — 11 bars of patterns, per intensity tier. Each entry is a
    // list of beats (0..3) that get a hit; empty = rest.
    const DRUM_CYCLE_LOW  = [
        [0], [], [0, 2], [0], [0], [], [0, 2], [],
        [0], [0, 2], []
    ];
    const DRUM_CYCLE_MID  = [
        [0, 2], [0], [0, 2, 3], [0, 2], [0, 2], [0, 3], [0, 2],
        [0, 1, 2], [0, 2], [0, 2, 3], [0]
    ];
    const DRUM_CYCLE_HIGH = [
        [0, 1, 2], [0, 2, 3], [0, 2], [0, 1, 2, 3], [0, 2, 3], [0, 1, 2],
        [0, 2], [0, 1, 2, 3], [0, 1, 3], [0, 2, 3], [0, 1, 2]
    ];

    let running = false;
    let schedulerTimer = null;
    let nextBarTime = 0;                      // AudioContext time of next bar start
    let currentZone = 'crossroads';
    let currentPalette = ZONE_PALETTES[currentZone];
    let targetPalette = currentPalette;
    let crossfade = 1;                        // 0..1, 1 = fully on current
    let intensity = 0;                        // 0..1
    let baselineIntensity = 0.2;              // what intensity drifts toward over time
    let barCounter = 0;                       // global bar index since start

    // One-off motifs scheduled for the next bar. Each entry is {instrument, motif, gain, step}.
    const pendingMotifs = [];

    // ±15ms humanize jitter, applied to every scheduled note. Enough to break
    // up the sample-locked grid feel without making anything sound loose.
    const HUMANIZE_SEC = 0.015;
    function jitter() { return (Math.random() - 0.5) * 2 * HUMANIZE_SEC; }

    function getBus() { return window.SoundBus; }

    function activePaletteNow() {
        return crossfade < 1 ? currentPalette : targetPalette;
    }

    // Seconds from ctx.currentTime to the next beat downbeat. SoundBus uses
    // this to quantize `quantize:'beat'` actions onto the music's grid so
    // they lock into the song rhythmically (max ~0.88s lag at 68 BPM).
    // Returns 0 when the engine isn't running — callers fall back to
    // immediate playback, preserving snappy UI feel.
    function nextBeatDelay() {
        const bus = getBus();
        if (!bus || !running) return 0;
        const ctx = bus.getContext();
        if (!ctx) return 0;
        const now = ctx.currentTime;
        // nextBarTime is the next bar to be *scheduled*, so the bar currently
        // sounding started one bar earlier.
        const barStart = nextBarTime - SECONDS_PER_BAR;
        const elapsed = now - barStart;
        const nextBeatIdx = Math.floor(elapsed / SECONDS_PER_BEAT) + 1;
        const nextT = barStart + nextBeatIdx * SECONDS_PER_BEAT;
        return Math.max(0, nextT - now);
    }

    // Snap a semitone (offset from A4) onto the nearest in-scale pitch for the
    // current palette. Used by SoundBus to key-lock UI sounds so they sit on
    // the same tonal center as the music.
    function snapToScale(semi) {
        const palette = activePaletteNow();
        const scale = palette.scale || SCALE_MAJOR;
        const root = palette.root;
        const delta = semi - root;
        const octave = Math.floor(delta / 12);
        const pc = ((delta % 12) + 12) % 12;
        let best = scale[0], bestDist = 13;
        for (let i = 0; i < scale.length; i++) {
            const d = Math.abs(pc - scale[i]);
            if (d < bestDist) { bestDist = d; best = scale[i]; }
        }
        return root + octave * 12 + best;
    }

    function start() {
        if (running) return;
        const bus = getBus();
        if (!bus) return;
        const ctx = bus._ensureContext();
        if (!ctx) return;
        bus.resume();                          // no-op if already running or no gesture yet
        running = true;
        barCounter = 0;
        nextBarTime = ctx.currentTime + 0.1;   // tiny offset so first schedule lands in the future
        tick();
    }

    function stop() {
        running = false;
        if (schedulerTimer) {
            clearTimeout(schedulerTimer);
            schedulerTimer = null;
        }
    }

    function tick() {
        if (!running) return;
        const bus = getBus();
        const ctx = bus && bus.getContext();
        if (!ctx) { schedulerTimer = setTimeout(tick, LOOKAHEAD_MS); return; }

        // Schedule any bars whose start falls within the lookahead window.
        while (nextBarTime < ctx.currentTime + SCHEDULE_AHEAD) {
            scheduleBar(nextBarTime);
            nextBarTime += SECONDS_PER_BAR;
        }
        schedulerTimer = setTimeout(tick, LOOKAHEAD_MS);
    }

    function scheduleBar(barTime) {
        const bus = getBus();
        if (!bus) return;
        const ctxNow = bus.getContext().currentTime;
        const delayTo = t => Math.max(0, t - ctxNow);

        // Advance crossfade toward 1 each bar (≈2-bar crossfade).
        if (crossfade < 1) {
            crossfade = Math.min(1, crossfade + 0.5);
            if (crossfade >= 1) currentPalette = targetPalette;
        }
        const activePalette = crossfade < 1 ? currentPalette : targetPalette;

        // Independent per-layer cycle counters. Chord progression is 8 bars
        // (4 chords × 2 bars); harp picks from a 7-entry pool, drums from an
        // 11-entry cycle, counter-melody gates on a 5-bar rotation. Cycle
        // lengths 5, 7, 8, 11 are all pairwise coprime, so the combined
        // layer pattern only exactly realigns every 5·7·8·11 = 3080 bars.
        const progressionLen = activePalette.progression.length;    // typically 4
        const phraseStep     = Math.floor(barCounter / 2) % progressionLen;
        const chord          = activePalette.progression[phraseStep];
        const harpStep       = barCounter % ARP_PATTERNS.length;    // len 7
        const drumStep       = barCounter % 11;
        const counterStep    = barCounter % 5;
        const bassOdd        = (barCounter % 2 === 1);

        // ── Bass line (lute) ──────────────────────────────────────────────
        // Soft, low lute plucks that always play (even at intensity 0).
        // The steady train of low notes and their decays act as the bed;
        // they bleed into the arp/counter voices for polyphony instead of
        // us sustaining a synth. Root on beat 1 every bar; fifth on beat 3
        // of even bars so the rhythm doesn't feel mechanical.
        const bassRoot  = activePalette.root + chord[0] - 12;   // low octave
        const fifthIdx  = chord.length >= 3 ? 2 : chord.length - 1;
        const bassFifth = activePalette.root + chord[fifthIdx] - 12;
        bus.playInstrument('lute', {
            semitones: bassRoot,
            gain:      0.13,
            channel:   'music',
            delay:     delayTo(barTime) + jitter()
        });
        if (!bassOdd) {
            bus.playInstrument('lute', {
                semitones: bassFifth,
                gain:      0.10,
                channel:   'music',
                delay:     delayTo(barTime + 2 * SECONDS_PER_BEAT) + jitter()
            });
        }

        // ── Mid arpeggio ──────────────────────────────────────────────────
        // Arpeggio pattern chosen from a 7-entry pool so the phrase doesn't
        // line up with the 4-step chord progression. Plays on beats 1 & 3
        // when intensity is moderate, adds beat 2.5 pickup when higher.
        if (intensity > 0.05) {
            const pattern = ARP_PATTERNS[harpStep];
            const chordUp = chord.slice();
            // Pad chord out to 4 notes if needed, by duplicating the top.
            while (chordUp.length < 4) chordUp.push(chordUp[chordUp.length - 1] + 5);
            const beats = intensity > 0.55 ? [0, 2, 2.5]
                        : intensity > 0.25 ? [0, 2]
                        : [1];                      // single sparse stroke at low intensity
            beats.forEach(beat => {
                const baseT = barTime + beat * SECONDS_PER_BEAT;
                pattern.forEach((step, i) => {
                    // Stochastic rests — up to 15% chance to drop a note at
                    // low intensity, 0 when driving hard. Keeps quiet
                    // sections from feeling mechanical.
                    if (intensity < 0.6 && Math.random() < 0.15) return;
                    bus.playInstrument('harp', {
                        semitones: activePalette.root + chordUp[step % chordUp.length] + 12,
                        gain:      0.07 * Math.min(1, intensity + 0.25),
                        channel:   'music',
                        delay:     delayTo(baseT) + i * (SECONDS_PER_BEAT * 0.22) + jitter()
                    });
                });
            });
        }

        // ── Counter-melody (recorder) ─────────────────────────────────────
        // Sparse high-range phrases on a 5-bar rotation — plays on two of
        // every five bars at different beats, so it floats above the arp
        // without turning into another regular line. Recorder's soft breath
        // attack lets it sit gently on top rather than cutting through.
        if (intensity > 0.2 && (counterStep === 1 || counterStep === 3)) {
            const pickIdx  = (harpStep + counterStep) % chord.length;
            const beat     = counterStep === 1 ? 3 : 1.5;
            bus.playInstrument('recorder', {
                semitones: activePalette.root + chord[pickIdx] + 12,
                gain:      0.08 * Math.min(1, intensity + 0.2),
                channel:   'music',
                delay:     delayTo(barTime + beat * SECONDS_PER_BEAT) + jitter()
            });
        }

        // Drums — tier-selected 11-bar cycle steps independently of the
        // progression. Intensity tiers:
        // Low  (0.25..0.55): quiet heartbeat, soft
        // Mid  (0.55..0.8):  back-beat fills
        // High (0.8+):       driving, all-beat variants
        if (intensity > 0.25) {
            let cycle   = DRUM_CYCLE_LOW;
            let gainMul = 0.12;
            if (intensity > 0.55) { cycle = DRUM_CYCLE_MID;  gainMul = 0.18; }
            if (intensity > 0.8)  { cycle = DRUM_CYCLE_HIGH; gainMul = 0.24; }
            const beats = cycle[drumStep % cycle.length];
            beats.forEach(beat => {
                bus.playInstrument('drum', {
                    semitones: activePalette.root,
                    gain:      gainMul,
                    channel:   'music',
                    delay:     delayTo(barTime + beat * SECONDS_PER_BEAT) + jitter()
                });
            });
        }

        // Drain action-enqueued motifs — scheduled on the bar downbeat.
        while (pendingMotifs.length) {
            const m = pendingMotifs.shift();
            bus.playMotif(m.instrument, m.motif, {
                gain:    m.gain,
                step:    m.step,
                channel: m.channel || 'music',
                delay:   delayTo(barTime)
            });
        }

        // Intensity ebbs toward the baseline so the pace relaxes between events.
        // ~5% of the delta per bar → roughly 14 bars to half-recover.
        if (intensity !== baselineIntensity) {
            intensity += (baselineIntensity - intensity) * 0.05;
            if (Math.abs(intensity - baselineIntensity) < 0.005) intensity = baselineIntensity;
        }

        barCounter++;
    }

    function setZone(zoneKey) {
        const next = ZONE_PALETTES[zoneKey] || DEFAULT_PALETTE;
        if (next === targetPalette) return;
        targetPalette = next;
        currentZone = zoneKey;
        crossfade = 0;
    }

    function setIntensity(level) {
        intensity = Math.max(0, Math.min(1, Number(level) || 0));
    }

    function bumpIntensity(delta) {
        setIntensity(intensity + (Number(delta) || 0));
    }

    // Baseline is where intensity drifts to over time. Set this when the game
    // moves into a new "mood" (quiet exploration vs. tense combat etc.);
    // bumpIntensity still gives short-term peaks on top.
    function setBaselineIntensity(level) {
        baselineIntensity = Math.max(0, Math.min(1, Number(level) || 0));
    }

    function enqueueMotif(args) {
        if (!args || !args.instrument) return;
        pendingMotifs.push({
            instrument: args.instrument,
            motif:      args.motif || [0],
            gain:       args.gain  != null ? args.gain : 0.5,
            step:       args.step  || 0.08,
            channel:    args.channel || 'music'
        });
    }

    function getState() {
        const phraseLen = targetPalette.progression.length;
        return {
            running:     running,
            bpm:         BPM,
            zone:        currentZone,
            paletteName: targetPalette.name,
            intensity:   intensity,
            phraseStep:  Math.floor(barCounter / 2) % phraseLen,
            phraseLen:   phraseLen,
            bar:         barCounter
        };
    }

    function listZones() {
        return Object.keys(ZONE_PALETTES);
    }

    window.MusicEngine = {
        start: start,
        stop: stop,
        setZone: setZone,
        setIntensity: setIntensity,
        bumpIntensity: bumpIntensity,
        setBaselineIntensity: setBaselineIntensity,
        enqueueMotif: enqueueMotif,
        snapToScale: snapToScale,
        nextBeatDelay: nextBeatDelay,
        getState: getState,
        listZones: listZones
    };
})();
