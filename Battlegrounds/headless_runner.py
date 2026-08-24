"""
Headless Game Runner - Run Battleground games programmatically without GUI.

Mirrors the exact same flow as routes.py endpoints:
  /move -> /select -> /combat/step -> /ghost-battle -> /upgrade-ring -> /travel-zone

Every game action goes through the real game engine. No shortcuts, no bypasses.

Usage:
    from headless_runner import HeadlessGameRunner, RandomDecisionAI, SmartDecisionAI, SimulatingDecisionAI, FullSimulationAI

    # Random AI (baseline / fuzz testing)
    runner = HeadlessGameRunner(RandomDecisionAI(), seed=42)
    result = runner.run_complete_game()

    # Smart AI (can actually win)
    runner = HeadlessGameRunner(SmartDecisionAI(), seed=42)
    result = runner.run_complete_game()

    # Simulating AI (evaluates every option to pick the best one)
    runner = HeadlessGameRunner(SimulatingDecisionAI(), hero_id='silas', seed=42)
    result = runner.run_complete_game()

    # Full Simulation AI (tries every option through the real game engine)
    runner = HeadlessGameRunner(FullSimulationAI(), hero_id='silas', seed=42)
    result = runner.run_complete_game()

    # Custom AI (implement DecisionAI)
    class MyAI(DecisionAI):
        ...
    runner = HeadlessGameRunner(MyAI(), hero_id='silas', seed=99)
    result = runner.run_complete_game()
"""

import random
import sys
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional

from database import (
    create_new_run, update_run, move_in_ring, upgrade_ring,
    check_ghost_battle_available, check_ghost_battle_trigger,
    create_ghost_snapshot, record_ghost_battle,
    pre_generate_ghost_opponent_for_milestone, db
)
from game_logic import GameLogic
from game_engine.combat_system import CombatSystem
from game_engine.sub_ring_controller import SubRingController
from game_engine.zone_controller import ZoneController
from game_random import game_random
from config import (
    MAX_GHOST_WINS, MAX_RING_AVAILABLE, EVENTS_FOR_GHOST_BATTLE,
    RING_SIZE, RING_START_POSITION
)


# ---------------------------------------------------------------------------
# Decision AI interface
# ---------------------------------------------------------------------------

class DecisionAI(ABC):
    """
    Interface for automated decision-making.

    Subclass and implement all abstract methods to create an AI
    that can play the full game headlessly.
    """

    @abstractmethod
    def choose_selection(self, run, pending: Dict) -> List[str]:
        """Pick option IDs from a pending selection (events, shops, buffs, etc).

        Args:
            run: The Run model object.
            pending: The pending_selection dict with 'options', 'event_type',
                     'min_selections', 'max_selections', etc.

        Returns:
            List of selected option IDs respecting min/max constraints.
        """
        pass

    @abstractmethod
    def choose_direction(self, run) -> str:
        """Choose ring movement direction.

        Returns 'left' or 'right'.
        """
        pass

    @abstractmethod
    def should_upgrade_ring(self, run, upgrade_cost: int, steps_available: int) -> bool:
        """Decide whether to upgrade to the next ring when possible.

        Args:
            upgrade_cost: How many event-steps the upgrade costs.
            steps_available: Steps left before the next ghost milestone.

        Returns True to upgrade, False to keep exploring.
        """
        pass

    @abstractmethod
    def should_fight_ghost_early(self, run) -> bool:
        """Decide whether to initiate a ghost battle before the milestone forces it."""
        pass

    @abstractmethod
    def choose_zone(self, run, destinations: List[str]) -> Optional[str]:
        """Pick a zone to travel to (or None to stay).

        Called when the player lands on a zone_portal event.
        destinations is the list of valid zone keys the player can travel to.
        """
        pass

    def on_event(self, event_name: str, data: Dict):
        """Optional hook called on game events for logging/analysis."""
        pass

    def manage_band(self, run) -> List[str]:
        """Optionally reposition or abandon minions between events.

        Called when there is no pending selection (free moment).
        Returns a list of action descriptions for logging (empty = no changes).

        Subclasses can override to implement band management strategy.
        """
        return []

    def get_name(self) -> str:
        return self.__class__.__name__


# ---------------------------------------------------------------------------
# RandomDecisionAI - makes random valid choices
# ---------------------------------------------------------------------------

class RandomDecisionAI(DecisionAI):
    """Simplest AI - random valid choices. Good for fuzz testing."""

    def __init__(self, upgrade_threshold: int = 8, ghost_fight_early: bool = False):
        self.upgrade_threshold = upgrade_threshold
        self.ghost_fight_early = ghost_fight_early

    def choose_selection(self, run, pending: Dict) -> List[str]:
        options = pending.get('options', [])
        min_sel = pending.get('min_selections', 1)
        max_sel = pending.get('max_selections', 1)

        if not options:
            return []

        available = [o for o in options if not o.get('disabled', False)]

        if not available:
            # Try escape options
            for o in options:
                if o.get('id') in ('leave', 'skip', 'pass', 'exit', 'continue', 'back'):
                    return [o['id']]
            return [options[0]['id']]

        n = random.randint(max(min_sel, 1), min(max_sel, len(available)))
        selected = random.sample(available, n)
        return [o['id'] for o in selected]

    def choose_direction(self, run) -> str:
        return random.choice(['left', 'right'])

    def should_upgrade_ring(self, run, upgrade_cost, steps_available):
        return upgrade_cost <= self.upgrade_threshold and steps_available >= upgrade_cost

    def should_fight_ghost_early(self, run):
        return self.ghost_fight_early

    def choose_zone(self, run, destinations):
        if destinations:
            return random.choice(destinations)
        return None


# ---------------------------------------------------------------------------
# SmartDecisionAI - basic strategy that can actually win
# ---------------------------------------------------------------------------

