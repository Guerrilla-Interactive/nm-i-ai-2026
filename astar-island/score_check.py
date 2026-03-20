#!/usr/bin/env python3
"""Score checker: test predictor against Round 2 ground truth."""
import json, numpy as np, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from predictor import Predictor
from config import SIM_TO_CLASS

def compute_kl(truth, pred):
    """Entropy-weighted KL divergence → score."""
    kl_sum, weight_sum = 0.0, 0.0
    for y in range(40):
        for x in range(40):
            p, q = truth[y, x], pred[y, x]
            entropy = -sum(pi * np.log(pi + 1e-12) for pi in p if pi > 0)
            if entropy < 1e-6:
                continue  # skip static cells
            kl = sum(pi * np.log(pi / max(qi, 1e-10)) for pi, qi in zip(p, q) if pi > 0)
            kl_sum += entropy * kl
            weight_sum += entropy
    weighted_kl = kl_sum / weight_sum if weight_sum > 0 else 0
    score = max(0, min(100, 100 * np.exp(-3 * weighted_kl)))
    return score, weighted_kl

predictor = Predictor()
scores = []
for seed in range(5):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f'round2_analysis_seed{seed}.json')
    if not os.path.exists(path):
        continue
    with open(path) as f:
        data = json.load(f)
    truth = np.array(data['ground_truth'])
    initial = data['initial_grid']
    # Predict using only initial state (no observations)
    pred = predictor.predict(initial)
    score, wkl = compute_kl(truth, pred)
    scores.append(score)
    print(f"Seed {seed}: score={score:.2f} (weighted_kl={wkl:.4f})")

if scores:
    print(f"\nAverage: {np.mean(scores):.2f} (was 14.24)")
else:
    print("No round2_analysis_seed*.json files found — cannot compute score.")
