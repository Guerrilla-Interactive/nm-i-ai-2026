#!/usr/bin/env python3
"""
Astar Island Solver — NM i AI 2026
Full pipeline: fetch round → observe via tiling → predict → submit

Usage (from the repo root, i.e. parent of astar-island/):
    python -c "from importlib import import_module; import_module('astar-island.solver')"

Or more practically, just run from inside the directory:
    cd astar-island && python solver.py

    python solver.py                           # Auto-detect active round
    python solver.py --round-id UUID           # Specific round
    python solver.py --token TOKEN             # Override token
    python solver.py --dry-run                 # Test without API calls
    python solver.py --initial-only            # Submit using only initial states (no queries)
"""
import argparse
import importlib
import importlib.util
import sys
import os
import time
import json
import random

import numpy as np

# Bootstrap: make sibling modules importable regardless of how this script
# is invoked.  The package directory is "astar-island" (hyphen), which is
# not a valid Python identifier — so we register it under an alias.
_this_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_this_dir)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)
# If running as a plain script (not via -m), __package__ is None and
# relative imports inside sibling modules (from . import config) will fail.
# Fix: import the package directory by path so Python knows about it.
_pkg_name = os.path.basename(_this_dir)
if _pkg_name not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        _pkg_name,
        os.path.join(_this_dir, "__init__.py"),
        submodule_search_locations=[_this_dir],
    )
    _pkg_mod = importlib.util.module_from_spec(_spec)
    sys.modules[_pkg_name] = _pkg_mod
    _spec.loader.exec_module(_pkg_mod)

# Now import sibling modules via the registered package name
config = importlib.import_module(f"{_pkg_name}.config")
client_mod = importlib.import_module(f"{_pkg_name}.client")
strategy_mod = importlib.import_module(f"{_pkg_name}.strategy")
predictor_mod = importlib.import_module(f"{_pkg_name}.predictor")

AstarClient = client_mod.AstarClient
get_query_plan = strategy_mod.get_query_plan
Predictor = predictor_mod.Predictor
SIM_TO_CLASS = config.SIM_TO_CLASS
GRID_SIZE = config.GRID_SIZE
NUM_CLASSES = config.NUM_CLASSES
NUM_SEEDS = config.NUM_SEEDS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Astar Island Solver — NM i AI 2026")
    parser.add_argument("--round-id", help="Specific round UUID (default: auto-detect active)")
    parser.add_argument("--token", help="Override auth token")
    parser.add_argument("--dry-run", action="store_true", help="Test without API calls")
    parser.add_argument("--initial-only", action="store_true",
                        help="Submit using only initial states (no queries)")
    parser.add_argument("--seeds", help="Comma-separated seed indices (default: 0,1,2,3,4)")
    parser.add_argument("--check-scores", action="store_true",
                        help="Check scores for a submitted round")
    return parser.parse_args()


def build_observation_map(
    observations: list[dict],
    grid_size: int = 40,
) -> tuple[np.ndarray, np.ndarray, list[list[list[int]]]]:
    """Merge all viewport results into a full grid.

    Args:
        observations: List of dicts with keys 'x', 'y', 'grid' where grid is
            the 2D array of sim terrain codes from the viewport.
        grid_size: Size of the full map (40).

    Returns:
        observed_terrain: (grid_size, grid_size) int array, -1 = unobserved,
            otherwise the submission class index (last observation).
        observation_count: (grid_size, grid_size) int array, how many times
            each cell was observed.
        all_observations: per-cell list of all observed class indices,
            for multi-sample averaging in the predictor.
    """
    observed_terrain = np.full((grid_size, grid_size), -1, dtype=int)
    observation_count = np.zeros((grid_size, grid_size), dtype=int)
    all_observations = [[[] for _ in range(grid_size)] for _ in range(grid_size)]

    for obs in observations:
        vx, vy = obs["x"], obs["y"]
        grid = obs["grid"]
        h = len(grid)
        w = len(grid[0]) if h > 0 else 0
        for row in range(h):
            for col in range(w):
                map_y = vy + row
                map_x = vx + col
                if 0 <= map_y < grid_size and 0 <= map_x < grid_size:
                    sim_code = grid[row][col]
                    cls = SIM_TO_CLASS.get(sim_code, 0)
                    observed_terrain[map_y][map_x] = cls
                    observation_count[map_y][map_x] += 1
                    all_observations[map_y][map_x].append(cls)

    return observed_terrain, observation_count, all_observations