class SmartDecisionAI(DecisionAI):
    """
    Strategic AI that makes reasonable decisions.
    Can actually win games - good for regression testing and ghost population.

    Strategy:
    - Buys strongest affordable minions from shops
    - Picks highest-power minions from events, avoids cant_attack
    - Buffs strongest minion (highest attack) for maximum combat impact
    - Conservative ring upgrades (only when band is strong enough)
    - Stays in starting_plains (balanced pool)
    """

    @staticmethod
    def _minion_power(minion_data):
        """Rate a minion's combat value from its data dict."""
        atk = minion_data.get('attack', 0)
        hp = minion_data.get('health', 0)
        kws = minion_data.get('keywords', [])
        # cant_attack minions contribute 0 attack damage
        if 'cant_attack' in kws:
            return hp * 0.3  # Low value - only useful as a body
        return atk + hp

    def choose_selection(self, run, pending: Dict) -> List[str]:
        options = pending.get('options', [])
        event_type = pending.get('event_type', '')
        min_sel = pending.get('min_selections', 1)
        max_sel = pending.get('max_selections', 1)

        if not options:
            return []

        available = [o for o in options if not o.get('disabled', False)]
        if not available:
            for o in options:
                if o.get('id') in ('leave', 'skip', 'pass', 'exit', 'continue', 'back'):
                    return [o['id']]
            return [options[0]['id']]

        # --- Shop events: buy the strongest affordable minion ---
        if event_type == 'shop_event':
            resources = run.get_resources()
            gold = resources.get('gold', 0)
            # Shop options use type 'purchase' or 'shop_replacement'
            buyable = [o for o in available
                       if o.get('type') in ('purchase', 'shop_replacement')
                       and o.get('cost', 999) <= gold
                       and o.get('data')]
            if buyable:
                # Pick the strongest minion we can afford
                best = max(buyable, key=lambda o: self._minion_power(o['data']))
                return [best['id']]
            # Can't afford anything - leave
            for o in options:
                if o.get('id') in ('leave', 'skip', 'pass', 'exit'):
                    return [o['id']]
            return [available[0]['id']]

        # --- Minion events: pick the strongest offered minion ---
        if event_type == 'minion_event':
            minion_opts = [o for o in available
                           if o.get('type') in ('minion', 'replacement') and o.get('data')]
            if minion_opts:
                best = max(minion_opts, key=lambda o: self._minion_power(o['data']))
                # Only take if it's decent (or band is small)
                band = run.get_band()
                if len(band) < 5 or self._minion_power(best['data']) > 4:
                    return [best['id']]
            # Skip if nothing good
            for o in options:
                if o.get('id') in ('skip', 'leave', 'pass'):
                    return [o['id']]
            return [available[0]['id']]

        # --- Target selection: buff the strongest attacker ---
        if event_type == 'target_minion':
            band = run.get_band()
            targets = [o for o in available if o.get('type') == 'apply_targeted_effect']
            if targets and band:
                # Pick target with highest attack (buffs help damage dealers most)
                best = max(targets, key=lambda t: band[t.get('target_index', 0)].get('attack', 0)
                           if t.get('target_index', 0) < len(band) else 0)
                return [best['id']]

        # --- Split events: prefer minions early, buffs once we have 3+ ---
        if event_type == 'split_event':
            band = run.get_band()
            if len(band) < 3:
                for o in available:
                    if 'minion' in o.get('event_type', ''):
                        return [o['id']]
            else:
                for o in available:
                    if 'buff' in o.get('event_type', ''):
                        return [o['id']]

        # --- Statue: try combining if possible ---
        if event_type == 'statue':
            combine = [o for o in available if o.get('type') == 'combine']
            if combine:
                return [combine[0]['id']]

        # --- Combine minions: select two identical minions ---
        if event_type == 'combine_minions':
            combine_opts = [o for o in available if o.get('type') == 'select_minion_for_combine']
            if len(combine_opts) >= 2:
                # Find a valid pair (same name, non-golden)
                for i, o1 in enumerate(combine_opts):
                    for o2 in combine_opts[i+1:]:
                        d1 = o1.get('data') or o1.get('minion_data', {})
                        d2 = o2.get('data') or o2.get('minion_data', {})
                        if d1.get('name') == d2.get('name'):
                            return [o1['id'], o2['id']]
            # No valid pair — skip
            for o in options:
                if o.get('id') in ('skip', 'leave', 'pass'):
                    return [o['id']]
            return [available[0]['id']]

        # --- Shop replacement target: replace weakest minion ---
        if event_type == 'shop_replace_target':
            band = run.get_band()
            replace_opts = [o for o in available if o.get('type') in ('replace_with', 'shop_replace_with')]
            if replace_opts and band:
                # Replace the weakest minion
                weakest = min(replace_opts,
                              key=lambda o: band[o.get('target_index', 0)].get('attack', 0) +
                              band[o.get('target_index', 0)].get('health', 0)
                              if o.get('target_index', 0) < len(band) else 999)
                return [weakest['id']]

        # Default: pick random valid selection
        n = random.randint(max(min_sel, 1), min(max_sel, len(available)))
        selected = random.sample(available, n)
        return [o['id'] for o in selected]

    def choose_direction(self, run) -> str:
        return 'right'

    def should_upgrade_ring(self, run, upgrade_cost, steps_available):
        # Only upgrade when the band is strong enough for harder enemies
        band = run.get_band()
        band_power = sum(m.get('attack', 0) + m.get('health', 0) for m in band)
        band_size = len(band)

        # Require minimum band size and power before upgrading
        # Ring 1→2: need 3+ minions and 20+ power
        # Ring 2→3: need 4+ minions and 40+ power
        # Ring 3→4: need 5+ minions and 70+ power
        next_ring = run.current_ring + 1
        min_size = min(2 + next_ring, 5)
        min_power = next_ring * 20

        if band_size < min_size or band_power < min_power:
            return False

        return upgrade_cost <= 8 and steps_available >= upgrade_cost

    def should_fight_ghost_early(self, run):
        return False

    def choose_zone(self, run, destinations):
        return None

    def manage_band(self, run) -> List[str]:
        """Reposition minions for optimal combat order and abandon dead weight."""
        from game_engine.band_manager import BandManager
        actions = []
        band = run.get_band()
        if len(band) <= 1:
            return actions

        # ── Abandon truly useless minions when band is full ──
        if len(band) >= 6:
            for i in range(len(band) - 1, -1, -1):  # iterate backwards
                m = band[i]
                atk = m.get('attack', 0)
                hp = m.get('health', 0)
                kws = m.get('keywords', [])
                # Useless = 0 attack, no useful keywords, tiny health
                useful_kws = {'guard', 'cast', 'fast', 'start_of_combat',
                              'on_any_death', 'death_toll', 'on_any_summon',
                              'on_any_cast', 'on_damage', 'rage', 'aura',
                              'ring', 'nobility', 'ignoble', 'rich',
                              'hide', 'obliterate', 'multi_attack',
                              'cleave', 'savage', 'poke', 'assault', 'calm',
                              'leap'}
                has_useful = any(k in useful_kws for k in kws)
                if atk == 0 and not has_useful and hp <= 2:
                    result = BandManager.abandon_minion(run, i)
                    if result.get('success'):
                        from database import update_run
                        update_run(run)
                        actions.append(f"Abandoned {m.get('name', '?')} ({atk}/{hp})")
                        band = run.get_band()  # refresh
                        break  # only abandon one per turn

        # ── Reposition for combat: best attackers first, cant_attack last ──
        band = run.get_band()
        if len(band) <= 1:
            return actions

        def _position_priority(m):
            """Higher = should be at lower position index (attacks first)."""
            atk = m.get('attack', 0)
            hp = m.get('health', 0)
            kws = m.get('keywords', [])
            score = 0.0
            # fast keyword: triggers start-of-combat first when at position 0
            if 'fast' in kws:
                score += 200
            # start_of_combat buffers: position matters for buff_adjacent
            if 'start_of_combat' in kws:
                score += 50
            # cant_attack: should be last (wastes attack turn)
            if 'cant_attack' in kws:
                score -= 500
            # High attack = should attack first
            score += atk * 3
            # Health as tiebreaker (tankier attackers survive longer)
            score += hp * 0.5
            return score

        # Build desired order
        indexed = [(i, _position_priority(band[i])) for i in range(len(band))]
        indexed.sort(key=lambda x: x[1], reverse=True)
        desired_order = [idx for idx, _ in indexed]

        # Check if already in desired order
        current_order = list(range(len(band)))
        if desired_order == current_order:
            return actions

        # Apply swaps to reach desired order using minimal swaps
        pos = list(range(len(band)))  # pos[i] = which minion is at position i
        for target_pos in range(len(band)):
            desired_minion = desired_order[target_pos]
            if pos[target_pos] == desired_minion:
                continue
            # Find where the desired minion currently is
            current_pos = None
            for p in range(len(pos)):
                if pos[p] == desired_minion:
                    current_pos = p
                    break
            if current_pos is None or current_pos == target_pos:
                continue
            # Swap
            result = BandManager.swap_minion_positions(run, target_pos, current_pos)
            if result.get('success'):
                old_name = band[pos[target_pos]].get('name', '?')
                new_name = band[desired_minion].get('name', '?')
                actions.append(f"Swap pos {target_pos}↔{current_pos}: "
                               f"{new_name} to front")
                pos[target_pos], pos[current_pos] = pos[current_pos], pos[target_pos]

        if actions:
            from database import update_run
            update_run(run)

        return actions


# ---------------------------------------------------------------------------
# SimulatingDecisionAI - evaluates every option to find the best one
# ---------------------------------------------------------------------------

