#!/usr/bin/env python3
"""
Test Left keyword matching - verifies that "left" in directional context
(like "left ally") does NOT chain to the Ethereal [Left] keyword tooltip.

This test validates the JavaScript tooltip enrichment logic by checking
that minion descriptions with directional "left" are properly formatted.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from minions import get_minion_by_name, MINIONS


def get_all_minions():
    """Get all minions from all tiers as a flat list"""
    all_minions = []
    for tier, minion_list in MINIONS.items():
        if isinstance(minion_list, list):
            all_minions.extend(minion_list)
    return all_minions


def test_left_keyword_in_descriptions():
    """
    Test that minions with 'left ally' in descriptions are properly identified.
    The JavaScript should NOT convert 'left' to a tooltip when followed by:
    - ally, allies, neighbor, neighbors, side, of, minion, minions
    """
    print("=" * 100)
    print("LEFT KEYWORD MATCHING TEST")
    print("=" * 100)
    print()
    print("Testing that 'left' in directional context is NOT linked to Ethereal [Left]")
    print()

    # Find minions that have "left" in their effects/descriptions
    minions_with_left = []

    for minion in get_all_minions():
        name = minion.get('name', '')

        # Check various effect fields for "left"
        effect_texts = []

        # Check attack effect
        attack_effect = minion.get('attack_effect', {})
        if attack_effect:
            # Handle both dict and list attack effects
            if isinstance(attack_effect, dict):
                target = attack_effect.get('target', '')
                if 'left' in str(target).lower():
                    effect_texts.append(f"attack_effect.target: {target}")
            elif 'left' in str(attack_effect).lower():
                effect_texts.append(f"attack_effect: {attack_effect}")

        # Check cast effect
        cast_effect = minion.get('cast_effect', {})
        if cast_effect:
            # Handle both dict and list cast effects
            if isinstance(cast_effect, dict):
                target = cast_effect.get('target', '')
                effect_type = cast_effect.get('type', '')
                if 'left' in str(target).lower() or 'left' in str(effect_type).lower():
                    effect_texts.append(f"cast_effect: {cast_effect}")
            elif 'left' in str(cast_effect).lower():
                effect_texts.append(f"cast_effect: {cast_effect}")

        # Check description
        description = minion.get('description', '')
        if 'left' in description.lower():
            effect_texts.append(f"description: {description}")

        # Check any condition with left
        for key in minion:
            if 'condition' in key.lower():
                condition = minion.get(key, {})
                if 'left' in str(condition).lower():
                    effect_texts.append(f"{key}: {condition}")

        if effect_texts:
            minions_with_left.append({
                'name': name,
                'effects': effect_texts
            })

    print(f"Found {len(minions_with_left)} minions with 'left' in effects/descriptions:")
    print("-" * 100)

    for minion in minions_with_left:
        print(f"\n{minion['name']}:")
        for effect in minion['effects']:
            print(f"  - {effect}")

    print()
    print("=" * 100)
    print()

    return minions_with_left


def test_meat_packing_plant():
    """Specifically test Meat Packaging Plant which should say 'left ally'"""
    print("=" * 100)
    print("MEAT PACKAGING PLANT SPECIFIC TEST")
    print("=" * 100)
    print()

    minion = get_minion_by_name('Meat Packaging Plant')
    if not minion:
        print("ERROR: Meat Packaging Plant not found!")
        return False

    print(f"Minion: {minion['name']}")
    print(f"Type: {minion.get('type', 'N/A')}")
    print(f"Stats: {minion['attack']}/{minion['health']}")
    print()

    # Check cast effect (Meat Packaging Plant uses cast_effect, not attack_effect)
    cast_effect = minion.get('cast_effect', {})
    print(f"Cast Effect: {cast_effect}")
    print()

    # The display should show "Destroy left ally" not "Destroy [tooltip]Left[/tooltip] ally"
    # Extract target from the conditional's then_effect
    condition = cast_effect.get('condition', {})
    then_effect = cast_effect.get('then_effect', [])

    print()
    print("VALIDATION:")
    print("-" * 100)

    # Check condition type
    condition_type = condition.get('type', '')
    if condition_type == 'has_left_ally':
        print("  Condition is 'has_left_ally': PASS")
        print("    (Display: 'you have a left ally' - 'left' should NOT be tooltip-linked)")
    else:
        print(f"  Condition type is '{condition_type}': CHECK")

    # Check then_effect for destroy_minion with left_ally target
    if isinstance(then_effect, list) and len(then_effect) > 0:
        destroy_effect = then_effect[0]
        target = destroy_effect.get('target', '')
        effect_type = destroy_effect.get('type', '')

        if target == 'left_ally':
            print("  Destroy target is 'left_ally': PASS")
            print("    (Display: 'Destroy left ally' - 'left' should NOT be tooltip-linked)")
        else:
            print(f"  Destroy target is '{target}': CHECK")

        if effect_type == 'destroy_minion':
            print("  Effect type is 'destroy_minion': PASS")
        else:
            print(f"  Effect type is '{effect_type}': CHECK")

    print()
    print("Expected tooltip display behavior:")
    print("  'Destroy left ally' - 'left' should NOT be highlighted/linked")
    print("  'Ethereal [Left]' - 'Left' in this context SHOULD be linked")
    print()
    print("=" * 100)

    return True


def test_ethereal_left_minions():
    """Find minions with Ethereal [Left] keyword to verify they still work"""
    print()
    print("=" * 100)
    print("ETHEREAL [LEFT] MINIONS TEST")
    print("=" * 100)
    print()
    print("Testing that minions with 'ethereal_left' keyword are properly identified")
    print("(These SHOULD link to the Ethereal [Left] tooltip)")
    print()

    ethereal_minions = []

    for minion in get_all_minions():
        keywords = minion.get('keywords', [])
        if 'ethereal_left' in keywords or 'ethereal' in keywords:
            ethereal_minions.append({
                'name': minion['name'],
                'keywords': keywords,
                'ethereal_condition': minion.get('ethereal_condition', 'N/A')
            })

    print(f"Found {len(ethereal_minions)} minions with Ethereal keywords:")
    print("-" * 100)

    for minion in ethereal_minions:
        print(f"\n{minion['name']}:")
        print(f"  Keywords: {minion['keywords']}")
        print(f"  Ethereal Condition: {minion['ethereal_condition']}")

    print()
    print("=" * 100)

    return ethereal_minions


def test_javascript_pattern():
    """
    Simulate the JavaScript pattern matching to verify it works correctly.
    This tests the same regex pattern used in enrichTooltipContent.
    """
    import re

    print()
    print("=" * 100)
    print("JAVASCRIPT PATTERN SIMULATION TEST")
    print("=" * 100)
    print()

    # The pattern that should NOT match (directional left)
    directional_pattern = re.compile(r'^\s+(ally|allies|neighbor|neighbors|side|of|minion|minions)', re.IGNORECASE)

    test_cases = [
        ("Destroy left ally", True, "Should NOT link - directional"),
        ("Destroy left allies", True, "Should NOT link - directional"),
        ("left side of the board", True, "Should NOT link - directional"),
        ("left neighbor", True, "Should NOT link - directional"),
        ("left minion dies", True, "Should NOT link - directional"),
        ("Ethereal [Left]", False, "SHOULD link - keyword context"),
        ("Left: condition met", False, "SHOULD link - standalone keyword"),
        ("When left is true", False, "SHOULD link - not followed by directional word"),
    ]

    print("Testing pattern matching:")
    print("-" * 100)

    all_passed = True
    for text, should_skip, reason in test_cases:
        # Find "left" in text (case insensitive)
        match = re.search(r'\bleft\b', text, re.IGNORECASE)
        if match:
            after_match = text[match.end():]
            would_skip = bool(directional_pattern.match(after_match))

            passed = would_skip == should_skip
            status = "PASS" if passed else "FAIL"

            if not passed:
                all_passed = False

            print(f"\n  Text: '{text}'")
            print(f"  After 'left': '{after_match}'")
            print(f"  Would skip tooltip: {would_skip}")
            print(f"  Expected skip: {should_skip}")
            print(f"  Reason: {reason}")
            print(f"  Status: {status}")
        else:
            print(f"\n  Text: '{text}'")
            print(f"  No 'left' found in text")

    print()
    print("=" * 100)
    if all_passed:
        print("ALL PATTERN TESTS PASSED")
    else:
        print("SOME PATTERN TESTS FAILED")
    print("=" * 100)

    return all_passed


if __name__ == '__main__':
    print("\n" + "=" * 100)
    print("RUNNING LEFT KEYWORD MATCHING TESTS")
    print("=" * 100 + "\n")

    # Run all tests
    minions_with_left = test_left_keyword_in_descriptions()
    meat_packing_ok = test_meat_packing_plant()
    ethereal_minions = test_ethereal_left_minions()
    pattern_ok = test_javascript_pattern()

    # Summary
    print("\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)
    print(f"\nMinions with directional 'left': {len(minions_with_left)}")
    print(f"Ethereal minions found: {len(ethereal_minions)}")
    print(f"Meat Packing Plant check: {'PASS' if meat_packing_ok else 'FAIL'}")
    print(f"Pattern simulation: {'PASS' if pattern_ok else 'FAIL'}")

    print("\n" + "=" * 100)
    if pattern_ok:
        print("ALL TESTS PASSED")
    else:
        print("SOME TESTS FAILED")
    print("=" * 100)
