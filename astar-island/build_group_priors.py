#!/usr/bin/env python3
"""
Build empirical group priors from R2 and R3 ground truth.
Groups: (terrain_type, is_coastal, settlement_neighbors_r1_bin)
Outputs: data/group_priors_r2.json, data/group_priors_r3.json
"""
import json, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from config import GRID_SIZE, NUM_CLASSES

def is_coastal(grid, y, x):
    """Check if cell is adjacent to ocean (code 10)."""
    for dy in range(-1, 2):
        for dx in range(-1, 2):
            if dy == 0 and dx == 0:
                continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < GRID_SIZE and 0 <= nx < GRID_SIZE:
                if grid[ny][nx] == 10:
                    return True
    return False

def count_settle_neighbors(grid, y, x, radius=1):
    """Count settlement/port/ruin neighbors."""
    count = 0
    for dy in range(-radius, radius+1):
        for dx in range(-radius, radius+1):
            if dy == 0 and dx == 0:
                continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < GRID_SIZE and 0 <= nx < GRID_SIZE:
                if grid[ny][nx] in (1, 2, 3):
                    count += 1
    return count

def settle_bin(count):
    """Bin settlement neighbor count: 0, 1, 2+"""
    if count == 0:
        return 0
    elif count == 1:
        return 1
    else:
        return 2

def count_forest_neighbors(grid, y, x, radius=1):
    count = 0
    for dy in range(-radius, radius+1):
        for dx in range(-radius, radius+1):
            if dy == 0 and dx == 0:
                continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < GRID_SIZE and 0 <= nx < GRID_SIZE:
                if grid[ny][nx] == 4:
                    count += 1
    return count

def forest_bin(count):
    if count == 0:
        return 0
    elif count <= 2:
        return 1
    else:
        return 2

def build_priors(round_name, seed_files):
    """Build group priors from ground truth files."""
    # Accumulate: group_key -> sum of ground truth distributions
    group_sums = {}
    group_counts = {}

    for fname in seed_files:
        data = json.load(open(fname))
        grid = data['initial_grid']
        gt = data['ground_truth']

        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                code = grid[y][x]

                # Static cells - skip
                if code == 5:  # Mountain
                    continue
                if code == 10:  # Ocean
                    continue

                coastal = is_coastal(grid, y, x)
                sn = settle_bin(count_settle_neighbors(grid, y, x))
                fn = forest_bin(count_forest_neighbors(grid, y, x))

                # Group key: (terrain, coastal, settle_bin, forest_bin)
                key = (code, coastal, sn, fn)

                if key not in group_sums:
                    group_sums[key] = np.zeros(NUM_CLASSES)
                    group_counts[key] = 0

                group_sums[key] += np.array(gt[y][x])
                group_counts[key] += 1

    # Convert to averages
    priors = {}
    for key, s in group_sums.items():
        avg = s / group_counts[key]
        # Serialize key as string
        str_key = f"{key[0]}_{key[1]}_{key[2]}_{key[3]}"
        priors[str_key] = {
            'dist': avg.tolist(),
            'count': group_counts[key],
            'terrain': key[0],
            'coastal': key[1],
            'settle_bin': key[2],
            'forest_bin': key[3],
        }

    return priors

