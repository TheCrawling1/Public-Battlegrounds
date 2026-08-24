// Animation System - Frontend animation player with unified bundle support and template execution
// Handles all visual effects for combat commands with flexible control
// UPDATED: Now includes template animation system for building complex animations from primitives
// ENHANCED: Added jagged lightning bolt rendering for wizard spells and arrow objects for huntsman

// Global animation state
let animationSystem = {
    activeAnimations: new Map(), // Map of animation ID to animation state
    animationQueue: [],          // Queue of pending animations
    bundleQueue: [],             // Queue of pending bundles
    globalSpeed: 1.0,            // Global animation speed multiplier
    isPaused: false,             // Global pause state
    nextAnimationId: 1,          // Incrementing ID for animations
    nextBundleId: 1,            // Incrementing ID for bundles
    activeBundles: new Map(),    // Map of bundle ID to bundle state
    debug: false                 // Debug logging
};

// Animation states
const ANIMATION_STATES = {
    PENDING: 'pending',
    RUNNING: 'running',
    PAUSED: 'paused',
    COMPLETED: 'completed',
    CANCELLED: 'cancelled'
};

// Bundle states
const BUNDLE_STATES = {
    PENDING: 'pending',
    RUNNING: 'running',
    PAUSED: 'paused',
    COMPLETED: 'completed',
    CANCELLED: 'cancelled'
};

// Template primitive types
const TEMPLATE_PRIMITIVES = {
    // Existing primitives
    LINE: 'line',
    GLOW: 'glow',
    PARTICLE: 'particle',
    FLASH: 'flash',
    NUMBER: 'number',
    PULSE: 'pulse',
    FADE: 'fade',
    // New generic primitives
    PROJECTILE: 'projectile',   // Straight-line projectile
    ARC: 'arc',                 // Curved/arcing projectile
    EXPLOSION: 'explosion',     // Radial burst effect
    SLASH: 'slash',             // Arc/slash motion
    BEAM: 'beam',               // Sustained beam
    SHOCKWAVE: 'shockwave',     // Expanding ring
    SPRAY: 'spray',             // Multiple projectiles in spread
    CHAIN: 'chain'              // Effect that jumps between targets
};

// Template targeting types
const TEMPLATE_TARGETING = {
    SOURCE_CENTER: 'source_center',
    TARGET_CENTER: 'target_center',
    EACH_TARGET_CENTER: 'each_target_center',
    SCREEN_POSITION: 'screen_position',
    RELATIVE_TO_SOURCE: 'relative_to_source',
    RELATIVE_TO_TARGET: 'relative_to_target'
};

/**
 * Initialize the animation system
 */
function initializeAnimationSystem() {
    console.log('[ANIMATIONS] Animation system initialized with template support, lightning rendering, and arrow objects');

    // CSS styles are in animations.css file - no dynamic injection needed

    // Start the animation update loop
    startAnimationLoop();
}

/**
 * Start the animation update loop
 */
function startAnimationLoop() {
    function updateAnimations() {
        if (!animationSystem.isPaused) {
            updateActiveAnimations();
            updateActiveBundles();
            processAnimationQueue();
            processBundleQueue();
        }
        requestAnimationFrame(updateAnimations);
    }

    requestAnimationFrame(updateAnimations);
}

/**
 * Update all currently active animations
 */
function updateActiveAnimations() {
    const now = Date.now();
    const toRemove = [];

    animationSystem.activeAnimations.forEach((animation, id) => {
        if (animation.state === ANIMATION_STATES.RUNNING) {
            const elapsed = now - animation.startTime;
            const adjustedDuration = animation.duration / animationSystem.globalSpeed;

            if (elapsed >= adjustedDuration && animation.autoCleanup !== false) {
                completeAnimation(id);
                toRemove.push(id);
            }
        }
    });

    toRemove.forEach(id => {
        animationSystem.activeAnimations.delete(id);
    });
}

/**
 * Update all currently active bundles
 */
function updateActiveBundles() {
    const now = Date.now();
    const toRemove = [];

    animationSystem.activeBundles.forEach((bundle, id) => {
        if (bundle.state === BUNDLE_STATES.RUNNING) {
            const elapsed = now - bundle.startTime;
            const adjustedDuration = bundle.duration / animationSystem.globalSpeed;

            if (elapsed >= adjustedDuration) {
                completeBundle(id);
                toRemove.push(id);
            }
        }
    });

    toRemove.forEach(id => {
        animationSystem.activeBundles.delete(id);
    });
}

/**
 * Process pending animations in the queue
 */
function processAnimationQueue() {
    if (animationSystem.animationQueue.length === 0) {
        return;
    }

    const toStart = [];
    for (let i = 0; i < animationSystem.animationQueue.length; i++) {
        const queuedAnimation = animationSystem.animationQueue[i];
        if (queuedAnimation.parallel || animationSystem.activeAnimations.size === 0) {
            toStart.push(i);
        } else {
            break;
        }
    }

    for (let i = toStart.length - 1; i >= 0; i--) {
        const index = toStart[i];
        const queuedAnimation = animationSystem.animationQueue.splice(index, 1)[0];
        startAnimation(queuedAnimation);
    }
}

/**
 * Process pending bundles in the queue
 */
function processBundleQueue() {
    if (animationSystem.bundleQueue.length === 0) {
        return;
    }

    // Start bundles that can run (respecting dependencies)
    const toStart = [];
    for (let i = 0; i < animationSystem.bundleQueue.length; i++) {
        const queuedBundle = animationSystem.bundleQueue[i];
        if (animationSystem.activeBundles.size === 0 || queuedBundle.parallel) {
            toStart.push(i);
        } else {
            break;
        }
    }

    for (let i = toStart.length - 1; i >= 0; i--) {
        const index = toStart[i];
        const queuedBundle = animationSystem.bundleQueue.splice(index, 1)[0];
        startBundle(queuedBundle);
    }
}

/**
 * Play a bundle of animations
 * @param {string} bundleType - Type of bundle (e.g., 'wizard_spell_barrage')
 * @param {Array} commands - Array of commands in the bundle
 * @param {Object} bundleData - Bundle metadata
 * @returns {number} Bundle ID
 */
function playBundle(bundleType, commands, bundleData = {}) {
    if (!commands || commands.length === 0) {
        console.warn('[ANIMATIONS] No commands provided for bundle');
        return null;
    }

    const bundleId = animationSystem.nextBundleId++;

    const bundle = {
        id: bundleId,
        type: bundleType,
        commands: commands,
        data: bundleData,
        state: BUNDLE_STATES.PENDING,
        parallel: bundleData.parallel !== false,
        duration: bundleData.duration || 2000,
        startTime: null,
        cleanup: null
    };

    console.log(`[ANIMATIONS] Queuing bundle: ${bundleType} with ${commands.length} commands`);

    animationSystem.bundleQueue.push(bundle);
    return bundleId;
}

/**
 * Start a bundle immediately
 * @param {Object} bundleData - Bundle configuration
 */
async function startBundle(bundleData) {
    bundleData.state = BUNDLE_STATES.RUNNING;
    bundleData.startTime = Date.now();

    animationSystem.activeBundles.set(bundleData.id, bundleData);

    console.log(`[ANIMATIONS] Starting bundle: ${bundleData.type} (ID: ${bundleData.id})`);

    try {
        // Check for template data first
        const templateData = getTemplateDataFromBundle(bundleData);
        if (templateData) {
            console.log(`[ANIMATIONS] Using template for bundle: ${bundleData.type}`);
            await processTemplateBundle(bundleData, templateData);
        } else {
            // Fallback to hardcoded bundle processing
            console.log(`[ANIMATIONS] No template found, using legacy bundle processing for: ${bundleData.type}`);
            await processLegacyBundle(bundleData);
        }
    } catch (error) {
        console.error(`[ANIMATIONS] Error processing bundle ${bundleData.id}:`, error);
        completeBundle(bundleData.id);
    }
}

/**
 * NEW: Get template data from bundle metadata
 * @param {Object} bundleData - Bundle configuration
 * @returns {Object|null} Template data or null if not available
 */
function getTemplateDataFromBundle(bundleData) {
    // Check if any of the commands have template data
    for (const command of bundleData.commands) {
        if (command.template_data) {
            return command.template_data;
        }
    }

    // Check bundle metadata for template data
    if (bundleData.data && bundleData.data.template_data) {
        return bundleData.data.template_data;
    }

    return null;
}

/**
 * NEW: Process bundle using template system
 * @param {Object} bundleData - Bundle configuration
 * @param {Object} templateData - Template definition
 */
async function processTemplateBundle(bundleData, templateData) {
    console.log(`[ANIMATIONS] Processing template bundle: ${templateData.name}`);

    // Extract source and target information from commands
    const context = extractBundleContext(bundleData);

    // Execute template elements
    await executeTemplate(templateData, context);

    bundleData.cleanup = () => {
        console.log(`[ANIMATIONS] Template bundle ${templateData.name} completed`);
    };

    // Use template duration or bundle duration
    bundleData.duration = templateData.duration || bundleData.duration;
}

/**
 * NEW: Extract context information from bundle commands
 * @param {Object} bundleData - Bundle configuration
 * @returns {Object} Context information for template execution
 */
function extractBundleContext(bundleData) {
    const castCommand = bundleData.commands[0]; // First command should be cast
    const damageCommands = bundleData.commands.slice(1); // Rest should be damage

    // Collect all target IDs - handle both single target_id and AOE target_ids
    const targetIds = [];
    const targetNames = [];
    const damageAmounts = [];

    // First check if bundle-level data has target_ids or target_positions
    if (bundleData.data && bundleData.data.target_ids && bundleData.data.target_ids.length > 0) {
        targetIds.push(...bundleData.data.target_ids);
    } else if (bundleData.data && bundleData.data.target_positions && bundleData.data.target_positions.length > 0) {
        targetIds.push(...bundleData.data.target_positions);
    }

    // Also check the first command's bundle_animation for target info
    if (castCommand.bundle_animation && castCommand.bundle_animation.target_positions) {
        for (const tid of castCommand.bundle_animation.target_positions) {
            if (tid && !targetIds.includes(tid)) {
                targetIds.push(tid);
            }
        }
    }

    // Then collect from individual commands
    for (const cmd of damageCommands) {
        // Single target
        if (cmd.target_id && !targetIds.includes(cmd.target_id)) {
            targetIds.push(cmd.target_id);
            if (cmd.target_name) targetNames.push(cmd.target_name);
            if (cmd.amount) damageAmounts.push(cmd.amount);
        }
        // AOE targets (array)
        if (cmd.target_ids && Array.isArray(cmd.target_ids)) {
            for (const tid of cmd.target_ids) {
                if (tid && !targetIds.includes(tid)) {
                    targetIds.push(tid);
                }
            }
        }
    }

    console.log(`[ANIMATIONS] Extracted context: source=${castCommand.source_id}, targets=${targetIds.length}`);

    return {
        source_id: castCommand.source_id,
        source_name: castCommand.source_name,
        source_golden: castCommand.golden || false,
        target_ids: targetIds,
        target_names: targetNames,
        damage_amounts: damageAmounts
    };
}

/**
 * NEW: Execute a template with given context
 * @param {Object} template - Template definition
 * @param {Object} context - Execution context
 */
async function executeTemplate(template, context) {
    console.log(`[ANIMATIONS] Executing template: ${template.name}`);

    // Process each element in the template
    for (const element of template.elements) {
        setTimeout(() => {
            executeTemplateElement(element, context);
        }, element.timing.delay || 0);
    }
}

/**
 * NEW: Execute a single template element
 * @param {Object} element - Template element definition
 * @param {Object} context - Execution context
 */
function executeTemplateElement(element, context) {
    console.log(`[ANIMATIONS] Executing template element: ${element.id} (${element.primitive})`);

    switch (element.primitive) {
        case TEMPLATE_PRIMITIVES.GLOW:
            executeGlowPrimitive(element, context);
            break;

        case TEMPLATE_PRIMITIVES.LINE:
            executeLinePrimitive(element, context);
            break;

        case TEMPLATE_PRIMITIVES.FLASH:
            executeFlashPrimitive(element, context);
            break;

        case TEMPLATE_PRIMITIVES.PARTICLE:
            executeParticlePrimitive(element, context);
            break;

        case TEMPLATE_PRIMITIVES.PULSE:
            executePulsePrimitive(element, context);
            break;

        case TEMPLATE_PRIMITIVES.FADE:
            executeFadePrimitive(element, context);
            break;

        // New generic primitives
        case TEMPLATE_PRIMITIVES.PROJECTILE:
            executeProjectilePrimitive(element, context);
            break;

        case TEMPLATE_PRIMITIVES.ARC:
            executeArcPrimitive(element, context);
            break;

        case TEMPLATE_PRIMITIVES.EXPLOSION:
            executeExplosionPrimitive(element, context);
            break;

        case TEMPLATE_PRIMITIVES.SLASH:
            executeSlashPrimitive(element, context);
            break;

        case TEMPLATE_PRIMITIVES.BEAM:
            executeBeamPrimitive(element, context);
            break;

        case TEMPLATE_PRIMITIVES.SHOCKWAVE:
            executeShockwavePrimitive(element, context);
            break;

        case TEMPLATE_PRIMITIVES.SPRAY:
            executeSprayPrimitive(element, context);
            break;

        case TEMPLATE_PRIMITIVES.CHAIN:
            executeChainPrimitive(element, context);
            break;

        default:
            console.warn(`[ANIMATIONS] Unknown template primitive: ${element.primitive}`);
            break;
    }
}

