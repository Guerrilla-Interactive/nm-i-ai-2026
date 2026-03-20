"""Predictor v10: 4-ring + interaction features regression."""
from __future__ import annotations

import numpy as np
from config import SIM_TO_CLASS, GRID_SIZE, NUM_CLASSES

STATIC_TRUTH = {
    10: np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
    5:  np.array([0.0, 0.0, 0.0, 0.0, 0.0, 1.0]),
}

CLASS_FLOORS = np.array([0.002, 0.002, 0.001, 0.001, 0.002, 0.0005])

def _make_ring(r):
    return [(dy, dx) for dy in range(-r, r+1) for dx in range(-r, r+1) if max(abs(dy), abs(dx)) == r]

_RINGS = [_make_ring(r) for r in range(1, 5)]

# 25 features: intercept + 5 types × 4 rings + 4 interactions
# Interactions: ocean_r1*settle_r1, forest_r1*settle_r1, forest_r1*plains_r1, ocean_r1*plains_r1
PLAINS_COEFFS = np.array([
    [0.053423, 0.088304, 0.055539, 0.099104, 0.093643, 0.090792, -0.007274, -0.036430, -0.002306, -0.005596, -0.005522, -0.003968, -0.020872, -0.000599, -0.002864, -0.002679, 0.004903, 0.001209, 0.002334, 0.001366, 0.005327, -0.016546, 0.000404, 0.000157, -0.000076],
    [0.013667, 0.018776, 0.048183, 0.002298, 0.018800, 0.021279, 0.005774, 0.018960, 0.003477, 0.002758, 0.004118, 0.003917, 0.006162, 0.001321, 0.003333, 0.002633, -0.004332, -0.008214, -0.001927, -0.001321, -0.004807, -0.003703, 0.002446, 0.000844, -0.003599],
    [0.005134, 0.011705, 0.007206, 0.013729, 0.003341, 0.005087, -0.000953, 0.002698, -0.002866, -0.000704, -0.001098, -0.001368, 0.000291, -0.001174, -0.001435, -0.001449, 0.000040, 0.000149, 0.000355, 0.000092, 0.000090, 0.018188, -0.002343, -0.001315, 0.003829],
    [0.000351, -0.000221, 0.001370, 0.000820, 0.000633, 0.000204, 0.000955, 0.002995, 0.000312, 0.000843, 0.000936, 0.000231, 0.001819, -0.000062, -0.000059, 0.000150, -0.000043, 0.000932, -0.000146, -0.000227, -0.000191, 0.000817, -0.000088, 0.000147, -0.000140],
    [-0.000110, -0.002622, 0.003643, -0.000009, -0.000474, -0.001420, 0.001499, 0.011778, 0.001383, 0.002700, 0.001567, 0.001188, 0.012601, 0.000513, 0.001025, 0.001345, -0.000568, 0.005924, -0.000616, 0.000089, -0.000419, 0.001244, -0.000419, 0.000167, -0.000014],
    [0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000],
])

FOREST_COEFFS = np.array([
    [0.001182, -0.002933, 0.006207, 0.006348, 0.002290, -0.002459, 0.002983, 0.026700, 0.002131, 0.002408, 0.003590, 0.003458, 0.030452, 0.001015, 0.004520, 0.003257, -0.001825, 0.012941, -0.000821, -0.001295, -0.001378, -0.001222, 0.001100, -0.000277, -0.001595],
    [0.014177, 0.019137, 0.054396, 0.006963, 0.013750, 0.019167, 0.008822, 0.021622, 0.006732, 0.005535, 0.006766, 0.007521, 0.007899, 0.001311, 0.008577, 0.005437, -0.007274, -0.012532, -0.003253, -0.007409, -0.007851, -0.003315, 0.001114, 0.000073, -0.005149],
    [0.007985, 0.013980, 0.011415, 0.018393, 0.009468, 0.010622, -0.003244, -0.000159, -0.005575, -0.002107, -0.003196, -0.001733, -0.000911, -0.001583, -0.002616, -0.002069, 0.000181, 0.000098, 0.000386, 0.000474, 0.000030, 0.020163, -0.000685, -0.000631, 0.003569],
    [0.000511, 0.000335, 0.001398, 0.001399, 0.000909, 0.000045, 0.000890, 0.002956, 0.000449, 0.000367, 0.000794, 0.000483, 0.002573, 0.000063, -0.000010, 0.000403, -0.000202, 0.000196, -0.000260, -0.000153, -0.000250, -0.000184, -0.000252, -0.000035, -0.000327],
    [0.048610, 0.085423, 0.042526, 0.082838, 0.089525, 0.088566, -0.009451, -0.051120, -0.003737, -0.006203, -0.007955, -0.009729, -0.040013, -0.000806, -0.010471, -0.007028, 0.009120, -0.000703, 0.003948, 0.008382, 0.009449, -0.015442, -0.001277, 0.000870, 0.003503],
    [0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000],
])

