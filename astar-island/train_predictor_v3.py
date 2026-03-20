#!/usr/bin/env python3
"""Train predictor v3: binning + KNN approach for higher accuracy."""
import json, numpy as np
from collections import defaultdict

GRID_SIZE = 40
NUM_CLASSES = 6

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
            if ny < 0 or ny >= GRID_SIZE or nx < 0 or nx >= GRID_SIZE:
                return 1
            if grid[ny][nx] == 10: return 1
    return 0

def get_bin_key(grid, y, x):
    """Create a binning key for this cell based on local neighborhood."""
    code = grid[y][x]
    s1 = count_neighbors(grid, y, x, {1, 2, 3}, 1)
    s2 = count_neighbors(grid, y, x, {1, 2, 3}, 2)
    s3 = count_neighbors(grid, y, x, {1, 2, 3}, 3)
    o1 = count_neighbors(grid, y, x, {10}, 1)
    f1 = count_neighbors(grid, y, x, {4}, 1)
    m1 = count_neighbors(grid, y, x, {5}, 1)
    coastal = is_coastal(grid, y, x)
    port_r1 = count_neighbors(grid, y, x, {2}, 1)
    
    # Bin settlements into groups
    s1_bin = min(s1, 4)  # 0,1,2,3,4+
    s2_bin = min(s2, 6) // 2  # 0-1, 2-3, 4-5, 6+
    s3_bin = min(s3, 8) // 3  # 0-2, 3-5, 6-8+
    o1_bin = min(o1, 3)  # 0,1,2,3+
    f1_bin = min(f1, 4) // 2  # 0-1, 2-3, 4+
    
    return (code, s1_bin, s2_bin, s3_bin, o1_bin, f1_bin, coastal, min(port_r1, 1))

def get_fine_features(grid, y, x):
    """Fine-grained features for regression fallback."""
    s1 = count_neighbors(grid, y, x, {1, 2, 3}, 1)
    s2 = count_neighbors(grid, y, x, {1, 2, 3}, 2)
    s3 = count_neighbors(grid, y, x, {1, 2, 3}, 3)
    s4 = count_neighbors(grid, y, x, {1, 2, 3}, 4)
    o1 = count_neighbors(grid, y, x, {10}, 1)
    o2 = count_neighbors(grid, y, x, {10}, 2)
    f1 = count_neighbors(grid, y, x, {4}, 1)
    f2 = count_neighbors(grid, y, x, {4}, 2)
    m1 = count_neighbors(grid, y, x, {5}, 1)
    p1 = count_neighbors(grid, y, x, {0, 11}, 1)
    p2 = count_neighbors(grid, y, x, {0, 11}, 2)
    coastal = is_coastal(grid, y, x)
    port1 = count_neighbors(grid, y, x, {2}, 1)
    
    return np.array([
        1, s1, s2, s3, s4, o1, o2, f1, f2, m1, p1, p2, coastal, port1,
        s1*o1, s1*f1, s1*coastal, s1**2, s2**2, o1**2, f1**2
    ])

NUM_FEATURES = 21

def load_seeds(indices):
    seeds = []
    for i in indices:
        with open(f'data/r2_analysis_seed{i}.json') as f:
            seeds.append(json.load(f))
    return seeds

def build_bin_lookup(seeds):
    """Build lookup table: bin_key -> average ground truth distribution."""
    bin_data = defaultdict(list)
    for seed in seeds:
        grid = seed['initial_grid']
        gt = seed['ground_truth']
        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                if grid[y][x] in (10, 5): continue
                key = get_bin_key(grid, y, x)
                bin_data[key].append(gt[y][x])
    
    lookup = {}
    for key, vals in bin_data.items():
        lookup[key] = np.mean(vals, axis=0)
    return lookup, bin_data

def build_regression(seeds):
    """Build per-terrain-type regression."""
    X_by_type = defaultdict(list)
    Y_by_type = defaultdict(list)
    for seed in seeds:
        grid = seed['initial_grid']
        gt = seed['ground_truth']
        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                code = grid[y][x]
                if code in (10, 5): continue
                feat = get_fine_features(grid, y, x)
                X_by_type[code].append(feat)
                Y_by_type[code].append(gt[y][x])
    
    coeffs = {}
    for code in X_by_type:
        X = np.array(X_by_type[code])
        Y = np.array(Y_by_type[code])
        lam = 0.01
        W = np.linalg.solve(X.T @ X + lam * np.eye(X.shape[1]), X.T @ Y)
        coeffs[code] = W.T
    return coeffs

