// Main Menu system - 4 Panel Layout
let currentPlayer = null;
let activeRankedRun = null;
let activeUnrankedRun = null;
let availableHeroes = [];
let selectedHeroId = null;

// LocalStorage keys
const UNRANKED_RUN_KEY = 'autobattler_unranked_run_id';
const SELECTED_HERO_KEY = 'autobattler_selected_hero';

// Check if user is already logged in when page loads
async function checkExistingSession() {
    try {
        const response = await fetch('/api/auth/check-session', {
            credentials: 'include'
        });

        if (!response.ok) return false;
        const data = await response.json();

        if (data.logged_in && data.player) {
            currentPlayer = data.player;
            console.log('Already logged in as:', currentPlayer.username);

            // Reload heroes to ensure correct equipped image paths
            await loadHeroes();

            // Check for active runs
            await checkActiveRuns();

            return true;
        }
    } catch (error) {
        console.error('Error checking session:', error);
    }

    return false;
}

// Check for active runs (both ranked and unranked)
async function checkActiveRuns() {
    // For logged-in users, check server-side runs
    if (currentPlayer) {
        try {
            const response = await fetch('/api/check-active-run', {
                credentials: 'include'
            });

            if (!response.ok) return;
            const data = await response.json();

            if (data.success) {
                activeRankedRun = data.has_ranked_run ? data.ranked_run : null;
                activeUnrankedRun = data.has_unranked_run ? data.unranked_run : null;

                if (activeRankedRun) {
                    console.log('Active ranked run found:', activeRankedRun);
                }
                if (activeUnrankedRun) {
                    console.log('Active unranked run found:', activeUnrankedRun);
                }
            }
        } catch (error) {
            console.error('Error checking active runs:', error);
            activeRankedRun = null;
            activeUnrankedRun = null;
        }
    } else {
        // For non-logged-in users, check localStorage for unranked run
        activeRankedRun = null;
        await checkLocalStorageRun();
    }
}

