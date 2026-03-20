# Grader Request Analysis

**Generated:** 2026-03-20T04:00Z
**Log window:** 2026-03-20 02:50 - 03:25 UTC (freshness=3h)
**Source:** Cloud Run logs for `tripletex-agent` in `nm-i-ai-490723`

---

## Summary

- **Total grader requests received:** 2
- **Total test requests (our own):** ~149
- **Grader success rate:** 0/2 (0%)
- **Grader user agent:** `python-httpx/0.28.1`
- **Grader IPs:** `34.34.240.77`, `34.34.240.86`
- **Grader endpoint:** `POST /` (root path, NOT `/solve`)
- **Grader proxy URL:** `tx-proxy-jwanbnu3pq-lz.a.run.app`

---

## Grader Requests

### Request #1 (FAILED)

| Field | Value |
|-------|-------|
| **Timestamp** | 2026-03-20T03:02:42.262Z |
| **Latency** | 43.56s |
| **Prompt** | "Le client Colline SARL (no org. 850491941) a une facture impayee de 10550 NOK hors TVA pour 'Heures de conseil'. Enregis..." |
| **Language** | French |
| **Expected task** | Create invoice + register payment (complex multi-step) |
| **Classified as** | `TaskType.REGISTER_PAYMENT` |
| **Confidence** | 0.75 (lowest seen in all logs) |
| **LLM** | Gemini 2.5 Pro |
| **API calls** | `GET /invoice?invoiceNumber=850491941` (HTTP 200 OK) |
| **Result** | FAILED: "Invoice #850491941 not found" |
| **Root cause** | Agent tried to find invoice by org number instead of creating one first. The task requires creating an invoice then registering payment, but was classified as just REGISTER_PAYMENT. |

**Key issues:**
1. Misclassification: This was a complex task requiring invoice creation + payment registration, but was classified as simple payment registration
2. The org number (850491941) was used as invoice number in the search query
3. Low confidence (0.75) suggests the classifier was uncertain but chose wrong
4. Extremely slow (43.56s) -- most of this was LLM classification time

### Request #2 (FAILED)

| Field | Value |
|-------|-------|
| **Timestamp** | 2026-03-20T03:19:59.530Z |
| **Latency** | 9.11s |
| **Prompt** | "Vi har en ny ansatt som heter Astrid Strand, fodt 4. May 1986. Opprett vedkommende som ansatt med e-post astrid.strand@e..." |
| **Language** | Norwegian |
| **Expected task** | Create employee |
| **Classified as** | `TaskType.CREATE_EMPLOYEE` |
| **Confidence** | 0.99 |
| **LLM** | Gemini 2.5 Pro |
| **API calls** | `GET /department?count=1` (HTTP 200), `POST /employee` (HTTP 422) |
| **Result** | FAILED: Tripletex 422 validation error |
| **Error detail** | `{"field":"startDate","message":"Feltet eksisterer ikke i objektet."}` ("The field does not exist in the object") |

**Key issues:**
1. Classification was CORRECT (CREATE_EMPLOYEE, 0.99 confidence)
2. The API call sequence was correct (get department first, then create employee)
3. Failure was in the employee POST body -- the `startDate` field was either missing or malformed
4. The Tripletex API requires `startDate` as a required field for employee creation but the executor did not include it properly

---

## Classification Accuracy Analysis

### Grader requests only (2 total)

| # | Prompt (truncated) | Expected | Classified | Correct? |
|---|-------------------|----------|------------|----------|
| 1 | "Le client Colline SARL..." | INVOICE_WITH_PAYMENT | REGISTER_PAYMENT | NO |
| 2 | "Vi har en ny ansatt..." | CREATE_EMPLOYEE | CREATE_EMPLOYEE | YES |

**Grader classification accuracy: 1/2 (50%)**

### Test requests classification distribution (all 149 test flows)

| Task Type | Count | Notes |
|-----------|-------|-------|
| CREATE_EMPLOYEE | 10 | Most tested |
| CREATE_CUSTOMER | 7 | |
| INVOICE_WITH_PAYMENT | 7 | |
| CREATE_TRAVEL_EXPENSE | 6 | |
| CREATE_PRODUCT | 6 | |
| CREATE_CONTACT | 5 | |
| CREATE_PROJECT | 4 | |
| INVOICE_EXISTING_CUSTOMER | 4 | |
| REGISTER_PAYMENT | 3 | |
| PROJECT_WITH_CUSTOMER | 3 | |
| CREATE_DEPARTMENT | 3 | |
| CREATE_INVOICE | 3 | |
| BANK_RECONCILIATION | 3 | |
| DELETE_EMPLOYEE | 2 | |
| UPDATE_EMPLOYEE | 2 | |
| UPDATE_CUSTOMER | 2 | |
| SET_EMPLOYEE_ROLES | 2 | |
| YEAR_END_CLOSING | 2 | |
| CREATE_CREDIT_NOTE | 2 | |
| DELETE_TRAVEL_EXPENSE | 2 | |
| ERROR_CORRECTION | 2 | |
| UPDATE_PROJECT | 2 | |
| DELETE_PROJECT | 2 | |
| PROJECT_BILLING | 1 | |
| FIND_CUSTOMER | 1 | |
| ENABLE_MODULE | 1 | |

