// Effect formatting and display functions

function formatMinionSpecificEffect(effectData, isGolden = false, depth = 0) {
    // Prevent infinite recursion with depth limit
    if (depth > 10) {
        console.warn('[formatMinionSpecificEffect] Max recursion depth reached at depth:', depth);
        return "[complex effect]";
    }

    if (!effectData || typeof effectData !== 'object') {
        return "";
    }

    // Debug: Log deep recursion to help identify problematic data
    if (depth > 5) {
        console.warn('[formatMinionSpecificEffect] Deep recursion at depth', depth, ':',
            typeof effectData === 'object' ? Object.keys(effectData) : effectData);
    }

    // Handle arrays of effects (like Tooth Fairy's assault)
    if (Array.isArray(effectData)) {
        const descriptions = effectData.map(effect => formatMinionSpecificEffect(effect, isGolden, depth + 1)).filter(desc => desc);
        return descriptions.join(', then ');
    }

    const effectType = effectData.type || '';
    const target = effectData.target || '';

    // Apply golden doubling to displayed values
    const multiplier = isGolden ? 2 : 1;
    const amount = (effectData.amount || 0) * multiplier;

    switch (effectType) {
        case 'deal_damage':
            const targetCount = (effectData.target_count || 1) * multiplier;
            if (targetCount > 1) {
                const targetPlural = target === 'random_enemy' ? 'random enemies' : target.replace(/_/g, ' ') + 's';
                return `Deal ${amount} damage to ${targetCount} ${targetPlural}`;
            } else if (target === 'defender') {
                return `Deal ${amount} damage to the defender`;
            } else if (target === 'random_enemy') {
                return `Deal ${amount} damage to a random enemy`;
            } else {
                return `Deal ${amount} damage to ${target}`;
            }

        case 'deal_aoe_damage':
            // Default to 999 (all enemies) to match combat system behavior
            const maxTargets = (effectData.max_targets || 999) * multiplier;
            const excludeType = effectData.exclude_type;
            const targetFilters = effectData.target_filters;

            let targetDesc = '';
            if (excludeType) {
                targetDesc = `all enemies except ${excludeType}`;
            } else if (targetFilters) {
                // Check for stunned filter
                const hasStunFilter = targetFilters.some(f => f.type === 'has_keyword' && f.keyword === 'stun');
                if (hasStunFilter) {
                    targetDesc = 'all stunned enemies';
                } else {
                    targetDesc = 'filtered enemies';
                }
            } else if (maxTargets >= 999) {
                targetDesc = 'all enemies';
            } else {
                targetDesc = `up to ${maxTargets} enemies`;
            }

            return `Deal ${amount} damage to ${targetDesc}`;

        case 'heal':
            if (target === 'random_ally') {
                return `Give a random ally ${amount} health`;
            } else {
                return `Give ${target} ${amount} health`;
            }

        case 'heal_self':
            return `Give self ${amount} health`;

        case 'buff_stats':
            const attackBuff = (effectData.attack || 0) * multiplier;
            const healthBuff = (effectData.health || 0) * multiplier;

            let buffText;
            if (attackBuff > 0 && healthBuff > 0) {
                // Both stats: use "+X/+Y" format
                buffText = `+${attackBuff}/+${healthBuff}`;
            } else if (attackBuff > 0) {
                buffText = `+${attackBuff} attack`;
            } else if (healthBuff > 0) {
                buffText = `+${healthBuff} health`;
            } else {
                buffText = '';
            }

            // Handle multiply_by_context (like Frog Prince's leap bonus)
            if (effectData.multiply_by_context) {
                const contextName = effectData.multiply_by_context.replace(/_/g, ' ');
                buffText += ` for each ${contextName}`;
            }

            if (target === 'self') {
                return `Gain ${buffText}`;
            } else if (target === 'random_ally') {
                return `Give a random ally ${buffText}`;
            } else if (target === 'all_allies') {
                return `Give all allies ${buffText}`;
            } else if (target === 'trigger_summoned' || target === 'summoned_minion') {
                return `Give the summoned minion ${buffText}`;
            } else if (target === 'trigger_source') {
                return `Give the triggering minion ${buffText}`;
            } else if (target === 'trigger_target') {
                return `Give the target ${buffText}`;
            } else if (target === 'trigger_leaper') {
                return `Give the leaping minion ${buffText}`;
            } else if (target === 'trigger_dying') {
                return `Give the dying minion ${buffText}`;
            } else {
                return `Give ${target} ${buffText}`;
            }

        case 'buff_stats_tribe':
            const tribe = effectData.tribe || 'Unknown';
            const tribeAttackBuff = (effectData.attack || 0) * multiplier;
            const tribeHealthBuff = (effectData.health || 0) * multiplier;

            let tribeBuffText;
            if (tribeAttackBuff > 0 && tribeHealthBuff > 0) {
                // Both stats: use "+X/+Y" format
                tribeBuffText = `+${tribeAttackBuff}/+${tribeHealthBuff}`;
            } else if (tribeAttackBuff > 0) {
                tribeBuffText = `+${tribeAttackBuff} attack`;
            } else if (tribeHealthBuff > 0) {
                tribeBuffText = `+${tribeHealthBuff} health`;
            } else {
                tribeBuffText = '';
            }
            return `Give all friendly ${tribe} minions ${tribeBuffText}`;

        case 'debuff_stats':
            const attackDebuff = Math.abs((effectData.attack || 0) * multiplier);
            const debuffTarget = target === 'defender' ? 'the defender' : target === 'random_enemy' ? 'a random enemy' : target.replace(/_/g, ' ');
            return `Reduce ${debuffTarget}'s attack by ${attackDebuff}`;

        case 'summon_minion':
            const summonCount = (effectData.summon_count || 1) * multiplier;
            const useSavedStats = effectData.use_saved_stats;
            const summonKeywords = effectData.keywords || [];

            // Check if summoning by criteria (tier) or by name
            let summonDesc = '';
            if (effectData.summon_criteria && effectData.summon_criteria.tier) {
                const tier = effectData.summon_criteria.tier;
                if (summonCount > 1) {
                    summonDesc = `Summon ${summonCount} tier ${tier} minions`;
                } else {
                    summonDesc = `Summon a tier ${tier} minion`;
                }
            } else {
                const minionName = effectData.minion_name || 'unknown';

                if (useSavedStats) {
                    if (summonCount > 1) {
                        summonDesc = `Summon ${summonCount} ${minionName}s with saved stats`;
                    } else {
                        summonDesc = `Summon a ${minionName} with saved stats`;
                    }
                } else {
                    const health = (effectData.health !== undefined ? effectData.health : 1) * multiplier;
                    const attack = (effectData.attack !== undefined ? effectData.attack : 1) * multiplier;

                    if (summonCount > 1) {
                        summonDesc = `Summon ${summonCount} ${minionName}s (${attack}/${health} each)`;
                    } else {
                        summonDesc = `Summon a ${minionName} (${attack}/${health})`;
                    }
                }
            }

            // Add keywords if present
            if (summonKeywords.length > 0) {
                const keywordNames = summonKeywords.map(kw => kw.charAt(0).toUpperCase() + kw.slice(1)).join(', ');
                summonDesc += `, give it ${keywordNames}`;
            }

            return summonDesc;

        case 'permanent_stat_gain':
            const attackGain = (effectData.attack || 0) * multiplier;
            const healthGain = (effectData.health || 0) * multiplier;
            let maxStacks = effectData.max_stacks;

            if (maxStacks && maxStacks < 999) {
                maxStacks = maxStacks * multiplier;
            }

            let gainText;
            if (attackGain > 0 && healthGain > 0) {
                // Both stats: use "+X/+Y" format
                gainText = `+${attackGain}/+${healthGain}`;
            } else if (attackGain > 0) {
                gainText = `+${attackGain} attack`;
            } else if (healthGain > 0) {
                gainText = `+${healthGain} health`;
            } else {
                gainText = '';
            }

            if (maxStacks && maxStacks < 999) {
                return `Permanently gain ${gainText} (max ${maxStacks} times)`;
            } else {
                return `Permanently gain ${gainText}`;
            }

        case 'damage_self':
            return `Take ${amount} damage`;

        case 'modify_fatigue':
            return `Accelerate fatigue by ${amount} attacks`;

        case 'move_minion':
            const direction = effectData.direction || 'right';
            const distance = (effectData.distance || 1) * multiplier;
            return `Move target ${distance} position(s) ${direction}`;

        case 'destroy_and_transform':
            const transformCount = (effectData.summon_count || 2) * multiplier;
            const transformName = effectData.minion_name || 'Meat Cube';
            const statRatio = effectData.stat_ratio || 0.5;
            return `Destroy left ally, summon ${transformCount} ${transformName}s with ${Math.round(statRatio * 100)}% of its stats`;

        case 'buff_adjacent':
            const adjAttack = (effectData.attack || 0) * multiplier;
            const adjHealth = (effectData.health || 0) * multiplier;

            let adjText;
            if (adjAttack > 0 && adjHealth > 0) {
                // Both stats: use "+X/+Y" format
                adjText = `+${adjAttack}/+${adjHealth}`;
            } else if (adjAttack > 0) {
                adjText = `+${adjAttack} attack`;
            } else if (adjHealth > 0) {
                adjText = `+${adjHealth} health`;
            } else {
                adjText = '';
            }
            return `Give adjacent minions ${adjText}`;

        case 'rich_buff':
            if (isGolden) {
                return `Gain +2/+2 per gold`;
            }
            return `Gain +1/+1 per gold`;

        case 'divide_attack':
            const divisor = effectData.divisor || 2;
            const divideTarget = effectData.target || 'self';
            if (divideTarget === 'self') {
                return `Divide attack by ${divisor}`;
            } else {
                return `Divide ${divideTarget.replace(/_/g, ' ')}'s attack by ${divisor}`;
            }

        case 'redirect_death':
            return `Prevent death of a stronger ally by dying instead`;

        case 'modify_gold':
            const goldAmount = (effectData.amount || 0) * multiplier;
            if (goldAmount > 0) {
                return `Gain ${goldAmount} gold`;
            } else {
                return `Lose ${Math.abs(goldAmount)} gold`;
            }

        case 'conditional':
            // Handle conditional effects - can have array or single then_effect
            if (effectData.then_effect) {
                const condition = formatCondition(effectData.condition);

                // Handle array of effects (complex conditionals)
                if (Array.isArray(effectData.then_effect)) {
                    const effects = effectData.then_effect.map(e => formatMinionSpecificEffect(e, isGolden, depth + 1));
                    let combinedDesc = effects.join(', then ');

                    // Replace repeated target descriptions with "it" for better readability
                    if (condition) {
                        const triggerPhrases = [
                            "the summoned minion",
                            "the triggering minion",
                            "the dying minion",
                            "the killer",
                            "the summoner",
                            "the transformed minion",
                            "the leaping minion",
                            "the target",
                            "the attacker",
                            "the defender"
                        ];

                        for (const phrase of triggerPhrases) {
                            if (condition.toLowerCase().includes(phrase)) {
                                const givePattern = `Give ${phrase}`;
                                if (combinedDesc.includes(givePattern)) {
                                    combinedDesc = combinedDesc.replace(givePattern, 'Give it');
                                    break;
                                }
                            }
                        }

                        return `If ${condition}: ${combinedDesc}`;
                    }
                    return combinedDesc;
                }

                // Handle single effect with optional else_effect
                const hasElse = effectData.else_effect;
                let thenDesc = formatMinionSpecificEffect(effectData.then_effect, isGolden, depth + 1);
                let elseDesc = hasElse ? formatMinionSpecificEffect(effectData.else_effect, isGolden, depth + 1) : null;

                // Special format for else_effect: "Do default. If condition, instead do alternative"
                // This is used for effects like Rust Beetle: "Give Can't Retaliate. If they have it, give Can't Attack"
                if (hasElse && condition && thenDesc && elseDesc) {
                    // Check if else_effect is a no-op (deal 0 damage = do nothing)
                    const elseIsNoop = effectData.else_effect.type === 'deal_damage' && effectData.else_effect.amount === 0;
                    if (elseIsNoop) {
                        return `If ${condition}: ${thenDesc}`;
                    }
                    // Format: "Default action. If condition, instead alternative action"
                    return `${elseDesc}. If ${condition}, instead ${thenDesc.toLowerCase()}`;
                }

                // Replace repeated target descriptions with "it" for better readability
                if (condition) {
                    const triggerPhrases = [
                        "the summoned minion",
                        "the triggering minion",
                        "the dying minion",
                        "the killer",
                        "the summoner",
                        "the transformed minion",
                        "the leaping minion",
                        "the target",
                        "the attacker",
                        "the defender"
                    ];

                    for (const phrase of triggerPhrases) {
                        if (condition.toLowerCase().includes(phrase)) {
                            const givePattern = `Give ${phrase}`;
                            if (thenDesc.includes(givePattern)) {
                                thenDesc = thenDesc.replace(givePattern, 'Give it');
                                break;
                            }
                        }
                    }

                    return `If ${condition}: ${thenDesc}`;
                }
                return thenDesc;
            }
            return 'Conditional effect';

        case 'destroy_minion':
            const saveStats = effectData.save_stats;
            const destroyStatRatio = effectData.stat_ratio || 1;
            if (target === 'left_ally') {
                if (saveStats) {
                    return `Destroy left ally (save ${Math.round(destroyStatRatio * 100)}% stats)`;
                }
                return `Destroy left ally`;
            }
            return `Destroy ${target}`;

        case 'copy_stats':
            return `Copy stats from ${target}`;

        case 'transform':
            const newName = effectData.new_minion_name || 'Unknown';
            return `Transform into ${newName}`;

        case 'draw_card':
            return `Draw a card`;

        case 'discover':
            return `Discover a minion`;

        case 'grant_effect_to_minion':
            // Handle granting effects like Possessed's death toll
            const grantedEffectType = effectData.effect_type || 'effect';
            const grantTarget = effectData.target || 'random_ally';
            const excludeName = effectData.exclude_name;
            const grantedEffect = effectData.effect_data;

            let grantTargetText = grantTarget.replace(/_/g, ' ');
            if (excludeName) {
                grantTargetText += ` (excluding ${excludeName})`;
            }
            let effectDescription = 'an effect';

            // Try to describe the granted effect
            if (grantedEffect) {
                effectDescription = formatMinionSpecificEffect(grantedEffect, isGolden, depth + 1);
            }

            // Clean up the effect type name
            let effectTypeName = grantedEffectType.replace(/_effect$/, '').replace(/_/g, ' ');

            return `Give ${grantTargetText} ${effectTypeName}: ${effectDescription}`;

        case 'grant_keyword': {
            const grantKeyword = effectData.keyword || 'unknown';
            const keywordTarget = effectData.target || 'unknown';
            let keywordName = grantKeyword.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

            // Fix "Cant" -> "Can't" for display
            if (keywordName === 'Cant Retaliate') keywordName = "Can't Retaliate";
            if (keywordName === 'Cant Attack') keywordName = "Can't Attack";

            // Add amount for keywords that have keyword_data
            if (effectData.keyword_data && effectData.keyword_data.amount) {
                const amount = effectData.keyword_data.amount * multiplier;
                keywordName = `${keywordName} ${amount}`;
            }

            if (keywordTarget === 'self') {
                return `Gain ${keywordName}`;
            } else if (keywordTarget === 'defender') {
                return `Give defender ${keywordName}`;
            } else if (keywordTarget === 'random_ally') {
                return `Give a random ally ${keywordName}`;
            } else if (keywordTarget === 'all_allies') {
                return `Give all allies ${keywordName}`;
            } else {
                return `Give ${keywordTarget} ${keywordName}`;
            }
        }

        case 'apply_stun': {
            const stunAmount = (effectData.stun_amount || 1) * multiplier;
            const stunTarget = effectData.target || 'defender';
            const stunExcludeSelf = effectData.exclude_self || false;
            const stunExcludeType = effectData.exclude_type || null;

            // Build exclusion text
            let stunExclusionText = '';
            if (stunExcludeSelf && stunExcludeType) {
                stunExclusionText = ` (except self and ${stunExcludeType})`;
            } else if (stunExcludeSelf) {
                stunExclusionText = ' (except self)';
            } else if (stunExcludeType) {
                stunExclusionText = ` (except ${stunExcludeType})`;
            }

            const turnText = stunAmount > 1 ? 's' : '';

            if (stunTarget === 'defender') {
                return `Stun defender for ${stunAmount} turn${turnText}`;
            } else if (stunTarget === 'self') {
                return `Stun self for ${stunAmount} turn${turnText}`;
            } else if (stunTarget === 'all_minions') {
                return `Stun all minions${stunExclusionText} for ${stunAmount} turn${turnText}`;
            } else if (stunTarget === 'all_enemies') {
                return `Stun all enemies${stunExclusionText} for ${stunAmount} turn${turnText}`;
            } else if (stunTarget === 'random_enemy') {
                return `Stun a random enemy for ${stunAmount} turn${turnText}`;
            } else {
                return `Stun ${stunTarget.replace(/_/g, ' ')} for ${stunAmount} turn${turnText}`;
            }
        }

        case 'transfer_stun':
            const fromTargets = effectData.from_targets || 'all_allies';
            const toTarget = effectData.to_target || 'random_enemy';
            return `Transfer stun from ${fromTargets.replace(/_/g, ' ')} to ${toTarget.replace(/_/g, ' ')}`;

        case 'scaling_damage': {
            const scalingBase = (effectData.base_amount || 0) * multiplier;
            const scalingIncrement = (effectData.increment || 0) * multiplier;
            const scalingTarget = effectData.target || 'random_enemy';
            return `Deal ${scalingBase} damage to ${scalingTarget.replace(/_/g, ' ')}, increase this by ${scalingIncrement} for this combat`;
        }

        case 'chrono_cascade':
            return `Force the next cast minion to cast and stun it for 1`;

        case 'trigger_death_toll': {
            const deathTollTarget = effectData.target || 'all_allies';
            const deathTollExcludeSelf = effectData.exclude_self;
            if (deathTollTarget === 'trigger_source') {
                return 'trigger it again';
            } else if (deathTollExcludeSelf) {
                return `Trigger a random friendly death toll (excluding self)`;
            } else if (deathTollTarget === 'all_allies') {
                return `Trigger a random friendly death toll`;
            } else {
                return `Trigger death toll of ${deathTollTarget.replace(/_/g, ' ')}`;
            }
        }

        case 'trigger_start_of_combat': {
            const socTarget = effectData.target || 'all_allies';
            const socExcludeSelf = effectData.exclude_self;
            if (socExcludeSelf) {
                return `Trigger a random friendly start of combat (excluding self)`;
            } else if (socTarget === 'all_allies') {
                return `Trigger a random friendly start of combat`;
            } else {
                return `Trigger start of combat of ${socTarget.replace(/_/g, ' ')}`;
            }
        }

        case 'transform_all_minions':
            const transformTarget = effectData.target || 'all_minions';
            const transformTo = effectData.transform_to || 'self';
            if (transformTo === 'self') {
                return `Transform ${transformTarget.replace(/_/g, ' ')} into copies of this`;
            } else {
                return `Transform ${transformTarget.replace(/_/g, ' ')} into ${transformTo}`;
            }

        case 'attack_target':
            // Determine who is attacking
            let attacker = 'this';
            if (effectData.attacker === 'trigger_summoned') {
                attacker = 'the summoned minion';
            } else if (effectData.attacker === 'condition_found_minion') {
                attacker = 'that minion';
            } else if (effectData.attacker === 'trigger_source') {
                attacker = 'the trigger source';
            } else if (effectData.attacker === 'this' || !effectData.attacker) {
                attacker = 'this';
            } else {
                attacker = effectData.attacker;
            }

            // Determine the target
            let attackTarget = 'a random enemy';
            if (effectData.target_minion === 'trigger_source') {
                attackTarget = 'the trigger source';
            } else if (effectData.target_minion === 'defender') {
                attackTarget = 'the defender';
            } else if (effectData.target_minion === 'left_ally') {
                attackTarget = 'left ally';
            } else if (effectData.target_minion === 'right_ally') {
                attackTarget = 'rightward ally';
            } else if (effectData.target_minion === 'lowest_health_enemy') {
                attackTarget = 'the lowest health enemy';
            } else if (effectData.target_minion && effectData.target_minion !== null) {
                attackTarget = effectData.target_minion;
            }

            // Construct the description
            if (attacker === 'this') {
                return `Attack ${attackTarget}`;
            } else {
                return `${attacker.charAt(0).toUpperCase() + attacker.slice(1)} attacks ${attackTarget}`;
            }

        default:
            return `${effectType.replace(/_/g, ' ')}`;
    }
}

