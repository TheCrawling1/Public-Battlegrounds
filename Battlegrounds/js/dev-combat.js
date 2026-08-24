// Dev Mode Combat Simulator - Enhanced with Band State Tracking
// FIXED: Added post-combat band display to see permanent buffs like Cat's death toll

const DEV_API_BASE = '/api/dev';

// Global state
let currentSessionId = null;
let availableMinions = [];
let availableHeroes = [];
let playerBand = [];
let enemyBand = [];
let selectionTypes = [];

// Mode management
let currentMode = 'step';

// Step mode state
let stepCombatState = null;
let debugEnabled = true;
let manualTargetingEnabled = false;

// Playback mode state - delegates to combat.js
let spoofedGold = 0;
let spoofedBandData = {
    shop_band: [],
    recruit_options: [],
    band_history: []
};

// UI state
let editingMinion = null;
let editingBandType = null;
let editingIndex = -1;

// Drag and drop state
let draggedMinion = null;
let draggedBandType = null;
let draggedIndex = -1;

// Store original updateDisplay function
let originalUpdateDisplay = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('Dev Combat Mode loaded with band state tracking');
    loadAvailableMinions();
    loadAvailableHeroes();
    loadPresets();
    initializeDragAndDrop();
    updateModeDisplay();
    overrideUpdateDisplayForDevMode();
    setupCombatControlWrappers();
});

// Setup wrappers so production combat controls work in dev mode
function setupCombatControlWrappers() {
    // Capture production functions before we override them
    const productionSubmitCombatSelection = window.submitCombatSelection;
    const productionStopAutoCombat = window.stopAutoCombat;
    const productionSetAutoCombatSpeed = window.setAutoCombatSpeed;

    // Override submitCombatSelection to use interpreter functions in playback mode
    window.submitCombatSelection = function(action) {
        if (currentMode !== 'playback') {
            console.log('[DEV] submitCombatSelection called in non-playback mode:', action);
            return;
        }

        console.log('[DEV] Combat action:', action);

        if (action === 'next') {
            if (window.combatFunctions && window.combatFunctions.stepThroughOneCommand) {
                window.combatFunctions.stepThroughOneCommand();
            }
        } else if (action === 'auto') {
            if (window.combatFunctions && window.combatFunctions.startAutoCombat) {
                window.combatFunctions.startAutoCombat();
            }
        } else if (action === 'end') {
            if (window.combatFunctions && window.combatFunctions.skipToEndCommand) {
                window.combatFunctions.skipToEndCommand();
                setTimeout(() => loadPostCombatBand(), 500);
            }
        }
    };

    // Override stopAutoCombat for the production controls
    window.stopAutoCombat = function() {
        if (currentMode === 'playback' && window.combatFunctions) {
            if (window.combatFunctions.stopAutoCombat) {
                window.combatFunctions.stopAutoCombat();
            }
        } else if (productionStopAutoCombat) {
            productionStopAutoCombat();
        }
    };

    // Override setAutoCombatSpeed - just call production version
    // Production code handles setting the global autoCombatSpeed variable
    window.setAutoCombatSpeed = function(speed) {
        if (currentMode === 'playback') {
            // Call the production implementation which sets global autoCombatSpeed
            if (productionSetAutoCombatSpeed) {
                productionSetAutoCombatSpeed(speed);
            } else {
                // Fallback if production function not yet loaded
                window.autoCombatSpeed = speed;
                console.log('[DEV] Auto combat speed set to:', speed);
                if (window.updateDisplay) {
                    window.updateDisplay();
                }
            }
        }
    };

    console.log('[DEV] Combat control wrappers installed');
}

// Override the global updateDisplay function
function overrideUpdateDisplayForDevMode() {
    if (typeof updateDisplay === 'function') {
        originalUpdateDisplay = updateDisplay;
    }

    window.updateDisplay = function() {
        console.log('[DEV] updateDisplay called - mode:', currentMode);

        if (currentMode === 'playback') {
            // In playback mode, update only the combat UI part, not the wrapper
            // This preserves animations and prevents unnecessary re-renders
            const combatZone = document.querySelector('.combat-zone');
            if (combatZone && typeof generateCombatUI === 'function') {
                // BEFORE regeneration - save scroll position (fix from readme)
                const combatLogContent = document.querySelector('.combat-log-content');
                const preservedCombatScrollTop = combatLogContent ? combatLogContent.scrollTop : null;

                // Just update the combat zone content, not the dev wrapper
                const productionCombatHTML = generateCombatUI(null);

                // Extract just the combat-zone content from the generated HTML
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = productionCombatHTML;
                const newCombatZone = tempDiv.querySelector('.combat-zone');

                if (newCombatZone && combatZone.parentNode) {
                    combatZone.parentNode.replaceChild(newCombatZone, combatZone);

                    // AFTER regeneration - restore scroll position (fix from readme)
                    if (preservedCombatScrollTop !== null) {
                        const newCombatLogContent = document.querySelector('.combat-log-content');
                        if (newCombatLogContent) {
                            newCombatLogContent.scrollTop = preservedCombatScrollTop;
                        }
                    }
                }
            } else {
                // First time or no combat zone - do full render with wrapper
                displayPlaybackCombat();
            }
        } else if (currentMode === 'step') {
            // In step mode, use custom step rendering
            if (stepCombatState) {
                displayStepCombat();
            }
        } else if (originalUpdateDisplay) {
            // Fallback to original if needed
            originalUpdateDisplay();
        }
    };

    console.log('[DEV] updateDisplay override installed');
}

