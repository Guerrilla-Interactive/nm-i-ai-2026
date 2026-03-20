#!/usr/bin/env python3
"""Deep analysis of R2+R3 ground truth to understand scoring dynamics."""
import json, numpy as np
from collections import defaultdict

GRID_SIZE = 40
NUM_CLASSES = 6
CLASS_NAMES = ['Empty', 'Settlement', 'Port', 'Ruin', 'Forest', 'Mountain']
TERRAIN_NAMES = {0:'Empty', 1:'Settlement', 2:'Port', 3:'Ruin', 4:'Forest', 5:'Mountain', 10:'Ocean', 11:'Plains'}

def load_seeds(round_num, n=5):
    seeds = []
    for i in range(n):
        with open(f'data/r{round_num}_analysis_seed{i}.json') as f:
            seeds.append(json.load(f))
    return seeds

def count_neighbors(grid, y, x, codes, radius):
    count = 0
    for dy in range(-radius, radius+1):
        for dx in range(-radius, radius+1):
            if dy == 0 and dx == 0: continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < GRID_SIZE and 0 <= nx < GRID_SIZE:
                if grid[ny][nx] in codes: count += 1
    return count

def is_coastal(grid, y, x):
    for dy in [-1, 0, 1]:
        for dx in [-1, 0, 1]:
            if dy == 0 and dx == 0: continue
            ny, nx = y + dy, x + dx
            if ny < 0 or ny >= GRID_SIZE or nx < 0 or nx >= GRID_SIZE: return True
            if grid[ny][nx] == 10: return True
    return False

def cell_entropy(p):
    return -sum(pi * np.log(pi) if pi > 0 else 0 for pi in p)

def kl_div(p, q):
    return sum(pi * np.log(pi / qi) if pi > 0 else 0 for pi, qi in zip(p, q))

# ============================================================
# SECTION 1: Per-terrain-type ground truth distributions
# ============================================================
print("=" * 70)
print("SECTION 1: Ground Truth Distributions by Terrain Type and Round")
print("=" * 70)

for rnd in [2, 3]:
    seeds = load_seeds(rnd)
    print(f"\n--- Round {rnd} ---")
    
    terrain_gt = defaultdict(list)
    terrain_ent = defaultdict(list)
    
    for seed in seeds:
        grid = seed['initial_grid']
        gt = seed['ground_truth']
        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                code = grid[y][x]
                p = gt[y][x]
                terrain_gt[code].append(p)
                terrain_ent[code].append(cell_entropy(p))
    
    for code in sorted(terrain_gt.keys()):
        avg_gt = np.mean(terrain_gt[code], axis=0)
        avg_ent = np.mean(terrain_ent[code])
        n_dynamic = sum(1 for e in terrain_ent[code] if e > 0.01)
        n = len(terrain_gt[code])
        print(f"  {TERRAIN_NAMES.get(code, code):10s} (n={n:5d}): "
              f"[{' '.join(f'{v:.4f}' for v in avg_gt)}] "
              f"ent={avg_ent:.4f} dynamic={n_dynamic}")

# ============================================================
# SECTION 2: Sub-group analysis (terrain × coastal × settle_r1)
# ============================================================
print("\n" + "=" * 70)
print("SECTION 2: Fine-grained Groups (terrain × coastal × settle_neighbors)")
print("=" * 70)

for rnd in [2, 3]:
    seeds = load_seeds(rnd)
    print(f"\n--- Round {rnd} ---")
    
    groups = defaultdict(list)
    for seed in seeds:
        grid = seed['initial_grid']
        gt = seed['ground_truth']
        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                code = grid[y][x]
                if code in (10, 5): continue
                coastal = is_coastal(grid, y, x)
                s1 = min(count_neighbors(grid, y, x, {1, 2, 3}, 1), 3)
                f1 = min(count_neighbors(grid, y, x, {4}, 1), 4)
                key = (code, coastal, s1)
                groups[key].append(gt[y][x])
    
    for key in sorted(groups.keys()):
        code, coastal, s1 = key
        vals = groups[key]
        if len(vals) < 10: continue
        avg = np.mean(vals, axis=0)
        avg_ent = np.mean([cell_entropy(v) for v in vals])
        c_str = "COAST" if coastal else "INLND"
        print(f"  ({TERRAIN_NAMES.get(code,'?'):8s}, {c_str}, s1={s1}): "
              f"n={len(vals):4d}  ent={avg_ent:.4f}  "
              f"[{' '.join(f'{v:.3f}' for v in avg)}]")

# ============================================================
# SECTION 3: Entropy distribution — what cells matter for scoring?
# ============================================================
print("\n" + "=" * 70)
print("SECTION 3: Entropy Distribution — What Matters for Scoring")
print("=" * 70)

for rnd in [2, 3]:
    seeds = load_seeds(rnd)
    print(f"\n--- Round {rnd} ---")
    
    all_ent = []
    ent_by_type = defaultdict(list)
    total_ent = 0
    ent_contribution = defaultdict(float)
    
    for seed in seeds:
        grid = seed['initial_grid']
        gt = seed['ground_truth']
        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                code = grid[y][x]
                p = gt[y][x]
                ent = cell_entropy(p)
                all_ent.append(ent)
                ent_by_type[code].append(ent)
                total_ent += ent
                ent_contribution[code] += ent
    
    print(f"  Total entropy weight: {total_ent:.1f}")
    print(f"  Cells with ent>0: {sum(1 for e in all_ent if e > 0.001)}/{len(all_ent)}")
    print(f"  Cells with ent>0.1: {sum(1 for e in all_ent if e > 0.1)}")
    print(f"  Cells with ent>0.5: {sum(1 for e in all_ent if e > 0.5)}")
    print(f"  Entropy contribution by terrain:")
    for code in sorted(ent_contribution.keys()):
        pct = ent_contribution[code] / total_ent * 100
        n = len(ent_by_type[code])
        print(f"    {TERRAIN_NAMES.get(code,'?'):10s}: {ent_contribution[code]:7.1f} ({pct:5.1f}%) n={n}")

