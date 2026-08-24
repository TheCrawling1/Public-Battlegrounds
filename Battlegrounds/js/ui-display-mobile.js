// Mobile UI display functions - inherits from desktop and overrides specific functions
// All desktop functions are available, we only override what needs to be different
// PERCENTAGE-BASED LAYOUT FOR 100vh - GUARANTEED FIT

// Mobile-specific state
let bandDrawerOpen = false;

// Mobile-specific minion selection state (separate from potentially interfering global)
let mobileSelectedMinionIndex = -1;

// Initialize selectedMinionIndex if it doesn't exist
if (typeof selectedMinionIndex === 'undefined') {
    window.selectedMinionIndex = -1;
}

// Sync mobile selection with global selection initially
mobileSelectedMinionIndex = window.selectedMinionIndex || -1;

// ---- Touch event handling and abandon button safety ----

// Stop card-click bubbling when user taps the "× Abandon" button inside a card.
document.addEventListener('click', function (e) {
    const btn = e.target.closest('.abandon-button');
    if (btn) {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();

        // Get the minion index from the button's parent card
        const card = btn.closest('.mobile-minion-card');
        if (card) {
            const index = parseInt(card.getAttribute('data-minion-index'));
            if (typeof abandonMinion === 'function') {
                abandonMinion(e, index);
            }
        }
        return false;
    }
}, { capture: true });

// Safe fallback if swapMinions isn't defined by core/desktop code.
if (typeof window.swapMinions !== 'function') {
    window.swapMinions = function (i, j) {
        const band = gameData?.run?.band;
        if (!band || i === j || i < 0 || j < 0 || i >= band.length || j >= band.length) {
            return;
        }
        [band[i], band[j]] = [band[j], band[i]];
        selectedMinionIndex = -1;
        updateDisplay();
    };
}

// Safe fallback if abandonMinion isn't defined by core/desktop code.
if (typeof window.abandonMinion !== 'function') {
    window.abandonMinion = function (event, index) {
        // Prevent event from bubbling to minion card
        if (event) {
            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();
        }

        // Clear selection
        mobileSelectedMinionIndex = -1;
        selectedMinionIndex = -1;

        // Remove minion from band
        if (gameData && gameData.run && gameData.run.band) {
            const band = gameData.run.band;
            if (index >= 0 && index < band.length) {
                band.splice(index, 1);
                updateDisplay();
            }
        }

        return false;
    };
} else {
    // Wrap the existing function to ensure proper mobile event handling
    const originalAbandonMinion = window.abandonMinion;
    window.abandonMinion = function(event, index) {
        // Extra event prevention for mobile
        if (event) {
            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();
        }

        // Clear mobile selection
        mobileSelectedMinionIndex = -1;

        // Call original function
        const result = originalAbandonMinion(event, index);

        return false;
    };
}

// Override generateStatusBar for mobile - FITS IN 10vh
function generateStatusBar(run, currentZone, isInSubRing, uiState) {
    const zone = currentZone ? `${currentZone.icon}${currentZone.name}` : '🌍';
    const position = isInSubRing ? `${run.sub_ring_position + 1}/${uiState.sub_ring_progress?.events?.length || 1}` : `${run.ring_position + 1}/12`;

    return `
        <div class="status-bar">
            <div class="status-item">
                <span class="value">${zone}</span>
            </div>
            <div class="status-item">
                <span class="value">R${run.current_ring}</span>
            </div>
            <div class="status-item">
                <span class="value">${position}</span>
            </div>
            <div class="status-item">
                <span class="value">${run.events_count}/${run.upcoming_ghost_milestone || (Math.floor(run.events_count / 10) + 1) * 10}</span>
            </div>
            <div class="status-item">
                <span class="value">💰${run.resources.gold}</span>
            </div>
        </div>
    `;
}

