#!/usr/bin/env python3
"""Analyze how neighbor terrain affects ground truth distributions."""
import json, numpy as np, os
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))

seeds = []
for seed in range(5):
    path = os.path.join(BASE, f'round2_analysis_seed{seed}.json')
    if os.path.exists(path):
        with open(path) as f:
            seeds.append(json.load(f))

# For each dynamic cell, compute neighbor features and correlate with truth
# Focus on Plains (code 11) since they're the most numerous dynamic cells

DIRECTIONS = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]

def get_neighbor_counts(initial, y, x):
    """Count neighbors by type."""
    counts = defaultdict(int)
    for dy, dx in DIRECTIONS:
        ny, nx = y + dy, x + dx
        if 0 <= ny < 40 and 0 <= nx < 40:
            counts[initial[ny][nx]] += 1
        else:
            counts[-1] += 1  # edge
    return counts

# Analyze: for Plains cells, how does number of Forest neighbors affect Forest probability?
print("=" * 80)
print("PLAINS CELLS: Forest neighbor count vs Forest probability (class 4)")
print("=" * 80)

by_forest_neighbors = defaultdict(list)
by_settlement_neighbors = defaultdict(list)
by_ocean_adj = defaultdict(list)

for data in seeds:
    initial = data['initial_grid']
    truth = np.array(data['ground_truth'])
    for y in range(40):
        for x in range(40):
            code = initial[y][x]
            dist = truth[y, x]
            entropy = -np.sum(dist * np.log(dist + 1e-12))
            if entropy < 1e-6:
                continue

            nc = get_neighbor_counts(initial, y, x)

            if code == 11:  # Plains
                n_forest = nc.get(4, 0)
                by_forest_neighbors[n_forest].append(dist)

                n_settle = nc.get(1, 0) + nc.get(2, 0) + nc.get(3, 0)
                by_settlement_neighbors[n_settle].append(dist)

                n_ocean = nc.get(10, 0)
                by_ocean_adj[n_ocean].append(dist)

print("\nForest neighbors -> avg distribution:")
for k in sorted(by_forest_neighbors.keys()):
    dists = np.array(by_forest_neighbors[k])
    mean = dists.mean(axis=0)
    print(f"  {k} forest neighbors (n={len(dists)}): [{', '.join(f'{v:.4f}' for v in mean)}]")

print("\nSettlement/Port/Ruin neighbors -> avg distribution:")
for k in sorted(by_settlement_neighbors.keys()):
    dists = np.array(by_settlement_neighbors[k])
    mean = dists.mean(axis=0)
    print(f"  {k} settle neighbors (n={len(dists)}): [{', '.join(f'{v:.4f}' for v in mean)}]")

print("\nOcean neighbors -> avg distribution:")
for k in sorted(by_ocean_adj.keys()):
    dists = np.array(by_ocean_adj[k])
    mean = dists.mean(axis=0)
    print(f"  {k} ocean neighbors (n={len(dists)}): [{', '.join(f'{v:.4f}' for v in mean)}]")

# Forest cells: Settlement neighbors
print("\n" + "=" * 80)
print("FOREST CELLS: neighbor effects")
print("=" * 80)

forest_by_settle = defaultdict(list)
forest_by_plains = defaultdict(list)
for data in seeds:
    initial = data['initial_grid']
    truth = np.array(data['ground_truth'])
    for y in range(40):
        for x in range(40):
            if initial[y][x] != 4:
                continue
            dist = truth[y, x]
            entropy = -np.sum(dist * np.log(dist + 1e-12))
            if entropy < 1e-6:
                continue
            nc = get_neighbor_counts(initial, y, x)
            n_settle = nc.get(1, 0) + nc.get(2, 0) + nc.get(3, 0)
            forest_by_settle[n_settle].append(dist)
            n_plains = nc.get(11, 0) + nc.get(0, 0)
            forest_by_plains[n_plains].append(dist)

