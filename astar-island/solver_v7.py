#!/usr/bin/env python3
"""
Solver V7: Heavy regime detection + empirical refinement.

Improvements over V6:
1. 15-20 simulation queries for regime detection (not 3)
2. Multiple viewports per seed → empirical class distributions
3. Adaptive BLEND_ALPHA based on probe confidence
4. Fast initial submit (regression-only), then resubmit with simulation data
5. Floor 0.001
"""
import os, sys, json, warnings
import numpy as np
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(__file__))
from client import AstarClient
from config import GRID_SIZE, NUM_CLASSES, SIM_TO_CLASS
from predictor_v3 import PredictorV3, get_features

from solver_v5 import (
    is_coastal, count_neighbors, settle_bin, forest_bin,
    get_group_key, get_fallback_keys, predict_with_group_priors,
    find_best_settlement_viewport, VP_TILES, VP_SIZE,
)

FLOOR = 0.001
N_REGIME_PROBES = 18  # target probes for regime detection


def detect_regime_heavy(client, round_id, initial_states, n_probes=N_REGIME_PROBES):
    """
    Heavy regime detection using many probes across seeds and viewports.
    Returns (growth_score, sim_results_by_seed) where sim_results_by_seed
    maps seed_idx -> list of SimulationResult objects.
    """
    n_seeds = len(initial_states)
    sim_results = {i: [] for i in range(n_seeds)}

    # Plan probes: spread across seeds × viewports for maximum coverage
    # Prioritize settlement-rich viewports first, then fill with others
    probe_plan = []
    for seed_idx in range(n_seeds):
        grid = initial_states[seed_idx].grid
        # Score each viewport by settlement count
        vp_scores = []
        for vx, vy in VP_TILES:
            count = 0
            for y in range(vy, min(vy + VP_SIZE, GRID_SIZE)):
                for x in range(vx, min(vx + VP_SIZE, GRID_SIZE)):
                    if grid[y][x] in (1, 2, 3):
                        count += 1
            vp_scores.append(((vx, vy), count, seed_idx))
        # Sort by settlement count descending
        vp_scores.sort(key=lambda t: -t[1])
        for vp, score, si in vp_scores:
            probe_plan.append((si, vp[0], vp[1], score))

    # Interleave seeds: take top viewport from each seed, then second, etc.
    interleaved = []
    max_vps = len(VP_TILES)
    for rank in range(max_vps):
        for seed_idx in range(n_seeds):
            idx = seed_idx * max_vps + rank
            if idx < len(probe_plan):
                interleaved.append(probe_plan[idx])

    # Execute probes
    total_initial_settle = 0
    total_final_settle = 0
    probes_done = 0

    for seed_idx, vx, vy, settle_count in interleaved:
        if probes_done >= n_probes:
            break

        print("  Probe %d: seed=%d vp=(%d,%d) settlements=%d" % (
            probes_done, seed_idx, vx, vy, settle_count))

        try:
            result = client.simulate(round_id, seed_idx, vx, vy, VP_SIZE, VP_SIZE)
            sim_results[seed_idx].append(result)
            probes_done += 1

            # Count initial settlements in viewport
            grid = initial_states[seed_idx].grid
            for y in range(vy, min(vy + VP_SIZE, GRID_SIZE)):
                for x in range(vx, min(vx + VP_SIZE, GRID_SIZE)):
                    if grid[y][x] in (1, 2):
                        total_initial_settle += 1

            # Count final settlements
            for row_idx, y in enumerate(range(vy, min(vy + VP_SIZE, GRID_SIZE))):
                for col_idx, x in enumerate(range(vx, min(vx + VP_SIZE, GRID_SIZE))):
                    if row_idx < len(result.grid) and col_idx < len(result.grid[row_idx]):
                        if result.grid[row_idx][col_idx] in (1, 2):
                            total_final_settle += 1

        except Exception as e:
            print("    ERROR: %s" % e)

    if total_initial_settle == 0:
        growth_score = 0.5
    else:
        survival = total_final_settle / total_initial_settle
        growth_score = min(1.0, survival)

    print("  Settlement survival: %d/%d = %.2f (probes=%d)" % (
        total_final_settle, total_initial_settle, growth_score, probes_done))

    return growth_score, sim_results, probes_done


