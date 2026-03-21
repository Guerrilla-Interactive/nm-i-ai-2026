# Competitive Scoring Analysis — Tripletex Agent

**Date:** 2026-03-21
**Our score:** 22.40 pts (rank #161)
**Top team:** 48.98 pts (T1=15.25, T2=33.73, T3=0.00)

---

## 1. Theoretical Maximum Scores

| Tier | Tasks | Max/task (no bonus) | Max/task (w/ bonus) | Total (no bonus) | Total (w/ bonus) |
|------|-------|---------------------|---------------------|------------------|------------------|
| T1 (x1) | 10 | 1.0 | 2.0 | 10.0 | 20.0 |
| T2 (x2) | 12 | 2.0 | 4.0 | 24.0 | 48.0 |
| T3 (x3) | 8 | 3.0 | 6.0 | 24.0 | 48.0 |
| **Total** | **30** | | | **58.0** | **116.0** |

---

## 2. Top Team Analysis

**Top team: 48.98 pts** (T1=15.25, T2=33.73, T3=0.00)

### T1 Breakdown (15.25 / 20.0 max)
- 15.25 out of 20.0 = **76.3% of max** (with efficiency bonuses)
- This means they likely have 100% correctness on most T1 tasks WITH efficiency bonuses
- If they scored 2.0 on 7 tasks + partial on 3: 14.0 + 1.25 = 15.25
- Or: perfect (2.0) on all 10 but with varying efficiency: avg 1.525/task

### T2 Breakdown (33.73 / 48.0 max)
- 33.73 out of 48.0 = **70.3% of max** (with efficiency bonuses)
- If perfect+efficient on 8 tasks: 32.0 + 1.73 partial = 33.73
- They likely nail most T2 tasks with good efficiency

### T3 = 0.00 for ALL teams
- **NO team has scored ANY T3 points yet**
- T3 tasks: BANK_RECONCILIATION, ERROR_CORRECTION, YEAR_END_CLOSING, ENABLE_MODULE, RUN_PAYROLL, REGISTER_SUPPLIER_INVOICE (+ 2 more)
- **First-mover advantage is massive** — even partial T3 scores give rank improvement

---

## 3. Our Score Breakdown (Estimated)

Based on grader log data, our confirmed scores:

| Task Type | Tier | Best Score | Max Possible | Gap | Status |
|-----------|------|------------|-------------|-----|--------|
| CREATE_PRODUCT | T1 | 1.0 (7/7) | 2.0 | 1.0 | Correctness perfect, efficiency gap |
| CREATE_INVOICE | T1 | ~0.7 | 2.0 | 1.3 | Partially working |
| CREATE_CUSTOMER | T1 | ~0.7 | 2.0 | 1.3 | Working but field gaps |
| CREATE_DEPARTMENT | T1 | ~0.5 | 2.0 | 1.5 | Batch failures observed |
| CREATE_EMPLOYEE | T1 | 0.0 | 2.0 | 2.0 | **startDate 422 error** |
| PROJECT_WITH_CUSTOMER | T2 | ~1.2 | 4.0 | 2.8 | Working but incomplete |
| INVOICE_WITH_PAYMENT | T2 | 0.57 (2/7) | 4.0 | 3.43 | Misclassification + VAT bugs |
| CREATE_PRODUCT (T1 eff) | T1 | 1.0 | 2.0 | 1.0 | Need efficiency bonus |
| *All other T1* | T1 | 0.0 | 2.0 ea | ~8.0 | Not yet scored |
| *All other T2* | T2 | 0.0 | 4.0 ea | ~36.0 | Not yet scored |
| *All T3* | T3 | 0.0 | 6.0 ea | ~48.0 | Not yet scored |

**Estimated total: ~4.17 from Tripletex** (rest of 22.40 from Astar + NorgesGruppen)

---

## 4. Point Recovery Per Fix

### Fix A: CREATE_EMPLOYEE startDate (35 failures observed)

**Root cause:** POST /employee returns 422 — `startDate` field missing/malformed
**Fix complexity:** LOW (add `"startDate": "2026-03-21"` default to POST body)
**Dev time:** ~15 minutes

| Metric | Value |
|--------|-------|
| Checks affected | 5/5 (employee found + name + email + admin role) — ALL fail if 422 |
| T1 score recovery | 0.0 → 1.0 (perfect) or 1.0-2.0 (with efficiency) |
| **Points gained** | **+1.0 to +2.0** |
| Points per hour | **4.0 - 8.0 pts/hr** |

**This is the single highest-ROI fix.** Every CREATE_EMPLOYEE submission currently scores 0.

### Fix B: INVOICE_WITH_PAYMENT VAT calculation

**Root cause:** Hardcoded 1.25x VAT multiplier; mixed ex/inc-VAT math wrong
**Fix:** Fetch invoice total from API after creation, use as paidAmount
**Dev time:** ~30 minutes

| Metric | Value |
|--------|-------|
| Current score | 0.57 (2/7 checks) |
| After fix | ~1.0 (7/7 = perfect base) |
| T2 multiplier | x2 |
| **Points gained** | **+1.43 to +3.43** (base to bonus range) |
| Points per hour | **2.9 - 6.9 pts/hr** |

### Fix C: _find_employee fallthrough (returns wrong employee)

**Root cause:** Returns `employees[0]` when no match found
**Fix:** Return None when lastName specified but unmatched
**Dev time:** ~15 minutes

| Metric | Value |
|--------|-------|
| Tasks affected | UPDATE_EMPLOYEE, DELETE_EMPLOYEE, SET_EMPLOYEE_ROLES, CREATE_TRAVEL_EXPENSE |
| Score impact per task | Prevents scoring 0 (wrong entity) vs scoring partial/full |
| T1 tasks: 3 × ~1.0 | **+3.0** |
| T2 tasks: 1 × ~2.0 | **+2.0** |
| **Points gained** | **+1.0 to +5.0** (cascading across tasks) |
| Points per hour | **4.0 - 20.0 pts/hr** |

### Fix D: Batch department creation (UNKNOWN classification)

**Root cause:** Keyword fallback can't handle "Create three departments"
**Fix:** Add batch detection regex in keyword fallback
**Dev time:** ~20 minutes

| Metric | Value |
|--------|-------|
| Current score | 0.0 (classified as UNKNOWN) |
| After fix | ~1.0 (3/3 departments) |
| T1 score | **+1.0 to +2.0** |
| Points per hour | **3.0 - 6.0 pts/hr** |

### Fix E: CREATE_INVOICE vs INVOICE_EXISTING_CUSTOMER misclassification

**Root cause:** Keyword classifier maps "faktura til kunde" → INVOICE_EXISTING_CUSTOMER
**Fix:** Both executors handle customer creation, so impact is LOW
**Dev time:** ~10 minutes (if needed at all)

| Metric | Value |
|--------|-------|
| **Points gained** | **+0.0 to +0.5** (executors handle both cases) |
| Points per hour | **0 - 3.0 pts/hr** |

### Fix F: Payment amount validation (None check)

**Root cause:** No validation before API call; `amount=None` passes through
**Fix:** Early validation + fetch invoice total from API
**Dev time:** ~15 minutes (combined with Fix B)

| Metric | Value |
|--------|-------|
| Tasks affected | REGISTER_PAYMENT (T2) |
| **Points gained** | **+1.0 to +4.0** |
| Points per hour | **4.0 - 16.0 pts/hr** |

### Fix G: Org number dash stripping

**Root cause:** `.replace("-", "")` missing in extraction
**Fix:** One line change
**Dev time:** ~5 minutes

| Metric | Value |
|--------|-------|
| Tasks affected | CREATE_CUSTOMER, INVOICE_WITH_PAYMENT, PROJECT_WITH_CUSTOMER |
| **Points gained** | **+0.3 to +1.0** |
| Points per hour | **3.6 - 12.0 pts/hr** |

### Fix H: T3 task implementations (FIRST MOVER)

**Status:** All 4+ T3 executors already implemented but untested against sandbox!
**Fix:** Test and fix whatever breaks
**Dev time:** ~2-4 hours for all T3 tasks

| Metric | Value |
|--------|-------|
| Tasks | BANK_RECONCILIATION, ERROR_CORRECTION, YEAR_END_CLOSING, ENABLE_MODULE, RUN_PAYROLL, REGISTER_SUPPLIER_INVOICE |
| T3 multiplier | x3 |
| Even 50% correctness on 4 tasks | 4 × 0.5 × 3 = **+6.0** |
| Perfect on 4 tasks | 4 × 3.0 = **+12.0** |
| With efficiency on 4 tasks | 4 × 6.0 = **+24.0** |
| **Points gained** | **+6.0 to +24.0** |
| Points per hour | **3.0 - 12.0 pts/hr** |
| **NO OTHER TEAM HAS T3 POINTS** | First mover sets efficiency benchmarks! |

---

## 5. T2 Gap Analysis: Us vs Top Team

**Gap:** 33.73 - ~1.77 (our estimated T2) = ~31.96 pts

| T2 Task Type | Top Team (est.) | Us (est.) | Gap | Fix Difficulty |
|--------------|----------------|-----------|-----|---------------|
| INVOICE_WITH_PAYMENT | ~3.5 | 0.57 | 2.93 | Fix B (VAT calc) |
| REGISTER_PAYMENT | ~3.5 | 0.0 | 3.50 | Fix F (amount validation) |
| INVOICE_EXISTING_CUSTOMER | ~3.5 | 0.0 | 3.50 | Already works, need submission |
| CREATE_TRAVEL_EXPENSE | ~3.0 | 0.0 | 3.00 | Field mapping issues |
| PROJECT_WITH_CUSTOMER | ~3.5 | ~1.2 | 2.30 | Mostly working |
| CREATE_CONTACT | ~3.0 | 0.0 | 3.00 | Customer lookup fix |
| CREATE_CREDIT_NOTE | ~3.0 | 0.0 | 3.00 | Invoice lookup |
| PROJECT_BILLING | ~2.5 | 0.0 | 2.50 | Classifier misses it |
| FIND_CUSTOMER | ~2.5 | 0.0 | 2.50 | Need response format |
| DELETE_TRAVEL_EXPENSE | ~2.5 | 0.0 | 2.50 | 403 handling |
| UPDATE_PROJECT | ~2.0 | 0.0 | 2.00 | Version management |
| DELETE_PROJECT | ~2.0 | 0.0 | 2.00 | 403 handling |

**Biggest T2 opportunities:** REGISTER_PAYMENT, INVOICE_EXISTING_CUSTOMER, INVOICE_WITH_PAYMENT — these 3 alone could recover ~10 pts.

---

## 6. T3 First-Mover Opportunity

**Current state:** T3 = 0.00 for ALL teams

If we deploy working T3 handlers:
- Even 30% correctness on 6 tasks = 6 × 0.3 × 3 = **+5.4 pts**
- 50% correctness on 6 tasks = 6 × 0.5 × 3 = **+9.0 pts**
- We SET the efficiency benchmarks (being first = automatic best efficiency)
- **Estimated rank improvement:** +50-80 positions from T3 alone

T3 tasks that are "easiest" (already have executors):

| Task | Executor Status | Estimated Difficulty |
|------|----------------|---------------------|
| ENABLE_MODULE | Implemented | LOW — likely 2-3 API calls |
| REGISTER_SUPPLIER_INVOICE | Implemented | MEDIUM — needs supplier+invoice |
| RUN_PAYROLL | Implemented | MEDIUM — needs employee+salary |
| YEAR_END_CLOSING | Implemented (3 approaches) | HIGH — complex ledger logic |
| ERROR_CORRECTION | Implemented | HIGH — needs voucher reversal |
| BANK_RECONCILIATION | Implemented | VERY HIGH — CSV parsing + vouchers |

**Recommended T3 priority:** ENABLE_MODULE first (lowest complexity), then REGISTER_SUPPLIER_INVOICE, then RUN_PAYROLL.

---

## 7. Priority-Ordered Fix List

| Rank | Fix | Points Expected | Dev Time | Pts/Hr | Risk |
|------|-----|-----------------|----------|--------|------|
| **1** | **A: CREATE_EMPLOYEE startDate** | +1.0 to +2.0 | 15 min | 4-8 | LOW |
| **2** | **B+F: Payment amount (fetch from API)** | +2.4 to +7.4 | 30 min | 4.8-14.8 | LOW |
| **3** | **C: _find_employee fallthrough** | +1.0 to +5.0 | 15 min | 4-20 | LOW |
| **4** | **H: T3 ENABLE_MODULE** | +1.5 to +6.0 | 30 min | 3-12 | MED |
| **5** | **D: Batch department keyword** | +1.0 to +2.0 | 20 min | 3-6 | LOW |
| **6** | **G: Org number dash strip** | +0.3 to +1.0 | 5 min | 3.6-12 | LOW |
| **7** | **H: T3 other tasks** | +4.5 to +18.0 | 2-3 hrs | 2-9 | HIGH |
| **8** | **E: Invoice classifier** | +0.0 to +0.5 | 10 min | 0-3 | LOW |

### Speed Run Estimate

Doing fixes 1-6 (total ~1.5 hours dev time):

| Scenario | Points Gained | New Total | Estimated Rank |
|----------|-------------|-----------|----------------|
| Conservative | +5.7 | 28.1 | ~120 |
| Expected | +12.4 | 34.8 | ~60-80 |
| Optimistic | +18.4 | 40.8 | ~20-40 |

Adding T3 first-mover (fixes 7, +2-3 hours):

| Scenario | Points Gained | New Total | Estimated Rank |
|----------|-------------|-----------|----------------|
| Conservative | +5.7 + 5.4 | 33.5 | ~70-90 |
| Expected | +12.4 + 9.0 | 40.4 | ~25-40 |
| Optimistic | +18.4 + 18.0 | 58.4 | ~1-10 |

---

## 8. Key Strategic Insights

1. **Fix A (startDate) is the easiest win** — one-line default, unlocks an entire task type that's been scoring 0.

2. **Payment amount from API (Fix B+F) has cascading value** — fixes INVOICE_WITH_PAYMENT AND REGISTER_PAYMENT, two T2 tasks worth up to 8 pts combined.

3. **T3 is the ultimate differentiator** — NO team has scored here. Even mediocre T3 scores leapfrog teams. First to submit sets efficiency benchmarks (automatic 2x multiplier for being "best").

4. **Efficiency bonus doubles the score** — on tasks we already get 100% correct (CREATE_PRODUCT), we're leaving 1.0 pts on the table. Reducing API calls from 3 to 1 could recover this.

5. **The _find_employee bug is a landmine** — any update/delete/role task that hits the wrong employee scores 0. This affects 4+ task types across T1 and T2.

6. **Deploy and resubmit frequently** — best score per task is kept, bad submissions never hurt. Ship early, ship often.
