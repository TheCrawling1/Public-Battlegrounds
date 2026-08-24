// Headless frontend test for the snapshot-based combat player.
//
// Loads the real Battlegrounds/js/combat.js into a jsdom window, generates
// combat data via a Python subprocess, and asserts that after every command
// the frontend band state equals the server-authored snapshot for that
// command. Also exercises jumpToCommandIndex and skipToEndCommand.
//
// Run with: node tests/test_snapshot_player_frontend.js

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');
const { JSDOM } = require('jsdom');

const REPO_ROOT = path.resolve(__dirname, '..');
const BATTLEGROUNDS = path.join(REPO_ROOT, 'Battlegrounds');
const COMBAT_JS_PATH = path.join(BATTLEGROUNDS, 'js', 'combat.js');

const COMBAT_JS = fs.readFileSync(COMBAT_JS_PATH, 'utf8');

// Appended to combat.js before injection. combat.js uses `let` at the top of
// the script, which (in indirect eval) does not leak to the global scope.
// This patch closes over those bindings and exposes them as window methods
// so the test can read interpreter position / queue state from Node.
// It also wraps applySnapshotForCommand to record the last seq actually
// applied (deaths in a batch are skipped by design).
const PATCH_SUFFIX = `
;(function () {
    const __origApply = applySnapshotForCommand;
    applySnapshotForCommand = function (cmd) {
        if (cmd && typeof cmd.seq === 'number') {
            window.__lastAppliedSeq = cmd.seq;
        }
        return __origApply(cmd);
    };
    window.__getInterpreterPosition = function () { return interpreterPosition; };
    window.__getIsProcessing = function () { return isProcessingAnimation; };
    window.__getQueueLength = function () { return combatAnimationQueue.length; };
})();
`;

// ----- Python driver -----------------------------------------------------
// Returns a raw JSON string. Callers must parse via the jsdom window's
// JSON.parse so arrays/objects come from the right realm — otherwise
// combat.js's `obj instanceof Array` check in deepCopy returns false and
// the band becomes a plain object.
function generateCombatDataJson(playerNames, enemyNames) {
    const py = `
import sys, os, io, json, contextlib
sys.path.insert(0, '${BATTLEGROUNDS}')
# Silence module-level validation prints so stdout only contains JSON.
_null = io.StringIO()
with contextlib.redirect_stdout(_null):
    import copy
    from game_engine.combat_system import CombatSystem
    from minions import MINIONS

def find(name):
    for _tier, ms in MINIONS.items():
        for m in ms:
            if m['name'] == name:
                return copy.deepcopy(m)
    raise KeyError(name)

def make(name, cid):
    m = find(name)
    m['_combat_id'] = cid
    return m

player_names = ${JSON.stringify(playerNames)}
enemy_names = ${JSON.stringify(enemyNames)}
p = [make(n, f'p{i}') for i, n in enumerate(player_names)]
e = [make(n, f'e{i}') for i, n in enumerate(enemy_names)]

with contextlib.redirect_stdout(_null):
    result = CombatSystem.resolve_combat(p, e, run=None)

sys.stdout.write(json.dumps(result['interpreter_data']))
`;
    const out = spawnSync('python3', ['-c', py], { maxBuffer: 128 * 1024 * 1024 });
    if (out.status !== 0) {
        throw new Error(`python failed (status ${out.status}): ${out.stderr.toString('utf8')}`);
    }
    return out.stdout.toString('utf8');
}

// Parse the JSON string inside the jsdom window. Returns data whose arrays
// are jsdom-realm arrays (so combat.js's `instanceof Array` works).
function parseInWindow(window, jsonStr) {
    return window.JSON.parse(jsonStr);
}

