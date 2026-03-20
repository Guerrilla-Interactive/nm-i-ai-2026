#!/usr/bin/env python3
"""Train predictor from Round 2 ground truth using neighborhood features."""
import json, numpy as np, os
from collections import defaultdict

GRID_SIZE = 40
NUM_CLASSES = 6

def count_neighbors(grid, y, x, codes, radius):
    count = 0
    for dy in range(-radius, radius+1):
        for dx in range(-radius, radius+1):
            if dy == 0 and dx == 0:
                continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < GRID_SIZE and 0 <= nx < GRID_SIZE:
                if grid[ny][nx] in codes:
                    count += 1
    return count

def is_coastal(grid, y, x):
    """Check if cell is adjacent to ocean."""
    for dy in [-1, 0, 1]:
        for dx in [-1, 0, 1]:
            if dy == 0 and dx == 0:
                continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < GRID_SIZE and 0 <= nx < GRID_SIZE:
                if grid[ny][nx] == 10:
                    return 1
            elif True:  # out of bounds = ocean
                return 1
    return 0

def get_features(grid, y, x):
    """Extended feature vector for a cell."""
    settle_r1 = count_neighbors(grid, y, x, {1, 2, 3}, 1)
    settle_r2 = count_neighbors(grid, y, x, {1, 2, 3}, 2)
    settle_r3 = count_neighbors(grid, y, x, {1, 2, 3}, 3)
    settle_r4 = count_neighbors(grid, y, x, {1, 2, 3}, 4)
    ocean_r1 = count_neighbors(grid, y, x, {10}, 1)
    ocean_r2 = count_neighbors(grid, y, x, {10}, 2)
    forest_r1 = count_neighbors(grid, y, x, {4}, 1)
    forest_r2 = count_neighbors(grid, y, x, {4}, 2)
    mountain_r1 = count_neighbors(grid, y, x, {5}, 1)
    plains_r1 = count_neighbors(grid, y, x, {0, 11}, 1)
    plains_r2 = count_neighbors(grid, y, x, {0, 11}, 2)
    coastal = is_coastal(grid, y, x)
    port_r1 = count_neighbors(grid, y, x, {2}, 1)
    port_r2 = count_neighbors(grid, y, x, {2}, 2)
    
    return np.array([
        1,  # intercept
        settle_r1, settle_r2, settle_r3, settle_r4,
        ocean_r1, ocean_r2,
        forest_r1, forest_r2,
        mountain_r1,
        plains_r1, plains_r2,
        coastal,
        port_r1, port_r2,
        settle_r1 * ocean_r1,  # interaction: settlement near coast
        settle_r1 * forest_r1,  # interaction: settlement near forest
        settle_r1 * coastal,    # coastal settlement interaction
    ])

NUM_FEATURES = 18

def load_training_data(seed_indices):
    """Load ground truth data for specified seeds."""
    X_by_type = defaultdict(list)  # terrain_code -> list of feature vectors
    Y_by_type = defaultdict(list)  # terrain_code -> list of GT distributions
    
    for si in seed_indices:
        with open(f'data/r2_analysis_seed{si}.json') as f:
            data = json.load(f)
        grid = data['initial_grid']
        gt = data['ground_truth']
        
        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                code = grid[y][x]
                if code in (10, 5):  # Ocean and Mountain are static
                    continue
                feat = get_features(grid, y, x)
                X_by_type[code].append(feat)
                Y_by_type[code].append(gt[y][x])
    
    return {c: (np.array(X_by_type[c]), np.array(Y_by_type[c])) for c in X_by_type}

def train_regression(X, Y):
    """Train linear regression: Y = X @ W, solve via least squares."""
    # Add L2 regularization
    lam = 0.001
    W = np.linalg.solve(X.T @ X + lam * np.eye(X.shape[1]), X.T @ Y)
    return W

