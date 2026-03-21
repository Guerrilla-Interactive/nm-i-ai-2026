#!/usr/bin/env python3
"""
Solver V8: 3-regime solver with retrained models (RETRAIN-RESULTS.md + FAILURE-ANALYSIS-R7R8.md).

Strategy:
1. FLOOR = 0.0001, BLEND_ALPHA = 0.1 (calibrated optimal)
2. NO Bayesian cell-level updates (proven to cost 5-10 pts with sparse observations)
3. Only 3 regime detection probes measuring survival + cell change rate
4. Phase 1: instant R2 submit (safe baseline — best score kept per competition rules)
5. Phase 2: 3 probes to detect regime (HEAVY_GROWTH / LIGHT_GROWTH / COLLAPSE)
6. Phase 3: resubmit only when a BETTER model is identified:
   - HEAVY_GROWTH (>75% cells change): keep R2 (already optimal: 93.6, 82.5)
   - LIGHT_GROWTH (<75% cells change): new growth model (+3 to +6 vs R2)
   - COLLAPSE (survival <10%): new collapse model (+40 vs old R3 on deep collapse)
7. Default ambiguous regime to R2 (growth is 7x more common than collapse)
"""
import os, sys, json, time, warnings
import numpy as np
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(__file__))
from client import AstarClient
from config import GRID_SIZE, NUM_CLASSES, SIM_TO_CLASS
from predictor_v3 import PredictorV3, get_features

from solver_v5 import (
    is_coastal, count_neighbors, settle_bin, forest_bin,
    get_group_key, get_fallback_keys, predict_with_group_priors,
    VP_SIZE,
)

FLOOR = 0.0001
BLEND_ALPHA = 0.1
N_REGIME_PROBES = 3

# 3 diverse viewports for regime detection (spread across grid)
REGIME_PROBE_VIEWPORTS = [
    (0, 0),    # top-left
    (13, 13),  # center
    (25, 25),  # bottom-right
]


def predict_ensemble(initial_grid, priors, predictor, alpha=BLEND_ALPHA, floor=FLOOR):
    """Generate prediction by blending regression prior + group priors."""
    reg_pred = predictor.predict_from_initial(initial_grid, floor=floor)
    grp_pred = predict_with_group_priors(initial_grid, priors, floor=floor)

    pred = alpha * grp_pred + (1 - alpha) * reg_pred
    pred = np.maximum(pred, floor)
    pred = pred / pred.sum(axis=-1, keepdims=True)
    return pred


def detect_regime_from_observations(sim_results, initial_states):
    """
    Detect regime from observation data.
    Returns (survival_ratio, cell_change_rate).
    - survival: settlement survival (higher = more growth)
    - cell_change_rate: fraction of cells that changed terrain type (0-1)
    """
    total_initial_settle = 0
    total_final_settle = 0
    total_cells = 0
    total_changed = 0

    for seed_idx, sims in sim_results.items():
        grid = initial_states[seed_idx].grid
        for sim in sims:
            vp = sim.viewport
            vx, vy = vp['x'], vp['y']
            vw, vh = vp['w'], vp['h']

            for row_idx, y in enumerate(range(vy, min(vy + vh, GRID_SIZE))):
                for col_idx, x in enumerate(range(vx, min(vx + vw, GRID_SIZE))):
                    if grid[y][x] in (1, 2):
                        total_initial_settle += 1
                    if row_idx < len(sim.grid) and col_idx < len(sim.grid[row_idx]):
                        sim_code = sim.grid[row_idx][col_idx]
                        if sim_code in (1, 2):
                            total_final_settle += 1
                        # Count cell changes
                        total_cells += 1
                        init_code = grid[y][x]
                        if sim_code != init_code:
                            total_changed += 1

    survival = 0.5
    if total_initial_settle > 0:
        survival = min(1.0, total_final_settle / total_initial_settle)

    change_rate = 0.5
    if total_cells > 0:
        change_rate = total_changed / total_cells

    return survival, change_rate


def run_regime_probes(client, round_id, initial_states):
    """
    Run 3 regime detection probes across different seeds.
    Returns (sim_results_by_seed, queries_used).
    """
    n_seeds = len(initial_states)
    sim_results = {i: [] for i in range(n_seeds)}
    queries_used = 0

    # Spread 3 probes: one per seed (up to 3 seeds), each at a different viewport
    for probe_idx in range(min(N_REGIME_PROBES, len(REGIME_PROBE_VIEWPORTS))):
        seed_idx = probe_idx % n_seeds
        vx, vy = REGIME_PROBE_VIEWPORTS[probe_idx]

        try:
            result = client.simulate(round_id, seed_idx, vx, vy, VP_SIZE, VP_SIZE)
            sim_results[seed_idx].append(result)
            queries_used += 1
            print("  Probe %d: seed=%d vp=(%2d,%2d) [%d/%d budget]" % (
                probe_idx + 1, seed_idx, vx, vy,
                result.queries_used, result.queries_max))
        except Exception as e:
            print("  Probe %d: ERROR seed=%d vp=(%d,%d): %s" % (
                probe_idx + 1, seed_idx, vx, vy, e))
            time.sleep(1)

    return sim_results, queries_used


