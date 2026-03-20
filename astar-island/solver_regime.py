#!/usr/bin/env python3
"""
Regime-detecting solver for Astar Island.

Strategy:
1. Use 1-3 simulation queries to detect the round's "regime"
   (growth vs collapse) by observing settlement survival rate
2. Blend R2 (growth) and R3 (collapse) models based on detected regime
3. Submit predictions

This approach works because:
- R2 model scores 93 on growth worlds, 35 on collapse worlds
- R3 model scores 89 on collapse worlds, 5 on growth worlds
- Detecting the regime correctly lets us choose the right model
"""
import os, sys, json, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from client import AstarClient
from config import SIM_TO_CLASS, GRID_SIZE, NUM_CLASSES
from predictor_v3 import PredictorV3

# Viewport tiles covering the full 40x40 map
VP_TILES = [
    (0, 0), (13, 0), (25, 0),
    (0, 13), (13, 13), (25, 13),
    (0, 25), (13, 25), (25, 25),
]
VP_SIZE = 15


def find_settlement_viewport(initial_grid):
    """Find viewport position with most initial settlements."""
    best_count = 0
    best_pos = (0, 0)
    
    for vx, vy in VP_TILES:
        count = 0
        for y in range(vy, min(vy + VP_SIZE, GRID_SIZE)):
            for x in range(vx, min(vx + VP_SIZE, GRID_SIZE)):
                if initial_grid[y][x] in (1, 2):  # Settlement or Port
                    count += 1
        if count > best_count:
            best_count = count
            best_pos = (vx, vy)
    
    return best_pos, best_count


def detect_regime(client, round_id, initial_states, n_probes=3):
    """
    Use simulation queries to detect round regime.
    Returns a 'growth_score' from 0 (total collapse) to 1 (full growth).
    """
    total_initial_settlements = 0
    total_final_settlements = 0
    total_initial_forest = 0
    total_final_forest = 0
    
    for probe in range(n_probes):
        # Use different seeds for probes to get diverse views
        seed_idx = probe % 5
        initial_grid = initial_states[seed_idx].grid
        
        # Find viewport with most settlements
        (vx, vy), n_settle = find_settlement_viewport(initial_grid)
        
        print(f"  Probe {probe}: seed={seed_idx} viewport=({vx},{vy}) initial_settlements={n_settle}")
        
        try:
            result = client.simulate(round_id, seed_idx, vx, vy, VP_SIZE, VP_SIZE)
            
            # Count initial settlements in viewport
            for y in range(vy, min(vy + VP_SIZE, GRID_SIZE)):
                for x in range(vx, min(vx + VP_SIZE, GRID_SIZE)):
                    if initial_grid[y][x] in (1, 2):
                        total_initial_settlements += 1
                    if initial_grid[y][x] == 4:
                        total_initial_forest += 1
            
            # Count final settlements in simulation result
            for row_idx, y in enumerate(range(vy, min(vy + VP_SIZE, GRID_SIZE))):
                for col_idx, x in enumerate(range(vx, min(vx + VP_SIZE, GRID_SIZE))):
                    if row_idx < len(result.grid) and col_idx < len(result.grid[row_idx]):
                        cell = result.grid[row_idx][col_idx]
                        if cell in (1, 2):
                            total_final_settlements += 1
                        if cell == 4:
                            total_final_forest += 1
            
            print(f"    Observed: {len(result.settlements)} settlements in viewport")
            
        except Exception as e:
            print(f"    ERROR: {e}")
    
    # Compute growth score
    if total_initial_settlements == 0:
        growth_score = 0.5  # Can't tell
    else:
        survival_rate = total_final_settlements / total_initial_settlements
        # R2 (growth): settlements expand → survival >> 1.0
        # R3 (collapse): settlements die → survival << 1.0
        growth_score = min(1.0, survival_rate)
    
    # Forest stability also tells us about regime
    if total_initial_forest > 0:
        forest_retain = total_final_forest / total_initial_forest
    else:
        forest_retain = 1.0
    
    print(f"\n  Settlement survival: {total_final_settlements}/{total_initial_settlements} = {growth_score:.2f}")
    print(f"  Forest retention: {total_final_forest}/{total_initial_forest} = {forest_retain:.2f}")
    
    return growth_score


