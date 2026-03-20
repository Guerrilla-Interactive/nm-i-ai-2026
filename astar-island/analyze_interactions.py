#!/usr/bin/env python3
"""Test interaction features and cumulative (ball) features."""
import json, numpy as np, os
from numpy.linalg import lstsq

BASE = os.path.dirname(os.path.abspath(__file__))

def make_ring(r):
    return [(dy, dx) for dy in range(-r, r+1) for dx in range(-r, r+1) if max(abs(dy), abs(dx)) == r]

def make_ball(r):
    """All cells within Chebyshev distance r."""
    return [(dy, dx) for dy in range(-r, r+1) for dx in range(-r, r+1) if (dy, dx) != (0, 0)]

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

RINGS = [make_ring(r) for r in range(1, 5)]
BALLS = [make_ball(r) for r in range(1, 5)]

for target_code, name in [(11, "Plains"), (4, "Forest")]:
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

                # Ring features
                ring_feats = []
                for ring in RINGS:
                    ring_feats.extend([
                        count_type(initial, y, x, ring, {4}),
                        count_type(initial, y, x, ring, {1,2,3}),
                        count_type(initial, y, x, ring, {10}),
                        count_type(initial, y, x, ring, {5}),
                        count_type(initial, y, x, ring, {11,0}),
                    ])

                # Ball features (cumulative)
                ball_feats = []
                for ball in BALLS:
                    ball_feats.extend([
                        count_type(initial, y, x, ball, {4}),
                        count_type(initial, y, x, ball, {1,2,3}),
                        count_type(initial, y, x, ball, {10}),
                        count_type(initial, y, x, ball, {5}),
                        count_type(initial, y, x, ball, {11,0}),
                    ])

                X_list.append(ring_feats + ball_feats)
                Y_list.append(dist)
        per_seed.append((np.array(X_list), np.array(Y_list)))

    print(f"\n{name}:")

    # Test: rings-only vs balls-only vs combined
    configs = [
        ("rings 1-4", slice(0, 20)),
        ("balls 1-4", slice(20, 40)),
        ("rings+balls", slice(0, 40)),
    ]

    for cfg_name, feat_slice in configs:
        cv_kls = []
        for test_idx in range(len(per_seed)):
            X_train = np.vstack([per_seed[i][0][:, feat_slice] for i in range(len(per_seed)) if i != test_idx])
            Y_train = np.vstack([per_seed[i][1] for i in range(len(per_seed)) if i != test_idx])
            X_test = per_seed[test_idx][0][:, feat_slice]
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
        print(f"  {cfg_name:15s}: CV-KL = {np.mean(cv_kls):.4f}")

    # Test key interactions: ocean_r1 * settle_r1 (for port proximity)
    print(f"\n  Testing interaction features:")
    cv_kls_base = []
    cv_kls_int = []
    for test_idx in range(len(per_seed)):
        X_train_base = np.vstack([per_seed[i][0][:, :20] for i in range(len(per_seed)) if i != test_idx])
        Y_train = np.vstack([per_seed[i][1] for i in range(len(per_seed)) if i != test_idx])
        X_test_base = per_seed[test_idx][0][:, :20]
        Y_test = per_seed[test_idx][1]

        # Add interaction features: ocean_r1*settle_r1, forest_r1*settle_r1, forest_r1*plains_r1
        def add_interactions(X):
            return np.column_stack([
                X,
                X[:, 2] * X[:, 1],  # ocean_r1 * settle_r1
                X[:, 0] * X[:, 1],  # forest_r1 * settle_r1
                X[:, 0] * X[:, 4],  # forest_r1 * plains_r1
                X[:, 2] * X[:, 4],  # ocean_r1 * plains_r1
            ])

        X_train_int = add_interactions(X_train_base)
        X_test_int = add_interactions(X_test_base)

        for X_train, X_test, kl_list in [(X_train_base, X_test_base, cv_kls_base),
                                          (X_train_int, X_test_int, cv_kls_int)]:
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
            kl_list.append(kl)

    print(f"  base:         CV-KL = {np.mean(cv_kls_base):.4f}")
    print(f"  +interactions: CV-KL = {np.mean(cv_kls_int):.4f}")