class SimulatingDecisionAI(DecisionAI):
    """
    Advanced AI that evaluates each available option by simulating the
    resulting band state and picking the action with the highest score.

    Improvements over SmartDecisionAI:
    - Keyword-aware minion scoring (guard, multi_attack, cast, etc.)
    - Golden potential: prioritises duplicates that can merge into goldens
    - Buff selection: picks the buff type that maximises total band power
    - Buff targeting: applies buffs to the minion that benefits most
    - Zone travel: moves to the zone matching the band's dominant tribe
    - Smarter ring upgrades with per-ring power curves
    """

    # Keyword power bonuses used in scoring (subset of keywords.py values)
    KEYWORD_POWER = {
        'guard': 8, 'poke': 5, 'assault': 6, 'death_toll': 4,
        'cast': 7, 'rage': 5, 'calm': 5, 'on_any_death': 4,
        'on_any_cast': 3, 'on_any_summon': 4, 'on_damage': 5,
        'hide': 7, 'fast': 8, 'cleave': 6, 'savage': 6,
        'multi_attack': 10, 'multi_attack_2': 10, 'ring': 10,
        'nobility': 15, 'ignoble': 8, 'obliterate': 25, 'rich': 5,
        'aura': 7, 'leap': 3, 'start_of_combat': 6,
        'fatigue_immune': 5, 'on_any_leap': 3, 'on_hide_lost': 4,
        'sacrifice': 3,
        'cant_attack': 0, 'cant_cast': -2, 'cant_retaliate': -2,
        'stun': -4,
    }

    # ---- scoring helpers ----

    @staticmethod
    def _position_priority(m):
        """Higher value = should be at lower position index (attacks first).

        Used by both manage_band() for repositioning and _score_state() for
        simulating combat with optimal ordering.
        """
        atk = m.get('attack', 0)
        hp = m.get('health', 0)
        kws = m.get('keywords', [])
        score = 0.0
        # fast keyword: start-of-combat trigger, leftmost goes first
        if 'fast' in kws:
            score += 200
        # start_of_combat buffers (buff_adjacent): next to strongest attacker
        if 'start_of_combat' in kws and 'cant_attack' in kws:
            score += 100
        elif 'start_of_combat' in kws:
            score += 50
        # cant_attack: should attack last (wastes turn)
        if 'cant_attack' in kws:
            score -= 500
        # High attack = should attack first to kill enemies early
        score += atk * 3
        # Health as tiebreaker
        score += hp * 0.5
        return score

    @staticmethod
    def _minion_score(m):
        """Score a single minion considering stats, keywords, scaling, and effects.

        Key improvements over naive atk*2+hp:
        - cant_attack minions: attack value is ignored (they never use it)
        - Scaling detection: permanent_stat_gain (Cat) gets huge bonus
        - Self-buff detection: in-combat scalers (Blood Bile, Clockwork) get bonus
        - Multi-attack count: Cabal (3 attacks) scores higher than Bear (1 extra)
        - Summon detection: creating extra bodies has value
        """
        atk = m.get('attack', 0)
        hp = m.get('health', 0)
        kws = m.get('keywords', [])

        # Base stat value — but cant_attack minions don't use their attack
        if 'cant_attack' in kws:
            base = hp  # attack is wasted, only health matters
        else:
            base = atk * 2 + hp

        # Keyword bonuses
        kw_bonus = 0
        for kw in kws:
            kw_bonus += SimulatingDecisionAI.KEYWORD_POWER.get(kw, 0)

        # --- Scaling & effect bonuses ---
        effect_bonus = 0

        # Check each effect slot for valuable patterns
        effect_keys = ('death_toll_effect', 'on_any_death_effect', 'assault_effect',
                       'cast_effect', 'rage_effect', 'calm_effect',
                       'start_of_combat_effect', 'on_damage_effect')
        for ek in effect_keys:
            effect = m.get(ek)
            if not isinstance(effect, dict):
                continue
            etype = effect.get('type', '')

            # Permanent scaling (Cat) — compounds across fights, best in game
            if etype == 'permanent_stat_gain':
                gain = effect.get('attack', 0) + effect.get('health', 0)
                effect_bonus += 15 + gain * 5

            # In-combat self-buff (Blood Bile on_any_death, Clockwork rage, etc.)
            elif etype == 'buff_stats' and effect.get('target') == 'self':
                gain = effect.get('attack', 0) + effect.get('health', 0)
                effect_bonus += gain * 2

            # Team-wide buffs (Brownie cast, Cultist death_toll tribe buff)
            elif etype in ('buff_stats', 'buff_stats_tribe') and effect.get('target') in ('all_allies',):
                gain = effect.get('attack', 0) + effect.get('health', 0)
                effect_bonus += gain * 4  # team-wide is very valuable

            # Summoning (Skeleton, Necromancer, Dryad, etc.)
            elif etype == 'summon_minion':
                count = effect.get('summon_count', 1)
                effect_bonus += 4 * count

            # Rich buff (King, Accursed) - gold-dependent scaling
            elif etype == 'rich_buff':
                effect_bonus += 8

        # Multi-attack count bonus (Cabal has 3, Bear has 1 extra)
        multi_count = m.get('multi_attack_count', 0)
        if multi_count > 1:
            effect_bonus += atk * (multi_count - 1)  # each extra attack ~= another minion

        # Tier bonus: higher-tier minions have better effects and scale better
        # This prevents buffed vanilla tier-1 minions from blocking upgrades
        tier = m.get('tier', 1)
        tier_bonus = {1: 0, 2: 5, 3: 15, 4: 30}.get(tier, 0)

        golden_mult = 1.5 if m.get('golden', False) else 1.0
        return (base + kw_bonus + effect_bonus + tier_bonus) * golden_mult

    def _band_score(self, band):
        """Score an entire band considering individual power + synergies."""
        if not band:
            return 0
        total = sum(self._minion_score(m) for m in band)

        # Bonus: golden merge potential (having 2 of the same non-golden minion)
        names = [m['name'] for m in band if not m.get('golden', False)]
        from collections import Counter
        name_counts = Counter(names)
        for name, count in name_counts.items():
            if count >= 2:
                total += 15  # significant bonus for merge potential

        # Bonus: having a guard (essential defensive layer)
        has_guard = any('guard' in m.get('keywords', []) for m in band)
        if has_guard:
            total += 5

        # --- Tribe synergy bonuses ---
        # Count minions by tribe
        tribe_counts = Counter()
        for m in band:
            mtype = m.get('type', 'None')
            if isinstance(mtype, list):
                for t in mtype:
                    tribe_counts[t] += 1
            elif mtype != 'None':
                tribe_counts[mtype] += 1

        # Cult synergy: Cultist buffs all Cult on death — more Cult = more value
        cult_count = tribe_counts.get('Cult', 0)
        has_cultist = any(m.get('name') == 'Cultist' for m in band)
        if has_cultist and cult_count >= 2:
            total += (cult_count - 1) * 5  # each extra Cult member gets buffed

        # Necromancer + Skeleton/death_toll: summoned Skeletons trigger more deaths
        has_necro = any(m.get('name') == 'Necromancer' for m in band)
        has_death_toll_scalers = any(
            m.get('name') in ('Cat', 'Blood Bile', 'Cultist', 'Reprocessor')
            for m in band
        )
        if has_necro and has_death_toll_scalers:
            total += 8  # Necromancer creates bodies that trigger death effects

        # Houndmaster + Hound: cast makes Hound attack extra
        has_houndmaster = any(m.get('name') == 'Houndmaster' for m in band)
        has_hound = any(m.get('name') == 'Hound' for m in band)
        if has_houndmaster and has_hound:
            total += 10  # strong combo: extra attacks

        # Warlord + tier 1 allies: buffs them +3/+3 on rage
        has_warlord = any(m.get('name') == 'Warlord' for m in band)
        if has_warlord:
            tier1_count = sum(1 for m in band if m.get('tier', 1) == 1 and m.get('name') != 'Warlord')
            total += tier1_count * 4

        return total

    def _golden_potential(self, minion_data, band):
        """Bonus if adding this minion would create a golden merge opportunity."""
        name = minion_data.get('name', '')
        for m in band:
            if m.get('name') == name and not m.get('golden', False):
                return 20  # big bonus — can merge into golden
        return 0

    def _hypothetical_band_with(self, band, new_minion, max_size=6):
        """Return the band score if we added new_minion (replacing weakest if full)."""
        hypo = list(band)
        if len(hypo) >= max_size:
            # Replace weakest
            weakest_idx = min(range(len(hypo)), key=lambda i: self._minion_score(hypo[i]))
            if self._minion_score(new_minion) <= self._minion_score(hypo[weakest_idx]):
                return self._band_score(hypo)  # not worth replacing
            hypo[weakest_idx] = new_minion
        else:
            hypo.append(new_minion)
        return self._band_score(hypo)

    # ---- decision methods ----

    def choose_selection(self, run, pending: Dict) -> List[str]:
        options = pending.get('options', [])
        event_type = pending.get('event_type', '')
        min_sel = pending.get('min_selections', 1)
        max_sel = pending.get('max_selections', 1)

        if not options:
            return []

        available = [o for o in options if not o.get('disabled', False)]
        if not available:
            for o in options:
                if o.get('id') in ('leave', 'skip', 'pass', 'exit', 'continue', 'back'):
                    return [o['id']]
            return [options[0]['id']]

        band = run.get_band()

        # --- Shop events: simulate buying each affordable minion ---
        if event_type == 'shop_event':
            resources = run.get_resources()
            gold = resources.get('gold', 0)
            buyable = [o for o in available
                       if o.get('type') in ('purchase', 'shop_replacement')
                       and o.get('cost', 999) <= gold
                       and o.get('data')]
            if buyable:
                best = max(buyable, key=lambda o: (
                    self._hypothetical_band_with(band, o['data'])
                    + self._golden_potential(o['data'], band)
                ))
                # Only buy if it actually improves the band
                current_score = self._band_score(band)
                new_score = self._hypothetical_band_with(band, best['data'])
                new_score += self._golden_potential(best['data'], band)
                if new_score > current_score or len(band) < 6:
                    return [best['id']]
            for o in options:
                if o.get('id') in ('leave', 'skip', 'pass', 'exit'):
                    return [o['id']]
            return [available[0]['id']]

        # --- Minion events: simulate each option ---
        if event_type == 'minion_event':
            minion_opts = [o for o in available
                           if o.get('type') in ('minion', 'replacement') and o.get('data')]
            if minion_opts:
                scored = []
                current_score = self._band_score(band)
                for o in minion_opts:
                    new_score = self._hypothetical_band_with(band, o['data'])
                    new_score += self._golden_potential(o['data'], band)
                    scored.append((new_score, o))
                scored.sort(key=lambda x: x[0], reverse=True)
                best_score, best = scored[0]
                # Take if band is small or if it improves band
                if len(band) < 5 or best_score > current_score:
                    return [best['id']]
            for o in options:
                if o.get('id') in ('skip', 'leave', 'pass'):
                    return [o['id']]
            return [available[0]['id']]

        # --- Buff type selection: simulate each buff on best target ---
        if event_type in ('buff_event', 'choose_buff'):
            buff_opts = [o for o in available if o.get('type') == 'choose_buff']
            if buff_opts and band:
                best_opt = None
                best_score = -1
                for o in buff_opts:
                    bd = o.get('buff_data', {})
                    bt = bd.get('type', '')
                    h_add = bd.get('amount', 0) if bt == 'health' else bd.get('health', 0)
                    a_add = bd.get('amount', 0) if bt == 'attack' else bd.get('attack', 0)
                    # Simulate applying to best target
                    for i, m in enumerate(band):
                        hypo = dict(m)
                        hypo['attack'] = hypo.get('attack', 0) + a_add
                        hypo['health'] = hypo.get('health', 0) + h_add
                        hypo_band = list(band)
                        hypo_band[i] = hypo
                        score = self._band_score(hypo_band)
                        if score > best_score:
                            best_score = score
                            best_opt = o
                if best_opt:
                    return [best_opt['id']]

        # --- Target selection: simulate buff on each minion ---
        if event_type == 'target_minion':
            targets = [o for o in available if o.get('type') == 'apply_targeted_effect']
            if targets and band:
                # Get the buff being applied from pending context
                buff_data = pending.get('buff_data', {})
                h_add = buff_data.get('amount', 0) if buff_data.get('type') == 'health' else buff_data.get('health', 0)
                a_add = buff_data.get('amount', 0) if buff_data.get('type') == 'attack' else buff_data.get('attack', 0)

                best_target = None
                best_score = -1
                for t in targets:
                    idx = t.get('target_index', 0)
                    if idx >= len(band):
                        continue
                    hypo = dict(band[idx])
                    hypo['attack'] = hypo.get('attack', 0) + a_add
                    hypo['health'] = hypo.get('health', 0) + h_add
                    hypo_band = list(band)
                    hypo_band[idx] = hypo
                    score = self._band_score(hypo_band)
                    if score > best_score:
                        best_score = score
                        best_target = t

                # Fallback: if no buff_data, use keyword-aware priority
                if not best_target or (h_add == 0 and a_add == 0):
                    best_target = max(targets, key=lambda t: (
                        self._minion_score(band[t.get('target_index', 0)])
                        if t.get('target_index', 0) < len(band) else -1
                    ))
                return [best_target['id']]

        # --- Split events: prefer buffs if band >= 3, else minions ---
        if event_type == 'split_event':
            if len(band) < 3:
                for o in available:
                    if 'minion' in o.get('event_type', ''):
                        return [o['id']]
            else:
                for o in available:
                    if 'buff' in o.get('event_type', ''):
                        return [o['id']]

        # --- Statue: try combining ---
        if event_type == 'statue':
            combine = [o for o in available if o.get('type') == 'combine']
            if combine:
                return [combine[0]['id']]

        # --- Combine minions: select two identical minions ---
        if event_type == 'combine_minions':
            combine_opts = [o for o in available if o.get('type') == 'select_minion_for_combine']
            if len(combine_opts) >= 2:
                # Pick the strongest pair (same name, non-golden)
                best_pair = None
                best_score = -1
                for i, o1 in enumerate(combine_opts):
                    for o2 in combine_opts[i+1:]:
                        d1 = o1.get('data') or o1.get('minion_data', {})
                        d2 = o2.get('data') or o2.get('minion_data', {})
                        if d1.get('name') == d2.get('name'):
                            pair_score = self._minion_score(d1) + self._minion_score(d2)
                            if pair_score > best_score:
                                best_score = pair_score
                                best_pair = (o1, o2)
                if best_pair:
                    return [best_pair[0]['id'], best_pair[1]['id']]
            # No valid pair — skip
            for o in options:
                if o.get('id') in ('skip', 'leave', 'pass'):
                    return [o['id']]
            return [available[0]['id']]

        # --- Shop replacement: replace weakest minion ---
        if event_type == 'shop_replace_target':
            replace_opts = [o for o in available if o.get('type') in ('replace_with', 'shop_replace_with')]
            if replace_opts and band:
                weakest = min(replace_opts,
                              key=lambda o: self._minion_score(band[o.get('target_index', 0)])
                              if o.get('target_index', 0) < len(band) else 999)
                return [weakest['id']]

        # Default: pick random valid selection
        n = random.randint(max(min_sel, 1), min(max_sel, len(available)))
        selected = random.sample(available, n)
        return [o['id'] for o in selected]

    def choose_direction(self, run) -> str:
        """Choose direction to maximize buffs before combat.

        The ring layout is fixed: combat at positions 7 and 10, buffs/shops
        at 1-6. Going LEFT from start (pos 5) gives more upgrade events
        before hitting combat.
        """
        pos = run.ring_position
        ring = run.current_ring
        zone = getattr(run, 'current_zone', None)

        # Get the ring layout
        ring_events = GameLogic.get_ring_events(ring, zone=zone)
        ring_size = len(ring_events)

        # Count steps to next combat in each direction
        combat_types = ('combat_event', 'combat_event_hard')

        def steps_to_combat(direction):
            steps = 0
            p = pos
            for _ in range(ring_size):
                if direction == 'right':
                    p = (p + 1) % ring_size
                else:
                    p = (p - 1) % ring_size
                event = ring_events[p]
                if isinstance(event, list):
                    steps += 1
                    continue
                if event in combat_types:
                    return steps
                steps += 1
            return steps

        left_steps = steps_to_combat('left')
        right_steps = steps_to_combat('right')

        # Choose the direction with more upgrade events before combat
        if left_steps > right_steps:
            return 'left'
        elif right_steps > left_steps:
            return 'right'
        return 'right'  # tiebreak

    def should_upgrade_ring(self, run, upgrade_cost, steps_available):
        band = run.get_band()
        band_score = self._band_score(band)
        band_size = len(band)

        # Conservative thresholds: ring upgrades mean harder regular combats
        # Only upgrade when band can handle the next ring's combat difficulty
        next_ring = run.current_ring + 1
        thresholds = {
            2: (3, 45),    # Ring 1→2: 3+ minions, 45+ score
            3: (5, 120),   # Ring 2→3: 5+ minions, 120+ score (need full band)
            4: (6, 200),   # Ring 3→4: 6 minions, 200+ score (very strong)
        }
        min_size, min_score = thresholds.get(next_ring, (5, 90))

        if band_size < min_size or band_score < min_score:
            return False

        return upgrade_cost <= 8 and steps_available >= upgrade_cost

    def should_fight_ghost_early(self, run):
        # Fight ghost early if band is very strong (high confidence win)
        band = run.get_band()
        if not band:
            return False
        band_score = self._band_score(band)
        # Strong threshold: 6 minions with good keywords
        return len(band) >= 6 and band_score >= 100

    def choose_zone(self, run, destinations):
        """Travel to the zone matching the band's dominant tribe."""
        band = run.get_band()
        if not band or not destinations:
            return None

        # Count tribe occurrences in current band
        from collections import Counter
        type_counts = Counter()
        for m in band:
            t = m.get('type', '')
            if isinstance(t, list):
                for tribe in t:
                    type_counts[tribe.lower()] += 1
            elif isinstance(t, str):
                for tribe in t.split(','):
                    tribe = tribe.strip().lower()
                    if tribe:
                        type_counts[tribe] += 1

        if not type_counts:
            return None

        # Map zone keys to tribes
        zone_tribe_map = {
            'beast_wildlands': 'beast',
            'human_kingdom': 'human',
            'undead_crypts': 'undead',
            'fey_grove': 'fey',
            'construct_foundry': 'construct',
            'cult_sanctum': 'cult',
        }

        dominant_tribe = type_counts.most_common(1)[0][0]
        dominant_count = type_counts.most_common(1)[0][1]

        # Only travel if at least 2 minions share the tribe
        if dominant_count < 2:
            return None

        # Find matching zone
        for zone_key in destinations:
            if zone_tribe_map.get(zone_key) == dominant_tribe:
                return zone_key

        return None

    def on_event(self, event_name: str, data: Dict):
        pass

    def get_name(self) -> str:
        return 'SimulatingDecisionAI'

    def manage_band(self, run) -> List[str]:
        """Reposition minions for optimal combat order and abandon dead weight.

        Uses keyword-aware _minion_score for better decisions than SmartDecisionAI.
        """
        from game_engine.band_manager import BandManager
        actions = []
        band = run.get_band()
        if len(band) <= 1:
            return actions

        # ── Abandon truly useless minions when band is full ──
        if len(band) >= 6:
            worst_idx = None
            worst_score = float('inf')
            for i, m in enumerate(band):
                s = self._minion_score(m)
                if s < worst_score:
                    worst_score = s
                    worst_idx = i
            # Abandon threshold scales with ring — standards rise as game progresses
            ring = getattr(run, 'current_ring', 1) or 1
            abandon_threshold = {1: 3, 2: 8, 3: 15, 4: 25}.get(ring, 3)
            if worst_idx is not None and worst_score < abandon_threshold:
                m = band[worst_idx]
                result = BandManager.abandon_minion(run, worst_idx)
                if result.get('success'):
                    from database import update_run
                    update_run(run)
                    actions.append(f"Abandoned {m.get('name', '?')} "
                                   f"({m.get('attack', 0)}/{m.get('health', 0)}, "
                                   f"score {worst_score:.0f})")
                    band = run.get_band()

        # ── Reposition for combat order ──
        band = run.get_band()
        if len(band) <= 1:
            return actions

        indexed = [(i, self._position_priority(band[i])) for i in range(len(band))]
        indexed.sort(key=lambda x: x[1], reverse=True)
        desired_order = [idx for idx, _ in indexed]

        if desired_order == list(range(len(band))):
            return actions  # already optimal

        # Apply swaps to reach desired order
        pos = list(range(len(band)))
        for target_pos in range(len(band)):
            desired_minion = desired_order[target_pos]
            if pos[target_pos] == desired_minion:
                continue
            current_pos = None
            for p in range(len(pos)):
                if pos[p] == desired_minion:
                    current_pos = p
                    break
            if current_pos is None or current_pos == target_pos:
                continue
            result = BandManager.swap_minion_positions(run, target_pos, current_pos)
            if result.get('success'):
                m = band[desired_minion]
                actions.append(f"Swap pos {target_pos}↔{current_pos}: "
                               f"{m.get('name', '?')} → pos {target_pos}")
                pos[target_pos], pos[current_pos] = pos[current_pos], pos[target_pos]

        if actions:
            from database import update_run
            update_run(run)

        return actions


