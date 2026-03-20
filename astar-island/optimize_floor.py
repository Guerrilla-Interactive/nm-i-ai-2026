#!/usr/bin/env python3
"""Find optimal floor value."""
import json, numpy as np, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from resubmit_simple import predict_from_initial

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

# Load data
seeds_data = []
for seed in range(5):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f'round2_analysis_seed{seed}.json')
    with open(path) as f:
        seeds_data.append(json.load(f))

for floor in [0.001, 0.002, 0.003, 0.004, 0.005, 0.007, 0.01, 0.015, 0.02]:
    scores = []
    for data in seeds_data:
        truth = np.array(data['ground_truth'])
        pred = predict_from_initial(data['initial_grid'], floor=floor)
        scores.append(compute_kl(truth, pred))
    print(f"Floor {floor:.3f}: avg={np.mean(scores):.2f} [{', '.join(f'{s:.1f}' for s in scores)}]")