// Override generateRingProgressBar for mobile - FITS IN 20vh
function generateRingProgressBar(run, ringEvents, uiState = {}) {
    if (!ringEvents || ringEvents.length === 0) {
        return '';
    }

    // All game logic should come from server via uiState
    const currentPosition = run.ring_position;
    const portalPositions = uiState.portal_positions || {};
    const subRingProgress = uiState.sub_ring_progress || null;
    const isInSubRing = subRingProgress !== null;

    let ringHTML = '';

    // Sub-ring display (if server says we're in one) - FITS IN 20vh
    if (isInSubRing) {
        ringHTML += generateSubRingProgressBar(subRingProgress, run);
    } else {
        // Main ring display - FITS IN 20vh
        ringHTML += `
            <div class="ring-progress">
                <div class="ring-events">
                    ${ringEvents.map((eventType, index) => {
                        // Server should provide event display data
                        const eventData = uiState.event_display_data && uiState.event_display_data[index];

                        // Check if general_event position has been visited (should show as blessing)
                        const visitedGeneralEvents = uiState.visited_general_events || {};
                        const isVisitedGeneralEvent = eventType === 'general_event' && visitedGeneralEvents[String(index)];
                        const displayEventType = isVisitedGeneralEvent ? 'buff_event' : eventType;

                        return generateEventPositionHTML(displayEventType, index, currentPosition, isInSubRing, subRingProgress, portalPositions[index], eventData);
                    }).join('')}
                </div>
            </div>
        `;
    }

    return ringHTML;
}

// Override the main updateDisplay function for mobile layout - PERCENTAGE BASED
function updateDisplay() {
    if (!gameData) return;

    const run = gameData.run;
    const uiState = gameData.ui_state || {};
    const isGhostAvailable = gameData.run.ghost_battle_available || false;
    const isGhostRequired = gameData.ghost_battle_required || false;
    const currentEvent = gameData.current_event || gameData.next_event || 'loading...';
    const hasSelection = run.pending_selection !== null;
    const isInSubRing = uiState.is_in_sub_ring || false;

    // SAFEGUARD: Use mobile-specific selection state to avoid external interference
    const preservedMinionIndex = mobileSelectedMinionIndex;

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
        mobileSelectedMinionIndex = -1;
        selectedMinionIndex = -1;
    } else if (preservedMinionIndex >= 0 && preservedMinionIndex < run.band.length) {
        // Keep mobile selection active and sync with global
        mobileSelectedMinionIndex = preservedMinionIndex;
        selectedMinionIndex = preservedMinionIndex;
    }

    // Server should provide all UI control states
    const canUsePortal = uiState.can_use_portal || false;
    const availableDestinations = gameData.available_destinations || [];

    // PERCENTAGE-BASED LAYOUT: 10% status + 20% ring + 50% content + 10% controls + 10% drawer
    document.getElementById('gameContent').innerHTML = `
        <div class="game-board">
            <div class="main-panel">
                ${generateStatusBar(run, gameData.current_zone || {}, isInSubRing, uiState)}

                ${generateRingProgressBar(run, gameData.ring_events, uiState)}

                <div class="main-content-area">
                    ${hasSelection ? generateSelectionUIFromServer(run.pending_selection) :
                        generateMainGameUI(run, isGhostAvailable, isGhostRequired, currentEvent, isInSubRing, canUsePortal, availableDestinations)}
                </div>

                ${hasSelection ? '' : generateMainControls(run, isGhostAvailable, isGhostRequired, isInSubRing)}
            </div>
        </div>

        ${generateBandDrawer(run)}
    `;

    // Restore previous selections if we still have a selection UI
    if (hasSelection && previousSelections.length > 0) {
        setTimeout(() => {
            restoreSelections(previousSelections);
        }, 50);
    } else if (!hasSelection) {
        selectedOptions = [];
    }
}

// Generate main game controls - FITS IN 10vh
function generateMainControls(run, isGhostAvailable, isGhostRequired, isInSubRing) {
    // Calculate ring upgrade cost using ring_upgrade_steps field
    // Apply tier_cost_reduction from Grand City Portal Transit
    const eventState = run.event_state ? (typeof run.event_state === 'string' ? JSON.parse(run.event_state) : run.event_state) : {};
    const tierCostReduction = eventState.tier_cost_reduction || 0;
    const upgradeCost = Math.max(0, 15 - (run.ring_upgrade_steps || 0) - tierCostReduction);
    const upgradeCostText = upgradeCost > 0 ? `(${upgradeCost})` : '(Free)';

    return `
        <div class="controls">
            <button class="btn btn-secondary" onclick="movePlayer('left')" ${isGhostRequired ? 'disabled' : ''}>
                Left
            </button>
            <button class="btn btn-secondary" onclick="movePlayer('right')" ${isGhostRequired ? 'disabled' : ''}>
                Right ➡️
            </button>
            <button class="btn btn-warning" onclick="upgradeRing()" ${isGhostRequired || isInSubRing ? 'disabled' : ''}>
                🔥 Up ${upgradeCostText}
            </button>
            <button class="btn btn-secondary" onclick="previewGhost()" ${isGhostAvailable ? '' : 'disabled'}>
                👁️ Preview
            </button>
            <button class="btn btn-info" onclick="fightGhostEarly()" ${isGhostAvailable ? '' : 'disabled'}>
                ⚔️ Early
            </button>
            <button class="btn btn-danger" onclick="ghostBattle()" ${isGhostAvailable ? '' : 'disabled'}>
                👻 Fight
            </button>
        </div>
    `;
}