// Load available minions
async function loadAvailableMinions() {
    try {
        const response = await fetch(`${DEV_API_BASE}/minions`);
        const result = await response.json();

        if (result.success) {
            availableMinions = result.minions;
            selectionTypes = result.selection_types || [];
            populateMinionSelects();
            console.log(`Loaded ${result.total} minions`);
        }
    } catch (error) {
        console.error('Failed to load minions:', error);
    }
}

// Load available heroes from API
async function loadAvailableHeroes() {
    try {
        const response = await fetch(`${DEV_API_BASE}/heroes`);
        const result = await response.json();

        if (result.success) {
            availableHeroes = result.heroes;
            populateHeroSelects();
            console.log(`Loaded ${result.total} heroes`);
        }
    } catch (error) {
        console.error('Failed to load heroes:', error);
    }
}

// Populate hero selection dropdowns
function populateHeroSelects() {
    const heroSelect = document.getElementById('heroSelect');
    const heroSelectPlayback = document.getElementById('heroSelectPlayback');

    let optionsHTML = '<option value="">None</option>';
    availableHeroes.forEach(hero => {
        optionsHTML += `<option value="${hero.id}">${hero.name}</option>`;
    });

    if (heroSelect) heroSelect.innerHTML = optionsHTML;
    if (heroSelectPlayback) heroSelectPlayback.innerHTML = optionsHTML;
}

// Format hero description by replacing placeholders with actual values
function formatDevHeroDescription(description, powerLevel = 1) {
    if (!description) return '';

    // Calculate derived values based on power level
    const puckMinions = 1 + powerLevel;  // Puck starts at 2 minions (1 + power_level)

    return description
        .replace(/{power_level}/g, String(powerLevel))
        .replace(/{puck_minions}/g, String(puckMinions));
}

// Update hero description for step mode
function updateHeroDescription() {
    const heroSelect = document.getElementById('heroSelect');
    const heroDescription = document.getElementById('heroDescription');
    const selectedHeroId = heroSelect.value;

    if (!selectedHeroId) {
        heroDescription.textContent = 'Select a hero to apply their effects during combat';
        heroDescription.style.color = '#FFD700';
        return;
    }

    const hero = availableHeroes.find(h => h.id === selectedHeroId);
    if (hero) {
        // Use base power level of 1 for dev combat mode
        heroDescription.textContent = formatDevHeroDescription(hero.description, 1);
        heroDescription.style.color = '#87CEEB';
    }
}

// Update hero description for playback mode
function updateHeroDescriptionPlayback() {
    const heroSelectPlayback = document.getElementById('heroSelectPlayback');
    const heroDescriptionPlayback = document.getElementById('heroDescriptionPlayback');
    const selectedHeroId = heroSelectPlayback.value;

    if (!selectedHeroId) {
        heroDescriptionPlayback.textContent = 'Select a hero to apply their effects during combat';
        heroDescriptionPlayback.style.color = '#FFD700';
        return;
    }

    const hero = availableHeroes.find(h => h.id === selectedHeroId);
    if (hero) {
        // Use base power level of 1 for dev combat mode
        heroDescriptionPlayback.textContent = formatDevHeroDescription(hero.description, 1);
        heroDescriptionPlayback.style.color = '#87CEEB';
    }
}

// Populate minion selection dropdowns
function populateMinionSelects() {
    const playerSelect = document.getElementById('playerMinionSelect');
    const enemySelect = document.getElementById('enemyMinionSelect');

    const tiers = {};
    availableMinions.forEach(minion => {
        const tier = minion.tier || 1;
        if (!tiers[tier]) tiers[tier] = [];
        tiers[tier].push(minion);
    });

    let optionsHTML = '<option value="">Select a minion...</option>';

    Object.keys(tiers).sort().forEach(tier => {
        optionsHTML += `<optgroup label="Tier ${tier}">`;
        tiers[tier].forEach(minion => {
            const keywords = minion.keywords.join(', ') || 'None';
            const label = `${minion.name} (${minion.health}/${minion.attack}) - ${keywords}`;
            optionsHTML += `<option value="${minion.name}">${label}</option>`;
        });
        optionsHTML += '</optgroup>';
    });

    playerSelect.innerHTML = optionsHTML;
    enemySelect.innerHTML = optionsHTML;
}

// Load combat presets
async function loadPresets() {
    try {
        const response = await fetch(`${DEV_API_BASE}/combat/presets`);
        const result = await response.json();

        if (result.success) {
            const presetsContainer = document.getElementById('presetButtons');
            presetsContainer.innerHTML = result.presets.map(preset => `
                <button class="preset-btn" onclick='loadPreset(${JSON.stringify(preset)})'>
                    <strong>${preset.name}</strong>
                    <small>${preset.description}</small>
                </button>
            `).join('');
        }
    } catch (error) {
        console.error('Failed to load presets:', error);
    }
}

// Mode switching functions
function switchToStepMode() {
    if (currentMode === 'step') return;
    currentMode = 'step';
    updateModeDisplay();
    if (currentSessionId) {
        switchSessionMode('step');
    }
}

