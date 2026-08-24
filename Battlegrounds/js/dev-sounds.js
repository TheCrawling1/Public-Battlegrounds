// Sound Studio controller — audition every sound, tweak mixer, drive the
// music engine manually. Operates entirely on window.SoundBus / SOUND_MAP /
// MusicEngine; zero backend calls.

(function () {
    'use strict';

    const CATEGORIES = [
        ['Combat: attack / damage', ['DECLARE_ATTACK','COMBAT_DAMAGE','COUNTER_DAMAGE','MULTI_ATTACK','FATIGUE_DAMAGE','DEAL_DAMAGE','DEAL_AOE_DAMAGE']],
        ['Combat: life / death',    ['DEATH','DESTROY_MINION','REMOVE_FROM_BAND','HEAL','PREVENT_DEATH','ETHEREAL_SAVE']],
        ['Combat: buffs / stats',   ['BUFF_STATS','DEBUFF_STATS','PERMANENT_STAT_GAIN','COPY_STATS','DIVIDE_ATTACK']],
        ['Combat: status effects',  ['STUN','APPLY_STUN','STUN_SKIP','STUN_REDUCED','TRANSFER_STUN','GIVE_KEYWORD','GRANT_KEYWORD','GRANT_EFFECT','REMOVE_KEYWORD','REDUCE_HIDE','REDUCE_RING']],
        ['Combat: summon / move',   ['SUMMON_MINION','TRANSFORM','MOVE_MINION','LEAP_MOVE','REDIRECT_DAMAGE','MODIFY_FATIGUE','MODIFY_GOLD','FORCE_CAST','RECALCULATE_AURAS','AURA_RECALCULATION']],
        ['Combat: triggers',        ['TRIGGER_RAGE','TRIGGER_ASSAULT','TRIGGER_CAST','TRIGGER_DEATH_TOLL','TRIGGER_ON_ANY_DEATH','TRIGGER_ON_ANY_CAST','TRIGGER_ON_ANY_SUMMON','TRIGGER_START_OF_COMBAT','TRIGGER_ON_DAMAGE','TRIGGER_ON_ANY_LEAP','TRIGGER_ON_ANY_DEATH_TOLL']],
        ['Combat: flow',            ['COMBAT_START','COMBAT_END_WIN','COMBAT_END_LOSS','ROUND_START','TURN_START','ATTACK_CANCELLED']],
        ['UI',                      ['UI_CLICK','UI_BACK','UI_HOVER','UI_ERROR','UI_CONFIRM','UI_SELECT','UI_DESELECT']],
        ['Events',                  ['SELECTION_TOGGLE','SHOP_BUY','MINION_SWAP','MINION_ABANDON','RING_UPGRADE','ZONE_TRAVEL','GHOST_READY','RUN_VICTORY','RUN_DEFEAT']],
        ['Music-only (no SFX)',     ['MUSIC_INTENSITY_UP','MUSIC_INTENSITY_DOWN','MUSIC_ZONE_CHANGE']]
    ];

    // Per-action pitch/gain overrides set by the user in the Studio UI.
    const overrides = {};

    function $(id) { return document.getElementById(id); }

    // ── Mixer ──────────────────────────────────────────────────────────────────

    function renderMixer() {
        if (!window.SoundBus) return;
        const s = window.SoundBus.getSettings();
        ['master','music','sfx','ui'].forEach(k => {
            const slider = $('mix-' + k);
            const label  = $('mix-' + k + '-val');
            slider.value = Math.round(s[k] * 100);
            label.textContent = Math.round(s[k] * 100) + '%';
            slider.oninput = () => {
                const v = Number(slider.value) / 100;
                window.SoundBus.setSetting(k, v);
                label.textContent = slider.value + '%';
            };
        });
        const muted = $('mix-muted');
        muted.checked = !!s.muted;
        muted.onchange = () => {
            window.SoundBus.setSetting('muted', muted.checked);
            if (!muted.checked) window.SoundBus.resume();
        };
    }

    // ── Instrument quick-test ──────────────────────────────────────────────────

    function setupInstrumentTest() {
        const semi = $('inst-semi');
        const gain = $('inst-gain');
        const semiVal = $('inst-semi-val');
        const gainVal = $('inst-gain-val');
        semi.oninput = () => { semiVal.textContent = semi.value; };
        gain.oninput = () => { gainVal.textContent = gain.value + '%'; };
    }

    window.studioPlayInstrument = function (instrument) {
        if (!window.SoundBus) return;
        window.SoundBus.resume();
        window.SoundBus.playInstrument(instrument, {
            semitones: Number($('inst-semi').value) || 0,
            gain:      Number($('inst-gain').value) / 100,
            channel:   $('inst-channel').value
        });
    };

    // ── Music engine controls ──────────────────────────────────────────────────

    function setupMusicEngine() {
        if (!window.MusicEngine) return;

        const zoneSel = $('music-zone');
        window.MusicEngine.listZones().forEach(z => {
            const opt = document.createElement('option');
            opt.value = z; opt.textContent = z;
            zoneSel.appendChild(opt);
        });
        zoneSel.onchange = () => window.MusicEngine.setZone(zoneSel.value);

        const intensity = $('music-intensity');
        const intensityVal = $('music-intensity-val');
        intensity.oninput = () => {
            const v = Number(intensity.value) / 100;
            window.MusicEngine.setIntensity(v);
            intensityVal.textContent = intensity.value + '%';
        };
        window.MusicEngine.setIntensity(Number(intensity.value) / 100);

        setInterval(updateMusicStatus, 500);
    }

    function updateMusicStatus() {
        if (!window.MusicEngine) return;
        const s = window.MusicEngine.getState();
        $('music-status').textContent =
            (s.running ? '▶ playing' : '■ stopped') +
            ` | ${s.paletteName} | intensity ${(s.intensity*100).toFixed(0)}%`;
    }

    window.studioMusicStart = function () {
        if (!window.SoundBus || !window.MusicEngine) return;
        window.SoundBus.resume();
        window.MusicEngine.start();
    };
    window.studioMusicStop = function () {
        if (!window.MusicEngine) return;
        window.MusicEngine.stop();
    };
    window.studioMusicBump = function (delta) {
        if (!window.MusicEngine) return;
        window.MusicEngine.bumpIntensity(delta);
        const s = window.MusicEngine.getState();
        $('music-intensity').value = Math.round(s.intensity * 100);
        $('music-intensity-val').textContent = Math.round(s.intensity * 100) + '%';
    };
    window.studioMusicEnqueue = function (instrument) {
        if (!window.MusicEngine) return;
        window.MusicEngine.enqueueMotif({
            instrument: instrument,
            motif:      instrument === 'drum' ? [0, 0, -2] : [0, 7, 12],
            gain:       0.5,
            step:       0.12
        });
    };

    // ── SOUND_MAP list ─────────────────────────────────────────────────────────

    function renderSoundMap() {
        const container = $('sound-list');
        if (!container || !window.SOUND_MAP) return;
        container.innerHTML = '';

        const seen = new Set();
        CATEGORIES.forEach(([heading, keys]) => {
            const section = document.createElement('div');
            section.className = 'category-section';
            section.innerHTML = `<h3>${heading}</h3><div class="sound-grid" id="grid-${slug(heading)}"></div>`;
            container.appendChild(section);
            const grid = section.querySelector('.sound-grid');
            keys.forEach(key => {
                seen.add(key);
                if (window.SOUND_MAP[key]) grid.appendChild(renderSoundRow(key, window.SOUND_MAP[key]));
            });
        });

        // Catch-all: any SOUND_MAP keys not in CATEGORIES.
        const leftoverKeys = Object.keys(window.SOUND_MAP).filter(k => !seen.has(k));
        if (leftoverKeys.length) {
            const section = document.createElement('div');
            section.className = 'category-section';
            section.innerHTML = `<h3>Other</h3><div class="sound-grid"></div>`;
            container.appendChild(section);
            const grid = section.querySelector('.sound-grid');
            leftoverKeys.forEach(k => grid.appendChild(renderSoundRow(k, window.SOUND_MAP[k])));
        }
    }

    function slug(s) { return s.toLowerCase().replace(/[^a-z0-9]+/g, '-'); }

    function renderSoundRow(key, def) {
        const row = document.createElement('div');
        row.className = 'sound-row' + (def.musicOnly ? ' music' : '');
        const desc = def.musicOnly
            ? '<span class="meta">music-only directive</span>'
            : `<span class="meta">${def.instrument} · [${(def.motif||[0]).join(',')}] · ch ${def.channel||'sfx'}</span>`;
        row.innerHTML = `
            <div>
                <div class="name">${key}</div>
                ${desc}
            </div>
            <input type="number" class="semi" value="0" step="1" style="width:60px;" title="Pitch offset (semitones)">
            <input type="range" class="gain" min="0" max="100" value="100" style="width:90px;" title="Gain override">
            <button class="btn small" data-key="${key}">▶</button>
        `;
        const btn = row.querySelector('button');
        const semi = row.querySelector('.semi');
        const gain = row.querySelector('.gain');
        btn.onclick = () => playFromStudio(key, def, Number(semi.value) || 0, Number(gain.value) / 100);
        return row;
    }

    function playFromStudio(key, def, semiOffset, gainMult) {
        if (!window.SoundBus) return;
        window.SoundBus.resume();
        if (def.musicOnly) {
            // Interpret the directive so the Studio button still does something useful.
            if (key === 'MUSIC_INTENSITY_UP' && window.MusicEngine) window.MusicEngine.bumpIntensity(+0.1);
            if (key === 'MUSIC_INTENSITY_DOWN' && window.MusicEngine) window.MusicEngine.bumpIntensity(-0.1);
            return;
        }
        const motif = (def.motif || [0]).map(s => s + semiOffset);
        window.SoundBus.playMotif(def.instrument, motif, {
            gain:    (def.gain != null ? def.gain : 0.8) * gainMult,
            step:    def.step || 0.07,
            channel: def.channel || 'sfx'
        });
    }

    // ── Autoplay unlock banner ─────────────────────────────────────────────────

    function checkUnlock() {
        if (!window.SoundBus) return;
        const ctx = window.SoundBus.getContext();
        const banner = $('unlock-banner');
        if (!banner) return;
        if (!ctx || ctx.state === 'running') {
            banner.style.display = 'none';
        } else {
            banner.style.display = 'block';
        }
    }

    window.studioUnlockAudio = function () {
        if (window.SoundBus) window.SoundBus.resume().then(checkUnlock);
    };

    // ── Init ───────────────────────────────────────────────────────────────────

    document.addEventListener('DOMContentLoaded', function () {
        renderMixer();
        setupInstrumentTest();
        setupMusicEngine();
        renderSoundMap();
        checkUnlock();
        setInterval(checkUnlock, 1000);
    });
})();
