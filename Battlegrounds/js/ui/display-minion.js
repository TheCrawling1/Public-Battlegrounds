// Minion card rendering - band display, unified minion cards, animations

function generateBandDisplay(run, uiState = {}) {
    const hasSelection = run.pending_selection !== null;
    const maxBandSize = uiState.max_band_size || 6;
    return `
        <div class="band-container">
            <div class="band-count-badge">${run.band.length}/${maxBandSize}</div>
            <div class="band-grid">
                ${run.band.map((minion, index) => generateMinionCard(minion, index, hasSelection)).join('')}
            </div>
        </div>
    `;
}

// Helper function to convert tier number to Roman numerals
function toRomanNumeral(num) {
    const romanNumerals = {
        1: 'I',
        2: 'II',
        3: 'III',
        4: 'IV',
        5: 'V',
        6: 'VI'
    };
    return romanNumerals[num] || num.toString();
}

// Helper function to calculate font size for minion stats based on value length
// Prevents stats from overflowing and blocking tribe display
function getStatFontSize(attack, health) {
    const maxValue = Math.max(Math.abs(attack), Math.abs(health));
    const digits = maxValue.toString().length;

    if (digits <= 2) {
        return '0.85rem';  // Default size for 1-2 digits
    } else if (digits === 3) {
        return '0.75rem';  // Smaller for 3 digits (e.g., 100)
    } else {
        return '0.65rem';  // Smallest for 4+ digits (e.g., 1000+)
    }
}

// Helper function to calculate font size for tribe names based on text length
// Shorter names get bigger text, longer names get smaller text
function getTribeFontSize(tribeName) {
    const len = tribeName.length;
    if (len <= 4) {
        return '0.7rem';   // Short: All, Mech, Naga
    } else if (len <= 6) {
        return '0.6rem';   // Medium: Beast, Demon, Dragon, Murloc, Pirate, Undead
    } else if (len <= 8) {
        return '0.5rem';   // Long: Quilboar
    } else {
        return '0.45rem';  // Very long: Elemental, Construct
    }
}

// Helper function to calculate font size for minion names based on text length
function getMinionNameFontSize(name) {
    const len = name.length;
    if (len <= 10) {
        return '0.7rem';   // Short names
    } else if (len <= 14) {
        return '0.6rem';   // Medium names
    } else if (len <= 18) {
        return '0.5rem';   // Long names
    } else {
        return '0.45rem';  // Very long names
    }
}

// Helper function to calculate font size for keyword tags based on text length
// Ensures long keywords like "Start of Combat" fit on one line
function getKeywordFontSize(keyword) {
    const len = keyword.length;
    if (len <= 5) {
        return '0.6rem';   // Short: Guard, Poke, Rage, Cast, Rich
    } else if (len <= 8) {
        return '0.55rem';  // Medium: Assault, Reborn
    } else if (len <= 12) {
        return '0.45rem';  // Long: Death Toll, Venomous
    } else {
        return '0.38rem';  // Very long: Start of Combat, End of Combat
    }
}

