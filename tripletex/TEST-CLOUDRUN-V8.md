# Cloud Run Stress Test V8 — All Task Types

**Date:** 2026-03-20
**Endpoint:** https://tripletex-agent-4nwfkerl6q-lz.a.run.app/solve
**Sandbox:** kkpqfuj-amager.tripletex.dev

## Results Summary

| # | Prompt | Lang | HTTP | TaskType Detected | Success | Time | Notes |
|---|--------|------|------|-------------------|---------|------|-------|
| 1 | Opprett avdeling Stresstest nummer 300 | NO | 200 | CREATE_DEPARTMENT | YES | 0.84s | id=874979 |
| 2 | Opprett kunde Stresstest Corp AS med e-post stress@test.no | NO | 200 | CREATE_CUSTOMER | YES | 0.47s | id=108187993 |
| 3 | Opprett ansatt med fornavn Test og etternavn Stress, e-post stress@corp.no | NO | 200 | CREATE_EMPLOYEE | YES | 0.99s | id=18511825 |
| 4 | Opprett produkt Stresstjeneste til 999 kr | NO | 200 | CREATE_PRODUCT | YES | 0.30s | id=84382560 |
| 5 | Opprett prosjekt Stresstest Alpha | NO | 200 | CREATE_PROJECT | YES | 0.45s | id=401951666 |
| 6 | Finn kunde Stresstest Corp | NO | 200 | FIND_CUSTOMER | YES | 0.28s | Found 1 result |
| 7 | Opprett kontaktperson Anna Stress for kunde Stresstest Corp AS | NO | 200 | CREATE_CONTACT | YES | 0.59s | id=18511882 |
| 8 | Opprett faktura til Stresstest Corp AS 1 stk Stresstjeneste | NO | 200 | INVOICE_EXISTING_CUSTOMER | NO | 0.34s | "No invoice lines specified" — classifier found customer but failed to extract lines |
| 9 | Registrer reiseregning Stresstest reise | NO | 200 | CREATE_TRAVEL_EXPENSE | YES | 0.48s | id=11142313 |
| 10 | Create employee named Stress English email stress.en@test.com | EN | 200 | CREATE_EMPLOYEE | NO | 0.58s | Tripletex 422: email domain validation — "stavefeil i e-postadresse" |
| 11 | Erstellen Kunden Stresstest GmbH | DE | 200 | CREATE_CUSTOMER | YES | 0.38s | id=108188093 |
| 12 | Créer département Stresstest numéro 310 | FR | 200 | CREATE_DEPARTMENT | YES | 0.29s | id=875044 |
| 13 | Crear cliente Stresstest SL | ES | 200 | CREATE_CUSTOMER | YES | 0.33s | id=108188105 |
| 14 | Bankavstemming for mars 2026 | NO | 200 | BANK_RECONCILIATION | NO | 0.07s | Expected: stub not implemented |
| 15 | Årsavslutning 2025 | NO | 200 | YEAR_END_CLOSING | NO | 0.07s | Expected: stub not implemented |
| 16 | Aktiver modul Reiseregning | NO | 200 | ENABLE_MODULE | NO | 0.07s | Expected: stub not implemented |

## Scoreboard

- **Total tests:** 16
- **HTTP 200:** 16/16 (100%)
- **Correct classification:** 16/16 (100%)
- **Execution success:** 11/16 (69%)
- **Expected failures (Tier 3 stubs):** 3 (bank recon, year-end, enable module)
- **Unexpected failures:** 2

## Issues Found

### Issue 1: Invoice line extraction failure (Test 8)
- **Prompt:** "Opprett faktura til Stresstest Corp AS 1 stk Stresstjeneste"
- **Classification:** Correct (INVOICE_EXISTING_CUSTOMER)
- **Problem:** Classifier found the customer but did not extract "1 stk Stresstjeneste" as an order line
- **Root cause:** The keyword-mode field extractor likely lacks logic to parse "N stk ProductName" into a line item
- **Severity:** HIGH — invoicing is a core Tier 1/2 task
- **Fix needed:** Improve `_extract_invoice_lines()` in classifier.py to handle "N stk X" patterns

### Issue 2: Tripletex email domain validation (Test 10)
- **Prompt:** "Create employee named Stress English email stress.en@test.com"
- **Classification:** Correct (CREATE_EMPLOYEE)
- **Problem:** Tripletex sandbox rejects `test.com` email domain as a typo
- **Severity:** LOW — sandbox-specific validation, not a code bug
- **Workaround:** Use a more "real-looking" email domain in prompts (e.g., `@example.org` or `@company.no`)

## Multilingual Coverage

| Language | Tests | All Classified Correctly |
|----------|-------|--------------------------|
| Norwegian (NO) | 11 | YES |
| English (EN) | 1 | YES |
| German (DE) | 1 | YES |
| French (FR) | 1 | YES |
| Spanish (ES) | 1 | YES |

## Performance

- Average response time (Tier 1/2): **0.47s**
- Average response time (Tier 3 stubs): **0.07s**
- Fastest: 0.07s (stubs)
- Slowest: 0.99s (create employee — includes department lookup)