// Override main game UI - FITS IN 50vh SCROLLABLE AREA
function generateMainGameUI(run, isGhostAvailable, isGhostRequired, currentEvent, isInSubRing, canUsePortal, availableDestinations) {
    return `
        <div class="current-event ${isGhostRequired ? 'ghost-battle-ready' : ''}">
            <h3>${isGhostRequired ? '👻 Required!' : formatEventName(currentEvent)}</h3>
        </div>
    `;
}

// Override combat UI for mobile - FITS IN 50vh SCROLLABLE AREA
function generateCombatUI(selection) {
    if (!selection || !selection.combat_state) {
        return `
            <div class="combat-zone">
                <h3>⚠️ Combat Error</h3>
                <div class="selection-controls">
                    <button class="btn btn-primary" onclick="submitSelection()" id="submitBtn">
                        Continue
                    </button>
                </div>
            </div>
        `;
    }

    const combat = selection.combat_state;
    const isOver = combat.combat_over;
    const isComplete = selection.combat_complete;

    // Ensure UI data exists (fallback for edge cases)
    if (!combat.ui_data) {
        const alivePlayerCount = combat.player_band.filter(m => m.health > 0).length;
        const aliveEnemyCount = combat.enemy_band.filter(m => m.health > 0).length;

        combat.ui_data = {
            alive_player_count: alivePlayerCount,
            alive_enemy_count: aliveEnemyCount,
            total_player_count: combat.player_band.length,
            total_enemy_count: combat.enemy_band.length
        };
    }

    // Use server-provided UI data
    const uiData = combat.ui_data;
    const alivePlayerCount = uiData.alive_player_count || 0;
    const aliveEnemyCount = uiData.alive_enemy_count || 0;
    const totalPlayerCount = uiData.total_player_count || combat.player_band.length;
    const totalEnemyCount = uiData.total_enemy_count || combat.enemy_band.length;

    return `
        <div class="combat-zone">
            <h3>R${combat.round_number} ${isOver ? (combat.winner === 'player' ? '🏆' : '💀') : ''}</h3>

            <div class="combat-battlefield">
                <div class="combat-side enemy">
                    <h4>Enemy (${aliveEnemyCount}/${totalEnemyCount})</h4>
                    <div class="combat-minions">
                        ${generateEnemyBandHTML(combat.enemy_band, uiData.active_enemy_index)}
                    </div>
                </div>

                <div class="combat-side player">
                    <h4>Player (${alivePlayerCount}/${totalPlayerCount})</h4>
                    <div class="combat-minions">
                        ${generatePlayerBandHTML(combat.player_band, uiData.active_player_index)}
                    </div>
                </div>
            </div>

            ${generateCombatLog(combat, isOver)}

            ${generateCombatControls(isOver, isComplete)}
        </div>
    `;
}

// Generate compact combat log
function generateCombatLog(combat, isOver) {
    if (!combat.combat_log || combat.combat_log.length === 0) {
        return '';
    }

    return `
        <div class="combat-log">
            <h4>📜 ${isOver ? 'Summary' : 'Log'}</h4>
            <div class="combat-log-content">
                ${combat.combat_log.slice(-5).map((entry, index) => {
                    // Handle both old string format and new object format
                    const message = typeof entry === 'string' ? entry : entry.message;
                    const commandIndex = typeof entry === 'object' ? entry.commandIndex : null;
                    const isClickable = commandIndex !== null;  // Always clickable if has index

                    // Check if this is the current position
                    const currentPosition = window.combatFunctions?.getCurrentPosition?.() ?? -1;
                    const isActive = commandIndex !== null && commandIndex === currentPosition;

                    if (isClickable) {
                        const activeClass = isActive ? ' log-entry-active' : '';
                        return `<div class="log-entry-clickable${activeClass}" data-command-index="${commandIndex}" onclick="window.combatFunctions.jumpToCommandIndex(${commandIndex})" title="Jump to this moment">${message}</div>`;
                    } else {
                        return `<div>${message}</div>`;
                    }
                }).join('')}
            </div>
        </div>
    `;
}

