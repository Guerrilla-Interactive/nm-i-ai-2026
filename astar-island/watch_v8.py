#!/usr/bin/env python3
"""
Watch for new rounds and auto-submit with V8 solver.
Polls every 30 seconds for active rounds.

V8 strategy:
1. Phase 1: Instant R2 (growth) submit — safe baseline (0 queries)
2. Phase 2: 3 regime probes — detect survival + cell change rate
3. Phase 3: Resubmit only if better model identified:
   - HEAVY_GROWTH: keep R2 (already best)
   - LIGHT_GROWTH: new growth model (+3-6 pts)
   - COLLAPSE: new collapse model (+20-40 pts)
"""
import os, sys, time, warnings
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(__file__))
from client import AstarClient
from solver_v8 import solve_round_with_client


def main():
    token = os.environ.get("ASTAR_TOKEN", "")
    if not token:
        print("Set ASTAR_TOKEN"); sys.exit(1)

    client = AstarClient(token)
    submitted_rounds = set()

    print("V8 Watching for new rounds... (Ctrl+C to stop)")

    while True:
        try:
            active = client.get_active_round()
            if active and active.id not in submitted_rounds:
                try:
                    success = solve_round_with_client(client, active)
                    if success:
                        submitted_rounds.add(active.id)
                except Exception as e:
                    print("\nSolver error for round %s: %s" % (
                        active.id[:8], e))
                    import traceback
                    traceback.print_exc()
            else:
                if active:
                    print(".", end="", flush=True)
                else:
                    print("x", end="", flush=True)

            time.sleep(30)

        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as e:
            print("\nWatch error: %s" % e)
            time.sleep(30)


if __name__ == '__main__':
    main()
