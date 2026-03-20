# NM i AI 2026 — Competition Strategy Analysis

> **Competition:** March 19 18:00 CET → March 22 15:00 CET (69 hours)
> **Prize pool:** 1,000,000 NOK
> **Research date:** 2026-03-19

---

## 1. Historical Context

### NM i AI 2025 (First Norwegian Championship)
- 160+ students, 85+ teams, 1 week (Aug 1-8), 50,000 NOK prize pool
- **Tasks:** Race Car simulation, Emergency Healthcare RAG, Tumor Segmentation
- **Winner:** "Attention Heads" (NTNU) — described it as "intense and rewarding"
- **Pattern:** One simulation/RL task, one NLP task, one computer vision/ML task

### Danish Championships (Precursor, same organizers — Ambolt AI)
- **DM i AI 2024:** Traffic Simulation, CT Inpainting, Cell Classification
- **DM i AI 2023:** Lunar Lander, AI Text Detector, Tumor Segmentation
- **DM i AI 2022:** Also 3 tasks, similar mix

### Patterns from Past Competitions
1. **Always 3 tasks** — diverse disciplines (vision, NLP, simulation/RL)
2. **Time-limited model execution** — inference timeouts (10-60s typically)
3. **Pre-built environments** — contestants don't set up infra from scratch
4. **Winning teams excelled across ALL tasks** — not just one
5. **Team PER (2024 DM)** won by being "precise and error-free across ALL three cases"

### Key Difference: NM i AI 2026 vs Previous
- **69 hours** (not 1 week) — much more compressed
- **1,000,000 NOK** (20× the 2025 prize pool) — much higher stakes
- **Tier system** on Tripletex — rewards patience and late-game execution
- **Open to all** (not just students) — stronger competition expected
- **Live API submissions** — iterative improvement possible
- **GCP infrastructure provided** — real cloud deployment, not just notebooks

---

## 2. Task-by-Task Analysis

### Task 1: NorgesGruppen — Object Detection

| Aspect | Assessment |
|--------|-----------|
| **Type** | Computer Vision (supervised, fine-tuning) |
| **Difficulty floor** | Low — pre-trained YOLO + training data provided |
| **Difficulty ceiling** | Medium-High — 356 categories with only 248 images |
| **Time to baseline** | 2-4 hours (YOLO fine-tune runs automatically) |
| **Time to competitive** | 8-16 hours (augmentation, ensemble, two-stage pipeline) |
| **Compute dependency** | High — GPU training required (L4 24GB provided) |
| **Iterative improvement** | Slow — each training run takes 1-3 hours |
| **Scoring** | 70% detection + 30% classification |

**Expected points-per-hour:**
- Hours 1-4: HIGH (baseline model gives immediate score jump from 0 to ~50-60%)
- Hours 4-16: MEDIUM (diminishing returns on augmentation/tuning, +10-20%)
- Hours 16+: LOW (ensemble tricks for +2-5%, many hours per marginal gain)

**Minimum viable submission:** Fine-tune YOLOv8m on training data with default settings (~2h training). Expected score: 50-65%.

**Maximum potential:** Two-stage (YOLO detect + EfficientNet classify) + ensemble + TTA. Expected score: 70-85%.

**Risk:** Training takes real time. A failed experiment costs 1-3 hours. Limited to sandbox GPU.

---

### Task 2: Tripletex — AI Accounting Agent

| Aspect | Assessment |
|--------|-----------|
| **Type** | LLM Agent / API Integration |
| **Difficulty floor** | Medium — need working HTTPS endpoint + LLM integration |
| **Difficulty ceiling** | Very High — 30 tasks × 7 languages × efficiency optimization |
| **Time to baseline** | 4-6 hours (Cloud Run + Gemini + basic task handling) |
| **Time to competitive** | 12-24 hours (all task types, efficiency optimization) |
| **Compute dependency** | Low — I/O bound (API calls) |
| **Iterative improvement** | Fast — deploy → test → fix → redeploy in minutes |
| **Scoring** | Correctness × Tier multiplier × Efficiency bonus (0-6 per task) |