function switchToPlaybackMode() {
    if (currentMode === 'playback') return;
    currentMode = 'playback';
    updateModeDisplay();
    if (currentSessionId) {
        switchSessionMode('playback');
    }
}

async function switchSessionMode(newMode) {
    if (!currentSessionId) return;

    try {
        console.log('[DEV] Switching to', newMode, 'mode - recreating combat');

        if (window.animationFunctions && window.animationFunctions.resetAnimationSystem) {
            window.animationFunctions.resetAnimationSystem();
        }

        // Clear current session
        currentSessionId = null;
        clearStepState();
        clearPlaybackState();

        // Update mode and recreate combat
        currentMode = newMode;
        updateModeDisplay();

        // Recreate combat in new mode
        await createCombat();

    } catch (error) {
        console.error('Failed to switch mode:', error);
        alert('Failed to switch mode: ' + error.message);
    }
}

function updateModeDisplay() {
    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.getElementById(`${currentMode}ModeBtn`).classList.add('active');

    const stepControls = document.getElementById('stepModeControls');
    const playbackControls = document.getElementById('playbackModeControls');

    if (currentMode === 'step') {
        stepControls.style.display = 'block';
        playbackControls.style.display = 'none';
    } else {
        stepControls.style.display = 'none';
        playbackControls.style.display = 'block';
    }

    updateDebugPanel();
}

function updateGoldDisplay() {
    const goldInput = document.getElementById('spoofedGold');
    const goldInputPlayback = document.getElementById('spoofedGoldPlayback');

    if (goldInput) {
        goldInput.value = spoofedGold;
    }
    if (goldInputPlayback) {
        goldInputPlayback.value = spoofedGold;
    }
}

async function setSpoofedGold(goldAmount) {
    if (!currentSessionId) {
        spoofedGold = goldAmount;
        return;
    }

    try {
        const response = await fetch(`${DEV_API_BASE}/combat/${currentSessionId}/set-gold`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ gold: goldAmount })
        });

        const result = await response.json();

        if (result.success) {
            spoofedGold = result.gold;
            updateGoldDisplay();
            console.log(`Spoofed gold set to ${spoofedGold}`);
        }
    } catch (error) {
        console.error('Failed to set gold:', error);
    }
}

// Load a preset configuration
function loadPreset(preset) {
    console.log('Loading preset:', preset.name);

    playerBand = [];
    enemyBand = [];

    preset.player_band.forEach(minion => {
        playerBand.push({
            name: minion.name,
            golden: minion.golden || false,
            health: minion.health,
            attack: minion.attack,
            keywords: minion.keywords
        });
    });

    preset.enemy_band.forEach(minion => {
        enemyBand.push({
            name: minion.name,
            golden: minion.golden || false,
            health: minion.health,
            attack: minion.attack,
            keywords: minion.keywords,
            add_possessed_death_toll: minion.add_possessed_death_toll
        });
    });

    if (preset.recommended_gold !== undefined) {
        spoofedGold = preset.recommended_gold;
        updateGoldDisplay();
    }

    updateBandDisplay('player');
    updateBandDisplay('enemy');

    if (document.getElementById('autoRun').checked) {
        setTimeout(() => createCombat(), 100);
    }
}

// Add minion to band
function addMinion(bandType) {
    const selectId = bandType === 'player' ? 'playerMinionSelect' : 'enemyMinionSelect';
    const goldenId = bandType === 'player' ? 'playerGolden' : 'enemyGolden';

    const select = document.getElementById(selectId);
    const goldenCheckbox = document.getElementById(goldenId);

    const minionName = select.value;
    if (!minionName) {
        alert('Please select a minion');
        return;
    }

    const minionData = availableMinions.find(m => m.name === minionName);
    if (!minionData) {
        alert('Minion not found');
        return;
    }

    const band = bandType === 'player' ? playerBand : enemyBand;

    if (band.length >= 6) {
        alert('Band is full (max 6 minions)');
        return;
    }

    band.push({
        name: minionData.name,
        golden: goldenCheckbox.checked,
        keywords: minionData.keywords,
        effects: minionData.effects
    });

    updateBandDisplay(bandType);

    select.value = '';
    goldenCheckbox.checked = false;
}

// Remove minion from band
function removeMinion(bandType, index) {
    const band = bandType === 'player' ? playerBand : enemyBand;
    band.splice(index, 1);
    updateBandDisplay(bandType);
}

// Move minion position
function moveMinion(bandType, index, direction) {
    const band = bandType === 'player' ? playerBand : enemyBand;

    if (direction === 'up' && index > 0) {
        [band[index], band[index - 1]] = [band[index - 1], band[index]];
    } else if (direction === 'down' && index < band.length - 1) {
        [band[index], band[index + 1]] = [band[index + 1], band[index]];
    }

    updateBandDisplay(bandType);
}