/**
 * NEW: Execute glow primitive
 * @param {Object} element - Element definition
 * @param {Object} context - Execution context
 */
function executeGlowPrimitive(element, context) {
    const targetIds = resolveTemplateTargeting(element.target, context);

    targetIds.forEach(targetId => {
        const targetElement = getTargetElement(targetId);
        if (targetElement) {
            applyGlowEffect(targetElement, element.properties, element.timing.duration);
        }
    });
}

/**
 * ENHANCED: Execute line primitive with lightning bolt and arrow support
 * @param {Object} element - Element definition
 * @param {Object} context - Execution context
 */
function executeLinePrimitive(element, context) {
    const fromTargets = resolveTemplateTargeting(element.from, context);
    const toTargets = resolveTemplateTargeting(element.to, context);

    // Handle multi-target scenarios
    if (element.to === TEMPLATE_TARGETING.EACH_TARGET_CENTER) {
        // Create line from source to each target
        const sourceElement = getTargetElement(fromTargets[0]);
        if (sourceElement) {
            const sourceRect = sourceElement.getBoundingClientRect();
            const sourceX = sourceRect.left + sourceRect.width / 2;
            const sourceY = sourceRect.top + sourceRect.height / 2;

            toTargets.forEach((targetId, index) => {
                const targetElement = getTargetElement(targetId);
                if (targetElement) {
                    const targetRect = targetElement.getBoundingClientRect();
                    const targetX = targetRect.left + targetRect.width / 2;
                    const targetY = targetRect.top + targetRect.height / 2;

                    // Route to appropriate line creator based on style
                    createStyledLine(sourceX, sourceY, targetX, targetY, element.properties, index);
                }
            });
        }
    } else {
        // Simple point-to-point line
        if (fromTargets.length > 0 && toTargets.length > 0) {
            const sourceElement = getTargetElement(fromTargets[0]);
            const targetElement = getTargetElement(toTargets[0]);

            if (sourceElement && targetElement) {
                const sourceRect = sourceElement.getBoundingClientRect();
                const targetRect = targetElement.getBoundingClientRect();

                const sourceX = sourceRect.left + sourceRect.width / 2;
                const sourceY = sourceRect.top + sourceRect.height / 2;
                const targetX = targetRect.left + targetRect.width / 2;
                const targetY = targetRect.top + targetRect.height / 2;

                // Route to appropriate line creator based on style
                createStyledLine(sourceX, sourceY, targetX, targetY, element.properties, 0);
            }
        }
    }
}

/**
 * NEW: Create a styled line based on properties (lightning, arrow, or regular)
 * @param {number} fromX - Source X coordinate
 * @param {number} fromY - Source Y coordinate
 * @param {number} toX - Target X coordinate
 * @param {number} toY - Target Y coordinate
 * @param {Object} properties - Line properties
 * @param {number} index - Line index for identification
 */
function createStyledLine(fromX, fromY, toX, toY, properties, index) {
    const style = properties.style || 'line';

    switch (style) {
        case 'lightning':
            createLightningBolt(fromX, fromY, toX, toY, properties, index);
            break;
        case 'arrow':
            createArrow(fromX, fromY, toX, toY, properties, index);
            break;
        default:
            createTemplateLine(fromX, fromY, toX, toY, properties, index);
            break;
    }
}

/**
 * NEW: Create an arrow object that flies and embeds
 * @param {number} fromX - Source X coordinate
 * @param {number} fromY - Source Y coordinate
 * @param {number} toX - Target X coordinate
 * @param {number} toY - Target Y coordinate
 * @param {Object} properties - Arrow properties
 * @param {number} index - Arrow index for identification
 */
function createArrow(fromX, fromY, toX, toY, properties, index) {
    console.log(`[ANIMATIONS] Creating arrow ${index + 1}: ${fromX},${fromY} -> ${toX},${toY}`);

    // Calculate arrow parameters
    const deltaX = toX - fromX;
    const deltaY = toY - fromY;
    const distance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);
    const angle = Math.atan2(deltaY, deltaX) * (180 / Math.PI);

    // Create arrow container - rotate the entire arrow as one unit
    const arrowContainer = document.createElement('div');
    arrowContainer.className = 'arrow-container';
    arrowContainer.style.position = 'fixed';
    arrowContainer.style.left = fromX + 'px';
    arrowContainer.style.top = fromY + 'px';
    arrowContainer.style.display = 'flex';
    arrowContainer.style.alignItems = 'center';
    arrowContainer.style.transform = `rotate(${angle}deg)`;
    arrowContainer.style.transformOrigin = '0 50%';
    arrowContainer.style.pointerEvents = 'none';
    arrowContainer.style.zIndex = '10000';
    arrowContainer.style.opacity = '0';
    arrowContainer.style.transition = 'opacity 0.1s ease-in';

    // Create arrow head (triangle pointing RIGHT - forward) - all black
    const arrowHead = document.createElement('div');
    arrowHead.className = 'arrow-head';
    arrowHead.style.width = '0';
    arrowHead.style.height = '0';
    arrowHead.style.borderLeft = '15px solid #000';  // Points RIGHT (forward)
    arrowHead.style.borderTop = '10px solid transparent';
    arrowHead.style.borderBottom = '10px solid transparent';
    arrowHead.style.zIndex = '2';

    // Create arrow body/shaft - all black
    const arrowBody = document.createElement('div');
    arrowBody.className = 'arrow-body';
    arrowBody.style.width = '40px';
    arrowBody.style.height = '4px';
    arrowBody.style.backgroundColor = '#000';
    arrowBody.style.marginLeft = '-2px'; // Slight overlap with head
    arrowBody.style.zIndex = '1';

    // Create fletching (triangle pointing LEFT - backward) - all black
    const arrowFletching = document.createElement('div');
    arrowFletching.className = 'arrow-fletching';
    arrowFletching.style.width = '0';
    arrowFletching.style.height = '0';
    arrowFletching.style.borderRight = '10px solid #000'; // Points LEFT (backward)
    arrowFletching.style.borderTop = '8px solid transparent';
    arrowFletching.style.borderBottom = '8px solid transparent';
    arrowFletching.style.marginLeft = '-8px'; // Overlap with body

    // Assemble arrow in correct order (tip first: head → body → fletching)
    arrowContainer.appendChild(arrowHead);
    arrowContainer.appendChild(arrowBody);
    arrowContainer.appendChild(arrowFletching);
    document.body.appendChild(arrowContainer);

    // Animate arrow appearance
    requestAnimationFrame(() => {
        arrowContainer.style.opacity = '1';
    });

    // Calculate flight time based on travel speed
    const travelSpeed = properties.travel_speed || 'medium';
    const flightTime = travelSpeed === 'fast' ? 200 :
                      travelSpeed === 'slow' ? 400 : 300;

    // Animate arrow flight to target - only move position, keep rotation constant
    const animation = arrowContainer.animate([
        {
            left: fromX + 'px',
            top: fromY + 'px',
            transform: `rotate(${angle}deg)` // Maintain orientation
        },
        {
            left: toX + 'px',
            top: toY + 'px',
            transform: `rotate(${angle}deg)` // Maintain orientation
        }
    ], {
        duration: flightTime,
        easing: 'linear',
        fill: 'forwards'  // Keep arrow at final position
    });

    animation.onfinish = () => {
        // Handle embedding effect
        if (properties.embed_on_impact) {
            // Remove only the arrow head (tip) on impact
            if (arrowHead && arrowHead.parentNode) {
                arrowHead.style.transition = 'opacity 0.1s ease-out';
                arrowHead.style.opacity = '0';
                setTimeout(() => {
                    if (arrowHead.parentNode) {
                        arrowHead.parentNode.removeChild(arrowHead);
                        console.log(`[ANIMATIONS] Arrow ${index + 1} embedded - tip removed`);
                    }
                }, 100);
            }

            // Keep embedded arrow (body + fletching) for specified duration
            const embedDuration = properties.embed_duration || 500;
            setTimeout(() => {
                arrowContainer.style.transition = 'opacity 0.3s ease-out';
                arrowContainer.style.opacity = '0';
                setTimeout(() => {
                    if (arrowContainer.parentNode) {
                        arrowContainer.parentNode.removeChild(arrowContainer);
                        console.log(`[ANIMATIONS] Arrow ${index + 1} cleanup complete`);
                    }
                }, 300);
            }, embedDuration);
        } else {
            // Regular arrow cleanup without embedding
            setTimeout(() => {
                arrowContainer.style.transition = 'opacity 0.3s ease-out';
                arrowContainer.style.opacity = '0';
                setTimeout(() => {
                    if (arrowContainer.parentNode) {
                        arrowContainer.parentNode.removeChild(arrowContainer);
                    }
                }, 300);
            }, 200);
        }
    };

    console.log(`[ANIMATIONS] Arrow ${index + 1} created - flight time: ${flightTime}ms, embed duration: ${properties.embed_duration || 0}ms`);
}

/**
 * NEW: Execute flash primitive
 * @param {Object} element - Element definition
 * @param {Object} context - Execution context
 */
function executeFlashPrimitive(element, context) {
    const targetIds = resolveTemplateTargeting(element.target, context);

    targetIds.forEach(targetId => {
        const targetElement = getTargetElement(targetId);
        if (targetElement) {
            applyFlashEffect(targetElement, element.properties, element.timing.duration);
        }
    });
}

/**
 * NEW: Execute particle primitive
 * @param {Object} element - Element definition
 * @param {Object} context - Execution context
 */
function executeParticlePrimitive(element, context) {
    const targetIds = resolveTemplateTargeting(element.target, context);

    targetIds.forEach(targetId => {
        const targetElement = getTargetElement(targetId);
        if (targetElement) {
            applyParticleEffect(targetElement, element.properties, element.timing.duration);
        }
    });
}

/**
 * NEW: Execute pulse primitive
 * @param {Object} element - Element definition
 * @param {Object} context - Execution context
 */
function executePulsePrimitive(element, context) {
    const targetIds = resolveTemplateTargeting(element.target, context);

    targetIds.forEach(targetId => {
        const targetElement = getTargetElement(targetId);
        if (targetElement) {
            applyPulseEffect(targetElement, element.properties, element.timing.duration);
        }
    });
}

/**
 * NEW: Execute fade primitive
 * @param {Object} element - Element definition
 * @param {Object} context - Execution context
 */
function executeFadePrimitive(element, context) {
    const targetIds = resolveTemplateTargeting(element.target, context);

    targetIds.forEach(targetId => {
        const targetElement = getTargetElement(targetId);
        if (targetElement) {
            applyFadeEffect(targetElement, element.properties, element.timing.duration);
        }
    });
}

// ============================================================
// NEW GENERIC PRIMITIVES
// ============================================================

/**
 * Execute projectile primitive - straight line projectile from source to target
 * Properties: color, size, speed, trail, shape ('circle', 'diamond', 'arrow')
 */
function executeProjectilePrimitive(element, context) {
    const fromTargets = resolveTemplateTargeting(element.from || TEMPLATE_TARGETING.SOURCE_CENTER, context);
    const toTargets = resolveTemplateTargeting(element.to || TEMPLATE_TARGETING.TARGET_CENTER, context);

    if (fromTargets.length === 0 || toTargets.length === 0) return;

    const sourceElement = getTargetElement(fromTargets[0]);
    if (!sourceElement) return;

    const sourceRect = sourceElement.getBoundingClientRect();
    const sourceX = sourceRect.left + sourceRect.width / 2;
    const sourceY = sourceRect.top + sourceRect.height / 2;

    const props = element.properties || {};
    const duration = element.timing?.duration || 400;

    toTargets.forEach((targetId, index) => {
        const targetElement = getTargetElement(targetId);
        if (!targetElement) return;

        const targetRect = targetElement.getBoundingClientRect();
        const targetX = targetRect.left + targetRect.width / 2;
        const targetY = targetRect.top + targetRect.height / 2;

        createProjectile(sourceX, sourceY, targetX, targetY, props, duration, index);
    });
}

/**
 * Execute arc primitive - curved projectile from source to target
 * Properties: color, size, arcHeight, speed, trail
 */
function executeArcPrimitive(element, context) {
    const fromTargets = resolveTemplateTargeting(element.from || TEMPLATE_TARGETING.SOURCE_CENTER, context);
    const toTargets = resolveTemplateTargeting(element.to || TEMPLATE_TARGETING.TARGET_CENTER, context);

    if (fromTargets.length === 0 || toTargets.length === 0) return;

    const sourceElement = getTargetElement(fromTargets[0]);
    if (!sourceElement) return;

    const sourceRect = sourceElement.getBoundingClientRect();
    const sourceX = sourceRect.left + sourceRect.width / 2;
    const sourceY = sourceRect.top + sourceRect.height / 2;

    const props = element.properties || {};
    const duration = element.timing?.duration || 600;

    toTargets.forEach((targetId, index) => {
        const targetElement = getTargetElement(targetId);
        if (!targetElement) return;

        const targetRect = targetElement.getBoundingClientRect();
        const targetX = targetRect.left + targetRect.width / 2;
        const targetY = targetRect.top + targetRect.height / 2;

        createArcProjectile(sourceX, sourceY, targetX, targetY, props, duration, index);
    });
}

/**
 * Execute explosion primitive - radial burst at target location
 * Properties: color, size, particleCount, speed, fadeOut
 */
function executeExplosionPrimitive(element, context) {
    const targetIds = resolveTemplateTargeting(element.target || TEMPLATE_TARGETING.TARGET_CENTER, context);

    const props = element.properties || {};
    const duration = element.timing?.duration || 500;

    targetIds.forEach((targetId, index) => {
        const targetElement = getTargetElement(targetId);
        if (!targetElement) return;

        const rect = targetElement.getBoundingClientRect();
        const x = rect.left + rect.width / 2;
        const y = rect.top + rect.height / 2;

        createExplosion(x, y, props, duration, index);
    });
}

