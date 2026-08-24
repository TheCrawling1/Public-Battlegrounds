// End Screen System - Show run completion statistics
// Follows the same pattern as main-menu.js

// Global MAX_GHOST_WINS loaded from server config
let MAX_GHOST_WINS = 6;

// Show the end screen with run statistics
function showEndScreen(runStats) {
    const gameContent = document.getElementById('gameContent');

    let endScreenHTML = `
        <div class="end-screen">
            ${generateEndScreenHeader(runStats)}
            ${generateEndScreenStats(runStats)}
            ${generateEndScreenActions(runStats)}
        </div>
    `;

    gameContent.innerHTML = endScreenHTML;
    gameContent.className = '';
}

// Generate header section with victory/defeat status
function generateEndScreenHeader(stats) {
    const isVictory = stats.victory;

    // Use Lucide icons if available, fallback to emoji
    const icon = typeof generateLucideSVG === 'function' ?
        generateLucideSVG(isVictory ? 'trophy' : 'skull', 80, 80, {cssClass: 'end-icon-svg'}) :
        `<div class="end-icon-emoji">${isVictory ? '🏆' : '💀'}</div>`;

    const title = isVictory ? 'Victory!' : 'Defeat';
    const subtitle = isVictory ?
        'You conquered the arena!' :
        'You fell in battle...';

    let headerHTML = `
        <div class="end-screen-header ${isVictory ? 'victory' : 'defeat'}">
            <div class="end-icon">${icon}</div>
            <div class="end-title">${title}</div>
            <div class="end-subtitle">${subtitle}</div>
        </div>
    `;

    return headerHTML;
}

// Generate statistics grid
function generateEndScreenStats(stats) {
    // Icon helper function
    const getIcon = (iconName) => {
        return typeof generateLucideSVG === 'function' ?
            generateLucideSVG(iconName, 40, 40, {cssClass: 'stat-icon-svg'}) :
            getIconEmoji(iconName);
    };

    // Emoji fallbacks
    const getIconEmoji = (iconName) => {
        const emojiMap = {
            'target': '🎯',
            'map': '🗺️',
            'layers': '📚',
            'heart': '❤️',
            'users': '👥',
            'coins': '💰'
        };
        return `<div class="stat-icon-emoji">${emojiMap[iconName] || '📊'}</div>`;
    };

    let statsHTML = `
        <div class="end-screen-stats">
            <div class="stats-grid">
                <div class="stat-card">
                    ${getIcon('target')}
                    <div class="stat-value">${stats.ghostsDefeated || 0}</div>
                    <div class="stat-label">Ghosts Defeated</div>
                </div>

                <div class="stat-card">
                    ${getIcon('map')}
                    <div class="stat-value">${stats.eventsCompleted || 0}</div>
                    <div class="stat-label">Events Completed</div>
                </div>

                <div class="stat-card">
                    ${getIcon('layers')}
                    <div class="stat-value">${stats.highestRing || 1}</div>
                    <div class="stat-label">Highest Ring</div>
                </div>

                <div class="stat-card">
                    ${getIcon('heart')}
                    <div class="stat-value">${stats.finalHealth || 0}</div>
                    <div class="stat-label">Final Health</div>
                </div>

                <div class="stat-card">
                    ${getIcon('users')}
                    <div class="stat-value">${stats.bandSize || 0}</div>
                    <div class="stat-label">Band Size</div>
                </div>

                <div class="stat-card">
                    ${getIcon('coins')}
                    <div class="stat-value">${stats.goldRemaining || 0}</div>
                    <div class="stat-label">Gold Remaining</div>
                </div>
            </div>

            ${generateFinalBandDisplay(stats.band || [])}
        </div>
    `;

    return statsHTML;
}

