#!/usr/bin/env python3
"""
Mini simulation: approximate the Astar Island dynamics.
Run thousands of times to get probability distributions.

Simplified model of 50-year Norse civilization:
1. Growth: settlements produce food from forests/plains, grow pop
2. Expansion: prosperous settlements found new ones on adjacent land
3. Ports: coastal settlements can develop ports
4. Conflict: settlements raid neighbors
5. Collapse: weak settlements → ruins
6. Reclamation: ruins → forest (natural) or settlement (nearby settlers)
"""
import numpy as np
from collections import defaultdict

GRID_SIZE = 40
NUM_CLASSES = 6
YEARS = 50

# Terrain codes
OCEAN = 10
PLAINS = 11
EMPTY = 0
SETTLEMENT = 1
PORT = 2
RUIN = 3
FOREST = 4
MOUNTAIN = 5

# Default parameters (to be calibrated per round)
DEFAULT_PARAMS = {
    'expansion_rate': 0.08,      # prob of founding new settlement per neighbor
    'port_development': 0.15,    # prob of coastal settlement becoming port
    'collapse_rate': 0.04,       # base prob of settlement collapse per year
    'forest_reclaim_rate': 0.03, # prob of ruin reverting to forest
    'settle_reclaim_rate': 0.05, # prob of ruin being reclaimed by nearby settlement
    'food_bonus_forest': 0.3,    # how much forest neighbors reduce collapse
    'food_bonus_port': 0.2,      # how much port status reduces collapse
    'raid_factor': 0.01,         # additional collapse risk per nearby enemy settlement
}


def count_adj(grid, y, x, codes):
    """Count adjacent cells (radius 1) matching codes."""
    count = 0
    for dy in [-1, 0, 1]:
        for dx in [-1, 0, 1]:
            if dy == 0 and dx == 0: continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < GRID_SIZE and 0 <= nx < GRID_SIZE:
                if grid[ny][nx] in codes: count += 1
    return count

def is_coastal(grid, y, x):
    return count_adj(grid, y, x, {OCEAN}) > 0

def simulate_once(initial_grid, params=None, rng=None):
    """Run one 50-year simulation, return final grid."""
    if params is None:
        params = DEFAULT_PARAMS
    if rng is None:
        rng = np.random.default_rng()
    
    grid = [row[:] for row in initial_grid]  # deep copy
    
    for year in range(YEARS):
        new_grid = [row[:] for row in grid]
        
        # Shuffle cell processing order for fairness
        cells = [(y, x) for y in range(GRID_SIZE) for x in range(GRID_SIZE)]
        rng.shuffle(cells)
        
        for y, x in cells:
            cell = grid[y][x]
            
            if cell in (OCEAN, MOUNTAIN):
                continue  # Static
            
            if cell in (SETTLEMENT, PORT):
                # Check for collapse
                forest_adj = count_adj(grid, y, x, {FOREST})
                settle_adj = count_adj(grid, y, x, {SETTLEMENT, PORT})
                ruin_adj = count_adj(grid, y, x, {RUIN})
                
                collapse_prob = params['collapse_rate']
                collapse_prob -= forest_adj * params['food_bonus_forest'] * 0.1
                if cell == PORT:
                    collapse_prob -= params['food_bonus_port'] * 0.5
                collapse_prob += settle_adj * params['raid_factor']
                collapse_prob = max(0, min(0.5, collapse_prob))
                
                if rng.random() < collapse_prob:
                    new_grid[y][x] = RUIN
                    continue
                
                # Check for port development (non-port settlement near ocean)
                if cell == SETTLEMENT and is_coastal(grid, y, x):
                    if rng.random() < params['port_development'] * 0.05:
                        new_grid[y][x] = PORT
                
                # Expansion: try to settle adjacent plains/empty
                if rng.random() < params['expansion_rate']:
                    # Find adjacent settleable cells
                    candidates = []
                    for dy in [-1, 0, 1]:
                        for dx in [-1, 0, 1]:
                            if dy == 0 and dx == 0: continue
                            ny, nx = y + dy, x + dx
                            if 0 <= ny < GRID_SIZE and 0 <= nx < GRID_SIZE:
                                if new_grid[ny][nx] in (PLAINS, EMPTY, FOREST, RUIN):
                                    candidates.append((ny, nx))
                    if candidates:
                        ny, nx = candidates[rng.integers(len(candidates))]
                        if is_coastal(grid, ny, nx) and rng.random() < params['port_development']:
                            new_grid[ny][nx] = PORT
                        else:
                            new_grid[ny][nx] = SETTLEMENT
            
            elif cell == RUIN:
                settle_adj = count_adj(grid, y, x, {SETTLEMENT, PORT})
                
                if settle_adj > 0 and rng.random() < params['settle_reclaim_rate'] * settle_adj:
                    if is_coastal(grid, y, x) and rng.random() < params['port_development']:
                        new_grid[y][x] = PORT
                    else:
                        new_grid[y][x] = SETTLEMENT
                elif rng.random() < params['forest_reclaim_rate']:
                    new_grid[y][x] = FOREST
            
            elif cell in (PLAINS, EMPTY):
                settle_adj = count_adj(grid, y, x, {SETTLEMENT, PORT})
                if settle_adj > 0 and rng.random() < params['expansion_rate'] * settle_adj * 0.3:
                    if is_coastal(grid, y, x) and rng.random() < params['port_development']:
                        new_grid[y][x] = PORT
                    else:
                        new_grid[y][x] = SETTLEMENT
            
            elif cell == FOREST:
                settle_adj = count_adj(grid, y, x, {SETTLEMENT, PORT})
                if settle_adj > 0 and rng.random() < params['expansion_rate'] * settle_adj * 0.15:
                    if is_coastal(grid, y, x) and rng.random() < params['port_development']:
                        new_grid[y][x] = PORT
                    else:
                        new_grid[y][x] = SETTLEMENT
        
        grid = new_grid
    
    return grid