**Expected points-per-hour:**
- Hours 1-6: MEDIUM (infra setup, first few tasks working)
- Hours 6-20: HIGH (each new task type adds guaranteed points)
- Hours 20-48: HIGH (Tier 2 opens Friday — 2× multiplier on new tasks)
- Hours 48-69: VERY HIGH (Tier 3 opens Saturday — 3× multiplier, complex tasks worth most)

**Minimum viable submission:** POST /solve endpoint that handles 5-10 basic task types. Expected score: ~15-30 across all tasks.

**Maximum potential:** All 30 tasks with perfect efficiency on Tier 3 = theoretical 180.0 (realistic: 80-120).

**Strategic insight:** This task **rewards late-game work disproportionately**. Tier 3 tasks are worth 3× with efficiency bonus up to 6.0 per task. A team that nails Tier 3 on Saturday can leapfrog teams that focused elsewhere.

**Risk:** Rate limits (5 submissions/task/day). Can't brute-force. Must test against sandbox thoroughly before submitting.

---

### Task 3: Astar Island — World Simulation

| Aspect | Assessment |
|--------|-----------|
| **Type** | Algorithmic / Probabilistic Prediction |
| **Difficulty floor** | Low-Medium — uniform probability is a valid (bad) baseline |
| **Difficulty ceiling** | High — optimal observation strategy + Bayesian inference |
| **Time to baseline** | 1-2 hours (submit uniform probabilities) |
| **Time to competitive** | 6-12 hours (smart observation + inference) |
| **Compute dependency** | Very Low — pure algorithmic |
| **Iterative improvement** | Medium — limited by 50 queries/round budget |
| **Scoring** | KL divergence → score = 100 × e^(-KL) |

**Expected points-per-hour:**
- Hours 1-2: HIGH (any informed prediction beats uniform, big score jump)
- Hours 2-8: MEDIUM (optimize observation strategy, improve inference)
- Hours 8+: LOW (diminishing returns, limited by observation budget)

**Minimum viable submission:** Submit uniform probabilities (1/6 each class, or use observed frequencies). Score: probably 20-40.

**Maximum potential:** Optimal query placement + Bayesian terrain propagation model. Score: 60-90.

**Key constraint:** Only 50 queries shared across 5 seeds. Each query reveals a 15×15 viewport of a 40×40 map. That's (40/15)² ≈ 7 non-overlapping views per seed if spread evenly = 50/5 = 10 queries per seed. Can cover ~56% of the map per seed (10 × 225 = 2250 cells out of 1600, with overlap). The challenge is *where* to look, not how much.

**Risk:** Low ceiling compared to other tasks? Hard to know without seeing actual scoring ranges.

---

## 3. Points-Per-Hour Comparison

| Task | Hours 1-6 | Hours 6-20 | Hours 20-48 | Hours 48-69 |
|------|-----------|------------|-------------|-------------|
| **NorgesGruppen** | ★★★★ | ★★★ | ★★ | ★ |
| **Tripletex** | ★★ | ★★★ | ★★★★ | ★★★★★ |
| **Astar Island** | ★★★★ | ★★ | ★ | ★ |

**Legend:** ★ = low points/hour, ★★★★★ = highest points/hour

---

## 4. Strategic Questions Answered

### Go deep on 1-2 tasks or spread across all 3?

**Answer: Spread across all 3, but with time-weighted allocation.**

Evidence from past competitions: winning team PER (DM i AI 2024) won by being "precise and error-free across ALL three cases." Going deep on one task has severe diminishing returns. The leaderboard likely weights all tasks, so zero on one task is catastrophic.

However, Tripletex's tier multiplier system creates a **temporal asymmetry** — work on Tripletex becomes 2-3× more valuable as the competition progresses. This means:
- Front-load NorgesGruppen and Astar Island (diminishing returns early → get baseline fast)
- Back-load Tripletex (increasing returns → invest most time here after Tier 2/3 open)

