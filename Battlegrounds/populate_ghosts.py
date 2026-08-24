#!/usr/bin/env python3
"""
Ghost Population Runner - Populates the game database with ghost data
and provides comprehensive analysis of game outcomes.

Usage:
    python populate_ghosts.py                    # 50 games, default settings
    python populate_ghosts.py --games 200        # More games = more ghost variety
    python populate_ghosts.py --heroes           # Include hero-powered ghosts
    python populate_ghosts.py --clear            # Wipe existing ghosts first
    python populate_ghosts.py --analyze          # Full analysis of ghost DB + game results
    python populate_ghosts.py --stats            # Quick ghost DB summary

Examples:
    # Initial population for a fresh game
    python populate_ghosts.py --games 100 --heroes --analyze

    # Add more ghosts to existing pool
    python populate_ghosts.py --games 50

    # Deep analysis of what's in the database
    python populate_ghosts.py --analyze
"""

import sys
import os
import argparse
import time
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from collections import Counter, defaultdict

# ── Helpers ──

def _bar(value, max_val, width=30):
    """ASCII bar chart helper."""
    if max_val <= 0:
        return ''
    filled = int(value / max_val * width)
    return '#' * filled + '.' * (width - filled)


# ── Quick Stats ──

def show_stats(app):
    """Quick ghost database summary."""
    with app.app_context():
        from models import GhostSnapshot, GhostBattle, db
        from config import EVENTS_FOR_GHOST_BATTLE

        total = GhostSnapshot.query.count()
        print(f"\n  Total ghost snapshots: {total}")

        if total == 0:
            print("  (empty - run with --games N to populate)")
            return

        # By source tag
        sources = db.session.query(
            GhostSnapshot.source,
            db.func.count(GhostSnapshot.id)
        ).group_by(GhostSnapshot.source).all()

        print(f"\n  By source:")
        for src, count in sources:
            print(f"    {src or 'unknown':>10}: {count:>4}")

        # By milestone
        milestones = db.session.query(
            GhostSnapshot.events_milestone,
            db.func.count(GhostSnapshot.id)
        ).group_by(GhostSnapshot.events_milestone).order_by(
            GhostSnapshot.events_milestone
        ).all()

        print(f"\n  By milestone:")
        max_count = max(c for _, c in milestones) if milestones else 1
        for milestone, count in milestones:
            print(f"    {milestone:>4}s: {count:>4}  {_bar(count, max_count, 20)}")

        # By hero
        heroes = db.session.query(
            GhostSnapshot.hero_id,
            db.func.count(GhostSnapshot.id)
        ).group_by(GhostSnapshot.hero_id).all()

        print(f"\n  By hero:")
        for hero, count in heroes:
            print(f"    {hero or 'none':>10}: {count:>4}")

        # Power distribution
        avg_power = db.session.query(db.func.avg(GhostSnapshot.power_level)).scalar()
        min_power = db.session.query(db.func.min(GhostSnapshot.power_level)).scalar()
        max_power = db.session.query(db.func.max(GhostSnapshot.power_level)).scalar()

        print(f"\n  Power range: {min_power} - {max_power} (avg {avg_power:.0f})")

        # Battle stats
        total_battles = GhostBattle.query.count()
        player_wins = GhostBattle.query.filter_by(winner='player').count()
        ghost_wins = GhostBattle.query.filter_by(winner='ghost').count()
        draws = total_battles - player_wins - ghost_wins

        print(f"\n  Ghost battles: {total_battles} "
              f"(player wins {player_wins}, ghost wins {ghost_wins}, draws {draws})")


# ── Full Analysis ──