// Override combat controls - FITS IN SELECTION AREA
function generateCombatControls(isOver, isComplete) {
    if (!isOver && !isComplete) {
        return `
            <div class="selection-controls">
                <button class="btn btn-primary" onclick="submitCombatSelection('next')" id="combatNextBtn" ${autoCombatInProgress ? 'disabled' : ''}>
                    Next
                </button>
                <button class="btn btn-warning" onclick="startAutoCombat()" id="combatAutoBtn" ${autoCombatInProgress ? 'disabled' : ''}>
                    ${autoCombatInProgress ? '🤖' : '⚡'}
                </button>
                <button class="btn btn-danger" onclick="submitCombatSelection('end')" id="combatEndBtn" ${autoCombatInProgress ? 'disabled' : ''}>
                    🔚 End
                </button>
                ${autoCombatInProgress ? `
                    <button class="btn btn-secondary" onclick="stopAutoCombat()" id="combatStopBtn">
                        ⏸️ Stop
                    </button>
                ` : ''}
            </div>
        `;
    } else {
        return `
            <div class="selection-controls">
                <button class="btn btn-primary" onclick="submitCombatSelection('continue')" id="combatCompleteBtn">
                    ✅ Continue
                </button>
            </div>
        `;
    }
}

// Updated band drawer using unified minion system - FITS IN 10vh HANDLE + 40vh CONTENT
function generateBandDrawer(run) {
    const hasSelection = run.pending_selection !== null;
    const bandCount = run.band.length;
    const bandPower = calculateBandPower(run.band);

    return `
        <div class="band-drawer-container">
            <button class="band-drawer-handle ${bandDrawerOpen ? 'open' : ''}" onclick="toggleBandDrawer()">
                🛡️ Band (${bandCount}/6) ${bandDrawerOpen ? '▼' : '▲'}
            </button>
            <div class="band-drawer ${bandDrawerOpen ? 'open' : ''}">
                <h3>🛡️ (${bandCount}/6) - ${bandPower}</h3>
                <div class="mobile-band-grid">
                    ${run.band.map((minion, index) => {
                        const isSelected = mobileSelectedMinionIndex === index;

                        const options = {
                            index,
                            showIndex: true,
                            isClickable: !hasSelection,
                            isSelected,
                            isDisabled: hasSelection,
                            showAbandonButton: isSelected && !hasSelection,
                            clickHandler: hasSelection ? '' : `onclick="selectMinionMobile(${index})"`,
                            extraClasses: `mobile-minion-card ${hasSelection ? 'disabled' : ''}`
                        };

                        return generateUnifiedMinionCard(minion, options);
                    }).join('')}
                </div>
            </div>
        </div>
    `;
}

// Mobile-specific minion selection
function selectMinionMobile(index) {
    // Initialize mobile selection if it's undefined
    if (typeof mobileSelectedMinionIndex === 'undefined') {
        mobileSelectedMinionIndex = -1;
    }

    if (mobileSelectedMinionIndex === index) {
        // Clicking same minion deselects it
        mobileSelectedMinionIndex = -1;
        selectedMinionIndex = -1;
    } else if (mobileSelectedMinionIndex >= 0) {
        // Swap with previously selected minion
        if (typeof swapMinions === 'function') {
            swapMinions(mobileSelectedMinionIndex, index);
            // swapMinions should handle clearing selection and updating display
            mobileSelectedMinionIndex = -1;
            selectedMinionIndex = -1;
        }
        return;
    } else {
        // Select this minion
        mobileSelectedMinionIndex = index;
        selectedMinionIndex = index;
    }

    updateDisplay();
}

// Override selectMinion to use mobile version (keep parity with desktop entry point)
function selectMinion(index) {
    selectMinionMobile(index);
}

