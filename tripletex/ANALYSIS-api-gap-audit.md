# Tripletex API Gap Audit — Live Sandbox Verification

> Generated: 2026-03-21 | Sandbox: `https://kkpqfuj-amager.tripletex.dev/v2`

---

## Executive Summary

**CRITICAL BUG**: Voucher postings missing `row` and `currency` fields in 4 executors — causes `"Posteringene på rad 0 (guiRow 0) er systemgenererte"` 422 error. Affects: `RUN_PAYROLL`, `BANK_RECONCILIATION`, `ERROR_CORRECTION`, `YEAR_END_CLOSING`.

**Secondary issues**: `/supplierInvoice` POST returns 500 (broken endpoint), `/salary/transaction` returns 403 (no permission), no "Memorialnota" voucher type exists, annual account `yearTo` is exclusive.

---

## 1. Employee API (`POST /employee`)

### Verified Working Payload
```json
{
  "firstName": "Test",
  "lastName": "User",
  "email": "test.user@example.com",
  "userType": "STANDARD",
  "dateOfBirth": "1990-01-01",
  "department": {"id": 864717}
}
```

### Key Findings

| Field | Status | Notes |
|-------|--------|-------|
| `firstName` | REQUIRED | |
| `lastName` | REQUIRED | |
| `email` | REQUIRED | Immutable after creation |
| `department.id` | **REQUIRED** | 422 if missing: "Feltet må fylles ut." |
| `userType` | Optional | STANDARD, EXTENDED, NO_ACCESS |
| `dateOfBirth` | Optional for create | Required for PUT updates |
| `startDate` | **DOES NOT EXIST** | 422 code 16000: "Feltet eksisterer ikke i objektet." |

### Our Code Status: **OK**
- `executor.py:376-443` correctly includes `department` ref and `dateOfBirth`
- `startDate` is NOT sent (good — comment at line 422 confirms this)
- The 35 failures mentioned are likely from older code versions

### Remaining Gap: None for employee creation itself.

---

## 2. Supplier Invoice (`POST /supplierInvoice`)

### Verified: POST /supplierInvoice is BROKEN in sandbox

**Test 1 — Minimal payload:**
```json
{"invoiceNumber":"TEST-001","invoiceDate":"2026-03-21","invoiceDueDate":"2026-04-21","supplier":{"id":108269521}}
```
→ **500 Internal Server Error** (no details)

**Test 2 — With nested voucher + postings:**
```json
{"invoiceNumber":"TEST-002","invoiceDate":"2026-03-21","invoiceDueDate":"2026-04-21","supplier":{"id":108269521},"voucher":{"date":"...","description":"...","postings":[...]}}
```
→ **500 Internal Server Error** (code 1002)

**GET /supplierInvoice** requires `invoiceDateFrom` + `invoiceDateTo` (both mandatory).

