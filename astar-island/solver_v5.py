#!/usr/bin/env python3
"""
Solver V5: Group-prior based solver with regime detection.

Strategy:
1. Use 3 simulation queries to detect regime (growth vs collapse)
2. Load regime-specific group priors (terrain × coastal × settle_bin × forest_bin)
3. Submit predictions for all 5 seeds — NO per-cell Bayesian update (it hurts)

Group priors score:
- R2 LOO-CV: 89.3 avg
- R3 LOO-CV: 85.4 avg
- With regime detection: picks the right one automatically
"""
import os, sys, json, time
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from client import AstarClient
from config import GRID_SIZE, NUM_CLASSES

# Group computation helpers
def is_coastal(grid, y, x):
    for dy in range(-1, 2):
        for dx in range(-1, 2):
            if dy == 0 and dx == 0:
                continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < GRID_SIZE and 0 <= nx < GRID_SIZE:
                if grid[ny][nx] == 10:
                    return True
    return False

def count_neighbors(grid, y, x, codes, radius=1):
    count = 0
    for dy in range(-radius, radius+1):
        for dx in range(-radius, radius+1):
            if dy == 0 and dx == 0:
                continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < GRID_SIZE and 0 <= nx < GRID_SIZE:
                if grid[ny][nx] in codes:
                    count += 1
    return count

def settle_bin(count):
    if count == 0: return 0
    elif count == 1: return 1
    else: return 2

def forest_bin(count):
    if count == 0: return 0
    elif count <= 2: return 1
    else: return 2

def get_group_key(grid, y, x):
    code = grid[y][x]
    coastal = is_coastal(grid, y, x)
    sn = settle_bin(count_neighbors(grid, y, x, {1, 2, 3}))
    fn = forest_bin(count_neighbors(grid, y, x, {4}))
    return "%d_%s_%d_%d" % (code, coastal, sn, fn)

def get_fallback_keys(grid, y, x):
    """Return list of fallback group keys in priority order."""
    code = grid[y][x]
    coastal = is_coastal(grid, y, x)
    sn = settle_bin(count_neighbors(grid, y, x, {1, 2, 3}))
    fn = forest_bin(count_neighbors(grid, y, x, {4}))
    return [
        "%d_%s_%d_%d" % (code, coastal, sn, fn),
        "%d_%s_%d_0" % (code, coastal, sn),
        "%d_%s_0_0" % (code, coastal),
        "%d_False_0_0" % code,
    ]


VP_TILES = [
    (0, 0), (13, 0), (25, 0),
    (0, 13), (13, 13), (25, 13),
    (0, 25), (13, 25), (25, 25),
]
VP_SIZE = 15


def find_best_settlement_viewport(initial_grid):
    """Find viewport with most settlements for regime detection."""
    best_count = 0
    best_pos = (0, 0)
    for vx, vy in VP_TILES:
        count = 0
        for y in range(vy, min(vy + VP_SIZE, GRID_SIZE)):
            for x in range(vx, min(vx + VP_SIZE, GRID_SIZE)):
                if initial_grid[y][x] in (1, 2):
                    count += 1
        if count > best_count:
            best_count = count
            best_pos = (vx, vy)
    return best_pos, best_count


def detect_regime(client, round_id, initial_states, n_probes=3):
    """
    Use simulation queries to detect regime.
    Returns growth_score: high = growth, low = collapse.
    """
    total_initial = 0
    total_final = 0

    for probe in range(n_probes):
        seed_idx = probe % 5
        initial_grid = initial_states[seed_idx].grid
        (vx, vy), n_settle = find_best_settlement_viewport(initial_grid)

        print("  Probe %d: seed=%d vp=(%d,%d) initial_settlements=%d" % (
            probe, seed_idx, vx, vy, n_settle))

        try:
            result = client.simulate(round_id, seed_idx, vx, vy, VP_SIZE, VP_SIZE)

            # Count initial settlements in viewport
            for y in range(vy, min(vy + VP_SIZE, GRID_SIZE)):
                for x in range(vx, min(vx + VP_SIZE, GRID_SIZE)):
                    if initial_grid[y][x] in (1, 2):
                        total_initial += 1

            # Count final settlements
            for row_idx, y in enumerate(range(vy, min(vy + VP_SIZE, GRID_SIZE))):
                for col_idx, x in enumerate(range(vx, min(vx + VP_SIZE, GRID_SIZE))):
                    if row_idx < len(result.grid) and col_idx < len(result.grid[row_idx]):
                        if result.grid[row_idx][col_idx] in (1, 2):
                            total_final += 1

        except Exception as e:
            print("    ERROR: %s" % e)

    if total_initial == 0:
        return 0.5

    survival = total_final / total_initial
    print("  Settlement survival: %d/%d = %.2f" % (total_final, total_initial, survival))
    return min(1.0, survival)


