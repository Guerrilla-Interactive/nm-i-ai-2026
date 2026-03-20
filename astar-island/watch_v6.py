#!/usr/bin/env python3
"""
Watch for new rounds and auto-submit with V6 ensemble solver.
Polls every 30 seconds for active rounds.
Uses regime detection (3 simulation probes) + ensemble prediction.
"""
import os, sys, json, time, warnings
import numpy as np
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(__file__))
from client import AstarClient
from config import GRID_SIZE, NUM_CLASSES
from predictor_v3 import PredictorV3
from solver_v5 import (
    predict_with_group_priors, detect_regime,
    find_best_settlement_viewport, VP_TILES, VP_SIZE,
)

FLOOR = 0.0001
BLEND_ALPHA = 0.2

def submit_round(client, rnd):
    """Submit predictions for a round using V6 ensemble."""
    round_id = rnd.id
    print("\n=== Round %d: %s ===" % (rnd.round_number, round_id[:8]))
    print("  Seeds: %d, closes: %s" % (rnd.seeds_count, rnd.closes_at))

    budget = client.get_budget()
    queries_left = budget['queries_max'] - budget['queries_used']
    print("  Budget: %d/%d used, %d remaining" % (
        budget['queries_used'], budget['queries_max'], queries_left))

    # Regime detection
    n_probes = min(3, queries_left)
    if n_probes > 0 and rnd.initial_states:
        print("\n--- Regime Detection (%d probes) ---" % n_probes)
        growth_score = detect_regime(client, round_id, rnd.initial_states, n_probes)
    else:
        print("\n--- No budget for probes, defaulting to combined ---")
        growth_score = 0.5

    # Load models
    base = os.path.dirname(__file__)
    r2_priors = json.load(open(os.path.join(base, 'data/group_priors_r2.json')))
    r3_priors = json.load(open(os.path.join(base, 'data/group_priors_r3.json')))
    r2_model = PredictorV3(os.path.join(base, 'data/model_r2.json'))
    r3_model = PredictorV3(os.path.join(base, 'data/model_r3.json'))

    if growth_score > 0.3:
        print("  Regime: GROWTH (%.2f) -> R2 models" % growth_score)
        priors, predictor = r2_priors, r2_model
    elif growth_score < 0.1:
        print("  Regime: COLLAPSE (%.2f) -> R3 models" % growth_score)
        priors, predictor = r3_priors, r3_model
    else:
        print("  Regime: AMBIGUOUS (%.2f) -> R3 models (conservative)" % growth_score)
        priors, predictor = r3_priors, r3_model

    # Submit
    print("\n--- Submitting (%.0f%% group + %.0f%% regression, floor=%.4f) ---" % (
        BLEND_ALPHA*100, (1-BLEND_ALPHA)*100, FLOOR))

    for seed_idx in range(rnd.seeds_count):
        grid = rnd.initial_states[seed_idx].grid
        reg_pred = predictor.predict_from_initial(grid, floor=FLOOR)
        grp_pred = predict_with_group_priors(grid, priors, floor=FLOOR)
        pred = BLEND_ALPHA * grp_pred + (1 - BLEND_ALPHA) * reg_pred
        pred = np.maximum(pred, FLOOR)
        pred = pred / pred.sum(axis=-1, keepdims=True)

        assert pred.shape == (GRID_SIZE, GRID_SIZE, NUM_CLASSES)
        assert (pred >= FLOOR * 0.9).all(), "Min: %.8f" % pred.min()

        result = client.submit(round_id, seed_idx, pred.tolist())
        print("  Seed %d: %s" % (seed_idx, result))

    print("\nRound %d submitted!" % rnd.round_number)
    return True


def main():
    token = os.environ.get("ASTAR_TOKEN", "")
    if not token:
        print("Set ASTAR_TOKEN"); sys.exit(1)

    client = AstarClient(token)
    submitted_rounds = set()

    print("Watching for new rounds... (Ctrl+C to stop)")

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
