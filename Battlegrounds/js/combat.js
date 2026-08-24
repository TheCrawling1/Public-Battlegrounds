// Combat system functions with full registry-based log integration
// UPDATED: ALL logs now come from backend via command.log_message
// REMOVED: All hardcoded frontend log generation

// Snapshot-based player: after each command's animations run, the bands in
// frontendCombatState are overwritten from the server-provided snapshot in
// interpreter_data.steps[seq].state_after. Jump and skip-to-end snap directly
// to the target step. The client does no delta reduction.
let interpreterSteps = [];

// Combat state management
let combatInterpreter = null;
let interpreterCommands = [];
let interpreterPosition = 0;
let currentlyDisplayingPosition = -1;  // Track which command is currently being displayed/animated
let lastScrolledPosition = -1;  // Track last position we auto-scrolled to
let lastValidLogPosition = -1;  // Track last position that had a log entry (for highlighting)
let combatAnimationQueue = [];
let isProcessingAnimation = false;
let combatInitialized = false;
let combatAutoLoading = false;

// Animation bundles loaded from interpreter
let animationBundles = [];

// FRONTEND COMBAT STATE - Independent of backend, modified by commands
let frontendCombatState = {
    player_band: [],
    enemy_band: [],
    combat_over: false,
    winner: null,
    round_number: 1,
    player_turn: true,
    combat_log: [],  // Array of {message: string, commandIndex: number}
    attack_count: 0,
    fatigue_active: false
};

// Animation integration
let currentCommandAnimations = [];

// Track which commands have been batched (to skip during normal processing)
let batchedCommandIndices = new Set();

// ============================================================================
// TRIGGER SKIPPING - Skip triggers that don't produce any effects
// ============================================================================

/**
 * Check if a trigger command should be skipped (has no effects)
 * @param {number} commandIndex - Index of the trigger command in interpreterCommands
 * @returns {boolean} - True if trigger should be skipped
 */
function shouldSkipTrigger(commandIndex) {
    const command = interpreterCommands[commandIndex];
    if (!command || !command.cmd.startsWith('TRIGGER_')) {
        return false;
    }

    // Extract trigger type: 'TRIGGER_RAGE' -> 'rage'
    const triggerType = command.cmd.replace('TRIGGER_', '').toLowerCase();

    // Look ahead for effects from this trigger
    for (let i = commandIndex + 1; i < interpreterCommands.length; i++) {
        const nextCmd = interpreterCommands[i];

        // Stop at next trigger or phase boundary
        if (nextCmd.cmd.startsWith('TRIGGER_') ||
            ['DECLARE_ATTACK', 'END', 'ROUND_START', 'TURN_START'].includes(nextCmd.cmd)) {
            break;
        }

        // Found an effect from this trigger - it did something
        if (nextCmd.is_effect_result && nextCmd.trigger_type === triggerType) {
            return false;
        }
    }

    // No effects found - skip this trigger
    console.log(`[COMBAT] Skipping useless trigger: ${command.cmd} at index ${commandIndex}`);
    return true;
}

// ============================================================================
// DEATH BATCHING - Play multiple deaths simultaneously
// ============================================================================

/**
 * Find all death commands in the current phase that should be batched together
 * @param {number} startIndex - Index of the first DEATH command
 * @returns {Array} - Array of {command, index} objects for deaths to batch
 */
function collectDeathsInPhase(startIndex) {
    const deaths = [];
    const phaseBoundaries = ['DECLARE_ATTACK', 'END', 'ROUND_START', 'TURN_START'];

    // Scan forward from current position
    for (let i = startIndex; i < interpreterCommands.length; i++) {
        const cmd = interpreterCommands[i];

        // Stop at phase boundary
        if (phaseBoundaries.includes(cmd.cmd)) {
            break;
        }

        // Collect DEATH commands (not DESTROY_MINION - those are different)
        if (cmd.cmd === 'DEATH') {
            deaths.push({ command: cmd, index: i });
        }
    }

    return deaths;
}

/**
 * Mark commands as batched so they get skipped during normal processing
 * @param {Array} indices - Array of command indices to mark as batched
 */
function markCommandsAsBatched(indices) {
    for (const index of indices) {
        batchedCommandIndices.add(index);
    }
}

/**
 * Check if a command has already been batched and processed
 * @param {number} index - Command index
 * @returns {boolean} - True if already batched
 */
function isCommandBatched(index) {
    return batchedCommandIndices.has(index);
}

/**
 * Reset batched commands tracking (call when resetting combat)
 */
function resetBatchedCommands() {
    batchedCommandIndices.clear();
}

// Build complete combat log from all commands upfront
function buildCompleteCombatLog() {
    frontendCombatState.combat_log = [];

    interpreterCommands.forEach((command, index) => {
        // Skip useless triggers from the log entirely
        if (command.cmd.startsWith('TRIGGER_') && shouldSkipTrigger(index)) {
            return; // Don't add to log
        }

        // Handle both log_message and LOG command types
        let logMessage = null;
        if (command.log_message && command.log_message.length > 0) {
            logMessage = command.log_message;
        } else if (command.cmd === 'LOG' && command.message) {
            logMessage = command.message;
        }

        if (logMessage) {
            frontendCombatState.combat_log.push({
                message: logMessage,
                commandIndex: index
            });
        }
    });

    console.log(`[COMBAT] Built complete log with ${frontendCombatState.combat_log.length} entries`);
}

// Initialize combat interpreter
function initializeCombatInterpreter(interpreterData) {
    if (!interpreterData) {
        console.log('No interpreter data provided');
        combatInterpreter = null;
        interpreterCommands = [];
        interpreterPosition = 0;
        combatInitialized = false;
        resetFrontendCombatState();
        return;
    }

    console.log('Initializing combat interpreter with', interpreterData.total_commands, 'commands');

    // DEBUG: Log initial_state structure
    if (interpreterData.initial_state) {
        console.log('[DEBUG] interpreter_data.initial_state:', {
            has_player_band: !!interpreterData.initial_state.player_band,
            player_band_length: (interpreterData.initial_state.player_band || []).length,
            has_enemy_band: !!interpreterData.initial_state.enemy_band,
            enemy_band_length: (interpreterData.initial_state.enemy_band || []).length,
            all_keys: Object.keys(interpreterData.initial_state)
        });
    } else {
        console.error('[ERROR] No initial_state in interpreter_data!');
    }

    interpreterCommands = interpreterData.commands || [];
    interpreterSteps = interpreterData.steps || [];
    interpreterPosition = 0;
    currentlyDisplayingPosition = -1;
    lastScrolledPosition = -1;
    lastValidLogPosition = -1;
    combatInitialized = true;

    animationBundles = interpreterData.animation_bundles || [];
    console.log(`[COMBAT] Loaded ${animationBundles.length} animation bundles`);
    console.log(`[COMBAT] Loaded ${interpreterSteps.length} snapshot steps`);

    initializeFrontendCombatState(interpreterData.initial_state);

    combatInterpreter = {
        initialState: interpreterData.initial_state || {
            player_band: [],
            enemy_band: []
        },
        commands: interpreterCommands,
        currentPosition: 0,
        playerBand: [...(interpreterData.initial_state?.player_band || [])],
        enemyBand: [...(interpreterData.initial_state?.enemy_band || [])]
    };

    // Build complete combat log upfront from all commands
    buildCompleteCombatLog();

    // Process START command if present
    if (interpreterCommands.length > 0 && interpreterCommands[0].cmd === 'START') {
        console.log('Processing START command');
        combatInterpreter.currentPosition = 1;
        interpreterPosition = 1;
    }

    console.log('Combat interpreter initialized with', interpreterCommands.length, 'total commands');
}

