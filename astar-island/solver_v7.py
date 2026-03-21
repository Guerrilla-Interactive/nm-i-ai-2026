#!/usr/bin/env python3
"""
Solver V7: Full-grid simulation + Bayesian update.

Improvements over V6:
1. Uses all 50 queries: 9 tiled viewports × 5 seeds = 45 queries covering entire 40×40 grid
2. Per-seed regime detection from simulation results (no wasted probes)
3. Bayesian update of ensemble prior with direct simulation observations
4. Port=0 enforcement for non-coastal cells in regression

Strategy:
1. For each seed, run 9 simulate calls tiling the full grid
2. Detect regime per-seed from simulation results (settlement survival)
3. Generate ensemble prior (regression + group) per-seed with regime-specific models
4. Bayesian update prior with simulation observations
5. Submit posterior predictions
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
    VP_TILES, VP_SIZE,
)

FLOOR = 0.001
BLEND_ALPHA = 0.05  # 5% group, 95% regression (optimized via LOO-CV)
PRIOR_STRENGTH = 10.0  # Dirichlet prior strength for Bayesian update (optimized)
# Disabled: validation shows Bayesian update hurts scores because single-observation sim data is too confident vs probabilistic ground truth
ENABLE_BAYESIAN_UPDATE = False


def simulate_full_grid(client, round_id, seed_idx):
    """Run 9 tiled simulations covering the full 40×40 grid for one seed.

    Returns list of simulation results (dicts with 'grid' and 'viewport').
    """
    results = []
    for vx, vy in VP_TILES:
        try:
            sim = client.simulate(round_id, seed_idx, vx, vy, VP_SIZE, VP_SIZE)
            results.append({
                'grid': sim.grid,
                'viewport': sim.viewport,
            })
        except Exception as e:
            print("    SIM ERROR seed=%d vp=(%d,%d): %s" % (seed_idx, vx, vy, e))
    return results


def detect_regime_from_sims(initial_grid, sim_results):
    """Detect growth/collapse regime from simulation results for one seed.

    Compares initial settlement count to simulated settlement count.
    Returns growth_score: high = growth, low = collapse.
    """
    total_initial = 0
    total_final = 0

    for sim in sim_results:
        vp = sim['viewport']
        vx, vy = vp['x'], vp['y']
        vw, vh = vp['w'], vp['h']

        for row_idx, y in enumerate(range(vy, vy + vh)):
            for col_idx, x in enumerate(range(vx, vx + vw)):
                if y < GRID_SIZE and x < GRID_SIZE:
                    # Count initial settlements
                    if initial_grid[y][x] in (1, 2):
                        total_initial += 1
                    # Count final settlements
                    if row_idx < len(sim['grid']) and col_idx < len(sim['grid'][row_idx]):
                        if sim['grid'][row_idx][col_idx] in (1, 2):
                            total_final += 1

    if total_initial == 0:
        return 0.5

    survival = total_final / total_initial
    return min(1.0, survival)


def predict_ensemble_with_coastal(initial_grid, priors, predictor, floor=FLOOR, alpha=BLEND_ALPHA):
    """Generate prediction by blending regression + group priors.
    Enforces port=0 for non-coastal cells in regression output.
    """
    # Regression prediction
    reg_pred = predictor.predict_from_initial(initial_grid, floor=floor)

    # Enforce port=0 for non-coastal cells in regression
    for y in range(GRID_SIZE):
        for x in range(GRID_SIZE):
            if not is_coastal(initial_grid, y, x):
                reg_pred[y, x, 2] = 0.0  # Port class
    # Renormalize regression after port zeroing
    reg_pred = np.maximum(reg_pred, floor)
    reg_pred = reg_pred / reg_pred.sum(axis=-1, keepdims=True)

    # Group prior prediction (already enforces port=0 for non-coastal)
    grp_pred = predict_with_group_priors(initial_grid, priors, floor=floor)

    # Blend
    pred = alpha * grp_pred + (1 - alpha) * reg_pred
    pred = np.maximum(pred, floor)
    pred = pred / pred.sum(axis=-1, keepdims=True)

    return pred


def bayesian_update(pred, sim_results, floor=FLOOR, prior_strength=PRIOR_STRENGTH):
    """Bayesian update of prediction using simulation observations.

    Uses Dirichlet conjugate update: posterior = prior_alpha + counts.
    """
    counts = np.zeros((GRID_SIZE, GRID_SIZE, NUM_CLASSES))
    n_obs = np.zeros((GRID_SIZE, GRID_SIZE))

    for sim in sim_results:
        vp = sim['viewport']
        vx, vy = vp['x'], vp['y']
        vw, vh = vp['w'], vp['h']

        for row_idx, y in enumerate(range(vy, vy + vh)):
            for col_idx, x in enumerate(range(vx, vx + vw)):
                if y < GRID_SIZE and x < GRID_SIZE:
                    if row_idx < len(sim['grid']) and col_idx < len(sim['grid'][row_idx]):
                        cell_code = sim['grid'][row_idx][col_idx]
                        class_idx = SIM_TO_CLASS.get(cell_code, 0)
                        counts[y, x, class_idx] += 1
                        n_obs[y, x] += 1

    # Bayesian update: Dirichlet posterior
    updated = pred.copy()
    observed_mask = n_obs > 0

    for y in range(GRID_SIZE):
        for x in range(GRID_SIZE):
            if observed_mask[y, x]:
                alpha_prior = prior_strength * pred[y, x]
                alpha_post = alpha_prior + counts[y, x]
                updated[y, x] = alpha_post / alpha_post.sum()

    # Floor and renormalize
    updated = np.maximum(updated, floor)
    updated = updated / updated.sum(axis=-1, keepdims=True)

    n_observed = int(observed_mask.sum())
    print("    Bayesian update: %d/%d cells observed" % (n_observed, GRID_SIZE * GRID_SIZE))

    return updated


def main():
    token = os.environ.get("ASTAR_TOKEN", "")
    if not token:
        print("Set ASTAR_TOKEN"); sys.exit(1)

    target_round_id = sys.argv[1] if len(sys.argv) > 1 else None

    client = AstarClient(token)

    if target_round_id:
        rnd = client.get_round(target_round_id)
        round_id = rnd.id
        print("=== Targeting Round %d: %s ===" % (rnd.round_number, round_id[:8]))
    else:
        rnd = client.get_active_round()
        if not rnd:
            print("No active round!")
            for r in client.get_rounds():
                print("  Round %d: %s" % (r.round_number, r.status))
            sys.exit(0)
        round_id = rnd.id
        print("=== Round %d: %s ===" % (rnd.round_number, round_id[:8]))

    print("  Seeds: %d, closes: %s" % (rnd.seeds_count, rnd.closes_at))

    budget = client.get_budget()
    queries_left = budget['queries_max'] - budget['queries_used']
    print("  Budget: %d/%d used, %d remaining" % (
        budget['queries_used'], budget['queries_max'], queries_left))

    # Load both model sets
    base = os.path.dirname(__file__)
    r2_priors = json.load(open(os.path.join(base, 'data/group_priors_r2.json')))
    r3_priors = json.load(open(os.path.join(base, 'data/group_priors_r3.json')))
    r2_predictor = PredictorV3(os.path.join(base, 'data/model_r2.json'))
    r3_predictor = PredictorV3(os.path.join(base, 'data/model_r3.json'))

    # Determine how many seeds we can fully simulate
    queries_per_seed = len(VP_TILES)  # 9
    max_seeds_simulated = min(rnd.seeds_count, queries_left // queries_per_seed)

    if max_seeds_simulated < rnd.seeds_count:
        print("  WARNING: Only enough budget for %d/%d seeds with full simulation" % (
            max_seeds_simulated, rnd.seeds_count))

    print("\n--- Step 1: Full-Grid Simulation (%d queries/seed × %d seeds = %d queries) ---" % (
        queries_per_seed, max_seeds_simulated, queries_per_seed * max_seeds_simulated))

    # Run simulations for each seed
    seed_sim_results = {}
    for seed_idx in range(max_seeds_simulated):
        initial_grid = rnd.initial_states[seed_idx].grid
        print("  Seed %d: simulating %d viewports..." % (seed_idx, queries_per_seed))
        sim_results = simulate_full_grid(client, round_id, seed_idx)
        seed_sim_results[seed_idx] = sim_results

        # Per-seed regime detection
        growth = detect_regime_from_sims(initial_grid, sim_results)
        print("    Got %d results, growth=%.2f" % (len(sim_results), growth))

    print("\n--- Step 2: Generate Predictions with Bayesian Update ---")
    print("  Blend: %.0f%% group + %.0f%% regression, floor=%.4f, prior_strength=%.1f" % (
        BLEND_ALPHA * 100, (1 - BLEND_ALPHA) * 100, FLOOR, PRIOR_STRENGTH))

    for seed_idx in range(rnd.seeds_count):
        initial_grid = rnd.initial_states[seed_idx].grid

        # Per-seed regime detection
        if seed_idx in seed_sim_results:
            growth = detect_regime_from_sims(initial_grid, seed_sim_results[seed_idx])
        else:
            growth = 0.5  # Fallback if no simulation data

        # Select models based on per-seed regime
        if growth > 0.3:
            regime = "GROWTH"
            priors, predictor = r2_priors, r2_predictor
        elif growth < 0.1:
            regime = "COLLAPSE"
            priors, predictor = r3_priors, r3_predictor
        else:
            regime = "AMBIGUOUS"
            priors, predictor = r3_priors, r3_predictor

        # Generate ensemble prior with coastal port enforcement
        pred = predict_ensemble_with_coastal(initial_grid, priors, predictor,
                                              floor=FLOOR, alpha=BLEND_ALPHA)

        # Bayesian update with simulation observations
        if ENABLE_BAYESIAN_UPDATE and seed_idx in seed_sim_results and seed_sim_results[seed_idx]:
            pred = bayesian_update(pred, seed_sim_results[seed_idx],
                                   floor=FLOOR, prior_strength=PRIOR_STRENGTH)

        # Validate
        assert pred.shape == (GRID_SIZE, GRID_SIZE, NUM_CLASSES)
        assert (pred >= FLOOR * 0.9).all(), "Min: %.8f" % pred.min()
        assert np.allclose(pred.sum(axis=-1), 1.0, atol=0.02)

        result = client.submit(round_id, seed_idx, pred.tolist())
        print("  Seed %d [%s growth=%.2f]: %s" % (seed_idx, regime, growth, result))

    print("\nDone! All %d seeds submitted." % rnd.seeds_count)


if __name__ == '__main__':
    main()
