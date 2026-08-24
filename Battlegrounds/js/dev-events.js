// Dev Mode Event Testing - Frontend JavaScript
// Allows testing and previewing events, icons, and selection screens

const DEV_EVENTS_API = '/api/dev-events';

// Global state
let currentSessionId = null;
let selectedEventType = null;
let availableEvents = {};
let eventIcons = {};
let availableMinions = [];
let currentBand = [];
let ringPreviewData = [];

// Selection state - game-core.js declares selectedOptions with let
// We need to ensure we can access it. Use window to make it truly global.
if (typeof window.selectedOptions === 'undefined') {
    window.selectedOptions = [];
}

// Define toggleSelection for main game UI compatibility
// This is called by onclick handlers in generateSelectionCardFromServer
function toggleSelection(optionId) {
    console.log('Dev mode toggleSelection:', optionId);

    const card = document.getElementById(`card_${optionId}`);
    if (!card) {
        console.error('Card not found:', `card_${optionId}`);
        return;
    }

    const index = window.selectedOptions.indexOf(optionId);

    if (index === -1) {
        // Add to selection
        window.selectedOptions.push(optionId);
        card.classList.add('selected');
        console.log('Added to selection. Current selections:', window.selectedOptions);
    } else {
        // Remove from selection
        window.selectedOptions.splice(index, 1);
        card.classList.remove('selected');
        console.log('Removed from selection. Current selections:', window.selectedOptions);
    }

    updateSubmitButton();
}

// Update submit button state
function updateSubmitButton() {
    const submitBtn = document.getElementById('submitBtn');
    if (!submitBtn) return;

    const selectedCount = window.selectedOptions.length;

    submitBtn.disabled = selectedCount === 0;
    submitBtn.textContent = `Confirm Selection (${selectedCount})`;

    if (selectedCount > 0) {
        submitBtn.classList.remove('btn-secondary');
        submitBtn.classList.add('btn-primary');
    } else {
        submitBtn.classList.remove('btn-primary');
        submitBtn.classList.add('btn-secondary');
    }
}

// Clear all selections
function clearSelection() {
    console.log('Clearing selection');
    window.selectedOptions.forEach(optionId => {
        const card = document.getElementById(`card_${optionId}`);
        if (card) {
            card.classList.remove('selected');
        }
    });
    window.selectedOptions = [];
    updateSubmitButton();
}

// Submit selection to dev mode backend
function submitSelection() {
    console.log('submitSelection called');
    console.log('  currentSessionId:', currentSessionId);
    console.log('  window.selectedOptions:', window.selectedOptions);

    if (!currentSessionId) {
        console.error('No active dev session');
        alert('Error: No active dev session. Did you trigger an event first?');
        return;
    }

    if (window.selectedOptions.length === 0) {
        console.log('No selections to submit');
        alert('Error: No selections to submit. Please select an option first.');
        return;
    }

    console.log('Dev mode submitting selections:', window.selectedOptions);
    resolveSelection([...window.selectedOptions]);
    window.selectedOptions = [];
}

// Go back to previous selection (for multi-step events)
function goBack() {
    console.log('Dev mode going back...');

    // Try the back option if it exists
    const backOption = document.querySelector('[data-option-id="back"]');
    if (backOption) {
        console.log('Back option found, using back navigation');
        clearSelection();
        toggleSelection('back');
        submitSelection();
    } else {
        console.log('No back option found, clearing selection');
        clearSelection();
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('Dev Events Mode loaded');
    loadEventList();
    loadEventIcons();
    loadMinions();
    updateRingPreview();
});

// ==================== DATA LOADING ====================

async function loadEventList() {
    try {
        const response = await fetch(`${DEV_EVENTS_API}/events/list`);
        const result = await response.json();

        if (result.success) {
            availableEvents = result.events;
            renderEventCategories();
            console.log(`Loaded ${result.total} events`);
        }
    } catch (error) {
        console.error('Failed to load events:', error);
        document.getElementById('eventCategories').innerHTML =
            '<div class="empty-state">Failed to load events</div>';
    }
}