// Initialize frontend combat state from initial state
function initializeFrontendCombatState(initialState) {
    if (!initialState) {
        console.warn('[DEBUG] initializeFrontendCombatState called with no initialState!');
        resetFrontendCombatState();
        return;
    }

    // DEBUG: Log what we received
    console.log('[DEBUG] initializeFrontendCombatState received:', {
        has_player_band: !!initialState.player_band,
        player_band_length: (initialState.player_band || []).length,
        has_enemy_band: !!initialState.enemy_band,
        enemy_band_length: (initialState.enemy_band || []).length,
        all_keys: Object.keys(initialState)
    });

    // Only log errors for empty bands if combat is NOT over (empty bands are normal after combat ends)
    if (!initialState.combat_over) {
        if (!initialState.player_band || initialState.player_band.length === 0) {
            console.error('[ERROR] player_band is missing or empty in initialState (combat not over)!');
        }
        if (!initialState.enemy_band || initialState.enemy_band.length === 0) {
            console.error('[ERROR] enemy_band is missing or empty in initialState (combat not over)!');
        }
    }

    frontendCombatState = {
        player_band: deepCopy(initialState.player_band || []),
        enemy_band: deepCopy(initialState.enemy_band || []),
        combat_over: false,  // Don't use backend state, let interpreter commands set this
        winner: null,        // Don't use backend state, let interpreter commands set this
        round_number: initialState.round_number || 1,
        player_turn: initialState.player_turn !== undefined ? initialState.player_turn : true,
        combat_log: [],  // Will be built from all commands upfront
        attack_count: initialState.attack_count || 0,
        fatigue_active: initialState.fatigue_active || false,
        ui_data: {
            alive_player_count: (initialState.player_band || []).filter(m => m.health > 0).length,
            alive_enemy_count: (initialState.enemy_band || []).filter(m => m.health > 0).length,
            active_player_index: null,
            active_enemy_index: null,
            total_player_count: (initialState.player_band || []).length,
            total_enemy_count: (initialState.enemy_band || []).length
        }
    };

    console.log('[DEBUG] Frontend combat state initialized with', frontendCombatState.player_band.length, 'player minions and', frontendCombatState.enemy_band.length, 'enemy minions');
}

// Reset frontend combat state
function resetFrontendCombatState() {
    frontendCombatState = {
        player_band: [],
        enemy_band: [],
        combat_over: false,
        winner: null,
        round_number: 1,
        player_turn: true,
        combat_log: [],
        attack_count: 0,
        fatigue_active: false,
        ui_data: {
            alive_player_count: 0,
            alive_enemy_count: 0,
            active_player_index: null,
            active_enemy_index: null,
            total_player_count: 0,
            total_enemy_count: 0
        }
    };
}

// Deep copy utility
function deepCopy(obj) {
    if (obj === null || typeof obj !== 'object') return obj;
    if (obj instanceof Array) return obj.map(item => deepCopy(item));

    const copy = {};
    for (let key in obj) {
        if (obj.hasOwnProperty(key)) {
            copy[key] = deepCopy(obj[key]);
        }
    }
    return copy;
}

// Get current frontend combat state (used by UI)
function getFrontendCombatState() {
    return frontendCombatState;
}

// Overwrites the bands in frontendCombatState with the server-authored snapshot
// for the given command. combat_over / winner / round_number come from the
// command switch in applyCommandEffect since the snapshot only carries bands.
function applySnapshotForCommand(command) {
    if (!command || typeof command.seq !== 'number') return;
    const step = interpreterSteps[command.seq];
    if (!step || !step.state_after) return;
    const snap = step.state_after;
    frontendCombatState.player_band = deepCopy(snap.player_band || []);
    frontendCombatState.enemy_band = deepCopy(snap.enemy_band || []);
}

// Snap straight to a target step's snapshot without replaying any commands.
// Used by jump-to-log-entry and skip-to-end. Restores combat_over/winner
// from the END command's payload when applicable.
function snapToStep(stepIndex) {
    if (!interpreterSteps || interpreterSteps.length === 0) return false;
    const idx = Math.max(0, Math.min(stepIndex, interpreterSteps.length - 1));
    const step = interpreterSteps[idx];
    if (!step || !step.state_after) return false;
    frontendCombatState.player_band = deepCopy(step.state_after.player_band || []);
    frontendCombatState.enemy_band = deepCopy(step.state_after.enemy_band || []);
    const cmd = step.command || {};
    if (cmd.cmd === 'END') {
        frontendCombatState.combat_over = true;
        frontendCombatState.winner = cmd.winner || null;
    } else {
        frontendCombatState.combat_over = false;
        frontendCombatState.winner = null;
    }
    return true;
}

// AUTO-LOAD COMBAT DATA when combat selection is first displayed
async function autoLoadCombatData() {
    if (combatAutoLoading || combatInitialized) {
        console.log('Combat data already loading or loaded');
        return;
    }

    if (!currentRunId) {
        console.log('No current run ID for auto-loading combat');
        return;
    }

    try {
        combatAutoLoading = true;
        console.log('Auto-loading combat data...');

        const result = await apiCall(`/run/${currentRunId}/select`, 'POST', {
            selections: ['next']
        });

        console.log('Auto-load API response received:', result);
        gameData = result;

        if (result.selection_result && result.selection_result.interpreter_data) {
            console.log('Auto-initializing interpreter with data');
            initializeCombatInterpreter(result.selection_result.interpreter_data);
            updateDisplay();
        } else {
            console.warn('No interpreter data in auto-load response');
        }

    } catch (error) {
        console.error('Failed to auto-load combat data:', error);
    } finally {
        combatAutoLoading = false;
    }
}

// Get command bundle metadata
function getCommandBundle(command) {
    if (!command.animation_bundle) {
        return null;
    }

    return animationBundles.find(bundle => bundle.bundle_id === command.animation_bundle);
}

// Get all commands in a bundle
function getBundleCommands(bundleId) {
    const bundle = animationBundles.find(b => b.bundle_id === bundleId);
    if (!bundle) {
        console.warn('[COMBAT] Bundle not found:', bundleId);
        return [];
    }

    return bundle.command_indices.map(index => interpreterCommands[index]).filter(cmd => cmd);
}

// Process a single interpreter command with animation support
function processInterpreterCommand(command) {
    console.log('Processing interpreter command:', command.cmd, command);

    if (autoCombatInProgress && command.animation_bundle && command.is_bundle_start) {
        console.log('[COMBAT] Processing animation bundle:', command.animation_bundle);
        processBundleAnimation(command);
        return;
    }

    currentCommandAnimations = [];

    combatAnimationQueue.push(command);

    if (!isProcessingAnimation) {
        processNextAnimation();
    }
}

// Process bundle animation
async function processBundleAnimation(startCommand) {
    const bundleId = startCommand.animation_bundle;
    const bundle = getCommandBundle(startCommand);

    if (!bundle) {
        console.warn('[COMBAT] Bundle not found, processing individual command');
        processInterpreterCommand(startCommand);
        return;
    }

    console.log(`[COMBAT] Processing bundle ${bundleId} with ${bundle.command_indices.length} commands`);

    const bundleCommands = getBundleCommands(bundleId);

    if (bundleCommands.length === 0) {
        console.warn('[COMBAT] No commands found in bundle');
        return;
    }

    // Pause auto-combat interval during bundle processing
    const wasAutoCombatRunning = autoCombatInProgress && autoCombatInterval;
    if (wasAutoCombatRunning) {
        clearInterval(autoCombatInterval);
        autoCombatInterval = null;
        console.log('[COMBAT] Paused auto-combat for bundle processing');
    }

    let templateData = bundle.template_data;
    if (!templateData) {
        for (const command of bundleCommands) {
            if (command.template_data) {
                templateData = command.template_data;
                break;
            }
        }
    }

    // Advance interpreter position past bundle commands
    const lastBundleIndex = Math.max(...bundle.command_indices);
    interpreterPosition = lastBundleIndex + 1;
    console.log(`[COMBAT] Advanced interpreter position to ${interpreterPosition}`);

    if (window.animationFunctions && window.animationFunctions.playBundle) {
        console.log('[COMBAT] Delegating bundle to animation system');

        const enhancedBundleData = {
            ...bundle.animation_data,
            template_data: templateData
        };

        const bundleAnimationId = window.animationFunctions.playBundle(
            bundle.bundle_type,
            bundleCommands,
            enhancedBundleData
        );

        const bundleDuration = templateData?.duration || bundle.animation_data?.duration || 2000;

        // Apply effects and resume auto-combat after animation completes
        setTimeout(async () => {
            for (const command of bundleCommands) {
                await applyCommandEffect(command);
            }

            updateDisplay();
            scrollCombatLogToBottom();

            console.log(`[COMBAT] Bundle ${bundleId} processing complete`);

            // Resume auto-combat if it was running
            if (wasAutoCombatRunning && autoCombatInProgress) {
                const delay = AUTO_COMBAT_DELAY / autoCombatSpeed;
                // Process next command immediately (for deaths etc), then start interval
                autoCombatStep();
                autoCombatInterval = setInterval(() => {
                    autoCombatStep();
                }, delay);
                console.log('[COMBAT] Resumed auto-combat after bundle');
            }
        }, bundleDuration);

    } else {
        console.warn('[COMBAT] Animation system not available for bundle processing');
        for (const command of bundleCommands) {
            await applyCommandEffect(command);
            await new Promise(resolve => setTimeout(resolve, 100));
        }
        updateDisplay();

        // Resume auto-combat if it was running
        if (wasAutoCombatRunning && autoCombatInProgress) {
            const delay = AUTO_COMBAT_DELAY / autoCombatSpeed;
            // Process next command immediately (for deaths etc), then start interval
            autoCombatStep();
            autoCombatInterval = setInterval(() => {
                autoCombatStep();
            }, delay);
            console.log('[COMBAT] Resumed auto-combat after bundle (no animation)');
        }
    }
}

