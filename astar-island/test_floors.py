#!/usr/bin/env python3
"""Quick test of different floor values."""
import json, numpy as np, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Temporarily patch CLASS_FLOORS and test
import predictor as pred_mod
from predictor import Predictor

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

BASE = os.path.dirname(os.path.abspath(__file__))
seed_data = []
for seed in range(5):
    path = os.path.join(BASE, f'round2_analysis_seed{seed}.json')
    if os.path.exists(path):
        with open(path) as f:
            seed_data.append(json.load(f))

# Test different floor configurations
floor_configs = [
    ("current", np.array([0.005, 0.005, 0.003, 0.003, 0.005, 0.001])),
    ("lower",   np.array([0.003, 0.003, 0.002, 0.002, 0.003, 0.001])),
    ("minimal", np.array([0.002, 0.002, 0.001, 0.001, 0.002, 0.0005])),
    ("tiny",    np.array([0.001, 0.001, 0.001, 0.001, 0.001, 0.0005])),
    ("ultra",   np.array([0.0005, 0.0005, 0.0005, 0.0005, 0.0005, 0.0005])),
]

for name, floors in floor_configs:
    pred_mod.CLASS_FLOORS = floors
    predictor = Predictor()
    scores = []
    for data in seed_data:
        truth = np.array(data['ground_truth'])
        initial = data['initial_grid']
        pred = predictor.predict(initial)
        score = compute_kl(truth, pred)
        scores.append(score)
    print(f"{name:10s}: floors={[f'{f:.4f}' for f in floors]} → avg={np.mean(scores):.2f} ({', '.join(f'{s:.2f}' for s in scores)})")