// Check localStorage for saved unranked run
async function checkLocalStorageRun() {
    const savedRunId = localStorage.getItem(UNRANKED_RUN_KEY);

    if (!savedRunId) {
        activeUnrankedRun = null;
        return;
    }

    try {
        // Try to load the run from the server
        const response = await fetch(`/api/run/${savedRunId}`, {
            credentials: 'include'
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        if (data.success && data.run && data.run.is_active) {
            activeUnrankedRun = data.run;
            console.log('Active unranked run loaded from localStorage:', activeUnrankedRun);
        } else {
            // Run doesn't exist or is inactive, clear localStorage
            localStorage.removeItem(UNRANKED_RUN_KEY);
            activeUnrankedRun = null;
        }
    } catch (error) {
        console.error('Error loading run from localStorage:', error);
        localStorage.removeItem(UNRANKED_RUN_KEY);
        activeUnrankedRun = null;
    }
}

// Load available heroes
async function loadHeroes() {
    try {
        const response = await fetch('/api/dev/heroes', {
            credentials: 'include'  // Include session cookie so server knows the user
        });
        if (!response.ok) return;
        const result = await response.json();

        if (result.success) {
            availableHeroes = result.heroes;
            console.log(`Loaded ${result.total} heroes`);

            // Load saved hero selection
            const savedHeroId = localStorage.getItem(SELECTED_HERO_KEY);
            if (savedHeroId && availableHeroes.find(h => h.id === savedHeroId)) {
                selectedHeroId = savedHeroId;
            }
        }
    } catch (error) {
        console.error('Failed to load heroes:', error);
    }
}

// Show the main menu with 4-panel layout
async function showMainMenu() {
    const gameContent = document.getElementById('gameContent');

    // Reload heroes if user is logged in (to get updated equipped image paths)
    if (currentPlayer) {
        await loadHeroes();
    }

    let menuHTML = `
        <div class="main-menu">
            <div class="main-menu-card">
                ${generateUpperBar()}
                ${generatePanels()}
            </div>
        </div>
    `;

    gameContent.innerHTML = menuHTML;
    gameContent.className = '';
}

// Format hero description by replacing placeholders with actual values
function formatHeroDescription(description, powerLevel = 1) {
    if (!description) return '';

    // Calculate derived values based on power level
    const puckMinions = 1 + powerLevel;  // Puck starts at 2 minions (1 + power_level)

    return description
        .replace(/{power_level}/g, String(powerLevel))
        .replace(/{puck_minions}/g, String(puckMinions));
}

// Hero icon mapping
const HERO_ICONS = {
    'silas': 'coins',
    'puck': 'crown',
    'olimpia': 'shield'
};

// Font sizing helpers for minion cards (matching ui-display-desktop.js)
function getHeroCardNameFontSize(name) {
    const len = name.length;
    if (len <= 10) return '0.7rem';
    if (len <= 14) return '0.6rem';
    if (len <= 18) return '0.5rem';
    return '0.45rem';
}

function getHeroCardTribeFontSize(tribeName) {
    const len = tribeName.length;
    if (len <= 4) return '0.7rem';
    if (len <= 6) return '0.6rem';
    if (len <= 8) return '0.5rem';
    return '0.45rem';
}

function getHeroCardStatFontSize(attack, health) {
    const maxValue = Math.max(Math.abs(attack), Math.abs(health));
    const digits = maxValue.toString().length;
    if (digits <= 2) return '0.85rem';
    if (digits === 3) return '0.75rem';
    return '0.65rem';
}

// Generate a minion card for hero selection - uses standard unified card
function generateHeroMinionCard(minion) {
    // Enrich minion with template data for keywords/effects
    const enrichedMinion = typeof enrichCombatMinion === 'function'
        ? enrichCombatMinion(minion)
        : minion;

    // Use generateUnifiedMinionCard if available (same as collection cards)
    if (typeof generateUnifiedMinionCard === 'function') {
        return generateUnifiedMinionCard(enrichedMinion, {
            showIndex: false,
            isClickable: false,
            isSelected: false,
            isDisabled: false,
            showAbandonButton: false,
            extraClasses: 'hero-starting-card'
        });
    }

    // Fallback if generateUnifiedMinionCard isn't loaded yet
    const imageStyle = typeof getMinionImageStyle === 'function'
        ? getMinionImageStyle(enrichedMinion)
        : (enrichedMinion.image ? `background-image: url('images/original/${enrichedMinion.image}'); background-size: 100% 100%; background-repeat: no-repeat; background-position: center;` : '');

    return `
        <div class="minion-card hero-starting-card" style="${imageStyle}">
            <div class="minion-name">${enrichedMinion.name || 'Unknown'}</div>
            <div class="minion-stats-box">
                <div class="minion-stats">
                    <span class="stat attack">⚔️${enrichedMinion.attack || 0}</span>
                    <span class="stat health">❤️${Math.max(0, enrichedMinion.health || 0)}</span>
                </div>
            </div>
        </div>
    `;
}

// Generate hero selection UI
function generateHeroSelection() {
    if (availableHeroes.length === 0) {
        return ''; // No heroes loaded yet
    }

    const userIcon = generateLucideSVG('user', 20, 20, 'currentColor', 'section-icon');

    let heroHTML = `
        <div class="hero-selection-container">
            <div class="hero-selection-title">${userIcon} Select Your Hero</div>
            <div class="hero-selection-grid">
    `;

    // Generate hero buttons in horizontal row with icon on left
    // Use base power level of 1 for main menu display (no active run yet)
    const basePowerLevel = 1;
    availableHeroes.forEach(hero => {
        const isSelected = selectedHeroId === hero.id;
        const formattedDescription = formatHeroDescription(hero.description, basePowerLevel);
        const iconName = HERO_ICONS[hero.id] || 'swords';
        const heroIcon = generateLucideSVG(iconName, 24, 24, 'currentColor', 'hero-icon-svg');

        // Generate full minion cards for starting band
        let minionsHTML = '';
        if (hero.starting_minions && hero.starting_minions.length > 0) {
            minionsHTML = '<div class="hero-starting-minions">';
            hero.starting_minions.forEach(minion => {
                minionsHTML += generateHeroMinionCard(minion);
            });
            minionsHTML += '</div>';
        }

        heroHTML += `
            <div class="hero-button ${isSelected ? 'selected' : ''}"
                    onclick="selectHero('${hero.id}')"
                    data-hero-id="${hero.id}">
                <div class="hero-header">
                    <div class="hero-icon">${heroIcon}</div>
                    <div class="hero-text">
                        <div class="hero-name">${hero.name}</div>
                        <div class="hero-effect">${formattedDescription}</div>
                    </div>
                </div>
                ${minionsHTML}
            </div>
        `;
    });

    heroHTML += `
            </div>
        </div>
    `;

    return heroHTML;
}

// Select a hero
function selectHero(heroId) {
    selectedHeroId = heroId;
    localStorage.setItem(SELECTED_HERO_KEY, heroId);
    console.log('Selected hero:', heroId);

    if (window.SoundBus) window.SoundBus.playAction('UI_SELECT');

    // Update UI to show selection
    showMainMenu();
}

// Generate upper bar with login/settings
function generateUpperBar() {
    const settingsIcon = generateLucideSVG('settings', 16, 16, 'currentColor', 'btn-icon');
    const logoutIcon = generateLucideSVG('log-out', 16, 16, 'currentColor', 'btn-icon');

    let upperBarHTML = `
        <div class="menu-upper-bar">
            <div class="menu-title">Auto Battler Arena</div>
            <div class="menu-user-section">
    `;

    if (currentPlayer) {
        // Logged in view
        upperBarHTML += `
                <div class="user-info">
                    <div class="username">${currentPlayer.username}</div>
                    <div class="stats">
                        ${currentPlayer.ranked_wins || 0}W - ${currentPlayer.ranked_losses || 0}L |
                        Ring ${currentPlayer.highest_ring || 0}
                    </div>
                </div>
                <div class="upper-bar-buttons">
                    <button class="icon-btn" onclick="showSettings()">${settingsIcon} Settings</button>
                    <button class="icon-btn" onclick="logout()">${logoutIcon} Logout</button>
                </div>
        `;
    } else {
        // Not logged in view
        upperBarHTML += `
                <div class="login-prompt">
                    <input type="text" id="username" placeholder="Username" />
                    <input type="password" id="password" placeholder="Password" />
                    <button class="btn btn-primary" onclick="login()">Login</button>
                </div>
                <div class="upper-bar-buttons">
                    <button class="icon-btn" onclick="showSettings()">${settingsIcon} Settings</button>
                </div>
                <div id="loginError" class="error-message" style="display:none;"></div>
        `;
    }

    upperBarHTML += `
            </div>
        </div>
    `;

    return upperBarHTML;
}

// Generate panels with hero selection above game modes
function generatePanels() {
    return `
        <div class="menu-panels">
            <div class="sub-panels">
                ${generateRankedPanel()}
                ${generateUnrankedPanel()}
                ${generateTrainingPanel()}
                ${generateCollectionPanel()}
            </div>
            ${generateHeroSelection()}
        </div>
    `;
}

// Generate Ranked panel
function generateRankedPanel() {
    const requiresLogin = !currentPlayer;
    const hasActiveRun = currentPlayer && activeRankedRun;

    const trophyIcon = generateLucideSVG('trophy', 28, 28, 'currentColor', 'panel-icon-svg');
    const playIcon = generateLucideSVG('play', 12, 12, 'currentColor', 'btn-icon');
    const trashIcon = generateLucideSVG('trash-2', 12, 12, 'currentColor', 'btn-icon');

    let panelHTML = `
        <div class="menu-panel panel-ranked sub-panel ${requiresLogin ? 'locked' : ''}">
            <div class="panel-icon">${trophyIcon}</div>
            <div class="panel-title">Ranked</div>
            <div class="panel-subtitle">Competitive Mode</div>
            <div class="panel-description">
                Climb the ranks and compete. Progress saved to leaderboard.
            </div>
    `;

    if (requiresLogin) {
        panelHTML += `
            <div class="panel-description login-warning">
                Login required to play ranked
            </div>
        `;
    } else if (hasActiveRun) {
        panelHTML += `
            <div class="panel-active-run">
                <h4>Active Run</h4>
                <div class="run-stats">
                    <div class="stat">
                        <div class="stat-label">Ring</div>
                        <div class="stat-value">${activeRankedRun.current_ring}</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Steps</div>
                        <div class="stat-value">${activeRankedRun.events_count}</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Band</div>
                        <div class="stat-value">${activeRankedRun.band.length}</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Position</div>
                        <div class="stat-value">${activeRankedRun.ring_position}</div>
                    </div>
                </div>
            </div>
            <div class="panel-actions">
                <button class="panel-btn panel-btn-primary" onclick="resumeRankedRun()">
                    ${playIcon} Resume
                </button>
                <button class="panel-btn panel-btn-danger" onclick="confirmAbandonRun('ranked')">
                    ${trashIcon} Abandon
                </button>
            </div>
        `;
    } else {
        panelHTML += `
            <div class="panel-actions">
                <button class="panel-btn panel-btn-primary" onclick="startRankedGame()">
                    ${generateLucideSVG('trophy', 12, 12, 'currentColor', 'btn-icon')} Start Ranked
                </button>
            </div>
        `;
    }

    panelHTML += `
        </div>
    `;

    return panelHTML;
}

// Generate Unranked panel
function generateUnrankedPanel() {
    const hasActiveRun = activeUnrankedRun !== null;

    const gamepadIcon = generateLucideSVG('gamepad-2', 28, 28, 'currentColor', 'panel-icon-svg');
    const playIcon = generateLucideSVG('play', 12, 12, 'currentColor', 'btn-icon');
    const trashIcon = generateLucideSVG('trash-2', 12, 12, 'currentColor', 'btn-icon');

    let panelHTML = `
        <div class="menu-panel panel-unranked sub-panel">
            <div class="panel-icon">${gamepadIcon}</div>
            <div class="panel-title">Unranked</div>
            <div class="panel-subtitle">Casual Mode</div>
            <div class="panel-description">
                Play casually without pressure. No login required!
            </div>
    `;

    if (hasActiveRun) {
        panelHTML += `
            <div class="panel-active-run">
                <h4>Active Run</h4>
                <div class="run-stats">
                    <div class="stat">
                        <div class="stat-label">Ring</div>
                        <div class="stat-value">${activeUnrankedRun.current_ring}</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Steps</div>
                        <div class="stat-value">${activeUnrankedRun.events_count}</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Band</div>
                        <div class="stat-value">${activeUnrankedRun.band.length}</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Position</div>
                        <div class="stat-value">${activeUnrankedRun.ring_position}</div>
                    </div>
                </div>
            </div>
            <div class="panel-actions">
                <button class="panel-btn panel-btn-primary" onclick="resumeUnrankedRun()">
                    ${playIcon} Resume
                </button>
                <button class="panel-btn panel-btn-danger" onclick="confirmAbandonRun('unranked')">
                    ${trashIcon} Abandon
                </button>
            </div>
        `;
    } else {
        panelHTML += `
            <div class="panel-actions">
                <button class="panel-btn panel-btn-primary" onclick="startUnrankedGame()">
                    ${generateLucideSVG('gamepad-2', 12, 12, 'currentColor', 'btn-icon')} Start Unranked
                </button>
            </div>
        `;
    }

    panelHTML += `
        </div>
    `;

    return panelHTML;
}

// Generate Training panel
function generateTrainingPanel() {
    const targetIcon = generateLucideSVG('target', 28, 28, 'currentColor', 'panel-icon-svg');
    const swordIcon = generateLucideSVG('swords', 12, 12, 'currentColor', 'btn-icon');
    const calendarIcon = generateLucideSVG('calendar', 12, 12, 'currentColor', 'btn-icon');
    const musicIcon = generateLucideSVG('sparkles', 12, 12, 'currentColor', 'btn-icon');

    return `
        <div class="menu-panel panel-training sub-panel">
            <div class="panel-icon">${targetIcon}</div>
            <div class="panel-title">Training</div>
            <div class="panel-subtitle">Practice Mode</div>
            <div class="panel-description">
                Test builds and practice combat mechanics.
            </div>
            <div class="panel-actions">
                <button class="panel-btn panel-btn-primary" onclick="window.location.href='/dev-combat'">
                    ${swordIcon} Test Combat
                </button>
                <button class="panel-btn panel-btn-primary" onclick="window.location.href='/dev-events'">
                    ${calendarIcon} Test Events
                </button>
                <button class="panel-btn panel-btn-primary" onclick="window.location.href='/dev-sounds'">
                    ${musicIcon} Sound Studio
                </button>
            </div>
        </div>
    `;
}

// Generate Collection panel
function generateCollectionPanel() {
    const bookIcon = generateLucideSVG('book-open', 28, 28, 'currentColor', 'panel-icon-svg');

    return `
        <div class="menu-panel panel-collection sub-panel" onclick="showCollection()">
            <div class="panel-icon">${bookIcon}</div>
            <div class="panel-title">Collection</div>
            <div class="panel-subtitle">Minion Gallery & Codex</div>
            <div class="panel-description">
                Browse minions, keywords, bands, and events.
            </div>
            <div class="panel-actions">
                <button class="panel-btn panel-btn-primary" onclick="showCollection()">
                    ${generateLucideSVG('book-open', 12, 12, 'currentColor', 'btn-icon')} View
                </button>
            </div>
        </div>
    `;
}

// Login function
async function login() {
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    const errorDiv = document.getElementById('loginError');

    if (!username || !password) {
        errorDiv.textContent = 'Please enter both username and password';
        errorDiv.style.display = 'block';
        return;
    }

    try {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'include',
            body: JSON.stringify({ username, password })
        });

        const data = await response.json();

        if (response.ok) {
            currentPlayer = data.player;
            console.log('Login successful:', currentPlayer);
            if (window.SoundBus) window.SoundBus.playAction('UI_CONFIRM');

            // Reset collection data so it reloads with user's ownership info
            if (typeof collectionData !== 'undefined') {
                collectionData.loaded = false;
            }
            // Reset and reload equipped images with new user's data
            if (typeof window.equippedImagesLoaded !== 'undefined') {
                window.equippedImagesLoaded = false;
            }
            if (typeof loadEquippedImages === 'function') {
                loadEquippedImages();
            }

            // Reload heroes to get correct equipped image paths for starting minions
            await loadHeroes();

            // Check for active runs after login
            await checkActiveRuns();

            showMainMenu();
        } else {
            errorDiv.textContent = data.error || 'Login failed';
            errorDiv.style.display = 'block';
            if (window.SoundBus) window.SoundBus.playAction('UI_ERROR');
        }
    } catch (error) {
        console.error('Login error:', error);
        errorDiv.textContent = 'Connection error. Please try again.';
        errorDiv.style.display = 'block';
        if (window.SoundBus) window.SoundBus.playAction('UI_ERROR');
    }
}