SETTLEMENT_COEFFS = np.array([
    [0.002618, 0.008676, -0.000000, -0.017747, 0.026503, 0.003511, -0.002722, 0.035960, 0.019089, -0.009488, -0.000953, 0.010517, 0.044552, 0.014407, 0.014513, 0.015985, 0.000320, 0.003875, -0.000685, 0.001995, 0.000114, 0.000000, 0.000000, -0.004441, 0.003238],
    [0.004563, 0.022204, 0.000000, -0.055187, 0.026896, 0.042595, 0.029275, -0.024448, 0.005227, 0.033880, 0.029081, -0.010294, -0.050159, -0.015420, -0.014365, -0.015767, -0.001957, -0.004573, 0.000746, -0.000437, -0.000915, 0.000000, 0.000000, 0.008954, 0.016947],
    [0.005072, -0.021806, -0.000000, 0.122371, -0.031858, -0.028128, 0.016427, 0.013987, 0.017864, 0.016070, 0.016810, -0.000089, -0.001124, -0.002079, -0.000395, -0.001209, -0.000159, -0.000582, -0.000513, -0.000601, -0.000901, 0.000000, 0.000000, -0.001398, -0.028083],
    [0.000568, 0.003821, 0.000000, -0.001145, -0.000754, 0.002623, 0.003498, -0.001611, 0.000383, 0.003324, 0.003495, -0.002044, -0.004706, -0.001547, -0.000123, -0.002569, 0.001025, 0.001644, 0.000818, 0.000188, 0.000476, 0.000000, 0.000000, -0.000378, 0.000834],
    [0.001841, 0.016432, 0.000000, -0.018967, 0.008539, 0.008724, 0.000442, 0.023033, 0.004357, 0.003134, -0.001513, 0.001910, 0.011438, 0.004639, 0.000371, 0.003560, 0.000772, -0.000364, -0.000366, -0.001144, 0.001226, 0.000000, 0.000000, -0.002736, 0.007064],
    [0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000],
])

PORT_MEAN = np.array([0.384091, 0.121364, 0.287727, 0.034545, 0.172273, 0.000000])


def _count_neighbors(grid_arr, offsets):
    """Compute neighbor counts for terrain types."""
    sz = GRID_SIZE
    forest = np.zeros((sz, sz), dtype=float)
    settle = np.zeros((sz, sz), dtype=float)
    ocean = np.zeros((sz, sz), dtype=float)
    mountain = np.zeros((sz, sz), dtype=float)
    plains = np.zeros((sz, sz), dtype=float)

    for dy, dx in offsets:
        y_s, y_e = max(0, dy), min(sz, sz + dy)
        x_s, x_e = max(0, dx), min(sz, sz + dx)
        sy_s, sx_s = max(0, -dy), max(0, -dx)
        sy_e = sy_s + (y_e - y_s)
        sx_e = sx_s + (x_e - x_s)
        slc = grid_arr[sy_s:sy_e, sx_s:sx_e]
        forest[y_s:y_e, x_s:x_e] += (slc == 4)
        settle[y_s:y_e, x_s:x_e] += ((slc == 1) | (slc == 2) | (slc == 3))
        ocean[y_s:y_e, x_s:x_e] += (slc == 10)
        mountain[y_s:y_e, x_s:x_e] += (slc == 5)
        plains[y_s:y_e, x_s:x_e] += ((slc == 11) | (slc == 0))

    return forest, settle, ocean, mountain, plains