# ---------------------------------------------------------------------------
# FullSimulationAI - tries every option through the real game engine
# ---------------------------------------------------------------------------

class FullSimulationAI(SimulatingDecisionAI):
    """
    Tries every available option through the real game engine using DB
    savepoints, then scores based on **simulated combat against the upcoming
    ghost opponent**.

    For each selection with 2+ options:
      1. Create a DB savepoint
      2. Apply option through GameLogic.resolve_selection (the real engine)
      3. Resolve follow-up selections (buff→target) heuristically
      4. Simulate combat against the upcoming ghost using CombatSystem
      5. Score: ghost-win bonus + surviving minions + health + band power
      6. Rollback the savepoint (all changes undone)
      7. Pick the option with the highest score

    This means the AI will happily spend health on events, take risky buffs,
    or pick weaker-looking minions — if doing so wins the ghost fight.

    Falls back to SimulatingDecisionAI scoring if no ghost is available or
    if savepoints fail.
    """

    def __init__(self):
        self._in_sim = False
        self._cached_ghost_id = None
        self._cached_ghost_band = None     # Deep-copied once, reused for every sim
        self._cached_ghost_hero_fx = None  # Hero effects, also stable

    def _load_ghost_data(self, run):
        """Load and cache the upcoming ghost opponent's band and hero effects.

        Returns (ghost_band, hero_effects) or (None, None).
        Caches a deep copy of the band so combat sims don't need to re-copy it.
        """
        import copy
        ghost_id = getattr(run, 'upcoming_ghost_id', None)
        if not ghost_id:
            return None, None
        if ghost_id == self._cached_ghost_id and self._cached_ghost_band is not None:
            return self._cached_ghost_band, self._cached_ghost_hero_fx

        from models import GhostSnapshot
        ghost = GhostSnapshot.query.get(ghost_id)
        if not ghost:
            return None, None

        band = ghost.get_band()
        if not band:
            return None, None

        self._cached_ghost_id = ghost_id
        self._cached_ghost_band = copy.deepcopy(band)
        self._cached_ghost_hero_fx = ghost.get_hero_effects()
        return self._cached_ghost_band, self._cached_ghost_hero_fx

    def _score_state(self, run):
        """Score by simulating combat against the upcoming ghost.

        If no ghost is available (early game, between milestones),
        falls back to band power + health + gold.

        Optimizes band positioning before simulating combat so the score
        reflects the best possible arrangement (matching manage_band logic).
        """
        import copy

        ghost_band, ghost_hero_fx = self._load_ghost_data(run)
        band = run.get_band()

        if not ghost_band or not band:
            # No ghost yet — fall back to band quality + health + gold
            resources = run.get_resources()
            return self._band_score(band) + run.health * 0.5 + resources.get('gold', 0) * 0.3

        try:
            # Sort band into optimal combat order before simulating
            player_copy = copy.deepcopy(band)
            player_copy.sort(key=lambda m: self._position_priority(m), reverse=True)
            for i, m in enumerate(player_copy):
                m['position'] = i
            ghost_copy = copy.deepcopy(ghost_band)
            result = CombatSystem.resolve_combat(
                player_copy, ghost_copy,
                run=run,
                enemy_hero_effects=ghost_hero_fx
            )

            winner = result.get('winner', 'draw')
            # Count surviving player minions
            surviving = len([m for m in result.get('player_band', [])
                             if m.get('health', 0) > 0])

            score = 0.0

            if winner == 'player':
                score += 200              # Massive bonus for winning the ghost fight
                score += surviving * 10   # Bonus per surviving minion (cleaner win)
            elif winner == 'draw':
                score += 50               # Draw is better than losing
            else:
                # Lost — still differentiate by how close it was
                enemy_surviving = len([m for m in result.get('enemy_band', [])
                                       if m.get('health', 0) > 0])
                score -= enemy_surviving * 10  # Fewer enemy survivors = closer to winning

            # Secondary factors:
            # Health is critical — losing at low HP means death
            hp = run.health
            if hp <= 10:
                score += hp * 2.0    # Every HP point matters when low
            else:
                score += hp * 0.3
            resources = run.get_resources()
            score += resources.get('gold', 0) * 0.1   # Gold has minor value
            # Band score as a small tiebreaker (for future fights, not just this one)
            score += self._band_score(band) * 0.05

            return score
        except Exception:
            # Combat simulation failed — fall back to band score
            resources = run.get_resources()
            return self._band_score(band) + run.health * 0.5 + resources.get('gold', 0) * 0.3

    def choose_selection(self, run, pending: Dict) -> List[str]:
        # While inside a simulation, use heuristic to resolve follow-ups
        if self._in_sim:
            return super().choose_selection(run, pending)

        options = pending.get('options', [])
        available = [o for o in options if not o.get('disabled', False)]
        if not available:
            return super().choose_selection(run, pending)

        escape_ids = {'leave', 'skip', 'pass', 'exit', 'continue', 'back'}
        actionable = [o for o in available if o['id'] not in escape_ids]

        # 0-1 real options → no need to simulate
        if len(actionable) <= 1:
            return super().choose_selection(run, pending)

        # Try each option through the real game engine
        try:
            best_score = None
            best_id = None

            for o in actionable:
                score = self._simulate_option(run, o['id'])
                if score is not None and (best_score is None or score > best_score):
                    best_score = score
                    best_id = o['id']

            if best_id is not None:
                # Also simulate the skip/leave option to compare properly
                skip_score = None
                for o in available:
                    if o['id'] in escape_ids:
                        skip_score = self._simulate_option(run, o['id'])
                        break

                # If we couldn't simulate skip, use current state as baseline
                if skip_score is None:
                    skip_score = self._score_state(run)

                band = run.get_band()
                if best_score >= skip_score or len(band) < 6:
                    return [best_id]

                # Skip/leave scored higher — take it
                for o in available:
                    if o['id'] in escape_ids:
                        return [o['id']]
                return [best_id]  # no skip available, take best anyway
        except Exception:
            pass  # savepoint approach failed entirely, fall through

        # Fallback to SimulatingDecisionAI heuristic
        return super().choose_selection(run, pending)

    def _simulate_option(self, run, option_id):
        """Try a single option via savepoint, score result, rollback."""
        self._in_sim = True
        try:
            sp = db.session.begin_nested()
            try:
                result = GameLogic.resolve_selection(run, [option_id])
                if not result or result.get('error'):
                    return None

                # Resolve follow-up selections heuristically (e.g. buff→target)
                for _ in range(3):
                    fp = run.get_pending_selection()
                    if not fp or not fp.get('options'):
                        break
                    fids = super().choose_selection(run, fp)
                    if fids:
                        GameLogic.resolve_selection(run, fids)

                return self._score_state(run)
            except Exception:
                return None
            finally:
                sp.rollback()
                try:
                    db.session.refresh(run)
                except Exception:
                    pass
        except Exception:
            # begin_nested itself failed — refresh to be safe
            try:
                db.session.refresh(run)
            except Exception:
                pass
            return None
        finally:
            self._in_sim = False

    def should_fight_ghost_early(self, run):
        """Never fight ghosts early — let the game play out and optimize
        for the required fight at the milestone boundary instead.

        Fighting early creates a loop where a new ghost is immediately
        pre-generated and the AI fights that one too, winning 7 in a row
        without actually playing events to build a stronger band.
        """
        return False

    def get_name(self):
        return 'FullSimulationAI'