def submit_all_seeds(client, round_id, rnd, priors, predictor, alpha, floor, label=""):
    """Submit predictions for all seeds using regression + group priors only."""
    for seed_idx in range(rnd.seeds_count):
        grid = rnd.initial_states[seed_idx].grid

        pred = predict_ensemble(grid, priors, predictor, alpha=alpha, floor=floor)

        # Validate
        assert pred.shape == (GRID_SIZE, GRID_SIZE, NUM_CLASSES)
        assert (pred >= floor * 0.9).all(), "Min prob: %.8f (floor: %.6f)" % (
            pred.min(), floor)
        assert np.allclose(pred.sum(axis=-1), 1.0, atol=0.02), "Sum range: %.4f-%.4f" % (
            pred.sum(axis=-1).min(), pred.sum(axis=-1).max())

        result = client.submit(round_id, seed_idx, pred.tolist())
        print("  %sSeed %d: %s" % (label, seed_idx, result))


def solve_round_with_client(client, rnd):
    """Solve a round using an existing client and round object."""
    round_id = rnd.id
    print("=== V8 Round %d: %s ===" % (rnd.round_number, round_id[:8]))
    print("  Seeds: %d, closes: %s" % (rnd.seeds_count, rnd.closes_at))

    budget = client.get_budget()
    queries_left = budget['queries_max'] - budget['queries_used']
    print("  Budget: %d/%d used, %d remaining" % (
        budget['queries_used'], budget['queries_max'], queries_left))

    # Load ALL models (old + new)
    base = os.path.dirname(__file__)
    # Old models (safe baseline)
    r2_priors = json.load(open(os.path.join(base, 'data/group_priors_r2.json')))
    r2_predictor = PredictorV3(os.path.join(base, 'data/model_r2.json'))
    # New retrained models
    growth_priors = json.load(open(os.path.join(base, 'data/group_priors_growth.json')))
    growth_predictor = PredictorV3(os.path.join(base, 'data/model_growth.json'))
    collapse_priors = json.load(open(os.path.join(base, 'data/group_priors_collapse.json')))
    collapse_predictor = PredictorV3(os.path.join(base, 'data/model_collapse.json'))

    # ======== PHASE 1: Instant R2 (growth) submit — safe baseline ========
    print("\n--- Phase 1: Fast Submit (R2/growth, alpha=%.1f, floor=%.4f) ---" % (
        BLEND_ALPHA, FLOOR))
    submit_all_seeds(client, round_id, rnd, r2_priors, r2_predictor,
                     alpha=BLEND_ALPHA, floor=FLOOR, label="[R2-fast] ")

    if queries_left <= 0:
        print("\nNo query budget remaining. Done with R2 fast submit only.")
        return True

    # ======== PHASE 2: Regime Detection (3 probes) ========
    print("\n--- Phase 2: Regime Detection (3 probes) ---")
    sim_results, n_probes = run_regime_probes(client, round_id, rnd.initial_states)

    if n_probes == 0:
        print("  No probes succeeded. Keeping R2 fast submit.")
        return True

    survival, change_rate = detect_regime_from_observations(sim_results, rnd.initial_states)
    print("  Survival: %.2f, Cell change rate: %.1f%%" % (survival, change_rate * 100))

    # 3-regime decision based on validated simulation probes:
    #
    # Heavy growth (R2, R6): change_rate > 25% (R2=25.8%, R6=34.2%). R2 model best.
    # Light growth (R4, R5, R7, R9): survival=1.0, change 15-22%. Growth model best.
    # Collapse (R3, R8): survival < 0.80 AND change_rate < 15% (R3=0.082/4.8%, R8=0.752/9.0%).
    #
    # Thresholds validated against R2-R9 ground truth data.

    if survival < 0.80 and change_rate < 0.15:
        regime = "COLLAPSE"
        priors, predictor = collapse_priors, collapse_predictor
    elif change_rate > 0.25:
        regime = "HEAVY_GROWTH"
        priors, predictor = r2_priors, r2_predictor  # Keep R2
    elif survival > 0.2:
        regime = "LIGHT_GROWTH"
        priors, predictor = growth_priors, growth_predictor
    else:
        regime = "AMBIGUOUS->GROWTH"
        priors, predictor = r2_priors, r2_predictor

    print("  Regime: %s" % regime)

    # ======== PHASE 3: Resubmit only if better model identified ========
    if regime == "COLLAPSE":
        print("\n--- Phase 3: Resubmit with new COLLAPSE model ---")
        submit_all_seeds(client, round_id, rnd, priors, predictor,
                         alpha=BLEND_ALPHA, floor=FLOOR, label="[collapse] ")
    elif regime == "LIGHT_GROWTH":
        print("\n--- Phase 3: Resubmit with new GROWTH model ---")
        submit_all_seeds(client, round_id, rnd, priors, predictor,
                         alpha=BLEND_ALPHA, floor=FLOOR, label="[growth] ")
    elif regime == "HEAVY_GROWTH":
        print("\n--- Phase 3: Heavy growth — R2 fast submit already optimal ---")
    else:
        print("\n--- Phase 3: Ambiguous — keeping R2 fast submit (growth is 7x more likely) ---")

    print("\nV8 Done! %d seeds submitted. %d probes used (47 saved)." % (
        rnd.seeds_count, n_probes))
    return True


def solve_round(round_id_or_none=None):
    """Standalone entry point for solving a round."""
    token = os.environ.get("ASTAR_TOKEN", "")
    if not token:
        print("Set ASTAR_TOKEN"); return False

    client = AstarClient(token)

    if round_id_or_none:
        rnd = client.get_round(round_id_or_none)
    else:
        rnd = client.get_active_round()
        if not rnd:
            print("No active round!")
            for r in client.get_rounds():
                print("  Round %d: %s" % (r.round_number, r.status))
            return False

    return solve_round_with_client(client, rnd)


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else None
    solve_round(target)


if __name__ == '__main__':
    main()
