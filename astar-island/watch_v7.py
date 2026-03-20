#!/usr/bin/env python3
"""
Watch for new rounds and auto-submit with V7 solver.
Polls every 30 seconds for active rounds.

V7 strategy:
1. Fast submit (regression-only, 0 queries)
2. Heavy regime detection (15-20 probes)
3. Refinement with remaining budget
4. Improved resubmit with Bayesian update
"""
import os, sys, json, time, warnings
import numpy as np
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(__file__))
from client import AstarClient
from config import GRID_SIZE, NUM_CLASSES
from predictor_v3 import PredictorV3
from solver_v5 import predict_with_group_priors
from solver_v7 import (
    detect_regime_heavy, build_empirical_counts, adaptive_blend_alpha,
    predict_ensemble, submit_predictions, refine_with_remaining,
    FLOOR, N_REGIME_PROBES,
)


def submit_round(client, rnd):
    """Submit predictions for a round using V7 multi-phase strategy."""
    round_id = rnd.id
    print("\n=== V7 Round %d: %s ===" % (rnd.round_number, round_id[:8]))
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

    # Phase 1: Fast submit
    print("\n--- Phase 1: Fast Submit ---")
    submit_predictions(client, round_id, rnd, r2_priors, r2_predictor,
                       alpha=0.20, floor=FLOOR, label="[fast] ")

    if queries_left <= 0:
        print("  No query budget. Done with fast submit only.")
        return True

    # Phase 2: Heavy regime detection
    n_probes = min(N_REGIME_PROBES, queries_left)
    print("\n--- Phase 2: Heavy Regime Detection (%d probes) ---" % n_probes)

    growth_score, sim_results, probes_done = detect_regime_heavy(
        client, round_id, rnd.initial_states, n_probes=n_probes)

    if growth_score > 0.3:
        print("  Regime: GROWTH (%.2f) -> R2 models" % growth_score)
        priors, predictor = r2_priors, r2_predictor
    elif growth_score < 0.1:
        print("  Regime: COLLAPSE (%.2f) -> R3 models" % growth_score)
        priors, predictor = r3_priors, r3_predictor
    else:
        print("  Regime: AMBIGUOUS (%.2f) -> R3 models" % growth_score)
        priors, predictor = r3_priors, r3_predictor

    alpha = adaptive_blend_alpha(probes_done, growth_score)
    print("  Adaptive alpha: %.2f" % alpha)

    # Phase 3: Refinement
    budget = client.get_budget()
    queries_left = budget['queries_max'] - budget['queries_used']
    print("\n--- Phase 3: Refinement (%d queries remaining) ---" % queries_left)

    if queries_left > 0:
        sim_results = refine_with_remaining(
            client, round_id, rnd, sim_results, queries_left, rnd.initial_states)

    counts_by_seed, nobs_by_seed = build_empirical_counts(sim_results, rnd.initial_states)
    total_obs = sum(n.sum() for n in nobs_by_seed.values())
    print("  Total observations: %d" % int(total_obs))

    # Phase 4: Improved resubmit
    print("\n--- Phase 4: Improved Resubmit ---")
    submit_predictions(client, round_id, rnd, priors, predictor,
                       alpha=alpha, floor=FLOOR, label="[improved] ",
                       counts_by_seed=counts_by_seed, nobs_by_seed=nobs_by_seed,
                       prior_strength=2.0)

    print("\nV7 Round %d done! (fast + improved)" % rnd.round_number)
    return True


def main():
    token = os.environ.get("ASTAR_TOKEN", "")
    if not token:
        print("Set ASTAR_TOKEN"); sys.exit(1)

    client = AstarClient(token)
    submitted_rounds = set()

    print("V7 Watching for new rounds... (Ctrl+C to stop)")

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