// Process the next animation in the queue with animation integration
async function processNextAnimation() {
    if (combatAnimationQueue.length === 0) {
        isProcessingAnimation = false;
        currentlyDisplayingPosition = interpreterPosition;  // Update to current position when queue is empty

        // Use lightweight update instead of full DOM regeneration
        updateActiveLogEntry();
        scrollToActiveLogEntry();  // Scroll to show final position
        return;
    }

    isProcessingAnimation = true;
    const command = combatAnimationQueue.shift();

    // Find the command index in the interpreter commands array
    const commandIndex = interpreterCommands.indexOf(command);
    if (commandIndex !== -1) {
        currentlyDisplayingPosition = commandIndex;

        // Update highlight BEFORE animation starts so it's visible throughout
        updateActiveLogEntry();
        scrollToActiveLogEntry();
    }

    // ========== DEATH BATCHING ==========
    // When we encounter a DEATH command, find all other deaths in the same phase
    // and play them all at once
    if (command.cmd === 'DEATH' && commandIndex !== -1) {
        const deathsInPhase = collectDeathsInPhase(commandIndex);

        if (deathsInPhase.length > 1) {
            console.log(`[COMBAT] Batching ${deathsInPhase.length} deaths together`);

            // Apply all death visuals at once (no waiting between them)
            for (const { command: deathCmd, index } of deathsInPhase) {
                markMinionDead(deathCmd.minion_id);

                // Start death animation for each
                if (deathCmd.animation) {
                    startCommandAnimation(deathCmd);
                }

                // Mark as batched so we skip it later
                if (index !== commandIndex) {
                    markCommandsAsBatched([index]);

                    // Also remove from animation queue if it's there
                    const queueIndex = combatAnimationQueue.findIndex(c => c === deathCmd);
                    if (queueIndex !== -1) {
                        combatAnimationQueue.splice(queueIndex, 1);
                    }
                }
            }

            // Update display once for all deaths
            updateDisplay();

            // Wait once for the death animation duration
            const duration = getEffectiveAnimationDuration(command);
            await new Promise(resolve => setTimeout(resolve, duration));

            processNextAnimation();
            return;
        }
    }
    // ========== END DEATH BATCHING ==========

    const animationId = startCommandAnimation(command);
    if (animationId) {
        currentCommandAnimations.push(animationId);
    }

    await applyCommandEffect(command);

    const duration = getEffectiveAnimationDuration(command);
    await new Promise(resolve => setTimeout(resolve, duration));

    // Highlight was already updated before animation - updateDisplay() called inside applyCommandEffect()
    // This keeps the highlight stable throughout the animation

    processNextAnimation();
}

// Start animation for a command using the animation system
function startCommandAnimation(command) {
    if (!window.animationFunctions) {
        console.warn('[COMBAT] Animation system not available');
        return null;
    }

    if (!command.animation) {
        return null;
    }

    try {
        const animationId = window.animationFunctions.playAnimation(command);
        if (animationId) {
            console.log('[COMBAT] Started animation for command:', command.cmd, 'ID:', animationId);
        }
        return animationId;
    } catch (error) {
        console.error('[COMBAT] Failed to start animation:', error);
        return null;
    }
}

// Get effective animation duration considering global animation speed
function getEffectiveAnimationDuration(command) {
    const baseDuration = command.duration || 200;

    if (window.animationFunctions) {
        const debugInfo = window.animationFunctions.getAnimationDebugInfo();
        return baseDuration / debugInfo.globalSpeed;
    }

    return baseDuration;
}

// Fire the sound mapped to this combat command, if any. All lookups are
// guarded — missing SoundBus/SOUND_MAP entries are silently ignored.
function dispatchCommandSound(command) {
    if (!window.SoundBus || !window.SOUND_MAP) return;
    // Combat start/end get special keys because START/END are generic names.
    // Drive the music baseline so combat feels driving and resolution relaxes.
    if (command.cmd === 'START') {
        window.SoundBus.playAction('COMBAT_START');
        if (window.MusicEngine) {
            window.MusicEngine.setBaselineIntensity(0.7);
            window.MusicEngine.setIntensity(0.75);
        }
        return;
    }
    if (command.cmd === 'END') {
        const key = command.winner === 'enemy' ? 'COMBAT_END_LOSS' : 'COMBAT_END_WIN';
        window.SoundBus.playAction(key);
        if (window.MusicEngine) {
            window.MusicEngine.setBaselineIntensity(0.2);
            window.MusicEngine.setIntensity(0.3);
        }
        return;
    }
    window.SoundBus.playAction(command.cmd);
}