def predict_with_group_priors(initial_grid, priors, floor=0.005):
    """Generate 40x40x6 prediction using group priors."""
    pred = np.zeros((GRID_SIZE, GRID_SIZE, NUM_CLASSES))

    for y in range(GRID_SIZE):
        for x in range(GRID_SIZE):
            code = initial_grid[y][x]

            # Static cells
            if code == 5:  # Mountain
                pred[y, x] = [0.0, 0.0, 0.0, 0.0, 0.0, 1.0]
                continue
            if code == 10:  # Ocean
                pred[y, x] = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0]
                continue

            # Look up group prior with fallbacks
            keys = get_fallback_keys(initial_grid, y, x)
            found = False
            for key in keys:
                if key in priors:
                    pred[y, x] = np.array(priors[key]['dist'])
                    found = True
                    break

            if not found:
                pred[y, x] = np.ones(NUM_CLASSES) / NUM_CLASSES

            # Enforce port=0 for non-coastal cells
            if not is_coastal(initial_grid, y, x):
                pred[y, x, 2] = 0.0  # Port class

    # Floor and renormalize
    pred = np.maximum(pred, floor)
    # But keep ocean and mountain pure
    for y in range(GRID_SIZE):
        for x in range(GRID_SIZE):
            code = initial_grid[y][x]
            if code == 5:
                pred[y, x] = [0.0, 0.0, 0.0, 0.0, 0.0, 1.0]
                pred[y, x] = np.maximum(pred[y, x], floor)
            elif code == 10:
                pred[y, x] = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0]
                pred[y, x] = np.maximum(pred[y, x], floor)

    pred = pred / pred.sum(axis=-1, keepdims=True)
    return pred


def main():
    token = os.environ.get("ASTAR_TOKEN", "")
    if not token:
        print("Set ASTAR_TOKEN"); sys.exit(1)

    client = AstarClient(token)
    active = client.get_active_round()
    if not active:
        print("No active round!")
        for r in client.get_rounds():
            print("  Round %d: %s" % (r.round_number, r.status))
        sys.exit(0)

    round_id = active.id
    print("=== Round %d: %s ===" % (active.round_number, round_id[:8]))
    print("  Seeds: %d, closes: %s" % (active.seeds_count, active.closes_at))

    budget = client.get_budget()
    queries_left = budget['queries_max'] - budget['queries_used']
    print("  Budget: %d/%d used, %d remaining" % (
        budget['queries_used'], budget['queries_max'], queries_left))

    # Step 1: Regime detection
    n_probes = min(3, queries_left)
    if n_probes > 0:
        print("\n--- Step 1: Regime Detection (%d probes) ---" % n_probes)
        growth_score = detect_regime(client, round_id, active.initial_states, n_probes)
    else:
        print("\n--- Step 1: No budget, using combined priors ---")
        growth_score = 0.5

    # Step 2: Select priors
    print("\n--- Step 2: Select Priors (growth=%.2f) ---" % growth_score)

    r2_priors = json.load(open('data/group_priors_r2.json'))
    r3_priors = json.load(open('data/group_priors_r3.json'))

    if growth_score > 0.3:
        print("  Regime: GROWTH -> R2 priors")
        priors = r2_priors
        floor = 0.0001
    elif growth_score < 0.1:
        print("  Regime: COLLAPSE -> R3 priors")
        priors = r3_priors
        floor = 0.0001
    else:
        # Ambiguous: blend
        print("  Regime: AMBIGUOUS (%.2f) -> blending R2/R3" % growth_score)
        blend = growth_score / 0.3  # 0 = pure R3, 1 = pure R2
        floor = 0.001  # Higher floor for uncertain regime
        priors = {}
        all_keys = set(list(r2_priors.keys()) + list(r3_priors.keys()))
        for key in all_keys:
            r2_dist = np.array(r2_priors[key]['dist']) if key in r2_priors else np.ones(NUM_CLASSES)/NUM_CLASSES
            r3_dist = np.array(r3_priors[key]['dist']) if key in r3_priors else np.ones(NUM_CLASSES)/NUM_CLASSES
            blended = blend * r2_dist + (1 - blend) * r3_dist
            priors[key] = {'dist': blended.tolist(), 'count': 1}

    # Step 3: Submit predictions
    print("\n--- Step 3: Submit Predictions ---")
    for seed_idx in range(active.seeds_count):
        initial_grid = active.initial_states[seed_idx].grid

        pred = predict_with_group_priors(initial_grid, priors, floor=floor)

        # Validate
        assert pred.shape == (GRID_SIZE, GRID_SIZE, NUM_CLASSES)
        assert (pred >= floor * 0.9).all(), "Min: %.6f" % pred.min()
        assert np.allclose(pred.sum(axis=-1), 1.0, atol=0.02)

        result = client.submit(round_id, seed_idx, pred.tolist())
        print("  Seed %d: %s" % (seed_idx, result))

    print("\nDone! All %d seeds submitted." % active.seeds_count)


if __name__ == '__main__':
    main()
