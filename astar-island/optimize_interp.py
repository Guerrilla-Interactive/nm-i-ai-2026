#!/usr/bin/env python3
"""Try linear interpolation based on settlement count for forest/plains."""
import json, numpy as np, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SETTLEMENT_DIST = np.array([0.3832, 0.4098, 0.0051, 0.0341, 0.1678, 0.0000])
PORT_DIST = np.array([0.3841, 0.1214, 0.2877, 0.0345, 0.1723, 0.0000])
RUIN_DIST = np.array([0.3832, 0.4098, 0.0051, 0.0341, 0.1678, 0.0000])

# Plains by sett count (from analysis)
PLAINS_SC = {
    0: np.array([0.8078, 0.1328, 0.0187, 0.0135, 0.0271, 0.0000]),
    1: np.array([0.7150, 0.2017, 0.0228, 0.0182, 0.0423, 0.0000]),
    2: np.array([0.7077, 0.2034, 0.0110, 0.0206, 0.0573, 0.0000]),
    3: np.array([0.7055, 0.2028, 0.0059, 0.0220, 0.0638, 0.0000]),
    4: np.array([0.7012, 0.2021, 0.0031, 0.0231, 0.0704, 0.0000]),
    5: np.array([0.6959, 0.2029, 0.0000, 0.0226, 0.0787, 0.0000]),
}
FOREST_SC = {
    0: np.array([0.0629, 0.1441, 0.0174, 0.0131, 0.7626, 0.0000]),
    1: np.array([0.0954, 0.2111, 0.0186, 0.0182, 0.6566, 0.0000]),
    2: np.array([0.1316, 0.2089, 0.0080, 0.0204, 0.6311, 0.0000]),
    3: np.array([0.1458, 0.2065, 0.0049, 0.0219, 0.6208, 0.0000]),
    4: np.array([0.1609, 0.2004, 0.0007, 0.0224, 0.6156, 0.0000]),
}

# Also: ocean effect for plains/forest
PLAINS_OCEAN_SC0 = np.array([0.8288, 0.1022, 0.0376, 0.0105, 0.0210, 0.0000])
PLAINS_OCEAN_MED = np.array([0.7455, 0.1505, 0.0544, 0.0145, 0.0351, 0.0000])

def count_neighbors(grid, y, x, codes, radius):
    count = 0
    for dy in range(-radius, radius+1):
        for dx in range(-radius, radius+1):
            if dy == 0 and dx == 0: continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < 40 and 0 <= nx < 40 and grid[ny][nx] in codes:
                count += 1
    return count

def predict_interp(initial_grid, floor=0.005):
    pred = np.zeros((40, 40, 6))
    for y in range(40):
        for x in range(40):
            code = initial_grid[y][x]
            if code == 5:
                pred[y,x] = [0,0,0,0,0,1]
            elif code == 10:
                pred[y,x] = [1,0,0,0,0,0]
            elif code == 1:
                pred[y,x] = SETTLEMENT_DIST
            elif code == 2:
                pred[y,x] = PORT_DIST
            elif code == 3:
                pred[y,x] = RUIN_DIST
            elif code in (11, 0):
                sc = count_neighbors(initial_grid, y, x, {1,2,3}, radius=3)
                oc = count_neighbors(initial_grid, y, x, {10}, radius=2)
                # Lookup or interpolate
                sc_key = min(sc, 5)
                base = PLAINS_SC[sc_key].copy()
                # Blend with ocean effect
                if oc >= 4 and sc <= 1:
                    # Coastal: blend toward ocean distribution
                    alpha = min(1.0, (oc - 3) / 5.0)
                    ocean_dist = PLAINS_OCEAN_SC0 if sc == 0 else PLAINS_OCEAN_MED
                    base = (1 - alpha) * base + alpha * ocean_dist
                pred[y,x] = base
            elif code == 4:
                sc = count_neighbors(initial_grid, y, x, {1,2,3}, radius=3)
                sc_key = min(sc, 4)
                pred[y,x] = FOREST_SC[sc_key]
            else:
                pred[y,x] = [1/6]*6

    for _ in range(10):
        pred = np.maximum(pred, floor)
        pred /= pred.sum(axis=-1, keepdims=True)
        if (pred >= floor - 1e-9).all():
            break
    return pred

def compute_kl(truth, pred):
    kl_sum, weight_sum = 0.0, 0.0
    for y in range(40):
        for x in range(40):
            p, q = truth[y, x], pred[y, x]
            entropy = -sum(pi * np.log(pi + 1e-12) for pi in p if pi > 0)
            if entropy < 1e-6: continue
            kl = sum(pi * np.log(pi / max(qi, 1e-10)) for pi, qi in zip(p, q) if pi > 0)
            kl_sum += entropy * kl
            weight_sum += entropy
    weighted_kl = kl_sum / weight_sum if weight_sum > 0 else 0
    return max(0, min(100, 100 * np.exp(-3 * weighted_kl)))

seeds_data = []
for seed in range(5):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f'round2_analysis_seed{seed}.json')
    with open(path) as f:
        seeds_data.append(json.load(f))

# Test interpolation approach
scores = []
for data in seeds_data:
    s = compute_kl(np.array(data['ground_truth']), predict_interp(data['initial_grid']))
    scores.append(s)
    print(f"Score: {s:.2f}")
print(f"Interp avg: {np.mean(scores):.2f}")

# Compare: what about using EXACT per-cell-type averages without ocean blending?
print("\n--- Forest per-sett-count (no ocean) ---")
scores2 = []
for data in seeds_data:
    pred = predict_interp(data['initial_grid'])
    s = compute_kl(np.array(data['ground_truth']), pred)
    scores2.append(s)
print(f"With ocean blend: {np.mean(scores):.2f}")