// Apply the effect of a command to the frontend combat state
// REGISTRY-BASED: ALL logs come from command.log_message
// Note: Logs are not added here - they're all built upfront in buildCompleteCombatLog()
async function applyCommandEffect(command) {
    dispatchCommandSound(command);
    switch(command.cmd) {
        case 'START':
            console.log('Combat started');
            break;

        case 'END':
            console.log('Combat ended:', command.winner);
            frontendCombatState.combat_over = true;
            frontendCombatState.winner = command.winner;
            break;

        case 'ROUND_START':
            frontendCombatState.round_number = command.round;
            break;

        case 'TURN_START':
            break;

        case 'DECLARE_ATTACK':
            highlightAttacker(command.attacker_id);
            highlightDefender(command.defender_id);

            // Queue attack animation (but not for spell casts, 0-attack, or can't attack minions)
            // Find the attacker minion to check if they can actually attack
            let attackerMinion = frontendCombatState.player_band.find(m => m._combat_id === command.attacker_id);
            if (!attackerMinion) {
                attackerMinion = frontendCombatState.enemy_band.find(m => m._combat_id === command.attacker_id);
            }

            // Check if this is a valid physical attack
            const hasCastKeyword = attackerMinion && attackerMinion.keywords &&
                                   attackerMinion.keywords.includes('cast');
            const hasCantAttackKeyword = attackerMinion && attackerMinion.keywords &&
                                         attackerMinion.keywords.includes('cant_attack');
            const hasAttackPower = attackerMinion && attackerMinion.attack > 0;

            // Only play attack animation for minions that can physically attack
            const shouldPlayAttackAnimation = !hasCastKeyword && !hasCantAttackKeyword && hasAttackPower;

            if (shouldPlayAttackAnimation) {
                if (window.animationFunctions && window.animationFunctions.queueAttackAnimation) {
                    window.animationFunctions.queueAttackAnimation(
                        command.attacker_id,
                        command.defender_id,
                        {
                            duration: 600,
                            shakeDuration: 100,
                            shakeIntensity: 5
                        }
                    );
                }
            } else {
                if (hasCastKeyword) {
                    console.log(`[COMBAT] Skipping attack animation for spell caster: ${command.attacker_name}`);
                } else if (hasCantAttackKeyword) {
                    console.log(`[COMBAT] Skipping attack animation for can't attack minion: ${command.attacker_name}`);
                } else if (!hasAttackPower) {
                    console.log(`[COMBAT] Skipping attack animation for 0-attack minion: ${command.attacker_name}`);
                }
            }

            break;

        case 'COMBAT_DAMAGE':
            if (command.obliterate_kill) {
                applyObliterateVisual(command.target_id, command.amount);
            } else {
                applyDamageVisual(command.target_id, command.amount);
            }
            if (window.animationFunctions && window.animationFunctions.showDamageNumber) {
                window.animationFunctions.showDamageNumber(command.target_id, command.amount, {
                    obliterate: command.obliterate_kill
                });
            }
            break;

        case 'COUNTER_DAMAGE':
            if (command.obliterate_kill) {
                applyObliterateVisual(command.target_id, command.amount);
            } else {
                applyDamageVisual(command.target_id, command.amount);
            }
            if (window.animationFunctions && window.animationFunctions.showDamageNumber) {
                window.animationFunctions.showDamageNumber(command.target_id, command.amount, {
                    obliterate: command.obliterate_kill
                });
            }
            break;

        case 'DEAL_DAMAGE':
            applyDamageVisual(command.target_id, command.amount);
            if (window.animationFunctions && window.animationFunctions.showDamageNumber) {
                window.animationFunctions.showDamageNumber(command.target_id, command.amount);
            }
            break;

        case 'HEAL':
            applyHealVisual(command.target_id, command.amount);
            if (window.animationFunctions && window.animationFunctions.showHealNumber) {
                window.animationFunctions.showHealNumber(command.target_id, command.amount);
            }
            break;

        case 'BUFF_STATS':
            applyBuffVisual(command.target_id, command.attack, command.health);
            if (window.animationFunctions && window.animationFunctions.showBuffNumber) {
                window.animationFunctions.showBuffNumber(
                    command.target_id,
                    command.attack || 0,
                    command.health || 0
                );
            }
            break;

        case 'DEBUFF_STATS':
            applyDebuffVisual(command.target_id, command.attack, command.health);
            if (window.animationFunctions && window.animationFunctions.showBuffNumber) {
                window.animationFunctions.showBuffNumber(
                    command.target_id,
                    command.attack || 0,
                    command.health || 0,
                    { color: '#ff44ff' }
                );
            }
            break;

        case 'SUMMON_MINION':
            applySummonVisual(command.band, command.position);
            break;

        case 'PERMANENT_STAT_GAIN':
            applyPermanentStatVisual(command.target_id, command.attack, command.health);
            if (window.animationFunctions && window.animationFunctions.showBuffNumber) {
                window.animationFunctions.showBuffNumber(
                    command.target_id,
                    command.attack || 0,
                    command.health || 0,
                    { color: '#ffcc00' }
                );
            }
            break;

        case 'MOVE_MINION':
            applyMoveVisual(command.minion_id, command.from_position, command.to_position);
            break;

        case 'STUN':
            applyStunVisual(command.target_id, command.stun_count);
            break;

        case 'GIVE_KEYWORD':
            applyKeywordVisual(command.target_id, command.keyword);
            break;

        case 'DEATH':
            markMinionDead(command.minion_id);
            break;

        case 'REMOVE_FROM_BAND':
            if (window.animationFunctions) {
                window.animationFunctions.cleanupAnimationsByTargetId(command.minion_id);
            }
            break;

        case 'TRIGGER_RAGE':
            showTriggerAnimation(command.source_id, 'rage');
            break;

        case 'TRIGGER_ASSAULT':
            showTriggerAnimation(command.source_id, 'assault');
            break;

        case 'TRIGGER_CAST':
            showTriggerAnimation(command.source_id, 'cast');
            break;

        case 'TRIGGER_DEATH_TOLL':
            showTriggerAnimation(command.source_id, 'death_toll');
            break;

        case 'TRIGGER_ON_ANY_DEATH':
            showTriggerAnimation(command.source_id, 'on_any_death');
            break;

        case 'TRIGGER_ON_ANY_CAST':
            showTriggerAnimation(command.source_id, 'on_any_cast');
            break;

        case 'TRIGGER_ON_ANY_SUMMON':
            showTriggerAnimation(command.source_id, 'on_any_summon');
            break;

        case 'TRIGGER_START_OF_COMBAT':
            showTriggerAnimation(command.source_id, 'start_of_combat');
            break;

        case 'TRIGGER_ON_DAMAGE':
            showTriggerAnimation(command.source_id, 'on_damage');
            break;

        case 'TRIGGER_ON_ANY_LEAP':
            showTriggerAnimation(command.source_id, 'on_any_leap');
            break;

        case 'TRIGGER_ON_ANY_DEATH_TOLL':
            showTriggerAnimation(command.source_id, 'on_any_death_toll');
            break;

        case 'LEAP_MOVE':
            applyMoveVisual(command.target_id, command.old_position, command.new_position);
            break;

        case 'DEAL_AOE_DAMAGE':
            if (command.target_ids && Array.isArray(command.target_ids)) {
                for (const targetId of command.target_ids) {
                    applyDamageVisual(targetId, command.amount);
                    if (window.animationFunctions && window.animationFunctions.showDamageNumber) {
                        window.animationFunctions.showDamageNumber(targetId, command.amount);
                    }
                }
            }
            break;

        case 'APPLY_STUN':
            applyStunVisual(command.target_id, command.stun_amount || 1);
            break;

        case 'ETHEREAL_SAVE':
            applyKeywordVisual(command.target_id, 'ethereal');
            break;

        case 'GRANT_KEYWORD':
            applyKeywordVisual(command.target_id, command.keyword || 'effect');
            break;

        case 'GRANT_EFFECT':
            applyKeywordVisual(command.target_id, command.keyword || 'effect');
            break;

        case 'TRANSFORM':
            applyTransformVisual(command.target_id, command.new_minion_name);
            break;

        case 'DESTROY_MINION':
            markMinionDead(command.target_id);
            break;

        case 'MODIFY_FATIGUE':
            break;

        case 'REDIRECT_DAMAGE':
            applyDamageVisual(command.target_id, command.amount);
            break;

        case 'PREVENT_DEATH':
            applyPreventDeathVisual(command.target_id);
            break;

        case 'COPY_STATS':
            applyBuffVisual(command.target_id, command.attack, command.health);
            break;

        case 'FORCE_CAST':
            showTriggerAnimation(command.target_id, 'cast');
            break;

        case 'RECALCULATE_AURAS':
            break;

        case 'REDUCE_HIDE':
            applyHideVisual(command.target_id, command.hide_remaining);
            break;

        case 'REDUCE_RING':
            applyRingVisual(command.target_id, command.permanent_ring_count);
            break;

        case 'REMOVE_KEYWORD':
            break;

        case 'DIVIDE_ATTACK':
            applyDebuffVisual(command.target_id, command.old_attack - command.new_attack, 0);
            break;

        case 'MODIFY_GOLD':
            break;

        case 'TRANSFER_STUN':
            break;

        case 'STUN_REDUCED':
            break;

        case 'MULTI_ATTACK':
            showMultiAttackIndicator(command.attacker_id, command.attack_count);
            break;

        case 'FATIGUE_DAMAGE':
            showFatigueDamage(command.amount, command.affected_minions);
            break;

        case 'STUN_SKIP':
            showStunSkip(command.minion_id, command.stun_count);
            break;

        case 'ATTACK_CANCELLED':
            break;

        case 'LOG':
            // Log already added upfront in buildCompleteCombatLog()
            break;

        case 'AURA_RECALCULATION':
            // No visual or log
            break;

        default:
            console.warn('[COMBAT] Unknown command type:', command.cmd);
            break;
    }

    // Overlay the server-authored snapshot onto the bands. This is the only
    // path that mutates minion state on the client.
    applySnapshotForCommand(command);

    // Update UI data after any change
    updateFrontendUIData();

    // Update display to show state changes (health, attack, etc.)
    // Called AFTER all effects are applied
    // NOTE: scrollToActiveLogEntry() was already called BEFORE animation started with valid element reference
    updateDisplay();
}

