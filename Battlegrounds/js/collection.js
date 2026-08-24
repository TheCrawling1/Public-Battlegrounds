// Collection (Codex) System
// Displays all minions, NPC bands, and events in the game

let collectionData = {
    minions: [],
    bands: [],
    events: [],
    images: [],
    loaded: false
};

// Global storage for equipped image variants (minion_id -> image_path)
// Used by Images tab equipping functionality. Minion card rendering uses
// server-provided image_path via getMinionImagePath()/getMinionImageStyle() from game-core.js
let equippedImagePaths = {};
window.equippedImagesLoaded = false;

// Load equipped image paths on startup (for Images tab functionality)
async function loadEquippedImages() {
    if (window.equippedImagesLoaded) return;

    try {
        const imagesData = await apiCall('/collection/images');
        if (imagesData.success) {
            equippedImagePaths = {};
            (imagesData.images || []).forEach(img => {
                if (img.is_equipped && img.image_path) {
                    equippedImagePaths[img.minion_id] = img.image_path;
                }
            });
            window.equippedImagesLoaded = true;
            console.log('[COLLECTION] Loaded equipped images on startup:', Object.keys(equippedImagePaths).length);
        }
    } catch (error) {
        console.error('[COLLECTION] Failed to load equipped images:', error);
    }
}

// Auto-load equipped images when script loads
loadEquippedImages();

let collectionView = 'minions'; // Current tab: 'minions', 'bands', 'events', 'images'
let collectionFilters = {
    minions: { sort: 'tier', search: '' },
    bands: { sort: 'tier', search: '' },
    events: { sort: 'name', search: '' },
    images: { sort: 'tier', search: '' }
};

// Parse search text for filter tags like "Type=Beast" "Tier=1"
// Supports multiple tags of the same type (e.g. "Type=Beast Type=Cult")
function parseSearchTags(searchText) {
    const tags = {};
    let remainingText = searchText;

    // Match patterns like Tier=1, Type=Beast, Keyword=guard, Zone=human_kingdom, etc.
    const tagPattern = /(\w+)=(\S+)/gi;
    let match;

    while ((match = tagPattern.exec(searchText)) !== null) {
        const key = match[1].toLowerCase();
        const value = match[2];
        // Support multiple values for the same key
        if (!tags[key]) {
            tags[key] = [];
        }
        tags[key].push(value);
        remainingText = remainingText.replace(match[0], '');
    }

    // Clean up remaining text (the actual search query)
    remainingText = remainingText.trim().replace(/\s+/g, ' ');

    return { tags, searchQuery: remainingText };
}

// Check if a value matches any of the tag values (case-insensitive)
function matchesTagValue(tagValues, actualValue) {
    if (!tagValues || tagValues.length === 0) return true;
    const lowerActual = String(actualValue).toLowerCase();
    return tagValues.some(tv => tv.toLowerCase() === lowerActual);
}

// Check if a value matches any of the tag values as a number
function matchesTagNumber(tagValues, actualValue) {
    if (!tagValues || tagValues.length === 0) return true;
    return tagValues.some(tv => parseInt(tv) === actualValue);
}

// Add a tag to the search bar (appends, doesn't replace)
function addSearchTag(view, tagKey, tagValue) {
    if (tagValue === 'all' || tagValue === '') return;

    const filters = collectionFilters[view];
    const tag = `${tagKey}=${tagValue}`;

    // Just append the tag to the search
    filters.search = (filters.search + ' ' + tag).trim();
    renderCollection();
}

// Load all collection data
async function loadCollectionData() {
    if (collectionData.loaded) {
        console.log('[COLLECTION] Data already loaded');
        return true;
    }

    try {
        console.log('[COLLECTION] Loading collection data...');

        // Load minions using apiCall helper
        const minionsData = await apiCall('/collection/minions');
        if (minionsData.success) {
            collectionData.minions = minionsData.minions || [];
            console.log(`[COLLECTION] Loaded ${collectionData.minions.length} minions`);
        }

        // Load NPC bands
        const bandsData = await apiCall('/collection/npc-bands');
        if (bandsData.success) {
            collectionData.bands = bandsData.bands || [];
            console.log(`[COLLECTION] Loaded ${collectionData.bands.length} NPC bands`);
        }

        // Load events
        const eventsData = await apiCall('/collection/events');
        if (eventsData.success) {
            collectionData.events = eventsData.events || [];
            console.log(`[COLLECTION] Loaded ${collectionData.events.length} events`);
        }

        // Load images
        const imagesData = await apiCall('/collection/images');
        if (imagesData.success) {
            collectionData.images = imagesData.images || [];
            console.log(`[COLLECTION] Loaded ${collectionData.images.length} image entries`);

            // Build equipped image paths map for use by other UI components
            equippedImagePaths = {};
            collectionData.images.forEach(img => {
                if (img.is_equipped && img.image_path) {
                    equippedImagePaths[img.minion_id] = img.image_path;
                }
            });
            console.log(`[COLLECTION] Equipped images:`, Object.keys(equippedImagePaths).length);
        }

        collectionData.loaded = true;
        return true;

    } catch (error) {
        console.error('[COLLECTION] Failed to load collection data:', error);
        return false;
    }
}

