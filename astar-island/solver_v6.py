#!/usr/bin/env python3
"""
Solver V6: Ensemble of regression + group priors with regime detection.

LOO-CV scores:
  R2=93.00, R3=89.03, avg=91.02

Strategy:
1. Use 3 simulation queries to detect regime (growth vs collapse)
2. Load regime-specific regression model + group priors
3. Blend: 20% group priors + 80% regression
4. floor=0.0001 for best KL scoring
5. Submit all 5 seeds
"""
import os, sys, json, warnings
import numpy as np
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(__file__))
from client import AstarClient
from config import GRID_SIZE, NUM_CLASSES
from predictor_v3 import PredictorV3, get_features

# Import group prior helpers
from solver_v5 import (
    is_coastal, count_neighbors, settle_bin, forest_bin,
    get_group_key, get_fallback_keys, predict_with_group_priors,
    find_best_settlement_viewport, detect_regime,
    VP_TILES, VP_SIZE,
)

FLOOR = 0.0001
BLEND_ALPHA = 0.2  # 20% group, 80% regression


def predict_ensemble(initial_grid, priors, predictor, floor=FLOOR, alpha=BLEND_ALPHA):
    """Generate prediction by blending regression + group priors."""
    # Regression prediction
    reg_pred = predictor.predict_from_initial(initial_grid, floor=floor)

    # Group prior prediction
    grp_pred = predict_with_group_priors(initial_grid, priors, floor=floor)

    # Blend
    pred = alpha * grp_pred + (1 - alpha) * reg_pred
    pred = np.maximum(pred, floor)
    pred = pred / pred.sum(axis=-1, keepdims=True)

    return pred


def main():
    token = os.environ.get("ASTAR_TOKEN", "")
    if not token:
        print("Set ASTAR_TOKEN"); sys.exit(1)

    # Allow passing round_id as argument for resubmission
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

    # Step 1: Regime detection
    n_probes = min(3, queries_left)
    if n_probes > 0 and rnd.initial_states:
        print("\n--- Step 1: Regime Detection (%d probes) ---" % n_probes)
        growth_score = detect_regime(client, round_id, rnd.initial_states, n_probes)
    else:
        print("\n--- Step 1: No budget/data for probes ---")
        growth_score = 0.5

    # Step 2: Select models
    print("\n--- Step 2: Select Models (growth=%.2f) ---" % growth_score)

    r2_priors = json.load(open(os.path.join(os.path.dirname(__file__), 'data/group_priors_r2.json')))
    r3_priors = json.load(open(os.path.join(os.path.dirname(__file__), 'data/group_priors_r3.json')))

    r2_model = os.path.join(os.path.dirname(__file__), 'data/model_r2.json')
    r3_model = os.path.join(os.path.dirname(__file__), 'data/model_r3.json')

    if growth_score > 0.3:
        print("  Regime: GROWTH -> R2 models")
        priors = r2_priors
        predictor = PredictorV3(r2_model)
    elif growth_score < 0.1:
        print("  Regime: COLLAPSE -> R3 models")
        priors = r3_priors
        predictor = PredictorV3(r3_model)
    else:
        # Ambiguous: use R3 priors (safer — lower variance)
        print("  Regime: AMBIGUOUS -> R3 models (conservative)")
        priors = r3_priors
        predictor = PredictorV3(r3_model)

    # Step 3: Submit predictions
    print("\n--- Step 3: Submit Predictions ---")
    print("  Blend: %.0f%% group + %.0f%% regression, floor=%.4f" % (
        BLEND_ALPHA * 100, (1 - BLEND_ALPHA) * 100, FLOOR))

    for seed_idx in range(rnd.seeds_count):
        initial_grid = rnd.initial_states[seed_idx].grid

        pred = predict_ensemble(initial_grid, priors, predictor, floor=FLOOR, alpha=BLEND_ALPHA)

        # Validate
        assert pred.shape == (GRID_SIZE, GRID_SIZE, NUM_CLASSES)
        assert (pred >= FLOOR * 0.9).all(), "Min: %.8f" % pred.min()
        assert np.allclose(pred.sum(axis=-1), 1.0, atol=0.02)

        result = client.submit(round_id, seed_idx, pred.tolist())
        print("  Seed %d: %s" % (seed_idx, result))

    print("\nDone! All %d seeds submitted." % rnd.seeds_count)


if __name__ == '__main__':
    main()
