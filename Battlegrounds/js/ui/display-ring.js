// Ring progress bar display functions

function generateRingProgressBar(run, ringEvents, uiState = {}) {
    if (!ringEvents || ringEvents.length === 0) {
        return '<div class="ring-progress"><h3>Ring Progress Unavailable</h3></div>';
    }

    // All game logic should come from server via uiState
    const currentPosition = run.ring_position;
    const currentZone = gameData.current_zone || {};
    const portalPositions = uiState.portal_positions || {};
    const subRingProgress = uiState.sub_ring_progress || null;
    const isInSubRing = subRingProgress !== null;

    let ringHTML = '';

    // Sub-ring display (if server says we're in one)
    if (isInSubRing) {
        ringHTML += generateSubRingProgressBar(subRingProgress, run);
    }

    // Main ring display - just render what server provides
    const mapIcon = typeof getIconForEmoji === 'function' ? getIconForEmoji('🗺️', {width: 24, height: 24, cssClass: 'icon-inline'}) : '🗺️';
    const zoneFallbackIcon = typeof getIconForEmoji === 'function' ? getIconForEmoji('🌍', {width: 24, height: 24, cssClass: 'icon-inline'}) : '🌍';
    const subRingIcon = typeof getIconForEmoji === 'function' ? getIconForEmoji('⚡', {width: 24, height: 24, cssClass: 'icon-inline'}) : '⚡';

    // Generate stone wave HTML (Tavern Warmth style)
    // Use cosine with full cycles for mirror symmetry (left and right edges at same height)
    // cos(0) = 1, cos(6 * 2π) = cos(12π) = 1, so both edges at +amplitude
    const STONE_COUNT = 100;
    const FLAG_COUNT = 12;
    const waveAmplitude = 20;
    const waveCycles = 6; // Full cycles = mirrored edges

    // Helper to calculate wave Y offset for any progress (0-1)
    const getWaveY = (progress) => Math.cos(progress * waveCycles * 2 * Math.PI) * waveAmplitude;

    // Calculate which stone indices have flags
    // Flag i maps to stone index: Math.round((i / (FLAG_COUNT - 1)) * (STONE_COUNT - 1))
    const flagStoneIndices = [];
    for (let i = 0; i < FLAG_COUNT; i++) {
        const stoneIndex = Math.round((i / (FLAG_COUNT - 1)) * (STONE_COUNT - 1));
        flagStoneIndices.push(stoneIndex);
    }

    // Center stone index (slot 6, which is flag index 5)
    const centerStoneIndex = flagStoneIndices[5];

    // Generate all stone slots - each slot contains a stone and potentially a flag
    let stoneWaveHTML = '';
    for (let i = 0; i < STONE_COUNT; i++) {
        const progress = i / (STONE_COUNT - 1);
        const yOffset = getWaveY(progress);

        // Check if this stone has a flag
        const flagIndex = flagStoneIndices.indexOf(i);
        const hasFlag = flagIndex !== -1;

        // Determine stone type - all stones include wave-stone for animation queries
        let stoneClass = 'wave-stone';
        if (i === centerStoneIndex) {
            stoneClass = 'wave-stone center-stone';
        } else if (i === 0 || i === STONE_COUNT - 1) {
            stoneClass = 'wave-stone edge-stone';
        }

        // Generate slot HTML - transform moves both stone and flag together
        stoneWaveHTML += `<div class="stone-slot" style="transform: translateY(${yOffset}px)">`;

        // Add flag if this stone has one
        if (hasFlag) {
            const eventType = ringEvents[flagIndex];
            const eventData = uiState.event_display_data && uiState.event_display_data[flagIndex];

            // Check if general_event position has been visited (should show as blessing)
            const visitedGeneralEvents = uiState.visited_general_events || {};
            const isVisitedGeneralEvent = eventType === 'general_event' && visitedGeneralEvents[String(flagIndex)];
            const displayEventType = isVisitedGeneralEvent ? 'buff_event' : eventType;

            stoneWaveHTML += generateEventPositionHTML(displayEventType, flagIndex, currentPosition, isInSubRing, subRingProgress, portalPositions[flagIndex], eventData);
        }

        // Add the stone
        stoneWaveHTML += `<div class="${stoneClass}"></div>`;
        stoneWaveHTML += '</div>';
    }

    ringHTML += `
        <div class="ring-progress">
            <div class="ring-title"><span>Ring ${run.current_ring}</span> — ${currentZone.name || 'Unknown Zone'}</div>
            <div class="stone-wave">${stoneWaveHTML}</div>
        </div>
    `;

    return ringHTML;
}