// Show collection view
async function showCollection() {
    const gameContent = document.getElementById('gameContent');

    // Show loading state
    gameContent.innerHTML = generateCollectionLoading();

    // Load data if not already loaded
    const success = await loadCollectionData();

    if (!success) {
        gameContent.innerHTML = generateCollectionError();
        return;
    }

    // Render collection
    renderCollection();
}

// Generate loading screen
function generateCollectionLoading() {
    const bookIcon = typeof generateLucideSVG === 'function' ?
        generateLucideSVG('book-open', 60, 60) : '📚';

    return `
        <div class="collection-container">
            <div class="collection-header">
                <button class="back-button" onclick="showMainMenu()">
                    ${typeof generateLucideSVG === 'function' ? generateLucideSVG('arrow-left', 20, 20) : '←'} Back
                </button>
                <h1>${bookIcon} Collection</h1>
            </div>
            <div class="collection-loading">
                <div class="loading-spinner"></div>
                <p>Loading collection data...</p>
            </div>
        </div>
    `;
}

// Generate error screen
function generateCollectionError() {
    const alertIcon = typeof generateLucideSVG === 'function' ?
        generateLucideSVG('alert-circle', 60, 60) : '⚠️';

    return `
        <div class="collection-container">
            <div class="collection-header">
                <button class="back-button" onclick="showMainMenu()">
                    ${typeof generateLucideSVG === 'function' ? generateLucideSVG('arrow-left', 20, 20) : '←'} Back
                </button>
                <h1>Collection</h1>
            </div>
            <div class="collection-error">
                ${alertIcon}
                <h2>Failed to Load Collection</h2>
                <p>Unable to load collection data from the server.</p>
                <button class="btn btn-primary" onclick="showCollection()">Retry</button>
            </div>
        </div>
    `;
}

// Render main collection view
function renderCollection() {
    const gameContent = document.getElementById('gameContent');
    const bookIcon = typeof generateLucideSVG === 'function' ?
        generateLucideSVG('book-open', 24, 24) : '📚';

    gameContent.innerHTML = `
        <div class="collection-container">
            <div class="collection-header">
                <button class="back-button" onclick="showMainMenu()">
                    ${typeof generateLucideSVG === 'function' ? generateLucideSVG('arrow-left', 20, 20) : '←'} Back
                </button>
                <h1>${bookIcon} Collection</h1>
                <div class="collection-stats">
                    <span>${collectionData.minions.length} Minions</span>
                    <span>${collectionData.bands.length} Bands</span>
                    <span>${collectionData.events.length} Events</span>
                    <span>${collectionData.images.length} Images</span>
                </div>
            </div>

            <div class="collection-tabs">
                <button class="tab-button ${collectionView === 'minions' ? 'active' : ''}"
                        onclick="switchCollectionTab('minions')">
                    ${typeof generateLucideSVG === 'function' ? generateLucideSVG('users', 20, 20) : '👥'}
                    Minions (${collectionData.minions.length})
                </button>
                <button class="tab-button ${collectionView === 'bands' ? 'active' : ''}"
                        onclick="switchCollectionTab('bands')">
                    ${typeof generateLucideSVG === 'function' ? generateLucideSVG('shield', 20, 20) : '🛡️'}
                    NPC Bands (${collectionData.bands.length})
                </button>
                <button class="tab-button ${collectionView === 'events' ? 'active' : ''}"
                        onclick="switchCollectionTab('events')">
                    ${typeof generateLucideSVG === 'function' ? generateLucideSVG('zap', 20, 20) : '⚡'}
                    Events (${collectionData.events.length})
                </button>
                <button class="tab-button ${collectionView === 'images' ? 'active' : ''}"
                        onclick="switchCollectionTab('images')">
                    ${typeof generateLucideSVG === 'function' ? generateLucideSVG('image', 20, 20) : '🖼️'}
                    Images (${collectionData.images.length})
                </button>
            </div>

            <div class="collection-content">
                ${renderCollectionContent()}
            </div>
        </div>
    `;
}

// Switch between tabs
function switchCollectionTab(tab) {
    collectionView = tab;
    renderCollection();
}

// Render content based on current view
function renderCollectionContent() {
    switch (collectionView) {
        case 'minions':
            return renderMinionsView();
        case 'bands':
            return renderBandsView();
        case 'events':
            return renderEventsView();
        case 'images':
            return renderImagesView();
        default:
            return '<p>Unknown view</p>';
    }
}

