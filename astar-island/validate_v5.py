#!/usr/bin/env python3
"""
Validate solver_v5 group-prior approach against R2 and R3 ground truth.
Tests both in-sample and cross-regime scenarios.
Also experiments with floor values to find optimal.
"""
import json, sys, os
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from config import GRID_SIZE, NUM_CLASSES
from solver_v5 import predict_with_group_priors, is_coastal

def score_prediction(pred, gt_data):
    """Score a 40x40x6 prediction against ground truth."""
    gt = np.array(gt_data)
    total_kl = 0.0
    total_weight = 0.0

    for y in range(GRID_SIZE):
        for x in range(GRID_SIZE):
            p = gt[y, x]
            q = pred[y, x]

            entropy = -np.sum(p[p > 0] * np.log(p[p > 0]))
            if entropy < 1e-10:
                continue

            q_safe = np.maximum(q, 1e-15)
            kl = np.sum(p[p > 0] * np.log(p[p > 0] / q_safe[p > 0]))
            total_kl += entropy * kl
            total_weight += entropy

    weighted_kl = total_kl / total_weight if total_weight > 0 else 0
    score = 100 * np.exp(-3 * weighted_kl)
    return score, weighted_kl


def main():
    r2_priors = json.load(open('data/group_priors_r2.json'))
    r3_priors = json.load(open('data/group_priors_r3.json'))

    r2_files = [json.load(open('data/r2_analysis_seed%d.json' % i)) for i in range(5)]
    r3_files = [json.load(open('data/r3_analysis_seed%d.json' % i)) for i in range(5)]

    # Test different floor values
    print("=== Floor Optimization ===")
    for floor in [0.001, 0.002, 0.005, 0.008, 0.01, 0.015, 0.02]:
        r2_scores = []
        r3_scores = []
        for seed in range(5):
            pred = predict_with_group_priors(r2_files[seed]['initial_grid'], r2_priors, floor=floor)
            s, _ = score_prediction(pred, r2_files[seed]['ground_truth'])
            r2_scores.append(s)

            pred = predict_with_group_priors(r3_files[seed]['initial_grid'], r3_priors, floor=floor)
            s, _ = score_prediction(pred, r3_files[seed]['ground_truth'])
            r3_scores.append(s)

        print("  floor=%.3f: R2=%.2f R3=%.2f avg=%.2f" % (
            floor, np.mean(r2_scores), np.mean(r3_scores),
            (np.mean(r2_scores) + np.mean(r3_scores)) / 2))

    # Best floor detailed results
    print("\n=== Detailed Results (floor=0.005) ===")
    floor = 0.005

    print("\nR2 priors on R2 (in-sample):")
    for seed in range(5):
        pred = predict_with_group_priors(r2_files[seed]['initial_grid'], r2_priors, floor=floor)
        s, kl = score_prediction(pred, r2_files[seed]['ground_truth'])
        print("  Seed %d: score=%.2f kl=%.4f" % (seed, s, kl))

    print("\nR3 priors on R3 (in-sample):")
    for seed in range(5):
        pred = predict_with_group_priors(r3_files[seed]['initial_grid'], r3_priors, floor=floor)
        s, kl = score_prediction(pred, r3_files[seed]['ground_truth'])
        print("  Seed %d: score=%.2f kl=%.4f" % (seed, s, kl))

    print("\nR2 priors on R3 (cross-regime, WRONG model):")
    for seed in range(5):
        pred = predict_with_group_priors(r3_files[seed]['initial_grid'], r2_priors, floor=floor)
        s, kl = score_prediction(pred, r3_files[seed]['ground_truth'])
        print("  Seed %d: score=%.2f kl=%.4f" % (seed, s, kl))

    print("\nR3 priors on R2 (cross-regime, WRONG model):")
    for seed in range(5):
        pred = predict_with_group_priors(r2_files[seed]['initial_grid'], r3_priors, floor=floor)
        s, kl = score_prediction(pred, r2_files[seed]['ground_truth'])
        print("  Seed %d: score=%.2f kl=%.4f" % (seed, s, kl))

    # LOO-CV
    print("\n=== Leave-One-Out Cross-Validation ===")
    from build_group_priors import build_priors, score_priors

    for round_name, files_list in [("R2", ['data/r2_analysis_seed%d.json' % i for i in range(5)]),
                                     ("R3", ['data/r3_analysis_seed%d.json' % i for i in range(5)])]:
        loo_scores = []
        for held_out in range(5):
            train = [f for i, f in enumerate(files_list) if i != held_out]
            priors = build_priors("loo", train)

            test_data = json.load(open(files_list[held_out]))
            pred = predict_with_group_priors(test_data['initial_grid'], priors, floor=floor)
            s, _ = score_prediction(pred, test_data['ground_truth'])
            loo_scores.append(s)

        print("  %s LOO-CV: %s avg=%.2f" % (
            round_name, ['%.1f' % s for s in loo_scores], np.mean(loo_scores)))


if __name__ == '__main__':
    main()