/**
 * Execute slash primitive - arc/slash motion at target
 * Properties: color, size, angle, direction ('left', 'right', 'up', 'down')
 */
function executeSlashPrimitive(element, context) {
    const targetIds = resolveTemplateTargeting(element.target || TEMPLATE_TARGETING.TARGET_CENTER, context);

    const props = element.properties || {};
    const duration = element.timing?.duration || 300;

    targetIds.forEach((targetId, index) => {
        const targetElement = getTargetElement(targetId);
        if (!targetElement) return;

        const rect = targetElement.getBoundingClientRect();
        const x = rect.left + rect.width / 2;
        const y = rect.top + rect.height / 2;

        createSlash(x, y, props, duration, index);
    });
}

/**
 * Execute beam primitive - sustained beam from source to target
 * Properties: color, width, pulseSpeed, glow
 */
function executeBeamPrimitive(element, context) {
    const fromTargets = resolveTemplateTargeting(element.from || TEMPLATE_TARGETING.SOURCE_CENTER, context);
    const toTargets = resolveTemplateTargeting(element.to || TEMPLATE_TARGETING.TARGET_CENTER, context);

    if (fromTargets.length === 0 || toTargets.length === 0) return;

    const sourceElement = getTargetElement(fromTargets[0]);
    if (!sourceElement) return;

    const sourceRect = sourceElement.getBoundingClientRect();
    const sourceX = sourceRect.left + sourceRect.width / 2;
    const sourceY = sourceRect.top + sourceRect.height / 2;

    const props = element.properties || {};
    const duration = element.timing?.duration || 800;

    toTargets.forEach((targetId, index) => {
        const targetElement = getTargetElement(targetId);
        if (!targetElement) return;

        const targetRect = targetElement.getBoundingClientRect();
        const targetX = targetRect.left + targetRect.width / 2;
        const targetY = targetRect.top + targetRect.height / 2;

        createBeam(sourceX, sourceY, targetX, targetY, props, duration, index);
    });
}

/**
 * Execute shockwave primitive - expanding ring from target
 * Properties: color, startSize, endSize, thickness, fadeOut
 */
function executeShockwavePrimitive(element, context) {
    const targetIds = resolveTemplateTargeting(element.target || TEMPLATE_TARGETING.SOURCE_CENTER, context);

    const props = element.properties || {};
    const duration = element.timing?.duration || 600;

    targetIds.forEach((targetId, index) => {
        const targetElement = getTargetElement(targetId);
        if (!targetElement) return;

        const rect = targetElement.getBoundingClientRect();
        const x = rect.left + rect.width / 2;
        const y = rect.top + rect.height / 2;

        createShockwave(x, y, props, duration, index);
    });
}

/**
 * Execute spray primitive - multiple projectiles in spread pattern
 * Properties: color, size, count, spread (degrees), speed
 */
function executeSprayPrimitive(element, context) {
    const fromTargets = resolveTemplateTargeting(element.from || TEMPLATE_TARGETING.SOURCE_CENTER, context);
    const toTargets = resolveTemplateTargeting(element.to || TEMPLATE_TARGETING.TARGET_CENTER, context);

    if (fromTargets.length === 0 || toTargets.length === 0) return;

    const sourceElement = getTargetElement(fromTargets[0]);
    if (!sourceElement) return;

    const sourceRect = sourceElement.getBoundingClientRect();
    const sourceX = sourceRect.left + sourceRect.width / 2;
    const sourceY = sourceRect.top + sourceRect.height / 2;

    const props = element.properties || {};
    const duration = element.timing?.duration || 400;

    // Get primary target direction
    const targetElement = getTargetElement(toTargets[0]);
    if (!targetElement) return;

    const targetRect = targetElement.getBoundingClientRect();
    const targetX = targetRect.left + targetRect.width / 2;
    const targetY = targetRect.top + targetRect.height / 2;

    createSpray(sourceX, sourceY, targetX, targetY, props, duration);
}

/**
 * Execute chain primitive - effect that jumps between targets
 * Properties: color, width, jumpDelay, fadeOut
 */
function executeChainPrimitive(element, context) {
    const fromTargets = resolveTemplateTargeting(element.from || TEMPLATE_TARGETING.SOURCE_CENTER, context);
    const toTargets = resolveTemplateTargeting(element.to || TEMPLATE_TARGETING.EACH_TARGET_CENTER, context);

    if (fromTargets.length === 0 || toTargets.length === 0) return;

    const props = element.properties || {};
    const duration = element.timing?.duration || 800;

    createChainEffect(fromTargets[0], toTargets, props, duration);
}

// ============================================================
// PRIMITIVE CREATION FUNCTIONS
// ============================================================

/**
 * Create a straight-line projectile
 */
function createProjectile(fromX, fromY, toX, toY, properties, duration, index = 0) {
    const color = properties.color || '#FFAA00';
    const size = properties.size || 8;
    const shape = properties.shape || 'circle';
    const trail = properties.trail !== false;

    const container = document.getElementById('animation-container') || document.body;

    // Create projectile element
    const projectile = document.createElement('div');
    projectile.className = 'animation-projectile';
    projectile.style.cssText = `
        position: fixed;
        left: ${fromX}px;
        top: ${fromY}px;
        width: ${size}px;
        height: ${size}px;
        background: ${color};
        border-radius: ${shape === 'circle' ? '50%' : shape === 'diamond' ? '0' : '2px'};
        transform: translate(-50%, -50%) ${shape === 'diamond' ? 'rotate(45deg)' : ''};
        box-shadow: 0 0 ${size}px ${color}, 0 0 ${size * 2}px ${color}50;
        z-index: 10000;
        pointer-events: none;
        transition: left ${duration}ms linear, top ${duration}ms linear;
    `;

    container.appendChild(projectile);

    // Animate to target
    requestAnimationFrame(() => {
        projectile.style.left = `${toX}px`;
        projectile.style.top = `${toY}px`;
    });

    // Clean up
    setTimeout(() => {
        projectile.remove();
    }, duration + 50);
}

/**
 * Create an arcing projectile - curved line from source to target
 */
function createArcProjectile(fromX, fromY, toX, toY, properties, duration, index = 0) {
    const color = properties.color || '#44FF44';
    const size = properties.size || 10;

    const container = document.getElementById('animation-container') || document.body;

    // Calculate distance for proportional arc
    const distance = Math.sqrt(Math.pow(toX - fromX, 2) + Math.pow(toY - fromY, 2));
    // Arc height proportional to distance, with minimum to ensure visible curve
    const arcHeight = properties.arcHeight || Math.max(80, distance * 0.4);

    // Calculate control point perpendicular to the source-target line
    const midX = (fromX + toX) / 2;
    const midY = (fromY + toY) / 2;

    // Get perpendicular direction (rotate 90 degrees left)
    const dx = toX - fromX;
    const dy = toY - fromY;
    const len = distance || 1;
    // Perpendicular vector pointing "left" of the direction
    const perpX = -dy / len;
    const perpY = dx / len;

    // Control point offset perpendicular to the line
    // This ensures curve regardless of source-target angle
    const controlX = midX + perpX * arcHeight;
    const controlY = midY + perpY * arcHeight;

    // Create canvas element for curved line (avoiding SVG rendering issues)
    const canvas = document.createElement('canvas');
    canvas.className = 'animation-arc';
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    canvas.style.cssText = `
        position: fixed;
        left: 0;
        top: 0;
        width: 100vw;
        height: 100vh;
        z-index: 10000;
        pointer-events: none;
    `;

    const ctx = canvas.getContext('2d');
    container.appendChild(canvas);

    // Calculate approximate path length for animation timing
    const segments = 50;
    let pathLength = 0;
    let prevX = fromX, prevY = fromY;
    for (let i = 1; i <= segments; i++) {
        const t = i / segments;
        const x = (1-t)*(1-t)*fromX + 2*(1-t)*t*controlX + t*t*toX;
        const y = (1-t)*(1-t)*fromY + 2*(1-t)*t*controlY + t*t*toY;
        pathLength += Math.sqrt((x-prevX)*(x-prevX) + (y-prevY)*(y-prevY));
        prevX = x;
        prevY = y;
    }

    // Animate the line drawing from source to target
    const startTime = performance.now();
    const animate = (currentTime) => {
        // Check if canvas was removed (e.g., during rewind) - stop animation
        if (!canvas.parentNode) {
            return;
        }

        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);

        // Clear canvas
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Draw glow layers
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';

        // Outer glow
        ctx.strokeStyle = color + '40';
        ctx.lineWidth = size;
        drawPartialCurve(ctx, fromX, fromY, controlX, controlY, toX, toY, progress);

        // Middle glow
        ctx.strokeStyle = color + '80';
        ctx.lineWidth = size / 2;
        drawPartialCurve(ctx, fromX, fromY, controlX, controlY, toX, toY, progress);

        // Core line
        ctx.strokeStyle = color;
        ctx.lineWidth = size / 4;
        drawPartialCurve(ctx, fromX, fromY, controlX, controlY, toX, toY, progress);

        if (progress < 1) {
            requestAnimationFrame(animate);
        } else {
            canvas.remove();
        }
    };

    requestAnimationFrame(animate);
}

/**
 * Helper function to draw a partial quadratic bezier curve
 */
function drawPartialCurve(ctx, fromX, fromY, controlX, controlY, toX, toY, progress) {
    ctx.beginPath();
    ctx.moveTo(fromX, fromY);

    if (progress >= 1) {
        ctx.quadraticCurveTo(controlX, controlY, toX, toY);
    } else {
        // Draw only up to progress point along curve
        const segments = Math.max(20, Math.floor(progress * 50));
        for (let i = 1; i <= segments; i++) {
            const t = (i / segments) * progress;
            const x = (1-t)*(1-t)*fromX + 2*(1-t)*t*controlX + t*t*toX;
            const y = (1-t)*(1-t)*fromY + 2*(1-t)*t*controlY + t*t*toY;
            ctx.lineTo(x, y);
        }
    }

    ctx.stroke();
}

/**
 * Create an explosion effect
 */
function createExplosion(x, y, properties, duration, index = 0) {
    const color = properties.color || '#FF4444';
    const size = properties.size || 60;
    const particleCount = properties.particleCount || 12;

    const container = document.getElementById('animation-container') || document.body;

    // Create central flash
    const flash = document.createElement('div');
    flash.className = 'animation-explosion-flash';
    flash.style.cssText = `
        position: fixed;
        left: ${x}px;
        top: ${y}px;
        width: ${size}px;
        height: ${size}px;
        background: radial-gradient(circle, white 0%, ${color} 40%, transparent 70%);
        border-radius: 50%;
        transform: translate(-50%, -50%) scale(0);
        z-index: 10000;
        pointer-events: none;
        animation: explosion-scale ${duration}ms ease-out forwards;
    `;

    container.appendChild(flash);

    // Create particles
    for (let i = 0; i < particleCount; i++) {
        const angle = (i / particleCount) * Math.PI * 2;
        const particle = document.createElement('div');
        const particleSize = 4 + Math.random() * 4;

        particle.className = 'animation-explosion-particle';
        particle.style.cssText = `
            position: fixed;
            left: ${x}px;
            top: ${y}px;
            width: ${particleSize}px;
            height: ${particleSize}px;
            background: ${color};
            border-radius: 50%;
            transform: translate(-50%, -50%);
            z-index: 10001;
            pointer-events: none;
        `;

        container.appendChild(particle);

        // Animate outward
        const distance = size * (0.5 + Math.random() * 0.5);
        const endX = x + Math.cos(angle) * distance;
        const endY = y + Math.sin(angle) * distance;

        requestAnimationFrame(() => {
            particle.style.transition = `all ${duration}ms ease-out`;
            particle.style.left = `${endX}px`;
            particle.style.top = `${endY}px`;
            particle.style.opacity = '0';
        });

        setTimeout(() => particle.remove(), duration + 50);
    }

    setTimeout(() => flash.remove(), duration + 50);
}

/**
 * Create a slash effect
 */
function createSlash(x, y, properties, duration, index = 0) {
    const color = properties.color || '#FFFFFF';
    const size = properties.size || 80;
    const direction = properties.direction || 'right';

    const container = document.getElementById('animation-container') || document.body;

    const slash = document.createElement('div');
    const rotation = direction === 'right' ? -30 : direction === 'left' ? 30 : direction === 'up' ? -60 : 60;

    slash.className = 'animation-slash';
    slash.style.cssText = `
        position: fixed;
        left: ${x}px;
        top: ${y}px;
        width: ${size}px;
        height: ${size / 8}px;
        background: linear-gradient(90deg, transparent 0%, ${color} 20%, white 50%, ${color} 80%, transparent 100%);
        border-radius: ${size / 16}px;
        transform: translate(-50%, -50%) rotate(${rotation}deg) scaleX(0);
        transform-origin: center;
        z-index: 10000;
        pointer-events: none;
        animation: slash-swipe ${duration}ms ease-out forwards;
    `;

    container.appendChild(slash);
    setTimeout(() => slash.remove(), duration + 50);
}

/**
 * Create a sustained beam
 */
