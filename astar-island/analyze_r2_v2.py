#!/usr/bin/env python3
"""Deeper analysis: settlement neighbor COUNT effect + ocean neighbor effect."""
import json, numpy as np, os
from collections import defaultdict

DIR = os.path.dirname(os.path.abspath(__file__))
seeds_data = []
for seed in range(5):
    with open(os.path.join(DIR, f'round2_analysis_seed{seed}.json')) as f:
        seeds_data.append(json.load(f))

def count_neighbors(grid, y, x, codes, radius):
    count = 0
    for dy in range(-radius, radius+1):
        for dx in range(-radius, radius+1):
            if dy == 0 and dx == 0: continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < 40 and 0 <= nx < 40 and grid[ny][nx] in codes:
                count += 1
    return count

# For plains (11): analyze settlement neighbor COUNT at radius=3
print("=== PLAINS (11): Settlement neighbor count (radius=3) ===")
buckets = defaultdict(list)
for data in seeds_data:
    g, t = data['initial_grid'], np.array(data['ground_truth'])
    for y in range(40):
        for x in range(40):
            if g[y][x] != 11: continue
            nc = count_neighbors(g, y, x, {1,2,3}, radius=3)
            # Also get ocean count
            oc = count_neighbors(g, y, x, {10}, radius=2)
            buckets[(nc, oc)].append(t[y,x])

# Aggregate by settlement count
sett_buckets = defaultdict(list)
for (sc, oc), vecs in buckets.items():
    sett_buckets[sc].extend(vecs)

for sc in sorted(sett_buckets.keys()):
    vecs = np.array(sett_buckets[sc])
    if len(vecs) >= 10:
        m = vecs.mean(axis=0)
        print(f"  sett_count={sc:2d} (n={len(vecs):4d}): [{', '.join(f'{v:.4f}' for v in m)}]")

# For plains: combined settlement + ocean
print("\n=== PLAINS (11): Combined sett(r=3) x ocean(r=2) ===")
for sett_thresh in [0, 1, 3]:
    for ocean_thresh in [0, 4]:
        vecs = []
        for data in seeds_data:
            g, t = data['initial_grid'], np.array(data['ground_truth'])
            for y in range(40):
                for x in range(40):
                    if g[y][x] != 11: continue
                    sc = count_neighbors(g, y, x, {1,2,3}, radius=3)
                    oc = count_neighbors(g, y, x, {10}, radius=2)
                    if sett_thresh == 0 and sc == 0 and oc >= ocean_thresh:
                        vecs.append(t[y,x])
                    elif sett_thresh == 1 and 1 <= sc <= 2 and oc < 4:
                        vecs.append(t[y,x])
                    elif sett_thresh == 3 and sc >= 3 and oc < 4:
                        vecs.append(t[y,x])
        if len(vecs) >= 10:
            m = np.array(vecs).mean(axis=0)
            print(f"  sett>={sett_thresh} ocean>={ocean_thresh} (n={len(vecs):4d}): [{', '.join(f'{v:.4f}' for v in m)}]")

# For forest (4): settlement neighbor COUNT at radius=3
print("\n=== FOREST (4): Settlement neighbor count (radius=3) ===")
sett_buckets = defaultdict(list)
for data in seeds_data:
    g, t = data['initial_grid'], np.array(data['ground_truth'])
    for y in range(40):
        for x in range(40):
            if g[y][x] != 4: continue
            sc = count_neighbors(g, y, x, {1,2,3}, radius=3)
            sett_buckets[sc].append(t[y,x])

for sc in sorted(sett_buckets.keys()):
    vecs = np.array(sett_buckets[sc])
    if len(vecs) >= 10:
        m = vecs.mean(axis=0)
        print(f"  sett_count={sc:2d} (n={len(vecs):4d}): [{', '.join(f'{v:.4f}' for v in m)}]")

# Settlement (1): analyze by forest neighbor count
print("\n=== SETTLEMENT (1): Forest neighbor count (radius=2) ===")
for data in seeds_data:
    g, t = data['initial_grid'], np.array(data['ground_truth'])
sett_buckets = defaultdict(list)
for data in seeds_data:
    g, t = data['initial_grid'], np.array(data['ground_truth'])
    for y in range(40):
        for x in range(40):
            if g[y][x] != 1: continue
            fc = count_neighbors(g, y, x, {4}, radius=2)
            sett_buckets[fc].append(t[y,x])

for fc in sorted(sett_buckets.keys()):
    vecs = np.array(sett_buckets[fc])
    if len(vecs) >= 10:
        m = vecs.mean(axis=0)
        print(f"  forest_count={fc:2d} (n={len(vecs):4d}): [{', '.join(f'{v:.4f}' for v in m)}]")

# Settlement (1): analyze by settlement neighbor count
print("\n=== SETTLEMENT (1): Settlement neighbor count (radius=2) ===")
sett_buckets = defaultdict(list)
for data in seeds_data:
    g, t = data['initial_grid'], np.array(data['ground_truth'])
    for y in range(40):
        for x in range(40):
            if g[y][x] != 1: continue
            sc = count_neighbors(g, y, x, {1,2,3}, radius=2)
            sett_buckets[sc].append(t[y,x])

for sc in sorted(sett_buckets.keys()):
    vecs = np.array(sett_buckets[sc])
    if len(vecs) >= 5:
        m = vecs.mean(axis=0)
        print(f"  sett_count={sc:2d} (n={len(vecs):4d}): [{', '.join(f'{v:.4f}' for v in m)}]")