// Logout function
async function logout() {
    try {
        await fetch('/api/auth/logout', {
            method: 'POST',
            credentials: 'include'
        });

        currentPlayer = null;
        activeRankedRun = null;
        activeUnrankedRun = null;

        // Clear heroes cache to force reload with default images
        availableHeroes = [];

        // Clear collection data cache (will reload on next view)
        if (typeof collectionData !== 'undefined') {
            collectionData.minions = [];
            collectionData.bands = [];
            collectionData.events = [];
            collectionData.images = [];
            collectionData.loaded = false;
        }

        // Clear equipped images cache
        if (typeof equippedImagePaths !== 'undefined') {
            Object.keys(equippedImagePaths).forEach(key => delete equippedImagePaths[key]);
        }
        window.equippedImagesLoaded = false;

        console.log('Logged out successfully');
        showMainMenu();
    } catch (error) {
        console.error('Logout error:', error);
    }
}

// Start ranked game (requires login)
function startRankedGame() {
    if (!currentPlayer) {
        alert('Please login to play ranked mode');
        return;
    }

    console.log('Starting ranked game...');
    startNewGame(true, false); // ranked=true, force_new=false
}

// Start unranked game (no login required)
async function startUnrankedGame() {
    console.log('Starting unranked game...');

    // Call the game start function
    await startNewGame(false, false); // ranked=false, force_new=false

    // If not logged in, save the run ID to localStorage
    // The run ID will be set in gameState after startNewGame completes
    if (!currentPlayer && window.gameState && window.gameState.runId) {
        localStorage.setItem(UNRANKED_RUN_KEY, window.gameState.runId);
        console.log('Saved unranked run to localStorage:', window.gameState.runId);
    }
}