### Confidence statistics (across all classifications)

- **Min:** 0.75 (grader request #1)
- **Max:** 0.99
- **Average:** 0.97
- **Below 0.90:** 1 occurrence (the grader misclassification)
- **At or above 0.95:** 85 occurrences

---

## API Error Patterns

### HTTP Status Code Distribution

| Status | Count | Description |
|--------|-------|-------------|
| 401 | 201 | Unauthorized -- test environment auth issue |
| 422 | 2 | Validation error (grader request #2) |

### Key Findings

1. **All 201 "401 Unauthorized" errors came from test requests** hitting `kkpqfuj-amager.tripletex.dev` -- this is an authentication configuration issue in our test environment, not a code bug.

2. **The 2 "422" errors came from the grader request #2** -- this is a real bug in the employee creation payload. The `startDate` field was not properly included in the POST body.

3. **The grader proxy (`tx-proxy-*`) returned 200 OK for GET requests** -- authentication works correctly when the grader provides the proxy URL. Only the POST failed due to payload issues.

---

## Failure Patterns

### Pattern 1: Complex Multi-Step Tasks Misclassified

**Affected:** Grader request #1
**Problem:** The classifier sees a French prompt describing "client has unpaid invoice, register payment" and classifies it as just REGISTER_PAYMENT instead of the compound INVOICE_WITH_PAYMENT task type. The prompt actually requires creating an invoice first, then registering payment.
**Evidence:** Confidence was only 0.75 -- the lowest seen across all requests.

### Pattern 2: Missing Required Fields in POST Bodies

**Affected:** Grader request #2
**Problem:** Employee creation POST to Tripletex API missing `startDate` field. The validation error message is "Feltet eksisterer ikke i objektet" (field does not exist in the object).
**Root cause:** The executor for CREATE_EMPLOYEE does not extract or set `startDate` from the prompt context. The grader prompt mentioned "fodt 4. May 1986" (born date) but the executor needs to set `startDate` (employment start date), which is a different concept.

### Pattern 3: High Latency on First Request

**Affected:** Grader request #1
**Problem:** 43.56s total latency, mostly from cold start + Gemini API classification call.
**Grader request #2:** 9.11s (more reasonable, container was warm).

### Pattern 4: Test Auth Configuration

**Affected:** All 149 test requests
**Problem:** All test requests fail with 401 against `kkpqfuj-amager.tripletex.dev`. This means we cannot validate our logic through test requests with the current auth setup.

---

## Recommendations

### Critical (affects grader score)

1. **Fix `startDate` in CREATE_EMPLOYEE executor** -- The POST body must include `startDate` (employment start date). If not specified in the prompt, default to today's date. This is a required field in the Tripletex API.

2. **Improve multi-step task classification** -- The classifier needs to handle compound tasks like "create invoice AND register payment" as `INVOICE_WITH_PAYMENT` rather than just `REGISTER_PAYMENT`. Consider:
   - Adding more training examples for compound tasks in multiple languages
   - Lowering the confidence threshold for fallback to more complex task types
   - Adding a re-classification step when confidence is below 0.85

3. **Support French language prompts better** -- Grader request #1 was in French and got both low confidence and wrong classification. Ensure the classification prompt explicitly handles French, German, and other languages.

### Important (affects reliability)

4. **Fix test authentication** -- The 401 errors on `kkpqfuj-amager.tripletex.dev` prevent validating any logic. Fix the token/session setup so tests actually exercise the full flow.

5. **Reduce cold start latency** -- 43.56s is dangerously long. Consider:
   - Setting minimum instances to 1 in Cloud Run
   - Pre-loading the Gemini model connection on startup
   - Caching the classification prompt template

6. **Validate all POST bodies against Tripletex API schema** -- Before sending POST requests, check that all required fields are present. The Tripletex API requires specific fields for each entity type.

### Nice to have

7. **Log the full prompt text** -- Currently `prompt_preview` is truncated. Log the complete prompt for debugging.

8. **Log the POST body** -- When making API calls, log the request body so we can debug field mapping issues without having to reproduce them.

9. **Add field extraction audit** -- After LLM extraction, log all extracted fields so we can see what was and was not captured from the prompt.

---

## Grader Infrastructure Notes

- Grader POSTs to `/` (root), not `/solve` -- our app handles both, which is correct
- Grader uses `python-httpx/0.28.1` user agent
- Grader IPs are in the `34.34.240.0/24` range (Google Cloud)
- Grader provides a per-request proxy URL (`tx-proxy-*`) in the request body
- The proxy URL authenticates on behalf of the grader's test company
- Our container correctly picks up and uses the proxy URL from the request