function generateEventPositionHTML(eventType, index, currentPosition, isInSubRing, subRingProgress, portalData, eventData) {
    // Use server-provided event data if available, otherwise fallback to client icons
    let eventInfo, tooltipHTML;
    let flagClass = 'ring-flag tooltip ';

    const isPortal = !!portalData;
    const isSubRingEntry = isInSubRing && index === (subRingProgress?.entry_position);

    // Helper: generate a small inline map icon for tooltip headers
    const _ttIcon = (lucideName) => {
        if (typeof generateLucideSVG === 'function') {
            return generateLucideSVG(lucideName, 14, 14, 'currentColor', 'icon-map');
        }
        return '';
    };

    // Helper: build structured tooltip HTML
    const _buildTooltip = (title, desc, hint, headerIcon, extraHTML) => {
        return `<div class="map-tooltip">
            <div class="tt-header">
                <span class="tt-icon">${headerIcon || ''}</span>
                <span class="tt-title">${title}</span>
            </div>
            <div class="tt-body">
                <div class="tt-desc">${desc}</div>
                ${extraHTML || ''}
                ${hint ? `<div class="tt-hint">${hint}</div>` : ''}
            </div>
        </div>`;
    };

    if (eventData) {
        // Server provided complete display data — wrap in structured tooltip
        eventInfo = eventData.event_info;
        tooltipHTML = `<div class="map-tooltip">
            <div class="tt-header">
                <span class="tt-title">${eventInfo.name || ''}</span>
            </div>
            <div class="tt-body">
                <div class="tt-desc">${eventData.tooltip_content || ''}</div>
            </div>
        </div>`;
    } else {
        const unknownInfo = { mapIcon: '❓', icon: '❓', name: 'Unknown', desc: '', hint: '' };

        if (isPortal) {
            const portalInfo = EVENT_ICONS['zone_portal'] || unknownInfo;
            eventInfo = { icon: portalInfo.mapIcon, name: 'Portal' };
            flagClass += 'portal ';

            const destItems = portalData?.map(dest =>
                `<li>${dest.zone_data.icon} ${dest.zone_data.name}</li>`
            ).join('') || '';

            tooltipHTML = _buildTooltip('Zone Portal', portalInfo.desc,
                portalInfo.hint, _ttIcon(portalInfo.lucide || 'workflow'),
                destItems ? `<ul class="tt-options">${destItems}</ul>` : '');

        } else if (Array.isArray(eventType)) {
            // Split event
            const ev1 = EVENT_ICONS[eventType[0]] || unknownInfo;
            const ev2 = EVENT_ICONS[eventType[1]] || unknownInfo;

            eventInfo = {
                icon: ev1.mapIcon + ev2.mapIcon,
                name: ev1.name + ' / ' + ev2.name
            };
            flagClass += 'split ';

            const splitItems = `<ul class="tt-options">
                <li>${ev1.mapIcon} ${ev1.name}</li>
                <li>${ev2.mapIcon} ${ev2.name}</li>
            </ul>`;
            tooltipHTML = _buildTooltip('Split Choice',
                'Choose between two event paths.', 'Pick one',
                _ttIcon('rotate-cw'), splitItems);

        } else if (typeof eventType === 'object' && eventType.type === 'branching_choice') {
            const branchInfo = EVENT_ICONS['split_event'] || unknownInfo;
            eventInfo = { icon: branchInfo.mapIcon, name: 'Choice' };
            tooltipHTML = _buildTooltip(
                eventType.title || 'Branching Choice',
                eventType.description || 'Choose your path.', '',
                _ttIcon('rotate-cw'));
        } else {
            // Normal single event
            const info = EVENT_ICONS[eventType] || unknownInfo;
            eventInfo = { icon: info.mapIcon, name: info.name };
            tooltipHTML = _buildTooltip(info.name, info.desc || '',
                info.hint || '', _ttIcon(info.lucide || 'help-circle'));
        }
    }

    // Apply position-based classes
    if (isInSubRing) {
        if (isSubRingEntry) {
            flagClass += 'sub-ring-entry ';
        } else {
            flagClass += 'upcoming ';
        }
    } else if (index === currentPosition) {
        flagClass += 'current';
    } else if (index < currentPosition) {
        flagClass += 'completed';
    } else {
        flagClass += 'upcoming';
    }

    // Determine event type for CSS class (drives accent colors)
    let cssEventType;
    if (isPortal) {
        cssEventType = 'zone_portal';
    } else if (Array.isArray(eventType)) {
        cssEventType = 'split_event';
    } else if (typeof eventType === 'object' && eventType.type === 'branching_choice') {
        cssEventType = 'branching_choice';
    } else {
        cssEventType = eventType;
    }

    return `
        <div class="${flagClass}" data-event-type="${cssEventType}" data-tooltip-context="event">
            <div class="flag-pole">
                <div class="flag-banner">
                    <span class="event-icon">${eventInfo.icon}</span>
                </div>
            </div>
            <span class="flag-num">${index}</span>
            ${tooltipHTML}
        </div>
    `;
}