def solve_seed(
    client,
    round_id: str,
    seed_index: int,
    initial_state_grid: list[list[int]],
    dry_run: bool = False,
) -> dict:
    """Run the full pipeline for a single seed: query → observe → predict → submit."""
    result = {
        "seed_index": seed_index,
        "queries_executed": 0,
        "submitted": False,
        "error": None,
    }

    queries = get_query_plan(seed_index)
    observations: list[dict] = []
    settlement_data: list[dict] = []  # settlement stats from each query
    queries_used = 0
    queries_max = config.QUERIES_PER_ROUND

    for i, q in enumerate(queries):
        x, y, w, h = q["x"], q["y"], q["w"], q["h"]
        label = q.get("label", f"tile-{i}")

        if dry_run:
            grid = _random_grid(h, w)
            print(f"  Query {i+1}/{len(queries)} for seed {seed_index}: "
                  f"({x},{y} {w}x{h}) [{label}] — dry-run")
            observations.append({"x": x, "y": y, "grid": grid})
            result["queries_executed"] += 1
            continue

        try:
            sim_result = client.simulate(round_id, seed_index, x, y, w, h)
            queries_used = sim_result.queries_used
            queries_max = sim_result.queries_max
            observations.append({
                "x": sim_result.viewport.get("x", x),
                "y": sim_result.viewport.get("y", y),
                "grid": sim_result.grid,
            })
            # Collect settlement stats for potential use by predictor
            for s in sim_result.settlements:
                settlement_data.append({
                    "x": s.x, "y": s.y,
                    "population": s.population,
                    "food": s.food,
                    "defense": s.defense,
                    "wealth": s.wealth,
                    "alive": s.alive,
                    "has_port": s.has_port,
                })
            result["queries_executed"] += 1
            print(f"  Query {i+1}/{len(queries)} for seed {seed_index}: "
                  f"({x},{y} {w}x{h}) [{label}] — {queries_used}/{queries_max} budget")
        except Exception as e:
            print(f"  Query {i+1}/{len(queries)} for seed {seed_index}: "
                  f"({x},{y} {w}x{h}) [{label}] — FAILED: {e}")
            continue

    # Build observation map (now returns per-cell observation lists)
    observed_terrain, observation_count, all_observations = build_observation_map(observations)

    # Log settlement stats summary
    if settlement_data:
        alive_count = sum(1 for s in settlement_data if s.get("alive"))
        print(f"  Settlements observed: {len(settlement_data)} "
              f"({alive_count} alive)")
    coverage = int((observed_terrain >= 0).sum())
    total_cells = GRID_SIZE * GRID_SIZE
    print(f"  Coverage: {coverage}/{total_cells} cells observed "
          f"({100 * coverage / total_cells:.1f}%)")

    # Store multi-observation data and settlement info in result for analysis
    result["all_observations"] = all_observations
    result["settlement_data"] = settlement_data

    # Predict (pass all_observations for multi-sample averaging if predictor supports it)
    predictor = Predictor()
    prediction = predictor.predict(initial_state_grid, observed_terrain, observation_count)

    # Validate
    assert prediction.shape == (GRID_SIZE, GRID_SIZE, NUM_CLASSES), \
        f"Bad shape: {prediction.shape}"
    assert (prediction >= 0.0004).all(), \
        f"Values below floor: min={prediction.min()}"
    sums = prediction.sum(axis=-1)
    assert np.allclose(sums, 1.0, atol=0.02), \
        f"Row sums off: min={sums.min()}, max={sums.max()}"

    # Submit
    if dry_run:
        print(f"  Seed {seed_index}: validated (dry-run, not submitting)")
        result["submitted"] = True
        return result

    try:
        submit_result = client.submit(round_id, seed_index, prediction.tolist())
        print(f"  Seed {seed_index}: submitted ✓")
        if "score" in submit_result:
            print(f"    Score: {submit_result['score']}")
        result["submitted"] = True
        result["submit_response"] = submit_result
    except Exception as e:
        print(f"  Seed {seed_index}: submit FAILED — {e}")
        result["error"] = str(e)

    return result