def predict(grid, lookup, bin_data, coeffs, floor=0.001, min_bin_size=5):
    """Predict using bin lookup with regression fallback."""
    pred = np.zeros((GRID_SIZE, GRID_SIZE, NUM_CLASSES))
    
    for y in range(GRID_SIZE):
        for x in range(GRID_SIZE):
            code = grid[y][x]
            if code == 5:
                pred[y, x] = [0, 0, 0, 0, 0, 1]
            elif code == 10:
                pred[y, x] = [1, 0, 0, 0, 0, 0]
            else:
                key = get_bin_key(grid, y, x)
                if key in lookup and key in bin_data and len(bin_data[key]) >= min_bin_size:
                    pred[y, x] = lookup[key]
                elif code in coeffs:
                    feat = get_fine_features(grid, y, x)
                    pred[y, x] = coeffs[code] @ feat
                else:
                    pred[y, x] = [1/6]*6
    
    pred = np.maximum(pred, floor)
    pred = pred / pred.sum(axis=-1, keepdims=True)
    return pred

def score_prediction(pred, gt_data):
    gt = np.array(gt_data)
    total_ent_kl = 0
    total_ent = 0
    for y in range(GRID_SIZE):
        for x in range(GRID_SIZE):
            p = gt[y, x]
            q = pred[y, x]
            ent = -sum(pi * np.log(pi) if pi > 0 else 0 for pi in p)
            if ent < 1e-10: continue
            kl = sum(pi * np.log(pi / qi) if pi > 0 else 0 for pi, qi in zip(p, q))
            total_ent_kl += ent * kl
            total_ent += ent
    weighted_kl = total_ent_kl / total_ent if total_ent > 0 else 0
    return max(0, min(100, 100 * np.exp(-3 * weighted_kl)))

# Cross-validation
print("=== V3 Cross-Validation ===")
all_seeds = load_seeds(range(5))
cv_scores = []

for test_idx in range(5):
    train = [s for i, s in enumerate(all_seeds) if i != test_idx]
    test = all_seeds[test_idx]
    
    lookup, bin_data = build_bin_lookup(train)
    coeffs = build_regression(train)
    
    pred = predict(test['initial_grid'], lookup, bin_data, coeffs, floor=0.001, min_bin_size=5)
    score = score_prediction(pred, test['ground_truth'])
    cv_scores.append(score)
    print(f"  Seed {test_idx}: {score:.2f}")

print(f"\n  Average: {np.mean(cv_scores):.2f}")

# Try different min_bin_size
print("\n=== Min Bin Size Sensitivity ===")
for mbs in [1, 3, 5, 10, 20]:
    scores = []
    for test_idx in range(5):
        train = [s for i, s in enumerate(all_seeds) if i != test_idx]
        test = all_seeds[test_idx]
        lookup, bin_data = build_bin_lookup(train)
        coeffs = build_regression(train)
        pred = predict(test['initial_grid'], lookup, bin_data, coeffs, floor=0.001, min_bin_size=mbs)
        score = score_prediction(pred, test['ground_truth'])
        scores.append(score)
    print(f"  min_bin={mbs:3d}: avg={np.mean(scores):.2f}  min={min(scores):.2f}  max={max(scores):.2f}")

# Check bin coverage
print("\n=== Bin Coverage ===")
lookup, bin_data = build_bin_lookup(all_seeds)
sizes = [len(v) for v in bin_data.values()]
print(f"  Total bins: {len(sizes)}")
print(f"  Bin sizes: min={min(sizes)}, max={max(sizes)}, mean={np.mean(sizes):.1f}, median={np.median(sizes):.0f}")
print(f"  Bins with <5 samples: {sum(1 for s in sizes if s < 5)}")
print(f"  Bins with <10 samples: {sum(1 for s in sizes if s < 10)}")