async function loadEventIcons() {
    try {
        const response = await fetch(`${DEV_EVENTS_API}/events/icons`);
        const result = await response.json();

        if (result.success) {
            eventIcons = result.icons;
            renderIconGallery();
        } else {
            document.getElementById('iconGallery').innerHTML =
                '<div class="empty-state">Failed to load icons</div>';
        }
    } catch (error) {
        console.error('Failed to load icons:', error);
        document.getElementById('iconGallery').innerHTML =
            `<div class="empty-state">Error: ${error.message}</div>`;
    }
}

async function loadMinions() {
    try {
        const response = await fetch(`${DEV_EVENTS_API}/minions`);
        const result = await response.json();

        if (result.success) {
            availableMinions = result.minions;
            populateMinionSelect();
        }
    } catch (error) {
        console.error('Failed to load minions:', error);
    }
}

async function updateRingPreview() {
    const ring = document.getElementById('ringLevel').value;
    const zone = document.getElementById('zoneSelect').value;

    try {
        const response = await fetch(`${DEV_EVENTS_API}/events/ring-preview?ring=${ring}&zone=${zone}`);
        const result = await response.json();

        if (result.success) {
            ringPreviewData = result.positions;
            renderRingPreview();
        }
    } catch (error) {
        console.error('Failed to load ring preview:', error);
    }
}

// ==================== UI RENDERING ====================

function renderEventCategories() {
    const container = document.getElementById('eventCategories');

    let html = '';

    // Basic Gameplay Events
    html += '<div class="event-category">';
    html += '<h5>Basic Gameplay</h5>';
    html += '<div class="event-list">';
    for (const [eventId, event] of Object.entries(availableEvents.basic_gameplay || {})) {
        html += renderEventItem(eventId, event);
    }
    html += '</div></div>';

    // Story Events (bell_tower)
    html += '<div class="event-category">';
    html += '<h5>Story Events</h5>';
    html += '<div class="event-list">';
    for (const [eventId, event] of Object.entries(availableEvents.story || {})) {
        html += renderEventItem(eventId, event);
    }
    html += '</div></div>';

    // Crossroads Events
    html += '<div class="event-category">';
    html += '<h5>Crossroads Events</h5>';
    html += '<div class="event-list">';
    for (const [eventId, event] of Object.entries(availableEvents.crossroads || {})) {
        html += renderEventItem(eventId, event);
    }
    html += '</div></div>';

    // Fey Zone Events
    html += '<div class="event-category">';
    html += '<h5>Fey Zone Events</h5>';
    html += '<div class="event-list">';
    for (const [eventId, event] of Object.entries(availableEvents.fey_zone || {})) {
        html += renderEventItem(eventId, event);
    }
    html += '</div></div>';

    // Construct Zone Events
    html += '<div class="event-category">';
    html += '<h5>Construct Zone Events</h5>';
    html += '<div class="event-list">';
    for (const [eventId, event] of Object.entries(availableEvents.construct_zone || {})) {
        html += renderEventItem(eventId, event);
    }
    html += '</div></div>';

    // Cult Zone Events
    html += '<div class="event-category">';
    html += '<h5>Cult Zone Events</h5>';
    html += '<div class="event-list">';
    for (const [eventId, event] of Object.entries(availableEvents.cult_zone || {})) {
        html += renderEventItem(eventId, event);
    }
    html += '</div></div>';

    // Undead Zone Events
    html += '<div class="event-category">';
    html += '<h5>Undead Zone Events</h5>';
    html += '<div class="event-list">';
    for (const [eventId, event] of Object.entries(availableEvents.undead_zone || {})) {
        html += renderEventItem(eventId, event);
    }
    html += '</div></div>';

    // Beast Wildlands Zone Events
    html += '<div class="event-category">';
    html += '<h5>Beast Wildlands Events</h5>';
    html += '<div class="event-list">';
    for (const [eventId, event] of Object.entries(availableEvents.beast_wildlands || {})) {
        html += renderEventItem(eventId, event);
    }
    html += '</div></div>';

    container.innerHTML = html;
}

function renderEventItem(eventId, event) {
    const iconName = event.icon || 'help-circle';
    const isSelected = selectedEventType === eventId;

    return `
        <div class="event-item ${isSelected ? 'selected' : ''}"
             onclick="selectEvent('${eventId}')"
             title="${event.description || ''}">
            <div class="event-icon">${generateLucideSVG(iconName, 24, 24)}</div>
            <div class="event-name">${eventId}</div>
        </div>
    `;
}