// ----- jsdom harness -----------------------------------------------------
function makeWindow() {
    const dom = new JSDOM(
        '<!DOCTYPE html><html><body><div class="combat-log-content"></div></body></html>',
        { runScripts: 'outside-only' }
    );
    const { window } = dom;

    // Silence combat.js's chatty console.log inside the test run. Real errors
    // still surface via throws. Set TEST_VERBOSE=1 to re-enable.
    if (!process.env.TEST_VERBOSE) {
        window.console.log = () => {};
        window.console.info = () => {};
        window.console.warn = () => {};
        window.console.error = () => {};
    }

    // Globals combat.js reads from window / top-level scope.
    window.currentRunId = null;
    window.gameData = null;
    window.autoCombatInProgress = false;
    window.autoCombatInterval = null;

    // UI functions. All no-ops in the headless test.
    window.updateDisplay = () => {};
    window.apiCall = async () => ({});
    window.processRunEnd = () => {};
    window.updateActiveLogEntry = () => {};
    window.scrollToActiveLogEntry = () => {};
    window.highlightAttacker = () => {};
    window.highlightDefender = () => {};
    window.applyDamageVisual = () => {};
    window.applyObliterateVisual = () => {};
    window.applyHealVisual = () => {};
    window.applyBuffVisual = () => {};
    window.applyDebuffVisual = () => {};
    window.applySummonVisual = () => {};
    window.applyPermanentStatVisual = () => {};
    window.applyMoveVisual = () => {};
    window.applyStunVisual = () => {};
    window.applyKeywordVisual = () => {};
    window.markMinionDead = () => {};
    window.showTriggerAnimation = () => {};
    window.applyTransformVisual = () => {};
    window.applyPreventDeathVisual = () => {};
    window.applyHideVisual = () => {};
    window.applyRingVisual = () => {};
    window.showMultiAttackIndicator = () => {};
    window.showFatigueDamage = () => {};
    window.showStunSkip = () => {};

    // Make animation durations effectively zero so setTimeout(0) resolves
    // on the next tick. All other animation hooks are no-ops.
    window.animationFunctions = {
        getAnimationDebugInfo: () => ({ globalSpeed: 1000000 }),
        playAnimation: () => null,
        queueAttackAnimation: () => {},
        cancelAllAnimations: () => {},
        stopAllAttackAnimations: () => {},
        stopAllDamageNumbers: () => {},
        cleanupAllAnimationDOM: () => {},
        cleanupAnimationsByTargetId: () => {},
        pauseAllAnimations: () => {},
        resumeAllAnimations: () => {},
        setAnimationSpeed: () => {},
        showDamageNumber: () => {},
        showHealNumber: () => {},
        showBuffNumber: () => {},
    };

    // SoundBus / MusicEngine intentionally undefined — combat.js guards.

    // jsdom doesn't implement requestAnimationFrame; combat.js uses it for
    // scroll restoration inside jumpToCommandIndex.
    if (typeof window.requestAnimationFrame !== 'function') {
        window.requestAnimationFrame = (cb) => setTimeout(cb, 0);
    }

    window.eval(COMBAT_JS + PATCH_SUFFIX);
    return window;
}

// Wait until the animation queue drains. Resolved timeouts inside jsdom run
// on Node's event loop, so awaiting a setImmediate tick per poll is plenty.
async function drain(window, maxTicks = 5000) {
    for (let i = 0; i < maxTicks; i++) {
        // eslint-disable-next-line no-await-in-loop
        await new Promise((r) => setImmediate(r));
        if (!window.__getIsProcessing() && window.__getQueueLength() === 0) return;
    }
    throw new Error('animation queue did not drain after ' + maxTicks + ' ticks');
}

// ----- assertions --------------------------------------------------------
function bandToCompareShape(band) {
    return band.map((m) => ({
        _combat_id: m._combat_id,
        name: m.name,
        health: m.health,
        attack: m.attack,
        position: m.position,
        keywords: (m.keywords || []).slice().sort(),
        stun_count: m.stun_count || 0,
        hide_remaining: m.hide_remaining || 0,
        permanent_ring_count: m.permanent_ring_count || 0,
        golden: !!m.golden,
    }));
}