def show_analysis(app, game_results=None):
    """Comprehensive analysis of ghost database and game outcomes."""
    with app.app_context():
        from models import GhostSnapshot, GhostBattle, Run, db
        from config import MAX_GHOST_WINS, EVENTS_FOR_GHOST_BATTLE

        total_ghosts = GhostSnapshot.query.count()
        if total_ghosts == 0:
            print("\n  No ghosts in database. Run with --games N first.")
            return

        print(f"\n{'=' * 65}")
        print("GHOST DATABASE OVERVIEW")
        print(f"{'=' * 65}")
        show_stats(app)

        # ── Band Composition Analysis ──
        print(f"\n{'=' * 65}")
        print("BAND COMPOSITION ANALYSIS")
        print(f"{'=' * 65}")

        all_ghosts = GhostSnapshot.query.all()

        minion_freq = Counter()
        minion_by_milestone = defaultdict(Counter)
        keyword_freq = Counter()
        tribe_freq = Counter()
        band_sizes = Counter()
        combo_freq = Counter()
        hero_power = defaultdict(list)

        for ghost in all_ghosts:
            band = ghost.get_band()
            if not band:
                continue
            band_sizes[len(band)] += 1
            names = sorted([m['name'] for m in band])
            for m in band:
                minion_freq[m['name']] += 1
                minion_by_milestone[ghost.events_milestone][m['name']] += 1
                for kw in m.get('keywords', []):
                    keyword_freq[kw] += 1
                if m.get('tribe'):
                    tribe_freq[m['tribe']] += 1
            unique_names = sorted(set(names))
            for i in range(len(unique_names)):
                for j in range(i + 1, len(unique_names)):
                    combo_freq[(unique_names[i], unique_names[j])] += 1
            hero_power[ghost.hero_id or 'none'].append(ghost.power_level)

        # Most common minions
        print(f"\n  Most Common Minions (across all ghosts):")
        max_freq = minion_freq.most_common(1)[0][1] if minion_freq else 1
        for name, count in minion_freq.most_common(15):
            pct = count / total_ghosts * 100
            print(f"    {name:20s} {count:>4} ({pct:5.1f}%)  {_bar(count, max_freq, 20)}")

        # Keywords
        print(f"\n  Keywords:")
        for kw, count in keyword_freq.most_common(15):
            print(f"    {kw:20s} {count:>4}")

        # Tribes
        if tribe_freq:
            print(f"\n  Tribes:")
            for tribe, count in tribe_freq.most_common():
                print(f"    {tribe:20s} {count:>4}")

        # Band sizes
        print(f"\n  Band Sizes:")
        for size in sorted(band_sizes.keys()):
            print(f"    {size} minions: {band_sizes[size]:>4}")

        # ── Best Combos ──
        print(f"\n{'=' * 65}")
        print("BEST MINION COMBOS (most common pairs)")
        print(f"{'=' * 65}")

        for (a, b), count in combo_freq.most_common(15):
            if count >= 3:
                print(f"    {a:15s} + {b:15s}  seen {count}x")

        # ── Milestone Progression ──
        print(f"\n{'=' * 65}")
        print("MILESTONE PROGRESSION (what appears when)")
        print(f"{'=' * 65}")

        milestones_sorted = sorted(minion_by_milestone.keys())
        for ms in milestones_sorted[:6]:
            mc = minion_by_milestone[ms]
            total_at_ms = GhostSnapshot.query.filter_by(events_milestone=ms).count()
            print(f"\n  {ms}s ({total_at_ms} ghosts):")
            for name, count in mc.most_common(8):
                pct = count / total_at_ms * 100
                print(f"    {name:20s} {count:>3} ({pct:4.0f}%)")

        # ── Strongest Ghosts ──
        print(f"\n{'=' * 65}")
        print("STRONGEST GHOSTS (top 10 by power)")
        print(f"{'=' * 65}")

        strongest = GhostSnapshot.query.order_by(
            GhostSnapshot.power_level.desc()
        ).limit(10).all()

        for i, g in enumerate(strongest):
            band = g.get_band()
            src = g.source or '?'
            print(f"\n  #{i+1} | Power {g.power_level} | {g.events_milestone}s | "
                  f"Ring {g.current_ring} | Hero: {g.hero_id or 'none'} | [{src}]")
            for m in band:
                kws = ','.join(m.get('keywords', []))
                print(f"       {m['name']:15s} {m.get('attack',0):>2}/{m.get('health',0):>2}  {kws}")

        # ── Hero Comparison from ghost DB ──
        print(f"\n{'=' * 65}")
        print("HERO COMPARISON (ghost DB)")
        print(f"{'=' * 65}")

        for hero_id in ['silas', 'puck', 'olimpia']:
            powers = hero_power.get(hero_id, [])
            if not powers:
                continue
            avg_p = sum(powers) / len(powers)
            max_p = max(powers)
            print(f"\n  {hero_id:>10}: {len(powers)} ghosts, "
                  f"avg power {avg_p:.0f}, max power {max_p}")

        # ── Ghost Battle Results ──
        print(f"\n{'=' * 65}")
        print("GHOST BATTLE RESULTS")
        print(f"{'=' * 65}")

        total_battles = GhostBattle.query.count()
        if total_battles > 0:
            battle_milestones = db.session.query(
                GhostBattle.events_milestone
            ).distinct().order_by(GhostBattle.events_milestone).all()

            print(f"\n  Win rate by milestone:")
            for (ms,) in battle_milestones:
                ms_total = GhostBattle.query.filter_by(events_milestone=ms).count()
                ms_player_wins = GhostBattle.query.filter_by(
                    events_milestone=ms, winner='player').count()
                wr = ms_player_wins / ms_total * 100 if ms_total > 0 else 0
                print(f"    {ms:>4}s: {ms_player_wins:>3}/{ms_total:>3} player wins "
                      f"({wr:4.0f}%)  {_bar(wr, 100, 20)}")

        # ── Game Results Analysis ──
        if game_results:
            _show_game_results_analysis(game_results, MAX_GHOST_WINS, GhostSnapshot)


