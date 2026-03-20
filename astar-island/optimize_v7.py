#!/usr/bin/env python3
"""V7: More features (interaction terms, radius 4), regression for port too."""
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

def get_features_v7(grid, y, x):
    """Extended features with radii 1,2,3 and interactions."""
    sc1 = count_neighbors(grid, y, x, {1,2,3}, 1)
    sc2 = count_neighbors(grid, y, x, {1,2,3}, 2)
    sc3 = count_neighbors(grid, y, x, {1,2,3}, 3)
    sc4 = count_neighbors(grid, y, x, {1,2,3}, 4)
    oc1 = count_neighbors(grid, y, x, {10}, 1)
    oc2 = count_neighbors(grid, y, x, {10}, 2)
    oc3 = count_neighbors(grid, y, x, {10}, 3)
    fc1 = count_neighbors(grid, y, x, {4}, 1)
    fc2 = count_neighbors(grid, y, x, {4}, 2)
    fc3 = count_neighbors(grid, y, x, {4}, 3)
    mc1 = count_neighbors(grid, y, x, {5}, 1)
    mc2 = count_neighbors(grid, y, x, {5}, 2)
    pc1 = count_neighbors(grid, y, x, {0, 11}, 1)
    pc2 = count_neighbors(grid, y, x, {0, 11}, 2)
    # Interaction: settlement * ocean (indicates port area)
    so_int = sc1 * oc1
    # Interaction: settlement * forest
    sf_int = sc1 * fc1
    return [1, sc1, sc2, sc3, sc4, oc1, oc2, oc3, fc1, fc2, fc3, mc1, mc2, pc1, pc2, so_int, sf_int]

NFEAT = 17

# Cross-validation: train on 4 seeds, test on 1
print("=== Leave-one-out cross-validation ===")
terrain_codes = [11, 4, 1]

for tc in terrain_codes:
    cv_scores = []
    for test_seed in range(5):
        # Train on other 4 seeds
        X_train, Y_train = [], []
        for i, data in enumerate(seeds_data):
            if i == test_seed: continue
            g = data['initial_grid']
            t = np.array(data['ground_truth'])
            for y in range(40):
                for x in range(40):
                    if g[y][x] != tc and not (tc == 11 and g[y][x] == 0): continue
                    X_train.append(get_features_v7(g, y, x))
                    Y_train.append(t[y, x])
        X = np.array(X_train)
        Y = np.array(Y_train)
        coeffs = []
        for c in range(6):
            beta, _, _, _ = lstsq(X, Y[:, c], rcond=None)
            coeffs.append(beta)

        # Test on held-out seed
        data = seeds_data[test_seed]
        g = data['initial_grid']
        t = np.array(data['ground_truth'])
        pred = np.zeros((40, 40, 6))
        for yy in range(40):
            for xx in range(40):
                code = g[yy][xx]
                if code == 5:
                    pred[yy,xx] = [0,0,0,0,0,1]
                elif code == 10:
                    pred[yy,xx] = [1,0,0,0,0,0]
                elif code == tc or (tc == 11 and code == 0):
                    feat = np.array(get_features_v7(g, yy, xx))
                    for c in range(6):
                        pred[yy, xx, c] = feat @ coeffs[c]
                else:
                    # Use global average for this code
                    pred[yy,xx] = t[yy,xx]  # cheat for CV (only measuring regression quality)

        pred = np.maximum(pred, 0.001)
        pred /= pred.sum(axis=-1, keepdims=True)
        # Only measure cells of this type
        kl_sum, w_sum = 0.0, 0.0
        for yy in range(40):
            for xx in range(40):
                code = g[yy][xx]
                if code != tc and not (tc == 11 and code == 0): continue
                p, q = t[yy, xx], pred[yy, xx]
                entropy = -sum(pi * np.log(pi + 1e-12) for pi in p if pi > 0)
                if entropy < 1e-6: continue
                kl = sum(pi * np.log(pi / max(qi, 1e-10)) for pi, qi in zip(p, q) if pi > 0)
                kl_sum += entropy * kl
                w_sum += entropy
        if w_sum > 0:
            cv_scores.append(100 * np.exp(-3 * kl_sum / w_sum))

    print(f"Code {tc}: CV scores = [{', '.join(f'{s:.1f}' for s in cv_scores)}] avg={np.mean(cv_scores):.1f}")

# Train on all data with v7 features
print("\n=== V7 full training ===")
all_coeffs = {}
for tc in [11, 4, 1]:
    X_train, Y_train = [], []
    for data in seeds_data:
        g = data['initial_grid']
        t = np.array(data['ground_truth'])
        for y in range(40):
            for x in range(40):
                if g[y][x] != tc and not (tc == 11 and g[y][x] == 0): continue
                X_train.append(get_features_v7(g, y, x))
                Y_train.append(t[y, x])
    X = np.array(X_train)
    Y = np.array(Y_train)
    coeffs = []
    for c in range(6):
        beta, _, _, _ = lstsq(X, Y[:, c], rcond=None)
        coeffs.append(beta)
    all_coeffs[tc] = np.array(coeffs)

# Test full model
def predict_v7(initial_grid, floor=0.001):
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
            elif code in (11, 0):
                feat = np.array(get_features_v7(initial_grid, y, x))
                pred[y, x] = all_coeffs[11] @ feat
            elif code == 4:
                feat = np.array(get_features_v7(initial_grid, y, x))
                pred[y, x] = all_coeffs[4] @ feat
            elif code == 1:
                feat = np.array(get_features_v7(initial_grid, y, x))
                pred[y, x] = all_coeffs[1] @ feat
            else:
                pred[y,x] = [1/6]*6
    pred = np.maximum(pred, floor)
    pred /= pred.sum(axis=-1, keepdims=True)
    return pred

scores = []
for data in seeds_data:
    s = compute_kl(np.array(data['ground_truth']), predict_v7(data['initial_grid']))
    scores.append(s)
print(f"V7 train avg: {np.mean(scores):.2f} [{', '.join(f'{s:.1f}' for s in scores)}]")

# Compare with V6 (12 features)
from resubmit_simple import predict_from_initial
scores_v6 = []
for data in seeds_data:
    s = compute_kl(np.array(data['ground_truth']), predict_from_initial(data['initial_grid']))
    scores_v6.append(s)
print(f"V6 train avg: {np.mean(scores_v6):.2f}")

# Print V7 coefficients
print("\n=== V7 Coefficients ===")
for tc in [11, 4, 1]:
    print(f"\nCOEFFS_{tc} = np.array([")
    for c in range(6):
        vals = ', '.join(f'{v:.10f}' for v in all_coeffs[tc][c])
        print(f"    [{vals}],")
    print("])")