class Predictor:
    def predict(
        self,
        initial_grid: list[list[int]],
        observed_terrain=None,
        observation_count=None,
        *,
        floor: float = 0.01,
    ) -> np.ndarray:
        """Build 40x40x6 prediction using 4-ring + interaction regression."""
        # ---- Parse calling convention ----
        if observed_terrain is None:
            observed_terrain = np.full((GRID_SIZE, GRID_SIZE), -1, dtype=int)
            observation_count = np.zeros((GRID_SIZE, GRID_SIZE), dtype=int)
        elif isinstance(observed_terrain, list):
            obs_list = observed_terrain
            observed_terrain = np.full((GRID_SIZE, GRID_SIZE), -1, dtype=int)
            observation_count = np.zeros((GRID_SIZE, GRID_SIZE), dtype=int)
            for obs in obs_list:
                vx = obs.get('viewport_x', obs.get('x', 0))
                vy = obs.get('viewport_y', obs.get('y', 0))
                vw = obs.get('viewport_w', obs.get('w', 15))
                vh = obs.get('viewport_h', obs.get('h', 15))
                grid = obs['grid']
                for dy in range(vh):
                    for dx in range(vw):
                        gy, gx = vy + dy, vx + dx
                        if 0 <= gy < GRID_SIZE and 0 <= gx < GRID_SIZE:
                            observed_terrain[gy, gx] = SIM_TO_CLASS.get(grid[dy][dx], 0)
                            observation_count[gy, gx] += 1
        else:
            observed_terrain = np.asarray(observed_terrain)
            if observation_count is None:
                observation_count = np.zeros((GRID_SIZE, GRID_SIZE), dtype=int)
            else:
                observation_count = np.asarray(observation_count)

        # Precompute neighbor counts for all 4 rings
        grid_arr = np.array(initial_grid)
        rings_data = [_count_neighbors(grid_arr, ring) for ring in _RINGS]

        pred = np.full((GRID_SIZE, GRID_SIZE, NUM_CLASSES), 1.0 / NUM_CLASSES)

        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                init_code = initial_grid[y][x]
                obs_cls = int(observed_terrain[y, x])

                if init_code in STATIC_TRUTH:
                    pred[y, x] = STATIC_TRUTH[init_code]
                    continue

                # Ring1 values for interactions
                f_r1 = rings_data[0][0][y, x]  # forest_r1
                s_r1 = rings_data[0][1][y, x]  # settle_r1
                o_r1 = rings_data[0][2][y, x]  # ocean_r1
                p_r1 = rings_data[0][4][y, x]  # plains_r1

                # Feature vector: [1, ring1(5), ring2(5), ring3(5), ring4(5), 4 interactions]
                features = np.empty(25)
                features[0] = 1.0
                for ri, rd in enumerate(rings_data):
                    offset = 1 + ri * 5
                    features[offset] = rd[0][y, x]
                    features[offset + 1] = rd[1][y, x]
                    features[offset + 2] = rd[2][y, x]
                    features[offset + 3] = rd[3][y, x]
                    features[offset + 4] = rd[4][y, x]
                # Interactions
                features[21] = o_r1 * s_r1
                features[22] = f_r1 * s_r1
                features[23] = f_r1 * p_r1
                features[24] = o_r1 * p_r1

                if init_code == 11 or init_code == 0:
                    base = PLAINS_COEFFS @ features
                elif init_code == 4:
                    base = FOREST_COEFFS @ features
                elif init_code == 1 or init_code == 3:
                    base = SETTLEMENT_COEFFS @ features
                elif init_code == 2:
                    base = PORT_MEAN.copy()
                else:
                    base = np.ones(NUM_CLASSES) / NUM_CLASSES

                base = np.maximum(base, 0.0)
                total = base.sum()
                if total > 1e-9:
                    base /= total

                # Observation adjustment
                if obs_cls >= 0:
                    obs_weight = 0.03
                    old_obs_val = base[obs_cls]
                    base[obs_cls] += obs_weight
                    other_total = 1.0 - old_obs_val
                    if other_total > 1e-9:
                        for c in range(NUM_CLASSES):
                            if c != obs_cls:
                                base[c] -= obs_weight * (base[c] / other_total)
                    base = np.maximum(base, 0.001)
                    base /= base.sum()

                pred[y, x] = base

        # Floor and renormalize
        floors = CLASS_FLOORS.copy()
        if floor != 0.01:
            floors = np.maximum(floors, floor * 0.1)
            floors = np.minimum(floors, floor)
            floors[5] = min(floors[5], 0.0005)

        for _ in range(10):
            pred = np.maximum(pred, floors[np.newaxis, np.newaxis, :])
            pred = pred / pred.sum(axis=-1, keepdims=True)
            if (pred >= floors[np.newaxis, np.newaxis, :] - 1e-9).all():
                break
        return pred