def build_empirical_counts(sim_results_by_seed, initial_states):
    """
    Build empirical observation counts from simulation results.
    Returns counts[seed_idx] = (40, 40, 6) array of observation counts,
    and n_obs[seed_idx] = (40, 40) array of observation counts per cell.
    """
    n_seeds = len(initial_states)
    all_counts = {}
    all_n_obs = {}

    for seed_idx in range(n_seeds):
        counts = np.zeros((GRID_SIZE, GRID_SIZE, NUM_CLASSES))
        n_obs = np.zeros((GRID_SIZE, GRID_SIZE))

        for sim in sim_results_by_seed.get(seed_idx, []):
            vp = sim.viewport
            vx, vy = vp['x'], vp['y']
            vw, vh = vp['w'], vp['h']

            for row_idx, y in enumerate(range(vy, vy + vh)):
                for col_idx, x in enumerate(range(vx, vx + vw)):
                    if y < GRID_SIZE and x < GRID_SIZE:
                        if row_idx < len(sim.grid) and col_idx < len(sim.grid[row_idx]):
                            cell_code = sim.grid[row_idx][col_idx]
                            class_idx = SIM_TO_CLASS.get(cell_code, 0)
                            counts[y, x, class_idx] += 1
                            n_obs[y, x] += 1

        all_counts[seed_idx] = counts
        all_n_obs[seed_idx] = n_obs

    return all_counts, all_n_obs


def adaptive_blend_alpha(n_probes, growth_score):
    """
    Adaptive blend alpha based on number of probes and regime confidence.

    More probes → more confident regime detection → more weight on group priors.
    Ambiguous regime → less weight on group priors.
    """
    # Base alpha from probe count (more probes = more confidence)
    if n_probes >= 15:
        base_alpha = 0.30
    elif n_probes >= 10:
        base_alpha = 0.25
    elif n_probes >= 5:
        base_alpha = 0.20
    else:
        base_alpha = 0.15

    # Regime confidence: high or low growth_score = confident, middle = uncertain
    confidence = abs(growth_score - 0.5) * 2  # 0 = ambiguous, 1 = certain
    # Scale alpha: confident regime → boost alpha slightly
    alpha = base_alpha * (0.8 + 0.4 * confidence)

    return min(0.40, max(0.10, alpha))


def bayesian_update(pred, counts, n_obs, prior_strength=2.0, floor=FLOOR):
    """
    Bayesian update: blend regression prior with empirical counts.
    Only updates cells that have observations.
    """
    updated = pred.copy()
    observed_cells = 0

    for y in range(GRID_SIZE):
        for x in range(GRID_SIZE):
            if n_obs[y, x] > 0:
                alpha_prior = prior_strength * pred[y, x]
                alpha_post = alpha_prior + counts[y, x]
                updated[y, x] = alpha_post / alpha_post.sum()
                observed_cells += 1

    updated = np.maximum(updated, floor)
    updated = updated / updated.sum(axis=-1, keepdims=True)
    return updated, observed_cells


def predict_ensemble(initial_grid, priors, predictor, floor=FLOOR, alpha=0.2):
    """Generate prediction by blending regression + group priors."""
    reg_pred = predictor.predict_from_initial(initial_grid, floor=floor)
    grp_pred = predict_with_group_priors(initial_grid, priors, floor=floor)

    pred = alpha * grp_pred + (1 - alpha) * reg_pred
    pred = np.maximum(pred, floor)
    pred = pred / pred.sum(axis=-1, keepdims=True)
    return pred


