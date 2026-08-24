"""
Dev Ghosts Routes - Ghost analysis dashboard for development

Provides API endpoints for viewing ghost database statistics,
band composition analysis, milestone progression, and battle results.
"""

import threading
import time
import traceback as tb_module

from flask import Blueprint, request, jsonify
from collections import Counter, defaultdict

dev_ghosts_api = Blueprint('dev_ghosts_api', __name__)
# Restrict all dev ghost endpoints to localhost
from rate_limit import localhost_only
dev_ghosts_api.before_request(localhost_only)


# ---------------------------------------------------------------------------
# Background populate job state
# ---------------------------------------------------------------------------
_populate_job = {
    'running': False,
    'cancel_requested': False,
    'total_games': 0,
    'completed_games': 0,
    'current_game': None,      # label of game currently running
    'results': [],             # per-game result summaries
    'errors': [],              # per-game errors
    'start_time': None,
    'end_time': None,
    'final_summary': None,     # set when job finishes
    'thread': None,
}


def _serialize_band(band):
    """Serialize a band for API responses with full minion data."""
    return [
        {
            'name': m.get('name', 'Unknown'),
            'attack': m.get('attack', 0),
            'health': m.get('health', 0),
            'keywords': m.get('keywords', []),
            'golden': m.get('golden', False),
            'type': m.get('type', ''),
            'tier': m.get('tier', 1),
            'image': m.get('image', ''),
        }
        for m in (band or [])
    ]


