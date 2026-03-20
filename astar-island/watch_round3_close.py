#!/usr/bin/env python3
"""Watch for Round 3 to close, then fetch ground truth and retrain."""
import os, sys, time, json
sys.path.insert(0, os.path.dirname(__file__))
from client import AstarClient

ROUND3_ID = "f1dac9a9-5cf1-49a9-8f17-d6cb5d5ba5cb"

def main():
    token = os.environ.get("ASTAR_TOKEN", "")
    client = AstarClient(token)
    
    print("Watching for Round 3 to close...")
    while True:
        try:
            my_rounds = client.get_my_rounds()
            for r in my_rounds:
                if r.get('id') == ROUND3_ID:
                    status = r.get('status')
                    score = r.get('round_score')
                    print(f"  Round 3: status={status}, score={score}")
                    
                    if status in ('completed', 'scoring'):
                        print(f"\n=== Round 3 is {status}! ===")
                        if score:
                            print(f"Our score: {score}")
                            if r.get('seed_scores'):
                                for i, s in enumerate(r['seed_scores']):
                                    print(f"  Seed {i}: {s}")
                        
                        # Fetch ground truth
                        print("\nFetching ground truth...")
                        os.makedirs('data', exist_ok=True)
                        for si in range(5):
                            out = f'data/r3_analysis_seed{si}.json'
                            if os.path.exists(out):
                                print(f"  Seed {si}: exists")
                                continue
                            try:
                                data = client._request("GET", f"/analysis/{ROUND3_ID}/{si}")
                                with open(out, 'w') as f:
                                    json.dump(data, f)
                                print(f"  Seed {si}: saved ({os.path.getsize(out)} bytes)")
                            except Exception as e:
                                print(f"  Seed {si}: {e}")
                        
                        # Check for new active round
                        active = client.get_active_round()
                        if active:
                            print(f"\n=== New active round detected! ===")
                            print(f"Round {active.round_number}: {active.id[:8]}")
                            print(f"Seeds: {active.seeds_count}, closes: {active.closes_at}")
                        
                        return
                    break
        except Exception as e:
            print(f"  Error: {e}")
        
        time.sleep(30)

if __name__ == '__main__':
    main()