### What's the minimum viable submission for each task?

| Task | MVP | Time | Expected % of Max |
|------|-----|------|-------------------|
| NorgesGruppen | YOLOv8m fine-tune, default settings | 3-4h | 60-70% |
| Tripletex | Cloud Run + Gemini + 5 task types | 5-6h | 15-25% |
| Astar Island | Observe center + edges, uniform prior | 2-3h | 30-50% |

### Which task has the lowest floor?

**Astar Island** — submitting educated-guess probabilities based on a few observations requires almost no infrastructure. Just API calls to observe + submit a JSON tensor.

**NorgesGruppen** — running the YOLO training script is nearly turnkey with provided infrastructure.

### Which task has the highest ceiling?

**Tripletex** — by far. With 30 tasks × max 6.0 points each = 180 theoretical maximum. Even realistically, a well-built agent can score 80-120+ points. The tier multipliers and efficiency bonus make this the biggest points pool.

NorgesGruppen and Astar Island have fixed, bounded scoring (percentage-based), while Tripletex scales with task coverage and quality.

### How should we allocate our 69 hours?

See recommended schedule below.

---

## 5. Recommended Time Allocation

### Phase 1: Parallel Sprint (Hours 0-8, Wed evening → Thu morning)

| Worker | Task | Goal |
|--------|------|------|
| Worker A | NorgesGruppen | Start YOLOv8m training. Set up data, kick off 200-epoch run. Submit baseline. |
| Worker B | Tripletex | Set up Cloud Run + FastAPI. Integrate Gemini. Get first 3 task types working (create employee, customer, product). |
| Worker C | Astar Island | Build observation + submission pipeline. Implement smart query placement. Submit first prediction. |
| Worker D | Strategy/Research | Explore Tripletex API in sandbox. Map task types. Read documentation. |

**Expected outcome:** Baseline scores on all 3 tasks. Training running in background.

### Phase 2: Deepen Baselines (Hours 8-24, Thu)

| Worker | Task | Goal |
|--------|------|------|
| Worker A | NorgesGruppen | Analyze first training results. Try YOLOv8l/x. Heavy augmentation. Submit improved model. |
| Worker B+D | Tripletex | Expand to 15-20 task types. Test all 7 languages. Deploy and submit for Tier 1 scoring. |
| Worker C | Astar Island | Refine prediction model. Bayesian inference from observations. Optimize query placement. |

**Expected outcome:** NorgesGruppen at 65-75%. Tripletex handling most Tier 1 tasks. Astar at 40-60%.

### Phase 3: Tripletex Focus + NorgesGruppen Polish (Hours 24-48, Fri)

**Tier 2 opens early Friday — 2× multiplier!**

| Worker | Task | Goal |
|--------|------|------|
| Worker A | NorgesGruppen | Final model improvements: ensemble, TTA, two-stage pipeline. Last submission. |
| Worker B+C+D | Tripletex | ALL hands on Tier 2 tasks. Multi-step workflows. Invoice+payment, credit notes, project billing. Efficiency optimization. |

**Expected outcome:** NorgesGruppen at 70-80% (final). Tripletex scoring on Tier 1 + Tier 2 tasks.

### Phase 4: Tripletex Tier 3 Blitz (Hours 48-69, Sat)

**Tier 3 opens early Saturday — 3× multiplier!**

| Worker | Task | Goal |
|--------|------|------|
| ALL | Tripletex | Bank reconciliation, ledger corrections, year-end closing. These are worth 3× with up to 6.0 points each. File processing (CSV/PDF) support. |
| (spare cycles) | Astar Island | Final optimization if low-hanging fruit remains |

**Expected outcome:** Maximizing the highest-value tasks in the competition.

---

## 6. Key Strategic Principles

### 1. "T3 Tripletex Points Are Worth 6× T1 Points"
A perfect Tier 3 task with best efficiency = 6.0 points.
A perfect Tier 1 task with best efficiency = 2.0 points.
Time spent on Tier 3 Saturday is 3× more productive than Tier 1 Wednesday.