def _random_grid(h: int, w: int) -> list[list[int]]:
    """Generate a random terrain grid for dry-run testing."""
    terrain_codes = [0, 1, 2, 3, 4, 5, 10, 11]
    weights = [0.1, 0.1, 0.05, 0.05, 0.3, 0.15, 0.15, 0.1]
    return [random.choices(terrain_codes, weights=weights, k=w) for _ in range(h)]


def _random_initial_state() -> list[list[int]]:
    """Generate a random initial state grid for dry-run testing."""
    terrain_codes = [0, 1, 4, 5, 10, 11]
    weights = [0.05, 0.08, 0.25, 0.12, 0.3, 0.2]
    return [random.choices(terrain_codes, weights=weights, k=GRID_SIZE) for _ in range(GRID_SIZE)]


def check_scores(client, round_id: str) -> None:
    """Print scores for a previously submitted round."""
    try:
        my_rounds = client.get_my_rounds()

        # Debug: show structure of first entry if no match found
        matched = None
        for r in my_rounds:
            # Handle multiple possible key names for round ID
            rid = r.get("round_id") or r.get("id") or r.get("roundId", "")
            if rid == round_id:
                matched = r
                break

        if not matched:
            print(f"No results found for round {round_id}")
            if my_rounds:
                print(f"\nAvailable rounds ({len(my_rounds)}):")
                for r in my_rounds:
                    rid = r.get("round_id") or r.get("id") or r.get("roundId", "?")
                    rnum = r.get("round_number") or r.get("roundNumber", "?")
                    print(f"  Round #{rnum} ({str(rid)[:12]}...)")
            return

        r = matched
        rnum = r.get("round_number") or r.get("roundNumber", "?")
        print(f"Round: #{rnum} ({round_id[:12]}...)")

        # Handle different response shapes for seed scores
        seed_scores = r.get("seed_scores") or r.get("seedScores") or r.get("scores", [])
        if isinstance(seed_scores, list):
            for ss in seed_scores:
                if isinstance(ss, dict):
                    si = ss.get("seed_index", ss.get("seedIndex", "?"))
                    score = ss.get("score", ss.get("logLoss", "pending"))
                    print(f"  Seed {si}: {score}")
                else:
                    print(f"  Score: {ss}")
        elif isinstance(seed_scores, dict):
            for k, v in seed_scores.items():
                print(f"  Seed {k}: {v}")

        avg = r.get("average_score") or r.get("averageScore") or r.get("totalScore")
        if avg is not None:
            print(f"  Average: {avg:.4f}")

        rank = r.get("rank") or r.get("position")
        if rank is not None:
            print(f"  Rank: {rank}")

    except Exception as e:
        print(f"Failed to fetch scores: {e}")


