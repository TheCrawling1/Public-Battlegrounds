// Selection UI rendering - routing, card renderers, selection screens

// Registry: event_type -> renderer function for selection UIs
const SELECTION_RENDERERS = {
    'combat':                   generateCombatUI,
    'boss_combat':              generateCombatUI,
    'ghost_preview':            generateGhostPreviewUI,
    'target_minion':            generateTargetMinionUI,
    'replacement':              generateReplacementUI,
    'confirm_replacement':      generateReplacementUI,
    'confirm_shop_replacement': generateReplacementUI,
    'zone_portal':              generateZonePortalUI,
    'amount_selector':          generateAmountSelectorUI,
};

function generateSelectionUIFromServer(selection) {
    console.log('Generating selection UI from server data:', selection);

    try {

    if (!selection || !selection.options) {
        return `
            <div class="selection-zone">
                <h3>⚠️ Selection Error</h3>
                <p>No selection options available.</p>
            </div>
        `;
    }

    const renderer = SELECTION_RENDERERS[selection.event_type] || generateGenericSelectionUI;
    return renderer(selection);

    } catch (error) {
        console.error('[generateSelectionUIFromServer] Error:', error);
        console.error('[generateSelectionUIFromServer] Selection data:', selection);
        console.error('[generateSelectionUIFromServer] Error stack:', error.stack);
        throw error;
    }
}

// Hero metadata mirrors hero_definitions.py so the preview can render the
// ghost's hero badge. Descriptions are built dynamically from the ghost's
// captured hero_effects so Silas/Puck/Olimpia power scaling shows correctly.
const GHOST_PREVIEW_HERO_META = {
    silas:   { name: 'Silas',   icon: 'coins'  },
    puck:    { name: 'Puck',    icon: 'zap'    },
    olimpia: { name: 'Olimpia', icon: 'shield' }
};

function buildGhostHeroDescription(heroId, powerLevel) {
    const puckMinions = 1 + powerLevel;
    switch (heroId) {
        case 'silas':
            return `Shops cost ${powerLevel} less (minimum 0)`;
        case 'puck':
            return `When combat starts your first ${puckMinions} minions take their turns`;
        case 'olimpia':
            return `Your first ${powerLevel} minion(s) to die are instead stunned and leaped to the rightmost position`;
        default:
            return '';
    }
}