@dev_ghosts_api.route('/stats', methods=['GET'])
def ghost_stats():
    """Quick ghost database summary."""
    try:
        from models import GhostSnapshot, GhostBattle, db

        total = GhostSnapshot.query.count()
        if total == 0:
            return jsonify({'success': True, 'total': 0, 'empty': True})

        # By source
        sources = db.session.query(
            GhostSnapshot.source,
            db.func.count(GhostSnapshot.id)
        ).group_by(GhostSnapshot.source).all()
        source_data = {src or 'unknown': count for src, count in sources}

        # By milestone
        milestones = db.session.query(
            GhostSnapshot.events_milestone,
            db.func.count(GhostSnapshot.id)
        ).group_by(GhostSnapshot.events_milestone).order_by(
            GhostSnapshot.events_milestone
        ).all()
        milestone_data = [{'milestone': ms, 'count': c} for ms, c in milestones]

        # By hero
        heroes = db.session.query(
            GhostSnapshot.hero_id,
            db.func.count(GhostSnapshot.id)
        ).group_by(GhostSnapshot.hero_id).all()
        hero_data = {hero or 'none': count for hero, count in heroes}

        # Power distribution
        avg_power = db.session.query(db.func.avg(GhostSnapshot.power_level)).scalar() or 0
        min_power = db.session.query(db.func.min(GhostSnapshot.power_level)).scalar() or 0
        max_power = db.session.query(db.func.max(GhostSnapshot.power_level)).scalar() or 0

        # Battle stats
        total_battles = GhostBattle.query.count()
        player_wins = GhostBattle.query.filter_by(winner='player').count()
        ghost_wins = GhostBattle.query.filter_by(winner='ghost').count()

        return jsonify({
            'success': True,
            'total': total,
            'sources': source_data,
            'milestones': milestone_data,
            'heroes': hero_data,
            'power': {
                'min': min_power,
                'max': max_power,
                'avg': round(avg_power, 1)
            },
            'battles': {
                'total': total_battles,
                'player_wins': player_wins,
                'ghost_wins': ghost_wins,
                'draws': total_battles - player_wins - ghost_wins
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@dev_ghosts_api.route('/analysis', methods=['GET'])
def ghost_analysis():
    """Full band composition and combo analysis."""
    try:
        from models import GhostSnapshot, GhostBattle, db

        all_ghosts = GhostSnapshot.query.all()
        total = len(all_ghosts)
        if total == 0:
            return jsonify({'success': True, 'total': 0, 'empty': True})

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
                if m.get('type'):
                    t = m['type']
                    if isinstance(t, list):
                        for tribe in t:
                            tribe_freq[tribe] += 1
                    elif isinstance(t, str) and ',' in t:
                        for tribe in t.split(','):
                            tribe_freq[tribe.strip()] += 1
                    else:
                        tribe_freq[t] += 1

            unique_names = sorted(set(names))
            for i in range(len(unique_names)):
                for j in range(i + 1, len(unique_names)):
                    combo_freq[(unique_names[i], unique_names[j])] += 1

            hero_power[ghost.hero_id or 'none'].append(ghost.power_level)

        # Minions
        minions = [
            {'name': name, 'count': count, 'pct': round(count / total * 100, 1)}
            for name, count in minion_freq.most_common(20)
        ]

        # Keywords
        keywords = [
            {'name': kw, 'count': count}
            for kw, count in keyword_freq.most_common(20)
        ]

        # Tribes
        tribes = [
            {'name': tribe, 'count': count}
            for tribe, count in tribe_freq.most_common()
        ]

        # Band sizes
        sizes = [
            {'size': size, 'count': band_sizes[size]}
            for size in sorted(band_sizes.keys())
        ]

        # Combos
        combos = [
            {'minion_a': a, 'minion_b': b, 'count': count}
            for (a, b), count in combo_freq.most_common(20)
            if count >= 2
        ]

        # Milestone progression
        milestone_progression = []
        for ms in sorted(minion_by_milestone.keys())[:8]:
            mc = minion_by_milestone[ms]
            ms_total = sum(1 for g in all_ghosts if g.events_milestone == ms)
            top_minions = [
                {'name': name, 'count': count, 'pct': round(count / ms_total * 100)}
                for name, count in mc.most_common(8)
            ]
            milestone_progression.append({
                'milestone': ms,
                'ghost_count': ms_total,
                'top_minions': top_minions
            })

        # Strongest ghosts
        strongest = GhostSnapshot.query.order_by(
            GhostSnapshot.power_level.desc()
        ).limit(10).all()
        strongest_data = []
        for g in strongest:
            band = g.get_band()
            strongest_data.append({
                'id': g.id,
                'power': g.power_level,
                'milestone': g.events_milestone,
                'ring': g.current_ring,
                'hero': g.hero_id or 'none',
                'source': g.source or 'unknown',
                'player_name': g.player_name,
                'band': _serialize_band(band),
            })

        # Hero comparison
        hero_comparison = []
        for hero_id in sorted(hero_power.keys()):
            powers = hero_power[hero_id]
            hero_comparison.append({
                'hero': hero_id,
                'count': len(powers),
                'avg_power': round(sum(powers) / len(powers), 1),
                'max_power': max(powers),
                'min_power': min(powers)
            })

        # Battle results by milestone
        battle_milestones = db.session.query(
            GhostBattle.events_milestone
        ).distinct().order_by(GhostBattle.events_milestone).all()

        battle_results = []
        for (ms,) in battle_milestones:
            ms_total = GhostBattle.query.filter_by(events_milestone=ms).count()
            ms_player_wins = GhostBattle.query.filter_by(
                events_milestone=ms, winner='player').count()
            ms_ghost_wins = GhostBattle.query.filter_by(
                events_milestone=ms, winner='ghost').count()
            battle_results.append({
                'milestone': ms,
                'total': ms_total,
                'player_wins': ms_player_wins,
                'ghost_wins': ms_ghost_wins,
                'win_rate': round(ms_player_wins / ms_total * 100, 1) if ms_total > 0 else 0
            })

        return jsonify({
            'success': True,
            'total': total,
            'minions': minions,
            'keywords': keywords,
            'tribes': tribes,
            'band_sizes': sizes,
            'combos': combos,
            'milestone_progression': milestone_progression,
            'strongest': strongest_data,
            'hero_comparison': hero_comparison,
            'battle_results': battle_results
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@dev_ghosts_api.route('/ghosts', methods=['GET'])
def list_ghosts():
    """List ghosts with optional filtering."""
    try:
        from models import GhostSnapshot

        query = GhostSnapshot.query

        # Filters
        source = request.args.get('source')
        if source:
            query = query.filter_by(source=source)

        milestone = request.args.get('milestone', type=int)
        if milestone is not None:
            query = query.filter_by(events_milestone=milestone)

        hero = request.args.get('hero')
        if hero:
            if hero == 'none':
                query = query.filter(GhostSnapshot.hero_id.is_(None))
            else:
                query = query.filter_by(hero_id=hero)

        # Sort
        sort = request.args.get('sort', 'power')
        if sort == 'power':
            query = query.order_by(GhostSnapshot.power_level.desc())
        elif sort == 'milestone':
            query = query.order_by(GhostSnapshot.events_milestone.asc())
        elif sort == 'recent':
            query = query.order_by(GhostSnapshot.created_at.desc())

        # Pagination
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 25, type=int)
        per_page = min(per_page, 100)

        paginated = query.paginate(page=page, per_page=per_page, error_out=False)

        ghosts = []
        for g in paginated.items:
            band = g.get_band() or []
            ghosts.append({
                'id': g.id,
                'power': g.power_level,
                'milestone': g.events_milestone,
                'ring': g.current_ring,
                'hero': g.hero_id or 'none',
                'source': g.source or 'unknown',
                'player_name': g.player_name,
                'health': g.health,
                'ghost_wins': g.ghost_wins_at_capture,
                'ghost_losses': g.ghost_losses_at_capture,
                'band_size': len(band),
                'has_actions': bool(g.actions_log),
                'band': _serialize_band(band),
            })

        return jsonify({
            'success': True,
            'ghosts': ghosts,
            'total': paginated.total,
            'pages': paginated.pages,
            'page': page,
            'per_page': per_page
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@dev_ghosts_api.route('/ghost/<int:ghost_id>', methods=['GET'])
def ghost_detail(ghost_id):
    """Get full ghost detail including actions log."""
    try:
        from models import GhostSnapshot

        g = GhostSnapshot.query.get(ghost_id)
        if not g:
            return jsonify({'success': False, 'error': 'Ghost not found'}), 404

        band = g.get_band() or []
        actions = g.get_actions_log()

        return jsonify({
            'success': True,
            'ghost': {
                'id': g.id,
                'power': g.power_level,
                'milestone': g.events_milestone,
                'ring': g.current_ring,
                'hero': g.hero_id or 'none',
                'source': g.source or 'unknown',
                'player_name': g.player_name,
                'health': g.health,
                'ghost_wins': g.ghost_wins_at_capture,
                'ghost_losses': g.ghost_losses_at_capture,
                'band': _serialize_band(band),
                'actions': actions,
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


def _run_populate_job(app, num_games, seed_start, ai_type, clear_first):
    """Background worker that runs headless games one at a time."""
    global _populate_job
    with app.app_context():
        try:
            import os
            from models import GhostSnapshot, GhostBattle, db
            from headless_runner import (HeadlessGameRunner, SmartDecisionAI,
                                         SimulatingDecisionAI, FullSimulationAI)

            # Create timestamped log directory for this batch
            log_dir = os.path.join(
                os.path.dirname(__file__), 'instance', 'headless_logs',
                time.strftime('%Y%m%d_%H%M%S')
            )

            if clear_first:
                GhostBattle.query.delete()
                GhostSnapshot.query.delete()
                db.session.commit()

            ghosts_before = GhostSnapshot.query.count()

            if ai_type == 'smart':
                ai_class_to_use = SmartDecisionAI
                ai_label = 'Smart'
            elif ai_type == 'simulating':
                ai_class_to_use = SimulatingDecisionAI
                ai_label = 'Simulating'
            else:
                ai_class_to_use = FullSimulationAI
                ai_label = 'FullSim'

            per_hero = num_games // 3
            remainder = num_games - (per_hero * 3)
            configs = [
                (f'{ai_label}+silas', ai_class_to_use, 'silas', per_hero + remainder),
                (f'{ai_label}+puck', ai_class_to_use, 'puck', per_hero),
                (f'{ai_label}+olimpia', ai_class_to_use, 'olimpia', per_hero),
            ]

            seed = seed_start
            game_idx = 0

            for label, ai_class, hero_id, count in configs:
                for i in range(count):
                    if _populate_job['cancel_requested']:
                        break

                    game_idx += 1
                    _populate_job['current_game'] = f"{label} (seed {seed})"
                    _populate_job['completed_games'] = game_idx - 1

                    try:
                        ai = ai_class()
                        runner = HeadlessGameRunner(
                            ai, seed=seed, hero_id=hero_id,
                            verbose=False, quiet_engine=True,
                            max_time=120.0,
                            cancel_check=lambda: _populate_job['cancel_requested'],
                            log_dir=log_dir,
                        )
                        result = runner.run_complete_game()
                        result['label'] = label

                        game_entry = {
                            'game': game_idx,
                            'label': label,
                            'seed': seed,
                            'hero': hero_id,
                            'result': result['result'],
                            'ghost_wins': result.get('ghost_wins', 0),
                            'events': result.get('events_completed', 0),
                            'health': result.get('final_health', 0),
                            'elapsed': result.get('elapsed', 0),
                            'error': result.get('error'),
                            'log_file': os.path.basename(runner.log_path) if runner.log_path else None,
                        }
                        # Include diagnostic trail for non-normal outcomes
                        trail = result.get('diagnostic_trail')
                        if trail:
                            game_entry['diagnostic_trail'] = trail
                        _populate_job['results'].append(game_entry)
                    except Exception as e:
                        err_msg = f"Game {game_idx} ({label}, seed {seed}): {e}"
                        _populate_job['errors'].append(err_msg)
                        _populate_job['results'].append({
                            'game': game_idx,
                            'label': label,
                            'seed': seed,
                            'hero': hero_id,
                            'result': 'error',
                            'error': str(e),
                        })
                        # Try to keep the DB session usable
                        try:
                            db.session.rollback()
                        except Exception:
                            pass

                    seed += 1

                if _populate_job['cancel_requested']:
                    break

            ghosts_after = GhostSnapshot.query.count()
            results = _populate_job['results']
            completed = [r for r in results if r['result'] != 'error']
            victories = sum(1 for r in results if r['result'] == 'victory')
            deaths = sum(1 for r in results if r['result'] == 'death')
            errors = sum(1 for r in results if r['result'] == 'error')
            timeouts = sum(1 for r in results if r['result'] in ('timeout', 'stuck'))
            elapsed = time.time() - _populate_job['start_time']

            _populate_job['final_summary'] = {
                'games_run': len(results),
                'victories': victories,
                'deaths': deaths,
                'errors': errors,
                'timeouts': timeouts,
                'cancelled': _populate_job['cancel_requested'],
                'new_ghosts': ghosts_after - ghosts_before,
                'total_ghosts': ghosts_after,
                'elapsed': round(elapsed, 1),
                'rate': round(len(completed) / elapsed, 1) if elapsed > 0 else 0,
                'log_dir': log_dir,
            }

        except Exception as e:
            _populate_job['errors'].append(f"Fatal error: {e}\n{tb_module.format_exc()}")
            _populate_job['final_summary'] = {
                'games_run': len(_populate_job['results']),
                'victories': 0,
                'deaths': 0,
                'errors': 1,
                'timeouts': 0,
                'cancelled': False,
                'fatal_error': str(e),
                'elapsed': round(time.time() - _populate_job['start_time'], 1),
            }
        finally:
            _populate_job['completed_games'] = len(_populate_job['results'])
            _populate_job['end_time'] = time.time()
            _populate_job['running'] = False
            _populate_job['current_game'] = None


@dev_ghosts_api.route('/populate', methods=['POST'])
def populate_ghosts():
    """Start headless games in background. Returns immediately with job status."""
    global _populate_job
    try:
        if _populate_job['running']:
            return jsonify({
                'success': False,
                'error': 'A populate job is already running. Check status or cancel it first.',
                'running': True,
            }), 409

        data = request.get_json() or {}
        num_games = min(data.get('games', 20), 200)
        clear_first = data.get('clear', False)
        seed_start = data.get('seed', 10000)
        ai_type = data.get('ai', 'full_simulation')

        from flask import current_app
        app = current_app._get_current_object()

        # Reset job state
        _populate_job.update({
            'running': True,
            'cancel_requested': False,
            'total_games': num_games,
            'completed_games': 0,
            'current_game': 'starting...',
            'results': [],
            'errors': [],
            'start_time': time.time(),
            'end_time': None,
            'final_summary': None,
        })

        thread = threading.Thread(
            target=_run_populate_job,
            args=(app, num_games, seed_start, ai_type, clear_first),
            daemon=True,
        )
        _populate_job['thread'] = thread
        thread.start()

        return jsonify({
            'success': True,
            'started': True,
            'total_games': num_games,
            'message': f'Started {num_games} games in background. Poll /populate/status for progress.',
        })
    except Exception as e:
        tb_module.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@dev_ghosts_api.route('/populate/status', methods=['GET'])
def populate_status():
    """Poll for populate job progress."""
    elapsed = 0
    if _populate_job['start_time']:
        end = _populate_job['end_time'] or time.time()
        elapsed = round(end - _populate_job['start_time'], 1)

    return jsonify({
        'success': True,
        'running': _populate_job['running'],
        'total_games': _populate_job['total_games'],
        'completed_games': _populate_job['completed_games'],
        'current_game': _populate_job['current_game'],
        'results': _populate_job['results'],
        'errors': _populate_job['errors'],
        'elapsed': elapsed,
        'final_summary': _populate_job['final_summary'],
        'cancel_requested': _populate_job['cancel_requested'],
    })


@dev_ghosts_api.route('/populate/cancel', methods=['POST'])
def populate_cancel():
    """Request cancellation of running populate job."""
    if not _populate_job['running']:
        return jsonify({'success': False, 'error': 'No job is running.'})

    _populate_job['cancel_requested'] = True
    return jsonify({
        'success': True,
        'message': 'Cancel requested. The current game will finish, then the job stops.',
    })


@dev_ghosts_api.route('/populate/log/<filename>', methods=['GET'])
def populate_log(filename):
    """Serve a single game log file."""
    import os

    # Only allow .log files, no path traversal
    if '..' in filename or '/' in filename or not filename.endswith('.log'):
        return jsonify({'success': False, 'error': 'Invalid filename'}), 400

    summary = _populate_job.get('final_summary') or {}
    log_dir = summary.get('log_dir')
    if not log_dir:
        return jsonify({'success': False, 'error': 'No log directory available'}), 404

    log_path = os.path.join(log_dir, filename)
    if not os.path.isfile(log_path):
        return jsonify({'success': False, 'error': 'Log file not found'}), 404

    try:
        with open(log_path, 'r') as f:
            content = f.read()
        return jsonify({'success': True, 'filename': filename, 'content': content})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@dev_ghosts_api.route('/journeys', methods=['GET'])
def ghost_journeys():
    """Analyze per-game journeys from action logs.

    Groups ghosts by run and aggregates action logs from ALL snapshots
    in the same run (each snapshot stores incremental actions for its section).
    Returns: per-game outcomes, ghost battle records, damage stats, streaks,
    ghost opponent details, event frequency, and zone statistics.
    """
    try:
        from models import GhostSnapshot, GhostBattle, db

        # Get all ghosts with actions logs, ordered by milestone asc
        # so we can aggregate them in chronological order per run
        ghosts_with_actions = GhostSnapshot.query.filter(
            GhostSnapshot.actions_log.isnot(None)
        ).order_by(
            GhostSnapshot.events_milestone.asc()
        ).all()

        if not ghosts_with_actions:
            return jsonify({'success': True, 'empty': True, 'journeys': []})

        # Group all ghosts by run, collecting ALL action logs per run.
        # Each snapshot stores only incremental actions for its section,
        # so we must concatenate them in milestone order for the full journey.
        run_snapshots = defaultdict(list)  # run_key -> list of (milestone, ghost)
        for g in ghosts_with_actions:
            actions = g.get_actions_log()
            if not actions:
                continue
            if g.run_id:
                run_key = g.run_id
            else:
                first = actions[0]
                run_key = ('legacy', g.hero_id, first.get('step', 0),
                           str(first.get('band_names', [])), g.id)
            run_snapshots[run_key].append(g)

        # Build run_ghosts: for each run, use highest-milestone ghost for metadata
        # but aggregate ALL actions from all snapshots in the run
        run_ghosts = []           # highest-milestone ghost per run (for metadata)
        run_all_actions = {}      # run_key -> combined actions list
        for run_key, snapshots in run_snapshots.items():
            # Snapshots already sorted by milestone asc from the query
            combined_actions = []
            for snap in snapshots:
                snap_actions = snap.get_actions_log()
                if snap_actions:
                    combined_actions.extend(snap_actions)
            # Use the highest-milestone ghost for metadata (hero, health, band, etc.)
            best_ghost = snapshots[-1]
            run_ghosts.append(best_ghost)
            run_all_actions[id(best_ghost)] = combined_actions

        # Pre-load ghost battle records indexed by run_id for opponent lookup
        all_battles = GhostBattle.query.order_by(GhostBattle.events_milestone).all()
        battles_by_run = defaultdict(list)
        for b in all_battles:
            battles_by_run[b.run_id].append(b)

        # Pre-load ghost snapshots for opponent details (hero, power, source, band)
        ghost_ids_needed = set(b.ghost_id for b in all_battles if b.ghost_id)
        opponent_ghosts = {}
        if ghost_ids_needed:
            for og in GhostSnapshot.query.filter(GhostSnapshot.id.in_(ghost_ids_needed)).all():
                opponent_ghosts[og.id] = og

        journeys = []
        hero_stats = defaultdict(lambda: {
            'games': 0, 'victories': 0, 'deaths': 0,
            'total_ghost_wins': 0, 'total_ghost_losses': 0,
            'total_damage_from_ghosts': 0, 'total_damage_from_combat': 0,
            'milestones_reached': Counter(),
            'max_milestone': 0,
            'win_streaks': [], 'loss_streaks': [],
        })

        # Aggregate event/zone stats across all journeys
        all_event_freq = Counter()
        all_zone_freq = Counter()
        all_combat_type_freq = Counter()

        for g in run_ghosts:
            # Use combined actions from ALL snapshots in this run
            actions = run_all_actions.get(id(g)) or g.get_actions_log()
            combats = [a for a in actions if a['action'] == 'combat']
            ghost_combats = [c for c in combats if 'ghost' in c.get('combat_type', '')]
            regular_combats = [c for c in combats if 'ghost' not in c.get('combat_type', '')]

            ghost_wins = sum(1 for c in ghost_combats if c.get('winner') == 'player')
            ghost_losses = sum(1 for c in ghost_combats if c.get('winner') != 'player')
            combat_wins = sum(1 for c in regular_combats if c.get('winner') == 'player')
            combat_losses = sum(1 for c in regular_combats if c.get('winner') != 'player')

            ghost_damage = sum(c.get('damage_taken', 0) for c in ghost_combats)
            combat_damage = sum(c.get('damage_taken', 0) for c in regular_combats)
            total_damage = ghost_damage + combat_damage

            # Determine outcome: use action log ghost wins, but also cross-check
            # with actual GhostBattle DB records (which are always complete even
            # if the final battle's action wasn't captured in a snapshot)
            run_battles = battles_by_run.get(g.run_id, [])
            db_ghost_wins = sum(1 for b in run_battles if b.winner == 'player')
            db_ghost_losses = sum(1 for b in run_battles if b.winner == 'ghost')
            # Use the higher of action-log count vs DB count
            ghost_wins = max(ghost_wins, db_ghost_wins)
            ghost_losses = max(ghost_losses, db_ghost_losses)
            is_victory = ghost_wins >= 7
            final_health = g.health or 0

            # Event frequency from selection actions
            event_freq = Counter()
            zones_visited = []
            for a in actions:
                if a['action'] == 'selection':
                    et = a.get('event_type', 'unknown')
                    event_freq[et] += 1
                    all_event_freq[et] += 1
                elif a['action'] == 'zone_travel':
                    zone = a.get('zone', 'unknown')
                    zones_visited.append(zone)
                    all_zone_freq[zone] += 1
                elif a['action'] == 'combat':
                    ct = a.get('combat_type', 'unknown')
                    all_combat_type_freq[ct] += 1

            # Ghost battle detail sequence - cross-reference with GhostBattle records
            ghost_sequence = []
            streak = 0
            max_win_streak = 0
            max_loss_streak = 0
            current_streak_type = None
            killing_ghost = None  # Which ghost dealt the final blow

            for idx, c in enumerate(ghost_combats):
                won = c.get('winner') == 'player'

                # Find matching GhostBattle record for opponent details
                opponent_info = {}
                milestone_step = c.get('step', 0)
                # Match by milestone position (10, 20, 30...)
                battle_milestone = ((milestone_step // 10) + 1) * 10
                if milestone_step % 10 == 0:
                    battle_milestone = milestone_step
                for rb in run_battles:
                    if rb.events_milestone == battle_milestone or \
                       (idx < len(run_battles) and rb == run_battles[idx]):
                        opp = opponent_ghosts.get(rb.ghost_id)
                        if opp:
                            opp_band = opp.get_band() or []
                            opponent_info = {
                                'ghost_hero': opp.hero_id or 'none',
                                'ghost_power': opp.power_level,
                                'ghost_source': opp.source or 'unknown',
                                'ghost_milestone': opp.events_milestone,
                                'ghost_band_names': [m.get('name', '?') for m in opp_band],
                            }
                        break

                entry = {
                    'won': won,
                    'damage': c.get('damage_taken', 0) or 0,
                    'player_power': c.get('player_power', 0) or 0,
                    'enemy_power': c.get('enemy_power', 0) or 0,
                    'step': c.get('step', 0),
                    'band_size': c.get('band_size', 0),
                    'health_after': c.get('health', 0) or 0,
                    **opponent_info,
                }
                ghost_sequence.append(entry)

                if not won and not is_victory:
                    killing_ghost = entry  # Track last loss as potential killing blow

                if won:
                    if current_streak_type == 'win':
                        streak += 1
                    else:
                        streak = 1
                        current_streak_type = 'win'
                    max_win_streak = max(max_win_streak, streak)
                else:
                    if current_streak_type == 'loss':
                        streak += 1
                    else:
                        streak = 1
                        current_streak_type = 'loss'
                    max_loss_streak = max(max_loss_streak, streak)

            # Ring upgrades
            upgrades = [a for a in actions if a['action'] == 'ring_upgrade']
            max_ring = max((u.get('new_ring', 1) for u in upgrades), default=1)

            # Band at highest point
            band = g.get_band() or []

            # Combat breakdown by type
            combat_by_type = Counter()
            combat_wins_by_type = Counter()
            combat_damage_by_type = Counter()
            for c in combats:
                ct = c.get('combat_type', 'unknown') or 'unknown'
                combat_by_type[ct] += 1
                if c.get('winner') == 'player':
                    combat_wins_by_type[ct] += 1
                combat_damage_by_type[ct] += c.get('damage_taken', 0) or 0

            combat_breakdown = []
            for ct in sorted(combat_by_type.keys()):
                total = combat_by_type[ct]
                wins = combat_wins_by_type[ct]
                dmg = combat_damage_by_type[ct]
                combat_breakdown.append({
                    'type': ct,
                    'total': total,
                    'wins': wins,
                    'losses': total - wins,
                    'win_rate': round(wins / total * 100) if total > 0 else 0,
                    'total_damage': dmg,
                })

            journey = {
                'ghost_id': g.id,
                'run_id': g.run_id,
                'hero': g.hero_id or 'none',
                'source': g.source or 'unknown',
                'milestone': g.events_milestone,
                'result': 'victory' if is_victory else 'death',
                'final_health': final_health,
                'max_ring': max_ring,
                'ghost_wins': ghost_wins,
                'ghost_losses': ghost_losses,
                'combat_wins': combat_wins,
                'combat_losses': combat_losses,
                'ghost_damage_taken': ghost_damage,
                'combat_damage_taken': combat_damage,
                'total_damage_taken': total_damage,
                'max_win_streak': max_win_streak,
                'max_loss_streak': max_loss_streak,
                'ghost_sequence': ghost_sequence,
                'killing_ghost': killing_ghost if not is_victory else None,
                'combat_breakdown': combat_breakdown,
                'zones_visited': zones_visited,
                'event_counts': dict(event_freq),
                'band_power': g.power_level,
                'band_size': len(band),
                'final_band': _serialize_band(band),
                'total_actions': len(actions),
                'ring_upgrades': len(upgrades),
            }
            journeys.append(journey)

            # Aggregate hero stats
            hs = hero_stats[g.hero_id or 'none']
            hs['games'] += 1
            if is_victory:
                hs['victories'] += 1
            else:
                hs['deaths'] += 1
            hs['total_ghost_wins'] += ghost_wins
            hs['total_ghost_losses'] += ghost_losses
            hs['total_damage_from_ghosts'] += ghost_damage
            hs['total_damage_from_combat'] += combat_damage
            hs['milestones_reached'][g.events_milestone] += 1
            hs['max_milestone'] = max(hs['max_milestone'], g.events_milestone)
            hs['win_streaks'].append(max_win_streak)
            hs['loss_streaks'].append(max_loss_streak)

        # Format hero summary
        hero_summary = []
        for hero_id, hs in sorted(hero_stats.items()):
            games = hs['games']
            hero_summary.append({
                'hero': hero_id,
                'games': games,
                'victories': hs['victories'],
                'deaths': hs['deaths'],
                'win_rate': round(hs['victories'] / games * 100, 1) if games > 0 else 0,
                'avg_ghost_wins': round(hs['total_ghost_wins'] / games, 1) if games > 0 else 0,
                'avg_ghost_losses': round(hs['total_ghost_losses'] / games, 1) if games > 0 else 0,
                'avg_ghost_damage': round(hs['total_damage_from_ghosts'] / games, 1) if games > 0 else 0,
                'avg_combat_damage': round(hs['total_damage_from_combat'] / games, 1) if games > 0 else 0,
                'max_milestone': hs['max_milestone'],
                'milestones': dict(hs['milestones_reached']),
                'avg_win_streak': round(sum(hs['win_streaks']) / len(hs['win_streaks']), 1) if hs['win_streaks'] else 0,
                'avg_loss_streak': round(sum(hs['loss_streaks']) / len(hs['loss_streaks']), 1) if hs['loss_streaks'] else 0,
            })

        # Format aggregate event/zone/combat stats
        event_stats = [
            {'event': e, 'count': c}
            for e, c in all_event_freq.most_common()
        ]
        zone_stats = [
            {'zone': z, 'count': c}
            for z, c in all_zone_freq.most_common()
        ]
        combat_type_stats = [
            {'type': ct, 'count': c}
            for ct, c in all_combat_type_freq.most_common()
        ]

        return jsonify({
            'success': True,
            'total_games': len(journeys),
            'hero_summary': hero_summary,
            'journeys': journeys,
            'event_stats': event_stats,
            'zone_stats': zone_stats,
            'combat_type_stats': combat_type_stats,
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@dev_ghosts_api.route('/clear', methods=['POST'])
def clear_ghosts():
    """Clear all ghost data."""
    try:
        from models import GhostSnapshot, GhostBattle, db

        battles_deleted = GhostBattle.query.delete()
        ghosts_deleted = GhostSnapshot.query.delete()
        db.session.commit()

        return jsonify({
            'success': True,
            'battles_deleted': battles_deleted,
            'ghosts_deleted': ghosts_deleted
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500
