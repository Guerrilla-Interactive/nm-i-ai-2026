#!/usr/bin/env python3
"""Test the predictor with real initial state data from Round 2."""
import json
import sys
import os

sys.path.insert(0, '/tmp/doey/nm-i-ai-2026/worktrees/team-3/astar-island')

# Load real round data
with open('/tmp/doey/nm-i-ai-2026/worktrees/team-3/astar-island/round_data.json') as f:
    round_data = json.load(f)

print(f"Round #{round_data['round_number']} — Status: {round_data['status']}")
print(f"Closes at: {round_data['closes_at']}")
print(f"Seeds: {round_data['seeds_count']}")
print()

# ── Test 1: Import modules ──
errors = []

try:
    from config import SIM_TO_CLASS, GRID_SIZE, NUM_CLASSES
    print("✓ config imports OK")
except Exception as e:
    print(f"✗ config import failed: {e}")
    errors.append(f"config: {e}")

try:
    from models import Settlement, SimulationResult, InitialState, Round
    print("✓ models imports OK")
except Exception as e:
    print(f"✗ models import failed: {e}")
    errors.append(f"models: {e}")

try:
    from client import AstarClient
    print("✓ client imports OK")
except Exception as e:
    print(f"✗ client import failed: {e}")
    errors.append(f"client: {e}")

try:
    from predictor import Predictor
    print("✓ predictor imports OK")
except Exception as e:
    print(f"✗ predictor import failed: {e}")
    errors.append(f"predictor: {e}")

try:
    from strategy import get_query_plan, TILE_POSITIONS
    print("✓ strategy imports OK")
except Exception as e:
    print(f"✗ strategy import failed: {e}")
    errors.append(f"strategy: {e}")

if errors:
    print(f"\n⚠ {len(errors)} import error(s) — some tests will be skipped")

print()

# ── Test 2: Predictor with initial state only (no observations) ──
import numpy as np

initial_states = round_data.get('initial_states', [])
if not initial_states:
    print("✗ No initial states in round data!")
    sys.exit(1)

initial_grid = initial_states[0].get('grid', [])
print(f"Seed 0: {len(initial_grid)}x{len(initial_grid[0]) if initial_grid else 0} grid")

# Count terrain types in initial state
from collections import Counter
flat = [cell for row in initial_grid for cell in row]
counts = Counter(flat)
print(f"\nInitial state terrain distribution (seed 0):")
terrain_names = {10: "Ocean", 11: "Plains", 0: "Empty", 1: "Settlement", 2: "Port", 3: "Ruin", 4: "Forest", 5: "Mountain"}
for code in sorted(counts.keys()):
    name = terrain_names.get(code, f"Unknown({code})")
    print(f"  {name} ({code}): {counts[code]} cells ({counts[code]/1600*100:.1f}%)")

if 'predictor' not in [e.split(':')[0] for e in errors]:
    print("\n── Predictor Tests ──")
    pred = Predictor()
    # Test with no observations — should still produce valid predictions
    prediction = pred.predict(initial_grid, [])

    assert prediction.shape == (40, 40, 6), f"Wrong shape: {prediction.shape}"
    assert (prediction >= 0.01 - 1e-9).all(), f"Values below floor: min={prediction.min()}"
    sums = prediction.sum(axis=2)
    assert np.allclose(sums, 1.0, atol=0.01), f"Sums not 1.0: min={sums.min()}, max={sums.max()}"
    print(f"✓ Prediction shape: {prediction.shape}")
    print(f"✓ Min value: {prediction.min():.4f} (floor=0.01)")
    print(f"✓ Sum range: [{sums.min():.4f}, {sums.max():.4f}]")

    # Check mountain cells are predicted correctly
    mountain_count = 0
    mountain_correct = 0
    for y in range(40):
        for x in range(40):
            if initial_grid[y][x] == 5:  # Mountain
                mountain_count += 1
                if prediction[y, x, 5] > 0.9:
                    mountain_correct += 1
    if mountain_count > 0:
        print(f"✓ Mountain predictions: {mountain_correct}/{mountain_count} cells > 0.9 confidence")

    # Check ocean cells
    ocean_count = 0
    ocean_correct = 0
    for y in range(40):
        for x in range(40):
            if initial_grid[y][x] == 10:  # Ocean
                ocean_count += 1
                if prediction[y, x, 0] > 0.8:
                    ocean_correct += 1
    if ocean_count > 0:
        print(f"✓ Ocean predictions: {ocean_correct}/{ocean_count} cells > 0.8 confidence")
else:
    print("\n⚠ Skipping predictor tests (import failed)")

# ── Test 3: Strategy query plan ──
if 'strategy' not in [e.split(':')[0] for e in errors]:
    print("\n── Strategy Tests ──")
    plan = get_query_plan(0)
    print(f"✓ Query plan for seed 0: {len(plan)} queries")
    for i, q in enumerate(plan):
        print(f"  Q{i+1}: viewport ({q['viewport_x']}, {q['viewport_y']}) {q['viewport_w']}x{q['viewport_h']}")

    # Verify full coverage with first 9 queries
    covered = set()
    for q in plan[:9]:
        for dy in range(q['viewport_h']):
            for dx in range(q['viewport_w']):
                covered.add((q['viewport_y'] + dy, q['viewport_x'] + dx))
    print(f"\n✓ Coverage (9 queries): {len(covered)}/1600 cells ({len(covered)/1600*100:.1f}%)")

    if len(covered) == 1600:
        print("✓ FULL COVERAGE achieved!")
    else:
        missing = 1600 - len(covered)
        print(f"⚠ COVERAGE INCOMPLETE — {missing} cells uncovered")
else:
    print("\n⚠ Skipping strategy tests (import failed)")

# ── Test 4: All seeds terrain summary ──
print("\n── All Seeds Summary ──")
for i, state in enumerate(initial_states):
    grid = state.get('grid', [])
    settlements = state.get('settlements', [])
    flat = [cell for row in grid for cell in row]
    c = Counter(flat)
    ports = sum(1 for s in settlements if s.get('has_port'))
    print(f"Seed {i}: {c.get(5,0)} mountains, {c.get(10,0)} ocean, {c.get(4,0)} forest, "
          f"{len(settlements)} settlements ({ports} ports)")

# ── Summary ──
if not errors:
    print("\n=== ALL TESTS PASSED ===")
else:
    print(f"\n=== {len(errors)} IMPORT ERROR(S) — partial test run ===")
    for e in errors:
        print(f"  - {e}")