// Update band display
function updateBandDisplay(bandType) {
    const band = bandType === 'player' ? playerBand : enemyBand;
    const containerId = bandType === 'player' ? 'playerBandList' : 'enemyBandList';
    const container = document.getElementById(containerId);

    if (band.length === 0) {
        container.innerHTML = '<div style="text-align: center; opacity: 0.5;">No minions added</div>';
        return;
    }

    container.innerHTML = band.map((minion, index) => {
        const minionData = availableMinions.find(m => m.name === minion.name);
        const health = minion.health || (minionData ? minionData.health : '?');
        const attack = minion.attack || (minionData ? minionData.attack : '?');

        return `
            <div class="minion-list-item"
                 draggable="true"
                 ondragstart="handleDragStart(event, '${bandType}', ${index})"
                 ondragover="handleDragOver(event)"
                 ondrop="handleDrop(event, '${bandType}', ${index})"
                 ondragend="handleDragEnd(event)">
                <div class="minion-info">
                    <div class="minion-name">
                        ${minion.name}
                        ${minion.golden ? '<span class="golden-badge">✨ Golden</span>' : ''}
                    </div>
                    <div class="minion-stats">
                        ❤️ ${health} ⚔️ ${attack}
                        ${minion.keywords ? `| ${minion.keywords.join(', ')}` : ''}
                    </div>
                </div>
                <div class="minion-controls">
                    <div class="position-controls">
                        <button class="position-btn"
                                onclick="moveMinion('${bandType}', ${index}, 'up')"
                                ${index === 0 ? 'disabled' : ''}>
                            ▲
                        </button>
                        <button class="position-btn"
                                onclick="moveMinion('${bandType}', ${index}, 'down')"
                                ${index === band.length - 1 ? 'disabled' : ''}>
                            ▼
                        </button>
                    </div>
                    <button class="remove-btn" onclick="removeMinion('${bandType}', ${index})">×</button>
                </div>
            </div>
        `;
    }).join('');
}

// Create combat session
async function createCombat() {
    if (playerBand.length === 0 || enemyBand.length === 0) {
        alert('Both bands must have at least one minion');
        return;
    }

    const settings = {
        mode: currentMode,
        debug_mode: document.getElementById('debugMode').checked,
        enable_fatigue: document.getElementById('enableFatigue').checked,
        auto_run: document.getElementById('autoRun').checked,
        manual_targeting: document.getElementById('manualTargeting') ?
            document.getElementById('manualTargeting').checked : false
    };

    const goldInput = currentMode === 'step' ?
        document.getElementById('spoofedGold') :
        document.getElementById('spoofedGoldPlayback');

    spoofedGold = goldInput ? parseInt(goldInput.value) || 0 : 0;

    // Get selected hero effects
    const heroSelect = currentMode === 'step' ?
        document.getElementById('heroSelect') :
        document.getElementById('heroSelectPlayback');

    const selectedHeroId = heroSelect ? heroSelect.value : '';
    const heroEffects = selectedHeroId ?
        (availableHeroes.find(h => h.id === selectedHeroId)?.effects || {}) : {};

    manualTargetingEnabled = settings.manual_targeting;
    debugEnabled = settings.debug_mode;

    try {
        const response = await fetch(`${DEV_API_BASE}/combat/create`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                player_band: playerBand,
                enemy_band: enemyBand,
                settings: settings,
                spoofed_gold: spoofedGold,
                spoofed_band_data: spoofedBandData,
                hero_effects: heroEffects
            })
        });

        const result = await response.json();

        if (result.success) {
            currentSessionId = result.session_id;
            currentMode = result.mode;

            if (result.spoofed_gold !== undefined) {
                spoofedGold = result.spoofed_gold;
                updateGoldDisplay();
            }

            console.log('Combat created in', currentMode, 'mode:', result.message);

            if (currentMode === 'step') {
                stepCombatState = result.combat_state;
                displayStepCombat();

                if (debugEnabled && result.debug_info) {
                    displayStepDebugInfo(result.debug_info);
                }

                if (manualTargetingEnabled) {
                    document.getElementById('targetingPanel').style.display = 'block';
                }

            } else if (currentMode === 'playback') {
                if (result.interpreter_data) {
                    initializePlaybackMode(result.interpreter_data);
                }

                if (settings.auto_run) {
                    setTimeout(() => startPlaybackAuto(), 500);
                }
            }

            updateModeDisplay();

        } else {
            alert('Failed to create combat: ' + result.error);
        }
    } catch (error) {
        console.error('Failed to create combat:', error);
        alert('Failed to create combat: ' + error.message);
    }
}

// ===== STEP MODE FUNCTIONS =====

function displayStepCombat() {
    if (!stepCombatState) return;

    const container = document.getElementById('combatDisplay');
    const combatHTML = generateStepCombatHTML(stepCombatState);
    container.innerHTML = combatHTML;

    // Check if combat is over and load post-combat band
    if (stepCombatState.combat_over) {
        loadPostCombatBand();
    }
}

