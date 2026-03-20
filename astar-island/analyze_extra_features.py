#!/usr/bin/env python3
"""Test additional features: 2nd-ring neighbors, position, edge effects."""
import json, numpy as np, os
from collections import defaultdict
from numpy.linalg import lstsq

BASE = os.path.dirname(os.path.abspath(__file__))
DIRS1 = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]
DIRS2 = [(-2,-2),(-2,-1),(-2,0),(-2,1),(-2,2),
         (-1,-2),(-1,2),(0,-2),(0,2),(1,-2),(1,2),
         (2,-2),(2,-1),(2,0),(2,1),(2,2)]

seeds = []
for seed in range(5):
    path = os.path.join(BASE, f'round2_analysis_seed{seed}.json')
    if os.path.exists(path):
        with open(path) as f:
            seeds.append(json.load(f))

def count_type(initial, y, x, dirs, code_set):
    c = 0
    for dy, dx in dirs:
        ny, nx = y + dy, x + dx
        if 0 <= ny < 40 and 0 <= nx < 40:
            if initial[ny][nx] in code_set:
                c += 1
    return c

def get_features(initial, y, x):
    """Extended feature set."""
    return [
        count_type(initial, y, x, DIRS1, {4}),      # forest ring1
        count_type(initial, y, x, DIRS1, {1,2,3}),   # settle ring1
        count_type(initial, y, x, DIRS1, {10}),       # ocean ring1
        count_type(initial, y, x, DIRS1, {5}),        # mountain ring1
        count_type(initial, y, x, DIRS1, {11,0}),     # plains ring1
        count_type(initial, y, x, DIRS2, {4}),        # forest ring2
        count_type(initial, y, x, DIRS2, {1,2,3}),    # settle ring2
        count_type(initial, y, x, DIRS2, {10}),        # ocean ring2
        count_type(initial, y, x, DIRS2, {5}),         # mountain ring2
        count_type(initial, y, x, DIRS2, {11,0}),      # plains ring2
    ]

for target_code, name in [(11, "Plains"), (4, "Forest"), (1, "Settlement")]:
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
    X_aug = np.column_stack([np.ones(len(X)), X])

    # Compare R² with ring1-only vs ring1+ring2
    feat_names_r1 = ["intercept", "forest_r1", "settle_r1", "ocean_r1", "mountain_r1", "plains_r1"]
    feat_names_all = feat_names_r1 + ["forest_r2", "settle_r2", "ocean_r2", "mountain_r2", "plains_r2"]

    print(f"\n{'='*80}")
    print(f"{name} (code {target_code}), n={len(X)}")
    print(f"{'='*80}")

    # Ring 1 only
    X_r1 = np.column_stack([np.ones(len(X)), X[:, :5]])
    for cls in range(5):
        c_r1, _, _, _ = lstsq(X_r1, Y[:, cls], rcond=None)
        y_pred_r1 = X_r1 @ c_r1
        ss_res_r1 = np.sum((Y[:, cls] - y_pred_r1) ** 2)
        ss_tot = np.sum((Y[:, cls] - Y[:, cls].mean()) ** 2)
        r2_r1 = 1 - ss_res_r1 / ss_tot if ss_tot > 0 else 0

        c_all, _, _, _ = lstsq(X_aug, Y[:, cls], rcond=None)
        y_pred_all = X_aug @ c_all
        ss_res_all = np.sum((Y[:, cls] - y_pred_all) ** 2)
        r2_all = 1 - ss_res_all / ss_tot if ss_tot > 0 else 0

        if r2_all - r2_r1 > 0.01:
            print(f"  Class {cls}: R²(r1)={r2_r1:.4f} → R²(r1+r2)={r2_all:.4f} (+{r2_all-r2_r1:.4f})")

    # Compute KL improvement
    coeffs_r1 = []
    coeffs_all = []
    for cls in range(6):
        c_r1, _, _, _ = lstsq(X_r1, Y[:, cls], rcond=None)
        c_all, _, _, _ = lstsq(X_aug, Y[:, cls], rcond=None)
        coeffs_r1.append(c_r1)
        coeffs_all.append(c_all)

    y_pred_r1 = X_r1 @ np.array(coeffs_r1).T
    y_pred_r1 = np.maximum(y_pred_r1, 0.001)
    y_pred_r1 /= y_pred_r1.sum(axis=1, keepdims=True)

    y_pred_all = X_aug @ np.array(coeffs_all).T
    y_pred_all = np.maximum(y_pred_all, 0.001)
    y_pred_all /= y_pred_all.sum(axis=1, keepdims=True)

    kl_r1 = np.mean([np.sum(y * np.log(y / (yp + 1e-12) + 1e-12)) for y, yp in zip(Y, y_pred_r1)])
    kl_all = np.mean([np.sum(y * np.log(y / (yp + 1e-12) + 1e-12)) for y, yp in zip(Y, y_pred_all)])
    print(f"  KL: ring1={kl_r1:.4f}, ring1+2={kl_all:.4f}, delta={kl_r1-kl_all:.4f}")

    # Print extended coefficients
    if kl_r1 - kl_all > 0.001:
        print(f"\n  # Extended coefficients worth using:")
        print(f"  {name.upper()}_COEFFS = np.array([")
        for cls in range(6):
            vals = ", ".join(f"{v:.6f}" for v in coeffs_all[cls])
            print(f"      [{vals}],  # class {cls}")
        print(f"  ])")

# Also test: what if we use different floors?
print(f"\n{'='*80}")
print("FLOOR SENSITIVITY TEST")
print(f"{'='*80}")
print("Testing whether lower floors for rare classes help...")

# For each cell type, what's the min probability in ground truth for each class?
for target_code, name in [(11, "Plains"), (4, "Forest"), (1, "Settlement")]:
    min_vals = np.ones(6)
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
                for c in range(6):
                    if dist[c] < min_vals[c]:
                        min_vals[c] = dist[c]
    print(f"  {name}: min per class = [{', '.join(f'{v:.4f}' for v in min_vals)}]")
