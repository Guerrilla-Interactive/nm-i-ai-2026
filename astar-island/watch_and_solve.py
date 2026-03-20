#!/usr/bin/env python3
"""Watch for new round, detect regime, and submit predictions."""
import os, sys, time, json
sys.path.insert(0, os.path.dirname(__file__))
from client import AstarClient
from config import SIM_TO_CLASS, GRID_SIZE
from predictor_v3 import PredictorV3
import numpy as np

VP_TILES = [
    (0, 0), (13, 0), (25, 0),
    (0, 13), (13, 13), (25, 13),
    (0, 25), (13, 25), (25, 25),
]
VP_SIZE = 15

def find_best_viewport(initial_grid):
    best_count = 0
    best_pos = (13, 13)
    for vx, vy in VP_TILES:
        count = sum(1 for y in range(vy, min(vy+VP_SIZE, 40))
                    for x in range(vx, min(vx+VP_SIZE, 40))
                    if initial_grid[y][x] in (1, 2))
        if count > best_count:
            best_count = count
            best_pos = (vx, vy)
    return best_pos, best_count

def detect_regime(client, round_id, initial_states):
    total_init = 0
    total_final = 0
    
    for probe_seed in range(min(3, len(initial_states))):
        grid = initial_states[probe_seed].grid
        (vx, vy), n = find_best_viewport(grid)
        
        try:
            result = client.simulate(round_id, probe_seed, vx, vy, VP_SIZE, VP_SIZE)
            for y in range(vy, min(vy+VP_SIZE, 40)):
                for x in range(vx, min(vx+VP_SIZE, 40)):
                    if grid[y][x] in (1, 2):
                        total_init += 1
            for row in result.grid:
                for cell in row:
                    if cell in (1, 2):
                        total_final += 1
            print(f"  Probe seed {probe_seed}: viewport ({vx},{vy}), {n} init settlements, {len(result.settlements)} final")
        except Exception as e:
            print(f"  Probe error: {e}")
    
    if total_init == 0:
        return 0.5
    survival = total_final / total_init
    print(f"  Settlement survival: {total_final}/{total_init} = {survival:.2%}")
    return survival

def main():
    token = os.environ.get("ASTAR_TOKEN", "")
    if not token:
        print("Set ASTAR_TOKEN"); sys.exit(1)
    
    client = AstarClient(token)
    
    print("=== Watching for new round ===")
    while True:
        active = client.get_active_round()
        if active:
            break
        print(f"  {time.strftime('%H:%M:%S UTC', time.gmtime())} - no active round, waiting 30s...")
        time.sleep(30)
    
    round_id = active.id
    print(f"\n=== Round {active.round_number} detected! ===")
    print(f"  ID: {round_id[:8]}")
    print(f"  Seeds: {active.seeds_count}")
    print(f"  Closes: {active.closes_at}")
    
    # Detect regime
    print("\n--- Regime Detection ---")
    growth_score = detect_regime(client, round_id, active.initial_states)
    
    if growth_score > 0.05:
        model_file = 'data/model_r2.json'
        floor = 0.001
        regime = "GROWTH"
    else:
        model_file = 'data/model_r3.json'
        floor = 0.0001
        regime = "COLLAPSE"
    
    print(f"  Regime: {regime} (growth_score={growth_score:.3f})")
    predictor = PredictorV3(model_file)
    
    # Submit predictions
    print(f"\n--- Submitting Predictions ({regime} model, floor={floor}) ---")
    for seed_idx in range(active.seeds_count):
        initial_grid = active.initial_states[seed_idx].grid
        pred = predictor.predict_from_initial(initial_grid, floor=floor)
        
        assert pred.shape == (40, 40, 6)
        assert (pred >= floor * 0.9).all()
        assert np.allclose(pred.sum(axis=-1), 1.0, atol=0.02)
        
        result = client.submit(round_id, seed_idx, pred.tolist())
        print(f"  Seed {seed_idx}: {result}")
    
    print(f"\nDone! All {active.seeds_count} seeds submitted for Round {active.round_number}.")
    print(f"Regime: {regime}, growth_score: {growth_score:.3f}")

if __name__ == '__main__':
    main()
