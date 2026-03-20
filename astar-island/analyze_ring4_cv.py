#!/usr/bin/env python3
"""Quick CV test of ring-4 and interaction features."""
import json, numpy as np, os
from numpy.linalg import lstsq

BASE = os.path.dirname(os.path.abspath(__file__))

def make_ring(r):
    return [(dy, dx) for dy in range(-r, r+1) for dx in range(-r, r+1) if max(abs(dy), abs(dx)) == r]

RINGS = [make_ring(r) for r in range(1, 6)]

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
                features = []
                for ring in RINGS:
                    features.extend([
                        count_type(initial, y, x, ring, {4}),
                        count_type(initial, y, x, ring, {1,2,3}),
                        count_type(initial, y, x, ring, {10}),
                        count_type(initial, y, x, ring, {5}),
                        count_type(initial, y, x, ring, {11,0}),
                    ])
                X_list.append(features)
                Y_list.append(dist)
        per_seed.append((np.array(X_list), np.array(Y_list)))

    print(f"\n{name}:")
    for n_rings in [3, 4, 5]:
        n_feat = n_rings * 5
        cv_kls = []
        for test_idx in range(len(per_seed)):
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
        print(f"  ring1..{n_rings}: CV-KL = {np.mean(cv_kls):.4f} ± {np.std(cv_kls):.4f}")
