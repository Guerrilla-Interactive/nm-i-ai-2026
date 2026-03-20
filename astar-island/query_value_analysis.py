#!/usr/bin/env python3
"""
Analyze: how much do simulation queries improve predictions?

Key question: given N observations of a cell, how well can we estimate
the ground truth distribution?

Strategy comparison:
A) 9 tiles per seed (10 per seed × 5 seeds = 50), 1 observation per cell
B) 9 tiles × 2 per seed on 2 seeds (45), leave 3 seeds regression-only  
C) Full tiling once per seed (45), 1 targeted re-query per seed (5)
"""
import json, numpy as np
from collections import defaultdict

GRID_SIZE = 40
NUM_CLASSES = 6
SIM_TO_CLASS = {10: 0, 11: 0, 0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5}

def cell_entropy(p):
    return -sum(pi * np.log(pi) if pi > 0 else 0 for pi in p)

def kl_div(p, q):
    return sum(pi * np.log(pi / qi) if pi > 0 else 0 for pi, qi in zip(p, q))

def score_pred(pred, gt, floor=0.005):
    gt = np.array(gt)
    pred = np.maximum(pred, floor)
    pred = pred / pred.sum(axis=-1, keepdims=True)
    tek, te = 0, 0
    for y in range(40):
        for x in range(40):
            p = gt[y,x]; q = pred[y,x]
            ent = cell_entropy(p)
            if ent < 1e-10: continue
            kl = kl_div(p, q)
            tek += ent * kl; te += ent
    return max(0, min(100, 100 * np.exp(-3 * tek / te))) if te > 0 else 0

def sample_from_gt(gt):
    """Sample ONE simulation outcome from ground truth."""
    result = np.zeros((GRID_SIZE, GRID_SIZE), dtype=int)
    for y in range(GRID_SIZE):
        for x in range(GRID_SIZE):
            result[y, x] = np.random.choice(6, p=gt[y][x])
    return result

def empirical_predict(samples, prior, prior_weight=1.0, floor=0.005):
    """
    Combine empirical counts with prior.
    
    For each cell: posterior = (prior_weight * prior + counts) / (prior_weight + n)
    """
    n_samples = len(samples)
    counts = np.zeros((GRID_SIZE, GRID_SIZE, NUM_CLASSES))
    for s in samples:
        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                counts[y, x, s[y, x]] += 1
    
    pred = (prior_weight * prior + counts) / (prior_weight + n_samples)
    pred = np.maximum(pred, floor)
    pred = pred / pred.sum(axis=-1, keepdims=True)
    return pred

# Load data
r2 = [json.load(open(f'data/r2_analysis_seed{i}.json')) for i in range(5)]
r3 = [json.load(open(f'data/r3_analysis_seed{i}.json')) for i in range(5)]

np.random.seed(42)

print("=" * 70)
print("SIMULATION QUERY VALUE ANALYSIS")
print("=" * 70)

for rnd_name, seeds in [('R2', r2), ('R3', r3)]:
    print(f"\n--- {rnd_name} ---")
    
    # Build terrain-group prior from same round (leave-one-out)
    def build_group_prior(train_seeds):
        groups = defaultdict(lambda: {'sum': np.zeros(6), 'count': 0})
        for seed in train_seeds:
            grid = seed['initial_grid']
            gt = seed['ground_truth']
            for y in range(40):
                for x in range(40):
                    code = grid[y][x]
                    if code in (10, 5): continue
                    from deep_analysis import is_coastal, count_neighbors
                    coastal = is_coastal(grid, y, x)
                    s1 = min(count_neighbors(grid, y, x, {1, 2, 3}, 1), 3)
                    key = (code, coastal, s1)
                    groups[key]['sum'] += gt[y][x]
                    groups[key]['count'] += 1
        return {k: v['sum']/v['count'] for k, v in groups.items() if v['count'] > 0}
    
    def make_prior_grid(grid, group_avgs):
        prior = np.zeros((40, 40, 6))
        for y in range(40):
            for x in range(40):
                code = grid[y][x]
                if code == 5:
                    prior[y,x] = [0,0,0,0,0,1]
                elif code == 10:
                    prior[y,x] = [1,0,0,0,0,0]
                else:
                    from deep_analysis import is_coastal, count_neighbors
                    coastal = is_coastal(grid, y, x)
                    s1 = min(count_neighbors(grid, y, x, {1, 2, 3}, 1), 3)
                    key = (code, coastal, s1)
                    if key in group_avgs:
                        prior[y,x] = group_avgs[key]
                    else:
                        prior[y,x] = [1/6]*6
        return prior
    
    for si in range(3):
        train = [s for i, s in enumerate(seeds) if i != si]
        test = seeds[si]
        gt = np.array(test['ground_truth'])
        grid = test['initial_grid']
        
        group_avgs = build_group_prior(train)
        prior = make_prior_grid(grid, group_avgs)
        
        # Score: prior only
        s_prior = score_pred(prior, gt)
        
        # Score: prior + N simulation samples
        for n_samples in [1, 2, 5, 10]:
            for pw in [0.5, 1.0, 2.0, 5.0]:
                samples = [sample_from_gt(gt) for _ in range(n_samples)]
                pred = empirical_predict(samples, prior, prior_weight=pw)
                s = score_pred(pred, gt)
                if pw == 1.0:
                    print(f"  Seed {si}: prior={s_prior:.1f}  "
                          f"+{n_samples}sim(pw={pw})={s:.1f}  "
                          f"delta={s-s_prior:+.1f}")

    # What about using ONLY empirical counts (no prior from another round)?
    print(f"\n  --- Empirical-only (uniform prior) ---")
    for si in range(3):
        gt = np.array(seeds[si]['ground_truth'])
        uniform_prior = np.full((40, 40, 6), 1/6)
        
        for n_samples in [1, 5, 10, 50]:
            samples = [sample_from_gt(gt) for _ in range(n_samples)]
            pred = empirical_predict(samples, uniform_prior, prior_weight=1.0)
            s = score_pred(pred, gt)
            print(f"  Seed {si}: {n_samples} samples (uniform prior): {s:.1f}")
