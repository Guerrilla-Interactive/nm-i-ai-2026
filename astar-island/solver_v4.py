#!/usr/bin/env python3
"""
Round 4 Solver: Regression prior + Monte Carlo simulation queries + Bayesian update.

Strategy:
- Use regression model from R2+R3 ground truth as prior
- Allocate 50 simulation queries across 5 seeds (10 per seed)
- Cover each seed's map with viewports to get simulation samples
- Bayesian update: combine prior with observed counts
- Submit improved predictions
"""
import sys
import os
import time
import json
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from client import AstarClient
from config import SIM_TO_CLASS, GRID_SIZE, NUM_CLASSES
from predictor_v3 import PredictorV3

# Viewport tiling strategy for 40x40 map with 15x15 viewports
# 3x3 grid of viewports with overlap:
VIEWPORT_TILES = [
    (0, 0), (13, 0), (25, 0),
    (0, 13), (13, 13), (25, 13),
    (0, 25), (13, 25), (25, 25),
]
VP_SIZE = 15

def get_query_plan(n_queries, n_seeds=5):
    """
    Allocate queries across seeds and viewports.
    
    With 50 queries / 5 seeds = 10 per seed:
    - 9 viewports to tile the map = 9 queries for 1 full coverage
    - 1 extra query for highest-entropy region
    """
    plan = []
    queries_per_seed = n_queries // n_seeds
    extra = n_queries % n_seeds
    
    for seed_idx in range(n_seeds):
        q = queries_per_seed + (1 if seed_idx < extra else 0)
        
        # First pass: cover the map
        for i, (vx, vy) in enumerate(VIEWPORT_TILES):
            if i >= q:
                break
            plan.append((seed_idx, vx, vy))
        
        # Extra queries: re-query center (usually most dynamic)
        remaining = q - min(len(VIEWPORT_TILES), q)
        center_tiles = [(13, 13), (0, 13), (13, 0), (25, 13), (13, 25)]
        for i in range(remaining):
            vx, vy = center_tiles[i % len(center_tiles)]
            plan.append((seed_idx, vx, vy))
    
    return plan


def run_simulations(client, round_id, query_plan):
    """Execute simulation queries according to plan."""
    # Group results by seed
    results_by_seed = {i: [] for i in range(5)}
    
    for i, (seed_idx, vx, vy) in enumerate(query_plan):
        print(f"  Query {i+1}/{len(query_plan)}: seed={seed_idx} viewport=({vx},{vy})")
        try:
            result = client.simulate(round_id, seed_idx, vx, vy, VP_SIZE, VP_SIZE)
            results_by_seed[seed_idx].append({
                'grid': result.grid,
                'viewport': {'x': vx, 'y': vy, 'w': VP_SIZE, 'h': VP_SIZE},
                'settlements': [{'x': s.x, 'y': s.y, 'population': s.population,
                                'food': s.food, 'wealth': s.wealth, 'defense': s.defense,
                                'has_port': s.has_port, 'alive': s.alive}
                               for s in result.settlements],
            })
        except Exception as e:
            print(f"    ERROR: {e}")
            continue
    
    return results_by_seed


def main():
    token = os.environ.get("ASTAR_TOKEN", "")
    if not token:
        print("Set ASTAR_TOKEN env var")
        sys.exit(1)
    
    client = AstarClient(token)
    
    # Find active round
    active = client.get_active_round()
    if not active:
        print("No active round found. Checking for upcoming...")
        rounds = client.get_rounds()
        for r in rounds:
            print(f"  Round {r.round_number}: {r.status}")
        sys.exit(0)
    
    round_id = active.id
    print(f"Active Round {active.round_number}: {round_id[:8]}")
    print(f"  Status: {active.status}")
    print(f"  Seeds: {active.seeds_count}")
    print(f"  Closes at: {active.closes_at}")
    
    # Load predictor
    coeffs_file = 'data/predictor_v3_coeffs.json'
    if os.path.exists(coeffs_file):
        predictor = PredictorV3(coeffs_file)
        print(f"  Loaded predictor from {coeffs_file}")
    else:
        print(f"  WARNING: No coefficients file found at {coeffs_file}")
        predictor = PredictorV3()
    
    # Check budget
    budget = client.get_budget()
    queries_remaining = budget['queries_max'] - budget['queries_used']
    print(f"  Budget: {budget['queries_used']}/{budget['queries_max']} used, {queries_remaining} remaining")
    
    if queries_remaining <= 0:
        print("  No queries remaining! Using regression-only predictions.")
        queries_remaining = 0
    
    # Step 1: Generate regression prior for all seeds
    print("\n--- Step 1: Regression Prior ---")
    priors = {}
    for seed_idx in range(active.seeds_count):
        initial_grid = active.initial_states[seed_idx].grid
        prior = predictor.predict_from_initial(initial_grid)
        priors[seed_idx] = prior
        
        # Count terrain types
        counts = {}
        for row in initial_grid:
            for cell in row:
                counts[cell] = counts.get(cell, 0) + 1
        print(f"  Seed {seed_idx}: terrain={dict(sorted(counts.items()))}")
    
    # Step 2: Run simulations
    if queries_remaining > 0:
        print(f"\n--- Step 2: Simulation Queries ({queries_remaining} available) ---")
        query_plan = get_query_plan(queries_remaining, active.seeds_count)
        print(f"  Plan: {len(query_plan)} queries")
        
        sim_results = run_simulations(client, round_id, query_plan)
        
        # Save simulation data
        sim_save = {str(k): v for k, v in sim_results.items()}
        with open(f'data/round{active.round_number}_simulations.json', 'w') as f:
            json.dump(sim_save, f)
        print(f"  Saved simulation data")
        
        # Step 3: Bayesian update
        print("\n--- Step 3: Bayesian Update ---")
        for seed_idx in range(active.seeds_count):
            n_sims = len(sim_results[seed_idx])
            if n_sims > 0:
                initial_grid = active.initial_states[seed_idx].grid
                updated = predictor.update_with_simulations(
                    priors[seed_idx], sim_results[seed_idx], initial_grid,
                    prior_strength=2.0  # Regression prior worth ~2 observations
                )
                priors[seed_idx] = updated
                print(f"  Seed {seed_idx}: updated with {n_sims} simulations")
            else:
                print(f"  Seed {seed_idx}: no simulations, using regression only")
    else:
        print("\n--- Step 2: Skipping simulations (no budget) ---")
    
    # Step 4: Submit predictions
    print(f"\n--- Step 4: Submit Predictions ---")
    for seed_idx in range(active.seeds_count):
        pred = priors[seed_idx]
        
        # Validate
        assert pred.shape == (GRID_SIZE, GRID_SIZE, NUM_CLASSES)
        assert (pred >= 0.0009).all(), f"Min: {pred.min()}"
        sums = pred.sum(axis=-1)
        assert np.allclose(sums, 1.0, atol=0.02), f"Sums: {sums.min()}-{sums.max()}"
        
        result = client.submit(round_id, seed_idx, pred.tolist())
        print(f"  Seed {seed_idx}: submitted -> {result}")
    
    print(f"\nDone! All {active.seeds_count} seeds submitted.")


if __name__ == '__main__':
    main()
