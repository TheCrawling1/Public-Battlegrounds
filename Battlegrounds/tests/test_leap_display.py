#!/usr/bin/env python3
"""
Test Leap display - verifies that all minions with the 'leap' keyword have
a leap_distance defined for proper frontend display.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from minions import MINIONS


def get_all_minions():
    """Get all minions from all tiers as a flat list"""
    all_minions = []
    for tier, minion_list in MINIONS.items():
        if isinstance(minion_list, list):
            all_minions.extend(minion_list)
    return all_minions


def test_leap_minions():
    """Test that all minions with leap keyword have leap_distance defined"""
    print("=" * 100)
    print("LEAP MINION TEST")
    print("=" * 100)
    print()
    print("Checking all minions with 'leap' keyword have 'leap_distance' defined")
    print()

    leap_minions = []
    missing_distance = []

    for minion in get_all_minions():
        keywords = minion.get('keywords', [])
        if 'leap' in keywords:
            name = minion['name']
            leap_distance = minion.get('leap_distance')
            tier = None
            # Find tier
            for t, tier_minions in MINIONS.items():
                if isinstance(tier_minions, list) and minion in tier_minions:
                    tier = t
                    break

            leap_minions.append({
                'name': name,
                'tier': tier,
                'leap_distance': leap_distance,
                'keywords': keywords
            })

            if leap_distance is None:
                missing_distance.append(name)

    print(f"Found {len(leap_minions)} minions with 'leap' keyword:")
    print("-" * 100)

    for m in leap_minions:
        status = "PASS" if m['leap_distance'] is not None else "MISSING"
        print(f"\n  [{status}] {m['name']} (Tier {m['tier']})")
        print(f"         Keywords: {m['keywords']}")
        print(f"         Leap Distance: {m['leap_distance']}")

    print()
    print("=" * 100)

    if missing_distance:
        print(f"FAIL: {len(missing_distance)} minions missing leap_distance:")
        for name in missing_distance:
            print(f"  - {name}")
        return False
    else:
        print("PASS: All leap minions have leap_distance defined")
        return True


def test_specific_minions():
    """Test specific minions mentioned by user"""
    print()
    print("=" * 100)
    print("SPECIFIC MINION CHECK (User Mentioned)")
    print("=" * 100)
    print()

    target_minions = ['Shinobi', 'Railway Cannon']
    all_minions = {m['name']: m for m in get_all_minions()}

    for name in target_minions:
        print(f"\nChecking {name}:")
        print("-" * 50)

        minion = all_minions.get(name)
        if not minion:
            print(f"  ERROR: Minion '{name}' not found!")
            continue

        keywords = minion.get('keywords', [])
        leap_distance = minion.get('leap_distance')
        has_leap = 'leap' in keywords

        print(f"  Keywords: {keywords}")
        print(f"  Has 'leap' keyword: {has_leap}")
        print(f"  leap_distance value: {leap_distance}")

        if has_leap:
            if leap_distance is not None:
                print(f"  Status: PASS - Should display as 'Leap {leap_distance}'")
            else:
                print(f"  Status: FAIL - Missing leap_distance!")
        else:
            print(f"  Status: N/A - No leap keyword")

    print()
    print("=" * 100)


def test_minion_serialization():
    """Test that minion data includes leap_distance when serialized"""
    print()
    print("=" * 100)
    print("SERIALIZATION CHECK")
    print("=" * 100)
    print()
    print("Checking that minion data properly includes leap_distance in all cases")
    print()

    # Test what gets sent to frontend (simulating the API)
    import copy
    from minions import MINIONS

    minion_info = {}
    for tier, tier_minions in MINIONS.items():
        for minion in tier_minions:
            name = minion['name']
            minion_copy = copy.deepcopy(minion)
            minion_copy['tier'] = tier
            minion_info[name] = minion_copy

    # Check leap minions in the serialized data
    leap_minions_in_api = []
    for name, minion in minion_info.items():
        keywords = minion.get('keywords', [])
        if 'leap' in keywords:
            leap_minions_in_api.append({
                'name': name,
                'leap_distance': minion.get('leap_distance'),
                'all_fields': list(minion.keys())
            })

    print(f"Leap minions in API response ({len(leap_minions_in_api)}):")
    print("-" * 100)

    for m in leap_minions_in_api:
        print(f"\n  {m['name']}:")
        print(f"    leap_distance: {m['leap_distance']}")
        has_leap_field = 'leap_distance' in m['all_fields']
        print(f"    'leap_distance' in fields: {has_leap_field}")

    print()
    print("=" * 100)


if __name__ == '__main__':
    print("\n" + "=" * 100)
    print("RUNNING LEAP DISPLAY TESTS")
    print("=" * 100 + "\n")

    test_specific_minions()
    all_pass = test_leap_minions()
    test_minion_serialization()

    print("\n" + "=" * 100)
    if all_pass:
        print("ALL TESTS PASSED")
    else:
        print("SOME TESTS FAILED")
    print("=" * 100)