def grid_to_classes(grid):
    """Convert terrain codes to class indices."""
    SIM_TO_CLASS = {10: 0, 11: 0, 0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5}
    result = np.zeros((GRID_SIZE, GRID_SIZE), dtype=int)
    for y in range(GRID_SIZE):
        for x in range(GRID_SIZE):
            result[y, x] = SIM_TO_CLASS.get(grid[y][x], 0)
    return result


def monte_carlo_predict(initial_grid, n_sims=200, params=None):
    """Run n_sims simulations and compute probability distribution."""
    counts = np.zeros((GRID_SIZE, GRID_SIZE, NUM_CLASSES))
    
    for i in range(n_sims):
        rng = np.random.default_rng(seed=i*1000 + 42)
        final = simulate_once(initial_grid, params=params, rng=rng)
        classes = grid_to_classes(final)
        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                counts[y, x, classes[y, x]] += 1
    
    pred = counts / n_sims
    return pred


def score_prediction(pred, gt_data, floor=0.001):
    gt = np.array(gt_data)
    pred = np.maximum(pred, floor)
    pred = pred / pred.sum(axis=-1, keepdims=True)
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


if __name__ == '__main__':
    import json
    
    # Test on R2 seed 0
    with open('data/r2_analysis_seed0.json') as f:
        data = json.load(f)
    
    print("Running mini simulation on R2 seed 0...")
    print("(200 simulations, default params)")
    
    pred = monte_carlo_predict(data['initial_grid'], n_sims=200)
    score = score_prediction(pred, data['ground_truth'])
    print(f"Score: {score:.2f}")
    
    # Compare per-terrain-type distributions
    gt = np.array(data['ground_truth'])
    grid = data['initial_grid']
    
    for code in [11, 4, 1]:
        gt_cells = []
        pred_cells = []
        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                if grid[y][x] == code:
                    gt_cells.append(gt[y][x])
                    pred_cells.append(pred[y][x])
        gt_avg = np.mean(gt_cells, axis=0)
        pred_avg = np.mean(pred_cells, axis=0)
        diff = pred_avg - gt_avg
        print(f"\n  Code {code}: {len(gt_cells)} cells")
        print(f"    GT avg:   [{' '.join(f'{v:.4f}' for v in gt_avg)}]")
        print(f"    Pred avg: [{' '.join(f'{v:.4f}' for v in pred_avg)}]")
        print(f"    Diff:     [{' '.join(f'{v:+.4f}' for v in diff)}]")
