#!/usr/bin/env python3
"""Analyze Round 2 ground truth to derive optimal INITIAL_TRUTH distributions."""
import json, numpy as np, os, sys
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))

# Load all seed files
seeds = []
for seed in range(5):
    path = os.path.join(BASE, f'round2_analysis_seed{seed}.json')
    if os.path.exists(path):
        with open(path) as f:
            seeds.append(json.load(f))

print(f"Loaded {len(seeds)} seed files\n")

# Collect distributions by initial terrain code
by_code = defaultdict(list)  # code -> list of [6] ground truth distributions
by_code_argmax = defaultdict(lambda: defaultdict(list))  # code -> argmax -> list of [6]

for data in seeds:
    initial = data['initial_grid']
    truth = np.array(data['ground_truth'])
    for y in range(40):
        for x in range(40):
            code = initial[y][x]
            dist = truth[y, x]
            by_code[code].append(dist)
            am = int(np.argmax(dist))
            by_code_argmax[code][am].append(dist)

# Print analysis for each code
code_names = {10: "Ocean", 11: "Plains", 0: "Empty", 1: "Settlement", 2: "Port", 3: "Ruin", 4: "Forest", 5: "Mountain"}
class_names = {0: "Empty/Ocean/Plains", 1: "Settlement", 2: "Port", 3: "Ruin", 4: "Forest", 5: "Mountain"}

print("=" * 80)
print("AVERAGE GROUND TRUTH DISTRIBUTIONS BY INITIAL CODE")
print("=" * 80)

initial_truth_dict = {}
for code in sorted(by_code.keys()):
    dists = np.array(by_code[code])
    mean = dists.mean(axis=0)
    std = dists.std(axis=0)
    mn = dists.min(axis=0)
    mx = dists.max(axis=0)

    # Check how many are "static" (entropy < 1e-6)
    entropies = [-np.sum(d * np.log(d + 1e-12)) for d in dists]
    n_static = sum(1 for e in entropies if e < 1e-6)
    n_dynamic = len(dists) - n_static

    name = code_names.get(code, f"Code{code}")
    print(f"\n--- Code {code} ({name}) ---")
    print(f"  Total cells: {len(dists)}, Dynamic: {n_dynamic}, Static: {n_static}")
    print(f"  Mean:  [{', '.join(f'{v:.6f}' for v in mean)}]")
    print(f"  Std:   [{', '.join(f'{v:.6f}' for v in std)}]")
    print(f"  Min:   [{', '.join(f'{v:.6f}' for v in mn)}]")
    print(f"  Max:   [{', '.join(f'{v:.6f}' for v in mx)}]")

    initial_truth_dict[code] = mean.tolist()

# Now show DYNAMIC-ONLY averages (these matter for scoring!)
print("\n\n" + "=" * 80)
print("DYNAMIC-ONLY AVERAGE DISTRIBUTIONS (entropy > 1e-6)")
print("=" * 80)

dynamic_truth_dict = {}
for code in sorted(by_code.keys()):
    dists = np.array(by_code[code])
    # Filter to dynamic cells only
    dynamic_dists = []
    for d in dists:
        entropy = -np.sum(d * np.log(d + 1e-12))
        if entropy > 1e-6:
            dynamic_dists.append(d)

    if not dynamic_dists:
        print(f"\n--- Code {code} ({code_names.get(code, '')}) --- ALL STATIC, skip")
        continue

    dynamic_dists = np.array(dynamic_dists)
    mean = dynamic_dists.mean(axis=0)
    std = dynamic_dists.std(axis=0)

    name = code_names.get(code, f"Code{code}")
    print(f"\n--- Code {code} ({name}) --- {len(dynamic_dists)} dynamic cells")
    print(f"  Mean:  [{', '.join(f'{v:.6f}' for v in mean)}]")
    print(f"  Std:   [{', '.join(f'{v:.6f}' for v in std)}]")
    print(f"  Python: [{', '.join(f'{v:.4f}' for v in mean)}],")

    dynamic_truth_dict[code] = mean.tolist()

# Sub-profiles: by (initial_code, dominant_class)
print("\n\n" + "=" * 80)
print("SUB-PROFILES: (initial_code, dominant_class) -> distribution")
print("=" * 80)

for code in sorted(by_code_argmax.keys()):
    name = code_names.get(code, f"Code{code}")
    print(f"\n--- Code {code} ({name}) ---")
    for am in sorted(by_code_argmax[code].keys()):
        dists = np.array(by_code_argmax[code][am])
        mean = dists.mean(axis=0)
        cn = class_names.get(am, f"Class{am}")
        print(f"  -> Class {am} ({cn}): n={len(dists)}, mean=[{', '.join(f'{v:.4f}' for v in mean)}]")

# Print ready-to-paste dict
print("\n\n" + "=" * 80)
print("READY-TO-PASTE INITIAL_TRUTH (all cells)")
print("=" * 80)
print("INITIAL_TRUTH = {")
for code in sorted(initial_truth_dict.keys()):
    vals = initial_truth_dict[code]
    name = code_names.get(code, "")
    print(f"    {code}: [{', '.join(f'{v:.6f}' for v in vals)}],  # {name}")
print("}")

print("\n\nDYNAMIC-ONLY INITIAL_TRUTH (what matters for scoring)")
print("INITIAL_TRUTH = {")
for code in sorted(dynamic_truth_dict.keys()):
    vals = dynamic_truth_dict[code]
    name = code_names.get(code, "")
    print(f"    {code}: [{', '.join(f'{v:.6f}' for v in vals)}],  # {name}")
print("}")

# Analyze how much variance there is WITHIN each initial code
print("\n\n" + "=" * 80)
print("VARIANCE ANALYSIS: Can we do better than a single distribution per code?")
print("=" * 80)
for code in sorted(by_code.keys()):
    dists = np.array(by_code[code])
    # Filter dynamic
    dynamic = [d for d in dists if -np.sum(d * np.log(d + 1e-12)) > 1e-6]
    if len(dynamic) < 10:
        continue
    dynamic = np.array(dynamic)

    # Compute average KL from mean
    mean = dynamic.mean(axis=0)
    kls = []
    for d in dynamic:
        kl = np.sum(d * np.log(d / (mean + 1e-12) + 1e-12))
        kls.append(kl)

    name = code_names.get(code, f"Code{code}")
    print(f"  Code {code} ({name}): avg KL from mean = {np.mean(kls):.4f}, "
          f"max = {np.max(kls):.4f}, n={len(dynamic)}")