def main() -> int:
    args = parse_args()

    # Seed indices
    if args.seeds:
        seed_indices = [int(s.strip()) for s in args.seeds.split(",")]
    else:
        seed_indices = list(range(NUM_SEEDS))

    # Client
    client = None
    if not args.dry_run:
        token = args.token or config.TOKEN
        if not token:
            print("ERROR: No auth token. Set ASTAR_TOKEN env var, "
                  "write to ~/.astar-token, or pass --token.")
            return 1
        client = AstarClient(token)

    # Check scores mode
    if args.check_scores:
        if not args.round_id:
            print("ERROR: --check-scores requires --round-id")
            return 1
        check_scores(client, args.round_id)
        return 0

    # Get round
    round_obj = None
    if args.dry_run:
        round_id = args.round_id or "dry-run-fake-uuid"
        print("=== DRY RUN MODE ===")
        print(f"Round: {round_id}")
    elif args.round_id:
        round_obj = client.get_round(args.round_id)
        round_id = round_obj.id
    else:
        print("Looking for active round...")
        round_obj = client.get_active_round()
        if not round_obj:
            print("ERROR: No active round found. Use --round-id to specify one.")
            return 1
        round_id = round_obj.id

    # Print round info
    if round_obj:
        print(f"\n=== Astar Island Solver ===")
        print(f"Round: #{round_obj.round_number} ({round_obj.id[:12]}...)")
        print(f"Status: {round_obj.status}")
        print(f"Closes at: {round_obj.closes_at}")
        print(f"Weight: {round_obj.round_weight}")
        if round_obj.status != "active":
            print(f"WARNING: Round is '{round_obj.status}', not 'active'!")

    # Get initial states
    initial_states: dict[int, list] = {}
    if args.dry_run:
        for si in seed_indices:
            initial_states[si] = _random_initial_state()
    elif round_obj and round_obj.initial_states:
        for si in seed_indices:
            if si < len(round_obj.initial_states):
                initial_states[si] = round_obj.initial_states[si].grid
            else:
                print(f"WARNING: No initial state for seed {si}")
    else:
        print("WARNING: No initial states available — predictions will be less accurate")

    # Check budget
    if client and not args.initial_only:
        try:
            budget = client.get_budget()
            print(f"Budget: {budget.get('queries_used', '?')}/"
                  f"{budget.get('queries_max', '?')} queries used")
        except Exception as e:
            print(f"Could not fetch budget: {e}")

    # Solve each seed
    print(f"\nSolving seeds: {seed_indices}")
    if args.initial_only:
        print("Mode: initial-only (no simulation queries)")
    print()

    results = []
    for si in seed_indices:
        print(f"--- Seed {si} ---")
        init_grid = initial_states.get(si)
        if init_grid is None:
            print(f"  Skipping seed {si}: no initial state available")
            results.append({"seed_index": si, "submitted": False, "error": "no initial state"})
            continue

        if args.initial_only:
            # Predict from initial state only, no queries
            observed_terrain = np.full((GRID_SIZE, GRID_SIZE), -1, dtype=int)
            observation_count = np.zeros((GRID_SIZE, GRID_SIZE), dtype=int)
            predictor = Predictor()
            prediction = predictor.predict(init_grid, observed_terrain, observation_count)
            if args.dry_run:
                print(f"  Seed {si}: validated (dry-run, initial-only)")
                results.append({"seed_index": si, "submitted": True})
            else:
                try:
                    submit_result = client.submit(round_id, si, prediction.tolist())
                    print(f"  Seed {si}: submitted ✓ (initial-only)")
                    results.append({"seed_index": si, "submitted": True,
                                    "submit_response": submit_result})
                except Exception as e:
                    print(f"  Seed {si}: submit FAILED — {e}")
                    results.append({"seed_index": si, "submitted": False, "error": str(e)})
        else:
            r = solve_seed(client, round_id, si, init_grid, dry_run=args.dry_run)
            results.append(r)
        print()

    # Summary
    submitted_count = sum(1 for r in results if r.get("submitted"))
    total_queries = sum(r.get("queries_executed", 0) for r in results)

    print("=== Astar Island Solver Results ===")
    if args.dry_run:
        print("Round: dry-run")
    else:
        print(f"Round: #{round_obj.round_number} ({round_id[:12]}...)")
    print(f"Seeds submitted: {submitted_count}/{len(seed_indices)}")
    if not args.initial_only:
        print(f"Queries executed: {total_queries}")
    print()
    for r in results:
        si = r["seed_index"]
        if r.get("submitted"):
            status = "submitted ✓"
        else:
            status = f"FAILED: {r.get('error', 'unknown')}"
        print(f"  Seed {si}: {status}")

    if not args.dry_run and round_id:
        print(f"\nCheck scores later:")
        print(f"  python solver.py --check-scores --round-id {round_id}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
