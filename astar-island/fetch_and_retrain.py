#!/usr/bin/env python3
"""
Fetch ground truth for a completed round and retrain predictor.
Usage: python fetch_and_retrain.py [round_id] [round_number]
"""
import sys
import os
import json
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from client import AstarClient
from predictor_v3 import train_from_ground_truth

def main():
    token = os.environ.get("ASTAR_TOKEN", "")
    if not token:
        print("Set ASTAR_TOKEN"); sys.exit(1)
    
    client = AstarClient(token)
    
    # Get round info
    if len(sys.argv) > 1:
        round_id = sys.argv[1]
        round_num = int(sys.argv[2]) if len(sys.argv) > 2 else "?"
    else:
        # Auto-detect: find most recently completed round
        rounds = client.get_rounds()
        completed = [r for r in rounds if r.status == 'completed']
        if not completed:
            print("No completed rounds found")
            sys.exit(1)
        # Sort by round_number desc
        completed.sort(key=lambda r: r.round_number, reverse=True)
        round_id = completed[0].id
        round_num = completed[0].round_number
    
    print(f"=== Fetching Ground Truth for Round {round_num} ({round_id[:8]}) ===")
    
    # Fetch analysis (ground truth) for all 5 seeds
    os.makedirs('data', exist_ok=True)
    for seed_idx in range(5):
        out_file = f'data/r{round_num}_analysis_seed{seed_idx}.json'
        if os.path.exists(out_file):
            print(f"  Seed {seed_idx}: already exists, skipping")
            continue
        
        print(f"  Fetching seed {seed_idx}...")
        try:
            data = client._request("GET", f"/analysis/{round_id}/{seed_idx}")
            with open(out_file, 'w') as f:
                json.dump(data, f)
            print(f"  Seed {seed_idx}: saved ({os.path.getsize(out_file)} bytes)")
        except Exception as e:
            print(f"  Seed {seed_idx}: ERROR - {e}")
    
    # Check our score
    my_rounds = client.get_my_rounds()
    for r in my_rounds:
        if r.get('id') == round_id or str(r.get('round_number')) == str(round_num):
            print(f"\n  Our Round {round_num} score: {r.get('round_score')}")
            if r.get('seed_scores'):
                for i, s in enumerate(r['seed_scores']):
                    print(f"    Seed {i}: {s}")
            break
    
    # Retrain using all available ground truth
    print(f"\n=== Retraining Predictor ===")
    all_seed_files = []
    for rn in range(1, round_num + 1):
        for si in range(5):
            f_path = f'data/r{rn}_analysis_seed{si}.json'
            if os.path.exists(f_path):
                all_seed_files.append(f_path)
    
    if not all_seed_files:
        print("No ground truth files found!")
        sys.exit(1)
    
    print(f"  Training on {len(all_seed_files)} seed files")
    for f in all_seed_files:
        print(f"    {f}")
    
    model_data = train_from_ground_truth(all_seed_files)
    
    out_file = 'data/predictor_v3_coeffs.json'
    with open(out_file, 'w') as f:
        json.dump(model_data, f)
    print(f"  Saved retrained model to {out_file}")
    
    # Cross-validate on latest round
    print(f"\n=== Validation on Round {round_num} ===")
    from predictor_v3 import PredictorV3
    predictor = PredictorV3(out_file)
    
    for si in range(5):
        f_path = f'data/r{round_num}_analysis_seed{si}.json'
        if not os.path.exists(f_path): continue
        
        with open(f_path) as f:
            data = json.load(f)
        
        pred = predictor.predict_from_initial(data['initial_grid'])
        gt = np.array(data['ground_truth'])
        
        total_ent_kl = 0
        total_ent = 0
        for y in range(40):
            for x in range(40):
                p = gt[y, x]
                q = pred[y, x]
                ent = -sum(pi * np.log(pi) if pi > 0 else 0 for pi in p)
                if ent < 1e-10: continue
                kl = sum(pi * np.log(pi / qi) if pi > 0 else 0 for pi, qi in zip(p, q))
                total_ent_kl += ent * kl
                total_ent += ent
        
        wkl = total_ent_kl / total_ent if total_ent > 0 else 0
        score = max(0, min(100, 100 * np.exp(-3 * wkl)))
        print(f"  Seed {si}: score={score:.2f}")

    print("\nDone! Predictor retrained and ready for next round.")


if __name__ == '__main__':
    main()