function renderIconGallery() {
    const container = document.getElementById('iconGallery');

    let html = '';
    for (const [eventId, iconData] of Object.entries(eventIcons)) {
        html += `
            <div class="icon-item" onclick="selectEvent('${eventId}')" title="${iconData.display_name}">
                <div class="icon-svg">${iconData.svg}</div>
                <div class="icon-name">${iconData.display_name}</div>
            </div>
        `;
    }

    container.innerHTML = html || '<div class="empty-state">No icons loaded</div>';
}

function renderRingPreview() {
    const container = document.getElementById('ringPreview');
    const currentPosition = parseInt(document.getElementById('ringPosition').value);

    let html = '';
    for (const pos of ringPreviewData) {
        const isCurrent = pos.position === currentPosition;
        let iconSvg = '';
        let displayName = '';

        if (pos.type === 'simple') {
            iconSvg = generateLucideSVG(pos.icon, 24, 24);
            displayName = pos.display_name;
        } else if (pos.type === 'split') {
            iconSvg = generateLucideSVG('git-branch', 24, 24);
            displayName = 'Split';
        } else if (pos.type === 'branching_choice') {
            iconSvg = generateLucideSVG('git-merge', 24, 24);
            displayName = pos.title || 'Choice';
        }

        html += `
            <div class="ring-position ${isCurrent ? 'current' : ''}"
                 onclick="selectRingPosition(${pos.position})"
                 title="${displayName}">
                <div class="pos-number">Pos ${pos.position}</div>
                <div class="pos-icon">${iconSvg}</div>
                <div class="pos-name">${displayName}</div>
            </div>
        `;
    }

    container.innerHTML = html;
}

function populateMinionSelect() {
    const select = document.getElementById('minionSelect');

    // Group by tier
    const tiers = {};
    availableMinions.forEach(minion => {
        const tier = minion.tier || 1;
        if (!tiers[tier]) tiers[tier] = [];
        tiers[tier].push(minion);
    });

    let html = '<option value="">Add minion...</option>';
    for (const tier of Object.keys(tiers).sort()) {
        html += `<optgroup label="Tier ${tier}">`;
        for (const minion of tiers[tier]) {
            html += `<option value="${minion.name}">${minion.name} (${minion.health}/${minion.attack})</option>`;
        }
        html += '</optgroup>';
    }

    select.innerHTML = html;
}

function updateBandDisplay() {
    const container = document.getElementById('bandList');

    if (currentBand.length === 0) {
        container.innerHTML = '<div class="empty-state" style="padding: 10px;">No minions</div>';
        return;
    }

    let html = '';
    currentBand.forEach((minion, index) => {
        html += `
            <div class="band-minion">
                <span>${minion.name} (${minion.health}/${minion.attack})</span>
                <button class="remove-btn" onclick="removeMinionFromBand(${index})">x</button>
            </div>
        `;
    });

    container.innerHTML = html;
}

// ==================== EVENT HANDLERS ====================

function selectEvent(eventId) {
    selectedEventType = eventId;
    renderEventCategories();

    // Show scaling preview for certain event types
    const scalingEventTypes = ['buff_event', 'combat_event', 'combat_event_hard', 'shop_event'];

    if (scalingEventTypes.includes(eventId)) {
        loadScalingPreview(eventId);
    } else {
        document.getElementById('scalingPreviewSection').style.display = 'none';
    }

    console.log('Selected event:', eventId);
}

function selectRingPosition(position) {
    document.getElementById('ringPosition').value = position;
    renderRingPreview();

    // Auto-select the event at this position if it's a simple event
    const posData = ringPreviewData.find(p => p.position === position);
    if (posData && posData.type === 'simple') {
        selectEvent(posData.event_type);
    }
}

function addMinionToBand() {
    const select = document.getElementById('minionSelect');
    const minionName = select.value;

    if (!minionName) {
        alert('Please select a minion');
        return;
    }

    if (currentBand.length >= 6) {
        alert('Band is full (max 6 minions)');
        return;
    }

    const minionData = availableMinions.find(m => m.name === minionName);
    if (minionData) {
        currentBand.push({...minionData});
        updateBandDisplay();
    }

    select.value = '';
}

function removeMinionFromBand(index) {
    currentBand.splice(index, 1);
    updateBandDisplay();
}

// ==================== EVENT TRIGGERING ====================