function generateStepCombatHTML(combatState) {
    const isOver = combatState.combat_over;
    const playerBand = combatState.player_band || [];
    const enemyBand = combatState.enemy_band || [];

    const alivePlayerCount = playerBand.filter(m => m.health > 0).length;
    const aliveEnemyCount = enemyBand.filter(m => m.health > 0).length;

    let statusMessage;
    if (isOver) {
        statusMessage = `${combatState.winner === 'player' ? 'Victory!' : combatState.winner === 'enemy' ? 'Defeat!' : 'Draw!'}`;
    } else {
        statusMessage = `Step Mode - Round ${combatState.round_number} - Ready for stepping!`;
    }

    return `
        <div class="combat-zone">
            <h3>⚔️ Step Mode Combat</h3>
            <p style="text-align: center; margin-bottom: 15px; font-size: 1rem;">
                ${statusMessage}
            </p>

            <div class="combat-battlefield">
                <div class="combat-side enemy">
                    <h4>Enemy Band (${aliveEnemyCount}/${enemyBand.length})</h4>
                    <div class="combat-minions">
                        ${generateStepBandHTML(enemyBand, 'enemy')}
                    </div>
                </div>

                <div class="combat-side player">
                    <h4>Your Band (${alivePlayerCount}/${playerBand.length})</h4>
                    <div class="combat-minions">
                        ${generateStepBandHTML(playerBand, 'player')}
                    </div>
                </div>
            </div>

            <div class="step-mode-controls">
                <button class="btn btn-primary" onclick="stepCombat()" ${isOver ? 'disabled' : ''}>
                    ⏭️ Step Once
                </button>
                <button class="btn btn-secondary" onclick="resetStepCombat()">
                    🔄 Reset
                </button>
                <button class="btn btn-danger" onclick="clearCombat()">
                    ❌ Clear
                </button>
            </div>

            <div class="combat-log">
                <h4>📜 Combat Log</h4>
                <div class="combat-log-content">
                    ${combatState.combat_log.map(entry => `<div class="log-entry">${entry}</div>`).join('')}
                </div>
            </div>

            ${isOver ? '<div id="postCombatBandContainer"></div>' : ''}
        </div>
    `;
}

function generateStepBandHTML(band, bandType) {
    if (!band || band.length === 0) {
        return '<div style="text-align: center; opacity: 0.6;">No minions</div>';
    }

    return band.map((minion, index) => {
        // Explicit dead check: only dead if health is a number AND <= 0
        // This prevents null/undefined from being treated as dead
        const isDead = typeof minion.health === 'number' && minion.health <= 0;

        // Use the unified minion card generator from ui-display-desktop.js
        // This ensures dev mode uses EXACT same styling as base game
        return generateUnifiedMinionCard(minion, {
            index: index,
            showIndex: true,
            isClickable: false,
            extraClasses: isDead ? 'dead' : '',
            indicators: []
        });
    }).join('');
}

// NEW: Load and display post-combat band state
async function loadPostCombatBand() {
    if (!currentSessionId) return;

    try {
        const response = await fetch(`${DEV_API_BASE}/combat/${currentSessionId}/post-combat-band`);
        const result = await response.json();

        if (result.success && result.combat_over) {
            displayPostCombatBand(result.post_combat_band);
        }
    } catch (error) {
        console.error('Failed to load post-combat band:', error);
    }
}

// NEW: Display post-combat band showing permanent buffs
function displayPostCombatBand(bandData) {
    const container = document.getElementById('postCombatBandContainer');
    if (!container) return;

    console.log('Post-combat band:', bandData);

    const bandHTML = `
        <div class="post-combat-band" style="margin-top: 20px; padding: 20px; background: rgba(76, 175, 80, 0.1); border-radius: 10px; border: 2px solid #4CAF50;">
            <h4 style="color: #4CAF50; text-align: center; margin-bottom: 15px;">
                📊 Post-Combat Band State (Permanent Buffs)
            </h4>
            <p style="text-align: center; margin-bottom: 15px; font-size: 0.9rem; opacity: 0.8;">
                This shows the band after combat with all permanent stat gains from death toll and other effects
            </p>
            <div class="combat-minions" style="display: flex; gap: 10px; flex-wrap: wrap; justify-content: center;">
                ${bandData.map(minion => generatePostCombatMinionCard(minion)).join('')}
            </div>
        </div>
    `;

    container.innerHTML = bandHTML;
}

// NEW: Generate minion card showing permanent buffs
function generatePostCombatMinionCard(minion) {
    const permHealth = minion.permanent_health || 0;
    const permAttack = minion.permanent_attack || 0;
    const hasPermanentGains = permHealth > 0 || permAttack > 0;

    // Use the unified minion card generator from ui-display-desktop.js
    // Add permanent buff indicator if the minion has permanent gains
    const indicators = hasPermanentGains ? [{
        class: 'permanent-buff-indicator',
        text: `Permanent: +${permAttack}/+${permHealth}`
    }] : [];

    const extraClasses = hasPermanentGains ? 'has-permanent-buffs' : '';

    // Wrap in a div with custom border color for permanent buffs
    const cardHtml = generateUnifiedMinionCard(minion, {
        index: 0,
        showIndex: false,
        isClickable: false,
        extraClasses: extraClasses,
        indicators: indicators
    });

    // Add custom border styling for permanent buffs
    if (hasPermanentGains) {
        return `<div style="border: 2px solid #4CAF50; border-radius: 12px; display: inline-block;">${cardHtml}</div>`;
    }

    return cardHtml;
}