### 2. "Submit Early, Submit Often"
- Best score per task is kept forever — bad submissions never hurt
- Rate limit: 5/task/day (verified). Plan submissions carefully
- Get baseline scores on Day 1 to establish floor

### 3. "NorgesGruppen Is Front-Loaded, Tripletex Is Back-Loaded"
- Start YOLO training immediately (GPU time is a scarce resource)
- Training runs in background while humans work on Tripletex
- NorgesGruppen diminishing returns after Day 2

### 4. "Efficiency Bonus Is The Multiplier"
- Tripletex efficiency bonus up to 2× only applies to PERFECT correctness
- Focus on getting 100% correctness first, THEN minimize API calls
- Every 4xx error costs efficiency points — validate before calling

### 5. "Astar Island Is The Quick Win"
- Lowest infrastructure overhead
- Can get meaningful score in 2-3 hours
- But ceiling may be lower — don't over-invest

### 6. "Test in Sandbox, Submit to Competition"
- Tripletex gives fresh account per submission — test against sandbox first
- Each wasted submission = one less chance that day
- Build local test harness that mimics competition conditions

---

## 7. Risk Matrix

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| NorgesGruppen training fails/bugs | Medium | Medium | Use proven Ultralytics pipeline, test locally first |
| Tripletex unknown task types | High | High | Plan-execute fallback architecture for unknown tasks |
| Tier 3 tasks require capabilities we haven't built | Medium | Very High | Reserve Saturday morning for rapid development |
| Rate limit prevents iteration | Medium | High | Test extensively in sandbox before submitting |
| Cloud Run deployment issues | Low | High | Deploy and test endpoint early, keep warm instance |
| Gemini rate limits / outages | Low | High | Have Claude API as backup LLM |
| Team coordination overhead | Medium | Medium | Clear task ownership, async communication |
| Astar Island scoring is poorly understood | Medium | Low | Get baseline early, don't over-invest |

---

## 8. Expected Final Score Distribution

| Task | Pessimistic | Realistic | Optimistic |
|------|------------|-----------|-----------|
| NorgesGruppen | 45-55% | 65-75% | 75-85% |
| Tripletex (total) | 30-40 pts | 60-80 pts | 90-120 pts |
| Astar Island | 25-40 | 45-65 | 65-85 |

**Where we win or lose:** Tripletex has the widest scoring range and is the primary differentiator. A team scoring 100+ on Tripletex will almost certainly be in the top tier.

---

## 9. Summary Recommendation

**Primary strategy: "Fast baselines everywhere, then go all-in on Tripletex for Tier 2/3."**

1. **Wednesday evening:** Parallel setup on all 3 tasks. Start YOLO training immediately.
2. **Thursday:** Complete baselines. Build Tripletex agent covering Tier 1 tasks.
3. **Friday:** NorgesGruppen final submission. ALL hands on Tripletex Tier 2.
4. **Saturday:** ALL hands on Tripletex Tier 3 (3× multiplier = maximum points per hour).

The tier multiplier system is the single most important strategic factor. A team that perfectly solves 5 Tier 3 tasks on Saturday outscores a team that perfectly solves 15 Tier 1 tasks over the entire competition.

---

## Sources
- [NM i AI 2026 Official Site](https://ainm.no/en)
- [NM i AI 2026 App & Docs](https://app.ainm.no/docs/game)
- [AI Championship 2025 (NORA)](https://www.nora.ai/competitions/ai-championship-2025/ai-championship.html)
- [Attention Heads Winning Team (2025)](https://www.nora.ai/news/2025/studentteam-attention-heads-fra-ntnu-ble-historien.html)
- [Guide by 2024 Danish Champions](https://norwegian-ai-championships-guide.lovable.app/)
- [DM i AI 2023 GitHub](https://github.com/amboltio/DM-i-AI-2023)
- [DM i AI 2024 Winners](https://di.ku.dk/english/news/2024/students-from-the-department-of-computer-science-secure-the-title-of-danish-national-champions-in-ai/)
