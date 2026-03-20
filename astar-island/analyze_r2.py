#!/usr/bin/env python3
"""Analyze Round 2 ground truth to extract empirical distributions per terrain code."""
import json, numpy as np, os, sys
from collections import defaultdict

DIR = os.path.dirname(os.path.abspath(__file__))

# Load all 5 seeds
seeds_data = []
for seed in range(5):
    path = os.path.join(DIR, f'round2_analysis_seed{seed}.json')
    with open(path) as f:
        seeds_data.append(json.load(f))

# ---- STEP 1: Average distribution per initial terrain code ----
code_dists = defaultdict(list)  # code -> list of 6-vectors

for data in seeds_data:
    grid = data['initial_grid']
    truth = np.array(data['ground_truth'])  # 40x40x6
    for y in range(40):
        for x in range(40):
            code = grid[y][x]
            code_dists[code].append(truth[y, x])

print("=" * 60)
print("AVERAGE GROUND TRUTH DISTRIBUTION PER INITIAL TERRAIN CODE")
print("=" * 60)
for code in sorted(code_dists.keys()):
    vecs = np.array(code_dists[code])
    mean = vecs.mean(axis=0)
    std = vecs.std(axis=0)
    entropy = -np.sum(mean * np.log(mean + 1e-12))
    print(f"\nCode {code:2d} (n={len(vecs):5d}, entropy={entropy:.3f}):")
    print(f"  mean: [{', '.join(f'{v:.6f}' for v in mean)}]")
    print(f"  std:  [{', '.join(f'{v:.6f}' for v in std)}]")
    # Python code ready to copy
    print(f"  # {code}: [{', '.join(f'{v:.4f}' for v in mean)}]")

# ---- STEP 2: Neighbor-based analysis for dynamic codes ----
print("\n" + "=" * 60)
print("NEIGHBOR-BASED ANALYSIS (radius=2)")
print("=" * 60)

DYNAMIC_CODES = [0, 1, 2, 3, 4, 10, 11]  # skip 5 (mountain)

def count_neighbors_of_type(grid, y, x, codes, radius=2):
    count = 0
    total = 0
    for dy in range(-radius, radius+1):
        for dx in range(-radius, radius+1):
            if dy == 0 and dx == 0:
                continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < 40 and 0 <= nx < 40:
                total += 1
                if grid[ny][nx] in codes:
                    count += 1
    return count, total

# For each dynamic code, check how the distribution changes based on:
# - fraction of ocean neighbors
# - fraction of settlement/port/ruin neighbors
# - fraction of forest neighbors
neighbor_groups = {
    'ocean': [10],
    'settlement': [1, 2, 3],
    'forest': [4],
    'plains': [0, 11],
    'mountain': [5],
}

for code in DYNAMIC_CODES:
    if code == 5:
        continue
    print(f"\n--- Code {code} ---")

    for ng_name, ng_codes in neighbor_groups.items():
        # Bucket by neighbor fraction: 0, low (1-3), med (4-8), high (9+)
        buckets = {'zero': [], 'low': [], 'med': [], 'high': []}

        for data in seeds_data:
            grid = data['initial_grid']
            truth = np.array(data['ground_truth'])
            for y in range(40):
                for x in range(40):
                    if grid[y][x] != code:
                        continue
                    nc, nt = count_neighbors_of_type(grid, y, x, ng_codes, radius=2)
                    if nc == 0:
                        buckets['zero'].append(truth[y, x])
                    elif nc <= 3:
                        buckets['low'].append(truth[y, x])
                    elif nc <= 8:
                        buckets['med'].append(truth[y, x])
                    else:
                        buckets['high'].append(truth[y, x])

        # Only print if there's meaningful variation
        means = {}
        for bname, vecs in buckets.items():
            if len(vecs) >= 5:
                means[bname] = np.array(vecs).mean(axis=0)

        if len(means) >= 2:
            # Check if there's meaningful variation
            all_means = list(means.values())
            max_diff = max(np.max(np.abs(a - b)) for a in all_means for b in all_means)
            if max_diff > 0.03:  # Only print if >3% variation
                print(f"  Neighbors={ng_name}:")
                for bname in ['zero', 'low', 'med', 'high']:
                    if bname in means:
                        n = len(buckets[bname])
                        m = means[bname]
                        print(f"    {bname:5s} (n={n:4d}): [{', '.join(f'{v:.4f}' for v in m)}]")

# ---- STEP 3: Specifically analyze near-settlement effect for key codes ----
print("\n" + "=" * 60)
print("NEAR-SETTLEMENT EFFECT (radius=3)")
print("=" * 60)

for code in [0, 4, 10, 11]:
    near = []
    far = []
    for data in seeds_data:
        grid = data['initial_grid']
        truth = np.array(data['ground_truth'])
        for y in range(40):
            for x in range(40):
                if grid[y][x] != code:
                    continue
                nc, _ = count_neighbors_of_type(grid, y, x, [1, 2, 3], radius=3)
                if nc > 0:
                    near.append(truth[y, x])
                else:
                    far.append(truth[y, x])

    if near and far:
        near_m = np.array(near).mean(axis=0)
        far_m = np.array(far).mean(axis=0)
        print(f"\nCode {code}:")
        print(f"  Near settlement (n={len(near):4d}): [{', '.join(f'{v:.4f}' for v in near_m)}]")
        print(f"  Far  settlement (n={len(far):4d}): [{', '.join(f'{v:.4f}' for v in far_m)}]")