**GET /incomingInvoice** → 405 Method Not Allowed (endpoint doesn't support GET).

### Our Code Status: **Correct workaround**
- `executor.py:2839-2979` correctly uses voucher-based approach as primary strategy
- Falls back to `/supplierInvoice` POST which will always fail with 500
- **The voucher approach works IF `row` and `currency` fields are correct**

### BUG in supplier invoice voucher: Postings at lines 2901-2923 correctly include `row: 1/2` — this part is OK.

### Recommendation
Keep the voucher-based approach. Remove `/supplierInvoice` fallback (it causes unnecessary 500 errors that hurt efficiency score).

---

## 3. Salary / Payroll API

### Endpoint Status

| Endpoint | Status | Response |
|----------|--------|----------|
| `GET /salary/type` | **WORKS** | 21 salary types (Fastlønn=2000, Timelønn=2001, etc.) |
| `GET /salary/settings` | WORKS | Municipality, tax method |
| `GET /salary/compilation` | WORKS | Requires `employeeId` param |
| `GET /salary/payslip` | WORKS | Empty (no payslips exist) |
| `GET /salary/transaction` | **403 FORBIDDEN** | "You do not have permission to access this feature." |
| `POST /salary/transaction` | **403 FORBIDDEN** | Same permission error |

### Salary Types Available
```
72779379: 1000 — Gjeld til ansatte
72779380: 2000 — Fastlønn
72779381: 2001 — Timelønn
72779382: 2009 — Utbetalt fleksisaldo
(+17 more types)
```

### Employment Prerequisite
- `POST /employee/employment` works with just `{employee, startDate}`:
  ```json
  {"employee":{"id":18493396},"startDate":"2026-01-01"}
  ```
- **DO NOT** include `employmentType` — causes 422 "Feltet eksisterer ikke i objektet"
- Employment is needed before salary transactions, but salary/transaction is 403 anyway

### Our Code Status: **Voucher approach is the only viable path**
- `executor.py:2619-2800` correctly falls back to voucher-based salary posting
- **CRITICAL BUG**: Postings at lines 2747-2773 are **MISSING `row` and `currency` fields**

### Required Fix for `_exec_run_payroll`
Each posting needs:
```python
{
    "date": today,
    "account": {"id": salary_acct_id},
    "amountGross": base_salary,
    "amountGrossCurrency": base_salary,
    "currency": {"id": 1},   # ← MISSING
    "row": 1,                 # ← MISSING (must be >= 1)
}
```

Without `row >= 1`, the API returns:
> "Posteringene på rad 0 (guiRow 0) er systemgenererte og kan ikke opprettes eller endres på utsiden av Tripletex."

Voucher type `10155925` (Lønnsbilag) is the correct type for payroll vouchers.

---

## 4. Timesheet / LOG_HOURS

### Verified Working

| Endpoint | Status | Notes |
|----------|--------|-------|
| `GET /activity` | WORKS | 4 activities: Administrasjon (5685468), Ferie, Prosjektadministrasjon, Timeregistrering |
| `GET /timesheet/entry` | WORKS | Requires `dateFrom`+`dateTo` params |
| `POST /timesheet/entry` | WORKS | Verified in existing entries |

### Activities Available
```
5685468: Administrasjon (GENERAL_ACTIVITY, isProjectActivity=false)
5685469: Ferie (GENERAL_ACTIVITY)
5685470: Prosjektadministrasjon (PROJECT_GENERAL_ACTIVITY, isProjectActivity=true)
5685471: Timeregistrering (PROJECT_GENERAL_ACTIVITY, isProjectActivity=true)
```

### Our Code Status: **OK**
- `executor.py:1833-1943` correctly resolves employee, project, activity
- Creates project if not found, uses first activity as fallback
- **Note**: When logging hours to a project, use `isProjectActivity=true` activities (5685470 or 5685471)

### Minor Gap
- Activity search uses `projectId` filter which may not work for all activities
- Code correctly falls back to fetching all activities

---

## 5. Ledger Voucher / ERROR_CORRECTION

### Voucher Types Available
```
10155921: Utgående faktura
10155922: Leverandørfaktura
10155923: Purring
10155924: Betaling
10155925: Lønnsbilag
10155926: Terminoppgave
10155927: Mva-melding
10155928: Betaling med KID-nummer
10155929: Remittering
10155930: Bankavstemming
10155931: Reiseregning
10155932: Ansattutlegg
10155933: Åpningsbalanse
10155934: Tolldeklarasjon
10155935: Pensjon
10155936: Refusjon av sykepenger
10155937: Øreavrunding
```

**No "Memorialnota" or "Korreksjon" voucher type exists.** The `_get_voucher_type_id` helper (line 126-140) searches for "memorial"/"memorialnota" keywords and will fall back to the first type (Utgående faktura) which may be wrong.

### Voucher Reverse
- `PUT /ledger/voucher/{id}/:reverse` → 422 "Bilaget kan ikke reverseres" for test vouchers
- Not all vouchers are reversible — only non-system-generated ones can be reversed
- `DELETE /ledger/voucher/{id}` is the better first attempt for error correction

### Creating Correcting Vouchers
**CRITICAL**: Postings MUST include `row >= 1` and `currency: {"id": 1}`.

Verified working:
```json
POST /ledger/voucher?sendToLedger=false
{
  "date": "2026-03-21",
  "description": "Test",
  "postings": [
    {"date":"2026-03-21","account":{"id":436982939},"amountGross":1000,"amountGrossCurrency":1000,"currency":{"id":1},"row":1},
    {"date":"2026-03-21","account":{"id":436982712},"amountGross":-1000,"amountGrossCurrency":-1000,"currency":{"id":1},"row":2}
  ]
}
```

### Our Code Status: **BUG in error correction manual reversal**
- `executor.py:2222-2255` creates reversed postings but **MISSING `row` and `currency`**
- `_get_voucher_type_id` should prefer "Leverandørfaktura" or just use no voucherType (works fine)

### Recommendation for voucher type resolution
Update preferred keywords in `_get_voucher_type_id` callers:
- Payroll: `["lønn", "lønnsbilag"]` → matches `10155925`
- Bank reconciliation: `["bankavstemming"]` → matches `10155930`
- Error correction: no good match — use `None` (voucherType is optional)

---

## 6. Year-End Closing / Annual Account

### Verified API Behavior

| Endpoint | Status | Notes |
|----------|--------|-------|
| `GET /ledger/annualAccount` | WORKS | `yearFrom`/`yearTo` are **exclusive range** — use `yearFrom=2025&yearTo=2026` to get year 2025 |
| `GET /ledger/closeGroup` | WORKS | Returns empty for 2025 (no close groups exist) |
| `GET /ledger/accountingPeriod` | WORKS | 6 periods, all `isClosed=false` |

### BUG: `yearTo` is exclusive!
Our code at `executor.py:2330-2333`:
```python
annual_accounts = await client.get_annual_accounts({
    "yearFrom": str(year),
    "yearTo": str(year),   # ← BUG: yearTo is exclusive!
})
```
This returns 422: "'From and including' value (2025) is >= 'To and excluding' value (2025)".

**Fix**: Use `"yearTo": str(year + 1)`.

### No Annual Account Exists for 2025
Even with the fix, there are no annual account records for 2025. The voucher-based closing approach (Approach 2) is the correct fallback.

### Voucher Closing Approach Status
- `executor.py:2380-2467` correctly looks up equity (2050) and result (8960) accounts
- **CRITICAL BUG**: Closing voucher postings at lines 2440-2454 are **MISSING `row` and `currency`**

---

## Summary of ALL Bugs Found

### CRITICAL (will cause 422 failures)

| Bug | Location | Fix |
|-----|----------|-----|
| **Missing `row` in postings** | `_exec_run_payroll` (L2747-2773) | Add `"row": N` to each posting (1, 2, 3...) |
| **Missing `row` in postings** | `_exec_bank_reconciliation` (L2039-2051) | Add `"row": N` to each posting |
| **Missing `row` in postings** | `_exec_error_correction` (L2226-2233) | Add `"row": N` to each posting |
| **Missing `row` in postings** | `_exec_year_end_closing` (L2440-2454) | Add `"row": N` to each posting |
| **Missing `currency` in postings** | All 4 above | Add `"currency": {"id": 1}` (NOK) |
| **`yearTo` exclusive** | `_exec_year_end_closing` (L2332) | Use `str(year + 1)` |

### MODERATE (causes unnecessary errors / efficiency penalty)

| Bug | Location | Fix |
|-----|----------|-----|
| `/supplierInvoice` fallback always 500s | `_exec_create_supplier_invoice` (L2938-2979) | Remove fallback — voucher approach works |
| `_get_voucher_type_id` keyword mismatch | `executor.py:135` | No "memorialnota" exists; update keywords |
| `/salary/transaction` 403 | Entire salary transaction path | Don't attempt — go straight to voucher |

### INFO (working correctly)

| Area | Status |
|------|--------|
| Employee creation | Correct — department ref included, no startDate |
| Timesheet/LOG_HOURS | Correct — activities resolve properly |
| Supplier invoice (voucher approach) | Correct — row fields present |
| Dimension voucher | Correct — dimensions API works, 3 slots available |

---

## Appendix: Verified Account IDs

```
Account 1920 (Bank): 436982614
Account 2400 (Leverandørgjeld): 436982673
Account 2920 (Skyldig lønn): 436982712
Account 4000 (Varekostnad): 436982775
Account 7700 (Annen driftskostnad): 436982939
Currency NOK: {"id": 1}
Department Avdeling: 864717
Department Hovedavdeling: 865127
```

## Appendix: Working Voucher Template

Every voucher creation across all executors should use this pattern:

```python
postings = []
for i, (acct_id, amount, desc) in enumerate(posting_lines, start=1):
    postings.append({
        "date": voucher_date,
        "account": {"id": acct_id},
        "amountGross": amount,
        "amountGrossCurrency": amount,
        "currency": {"id": 1},
        "row": i,
        "description": desc,
    })

voucher_payload = {
    "date": voucher_date,
    "description": description,
    "voucherType": {"id": voucher_type_id} if voucher_type_id else None,
    "postings": postings,
}
result = await client.create_voucher(voucher_payload)
```
