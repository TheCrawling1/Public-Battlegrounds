// Event handling and selection management - CLIENT SIDE UI ONLY

function toggleSelection(optionId) {
    console.log('Toggling selection:', optionId);

    const card = document.getElementById(`card_${optionId}`);
    if (!card) {
        console.error('Card not found:', `card_${optionId}`);
        return;
    }

    // Simple client-side selection tracking - no validation
    const index = selectedOptions.indexOf(optionId);

    if (index === -1) {
        // Add to selection
        selectedOptions.push(optionId);
        card.classList.add('selected');
        console.log('Added to selection. Current selections:', selectedOptions);
        if (window.SoundBus) window.SoundBus.playAction('UI_SELECT');
    } else {
        // Remove from selection
        selectedOptions.splice(index, 1);
        card.classList.remove('selected');
        console.log('Removed from selection. Current selections:', selectedOptions);
        if (window.SoundBus) window.SoundBus.playAction('UI_DESELECT');
    }

    // Update button display (no validation, just show count)
    updateSubmitButton();
}

function updateSubmitButton() {
    const submitBtn = document.getElementById('submitBtn');
    if (!submitBtn) return;

    const selectedCount = selectedOptions.length;

    // Just update display - server will validate
    submitBtn.disabled = selectedCount === 0;
    submitBtn.textContent = `✅ Confirm Selection (${selectedCount})`;

    // Always show as primary if something selected
    if (selectedCount > 0) {
        submitBtn.classList.remove('btn-secondary');
        submitBtn.classList.add('btn-primary');
    } else {
        submitBtn.classList.remove('btn-primary');
        submitBtn.classList.add('btn-secondary');
    }
}

function updateCardStates() {
    // Server should provide card states - client just displays them
    // Remove all client-side validation logic
    console.log('Card states managed by server');
}

function goBack() {
    console.log('Going back...');

    // Always try the back option first if it exists
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

function clearSelection() {
    console.log('Clearing selection');
    selectedOptions.forEach(optionId => {
        const card = document.getElementById(`card_${optionId}`);
        if (card) {
            card.classList.remove('selected');
        }
    });
    selectedOptions = [];
    updateSubmitButton();
}

async function submitSelection(forceSelection = null) {
    if (!currentRunId) return;

    // Allow callers (e.g., the Close Preview button) to submit a fixed option
    // without needing a visible selectable card + manual confirm.
    const selectionsToSubmit = forceSelection ? [forceSelection] : selectedOptions;

    if (selectionsToSubmit.length === 0) {
        console.log('No selections to submit');
        return;
    }

    try {
        console.log('Submitting selections to server:', selectionsToSubmit);

        const result = await apiCall(`/run/${currentRunId}/select`, 'POST', {
            selections: selectionsToSubmit
        });

        // Server handles all validation and returns complete game state
        gameData = result;
        selectedOptions = []; // Clear selections after successful submission

        // Debug logging for end conditions
        console.log('[END CHECK] Ghost wins:', result.ghost_wins, 'Health:', result.run?.health);
        console.log('[END CHECK] run_should_end:', result.run_should_end, 'run_victory:', result.run_victory);

        // Check if run should end (victory or defeat)
        if (result.run_should_end) {
            console.log('[END SCREEN] Run ending:', result.end_reason);
            addLogEntry(`🏁 ${result.end_reason}`, result.run_victory ? 'victory' : 'defeat');

            // Small delay to ensure log is visible
            await new Promise(resolve => setTimeout(resolve, 500));

            // Trigger end screen
            console.log('[END SCREEN] Calling processRunEnd for run:', currentRunId);
            await processRunEnd(currentRunId);
            return; // Stop further processing
        }

        updateDisplay();

        // Log server-provided results
        if (result.selection_result && result.selection_result.results) {
            result.selection_result.results.forEach(message => {
                if (result.selection_result.back_navigation) {
                    addLogEntry(`⬅️ ${message}`, 'event');
                } else {
                    addLogEntry(`✨ ${message}`, 'event');
                }
            });
        }

        // Handle server-provided event results
        if (result.chosen_event) {
            addLogEntry(`🔄 Chose: ${formatEventName(result.chosen_event)}`, 'event');
        }

        if (result.zone_travel) {
            addLogEntry(`🌀 Zone travel completed!`, 'event');
            if (window.SoundBus) window.SoundBus.playAction('ZONE_TRAVEL');
            if (window.MusicEngine && gameData && gameData.current_zone) {
                window.MusicEngine.setZone(gameData.current_zone.key);
            }
        }

        if (result.ghost_battle_ready && !lastGhostBattleReady) {
            addLogEntry('👻 GHOST BATTLE READY! 10 events completed!', 'battle');
            if (window.SoundBus) window.SoundBus.playAction('GHOST_READY');
            if (window.MusicEngine) window.MusicEngine.setIntensity(0.85);
        }
        lastGhostBattleReady = !!result.ghost_battle_ready;

    } catch (error) {
        console.error('Failed to submit selection:', error);
        // Don't clear selections on error so user can retry
    }
}

// Minion management functions - these call APIs instead of local logic
function selectMinion(index) {
    // Don't allow selection during pending selections
    if (gameData && gameData.run && gameData.run.pending_selection) {
        return;
    }

    console.log('Selecting minion:', index);

    if (selectedMinionIndex === index) {
        // Clicking same minion deselects it
        selectedMinionIndex = -1;
    } else if (selectedMinionIndex >= 0) {
        // Swap with previously selected minion
        swapMinions(selectedMinionIndex, index);
        return;
    } else {
        // Select this minion
        selectedMinionIndex = index;
    }

    updateDisplay();
}

async function swapMinions(index1, index2) {
    if (!currentRunId) return;

    try {
        console.log('Swapping minions via API:', index1, index2);

        const result = await apiCall(`/run/${currentRunId}/swap-minions`, 'POST', {
            index1: index1,
            index2: index2
        });

        gameData.run = result.run;
        selectedMinionIndex = -1; // Clear selection after swap
        updateDisplay();

        addLogEntry(`🔄 ${result.message}`, 'event');
        if (window.SoundBus) window.SoundBus.playAction('MINION_SWAP');

    } catch (error) {
        console.error('Failed to swap minions:', error);
        selectedMinionIndex = -1;
        updateDisplay();
    }
}

async function abandonMinion(event, index) {
    event.stopPropagation(); // Prevent minion selection

    if (!currentRunId) return;

    const minion = gameData.run.band[index];
    if (!confirm(`Are you sure you want to abandon ${minion.name}?`)) {
        return;
    }

    try {
        console.log('Abandoning minion via API:', index);

        const result = await apiCall(`/run/${currentRunId}/abandon-minion`, 'POST', {
            index: index
        });

        gameData.run = result.run;
        selectedMinionIndex = -1; // Clear selection after abandon
        updateDisplay();

        addLogEntry(`❌ ${result.message}`, 'event');
        if (window.SoundBus) window.SoundBus.playAction('MINION_ABANDON');

    } catch (error) {
        console.error('Failed to abandon minion:', error);
    }
}

// Click outside to deselect minion
document.addEventListener('click', function(event) {
    // Check if click is outside band area and not on a minion card
    if (selectedMinionIndex >= 0 &&
        !event.target.closest('.minion-card') &&
        !event.target.closest('.abandon-button')) {
        selectedMinionIndex = -1;
        updateDisplay();
    }
});