# ---------------------------------------------------------------------------
# HeadlessGameRunner - orchestrates a complete game
# ---------------------------------------------------------------------------

class HeadlessGameRunner:
    """
    Runs a complete Battleground game programmatically.

    Mirrors the frontend's interaction pattern with the backend:
    1. Move in ring -> triggers event creation
    2. Resolve pending selections (may chain)
    3. Handle combat (auto-resolve + continue)
    4. Check ghost battle milestones
    5. Upgrade ring when possible
    6. Check win/loss conditions

    Uses the REAL game engine - all restrictions apply.
    """

    def __init__(self,
                 decision_ai: DecisionAI,
                 hero_id: Optional[str] = None,
                 seed: Optional[int] = None,
                 verbose: bool = True,
                 persist_run: bool = False,
                 quiet_engine: bool = True,
                 starting_health: Optional[int] = None,
                 max_time: float = 120.0,
                 cancel_check: Optional[callable] = None,
                 log_dir: Optional[str] = None):
        self.ai = decision_ai
        self.hero_id = hero_id
        self.seed = seed
        self.verbose = verbose
        self.persist_run = persist_run
        self.quiet_engine = quiet_engine
        self.starting_health = starting_health  # Override default 30 HP if set
        self.max_time = max_time              # Wall-clock timeout in seconds
        self.cancel_check = cancel_check      # Callable returning True to cancel
        self.log_dir = log_dir                # Directory for per-game log files

        self.run = None
        self.iterations = 0
        self.max_iterations = 10000
        self.events_log = []  # Track what happened for analysis
        self.actions_log = []  # Detailed action tracking for ghost analysis
        self.combat_count = 0
        self.combat_wins = 0
        self.ghost_count = 0
        self.ghost_wins = 0
        self.rings_upgraded = 0
        self._last_snapshot_action_idx = 0  # Track where last snapshot's actions ended
        self._start_time = None
        self._last_events_count = 0       # For stuck detection
        self._stuck_iterations = 0        # How many iterations with no event progress
        self._max_stuck = 200             # Kill game if stuck this many iterations
        self.error = None                 # Stores error info if game crashes
        self._log_lines = []              # Buffered log lines for file output
        self.log_path = None              # Set after game ends if log_dir given

    def log(self, msg: str):
        line = f"  [{self.iterations:>4}] {msg}"
        self._log_lines.append(line)
        if self.verbose:
            print(line)

    def log_header(self, msg: str):
        line = f"\n{'='*60}\n{msg}\n{'='*60}"
        self._log_lines.append(line)
        if self.verbose:
            print(f"\n{'='*60}\n{msg}\n{'='*60}")

    def _track_action(self, action_type: str, details: dict):
        """Record an action for detailed ghost analysis."""
        band = self.run.get_band() if self.run else []
        self.actions_log.append({
            'action': action_type,
            'step': self.run.events_count if self.run else 0,
            'ring': self.run.current_ring if self.run else 0,
            'health': self.run.health if self.run else 0,
            'band_size': len(band),
            'band_power': sum(m.get('attack', 0) + m.get('health', 0) for m in band),
            'band_names': [m['name'] for m in band],
            **details
        })

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run_complete_game(self) -> Dict[str, Any]:
        """Run a full game and return results."""
        # Suppress engine debug output for speed
        _saved_stdout = None
        if self.quiet_engine:
            import io as _io
            import game_engine.combat_system as _cs_mod
            _cs_mod.QUIET_MODE = True
            _saved_stdout = sys.stdout
            sys.stdout = _io.StringIO()

        try:
            self._setup()
            self._start_time = time.time()
            self.log_header(f"Game started | AI: {self.ai.get_name()} | "
                            f"Hero: {self.hero_id or 'None'} | Seed: {self.seed}")

            while self.iterations < self.max_iterations:
                self.iterations += 1

                # Safety: check cancellation
                if self.cancel_check and self.cancel_check():
                    self.log("CANCELLED by user")
                    return self._result('cancelled')

                # Safety: check wall-clock timeout
                elapsed = time.time() - self._start_time
                if elapsed > self.max_time:
                    self.error = f"Wall-clock timeout after {elapsed:.1f}s"
                    self.log(f"TIMEOUT - {self.error}")
                    return self._result('timeout')

                # Safety: stuck detection (no event progress for too many iterations)
                current_events = self.run.events_count if self.run else 0
                if current_events > self._last_events_count:
                    self._last_events_count = current_events
                    self._stuck_iterations = 0
                else:
                    self._stuck_iterations += 1
                    if self._stuck_iterations >= self._max_stuck:
                        pending = self.run.get_pending_selection() if self.run else None
                        pending_type = pending.get('event_type', '?') if pending else 'none'
                        self.error = (f"Stuck for {self._stuck_iterations} iterations at "
                                      f"event {current_events}, pending: {pending_type}")
                        self.log(f"STUCK - {self.error}")
                        return self._result('stuck')

                # 1. Check end conditions
                end = self._check_end()
                if end:
                    return self._result(end)

                # 2. If there's a pending selection, resolve it
                pending = self.run.get_pending_selection()
                if pending:
                    self._resolve_pending(pending)
                    continue

                # 3. Check if ghost battle is REQUIRED (at milestone boundary)
                if check_ghost_battle_trigger(self.run):
                    if check_ghost_battle_available(self.run):
                        self._initiate_ghost_battle()
                        continue

                # 4. Check if we should upgrade ring
                if self._try_upgrade_ring():
                    continue

                # 5. Check if AI wants to fight ghost early (optional)
                if (check_ghost_battle_available(self.run) and
                        self.ai.should_fight_ghost_early(self.run)):
                    self._initiate_ghost_battle()
                    continue

                # 6. Manage band (reposition, abandon) between events
                band_actions = self.ai.manage_band(self.run)
                for action in band_actions:
                    self.log(f"Band: {action}")

                # 7. Move to next event (the normal game flow)
                self._move_and_create_event()

            self.error = f"Max iterations ({self.max_iterations}) reached"
            self.log("TIMEOUT - max iterations reached")
            return self._result('timeout')

        finally:
            # Restore stdout if suppressed
            if _saved_stdout is not None:
                sys.stdout = _saved_stdout
                import game_engine.combat_system as _cs_mod
                _cs_mod.QUIET_MODE = False
            self._cleanup()

    # ------------------------------------------------------------------
    # Setup / teardown
    # ------------------------------------------------------------------

    def _setup(self):
        """Initialize seed and create new run."""
        if self.seed is not None:
            game_random.rng.seed(self.seed)
            random.seed(self.seed)

        # Enable WAL mode for faster writes in headless
        if self.quiet_engine:
            try:
                db.session.execute(db.text("PRAGMA journal_mode=WAL"))
                db.session.execute(db.text("PRAGMA synchronous=NORMAL"))
            except Exception:
                pass

        self.run = create_new_run(
            player_id=None,
            is_ranked=False,
            hero_id=self.hero_id
        )

        # Override starting health if specified (useful for populate to generate
        # diverse ghost data across more milestones)
        if self.starting_health is not None:
            self.run.health = self.starting_health

        update_run(self.run)

    def _cleanup(self):
        """Mark run inactive unless persisting."""
        if not self.persist_run and self.run:
            try:
                self.run.is_active = False
                update_run(self.run)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # End condition checks
    # ------------------------------------------------------------------

    def _check_end(self) -> Optional[str]:
        """Check victory/defeat."""
        if self.run.health <= 0:
            self.log_header(f"DEFEAT - Health reached 0 at Ring {self.run.current_ring}")
            return 'death'

        wins = self._count_ghost_wins()
        if wins >= MAX_GHOST_WINS:
            self.log_header(f"VICTORY - {wins}/{MAX_GHOST_WINS} ghost battles won!")
            return 'victory'

        return None

    def _count_ghost_wins(self) -> int:
        from models import GhostBattle
        return GhostBattle.query.filter_by(
            run_id=self.run.id,
            winner='player'
        ).count()

    # ------------------------------------------------------------------
    # Selection resolution (the core loop)
    # ------------------------------------------------------------------

    def _resolve_pending(self, pending: Dict):
        """Resolve whatever pending selection exists."""
        event_type = pending.get('event_type', 'unknown')

        # Combat selection
        if event_type in ('combat', 'boss_combat'):
            self._resolve_combat(pending)
            return

        # Zone portal - AI decides whether to travel
        if event_type == 'zone_portal':
            self._resolve_zone_portal(pending)
            return

        # Regular selection - ask AI
        try:
            selected_ids = self.ai.choose_selection(self.run, pending)
        except Exception as e:
            self.log(f"AI error choosing selection: {e}")
            # Fallback: pick first available option
            options = pending.get('options', [])
            selected_ids = [options[0]['id']] if options else []

        if not selected_ids:
            # No options - try to leave
            self.log(f"No selection possible for {event_type}, clearing")
            self.run.set_pending_selection(None)
            update_run(self.run)
            return

        self.log(f"Select [{event_type}]: {selected_ids}")
        self.ai.on_event('selection', {'event_type': event_type, 'selected': selected_ids})

        # Snapshot band before selection to detect changes
        band_before = [m['name'] for m in self.run.get_band()]

        result = GameLogic.resolve_selection(self.run, selected_ids)
        update_run(self.run)

        # Track what changed
        band_after = [m['name'] for m in self.run.get_band()]
        added = [n for n in band_after if n not in band_before]
        removed = [n for n in band_before if n not in band_after]
        self._track_action('selection', {
            'event_type': event_type,
            'selected': selected_ids,
            'minions_added': added,
            'minions_removed': removed,
        })

        if result.get('error'):
            self.log(f"Selection error: {result['error']}")
            # If selection errored, try to recover by clearing if leaveable
            if pending.get('leaveable', False):
                self.run.set_pending_selection(None)
                update_run(self.run)

    def _resolve_combat(self, pending: Dict):
        """Resolve combat using the real CombatSystem path.

        Flow mirrors routes.py /select endpoint:
        1. Send 'end' to resolve_combat_selection -> runs combat + applies results
        2. Send 'continue' to resolve_combat_selection -> chains to next event or clears
        """
        combat_type = pending.get('combat_type', 'combat')
        is_complete = pending.get('combat_complete', False)

        if is_complete:
            # Combat already resolved, need to press "continue"
            self.log(f"Combat continue [{combat_type}]")
            result = GameLogic.resolve_combat_selection(self.run, 'continue')
            update_run(self.run)

            if result.get('error'):
                self.log(f"Combat continue error: {result['error']}")
                self.run.set_pending_selection(None)
                update_run(self.run)
            return

        # Resolve combat with 'end' (skip animations, go straight to result)
        player_band = self.run.get_band()
        combat_state = pending.get('combat_state', {})
        enemy_band = combat_state.get('enemy_band', [])
        is_duel = pending.get('is_duel', False)

        if is_duel:
            # Duels use a single champion — show champion stats, not full band
            champ_idx = pending.get('champion_index', 0)
            if champ_idx is not None and champ_idx < len(player_band):
                champ = player_band[champ_idx]
                player_power = champ.get('attack', 0)
                player_hp = champ.get('health', 0)
                champ_name = champ.get('name', '?')
                self.log(f"Combat [{combat_type}]: {champ_name} "
                         f"({player_power}/{player_hp}) vs {len(enemy_band)} enemies "
                         f"(atk {sum(m.get('attack', 0) for m in enemy_band)}"
                         f"/hp {sum(m.get('health', 0) for m in enemy_band)})")
            else:
                player_power = sum(m.get('attack', 0) for m in player_band)
                self.log(f"Combat [{combat_type}]: duel (pow {player_power}) vs "
                         f"{len(enemy_band)} enemies")
        else:
            player_power = sum(m.get('attack', 0) for m in player_band)
            player_hp = sum(m.get('health', 0) for m in player_band)
            enemy_power = sum(m.get('attack', 0) for m in enemy_band)
            enemy_hp = sum(m.get('health', 0) for m in enemy_band)
            self.log(f"Combat [{combat_type}]: {len(player_band)} minions "
                     f"(atk {player_power}/hp {player_hp}) vs {len(enemy_band)} enemies "
                     f"(atk {enemy_power}/hp {enemy_hp})")
        enemy_power = sum(m.get('attack', 0) for m in enemy_band)
        health_before = self.run.health

        result = GameLogic.resolve_combat_selection(self.run, 'end')
        update_run(self.run)

        if result.get('error'):
            self.log(f"Combat error: {result['error']}")
            self.run.set_pending_selection(None)
            update_run(self.run)
            return

        winner = result.get('combat_result', 'unknown')
        self.combat_count += 1
        if winner == 'player':
            self.combat_wins += 1

        if 'ghost' in combat_type:
            self.ghost_count += 1
            if winner == 'player':
                self.ghost_wins += 1

        damage_taken = max(0, health_before - self.run.health)
        self.log(f"Combat result: {winner} | Health: {self.run.health} | Dmg: {damage_taken}")
        self._track_action('combat', {
            'combat_type': combat_type,
            'winner': winner,
            'player_power': player_power,
            'enemy_power': enemy_power,
            'enemy_count': len(enemy_band),
            'damage_taken': damage_taken,
            'health_before': health_before,
        })
        self.ai.on_event('combat_result', {
            'combat_type': combat_type,
            'winner': winner,
            'health': self.run.health
        })

    def _resolve_zone_portal(self, pending: Dict):
        """Handle zone portal selections."""
        destinations = []
        for opt in pending.get('options', []):
            if opt.get('type') == 'travel_to_zone':
                destinations.append(opt.get('zone', opt.get('id', '')))

        chosen_zone = self.ai.choose_zone(self.run, destinations)

        if chosen_zone and chosen_zone in destinations:
            # Find the option ID for this zone
            for opt in pending.get('options', []):
                if opt.get('zone') == chosen_zone or opt.get('id') == chosen_zone:
                    self.log(f"Travel to zone: {chosen_zone}")
                    self._track_action('zone_travel', {'zone': chosen_zone})
                    result = GameLogic.resolve_selection(self.run, [opt['id']])
                    update_run(self.run)
                    return

        # Stay in current zone - pick stay option or leave
        for opt in pending.get('options', []):
            if opt.get('type') in ('stay_in_zone', 'skip', 'leave'):
                result = GameLogic.resolve_selection(self.run, [opt['id']])
                update_run(self.run)
                return

        # Fallback: just pick first option
        options = pending.get('options', [])
        if options:
            result = GameLogic.resolve_selection(self.run, [options[0]['id']])
            update_run(self.run)
        else:
            self.run.set_pending_selection(None)
            update_run(self.run)

    # ------------------------------------------------------------------
    # Ghost battles
    # ------------------------------------------------------------------

    def _initiate_ghost_battle(self):
        """Initiate a ghost battle, mirroring the /ghost-battle endpoint."""
        if not self.run.upcoming_ghost_id:
            self.log("Ghost battle requested but no upcoming ghost")
            return

        # Clear leaveable pending selection if any
        if self.run.has_pending_selection():
            pending = self.run.get_pending_selection()
            if pending.get('leaveable', False):
                self.run.set_pending_selection(None)
            else:
                self.log("Cannot start ghost battle - non-leaveable selection active")
                return

        # Create player ghost snapshot with only actions since last snapshot
        snapshot_actions = self.actions_log[self._last_snapshot_action_idx:]
        create_ghost_snapshot(self.run, actions_log=snapshot_actions)
        self._last_snapshot_action_idx = len(self.actions_log)

        # Get bands
        player_band = self.run.get_band()

        from models import GhostSnapshot
        opponent_ghost = GhostSnapshot.query.get(self.run.upcoming_ghost_id)
        if not opponent_ghost:
            self.log("Ghost opponent not found in DB")
            return

        enemy_band = opponent_ghost.get_band_with_images()

        # Pre-resolve combat with ghost hero effects (same as routes.py)
        battle_result = CombatSystem.resolve_combat(
            player_band, enemy_band, run=self.run,
            enemy_hero_effects=opponent_ghost.get_hero_effects()
        )
        interpreter_data = battle_result.get('interpreter_data')

        # Minimal combat_state — interpreter_data has the actual resolved combat.
        # This is only here because resolve_combat_selection expects the structure.
        combat_state = {
            'player_band': [m.copy() for m in player_band],
            'enemy_band': [m.copy() for m in enemy_band],
        }

        ghost_name = opponent_ghost.player_name or 'Ghost'

        selection = {
            'event_type': 'combat',
            'combat_type': 'ghost_battle',
            'ghost_id': opponent_ghost.id,
            'ghost_player_name': ghost_name,
            'ghost_hero_id': opponent_ghost.hero_id,
            'title': f'Ghost Battle vs {ghost_name} (Event {self.run.events_count})',
            'message': f'Fighting {ghost_name}\'s band:',
            'combat_state': combat_state,
            'interpreter_data': interpreter_data,
            'options': [
                {'type': 'combat_next', 'message': 'Next Attack', 'id': 'next'},
                {'type': 'combat_auto', 'message': 'Auto Combat', 'id': 'auto'},
                {'type': 'combat_end', 'message': 'End Combat', 'id': 'end'}
            ],
            'min_selections': 1,
            'max_selections': 1,
            'repeating': False,
            'leaveable': False
        }

        self.run.set_pending_selection(selection)
        update_run(self.run)
        self.log(f"Ghost battle initiated (event {self.run.events_count})")

    # ------------------------------------------------------------------
    # Ring upgrades
    # ------------------------------------------------------------------

    def _try_upgrade_ring(self) -> bool:
        """Attempt to upgrade ring if conditions are met. Returns True if upgraded."""
        if SubRingController.is_in_sub_ring(self.run):
            return False
        if self.run.current_ring >= MAX_RING_AVAILABLE:
            return False

        # Calculate cost (same as routes.py /upgrade-ring)
        event_state = self.run.get_event_state()
        tier_cost_reduction = event_state.get('tier_cost_reduction', 0)
        upgrade_cost = max(0, 15 - self.run.ring_upgrade_steps - tier_cost_reduction)

        # Calculate steps available until next ghost milestone
        from models import GhostSnapshot
        if self.run.upcoming_ghost_id:
            upcoming_ghost = GhostSnapshot.query.get(self.run.upcoming_ghost_id)
            if upcoming_ghost:
                next_ghost_milestone = upcoming_ghost.events_milestone
            else:
                current_cycle = self.run.events_count // EVENTS_FOR_GHOST_BATTLE
                next_ghost_milestone = (current_cycle + 1) * EVENTS_FOR_GHOST_BATTLE
        else:
            current_cycle = self.run.events_count // EVENTS_FOR_GHOST_BATTLE
            next_ghost_milestone = (current_cycle + 1) * EVENTS_FOR_GHOST_BATTLE

        steps_available = next_ghost_milestone - self.run.events_count

        if steps_available < upgrade_cost:
            return False

        # Would the upgrade overshoot the ghost milestone?
        if self.run.events_count + upgrade_cost >= next_ghost_milestone:
            return False

        # Ask AI
        if not self.ai.should_upgrade_ring(self.run, upgrade_cost, steps_available):
            return False

        # Clear leaveable pending selection
        if self.run.has_pending_selection():
            pending = self.run.get_pending_selection()
            if pending.get('leaveable', False):
                self.run.set_pending_selection(None)
            else:
                return False

        # Do the upgrade (mirrors routes.py)
        old_ring = self.run.current_ring
        self.run.events_count += upgrade_cost

        # Clear sub-ring state
        self.run.current_ring_type = 'main'
        self.run.current_sub_ring = None
        self.run.sub_ring_position = 0
        self.run.main_ring_return_position = None
        self.run.set_sub_ring_data(None)

        upgrade_ring(self.run)

        # Clear tier_cost_reduction
        if tier_cost_reduction > 0:
            event_state.pop('tier_cost_reduction', None)
            self.run.set_event_state(event_state)

        update_run(self.run)

        self.rings_upgraded += 1
        self._track_action('ring_upgrade', {
            'old_ring': old_ring,
            'new_ring': self.run.current_ring,
            'cost': upgrade_cost,
        })
        self.log(f"RING UPGRADE: {old_ring} -> {self.run.current_ring} (cost {upgrade_cost})")
        self.ai.on_event('ring_upgrade', {
            'old_ring': old_ring,
            'new_ring': self.run.current_ring,
            'cost': upgrade_cost
        })
        return True

    # ------------------------------------------------------------------
    # Movement
    # ------------------------------------------------------------------

    def _move_and_create_event(self):
        """Move in ring and create the next event selection."""
        # Clear leaveable pending selection
        if self.run.has_pending_selection():
            pending = self.run.get_pending_selection()
            if pending.get('leaveable', False):
                self.run.set_pending_selection(None)
                update_run(self.run)
            else:
                self.log("Cannot move - non-leaveable selection active")
                return

        direction = self.ai.choose_direction(self.run)

        if SubRingController.is_in_sub_ring(self.run):
            success, message = SubRingController.move_in_sub_ring(self.run, direction)
            if not success:
                # Try opposite direction
                other = 'right' if direction == 'left' else 'left'
                success, message = SubRingController.move_in_sub_ring(self.run, other)
                if not success:
                    self.log(f"Sub-ring movement failed both ways: {message}")
                    return

            # Check if we exited sub-ring
            if not SubRingController.is_in_sub_ring(self.run):
                current_event = GameLogic.get_current_event(self.run)
            else:
                current_event = SubRingController.get_current_sub_ring_event(self.run)
        else:
            move_in_ring(self.run, direction)
            current_event = GameLogic.get_current_event(self.run)

        ring_info = f"Ring {self.run.current_ring}, Pos {self.run.ring_position}"
        if SubRingController.is_in_sub_ring(self.run):
            ring_info = f"Sub-Ring pos {self.run.sub_ring_position}"

        self.log(f"Move {direction} -> {ring_info} | Event: {current_event} | "
                 f"Events: {self.run.events_count}")

        try:
            GameLogic.create_event_selection(self.run, current_event)
            update_run(self.run)
        except Exception as e:
            self.log(f"Event creation error: {e}")
            update_run(self.run)

        self.events_log.append({
            'event': current_event,
            'ring': self.run.current_ring,
            'position': self.run.ring_position,
            'events_count': self.run.events_count
        })

    # ------------------------------------------------------------------
    # Result building
    # ------------------------------------------------------------------

    def _result(self, outcome: str) -> Dict[str, Any]:
        # Save a final snapshot with any remaining unsnapshotted actions
        # (e.g. the last ghost battle result that triggered victory/death)
        remaining_actions = self.actions_log[self._last_snapshot_action_idx:]
        if remaining_actions:
            create_ghost_snapshot(self.run, actions_log=remaining_actions)
            self._last_snapshot_action_idx = len(self.actions_log)

        ghost_wins = self._count_ghost_wins()
        elapsed = time.time() - self._start_time if self._start_time else 0

        # Build diagnostic trail for non-normal outcomes
        trail = None
        if outcome not in ('victory', 'death'):
            trail = self._diagnostic_trail()

        # Log final summary line
        band = self.run.get_band()
        band_str = ', '.join(f"{m.get('name','?')} {m.get('attack',0)}/{m.get('health',0)}" for m in band)
        self.log(f"RESULT: {outcome} | Ghost W/L: {ghost_wins}/{self.ghost_count - self.ghost_wins} | "
                 f"HP: {self.run.health} | Events: {self.run.events_count} | "
                 f"Ring: {self.run.current_ring} | Band({len(band)}): [{band_str}] | "
                 f"Time: {elapsed:.1f}s")
        if self.error:
            self.log(f"ERROR: {self.error}")

        # Write log file
        self._write_log_file(outcome)

        return {
            'result': outcome,
            'final_ring': self.run.current_ring,
            'final_health': self.run.health,
            'ghost_wins': ghost_wins,
            'max_ghost_wins': MAX_GHOST_WINS,
            'events_completed': self.run.events_count,
            'iterations': self.iterations,
            'run_id': self.run.id,
            'combat_count': self.combat_count,
            'combat_wins': self.combat_wins,
            'ghost_count': self.ghost_count,
            'ghost_wins_count': self.ghost_wins,
            'rings_upgraded': self.rings_upgraded,
            'final_band': band,
            'final_resources': self.run.get_resources(),
            'events_log': self.events_log,
            'actions_log': self.actions_log,
            'elapsed': round(elapsed, 2),
            'error': self.error,
            'diagnostic_trail': trail,
        }

    def _write_log_file(self, outcome: str):
        """Write the buffered log lines to a file if log_dir is set."""
        if not self.log_dir or not self._log_lines:
            return
        try:
            import os
            os.makedirs(self.log_dir, exist_ok=True)
            hero = self.hero_id or 'nohero'
            seed = self.seed if self.seed is not None else 'noseed'
            filename = f"{hero}_s{seed}_{outcome}.log"
            self.log_path = os.path.join(self.log_dir, filename)
            with open(self.log_path, 'w') as f:
                f.write('\n'.join(self._log_lines))
                f.write('\n')
        except Exception:
            pass  # Don't let logging failures break the game

    def _diagnostic_trail(self, n=20) -> Dict[str, Any]:
        """Build a diagnostic snapshot for debugging stuck/timeout/error games.

        Returns the last N actions, current pending selection info, band state,
        and recent events — everything needed to understand what went wrong.
        """
        trail = {
            'last_actions': self.actions_log[-n:] if self.actions_log else [],
            'last_events': self.events_log[-n:] if self.events_log else [],
            'total_actions': len(self.actions_log),
            'total_events': len(self.events_log),
            'iterations': self.iterations,
            'stuck_iterations': self._stuck_iterations,
        }

        # Current game state
        if self.run:
            band = self.run.get_band()
            resources = self.run.get_resources()
            trail['state'] = {
                'events_count': self.run.events_count,
                'ring': self.run.current_ring,
                'position': self.run.ring_position,
                'health': self.run.health,
                'gold': resources.get('gold', 0),
                'band_size': len(band),
                'band': [f"{m.get('name','?')} {m.get('attack',0)}/{m.get('health',0)}" for m in band],
                'ghost_wins': self.ghost_wins,
                'in_sub_ring': SubRingController.is_in_sub_ring(self.run),
            }

            # Current pending selection (the thing we were stuck on)
            pending = self.run.get_pending_selection()
            if pending:
                options = pending.get('options', [])
                trail['pending'] = {
                    'event_type': pending.get('event_type', '?'),
                    'combat_type': pending.get('combat_type'),
                    'combat_complete': pending.get('combat_complete', False),
                    'leaveable': pending.get('leaveable', False),
                    'repeating': pending.get('repeating', False),
                    'min_selections': pending.get('min_selections'),
                    'max_selections': pending.get('max_selections'),
                    'num_options': len(options),
                    'option_ids': [o.get('id', '?') for o in options[:10]],
                    'option_types': [o.get('type', '?') for o in options[:10]],
                    'disabled_count': sum(1 for o in options if o.get('disabled')),
                }
            else:
                trail['pending'] = None

        return trail

    # ------------------------------------------------------------------
    # State inspection (for mid-game analysis)
    # ------------------------------------------------------------------

    def get_snapshot(self) -> Dict[str, Any]:
        """Get current game state snapshot for analysis."""
        if not self.run:
            return {}
        band = self.run.get_band()
        resources = self.run.get_resources()
        return {
            'run_id': self.run.id,
            'ring': self.run.current_ring,
            'position': self.run.ring_position,
            'zone': self.run.current_zone,
            'health': self.run.health,
            'gold': resources.get('gold', 0),
            'band_size': len(band),
            'band': band,
            'band_power': sum(m.get('attack', 0) + m.get('health', 0) for m in band),
            'events_count': self.run.events_count,
            'ghost_wins': self._count_ghost_wins(),
            'in_sub_ring': SubRingController.is_in_sub_ring(self.run),
            'pending_event_type': (self.run.get_pending_selection() or {}).get('event_type'),
            'iterations': self.iterations,
        }


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

def run_game(ai: Optional[DecisionAI] = None,
             seed: Optional[int] = None,
             hero_id: Optional[str] = None,
             verbose: bool = True) -> Dict[str, Any]:
    """Quick one-liner to run a game."""
    if ai is None:
        ai = SmartDecisionAI()
    runner = HeadlessGameRunner(ai, hero_id=hero_id, seed=seed, verbose=verbose)
    return runner.run_complete_game()


def run_batch(n: int = 10,
              ai_factory=None,
              seed_start: int = 1000,
              hero_id: Optional[str] = None,
              verbose: bool = False) -> List[Dict[str, Any]]:
    """Run multiple games and collect results."""
    if ai_factory is None:
        ai_factory = SmartDecisionAI
    results = []
    for i in range(n):
        ai = ai_factory()
        runner = HeadlessGameRunner(ai, hero_id=hero_id, seed=seed_start + i, verbose=verbose)
        result = runner.run_complete_game()
        results.append(result)
    return results