// Band drawer toggle
function toggleBandDrawer() {
    bandDrawerOpen = !bandDrawerOpen;

    const handle = document.querySelector('.band-drawer-handle');
    const drawer = document.querySelector('.band-drawer');

    if (handle && drawer) {
        const bandCount = gameData?.run?.band?.length || 0;
        if (bandDrawerOpen) {
            handle.classList.add('open');
            drawer.classList.add('open');
            handle.innerHTML = `🛡️ Band (${bandCount}/6) ▼`;
        } else {
            handle.classList.remove('open');
            drawer.classList.remove('open');
            handle.innerHTML = `🛡️ Band (${bandCount}/6) ▲`;
        }
    }
}

// Override band display to return empty for mobile (drawer handles it)
function generateBandDisplay(run) {
    return ''; // Band is handled by drawer on mobile
}

// Override selection options to enforce single-row layout - FITS IN 50vh SCROLLABLE
function generateGenericSelectionUI(selection) {
    return `
        <div class="selection-zone">
            <h3>${selection.title || 'Select'}</h3>

            <div class="selection-options">
                ${selection.options.map(option => generateSelectionCardFromServer(option)).join('')}
            </div>

            <div class="selection-controls">
                <button class="btn btn-primary" onclick="submitSelection()" id="submitBtn" disabled>
                    OK
                </button>
                <button class="btn btn-secondary" onclick="clearSelection()">
                    🔄 Clear
                </button>
            </div>
        </div>
    `;
}

// Override target minion UI - MINIMAL, FITS IN SCROLLABLE AREA
function generateTargetMinionUI(selection) {
    if (!selection || !selection.effect_preview) {
        return `
            <div class="selection-zone">
                <h3>⚠️ Target Error</h3>
                <div class="selection-controls">
                    <button class="btn btn-secondary" onclick="goBack()">
                        Back
                    </button>
                </div>
            </div>
        `;
    }

    const effect = selection.effect_preview;

    return `
        <div class="selection-zone">
            <h3>${effect.name}</h3>

            <div class="selection-options">
                ${selection.options.map(option => generateSelectionCardFromServer(option)).join('')}
            </div>

            <div class="selection-controls">
                <button class="btn btn-primary" onclick="submitSelection()" id="submitBtn" disabled>
                    Apply
                </button>
                <button class="btn btn-secondary" onclick="goBack()">
                    ⬅️ Back
                </button>
            </div>
        </div>
    `;
}

// Override replacement UI - MINIMAL, FITS IN SCROLLABLE AREA
function generateReplacementUI(selection) {
    if (selection.event_type === 'replacement') {
        return `
            <div class="selection-zone">
                <h3>🔄 Replace</h3>

                <div class="selection-options">
                    ${selection.options.map(option => generateSelectionCardFromServer(option)).join('')}
                </div>

                <div class="selection-controls">
                    <button class="btn btn-primary" onclick="submitSelection()" id="submitBtn" disabled>
                        OK
                    </button>
                    <button class="btn btn-secondary" onclick="clearSelection()">
                        🔄 Clear
                    </button>
                </div>
            </div>
        `;
    } else if (selection.event_type === 'confirm_replacement' || selection.event_type === 'confirm_shop_replacement') {
        return `
            <div class="selection-zone">
                <h3>🔄 Confirm</h3>

                <div class="selection-options">
                    ${selection.options.map(option => generateSelectionCardFromServer(option)).join('')}
                </div>

                <div class="selection-controls">
                    <button class="btn btn-primary" onclick="submitSelection()" id="submitBtn" disabled>
                        Replace
                    </button>
                    <button class="btn btn-secondary" onclick="goBack()">
                        Back
                    </button>
                </div>
            </div>
        `;
    }
}

// Override zone portal UI - MINIMAL, FITS IN SCROLLABLE AREA
function generateZonePortalUI(selection) {
    if (!selection || !selection.options) {
        return `
            <div class="selection-zone">
                <h3>⚠️ Portal Error</h3>
                <div class="selection-controls">
                    <button class="btn btn-secondary" onclick="clearSelection()">
                        🔄 Clear
                    </button>
                </div>
            </div>
        `;
    }

    return `
        <div class="zone-portal-zone">
            <h3>🌀 Portal</h3>

            <div class="selection-options">
                ${selection.options.map(option => generateZonePortalCard(option)).join('')}
            </div>

            <div class="selection-controls">
                <button class="btn btn-primary" onclick="submitSelection()" id="submitBtn" disabled>
                    Go
                </button>
                <button class="btn btn-secondary" onclick="clearSelection()">
                    🔄 Clear
                </button>
            </div>
        </div>
    `;
}