async function triggerEvent() {
    if (!selectedEventType) {
        alert('Please select an event type first');
        return;
    }

    // Build request body
    const requestBody = {
        event_type: selectedEventType
    };

    // If we have an existing session, reuse it (state persists)
    if (currentSessionId) {
        requestBody.session_id = currentSessionId;
        console.log('Continuing existing session:', currentSessionId);
    } else {
        // New session - use UI config
        requestBody.run_config = {
            ring: parseInt(document.getElementById('ringLevel').value),
            position: parseInt(document.getElementById('ringPosition').value),
            zone: document.getElementById('zoneSelect').value,
            gold: parseInt(document.getElementById('goldAmount').value) || 10,
            health: parseInt(document.getElementById('healthAmount').value) || 100,
            band: currentBand.map(m => ({name: m.name})),
            event_state: {
                bells_rung: parseInt(document.getElementById('bellsRung').value) || 0
            }
        };
        console.log('Creating new session with config:', requestBody.run_config);
    }

    try {
        const response = await fetch(`${DEV_EVENTS_API}/events/create`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(requestBody)
        });

        const result = await response.json();

        if (result.success) {
            currentSessionId = result.session_id;
            renderEventPreview(result);
            showDebugInfo(result);
            // Sync UI with run state
            syncUIFromRunState(result.run_state);
            console.log('Event created:', result);
            if (result.continued_session) {
                console.log('Session continued - state preserved');
            }
        } else {
            alert('Failed to trigger event: ' + result.error);
        }
    } catch (error) {
        console.error('Failed to trigger event:', error);
        alert('Failed to trigger event: ' + error.message);
    }
}

// Reset session - start fresh with new MockRun
function resetSession() {
    currentSessionId = null;
    console.log('Session reset - next event will create new run');
    // Clear the event preview
    const previewContainer = document.getElementById('eventPreview');
    if (previewContainer) {
        previewContainer.innerHTML = '<p class="text-muted">Click "Trigger Event" to start a new session</p>';
    }
    alert('Session reset. Next event will use the current UI configuration.');
}

// Sync UI elements from run state (after event resolution)
function syncUIFromRunState(runState) {
    if (!runState) return;

    // Update gold display
    const goldInput = document.getElementById('goldAmount');
    if (goldInput && runState.gold !== undefined) {
        goldInput.value = runState.gold;
    }

    // Update health display
    const healthInput = document.getElementById('healthAmount');
    if (healthInput && runState.health !== undefined) {
        healthInput.value = runState.health;
    }

    // Update band display
    if (runState.band) {
        currentBand = runState.band;
        updateBandDisplay();
    }

    // Update event state (bells_rung, etc.)
    if (runState.event_state) {
        const bellsInput = document.getElementById('bellsRung');
        if (bellsInput && runState.event_state.bells_rung !== undefined) {
            bellsInput.value = runState.event_state.bells_rung;
        }
    }

    console.log('UI synced from run state:', runState);
}

