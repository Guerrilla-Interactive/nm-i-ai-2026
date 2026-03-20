#!/usr/bin/env python3
"""Final optimization: floor sweep + try regression-based predictor."""
import json, numpy as np, os, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from resubmit_simple import predict_from_initial

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

seeds_data = []
for seed in range(5):
    with open(os.path.join(DIR, f'round2_analysis_seed{seed}.json')) as f:
        seeds_data.append(json.load(f))

# 1. Floor sweep
print("=== Floor sweep ===")
for floor in [0.0001, 0.0003, 0.0005, 0.001, 0.002]:
    scores = []
    for data in seeds_data:
        pred = predict_from_initial(data['initial_grid'], floor=floor)
        scores.append(compute_kl(np.array(data['ground_truth']), pred))
    print(f"Floor {floor:.4f}: avg={np.mean(scores):.2f}")

# 2. Try a simple per-terrain-code regression using multiple neighbor features
print("\n=== Regression approach for plains (code 11) ===")
# Build feature matrix: for each plains cell, compute features and target
def count_neighbors(grid, y, x, codes, radius):
    count = 0
    for dy in range(-radius, radius+1):
        for dx in range(-radius, radius+1):
            if dy == 0 and dx == 0: continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < 40 and 0 <= nx < 40 and grid[ny][nx] in codes:
                count += 1
    return count

# Collect training data from all 5 seeds
X_train = []
Y_train = []
for data in seeds_data:
    g = data['initial_grid']
    t = np.array(data['ground_truth'])
    for y in range(40):
        for x in range(40):
            if g[y][x] != 11: continue
            # Features: settlement count (r=2,3), ocean count (r=2), forest count (r=2)
            sc2 = count_neighbors(g, y, x, {1,2,3}, 2)
            sc3 = count_neighbors(g, y, x, {1,2,3}, 3)
            oc2 = count_neighbors(g, y, x, {10}, 2)
            fc2 = count_neighbors(g, y, x, {4}, 2)
            mc2 = count_neighbors(g, y, x, {5}, 2)
            X_train.append([1, sc2, sc3, oc2, fc2, mc2])  # with intercept
            Y_train.append(t[y, x])

X = np.array(X_train)
Y = np.array(Y_train)

# Fit linear regression per class
print(f"Plains: n={len(X)}")
from numpy.linalg import lstsq
coeffs = []
for c in range(6):
    beta, _, _, _ = lstsq(X, Y[:, c], rcond=None)
    coeffs.append(beta)
    r2 = 1 - np.sum((Y[:, c] - X @ beta)**2) / np.sum((Y[:, c] - Y[:, c].mean())**2)
    print(f"  Class {c}: R²={r2:.4f}, coeffs={[f'{b:.5f}' for b in beta]}")

# Now do the same for forest
print("\n=== Regression for forest (code 4) ===")
X_train = []
Y_train = []
for data in seeds_data:
    g = data['initial_grid']
    t = np.array(data['ground_truth'])
    for y in range(40):
        for x in range(40):
            if g[y][x] != 4: continue
            sc2 = count_neighbors(g, y, x, {1,2,3}, 2)
            sc3 = count_neighbors(g, y, x, {1,2,3}, 3)
            oc2 = count_neighbors(g, y, x, {10}, 2)
            fc2 = count_neighbors(g, y, x, {4}, 2)
            mc2 = count_neighbors(g, y, x, {5}, 2)
            X_train.append([1, sc2, sc3, oc2, fc2, mc2])
            Y_train.append(t[y, x])

X = np.array(X_train)
Y = np.array(Y_train)
print(f"Forest: n={len(X)}")
forest_coeffs = []
for c in range(6):
    beta, _, _, _ = lstsq(X, Y[:, c], rcond=None)
    forest_coeffs.append(beta)
    r2 = 1 - np.sum((Y[:, c] - X @ beta)**2) / np.sum((Y[:, c] - Y[:, c].mean())**2)
    print(f"  Class {c}: R²={r2:.4f}, coeffs={[f'{b:.5f}' for b in beta]}")

# Test: use regression predictions and score
print("\n=== Regression-based predictor score ===")
plains_coeffs = coeffs

def predict_regression(initial_grid, floor=0.001):
    pred = np.zeros((40, 40, 6))
    for y in range(40):
        for x in range(40):
            code = initial_grid[y][x]
            if code == 5:
                pred[y,x] = [0,0,0,0,0,1]
            elif code == 10:
                pred[y,x] = [1,0,0,0,0,0]
            elif code == 1:
                pred[y,x] = [0.3832, 0.4098, 0.0051, 0.0341, 0.1678, 0.0000]
            elif code == 2:
                pred[y,x] = [0.3841, 0.1214, 0.2877, 0.0345, 0.1723, 0.0000]
            elif code == 3:
                pred[y,x] = [0.3832, 0.4098, 0.0051, 0.0341, 0.1678, 0.0000]
            elif code in (11, 0):
                sc2 = count_neighbors(initial_grid, y, x, {1,2,3}, 2)
                sc3 = count_neighbors(initial_grid, y, x, {1,2,3}, 3)
                oc2 = count_neighbors(initial_grid, y, x, {10}, 2)
                fc2 = count_neighbors(initial_grid, y, x, {4}, 2)
                mc2 = count_neighbors(initial_grid, y, x, {5}, 2)
                feat = np.array([1, sc2, sc3, oc2, fc2, mc2])
                for c in range(6):
                    pred[y, x, c] = feat @ plains_coeffs[c]
            elif code == 4:
                sc2 = count_neighbors(initial_grid, y, x, {1,2,3}, 2)
                sc3 = count_neighbors(initial_grid, y, x, {1,2,3}, 3)
                oc2 = count_neighbors(initial_grid, y, x, {10}, 2)
                fc2 = count_neighbors(initial_grid, y, x, {4}, 2)
                mc2 = count_neighbors(initial_grid, y, x, {5}, 2)
                feat = np.array([1, sc2, sc3, oc2, fc2, mc2])
                for c in range(6):
                    pred[y, x, c] = feat @ forest_coeffs[c]
            else:
                pred[y,x] = [1/6]*6

    # Clip and normalize
    pred = np.maximum(pred, floor)
    pred /= pred.sum(axis=-1, keepdims=True)
    return pred

scores = []
for data in seeds_data:
    pred = predict_regression(data['initial_grid'])
    s = compute_kl(np.array(data['ground_truth']), pred)
    scores.append(s)
    print(f"  Seed: {s:.2f}")
print(f"Regression avg: {np.mean(scores):.2f}")