// Resume ranked run
async function resumeRankedRun() {
    if (!activeRankedRun) {
        console.error('No active ranked run to resume');
        return;
    }

    console.log('Resuming ranked run:', activeRankedRun.id);

    try {
        await startNewGame(true, false); // Will auto-resume
    } catch (error) {
        console.error('Error resuming run:', error);
        alert('Failed to resume run. Please try again.');
    }
}

// Resume unranked run
async function resumeUnrankedRun() {
    if (!activeUnrankedRun) {
        console.error('No active unranked run to resume');
        return;
    }

    console.log('Resuming unranked run:', activeUnrankedRun.id);

    try {
        await startNewGame(false, false); // Will auto-resume
    } catch (error) {
        console.error('Error resuming run:', error);
        alert('Failed to resume run. Please try again.');
    }
}

// Confirm abandon run
function confirmAbandonRun(mode) {
    const run = mode === 'ranked' ? activeRankedRun : activeUnrankedRun;

    if (!run) {
        return;
    }

    if (confirm(`Are you sure you want to abandon your current ${mode} run?\n\nRing: ${run.current_ring}, Steps: ${run.events_count}\n\nThis cannot be undone!`)) {
        abandonRun(mode);
    }
}

// Abandon current run
async function abandonRun(mode) {
    const run = mode === 'ranked' ? activeRankedRun : activeUnrankedRun;

    if (!run) {
        return;
    }

    try {
        // Abandon the current run
        const response = await fetch(`/api/run/${run.id}/abandon`, {
            method: 'POST',
            credentials: 'include'
        });

        const data = await response.json();

        if (data.success) {
            console.log('Run abandoned successfully');

            // Clear the active run and refresh the menu
            if (mode === 'ranked') {
                activeRankedRun = null;
            } else {
                activeUnrankedRun = null;

                // If not logged in, also clear localStorage for unranked
                if (!currentPlayer) {
                    localStorage.removeItem(UNRANKED_RUN_KEY);
                    console.log('Cleared unranked run from localStorage');
                }
            }

            // Refresh the main menu to show updated state
            showMainMenu();
        } else {
            alert('Failed to abandon run: ' + data.error);
        }
    } catch (error) {
        console.error('Error abandoning run:', error);
        alert('Failed to abandon run. Please try again.');
    }
}

