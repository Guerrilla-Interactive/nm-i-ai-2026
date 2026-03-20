#!/usr/bin/env python3
"""Try smart floor: skip static cells, vary floor per class."""
import json, numpy as np, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import GRID_SIZE, NUM_CLASSES

# Copy the distributions from resubmit_simple
SETTLEMENT_DIST = [0.3832, 0.4098, 0.0051, 0.0341, 0.1678, 0.0000]
PORT_DIST = [0.3841, 0.1214, 0.2877, 0.0345, 0.1723, 0.0000]
RUIN_DIST = [0.3832, 0.4098, 0.0051, 0.0341, 0.1678, 0.0000]
PLAINS_NEAR_SETT = [0.7099, 0.2025, 0.0146, 0.0200, 0.0530, 0.0000]
PLAINS_FAR_SETT  = [0.8078, 0.1328, 0.0187, 0.0135, 0.0271, 0.0000]
PLAINS_NEAR_OCEAN = [0.7550, 0.1400, 0.0540, 0.0145, 0.0365, 0.0000]
FOREST_NEAR_SETT = [0.1205, 0.2088, 0.0116, 0.0199, 0.6393, 0.0000]
FOREST_FAR_SETT  = [0.0629, 0.1441, 0.0174, 0.0131, 0.7626, 0.0000]
FOREST_NEAR_OCEAN = [0.0775, 0.1670, 0.0491, 0.0144, 0.6919, 0.0000]

def count_neighbors(grid, y, x, codes, radius):
    count = 0
    for dy in range(-radius, radius+1):
        for dx in range(-radius, radius+1):
            if dy == 0 and dx == 0: continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < 40 and 0 <= nx < 40 and grid[ny][nx] in codes:
                count += 1
    return count

def predict_smart(initial_grid, floor=0.005, mountain_floor=None):
    """Smart floor: different floors for static vs dynamic cells."""
    if mountain_floor is None:
        mountain_floor = floor
    pred = np.zeros((40, 40, 6))
    for y in range(40):
        for x in range(40):
            code = initial_grid[y][x]
            if code == 5:
                # Mountain: static. Use mountain_floor for non-mountain classes
                pred[y, x] = [mountain_floor, mountain_floor, mountain_floor, mountain_floor, mountain_floor, 1.0]
                pred[y, x] /= pred[y, x].sum()
            elif code == 10:
                # Ocean: static. Use mountain_floor for non-ocean classes
                pred[y, x] = [1.0, mountain_floor, mountain_floor, mountain_floor, mountain_floor, mountain_floor]
                pred[y, x] /= pred[y, x].sum()
            elif code == 1:
                pred[y, x] = SETTLEMENT_DIST
            elif code == 2:
                pred[y, x] = PORT_DIST
            elif code == 3:
                pred[y, x] = RUIN_DIST
            elif code in (11, 0):
                oc = count_neighbors(initial_grid, y, x, {10}, radius=2)
                sc = count_neighbors(initial_grid, y, x, {1, 2, 3}, radius=3)
                if oc >= 4:
                    pred[y, x] = PLAINS_NEAR_OCEAN
                elif sc > 0:
                    pred[y, x] = PLAINS_NEAR_SETT
                else:
                    pred[y, x] = PLAINS_FAR_SETT
            elif code == 4:
                oc = count_neighbors(initial_grid, y, x, {10}, radius=2)
                sc = count_neighbors(initial_grid, y, x, {1, 2, 3}, radius=3)
                if oc >= 4:
                    pred[y, x] = FOREST_NEAR_OCEAN
                elif sc > 0:
                    pred[y, x] = FOREST_NEAR_SETT
                else:
                    pred[y, x] = FOREST_FAR_SETT
            else:
                pred[y, x] = [1/6] * 6

    # Floor dynamic cells only
    for y in range(40):
        for x in range(40):
            code = initial_grid[y][x]
            if code in (5, 10):
                continue  # already handled above
            pred[y, x] = np.maximum(pred[y, x], floor)
            pred[y, x] /= pred[y, x].sum()

    return pred

def compute_kl(truth, pred):
    kl_sum, weight_sum = 0.0, 0.0
    for y in range(40):
        for x in range(40):
            p, q = truth[y, x], pred[y, x]
            entropy = -sum(pi * np.log(pi + 1e-12) for pi in p if pi > 0)
            if entropy < 1e-6:
                continue
            kl = sum(pi * np.log(pi / max(qi, 1e-10)) for pi, qi in zip(p, q) if pi > 0)
            kl_sum += entropy * kl
            weight_sum += entropy
    weighted_kl = kl_sum / weight_sum if weight_sum > 0 else 0
    return max(0, min(100, 100 * np.exp(-3 * weighted_kl)))

seeds_data = []
for seed in range(5):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f'round2_analysis_seed{seed}.json')
    with open(path) as f:
        seeds_data.append(json.load(f))

# Test: static cells get tiny floor (0.001), dynamic get 0.005
for floor in [0.003, 0.005]:
    for mf in [0.001, 0.005]:
        scores = []
        for data in seeds_data:
            pred = predict_smart(data['initial_grid'], floor=floor, mountain_floor=mf)
            scores.append(compute_kl(np.array(data['ground_truth']), pred))
            # Check min value
        min_val = min(predict_smart(data['initial_grid'], floor=floor, mountain_floor=mf).min() for data in seeds_data)
        print(f"Floor={floor:.3f} mtn_floor={mf:.3f}: avg={np.mean(scores):.2f} min_pred={min_val:.4f}")

# The real question: what's the actual API minimum?
# Let's test 0.005 floor everywhere (safe) but see per-class effect
print("\n--- Per-class floor optimization ---")
# What if mountain class (5) gets floor=0.005 but we don't floor it for dynamic cells?
# Ground truth shows class 5 is ALWAYS 0 in non-mountain cells
# So flooring it at 0.005 wastes probability

# Class-specific floors: [c0, c1, c2, c3, c4, c5]
for c5_floor in [0.001, 0.003, 0.005]:
    for c2_floor in [0.003, 0.005]:
        class_floors = np.array([0.005, 0.005, c2_floor, 0.005, 0.005, c5_floor])
        scores = []
        for data in seeds_data:
            pred = predict_smart(data['initial_grid'], floor=0.005, mountain_floor=0.001)
            # Override: apply per-class floor
            for y in range(40):
                for x in range(40):
                    code = data['initial_grid'][y][x]
                    if code in (5, 10): continue
                    pred[y, x] = np.maximum(pred[y, x], class_floors)
                    pred[y, x] /= pred[y, x].sum()
            scores.append(compute_kl(np.array(data['ground_truth']), pred))
        print(f"c5_floor={c5_floor:.3f} c2_floor={c2_floor:.3f}: avg={np.mean(scores):.2f}")
