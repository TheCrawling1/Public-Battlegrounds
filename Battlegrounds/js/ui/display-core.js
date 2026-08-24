// Core display functions - status bar, updateDisplay, main game UI

function generateStatusBar(run, currentZone, isInSubRing, uiState) {
    const health = run.health !== undefined ? run.health : 30;

    // Calculate steps available until next ghost battle
    const EVENTS_FOR_GHOST_BATTLE = 10;
    const ghostMilestone = uiState?.ghost_milestone;
    let nextGhostMilestone;

    if (ghostMilestone) {
        nextGhostMilestone = ghostMilestone;
    } else {
        const currentCycle = Math.floor(run.events_count / EVENTS_FOR_GHOST_BATTLE);
        nextGhostMilestone = (currentCycle + 1) * EVENTS_FOR_GHOST_BATTLE;
    }

    const stepsAvailable = nextGhostMilestone - run.events_count;
    const stepsInCycle = run.events_count % 10;

    // DEBUG: Log step calculation
    console.log('[STEP DEBUG]', {
        events_count: run.events_count,
        ghostMilestone,
        nextGhostMilestone,
        stepsAvailable,
        stepsInCycle,
        extraSteps: stepsAvailable > 10 ? stepsAvailable - 10 : 0
    });

    // Determine which step (0-9) is the ghost battle step in the current cycle
    const currentCycleStart = Math.floor(run.events_count / EVENTS_FOR_GHOST_BATTLE) * EVENTS_FOR_GHOST_BATTLE;
    const currentCycleEnd = currentCycleStart + EVENTS_FOR_GHOST_BATTLE;
    const ghostIsInCurrentCycle = nextGhostMilestone <= currentCycleEnd;
    const ghostStepIndex = ghostIsInCurrentCycle ? (nextGhostMilestone - currentCycleStart - 1) : -1;

    // Roman numerals for step display (Tavern Warmth style)
    const stepRomanNumerals = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X'];

    // Generate 10 step slots with Roman numerals
    const stepSlots = Array.from({length: 10}, (_, i) => {
        const isActive = i === stepsInCycle;
        const isFilled = i < stepsInCycle;
        const isGhostStep = i === ghostStepIndex;
        const classes = ['step-slot'];
        if (isFilled) classes.push('filled');
        if (isActive) classes.push('active');
        if (isGhostStep) classes.push('ghost-step');

        // Ghost step gets its own special tooltip
        if (isGhostStep) {
            return `<div class="${classes.join(' ')} tooltip">
                ${stepRomanNumerals[i]}
                <span class="tooltiptext"><strong>Ghost Battle:</strong> Required battle to progress</span>
            </div>`;
        } else {
            // Regular steps get the general tooltip
            return `<div class="${classes.join(' ')} tooltip">
                ${stepRomanNumerals[i]}
                <span class="tooltiptext">Event ${run.events_count}/${nextGhostMilestone} - Next ghost battle</span>
            </div>`;
        }
    }).join('');

    // Calculate extra steps as complete future 10-step cycles beyond current cycle
    // This ensures +X doesn't drop as you progress through the current cycle
    const completeCyclesAfterCurrent = Math.floor((nextGhostMilestone - currentCycleEnd) / EVENTS_FOR_GHOST_BATTLE);
    const extraSteps = completeCyclesAfterCurrent * EVENTS_FOR_GHOST_BATTLE;
    const extraStepsDisplay = extraSteps > 0 ? `<div class="extra-steps tooltip">
        +${extraSteps}
        <span class="tooltiptext">Extra steps available until ghost</span>
    </div>` : '';

    // Convert tier to Roman numerals
    const romanNumerals = ['0', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X'];
    const tierRoman = romanNumerals[run.current_ring] || run.current_ring;

    // Calculate power level from hero effects (base 1 + upgrades)
    const powerUpgraded = (run.hero_effects && run.hero_effects.power_upgraded) || 0;
    const powerLevel = 1 + powerUpgraded;
    const puckMinions = 1 + powerLevel;  // Puck minions = 1 + power_level

    // Hero definitions with icons and dynamic descriptions based on power level
    const HEROES = {
        'silas': {
            name: 'Silas',
            description: `Shops cost ${powerLevel} less (minimum 0)`,
            icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('coins', 16, 16) : '💰'
        },
        'puck': {
            name: 'Puck',
            description: `When combat starts your first ${puckMinions} minions take their turns`,
            icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('zap', 16, 16) : '⚡'
        },
        'olimpia': {
            name: 'Olimpia',
            description: `Your first ${powerLevel} minion(s) to die are instead stunned and leaped to the rightmost position`,
            icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('shield', 16, 16) : '🛡️'
        }
    };
    const hero = run.hero_id ? HEROES[run.hero_id] : null;

    // Check for Lichdom (second hero power from The Great Work)
    const hasLichdom = run.hero_effects && run.hero_effects.lichdom;
    const lichdomPower = {
        name: 'Lichdom',
        description: 'Effects that cost health instead cost gold',
        icon: typeof generateLucideSVG === 'function' ? generateLucideSVG('crown', 16, 16) : '👑'
    };

    // Generate trophy/wins display
    const ghostWins = run.ghost_wins || 0;
    const maxGhostWins = typeof MAX_GHOST_WINS !== 'undefined' ? MAX_GHOST_WINS : 7;
    const trophySvgPath = '<path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22H17c0-1.76-.85-3.25-2.03-3.79-.5-.23-.97-.66-.97-1.21v-2.34z"/><path d="M18 2H6v7a6 6 0 0 0 12 0z"/>';
    const trophySlots = Array.from({length: maxGhostWins}, (_, i) => {
        const isWon = i < ghostWins;
        const isLatest = isWon && i === ghostWins - 1;
        const classes = ['trophy-slot'];
        if (isWon) classes.push('won');
        if (isLatest) classes.push('latest');
        return `<div class="${classes.join(' ')}"><svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${trophySvgPath}</svg></div>`;
    }).join('');

    return `
        <div class="status-bar">
            <div class="status-cubes-group">
                <div class="status-cube health-cube tooltip">
                    <div class="status-cube-value">${health}</div>
                    <span class="tooltiptext"><strong>Health:</strong> ${health}/30</span>
                </div>
                <div class="status-cube tier-cube tooltip">
                    <div class="status-cube-value">${tierRoman}</div>
                    <span class="tooltiptext"><strong>Tier:</strong> Current tier level (${run.current_ring})</span>
                </div>
                <div class="status-cube gold-cube tooltip">
                    <div class="status-cube-value">${run.resources.gold}</div>
                    <span class="tooltiptext"><strong>Gold:</strong> Available gold for purchases</span>
                </div>
            </div>
            <div class="status-divider"></div>
            <div class="steps-container">
                <div class="steps-line"></div>
                <div class="steps-indicator">
                    <div class="wins-row tooltip">
                        ${trophySlots}
                        <span class="tooltiptext"><strong>Ghost Victories:</strong> ${ghostWins}/${maxGhostWins} - Defeat ${maxGhostWins} ghosts to win!</span>
                    </div>
                    <div class="wins-step-divider"></div>
                    <div class="steps-slots-wrapper">
                        ${stepSlots}
                        ${extraStepsDisplay}
                    </div>
                </div>
                <div class="steps-line"></div>
            </div>
            ${hero ? `
            <div class="status-divider"></div>
            <div class="status-cube hero-cube tooltip">
                <div class="status-cube-value">${hero.icon}</div>
                <span class="tooltiptext"><strong>${hero.name}:</strong> ${hero.description}${hasLichdom ? `<br><br><strong>${lichdomPower.name}:</strong> ${lichdomPower.description}` : ''}</span>
            </div>
            ` : ''}
        </div>
    `;
}

function updateDisplay() {
    console.log('[UPDATE_DISPLAY] updateDisplay() called - FULL DOM REGENERATION!');
    console.trace('[UPDATE_DISPLAY] Call stack:');

    if (!gameData) return;

    // Clean up any active tooltips when UI updates/navigates
    TooltipPortal.cleanup();

    const run = gameData.run;
    const uiState = gameData.ui_state || {};
    const isGhostAvailable = gameData.run.ghost_battle_available || false;
    const isGhostRequired = gameData.ghost_battle_required || false;
    const currentEvent = gameData.current_event || gameData.next_event || 'loading...';
    const hasSelection = run.pending_selection !== null;
    const isInSubRing = uiState.is_in_sub_ring || false;

    // DEBUG: Log UI state from backend
    console.log('[UI_STATE DEBUG]', {
        ghost_milestone: uiState.ghost_milestone,
        events_count: run.events_count,
        ring_upgrade_steps: run.ring_upgrade_steps,
        upcoming_ghost_id: run.upcoming_ghost_id
    });

    // Detect if selection type has changed - clear selections if so
    const newSelectionEventType = hasSelection ? run.pending_selection.event_type : null;
    if (newSelectionEventType !== currentSelectionEventType) {
        console.log(`Selection type changed from ${currentSelectionEventType} to ${newSelectionEventType}, clearing selections`);
        selectedOptions = [];
        currentSelectionEventType = newSelectionEventType;
    }

    // Preserve current selections during UI refresh (only if selection type hasn't changed)
    const previousSelections = [...selectedOptions];

    // Clear minion selection when entering selection events
    if (hasSelection) {
        selectedMinionIndex = -1;
    }

    // Server should provide all UI control states
    const canUsePortal = uiState.can_use_portal || false;
    const availableDestinations = gameData.available_destinations || [];

    // Preserve combat log scroll position before DOM regeneration
    const combatLogContent = document.querySelector('.combat-log-content');
    const preservedCombatScrollTop = combatLogContent ? combatLogContent.scrollTop : null;

    document.getElementById('gameContent').innerHTML = `
        <div class="game-board">
            <div class="main-panel">
                ${generateStatusBar(run, gameData.current_zone || {}, isInSubRing, uiState)}

                ${generateRingProgressBar(run, gameData.ring_events, uiState)}

                ${hasSelection ? generateSelectionUIFromServer(run.pending_selection) :
                    generateMainGameUI(run, isGhostAvailable, isGhostRequired, currentEvent, isInSubRing, canUsePortal, availableDestinations)}

                ${generateBandDisplay(run, uiState)}
            </div>
        </div>
    `;

    // Restore combat log scroll position after DOM regeneration
    // This prevents the "jump to top then back" behavior during animations
    if (preservedCombatScrollTop !== null) {
        const newCombatLogContent = document.querySelector('.combat-log-content');
        if (newCombatLogContent) {
            newCombatLogContent.scrollTop = preservedCombatScrollTop;
        }
    }

    // Note: Active entry highlight is automatically applied during rendering
    // based on getCurrentPosition(), so no need to preserve/restore it manually

    // Restore previous selections if we still have a selection UI
    if (hasSelection && previousSelections.length > 0) {
        setTimeout(() => {
            restoreSelections(previousSelections);
        }, 50);
    } else if (!hasSelection) {
        selectedOptions = [];
    }

    // Attach stone trail animation listeners after DOM update
    // Use requestAnimationFrame + setTimeout to ensure DOM is fully rendered
    requestAnimationFrame(() => {
        setTimeout(attachStoneTrailListeners, 50);
    });
}

// Get a flavorful quote for the current event (shown after event completion)
function getEventQuote(eventType) {
    const quotes = {
        'minion_event': 'A new ally joins your cause.',
        'minion_event_rare': 'A skilled warrior pledges their blade.',
        'minion_event_epic': 'A legendary figure now marches beside you.',
        'minion_event_legendary': 'Destiny\'s champion stands with you.',
        'buff_event': 'Your minions surge with newfound power.',
        'combat_event': 'Victory! The enemies have fallen.',
        'combat_event_hard': 'A hard-fought victory against formidable foes.',
        'shop_event': 'Gold well spent on capable allies.',
        'shop_event_legendary': 'Rare treasures now grace your collection.',
        'shop_event_mythic': 'Legendary artifacts change hands.',
        'statue': 'Golden light fades, leaving something greater behind.',
        'artifact': 'The mystery reveals its secrets.',
        'zone_portal': 'The portal waits for you.',
        'split_event': 'Your choice is made. The path is set.',
        'bell_tower': 'The bell\'s echo fades into silence.'
    };
    return quotes[eventType] || 'The journey continues.';
}

function generateMainGameUI(run, isGhostAvailable, isGhostRequired, currentEvent, isInSubRing, canUsePortal, availableDestinations) {
    // Calculate ring upgrade cost using ring_upgrade_steps field
    // Apply tier_cost_reduction from Grand City Portal Transit
    const eventState = run.event_state ? (typeof run.event_state === 'string' ? JSON.parse(run.event_state) : run.event_state) : {};
    const tierCostReduction = eventState.tier_cost_reduction || 0;
    const upgradeCost = Math.max(0, 15 - (run.ring_upgrade_steps || 0) - tierCostReduction);

    // Calculate steps available until next REQUIRED ghost battle
    const EVENTS_FOR_GHOST_BATTLE = 10;
    const ghostMilestone = gameData?.ui_state?.ghost_milestone;
    let nextGhostMilestone;

    if (ghostMilestone) {
        nextGhostMilestone = ghostMilestone;
    } else {
        // Fallback: calculate next 10-step milestone
        const currentCycle = Math.floor((run.events_count || 0) / EVENTS_FOR_GHOST_BATTLE);
        nextGhostMilestone = (currentCycle + 1) * EVENTS_FOR_GHOST_BATTLE;
    }

    const stepsAvailable = nextGhostMilestone - (run.events_count || 0);
    const isAffordable = stepsAvailable >= upgradeCost;
    const affordableClass = isAffordable ? 'affordable' : '';

    // DEBUG: Log upgrade affordability
    console.log('[UPGRADE DEBUG]', {
        ring_upgrade_steps: run.ring_upgrade_steps,
        upgradeCost,
        ghostMilestone,
        nextGhostMilestone,
        stepsAvailable,
        isAffordable
    });

    // Get a simple quote for the current event
    const eventQuote = getEventQuote(currentEvent);

    return `
        <div class="current-event ${isGhostRequired ? 'ghost-battle-ready' : ''}">
            ${isGhostRequired ? `
                <h3>${typeof generateLucideSVG === 'function' ? generateLucideSVG('ghost', 20, 20) : ''} Ghost Battle Required</h3>
                <p style="font-size: 1.1rem;">You must fight the ghost to continue!</p>
            ` : `<p class="event-quote">${eventQuote}</p>`}
            ${generateEventSpecificUI(isInSubRing, canUsePortal, availableDestinations)}
        </div>

        <div class="controls">
            <button class="btn btn-secondary" onclick="movePlayer('left')" ${isGhostRequired ? 'disabled' : ''}>
                Move Left
            </button>
            <button class="btn btn-secondary" onclick="movePlayer('right')" ${isGhostRequired ? 'disabled' : ''}>
                Move Right
            </button>
            <button class="btn btn-warning ${affordableClass}" onclick="upgradeRing()" ${isGhostRequired || isInSubRing ? 'disabled' : ''}>
                Upgrade ${run.current_ring}|${upgradeCost}
            </button>
            <button class="btn btn-secondary" onclick="previewGhost()" ${isGhostAvailable ? '' : 'disabled'}>
                Preview
            </button>
            <button class="btn btn-info" onclick="fightGhostEarly()" ${isGhostAvailable ? '' : 'disabled'}>
                Fight Ghost
            </button>
        </div>
    `;
}

function generateEventSpecificUI(isInSubRing, canUsePortal, availableDestinations) {
    if (isInSubRing) {
        const subRing = gameData.sub_ring_progress || {};
        return `
            <div style="margin-top: 10px; padding: 10px; background: linear-gradient(135deg, rgba(255, 69, 0, 0.2), rgba(255, 69, 0, 0.1)); border: 2px solid #FF4500; border-radius: 8px;">
                <strong>${subRing.icon || '⚡'} ${subRing.name || 'Sub-Ring'}!</strong>
                <br><small>⬅️ Exit Left → Main Ring Position ${subRing.entry_position || 0}</small>
                <br><small>➡️ Exit Right → Main Ring Position ${subRing.exit_position || 0}</small>
                <br><small style="color: #FFD700;">Sub-Ring Type: ${subRing.description || 'Unknown'}</small>
            </div>
        `;
    }
    return '';
}