// Show settings — currently a sound control panel. Pulls current values from
// SoundBus and writes back through setSetting(); bus persists to localStorage.
function showSettings() {
    const gameContent = document.getElementById('gameContent');
    const s = (window.SoundBus && window.SoundBus.getSettings())
        || { master: 0.7, music: 0.5, sfx: 0.8, ui: 0.6, muted: false };
    const pct = v => Math.round(v * 100);

    gameContent.innerHTML = `
        <div class="main-menu">
            <div class="menu-upper-bar">
                <div class="menu-title">Settings</div>
                <div class="menu-user-section">
                    <button class="icon-btn" onclick="showMainMenu()">← Back</button>
                </div>
            </div>
            <div class="main-menu-card" style="padding:32px;max-width:560px;margin:24px auto;">
                <h2 style="color:#d4af5a;margin-top:0;">🔊 Sound</h2>

                <label style="display:flex;align-items:center;gap:12px;margin:18px 0;color:#c9b074;">
                    <input type="checkbox" id="settings-muted" ${s.muted ? 'checked' : ''}
                        onchange="updateSoundSetting('muted', this.checked)">
                    Mute all sound
                </label>

                ${soundSliderRow('master', 'Master',     s.master)}
                ${soundSliderRow('music',  'Music',      s.music)}
                ${soundSliderRow('sfx',    'Effects',    s.sfx)}
                ${soundSliderRow('ui',     'UI Clicks',  s.ui)}

                <div style="margin-top:24px;display:flex;gap:12px;flex-wrap:wrap;">
                    <button class="panel-btn panel-btn-primary" onclick="previewSoundSettings()">
                        🎵 Test Sound
                    </button>
                    <button class="panel-btn panel-btn-primary" onclick="window.location.href='/dev-sounds'">
                        🎛️ Open Sound Studio
                    </button>
                </div>

                <p style="color:#8c7a5a;font-size:0.8rem;margin-top:24px;">
                    Sliders take effect immediately. Values persist across sessions.
                </p>
            </div>
        </div>
    `;
}