// Format condition descriptions for conditional effects
function formatCondition(condition) {
    if (!condition) return '';

    // Check for empty condition object (always-true condition)
    if (Object.keys(condition).length === 0) return '';

    // Handle compound conditions
    const checkType = condition.check_type || 'simple';
    if (checkType === 'compound') {
        const checks = condition.checks || [];
        const operator = condition.operator || 'AND';
        // Filter out scope conditions (is_ally, is_enemy, is_self) as they're shown in keyword name
        const filteredChecks = checks.filter(c =>
            c.type !== 'is_ally' && c.type !== 'is_enemy' && c.type !== 'is_self'
        );
        const descriptions = filteredChecks.map(c => formatCondition(c)).filter(d => d);
        if (descriptions.length === 0) return '';
        return descriptions.join(` ${operator.toLowerCase()} `);
    }

    // Skip scope conditions for single conditions too (shown in keyword name)
    if (condition.type === 'is_ally' || condition.type === 'is_enemy' || condition.type === 'is_self') {
        return '';
    }

    const type = condition.type;
    const target = condition.target || '';

    // Format target for readability
    let formattedTarget = target;
    if (target === 'trigger_dying') formattedTarget = 'the dying minion';
    else if (target === 'trigger_source') formattedTarget = 'the triggering minion';
    else if (target === 'trigger_target') formattedTarget = 'the target';
    else if (target === 'trigger_attacker') formattedTarget = 'the attacker';
    else if (target === 'trigger_defender') formattedTarget = 'the defender';
    else if (target === 'trigger_summoned' || target === 'summoned_minion') formattedTarget = 'the summoned minion';
    else if (target === 'trigger_caster') formattedTarget = 'the caster';
    else if (target === 'condition_found_minion') formattedTarget = 'the found minion';
    else if (target === 'self') formattedTarget = ''; // Simplify self references

    switch (type) {
        case 'is_ally':
            return `${formattedTarget} is an ally`;
        case 'is_enemy':
            return `${formattedTarget} is an enemy`;
        case 'is_tier':
            return `${formattedTarget} is tier ${condition.tier}`;
        case 'is_adjacent':
            return `${formattedTarget} is adjacent`;
        case 'is_position':
            return condition.position; // Simplified: just "rightmost", "leftmost", etc.
        case 'has_left_ally':
            return 'you have a left ally';
        case 'is_name':
            return `${formattedTarget} is ${condition.minion_name}`;
        case 'not_name':
            return `${formattedTarget} is not ${condition.minion_name}`;
        case 'has_type':
            return `${formattedTarget} is type ${condition.minion_type}`;
        case 'not_has_type':
            return `${formattedTarget} is not type ${condition.minion_type}`;
        case 'has_keyword': {
            // Look up keyword display name from KEYWORDS
            const hasKeywordInfo = KEYWORDS[condition.keyword];
            let hasKeywordName = hasKeywordInfo ? hasKeywordInfo.name : condition.keyword.replace(/_/g, ' ');
            // Add amount for keywords that have it (like cleave 1)
            if (condition.keyword === 'cleave') {
                hasKeywordName = 'Cleave 1'; // Default cleave amount
            }
            return formattedTarget ? `${formattedTarget} has ${hasKeywordName}` : `have ${hasKeywordName}`;
        }
        case 'not_has_keyword': {
            // Look up keyword display name from KEYWORDS
            const notHasKeywordInfo = KEYWORDS[condition.keyword];
            let notHasKeywordName = notHasKeywordInfo ? notHasKeywordInfo.name : condition.keyword.replace(/_/g, ' ');
            // Add amount for keywords that have it (like cleave 1)
            if (condition.keyword === 'cleave') {
                notHasKeywordName = 'Cleave 1'; // Default cleave amount
            }
            return formattedTarget ? `${formattedTarget} doesn't have ${notHasKeywordName}` : `don't have ${notHasKeywordName}`;
        }
        case 'is_self':
            return `${formattedTarget} is this minion`;
        case 'health_above':
            return `${formattedTarget} has more than ${condition.health_threshold || condition.value} health`;
        case 'health_at_most':
            return `${formattedTarget} has at most ${condition.health_threshold || condition.value} health`;
        case 'attack_above':
            return `${formattedTarget} has more than ${condition.attack_threshold || condition.value} attack`;
        case 'attack_at_most': {
            const attackValue = condition.attack_threshold || condition.value;
            return `${formattedTarget} has ${attackValue} or less attack`;
        }
        case 'times_attacked':
            return `this has attacked ${condition.count} time(s)`;
        case 'trigger_count_equals':
            return `this is trigger ${condition.count}`;
        case 'not_additional_trigger':
            return "it isn't an additional trigger";
        case 'has_minion_named':
            return `you have a ${condition.minion_name}`;
        case 'has_minion_with_keyword':
            return `you have a minion with ${condition.keyword}`;
        default:
            return '';
    }
}

