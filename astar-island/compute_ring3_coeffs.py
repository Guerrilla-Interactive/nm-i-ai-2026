#!/usr/bin/env python3
"""Compute ring1+2+3 regression coefficients for all cell types."""
import json, numpy as np, os
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

    X = np.array(X_list)
    Y = np.array(Y_list)
    X_aug = np.column_stack([np.ones(len(X)), X])

    print(f"\n{name.upper()}_COEFFS = np.array([")
    for cls in range(6):
        c, _, _, _ = lstsq(X_aug, Y[:, cls], rcond=None)
        vals = ", ".join(f"{v:.6f}" for v in c)
        print(f"    [{vals}],  # class {cls}")
    print("])")