function renderGhostPreviewHeader(previewData) {
    const ghostName   = previewData.ghost_player_name || 'AI Opponent';
    const powerLevel  = previewData.power_level  || 0;
    const milestone   = previewData.milestone    || 0;
    const ring        = previewData.ghost_ring   || 1;
    const heroId      = previewData.ghost_hero_id;
    const heroEffects = previewData.ghost_hero_effects || {};
    const isRanked    = previewData.ghost_is_ranked;
    const mmr         = previewData.ghost_mmr;
    const source      = previewData.ghost_source || 'player';

    // Hero badge — same status-cube styling as the live HUD.
    let heroBadge = '';
    if (heroId && GHOST_PREVIEW_HERO_META[heroId]) {
        const meta = GHOST_PREVIEW_HERO_META[heroId];
        const heroName = previewData.ghost_hero_name || meta.name;
        const iconSvg = typeof generateLucideSVG === 'function'
            ? generateLucideSVG(meta.icon, 16, 16)
            : '';
        const powerUpgraded = heroEffects.power_upgraded || 0;
        const ghostPowerLevel = 1 + powerUpgraded;
        const heroDescription = buildGhostHeroDescription(heroId, ghostPowerLevel);
        heroBadge = `
            <div class="status-cube hero-cube tooltip">
                <div class="status-cube-value">${iconSvg}</div>
                <span class="tooltiptext"><strong>${heroName}</strong> (Power ${ghostPowerLevel})<br>${heroDescription}</span>
            </div>
        `;

        // Lichdom is a second hero power granted by The Great Work.
        if (heroEffects.lichdom) {
            const lichIconSvg = typeof generateLucideSVG === 'function'
                ? generateLucideSVG('crown', 16, 16)
                : '';
            heroBadge += `
                <div class="status-cube hero-cube tooltip">
                    <div class="status-cube-value">${lichIconSvg}</div>
                    <span class="tooltiptext"><strong>Lichdom</strong><br>Effects that cost health instead cost gold</span>
                </div>
            `;
        }
    }

    const romanNumerals = ['0', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X'];
    const ringRoman = romanNumerals[ring] || ring;

    // Source pill — 'player' is the default and gets no decoration.
    let sourceBadge = '';
    if (source === 'headless' || source === 'ai') {
        const label = source === 'headless' ? 'AI Replay' : 'Generated';
        sourceBadge = `<span class="ghost-preview-source-badge source-${source}">${label}</span>`;
    }
    const rankedBadge = isRanked && mmr
        ? `<span class="ghost-preview-rank-badge">MMR ${mmr}</span>`
        : '';

    return `
        <div class="ghost-preview-header">
            <div class="ghost-preview-identity">
                <div class="ghost-preview-name">${ghostName}</div>
                <div class="ghost-preview-sub">
                    Event ${milestone} · Tier ${ringRoman} · Power ${powerLevel}
                    ${sourceBadge}${rankedBadge}
                </div>
            </div>
            <div class="ghost-preview-cubes">
                ${heroBadge}
            </div>
        </div>
    `;
}

function generateGhostPreviewUI(selection) {
    console.log('Generating ghost preview UI:', selection);

    const previewData = selection.preview_data;
    if (!previewData) {
        return `
            <div class="combat-zone">
                <h3>👁️ Ghost Preview</h3>
                <p style="text-align: center;">Preview data not available.</p>
            </div>
        `;
    }

    const playerBand = previewData.player_band || [];
    const ghostBand  = previewData.ghost_band  || [];

    const header = renderGhostPreviewHeader(previewData);

    return `
        <div class="combat-zone ghost-preview-zone">
            ${header}

            <div class="combat-battlefield">
                <div class="combat-side enemy">
                    <h4>Ghost Band (${ghostBand.length})</h4>
                    <div class="combat-minions">
                        ${generateEnemyBandHTML(ghostBand, -1)}
                    </div>
                </div>

                <div class="combat-side player">
                    <h4>Your Band (${playerBand.length})</h4>
                    <div class="combat-minions">
                        ${generatePlayerBandHTML(playerBand, -1)}
                    </div>
                </div>
            </div>

            <div class="ghost-preview-controls">
                <button class="btn btn-primary" onclick="submitSelection('close')">
                    Close Preview
                </button>
            </div>
        </div>
    `;
}

function generateGenericSelectionUI(selection) {
    // Update dynamic keywords based on event_state (e.g., bells_rung for Bell Tower)
    // Check if this is a bell_tower event and update the Rung keyword dynamically
    if (selection.event_type === 'bell_tower' && KEYWORDS['rung']) {
        const bellsRung = (selection.event_state && selection.event_state.bells_rung) || 0;
        KEYWORDS['rung'].description = `You have rung the bell ${bellsRung} time${bellsRung !== 1 ? 's' : ''} so far. Need 4 to recruit Quasimodo.`;
    }

    // Update Scrap Curse keyword with current curse level
    if (KEYWORDS['scrap_curse'] && selection.event_state && selection.event_state.curse_level !== undefined) {
        const curseLevel = selection.event_state.curse_level;
        KEYWORDS['scrap_curse'].description = `Your next general event is guaranteed to be Scrap Heap. You have curse ${curseLevel}.`;
    }

    // Build scried event display if present (for Mark the Scrolls)
    let scriedEventHtml = '';
    if (selection.scried_event) {
        const scried = selection.scried_event;

        // Build choices list - render as template_choice style options with tooltips (horizontal grid)
        let choicesHtml = '';
        if (scried.choices && scried.choices.length > 0) {
            // Use selection-options class for horizontal grid layout like actual events
            choicesHtml = '<div class="selection-options" style="margin-top: 15px;">';
            for (const choice of scried.choices) {
                const hasTooltip = choice.tooltip && choice.tooltip.length > 0;
                const goldCostDisplay = choice.gold_cost > 0 ? `<div class="choice-cost" style="color: #FFD700; font-size: 0.85rem; margin-top: 4px;">${choice.gold_cost} gold</div>` : '';

                // Build the choice content (similar to template_choice, centered for cards)
                let choiceContent = `
                    <div class="template-choice-content scried-preview" style="padding: 12px; text-align: center;">
                        ${choice.icon ? `<div class="choice-icon" style="margin-bottom: 6px;">${choice.icon}</div>` : ''}
                        <div class="choice-name" style="font-weight: bold; margin-bottom: 4px;">${choice.name}</div>
                        <div class="choice-description" style="font-size: 0.85rem; opacity: 0.8;">${choice.description}</div>
                        ${goldCostDisplay}
                    </div>
                `;

                // Wrap in selection-card style with tooltip
                if (hasTooltip) {
                    choicesHtml += `
                        <div class="selection-card scried-choice-wrapper tooltip" data-tooltip-position="top" data-tooltip-context="event" style="cursor: default; pointer-events: auto; opacity: 0.85;">
                            ${choiceContent}
                            <span class="tooltiptext">${choice.tooltip}</span>
                        </div>
                    `;
                } else {
                    choicesHtml += `<div class="selection-card scried-choice-wrapper" style="cursor: default; opacity: 0.85;">${choiceContent}</div>`;
                }
            }
            choicesHtml += '</div>';
        }

        scriedEventHtml = `
            <div class="scried-event-display" style="background: rgba(100, 100, 200, 0.15); border: 2px solid #6666cc; border-radius: 10px; padding: 15px; margin-bottom: 20px;">
                <h4 style="color: #9999ff; margin-bottom: 8px; text-align: center;">${scried.title}</h4>
                <p style="font-size: 0.95rem; opacity: 0.9; text-align: center; margin-bottom: 4px;">${scried.description}</p>
                ${choicesHtml}
            </div>
        `;
    }

    // Generic selection UI for most events
    return `
        <div class="selection-zone">
            <h3>${selection.title || 'Make Selection'}</h3>
            ${selection.warning_text ? `<p style="text-align: center; margin-bottom: 10px; font-size: 1rem; color: #f44336; font-weight: bold;">${selection.warning_text}</p>` : ''}
            <p style="text-align: center; margin-bottom: 15px; font-size: 1.1rem;">${selection.message || ''}</p>
            ${scriedEventHtml}
            ${selection.selection_info ? `<p style="text-align: center; margin-bottom: 20px; font-size: 0.9rem; color: #FFD700;">${selection.selection_info}</p>` : ''}

            <div class="selection-options">
                ${selection.options.map(option => generateSelectionCardFromServer(option)).join('')}
            </div>

            <div class="selection-controls">
                <button class="btn btn-primary" onclick="submitSelection()" id="submitBtn" disabled>
                    Confirm Selection (0)
                </button>
                <button class="btn btn-secondary" onclick="clearSelection()">
                    🔄 Clear Selection
                </button>
            </div>
            <p style="text-align: center; margin-top: 10px; font-size: 0.9rem; opacity: 0.8;">
                Click cards to select, then confirm your choice.
            </p>
        </div>
    `;
}

function generateAmountSelectorUI(selection) {
    // Amount selector for stat reduction with -5/-1/+1/+5/Finish/Cancel buttons
    console.log('[AMOUNT_SELECTOR] Full selection data:', JSON.stringify(selection, null, 2));
    console.log('[AMOUNT_SELECTOR] selection.minion:', selection.minion);
    console.log('[AMOUNT_SELECTOR] selection keys:', Object.keys(selection || {}));

    const minion = selection.minion;
    const stat = selection.stat || 'stat';
    const currentValue = selection.current_value ?? 0;
    const selectedAmount = selection.selected_amount ?? 0;
    const newValue = selection.new_value ?? currentValue;  // Use ?? to handle 0 correctly
    const maxReduction = selection.max_reduction ?? 0;

    // Generate minion card preview with reduced stats
    let minionPreview = '';
    if (minion && minion.name) {
        // Create a copy of the minion with the reduced stat for preview
        const previewMinion = { ...minion };
        if (stat === 'attack') {
            previewMinion.attack = newValue;
        } else if (stat === 'health') {
            previewMinion.health = newValue;
        }

        const options = {
            index: 0,
            showIndex: false,
            isClickable: false,
            isSelected: false,
            isDisabled: false,
            showAbandonButton: false,
            clickHandler: '',
            extraClasses: 'amount-selector-minion'
        };
        try {
            minionPreview = generateUnifiedMinionCard(previewMinion, options);
        } catch (e) {
            console.error('[AMOUNT_SELECTOR] Error generating minion card:', e);
            minionPreview = `<div style="text-align: center; padding: 20px; color: #f44; border: 1px solid #f44; border-radius: 8px;">Error: ${e.message}</div>`;
        }
    } else {
        console.warn('[AMOUNT_SELECTOR] No minion data in selection! minion=', minion);
        minionPreview = `<div style="text-align: center; padding: 20px; color: #ff8; border: 1px solid #ff8; border-radius: 8px;">
            <div>Minion data missing</div>
        </div>`;
    }

    // Generate the increment/decrement buttons
    const decreaseDisabled = selectedAmount <= 0;
    const increaseDisabled = selectedAmount >= maxReduction;

    return `
        <div class="selection-zone amount-selector-zone">
            <h3>${selection.title || 'Reduce ' + stat}</h3>
            <p style="text-align: center; margin-bottom: 15px; font-size: 1.1rem;">${selection.message || ''}</p>

            <div class="amount-selector-content" style="display: flex; flex-direction: column; align-items: center; gap: 20px;">
                <!-- Minion Preview -->
                <div class="amount-selector-minion-preview" style="width: 180px; min-height: 160px;">
                    ${minionPreview}
                </div>

                <!-- Stat Display -->
                <div class="amount-selector-stat-display" style="text-align: center; font-size: 1.2rem;">
                    <div style="margin-bottom: 8px;">
                        <span style="opacity: 0.7;">${stat}:</span>
                        <span style="text-decoration: ${selectedAmount > 0 ? 'line-through' : 'none'}; opacity: ${selectedAmount > 0 ? '0.5' : '1'};">${currentValue}</span>
                        ${selectedAmount > 0 ? `<span style="color: #f44336; margin-left: 8px;">→ ${newValue}</span>` : ''}
                    </div>
                    <div style="font-size: 1.5rem; font-weight: bold; color: #f44336;">
                        -${selectedAmount}
                    </div>
                </div>

                <!-- Increment/Decrement Buttons -->
                <div class="amount-selector-buttons" style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap; justify-content: center;">
                    <button class="btn ${decreaseDisabled ? 'btn-disabled' : 'btn-secondary'}"
                            onclick="${decreaseDisabled ? '' : "amountSelectorSubmit('decrease_5')"}"
                            ${decreaseDisabled ? 'disabled' : ''}
                            style="min-width: 50px;">
                        -5
                    </button>
                    <button class="btn ${decreaseDisabled ? 'btn-disabled' : 'btn-secondary'}"
                            onclick="${decreaseDisabled ? '' : "amountSelectorSubmit('decrease_1')"}"
                            ${decreaseDisabled ? 'disabled' : ''}
                            style="min-width: 50px;">
                        -1
                    </button>

                    <div style="padding: 0 15px; font-size: 1.2rem; min-width: 60px; text-align: center;">
                        ${selectedAmount}
                    </div>

                    <button class="btn ${increaseDisabled ? 'btn-disabled' : 'btn-secondary'}"
                            onclick="${increaseDisabled ? '' : "amountSelectorSubmit('increase_1')"}"
                            ${increaseDisabled ? 'disabled' : ''}
                            style="min-width: 50px;">
                        +1
                    </button>
                    <button class="btn ${increaseDisabled ? 'btn-disabled' : 'btn-secondary'}"
                            onclick="${increaseDisabled ? '' : "amountSelectorSubmit('increase_5')"}"
                            ${increaseDisabled ? 'disabled' : ''}
                            style="min-width: 50px;">
                        +5
                    </button>
                </div>

                <!-- Action Buttons -->
                <div class="amount-selector-actions" style="display: flex; gap: 15px; margin-top: 10px;">
                    <button class="btn btn-primary" onclick="amountSelectorSubmit('finish')" style="min-width: 100px;">
                        Finish
                    </button>
                    <button class="btn btn-secondary" onclick="amountSelectorSubmit('cancel')" style="min-width: 100px;">
                        Cancel
                    </button>
                </div>
            </div>
        </div>
    `;
}

function amountSelectorSubmit(optionId) {
    // Helper function for amount selector buttons - directly submit the selection
    // Uses window.selectedOptions for dev mode compatibility
    console.log('amountSelectorSubmit called with:', optionId);
    window.selectedOptions = [optionId];

    // Call the global submitSelection function (works for both regular and dev mode)
    if (typeof submitSelection === 'function') {
        submitSelection();
    } else {
        console.error('submitSelection function not found');
    }
}

function generateCombatUI(selection) {
    console.log('Generating combat UI:', selection);

    // Get combat state once for consistency
    const combat = window.combatFunctions?.getFrontendCombatState?.();

    // DEBUG: Log combat state when generating UI
    console.log('[DEBUG] generateCombatUI - combat state:', {
        exists: !!combat,
        combat_over: combat?.combat_over,
        winner: combat?.winner,
        player_band_length: combat?.player_band?.length,
        enemy_band_length: combat?.enemy_band?.length
    });

    // Check if we need to show loading screen
    const hasBands = combat?.player_band?.length || combat?.enemy_band?.length;
    const hasLogEntries = combat?.combat_log?.length > 0;

    // Show loading if:
    // 1. No combat state at all, OR
    // 2. Combat exists but bands are empty AND log is empty (fresh combat, not yet loaded)
    // Don't show loading if bands are empty but log has entries (all minions died)
    const needsLoading = !combat || (!hasBands && !hasLogEntries);

    if (needsLoading) {
        // Auto-load combat data if available
        if (window.combatFunctions?.autoLoadCombatData) {
            console.log('[AUTOLOAD] Fresh combat or no state - triggering auto-load');
            setTimeout(() => {
                window.combatFunctions.autoLoadCombatData();
            }, 50);

            // Show loading state initially
            const combatIcon = typeof getIconForEmoji === 'function' ? getIconForEmoji('⚔️', {width: 24, height: 24, cssClass: 'icon-inline'}) : '⚔️';
            const combatIconLarge = typeof getIconForEmoji === 'function' ? getIconForEmoji('⚔️', {width: 48, height: 48, cssClass: 'icon-inline'}) : '⚔️';
            return `
                <div class="combat-zone">
                    <h3>${combatIcon} Combat</h3>
                    <p style="text-align: center; margin-bottom: 15px; font-size: 1rem;">
                        Loading combat data...
                    </p>
                    <div style="text-align: center; padding: 40px;">
                        <div style="font-size: 2rem;">${combatIconLarge}</div>
                        <div>Preparing battle...</div>
                    </div>
                </div>
            `;
        }

        // If no autoload function, show waiting message
        const combatIcon = typeof getIconForEmoji === 'function' ? getIconForEmoji('⚔️', {width: 24, height: 24, cssClass: 'icon-inline'}) : '⚔️';
        const combatIconLarge = typeof getIconForEmoji === 'function' ? getIconForEmoji('⚔️', {width: 48, height: 48, cssClass: 'icon-inline'}) : '⚔️';
        return `
            <div class="combat-zone">
                <h3>${combatIcon} Combat</h3>
                <p style="text-align: center; margin-bottom: 15px; font-size: 1rem;">
                    Waiting for combat data...
                </p>
                <div style="text-align: center; padding: 40px;">
                    <div style="font-size: 2rem;">${combatIconLarge}</div>
                    <div>Battle preparation in progress...</div>
                </div>
            </div>
        `;
    }

    // Combat state exists - render it (even if bands are empty)
    // This is intentionally removed to prevent loading screen when all minions die
    if (false && (!combat || (!combat.player_band?.length && !combat.enemy_band?.length)) && !combat?.combat_over) {
        const combatIcon = typeof getIconForEmoji === 'function' ? getIconForEmoji('⚔️', {width: 24, height: 24, cssClass: 'icon-inline'}) : '⚔️';
        const combatIconLarge = typeof getIconForEmoji === 'function' ? getIconForEmoji('⚔️', {width: 48, height: 48, cssClass: 'icon-inline'}) : '⚔️';
        return `
            <div class="combat-zone">
                <h3>${combatIcon} Combat</h3>
                <p style="text-align: center; margin-bottom: 15px; font-size: 1rem;">
                    Waiting for combat data...
                </p>
                <div style="text-align: center; padding: 40px;">
                    <div style="font-size: 2rem;">${combatIconLarge}</div>
                    <div>Battle preparation in progress...</div>
                </div>
            </div>
        `;
    }

    const isOver = combat.combat_over;
    const uiData = combat.ui_data || {};
    const alivePlayerCount = uiData.alive_player_count || 0;
    const aliveEnemyCount = uiData.alive_enemy_count || 0;
    const totalPlayerCount = uiData.total_player_count || combat.player_band.length;
    const totalEnemyCount = uiData.total_enemy_count || combat.enemy_band.length;

    return `
        <div class="combat-zone">
            <div class="combat-battlefield">
                <div class="combat-side enemy">
                    <h4>Enemy Band (${aliveEnemyCount}/${totalEnemyCount})</h4>
                    <div class="combat-minions">
                        ${generateEnemyBandHTML(combat.enemy_band, uiData.active_enemy_index)}
                    </div>
                </div>

                <div class="combat-side player">
                    <h4>Your Band (${alivePlayerCount}/${totalPlayerCount})</h4>
                    <div class="combat-minions">
                        ${generatePlayerBandHTML(combat.player_band, uiData.active_player_index)}
                    </div>
                </div>
            </div>

            ${generateCombatControls(isOver)}

            <div class="combat-log">
                <h4>📜 Combat ${isOver ? 'Summary' : 'Log'}</h4>
                <div class="combat-log-content">
                    ${combat.combat_log.map((entry, index) => {
                        // Handle both old string format and new object format
                        const message = typeof entry === 'string' ? entry : entry.message;
                        const commandIndex = typeof entry === 'object' ? entry.commandIndex : null;
                        const isClickable = commandIndex !== null;  // Always clickable if has index

                        // Get current interpreter position from combat functions
                        const currentPosition = window.combatFunctions ?
                            (window.combatFunctions.getCurrentPosition ? window.combatFunctions.getCurrentPosition() : -1) : -1;
                        const isActive = commandIndex !== null && commandIndex === currentPosition;

                        if (isClickable) {
                            const activeClass = isActive ? ' log-entry-active' : '';
                            return `<div class="log-entry log-entry-clickable${activeClass}" data-command-index="${commandIndex}" onclick="window.combatFunctions.jumpToCommandIndex(${commandIndex})" title="Click to jump to this moment">${message}</div>`;
                        } else {
                            return `<div class="log-entry">${message}</div>`;
                        }
                    }).join('')}
                </div>
            </div>
        </div>
    `;
}

// Helper function to get minion template from backend-provided data
function getMinionTemplate(minionName) {
    // Get template from loaded minion data
    const minionData = TooltipPortal.getMinionData();
    if (minionData && minionData[minionName]) {
        return minionData[minionName];
    }
    return null;
}

// Enrich combat minion with template data if needed
function enrichCombatMinion(minion) {
    // Always try to get template data for tier and other missing fields
    const template = getMinionTemplate(minion.name);

    // Ensure health is a valid number (fixes summons appearing dead when health is null/undefined)
    if (typeof minion.health !== 'number' || minion.health === null) {
        minion.health = template?.health || 1;
        console.warn(`[enrichCombatMinion] Fixed missing health for ${minion.name}`);
    }

    // Fill in tier from template if missing
    if (!minion.tier && template && template.tier) {
        minion.tier = template.tier;
    }
    // Fill in type from template if missing
    if (!minion.type && template && template.type) {
        minion.type = template.type;
    }

    // Always fill in keyword-related count fields from template if missing
    // These are needed for proper display (e.g., "Leap 1", "Hide 2", "Ring 3")
    if (template) {
        const countFields = [
            'leap_distance', 'hide_count', 'ring_count', 'stun_count',
            'multi_attack_count', 'cleave_amount'
        ];
        for (const field of countFields) {
            if (minion[field] === undefined && template[field] !== undefined) {
                minion[field] = template[field];
            }
        }
    }

    // Always fill in missing effect fields from template
    // This ensures on_any_x and other effects are available for tooltip display
    if (template) {
        const effectFields = [
            'cast_effect', 'assault_effect', 'death_toll_effect', 'rage_effect',
            'calm_effect', 'start_of_combat_effect', 'on_hide_lost_effect',
            'on_any_death_effect', 'on_any_summon_effect', 'on_any_cast_effect',
            'on_any_leap_effect', 'on_any_death_toll_effect', 'on_damage_effect'
        ];
        for (const field of effectFields) {
            if (!minion[field] && template[field]) {
                minion[field] = template[field];
            }
        }
    }

    // Check if minion has any effect field that indicates it came with full data
    const hasEffectFields = minion.cast_effect || minion.assault_effect || minion.death_toll_effect;

    // If minion already has effect fields, return now (we've already filled in missing data above)
    if (hasEffectFields) {
        return minion;
    }

    if (template) {
        // Merge template data (effect definitions) with combat state
        // Start with template to get all base data
        const enriched = { ...template };

        // Only override template values with defined values from combat minion
        // This prevents undefined values from overwriting template data
        for (const key in minion) {
            if (minion[key] !== undefined) {
                enriched[key] = minion[key];
            }
        }

        // Ensure health is a valid number after enrichment
        if (typeof enriched.health !== 'number' || enriched.health === null) {
            enriched.health = template.health || 1;
            console.warn(`[enrichCombatMinion] Fixed missing health for ${minion.name} using template`);
        }

        return enriched;
    }

    // Return minion as-is if we can't enrich it, but ensure health is valid
    if (typeof minion.health !== 'number' || minion.health === null) {
        minion.health = 1; // Default to 1 if health is missing and no template
        console.warn(`[enrichCombatMinion] Fixed missing health for ${minion.name} (no template)`);
    }
    return minion;
}

function generatePlayerBandHTML(playerBand, activePlayerIndex) {
    if (!playerBand || playerBand.length === 0) {
        return '<div style="text-align: center; opacity: 0.6;">No minions</div>';
    }

    return playerBand.map((minion, index) => {
        // Enrich minion with template data for complete tooltips
        const enrichedMinion = enrichCombatMinion(minion);

        // Explicit dead check: only dead if health is a number AND <= 0
        // This prevents null/undefined from being treated as dead
        const isDead = typeof enrichedMinion.health === 'number' && enrichedMinion.health <= 0;
        const isActive = !isDead && index === activePlayerIndex;

        const indicators = [];
        if (isActive) indicators.push({ class: 'active-indicator', text: 'Next to Attack' });

        const extraClasses = [
            isDead ? 'dead' : '',
            isActive ? 'active' : ''
        ].filter(Boolean).join(' ');

        const options = {
            index,
            showIndex: true,
            isClickable: false,
            isSelected: false,
            isDisabled: false,
            showAbandonButton: false,
            clickHandler: '',
            extraClasses,
            indicators
        };

        return generateUnifiedMinionCard(enrichedMinion, options);
    }).join('');
}

function generateEnemyBandHTML(enemyBand, activeEnemyIndex) {
    if (!enemyBand || enemyBand.length === 0) {
        return '<div style="text-align: center; opacity: 0.6;">No minions</div>';
    }

    return enemyBand.map((minion, index) => {
        // Enrich minion with template data for complete tooltips
        const enrichedMinion = enrichCombatMinion(minion);

        // Explicit dead check: only dead if health is a number AND <= 0
        // This prevents null/undefined from being treated as dead
        const isDead = typeof enrichedMinion.health === 'number' && enrichedMinion.health <= 0;
        const isActive = !isDead && index === activeEnemyIndex;

        const indicators = [];
        if (isActive) indicators.push({ class: 'active-indicator', text: 'Next to Attack' });

        const extraClasses = [
            isDead ? 'dead' : '',
            isActive ? 'active' : ''
        ].filter(Boolean).join(' ');

        const options = {
            index,
            showIndex: true,
            isClickable: false,
            isSelected: false,
            isDisabled: false,
            showAbandonButton: false,
            clickHandler: '',
            extraClasses,
            indicators
        };

        return generateUnifiedMinionCard(enrichedMinion, options);
    }).join('');
}

function generateCombatControls(isOver) {
    // SVG icons for combat buttons
    const nextIcon = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>';
    const playIcon = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>';
    const pauseIcon = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>';
    const endIcon = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="13 17 18 12 13 7"></polyline><polyline points="6 17 11 12 6 7"></polyline></svg>';
    const continueIcon = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline><line x1="15" y1="6" x2="15" y2="18"></line></svg>';

    if (!isOver) {
        // Speed selector buttons
        const speedButtons = ['1x', '2x', '3x'].map(speed => {
            const speedNum = parseInt(speed);
            const isActive = autoCombatSpeed === speedNum;
            return `<button class="btn btn-speed ${isActive ? 'btn-speed-active' : ''}"
                           onclick="setAutoCombatSpeed(${speedNum})"
                           title="Auto speed ${speed}">
                        ${speed}
                    </button>`;
        }).join('');

        return `
            <div class="combat-controls">
                <button class="btn btn-primary" onclick="submitCombatSelection('next')" id="combatNextBtn" ${autoCombatInProgress ? 'disabled' : ''}>
                    ${nextIcon} Next action
                </button>
                <button class="btn ${autoCombatInProgress ? 'btn-secondary' : 'btn-warning'}"
                        onclick="${autoCombatInProgress ? 'stopAutoCombat()' : 'submitCombatSelection(\'auto\')'}"
                        id="combatAutoBtn">
                    ${autoCombatInProgress ? pauseIcon : playIcon} ${autoCombatInProgress ? 'Stop' : 'Auto'}
                </button>
                <div class="speed-selector">
                    ${speedButtons}
                </div>
                <button class="btn btn-danger" onclick="submitCombatSelection('end')" id="combatEndBtn" ${autoCombatInProgress ? 'disabled' : ''}>
                    ${endIcon} End combat
                </button>
            </div>
        `;
    } else {
        return `
            <div class="combat-controls">
                <button class="btn btn-primary" onclick="submitCombatSelection('continue')" id="combatCompleteBtn">
                    ${continueIcon} Continue
                </button>
            </div>
        `;
    }
}

function generateTargetMinionUI(selection) {
    console.log('Generating target minion UI:', selection);

    if (!selection || !selection.effect_preview) {
        return `
            <div class="selection-zone">
                <h3>⚠️ Target Selection Error</h3>
                <p>Effect preview not available.</p>
            </div>
        `;
    }

    const effect = selection.effect_preview;
    const hasBack = selection.previous_selection;

    // For ring/keyword/buff types, render as a simple text description
    const isSimpleStyle = effect.type === 'ring' || effect.type === 'keyword' || effect.type === 'buff';

    let effectHtml = '';
    if (isSimpleStyle) {
        // Display effect as simple styled text (matching other UI elements)
        if (effect.type === 'ring' || effect.type === 'keyword') {
            // For ring/keyword: show "Name: Description"
            effectHtml = `
                <p style="text-align: center; margin-bottom: 20px; font-size: 1.1rem;">
                    <strong>${effect.name}:</strong> ${effect.description || ''}
                </p>`;
        } else {
            // For buff: just show the name (e.g., "+3 Health")
            effectHtml = `
                <p style="text-align: center; margin-bottom: 20px; font-size: 1.1rem;">
                    <strong>${effect.name}</strong>
                </p>`;
        }
    } else if (selection.message) {
        // Only show message and comparison if message is provided
        effectHtml = `
            <p style="text-align: center; margin-bottom: 20px; font-size: 1.1rem;">
                ${selection.message}
            </p>
            <div class="replacement-comparison">
                <div class="replacement-new">
                    <h4 style="color: #4CAF50; text-align: center; margin-bottom: 10px;">Blessing</h4>
                    <div style="text-align: center;">
                        <div style="font-weight: bold; margin-bottom: 5px;">${effect.name}</div>
                        <div style="color: #FFD700;">${effect.description}</div>
                    </div>
                </div>
                <div class="replacement-arrow">➡️</div>
                <div class="replacement-current">
                    <h4 style="color: #FF9800; text-align: center; margin-bottom: 10px;">Choose Target</h4>
                    <p style="text-align: center; font-size: 0.9rem;">Click a minion to apply the effect</p>
                </div>
            </div>`;
    }

    return `
        <div class="replacement-zone">
            <h3>${selection.title}</h3>
            ${effectHtml}
            <div class="selection-options">
                ${selection.options.map(option => generateSelectionCardFromServer(option)).join('')}
            </div>

            <div class="selection-controls">
                <button class="btn btn-primary" onclick="submitSelection()" id="submitBtn" disabled>
                    Apply Effect (0/1)
                </button>
                <button class="btn btn-secondary" onclick="goBack()">
                    ${hasBack ? 'Back' : 'Cancel'}
                </button>
            </div>
        </div>
    `;
}

function generateReplacementUI(selection) {
    console.log('Generating replacement UI:', selection);

    if (selection.event_type === 'replacement') {
        // Initial replacement selection
        return `
            <div class="replacement-zone">
                <h3>🔄 ${selection.title}</h3>
                <div class="band-full-warning">
                    ⚠️ Your band is full (6/6 minions)! You must replace a minion to add a new one.
                </div>
                <p style="text-align: center; margin-bottom: 20px; font-size: 1.1rem;">${selection.message}</p>

                <div class="selection-options">
                    ${selection.options.map(option => generateSelectionCardFromServer(option)).join('')}
                </div>

                <div class="selection-controls">
                    <button class="btn btn-primary" onclick="submitSelection()" id="submitBtn" disabled>
                        Confirm Selection (0/1)
                    </button>
                    <button class="btn btn-secondary" onclick="clearSelection()">
                        🔄 Clear Selection
                    </button>
                </div>
            </div>
        `;
    } else if (selection.event_type === 'confirm_replacement' || selection.event_type === 'confirm_shop_replacement') {
        // Confirmation step for replacement
        const newMinion = selection.new_minion;
        const cost = selection.cost || 0;
        const hasBack = selection.previous_selection;

        const cardOptions = {
            index: 0,
            showIndex: false,
            isClickable: false,
            isSelected: false,
            isDisabled: false,
            showAbandonButton: false,
            clickHandler: '',
            extraClasses: 'selection-minion-card'
        };
        const newMinionCard = generateUnifiedMinionCard(newMinion, cardOptions);

        return `
            <div class="replacement-zone">
                <h3>${selection.title}</h3>

                <div class="replacement-new-minion" style="display: flex; justify-content: center; margin-bottom: 15px; max-width: clamp(120px, 16vw, 180px); margin-left: auto; margin-right: auto;">
                    ${newMinionCard}
                </div>
                ${cost > 0 ? `<p style="text-align: center; color: var(--gold-glow); margin-bottom: 10px;">${cost} gold</p>` : ''}
                <p style="text-align: center; margin-bottom: 15px; font-size: 1.1rem;">
                    Choose a minion for this to replace
                </p>

                <div class="selection-options">
                    ${selection.options.map(option => generateSelectionCardFromServer(option)).join('')}
                </div>

                <div class="selection-controls">
                    <button class="btn btn-primary" onclick="submitSelection()" id="submitBtn" disabled>
                        Confirm Replacement (0/1)
                    </button>
                    <button class="btn btn-secondary" onclick="goBack()">
                        ${hasBack ? 'Back' : 'Cancel'}
                    </button>
                </div>
            </div>
        `;
    }
}

function generateZonePortalUI(selection) {
    console.log('Generating zone portal UI:', selection);

    if (!selection || !selection.options) {
        return `
            <div class="selection-zone">
                <h3>⚠️ Portal Error</h3>
                <p>No portal options available.</p>
            </div>
        `;
    }

    const availableDestinations = selection.available_destinations || [];
    const currentZone = gameData.current_zone || {};

    return `
        <div class="zone-portal-zone">
            <h3>${selection.title}</h3>
            <p style="text-align: center; margin-bottom: 15px; font-size: 1.1rem;">${selection.message}</p>

            <div class="selection-options">
                ${selection.options.map(option => generateZonePortalCard(option)).join('')}
            </div>

            <div class="selection-controls">
                <button class="btn btn-primary" onclick="submitSelection()" id="submitBtn" disabled>
                    Confirm Choice (0/1)
                </button>
                <button class="btn btn-secondary" onclick="clearSelection()">
                    🔄 Clear Selection
                </button>
            </div>
            <p style="text-align: center; margin-top: 10px; font-size: 0.9rem; opacity: 0.8;">
                Choose your destination or stay in your current zone.
            </p>
        </div>
    `;
}

function generateZonePortalCard(option) {
    const cardClass = `selection-card zone-portal-card`;

    let content = '';

    if (option.type === 'travel_to_zone') {
        const zoneData = option.zone_data;
        content = `
            <div class="zone-travel-option">
                <div class="zone-icon">${zoneData.icon || '🌍'}</div>
                <div class="zone-name">${zoneData.name}</div>
                <div class="zone-description">${zoneData.description || 'A mysterious land...'}</div>
                <div class="zone-pool-info">
                    ${zoneData.pool_modifiers ?
                        `Creatures: ${zoneData.pool_modifiers.join(', ')}` :
                        'Creatures: All Types'}
                </div>
            </div>
        `;
    } else if (option.type === 'stay_in_zone') {
        const currentZone = gameData.current_zone || {};
        content = `
            <div class="zone-stay-option">
                <div class="zone-icon">${currentZone.icon || '🌍'}</div>
                <div class="zone-name">Stay Here</div>
                <div class="zone-description">Continue exploring ${currentZone.name || 'this zone'}</div>
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

function generateSelectionCardFromServer(option) {
    // Server should provide complete card display data
    const isAffordable = option.affordable !== false && option.disabled !== true;
    const cardClass = `selection-card ${!isAffordable ? 'unaffordable' : ''}`;

    // Server should provide complete HTML content for each card
    let content = option.display_content || generateFallbackCardContent(option);

    const clickAction = isAffordable ? `onclick="toggleSelection('${option.id}')"` : '';

    // Debug logging
    console.log(`Generating selection card: type=${option.type}, id=${option.id}, affordable=${isAffordable}, hasClick=${!!clickAction}`);

    return `
        <div class="${cardClass}" id="card_${option.id}" ${clickAction} data-option-id="${option.id}">
            ${content}
        </div>
    `;
}

// --- Card renderer functions (one per option type) ---

const BASE_MINION_OPTS = {
    showIndex: false, isClickable: false, isSelected: false,
    isDisabled: false, showAbandonButton: false, clickHandler: '',
    extraClasses: 'selection-minion-card'
};

function renderMinionPurchaseCard(option) {
    const minion = option.data;
    let content = generateUnifiedMinionCard(minion, { ...BASE_MINION_OPTS, index: 0 });
    if (option.cost > 0) {
        content += `<div class="selection-cost">${option.cost} gold</div>`;
    }
    return content;
}

function renderTargetedEffectCard(option) {
    const minion = option.data || (gameData?.run?.band?.[option.target_index]);
    console.log('[renderTargetedEffectCard] apply_targeted_effect:', {
        hasOptionData: !!option.data,
        minionName: minion?.name,
        minionImage: minion?.image,
        minionKeywords: minion?.keywords,
        targetIndex: option.target_index
    });
    return generateUnifiedMinionCard(minion, { ...BASE_MINION_OPTS, index: option.target_index, showIndex: true });
}

function renderReplacementCard(option) {
    const minion = option.data;
    return generateUnifiedMinionCard(minion, { ...BASE_MINION_OPTS, index: 0, extraClasses: 'selection-minion-card new-minion-offer' });
}

function renderReplaceWithCard(option) {
    const band = gameData.run.band;
    const minion = band[option.replace_index];
    return generateUnifiedMinionCard(minion, { ...BASE_MINION_OPTS, index: option.replace_index, showIndex: true, extraClasses: 'selection-minion-card replacement-target' });
}

function renderBuffCard(option) {
    return `
        <div class="selection-buff">
            <div style="font-weight: bold;">${option.message}</div>
        </div>
    `;
}

function renderSkipCard(option) {
    return `
        <div class="selection-skip">
            <div>${option.message}</div>
        </div>
    `;
}

function renderScryCard(option) {
    const iconColor = option.type === 'scry_keep' ? '#4CAF50' : option.type === 'scry_discard' ? '#f44336' : '#9999ff';
    return `
        <div class="selection-scry-option" style="padding: 12px; text-align: center;">
            <div style="font-weight: bold; color: ${iconColor}; margin-bottom: 4px;">${option.message}</div>
            ${option.description ? `<div style="font-size: 0.85rem; opacity: 0.8;">${option.description}</div>` : ''}
        </div>
    `;
}

function renderTemplateChoiceCard(option) {
    const hasTooltip = option.tooltip && option.tooltip.length > 0;
    const disabledClass = option.disabled ? 'choice-disabled' : '';
    const goldCostDisplay = option.gold_cost > 0 ? `<div class="choice-cost">${option.gold_cost} gold</div>` : '';
    const healthCostDisplay = option.health_cost > 0
        ? (option.lichdom
            ? `<div class="choice-health-cost" style="color: #FFD700; font-weight: bold;">${option.health_cost} gold</div>`
            : `<div class="choice-health-cost" style="color: #f44336; font-weight: bold;">${option.health_cost} HP</div>`)
        : '';

    let content = `
        <div class="template-choice-content ${disabledClass}">
            ${option.icon ? `<div class="choice-icon">${option.icon}</div>` : ''}
            <div class="choice-name" style="font-weight: bold; margin-bottom: 4px;">${option.message}</div>
            <div class="choice-description" style="font-size: 0.85rem; opacity: 0.8;">${option.description}</div>
            ${goldCostDisplay}
            ${healthCostDisplay}
        </div>
    `;

    if (hasTooltip) {
        return `
            <div class="selection-template-choice tooltip" data-tooltip-position="top" data-tooltip-context="event">
                ${content}
                <span class="tooltiptext">${option.tooltip}</span>
            </div>
        `;
    }

    return `<div class="selection-template-choice">${content}</div>`;
}

function renderSacrificeGoldenCard(option) {
    const minion = option.data;

    if (minion) {
        let content = generateUnifiedMinionCard(minion, { ...BASE_MINION_OPTS, index: option.target_index, showIndex: true });

        if (option.type === 'sacrifice_target') {
            content += '<div class="sacrifice-indicator" style="color: #f44336; font-weight: bold; margin-top: 4px;">Click to sacrifice</div>';
        } else if (option.type === 'golden_target') {
            content += '<div class="golden-indicator" style="color: #ffc107; font-weight: bold; margin-top: 4px;">Click to make golden</div>';
        }

        return content;
    }

    return renderDefaultCard(option);
}

function renderMinionStatCard(option) {
    const minion = option.minion || option.data;

    if (minion) {
        const isDisabled = option.disabled === true;
        const opts = {
            ...BASE_MINION_OPTS,
            index: option.target_index,
            showIndex: true,
            isDisabled: isDisabled,
            extraClasses: `selection-minion-card ${isDisabled ? 'disabled-minion' : ''}`
        };

        let content = generateUnifiedMinionCard(minion, opts);

        if (option.stat && option.current_value !== undefined) {
            content += `<div class="stat-info" style="text-align: center; margin-top: 4px; font-size: 0.85rem;">${option.stat}: ${option.current_value}</div>`;
        }

        if (isDisabled) {
            content += '<div class="disabled-indicator" style="color: #888; font-size: 0.8rem; margin-top: 4px;">Nothing to reduce</div>';
        }

        return content;
    }

    return renderDefaultCard(option);
}

function renderChooseEventCard(option) {
    return `
        <div class="selection-template-choice">
            <div class="template-choice-content">
                ${option.icon ? `<div class="choice-icon">${option.icon}</div>` : ''}
                <div class="choice-name">${option.message}</div>
                ${option.description ? `<div class="choice-description">${option.description}</div>` : ''}
            </div>
        </div>
    `;
}

function renderCombineCard(option) {
    const minion = option.minion_data;
    return generateUnifiedMinionCard(minion, { ...BASE_MINION_OPTS, index: option.minion_index, showIndex: true });
}

function renderDefaultCard(option) {
    return `
        <div class="selection-other">
            <div>${option.message || option.type}</div>
        </div>
    `;
}

// Registry: option type/render_as -> renderer function
const CARD_RENDERERS = {
    'minion':                     renderMinionPurchaseCard,
    'purchase':                   renderMinionPurchaseCard,
    'shop_replacement':           renderMinionPurchaseCard,
    'apply_targeted_effect':      renderTargetedEffectCard,
    'replacement':                renderReplacementCard,
    'replace_with':               renderReplaceWithCard,
    'shop_replace_with':          renderReplaceWithCard,
    'choose_buff':                renderBuffCard,
    'skip':                       renderSkipCard,
    'scry_keep':                  renderScryCard,
    'scry_discard':               renderScryCard,
    'back_to_parent':             renderScryCard,
    'template_choice':            renderTemplateChoiceCard,
    'sacrifice_target':           renderSacrificeGoldenCard,
    'golden_target':              renderSacrificeGoldenCard,
    'select_for_number_choice':   renderMinionStatCard,
    'select_for_choice_list':     renderMinionStatCard,
    'minion_card':                renderMinionStatCard,
    'select_minion_for_combine':  renderCombineCard,
    'choose_event':               renderChooseEventCard,
};

function generateFallbackCardContent(option) {
    // Check render_as hint first (server can override), then fall back to type
    const renderer = CARD_RENDERERS[option.render_as] || CARD_RENDERERS[option.type] || renderDefaultCard;
    return renderer(option);
}