function createBeam(fromX, fromY, toX, toY, properties, duration, index = 0) {
    const color = properties.color || '#00FFFF';
    const width = properties.width || 4;

    const container = document.getElementById('animation-container') || document.body;

    const dx = toX - fromX;
    const dy = toY - fromY;
    const length = Math.sqrt(dx * dx + dy * dy);
    const angle = Math.atan2(dy, dx) * 180 / Math.PI;

    const beam = document.createElement('div');
    beam.className = 'animation-beam';
    beam.style.cssText = `
        position: fixed;
        left: ${fromX}px;
        top: ${fromY}px;
        width: ${length}px;
        height: ${width}px;
        background: linear-gradient(90deg, ${color}00 0%, ${color} 10%, ${color} 90%, ${color}00 100%);
        transform: rotate(${angle}deg);
        transform-origin: 0 50%;
        z-index: 10000;
        pointer-events: none;
        box-shadow: 0 0 ${width * 2}px ${color}, 0 0 ${width * 4}px ${color}50;
        animation: beam-pulse ${duration}ms ease-in-out;
    `;

    container.appendChild(beam);
    setTimeout(() => beam.remove(), duration + 50);
}

/**
 * Create a shockwave effect
 */
function createShockwave(x, y, properties, duration, index = 0) {
    const color = properties.color || '#FFFFFF';
    const startSize = properties.startSize || 20;
    const endSize = properties.endSize || 120;
    const thickness = properties.thickness || 3;

    const container = document.getElementById('animation-container') || document.body;

    const ring = document.createElement('div');
    ring.className = 'animation-shockwave';
    ring.style.cssText = `
        position: fixed;
        left: ${x}px;
        top: ${y}px;
        width: ${startSize}px;
        height: ${startSize}px;
        border: ${thickness}px solid ${color};
        border-radius: 50%;
        transform: translate(-50%, -50%);
        z-index: 10000;
        pointer-events: none;
        box-shadow: 0 0 ${thickness * 2}px ${color};
    `;

    container.appendChild(ring);

    requestAnimationFrame(() => {
        ring.style.transition = `all ${duration}ms ease-out`;
        ring.style.width = `${endSize}px`;
        ring.style.height = `${endSize}px`;
        ring.style.opacity = '0';
        ring.style.borderWidth = '1px';
    });

    setTimeout(() => ring.remove(), duration + 50);
}

/**
 * Create a spray of projectiles
 */
function createSpray(fromX, fromY, toX, toY, properties, duration) {
    const color = properties.color || '#FFAA00';
    const size = properties.size || 6;
    const count = properties.count || 5;
    const spread = properties.spread || 30; // degrees

    const baseAngle = Math.atan2(toY - fromY, toX - fromX);
    const spreadRad = (spread * Math.PI) / 180;
    const distance = Math.sqrt((toX - fromX) ** 2 + (toY - fromY) ** 2);

    for (let i = 0; i < count; i++) {
        const angleOffset = (i - (count - 1) / 2) * (spreadRad / (count - 1 || 1));
        const angle = baseAngle + angleOffset;
        const endX = fromX + Math.cos(angle) * distance;
        const endY = fromY + Math.sin(angle) * distance;

        setTimeout(() => {
            createProjectile(fromX, fromY, endX, endY, { color, size, shape: 'circle' }, duration, i);
        }, i * 30); // Stagger slightly
    }
}

/**
 * Create a chain effect jumping between targets
 */
function createChainEffect(sourceId, targetIds, properties, duration) {
    const color = properties.color || '#AAAAFF';
    const width = properties.width || 3;
    const jumpDelay = properties.jumpDelay || 100;

    let currentId = sourceId;

    targetIds.forEach((targetId, index) => {
        setTimeout(() => {
            const sourceElement = getTargetElement(currentId);
            const targetElement = getTargetElement(targetId);

            if (sourceElement && targetElement) {
                const sourceRect = sourceElement.getBoundingClientRect();
                const targetRect = targetElement.getBoundingClientRect();

                const fromX = sourceRect.left + sourceRect.width / 2;
                const fromY = sourceRect.top + sourceRect.height / 2;
                const toX = targetRect.left + targetRect.width / 2;
                const toY = targetRect.top + targetRect.height / 2;

                createBeam(fromX, fromY, toX, toY, { color, width }, duration / targetIds.length);
            }

            currentId = targetId;
        }, index * jumpDelay);
    });
}

/**
 * NEW: Resolve template targeting to actual element IDs
 * @param {string} targeting - Targeting type
 * @param {Object} context - Execution context
 * @returns {Array} Array of target element IDs
 */
function resolveTemplateTargeting(targeting, context) {
    switch (targeting) {
        case TEMPLATE_TARGETING.SOURCE_CENTER:
            return [context.source_id];

        case TEMPLATE_TARGETING.TARGET_CENTER:
            return context.target_ids.slice(0, 1); // First target only

        case TEMPLATE_TARGETING.EACH_TARGET_CENTER:
            return context.target_ids; // All targets

        default:
            console.warn(`[ANIMATIONS] Unknown targeting type: ${targeting}`);
            return [];
    }
}

/**
 * NEW: Create a jagged lightning bolt between two points
 * @param {number} fromX - Source X coordinate
 * @param {number} fromY - Source Y coordinate
 * @param {number} toX - Target X coordinate
 * @param {number} toY - Target Y coordinate
 * @param {Object} properties - Lightning properties
 * @param {number} index - Lightning bolt index for identification
 */
function createLightningBolt(fromX, fromY, toX, toY, properties, index) {
    console.log(`[ANIMATIONS] Creating lightning bolt ${index + 1}: ${fromX},${fromY} -> ${toX},${toY}`);

    // Create SVG container for jagged lightning
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', 'lightning-bolt');
    svg.style.position = 'fixed';
    svg.style.top = '0';
    svg.style.left = '0';
    svg.style.width = '100%';
    svg.style.height = '100%';
    svg.style.pointerEvents = 'none';
    svg.style.zIndex = '10000';
    svg.style.opacity = '0';
    svg.style.transition = 'opacity 0.1s ease-in';

    // Generate jagged lightning path
    const lightningPath = generateLightningPath(fromX, fromY, toX, toY, properties);

    // Create lightning path element
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', lightningPath);
    path.setAttribute('stroke', properties.color || '#FFFFFF');
    path.setAttribute('stroke-width', properties.thickness || 2);
    path.setAttribute('fill', 'none');
    path.setAttribute('stroke-linecap', 'round');
    path.setAttribute('stroke-linejoin', 'round');

    // Add glow effect if specified
    if (properties.glow) {
        path.setAttribute('filter', 'url(#lightning-glow)');

        // Create glow filter
        const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
        const filter = document.createElementNS('http://www.w3.org/2000/svg', 'filter');
        filter.setAttribute('id', 'lightning-glow');

        const glow1 = document.createElementNS('http://www.w3.org/2000/svg', 'feGaussianBlur');
        glow1.setAttribute('stdDeviation', '3');
        glow1.setAttribute('result', 'coloredBlur');

        const merge = document.createElementNS('http://www.w3.org/2000/svg', 'feMerge');
        const mergeNode1 = document.createElementNS('http://www.w3.org/2000/svg', 'feMergeNode');
        mergeNode1.setAttribute('in', 'coloredBlur');
        const mergeNode2 = document.createElementNS('http://www.w3.org/2000/svg', 'feMergeNode');
        mergeNode2.setAttribute('in', 'SourceGraphic');

        merge.appendChild(mergeNode1);
        merge.appendChild(mergeNode2);
        filter.appendChild(glow1);
        filter.appendChild(merge);
        defs.appendChild(filter);
        svg.appendChild(defs);
    }

    svg.appendChild(path);
    document.body.appendChild(svg);

    // Animate lightning appearance
    requestAnimationFrame(() => {
        svg.style.opacity = '1';

        // Add flickering effect if specified
        if (properties.flicker) {
            addLightningFlicker(path, properties);
        }
    });

    // Remove lightning after duration
    const duration = properties.travel_speed === 'fast' ? 400 :
                    properties.travel_speed === 'slow' ? 800 : 600;

    setTimeout(() => {
        svg.style.opacity = '0';
        setTimeout(() => {
            if (svg.parentNode) {
                svg.parentNode.removeChild(svg);
            }
        }, 100);
    }, duration);

    console.log(`[ANIMATIONS] Lightning bolt ${index + 1} created with ${lightningPath.split('L').length} segments`);
}

/**
 * NEW: Generate a jagged lightning path between two points
 * @param {number} fromX - Source X coordinate
 * @param {number} fromY - Source Y coordinate
 * @param {number} toX - Target X coordinate
 * @param {number} toY - Target Y coordinate
 * @param {Object} properties - Lightning properties
 * @returns {string} SVG path string
 */
function generateLightningPath(fromX, fromY, toX, toY, properties) {
    const segments = [];
    const deltaX = toX - fromX;
    const deltaY = toY - fromY;
    const distance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);

    // Determine jaggedness intensity
    const intensityMap = {
        'low': 0.1,
        'medium': 0.2,
        'high': 0.3
    };
    const jaggedness = intensityMap[properties.jaggedness_intensity] || intensityMap['medium'];

    // Calculate number of segments based on distance
    const segmentCount = Math.max(4, Math.floor(distance / 50));
    const maxDeviation = distance * jaggedness;

    // Start path at source
    let pathString = `M ${fromX} ${fromY}`;

    // Generate intermediate points with random deviations
    for (let i = 1; i < segmentCount; i++) {
        const progress = i / segmentCount;

        // Base position along direct line
        const baseX = fromX + deltaX * progress;
        const baseY = fromY + deltaY * progress;

        // Calculate perpendicular direction for deviation
        const perpX = -deltaY / distance;
        const perpY = deltaX / distance;

        // Random deviation (stronger in middle, weaker near endpoints)
        const deviationStrength = Math.sin(progress * Math.PI);
        const maxDev = maxDeviation * deviationStrength;
        const deviation = (Math.random() - 0.5) * 2 * maxDev;

        // Apply deviation
        const jaggedX = baseX + perpX * deviation;
        const jaggedY = baseY + perpY * deviation;

        segments.push({x: jaggedX, y: jaggedY});
        pathString += ` L ${jaggedX.toFixed(1)} ${jaggedY.toFixed(1)}`;
    }

    // End at target
    pathString += ` L ${toX} ${toY}`;

    return pathString;
}

/**
 * NEW: Add flickering effect to lightning bolt
 * @param {Element} pathElement - SVG path element
 * @param {Object} properties - Lightning properties
 */
function addLightningFlicker(pathElement, properties) {
    let flickerCount = 0;
    const maxFlickers = 8;
    const baseOpacity = 1.0;
    const flickerOpacity = 0.3;

    function flicker() {
        if (flickerCount >= maxFlickers) return;

        pathElement.style.opacity = flickerOpacity;
        setTimeout(() => {
            pathElement.style.opacity = baseOpacity;
            flickerCount++;

            if (flickerCount < maxFlickers) {
                setTimeout(flicker, 30 + Math.random() * 50);
            }
        }, 20 + Math.random() * 30);
    }

    // Start flickering after a brief moment
    setTimeout(flicker, 50);
}

/**
 * NEW: Create a template-defined line between two points (original straight line)
 * @param {number} fromX - Source X coordinate
 * @param {number} fromY - Source Y coordinate
 * @param {number} toX - Target X coordinate
 * @param {number} toY - Target Y coordinate
 * @param {Object} properties - Line properties
 * @param {number} index - Line index for identification
 */
function createTemplateLine(fromX, fromY, toX, toY, properties, index) {
    const line = document.createElement('div');
    line.className = 'template-line';
    line.style.position = 'fixed';
    line.style.pointerEvents = 'none';
    line.style.zIndex = '10000';

    const deltaX = toX - fromX;
    const deltaY = toY - fromY;
    const distance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);
    const angle = Math.atan2(deltaY, deltaX) * (180 / Math.PI);

    line.style.left = fromX + 'px';
    line.style.top = fromY + 'px';
    line.style.width = distance + 'px';
    line.style.height = (properties.thickness || 3) + 'px';
    line.style.backgroundColor = properties.color || '#00BFFF';
    line.style.transform = `rotate(${angle}deg)`;
    line.style.transformOrigin = '0 50%';
    line.style.opacity = '0';
    line.style.transition = 'opacity 0.2s ease-in';

    // Add glow effect if specified
    if (properties.glow) {
        line.style.boxShadow = `0 0 10px ${properties.glow_color || properties.color}, 0 0 20px ${properties.glow_color || properties.color}`;
    }

    document.body.appendChild(line);

    // Animate line appearance
    requestAnimationFrame(() => {
        line.style.opacity = '1';
        line.classList.add('active');
    });

    // Remove line after duration
    const duration = properties.travel_speed === 'fast' ? 400 :
                    properties.travel_speed === 'slow' ? 800 : 600;

    setTimeout(() => {
        line.style.opacity = '0';
        setTimeout(() => {
            if (line.parentNode) {
                line.parentNode.removeChild(line);
            }
        }, 200);
    }, duration);

    console.log(`[ANIMATIONS] Created template line ${index + 1}: ${fromX},${fromY} -> ${toX},${toY} (${distance.toFixed(1)}px)`);
}

/**
 * NEW: Apply glow effect to element
 * @param {Element} element - Target element
 * @param {Object} properties - Effect properties
 * @param {number} duration - Effect duration
 */
function applyGlowEffect(element, properties, duration) {
    element.classList.add('template-glow');

    if (properties.color) {
        element.style.setProperty('--template-glow-color', properties.color);
    }

    if (properties.intensity === 'high') {
        element.classList.add('glow-high');
    } else {
        element.classList.add('glow-active');
    }

    if (properties.pulse) {
        if (properties.pulse_speed === 'fast') {
            element.classList.add('glow-pulse-fast');
        } else {
            element.classList.add('glow-pulse');
        }
    }

    setTimeout(() => {
        element.classList.remove('template-glow', 'glow-active', 'glow-high', 'glow-pulse', 'glow-pulse-fast');
        element.style.removeProperty('--template-glow-color');
    }, duration);
}