def submit_predictions(client, round_id, rnd, priors, predictor, alpha, floor,
                       label="", counts_by_seed=None, nobs_by_seed=None,
                       prior_strength=2.0):
    """Submit predictions for all seeds. Optionally apply Bayesian update."""
    for seed_idx in range(rnd.seeds_count):
        grid = rnd.initial_states[seed_idx].grid

        pred = predict_ensemble(grid, priors, predictor, floor=floor, alpha=alpha)

        # Apply Bayesian update if we have simulation data for this seed
        obs_cells = 0
        if counts_by_seed and nobs_by_seed:
            counts = counts_by_seed.get(seed_idx)
            n_obs = nobs_by_seed.get(seed_idx)
            if counts is not None and n_obs is not None and n_obs.sum() > 0:
                pred, obs_cells = bayesian_update(
                    pred, counts, n_obs, prior_strength=prior_strength, floor=floor)

        # Validate
        assert pred.shape == (GRID_SIZE, GRID_SIZE, NUM_CLASSES)
        assert (pred >= floor * 0.9).all(), "Min: %.8f" % pred.min()
        assert np.allclose(pred.sum(axis=-1), 1.0, atol=0.02)

        result = client.submit(round_id, seed_idx, pred.tolist())
        obs_info = " (%d observed cells)" % obs_cells if obs_cells > 0 else ""
        print("  %sSeed %d: %s%s" % (label, seed_idx, result, obs_info))


def refine_with_remaining(client, round_id, rnd, sim_results_by_seed,
                          queries_remaining, initial_states):
    """
    Use remaining query budget for targeted refinement.
    Focus on seeds/viewports not yet covered.
    Returns updated sim_results_by_seed.
    """
    if queries_remaining <= 0:
        return sim_results_by_seed

    n_seeds = len(initial_states)

    # Find uncovered viewports per seed
    covered = {i: set() for i in range(n_seeds)}
    for seed_idx, sims in sim_results_by_seed.items():
        for sim in sims:
            vp = sim.viewport
            covered[seed_idx].add((vp['x'], vp['y']))

    # Plan: prioritize seeds with fewest observations
    refine_plan = []
    for seed_idx in range(n_seeds):
        grid = initial_states[seed_idx].grid
        for vx, vy in VP_TILES:
            if (vx, vy) not in covered[seed_idx]:
                # Score by settlement count
                count = 0
                for y in range(vy, min(vy + VP_SIZE, GRID_SIZE)):
                    for x in range(vx, min(vx + VP_SIZE, GRID_SIZE)):
                        if grid[y][x] in (1, 2, 3, 4):  # dynamic cells
                            count += 1
                refine_plan.append((seed_idx, vx, vy, count))

    # Sort by dynamic cell count descending
    refine_plan.sort(key=lambda t: -t[3])

    probes_done = 0
    for seed_idx, vx, vy, dyn_count in refine_plan:
        if probes_done >= queries_remaining:
            break

        try:
            result = client.simulate(round_id, seed_idx, vx, vy, VP_SIZE, VP_SIZE)
            sim_results_by_seed[seed_idx].append(result)
            probes_done += 1
            print("  Refine probe %d: seed=%d vp=(%d,%d) dynamic=%d" % (
                probes_done, seed_idx, vx, vy, dyn_count))
        except Exception as e:
            print("    Refine ERROR: %s" % e)

    print("  Refinement: %d additional probes" % probes_done)
    return sim_results_by_seed


