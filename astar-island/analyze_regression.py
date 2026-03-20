#!/usr/bin/env python3
"""Compute regression coefficients for Forest and Settlement cells too."""
import json, numpy as np, os
from collections import defaultdict
from numpy.linalg import lstsq

BASE = os.path.dirname(os.path.abspath(__file__))
DIRECTIONS = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]

seeds = []
for seed in range(5):
    path = os.path.join(BASE, f'round2_analysis_seed{seed}.json')
    if os.path.exists(path):
        with open(path) as f:
            seeds.append(json.load(f))

def get_features(initial, y, x):
    counts = defaultdict(int)
    for dy, dx in DIRECTIONS:
        ny, nx = y + dy, x + dx
        if 0 <= ny < 40 and 0 <= nx < 40:
            counts[initial[ny][nx]] += 1
    return [
        counts.get(4, 0),   # forest
        counts.get(1, 0) + counts.get(2, 0) + counts.get(3, 0),  # settlement/port/ruin
        counts.get(10, 0),  # ocean
        counts.get(5, 0),   # mountain
        counts.get(11, 0) + counts.get(0, 0),  # plains/empty
    ]

for target_code, name in [(4, "Forest"), (1, "Settlement"), (11, "Plains")]:
    X_list, Y_list = [], []
    for data in seeds:
        initial = data['initial_grid']
        truth = np.array(data['ground_truth'])
        for y in range(40):
            for x in range(40):
                code = initial[y][x]
                if target_code == 11 and code not in (11, 0):
                    continue
                if target_code != 11 and code != target_code:
                    continue
                dist = truth[y, x]
                entropy = -np.sum(dist * np.log(dist + 1e-12))
                if entropy < 1e-6:
                    continue
                features = get_features(initial, y, x)
                X_list.append(features)
                Y_list.append(dist)

    X = np.array(X_list)
    Y = np.array(Y_list)

    print(f"\n{'='*80}")
    print(f"REGRESSION FOR {name} (code {target_code}), n={len(X)}")
    print(f"{'='*80}")

    # Features: 1, forest, settle, ocean, mountain, plains
    X_aug = np.column_stack([np.ones(len(X)), X])
    feat_names = ["intercept", "forest", "settle", "ocean", "mountain", "plains"]

    coeffs_all = []
    for cls in range(6):
        coeffs, residuals, _, _ = lstsq(X_aug, Y[:, cls], rcond=None)
        coeffs_all.append(coeffs)
        # Compute R²
        y_pred = X_aug @ coeffs
        ss_res = np.sum((Y[:, cls] - y_pred) ** 2)
        ss_tot = np.sum((Y[:, cls] - Y[:, cls].mean()) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
        print(f"\nClass {cls}: R²={r2:.4f}")
        for i, fn in enumerate(feat_names):
            print(f"  {fn}: {coeffs[i]:.6f}")

    # Print as numpy array for pasting
    print(f"\n# Ready to paste:")
    print(f"{name.upper()}_COEFFS = np.array([")
    for cls in range(6):
        vals = ", ".join(f"{v:.6f}" for v in coeffs_all[cls])
        print(f"    [{vals}],  # class {cls}")
    print("])")

    # Cross-validation: mean score improvement
    # Compute KL with regression vs flat mean
    mean_dist = Y.mean(axis=0)
    kl_flat = np.mean([np.sum(y * np.log(y / (mean_dist + 1e-12) + 1e-12)) for y in Y])
    y_pred_all = X_aug @ np.array(coeffs_all).T
    y_pred_all = np.maximum(y_pred_all, 0.001)
    y_pred_all /= y_pred_all.sum(axis=1, keepdims=True)
    kl_reg = np.mean([np.sum(y * np.log(y / (yp + 1e-12) + 1e-12)) for y, yp in zip(Y, y_pred_all)])
    print(f"\nAvg KL: flat={kl_flat:.4f}, regression={kl_reg:.4f}, improvement={kl_flat-kl_reg:.4f}")