/**
 * NEW: Apply flash effect to element
 * @param {Element} element - Target element
 * @param {Object} properties - Effect properties
 * @param {number} duration - Effect duration
 */
function applyFlashEffect(element, properties, duration) {
    element.classList.add('template-flash');

    if (properties.color) {
        element.style.setProperty('--template-flash-color', properties.color);
    }

    setTimeout(() => {
        element.classList.remove('template-flash');
        element.style.removeProperty('--template-flash-color');
    }, duration);
}

/**
 * NEW: Apply particle effect to element
 * @param {Element} element - Target element
 * @param {Object} properties - Effect properties
 * @param {number} duration - Effect duration
 */
function applyParticleEffect(element, properties, duration) {
    const particleCount = properties.count || 5;
    const particleColor = properties.color || '#FFFF00';

    for (let i = 0; i < particleCount; i++) {
        setTimeout(() => {
            createParticle(element, particleColor, properties.particle_type);
        }, i * 50); // Stagger particle creation
    }
}

/**
 * NEW: Create a single particle
 * @param {Element} element - Parent element
 * @param {string} color - Particle color
 * @param {string} type - Particle type
 */
function createParticle(element, color, type) {
    const particle = document.createElement('div');
    particle.className = `template-particle particle-${type}`;
    particle.style.position = 'absolute';
    particle.style.width = '4px';
    particle.style.height = '4px';
    particle.style.backgroundColor = color;
    particle.style.borderRadius = '50%';
    particle.style.pointerEvents = 'none';
    particle.style.zIndex = '9999';

    const rect = element.getBoundingClientRect();
    particle.style.left = (rect.left + rect.width / 2) + 'px';
    particle.style.top = (rect.top + rect.height / 2) + 'px';

    document.body.appendChild(particle);

    // Animate particle
    const angle = Math.random() * Math.PI * 2;
    const distance = 20 + Math.random() * 30;
    const endX = parseFloat(particle.style.left) + Math.cos(angle) * distance;
    const endY = parseFloat(particle.style.top) + Math.sin(angle) * distance;

    particle.animate([
        { transform: 'translate(0, 0) scale(1)', opacity: 1 },
        { transform: `translate(${endX - parseFloat(particle.style.left)}px, ${endY - parseFloat(particle.style.top)}px) scale(0)`, opacity: 0 }
    ], {
        duration: 500,
        easing: 'ease-out'
    }).onfinish = () => {
        if (particle.parentNode) {
            particle.parentNode.removeChild(particle);
        }
    };
}

/**
 * NEW: Apply pulse effect to element
 * @param {Element} element - Target element
 * @param {Object} properties - Effect properties
 * @param {number} duration - Effect duration
 */
function applyPulseEffect(element, properties, duration) {
    element.classList.add('template-pulse');

    setTimeout(() => {
        element.classList.remove('template-pulse');
    }, duration);
}

/**
 * NEW: Apply fade effect to element
 * @param {Element} element - Target element
 * @param {Object} properties - Effect properties
 * @param {number} duration - Effect duration
 */
function applyFadeEffect(element, properties, duration) {
    const startOpacity = properties.from || 1;
    const endOpacity = properties.to || 0;

    element.style.opacity = startOpacity;
    element.style.transition = `opacity ${duration}ms ease`;

    requestAnimationFrame(() => {
        element.style.opacity = endOpacity;
    });

    setTimeout(() => {
        element.style.removeProperty('opacity');
        element.style.removeProperty('transition');
    }, duration);
}

/**
 * Process legacy bundle (fallback for non-template bundles)
 * @param {Object} bundleData - Bundle configuration
 */
async function processLegacyBundle(bundleData) {
    // Route to appropriate legacy bundle handler
    switch (bundleData.type) {
        case 'wizard_spell_barrage':
            await processLegacyWizardSpellBarrageBundle(bundleData);
            break;
        default:
            console.warn(`[ANIMATIONS] Unknown legacy bundle type: ${bundleData.type}`);
            await processGenericBundle(bundleData);
            break;
    }
}

/**
 * Process legacy wizard spell barrage bundle with bolt animations
 * This is the fallback when no template is available
 */
async function processLegacyWizardSpellBarrageBundle(bundleData) {
    const commands = bundleData.commands;
    const castCommand = commands[0]; // First command should be TRIGGER_CAST
    const damageCommands = commands.slice(1); // Rest should be DEAL_DAMAGE

    console.log('[ANIMATIONS] Processing legacy wizard spell barrage with bolt animations');

    // Show cast trigger animation
    const castAnimationId = playAnimation(castCommand);

    // Create wizard bolt barrage visuals using legacy method
    createWizardBoltBarrage(castCommand, damageCommands, bundleData.data);

    // Set up bundle completion callback
    bundleData.cleanup = () => {
        console.log('[ANIMATIONS] Legacy wizard spell barrage bundle completed');
    };

    // The bundle duration is controlled by the bolt travel time + impact time
    bundleData.duration = 1200; // Bolt travel (400ms) + impact effects (800ms)
}

/**
 * Process generic bundle (fallback for unknown bundle types)
 */
async function processGenericBundle(bundleData) {
    console.log(`[ANIMATIONS] Processing generic bundle: ${bundleData.type}`);

    // Process all commands in sequence with short delays
    for (let i = 0; i < bundleData.commands.length; i++) {
        const command = bundleData.commands[i];
        playAnimation(command);

        // Short delay between commands in bundle
        if (i < bundleData.commands.length - 1) {
            await new Promise(resolve => setTimeout(resolve, 150));
        }
    }

    bundleData.cleanup = () => {
        console.log(`[ANIMATIONS] Generic bundle ${bundleData.type} completed`);
    };
}

/**
 * Play an animation from command metadata
 * @param {Object} command - Command with animation metadata
 * @returns {number} Animation ID
 */
function playAnimation(command) {
    if (!command.animation || !command.animation.type) {
        if (animationSystem.debug) {
            console.log('[ANIMATIONS] No animation data in command:', command.cmd);
        }
        return null;
    }

    const animationData = {
        id: animationSystem.nextAnimationId++,
        type: command.animation.type,
        properties: command.animation.properties || {},
        duration: command.animation.duration || command.duration || 800,
        controllable: command.animation.controllable !== false,
        parallel: command.animation.parallel !== false,
        autoCleanup: command.animation.autoCleanup !== false,
        command: command
    };

    if (animationSystem.debug) {
        console.log('[ANIMATIONS] Queuing animation:', animationData.type, 'for', animationData.properties.target_id);
    }

    animationSystem.animationQueue.push(animationData);
    return animationData.id;
}

/**
 * Start an animation immediately
 * @param {Object} animationData - Animation configuration
 */
function startAnimation(animationData) {
    const targetElement = getTargetElement(animationData.properties.target_id);
    if (!targetElement) {
        console.warn('[ANIMATIONS] Target element not found:', animationData.properties.target_id);
        return;
    }

    animationData.state = ANIMATION_STATES.RUNNING;
    animationData.startTime = Date.now();
    animationData.targetElement = targetElement;

    animationSystem.activeAnimations.set(animationData.id, animationData);

    // Apply animation based on type
    switch (animationData.type) {
        case 'glow':
            // DISABLED: Skip glow animations to reduce visual clutter
            console.log('[ANIMATIONS] Skipping glow animation (disabled)');
            animationData.state = ANIMATION_STATES.COMPLETED;
            animationSystem.activeAnimations.delete(animationData.id);
            return;
            // startGlowAnimation(animationData);
            // break;
        case 'death_fade':
            startDeathFadeAnimation(animationData);
            break;
        case 'move_highlight':
            startMoveHighlightAnimation(animationData);
            break;
        default:
            console.warn('[ANIMATIONS] Unknown animation type:', animationData.type);
            completeAnimation(animationData.id);
            break;
    }

    if (animationSystem.debug) {
        console.log('[ANIMATIONS] Started animation:', animationData.type, 'on', animationData.properties.target_id);
    }
}

/**
 * Start a glow animation
 * @param {Object} animationData - Animation configuration
 */
function startGlowAnimation(animationData) {
    const element = animationData.targetElement;
    const props = animationData.properties;

    element.classList.add('animation-glow');

    if (props.color) {
        element.style.setProperty('--animation-glow-color', props.color);
        element.style.setProperty('color', props.color);
    }

    if (props.intensity === 'high') {
        element.classList.add('glow-high');
    } else {
        element.classList.add('glow-active');
    }

    if (props.pulse) {
        if (props.pulse_speed === 'fast' || props.pulse_pattern === 'fast') {
            element.classList.add('glow-pulse-fast');
        } else if (props.pulse_pattern === 'stun') {
            element.classList.add('glow-pulse-stun');
        } else {
            element.classList.add('glow-pulse');
        }
    }

    animationData.cleanup = () => {
        element.classList.remove('animation-glow', 'glow-active', 'glow-high', 'glow-pulse', 'glow-pulse-fast', 'glow-pulse-stun');
        element.style.removeProperty('--animation-glow-color');
        element.style.removeProperty('color');
    };
}

/**
 * Start a death fade animation
 * @param {Object} animationData - Animation configuration
 */
function startDeathFadeAnimation(animationData) {
    const element = animationData.targetElement;

    animationData.autoCleanup = false;

    element.classList.add('animation-death-fade');

    setTimeout(() => {
        element.classList.add('death-active');
    }, 50);

    animationData.cleanup = () => {
        element.classList.remove('animation-death-fade', 'death-active');
    };

    if (animationSystem.debug) {
        console.log('[ANIMATIONS] Death animation started (persistent until manual cleanup):', animationData.properties.target_id);
    }
}

/**
 * Start a move highlight animation
 * @param {Object} animationData - Animation configuration
 */
function startMoveHighlightAnimation(animationData) {
    const element = animationData.targetElement;
    const props = animationData.properties;

    element.classList.add('animation-move-highlight');

    if (props.color) {
        element.style.setProperty('color', props.color);
    }

    setTimeout(() => {
        element.classList.add('move-active');
    }, 50);

    animationData.cleanup = () => {
        element.classList.remove('animation-move-highlight', 'move-active');
        element.style.removeProperty('color');
    };
}

/**
 * Complete an animation and clean up
 * @param {number} animationId - Animation ID
 */
function completeAnimation(animationId) {
    const animation = animationSystem.activeAnimations.get(animationId);
    if (!animation) {
        return;
    }

    animation.state = ANIMATION_STATES.COMPLETED;

    if (animation.cleanup) {
        animation.cleanup();
    }

    if (animationSystem.debug) {
        console.log('[ANIMATIONS] Completed animation:', animation.type, 'on', animation.properties.target_id);
    }
}

/**
 * Complete a bundle and clean up
 * @param {number} bundleId - Bundle ID
 */
function completeBundle(bundleId) {
    const bundle = animationSystem.activeBundles.get(bundleId);
    if (!bundle) {
        return;
    }

    bundle.state = BUNDLE_STATES.COMPLETED;

    if (bundle.cleanup) {
        bundle.cleanup();
    }

    if (animationSystem.debug) {
        console.log('[ANIMATIONS] Completed bundle:', bundle.type, 'ID:', bundleId);
    }
}

/**
 * Manually cleanup an animation
 * @param {number} animationId - Animation ID
 */
function cleanupAnimation(animationId) {
    const animation = animationSystem.activeAnimations.get(animationId);
    if (!animation) {
        return false;
    }

    if (animation.cleanup) {
        animation.cleanup();
    }

    animation.state = ANIMATION_STATES.COMPLETED;
    animationSystem.activeAnimations.delete(animationId);

    if (animationSystem.debug) {
        console.log('[ANIMATIONS] Manually cleaned up animation:', animation.type, 'on', animation.properties.target_id);
    }

    return true;
}

/**
 * Manually cleanup a bundle
 * @param {number} bundleId - Bundle ID
 */
function cleanupBundle(bundleId) {
    const bundle = animationSystem.activeBundles.get(bundleId);
    if (!bundle) {
        return false;
    }

    if (bundle.cleanup) {
        bundle.cleanup();
    }

    bundle.state = BUNDLE_STATES.COMPLETED;
    animationSystem.activeBundles.delete(bundleId);

    if (animationSystem.debug) {
        console.log('[ANIMATIONS] Manually cleaned up bundle:', bundle.type, 'ID:', bundleId);
    }

    return true;
}

/**
 * Cleanup animations by target ID
 * @param {string} targetId - Target element ID to cleanup
 */
function cleanupAnimationsByTargetId(targetId) {
    let cleanedCount = 0;
    const toCleanup = [];

    animationSystem.activeAnimations.forEach((animation, id) => {
        if (animation.properties.target_id === targetId) {
            toCleanup.push(id);
        }
    });

    toCleanup.forEach(id => {
        if (cleanupAnimation(id)) {
            cleanedCount++;
        }
    });

    if (animationSystem.debug && cleanedCount > 0) {
        console.log('[ANIMATIONS] Cleaned up', cleanedCount, 'animations for target:', targetId);
    }

    return cleanedCount;
}

/**
 * Pause a specific animation
 * @param {number} animationId - Animation ID
 */
function pauseAnimation(animationId) {
    const animation = animationSystem.activeAnimations.get(animationId);
    if (!animation || !animation.controllable) {
        return false;
    }

    if (animation.state === ANIMATION_STATES.RUNNING) {
        animation.state = ANIMATION_STATES.PAUSED;
        animation.pauseTime = Date.now();

        if (animation.targetElement) {
            animation.targetElement.classList.add('animation-paused');
        }

        if (animationSystem.debug) {
            console.log('[ANIMATIONS] Paused animation:', animationId);
        }
        return true;
    }

    return false;
}