// UNIFIED MINION RENDERING - Used everywhere in the game
function generateUnifiedMinionCard(minion, options = {}) {
    // Defensive check - return placeholder if minion is invalid
    if (!minion || typeof minion !== 'object') {
        console.warn('[generateUnifiedMinionCard] Invalid minion data:', minion);
        return `<div class="minion-card error-card">
            <div class="minion-name">Invalid Minion</div>
            <div class="minion-stats-box">
                <div class="minion-stats">
                    <span class="stat attack">?</span>
                    <span class="stat health">?</span>
                </div>
            </div>
        </div>`;
    }

    const {
        index = 0,
        showIndex = true,
        isClickable = false,
        isSelected = false,
        isDisabled = false,
        showAbandonButton = false,
        clickHandler = '',
        extraClasses = '',
        indicators = [],
        dataAttributes = {}  // Custom data attributes e.g. { 'minion-id': '123' }
    } = options;

    // Get minion image style - uses server-provided image_path
    const imageStyle = typeof getMinionImageStyle === 'function'
        ? getMinionImageStyle(minion)
        : (minion.image ? `background-image: url('images/original/${minion.image}'); background-size: 100% 100%; background-repeat: no-repeat; background-position: center;` : '');

    const cardClasses = [
        'minion-card',
        minion.golden ? 'golden' : '',
        isSelected ? 'selected' : '',
        isDisabled ? 'disabled' : '',
        extraClasses
    ].filter(Boolean).join(' ');

    const indexDisplay = showIndex ? ` #${index + 1}` : '';
    const clickAttr = isClickable && clickHandler ? clickHandler : '';

    // Format tribe(s) display - handle array, comma-separated string, or single string
    // Font size scales based on tribe name length
    let tribesHtml = '';
    if (minion.type) {
        let tribes;
        if (Array.isArray(minion.type)) {
            tribes = minion.type;
        } else if (typeof minion.type === 'string' && minion.type.includes(',')) {
            // Split comma-separated string into array
            tribes = minion.type.split(',').map(t => t.trim());
        } else {
            tribes = [minion.type];
        }
        if (tribes.length > 0 && tribes[0]) {
            tribesHtml = `<div class="minion-tribes">
                ${tribes.map(tribe => `<div class="minion-tribe" style="font-size: ${getTribeFontSize(tribe)}">${tribe}</div>`).join('')}
            </div>`;
        }
    }

    // Format tier display in Roman numerals - or X if selected for abandonment
    const tierHtml = showAbandonButton
        ? `<div class="minion-tier minion-tier-abandon" onclick="abandonMinion(event, ${index})">×</div>`
        : (minion.tier ? `<div class="minion-tier">${toRomanNumeral(minion.tier)}</div>` : '');

    // Calculate dynamic font sizes based on content length
    const statFontSize = getStatFontSize(minion.attack, minion.health);
    const nameFontSize = getMinionNameFontSize(minion.name + (showIndex ? ` #${index + 1}` : ''));

    // Build custom data attributes string
    const customDataAttrs = Object.entries(dataAttributes)
        .map(([key, value]) => `data-${key}="${value}"`)
        .join(' ');

    // Golden minions get a clipped sheen overlay (V3 treatment).
    const goldenSheen = minion.golden ? '<div class="golden-sheen"></div>' : '';

    return `
        <div class="${cardClasses}"
             ${clickAttr}
             data-minion-index="${index}"
             data-combat-id="${minion._combat_id || ''}"
             data-tooltip-context="minion"
             ${customDataAttrs}
             style="${imageStyle}">
            ${goldenSheen}

            <div class="minion-name" style="font-size: ${nameFontSize}">${minion.name}${indexDisplay}</div>

            ${tierHtml}

            <div class="minion-tags">
                ${generateAllEffectTags(minion)}
            </div>

            <div class="minion-stats-box">
                <div class="minion-stats">
                    <span class="stat attack" style="font-size: ${statFontSize}">${typeof getIconForEmoji === 'function' ? getIconForEmoji('⚔️', {width: 20, height: 20, cssClass: 'icon-inline'}) : '⚔️'}${minion.attack}</span>
                    <span class="stat health" style="font-size: ${statFontSize}">${typeof getIconForEmoji === 'function' ? getIconForEmoji('❤️', {width: 20, height: 20, cssClass: 'icon-inline'}) : '❤️'}${Math.max(0, minion.health)}</span>
                </div>
            </div>

            ${tribesHtml}

            ${indicators.map(indicator => `<div class="${indicator.class}">${indicator.text}</div>`).join('')}
        </div>
    `;
}