// Slider row helper — kept inline near showSettings() so everything sound-related
// in the menu lives in one place.
function soundSliderRow(key, label, value) {
    const pct = Math.round(value * 100);
    return `
        <div style="margin:14px 0;">
            <div style="display:flex;justify-content:space-between;color:#b89a4a;">
                <span>${label}</span>
                <span id="settings-val-${key}">${pct}%</span>
            </div>
            <input type="range" min="0" max="100" value="${pct}"
                id="settings-${key}" style="width:100%;"
                oninput="updateSoundSetting('${key}', this.value / 100)">
        </div>
    `;
}

function updateSoundSetting(key, value) {
    if (!window.SoundBus) return;
    window.SoundBus.setSetting(key, value);
    if (key !== 'muted') {
        const label = document.getElementById('settings-val-' + key);
        if (label) label.textContent = Math.round(Number(value) * 100) + '%';
    } else {
        // Mute toggled — unlock context if we just un-muted so preview works.
        window.SoundBus.resume();
    }
}

function previewSoundSettings() {
    if (!window.SoundBus) return;
    window.SoundBus.resume();
    window.SoundBus.playAction('UI_CONFIRM');
    setTimeout(() => window.SoundBus.playAction('COMBAT_DAMAGE'), 250);
    setTimeout(() => window.SoundBus.playAction('HEAL'), 550);
}

