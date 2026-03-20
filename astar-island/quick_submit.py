#!/usr/bin/env python3
"""
Quick submit: fetch active round, predict with v3 model, submit all seeds.
Usage: python quick_submit.py
"""
import os, sys, json, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from client import AstarClient
from predictor_v3 import PredictorV3

def main():
    token = os.environ.get("ASTAR_TOKEN", "")
    if not token:
        print("Set ASTAR_TOKEN"); sys.exit(1)
    
    client = AstarClient(token)
    active = client.get_active_round()
    if not active:
        print("No active round!")
        rounds = client.get_rounds()
        for r in rounds:
            print(f"  Round {r.round_number}: {r.status}")
        sys.exit(1)
    
    print(f"Round {active.round_number}: {active.id[:8]}")
    print(f"  Seeds: {active.seeds_count}, closes: {active.closes_at}")
    
    # Load best model
    coeffs_file = 'data/predictor_v3_coeffs.json'
    predictor = PredictorV3(coeffs_file)
    print(f"  Model: {coeffs_file}")
    
    for seed_idx in range(active.seeds_count):
        initial_grid = active.initial_states[seed_idx].grid
        pred = predictor.predict_from_initial(initial_grid, floor=0.001)
        
        # Validate
        assert pred.shape == (40, 40, 6)
        assert (pred >= 0.0009).all()
        assert np.allclose(pred.sum(axis=-1), 1.0, atol=0.02)
        
        result = client.submit(active.id, seed_idx, pred.tolist())
        print(f"  Seed {seed_idx}: {result}")
    
    print(f"\nDone! {active.seeds_count} seeds submitted for Round {active.round_number}.")

if __name__ == '__main__':
    main()