/**
 * Resume a paused animation
 * @param {number} animationId - Animation ID
 */
function resumeAnimation(animationId) {
    const animation = animationSystem.activeAnimations.get(animationId);
    if (!animation || !animation.controllable) {
        return false;
    }

    if (animation.state === ANIMATION_STATES.PAUSED) {
        const pauseDuration = Date.now() - animation.pauseTime;
        animation.startTime += pauseDuration;
        animation.state = ANIMATION_STATES.RUNNING;

        if (animation.targetElement) {
            animation.targetElement.classList.remove('animation-paused');
            animation.targetElement.classList.add('animation-running');
        }

        if (animationSystem.debug) {
            console.log('[ANIMATIONS] Resumed animation:', animationId);
        }
        return true;
    }

    return false;
}

/**
 * Cancel a specific animation
 * @param {number} animationId - Animation ID
 */
function cancelAnimation(animationId) {
    const animation = animationSystem.activeAnimations.get(animationId);
    if (!animation) {
        return false;
    }

    animation.state = ANIMATION_STATES.CANCELLED;

    if (animation.cleanup) {
        animation.cleanup();
    }

    animationSystem.activeAnimations.delete(animationId);

    if (animationSystem.debug) {
        console.log('[ANIMATIONS] Cancelled animation:', animationId);
    }

    return true;
}

/**
 * Pause all animations and bundles
 */
function pauseAllAnimations() {
    animationSystem.isPaused = true;

    animationSystem.activeAnimations.forEach((animation, id) => {
        if (animation.controllable && animation.state === ANIMATION_STATES.RUNNING) {
            pauseAnimation(id);
        }
    });

    // Also pause bundles
    animationSystem.activeBundles.forEach((bundle, id) => {
        if (bundle.state === BUNDLE_STATES.RUNNING) {
            bundle.state = BUNDLE_STATES.PAUSED;
            bundle.pauseTime = Date.now();
        }
    });

    if (animationSystem.debug) {
        console.log('[ANIMATIONS] Paused all animations and bundles');
    }
}

/**
 * Resume all animations and bundles
 */
function resumeAllAnimations() {
    animationSystem.isPaused = false;

    animationSystem.activeAnimations.forEach((animation, id) => {
        if (animation.controllable && animation.state === ANIMATION_STATES.PAUSED) {
            resumeAnimation(id);
        }
    });

    // Also resume bundles
    animationSystem.activeBundles.forEach((bundle, id) => {
        if (bundle.state === BUNDLE_STATES.PAUSED) {
            const pauseDuration = Date.now() - bundle.pauseTime;
            bundle.startTime += pauseDuration;
            bundle.state = BUNDLE_STATES.RUNNING;
        }
    });

    if (animationSystem.debug) {
        console.log('[ANIMATIONS] Resumed all animations and bundles');
    }
}

/**
 * Cancel all animations and bundles
 */
function cancelAllAnimations() {
    const animationIds = Array.from(animationSystem.activeAnimations.keys());
    const bundleIds = Array.from(animationSystem.activeBundles.keys());

    animationIds.forEach(id => {
        cancelAnimation(id);
    });

    // Cancel all bundles
    bundleIds.forEach(id => {
        const bundle = animationSystem.activeBundles.get(id);
        if (bundle) {
            bundle.state = BUNDLE_STATES.CANCELLED;
            if (bundle.cleanup) {
                bundle.cleanup();
            }
            animationSystem.activeBundles.delete(id);
        }
    });

    animationSystem.animationQueue = [];
    animationSystem.bundleQueue = [];

    if (animationSystem.debug) {
        console.log('[ANIMATIONS] Cancelled all animations and bundles');
    }
}

/**
 * NEW: Complete reset of animation system (for dev mode)
 */
function resetAnimationSystem() {
    console.log('[ANIMATIONS] Performing complete animation system reset');

    // Cancel everything first
    cancelAllAnimations();

    // Clear all DOM elements created by animations
    cleanupAllAnimationDOM();

    // Reset all state
    animationSystem.activeAnimations.clear();
    animationSystem.activeBundles.clear();
    animationSystem.animationQueue = [];
    animationSystem.bundleQueue = [];
    animationSystem.isPaused = false;

    // Don't reset IDs - keep incrementing to avoid conflicts
    // animationSystem.nextAnimationId = 1;
    // animationSystem.nextBundleId = 1;

    // Remove any animation classes from all elements
    document.querySelectorAll('[class*="animation-"], [class*="template-"], [class*="lightning-"]').forEach(element => {
        // Remove animation-related classes
        const classesToRemove = Array.from(element.classList).filter(className =>
            className.includes('animation-') ||
            className.includes('template-') ||
            className.includes('lightning-') ||
            className.includes('glow-') ||
            className.includes('death-') ||
            className.includes('move-')
        );

        classesToRemove.forEach(className => {
            element.classList.remove(className);
        });

        // Remove animation-related CSS properties
        element.style.removeProperty('--animation-glow-color');
        element.style.removeProperty('--template-glow-color');
        element.style.removeProperty('--template-flash-color');
        element.style.removeProperty('opacity');
        element.style.removeProperty('transition');
        element.style.removeProperty('color');
    });

    console.log('[ANIMATIONS] Animation system reset complete');
}

/**
 * NEW: Clean up all DOM elements created by animations
 */
function cleanupAllAnimationDOM() {
    // Remove all lightning bolts
    document.querySelectorAll('.lightning-bolt').forEach(element => {
        if (element.parentNode) {
            element.parentNode.removeChild(element);
        }
    });

    // Remove all wizard bolts (legacy)
    document.querySelectorAll('.wizard-bolt').forEach(element => {
        if (element.parentNode) {
            element.parentNode.removeChild(element);
        }
    });

    // Remove all template lines
    document.querySelectorAll('.template-line').forEach(element => {
        if (element.parentNode) {
            element.parentNode.removeChild(element);
        }
    });

    // Remove all template particles
    document.querySelectorAll('.template-particle').forEach(element => {
        if (element.parentNode) {
            element.parentNode.removeChild(element);
        }
    });

    // Remove all lightning impacts
    document.querySelectorAll('.lightning-impact').forEach(element => {
        if (element.parentNode) {
            element.parentNode.removeChild(element);
        }
    });

    // NEW: Remove all arrows
    document.querySelectorAll('.arrow-container').forEach(element => {
        if (element.parentNode) {
            element.parentNode.removeChild(element);
        }
    });

    // Remove all projectiles
    document.querySelectorAll('.animation-projectile').forEach(element => {
        if (element.parentNode) {
            element.parentNode.removeChild(element);
        }
    });

    // Remove all arc projectiles (canvas)
    document.querySelectorAll('.animation-arc').forEach(element => {
        if (element.parentNode) {
            element.parentNode.removeChild(element);
        }
    });

    // Remove all explosion effects
    document.querySelectorAll('.animation-explosion-flash').forEach(element => {
        if (element.parentNode) {
            element.parentNode.removeChild(element);
        }
    });

    document.querySelectorAll('.animation-explosion-particle').forEach(element => {
        if (element.parentNode) {
            element.parentNode.removeChild(element);
        }
    });

    // Remove all slash effects
    document.querySelectorAll('.animation-slash').forEach(element => {
        if (element.parentNode) {
            element.parentNode.removeChild(element);
        }
    });

    // Remove all beam effects
    document.querySelectorAll('.animation-beam').forEach(element => {
        if (element.parentNode) {
            element.parentNode.removeChild(element);
        }
    });

    // Remove all shockwave effects
    document.querySelectorAll('.animation-shockwave').forEach(element => {
        if (element.parentNode) {
            element.parentNode.removeChild(element);
        }
    });

    // Remove any orphaned SVG elements
    document.querySelectorAll('svg.lightning-bolt').forEach(element => {
        if (element.parentNode) {
            element.parentNode.removeChild(element);
        }
    });

    console.log('[ANIMATIONS] All animation DOM elements cleaned up');
}

/**
 * Set global animation speed
 * @param {number} speed - Speed multiplier
 */
function setAnimationSpeed(speed) {
    animationSystem.globalSpeed = Math.max(0.1, Math.min(10.0, speed));

    if (animationSystem.debug) {
        console.log('[ANIMATIONS] Set animation speed:', animationSystem.globalSpeed);
    }
}

/**
 * Get target element by combat ID or element ID
 * @param {string} targetId - Target identifier
 * @returns {Element|null} Target element
 */
function getTargetElement(targetId) {
    if (!targetId) {
        console.warn('[ANIMATIONS] No target ID provided');
        return null;
    }

    let element = document.querySelector(`[data-combat-id="${targetId}"]`);

    if (!element) {
        element = document.getElementById(targetId);
    }

    if (!element) {
        element = document.querySelector(`[data-minion-index]`);
    }

    if (!element) {
        console.warn('[ANIMATIONS] Could not find target element for ID:', targetId);
        const allCombatElements = document.querySelectorAll('[data-combat-id]');
        console.log('[ANIMATIONS] Available combat elements:', Array.from(allCombatElements).map(el => el.getAttribute('data-combat-id')));
    }

    return element;
}

/**
 * Create a custom glow animation
 * @param {string} targetId - Target element ID
 * @param {string} color - Glow color
 * @param {number} duration - Animation duration
 * @param {string} intensity - Glow intensity
 * @param {boolean} pulse - Whether to pulse
 * @returns {number} Animation ID
 */
function createCustomGlow(targetId, color = '#FFFFFF', duration = 800, intensity = 'medium', pulse = false) {
    const customCommand = {
        cmd: 'CUSTOM_GLOW',
        animation: {
            type: 'glow',
            duration: duration,
            controllable: true,
            properties: {
                target_id: targetId,
                color: color,
                intensity: intensity,
                pulse: pulse,
                effect_type: 'custom'
            }
        }
    };

    return playAnimation(customCommand);
}

/**
 * Create wizard bolt barrage animation (legacy fallback)
 * @param {Object} castCommand - The TRIGGER_CAST command
 * @param {Array} damageCommands - Array of DEAL_DAMAGE commands
 * @param {Object} bundle - Bundle metadata
 */
function createWizardBoltBarrage(castCommand, damageCommands, bundle) {
    console.log('[ANIMATIONS] Creating legacy wizard bolt barrage animation');

    const sourceId = castCommand.source_id;
    const sourceElement = getTargetElement(sourceId);

    if (!sourceElement) {
        console.warn('[ANIMATIONS] Wizard source element not found:', sourceId);
        return;
    }

    const sourceRect = sourceElement.getBoundingClientRect();
    const sourceX = sourceRect.left + sourceRect.width / 2;
    const sourceY = sourceRect.top + sourceRect.height / 2;

    console.log(`[ANIMATIONS] Wizard at position: ${sourceX}, ${sourceY}`);

    // Fire all bolts simultaneously
    damageCommands.forEach((damageCommand, index) => {
        const targetId = damageCommand.target_id;
        const targetElement = getTargetElement(targetId);

        if (targetElement) {
            const targetRect = targetElement.getBoundingClientRect();
            const targetX = targetRect.left + targetRect.width / 2;
            const targetY = targetRect.top + targetRect.height / 2;

            console.log(`[ANIMATIONS] Firing bolt to target ${index + 1} at: ${targetX}, ${targetY}`);

            createWizardBolt(sourceX, sourceY, targetX, targetY, index);
        } else {
            console.warn('[ANIMATIONS] Target element not found:', targetId);
        }
    });
}

/**
 * Create a wizard bolt animation (legacy fallback)
 * @param {number} fromX - Source X coordinate
 * @param {number} fromY - Source Y coordinate
 * @param {number} toX - Target X coordinate
 * @param {number} toY - Target Y coordinate
 * @param {number} boltIndex - Bolt index for identification
 */
function createWizardBolt(fromX, fromY, toX, toY, boltIndex) {
    const bolt = document.createElement('div');
    bolt.className = 'wizard-bolt';
    bolt.style.position = 'fixed';
    bolt.style.pointerEvents = 'none';
    bolt.style.zIndex = '10000';

    const deltaX = toX - fromX;
    const deltaY = toY - fromY;
    const distance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);
    const angle = Math.atan2(deltaY, deltaX) * (180 / Math.PI);

    bolt.style.left = fromX + 'px';
    bolt.style.top = fromY + 'px';
    bolt.style.width = distance + 'px';
    bolt.style.height = '3px';
    bolt.style.backgroundColor = '#00BFFF';
    bolt.style.boxShadow = '0 0 10px #00BFFF, 0 0 20px #00BFFF';
    bolt.style.transform = `rotate(${angle}deg)`;
    bolt.style.transformOrigin = '0 50%';
    bolt.style.opacity = '0';
    bolt.style.transition = 'opacity 0.2s ease-in';

    document.body.appendChild(bolt);

    requestAnimationFrame(() => {
        bolt.style.opacity = '1';
        bolt.classList.add('active');
    });

    setTimeout(() => {
        bolt.style.opacity = '0';
        setTimeout(() => {
            if (bolt.parentNode) {
                bolt.parentNode.removeChild(bolt);
            }
        }, 200);
    }, 400);

    console.log(`[ANIMATIONS] Created wizard bolt ${boltIndex + 1}: ${fromX},${fromY} -> ${toX},${toY} (${distance.toFixed(1)}px, ${angle.toFixed(1)}°)`);
}

/**
 * Get animation system debug information
 * @returns {Object} Debug information
 */