// Step one combat action
async function stepCombat() {
    if (!currentSessionId || currentMode !== 'step') {
        alert('No active step mode combat session');
        return;
    }

    try {
        const response = await fetch(`${DEV_API_BASE}/combat/${currentSessionId}/step`, {
            method: 'POST'
        });

        const result = await response.json();

        if (result.success) {
            stepCombatState = result.combat_state;
            displayStepCombat();

            if (debugEnabled && result.debug_info) {
                displayStepDebugInfo(result.debug_info);
            }

            if (manualTargetingEnabled && result.next_action) {
                displayNextAction(result.next_action);
            }

            if (result.combat_over) {
                console.log(`Step combat ended: ${result.winner} wins!`);
                // Load post-combat band automatically
                setTimeout(() => loadPostCombatBand(), 500);
            }
        } else {
            alert('Step failed: ' + result.error);
        }
    } catch (error) {
        console.error('Failed to step combat:', error);
    }
}

// Reset step combat
async function resetStepCombat() {
    if (!currentSessionId) {
        alert('No active combat session');
        return;
    }

    try {
        console.log('[DEV] Resetting step combat...');

        if (window.animationFunctions && window.animationFunctions.resetAnimationSystem) {
            window.animationFunctions.resetAnimationSystem();
        }

        const response = await fetch(`${DEV_API_BASE}/combat/${currentSessionId}/reset`, {
            method: 'POST'
        });

        const result = await response.json();

        if (result.success && result.mode === 'step') {
            stepCombatState = result.combat_state;
            displayStepCombat();
            console.log('Step combat reset to initial state');

            if (debugEnabled) {
                document.getElementById('debugInfo').innerHTML = '';
            }

            if (manualTargetingEnabled) {
                displayNextAction(null);
                updateOverridesDisplay();
            }
        } else {
            alert('Reset failed: ' + result.error);
        }
    } catch (error) {
        console.error('Failed to reset combat:', error);
        alert('Reset failed: ' + error.message);
    }
}

function displayStepDebugInfo(debugInfo) {
    const panel = document.getElementById('debugPanel');
    const info = document.getElementById('debugInfo');

    panel.style.display = 'block';

    let debugHTML = '<h5>Step Mode Debug Info</h5>';

    if (debugInfo.mock_run) {
        debugHTML += '<div class="debug-section">';
        debugHTML += '<span class="debug-label">💰 Spoofed Game State:</span><br>';
        debugHTML += `<div style="margin-left: 20px; color: #FFD700;">
            Gold: <span class="debug-value">${debugInfo.mock_run.gold}</span><br>
            Band Minions: <span class="debug-value">${debugInfo.mock_run.band ? debugInfo.mock_run.band.length : 0}</span>
        </div>`;
        debugHTML += '</div>';
    }

    if (debugInfo.registry_state) {
        debugHTML += '<div class="debug-section">';
        debugHTML += '<span class="debug-label">Registry State:</span><br>';
        debugHTML += '<pre style="margin-left: 20px; color: #87CEEB;">' + debugInfo.registry_state + '</pre>';
        debugHTML += '</div>';
    }

    if (debugInfo.random_state) {
        debugHTML += '<div class="debug-section">';
        debugHTML += '<span class="debug-label">Random System:</span><br>';
        debugHTML += `<div style="margin-left: 20px;">
            Dev Mode: <span class="debug-value">${debugInfo.random_state.dev_mode ? 'Enabled' : 'Disabled'}</span><br>
            Pending Overrides: <span class="debug-value">${debugInfo.random_state.pending_overrides}</span>
        </div>`;
        debugHTML += '</div>';
    }

    if (debugInfo.step_count !== undefined) {
        debugHTML += '<div class="debug-section">';
        debugHTML += `<span class="debug-label">Steps Taken:</span>
                      <span class="debug-value">${debugInfo.step_count}</span>`;
        debugHTML += '</div>';
    }

    info.innerHTML = debugHTML;
}

// ===== PLAYBACK MODE FUNCTIONS =====

function initializePlaybackMode(interpreterData) {
    console.log('[DEV] Initializing playback mode with production combat system');

    if (window.animationFunctions && window.animationFunctions.resetAnimationSystem) {
        window.animationFunctions.resetAnimationSystem();
    }

    if (!window.combatFunctions || !window.combatFunctions.initializeCombatInterpreter) {
        console.error('[DEV] Combat functions not available');
        return;
    }

    // Initialize the production combat interpreter
    window.combatFunctions.initializeCombatInterpreter(interpreterData);
    console.log('[DEV] Combat interpreter initialized');

    // Use production code to render combat
    displayPlaybackCombat();
}

function displayPlaybackCombat() {
    const container = document.getElementById('combatDisplay');

    // Use production generateCombatUI function
    let productionCombatHTML = '';
    if (typeof generateCombatUI === 'function') {
        productionCombatHTML = generateCombatUI(null);
    } else {
        productionCombatHTML = '<div class="loading">Combat UI not available</div>';
    }

    // Wrap production combat UI with dev controls
    container.innerHTML = `
        <div class="dev-playback-container">
            ${productionCombatHTML}
            <div class="dev-playback-controls">
                <h4>🎬 Dev Playback Controls</h4>
                <div style="display: flex; gap: 10px; justify-content: center; flex-wrap: wrap;">
                    <button class="btn btn-secondary" onclick="clearPlaybackCombat()">
                        🗑️ Clear Combat
                    </button>
                    <button class="btn btn-secondary" onclick="regeneratePlayback()">
                        🔄 Regenerate
                    </button>
                    <button class="btn btn-secondary" onclick="resetPlaybackCombat()">
                        ⏮️ Reset to Start
                    </button>
                </div>
                <div style="margin-top: 10px; font-size: 0.9rem; opacity: 0.8;">
                    💡 Using production combat.js | Gold: ${spoofedGold}
                </div>
            </div>
        </div>
    `;

    // Check if combat is over and load post-combat band
    const combatState = window.combatFunctions ? window.combatFunctions.getFrontendCombatState() : null;
    if (combatState && combatState.combat_over) {
        setTimeout(() => loadPostCombatBand(), 100);
    }
}

