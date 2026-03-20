# Astar Island — Round 2 Analysis (Updated)

> Generated: 2026-03-20T00:20 (Oslo time)

---

## Round Status

| Round | ID | Status | Weight | Closes (UTC) | Seeds Submitted | Queries Used |
|-------|----|--------|--------|---------------|-----------------|--------------|
| 1 | `71451d74-...` | **completed** | 1.050 | 2026-03-19T20:42 | 0 (MISSED) | 0/50 |
| 2 | `76909e29-...` | **active** (scoring pending) | 1.1025 | 2026-03-19T23:47 | 5/5 | 50/50 |

- **Round 1:** MISSED entirely. Zero submissions, zero queries.
- **Round 2:** All 5 seeds submitted (23:18 UTC, ~29 min before close). Scores NOT YET COMPUTED (all seeds show `score: null`).
- **Round 3:** NOT started yet. Only 2 rounds exist.

---

## Leaderboard (Round 1 Scores — as of 2026-03-20)

The leaderboard is now populated with **Round 1** scores. 117 teams ranked. We are **NOT on the leaderboard** (missed Round 1).

### Top 20

| Rank | Team | Weighted Score | Hot Streak | Verified |
|------|------|---------------|------------|----------|
| 1 | Propulsion Optimizers | 85.51 | 81.44 | Yes |
| 2 | Token Titans | 85.26 | 81.20 | Yes |
| 3 | Kodegutta | 82.48 | 78.56 | Yes |
| 4 | Retriever | 81.63 | 77.74 | No |
| 5 | Skirnir | 80.98 | 77.13 | No |
| 6 | CAL-culated risks | 79.46 | 75.67 | Yes |
| 7 | DS BI | 78.79 | 75.04 | Yes |
| 8 | Make no mistakes | 77.47 | 73.78 | Yes |
| 9 | Aibo | 72.87 | 69.40 | Yes |
| 10 | Popkorn | 72.24 | 68.80 | Yes |
| 11 | Strata Nova | 71.39 | 67.99 | Yes |
| 12 | 123 | 69.31 | 66.01 | Yes |
| 13 | UltraThink | 67.77 | 64.54 | Yes |
| 14 | FlipFlop | 66.66 | 63.49 | Yes |
| 15 | Claud-ius Maximus | 63.54 | 60.51 | Yes |
| 16 | Havvind | 62.41 | 59.44 | Yes |
| 17 | The vector space | 62.28 | 59.31 | Yes |
| 18 | Neutrophiles | 61.14 | 58.23 | Yes |
| 19 | Reliable | 60.50 | 57.61 | Yes |
| 20 | Ave Christus Rex | 59.38 | 56.55 | Yes |

### Score Distribution
- **Top 5:** 80.98 — 85.51 (tight cluster)
- **Median (rank ~58):** ~32.3
- **Bottom teams:** Many at exactly 4.97 (likely default/baseline submissions)
- **Zero scores:** 3 teams at 0.0

### Target
To be competitive, we need **>70** per round (top 10 territory). Top teams are at **85+** — very strong.

---

## Our Prediction Quality Analysis

### Submission Details
All 5 seeds submitted between 23:18:08 and 23:18:39 UTC.

### Confidence Distribution (from API confidence_grid)
| Seed | Avg Confidence | Cells at 0.40-0.50 | Cells at 0.70-0.80 | Cells at 0.90+ |
|------|---------------|---------------------|---------------------|----------------|
| 0 | 0.783 | 317 (~20%) | 269 (~17%) | 1001 (~63%) |
| 1 | 0.792 | 273 (~17%) | 284 (~18%) | 1022 (~64%) |
| 2 | 0.792 | 282 (~18%) | 250 (~16%) | 1048 (~66%) |
| 3 | 0.793 | 271 (~17%) | 269 (~17%) | 1037 (~65%) |
| 4 | 0.762 | 384 (~24%) | 255 (~16%) | 937 (~59%) |

### Argmax Class Distribution (per seed)
| Seed | Ocean/Plains | Settlement | Port | Ruin | Forest | Mountain |
|------|-------------|------------|------|------|--------|----------|
| 0 | 971 | 298 | 13 | 19 | 269 | 30 |
| 1 | 983 | 258 | 21 | 15 | 284 | 39 |
| 2 | 1021 | 251 | 20 | 31 | 250 | 27 |
| 3 | 1022 | 249 | 23 | 22 | 269 | 15 |
| 4 | 910 | 347 | 24 | 37 | 255 | 27 |

---

## Scoring Formula