async function resolveSelection(selections) {
    console.log('resolveSelection called with:', selections);

    if (!currentSessionId) {
        alert('No active event session');
        return;
    }

    // Check if combat interpreter is initialized and this is a combat action
    // If so, use the local combat.js functions instead of making an API call
    const combatActions = ['next', 'auto', 'end'];
    if (selections.length === 1 && combatActions.includes(selections[0])) {
        // Check if combat is initialized via combatFunctions
        if (window.combatFunctions && window.combatFunctions.isCombatInitialized &&
            window.combatFunctions.isCombatInitialized()) {
            console.log('[DEV-EVENTS] Combat interpreter active, handling locally');

            const action = selections[0];
            if (action === 'next') {
                if (window.combatFunctions.stepThroughOneCommand) {
                    window.combatFunctions.stepThroughOneCommand();
                }
                if (window.updateDisplay) window.updateDisplay();
                return;
            } else if (action === 'auto') {
                if (window.combatFunctions.startAutoCombat) {
                    window.combatFunctions.startAutoCombat();
                }
                return;
            } else if (action === 'end') {
                if (window.combatFunctions.skipToEndCommand) {
                    window.combatFunctions.skipToEndCommand();
                }
                if (window.updateDisplay) window.updateDisplay();
                return;
            }
        }
    }

    try {
        console.log('Sending POST to:', `${DEV_EVENTS_API}/events/${currentSessionId}/select`);
        const response = await fetch(`${DEV_EVENTS_API}/events/${currentSessionId}/select`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({selections: selections})
        });

        console.log('Response status:', response.status);
        const result = await response.json();
        console.log('Response data:', result);

        if (result.success) {
            console.log('Selection successful! has_pending=' + result.has_pending_selection);

            // Sync UI with updated run state (gold, band, etc.)
            syncUIFromRunState(result.run_state);

            // Check if this is a combat response with interpreter data
            // Initialize the combat interpreter so playback controls work
            if (result.result && result.result.interpreter_data) {
                console.log('[DEV-EVENTS] Combat response - initializing interpreter');
                if (window.combatFunctions && window.combatFunctions.initializeCombatInterpreter) {
                    window.combatFunctions.initializeCombatInterpreter(result.result.interpreter_data);
                    console.log('[DEV-EVENTS] Combat interpreter initialized');
                }
            }

            // Show debug info first (with safe stringify)
            try {
                showDebugInfo(result);
            } catch (debugError) {
                console.error('[DEV-EVENTS] Error showing debug info:', debugError);
            }

            if (result.has_pending_selection && result.new_selection) {
                // Multi-step event - show next selection using main game UI
                console.log('[DEV-EVENTS] Rendering new selection:', result.new_selection.event_type);
                window.devEventSelection = result.new_selection;
                window.devEventRunState = result.run_state;
                window.selectedOptions = [];  // Clear selection state for new selection screen

                // Render using main game's UI
                try {
                    renderEventPreview({
                        event_type: result.new_selection.event_type,
                        selection_data: result.new_selection,
                        run_state: result.run_state
                    });
                    console.log('[DEV-EVENTS] renderEventPreview completed successfully');
                } catch (renderError) {
                    console.error('[DEV-EVENTS] Error in renderEventPreview:', renderError);
                    alert('Render error: ' + renderError.message);
                }
            } else {
                // Event complete - clear dev selection state
                window.devEventSelection = null;
                renderEventComplete(result);
            }
        } else {
            alert('Selection failed: ' + result.error);
        }
    } catch (error) {
        console.error('[DEV-EVENTS] Selection failed:', error);
        console.error('[DEV-EVENTS] Error stack:', error.stack);
        alert('Network/fetch error: ' + error.message);
    }
}

// ==================== RENDERING ====================