// Desktop UI Display Module - v1.5 (Combat tooltip parity)
// Handles all UI rendering for desktop view
// Last updated: 2025-10-27 - Ensured combat minions have complete tooltip data

// Unified effect registry - maps all minion effect fields to display properties
const EFFECT_REGISTRY = [
    // Keywords with effect fields (trigger-based effects)
    { field: 'assault_effect', keyword: 'assault', name: 'Assault', icon: '⚡', color: '#FF5722' },
    { field: 'death_toll_effect', keyword: 'death_toll', name: 'Death Toll', icon: '💀', color: '#9C27B0' },
    { field: 'cast_effect', keyword: 'cast', name: 'Cast', icon: '🔮', color: '#E91E63' },
    { field: 'rage_effect', keyword: 'rage', name: 'Rage', icon: '😡', color: '#D32F2F' },
    { field: 'calm_effect', keyword: 'calm', name: 'Calm', icon: '😌', color: '#00BCD4' },
    { field: 'on_any_cast_effect', keyword: 'on_any_cast', name: 'On Any Cast', icon: '📖', color: '#3F51B5' },
    { field: 'on_any_death_effect', keyword: 'on_any_death', name: 'On Any Death', icon: '👁️', color: '#673AB7' },
    { field: 'on_any_summon_effect', keyword: 'on_any_summon', name: 'On Any Summon', icon: '🌟', color: '#FFD700' },
    { field: 'on_adjacent_transform_effect', keyword: 'on_adjacent_transform', name: 'On Adjacent Transform', icon: '🔄', color: '#8BC34A' },
    { field: 'on_damage_effect', keyword: 'on_damage', name: 'On Damage', icon: '💥', color: '#FF6F00' },
    { field: 'start_of_combat_effect', keyword: 'start_of_combat', name: 'Start of Combat', icon: '🎬', color: '#4CAF50' },
    { field: 'aura_effect', keyword: 'aura', name: 'Aura', icon: '💫', color: '#9C27B0' },
    { field: 'sacrifice_effect', keyword: 'sacrifice', name: 'Sacrifice', icon: '🛡️', color: '#795548' },
    { field: 'on_hide_lost_effect', keyword: 'on_hide_lost', name: 'On Ally Hide Lost', icon: '👁️⚡', color: '#607D8B' },
    { field: 'on_any_death_toll_effect', keyword: 'on_any_death_toll', name: 'On Any Death Toll', icon: '⚰️', color: '#9C27B0' },
    { field: 'on_any_leap_effect', keyword: 'on_any_leap', name: 'On Any Leap', icon: '🦘👁️', color: '#00BCD4' },
    { field: 'cleave_effect', keyword: 'cleave', name: 'Cleave', icon: '🗡️', color: '#F44336' },
    { field: 'obliterate_effect', keyword: 'obliterate', name: 'Obliterate', icon: '💀⚡', color: '#000000' },

    // Keywords without effect fields (passive abilities)
    { keyword: 'poke', name: 'Poke', icon: '🏹', color: '#4CAF50' },
    { keyword: 'guard', name: 'Guard', icon: '🛡️', color: '#2196F3' },
    { keyword: 'cant_attack', name: "Can't Attack", icon: '🚫', color: '#795548' },
    { keyword: 'cant_retaliate', name: "Can't Retaliate", icon: '🛑', color: '#607D8B' },
    { keyword: 'multi_attack', name: 'Multi Attack', icon: '⚔️', color: '#FFC107' },
    { keyword: 'multi_attack_2', name: 'Multi Attack 2', icon: '⚔️⚔️', color: '#FF9800' },
    { keyword: 'stun', name: 'Stun', icon: '⏸️', color: '#9E9E9E' },
    { keyword: 'hide', name: 'Hide', icon: '🫥', color: '#607D8B' },
    { keyword: 'ring', name: 'Ring', icon: '🔔', color: '#FFA500' },
    { keyword: 'leap', name: 'Leap', icon: '🦘', color: '#00BCD4' },
    { keyword: 'nobility', name: 'Nobility', icon: '👑', color: '#9C27B0' },
    { keyword: 'rich', name: 'Rich', icon: '💰', color: '#FFD700' },
    { keyword: 'fatigue_immune', name: 'Fatigue Immune', icon: '💪', color: '#FF5722' },
    { keyword: 'fast', name: 'Fast', icon: '⚡💨', color: '#FFEB3B' },
    { keyword: 'savage', name: 'Savage', icon: '🎯', color: '#D32F2F' },
    { keyword: 'imperfect', name: 'Imperfect', icon: '⚙️', color: '#607D8B' },
    { keyword: 'ignoble', name: 'Ignoble', icon: '🚫👑', color: '#424242' },
    { keyword: 'ethereal', name: 'Ethereal [Last]', icon: '👻', color: '#1565C0' },
    { keyword: 'ethereal_left', name: 'Ethereal [Left]', icon: '👻', color: '#1565C0' },
    { keyword: 'left', name: 'Left', icon: '⬅️', color: '#1565C0' }
];