function resetPlaybackCombat() {
    console.log('[DEV] Resetting playback combat');

    if (window.animationFunctions && window.animationFunctions.resetAnimationSystem) {
        window.animationFunctions.resetAnimationSystem();
    }

    if (window.combatFunctions && window.combatFunctions.resetCombatState) {
        window.combatFunctions.resetCombatState();
    }

    if (currentSessionId) {
        regeneratePlayback();
    }
}

function clearPlaybackCombat() {
    console.log('Clearing playback combat');

    if (window.animationFunctions && window.animationFunctions.resetAnimationSystem) {
        window.animationFunctions.resetAnimationSystem();
    }

    if (window.combatFunctions && window.combatFunctions.resetCombatState) {
        window.combatFunctions.resetCombatState();
    }

    currentSessionId = null;

    document.getElementById('combatDisplay').innerHTML = `
        <div class="loading">
            Select minions and click "Create Combat" to begin simulation
        </div>
    `;
}

async function regeneratePlayback() {
    if (!currentSessionId) {
        alert('No active session');
        return;
    }

    try {
        console.log('[DEV] Regenerating playback...');

        if (window.animationFunctions && window.animationFunctions.resetAnimationSystem) {
            window.animationFunctions.resetAnimationSystem();
        }

        const response = await fetch(`${DEV_API_BASE}/combat/${currentSessionId}/regenerate-playback`, {
            method: 'POST'
        });

        const result = await response.json();

        if (result.success && result.interpreter_data) {
            console.log('Playback data regenerated');
            initializePlaybackMode(result.interpreter_data);
        } else {
            alert('Failed to regenerate: ' + result.error);
        }
    } catch (error) {
        console.error('Failed to regenerate playback:', error);
        alert('Failed to regenerate: ' + error.message);
    }
}

// ===== COMMON FUNCTIONS =====

function clearCombat() {
    console.log('[DEV] Clearing combat');

    if (window.animationFunctions && window.animationFunctions.resetAnimationSystem) {
        window.animationFunctions.resetAnimationSystem();
    }

    if (currentMode === 'playback') {
        clearPlaybackCombat();
        return;
    }

    currentSessionId = null;
    stepCombatState = null;
    clearStepState();

    document.getElementById('combatDisplay').innerHTML = `
        <div class="loading">
            Select minions and click "Create Combat" to begin simulation
        </div>
    `;
    document.getElementById('debugPanel').style.display = 'none';
    if (document.getElementById('targetingPanel')) {
        document.getElementById('targetingPanel').style.display = 'none';
    }
}

function clearPlaybackState() {
    if (window.combatFunctions && window.combatFunctions.resetCombatState) {
        window.combatFunctions.resetCombatState();
    }
}

function clearStepState() {
    stepCombatState = null;
}

function updateDebugPanel() {
    const panel = document.getElementById('debugPanel');
    const info = document.getElementById('debugInfo');

    if (currentMode === 'step' && debugEnabled) {
        panel.style.display = 'block';
    } else if (currentMode === 'playback') {
        panel.style.display = 'block';

        const combatState = window.combatFunctions ? window.combatFunctions.getFrontendCombatState() : null;

        let animationDebugInfo = 'Not available';
        if (window.animationFunctions && window.animationFunctions.getAnimationDebugInfo) {
            const animDebug = window.animationFunctions.getAnimationDebugInfo();
            animationDebugInfo = `Active: ${animDebug.activeAnimations}, Queued: ${animDebug.queuedAnimations}`;
        }

        info.innerHTML = `
            <h5>Playback Mode Debug Info</h5>
            <div class="debug-section">
                <span class="debug-label">💰 Spoofed Gold:</span>
                <span class="debug-value">${spoofedGold}</span><br>
                <span class="debug-label">Combat Over:</span>
                <span class="debug-value">${combatState ? combatState.combat_over : 'Unknown'}</span><br>
                <span class="debug-label">Animation System:</span>
                <span class="debug-value">${animationDebugInfo}</span>
            </div>
        `;
    } else {
        panel.style.display = 'none';
    }
}

// Drag and drop functions
function initializeDragAndDrop() {}

function handleDragStart(e, bandType, index) {
    draggedMinion = bandType === 'player' ? playerBand[index] : enemyBand[index];
    draggedBandType = bandType;
    draggedIndex = index;
    e.dataTransfer.effectAllowed = 'move';
    e.target.classList.add('dragging');
}

function handleDragOver(e) {
    if (e.preventDefault) {
        e.preventDefault();
    }
    e.dataTransfer.dropEffect = 'move';
    return false;
}