function renderEventPreview(result) {
    const container = document.getElementById('eventPreview');

    const eventType = result.event_type;
    const selection = result.selection_data;
    const runState = result.run_state;

    // Store selection in dev mode context for the main game's selection system
    window.devEventSelection = selection;
    window.devEventRunState = runState;

    // IMPORTANT: Set gameData.run.band for the main game UI functions that need it
    // (e.g., generateFallbackCardContent for apply_targeted_effect options)
    // Note: gameData is declared with 'let' in game-core.js, so we assign directly
    try {
        if (typeof gameData === 'undefined' || gameData === null) {
            // Create a new object if gameData doesn't exist
            // Use window.gameData as fallback for scoping issues
            if (typeof window !== 'undefined') {
                window.gameData = {};
                // Also try to set the let variable directly
                gameData = window.gameData;
            } else {
                gameData = {};
            }
        }
        if (!gameData.run) {
            gameData.run = {};
        }
        // Use the band from selection (for target_minion) or from runState
        // Make a shallow copy to avoid circular reference issues
        const bandData = selection?.current_band || runState?.band || [];
        gameData.run.band = Array.isArray(bandData) ? [...bandData] : [];
        gameData.run.health = runState?.health || 100;
        gameData.run.gold = runState?.gold || 0;
        gameData.run.pending_selection = selection; // Set for UI functions that check this

        console.log('[DEV-EVENTS] Set gameData:', {
            band_length: gameData.run.band.length,
            health: gameData.run.health,
            gold: gameData.run.gold,
            selection_type: selection?.event_type
        });
    } catch (gameDataError) {
        console.error('[DEV-EVENTS] Error setting gameData:', gameDataError);
    }

    let html = '';

    // Info header showing dev mode context
    html += '<div class="dev-info-bar" style="background: rgba(255,215,0,0.2); padding: 10px; border-radius: 8px; margin-bottom: 15px; font-size: 0.9rem;">';
    html += `<strong>Event:</strong> ${eventType} | <strong>Ring:</strong> ${runState.current_ring} | <strong>Position:</strong> ${runState.ring_position} | <strong>Gold:</strong> ${runState.gold} | <strong>Health:</strong> ${runState.health} | <strong>Steps:</strong> ${runState.events_count}/${runState.upcoming_ghost_milestone || 10}`;
    html += '</div>';

    // Use the main game's selection UI rendering for ALL selection types
    // The depth limit in formatMinionSpecificEffect should prevent recursion
    if (selection) {
        try {
            if (typeof generateSelectionUIFromServer === 'function') {
                console.log('[DEV-EVENTS] Calling generateSelectionUIFromServer with:', {
                    event_type: selection.event_type,
                    options_count: selection.options?.length || 0,
                    has_current_band: !!selection.current_band,
                    current_band_length: selection.current_band?.length || 0
                });
                html += generateSelectionUIFromServer(selection);
            } else {
                console.log('[DEV-EVENTS] generateSelectionUIFromServer not found, using fallback');
                html += renderSelectionScreenFallback(selection, runState);
            }
        } catch (uiError) {
            console.error('[DEV-EVENTS] Error generating selection UI:', uiError);
            // Fall back to simplified rendering for target_minion if main game fails
            if (selection.event_type === 'target_minion') {
                console.log('[DEV-EVENTS] Falling back to renderDevTargetMinionUI');
                html += renderDevTargetMinionUI(selection);
            } else {
                html += `<div class="selection-zone">
                    <h3>⚠️ UI Generation Error</h3>
                    <p style="text-align: center;">${uiError.message}</p>
                    <p style="text-align: center; font-size: 0.8rem;">Check console for details.</p>
                </div>`;
                html += renderSelectionScreenFallback(selection, runState);
            }
        }
    } else {
        html += '<div class="selection-zone"><h3>Event Triggered</h3><p style="text-align: center;">No selection required (immediate event)</p></div>';
    }

    container.innerHTML = html;

    // Clear selection state when rendering new event
    window.selectedOptions = [];
}