function getAnimationDebugInfo() {
    return {
        activeAnimations: animationSystem.activeAnimations.size,
        activeBundles: animationSystem.activeBundles.size,
        queuedAnimations: animationSystem.animationQueue.length,
        queuedBundles: animationSystem.bundleQueue.length,
        globalSpeed: animationSystem.globalSpeed,
        isPaused: animationSystem.isPaused,
        nextAnimationId: animationSystem.nextAnimationId,
        nextBundleId: animationSystem.nextBundleId,
        activeAnimationDetails: Array.from(animationSystem.activeAnimations.values()).map(anim => ({
            id: anim.id,
            type: anim.type,
            state: anim.state,
            target: anim.properties.target_id,
            duration: anim.duration,
            autoCleanup: anim.autoCleanup
        })),
        activeBundleDetails: Array.from(animationSystem.activeBundles.values()).map(bundle => ({
            id: bundle.id,
            type: bundle.type,
            state: bundle.state,
            commands: bundle.commands.length,
            duration: bundle.duration
        }))
    };
}

/**
 * Enable or disable animation debug logging
 * @param {boolean} enabled - Whether to enable debug logging
 */
function setAnimationDebug(enabled) {
    animationSystem.debug = enabled;
    console.log('[ANIMATIONS] Debug logging', enabled ? 'enabled' : 'disabled');
}

// Initialize the animation system when this script loads
if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeAnimationSystem);
    } else {
        initializeAnimationSystem();
    }

    setTimeout(() => {
        if (window.animationFunctions) {
            window.animationFunctions.setAnimationDebug(true);
            console.log('[ANIMATIONS] Animation system loaded with lightning bolt support, arrow objects, and debug enabled');
        }
    }, 100);
}

// ============================================================================
// COMBAT ATTACK ANIMATIONS - JavaScript-based animations for attack sequences
// ============================================================================

/**
 * Combat attack animation system state
 */
let combatAttackAnimations = {
    activeAttacks: new Map(),        // Map of attack ID to attack animation state
    attackQueue: [],                 // Queue of pending attack animations
    nextAttackId: 1,                 // Incrementing ID for attack animations
    isProcessing: false,             // Whether we're currently processing the queue
    currentShake: null,              // Current screen shake animation
    overlapPercent: 0.5              // 50% overlap between animations
};

/**
 * Screen shake effect using JavaScript animation
 * @param {HTMLElement} element - Element to shake (default: combat battlefield)
 * @param {number} duration - Shake duration in milliseconds (default: 100ms)
 * @param {number} intensity - Shake intensity in pixels (default: 5px)
 * @returns {Object} Animation control object with stop() method
 */
function screenShake(element = null, duration = 100, intensity = 5) {
    // Default to combat battlefield if no element specified
    if (!element) {
        element = document.querySelector('.combat-battlefield') ||
                  document.querySelector('.combat-zone') ||
                  document.body;
    }

    // Store original transform
    const originalTransform = element.style.transform || '';

    let startTime = null;
    let animationFrameId = null;
    let stopped = false;

    function shake(timestamp) {
        if (stopped) {
            // Restore original transform
            element.style.transform = originalTransform;
            return;
        }

        if (!startTime) {
            startTime = timestamp;
        }

        const elapsed = timestamp - startTime;
        const progress = elapsed / duration;

        if (progress >= 1) {
            // Animation complete - restore original transform
            element.style.transform = originalTransform;
            combatAttackAnimations.currentShake = null;
            return;
        }

        // Calculate shake offset with decay (starts strong, weakens over time)
        const decay = 1 - progress;
        const offsetX = (Math.random() - 0.5) * 2 * intensity * decay;
        const offsetY = (Math.random() - 0.5) * 2 * intensity * decay;

        // Apply shake transform
        element.style.transform = `${originalTransform} translate(${offsetX}px, ${offsetY}px)`;

        // Continue animation
        animationFrameId = requestAnimationFrame(shake);
    }

    // Start the shake animation
    animationFrameId = requestAnimationFrame(shake);

    // Return control object
    const control = {
        stop: () => {
            stopped = true;
            if (animationFrameId) {
                cancelAnimationFrame(animationFrameId);
            }
            element.style.transform = originalTransform;
            combatAttackAnimations.currentShake = null;
        },
        element: element,
        duration: duration,
        intensity: intensity
    };

    combatAttackAnimations.currentShake = control;
    return control;
}

/**
 * Stop current screen shake if active
 */
function stopScreenShake() {
    if (combatAttackAnimations.currentShake) {
        combatAttackAnimations.currentShake.stop();
        combatAttackAnimations.currentShake = null;
    }
}

/**
 * Attack animation - JavaScript-based attack with minion movement and screen shake
 * @param {string} attackerId - Combat ID of attacker minion
 * @param {string} targetId - Combat ID of target minion
 * @param {Object} options - Animation options
 * @returns {Object} Animation control object
 */
function playAttackAnimation(attackerId, targetId, options = {}) {
    const attackId = combatAttackAnimations.nextAttackId++;

    // Default options
    const duration = options.duration || 600;
    const shakeDuration = options.shakeDuration || 100;
    const shakeIntensity = options.shakeIntensity || 5;

    let startTime = null;
    let animationFrameId = null;
    let stopped = false;
    let shakeControl = null;
    let movementCache = null; // Cache the movement calculation
    let attackerElement = null;
    let targetElement = null;
    let initialized = false;

    function animate(timestamp) {
        if (stopped) {
            if (attackerElement) {
                attackerElement.style.transform = '';
                attackerElement.classList.remove('attack-animating');
            }
            if (shakeControl) {
                shakeControl.stop();
            }
            return;
        }

        // Initialize on first frame - lookup elements FRESH after updateDisplay()
        if (!initialized) {
            initialized = true;

            // Look up elements NOW (after DOM has been updated)
            attackerElement = document.querySelector(`[data-combat-id="${attackerId}"]`);
            targetElement = document.querySelector(`[data-combat-id="${targetId}"]`);

            // Skip animation if attacker or target doesn't exist
            if (!attackerElement) {
                console.log(`[ATTACK ANIM] Skipping attack animation - attacker ${attackerId} not found after DOM update`);
                stopped = true;
                combatAttackAnimations.activeAttacks.delete(attackId);
                return;
            }

            if (!targetElement) {
                console.log(`[ATTACK ANIM] Skipping attack animation - target ${targetId} not found (may be dead)`);
                stopped = true;
                combatAttackAnimations.activeAttacks.delete(attackId);
                return;
            }

            // Set position and disable transitions
            const computedPosition = window.getComputedStyle(attackerElement).position;
            if (computedPosition === 'static') {
                attackerElement.style.position = 'relative';
            }
            attackerElement.classList.add('attack-animating');
        }

        if (!startTime) {
            startTime = timestamp;

            // Calculate movement ONCE on first frame (after DOM has settled)
            const attackerRect = attackerElement.getBoundingClientRect();
            const targetRect = targetElement.getBoundingClientRect();

            const deltaX = targetRect.left - attackerRect.left;
            const deltaY = targetRect.top - attackerRect.top;

            // Move 85% of the distance toward target
            movementCache = {
                x: deltaX * 0.85,
                y: deltaY * 0.85
            };

            console.log(`[ATTACK ANIM] Attacker at (${attackerRect.left.toFixed(1)}, ${attackerRect.top.toFixed(1)}), size: ${attackerRect.width.toFixed(0)}x${attackerRect.height.toFixed(0)}`);
            console.log(`[ATTACK ANIM] Target at (${targetRect.left.toFixed(1)}, ${targetRect.top.toFixed(1)}), size: ${targetRect.width.toFixed(0)}x${targetRect.height.toFixed(0)}`);
            console.log(`[ATTACK ANIM] Calculated movement: (${movementCache.x.toFixed(1)}, ${movementCache.y.toFixed(1)})`);

            // If elements have no size, abort animation
            if (attackerRect.width === 0 || attackerRect.height === 0 || targetRect.width === 0 || targetRect.height === 0) {
                console.error(`[ATTACK ANIM] Element has no size - aborting animation`);
                stopped = true;
                attackerElement.classList.remove('attack-animating');
                combatAttackAnimations.activeAttacks.delete(attackId);
                return;
            }
        }

        const elapsed = timestamp - startTime;
        const progress = Math.min(elapsed / duration, 1);

        // Animation phases:
        // 0-50%: Move toward target
        // 50%: Impact (trigger screen shake)
        // 50-100%: Return to original position

        if (progress < 0.5) {
            // Moving toward target
            const moveProgress = progress * 2; // 0 to 1

            // Ease out curve for smooth movement
            const eased = 1 - Math.pow(1 - moveProgress, 3);
            const offsetX = movementCache.x * eased;
            const offsetY = movementCache.y * eased;

            attackerElement.style.transform = `translate(${offsetX}px, ${offsetY}px)`;

            // Debug log on first few frames
            if (progress < 0.1) {
                console.log(`[ATTACK ANIM] Frame ${Math.floor(progress * 100)}%: translate(${offsetX.toFixed(1)}px, ${offsetY.toFixed(1)}px)`);
            }

        } else {
            // Impact and return
            if (progress >= 0.5 && !shakeControl) {
                // Trigger screen shake at impact point
                shakeControl = screenShake(null, shakeDuration, shakeIntensity);
                console.log(`[ATTACK ANIM] Impact! Triggered screen shake`);
            }

            // Moving back to original position
            const returnProgress = (progress - 0.5) * 2; // 0 to 1

            // Ease in curve for return
            const eased = Math.pow(1 - returnProgress, 3);
            const offsetX = movementCache.x * eased;
            const offsetY = movementCache.y * eased;

            attackerElement.style.transform = `translate(${offsetX}px, ${offsetY}px)`;
        }

        if (progress >= 1) {
            // Animation complete
            attackerElement.style.transform = '';
            attackerElement.classList.remove('attack-animating');
            combatAttackAnimations.activeAttacks.delete(attackId);
            console.log(`[ATTACK ANIM] Attack ${attackId} complete`);
            return;
        }

        // Continue animation
        animationFrameId = requestAnimationFrame(animate);
    }

    // Wait one frame to ensure DOM has rendered before starting animation
    requestAnimationFrame(() => {
        if (!stopped) {
            animationFrameId = requestAnimationFrame(animate);
        }
    });

    const control = {
        id: attackId,
        attackerId: attackerId,
        targetId: targetId,
        stop: () => {
            stopped = true;
            if (animationFrameId) {
                cancelAnimationFrame(animationFrameId);
            }
            if (attackerElement) {
                attackerElement.style.transform = '';
                attackerElement.classList.remove('attack-animating');
            }
            if (shakeControl) {
                shakeControl.stop();
            }
            combatAttackAnimations.activeAttacks.delete(attackId);
        },
        duration: duration
    };

    combatAttackAnimations.activeAttacks.set(attackId, control);
    console.log(`[ATTACK ANIM] Started attack animation ${attackId}: ${attackerId} -> ${targetId}`);

    return control;
}

/**
 * Queue an attack animation with overlap support
 * @param {string} attackerId - Combat ID of attacker
 * @param {string} targetId - Combat ID of target
 * @param {Object} options - Animation options
 */
function queueAttackAnimation(attackerId, targetId, options = {}) {
    combatAttackAnimations.attackQueue.push({
        attackerId: attackerId,
        targetId: targetId,
        options: options
    });

    // Start processing queue if not already processing
    if (!combatAttackAnimations.isProcessing) {
        processAttackQueue();
    }
}

/**
 * Process the attack animation queue with overlap support
 */
async function processAttackQueue() {
    if (combatAttackAnimations.attackQueue.length === 0) {
        combatAttackAnimations.isProcessing = false;
        return;
    }

    combatAttackAnimations.isProcessing = true;

    const attack = combatAttackAnimations.attackQueue.shift();
    const control = playAttackAnimation(attack.attackerId, attack.targetId, attack.options);

    if (control) {
        // Wait for overlap period before starting next animation
        // 50% overlap means we wait for 50% of the duration
        const overlapDelay = control.duration * combatAttackAnimations.overlapPercent;

        setTimeout(() => {
            processAttackQueue(); // Process next attack
        }, overlapDelay);
    } else {
        // If animation failed to start, immediately process next
        processAttackQueue();
    }
}

/**
 * Stop all attack animations
 */
function stopAllAttackAnimations() {
    // Stop all active attacks
    combatAttackAnimations.activeAttacks.forEach(control => {
        control.stop();
    });
    combatAttackAnimations.activeAttacks.clear();

    // Clear queue
    combatAttackAnimations.attackQueue = [];
    combatAttackAnimations.isProcessing = false;

    // Stop screen shake
    stopScreenShake();

    console.log('[ATTACK ANIM] All attack animations stopped');
}

/**
 * Set overlap percentage for attack animations
 * @param {number} percent - Overlap percentage (0.0 to 1.0)
 */
function setAttackAnimationOverlap(percent) {
    combatAttackAnimations.overlapPercent = Math.max(0, Math.min(1, percent));
    console.log(`[ATTACK ANIM] Attack overlap set to ${combatAttackAnimations.overlapPercent * 100}%`);
}

/**
 * Get debug info for combat attack animations
 */
function getCombatAttackDebugInfo() {
    return {
        activeAttacks: combatAttackAnimations.activeAttacks.size,
        queuedAttacks: combatAttackAnimations.attackQueue.length,
        isProcessing: combatAttackAnimations.isProcessing,
        overlapPercent: combatAttackAnimations.overlapPercent,
        hasActiveShake: combatAttackAnimations.currentShake !== null
    };
}

