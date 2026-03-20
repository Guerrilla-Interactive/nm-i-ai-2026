#!/usr/bin/env python3
"""
Predictor v3: Regression model trained on Round 2 ground truth.
Can be used standalone or as a prior for simulation-based refinement.
"""
import numpy as np
import json
import os

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
    coastal = is_coastal(grid, y, x)
    port1 = count_neighbors(grid, y, x, {2}, 1)
    return np.array([
        1, s1, s2, s3, s4, o1, o2, f1, f2, m1, p1, p2, coastal, port1,
        s1*o1, s1*f1, s1*coastal, s1**2, s2**2, o1**2, f1**2
    ])

NUM_FEATURES = 21

# SIM_TO_CLASS mapping
SIM_TO_CLASS = {10: 0, 11: 0, 0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5}


class PredictorV3:
    def __init__(self, coeffs_file=None):
        self.coeffs = {}
        if coeffs_file and os.path.exists(coeffs_file):
            with open(coeffs_file) as f:
                data = json.load(f)
            for code_str, coeff_list in data['coefficients'].items():
                self.coeffs[int(code_str)] = np.array(coeff_list)
            self.floor = data.get('floor', 0.001)
        else:
            self.floor = 0.001

    def predict_from_initial(self, initial_grid, floor=None):
        """Predict 40x40x6 from initial grid alone (regression prior)."""
        if floor is None:
            floor = self.floor
        pred = np.zeros((GRID_SIZE, GRID_SIZE, NUM_CLASSES))

        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                code = initial_grid[y][x]
                if code == 5:
                    pred[y, x] = [0, 0, 0, 0, 0, 1]
                elif code == 10:
                    pred[y, x] = [1, 0, 0, 0, 0, 0]
                elif code in self.coeffs:
                    feat = get_features(initial_grid, y, x)
                    pred[y, x] = self.coeffs[code] @ feat
                else:
                    # Fallback: use terrain-type average from R2
                    pred[y, x] = self._fallback(code)

        pred = np.maximum(pred, floor)
        pred = pred / pred.sum(axis=-1, keepdims=True)
        return pred

    def _fallback(self, code):
        """Average ground truth by terrain type from R2."""
        defaults = {
            0: [0.7276, 0.1899, 0.0153, 0.0188, 0.0483, 0.0],
            11: [0.7276, 0.1899, 0.0153, 0.0188, 0.0483, 0.0],
            1: [0.3832, 0.4098, 0.0051, 0.0341, 0.1678, 0.0],
            2: [0.3841, 0.1214, 0.2877, 0.0345, 0.1723, 0.0],
            3: [0.3841, 0.1214, 0.2877, 0.0345, 0.1723, 0.0],
            4: [0.1095, 0.1965, 0.0127, 0.0186, 0.6627, 0.0],
        }
        return defaults.get(code, [1/6]*6)

    def update_with_simulations(self, pred, sim_results, initial_grid, 
                                  prior_strength=2.0):
        """
        Bayesian update: combine regression prior with Monte Carlo samples.
        
        pred: (40, 40, 6) regression prior
        sim_results: list of simulation query results, each with 'grid' and 'viewport'
        initial_grid: the initial terrain grid
        prior_strength: effective number of prior pseudo-observations (Dirichlet)
        """
        # Count observations per cell
        counts = np.zeros((GRID_SIZE, GRID_SIZE, NUM_CLASSES))
        n_obs = np.zeros((GRID_SIZE, GRID_SIZE))

        for sim in sim_results:
            vp = sim['viewport']
            vx, vy, vw, vh = vp['x'], vp['y'], vp['w'], vp['h']
            sim_grid = sim['grid']
            
            for row_idx, y in enumerate(range(vy, vy + vh)):
                for col_idx, x in enumerate(range(vx, vx + vw)):
                    if y < GRID_SIZE and x < GRID_SIZE:
                        cell_code = sim_grid[row_idx][col_idx]
                        class_idx = SIM_TO_CLASS.get(cell_code, 0)
                        counts[y, x, class_idx] += 1
                        n_obs[y, x] += 1

        # Bayesian update: Dirichlet posterior
        updated = pred.copy()
        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                if n_obs[y, x] > 0:
                    # Prior: alpha = prior_strength * pred
                    alpha_prior = prior_strength * pred[y, x]
                    # Posterior: alpha_prior + counts
                    alpha_post = alpha_prior + counts[y, x]
                    # Posterior mean
                    updated[y, x] = alpha_post / alpha_post.sum()

        # Floor and renormalize
        updated = np.maximum(updated, self.floor)
        updated = updated / updated.sum(axis=-1, keepdims=True)
        return updated


def train_from_ground_truth(seed_files):
    """Train regression coefficients from ground truth data files."""
    from collections import defaultdict
    
    X_by_type = defaultdict(list)
    Y_by_type = defaultdict(list)
    
    for f_path in seed_files:
        with open(f_path) as f:
            data = json.load(f)
        grid = data['initial_grid']
        gt = data['ground_truth']
        
        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                code = grid[y][x]
                if code in (10, 5): continue
                feat = get_features(grid, y, x)
                X_by_type[code].append(feat)
                Y_by_type[code].append(gt[y][x])
    
    coeffs = {}
    for code in X_by_type:
        X = np.array(X_by_type[code])
        Y = np.array(Y_by_type[code])
        lam = 0.01
        W = np.linalg.solve(X.T @ X + lam * np.eye(X.shape[1]), X.T @ Y)
        coeffs[code] = W.T.tolist()  # (6, num_features)
    
    return {
        'coefficients': {str(k): v for k, v in coeffs.items()},
        'num_features': NUM_FEATURES,
        'floor': 0.001,
    }


if __name__ == '__main__':
    # Train on R2 data
    seed_files = [f'data/r2_analysis_seed{i}.json' for i in range(5)]
    model_data = train_from_ground_truth(seed_files)
    
    out_file = 'data/predictor_v3_coeffs.json'
    with open(out_file, 'w') as f:
        json.dump(model_data, f)
    print(f"Saved model to {out_file}")
    
    # Validate
    predictor = PredictorV3(out_file)
    for i in range(5):
        with open(seed_files[i]) as f:
            data = json.load(f)
        pred = predictor.predict_from_initial(data['initial_grid'])
        gt = np.array(data['ground_truth'])
        
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
        
        wkl = total_ent_kl / total_ent if total_ent > 0 else 0
        score = max(0, min(100, 100 * np.exp(-3 * wkl)))
        print(f"  R2 Seed {i} (train): score={score:.2f}")