def _show_game_results_analysis(game_results, max_ghost_wins, GhostSnapshot):
    """Deep analysis of headless game results with journeys, MVPs, and combat breakdowns."""

    total = len(game_results)
    victories = [r for r in game_results if r['result'] == 'victory']
    deaths = [r for r in game_results if r['result'] == 'death']

    # ==================================================================
    # OVERALL RESULTS
    # ==================================================================
    print(f"\n{'=' * 65}")
    print(f"GAME RESULTS ({total} games)")
    print(f"{'=' * 65}")

    outcomes = Counter(r['result'] for r in game_results)
    for outcome, count in outcomes.most_common():
        pct = count / total * 100
        print(f"    {outcome:>10}: {count:>3} ({pct:.0f}%)")

    avg_events = sum(r['events_completed'] for r in game_results) / total
    avg_ring = sum(r['final_ring'] for r in game_results) / total
    avg_ghost_wins = sum(r['ghost_wins'] for r in game_results) / total
    total_combats = sum(r['combat_count'] for r in game_results)
    total_combat_wins = sum(r['combat_wins'] for r in game_results)
    combat_wr = total_combat_wins / max(1, total_combats) * 100

    print(f"\n  Averages:")
    print(f"    Events survived:  {avg_events:.0f}")
    print(f"    Ring reached:     {avg_ring:.1f}")
    print(f"    Ghost wins:       {avg_ghost_wins:.1f}/{max_ghost_wins}")
    print(f"    NPC Combat WR:    {combat_wr:.0f}% ({total_combat_wins}/{total_combats})")

    # ==================================================================
    # HERO WIN RATES
    # ==================================================================
    print(f"\n{'=' * 65}")
    print("HERO PERFORMANCE")
    print(f"{'=' * 65}")

    by_hero = defaultdict(list)
    for r in game_results:
        hero = r.get('label', '').split('+')[-1] if '+' in r.get('label', '') else 'unknown'
        by_hero[hero].append(r)

    for hero in ['silas', 'puck', 'olimpia']:
        batch = by_hero.get(hero, [])
        if not batch:
            continue
        n = len(batch)
        wins = sum(1 for r in batch if r['result'] == 'victory')
        avg_gw = sum(r['ghost_wins'] for r in batch) / n
        avg_ev = sum(r['events_completed'] for r in batch) / n
        avg_rng = sum(r['final_ring'] for r in batch) / n
        c_total = sum(r['combat_count'] for r in batch)
        c_wins = sum(r['combat_wins'] for r in batch)
        c_wr = c_wins / max(1, c_total) * 100

        # Ghost battle win rate from actions_log
        gb_wins = 0
        gb_total = 0
        for r in batch:
            for a in r.get('actions_log', []):
                if isinstance(a, dict) and a.get('combat_type') == 'ghost_battle':
                    gb_total += 1
                    if a.get('winner') == 'player':
                        gb_wins += 1
        gb_wr = gb_wins / max(1, gb_total) * 100

        best_game = max(batch, key=lambda r: (r['ghost_wins'], r['events_completed']))

        print(f"\n  {hero.upper()} ({n} games):")
        print(f"    Victory rate:     {wins}/{n} ({wins/n*100:.0f}%)")
        print(f"    Ghost wins:       {avg_gw:.1f}/{max_ghost_wins} avg")
        print(f"    Ghost battle WR:  {gb_wr:.0f}% ({gb_wins}/{gb_total})")
        print(f"    NPC combat WR:    {c_wr:.0f}% ({c_wins}/{c_total})")
        print(f"    Avg events:       {avg_ev:.0f}")
        print(f"    Avg ring:         {avg_rng:.1f}")
        print(f"    Best run:         {best_game['ghost_wins']}W ghost, "
              f"ring {best_game['final_ring']}, {best_game['events_completed']} events")

    # ==================================================================
    # COMBAT BREAKDOWN
    # ==================================================================
    print(f"\n{'=' * 65}")
    print("COMBAT BREAKDOWN")
    print(f"{'=' * 65}")

    combat_stats = defaultdict(lambda: {'wins': 0, 'losses': 0, 'total_dmg': 0})
    for r in game_results:
        for a in r.get('actions_log', []):
            if not isinstance(a, dict) or a.get('action') != 'combat':
                continue
            ct = a.get('combat_type', 'unknown')
            if a.get('winner') == 'player':
                combat_stats[ct]['wins'] += 1
            else:
                combat_stats[ct]['losses'] += 1
            combat_stats[ct]['total_dmg'] += a.get('damage_taken', 0)

    for ct in ['combat_event', 'combat_event_hard', 'ghost_battle']:
        s = combat_stats.get(ct)
        if not s:
            continue
        t = s['wins'] + s['losses']
        wr = s['wins'] / max(1, t) * 100
        avg_dmg = s['total_dmg'] / max(1, t)
        label = {'combat_event': 'Normal NPC', 'combat_event_hard': 'Hard NPC',
                 'ghost_battle': 'Ghost Battle'}.get(ct, ct)
        print(f"\n  {label}:")
        print(f"    Win rate:      {wr:.0f}% ({s['wins']}W / {s['losses']}L)")
        print(f"    Avg dmg taken: {avg_dmg:.1f} HP per fight")

    # ==================================================================
    # STRONGEST MINIONS (MVP Analysis)
    # ==================================================================
    print(f"\n{'=' * 65}")
    print("STRONGEST MINIONS (MVP ANALYSIS)")
    print(f"{'=' * 65}")

    # Track minions in final bands of victories vs deaths
    win_minions = Counter()
    death_minions = Counter()
    # Track minion stats at peak from late-game snapshots
    minion_peak_stats = {}
    late_game_minions = Counter()

    for r in game_results:
        band = r.get('final_band', [])
        for m in band:
            name = m['name']
            if r['result'] == 'victory':
                win_minions[name] += 1
            else:
                death_minions[name] += 1

    # From ghost snapshots at later milestones
    late_ghosts = GhostSnapshot.query.filter(
        GhostSnapshot.events_milestone >= 40
    ).all()
    for g in late_ghosts:
        band = g.get_band()
        for m in band:
            name = m['name']
            late_game_minions[name] += 1
            power = m.get('attack', 0) + m.get('health', 0)
            if power > (minion_peak_stats.get(name, (0, 0, []))[0] +
                        minion_peak_stats.get(name, (0, 0, []))[1]):
                minion_peak_stats[name] = (
                    m.get('attack', 0), m.get('health', 0),
                    m.get('keywords', [])
                )

    # Victory MVPs
    if victories:
        print(f"\n  Victory MVPs (minions in winning final bands):")
        for name, count in win_minions.most_common(10):
            pct = count / len(victories) * 100
            peak = minion_peak_stats.get(name)
            stats_str = f" (peak {peak[0]}/{peak[1]})" if peak else ""
            print(f"    {name:20s}  in {count}/{len(victories)} wins ({pct:.0f}%){stats_str}")
    else:
        print(f"\n  No victories to analyze MVPs from.")

    # Late-game survivors
    if late_game_minions:
        print(f"\n  Late-Game Survivors (in bands at milestone 40+):")
        for name, count in late_game_minions.most_common(15):
            peak = minion_peak_stats.get(name)
            kws = ','.join(peak[2]) if peak else ''
            stats_str = f" {peak[0]:>2}/{peak[1]:>2}" if peak else ""
            print(f"    {name:20s} {count:>3} appearances{stats_str}  {kws}")

    # Highest peak stats
    if minion_peak_stats:
        print(f"\n  Highest Peak Stats (from late-game snapshots):")
        by_power = sorted(minion_peak_stats.items(),
                         key=lambda x: x[1][0] + x[1][1], reverse=True)
        for name, (atk, hp, kws) in by_power[:15]:
            kw_str = ','.join(kws) if kws else '-'
            print(f"    {name:20s} {atk:>3}/{hp:>3}  {kw_str}")

    # ==================================================================
    # KEYWORD PERFORMANCE
    # ==================================================================
    print(f"\n{'=' * 65}")
    print("KEYWORD PERFORMANCE")
    print(f"{'=' * 65}")

    kw_in_wins = Counter()
    kw_in_losses = Counter()
    for r in game_results:
        band = r.get('final_band', [])
        seen_kws = set()
        for m in band:
            for kw in m.get('keywords', []):
                seen_kws.add(kw)
        for kw in seen_kws:
            if r['result'] == 'victory':
                kw_in_wins[kw] += 1
            else:
                kw_in_losses[kw] += 1

    all_kws = set(kw_in_wins.keys()) | set(kw_in_losses.keys())
    if all_kws and victories:
        kw_rates = []
        for kw in all_kws:
            w = kw_in_wins.get(kw, 0)
            l = kw_in_losses.get(kw, 0)
            t = w + l
            if t >= 3:
                kw_rates.append((kw, w, l, t, w / t * 100))
        kw_rates.sort(key=lambda x: -x[4])

        print(f"\n  Keywords in final bands (min 3 appearances):")
        for kw, w, l, t, wr in kw_rates:
            print(f"    {kw:20s}  {w}W/{l}L  ({wr:.0f}% win rate)")
    elif all_kws:
        print(f"\n  Keywords in final bands (no victories for win rate):")
        for kw, count in sorted(kw_in_losses.items(), key=lambda x: -x[1])[:15]:
            print(f"    {kw:20s}  {count} games")

    # ==================================================================
    # GAME JOURNEYS (Notable runs)
    # ==================================================================
    print(f"\n{'=' * 65}")
    print("NOTABLE GAME JOURNEYS")
    print(f"{'=' * 65}")

    # Sort by ghost wins desc, then events desc
    ranked = sorted(game_results, key=lambda r: (
        r['result'] == 'victory',
        r['ghost_wins'],
        r['events_completed']
    ), reverse=True)

    for i, r in enumerate(ranked[:5]):
        hero = r.get('label', '').split('+')[-1] if '+' in r.get('label', '') else '?'
        outcome_icon = 'VICTORY' if r['result'] == 'victory' else 'DEATH'

        # Count ghost battle wins/losses from battle records
        gb_results = r.get('ghost_battle_results', [])
        gb_w = sum(1 for b in gb_results if b['winner'] == 'player')
        gb_l = sum(1 for b in gb_results if b['winner'] == 'ghost')

        print(f"\n  #{i+1} [{outcome_icon}] {hero.upper()} "
              f"(seed {r.get('seed', '?')})")
        print(f"    Ghosts: {gb_w}W/{gb_l}L | Ring {r['final_ring']} | "
              f"HP {r['final_health']} | {r['events_completed']} events | "
              f"NPC combats: {r['combat_wins']}W/{r['combat_count'] - r['combat_wins']}L")

        # Show final band
        band = r.get('final_band', [])
        if band:
            band_str = ', '.join(f"{m['name']} {m.get('attack',0)}/{m.get('health',0)}"
                                for m in band)
            print(f"    Final band: {band_str}")

        # Ghost battle journey from actions_log
        ghost_results = []
        for a in r.get('actions_log', []):
            if isinstance(a, dict) and a.get('combat_type') == 'ghost_battle':
                ghost_results.append(a)

        if ghost_results:
            journey = []
            for gb in ghost_results:
                w = 'W' if gb.get('winner') == 'player' else 'L'
                bp = gb.get('band_power', '?')
                hp = gb.get('health', '?')
                journey.append(f"{w}(pow:{bp} hp:{hp})")
            print(f"    Ghost journey: {' -> '.join(journey)}")

        # Health trajectory
        health_points = []
        for a in r.get('actions_log', []):
            if isinstance(a, dict) and 'health' in a:
                health_points.append(a['health'])
        if health_points:
            indices = [0, len(health_points)//4, len(health_points)//2,
                      3*len(health_points)//4, len(health_points)-1]
            indices = sorted(set(i for i in indices if 0 <= i < len(health_points)))
            hp_trace = [str(health_points[i]) for i in indices]
            print(f"    HP trajectory: {' -> '.join(hp_trace)}")

    # ==================================================================
    # BAND EVOLUTION
    # ==================================================================
    print(f"\n{'=' * 65}")
    print("BAND EVOLUTION (how bands change over milestones)")
    print(f"{'=' * 65}")

    minions_added = Counter()
    minions_removed = Counter()
    for r in game_results:
        for a in r.get('actions_log', []):
            if not isinstance(a, dict):
                continue
            for m in a.get('minions_added', []):
                minions_added[m] += 1
            for m in a.get('minions_removed', []):
                minions_removed[m] += 1

    if minions_added:
        print(f"\n  Most Recruited:")
        for name, count in minions_added.most_common(10):
            print(f"    {name:20s}  recruited {count}x")

    if minions_removed:
        print(f"\n  Most Replaced (sold/swapped):")
        for name, count in minions_removed.most_common(10):
            print(f"    {name:20s}  removed {count}x")

    # Net retention
    all_minion_names = set(minions_added.keys()) | set(minions_removed.keys())
    retention = {}
    for name in all_minion_names:
        added = minions_added.get(name, 0)
        removed = minions_removed.get(name, 0)
        retention[name] = added - removed

    keepers = sorted(retention.items(), key=lambda x: -x[1])
    dumped = sorted(retention.items(), key=lambda x: x[1])

    if keepers:
        print(f"\n  Most Kept (recruited >> removed):")
        for name, net in keepers[:8]:
            if net > 0:
                print(f"    {name:20s}  net +{net}")

    if dumped:
        print(f"\n  Most Dumped (removed >> recruited):")
        for name, net in dumped[:8]:
            if net < 0:
                print(f"    {name:20s}  net {net}")

    # ==================================================================
    # EVENT DISTRIBUTION
    # ==================================================================
    print(f"\n{'=' * 65}")
    print("EVENTS ENCOUNTERED")
    print(f"{'=' * 65}")

    event_types = Counter()
    for r in game_results:
        for ev in r.get('events_log', []):
            if isinstance(ev, dict):
                event_types[ev.get('event', 'unknown')] += 1
            elif isinstance(ev, str):
                event_types[ev] += 1

    if event_types:
        for ev, count in event_types.most_common(20):
            avg_per_game = count / total
            print(f"    {ev:25s} {count:>4} total ({avg_per_game:.1f}/game)")


# ── Clear ──

def clear_ghosts(app):
    """Clear all ghost data."""
    with app.app_context():
        from models import GhostSnapshot, GhostBattle, db
        GhostBattle.query.delete()
        GhostSnapshot.query.delete()
        db.session.commit()
        print("  Cleared all ghost snapshots and battle records.")


# ── Populate ──

def populate(app, num_games, include_heroes, seed_start):
    """Run headless games to populate ghost database. Returns game results for analysis."""
    with app.app_context():
        from headless_runner import HeadlessGameRunner, SmartDecisionAI, RandomDecisionAI
        from models import GhostSnapshot, GhostBattle, db
        from config import MAX_GHOST_WINS

        # Always run with heroes - split evenly across silas, puck, olimpia
        per_hero = num_games // 3
        remainder = num_games - (per_hero * 3)
        configs = [
            ('Smart+silas', SmartDecisionAI, 'silas', per_hero + remainder),
            ('Smart+puck', SmartDecisionAI, 'puck', per_hero),
            ('Smart+olimpia', SmartDecisionAI, 'olimpia', per_hero),
        ]

        game_results = []
        ghosts_before = GhostSnapshot.query.count()

        seed = seed_start
        start_time = time.time()

        for label, ai_class, hero_id, count in configs:
            print(f"\n  {label} ({count} games):")

            for i in range(count):
                ai = ai_class()
                # Mix health values: 60% at default 30 HP (realistic), 40% at 50 HP (reach later milestones)
                # This creates a representative ghost pool at early milestones while still populating later ones
                hp = 30 if (i % 5) < 3 else 50
                runner = HeadlessGameRunner(
                    ai, seed=seed, hero_id=hero_id,
                    verbose=False, quiet_engine=True,
                    starting_health=hp
                )
                result = runner.run_complete_game()
                result['label'] = label
                result['seed'] = seed

                # Capture ghost battles for this run
                battles = GhostBattle.query.filter_by(run_id=result['run_id']).all()
                result['ghost_battle_results'] = [
                    {'milestone': b.events_milestone, 'winner': b.winner}
                    for b in battles
                ]

                game_results.append(result)

                if (i + 1) % 10 == 0 or i == count - 1:
                    elapsed = time.time() - start_time
                    total = len(game_results)
                    rate = total / elapsed if elapsed > 0 else 0
                    print(f"    {i+1:>4}/{count} done "
                          f"({rate:.1f} games/sec)")

                seed += 1

        ghosts_after = GhostSnapshot.query.count()
        elapsed = time.time() - start_time
        total_games = len(game_results)
        total_wins = sum(1 for r in game_results if r['result'] == 'victory')
        total_deaths = sum(1 for r in game_results if r['result'] == 'death')

        print(f"\n{'=' * 65}")
        print(f"POPULATION COMPLETE")
        print(f"{'=' * 65}")
        print(f"  Games run:        {total_games}")
        print(f"  Wins/Deaths:      {total_wins}/{total_deaths}")
        print(f"  Time:             {elapsed:.1f}s ({total_games/elapsed:.1f} games/sec)")
        print(f"  New ghosts added: {ghosts_after - ghosts_before}")
        print(f"  Total ghosts:     {ghosts_after}")

        return game_results


# ── Main ──

def main():
    parser = argparse.ArgumentParser(
        description='Populate ghost database for Battleground game testing'
    )
    parser.add_argument('--games', type=int, default=50,
                        help='Number of games to run (default: 50)')
    parser.add_argument('--heroes', action='store_true',
                        help='Include hero-powered games (silas, puck, olimpia)')
    parser.add_argument('--clear', action='store_true',
                        help='Clear existing ghosts before populating')
    parser.add_argument('--analyze', action='store_true',
                        help='Full analysis of ghost DB and game results')
    parser.add_argument('--stats', action='store_true',
                        help='Quick ghost database summary only')
    parser.add_argument('--seed', type=int, default=10000,
                        help='Starting seed for reproducibility (default: 10000)')
    args = parser.parse_args()

    from app import create_app
    app = create_app()

    print("=" * 65)
    print("BATTLEGROUND GHOST POPULATION TOOL")
    print("=" * 65)

    if args.stats:
        show_stats(app)
        return

    if args.analyze and args.games == 50 and not args.clear:
        # Just analyze existing data
        show_analysis(app)
        return

    if args.clear:
        print("\nClearing existing ghosts...")
        clear_ghosts(app)

    print(f"\nRunning {args.games} games to populate ghosts...")
    if args.heroes:
        print("  (including hero variants)")

    game_results = populate(app, args.games, args.heroes, args.seed)

    if args.analyze:
        show_analysis(app, game_results)
    else:
        print("\nGhost database stats:")
        show_stats(app)


if __name__ == '__main__':
    main()
