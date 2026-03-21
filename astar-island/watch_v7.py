#!/usr/bin/env python3
"""
Watch for new rounds and auto-submit with V7 full-grid Bayesian solver.
Polls every 30 seconds for active rounds.
Uses all 50 queries: 9 tiled viewports × 5 seeds for full-grid coverage
+ per-seed regime detection + Bayesian update of predictions.
"""
import os, sys, json, time, warnings
import numpy as np
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(__file__))
from client import AstarClient
from config import GRID_SIZE, NUM_CLASSES
from predictor_v3 import PredictorV3
from solver_v5 import VP_TILES, VP_SIZE
from solver_v7 import (
    simulate_full_grid, detect_regime_from_sims,
    predict_ensemble_with_coastal, bayesian_update,
    FLOOR, BLEND_ALPHA, PRIOR_STRENGTH,
)


def submit_round(client, rnd):
    """Submit predictions for a round using V7 full-grid Bayesian solver."""
    round_id = rnd.id
    print("\n=== Round %d: %s ===" % (rnd.round_number, round_id[:8]))
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

    print("\n--- Step 1: Full-Grid Simulation (%d queries/seed x %d seeds = %d queries) ---" % (
        queries_per_seed, max_seeds_simulated, queries_per_seed * max_seeds_simulated))

    # Run simulations for each seed
    seed_sim_results = {}
    for seed_idx in range(max_seeds_simulated):
        initial_grid = rnd.initial_states[seed_idx].grid
        print("  Seed %d: simulating %d viewports..." % (seed_idx, queries_per_seed))
        sim_results = simulate_full_grid(client, round_id, seed_idx)
        seed_sim_results[seed_idx] = sim_results

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
            growth = 0.5

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
        if seed_idx in seed_sim_results and seed_sim_results[seed_idx]:
            pred = bayesian_update(pred, seed_sim_results[seed_idx],
                                   floor=FLOOR, prior_strength=PRIOR_STRENGTH)

        # Validate
        assert pred.shape == (GRID_SIZE, GRID_SIZE, NUM_CLASSES)
        assert (pred >= FLOOR * 0.9).all(), "Min: %.8f" % pred.min()
        assert np.allclose(pred.sum(axis=-1), 1.0, atol=0.02)

        result = client.submit(round_id, seed_idx, pred.tolist())
        print("  Seed %d [%s growth=%.2f]: %s" % (seed_idx, regime, growth, result))

    print("\nRound %d submitted!" % rnd.round_number)
    return True


def main():
    token = os.environ.get("ASTAR_TOKEN", "")
    if not token:
        print("Set ASTAR_TOKEN"); sys.exit(1)

    client = AstarClient(token)
    submitted_rounds = set()

    print("Watching for new rounds (V7 full-grid Bayesian)... (Ctrl+C to stop)")

    while True:
        try:
            active = client.get_active_round()
            if active and active.id not in submitted_rounds:
                success = submit_round(client, active)
                if success:
                    submitted_rounds.add(active.id)
            else:
                if active:
                    print(".", end="", flush=True)
                else:
                    print("x", end="", flush=True)

            time.sleep(30)

        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as e:
            print("\nError: %s" % e)
            time.sleep(30)


if __name__ == '__main__':
    main()