function handleDrop(e, bandType, index) {
    if (e.stopPropagation) {
        e.stopPropagation();
    }

    if (draggedBandType === bandType) {
        const band = bandType === 'player' ? playerBand : enemyBand;

        if (draggedIndex !== index) {
            band.splice(draggedIndex, 1);

            if (draggedIndex < index) {
                band.splice(index - 1, 0, draggedMinion);
            } else {
                band.splice(index, 0, draggedMinion);
            }

            updateBandDisplay(bandType);
        }
    }

    return false;
}

function handleDragEnd(e) {
    e.target.classList.remove('dragging');
    draggedMinion = null;
    draggedBandType = null;
    draggedIndex = -1;
}

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

// Utility functions for manual targeting (Step Mode only)
function displayNextAction(nextAction) {
    const panel = document.getElementById('targetingPanel');
    const content = document.getElementById('targetingContent');

    if (!panel || !content) return;

    if (!nextAction) {
        content.innerHTML = '<p style="text-align: center; opacity: 0.6;">No pending action</p>';
        return;
    }

    const actionType = nextAction.action_type || 'unknown';
    const attacker = nextAction.attacker || {};
    const validTargets = nextAction.valid_targets || [];

    let html = '<div class="next-action-display">';
    html += `<h5>⚔️ Next Action: ${actionType === 'multi_attack' ? 'Multi-Attack' : 'Combat Attack'}</h5>`;

    // Display attacker info
    html += '<div class="attacker-info" style="margin-bottom: 15px; padding: 10px; background: rgba(255,255,255,0.05); border-radius: 5px;">';
    html += `<strong>Attacker:</strong> ${attacker.name} (${attacker.side})<br>`;
    html += `<strong>Stats:</strong> ❤️ ${attacker.health} ⚔️ ${attacker.attack}<br>`;
    if (attacker.abilities && attacker.abilities.length > 0) {
        html += `<strong>Abilities:</strong> ${attacker.abilities.join(', ')}<br>`;
    }
    html += '</div>';

    // Display valid targets
    html += '<div class="valid-targets">';
    html += '<strong>Valid Targets:</strong>';
    if (validTargets.length === 0) {
        html += '<p style="opacity: 0.6;">No valid targets</p>';
    } else {
        html += '<div class="target-list" style="margin-top: 10px;">';
        validTargets.forEach((target, index) => {
            html += `
                <div class="target-option" style="padding: 8px; margin: 5px 0; background: rgba(100,100,100,0.2); border-radius: 5px;">
                    <strong>${target.name}</strong> | ❤️ ${target.health} ⚔️ ${target.attack}
                    ${target.keywords.length > 0 ? `| ${target.keywords.join(', ')}` : ''}
                </div>
            `;
        });
        html += '</div>';
    }
    html += '</div>';

    html += '</div>';

    content.innerHTML = html;
}

async function setTargetOverride(selectionType, targetIdentifier) {
    console.log('Manual targeting not available - backend endpoint not implemented');
}

async function clearAllOverrides() {
    console.log('Manual targeting not available - backend endpoint not implemented');
}

async function updateOverridesDisplay() {
    console.log('Manual targeting not available - backend endpoint not implemented');
}

// Export/Import functions
async function exportConfig() {
    // Client-side export without backend call
    try {
        const exportData = {
            version: '1.0',
            player_band: playerBand,
            enemy_band: enemyBand,
            settings: {
                mode: currentMode,
                debug_mode: document.getElementById('debugMode')?.checked || false,
                enable_fatigue: document.getElementById('enableFatigue')?.checked || true,
                manual_targeting: document.getElementById('manualTargeting')?.checked || false
            },
            spoofed_gold: spoofedGold,
            spoofed_band_data: spoofedBandData
        };

        const dataStr = JSON.stringify(exportData, null, 2);
        const dataUri = 'data:application/json;charset=utf-8,' + encodeURIComponent(dataStr);
        const exportFileDefaultName = `dev_combat_${new Date().toISOString().slice(0,10)}.json`;

        const linkElement = document.createElement('a');
        linkElement.setAttribute('href', dataUri);
        linkElement.setAttribute('download', exportFileDefaultName);
        linkElement.click();

        console.log('Configuration exported successfully');
    } catch (error) {
        console.error('Failed to export config:', error);
        alert('Failed to export: ' + error.message);
    }
}

function importConfig() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'application/json';

    input.onchange = async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = async (event) => {
            try {
                const importData = JSON.parse(event.target.result);

                // Validate import data
                if (!importData.player_band || !importData.enemy_band) {
                    alert('Invalid config file: missing band data');
                    return;
                }

                // Load the configuration
                playerBand = importData.player_band;
                enemyBand = importData.enemy_band;

                if (importData.spoofed_gold !== undefined) {
                    spoofedGold = importData.spoofed_gold;
                    updateGoldDisplay();
                }

                if (importData.spoofed_band_data) {
                    spoofedBandData = importData.spoofed_band_data;
                }

                if (importData.settings && importData.settings.mode) {
                    currentMode = importData.settings.mode;
                    updateModeDisplay();
                }

                // Update UI
                updateBandDisplay('player');
                updateBandDisplay('enemy');

                console.log('Configuration imported successfully');
                alert('Configuration imported! Click "Create Combat" to start.');

            } catch (error) {
                console.error('Failed to parse import file:', error);
                alert('Failed to import: ' + error.message);
            }
        };

        reader.readAsText(file);
    };

    input.click();
}