// Update UI data based on current frontend state
function updateFrontendUIData() {
    const alivePlayerCount = frontendCombatState.player_band.filter(m => m.health > 0).length;
    const aliveEnemyCount = frontendCombatState.enemy_band.filter(m => m.health > 0).length;

    frontendCombatState.ui_data = {
        alive_player_count: alivePlayerCount,
        alive_enemy_count: aliveEnemyCount,
        active_player_index: null,
        active_enemy_index: null,
        total_player_count: frontendCombatState.player_band.length,
        total_enemy_count: frontendCombatState.enemy_band.length
    };
}

// Scroll combat log to bottom
function scrollCombatLogToBottom() {
    const logContent = document.querySelector('.combat-log-content');
    if (logContent) {
        requestAnimationFrame(() => {
            logContent.scrollTop = logContent.scrollHeight;
            console.log('[COMBAT] Scrolled combat log to bottom');
        });
    }
}

// Update the active log entry highlight without regenerating entire DOM
function updateActiveLogEntry() {
    console.log('[HIGHLIGHT] updateActiveLogEntry called, currentlyDisplayingPosition:', currentlyDisplayingPosition);

    // First, check if the current entry exists
    const currentEntry = document.querySelector(`[data-command-index="${currentlyDisplayingPosition}"]`);
    console.log('[HIGHLIGHT] Looking for entry', currentlyDisplayingPosition, 'found:', !!currentEntry);

    if (!currentEntry) {
        console.warn('[HIGHLIGHT] Entry does not exist in log - skipping highlight update (command has no log entry)');
        // Don't remove old highlight if new entry doesn't exist
        // Keep lastValidLogPosition unchanged so DOM regeneration uses the last valid position
        return;
    }

    // Only remove old highlights if we found a new entry to highlight
    const allEntries = document.querySelectorAll('.log-entry-active');
    console.log('[HIGHLIGHT] Removing active class from', allEntries.length, 'entries');
    allEntries.forEach(entry => entry.classList.remove('log-entry-active'));

    // Add active class to current entry
    currentEntry.classList.add('log-entry-active');
    console.log('[HIGHLIGHT] Active class added successfully to entry', currentlyDisplayingPosition);

    // Track this as the last valid log position for DOM regeneration
    lastValidLogPosition = currentlyDisplayingPosition;
}

// Scroll to the currently active log entry (only if position changed)
function scrollToActiveLogEntry() {
    // Only scroll if the position actually changed
    if (currentlyDisplayingPosition === lastScrolledPosition) {
        return;
    }

    const logContainer = document.querySelector('.combat-log-content');
    const activeEntry = document.querySelector('.log-entry-active');

    if (!logContainer || !activeEntry) {
        console.warn('[COMBAT] Could not find log container or active entry');
        return;
    }

    lastScrolledPosition = currentlyDisplayingPosition;

    // Calculate scroll position manually instead of using scrollIntoView
    // This avoids RAF timing issues with DOM regeneration
    const containerRect = logContainer.getBoundingClientRect();
    const entryRect = activeEntry.getBoundingClientRect();

    // Calculate how much we need to scroll
    const entryTopRelativeToContainer = entryRect.top - containerRect.top;
    const entryBottomRelativeToContainer = entryRect.bottom - containerRect.top;

    // Only scroll if entry is not fully visible
    if (entryTopRelativeToContainer < 0) {
        // Entry is above visible area - scroll up
        logContainer.scrollTop += entryTopRelativeToContainer;
        console.log('[COMBAT] Scrolled up to show entry at position', currentlyDisplayingPosition);
    } else if (entryBottomRelativeToContainer > containerRect.height) {
        // Entry is below visible area - scroll down
        logContainer.scrollTop += (entryBottomRelativeToContainer - containerRect.height);
        console.log('[COMBAT] Scrolled down to show entry at position', currentlyDisplayingPosition);
    } else {
        console.log('[COMBAT] Entry already visible at position', currentlyDisplayingPosition);
    }
}

// Preserve and restore combat log scroll position
let preservedScrollPosition = null;

function preserveCombatLogScroll() {
    const logContent = document.querySelector('.combat-log-content');
    if (logContent) {
        preservedScrollPosition = logContent.scrollTop;
    }
}

function restoreCombatLogScroll() {
    const logContent = document.querySelector('.combat-log-content');
    if (logContent && preservedScrollPosition !== null) {
        requestAnimationFrame(() => {
            const wasAtBottom = preservedScrollPosition >= (logContent.scrollHeight - logContent.clientHeight - 10);
            if (!wasAtBottom) {
                logContent.scrollTop = preservedScrollPosition;
            } else {
                logContent.scrollTop = logContent.scrollHeight;
            }
            preservedScrollPosition = null;
        });
    }
}

// Visual effect functions
function highlightAttacker(minionId) {
    const element = document.querySelector(`[data-combat-id="${minionId}"]`);
    if (element) {
        element.classList.add('attacking');
        setTimeout(() => element.classList.remove('attacking'), 500);
    }
}

function highlightDefender(minionId) {
    const element = document.querySelector(`[data-combat-id="${minionId}"]`);
    if (element) {
        element.classList.add('defending');
        setTimeout(() => element.classList.remove('defending'), 500);
    }
}

function applyDamageVisual(minionId, amount) {
    const element = document.querySelector(`[data-combat-id="${minionId}"]`);
    if (element) {
        // DISABLED: Don't add damaged class (causes unwanted visual effects)
        // element.classList.add('damaged');

        // DISABLED: Don't create damage number element (using floating numbers instead)
        // const damageNumber = document.createElement('div');
        // damageNumber.className = 'damage-number';
        // damageNumber.textContent = `-${amount}`;
        // element.appendChild(damageNumber);

        // setTimeout(() => {
        //     element.classList.remove('damaged');
        //     // damageNumber.remove();
        // }, 1000);
    }
}

function applyObliterateVisual(minionId, amount) {
    const element = document.querySelector(`[data-combat-id="${minionId}"]`);
    if (element) {
        element.classList.add('obliterated');

        const obliterateIndicator = document.createElement('div');
        obliterateIndicator.className = 'obliterate-indicator';
        obliterateIndicator.textContent = '💀 OBLITERATED';
        element.appendChild(obliterateIndicator);

        setTimeout(() => {
            element.classList.remove('obliterated');
            obliterateIndicator.remove();
        }, 1500);
    }
}

function applyHealVisual(minionId, amount) {
    const element = document.querySelector(`[data-combat-id="${minionId}"]`);
    if (element) {
        // DISABLED: Don't add healed class (causes unwanted visual effects)
        // element.classList.add('healed');

        // DISABLED: Don't create heal number element (using floating numbers instead)
        // const healNumber = document.createElement('div');
        // healNumber.className = 'heal-number';
        // healNumber.textContent = `+${amount}`;
        // element.appendChild(healNumber);

        // setTimeout(() => {
        //     element.classList.remove('healed');
        //     // healNumber.remove();
        // }, 1000);
    }
}

function applyBuffVisual(minionId, attack, health) {
    const element = document.querySelector(`[data-combat-id="${minionId}"]`);
    if (element) {
        // DISABLED: Don't add buffed class (causes unwanted visual effects)
        // element.classList.add('buffed');

        // DISABLED: Don't create buff indicator element
        // const buffIndicator = document.createElement('div');
        // buffIndicator.className = 'buff-indicator';
        // const buffParts = [];
        // if (attack > 0) buffParts.push(`+${attack} ATK`);
        // if (health > 0) buffParts.push(`+${health} HP`);
        // buffIndicator.textContent = buffParts.join(' ');
        // element.appendChild(buffIndicator);

        // setTimeout(() => {
        //     element.classList.remove('buffed');
        //     buffIndicator.remove();
        // }, 1500);
    }
}