print("\nSettlement neighbors:")
for k in sorted(forest_by_settle.keys()):
    dists = np.array(forest_by_settle[k])
    mean = dists.mean(axis=0)
    print(f"  {k} settle neighbors (n={len(dists)}): [{', '.join(f'{v:.4f}' for v in mean)}]")

print("\nPlains neighbors:")
for k in sorted(forest_by_plains.keys()):
    dists = np.array(forest_by_plains[k])
    mean = dists.mean(axis=0)
    print(f"  {k} plains neighbors (n={len(dists)}): [{', '.join(f'{v:.4f}' for v in mean)}]")

# Settlement cells: neighbor effects
print("\n" + "=" * 80)
print("SETTLEMENT CELLS: neighbor effects")
print("=" * 80)

settle_by_forest = defaultdict(list)
settle_by_plains = defaultdict(list)
for data in seeds:
    initial = data['initial_grid']
    truth = np.array(data['ground_truth'])
    for y in range(40):
        for x in range(40):
            if initial[y][x] != 1:
                continue
            dist = truth[y, x]
            nc = get_neighbor_counts(initial, y, x)
            n_forest = nc.get(4, 0)
            settle_by_forest[n_forest].append(dist)
            n_plains = nc.get(11, 0) + nc.get(0, 0)
            settle_by_plains[n_plains].append(dist)

print("\nForest neighbors:")
for k in sorted(settle_by_forest.keys()):
    dists = np.array(settle_by_forest[k])
    mean = dists.mean(axis=0)
    print(f"  {k} forest neighbors (n={len(dists)}): [{', '.join(f'{v:.4f}' for v in mean)}]")

print("\nPlains neighbors:")
for k in sorted(settle_by_plains.keys()):
    dists = np.array(settle_by_plains[k])
    mean = dists.mean(axis=0)
    print(f"  {k} plains neighbors (n={len(dists)}): [{', '.join(f'{v:.4f}' for v in mean)}]")

# Try a regression: for Plains cells, predict each class probability from neighbor counts
print("\n" + "=" * 80)
print("LINEAR REGRESSION: Plains cell distributions from neighbor features")
print("=" * 80)

X_list = []
Y_list = []
for data in seeds:
    initial = data['initial_grid']
    truth = np.array(data['ground_truth'])
    for y in range(40):
        for x in range(40):
            if initial[y][x] != 11:
                continue
            dist = truth[y, x]
            entropy = -np.sum(dist * np.log(dist + 1e-12))
            if entropy < 1e-6:
                continue
            nc = get_neighbor_counts(initial, y, x)
            features = [
                nc.get(4, 0),   # forest neighbors
                nc.get(1, 0) + nc.get(2, 0) + nc.get(3, 0),  # settlement/port/ruin
                nc.get(10, 0),  # ocean neighbors
                nc.get(5, 0),   # mountain neighbors
            ]
            X_list.append(features)
            Y_list.append(dist)

X = np.array(X_list)
Y = np.array(Y_list)

# Simple: correlations
for cls in range(6):
    print(f"\nClass {cls}:")
    for feat_idx, feat_name in enumerate(["forest_nbrs", "settle_nbrs", "ocean_nbrs", "mountain_nbrs"]):
        corr = np.corrcoef(X[:, feat_idx], Y[:, cls])[0, 1]
        print(f"  {feat_name}: corr={corr:.4f}")

# Linear regression
from numpy.linalg import lstsq
X_aug = np.column_stack([np.ones(len(X)), X])
for cls in range(5):  # skip Mountain
    coeffs, _, _, _ = lstsq(X_aug, Y[:, cls], rcond=None)
    print(f"\nClass {cls} regression: intercept={coeffs[0]:.6f}, "
          f"forest={coeffs[1]:.6f}, settle={coeffs[2]:.6f}, "
          f"ocean={coeffs[3]:.6f}, mountain={coeffs[4]:.6f}")