function assertBandsMatch(actualBand, expectedBand, label) {
    const a = bandToCompareShape(actualBand);
    const e = bandToCompareShape(expectedBand);
    // Order-insensitive compare by _combat_id
    a.sort((x, y) => (x._combat_id < y._combat_id ? -1 : 1));
    e.sort((x, y) => (x._combat_id < y._combat_id ? -1 : 1));
    if (a.length !== e.length) {
        throw new Error(`${label}: band size mismatch: actual=${a.length} expected=${e.length}`);
    }
    for (let i = 0; i < a.length; i++) {
        const am = a[i];
        const em = e[i];
        for (const k of Object.keys(em)) {
            const av = am[k];
            const ev = em[k];
            if (Array.isArray(av) || Array.isArray(ev)) {
                if (JSON.stringify(av) !== JSON.stringify(ev)) {
                    throw new Error(
                        `${label}: ${am._combat_id}.${k} array mismatch:\n  actual=  ${JSON.stringify(av)}\n  expected=${JSON.stringify(ev)}`
                    );
                }
            } else if (av !== ev) {
                throw new Error(
                    `${label}: ${am._combat_id}.${k} mismatch: actual=${JSON.stringify(av)} expected=${JSON.stringify(ev)}`
                );
            }
        }
    }
}

function assertSnapshotMatches(window, seq, data, label) {
    const state = window.combatFunctions.getFrontendCombatState();
    const step = data.steps[seq];
    const cmdLabel = `${label} seq=${seq} cmd=${step.command.cmd}`;
    assertBandsMatch(state.player_band, step.state_after.player_band, `${cmdLabel} player_band`);
    assertBandsMatch(state.enemy_band, step.state_after.enemy_band, `${cmdLabel} enemy_band`);
}

// ----- scenarios ---------------------------------------------------------
const SCENARIOS = [
    { label: 'basic 2v2',        player: ['Soldier', 'Farmer'],              enemy: ['Huntsman', 'Zombie'] },
    { label: 'assault trigger',  player: ['Huntsman', 'Soldier'],            enemy: ['Zombie', 'Zombie'] },
    { label: 'death_toll',       player: ['Skeleton', 'Soldier'],            enemy: ['Bear', 'Bear'] },
    { label: 'multi_attack Bear',player: ['Bear', 'Farmer'],                 enemy: ['Zombie', 'Zombie', 'Zombie'] },
    { label: 'guard Iron Wall',  player: ['Iron Wall', 'Farmer'],            enemy: ['Bear'] },
    { label: 'ethereal Vestige', player: ['Vestige', 'Soldier'],             enemy: ['Bear'] },
    { label: 'cleave Shinobi',   player: ['Soldier', 'Shinobi'],             enemy: ['Bear', 'Bear', 'Bear'] },
    { label: 'aura Ritual Alter',player: ['Soldier', 'Ritual Alter', 'Soldier'], enemy: ['Zombie', 'Zombie'] },
    { label: 'position stability',player: ['Paper Tiger', 'Skeleton', 'Soldier'], enemy: ['Bear', 'Huntsman', 'Zombie'] },
    { label: 'summon cascade',   player: ['Necromancer', 'Skeleton', 'Cat'], enemy: ['Bear', 'Bear', 'Bear'] },
    { label: 'on_any_summon',    player: ['Quartermaster', 'Skeleton'],      enemy: ['Bear', 'Bear'] },
    { label: 'empty vs empty',   player: [],                                 enemy: [] },
];

// ----- runner ------------------------------------------------------------
async function runStepThroughTest(scenario) {
    const window = makeWindow();
    const data = parseInWindow(window, generateCombatDataJson(scenario.player, scenario.enemy));
    window.combatFunctions.initializeCombatInterpreter(data);

    let appliedChecks = 0;
    let lastSeen = -1;
    const totalCommands = data.commands.length;

    // Step through until position reaches end. Budget 3x commands for skips.
    for (let i = 0; i < totalCommands * 3 + 10; i++) {
        const posBefore = window.__getInterpreterPosition();
        if (posBefore >= totalCommands) break;
        const ok = window.combatFunctions.stepThroughOneCommand();
        if (!ok) break;
        // eslint-disable-next-line no-await-in-loop
        await drain(window);
        const lastSeq = window.__lastAppliedSeq;
        if (lastSeq !== undefined && lastSeq !== lastSeen) {
            lastSeen = lastSeq;
            assertSnapshotMatches(window, lastSeq, data, `[${scenario.label}] step`);
            appliedChecks++;
        }
    }

    // Final state = end snapshot.
    assertSnapshotMatches(window, totalCommands - 1, data, `[${scenario.label}] end`);

    // combat_over / winner should be set from END command.
    const endCmd = data.commands[totalCommands - 1];
    if (endCmd.cmd === 'END') {
        const state = window.combatFunctions.getFrontendCombatState();
        if (!state.combat_over) {
            throw new Error(`[${scenario.label}] combat_over not set after END`);
        }
        if (state.winner !== endCmd.winner) {
            throw new Error(`[${scenario.label}] winner mismatch: got=${state.winner} expected=${endCmd.winner}`);
        }
    }

    return { totalCommands, appliedChecks };
}