// Helper function to detect effect scope from conditions
// Returns 'ally', 'enemy', 'self', or null (for no specific scope / any)
function detectEffectScope(effectData) {
    if (!effectData || typeof effectData !== 'object') {
        return null;
    }

    // Check if this is a conditional effect
    if (effectData.type !== 'conditional' || !effectData.condition) {
        return null;
    }

    const condition = effectData.condition;

    // Simple condition type check
    if (condition.type === 'is_ally') {
        return 'ally';
    }
    if (condition.type === 'is_enemy') {
        return 'enemy';
    }
    if (condition.type === 'is_self') {
        return 'self';
    }

    // Compound condition check (e.g., Old Cat Lady has AND checks)
    if (condition.check_type === 'compound' && Array.isArray(condition.checks)) {
        for (const check of condition.checks) {
            if (check.type === 'is_ally') {
                return 'ally';
            }
            if (check.type === 'is_enemy') {
                return 'enemy';
            }
            if (check.type === 'is_self') {
                return 'self';
            }
        }
    }

    return null;
}

// Adjust display name for On_Any_X keywords based on effect scope
function getAdjustedDisplayName(baseName, effectData) {
    const scope = detectEffectScope(effectData);
    if (!scope) {
        return baseName; // Keep original name if no scope detected
    }

    // Map base names to their scope-adjusted versions
    // "On Any Death" -> "On Ally Death", "On Enemy Death", or "On Death" (self)
    // "On Any Summon" -> "On Ally Summon", etc.
    // "On Any Damage" -> "On Ally Damage", etc.

    const scopePrefixMap = {
        'ally': 'Ally ',
        'enemy': 'Enemy ',
        'self': '' // Self triggers just remove "Any "
    };

    const scopePrefix = scopePrefixMap[scope];

    // Replace "Any " with the appropriate scope prefix
    if (baseName.includes('On Any ')) {
        return baseName.replace('On Any ', 'On ' + scopePrefix);
    }

    return baseName;
}

