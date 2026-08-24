// Desktop UI display functions - CLIENT SIDE DISPLAY ONLY

// Recursive Tooltip Portal System - allows nested tooltips with locking
const TooltipPortal = (function() {
    const tooltips = new Map(); // id -> TooltipNode
    const rootTooltips = new Set(); // Top-level tooltips
    let nextId = 0;
    let MINION_DATA = {}; // Will be loaded from API

    const LOCK_DELAY = 3000; // 3 seconds to lock
    const CLOSE_DELAY = 500; // 0.5 seconds after leaving to close
    const MAX_DEPTH = 5; // Maximum nesting depth
    const BASE_Z_INDEX = 100000;

    // Load minion data for tooltips
    async function loadMinionData() {
        try {
            const response = await fetch('/api/dev/minion-info');
            const data = await response.json();
            if (data.success) {
                MINION_DATA = data.minions;
                console.log(`Loaded ${Object.keys(MINION_DATA).length} minions for tooltips`);
            }
        } catch (error) {
            console.warn('Failed to load minion data for tooltips:', error);
        }
    }

    // Load minion data on init
    loadMinionData();

    // Generate unique ID for tooltip
    function generateId(level) {
        return `tooltip-${level}-${Date.now()}-${nextId++}`;
    }

    // Calculate z-index based on depth
    function getZIndex(level) {
        return BASE_Z_INDEX + (level * 10);
    }

    // Generate minion card HTML for sub-tooltips using the actual game rendering function
    function generateMinionCardForTooltip(minion) {
        // Debug logging for sub-minion effects
        if (minion.name === 'Skeleton' || minion.name === 'Bone') {
            console.log(`[TOOLTIP] Generating card for ${minion.name}:`, {
                keywords: minion.keywords,
                has_death_toll_effect: !!minion.death_toll_effect,
                death_toll_effect: minion.death_toll_effect
            });
        }

        // Enrich minion with template data (same as combat rendering)
        const enriched = enrichCombatMinion(minion);

        // Debug enriched version
        if (enriched.name === 'Skeleton' || enriched.name === 'Bone') {
            console.log(`[TOOLTIP] After enrichment ${enriched.name}:`, {
                keywords: enriched.keywords,
                has_death_toll_effect: !!enriched.death_toll_effect,
                death_toll_effect: enriched.death_toll_effect
            });
        }

        // Use the same function that renders minions in combat/events
        // Pass showIndex=false since we don't need position numbers in tooltips
        return generateUnifiedMinionCard(enriched, {
            index: 0,
            showIndex: false,
            isClickable: false,
            isSelected: false,
            isDisabled: false,
            showAbandonButton: false,
            extraClasses: 'tooltip-minion-card'
        });
    }

    // Enrich tooltip content with sub-tooltip triggers (recursive)
    // `context` selects a context-specific description when a keyword defines
    // `descriptions: { minion, event }` — e.g., "Sacrifice" on a minion card means
    // "dies instead of other allies", but inside an event choice it means
    // "remove a minion from your band". Nested chains inherit the parent context.
    function enrichTooltipContent(text, currentDepth = 0, visitedTerms = new Set(), context = 'minion') {
        if (currentDepth >= MAX_DEPTH || !text) return text;

        let enriched = text;

        // Check if minion data is loaded
        const hasMinionData = Object.keys(MINION_DATA).length > 0;
        if (currentDepth === 0 && hasMinionData) {
            console.log('Enriching tooltip with minion data, found', Object.keys(MINION_DATA).length, 'minions');
        }

        // Enrich minion names (only if data is loaded)
        if (hasMinionData) {
            // Sort minion names by length (longest first) to prevent partial matches
            // e.g., "Dullahan's Head" should be matched before "Dullahan"
            const minionNames = Object.keys(MINION_DATA).sort((a, b) => b.length - a.length);
            minionNames.forEach(minionName => {
                const minion = MINION_DATA[minionName];
                // Escape special regex characters in minion name
                const escapedName = minionName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                // Use regex that won't match inside HTML tags or attributes
                const regex = new RegExp(`(?<![<"])\\b${escapedName}\\b(?![^<]*>)`, 'g');

                enriched = enriched.replace(regex, (match, offset, string) => {
                    // Avoid circular references
                    if (visitedTerms.has(minionName)) {
                        return `<span class="minion-plain" style="color: #FFD700">${match}</span>`;
                    }

                    // Check if we're inside an HTML tag by looking backwards for < without closing >
                    const beforeMatch = string.substring(0, offset);
                    const lastOpenTag = beforeMatch.lastIndexOf('<');
                    const lastCloseTag = beforeMatch.lastIndexOf('>');
                    if (lastOpenTag > lastCloseTag) {
                        // We're inside a tag, don't enrich
                        return match;
                    }

                    // Check if we're inside a tooltiptext span - don't enrich content that's already a tooltip
                    const lastTooltipOpen = beforeMatch.lastIndexOf('<span class="tooltiptext"');
                    const lastTooltipClose = beforeMatch.lastIndexOf('</span>');
                    if (lastTooltipOpen > lastTooltipClose && lastTooltipOpen !== -1) {
                        // We're inside a tooltiptext span, don't enrich
                        return match;
                    }

                    // Check if we're inside a minion tooltip span - don't re-match parts of already-matched minion names
                    const lastMinionOpen = beforeMatch.lastIndexOf('<span class="minion-tooltip-trigger');
                    const lastSpanClose = beforeMatch.lastIndexOf('</span>');
                    if (lastMinionOpen > lastSpanClose && lastMinionOpen !== -1) {
                        // We're inside a minion tooltip span, don't enrich
                        return match;
                    }

                    // Generate the full minion card HTML (no recursive enrichment needed)
                    const minionCardHTML = generateMinionCardForTooltip(minion);

                    if (currentDepth === 0) {
                        console.log('Enriched minion:', minionName);
                    }

                    return `<span class="minion-tooltip-trigger tooltip"
                                 data-minion="${minionName}"
                                 data-depth="${currentDepth}"
                                 data-is-minion-card="true"
                                 style="color: #FFD700; cursor: help; border-bottom: 1px dotted #FFD700; font-weight: 500;">
                        ${match}
                        <span class="tooltiptext" style="display: none;" data-no-enrich="true">
                            ${minionCardHTML}
                        </span>
                    </span>`;
                });
            });
        }

        // Enrich each keyword - sort by name length (longest first) to prevent partial matches
        // e.g., "On Ally Leap" should be matched before "Leap"
        const keywordKeys = Object.keys(KEYWORDS).sort((a, b) =>
            KEYWORDS[b].name.length - KEYWORDS[a].name.length
        );
        keywordKeys.forEach(keywordKey => {
            const keyword = KEYWORDS[keywordKey];
            // Use a regex that won't match inside HTML tags or attributes
            // Match keyword name but not if preceded by < or " (inside tag/attribute)
            // The callback function does additional checks for being inside tags
            const regex = new RegExp(`(?<![<"])\\b${keyword.name}\\b`, 'gi');

            enriched = enriched.replace(regex, (match, offset, string) => {
                // Avoid circular references
                if (visitedTerms.has(keywordKey)) {
                    return `<span class="keyword-plain" style="color: ${keyword.color}">${match}</span>`;
                }

                // Check if we're inside an HTML tag by looking backwards for < without closing >
                const beforeMatch = string.substring(0, offset);
                const lastOpenTag = beforeMatch.lastIndexOf('<');
                const lastCloseTag = beforeMatch.lastIndexOf('>');
                if (lastOpenTag > lastCloseTag) {
                    // We're inside a tag, don't enrich
                    return match;
                }

                // Check if we're inside a tooltiptext span - don't enrich content that's already a tooltip
                const lastTooltipOpen = beforeMatch.lastIndexOf('<span class="tooltiptext"');
                const lastTooltipClose = beforeMatch.lastIndexOf('</span>');
                if (lastTooltipOpen > lastTooltipClose && lastTooltipOpen !== -1) {
                    // We're inside a tooltiptext span, don't enrich
                    return match;
                }

                // Check if we're inside an already-created keyword tooltip trigger
                // This prevents "Leap" from matching inside "On Ally Leap" after it's been wrapped
                const lastKeywordTriggerOpen = beforeMatch.lastIndexOf('<span class="keyword-tooltip-trigger');
                const lastSpanClose = beforeMatch.lastIndexOf('</span>');
                if (lastKeywordTriggerOpen > lastSpanClose && lastKeywordTriggerOpen !== -1) {
                    // We're inside a keyword tooltip trigger (but not in its tooltiptext), don't enrich
                    return match;
                }

                // Special handling for "left" keyword - don't match when used as a direction
                // e.g., "left ally", "left side", "left neighbor" should NOT link to Ethereal [Left]
                if (keywordKey === 'left') {
                    const afterMatch = string.substring(offset + match.length);
                    // Check if "left" is followed by directional context words
                    const directionalPattern = /^\s+(ally|allies|neighbor|neighbors|side|of|minion|minions)/i;
                    if (directionalPattern.test(afterMatch)) {
                        // This is directional "left", not the Ethereal condition keyword
                        return match;
                    }
                }

                // Pick the context-specific description if the keyword provides one.
                // Nested tooltips inherit the parent context, so a sacrifice mention
                // inside an event keeps event-flavor all the way down the chain.
                const resolvedDescription =
                    (keyword.descriptions && keyword.descriptions[context]) ||
                    keyword.description;

                // Recursively enrich the nested description
                const nestedVisited = new Set([...visitedTerms, keywordKey]);
                const nestedContent = enrichTooltipContent(
                    resolvedDescription,
                    currentDepth + 1,
                    nestedVisited,
                    context
                );

                return `<span class="keyword-tooltip-trigger tooltip"
                             data-keyword="${keywordKey}"
                             data-depth="${currentDepth}"
                             data-context="${context}"
                             style="color: ${keyword.color}; cursor: help; border-bottom: 1px dotted ${keyword.color};">
                    ${match}
                    <span class="tooltiptext" style="display: none;">
                        <strong>${keyword.name}:</strong> ${nestedContent}
                    </span>
                </span>`;
            });
        });

        return enriched;
    }

    // Calculate tooltip position
    function calculatePosition(triggerRect, parentNode, level, triggerElement = null) {
        const TOOLTIP_OFFSET = 10;
        const VIEWPORT_MARGIN = 0;
        const ESTIMATED_WIDTH = 300;
        const ESTIMATED_HEIGHT = 100;

        let x, y, placement;

        // Check for explicit position preference via data attribute
        const preferredPosition = triggerElement?.dataset?.tooltipPosition;

        if (level === 0) {
            // Root level: check for preferred position, default to below trigger
            if (preferredPosition === 'top') {
                // Position above
                x = triggerRect.left;
                y = triggerRect.top - ESTIMATED_HEIGHT - TOOLTIP_OFFSET;
                placement = 'top';

                // Check if would overflow top, fall back to bottom
                if (y < VIEWPORT_MARGIN) {
                    y = triggerRect.bottom + TOOLTIP_OFFSET;
                    placement = 'bottom';
                }
            } else {
                // Default: below trigger
                x = triggerRect.left;
                y = triggerRect.bottom + TOOLTIP_OFFSET;
                placement = 'bottom';

                // Check if would overflow bottom
                if (y + ESTIMATED_HEIGHT > window.innerHeight - VIEWPORT_MARGIN) {
                    y = triggerRect.top - ESTIMATED_HEIGHT - TOOLTIP_OFFSET;
                    placement = 'top';
                }
            }

            // Check if would overflow right edge (for root tooltips)
            if (x + ESTIMATED_WIDTH > window.innerWidth - VIEWPORT_MARGIN) {
                x = window.innerWidth - ESTIMATED_WIDTH - VIEWPORT_MARGIN;
            }
        } else {
            // Nested levels: to the right of parent (or left if no room)
            const parentRect = parentNode.element.getBoundingClientRect();

            // Try right first
            x = parentRect.right + TOOLTIP_OFFSET;
            y = triggerRect.top;
            placement = 'right';

            // Check if would overflow right edge
            if (x + ESTIMATED_WIDTH > window.innerWidth - VIEWPORT_MARGIN) {
                // Try left instead
                x = parentRect.left - ESTIMATED_WIDTH - TOOLTIP_OFFSET;
                placement = 'left';

                // If still no room, force right (will be partially off-screen)
                if (x < VIEWPORT_MARGIN) {
                    x = parentRect.right + TOOLTIP_OFFSET;
                    placement = 'right-forced';
                }
            }

            // Keep in vertical bounds
            y = Math.max(
                VIEWPORT_MARGIN,
                Math.min(y, window.innerHeight - ESTIMATED_HEIGHT - VIEWPORT_MARGIN)
            );
        }

        return { x, y, placement };
    }

    // Close tooltip and all its children
    function closeTooltipAndChildren(node) {
        if (!node) return;

        // Store parent before closing
        const parent = node.parent;

        // Recursively close all children first
        node.children.forEach(child => {
            closeTooltipAndChildren(child);
        });

        // Clear timers
        if (node.lockTimer) clearTimeout(node.lockTimer);
        if (node.closeTimer) clearTimeout(node.closeTimer);
        if (node.unlockTimer) clearTimeout(node.unlockTimer);

        // Check if tooltip was ever locked (has golden border classes)
        const wasLocked = node.element.classList.contains('tooltip-locking') ||
                         node.element.classList.contains('tooltip-locked');

        // Remove locking class to start fade-out transition
        node.element.classList.remove('tooltip-locking');
        node.element.classList.remove('tooltip-locked');

        // Only wait for transition if tooltip was actually locked
        if (wasLocked) {
            // Wait for transition to complete before removing element
            setTimeout(() => {
                node.element.remove();
            }, 1500); // Match CSS transition duration
        } else {
            // Remove immediately if never locked
            node.element.remove();
        }

        // Remove from registry
        tooltips.delete(node.id);

        // Remove from parent's children or from root set
        if (parent) {
            parent.children.delete(node);

            // Check if parent should close now that this child is gone
            if (parent.children.size === 0 && !parent.element.matches(':hover')) {
                // Parent has no more children and is not being hovered - unlock and close
                parent.element.classList.remove('tooltip-locking');
                parent.element.classList.remove('tooltip-locked');
                parent.isLocked = false;

                parent.closeTimer = setTimeout(() => {
                    closeTooltipAndChildren(parent);
                }, CLOSE_DELAY);
            }
        } else {
            rootTooltips.delete(node);
        }
    }

    // Find tooltip node by its element
    function findNodeByElement(element) {
        if (!element || !element.dataset.tooltipId) return null;
        return tooltips.get(element.dataset.tooltipId);
    }

    // Show tooltip for a trigger element
    function showTooltip(triggerElement, parentNode = null) {
        const level = parentNode ? parentNode.level + 1 : 0;

        // Enforce max depth
        if (level >= MAX_DEPTH) {
            console.warn('Max tooltip depth reached');
            return null;
        }

        // Get tooltip content (new .map-tooltip or legacy .tooltiptext)
        const tooltipContent = triggerElement.querySelector('.tooltiptext') || triggerElement.querySelector('.map-tooltip');
        if (!tooltipContent) return null;

        // Check if this tooltip already exists for this trigger
        // (prevents duplicate tooltips)
        const existingId = triggerElement.dataset.activeTooltipId;
        if (existingId && tooltips.has(existingId)) {
            return tooltips.get(existingId);
        }

        const id = generateId(level);

        // Clone and enrich content
        const portal = document.createElement('div');
        portal.className = 'portal-tooltip';
        portal.classList.add(`tooltip-level-${level}`);
        portal.dataset.tooltipId = id;
        portal.style.position = 'fixed';
        portal.style.display = 'block';
        portal.style.visibility = 'visible';
        portal.style.opacity = '1';
        portal.style.zIndex = getZIndex(level);
        portal.style.pointerEvents = 'auto'; // Always interactive so hover can lock

        // Inherit --flag-accent from trigger's ring-flag parent (for map tooltips)
        const ringFlag = triggerElement.closest('.ring-flag') || triggerElement;
        const flagAccent = getComputedStyle(ringFlag).getPropertyValue('--flag-accent').trim();
        if (flagAccent) {
            portal.style.setProperty('--flag-accent', flagAccent);
        }

        // Enrich content with sub-tooltips (unless marked as pre-rendered)
        const originalHTML = tooltipContent.innerHTML;
        let enrichedHTML;

        // Check if this tooltip content should skip enrichment (e.g., pre-rendered minion cards)
        if (tooltipContent.dataset.noEnrich === 'true') {
            enrichedHTML = originalHTML;
            // Mark as minion card tooltip to remove extra box styling
            portal.classList.add('minion-card-tooltip');
        } else {
            // Determine the semantic context. For a root tooltip (level 0) we climb
            // from the trigger element to the nearest surface that declared a context
            // (event cards, ring flags, effect tags, etc). For nested tooltips we
            // inherit the parent keyword's already-tagged context so chains stay
            // consistent with the surface that opened them.
            let resolvedContext = 'minion';
            if (level === 0) {
                const ctxHost = triggerElement.closest('[data-tooltip-context]');
                if (ctxHost && ctxHost.dataset.tooltipContext) {
                    resolvedContext = ctxHost.dataset.tooltipContext;
                }
            } else if (triggerElement.dataset.context) {
                resolvedContext = triggerElement.dataset.context;
            }

            const visitedTerms = new Set();
            enrichedHTML = enrichTooltipContent(originalHTML, level, visitedTerms, resolvedContext);
            portal.dataset.context = resolvedContext;
        }

        portal.innerHTML = enrichedHTML;

        // Position tooltip
        const triggerRect = triggerElement.getBoundingClientRect();
        const position = calculatePosition(triggerRect, parentNode, level, triggerElement);
        portal.style.left = position.x + 'px';
        portal.style.top = position.y + 'px';
        portal.dataset.placement = position.placement;

        document.body.appendChild(portal);

        // Start visual transition to locked state immediately (before lock timer)
        // Use requestAnimationFrame to ensure the initial state is rendered first
        requestAnimationFrame(() => {
            portal.classList.add('tooltip-locking');
        });

        // Create node
        const node = {
            id: id,
            element: portal,
            parent: parentNode,
            children: new Set(),
            level: level,
            triggerElement: triggerElement,
            lockTimer: null,
            closeTimer: null,
            unlockTimer: null,
            isLocked: false
        };

        // Start lock timer
        node.lockTimer = setTimeout(() => {
            node.isLocked = true;
            portal.classList.add('tooltip-locked');
            portal.style.pointerEvents = 'auto'; // Allow interaction when locked
        }, LOCK_DELAY);

        // Register tooltip
        tooltips.set(id, node);
        if (parentNode) {
            parentNode.children.add(node);

            // Ensure parent is locked when showing children
            if (!parentNode.isLocked) {
                clearTimeout(parentNode.lockTimer);
                parentNode.isLocked = true;
                parentNode.element.classList.add('tooltip-locked');
                parentNode.element.style.pointerEvents = 'auto';
            }

            // Cancel any close timer on parent
            if (parentNode.closeTimer) {
                clearTimeout(parentNode.closeTimer);
                parentNode.closeTimer = null;
            }
        } else {
            rootTooltips.add(node);
        }

        // Track active tooltip on trigger
        triggerElement.dataset.activeTooltipId = id;

        // Add event listeners to portal
        portal.addEventListener('mouseenter', () => {
            // Cancel all timers
            if (node.unlockTimer) clearTimeout(node.unlockTimer);
            if (node.closeTimer) clearTimeout(node.closeTimer);
            if (node.lockTimer) clearTimeout(node.lockTimer);
            node.unlockTimer = null;
            node.closeTimer = null;
            node.lockTimer = null;

            // Immediately lock on hover - disable transition for instant effect
            portal.style.transition = 'none';
            node.isLocked = true;
            portal.classList.add('tooltip-locking');
            portal.classList.add('tooltip-locked');
            portal.style.pointerEvents = 'auto';

            // Re-enable transition after a frame
            requestAnimationFrame(() => {
                portal.style.transition = '';
            });
        });

        portal.addEventListener('mouseleave', (e) => {
            const relatedTarget = e.relatedTarget;

            // Check if moving to a child tooltip
            const movingToChild = relatedTarget &&
                Array.from(node.children).some(child =>
                    child.element.contains(relatedTarget) || child.element === relatedTarget
                );

            if (!movingToChild && node.children.size === 0) {
                // Immediately start unlocking - remove golden border
                portal.classList.remove('tooltip-locking');
                portal.classList.remove('tooltip-locked');
                node.isLocked = false;

                // Start close timer after transition
                node.closeTimer = setTimeout(() => {
                    closeTooltipAndChildren(node);
                }, CLOSE_DELAY);
            }
        });

        return node;
    }

    // Public cleanup function
    function cleanup() {
        // Close all root tooltips (which will cascade to children)
        rootTooltips.forEach(root => {
            closeTooltipAndChildren(root);
        });

        // Safety net: remove any orphaned tooltips
        const orphanedTooltips = document.querySelectorAll('.portal-tooltip');
        orphanedTooltips.forEach(tooltip => tooltip.remove());

        tooltips.clear();
        rootTooltips.clear();
    }

    // Global event delegation for showing tooltips
    document.addEventListener('mouseover', function(e) {
        const tooltip = e.target.closest('.tooltip');
        if (!tooltip) return;

        // If tooltip already has an active tooltip, immediately lock it
        const tooltipId = tooltip.dataset.activeTooltipId;
        if (tooltipId) {
            const node = tooltips.get(tooltipId);
            if (node) {
                // Cancel all timers
                if (node.unlockTimer) clearTimeout(node.unlockTimer);
                if (node.closeTimer) clearTimeout(node.closeTimer);
                if (node.lockTimer) clearTimeout(node.lockTimer);
                node.unlockTimer = null;
                node.closeTimer = null;
                node.lockTimer = null;

                // Immediately lock on hover - disable transition for instant effect
                node.element.style.transition = 'none';
                node.isLocked = true;
                node.element.classList.add('tooltip-locking');
                node.element.classList.add('tooltip-locked');
                node.element.style.pointerEvents = 'auto';

                // Re-enable transition after a frame
                requestAnimationFrame(() => {
                    node.element.style.transition = '';
                });
            }
        }

        // Check if we're inside a portal tooltip (nested case)
        const parentPortal = tooltip.closest('.portal-tooltip');
        const parentNode = parentPortal ? findNodeByElement(parentPortal) : null;

        // Don't create tooltip for root-level tooltips inside portals
        if (!parentPortal && tooltip.closest('.portal-tooltip')) {
            return;
        }

        // Only show if parent is locked (for nested tooltips) or if root level
        if (parentNode && !parentNode.isLocked) {
            return;
        }

        showTooltip(tooltip, parentNode);
    });

    document.addEventListener('mouseout', function(e) {
        const tooltip = e.target.closest('.tooltip');
        if (!tooltip) return;

        const tooltipId = tooltip.dataset.activeTooltipId;
        if (!tooltipId) return;

        const node = tooltips.get(tooltipId);
        if (!node) return;

        const relatedTarget = e.relatedTarget;

        // Check if moving to the portal itself
        const movingToPortal = relatedTarget &&
            (relatedTarget === node.element || node.element.contains(relatedTarget));

        // Check if moving to a child
        const movingToChild = relatedTarget &&
            Array.from(node.children).some(child =>
                child.element.contains(relatedTarget) || child.element === relatedTarget
            );

        if (!movingToPortal && !movingToChild) {
            // Immediately start unlocking
            node.element.classList.remove('tooltip-locking');
            node.element.classList.remove('tooltip-locked');
            node.isLocked = false;

            // Start close timer
            node.closeTimer = setTimeout(() => {
                closeTooltipAndChildren(node);
                delete tooltip.dataset.activeTooltipId;
            }, CLOSE_DELAY);
        }
    });

    // Close all tooltips on scroll (positions become invalid)
    window.addEventListener('scroll', () => {
        cleanup();
    }, { passive: true });

    // Expose public API
    return {
        cleanup: cleanup,
        getMinionData: () => MINION_DATA
    };
})();