// Legacy function - now just calls unified version
function generateMinionCard(minion, index, hasSelection, cardType = 'band') {
    const isSelected = selectedMinionIndex === index;

    // Enrich minion with template data for consistent tooltips
    const enrichedMinion = enrichCombatMinion(minion);

    const options = {
        index,
        showIndex: true,
        isClickable: cardType === 'band',
        isSelected,
        isDisabled: hasSelection,
        showAbandonButton: isSelected && cardType === 'band',
        clickHandler: cardType === 'band' ? `onclick="selectMinion(${index})"` : ''
    };

    return generateUnifiedMinionCard(enrichedMinion, options);
}

function restoreSelections(previousSelections) {
    // Restore selections after UI updates
    previousSelections.forEach(optionId => {
        const card = document.getElementById(`card_${optionId}`);
        if (card) {
            card.classList.add('selected');
            if (!selectedOptions.includes(optionId)) {
                selectedOptions.push(optionId);
            }
        }
    });
    updateSubmitButton();
}

// Stone trail animation for movement hover effects
let stoneTrailAnimation = null;

function triggerStoneTrailAnimation(direction) {
    // Cancel any existing animation
    if (stoneTrailAnimation) {
        clearTimeout(stoneTrailAnimation);
        stoneTrailAnimation = null;
    }

    const stoneWave = document.querySelector('.stone-wave');
    if (!stoneWave || !gameData || !gameData.run) return;

    const stones = stoneWave.querySelectorAll('.wave-stone');
    const centerStone = stoneWave.querySelector('.center-stone');
    const totalStones = stones.length;

    // Clear any existing lit states
    stones.forEach(stone => stone.classList.remove('lit'));
    if (centerStone) centerStone.classList.remove('lit');

    // Get current position (0-11 for 12 flag positions)
    const currentPosition = gameData.run.ring_position || 0;
    const FLAG_COUNT = 12;

    // Convert ring position to stone index (use totalStones - 1 to avoid out of bounds)
    const currentStoneIndex = Math.round((currentPosition / (FLAG_COUNT - 1)) * (totalStones - 1));

    // Center stone is at slot 6 (index 5 with 0-indexing)
    const centerStoneIndex = Math.round((5 / (FLAG_COUNT - 1)) * (totalStones - 1));

    const delayPerStone = 5; // ms between each stone
    let animationStep = 0;

    if (direction === 'left') {
        // Calculate destination position (wraps from 0 to 11)
        const destPosition = currentPosition === 0 ? FLAG_COUNT - 1 : currentPosition - 1;
        const destStoneIndex = Math.round((destPosition / (FLAG_COUNT - 1)) * (totalStones - 1));

        if (currentPosition === 0) {
            // Wrap around: going from position 0 to position 11 (right side)
            // Animate left to right across entire display
            function animateWrapLeft() {
                const stoneIndex = animationStep;
                if (stoneIndex < totalStones && stones[stoneIndex]) {
                    stones[stoneIndex].classList.add('lit');
                    animationStep++;
                    stoneTrailAnimation = setTimeout(animateWrapLeft, delayPerStone);
                }
            }
            animateWrapLeft();
        } else {
            // Normal left movement - animate to destination stone
            function animateLeft() {
                const stoneIndex = currentStoneIndex - animationStep;
                if (stoneIndex >= destStoneIndex && stoneIndex >= 0 && stones[stoneIndex]) {
                    stones[stoneIndex].classList.add('lit');
                    animationStep++;
                    stoneTrailAnimation = setTimeout(animateLeft, delayPerStone);
                }
            }
            animateLeft();
        }

    } else if (direction === 'right') {
        // Calculate destination position (wraps from 11 to 0)
        const destPosition = currentPosition === FLAG_COUNT - 1 ? 0 : currentPosition + 1;
        const destStoneIndex = Math.round((destPosition / (FLAG_COUNT - 1)) * (totalStones - 1));

        if (currentPosition === FLAG_COUNT - 1) {
            // Wrap around: going from position 11 to position 0 (left side)
            // Animate right to left across entire display
            function animateWrapRight() {
                const stoneIndex = totalStones - 1 - animationStep;
                if (stoneIndex >= 0 && stones[stoneIndex]) {
                    stones[stoneIndex].classList.add('lit');
                    animationStep++;
                    stoneTrailAnimation = setTimeout(animateWrapRight, delayPerStone);
                }
            }
            animateWrapRight();
        } else {
            // Normal right movement - animate to destination stone
            function animateRight() {
                const stoneIndex = currentStoneIndex + animationStep;
                if (stoneIndex <= destStoneIndex && stoneIndex < totalStones && stones[stoneIndex]) {
                    stones[stoneIndex].classList.add('lit');
                    animationStep++;
                    stoneTrailAnimation = setTimeout(animateRight, delayPerStone);
                }
            }
            animateRight();
        }

    } else if (direction === 'center') {
        // Animate from current position toward center stone (slot 6)
        // Always ensure center stone gets lit at the end
        const goingLeft = currentStoneIndex > centerStoneIndex;

        function animateToCenter() {
            let stoneIndex;
            if (goingLeft) {
                stoneIndex = currentStoneIndex - animationStep;
                if (stoneIndex >= centerStoneIndex && stoneIndex >= 0 && stones[stoneIndex]) {
                    stones[stoneIndex].classList.add('lit');
                    animationStep++;
                    stoneTrailAnimation = setTimeout(animateToCenter, delayPerStone);
                }
            } else {
                stoneIndex = currentStoneIndex + animationStep;
                if (stoneIndex <= centerStoneIndex && stoneIndex < totalStones && stones[stoneIndex]) {
                    stones[stoneIndex].classList.add('lit');
                    animationStep++;
                    stoneTrailAnimation = setTimeout(animateToCenter, delayPerStone);
                }
            }
        }

        // If already at center, just light it immediately
        if (currentStoneIndex === centerStoneIndex) {
            if (stones[centerStoneIndex]) stones[centerStoneIndex].classList.add('lit');
        } else {
            animateToCenter();
        }
    }
}