def predict_and_score(grid, gt, coeffs_by_type, floor=0.005):
    """Predict and compute entropy-weighted KL score."""
    pred = np.zeros((GRID_SIZE, GRID_SIZE, NUM_CLASSES))
    
    for y in range(GRID_SIZE):
        for x in range(GRID_SIZE):
            code = grid[y][x]
            if code == 5:
                pred[y, x] = [0, 0, 0, 0, 0, 1]
            elif code == 10:
                pred[y, x] = [1, 0, 0, 0, 0, 0]
            elif code in coeffs_by_type:
                feat = get_features(grid, y, x)
                pred[y, x] = coeffs_by_type[code] @ feat
            else:
                pred[y, x] = [1/6]*6
    
    # Floor and normalize
    pred = np.maximum(pred, floor)
    pred = pred / pred.sum(axis=-1, keepdims=True)
    
    # Compute score
    gt = np.array(gt)
    total_ent_kl = 0
    total_ent = 0
    for y in range(GRID_SIZE):
        for x in range(GRID_SIZE):
            p = gt[y, x]
            q = pred[y, x]
            ent = -sum(pi * np.log(pi) if pi > 0 else 0 for pi in p)
            if ent < 1e-10:
                continue
            kl = sum(pi * np.log(pi / qi) if pi > 0 else 0 for pi, qi in zip(p, q))
            total_ent_kl += ent * kl
            total_ent += ent
    
    weighted_kl = total_ent_kl / total_ent if total_ent > 0 else 0
    score = max(0, min(100, 100 * np.exp(-3 * weighted_kl)))
    return score, pred

# Cross-validation: leave-one-seed-out
print("=== Cross-Validation (Leave-One-Seed-Out) ===")
all_scores = []

for test_seed in range(5):
    train_seeds = [s for s in range(5) if s != test_seed]
    
    # Train
    data_by_type = load_training_data(train_seeds)
    coeffs = {}
    for code, (X, Y) in data_by_type.items():
        W = train_regression(X, Y)
        coeffs[code] = W.T  # shape: (6, num_features)
    
    # Test
    with open(f'data/r2_analysis_seed{test_seed}.json') as f:
        test_data = json.load(f)
    
    score, _ = predict_and_score(test_data['initial_grid'], test_data['ground_truth'], coeffs)
    all_scores.append(score)
    print(f"  Seed {test_seed}: score={score:.2f}")

print(f"\n  Average CV score: {np.mean(all_scores):.2f}")

# Train final model on all 5 seeds
print("\n=== Training Final Model (all 5 seeds) ===")
data_by_type = load_training_data(range(5))
final_coeffs = {}
for code, (X, Y) in data_by_type.items():
    W = train_regression(X, Y)
    final_coeffs[code] = W.T.tolist()
    print(f"  Terrain code {code}: {X.shape[0]} samples, {X.shape[1]} features")

# Save coefficients
output = {
    'coefficients': {str(k): v for k, v in final_coeffs.items()},
    'feature_names': ['intercept', 'settle_r1', 'settle_r2', 'settle_r3', 'settle_r4',
                      'ocean_r1', 'ocean_r2', 'forest_r1', 'forest_r2', 'mountain_r1',
                      'plains_r1', 'plains_r2', 'coastal', 'port_r1', 'port_r2',
                      'settle_ocean_int', 'settle_forest_int', 'settle_coastal_int'],
    'num_features': NUM_FEATURES,
    'floor': 0.005,
    'trained_on': 'round2_all_seeds',
}

with open('data/predictor_v2_coeffs.json', 'w') as f:
    json.dump(output, f, indent=2)
print("\nSaved to data/predictor_v2_coeffs.json")

# Also try different floor values
print("\n=== Floor Sensitivity (on CV) ===")
for floor in [0.001, 0.003, 0.005, 0.01, 0.02]:
    scores = []
    for test_seed in range(5):
        train_seeds = [s for s in range(5) if s != test_seed]
        data_by_type = load_training_data(train_seeds)
        coeffs = {}
        for code, (X, Y) in data_by_type.items():
            W = train_regression(X, Y)
            coeffs[code] = W.T
        with open(f'data/r2_analysis_seed{test_seed}.json') as f:
            test_data = json.load(f)
        score, _ = predict_and_score(test_data['initial_grid'], test_data['ground_truth'], coeffs, floor=floor)
        scores.append(score)
    print(f"  floor={floor:.3f}: avg={np.mean(scores):.2f}  min={min(scores):.2f}  max={max(scores):.2f}")