async function runSkipToEndTest(scenario) {
    const window = makeWindow();
    const data = parseInWindow(window, generateCombatDataJson(scenario.player, scenario.enemy));
    window.combatFunctions.initializeCombatInterpreter(data);

    // Immediately skip to end without stepping. State should equal END snapshot.
    window.combatFunctions.skipToEndCommand();
    // skipToEndCommand does NOT feed through applySnapshotForCommand — it
    // calls snapToStep directly — so __lastAppliedSeq may be unset. Compare
    // against steps[last] directly.
    const state = window.combatFunctions.getFrontendCombatState();
    const endIdx = data.steps.length - 1;
    assertBandsMatch(state.player_band, data.steps[endIdx].state_after.player_band,
        `[${scenario.label}] skipToEnd player_band`);
    assertBandsMatch(state.enemy_band, data.steps[endIdx].state_after.enemy_band,
        `[${scenario.label}] skipToEnd enemy_band`);
    const endCmd = data.commands[endIdx];
    if (endCmd.cmd === 'END') {
        if (!state.combat_over) throw new Error(`[${scenario.label}] skipToEnd combat_over not set`);
        if (state.winner !== endCmd.winner) throw new Error(`[${scenario.label}] skipToEnd winner mismatch`);
    }
}

async function runJumpTest(scenario) {
    const window = makeWindow();
    const data = parseInWindow(window, generateCombatDataJson(scenario.player, scenario.enemy));
    if (data.commands.length < 4) return;  // need at least a couple commands
    window.combatFunctions.initializeCombatInterpreter(data);

    // Jump to several points and verify state.
    const targets = [1, Math.floor(data.commands.length / 2), data.commands.length - 1];
    for (const targetIndex of targets) {
        window.combatFunctions.jumpToCommandIndex(targetIndex);
        // eslint-disable-next-line no-await-in-loop
        await drain(window);
        const snapIdx = Math.max(0, targetIndex - 1);
        const state = window.combatFunctions.getFrontendCombatState();
        assertBandsMatch(state.player_band, data.steps[snapIdx].state_after.player_band,
            `[${scenario.label}] jump(${targetIndex}) player_band`);
        assertBandsMatch(state.enemy_band, data.steps[snapIdx].state_after.enemy_band,
            `[${scenario.label}] jump(${targetIndex}) enemy_band`);
    }
}

async function main() {
    let passed = 0;
    let failed = 0;
    let totalCommands = 0;
    let totalChecks = 0;

    for (const scenario of SCENARIOS) {
        try {
            const step = await runStepThroughTest(scenario);
            await runSkipToEndTest(scenario);
            await runJumpTest(scenario);
            console.log(`  [PASS] ${scenario.label}: ${step.totalCommands} commands, ${step.appliedChecks} snapshot checks`);
            passed++;
            totalCommands += step.totalCommands;
            totalChecks += step.appliedChecks;
        } catch (err) {
            console.error(`  [FAIL] ${scenario.label}: ${err.message}`);
            if (err.stack) console.error(err.stack);
            failed++;
        }
    }

    console.log('');
    console.log('='.repeat(70));
    console.log(`RESULTS: ${passed} passed, ${failed} failed`);
    console.log(`Totals: ${totalCommands} commands, ${totalChecks} per-step snapshot checks`);
    console.log('='.repeat(70));
    process.exit(failed === 0 ? 0 : 1);
}

main().catch((err) => {
    console.error('harness crashed:', err);
    process.exit(2);
});