// Simplified target minion UI for dev mode - uses main game's minion cards when possible
function renderDevTargetMinionUI(selection) {
    const effect = selection.effect_preview || {};
    const band = selection.current_band || [];
    const hasBack = selection.previous_selection;

    // For ring/keyword types, render as effect-tag with tooltip (same as minion keywords)
    const isKeywordStyle = effect.type === 'ring' || effect.type === 'keyword';

    let effectHtml = '';
    if (isKeywordStyle) {
        // Use the same tooltip structure as minion keywords (effect-tag tooltip)
        const tooltipContent = `<strong>${effect.name}:</strong> ${effect.description || ''}`;
        effectHtml = `
            <div style="text-align: center; margin-bottom: 20px;">
                <div class="effect-tag tooltip" style="background-color: #FFD700; display: inline-block;">
                    ${effect.icon || ''} ${effect.name || ''}
                    <span class="tooltiptext">${tooltipContent}</span>
                </div>
            </div>`;
    } else if (selection.message) {
        // Only show message section if message is provided
        effectHtml = `
            <p style="text-align: center; margin-bottom: 20px; font-size: 1.1rem;">
                ${selection.message}
            </p>`;
    }

    let html = `
        <div class="replacement-zone">
            <h3>${selection.title || 'Choose Target'}</h3>
            ${effectHtml}
            <div class="selection-options">`;

    // Render each option - try to use main game's minion card rendering
    (selection.options || []).forEach((option, index) => {
        if (option.type === 'apply_targeted_effect') {
            const minion = band[option.target_index] || {};

            // Try to use the main game's minion card rendering
            let minionCardHtml = '';
            try {
                if (typeof generateUnifiedMinionCard === 'function' && minion && minion.name) {
                    const cardOptions = {
                        index: option.target_index,
                        showIndex: true,
                        isClickable: false, // Click handled by parent selection card
                        isSelected: false,
                        isDisabled: false,
                        showAbandonButton: false,
                        clickHandler: '',
                        extraClasses: 'selection-minion-card'
                    };
                    minionCardHtml = generateUnifiedMinionCard(minion, cardOptions);
                }
            } catch (cardError) {
                console.warn('[DEV-EVENTS] Failed to render minion card with main game function:', cardError);
                minionCardHtml = ''; // Will use fallback below
            }

            // Fallback to simple rendering if main game function failed
            if (!minionCardHtml) {
                const minionName = minion.name || 'Unknown';
                const minionHealth = minion.health || '?';
                const minionAttack = minion.attack || '?';
                const minionTier = minion.tier || 1;

                minionCardHtml = `
                    <div class="minion-card" style="background: rgba(0,0,0,0.3); border: 2px solid rgba(255,255,255,0.3); border-radius: 8px; padding: 15px; text-align: center;">
                        <div class="minion-name" style="font-weight: bold; margin-bottom: 8px; color: #FFD700;">
                            ${minionName} #${option.target_index + 1}
                        </div>
                        <div class="minion-tier" style="font-size: 0.8rem; opacity: 0.7; margin-bottom: 5px;">
                            Tier ${minionTier}
                        </div>
                        <div class="minion-stats" style="display: flex; justify-content: center; gap: 20px;">
                            <span style="color: #ff6b6b;">⚔️ ${minionAttack}</span>
                            <span style="color: #4ecdc4;">❤️ ${minionHealth}</span>
                        </div>
                    </div>
                `;
            }

            html += `
                <div class="selection-card" id="card_${option.id}"
                     onclick="toggleSelection('${option.id}')"
                     data-option-id="${option.id}"
                     style="cursor: pointer;">
                    ${minionCardHtml}
                </div>
            `;
        } else if (option.type === 'back') {
            html += `
                <div class="selection-card" id="card_${option.id}"
                     onclick="toggleSelection('${option.id}')"
                     data-option-id="${option.id}"
                     style="cursor: pointer;">
                    <div style="padding: 15px; text-align: center; border: 2px solid rgba(255,255,255,0.3); border-radius: 8px;">
                        <div>⬅️ ${option.message || 'Back'}</div>
                    </div>
                </div>
            `;
        }
    });

    html += `
            </div>

            <div class="selection-controls">
                <button class="btn btn-primary" onclick="submitSelection()" id="submitBtn" disabled>
                    Apply Effect (0/1)
                </button>
                ${hasBack ? '<button class="btn btn-secondary" onclick="goBack()">Back</button>' : ''}
            </div>
        </div>
    `;

    return html;
}

// Fallback rendering if main game UI functions not available
function renderSelectionScreenFallback(selection, runState) {
    let html = '<div class="selection-zone">';

    // Title and message
    html += `<h3>${selection.title || 'Event Selection'}</h3>`;
    html += `<p style="text-align: center; margin-bottom: 15px;">${selection.message || ''}</p>`;

    // Options
    const options = selection.options || [];
    html += '<div class="selection-options">';

    options.forEach((option, index) => {
        const isDisabled = option.disabled ? 'disabled' : '';
        const optionClass = option.affordable === false ? 'unaffordable' : '';

        html += `
            <div class="selection-option ${optionClass}" data-option-id="${option.id}"
                 onclick="devSelectOption('${option.id}')"
                 style="cursor: pointer; padding: 15px; border: 2px solid rgba(255,255,255,0.3); border-radius: 8px; margin-bottom: 10px;"
                 ${isDisabled}>
                <h4 style="margin: 0 0 5px 0;">
                    ${option.message || option.id}
                    ${option.cost ? `<span style="color: #FFD700;"> (${option.cost} gold)</span>` : ''}
                </h4>
                ${option.description ? `<p style="margin: 0; opacity: 0.8; font-size: 0.9rem;">${option.description}</p>` : ''}
            </div>
        `;
    });

    html += '</div>';

    // Selection controls
    html += `<div class="selection-controls" style="margin-top: 20px; text-align: center;">
        <button class="btn btn-primary" onclick="devSubmitSelection()" id="devSubmitBtn" disabled>
            Confirm Selection (0)
        </button>
    </div>`;

    // Selection info
    html += `<p style="text-align: center; margin-top: 15px; font-size: 0.85rem; opacity: 0.7;">`;
    html += `Min: ${selection.min_selections || 0} | Max: ${selection.max_selections || 1}`;
    if (selection.repeating) html += ' | Repeating';
    if (selection.leaveable) html += ' | Leaveable';
    html += '</p>';

    html += '</div>';

    return html;
}