def score_priors(priors, seed_files):
    """Score priors against ground truth using entropy-weighted KL."""
    total_kl = 0.0
    total_weight = 0.0

    for fname in seed_files:
        data = json.load(open(fname))
        grid = data['initial_grid']
        gt = data['ground_truth']

        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                code = grid[y][x]
                if code == 5 or code == 10:
                    continue

                p = np.array(gt[y][x])

                # Entropy weight
                entropy = -np.sum(p[p > 0] * np.log(p[p > 0]))
                if entropy < 1e-10:
                    continue

                coastal = is_coastal(grid, y, x)
                sn = settle_bin(count_settle_neighbors(grid, y, x))
                fn = forest_bin(count_forest_neighbors(grid, y, x))
                key = f"{code}_{coastal}_{sn}_{fn}"

                if key in priors:
                    q = np.array(priors[key]['dist'])
                else:
                    # Fallback: simpler group
                    fallback_key = f"{code}_{coastal}_{sn}_0"
                    if fallback_key in priors:
                        q = np.array(priors[fallback_key]['dist'])
                    else:
                        q = np.ones(NUM_CLASSES) / NUM_CLASSES

                q = np.maximum(q, 0.005)
                q = q / q.sum()

                kl = np.sum(p[p > 0] * np.log(p[p > 0] / q[p > 0]))
                total_kl += entropy * kl
                total_weight += entropy

    weighted_kl = total_kl / total_weight if total_weight > 0 else 0
    score = 100 * np.exp(-3 * weighted_kl)
    return score, weighted_kl

def main():
    # Build R2 priors
    r2_files = [f'data/r2_analysis_seed{i}.json' for i in range(5)]
    r3_files = [f'data/r3_analysis_seed{i}.json' for i in range(5)]

    print("=== Building R2 Group Priors ===")
    r2_priors = build_priors("R2", r2_files)
    print(f"  {len(r2_priors)} groups")

    print("\n=== Building R3 Group Priors ===")
    r3_priors = build_priors("R3", r3_files)
    print(f"  {len(r3_priors)} groups")

    # Build combined priors
    print("\n=== Building Combined Priors ===")
    combined_priors = build_priors("Combined", r2_files + r3_files)
    print(f"  {len(combined_priors)} groups")

    # Score each against each
    print("\n=== In-sample Scores ===")
    r2_on_r2 = score_priors(r2_priors, r2_files)
    print(f"  R2 priors on R2 data: score={r2_on_r2[0]:.2f} (kl={r2_on_r2[1]:.4f})")

    r3_on_r3 = score_priors(r3_priors, r3_files)
    print(f"  R3 priors on R3 data: score={r3_on_r3[0]:.2f} (kl={r3_on_r3[1]:.4f})")

    print("\n=== Cross-regime Scores ===")
    r2_on_r3 = score_priors(r2_priors, r3_files)
    print(f"  R2 priors on R3 data: score={r2_on_r3[0]:.2f} (kl={r2_on_r3[1]:.4f})")

    r3_on_r2 = score_priors(r3_priors, r2_files)
    print(f"  R3 priors on R2 data: score={r3_on_r2[0]:.2f} (kl={r3_on_r2[1]:.4f})")

    print("\n=== Combined Scores ===")
    comb_on_r2 = score_priors(combined_priors, r2_files)
    print(f"  Combined priors on R2: score={comb_on_r2[0]:.2f} (kl={comb_on_r2[1]:.4f})")
    comb_on_r3 = score_priors(combined_priors, r3_files)
    print(f"  Combined priors on R3: score={comb_on_r3[0]:.2f} (kl={comb_on_r3[1]:.4f})")

    # Leave-one-out cross-validation for R2
    print("\n=== Leave-one-out CV ===")
    for round_name, files in [("R2", r2_files), ("R3", r3_files)]:
        scores = []
        for held_out in range(5):
            train = [f for i, f in enumerate(files) if i != held_out]
            test = [files[held_out]]
            priors = build_priors(f"{round_name}_loo{held_out}", train)
            s, _ = score_priors(priors, test)
            scores.append(s)
        avg = np.mean(scores)
        print(f"  {round_name} LOO-CV: {[f'{s:.1f}' for s in scores]} avg={avg:.2f}")

    # Save
    json.dump(r2_priors, open('data/group_priors_r2.json', 'w'), indent=1)
    json.dump(r3_priors, open('data/group_priors_r3.json', 'w'), indent=1)
    json.dump(combined_priors, open('data/group_priors_combined.json', 'w'), indent=1)
    print("\nSaved: data/group_priors_r2.json, data/group_priors_r3.json, data/group_priors_combined.json")


if __name__ == '__main__':
    main()