def main():
    token = os.environ.get("ASTAR_TOKEN", "")
    if not token:
        print("Set ASTAR_TOKEN"); sys.exit(1)

    target_round_id = sys.argv[1] if len(sys.argv) > 1 else None

    client = AstarClient(token)

    if target_round_id:
        rnd = client.get_round(target_round_id)
        round_id = rnd.id
        print("=== V7 Targeting Round %d: %s ===" % (rnd.round_number, round_id[:8]))
    else:
        rnd = client.get_active_round()
        if not rnd:
            print("No active round!")
            for r in client.get_rounds():
                print("  Round %d: %s" % (r.round_number, r.status))
            sys.exit(0)
        round_id = rnd.id
        print("=== V7 Round %d: %s ===" % (rnd.round_number, round_id[:8]))

    print("  Seeds: %d, closes: %s" % (rnd.seeds_count, rnd.closes_at))

    budget = client.get_budget()
    queries_left = budget['queries_max'] - budget['queries_used']
    print("  Budget: %d/%d used, %d remaining" % (
        budget['queries_used'], budget['queries_max'], queries_left))

    # Load models
    base = os.path.dirname(__file__)
    r2_priors = json.load(open(os.path.join(base, 'data/group_priors_r2.json')))
    r3_priors = json.load(open(os.path.join(base, 'data/group_priors_r3.json')))
    r2_predictor = PredictorV3(os.path.join(base, 'data/model_r2.json'))
    r3_predictor = PredictorV3(os.path.join(base, 'data/model_r3.json'))

    # ======== PHASE 1: Fast initial submit (no queries used) ========
    print("\n--- Phase 1: Fast Submit (regression-only, no probes) ---")
    # Use R2 as default (growth is more common)
    submit_predictions(client, round_id, rnd, r2_priors, r2_predictor,
                       alpha=0.20, floor=FLOOR, label="[fast] ")

    if queries_left <= 0:
        print("\nNo query budget remaining. Done with fast submit only.")
        return

    # ======== PHASE 2: Heavy regime detection ========
    n_probes = min(N_REGIME_PROBES, queries_left)
    print("\n--- Phase 2: Heavy Regime Detection (%d probes) ---" % n_probes)

    growth_score, sim_results, probes_done = detect_regime_heavy(
        client, round_id, rnd.initial_states, n_probes=n_probes)

    # Select regime
    if growth_score > 0.3:
        print("  Regime: GROWTH (%.2f) -> R2 models" % growth_score)
        priors, predictor = r2_priors, r2_predictor
    elif growth_score < 0.1:
        print("  Regime: COLLAPSE (%.2f) -> R3 models" % growth_score)
        priors, predictor = r3_priors, r3_predictor
    else:
        print("  Regime: AMBIGUOUS (%.2f) -> R3 models (conservative)" % growth_score)
        priors, predictor = r3_priors, r3_predictor

    alpha = adaptive_blend_alpha(probes_done, growth_score)
    print("  Adaptive alpha: %.2f (probes=%d, growth=%.2f)" % (
        alpha, probes_done, growth_score))

    # ======== PHASE 3: Refinement with remaining budget ========
    budget = client.get_budget()
    queries_left = budget['queries_max'] - budget['queries_used']
    print("\n--- Phase 3: Refinement (%d queries remaining) ---" % queries_left)

    if queries_left > 0:
        sim_results = refine_with_remaining(
            client, round_id, rnd, sim_results, queries_left, rnd.initial_states)

    # Build empirical counts from all simulations
    counts_by_seed, nobs_by_seed = build_empirical_counts(sim_results, rnd.initial_states)

    total_obs = sum(n.sum() for n in nobs_by_seed.values())
    print("  Total observed cell-observations: %d" % int(total_obs))

    # ======== PHASE 4: Improved resubmit ========
    print("\n--- Phase 4: Improved Resubmit (alpha=%.2f, floor=%.4f) ---" % (alpha, FLOOR))
    submit_predictions(client, round_id, rnd, priors, predictor,
                       alpha=alpha, floor=FLOOR, label="[improved] ",
                       counts_by_seed=counts_by_seed, nobs_by_seed=nobs_by_seed,
                       prior_strength=2.0)

    print("\nV7 Done! All %d seeds submitted (fast + improved)." % rnd.seeds_count)


if __name__ == '__main__':
    main()