def main():
    token = os.environ.get("ASTAR_TOKEN", "")
    if not token:
        print("Set ASTAR_TOKEN"); sys.exit(1)
    
    client = AstarClient(token)
    active = client.get_active_round()
    if not active:
        print("No active round!")
        for r in client.get_rounds():
            print(f"  Round {r.round_number}: {r.status}")
        sys.exit(0)
    
    round_id = active.id
    print(f"=== Round {active.round_number}: {round_id[:8]} ===")
    print(f"  Seeds: {active.seeds_count}, closes: {active.closes_at}")
    
    budget = client.get_budget()
    queries_left = budget['queries_max'] - budget['queries_used']
    print(f"  Budget: {budget['queries_used']}/{budget['queries_max']} used, {queries_left} remaining")
    
    # Step 1: Detect regime
    n_probes = min(3, queries_left)
    if n_probes > 0:
        print(f"\n--- Step 1: Regime Detection ({n_probes} probes) ---")
        growth_score = detect_regime(client, round_id, active.initial_states, n_probes=n_probes)
    else:
        print("\n--- Step 1: No budget for probes, using combined model ---")
        growth_score = 0.5
    
    # Step 2: Load appropriate model(s)
    print(f"\n--- Step 2: Select Model (growth_score={growth_score:.2f}) ---")
    
    r2_model_file = 'data/model_r2.json'
    r3_model_file = 'data/model_r3.json'
    combined_file = 'data/model_combined.json'
    
    # Binary regime selection (blending hurts both sides)
    if growth_score > 0.05:
        print("  Regime: GROWTH → using R2 model (floor=0.001)")
        predictor = PredictorV3(r2_model_file)
        floor = 0.001
    else:
        print("  Regime: COLLAPSE → using R3 model (floor=0.0001)")
        predictor = PredictorV3(r3_model_file)
        floor = 0.0001
    
    # Step 3: Run remaining simulations for refinement
    queries_left = budget['queries_max'] - budget['queries_used'] - n_probes
    print(f"\n--- Step 3: Additional Queries ({queries_left} remaining) ---")
    
    # Use remaining queries to get more regime evidence and refine
    sim_results = {i: [] for i in range(5)}
    if queries_left > 0:
        queries_per_seed = queries_left // 5
        for seed_idx in range(5):
            for q in range(queries_per_seed):
                vx, vy = VP_TILES[q % len(VP_TILES)]
                try:
                    result = client.simulate(round_id, seed_idx, vx, vy, VP_SIZE, VP_SIZE)
                    sim_results[seed_idx].append({
                        'grid': result.grid,
                        'viewport': {'x': vx, 'y': vy, 'w': VP_SIZE, 'h': VP_SIZE},
                    })
                except Exception as e:
                    print(f"    Seed {seed_idx} query {q}: {e}")
                    break
        print(f"  Collected {sum(len(v) for v in sim_results.values())} additional simulations")
    
    # Step 4: Generate and submit predictions
    print(f"\n--- Step 4: Submit Predictions ---")
    for seed_idx in range(active.seeds_count):
        initial_grid = active.initial_states[seed_idx].grid
        
        pred = predictor.predict_from_initial(initial_grid, floor=floor)
        
        # Optional: Bayesian update with simulation data
        if sim_results[seed_idx]:
            pred = bayesian_update_grouped(pred, sim_results[seed_idx], initial_grid)
        
        # Validate and submit
        assert pred.shape == (GRID_SIZE, GRID_SIZE, NUM_CLASSES)
        assert (pred >= 0.0009).all(), f"Min: {pred.min()}"
        assert np.allclose(pred.sum(axis=-1), 1.0, atol=0.02)
        
        result = client.submit(round_id, seed_idx, pred.tolist())
        print(f"  Seed {seed_idx}: {result}")
    
    print(f"\nDone! All {active.seeds_count} seeds submitted.")


def bayesian_update_grouped(pred, sim_results, initial_grid, prior_strength=5.0):
    """Light Bayesian update from simulation observations."""
    counts = np.zeros((GRID_SIZE, GRID_SIZE, NUM_CLASSES))
    n_obs = np.zeros((GRID_SIZE, GRID_SIZE))
    
    for sim in sim_results:
        vp = sim['viewport']
        for row_idx, y in enumerate(range(vp['y'], vp['y'] + vp['h'])):
            for col_idx, x in enumerate(range(vp['x'], vp['x'] + vp['w'])):
                if y < GRID_SIZE and x < GRID_SIZE and row_idx < len(sim['grid']):
                    cell = sim['grid'][row_idx][col_idx]
                    class_idx = SIM_TO_CLASS.get(cell, 0)
                    counts[y, x, class_idx] += 1
                    n_obs[y, x] += 1
    
    updated = pred.copy()
    for y in range(GRID_SIZE):
        for x in range(GRID_SIZE):
            if n_obs[y, x] > 0:
                alpha = prior_strength * pred[y, x] + counts[y, x]
                updated[y, x] = alpha / alpha.sum()
    
    updated = np.maximum(updated, 0.001)
    updated = updated / updated.sum(axis=-1, keepdims=True)
    return updated


if __name__ == '__main__':
    main()