// Initialize main menu on page load
document.addEventListener('DOMContentLoaded', async function() {
    console.log('Initializing 4-panel main menu...');

    // Gate: verify we're connected to the Flask game server before doing anything.
    // If not reachable (e.g. opened via IDE built-in server), block the UI entirely.
    let serverStatus = 0;
    try {
        const probe = await fetch('/api/auth/check-session', { credentials: 'include' });
        serverStatus = probe.status;
    } catch {
        serverStatus = 0; // Network error — wrong server or server down
    }

    if (serverStatus === 0 || (serverStatus !== 200 && serverStatus !== 403)) {
        // Wrong server (e.g. IDE preview) or server down — block everything
        document.body.innerHTML = `
            <div style="display:flex;align-items:center;justify-content:center;
                        height:100vh;background:#0d0b08;font-family:serif;text-align:center;padding:2rem;">
                <div style="max-width:480px;color:#b89a4a;border:1px solid #b89a4a44;
                            border-radius:8px;padding:2.5rem 2rem;">
                    <div style="font-size:2rem;margin-bottom:1rem;">⚔</div>
                    <h2 style="margin:0 0 1rem;color:#d4af5a;font-size:1.3rem;">Game Server Required</h2>
                    <p style="margin:0 0 1.5rem;color:#8c7a5a;line-height:1.6;font-size:0.9rem;">
                        This game must be opened through the Flask game server, not a file browser or IDE preview.
                    </p>
                    <p style="margin:0;color:#6a5a3a;font-size:0.8rem;">
                        Start the server with <code style="color:#b89a4a;">python app.py</code><br>
                        then open <strong style="color:#b89a4a;">http://&lt;server-ip&gt;:5000/</strong>
                    </p>
                </div>
            </div>`;
        return;
    }

    if (serverStatus === 403) {
        // Safety gate active but session not verified — redirect to safety login
        window.location.href = '/safety-login';
        return;
    }

    // Server reachable and safety verified — proceed normally
    await loadHeroes();
    await checkExistingSession();
    showMainMenu();

    // Register callback to re-render when UI script loads
    // (generateUnifiedMinionCard with tooltips isn't available until ui-display-desktop.js loads)
    window.onUIScriptLoaded = function() {
        console.log('UI script loaded - re-rendering main menu with full tooltips');
        // Re-render the entire menu to use generateUnifiedMinionCard for hero cards
        if (typeof generateUnifiedMinionCard === 'function') {
            showMainMenu();
        }
    };

    // If UI script already loaded, trigger immediately
    if (window.uiScriptLoaded && typeof generateUnifiedMinionCard === 'function') {
        window.onUIScriptLoaded();
    }
});

// Add Enter key support for login
document.addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        const usernameField = document.getElementById('username');
        const passwordField = document.getElementById('password');

        if (usernameField && passwordField &&
            (document.activeElement === usernameField || document.activeElement === passwordField)) {
            login();
        }
    }
});