// ============================================================================
// DAMAGE NUMBERS - Floating damage/heal numbers that pop up on minions
// ============================================================================

/**
 * Damage number animation system state
 */
let damageNumberSystem = {
    activeNumbers: new Map(),    // Map of number ID to animation state
    nextNumberId: 1              // Incrementing ID
};

/**
 * Show a damage number popup on a minion
 * @param {string} targetId - Combat ID of target minion
 * @param {number} amount - Damage amount to display
 * @param {Object} options - Animation options
 * @returns {number} Animation ID
 */
function showDamageNumber(targetId, amount, options = {}) {
    const numberId = damageNumberSystem.nextNumberId++;

    // Options with defaults
    const color = options.color || '#ff4444';
    const prefix = options.prefix || '';
    const duration = options.duration || 500;  // Reduced from 800ms to 500ms
    const fontSize = options.fontSize || 36;
    const isObliterate = options.obliterate || false;
    const isCritical = amount >= 5 && !isObliterate;

    // Look up target element immediately (no delay)
    const targetElement = document.querySelector(`[data-combat-id="${targetId}"]`);

    if (!targetElement) {
        console.log(`[DAMAGE NUM] Target ${targetId} not found - skipping number`);
        return numberId;
    }

    // Get target position
    const targetRect = targetElement.getBoundingClientRect();

    if (targetRect.width === 0 || targetRect.height === 0) {
        console.log(`[DAMAGE NUM] Target has no size - skipping number`);
        return numberId;
    }

    // Calculate center position with random offset to avoid stacking
    const centerX = targetRect.left + targetRect.width / 2;
    const centerY = targetRect.top + targetRect.height / 2;
    const randomOffsetX = (Math.random() - 0.5) * 40; // ±20px
    const randomOffsetY = (Math.random() - 0.5) * 20; // ±10px

    // Create damage number element
    const numberElement = document.createElement('div');
    numberElement.className = 'damage-number-popup';
    numberElement.textContent = `${prefix}${amount}`;
    numberElement.style.position = 'fixed';
    numberElement.style.left = (centerX + randomOffsetX) + 'px';
    numberElement.style.top = (centerY + randomOffsetY) + 'px';
    numberElement.style.fontSize = fontSize + 'px';
    numberElement.style.fontWeight = 'bold';
    numberElement.style.color = color;
    numberElement.style.textShadow = '2px 2px 4px rgba(0, 0, 0, 0.8), -1px -1px 2px rgba(0, 0, 0, 0.8)';
    numberElement.style.pointerEvents = 'none';
    numberElement.style.zIndex = '10001';
    numberElement.style.transform = 'translate(-50%, -50%) scale(0.5)';
    numberElement.style.opacity = '0';
    numberElement.style.whiteSpace = 'nowrap';
    numberElement.style.userSelect = 'none';

    // Special styling for obliterate
    if (isObliterate) {
        numberElement.style.fontSize = (fontSize * 1.3) + 'px';
        numberElement.style.color = '#ff00ff';
        numberElement.textContent = `💀 ${amount}`;
    }
    // Critical damage (5+ damage)
    else if (isCritical) {
        numberElement.style.fontSize = (fontSize * 1.2) + 'px';
    }

    document.body.appendChild(numberElement);

    // Animation state
    let startTime = null;
    let stopped = false;
    let animationFrameId = null;

    const startX = centerX + randomOffsetX;
    const startY = centerY + randomOffsetY;

    function animate(timestamp) {
        if (stopped) {
            if (numberElement.parentNode) {
                numberElement.parentNode.removeChild(numberElement);
            }
            damageNumberSystem.activeNumbers.delete(numberId);
            return;
        }

        if (!startTime) {
            startTime = timestamp;
        }

        const elapsed = timestamp - startTime;
        const progress = Math.min(elapsed / duration, 1);

        // Three-phase animation (now 500ms total, was 800ms)
        let scale, opacity, offsetY;

        if (progress < 0.3) {
            // Phase 1: Grow out (0-150ms) - faster
            const phase1Progress = progress / 0.3;
            const eased = 1 - Math.pow(1 - phase1Progress, 3); // Ease out
            scale = 0.5 + (0.8 * eased); // 0.5 → 1.3
            opacity = eased;
            offsetY = -20 * eased;
        } else if (progress < 0.6) {
            // Phase 2: Hold & float (150-300ms) - shorter hold
            const phase2Progress = (progress - 0.3) / 0.3;
            scale = 1.3;
            opacity = 1;
            offsetY = -20 - (15 * phase2Progress); // Slow drift up
        } else {
            // Phase 3: Shrink & fade (300-500ms) - faster fade
            const phase3Progress = (progress - 0.6) / 0.4;
            const eased = Math.pow(phase3Progress, 2); // Ease in
            scale = 1.3 - (1.0 * eased); // 1.3 → 0.3
            opacity = 1 - eased;
            offsetY = -35 - (30 * eased); // Faster drift up
        }

        // Apply transforms
        numberElement.style.transform = `translate(-50%, -50%) scale(${scale})`;
        numberElement.style.opacity = opacity;
        numberElement.style.top = (startY + offsetY) + 'px';

        if (progress >= 1) {
            // Animation complete
            if (numberElement.parentNode) {
                numberElement.parentNode.removeChild(numberElement);
            }
            damageNumberSystem.activeNumbers.delete(numberId);
            return;
        }

        // Continue animation
        animationFrameId = requestAnimationFrame(animate);
    }

    // Start animation immediately
    animationFrameId = requestAnimationFrame(animate);

    // Store control object
    const control = {
        id: numberId,
        element: numberElement,
        stop: () => {
            stopped = true;
            if (animationFrameId) {
                cancelAnimationFrame(animationFrameId);
            }
            if (numberElement.parentNode) {
                numberElement.parentNode.removeChild(numberElement);
            }
            damageNumberSystem.activeNumbers.delete(numberId);
        }
    };

    damageNumberSystem.activeNumbers.set(numberId, control);

    return numberId;
}

/**
 * Show a buff/debuff number popup on a minion
 * @param {string} targetId - Combat ID of target minion
 * @param {number} attackChange - Attack change amount
 * @param {number} healthChange - Health change amount
 * @param {Object} options - Animation options
 * @returns {number} Animation ID
 */
function showBuffNumber(targetId, attackChange, healthChange, options = {}) {
    const numberId = damageNumberSystem.nextNumberId++;

    // Determine if buff or debuff
    const isBuff = (attackChange > 0 || healthChange > 0);
    const isDebuff = (attackChange < 0 || healthChange < 0);

    // Options with defaults
    const color = options.color || (isBuff ? '#44ff44' : '#ff44ff');
    const duration = options.duration || 500;
    const fontSize = options.fontSize || 32;

    // Look up target element
    const targetElement = document.querySelector(`[data-combat-id="${targetId}"]`);

    if (!targetElement) {
        console.log(`[BUFF NUM] Target ${targetId} not found - skipping number`);
        return numberId;
    }

    // Get target position
    const targetRect = targetElement.getBoundingClientRect();

    if (targetRect.width === 0 || targetRect.height === 0) {
        console.log(`[BUFF NUM] Target has no size - skipping number`);
        return numberId;
    }

    // Build text from stat changes
    const parts = [];
    if (attackChange !== 0 && attackChange !== undefined) {
        const sign = attackChange > 0 ? '+' : '';
        parts.push(`${sign}${attackChange} ATK`);
    }
    if (healthChange !== 0 && healthChange !== undefined) {
        const sign = healthChange > 0 ? '+' : '';
        parts.push(`${sign}${healthChange} HP`);
    }

    if (parts.length === 0) {
        return numberId; // No stat changes to show
    }

    const text = parts.join(' ');

    // Calculate center position with random offset
    const centerX = targetRect.left + targetRect.width / 2;
    const centerY = targetRect.top + targetRect.height / 3; // Slightly higher than damage numbers
    const randomOffsetX = (Math.random() - 0.5) * 40;
    const randomOffsetY = (Math.random() - 0.5) * 20;

    // Create buff number element
    const numberElement = document.createElement('div');
    numberElement.className = 'buff-number-popup';
    numberElement.textContent = text;
    numberElement.style.position = 'fixed';
    numberElement.style.left = (centerX + randomOffsetX) + 'px';
    numberElement.style.top = (centerY + randomOffsetY) + 'px';
    numberElement.style.fontSize = fontSize + 'px';
    numberElement.style.fontWeight = 'bold';
    numberElement.style.color = color;
    numberElement.style.textShadow = '2px 2px 4px rgba(0, 0, 0, 0.8), -1px -1px 2px rgba(0, 0, 0, 0.8)';
    numberElement.style.pointerEvents = 'none';
    numberElement.style.zIndex = '10002'; // Above damage numbers
    numberElement.style.transform = 'translate(-50%, -50%) scale(0.5)';
    numberElement.style.opacity = '0';
    numberElement.style.whiteSpace = 'nowrap';
    numberElement.style.userSelect = 'none';

    document.body.appendChild(numberElement);

    // Animation state
    let startTime = null;
    let stopped = false;
    let animationFrameId = null;

    const startX = centerX + randomOffsetX;
    const startY = centerY + randomOffsetY;

    function animate(timestamp) {
        if (stopped) {
            if (numberElement.parentNode) {
                numberElement.parentNode.removeChild(numberElement);
            }
            damageNumberSystem.activeNumbers.delete(numberId);
            return;
        }

        if (!startTime) startTime = timestamp;
        const elapsed = timestamp - startTime;
        const progress = Math.min(elapsed / duration, 1);

        // Three-phase animation: grow (0-0.3), hold (0.3-0.6), fade (0.6-1.0)
        let scale, opacity;

        if (progress < 0.3) {
            // Growing phase
            const phaseProgress = progress / 0.3;
            scale = 0.5 + (phaseProgress * 0.7); // 0.5 to 1.2
            opacity = phaseProgress;
        } else if (progress < 0.6) {
            // Hold phase
            scale = 1.2;
            opacity = 1;
        } else {
            // Fade out phase
            const phaseProgress = (progress - 0.6) / 0.4;
            scale = 1.2 - (phaseProgress * 0.2); // 1.2 to 1.0
            opacity = 1 - phaseProgress;
        }

        // Apply float upward during animation
        const floatOffset = progress * 30; // Float up 30px

        numberElement.style.transform = `translate(-50%, -50%) scale(${scale})`;
        numberElement.style.opacity = opacity;
        numberElement.style.top = (startY - floatOffset) + 'px';

        if (progress < 1) {
            animationFrameId = requestAnimationFrame(animate);
        } else {
            // Animation complete
            if (numberElement.parentNode) {
                numberElement.parentNode.removeChild(numberElement);
            }
            damageNumberSystem.activeNumbers.delete(numberId);
        }
    }

    animationFrameId = requestAnimationFrame(animate);

    // Store animation state
    damageNumberSystem.activeNumbers.set(numberId, {
        element: numberElement,
        stop: () => {
            stopped = true;
            if (animationFrameId !== null) {
                cancelAnimationFrame(animationFrameId);
            }
        }
    });

    return numberId;
}

/**
 * Show a healing number popup on a minion
 * @param {string} targetId - Combat ID of target minion
 * @param {number} amount - Heal amount to display
 * @param {Object} options - Animation options
 * @returns {number} Animation ID
 */
function showHealNumber(targetId, amount, options = {}) {
    return showDamageNumber(targetId, amount, {
        ...options,
        color: '#44ff44',
        prefix: '+'
    });
}

/**
 * Stop all damage number animations
 */
function stopAllDamageNumbers() {
    damageNumberSystem.activeNumbers.forEach(control => {
        control.stop();
    });
    damageNumberSystem.activeNumbers.clear();
    console.log('[DAMAGE NUM] All damage numbers stopped');
}

/**
 * Get debug info for damage numbers
 */
function getDamageNumberDebugInfo() {
    return {
        activeNumbers: damageNumberSystem.activeNumbers.size
    };
}

// Export functions for use by combat.js
window.animationFunctions = {
    // Core animation functions
    playAnimation,
    pauseAnimation,
    resumeAnimation,
    cancelAnimation,

    // Bundle functions
    playBundle,
    cleanupBundle,

    // Global animation control
    pauseAllAnimations,
    resumeAllAnimations,
    cancelAllAnimations,
    setAnimationSpeed,

    // Manual cleanup functions
    cleanupAnimation,
    cleanupAnimationsByTargetId,

    // NEW: Dev mode reset functions
    resetAnimationSystem,
    cleanupAllAnimationDOM,

    // Custom animations
    createCustomGlow,

    // Legacy animation functions (maintained for compatibility)
    createWizardBoltBarrage,
    createWizardBolt,

    // NEW: Enhanced template system functions
    executeTemplate,
    executeTemplateElement,
    resolveTemplateTargeting,
    createTemplateLine,
    createStyledLine,

    // NEW: Lightning bolt functions
    createLightningBolt,
    generateLightningPath,
    addLightningFlicker,

    // NEW: Arrow functions
    createArrow,

    // Debug functions
    getAnimationDebugInfo,
    setAnimationDebug,

    // Combat attack animation functions
    screenShake,
    stopScreenShake,
    playAttackAnimation,
    queueAttackAnimation,
    stopAllAttackAnimations,
    setAttackAnimationOverlap,
    getCombatAttackDebugInfo,

    // Damage number functions
    showDamageNumber,
    showHealNumber,
    showBuffNumber,
    stopAllDamageNumbers,
    getDamageNumberDebugInfo,

    // Internal state (for debugging)
    getAnimationSystem: () => animationSystem,
    getCombatAttackAnimations: () => combatAttackAnimations
};