function renderEventComplete(result) {
    const container = document.getElementById('eventPreview');

    let html = '<div class="event-preview">';
    html += '<div class="preview-header">';
    html += '<h3>Event Complete</h3>';
    html += '</div>';

    // Show result
    html += '<div class="selection-preview">';
    html += '<h4>Result</h4>';

    if (result.result) {
        if (result.result.band_changes && result.result.band_changes.length > 0) {
            html += '<p><strong>Band Changes:</strong></p>';
            html += '<ul>';
            result.result.band_changes.forEach(change => {
                html += `<li>${JSON.stringify(change)}</li>`;
            });
            html += '</ul>';
        }

        if (result.result.resource_changes && Object.keys(result.result.resource_changes).length > 0) {
            html += '<p><strong>Resource Changes:</strong></p>';
            html += `<pre>${JSON.stringify(result.result.resource_changes, null, 2)}</pre>`;
        }

        if (result.result.message) {
            html += `<p>${result.result.message}</p>`;
        }
    }

    // Run state
    html += '<h4 style="margin-top: 20px;">Updated Run State</h4>';
    html += `<p>Gold: ${result.run_state.gold} | Health: ${result.run_state.health} | Band Size: ${result.run_state.band_size} | Steps: ${result.run_state.events_count}/${result.run_state.upcoming_ghost_milestone || 10}</p>`;

    html += '</div>';
    html += '</div>';

    container.innerHTML = html;
}


async function loadScalingPreview(eventType) {
    try {
        const response = await fetch(`${DEV_EVENTS_API}/events/scaling-preview?event_type=${eventType}`);
        const result = await response.json();

        if (result.success) {
            renderScalingPreview(result);
            document.getElementById('scalingPreviewSection').style.display = 'block';
        }
    } catch (error) {
        console.error('Failed to load scaling preview:', error);
    }
}

function renderScalingPreview(result) {
    const container = document.getElementById('scalingContent');

    let html = '<table class="scaling-table">';
    html += '<tr><th>Ring</th><th>Details</th></tr>';

    result.ring_previews.forEach(preview => {
        html += `<tr><td>Ring ${preview.ring}</td><td>`;

        if (preview.buff_options) {
            html += preview.buff_options.map(opt => opt.name).join(' | ');
        } else if (preview.combat_info) {
            html += `${preview.combat_info.difficulty} - ${preview.combat_info.enemy_band_size} enemies (Tier ${preview.combat_info.tier})`;
        } else if (preview.shop_info) {
            html += `${preview.shop_info.num_offers} offers, cost: ${preview.shop_info.cost_range}`;
        }

        html += '</td></tr>';
    });

    html += '</table>';

    container.innerHTML = html;
}

function showDebugInfo(data) {
    const panel = document.getElementById('debugPanel');
    const content = document.getElementById('debugContent');

    panel.style.display = 'block';

    // Use safe JSON stringify to avoid "too much recursion" from circular references
    try {
        content.textContent = safeJsonStringify(data);
    } catch (e) {
        content.textContent = `Error displaying data: ${e.message}\n\nKeys: ${Object.keys(data || {}).join(', ')}`;
    }
}

// Safe JSON stringify that handles circular references
function safeJsonStringify(obj, indent = 2) {
    const seen = new WeakSet();
    return JSON.stringify(obj, (key, value) => {
        if (typeof value === 'object' && value !== null) {
            if (seen.has(value)) {
                return '[Circular Reference]';
            }
            seen.add(value);
        }
        return value;
    }, indent);
}

// ==================== HELPER FUNCTIONS ====================

function getEventDisplayName(eventType) {
    const names = {
        'minion_event': 'Free Minion',
        'buff_event': 'Blessing',
        'combat_event': 'Combat',
        'combat_event_hard': 'Hard Combat',
        'shop_event': 'Tavern',
        'statue': 'Ancient Statue',
        'zone_portal': 'Zone Portal',
        'bell_tower': 'Bell Tower',
        'ancient_shrine': 'Ancient Shrine',
        'mysterious_merchant': 'Mysterious Merchant',
        'guardian_trial': 'Guardian Trial',
        'cursed_fountain': 'Cursed Fountain'
    };
    return names[eventType] || eventType.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

// NOTE: generateLucideSVG is provided by lucide-icons.js which is loaded first
// Do NOT define it here or it will cause infinite recursion
