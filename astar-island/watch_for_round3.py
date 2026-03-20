#!/usr/bin/env python3
"""Poll for Round 3 and auto-run solver when it starts."""
import time
import subprocess
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from client import AstarClient
from config import TOKEN


def main():
    if not TOKEN:
        print("ERROR: No token set. Export ASTAR_TOKEN or write ~/.astar-token")
        sys.exit(1)

    client = AstarClient(TOKEN)
    print("Watching for new active round...")

    seen_rounds = set()
    # Get currently known rounds
    for r in client.get_rounds():
        seen_rounds.add(r.id)

    while True:
        try:
            rounds = client.get_rounds()
            for r in rounds:
                if r.status == "active" and r.id not in seen_rounds:
                    print(f"\nNEW ROUND DETECTED: #{r.round_number} ({r.id})")
                    print(f"   Closes at: {r.closes_at}")
                    print(f"   Weight: {r.round_weight}")
                    print(f"\nRunning solver...")

                    # Run solver
                    solver_path = os.path.join(os.path.dirname(__file__), "solver.py")
                    env = os.environ.copy()
                    env["ASTAR_TOKEN"] = TOKEN
                    result = subprocess.run(
                        [sys.executable, solver_path, "--round-id", r.id],
                        env=env,
                        cwd=os.path.dirname(__file__),
                    )

                    if result.returncode == 0:
                        print("Solver completed successfully!")
                    else:
                        print(f"Solver exited with code {result.returncode}")

                    seen_rounds.add(r.id)
                    print("\nContinuing to watch for more rounds...")

                elif r.id not in seen_rounds:
                    seen_rounds.add(r.id)

            time.sleep(30)  # Poll every 30 seconds
            print(".", end="", flush=True)

        except KeyboardInterrupt:
            print("\nStopped watching.")
            break
        except Exception as e:
            print(f"\nError: {e}")
            time.sleep(10)


if __name__ == "__main__":
    main()