// Override generateSelectionCardFromServer to use unified system for minions
function generateSelectionCardFromServer(option) {
    // Server should provide complete card display data
    const isAffordable = option.affordable !== false && option.disabled !== true;
    const cardClass = `selection-card ${!isAffordable ? 'unaffordable' : ''}`;

    let content = '';

    // Use unified minion system for minion cards
    if (option.type === 'minion' || option.type === 'purchase') {
        const minion = option.data;

        const options = {
            index: 0,
            showIndex: false, // Don't show index in selections
            isClickable: false, // Click handled by parent selection card
            isSelected: false,
            isDisabled: false,
            showAbandonButton: false,
            clickHandler: '',
            extraClasses: 'selection-minion-card'
        };

        content = generateUnifiedMinionCard(minion, options);

        // Add cost display if present - MINIMAL
        if (option.cost > 0) {
            content += `<div style="color: #FFD700; font-size: 0.6rem; text-align: center; margin-top: 1px;">💰${option.cost}</div>`;
        }

    } else if (option.type === 'apply_targeted_effect') {
        // Show minion info for targeting using unified system
        const band = gameData.run.band;
        const minion = band[option.target_index];

        const options = {
            index: option.target_index,
            showIndex: true,
            isClickable: false,
            isSelected: false,
            isDisabled: false,
            showAbandonButton: false,
            clickHandler: '',
            extraClasses: 'selection-minion-card'
        };

        content = generateUnifiedMinionCard(minion, options);

    } else if (option.type === 'replace_with' || option.type === 'shop_replace_with') {
        // Show existing minion for replacement choice using unified system
        const band = gameData.run.band;
        const minion = band[option.replace_index];

        const options = {
            index: option.replace_index,
            showIndex: true,
            isClickable: false,
            isSelected: false,
            isDisabled: false,
            showAbandonButton: false,
            clickHandler: '',
            extraClasses: 'selection-minion-card replacement-target'
        };

        content = generateUnifiedMinionCard(minion, options);
        content += '<div style="background: rgba(244, 67, 54, 0.9); color: white; padding: 1px 2px; border-radius: 2px; font-size: 0.5rem; position: absolute; bottom: 20px; left: 50%; transform: translateX(-50%); z-index: 4;">Replace</div>';

    } else if (option.type === 'choose_buff') {
        // Only show the message (e.g., "+3 Health")
        content = `
            <div style="padding: 8px; text-align: center; font-size: 0.6rem;">
                <div style="font-weight: bold;">${option.message}</div>
            </div>
        `;
    } else if (option.type === 'skip') {
        content = `
            <div style="padding: 8px; text-align: center; font-size: 0.6rem; color: #ff6b6b;">
                <div>❌ Skip</div>
            </div>
        `;
    } else if (option.type === 'sacrifice_target' || option.type === 'golden_target') {
        // Show minion card for sacrifice/golden target selection
        const minion = option.data;

        if (minion) {
            const options = {
                index: option.target_index,
                showIndex: true,
                isClickable: false,
                isSelected: false,
                isDisabled: false,
                showAbandonButton: false,
                clickHandler: '',
                extraClasses: 'selection-minion-card'
            };

            content = generateUnifiedMinionCard(minion, options);

            // Add indicator based on type
            if (option.type === 'sacrifice_target') {
                content += '<div style="background: rgba(244, 67, 54, 0.9); color: white; padding: 1px 2px; border-radius: 2px; font-size: 0.5rem; position: absolute; bottom: 20px; left: 50%; transform: translateX(-50%); z-index: 4;">Sacrifice</div>';
            } else if (option.type === 'golden_target') {
                content += '<div style="background: rgba(255, 193, 7, 0.9); color: black; padding: 1px 2px; border-radius: 2px; font-size: 0.5rem; position: absolute; bottom: 20px; left: 50%; transform: translateX(-50%); z-index: 4;">Make Golden</div>';
            }
        } else {
            content = `
                <div style="padding: 8px; text-align: center; font-size: 0.6rem;">
                    <div>${option.message || option.type}</div>
                </div>
            `;
        }
    } else {
        content = `
            <div style="padding: 8px; text-align: center; font-size: 0.6rem;">
                <div>${option.message || option.type}</div>
            </div>
        `;
    }

    const clickAction = isAffordable ? `onclick="toggleSelection('${option.id}')"` : '';

    return `
        <div class="${cardClass}" id="card_${option.id}" ${clickAction} data-option-id="${option.id}">
            ${content}
        </div>
    `;
}

