#!/usr/bin/env python3
"""
Predictor v4: Split coastal/inland models + better port handling.
Key insight: ports ONLY occur on coastal cells (adjacent to ocean).
"""
import json, numpy as np, os
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
                return True
            if grid[ny][nx] == 10: return True
    return False

def get_features(grid, y, x):
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
    port1 = count_neighbors(grid, y, x, {2}, 1)
    return np.array([
        1, s1, s2, s3, s4, o1, o2, f1, f2, m1, p1, p2, port1,
        s1*o1, s1*f1, s1**2, o1**2, f1**2
    ])

NUM_FEATURES = 18

def train_split_models(seed_files):
    """Train separate models for coastal and inland cells, per terrain type."""
    # Collect training data: key = (terrain_code, is_coastal)
    X_data = defaultdict(list)
    Y_data = defaultdict(list)
    
    for f_path in seed_files:
        with open(f_path) as f:
            data = json.load(f)
        grid = data['initial_grid']
        gt = data['ground_truth']
        
        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                code = grid[y][x]
                if code in (10, 5): continue
                coastal = is_coastal(grid, y, x)
                feat = get_features(grid, y, x)
                key = (code, coastal)
                X_data[key].append(feat)
                Y_data[key].append(gt[y][x])
    
    models = {}
    for key in X_data:
        X = np.array(X_data[key])
        Y = np.array(Y_data[key])
        
        # For inland cells, zero out port class in target (should be 0 anyway)
        if not key[1]:  # inland
            port_mass = Y[:, 2].copy()
            Y[:, 2] = 0
            # Redistribute port mass proportionally to other classes
            other_sum = Y.sum(axis=1)
            mask = other_sum > 0
            Y[mask] = Y[mask] / other_sum[mask, np.newaxis]
        
        lam = 0.01
        W = np.linalg.solve(X.T @ X + lam * np.eye(X.shape[1]), X.T @ Y)
        models[f"{key[0]}_{key[1]}"] = W.T.tolist()
        print(f"  ({key[0]}, coastal={key[1]}): {X.shape[0]} samples")
    
    return models

def predict_grid(grid, models, floor=0.001):
    """Predict using split coastal/inland models."""
    pred = np.zeros((GRID_SIZE, GRID_SIZE, NUM_CLASSES))
    
    for y in range(GRID_SIZE):
        for x in range(GRID_SIZE):
            code = grid[y][x]
            if code == 5:
                pred[y, x] = [0, 0, 0, 0, 0, 1]
            elif code == 10:
                pred[y, x] = [1, 0, 0, 0, 0, 0]
            else:
                coastal = is_coastal(grid, y, x)
                key = f"{code}_{coastal}"
                if key in models:
                    feat = get_features(grid, y, x)
                    W = np.array(models[key])
                    pred[y, x] = W @ feat
                else:
                    # Fallback to the other coastal variant
                    alt_key = f"{code}_{not coastal}"
                    if alt_key in models:
                        feat = get_features(grid, y, x)
                        W = np.array(models[alt_key])
                        pred[y, x] = W @ feat
                    else:
                        pred[y, x] = [1/6]*6
                
                # HARD CONSTRAINT: inland cells cannot have ports
                if not coastal:
                    pred[y, x, 2] = 0
    
    pred = np.maximum(pred, floor)
    # Set port floor to near-zero for inland
    for y in range(GRID_SIZE):
        for x in range(GRID_SIZE):
            if grid[y][x] not in (10, 5) and not is_coastal(grid, y, x):
                pred[y, x, 2] = floor  # minimal floor
    
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

# Train and cross-validate
seed_files = [f'data/r2_analysis_seed{i}.json' for i in range(5)]

print("=== V4 Cross-Validation (coastal/inland split) ===")
cv_scores = []
for test_idx in range(5):
    train_files = [f for i, f in enumerate(seed_files) if i != test_idx]
    models = train_split_models(train_files)
    
    with open(seed_files[test_idx]) as f:
        test = json.load(f)
    
    pred = predict_grid(test['initial_grid'], models, floor=0.001)
    score = score_prediction(pred, test['ground_truth'])
    cv_scores.append(score)
    print(f"  Test seed {test_idx}: {score:.2f}")

print(f"\n  Average CV: {np.mean(cv_scores):.2f}")

# Train final model
print("\n=== Training Final Model ===")
models = train_split_models(seed_files)

# Save
output = {'models': models, 'num_features': NUM_FEATURES, 'floor': 0.001}
with open('data/predictor_v4_coeffs.json', 'w') as f:
    json.dump(output, f)
print("Saved to data/predictor_v4_coeffs.json")

# Validate on training data
print("\n=== Training Scores ===")
for i in range(5):
    with open(seed_files[i]) as f:
        data = json.load(f)
    pred = predict_grid(data['initial_grid'], models, floor=0.001)
    score = score_prediction(pred, data['ground_truth'])
    print(f"  Seed {i}: {score:.2f}")