function applyDebuffVisual(minionId, attack, health) {
    const element = document.querySelector(`[data-combat-id="${minionId}"]`);
    if (element) {
        // DISABLED: Don't add debuffed class (causes unwanted visual effects)
        // element.classList.add('debuffed');

        // DISABLED: Don't create debuff indicator element
        // const debuffIndicator = document.createElement('div');
        // debuffIndicator.className = 'debuff-indicator';
        // const debuffParts = [];
        // if (attack > 0) debuffParts.push(`-${attack} ATK`);
        // if (health > 0) debuffParts.push(`-${health} HP`);
        // debuffIndicator.textContent = debuffParts.join(' ');
        // element.appendChild(debuffIndicator);

        // setTimeout(() => {
        //     element.classList.remove('debuffed');
        //     debuffIndicator.remove();
        // }, 1500);
    }
}

function applySummonVisual(band, position) {
    const bandContainer = document.querySelector(`.combat-side.${band} .combat-minions`);
    if (bandContainer) {
        bandContainer.classList.add('summoning');
        setTimeout(() => bandContainer.classList.remove('summoning'), 800);
    }
}

function applyPermanentStatVisual(minionId, attack, health) {
    const element = document.querySelector(`[data-combat-id="${minionId}"]`);
    if (element) {
        // DISABLED: Don't add permanent-gain class (causes unwanted visual effects)
        // element.classList.add('permanent-gain');

        // DISABLED: Don't create permanent indicator element
        // const permIndicator = document.createElement('div');
        // permIndicator.className = 'permanent-indicator';
        // const permParts = [];
        // if (attack > 0) permParts.push(`+${attack} ATK`);
        // if (health > 0) permParts.push(`+${health} HP`);
        // permIndicator.textContent = `PERM: ${permParts.join(' ')}`;
        // element.appendChild(permIndicator);

        // setTimeout(() => {
        //     element.classList.remove('permanent-gain');
        //     permIndicator.remove();
        // }, 2000);
    }
}

function applyMoveVisual(minionId, fromPos, toPos) {
    console.log(`[MOVE] Moving minion ${minionId} from position ${fromPos} to ${toPos}`);

    // Find the minion in frontend combat state
    let minion = null;
    let band = null;
    let bandType = null;

    // Check player band
    const playerIndex = frontendCombatState.player_band.findIndex(m => m._combat_id === minionId);
    if (playerIndex !== -1) {
        minion = frontendCombatState.player_band[playerIndex];
        band = frontendCombatState.player_band;
        bandType = 'player';
    } else {
        // Check enemy band
        const enemyIndex = frontendCombatState.enemy_band.findIndex(m => m._combat_id === minionId);
        if (enemyIndex !== -1) {
            minion = frontendCombatState.enemy_band[enemyIndex];
            band = frontendCombatState.enemy_band;
            bandType = 'enemy';
        }
    }

    if (!minion || !band) {
        console.warn(`[MOVE] Could not find minion ${minionId} in combat state`);
        return;
    }

    // Update minion's position field
    minion.position = toPos;

    // Rearrange band array to match new positions
    // Sort by position to get correct visual order
    band.sort((a, b) => (a.position || 0) - (b.position || 0));

    console.log(`[MOVE] Minion ${minion.name} moved to position ${toPos}, band reordered`);
}

function applyStunVisual(minionId, stunCount) {
    const element = document.querySelector(`[data-combat-id="${minionId}"]`);
    if (element) {
        // DISABLED: Don't add stunned class (causes unwanted visual effects)
        // element.classList.add('stunned');

        // DISABLED: Don't create stun indicator element
        // const stunIndicator = document.createElement('div');
        // stunIndicator.className = 'stun-indicator';
        // stunIndicator.textContent = `STUNNED ${stunCount}`;
        // element.appendChild(stunIndicator);

        // setTimeout(() => {
        //     stunIndicator.remove();
        // }, 2000);
    }
}

function applyKeywordVisual(minionId, keyword) {
    const element = document.querySelector(`[data-combat-id="${minionId}"]`);
    if (element) {
        // DISABLED: Don't add keyword-gained class (causes unwanted visual effects)
        // element.classList.add('keyword-gained');

        // DISABLED: Don't create keyword indicator element
        // const keywordIndicator = document.createElement('div');
        // keywordIndicator.className = 'keyword-indicator';
        // keywordIndicator.textContent = `+${keyword.toUpperCase()}`;
        // element.appendChild(keywordIndicator);

        // setTimeout(() => {
        //     element.classList.remove('keyword-gained');
        //     keywordIndicator.remove();
        // }, 1500);
    }
}

function markMinionDead(minionId) {
    const element = document.querySelector(`[data-combat-id="${minionId}"]`);
    if (element) {
        element.classList.add('dead');
    }
}

function showTriggerAnimation(minionId, triggerType) {
    const element = document.querySelector(`[data-combat-id="${minionId}"]`);
    if (element) {
        // DISABLED: Don't add trigger classes (causes unwanted visual effects)
        // element.classList.add(`trigger-${triggerType}`);
        // setTimeout(() => element.classList.remove(`trigger-${triggerType}`), 800);
    }
}

function showMultiAttackIndicator(minionId, count) {
    const element = document.querySelector(`[data-combat-id="${minionId}"]`);
    if (element) {
        const indicator = document.createElement('div');
        indicator.className = 'multi-attack-indicator';
        indicator.textContent = `x${count}`;
        element.appendChild(indicator);

        setTimeout(() => indicator.remove(), 2000);
    }
}

function showFatigueDamage(amount, affectedMinions) {
    const combatZone = document.querySelector('.combat-zone');
    if (combatZone) {
        combatZone.classList.add('fatigue-damage');
        setTimeout(() => combatZone.classList.remove('fatigue-damage'), 1000);
    }

    if (affectedMinions && affectedMinions.length > 0) {
        affectedMinions.forEach(minionIdOrObj => {
            // Handle both ID strings and objects with id property
            const minionId = typeof minionIdOrObj === 'string' ? minionIdOrObj : minionIdOrObj.id;
            applyDamageVisual(minionId, amount);
        });
    }
}

function showStunSkip(minionId, stunCount) {
    const element = document.querySelector(`[data-combat-id="${minionId}"]`);
    if (element) {
        // DISABLED: Don't add stunned class (causes unwanted visual effects)
        // element.classList.add('stunned');

        // DISABLED: Don't create stun indicator element
        // const stunIndicator = document.createElement('div');
        // stunIndicator.className = 'stun-indicator';
        // stunIndicator.textContent = `Stunned (${stunCount})`;
        // element.appendChild(stunIndicator);

        // setTimeout(() => {
        //     element.classList.remove('stunned');
        //     stunIndicator.remove();
        // }, 1500);
    }
}

function applyTransformVisual(minionId, newMinionName) {
    const element = document.querySelector(`[data-combat-id="${minionId}"]`);
    if (element) {
        element.classList.add('transforming');

        const transformIndicator = document.createElement('div');
        transformIndicator.className = 'transform-indicator';
        transformIndicator.textContent = `→ ${newMinionName}`;
        element.appendChild(transformIndicator);

        setTimeout(() => {
            element.classList.remove('transforming');
            transformIndicator.remove();
        }, 1500);
    }
}

function applyPreventDeathVisual(minionId) {
    const element = document.querySelector(`[data-combat-id="${minionId}"]`);
    if (element) {
        element.classList.add('death-prevented');

        const preventIndicator = document.createElement('div');
        preventIndicator.className = 'prevent-death-indicator';
        preventIndicator.textContent = '🛡️ SAVED';
        element.appendChild(preventIndicator);

        setTimeout(() => {
            element.classList.remove('death-prevented');
            preventIndicator.remove();
        }, 1500);
    }
}