function generateSubRingProgressBar(subRingProgress, run) {
    if (!subRingProgress || !subRingProgress.events) {
        return '';
    }

    // Just display server-provided sub-ring data
    const currentPosition = run.sub_ring_position;
    const events = subRingProgress.events;
    const icon = subRingProgress.icon || '❓';
    const entryPosition = subRingProgress.entry_position || 0;
    const exitPosition = subRingProgress.exit_position || 0;

    return `
        <div class="sub-ring-progress" style="border-color: #FF4500; background: linear-gradient(135deg, rgba(255, 69, 0, 0.2), rgba(255, 69, 0, 0.1));">
            <h3 style="color: #FF4500;">
                ${icon} ${subRingProgress.name} - Sub-Ring (Position ${currentPosition + 1}/${events.length})
            </h3>
            <div class="sub-ring-info" style="text-align: center; margin-bottom: 10px; font-size: 0.9rem; opacity: 0.9;">
                ${subRingProgress.description}
                <br><span style="color: #FFD700;">Entry: Position ${entryPosition} | Exit: Position ${exitPosition}</span>
                <br><span style="color: #87CEEB;">Exit Left → Position ${entryPosition} | Exit Right → Position ${exitPosition}</span>
            </div>
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

                    const tooltipContent = `
                        Sub-Ring Position ${index + 1}: ${eventInfo.name}
                        ${index === currentPosition ? '<br>📍 Current Position' : ''}
                        ${index < currentPosition ? '<br>✅ Completed' : ''}
                        ${index === 0 ? '<br>⬅️ Move left here to exit backwards' : ''}
                        ${index === events.length - 1 ? '<br>➡️ Move right here to exit forwards' : ''}
                    `;

                    return `
                        <div class="${eventClass} tooltip" data-event-type="${eventType}" data-tooltip-context="event" style="border-color: #FF4500;">
                            <span class="position-number">${index}</span>
                            <span class="event-icon">${eventInfo.icon}</span>
                            <span class="event-name">${eventInfo.name}</span>
                            <span class="tooltiptext">${tooltipContent}</span>
                        </div>
                    `;
                }).join('')}
            </div>
        </div>
    `;
}