# ============================================================
# SECTION 4: What would a PERFECT terrain-type prior score?
# ============================================================
print("\n" + "=" * 70)
print("SECTION 4: Baseline Scores — Terrain-Type Averages")
print("=" * 70)

for rnd in [2, 3]:
    seeds = load_seeds(rnd)
    print(f"\n--- Round {rnd} ---")
    
    # Build per-terrain-type average from 4 seeds, test on 1
    for test_idx in range(5):
        train_seeds = [s for i, s in enumerate(seeds) if i != test_idx]
        
        terrain_avg = defaultdict(lambda: np.zeros(6))
        terrain_count = defaultdict(int)
        for seed in train_seeds:
            grid = seed['initial_grid']
            gt = seed['ground_truth']
            for y in range(GRID_SIZE):
                for x in range(GRID_SIZE):
                    code = grid[y][x]
                    terrain_avg[code] += gt[y][x]
                    terrain_count[code] += 1
        for code in terrain_avg:
            terrain_avg[code] /= terrain_count[code]
        
        # Score
        test = seeds[test_idx]
        grid = test['initial_grid']
        gt = np.array(test['ground_truth'])
        
        total_ent_kl = 0
        total_ent = 0
        floor = 0.005
        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                p = gt[y, x]
                code = grid[y][x]
                q = np.maximum(terrain_avg[code], floor)
                q = q / q.sum()
                ent = cell_entropy(p)
                if ent < 1e-10: continue
                kl = kl_div(p, q)
                total_ent_kl += ent * kl
                total_ent += ent
        
        wkl = total_ent_kl / total_ent
        score = max(0, min(100, 100 * np.exp(-3 * wkl)))
        print(f"  Seed {test_idx} (terrain-avg prior): score={score:.2f}")

# ============================================================
# SECTION 5: Fine-grained group averages as predictor
# ============================================================
print("\n" + "=" * 70)
print("SECTION 5: Fine-Grained Group Averages")
print("=" * 70)

for rnd in [2, 3]:
    seeds = load_seeds(rnd)
    print(f"\n--- Round {rnd} ---")
    
    for test_idx in range(5):
        train_seeds = [s for i, s in enumerate(seeds) if i != test_idx]
        
        # Build group averages
        groups = defaultdict(lambda: {'sum': np.zeros(6), 'count': 0})
        terrain_avg = defaultdict(lambda: {'sum': np.zeros(6), 'count': 0})
        
        for seed in train_seeds:
            grid = seed['initial_grid']
            gt = seed['ground_truth']
            for y in range(GRID_SIZE):
                for x in range(GRID_SIZE):
                    code = grid[y][x]
                    if code in (10, 5): continue
                    
                    coastal = is_coastal(grid, y, x)
                    s1 = min(count_neighbors(grid, y, x, {1, 2, 3}, 1), 3)
                    f1 = min(count_neighbors(grid, y, x, {4}, 1), 4)
                    
                    # Multiple granularity keys
                    key_fine = (code, coastal, s1, f1)
                    key_med = (code, coastal, s1)
                    key_coarse = (code, coastal)
                    
                    for k in [key_fine, key_med, key_coarse]:
                        groups[k]['sum'] += gt[y][x]
                        groups[k]['count'] += 1
                    
                    terrain_avg[code]['sum'] += gt[y][x]
                    terrain_avg[code]['count'] += 1
        
        # Score
        test = seeds[test_idx]
        grid = test['initial_grid']
        gt = np.array(test['ground_truth'])
        floor = 0.005
        
        total_ent_kl = 0
        total_ent = 0
        
        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                p = gt[y, x]
                code = grid[y][x]
                
                if code == 5:
                    q = np.array([0, 0, 0, 0, 0, 1.0])
                elif code == 10:
                    q = np.array([1.0, 0, 0, 0, 0, 0])
                else:
                    coastal = is_coastal(grid, y, x)
                    s1 = min(count_neighbors(grid, y, x, {1, 2, 3}, 1), 3)
                    f1 = min(count_neighbors(grid, y, x, {4}, 1), 4)
                    
                    # Try finest granularity first
                    for key in [(code, coastal, s1, f1), (code, coastal, s1), (code, coastal)]:
                        if groups[key]['count'] >= 10:
                            q = groups[key]['sum'] / groups[key]['count']
                            break
                    else:
                        q = terrain_avg[code]['sum'] / terrain_avg[code]['count']
                
                q = np.maximum(q, floor)
                q = q / q.sum()
                
                ent = cell_entropy(p)
                if ent < 1e-10: continue
                kl = kl_div(p, q)
                total_ent_kl += ent * kl
                total_ent += ent
        
        wkl = total_ent_kl / total_ent
        score = max(0, min(100, 100 * np.exp(-3 * wkl)))
        print(f"  Seed {test_idx} (group-avg): score={score:.2f}")

print("\nDone!")