function applyHideVisual(minionId, hideRemaining) {
    const element = document.querySelector(`[data-combat-id="${minionId}"]`);
    if (element) {
        element.classList.add('hide-reduced');

        const hideIndicator = document.createElement('div');
        hideIndicator.className = 'hide-indicator';
        hideIndicator.textContent = `Hide: ${hideRemaining}`;
        element.appendChild(hideIndicator);

        setTimeout(() => {
            element.classList.remove('hide-reduced');
            hideIndicator.remove();
        }, 1000);
    }
}

function applyRingVisual(minionId, ringRemaining) {
    const element = document.querySelector(`[data-combat-id="${minionId}"]`);
    if (element) {
        element.classList.add('ring-reduced');

        const ringIndicator = document.createElement('div');
        ringIndicator.className = 'ring-indicator';
        ringIndicator.textContent = `Ring: ${ringRemaining}`;
        element.appendChild(ringIndicator);

        setTimeout(() => {
            element.classList.remove('ring-reduced');
            ringIndicator.remove();
        }, 1000);
    }
}

// Update the combat UI
function updateCombatUI() {
    updateDisplay();
}

// Handle combat end
function handleCombatEnd(command) {
    stopAutoCombat();
    updateCombatUI();
}

// Start auto combat
async function startAutoCombat() {
    if (autoCombatInProgress) {
        console.log('Auto combat already in progress');
        return;
    }

    if (!combatInitialized || !interpreterCommands || interpreterCommands.length === 0) {
        console.log('No combat data loaded for auto playback');
        return;
    }

    autoCombatInProgress = true;
    console.log('Starting auto combat at speed:', autoCombatSpeed);

    // Calculate delay based on speed (1x = 1500ms, 2x = 750ms, 3x = 500ms)
    const delay = AUTO_COMBAT_DELAY / autoCombatSpeed;

    autoCombatInterval = setInterval(() => {
        autoCombatStep();
    }, delay);

    updateDisplay();
}

// Single step of auto-combat processing (extracted for reuse after bundle resume)
function autoCombatStep() {
    if (interpreterPosition < interpreterCommands.length) {
        const command = interpreterCommands[interpreterPosition];
        console.log(`Auto combat processing command ${interpreterPosition}: ${command.cmd}`);

        // Skip commands that were already batched (e.g., deaths processed together)
        if (isCommandBatched(interpreterPosition)) {
            console.log(`[COMBAT] Skipping batched command at ${interpreterPosition}: ${command.cmd}`);
            interpreterPosition++;
            return;
        }

        // Skip useless triggers (no effects follow them)
        if (command.cmd.startsWith('TRIGGER_') && shouldSkipTrigger(interpreterPosition)) {
            console.log(`[COMBAT] Skipping useless trigger at ${interpreterPosition}: ${command.cmd}`);
            interpreterPosition++;
            return;
        }

        // Special handling for END command - apply effect immediately before stopping
        if (command.cmd === 'END') {
            console.log('Auto combat reached END command - applying end state');
            frontendCombatState.combat_over = true;
            frontendCombatState.winner = command.winner;
            // Log already added upfront in buildCompleteCombatLog()
            // Don't queue END command for animation, just stop
            stopAutoCombat();
            return;
        }

        if (command.animation_bundle && command.is_bundle_start) {
            processInterpreterCommand(command);
        } else if (!command.animation_bundle) {
            processInterpreterCommand(command);
            interpreterPosition++;
        } else {
            // This command is part of a bundle but not the start - it will be handled by processBundleAnimation
            interpreterPosition++;
        }
    } else {
        console.log('Auto combat finished');
        stopAutoCombat();
    }
}

function stopAutoCombat() {
    if (autoCombatInterval) {
        clearInterval(autoCombatInterval);
        autoCombatInterval = null;
    }
    autoCombatInProgress = false;
    console.log('Stopped auto combat');

    if (window.animationFunctions) {
        window.animationFunctions.pauseAllAnimations();

        // Stop attack animations when auto combat stops
        if (window.animationFunctions.stopAllAttackAnimations) {
            window.animationFunctions.stopAllAttackAnimations();
        }

        // Stop damage numbers when auto combat stops
        if (window.animationFunctions.stopAllDamageNumbers) {
            window.animationFunctions.stopAllDamageNumbers();
        }
    }

    updateDisplay();
}

// Set auto combat speed
function setAutoCombatSpeed(speed) {
    autoCombatSpeed = speed;
    console.log('Auto combat speed set to:', speed);

    // If auto combat is running, restart it with new speed
    if (autoCombatInProgress) {
        stopAutoCombat();
        startAutoCombat();
    } else {
        // Just update UI to show selected speed
        updateDisplay();
    }
}

// Step through one command
function stepThroughOneCommand() {
    if (!combatInitialized || !interpreterCommands || interpreterCommands.length === 0) {
        console.log('No combat data loaded for stepping');
        return false;
    }

    if (interpreterPosition >= interpreterCommands.length) {
        console.log('No more combat steps');
        return false;
    }

    // Skip batched commands (already processed with a batch)
    while (interpreterPosition < interpreterCommands.length && isCommandBatched(interpreterPosition)) {
        console.log(`[STEP] Skipping batched command at ${interpreterPosition}`);
        interpreterPosition++;
    }

    // Skip useless triggers
    while (interpreterPosition < interpreterCommands.length) {
        const cmd = interpreterCommands[interpreterPosition];
        if (cmd.cmd.startsWith('TRIGGER_') && shouldSkipTrigger(interpreterPosition)) {
            console.log(`[STEP] Skipping useless trigger at ${interpreterPosition}: ${cmd.cmd}`);
            interpreterPosition++;
        } else {
            break;
        }
    }

    if (interpreterPosition >= interpreterCommands.length) {
        console.log('No more combat steps');
        return false;
    }

    const command = interpreterCommands[interpreterPosition];
    console.log(`Stepping through command ${interpreterPosition}: ${command.cmd}`);

    // Special handling for END command - apply effect immediately
    if (command.cmd === 'END') {
        console.log('[STEP] Combat complete - applying end state immediately');
        console.log('[STEP] END command winner:', command.winner);
        frontendCombatState.combat_over = true;
        frontendCombatState.winner = command.winner;
        // Don't add log message here - let processInterpreterCommand handle it to avoid duplicates
        console.log('[STEP] frontendCombatState after setting:', {
            combat_over: frontendCombatState.combat_over,
            winner: frontendCombatState.winner,
            player_band_length: frontendCombatState.player_band?.length,
            enemy_band_length: frontendCombatState.enemy_band?.length
        });
        interpreterPosition++;
        // Still process for animations, but state is already updated
        processInterpreterCommand(command);
        return true;
    }

    processInterpreterCommand(command);
    interpreterPosition++;

    return true;
}

// Skip to end
function skipToEndCommand() {
    if (!combatInitialized || !interpreterCommands || interpreterCommands.length === 0) {
        console.log('No combat data loaded for skipping');
        return false;
    }

    console.log('Skipping to combat conclusion...');

    completeAnimationCleanup();

    if (interpreterSteps.length > 0) {
        const lastIndex = interpreterSteps.length - 1;
        snapToStep(lastIndex);
        interpreterPosition = interpreterCommands.length;
    }

    updateDisplay();
    console.log('Skipped to end of combat');
    return true;
}