// Generate all effect tags for a minion using the unified registry
function generateAllEffectTags(minion) {
    // Defensive check - return empty if minion is invalid
    if (!minion || typeof minion !== 'object') {
        console.warn('[generateAllEffectTags] Invalid minion data:', minion);
        return '';
    }

    const isGolden = minion.golden || false;
    const effectTags = [];
    const keywords = minion.keywords || [];

    // Debug logging for Skeleton/Bone
    if (minion.name === 'Skeleton' || minion.name === 'Bone') {
        console.log(`[EFFECT_TAGS] Generating effect tags for ${minion.name}:`, {
            keywords: keywords,
            has_death_toll_effect: !!minion.death_toll_effect
        });
    }

    // Process each entry in the registry
    EFFECT_REGISTRY.forEach(entry => {
        let shouldShow = false;
        let description = '';
        let displayName = entry.name;

        // Check if this effect exists on the minion
        if (entry.field && minion[entry.field]) {
            // Has an effect field (assault_effect, cast_effect, etc.)

            // SPECIAL CASE: Skip start_of_combat if the minion has rich or fast
            // (rich/fast are wrappers around start_of_combat and will display it themselves)
            if (entry.keyword === 'start_of_combat' &&
                (keywords.includes('rich') || keywords.includes('fast'))) {
                return; // Skip this entry
            }

            shouldShow = true;
            description = formatMinionSpecificEffect(minion[entry.field], isGolden);

            // Dynamic display name adjustment for On_Any_X keywords based on effect conditions
            if (entry.keyword && entry.keyword.startsWith('on_any_')) {
                displayName = getAdjustedDisplayName(entry.name, minion[entry.field]);
            }

            // Debug logging
            if (minion.name === 'Skeleton' && entry.keyword === 'death_toll') {
                console.log(`[EFFECT_TAGS] Set description for ${entry.name}:`, description);
            }
        } else if (entry.keyword && keywords.includes(entry.keyword)) {
            // Is a keyword (poke, guard, etc.)
            shouldShow = true;

            // Get description from KEYWORDS constant if available
            const keywordInfo = KEYWORDS[entry.keyword];
            if (keywordInfo) {
                description = keywordInfo.description;

                // Check if there's an associated effect field
                const effectField = entry.field || `${entry.keyword}_effect`;
                if (minion[effectField]) {
                    const effectDesc = formatMinionSpecificEffect(minion[effectField], isGolden);
                    // For keywords with complex effects, replace the generic description entirely
                    // on_any_x keywords also replace since the keyword name already describes the trigger
                    if (entry.keyword === 'start_of_combat' || entry.keyword === 'assault' ||
                        entry.keyword === 'cast' || entry.keyword === 'rage' ||
                        entry.keyword.startsWith('on_any_')) {
                        description = effectDesc;
                    } else {
                        description += ': ' + effectDesc;
                    }

                    // Dynamic display name adjustment for On_Any_X keywords based on effect conditions
                    if (entry.keyword && entry.keyword.startsWith('on_any_')) {
                        displayName = getAdjustedDisplayName(entry.name, minion[effectField]);
                    }
                }
            }

            // SPECIAL CASE: Rich and Fast are wrappers around Start of Combat
            // Show them as "Rich: Start of Combat: <effect>" instead of separate tags
            if ((entry.keyword === 'rich' || entry.keyword === 'fast') &&
                minion.start_of_combat_effect) {
                const startOfCombatDesc = formatMinionSpecificEffect(minion.start_of_combat_effect, isGolden);
                description = `Start of Combat: ${startOfCombatDesc}`;
            }

            // Special handling for multi-attack count
            if (entry.keyword === 'multi_attack' || entry.keyword === 'multi_attack_2') {
                const multiCount = (minion.multi_attack_count || (entry.keyword === 'multi_attack_2' ? 2 : 1)) * (isGolden ? 2 : 1);
                displayName = `${entry.name} ${multiCount}`;
            }

            // Special handling for stun count
            if (entry.keyword === 'stun') {
                // During combat, use stun_remaining; outside combat, use stun_count
                // Check both fields and use whichever is defined and > 0
                let stunCount = undefined;
                if (minion.stun_remaining !== undefined && minion.stun_remaining !== null) {
                    stunCount = minion.stun_remaining;
                } else if (minion.stun_count !== undefined && minion.stun_count !== null) {
                    stunCount = minion.stun_count;
                }

                if (stunCount !== undefined && stunCount !== null && stunCount > 0) {
                    displayName = `Stun ${stunCount}`;
                    description += ` (${stunCount} attack(s) skipped)`;
                }
            }

            // Special handling for hide count
            if (entry.keyword === 'hide') {
                // During combat, use hide_remaining; outside combat, use hide_count
                // Check both fields and use whichever is defined and > 0
                let hideCount = undefined;
                if (minion.hide_remaining !== undefined && minion.hide_remaining !== null) {
                    hideCount = minion.hide_remaining;
                } else if (minion.hide_count !== undefined && minion.hide_count !== null) {
                    hideCount = minion.hide_count;
                }

                if (hideCount !== undefined && hideCount !== null && hideCount > 0) {
                    const finalCount = hideCount * (isGolden ? 2 : 1);
                    displayName = `Hide ${finalCount}`;
                    description += ` (${finalCount} attacks before revealed)`;
                }
            }

            // Special handling for ring count
            if (entry.keyword === 'ring') {
                // Use permanent_ring_count (like Cat's permanent stats)
                // Note: Backend already handles base vs added keyword logic for golden minions
                let ringCount = minion.permanent_ring_count;
                console.log(`[RING_DISPLAY] Minion ${minion.name}: permanent_ring_count=${ringCount}, golden=${isGolden}, keywords=${JSON.stringify(minion.keywords)}`);

                if (ringCount !== undefined && ringCount !== null && ringCount > 0) {
                    // Display count as-is (no golden doubling - backend calculates correctly)
                    const finalCount = ringCount;
                    displayName = `Ring ${finalCount}`;
                    description += ` (triggers ${finalCount} more time(s))`;
                    console.log(`[RING_DISPLAY] Displaying as "${displayName}"`);
                } else {
                    console.log(`[RING_DISPLAY] Ring count not valid, showing default "Ring"`);
                }
            }

            // Special handling for leap distance
            if (entry.keyword === 'leap') {
                const leapDist = minion.leap_distance;
                console.log(`[LEAP_DISPLAY] Minion ${minion.name}: leap_distance=${leapDist}, type=${typeof leapDist}`);
                if (leapDist !== undefined && leapDist !== null && leapDist > 0) {
                    displayName = `Leap ${leapDist}`;
                    description = `Moves right ${leapDist} space(s) when attacking`;
                } else {
                    console.log(`[LEAP_DISPLAY] ${minion.name}: Using default Leap (no valid distance)`);
                }
            }

            // Special handling for cleave amount
            if (entry.keyword === 'cleave') {
                const cleaveAmount = minion.cleave_amount;
                if (cleaveAmount !== undefined && cleaveAmount !== null && cleaveAmount > 0) {
                    displayName = `Cleave ${cleaveAmount}`;
                    description = `Attacks also hit ${cleaveAmount} ${cleaveAmount > 1 ? 'enemies' : 'enemy'} on either side of the defender`;
                }
            }
        }

        if (shouldShow) {
            // Debug logging
            if (minion.name === 'Skeleton' && entry.keyword === 'death_toll') {
                console.log(`[EFFECT_TAGS] Adding effect tag:`, {
                    name: displayName,
                    description: description,
                    keyword: entry.keyword
                });
            }

            effectTags.push({
                name: displayName,
                description: description,
                color: entry.color,
                icon: entry.icon
            });
        }
    });

    // Render all tags
    return effectTags.map(effect => {
        const tooltip = `<strong>${effect.name}:</strong> ${effect.description}`;

        // Debug logging
        if (minion.name === 'Skeleton' && effect.name === 'Death Toll') {
            console.log(`[EFFECT_TAGS] Final tooltip for ${effect.name}:`, tooltip);
        }

        const keywordFontSize = getKeywordFontSize(effect.name);
        return `<div class="effect-tag tooltip" data-tooltip-context="minion" style="background: linear-gradient(90deg, ${effect.color} 0%, rgba(0,0,0,0.85) 100%); font-size: ${keywordFontSize};">
            ${effect.name}
            <span class="tooltiptext">${tooltip}</span>
        </div>`;
    }).join('');
}