// Override zone portal card - MINIMAL
function generateZonePortalCard(option) {
    const cardClass = `selection-card zone-portal-card`;

    let content = '';

    if (option.type === 'travel_to_zone') {
        const zoneData = option.zone_data;
        content = `
            <div style="text-align: center; padding: 6px; font-size: 0.6rem;">
                <div style="font-size: 1rem; margin-bottom: 2px;">${zoneData.icon || '🌍'}</div>
                <div style="font-weight: bold; color: #FFD700;">${zoneData.name}</div>
            </div>
        `;
    } else if (option.type === 'stay_in_zone') {
        const currentZone = gameData.current_zone || {};
        content = `
            <div style="text-align: center; padding: 6px; font-size: 0.6rem;">
                <div style="font-size: 1rem; margin-bottom: 2px;">${currentZone.icon || '🌍'}</div>
                <div style="font-weight: bold; color: #FFD700;">Stay</div>
            </div>
        `;
    }

    const clickAction = `onclick="toggleSelection('${option.id}')"`;

    return `
        <div class="${cardClass}" id="card_${option.id}" ${clickAction} data-option-id="${option.id}">
            ${content}
        </div>
    `;
}

// Override generateSubRingProgressBar - FITS IN 20vh
function generateSubRingProgressBar(subRingProgress, run) {
    if (!subRingProgress || !subRingProgress.events) {
        return '';
    }

    const currentPosition = run.sub_ring_position;
    const events = subRingProgress.events;

    return `
        <div class="sub-ring-progress">
            <h3>${subRingProgress.icon || '⚡'} ${subRingProgress.name}</h3>
            <div class="sub-ring-events">
                ${events.map((eventType, index) => {
                    const eventInfo = EVENT_ICONS[eventType] || { icon: '❓', name: 'Unknown' };
                    let eventClass = 'sub-ring-event ';

                    if (index === currentPosition) {
                        eventClass += 'current';
                    } else if (index < currentPosition) {
                        eventClass += 'completed';
                    } else {
                        eventClass += 'upcoming';
                    }

                    return `
                        <div class="${eventClass}" data-event-type="${eventType}">
                            <span class="position-number">${index}</span>
                            <span class="event-icon">${eventInfo.icon}</span>
                            <span class="event-name">${eventInfo.name}</span>
                        </div>
                    `;
                }).join('')}
            </div>
        </div>
    `;
}

// Close drawer when interacting with main UI
document.addEventListener('click', function(event) {
    // Close drawer if clicking outside band drawer area and drawer is open
    if (bandDrawerOpen && !event.target.closest('.band-drawer-container')) {
        // Only close if not clicking on minion-related elements or selection cards
        if (!event.target.closest('.mobile-minion-card') &&
            !event.target.closest('.abandon-button') &&
            !event.target.closest('.band-drawer-handle') &&
            !event.target.closest('.selection-card') &&
            !event.target.closest('.btn')) {

            bandDrawerOpen = false;
            const handle = document.querySelector('.band-drawer-handle');
            const drawer = document.querySelector('.band-drawer');
            if (handle && drawer) {
                handle.classList.remove('open');
                drawer.classList.remove('open');
                const bandCount = gameData?.run?.band?.length || 0;
                handle.innerHTML = `🛡️ Band (${bandCount}/6) ▲`;
            }
        }
    }
});

// Prevent drawer from interfering with game interactions
document.addEventListener('touchstart', function(event) {
    const target = event.target;

    // Don't interfere with minion card touches
    if (target.closest('.mobile-minion-card')) {
        return;
    }

    // If touching a game element and drawer is open, close drawer first
    if (bandDrawerOpen &&
        (target.closest('.ring-event') ||
         target.closest('.selection-card') ||
         target.closest('.btn:not(.band-drawer-handle)') ||
         target.closest('.current-event'))) {

        // Close drawer but don't prevent the event
        bandDrawerOpen = false;
        const handle = document.querySelector('.band-drawer-handle');
        const drawer = document.querySelector('.band-drawer');
        if (handle && drawer) {
            handle.classList.remove('open');
            drawer.classList.remove('open');
            const bandCount = gameData?.run?.band?.length || 0;
            handle.innerHTML = `🛡️ Band (${bandCount}/6) ▲`;
        }
    }
});