function clearStoneTrailAnimation() {
    if (stoneTrailAnimation) {
        clearTimeout(stoneTrailAnimation);
        stoneTrailAnimation = null;
    }

    const stoneWave = document.querySelector('.stone-wave');
    if (!stoneWave) return;

    const stones = stoneWave.querySelectorAll('.wave-stone');
    const centerStone = stoneWave.querySelector('.center-stone');

    stones.forEach(stone => stone.classList.remove('lit'));
    if (centerStone) centerStone.classList.remove('lit');
}

// Attach hover listeners to movement buttons after UI updates
// Uses data attributes to prevent duplicate listeners and addEventListener for reliability
function attachStoneTrailListeners() {
    // Helper to attach listeners only if not already attached
    function attachIfNeeded(element, direction) {
        if (!element || element.dataset.stoneListenerAttached) return;

        // Create bound handlers for this element
        const enterHandler = () => triggerStoneTrailAnimation(direction);
        const leaveHandler = clearStoneTrailAnimation;

        element.addEventListener('mouseenter', enterHandler);
        element.addEventListener('mouseleave', leaveHandler);
        element.dataset.stoneListenerAttached = 'true';
    }

    // Left movement button
    document.querySelectorAll('button[onclick*="movePlayer(\'left\')"]').forEach(btn => {
        attachIfNeeded(btn, 'left');
    });

    // Right movement button
    document.querySelectorAll('button[onclick*="movePlayer(\'right\')"]').forEach(btn => {
        attachIfNeeded(btn, 'right');
    });

    // Tier up button - goes to center
    document.querySelectorAll('button[onclick*="upgradeRing"]').forEach(btn => {
        attachIfNeeded(btn, 'center');
    });

    // Portal travel cards - goes to center (but not "stay" option)
    document.querySelectorAll('.zone-portal-card').forEach(card => {
        // Skip "stay" option - it doesn't teleport you
        if (card.id === 'card_stay' || card.querySelector('.zone-stay-option')) {
            return;
        }
        attachIfNeeded(card, 'center');
    });
}

// Call after initial page load
document.addEventListener('DOMContentLoaded', attachStoneTrailListeners);