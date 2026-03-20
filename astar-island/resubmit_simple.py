#!/usr/bin/env python3
"""
Resubmit Astar predictions using regression model trained on Round 2 ground truth.
V7: Extended features with radii 1-4, interaction terms.
Features: [1, sc1, sc2, sc3, sc4, oc1, oc2, oc3, fc1, fc2, fc3, mc1, mc2, pc1, pc2, so_int, sf_int]
"""
import sys
import os
import numpy as np
import json

sys.path.insert(0, os.path.dirname(__file__))
from client import AstarClient
from config import SIM_TO_CLASS, GRID_SIZE, NUM_CLASSES

ROUND_ID = "f1dac9a9-5cf1-49a9-8f17-d6cb5d5ba5cb"

PORT_DIST = [0.3841, 0.1214, 0.2877, 0.0345, 0.1723, 0.0000]
RUIN_DIST = [0.3832, 0.4098, 0.0051, 0.0341, 0.1678, 0.0000]

PLAINS_COEFFS = np.array([
    [0.0546543699, 0.0799546296, -0.0122100845, -0.0139452407, -0.0011617173, 0.0975389258, 0.0044873138, -0.0025391392, 0.0850772236, 0.0004689739, -0.0003428578, 0.0894635954, -0.0000938508, 0.0852005848, 0.0015226901, -0.0156707319, 0.0002890679],
    [0.0120363651, 0.0384284501, 0.0113772300, 0.0067616602, -0.0061278007, -0.0116236204, -0.0022732270, 0.0027776826, 0.0242907411, -0.0000063548, 0.0004065172, 0.0209982929, -0.0006520830, 0.0241970575, -0.0009374931, -0.0037075735, 0.0012756100],
    [0.0092292257, 0.0085635567, -0.0021270703, 0.0016190767, -0.0001748824, 0.0316964764, -0.0046952864, 0.0002048810, 0.0118916002, -0.0041324433, -0.0000616531, 0.0102944535, -0.0039239227, 0.0113877190, -0.0043092961, 0.0172088301, -0.0009427518],
    [-0.0003205039, -0.0015098022, 0.0012270125, 0.0005821712, 0.0010504905, -0.0000128097, 0.0003304918, -0.0000829287, -0.0004287228, 0.0007863100, 0.0000806645, -0.0000688732, 0.0006193593, -0.0005438233, 0.0008698665, 0.0008674237, -0.0001634460],
    [-0.0031356887, -0.0094948052, 0.0017329123, 0.0049823326, 0.0064139099, -0.0016569431, 0.0021507077, -0.0003604958, -0.0048888132, 0.0028835142, -0.0000826708, -0.0047454396, 0.0040504973, -0.0042995089, 0.0028542327, 0.0013020515, -0.0004584802],
    [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
])

FOREST_COEFFS = np.array([
    [-0.0060809266, -0.0230212551, 0.0023205638, 0.0129450949, 0.0141366726, -0.0011341940, 0.0036755719, -0.0005227817, -0.0102511415, 0.0058275841, 0.0001059596, -0.0042190354, 0.0062227008, -0.0100217870, 0.0064701833, -0.0009882649, 0.0007903874],
    [0.0111188560, 0.0450201282, 0.0139757765, 0.0065800448, -0.0083618414, -0.0131438118, -0.0008588066, 0.0032441895, 0.0206245653, 0.0013285258, 0.0005689089, 0.0151263962, 0.0010834827, 0.0213235699, 0.0001264487, -0.0034935665, -0.0002208100],
    [0.0139939659, 0.0170896742, -0.0053211750, 0.0009961460, -0.0006551566, 0.0368576643, -0.0074465031, 0.0001576561, 0.0201699860, -0.0073737322, 0.0001245735, 0.0180809284, -0.0064548256, 0.0197534741, -0.0072319371, 0.0190647919, -0.0000095335],
    [-0.0003827087, -0.0015836093, 0.0009803497, 0.0016838231, 0.0004388768, -0.0000632465, 0.0005695093, -0.0001248257, -0.0008517885, 0.0009911448, 0.0001003746, 0.0004738798, 0.0003599644, -0.0010369049, 0.0009890953, -0.0000637527, -0.0003174837],
    [0.0538145816, 0.0784370910, -0.0119555150, -0.0222051088, -0.0055585514, 0.0934256170, 0.0040602284, -0.0027542383, 0.0862504077, -0.0007735226, -0.0008998166, 0.0864798600, -0.0012113222, 0.0859236769, -0.0003537903, -0.0145192078, -0.0002425601],
    [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
])

SETTLEMENT_COEFFS = np.array([
    [0.0033455462, 0.0, 0.0192067881, 0.0275347960, 0.0059238266, 0.0036710458, 0.0201883938, 0.0000736673, -0.0134224088, 0.0196306348, -0.0036918727, 0.0397283862, 0.0050644401, -0.0032126537, 0.0162028517, 0.0, 0.0],
    [0.0014988240, 0.0, -0.0033615269, -0.0318783038, -0.0073645258, -0.0399152368, 0.0040273752, -0.0002439234, 0.0385133788, 0.0053075602, 0.0031106817, -0.0137848185, 0.0199810081, 0.0271772686, 0.0100173596, 0.0, 0.0],
    [0.0008570586, 0.0, 0.0033266982, -0.0029042086, 0.0006555535, 0.0474243869, 0.0059718711, -0.0004060246, -0.0099230277, 0.0026614583, 0.0009497853, -0.0171814532, 0.0044789501, -0.0134634375, 0.0041304277, 0.0, 0.0],
    [0.0001193886, 0.0, -0.0012283103, -0.0035858523, 0.0008051124, 0.0009720226, -0.0004425861, 0.0003004249, 0.0013066954, 0.0007999649, 0.0002429694, -0.0028007163, 0.0026596819, 0.0014771070, 0.0010765756, 0.0, 0.0],
    [0.0017434792, 0.0, 0.0183649742, 0.0108335687, -0.0000199667, 0.0029763745, 0.0065635692, 0.0002758558, -0.0013460446, 0.0079090051, -0.0006115638, 0.0091671948, 0.0041245431, 0.0031503087, 0.0048814087, 0.0, 0.0],
    [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
])


def count_neighbors(grid, y, x, codes, radius):
    count = 0
    for dy in range(-radius, radius+1):
        for dx in range(-radius, radius+1):
            if dy == 0 and dx == 0:
                continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < GRID_SIZE and 0 <= nx < GRID_SIZE:
                if grid[ny][nx] in codes:
                    count += 1
    return count


def get_features(grid, y, x):
    sc1 = count_neighbors(grid, y, x, {1, 2, 3}, 1)
    sc2 = count_neighbors(grid, y, x, {1, 2, 3}, 2)
    sc3 = count_neighbors(grid, y, x, {1, 2, 3}, 3)
    sc4 = count_neighbors(grid, y, x, {1, 2, 3}, 4)
    oc1 = count_neighbors(grid, y, x, {10}, 1)
    oc2 = count_neighbors(grid, y, x, {10}, 2)
    oc3 = count_neighbors(grid, y, x, {10}, 3)
    fc1 = count_neighbors(grid, y, x, {4}, 1)
    fc2 = count_neighbors(grid, y, x, {4}, 2)
    fc3 = count_neighbors(grid, y, x, {4}, 3)
    mc1 = count_neighbors(grid, y, x, {5}, 1)
    mc2 = count_neighbors(grid, y, x, {5}, 2)
    pc1 = count_neighbors(grid, y, x, {0, 11}, 1)
    pc2 = count_neighbors(grid, y, x, {0, 11}, 2)
    so_int = sc1 * oc1
    sf_int = sc1 * fc1
    return np.array([1, sc1, sc2, sc3, sc4, oc1, oc2, oc3, fc1, fc2, fc3, mc1, mc2, pc1, pc2, so_int, sf_int])


def predict_from_initial(initial_grid, floor=0.001):
    """Build 40x40x6 prediction from initial state only."""
    pred = np.zeros((GRID_SIZE, GRID_SIZE, NUM_CLASSES))

    for y in range(GRID_SIZE):
        for x in range(GRID_SIZE):
            code = initial_grid[y][x]

            if code == 5:
                pred[y, x] = [0.0, 0.0, 0.0, 0.0, 0.0, 1.0]
            elif code == 10:
                pred[y, x] = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0]
            elif code == 2:
                pred[y, x] = PORT_DIST
            elif code == 3:
                pred[y, x] = RUIN_DIST
            elif code in (11, 0):
                feat = get_features(initial_grid, y, x)
                pred[y, x] = PLAINS_COEFFS @ feat
            elif code == 4:
                feat = get_features(initial_grid, y, x)
                pred[y, x] = FOREST_COEFFS @ feat
            elif code == 1:
                feat = get_features(initial_grid, y, x)
                pred[y, x] = SETTLEMENT_COEFFS @ feat
            else:
                pred[y, x] = [1/6] * 6

    # Floor and renormalize
    pred = np.maximum(pred, floor)
    pred = pred / pred.sum(axis=-1, keepdims=True)

    return pred


def main():
    token = os.environ.get("ASTAR_TOKEN", "")
    if not token:
        print("Set ASTAR_TOKEN env var")
        sys.exit(1)

    client = AstarClient(token)

    print(f"Fetching round {ROUND_ID[:8]}...")
    rnd = client.get_round(ROUND_ID)

    if not rnd.initial_states:
        print("ERROR: No initial states in round data")
        sys.exit(1)

    print(f"Round {rnd.round_number}: {rnd.status}, {rnd.seeds_count} seeds")

    for seed_idx in range(rnd.seeds_count):
        initial_grid = rnd.initial_states[seed_idx].grid
        counts = {}
        for row in initial_grid:
            for cell in row:
                counts[cell] = counts.get(cell, 0) + 1
        print(f"\n  Seed {seed_idx} initial: {dict(sorted(counts.items()))}")

        prediction = predict_from_initial(initial_grid)

        assert prediction.shape == (GRID_SIZE, GRID_SIZE, NUM_CLASSES)
        assert (prediction >= 0.0009).all(), f"Min: {prediction.min()}"
        sums = prediction.sum(axis=-1)
        assert np.allclose(sums, 1.0, atol=0.02), f"Sums: {sums.min()}-{sums.max()}"

        result = client.submit(ROUND_ID, seed_idx, prediction.tolist())
        print(f"  Seed {seed_idx}: resubmitted -> {result}")

    print(f"\nDone! All {rnd.seeds_count} seeds resubmitted.")


if __name__ == "__main__":
    main()