// Render minions view
function renderMinionsView() {
    const filters = collectionFilters.minions;
    const { tags, searchQuery } = parseSearchTags(filters.search);

    // Get unique values for filters
    const tiers = [...new Set(collectionData.minions.map(m => m.tier))].sort((a, b) => a - b);
    const types = [...new Set(collectionData.minions.map(m => m.type).filter(t => t))].sort();
    const allKeywords = [...new Set(collectionData.minions.flatMap(m => m.keywords || []))].sort();

    // Filter minions using parsed tags (case-insensitive, supports multiple values)
    let filteredMinions = collectionData.minions.filter(minion => {
        if (!matchesTagNumber(tags.tier, minion.tier)) return false;
        if (!matchesTagValue(tags.type, minion.type)) return false;
        if (tags.keyword && tags.keyword.length > 0) {
            const hasKeyword = tags.keyword.some(kw =>
                minion.keywords?.some(mk => mk.toLowerCase() === kw.toLowerCase())
            );
            if (!hasKeyword) return false;
        }
        if (searchQuery && !minion.name.toLowerCase().includes(searchQuery.toLowerCase())) return false;
        return true;
    });

    // Sort minions
    filteredMinions.sort((a, b) => {
        switch (filters.sort) {
            case 'name':
                return a.name.localeCompare(b.name);
            case 'tier':
                return a.tier - b.tier || a.name.localeCompare(b.name);
            case 'health':
                return b.health - a.health || a.name.localeCompare(b.name);
            case 'attack':
                return b.attack - a.attack || a.name.localeCompare(b.name);
            default:
                return 0;
        }
    });

    return `
        <div class="filter-bar">
            <input type="text"
                   class="search-input"
                   placeholder="Search... (e.g. Type=Beast Tier=1)"
                   value="${filters.search}"
                   oninput="updateCollectionFilter('minions', 'search', this.value)">

            <select onchange="addSearchTag('minions', 'Tier', this.value); this.selectedIndex=0;">
                <option value="" selected disabled>+ Tier</option>
                <option value="all">Clear Tier</option>
                ${tiers.map(t => `<option value="${t}">Tier ${t}</option>`).join('')}
            </select>

            <select onchange="addSearchTag('minions', 'Type', this.value); this.selectedIndex=0;">
                <option value="" selected disabled>+ Type</option>
                <option value="all">Clear Type</option>
                ${types.map(t => `<option value="${t}">${t}</option>`).join('')}
            </select>

            <select onchange="addSearchTag('minions', 'Keyword', this.value); this.selectedIndex=0;">
                <option value="" selected disabled>+ Keyword</option>
                <option value="all">Clear Keyword</option>
                ${allKeywords.map(k => `<option value="${k}">${k}</option>`).join('')}
            </select>

            <select onchange="updateCollectionFilter('minions', 'sort', this.value)">
                <option value="tier" ${filters.sort === 'tier' ? 'selected' : ''}>Sort: Tier</option>
                <option value="name" ${filters.sort === 'name' ? 'selected' : ''}>Sort: Name</option>
                <option value="health" ${filters.sort === 'health' ? 'selected' : ''}>Sort: Health</option>
                <option value="attack" ${filters.sort === 'attack' ? 'selected' : ''}>Sort: Attack</option>
            </select>
        </div>

        <div class="collection-grid">
            ${filteredMinions.length > 0 ?
                filteredMinions.map(minion => generateCollectionMinionCard(minion)).join('') :
                '<p class="no-results">No minions match your filters</p>'
            }
        </div>

        <div class="collection-results-count">
            Showing ${filteredMinions.length} of ${collectionData.minions.length} minions
        </div>
    `;
}

// Generate minion card for collection - uses unified card from ui-display-desktop.js
// Collection cards: no index, no selection, custom click handler for details view
// Named differently to avoid collision with game's generateMinionCard
function generateCollectionMinionCard(minion) {
    // Enrich minion with template data for tooltips (effect fields, etc.)
    const enrichedMinion = typeof enrichCombatMinion === 'function'
        ? enrichCombatMinion(minion)
        : minion;

    // Use the unified card renderer with collection-specific options
    return generateUnifiedMinionCard(enrichedMinion, {
        showIndex: false,
        isClickable: true,
        showAbandonButton: false,  // Explicitly set to false for collection
        clickHandler: `onclick="showMinionDetails('${minion.id}')"`,
        dataAttributes: { 'minion-id': minion.id || '' }
    });
}

