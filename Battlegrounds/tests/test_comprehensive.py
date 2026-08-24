"""
Comprehensive headless test - runs a large batch of games to verify
all game systems work end-to-end with both AI types and all heroes.
"""

import sys
import os
import io
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))


def run_comprehensive():
    from app import create_app
    app = create_app()

    with app.app_context():
        from headless_runner import HeadlessGameRunner, SmartDecisionAI, RandomDecisionAI
        from models import GhostBattle, db
        from config import MAX_GHOST_WINS

        results_all = []
        errors = []

        def run_batch(label, ai_factory, seeds, hero_id=None):
            batch = []
            for seed in seeds:
                ai = ai_factory()
                runner = HeadlessGameRunner(ai, seed=seed, hero_id=hero_id, verbose=False)

                old_stdout = sys.stdout
                sys.stdout = io.StringIO()
                try:
                    result = runner.run_complete_game()
                except Exception as e:
                    sys.stdout = old_stdout
                    errors.append(f"{label} seed={seed}: {e}")
                    print(f"    ERROR seed {seed}: {e}")
                    continue
                finally:
                    sys.stdout = old_stdout

                run_id = result['run_id']
                ghost_battles = GhostBattle.query.filter_by(run_id=run_id).all()
                ghost_results = [(gb.events_milestone, gb.winner) for gb in
                                 sorted(ghost_battles, key=lambda x: x.events_milestone)]

                result['label'] = label
                result['seed'] = seed
                result['ghost_results'] = ghost_results
                batch.append(result)
                results_all.append(result)

                status = "WIN" if result['result'] == 'victory' else result['result'].upper()[:5]
                print(f"    {status:>5} seed={seed:>5} | "
                      f"R{result['final_ring']} HP{result['final_health']:>2} | "
                      f"G {result['ghost_wins']}/{MAX_GHOST_WINS} | "
                      f"Ev {result['events_completed']:>3} | "
                      f"C {result['combat_wins']}/{result['combat_count']}")

            return batch

        # ── SmartAI, no hero (baseline) ──
        print("=" * 70)
        print(f"SmartAI, no hero (20 games)")
        print("=" * 70)
        smart_base = run_batch("SmartAI", SmartDecisionAI, range(9000, 9020))

        # ── SmartAI with each hero ──
        for hero in ['silas', 'puck', 'olimpia']:
            print(f"\n{'=' * 70}")
            print(f"SmartAI + {hero} (10 games)")
            print("=" * 70)
            run_batch(f"Smart+{hero}", SmartDecisionAI, range(9100, 9110), hero_id=hero)

        # ── RandomAI (fuzz test) ──
        print(f"\n{'=' * 70}")
        print(f"RandomAI (20 games)")
        print("=" * 70)
        run_batch("RandomAI", RandomDecisionAI, range(9200, 9220))

        # ── Summary ──
        print(f"\n{'=' * 70}")
        print("COMPREHENSIVE RESULTS")
        print(f"{'=' * 70}")

        from collections import Counter, defaultdict

        by_label = defaultdict(list)
        for r in results_all:
            by_label[r['label']].append(r)

        for label, batch in by_label.items():
            n = len(batch)
            wins = sum(1 for r in batch if r['result'] == 'victory')
            deaths = sum(1 for r in batch if r['result'] == 'death')
            timeouts = sum(1 for r in batch if r['result'] == 'timeout')
            avg_ghosts = sum(r['ghost_wins'] for r in batch) / n if n else 0
            avg_events = sum(r['events_completed'] for r in batch) / n if n else 0
            avg_health = sum(r['final_health'] for r in batch) / n if n else 0
            avg_ring = sum(r['final_ring'] for r in batch) / n if n else 0
            combat_wr = (sum(r['combat_wins'] for r in batch) /
                         max(1, sum(r['combat_count'] for r in batch))) * 100

            print(f"\n  {label:20s} ({n} games)")
            print(f"    Win/Death/Timeout: {wins}/{deaths}/{timeouts}")
            print(f"    Win rate:          {wins/n*100:.0f}%")
            print(f"    Avg ghost wins:    {avg_ghosts:.1f}/{MAX_GHOST_WINS}")
            print(f"    Avg events:        {avg_events:.0f}")
            print(f"    Avg final ring:    {avg_ring:.1f}")
            print(f"    Avg final HP:      {avg_health:.0f}")
            print(f"    Combat win rate:   {combat_wr:.0f}%")

        # ── Validation checks ──
        print(f"\n{'=' * 70}")
        print("VALIDATION")
        print(f"{'=' * 70}")

        issues = []

        # Check: every game ended properly
        for r in results_all:
            if r['result'] not in ('victory', 'death', 'timeout'):
                issues.append(f"Unexpected outcome: {r['result']} (seed {r['seed']})")

        # Check: victories have 7 ghost wins
        for r in results_all:
            if r['result'] == 'victory' and r['ghost_wins'] < MAX_GHOST_WINS:
                issues.append(f"Victory with only {r['ghost_wins']}/{MAX_GHOST_WINS} ghosts (seed {r['seed']})")

        # Check: deaths have 0 health
        for r in results_all:
            if r['result'] == 'death' and r['final_health'] > 0:
                issues.append(f"Death with {r['final_health']} HP remaining (seed {r['seed']})")

        # Check: at least some ghost battles occurred
        total_ghosts = sum(r['ghost_count'] for r in results_all)
        if total_ghosts == 0:
            issues.append("No ghost battles occurred in any game!")

        # Check: at least some combat events occurred
        total_combats = sum(r['combat_count'] for r in results_all)
        if total_combats == 0:
            issues.append("No combat events occurred in any game!")

        # Check: no timeouts (games should resolve)
        timeouts = sum(1 for r in results_all if r['result'] == 'timeout')
        if timeouts > 0:
            issues.append(f"{timeouts} game(s) timed out - possible infinite loop!")

        if errors:
            for e in errors:
                issues.append(f"CRASH: {e}")

        if issues:
            print(f"\n  ISSUES FOUND ({len(issues)}):")
            for issue in issues:
                print(f"    - {issue}")
        else:
            print(f"\n  ALL CHECKS PASSED")

        print(f"\n  Total games:    {len(results_all)}")
        print(f"  Total combats:  {total_combats}")
        print(f"  Total ghosts:   {total_ghosts}")
        print(f"  Errors/crashes: {len(errors)}")

        # Return for scripting
        return len(issues) == 0


if __name__ == '__main__':
    success = run_comprehensive()
    sys.exit(0 if success else 1)