// Generate final band display
function generateFinalBandDisplay(band) {
    if (!band || band.length === 0) {
        return `
            <div class="final-band">
                <h3>Final Band</h3>
                <div class="no-minions">
                    <p>No minions survived</p>
                </div>
            </div>
        `;
    }

    // Use the unified minion card generator for proper display with images and abilities
    let minionsHTML = band.map((minion, index) => {
        // Enrich minion with template data if available
        const enrichedMinion = typeof enrichCombatMinion === 'function'
            ? enrichCombatMinion(minion)
            : minion;

        // Use generateUnifiedMinionCard if available, otherwise fallback to simple display
        if (typeof generateUnifiedMinionCard === 'function') {
            return generateUnifiedMinionCard(enrichedMinion, {
                index: index,
                showIndex: true,
                isClickable: false,
                isSelected: false,
                isDisabled: true,
                showAbandonButton: false,
                clickHandler: '',
                extraClasses: 'end-screen-minion-card'
            });
        } else {
            // Fallback to simple display if unified card generator not available
            return `
                <div class="minion-card-mini">
                    <div class="minion-name">${minion.name || 'Unknown'}</div>
                    <div class="minion-stats">
                        <span class="minion-health">${minion.health || 0}</span>
                        /
                        <span class="minion-attack">${minion.attack || 0}</span>
                    </div>
                </div>
            `;
        }
    }).join('');

    return `
        <div class="final-band">
            <h3>Final Band</h3>
            <div class="final-band-grid">
                ${minionsHTML}
            </div>
        </div>
    `;
}

// Generate action buttons
function generateEndScreenActions(stats) {
    const isRanked = stats.isRanked || false;

    let actionsHTML = `
        <div class="end-screen-actions">
            <button class="panel-btn panel-btn-primary" onclick="returnToMainMenu()">
                🏠 Main Menu
            </button>
    `;

    // Only show "Play Again" for unranked (ranked requires creating new run)
    if (!isRanked) {
        actionsHTML += `
            <button class="panel-btn panel-btn-secondary" onclick="startNewUnrankedGame()">
                🔄 Play Again
            </button>
        `;
    }

    actionsHTML += `
        </div>
    `;

    return actionsHTML;
}

// Return to main menu
function returnToMainMenu() {
    console.log('Returning to main menu...');

    // Clear any stored run data
    if (!currentPlayer) {
        localStorage.removeItem('autobattler_unranked_run_id');
    }

    // Reset state
    currentRunId = null;
    gameData = null;

    // Show main menu
    if (typeof showMainMenu === 'function') {
        showMainMenu();
    } else {
        // Fallback: reload page
        window.location.reload();
    }
}

// Start new unranked game from end screen
async function startNewUnrankedGame() {
    console.log('Starting new unranked game from end screen...');

    // Clear any stored run data
    if (!currentPlayer) {
        localStorage.removeItem('autobattler_unranked_run_id');
    }

    // Start new game
    if (typeof startUnrankedGame === 'function') {
        await startUnrankedGame();
    } else {
        console.error('startUnrankedGame function not found');
        returnToMainMenu();
    }
}

// Process run end - called from combat or other game logic
async function processRunEnd(runId) {
    console.log('[PROCESS RUN END] Starting for run ID:', runId);

    try {
        // Call backend endpoint to get final statistics
        console.log('[PROCESS RUN END] Fetching stats from /api/run/' + runId + '/end');
        const response = await fetch(`/api/run/${runId}/end`, {
            method: 'POST',
            credentials: 'include'
        });

        console.log('[PROCESS RUN END] Response status:', response.status);
        const data = await response.json();
        console.log('[PROCESS RUN END] Response data:', data);

        if (data.success) {
            console.log('[PROCESS RUN END] Run ended successfully, showing end screen');
            console.log('[PROCESS RUN END] Stats:', data.stats);

            // Show end screen with statistics
            showEndScreen(data.stats);
        } else {
            console.error('[PROCESS RUN END] Failed to end run:', data.error);
            alert('Error ending run: ' + data.error);
            returnToMainMenu();
        }
    } catch (error) {
        console.error('[PROCESS RUN END] Exception caught:', error);
        console.error('[PROCESS RUN END] Stack trace:', error.stack);
        alert('Failed to load end screen. Error: ' + error.message);
        returnToMainMenu();
    }
}

// Check if run should end (called after events/combat)
function checkRunEndConditions(runData) {
    // Victory condition: MAX_GHOST_WINS reached
    const ghostWins = runData.ghost_wins || 0;
    if (ghostWins >= MAX_GHOST_WINS) {
        console.log('Victory condition met: ghost wins =', ghostWins);
        return {
            shouldEnd: true,
            victory: true,
            reason: 'Defeated enough ghosts!'
        };
    }

    // Defeat condition: Health <= 0
    if (runData.health <= 0) {
        console.log('Defeat condition met: health =', runData.health);
        return {
            shouldEnd: true,
            victory: false,
            reason: 'Your health reached zero'
        };
    }

    // Run continues
    return {
        shouldEnd: false,
        victory: null,
        reason: null
    };
}
