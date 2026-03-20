#!/usr/bin/env python3
"""Try regression for settlement cells too, and more features."""
import json, numpy as np, os, sys
from numpy.linalg import lstsq
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DIR = os.path.dirname(os.path.abspath(__file__))

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

def count_neighbors(grid, y, x, codes, radius):
    count = 0
    for dy in range(-radius, radius+1):
        for dx in range(-radius, radius+1):
            if dy == 0 and dx == 0: continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < 40 and 0 <= nx < 40 and grid[ny][nx] in codes:
                count += 1
    return count

seeds_data = []
for seed in range(5):
    with open(os.path.join(DIR, f'round2_analysis_seed{seed}.json')) as f:
        seeds_data.append(json.load(f))

def get_features(grid, y, x):
    """Extended feature set."""
    sc1 = count_neighbors(grid, y, x, {1,2,3}, 1)
    sc2 = count_neighbors(grid, y, x, {1,2,3}, 2)
    sc3 = count_neighbors(grid, y, x, {1,2,3}, 3)
    oc1 = count_neighbors(grid, y, x, {10}, 1)
    oc2 = count_neighbors(grid, y, x, {10}, 2)
    fc1 = count_neighbors(grid, y, x, {4}, 1)
    fc2 = count_neighbors(grid, y, x, {4}, 2)
    mc1 = count_neighbors(grid, y, x, {5}, 1)
    mc2 = count_neighbors(grid, y, x, {5}, 2)
    pc1 = count_neighbors(grid, y, x, {0, 11}, 1)
    pc2 = count_neighbors(grid, y, x, {0, 11}, 2)
    return [1, sc1, sc2, sc3, oc1, oc2, fc1, fc2, mc1, mc2, pc1, pc2]

# Train regression for each terrain code
terrain_codes = {
    11: 'Plains',
    4: 'Forest',
    1: 'Settlement',
}

all_coeffs = {}
for tc, name in terrain_codes.items():
    X_train, Y_train = [], []
    for data in seeds_data:
        g = data['initial_grid']
        t = np.array(data['ground_truth'])
        for y in range(40):
            for x in range(40):
                if g[y][x] != tc: continue
                X_train.append(get_features(g, y, x))
                Y_train.append(t[y, x])

    X = np.array(X_train)
    Y = np.array(Y_train)
    print(f"\n{name} (code {tc}): n={len(X)}")
    coeffs = []
    for c in range(6):
        beta, _, _, _ = lstsq(X, Y[:, c], rcond=None)
        coeffs.append(beta)
        ss_res = np.sum((Y[:, c] - X @ beta)**2)
        ss_tot = np.sum((Y[:, c] - Y[:, c].mean())**2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
        print(f"  Class {c}: R²={r2:.4f}")
    all_coeffs[tc] = np.array(coeffs)

# Test with extended regression
def predict_v6(initial_grid, floor=0.001):
    pred = np.zeros((40, 40, 6))
    for y in range(40):
        for x in range(40):
            code = initial_grid[y][x]
            if code == 5:
                pred[y,x] = [0,0,0,0,0,1]
            elif code == 10:
                pred[y,x] = [1,0,0,0,0,0]
            elif code == 2:
                pred[y,x] = [0.3841, 0.1214, 0.2877, 0.0345, 0.1723, 0.0000]
            elif code == 3:
                pred[y,x] = [0.3832, 0.4098, 0.0051, 0.0341, 0.1678, 0.0000]
            elif code in all_coeffs:
                feat = np.array(get_features(initial_grid, y, x))
                pred[y, x] = all_coeffs[code] @ feat
            elif code in (0,):
                # Empty/0 - use plains coeffs
                feat = np.array(get_features(initial_grid, y, x))
                pred[y, x] = all_coeffs[11] @ feat
            else:
                pred[y,x] = [1/6]*6
    pred = np.maximum(pred, floor)
    pred /= pred.sum(axis=-1, keepdims=True)
    return pred

print("\n=== V6 Score (extended features) ===")
scores = []
for data in seeds_data:
    s = compute_kl(np.array(data['ground_truth']), predict_v6(data['initial_grid']))
    scores.append(s)
    print(f"  {s:.2f}")
print(f"V6 avg: {np.mean(scores):.2f}")

# Print coefficients for integration
print("\n=== Coefficients for resubmit_simple.py ===")
for tc, name in terrain_codes.items():
    print(f"\n# {name} (code {tc})")
    print(f"COEFFS_{tc} = [")
    for c in range(6):
        vals = ', '.join(f'{v:.8f}' for v in all_coeffs[tc][c])
        print(f"    [{vals}],  # class {c}")
    print("]")
