# Astar Island Solver — Verification Report

**Date:** 2026-03-20
**Verified by:** Worker 5 (Doey team-4)

## Import & Module Loading

- All modules import cleanly: config, models, client, predictor, strategy, solver
- `solver.py` bootstrap handles the `astar-island` (hyphen) package name correctly via `importlib`

## Bug Found & Fixed

**solver.py:205 — Floor assertion mismatch**
- The predictor uses per-class floors: `CLASS_FLOORS = [0.01, 0.01, 0.01, 0.01, 0.01, 0.001]`
- Mountain (class 5) has floor 0.001, not 0.01
- The solver asserted `prediction >= 0.01`, which failed on mountain predictions in dynamic cells
- **Fix:** Changed assertion to `>= 0.001` to match the actual minimum floor

## Terrain Code Mapping (config.py)

SIM_TO_CLASS mapping verified:
| Sim Code | Class | Name |
|----------|-------|------|
| 10 | 0 | Ocean |
| 11 | 0 | Plains/Empty |
| 0 | 0 | Empty |
| 1 | 1 | Settlement |
| 2 | 2 | Port |
| 3 | 3 | Ruin |
| 4 | 4 | Forest |
| 5 | 5 | Mountain |

- Codes 10, 11, 0 all map to class 0 (correct — they are "empty/ocean/plains" for prediction)
- 6 prediction classes total (0-5)

## Probability Floors & Normalization (predictor.py)

- Per-class floors applied: 0.01 for classes 0-4, 0.001 for mountain (class 5)
- Iterative floor+renormalize loop runs up to 10 iterations (convergence check)
- Sums verified to be 1.0 (atol=0.01)
- Static cells (ocean=10, mountain=5) get deterministic distributions [1,0,0,0,0,0] and [0,0,0,0,0,1]

## Tiling Strategy (strategy.py)

- 3x3 grid of 15x15 viewports at offsets [0, 13, 25]
- Tiles: [0-14], [13-27], [25-39] → overlapping covers full 0-39 range
- 9 queries achieve **100% coverage** (1600/1600 cells)
- 10th query repeats center for stochastic sampling
- 10 queries per seed x 5 seeds = 50 queries = full budget

## Predictor Logic (predictor.py v6)

- Neighbor-regression model using 8-connected neighbor counts
- Separate coefficient matrices for Plains, Forest, Settlement initial types
- Port uses flat mean (only 11 training samples)
- Observation adjustment: +0.03 weight boost to observed class, redistributed from others
- Mountain class always predicted as 0 probability in dynamic cells (correct — mountains don't appear dynamically)

## Test Suite Results

All tests pass:
- Prediction shape: (40, 40, 6)
- Min value: 0.0100 for classes 0-4, 0.001 for class 5
- Sum range: [1.0000, 1.0000]
- Mountain predictions: 30/30 cells > 0.9 confidence (seed 0)
- Ocean predictions: 182/182 cells > 0.8 confidence (seed 0)
- Full coverage: 1600/1600 cells with 9 queries
- Dry-run solver completes without errors (after fix)

## Competition Status (2026-03-20)

- **2 rounds completed** (both on 2026-03-19)
  - Round 1: `71451d74...` (weight 1.05)
  - Round 2: `76909e29...` (weight 1.1025)
- **No active round** at time of check
- **176 teams** on leaderboard

### Top 5 Leaderboard
| Rank | Team | Weighted Score |
|------|------|---------------|
| 1 | Algebros | 98.79 |
| 2 | Propulsion Optimizers | 98.71 |
| 3 | claudeus | 97.81 |
| 4 | People Made Machines | 95.28 |
| 5 | Paralov - studs.gg | 95.26 |

## Conclusion

Code is functional and correct after the floor assertion fix. The solver is ready for the next active round.
