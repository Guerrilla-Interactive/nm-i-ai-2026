#!/usr/bin/env python3
"""Test ring-3 features and cross-validated regression."""
import json, numpy as np, os
from collections import defaultdict
from numpy.linalg import lstsq

BASE = os.path.dirname(os.path.abspath(__file__))
DIRS1 = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]
DIRS2 = [(-2,-2),(-2,-1),(-2,0),(-2,1),(-2,2),(-1,-2),(-1,2),(0,-2),(0,2),(1,-2),(1,2),(2,-2),(2,-1),(2,0),(2,1),(2,2)]
DIRS3 = []
for dy in range(-3, 4):
    for dx in range(-3, 4):
        if max(abs(dy), abs(dx)) == 3:
            DIRS3.append((dy, dx))

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

# Test cross-validated KL for Plains with ring1, ring1+2, ring1+2+3
for target_code, name in [(11, "Plains"), (4, "Forest")]:
    # Collect features per seed
    per_seed = []
    for data in seeds:
        initial = data['initial_grid']
        truth = np.array(data['ground_truth'])
        X_list, Y_list = [], []
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
                features = [
                    count_type(initial, y, x, DIRS1, {4}),
                    count_type(initial, y, x, DIRS1, {1,2,3}),
                    count_type(initial, y, x, DIRS1, {10}),
                    count_type(initial, y, x, DIRS1, {5}),
                    count_type(initial, y, x, DIRS1, {11,0}),
                    count_type(initial, y, x, DIRS2, {4}),
                    count_type(initial, y, x, DIRS2, {1,2,3}),
                    count_type(initial, y, x, DIRS2, {10}),
                    count_type(initial, y, x, DIRS2, {5}),
                    count_type(initial, y, x, DIRS2, {11,0}),
                    count_type(initial, y, x, DIRS3, {4}),
                    count_type(initial, y, x, DIRS3, {1,2,3}),
                    count_type(initial, y, x, DIRS3, {10}),
                    count_type(initial, y, x, DIRS3, {5}),
                    count_type(initial, y, x, DIRS3, {11,0}),
                ]
                X_list.append(features)
                Y_list.append(dist)
        per_seed.append((np.array(X_list), np.array(Y_list)))

    print(f"\n{'='*60}")
    print(f"CROSS-VALIDATED KL for {name}")
    print(f"{'='*60}")

    for n_feat, feat_name in [(5, "ring1"), (10, "ring1+2"), (15, "ring1+2+3")]:
        cv_kls = []
        for test_idx in range(len(per_seed)):
            # Train on all seeds except test_idx
            X_train = np.vstack([per_seed[i][0][:, :n_feat] for i in range(len(per_seed)) if i != test_idx])
            Y_train = np.vstack([per_seed[i][1] for i in range(len(per_seed)) if i != test_idx])
            X_test = per_seed[test_idx][0][:, :n_feat]
            Y_test = per_seed[test_idx][1]

            X_train_aug = np.column_stack([np.ones(len(X_train)), X_train])
            X_test_aug = np.column_stack([np.ones(len(X_test)), X_test])

            coeffs = []
            for cls in range(6):
                c, _, _, _ = lstsq(X_train_aug, Y_train[:, cls], rcond=None)
                coeffs.append(c)
            coeffs = np.array(coeffs)

            Y_pred = X_test_aug @ coeffs.T
            Y_pred = np.maximum(Y_pred, 0.001)
            Y_pred /= Y_pred.sum(axis=1, keepdims=True)

            kl = np.mean([np.sum(y * np.log(y / (yp + 1e-12) + 1e-12)) for y, yp in zip(Y_test, Y_pred)])
            cv_kls.append(kl)

        print(f"  {feat_name:12s}: CV-KL = {np.mean(cv_kls):.4f} ± {np.std(cv_kls):.4f}")

    # Also test ridge regression for ring1+2
    print(f"\n  Ridge regression (ring1+2):")
    for alpha in [0.001, 0.01, 0.1, 1.0]:
        cv_kls = []
        for test_idx in range(len(per_seed)):
            X_train = np.vstack([per_seed[i][0][:, :10] for i in range(len(per_seed)) if i != test_idx])
            Y_train = np.vstack([per_seed[i][1] for i in range(len(per_seed)) if i != test_idx])
            X_test = per_seed[test_idx][0][:, :10]
            Y_test = per_seed[test_idx][1]

            X_train_aug = np.column_stack([np.ones(len(X_train)), X_train])
            X_test_aug = np.column_stack([np.ones(len(X_test)), X_test])

            # Ridge: (X'X + αI)^-1 X'y
            I = np.eye(X_train_aug.shape[1])
            I[0, 0] = 0  # don't regularize intercept
            coeffs = []
            for cls in range(6):
                c = np.linalg.solve(X_train_aug.T @ X_train_aug + alpha * I, X_train_aug.T @ Y_train[:, cls])
                coeffs.append(c)
            coeffs = np.array(coeffs)

            Y_pred = X_test_aug @ coeffs.T
            Y_pred = np.maximum(Y_pred, 0.001)
            Y_pred /= Y_pred.sum(axis=1, keepdims=True)

            kl = np.mean([np.sum(y * np.log(y / (yp + 1e-12) + 1e-12)) for y, yp in zip(Y_test, Y_pred)])
            cv_kls.append(kl)
        print(f"    alpha={alpha:6.3f}: CV-KL = {np.mean(cv_kls):.4f} ± {np.std(cv_kls):.4f}")
