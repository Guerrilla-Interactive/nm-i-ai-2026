# TRIPLETEX BATTLE PLAN — 2026-03-21 (Tier 3 Day)

**Our score:** 22.40 pts (rank #161) | **Top team:** 48.98 pts | **T3 = 0 for ALL teams**

---

## 1. PRIORITY-RANKED FIX LIST

### FIX 1: Voucher Postings — Add `row` + `currency` (CRITICAL)
- **What:** 4 executor functions create voucher postings WITHOUT required `row` and `currency` fields, causing 422 errors
- **Files/Lines:**
  - `executor.py:2039-2051` — `_exec_bank_reconciliation` postings
  - `executor.py:2747-2773` — `_exec_run_payroll` postings
  - `executor.py:2226-2233` — `_exec_error_correction` reversed postings (has `currency` from source but NO `row`)
  - `executor.py:2440-2454` — `_exec_year_end_closing` closing postings
- **Fix:** Add `"row": i` (1-indexed) and `"currency": {"id": 1}` to every posting dict. Use the template:
  ```python
  for i, posting in enumerate(postings, start=1):
      posting["row"] = i
      posting["currency"] = {"id": 1}
  ```
- **Expected points:** +6.0 to +18.0 (fixes ALL T3 voucher-based tasks × 3 multiplier)
- **Difficulty:** EASY (mechanical — same fix 4 times)
- **Dependencies:** None
- **Priority:** P0 — this single fix unblocks BANK_RECONCILIATION, RUN_PAYROLL, ERROR_CORRECTION, YEAR_END_CLOSING

### FIX 2: Year-End Closing — `yearTo` exclusive range
- **What:** `yearTo` parameter is exclusive in Tripletex API. Our code sends `yearFrom=2025, yearTo=2025` which returns 422
- **File/Line:** `executor.py:2332` — `"yearTo": str(year)` → `"yearTo": str(year + 1)`
- **Expected points:** +1.5 to +6.0 (T3 × 3 multiplier)
- **Difficulty:** EASY (one-line change)
- **Dependencies:** Combine with FIX 1 (same function)

### FIX 3: Voucher Type Resolution — Fix keyword mismatches
- **What:** `_get_voucher_type_id` searches for "memorial"/"memorialnota" which don't exist. Callers need correct keywords.
- **File/Lines:**
  - `executor.py:126-140` — `_get_voucher_type_id` helper
  - Payroll caller should use `["lønn", "lønnsbilag"]` → matches type 10155925
  - Bank reconciliation caller should use `["bankavstemming"]` → matches type 10155930
  - Error correction: use `None` (voucherType is optional for correction vouchers)
  - `executor.py:2054` — bank reconciliation already uses `["bank", "innbetaling"]` — could use `["bankavstemming"]`
  - `executor.py:2236` — error correction uses `["korreksjon", "correction"]` — no match exists, falls back to first type (wrong)
- **Expected points:** +1.0 to +3.0 (prevents wrong voucher type assignment)
- **Difficulty:** EASY
- **Dependencies:** Combine with FIX 1

### FIX 4: Batch Department Creation
- **What:** "Create three departments: X, Y, and Z" classifies as UNKNOWN because keyword fallback can't handle batch intent
- **File/Lines:**
  - `classifier.py` — keyword fallback section. Add batch detection: split comma/and-separated lists into N individual classifications
  - `executor.py:667` — `_exec_create_department` handles single creation fine; need loop in caller
- **Expected points:** +1.0 to +2.0 (T1 × 1)
- **Difficulty:** MEDIUM (classifier change + loop logic)
- **Dependencies:** None

### FIX 5: INVOICE_WITH_PAYMENT Misclassification (French/non-Norwegian)
- **What:** Narrative prompts like "Le client X a une facture impayée... Enregistrer le paiement" misclassify as REGISTER_PAYMENT instead of INVOICE_WITH_PAYMENT
- **File/Lines:**
  - `classifier.py` — INVOICE_WITH_PAYMENT patterns. Add French/German/Spanish/Portuguese patterns:
    - fr: "facture impayée", "enregistrer le paiement"
    - de: "unbezahlte Rechnung", "Zahlung registrieren"
    - es: "factura impaga", "registrar el pago"
    - pt: "fatura pendente", "registrar pagamento"
  - Also add: when prompt mentions BOTH a customer AND payment AND no existing invoice number → classify as INVOICE_WITH_PAYMENT
- **Expected points:** +1.4 to +3.4 (T2 × 2)
- **Difficulty:** MEDIUM
- **Dependencies:** None

### FIX 6: Remove `/supplierInvoice` POST Fallback
- **What:** `POST /supplierInvoice` always returns 500 in sandbox. The fallback wastes time and creates error noise.
- **File/Line:** `executor.py:2938-2979` — Remove the try/except block that attempts `POST /supplierInvoice`
- **Expected points:** +0.5 to +1.0 (efficiency improvement on supplier invoice tasks)
- **Difficulty:** EASY
- **Dependencies:** None

### FIX 7: Error Correction — Add `"date"` field to reversed postings
- **What:** Reversed postings at line 2227-2233 copy from source but may be missing `"date"` field
- **File/Line:** `executor.py:2227-2233` — Add `"date": _today()` to each reversed posting
- **Expected points:** Included in FIX 1 points
- **Difficulty:** EASY
- **Dependencies:** Part of FIX 1 scope

### FIX 8: ENABLE_MODULE — Verify executor has correct API calls
- **What:** `_exec_enable_module` (line 2500) likely needs verification against actual Tripletex module API
- **File/Line:** `executor.py:2500-2618`
- **Expected points:** +1.5 to +6.0 (T3 × 3; NO other team has scored T3)
- **Difficulty:** MEDIUM (need to verify API endpoint structure)
- **Dependencies:** None

---

## 2. WORKER ASSIGNMENT PLAN

### Wave 1 — Deploy First (Parallel, ~30 min)

| Worker | Task | Files | Est. Time |
|--------|------|-------|-----------|
| **W1** | FIX 1: Add `row` + `currency` to ALL 4 voucher functions + FIX 2: yearTo + FIX 3: voucher type keywords + FIX 7: date field | `executor.py` (lines 2039-2051, 2226-2233, 2332, 2440-2454, 2747-2773, 2054, 2236) | 25 min |
| **W2** | FIX 5: INVOICE_WITH_PAYMENT multilingual classifier patterns | `classifier.py` | 25 min |
| **W3** | FIX 4: Batch detection in classifier (split "X, Y, and Z" into N tasks) | `classifier.py` + `main.py` (if batch loop needed) | 30 min |
| **W4** | FIX 6: Remove broken `/supplierInvoice` POST fallback | `executor.py` (lines 2938-2979) | 10 min |

**IMPORTANT:** W2 and W3 both edit `classifier.py`. Assign them non-overlapping sections or serialize them (W2 first, W3 second).

### Wave 2 — Deploy Second (After Wave 1, ~45 min)

| Worker | Task | Files | Est. Time |
|--------|------|-------|-----------|
| **W5** | FIX 8: Verify ENABLE_MODULE executor against sandbox API + fix any issues | `executor.py:2500-2618`, `tripletex_client.py` | 30 min |
| **W6** | End-to-end test: Run `test_local.py` and `test_e2e_live.py` against sandbox to verify all fixes | Test scripts only | 20 min |

### Wave 3 — Deploy Third (If time permits)

| Worker | Task | Files | Est. Time |
|--------|------|-------|-----------|
| **Any** | Add RUN_PAYROLL salary transaction shortcut (try `/salary/transaction` first, only voucher if 403) | `executor.py:2619-2800` | 30 min |
| **Any** | Add sequential context: store last-created entity IDs in module-level dict keyed by entity type | `executor.py` (all `_exec_create_*` returns) + `main.py` (session state) | 45 min |

### Deploy Sequence
```
W1 + W4 (parallel) → DEPLOY → Score check
W2 (classifier) → W3 (classifier, same file) → DEPLOY → Score check
W5 (enable module) → DEPLOY → Score check
W6 (validation) → Final DEPLOY
```

---

## 3. USER GROUP COVERAGE MATRIX

| User Group | Current Success Rate | Biggest Gap | Fix That Helps | Post-Fix Expected |
|-----------|---------------------|-------------|----------------|-------------------|
| **Accountant** | 0% (untested) | ALL T3 tasks fail due to missing `row`/`currency` | FIX 1, FIX 2, FIX 3 | 40-70% (T3 × 3) |
| **HR Manager** | 0% (3/3 failed) | Batch dept fails, employee creation works now | FIX 4 | 50-80% |
| **Supplier Manager** | 0% (untested) | `/supplierInvoice` POST always 500s | FIX 6 (remove fallback) | 40-60% |
| **System Admin** | 0% (untested) | ENABLE_MODULE untested | FIX 8 | 30-60% |
| **SMB Owner** | 50% (2/4) | Compound prompts misclassified in fr/de/es/pt | FIX 5 | 70-90% |
| **Project Manager** | 50% (1/2) | Failures were infra (401), not logic | None needed | 70-90% |

---

## 4. NEW TASK TYPES OR PATTERNS

### No new TaskType enums needed for immediate scoring
The 30+ existing types cover all likely grader scenarios. Focus on FIXING existing implementations.

### New Classifier Patterns Needed

| Pattern | Language | Current Route | Correct Route | File |
|---------|----------|--------------|---------------|------|
| "facture impayée...enregistrer le paiement" | fr | REGISTER_PAYMENT | INVOICE_WITH_PAYMENT | classifier.py |
| "unbezahlte Rechnung...Zahlung registrieren" | de | REGISTER_PAYMENT | INVOICE_WITH_PAYMENT | classifier.py |
| "Create three departments: X, Y, Z" | en | UNKNOWN | CREATE_DEPARTMENT (×3) | classifier.py |
| "Opprett 3 avdelinger: X, Y, Z" | nb | UNKNOWN | CREATE_DEPARTMENT (×3) | classifier.py |

### Batch Detection Logic (classifier.py)
Add to keyword fallback:
```python
# Detect batch: "Create X, Y, and Z" → split into N tasks
batch_pattern = r'(?:opprett|lag|create)\s+(?:tre|three|3|fire|four|4|fem|five|5)?\s*(?:avdelinger|departments|ansatte|employees|produkter|products)'
```

---

## 5. API ENDPOINT CHANGES

### tripletex_client.py — No new endpoints needed

All required endpoints already exist. The issues are in how executor.py CALLS them.

### Payload Fixes (executor.py)

| Function | Line | Current Payload | Required Fix |
|----------|------|----------------|-------------|
| `_exec_bank_reconciliation` | 2039-2051 | Missing `row`, `currency` | Add `"row": i, "currency": {"id": 1}` |
| `_exec_run_payroll` | 2747-2773 | Missing `row`, `currency` | Add `"row": i, "currency": {"id": 1}` |
| `_exec_error_correction` | 2226-2233 | Missing `row`, has `currency` from source | Add `"row": i`, ensure `"date": _today()` |
| `_exec_year_end_closing` | 2440-2454 | Missing `row`, `currency` | Add `"row": i, "currency": {"id": 1}` |
| `_exec_year_end_closing` | 2332 | `yearTo = str(year)` | Change to `str(year + 1)` |

### Verified Working Voucher Template
```python
for i, posting in enumerate(postings, start=1):
    posting["row"] = i
    posting["currency"] = {"id": 1}
```

---

## 6. DEPLOYMENT STRATEGY

### Order of Deployment

1. **FIX 1 + 2 + 3 + 6 + 7** (all executor.py, no conflicts) → `bash deploy.sh` → **SCORE CHECK**
   - Expected: +6 to +18 points from T3 alone
   - Risk: LOW (mechanical fixes, well-understood API behavior)

2. **FIX 5** (classifier.py — INVOICE_WITH_PAYMENT patterns) → `bash deploy.sh` → **SCORE CHECK**
   - Expected: +1.4 to +3.4 points
   - Risk: LOW (additive patterns, won't break existing classification)

3. **FIX 4** (classifier.py — batch detection) → `bash deploy.sh` → **SCORE CHECK**
   - Expected: +1.0 to +2.0 points
   - Risk: MEDIUM (new logic path — test carefully)

4. **FIX 8** (executor.py — ENABLE_MODULE verification) → `bash deploy.sh` → **SCORE CHECK**
   - Expected: +1.5 to +6.0 points
   - Risk: MEDIUM (may require sandbox testing to find correct API calls)

### Scoring Strategy
- **Deploy after EACH fix group** — best score per task is kept, bad submissions never hurt
- **T3 first mover advantage is massive** — even 30% correctness on T3 tasks scores more than most teams have
- **Submit early in the morning** to set efficiency benchmarks (first submission = best efficiency ratio)

### Risk Mitigation
- **Never break passing tests:** Run `python test_local.py` before each deploy
- **T1/T2 regression:** The voucher fixes (FIX 1) only affect T3 task paths; T1/T2 executors are untouched
- **Classifier changes:** FIX 5 adds patterns (additive), FIX 4 adds batch logic (new code path — higher risk)
- **Rollback plan:** Keep git tag before each deploy

---

## 7. SCORE PROJECTION

### Conservative (fixes 1-3 + 6)
| Source | Points |
|--------|--------|
| Current score | 22.40 |
| T3 voucher fixes (30% correctness × 4 tasks × 3) | +3.6 |
| yearTo fix | +1.5 |
| **Total** | **~27.5** |
| **Estimated rank** | ~130 |

### Expected (all fixes)
| Source | Points |
|--------|--------|
| Current score | 22.40 |
| T3 voucher fixes (50% × 4 × 3) | +6.0 |
| yearTo fix + voucher type | +3.0 |
| INVOICE_WITH_PAYMENT classification | +2.0 |
| Batch department | +1.0 |
| ENABLE_MODULE | +3.0 |
| Supplier invoice efficiency | +0.5 |
| **Total** | **~37.9** |
| **Estimated rank** | ~40-60 |

### Optimistic (all fixes + efficiency bonus as first mover)
| Source | Points |
|--------|--------|
| Current score | 22.40 |
| T3 voucher fixes (80% × 4 × 6 with efficiency) | +19.2 |
| All other fixes | +6.5 |
| ENABLE_MODULE with efficiency | +6.0 |
| **Total** | **~54.1** |
| **Estimated rank** | ~1-10 |

---

## 8. CRITICAL REMINDERS

1. **FIX 1 IS THE SINGLE MOST IMPORTANT FIX.** It unblocks ALL T3 voucher-based tasks. Every minute spent on anything else before FIX 1 is deployed is wasted.

2. **T3 first mover = automatic best efficiency.** Being first to submit ANY T3 score gives us the efficiency benchmark (up to 2× multiplier). Even a mediocre T3 score is worth more than a perfect T1 score.

3. **W2 and W3 both edit classifier.py.** Either assign non-overlapping sections OR run W2 first, then W3.

4. **The employee `startDate` issue is already fixed** (line 422 confirms `startDate` is NOT sent — API doesn't support it). The `department.id` is included. Employee creation should work now.

5. **`_find_employee` fallthrough is already fixed** (line 218-220: returns `None` when `last_name` specified but unmatched).

6. **INVOICE_WITH_PAYMENT VAT is already fixed** (line 1363: uses `api_amount` from invoice response, not hardcoded 1.25×).

7. **Deploy command:** `cd /tmp/doey/nm-i-ai-2026/worktrees/team-3/tripletex && bash deploy.sh`