```
KL(p || q) = Σ pᵢ × log(pᵢ / qᵢ)     (per cell, p=truth, q=ours)

weighted_kl = Σ entropy(cell) × KL(truth, pred)
              ─────────────────────────────────
                      Σ entropy(cell)

score = max(0, min(100, 100 × exp(-3 × weighted_kl)))
```

### Key Properties
1. **Only dynamic cells matter.** Static ocean/mountain have near-zero entropy → zero weight in scoring. Our score is determined entirely by the ~300-600 dynamic cells (settlements, forests near civ, ruins, ports).

2. **Never predict 0.0.** KL divergence → ∞ if truth > 0 and prediction = 0. Our floor of 0.01 prevents this.

3. **Exponential scoring curve:**

| weighted_kl | score |
|-------------|-------|
| 0.00 | 100.0 |
| 0.05 | 86.1 |
| 0.10 | 74.1 |
| 0.15 | 63.8 |
| 0.20 | 54.9 |
| 0.30 | 40.7 |
| 0.50 | 22.3 |
| 1.00 | 5.0 |

Top teams at ~85 corresponds to weighted_kl ≈ 0.05. Very precise predictions.

---

## Improvement Recommendations (Priority Order)

### 1. CRITICAL: Don't Miss Rounds
Round 1 was missed (score = 0). Every missed round is devastating. **Monitor continuously for new rounds and run solver immediately.**

### 2. Observation Strategy (HIGH IMPACT)
Currently: 10 queries per seed × 15×15 viewport = 2250 cell observations, but with overlap ~1375 unique cells observed out of 1600.

**Improvements:**
- **Minimize overlap** — spread queries to maximize coverage (nearly all 1600 cells observable with 10 non-overlapping 15×15 queries covering 2250 cells)
- **Focus on dynamic regions** — Initial state reveals where ocean/mountains are. Query the civilized zones, not deep ocean.
- **Multiple observations of volatile cells** — If a cell is settlement in one query and ruin in another, that directly reveals the probability distribution.

### 3. Confidence Calibration (HIGH IMPACT)
Current values may be too high for volatile cells. The top teams at score 85 have weighted_kl ≈ 0.05.

**Current OBSERVED_CONFIDENCE:**
- Mountain: 0.99, Ocean: 0.88, Forest: 0.78
- Port: 0.42, Settlement: 0.40, Ruin: 0.32

**Recommendations:**
- **Settlement confidence too high at 0.40.** Ground truth likely shows settlements at only 25-35% probability due to high volatility. Lower to 0.30-0.35.
- **Spread remaining probability more toward ruin/forest** — the settlement↔ruin↔forest transition triangle dominates dynamic cells.
- **Raise floor to 0.02** for volatile cells — safer against KL blowup from underestimated rare classes.

### 4. Multi-Observation Empirical Distributions (HIGH IMPACT)
If the same cell is observed across multiple queries with different outcomes (e.g., settlement 6/10 times, ruin 3/10, forest 1/10), use that empirical distribution directly instead of heuristic confidence values. This would be the single biggest improvement for cells with multiple observations.

### 5. Unobserved Cell Heuristics (MEDIUM IMPACT)
~225+ unobserved cells use purely initial-state-based predictions. These are inherently less accurate:
- **Maximize coverage** to reduce unobserved count
- **Use neighbor observations** to inform unobserved cell predictions
- **Lower confidence on unobserved volatile cells** (settlements/ruins)

### 6. Context-Aware Predictions (MEDIUM IMPACT)
- Settlements near ports: higher port transition probability
- Ruins near active settlements: higher rebuild probability
- Forest near civilization edge: higher clearing probability
- Use distance-to-nearest-observed-X as a signal

---

## Gap Analysis vs Top Teams

| Factor | Our Approach | Top Teams (likely) |
|--------|-------------|-------------------|
| Observation coverage | Good (50/50 queries) | Same budget |
| Query placement | Unknown optimization | Likely targeting dynamic zones |
| Confidence calibration | Fixed heuristics | Possibly empirically tuned or simulation-based |
| Multi-observation | Basic (obs_count bonus) | Likely using empirical distributions |
| Transition model | Heuristic spread weights | Possibly learned from simulation data |

The ~15-point gap between a score of 70 and 85 comes down to getting the **probability distributions right on dynamic cells**. Small improvements in KL divergence have exponential impact on score.

---

## Next Actions

1. **Watch for Round 3** — `watch_for_round3.py` exists. Run it continuously.
2. **Check Round 2 scores** — Re-query `/my-rounds` after scoring completes.
3. **Optimize query placement** — Pre-analyze initial state to avoid querying ocean/mountains.
4. **Implement empirical distributions** from multi-observation data.
5. **Lower settlement/ruin confidence** and redistribute probability mass.