// Submit combat selection
async function submitCombatSelection(choice) {
    if (!currentRunId) return;

    if (autoCombatInProgress && choice !== 'end') return;

    try {
        console.log('Submitting combat choice:', choice);

        if (combatInitialized && interpreterCommands && interpreterCommands.length > 0) {
            console.log('Combat data already loaded, doing local stepping');

            if (autoCombatInProgress) {
                stopAutoCombat();
            }

            if (choice === 'next') {
                if (stepThroughOneCommand()) {
                    updateDisplay();
                    return;
                } else {
                    console.log('No more combat steps');
                    return;
                }

            } else if (choice === 'auto') {
                if (window.animationFunctions) {
                    window.animationFunctions.resumeAllAnimations();
                }
                startAutoCombat();
                return;

            } else if (choice === 'end') {
                skipToEndCommand();
                updateDisplay();
                return;

            } else if (choice === 'continue') {
                // Fall through to API call
            } else {
                console.log('Unknown choice with loaded combat data:', choice);
            }
        }

        console.log('Making API call for continue or unloaded combat');
        const result = await apiCall(`/run/${currentRunId}/select`, 'POST', {
            selections: [choice]
        });

        console.log('API response received:', result);
        gameData = result;

        if (choice === 'continue') {
            // Check if run should end (victory or defeat) before continuing
            console.log('[END CHECK] Ghost wins:', result.ghost_wins, 'Health:', result.run?.health);
            console.log('[END CHECK] run_should_end:', result.run_should_end, 'run_victory:', result.run_victory);

            if (result.run_should_end) {
                console.log('[END SCREEN] Run ending after combat:', result.end_reason);
                addLogEntry(`🏁 ${result.end_reason}`, result.run_victory ? 'victory' : 'defeat');

                // Small delay to ensure log is visible
                await new Promise(resolve => setTimeout(resolve, 500));

                // Trigger end screen
                console.log('[END SCREEN] Calling processRunEnd for run:', currentRunId);
                await processRunEnd(currentRunId);
                return; // Stop further processing
            }

            resetCombatState();
            updateDisplay();
            return;
        }

        if (result.selection_result && result.selection_result.interpreter_data) {
            console.log('Initializing interpreter with data from API response');
            initializeCombatInterpreter(result.selection_result.interpreter_data);

            const selectionMode = result.selection_result.selection_mode || choice;
            console.log('Selection mode:', selectionMode);

            if (selectionMode === 'auto') {
                console.log('Combat loaded! Starting auto playback...');
                startAutoCombat();

            } else if (selectionMode === 'end') {
                console.log('Combat loaded! Jumping to final result...');
                skipToEndCommand();
            }
        }

        updateDisplay();

        if (result.ghost_battle_ready) {
            console.log('👻 GHOST BATTLE READY!');
        }

    } catch (error) {
        console.error('Failed to submit combat selection:', error);
        stopAutoCombat();
    }
}

// Initialize combat from state
function initializeCombatFromState(combatState) {
    if (combatState && combatState.interpreter_data) {
        initializeCombatInterpreter(combatState.interpreter_data);
    } else {
        combatInterpreter = null;
        interpreterCommands = [];
        interpreterPosition = 0;
        combatInitialized = false;
        resetFrontendCombatState();
    }
}

/**
 * Complete cleanup of all animation systems
 * Ensures all animation Maps, RAF callbacks, and DOM elements are cleaned
 */
function completeAnimationCleanup() {
    if (!window.animationFunctions) {
        return;
    }

    // 1. Cancel main animation system (activeAnimations + activeBundles Maps)
    window.animationFunctions.cancelAllAnimations();

    // 2. Stop attack animations (combatAttackAnimations.activeAttacks Map)
    if (window.animationFunctions.stopAllAttackAnimations) {
        window.animationFunctions.stopAllAttackAnimations();
    }

    // 3. Stop damage numbers (damageNumberSystem.activeNumbers Map)
    if (window.animationFunctions.stopAllDamageNumbers) {
        window.animationFunctions.stopAllDamageNumbers();
    }

    // 4. Clean up ALL animation DOM elements
    if (window.animationFunctions.cleanupAllAnimationDOM) {
        window.animationFunctions.cleanupAllAnimationDOM();
    }

    console.log('[COMBAT] Complete animation cleanup performed');
}

// Reset combat state
function resetCombatState() {
    stopAutoCombat();

    completeAnimationCleanup();

    combatInterpreter = null;
    interpreterCommands = [];
    interpreterPosition = 0;
    combatAnimationQueue = [];
    isProcessingAnimation = false;
    combatInitialized = false;
    combatAutoLoading = false;
    currentCommandAnimations = [];

    animationBundles = [];

    // Reset batched commands tracking
    resetBatchedCommands();

    resetFrontendCombatState();

    console.log('Combat state completely reset for new combat');
}

// Animation control functions
function pauseCombatAnimations() {
    if (window.animationFunctions) {
        window.animationFunctions.pauseAllAnimations();
    }
}

function resumeCombatAnimations() {
    if (window.animationFunctions) {
        window.animationFunctions.resumeAllAnimations();
    }
}

function setCombatAnimationSpeed(speed) {
    if (window.animationFunctions) {
        window.animationFunctions.setAnimationSpeed(speed);
    }
}

function getCombatAnimationDebugInfo() {
    if (window.animationFunctions) {
        return window.animationFunctions.getAnimationDebugInfo();
    }
    return null;
}

// Jump to a specific command index (for log navigation)
function jumpToCommandIndex(targetIndex) {
    if (!combatInitialized || !interpreterCommands || interpreterCommands.length === 0) {
        console.log('No combat data loaded for jumping');
        return false;
    }

    if (targetIndex < 0 || targetIndex >= interpreterCommands.length) {
        console.warn('Invalid jump target index:', targetIndex);
        return false;
    }

    console.log(`Jumping to command index ${targetIndex}`);

    // Stop any running auto-combat
    if (autoCombatInProgress) {
        stopAutoCombat();
    }

    // Cancel all active animations and clean up DOM
    completeAnimationCleanup();

    // Resume animation system (stopAutoCombat paused it)
    if (window.animationFunctions) {
        window.animationFunctions.resumeAllAnimations();
    }

    // Clear animation queue and processing state
    combatAnimationQueue = [];
    isProcessingAnimation = false;

    // Reset batched commands so they can be re-batched when replaying
    resetBatchedCommands();

    // Preserve scroll position before updating display
    const logContent = document.querySelector('.combat-log-content');
    const scrollPos = logContent ? logContent.scrollTop : 0;

    // Preserve the full combat log (don't truncate when rewinding)
    const fullCombatLog = frontendCombatState.combat_log.slice();

    // Reset to initial state
    initializeFrontendCombatState(combatInterpreter.initialState);

    // Snap straight to the target step's snapshot. targetIndex is the
    // next-to-play position, so the displayed state is the snapshot of the
    // previous command.
    const snapIndex = Math.max(0, targetIndex - 1);
    snapToStep(snapIndex);
    interpreterPosition = targetIndex;

    // Restore the full combat log (so all entries remain visible/clickable)
    frontendCombatState.combat_log = fullCombatLog;

    // Set display position to target
    currentlyDisplayingPosition = targetIndex;
    lastValidLogPosition = targetIndex;  // Update for highlighting

    // Set interpreter position to the target (ready for Step/Auto from here)
    interpreterPosition = targetIndex;

    // Update display with state at target position
    updateDisplay();

    // Restore scroll position after DOM update
    requestAnimationFrame(() => {
        const newLogContent = document.querySelector('.combat-log-content');
        if (newLogContent) {
            newLogContent.scrollTop = scrollPos;
        }
    });

    console.log(`Jumped to command ${targetIndex}, position now ${interpreterPosition}`);
    return true;
}

// Get current interpreter position for UI highlighting
function getCurrentPosition() {
    // Return the last valid log position for highlighting during DOM regeneration
    // This ensures that when commands without log entries are processed (like REMOVE_FROM_BAND),
    // the highlight stays on the last entry that DID have a log entry
    return lastValidLogPosition;
}

// Export functions
window.combatFunctions = {
    startAutoCombat,
    stopAutoCombat,
    submitCombatSelection,
    initializeCombatFromState,
    initializeCombatInterpreter,
    resetCombatState,
    getFrontendCombatState,
    autoLoadCombatData,
    stepThroughOneCommand,
    skipToEndCommand,
    pauseCombatAnimations,
    resumeCombatAnimations,
    setCombatAnimationSpeed,
    getCombatAnimationDebugInfo,
    jumpToCommandIndex,
    getCurrentPosition
};