// Render bands view
function renderBandsView() {
    const filters = collectionFilters.bands;
    const { tags, searchQuery } = parseSearchTags(filters.search);

    // Get unique values
    const zones = [...new Set(collectionData.bands.map(b => b.zone))].sort();
    const tiers = [...new Set(collectionData.bands.map(b => b.tier))].sort((a, b) => a - b);

    // Filter bands using parsed tags (case-insensitive, supports multiple values)
    let filteredBands = collectionData.bands.filter(band => {
        if (!matchesTagValue(tags.zone, band.zone)) return false;
        if (!matchesTagNumber(tags.tier, band.tier)) return false;
        if (searchQuery && !band.name.toLowerCase().includes(searchQuery.toLowerCase())) return false;
        return true;
    });

    // Sort bands
    filteredBands.sort((a, b) => {
        switch (filters.sort) {
            case 'name':
                return a.name.localeCompare(b.name);
            case 'tier':
                return a.tier - b.tier || a.name.localeCompare(b.name);
            case 'zone':
                return a.zone.localeCompare(b.zone) || a.name.localeCompare(b.name);
            default:
                return 0;
        }
    });

    return `
        <div class="filter-bar">
            <input type="text"
                   class="search-input"
                   placeholder="Search... (e.g. Zone=forest Tier=2)"
                   value="${filters.search}"
                   oninput="updateCollectionFilter('bands', 'search', this.value)">

            <select onchange="addSearchTag('bands', 'Zone', this.value); this.selectedIndex=0;">
                <option value="" selected disabled>+ Zone</option>
                <option value="all">Clear Zone</option>
                ${zones.map(z => `<option value="${z}">${z.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</option>`).join('')}
            </select>

            <select onchange="addSearchTag('bands', 'Tier', this.value); this.selectedIndex=0;">
                <option value="" selected disabled>+ Tier</option>
                <option value="all">Clear Tier</option>
                ${tiers.map(t => `<option value="${t}">Tier ${t}</option>`).join('')}
            </select>

            <select onchange="updateCollectionFilter('bands', 'sort', this.value)">
                <option value="tier" ${filters.sort === 'tier' ? 'selected' : ''}>Sort: Tier</option>
                <option value="name" ${filters.sort === 'name' ? 'selected' : ''}>Sort: Name</option>
                <option value="zone" ${filters.sort === 'zone' ? 'selected' : ''}>Sort: Zone</option>
            </select>
        </div>

        <div class="collection-list">
            ${filteredBands.length > 0 ?
                filteredBands.map(band => generateBandCard(band)).join('') :
                '<p class="no-results">No bands match your filters</p>'
            }
        </div>

        <div class="collection-results-count">
            Showing ${filteredBands.length} of ${collectionData.bands.length} bands
        </div>
    `;
}

// Generate band card - displays minions as actual cards
function generateBandCard(band) {
    const zoneName = band.zone.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

    // Find full minion data and create minion cards
    const minionCards = band.minions.map(bandMinion => {
        // Look up full minion data from collection
        const fullMinion = collectionData.minions.find(m => m.name === bandMinion.name);

        if (!fullMinion) {
            // Fallback for minions not in collection
            return generateCollectionMinionCard({
                name: bandMinion.name,
                health: bandMinion.health,
                attack: bandMinion.attack,
                tier: band.tier,
                keywords: [],
                type: '',
                rarity: 'common',
                image: ''
            });
        }

        // Use full minion data but override stats if custom
        const minionData = {...fullMinion};
        if (bandMinion.custom) {
            minionData.health = bandMinion.health;
            minionData.attack = bandMinion.attack;
        }

        return generateCollectionMinionCard(minionData);
    }).join('');

    return `
        <div class="band-container">
            <div class="band-header">
                <h3 class="band-title">${band.name}</h3>
                <div class="band-meta">
                    <span class="band-tier-badge">Tier ${band.tier}</span>
                    <span class="band-zone-badge">${zoneName}</span>
                </div>
            </div>
            <div class="collection-grid">
                ${minionCards}
            </div>
        </div>
    `;
}

// Generate compact minion card for bands (smaller version with keywords and type)
function generateCompactMinionCard(minion, isCustom = false) {
    const keywords = (minion.keywords || []).slice(0, 2).map(k => {
        const keyword = KEYWORDS[k];
        return keyword ? `<span class="keyword-badge-small" style="background-color: ${keyword.color}20; color: ${keyword.color}">${keyword.name}</span>` : '';
    }).join('');

    const customBadge = isCustom ? '<span class="custom-badge">★</span>' : '';

    // Get minion image path - uses server-provided image_path
    const imagePath = typeof window.getMinionImagePath === 'function'
        ? window.getMinionImagePath(minion)
        : (minion.image_path || (minion.image ? `images/original/${minion.image}` : ''));

    return `
        <div class="minion-card-compact">
            ${imagePath ? `<div class="minion-compact-image">
                <img src="${imagePath}" alt="${minion.name}" onerror="this.style.display='none'">
            </div>` : ''}
            <div class="minion-compact-header">
                <span class="minion-compact-name">${minion.name}</span>
                <div class="minion-compact-badges">
                    <span class="minion-compact-tier">T${minion.tier}</span>
                    ${customBadge}
                </div>
            </div>
            ${minion.type ? `<div class="minion-compact-type">${minion.type}</div>` : ''}
            <div class="minion-compact-stats">
                <span class="stat-compact stat-health">
                    ${typeof generateLucideSVG === 'function' ? generateLucideSVG('heart', 12, 12) : '❤️'}
                    ${minion.health}
                </span>
                <span class="stat-compact stat-attack">
                    ${typeof generateLucideSVG === 'function' ? generateLucideSVG('sword', 12, 12) : '⚔️'}
                    ${minion.attack}
                </span>
            </div>
            ${keywords ? `<div class="minion-compact-keywords">${keywords}</div>` : ''}
        </div>
    `;
}

// Render events view
function renderEventsView() {
    const filters = collectionFilters.events;
    const { tags, searchQuery } = parseSearchTags(filters.search);

    // Get unique zones (kingdoms) from events
    const zones = [...new Set(collectionData.events.map(e => e.zone))].filter(z => z).sort();
    const visitRules = [...new Set(collectionData.events.map(e => e.visit_rule))].sort();

    // Filter events using parsed tags (case-insensitive, supports multiple values)
    let filteredEvents = collectionData.events.filter(event => {
        if (!matchesTagValue(tags.kingdom, event.zone)) return false;
        if (!matchesTagValue(tags.rule, event.visit_rule)) return false;
        if (searchQuery && !event.name.toLowerCase().includes(searchQuery.toLowerCase())) return false;
        return true;
    });

    // Sort events
    filteredEvents.sort((a, b) => {
        switch (filters.sort) {
            case 'name':
                return a.name.localeCompare(b.name);
            case 'zone':
                return (a.zone || '').localeCompare(b.zone || '') || a.name.localeCompare(b.name);
            default:
                return 0;
        }
    });

    return `
        <div class="filter-bar">
            <input type="text"
                   class="search-input"
                   placeholder="Search... (e.g. Kingdom=Fae Rule=always)"
                   value="${filters.search}"
                   oninput="updateCollectionFilter('events', 'search', this.value)">

            <select onchange="addSearchTag('events', 'Kingdom', this.value); this.selectedIndex=0;">
                <option value="" selected disabled>+ Kingdom</option>
                <option value="all">Clear Kingdom</option>
                ${zones.map(z => `<option value="${z}">${z}</option>`).join('')}
            </select>

            <select onchange="addSearchTag('events', 'Rule', this.value); this.selectedIndex=0;">
                <option value="" selected disabled>+ Rule</option>
                <option value="all">Clear Rule</option>
                ${visitRules.map(vr => `<option value="${vr}">${vr.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</option>`).join('')}
            </select>

            <select onchange="updateCollectionFilter('events', 'sort', this.value)">
                <option value="name" ${filters.sort === 'name' ? 'selected' : ''}>Sort: Name</option>
                <option value="zone" ${filters.sort === 'zone' ? 'selected' : ''}>Sort: Kingdom</option>
            </select>
        </div>

        <div class="collection-list">
            ${filteredEvents.length > 0 ?
                filteredEvents.map(event => generateEventCard(event)).join('') :
                '<p class="no-results">No events match your filters</p>'
            }
        </div>

        <div class="collection-results-count">
            Showing ${filteredEvents.length} of ${collectionData.events.length} events
        </div>
    `;
}

// Generate event card - uses TooltipPortal system for full tooltip functionality
// TooltipPortal handles: locking, nesting, keyword enrichment, minion tooltips
function generateEventCard(event) {
    // Format category badge
    const categoryColors = {
        'basic': '#4facfe',
        'zone': '#4ade80'
    };
    const categoryColor = categoryColors[event.category] || '#6b7280';
    const categoryName = event.category === 'basic' ? 'Basic' : 'Zone Event';

    // Warning text (for events like The Great Work)
    const warningHtml = event.warning
        ? `<div class="event-warning">${event.warning}</div>`
        : '';

    // Format options using standard .tooltip + .tooltiptext structure
    // TooltipPortal will automatically handle hover, locking, and keyword enrichment
    const optionsHtml = event.options && event.options.length > 0
        ? `<div class="event-options-container">
            <div class="options-header">Choices:</div>
            <div class="event-choices">
                ${event.options.map(option => {
                    const hasCondition = option.condition;
                    const conditionClass = hasCondition ? 'has-condition' : '';
                    const tooltipText = option.tooltip || '';
                    return `
                        <div class="selection-card collection-choice ${conditionClass} tooltip" data-tooltip-position="top">
                            <div class="choice-name">${option.name}</div>
                            <span class="tooltiptext" style="display: none;">${tooltipText}</span>
                        </div>
                    `;
                }).join('')}
            </div>
        </div>`
        : '';

    // Scaling info (show for all events that have it)
    const scalingHtml = event.scaling
        ? `<div class="event-scaling-info">${event.scaling}</div>`
        : '';

    return `
        <div class="event-list-item">
            <div class="event-content">
                <div class="event-header">
                    <h3 class="event-title">${event.name}</h3>
                    <div class="event-meta">
                        <span class="event-category-badge" style="background: ${categoryColor}20; color: ${categoryColor}; border: 1px solid ${categoryColor}">${categoryName}</span>
                        <span class="event-zone-badge">${event.zone || 'All Zones'}</span>
                    </div>
                </div>
                <p class="event-description">${event.description || 'No description available.'}</p>
                ${warningHtml}
                ${scalingHtml}
                ${optionsHtml}
            </div>
        </div>
    `;
}

// Update filter and re-render
function updateCollectionFilter(view, filterKey, value) {
    collectionFilters[view][filterKey] = value;

    // If only search changed, just update the grid to preserve cursor position
    if (filterKey === 'search') {
        updateCollectionGrid();
    } else {
        renderCollection();
    }
}

// Update only the grid content (preserves filter bar and cursor position)
function updateCollectionGrid() {
    const gridContainer = document.querySelector('.collection-content .collection-grid, .collection-content .collection-list');
    const resultsCount = document.querySelector('.collection-results-count');

    if (!gridContainer) {
        // Fallback to full render if grid not found
        renderCollection();
        return;
    }

    const filters = collectionFilters[collectionView];
    const { tags, searchQuery } = parseSearchTags(filters.search);

    let filteredItems = [];
    let totalItems = 0;
    let itemType = 'items';

    switch (collectionView) {
        case 'minions':
            filteredItems = filterMinions(tags, searchQuery, filters.sort);
            totalItems = collectionData.minions.length;
            itemType = 'minions';
            gridContainer.innerHTML = filteredItems.length > 0
                ? filteredItems.map(m => generateCollectionMinionCard(m)).join('')
                : '<p class="no-results">No minions match your filters</p>';
            break;
        case 'bands':
            filteredItems = filterBands(tags, searchQuery, filters.sort);
            totalItems = collectionData.bands.length;
            itemType = 'bands';
            gridContainer.innerHTML = filteredItems.length > 0
                ? filteredItems.map(b => generateBandCard(b)).join('')
                : '<p class="no-results">No bands match your filters</p>';
            break;
        case 'events':
            filteredItems = filterEvents(tags, searchQuery, filters.sort);
            totalItems = collectionData.events.length;
            itemType = 'events';
            gridContainer.innerHTML = filteredItems.length > 0
                ? filteredItems.map(e => generateEventCard(e)).join('')
                : '<p class="no-results">No events match your filters</p>';
            break;
        case 'images':
            filteredItems = filterImages(tags, searchQuery, filters.sort);
            totalItems = collectionData.images.length;
            itemType = 'minions';
            gridContainer.innerHTML = filteredItems.length > 0
                ? filteredItems.map(img => generateImageCard(img)).join('')
                : '<p class="no-results">No images match your filters</p>';
            break;
    }

    if (resultsCount) {
        resultsCount.textContent = `Showing ${filteredItems.length} of ${totalItems} ${itemType}`;
    }
}

// Filter helper functions
function filterMinions(tags, searchQuery, sortBy) {
    let filtered = collectionData.minions.filter(minion => {
        if (!matchesTagNumber(tags.tier, minion.tier)) return false;
        if (!matchesTagValue(tags.type, minion.type)) return false;
        if (tags.keyword && tags.keyword.length > 0) {
            const hasKeyword = tags.keyword.some(kw =>
                minion.keywords?.some(mk => mk.toLowerCase() === kw.toLowerCase())
            );
            if (!hasKeyword) return false;
        }
        if (searchQuery && !minion.name.toLowerCase().includes(searchQuery.toLowerCase())) return false;
        return true;
    });

    filtered.sort((a, b) => {
        switch (sortBy) {
            case 'name': return a.name.localeCompare(b.name);
            case 'tier': return a.tier - b.tier || a.name.localeCompare(b.name);
            case 'health': return b.health - a.health || a.name.localeCompare(b.name);
            case 'attack': return b.attack - a.attack || a.name.localeCompare(b.name);
            default: return 0;
        }
    });

    return filtered;
}

function filterBands(tags, searchQuery, sortBy) {
    let filtered = collectionData.bands.filter(band => {
        if (!matchesTagValue(tags.zone, band.zone)) return false;
        if (!matchesTagNumber(tags.tier, band.tier)) return false;
        if (searchQuery && !band.name.toLowerCase().includes(searchQuery.toLowerCase())) return false;
        return true;
    });

    filtered.sort((a, b) => {
        switch (sortBy) {
            case 'name': return a.name.localeCompare(b.name);
            case 'tier': return a.tier - b.tier || a.name.localeCompare(b.name);
            case 'zone': return a.zone.localeCompare(b.zone) || a.name.localeCompare(b.name);
            default: return 0;
        }
    });

    return filtered;
}

function filterEvents(tags, searchQuery, sortBy) {
    let filtered = collectionData.events.filter(event => {
        if (!matchesTagValue(tags.kingdom, event.zone)) return false;
        if (!matchesTagValue(tags.rule, event.visit_rule)) return false;
        if (searchQuery && !event.name.toLowerCase().includes(searchQuery.toLowerCase())) return false;
        return true;
    });

    filtered.sort((a, b) => {
        switch (sortBy) {
            case 'name': return a.name.localeCompare(b.name);
            case 'zone': return (a.zone || '').localeCompare(b.zone || '') || a.name.localeCompare(b.name);
            default: return 0;
        }
    });

    return filtered;
}

function filterImages(tags, searchQuery, sortBy) {
    let filtered = collectionData.images.filter(img => {
        if (!matchesTagValue(tags.minion, img.minion_id)) return false;
        if (!matchesTagNumber(tags.tier, img.tier)) return false;
        if (!matchesTagValue(tags.type, img.type)) return false;
        if (!matchesTagValue(tags.variant, img.variant)) return false;
        if (searchQuery && !img.name.toLowerCase().includes(searchQuery.toLowerCase())) return false;
        return true;
    });

    const variantOrder = { 'original': 0, 'alt_1': 1, 'alt_2': 2, 'alt_3': 3 };
    filtered.sort((a, b) => {
        switch (sortBy) {
            case 'name':
                return a.name.localeCompare(b.name) ||
                       variantOrder[a.variant] - variantOrder[b.variant];
            case 'tier':
                return a.tier - b.tier ||
                       a.name.localeCompare(b.name) ||
                       variantOrder[a.variant] - variantOrder[b.variant];
            default: return 0;
        }
    });

    return filtered;
}

// Show minion details (modal)
function showMinionDetails(minionId) {
    const minion = collectionData.minions.find(m => m.id === minionId);
    if (!minion) return;

    // TODO: Implement detailed modal view
    console.log('Show minion details:', minion);
    alert(`${minion.name}\nTier ${minion.tier}\n${minion.health} HP / ${minion.attack} ATK\n\nDetailed view coming soon!`);
}

// Show band details (modal)
function showBandDetails(bandId) {
    const band = collectionData.bands.find(b => b.id === bandId);
    if (!band) return;

    console.log('Show band details:', band);
    alert(`${band.name}\nTier ${band.tier}\nZone: ${band.zone_name}\n\nDetailed view coming soon!`);
}

// Show event details (modal)
function showEventDetails(eventId) {
    const event = collectionData.events.find(e => e.id === eventId);
    if (!event) return;

    console.log('Show event details:', event);
    alert(`${event.name}\nType: ${event.type}\n\nDetailed view coming soon!`);
}

// Render images view - displays all image variants in a grid
function renderImagesView() {
    const filters = collectionFilters.images;
    const { tags, searchQuery } = parseSearchTags(filters.search);

    // Get unique values for filters
    const tiers = [...new Set(collectionData.images.map(m => m.tier))].sort((a, b) => a - b);
    const types = [...new Set(collectionData.images.map(m => m.type).filter(t => t))].sort();
    const variants = [...new Set(collectionData.images.map(m => m.variant))].sort();

    // Filter images using parsed tags (case-insensitive, supports multiple values)
    let filteredImages = collectionData.images.filter(img => {
        if (!matchesTagValue(tags.minion, img.minion_id)) return false;
        if (!matchesTagNumber(tags.tier, img.tier)) return false;
        if (!matchesTagValue(tags.type, img.type)) return false;
        if (!matchesTagValue(tags.variant, img.variant)) return false;
        if (searchQuery && !img.name.toLowerCase().includes(searchQuery.toLowerCase())) return false;
        return true;
    });

    // Sort images - keep variant order within same minion
    const variantOrder = { 'original': 0, 'alt_1': 1, 'alt_2': 2, 'alt_3': 3 };
    filteredImages.sort((a, b) => {
        switch (filters.sort) {
            case 'name':
                return a.name.localeCompare(b.name) ||
                       variantOrder[a.variant] - variantOrder[b.variant];
            case 'tier':
                return a.tier - b.tier ||
                       a.name.localeCompare(b.name) ||
                       variantOrder[a.variant] - variantOrder[b.variant];
            default:
                return 0;
        }
    });

    return `
        <div class="filter-bar">
            <input type="text"
                   class="search-input"
                   placeholder="Search... (e.g. Type=Beast Tier=1 Variant=alt_1)"
                   value="${filters.search}"
                   oninput="updateCollectionFilter('images', 'search', this.value)">

            <select onchange="addSearchTag('images', 'Tier', this.value); this.selectedIndex=0;">
                <option value="" selected disabled>+ Tier</option>
                <option value="all">Clear Tier</option>
                ${tiers.map(t => `<option value="${t}">Tier ${t}</option>`).join('')}
            </select>

            <select onchange="addSearchTag('images', 'Type', this.value); this.selectedIndex=0;">
                <option value="" selected disabled>+ Type</option>
                <option value="all">Clear Type</option>
                ${types.map(t => `<option value="${t}">${t}</option>`).join('')}
            </select>

            <select onchange="addSearchTag('images', 'Variant', this.value); this.selectedIndex=0;">
                <option value="" selected disabled>+ Variant</option>
                <option value="all">Clear Variant</option>
                ${variants.map(v => `<option value="${v}">${v.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}</option>`).join('')}
            </select>

            <select onchange="updateCollectionFilter('images', 'sort', this.value)">
                <option value="tier" ${filters.sort === 'tier' ? 'selected' : ''}>Sort: Tier</option>
                <option value="name" ${filters.sort === 'name' ? 'selected' : ''}>Sort: Name</option>
            </select>
        </div>

        <div class="collection-grid">
            ${filteredImages.length > 0 ?
                filteredImages.map(img => generateImageCard(img)).join('') :
                '<p class="no-results">No images match your filters</p>'
            }
        </div>

        <div class="collection-results-count">
            Showing ${filteredImages.length} of ${collectionData.images.length} images
        </div>
    `;
}

// Generate image card for collection - displays individual image variant
function generateImageCard(imageData) {
    const imagePath = imageData.image_path || '';
    const isEquipped = imageData.is_equipped;
    const isOwned = imageData.is_owned;
    const variantLabel = imageData.variant === 'original' ? '' : ` (${imageData.variant_label})`;

    // Add classes for equipped (gold border) and locked state
    const equippedClass = isEquipped ? 'image-equipped' : '';
    const lockedClass = !isOwned ? 'image-locked' : '';

    // Click handler - select this variant if owned, do nothing if locked
    const clickHandler = isOwned
        ? `onclick="equipImageVariant('${imageData.minion_id}', '${imageData.variant}')"`
        : '';  // No click handler for locked images

    return `
        <div class="image-card ${equippedClass} ${lockedClass}" ${clickHandler}
             style="background-image: url('${imagePath}')">
            <div class="image-card-name">${imageData.name}${variantLabel}</div>
            ${isEquipped ? '<div class="equipped-badge">Equipped</div>' : ''}
            ${!isOwned ? '<div class="locked-overlay"><span class="lock-icon">🔒</span></div>' : ''}
        </div>
    `;
}

// Equip an image variant for a minion
async function equipImageVariant(minionId, variant) {
    // Check if this variant is already equipped
    const currentImage = collectionData.images.find(img =>
        img.minion_id === minionId && img.is_equipped
    );
    if (currentImage && currentImage.variant === variant) {
        return; // Already equipped, do nothing
    }

    // Update local state and global equipped paths
    let newEquippedPath = null;
    collectionData.images.forEach(img => {
        if (img.minion_id === minionId) {
            img.is_equipped = (img.variant === variant);
            if (img.is_equipped && img.image_path) {
                newEquippedPath = img.image_path;
            }
        }
    });

    // Update global equipped paths map
    if (newEquippedPath) {
        equippedImagePaths[minionId] = newEquippedPath;

        // Also update image_path in collectionData.minions so tab switching shows correct images
        collectionData.minions.forEach(minion => {
            if (minion.image && minion.image.replace('.png', '') === minionId) {
                minion.image_path = newEquippedPath;
            }
        });
    }

    // Re-render to show selection (only update grid to preserve state)
    updateCollectionGrid();

    // Try to save selection to server (silently fail if not logged in)
    try {
        const response = await apiCall('/collection/images/equip', 'POST', {
            minion_id: minionId,
            variant: variant
        });
        // Silently ignore failures (e.g., not logged in)
    } catch (error) {
        // Silently ignore errors (user not logged in, network issues, etc.)
    }
}

// Show info for locked image variant
function showLockedImageInfo(minionId, variant) {
    const imageEntry = collectionData.images.find(img =>
        img.minion_id === minionId && img.variant === variant
    );
    if (!imageEntry) return;

    const variantLabel = variant.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
    alert(`${imageEntry.name} (${variantLabel})\n\nThis image variant is locked.\nAlt variants can be unlocked through gameplay.`);
}

// Navigate to Images tab filtered to a specific minion
function showMinionImages(minionId) {
    addSearchTag('images', 'Minion', minionId);
    collectionView = 'images';
    renderCollection();
}

// Export functions and variables
window.showCollection = showCollection;
window.switchCollectionTab = switchCollectionTab;
window.updateCollectionFilter = updateCollectionFilter;
window.addSearchTag = addSearchTag;
window.showMinionDetails = showMinionDetails;
window.showBandDetails = showBandDetails;
window.showEventDetails = showEventDetails;
window.equipImageVariant = equipImageVariant;
window.showLockedImageInfo = showLockedImageInfo;
window.showMinionImages = showMinionImages;
// Note: getMinionImagePath and getMinionImageStyle are exported from game-core.js
// These use server-provided image_path for correct equipped variant rendering
window.equippedImagePaths = equippedImagePaths;
window.loadEquippedImages = loadEquippedImages;
// Note: equippedImagesLoaded is accessed via window.equippedImagesLoaded in the reset code
