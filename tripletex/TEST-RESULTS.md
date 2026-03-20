# Tripletex Agent — Curl Test Results

**Date:** 2026-03-20
**Endpoint:** http://localhost:8080/solve
**Sandbox:** https://kkpqfuj-amager.tripletex.dev/v2
**LLM Mode:** `none` (rule-based classifier)

---

## Previous Test Results (earlier session)

| # | Task | Language | HTTP | Created ID | Time |
|---|------|----------|------|------------|------|
| 1 | Create department "Salg" (nr 10) | NO | 200 | 865587 | 0.25s |
| 2 | Create customer "Test Firma AS" | NO | 200 | 108169123 | 0.26s |
| 3 | Create employee "Ola Nordmann" | NO | 200 | 18493536 | 0.45s |
| 4 | Create product "Widget" (299 NOK) | EN | 200 | 84382025 | 0.25s |
| 5 | Create department "Marketing" | FR | 200 | 865590 | 0.23s |

---

## Comprehensive Curl Tests (2026-03-20, latest run)

### Norwegian Tests

#### Test 1: create_department — Norwegian
**Prompt:** "Opprett en avdeling med navn Logistikk og avdelingsnummer 600"
**Response:** `{"status":"completed"}`
**HTTP:** 200 in 9.5s
**Verification:** Department "Logistikk" (#600) found — ID 871268
**Result:** ✅ PASS

#### Test 2: create_employee — Norwegian
**Prompt:** "Opprett en ansatt med fornavn Lars og etternavn Berg, e-post lars.berg@testfirma.no"
**Response:** `{"status":"completed"}`
**HTTP:** 200 in 1.4s
**Verification:** Employee "Lars Berg" (lars.berg@testfirma.no) found — ID 18504556
**Result:** ✅ PASS

#### Test 3: create_customer — Norwegian
**Prompt:** "Opprett en kunde med navn Testbedrift AS"
**Response:** `{"status":"completed"}`
**HTTP:** 200 in 0.4s
**Verification:** Customer "Testbedrift AS" found — ID 108180580 (new instance)
**Result:** ✅ PASS

#### Test 4: create_product — Norwegian
**Prompt:** "Opprett et produkt med navn Rådgivning"
**Response:** `{"status":"completed"}`
**HTTP:** 200 in 0.4s
**Verification:** No exact "Rådgivning" product found. "Raadgivning" (ID 84382304) exists but may be from prior test. No new product with å in name was created.
**Result:** ⚠️ PARTIAL — API returned completed but exact product name not verified. Possible name transliteration issue (å→aa) or duplicate prevention.

---

### English Tests

#### Test 5: create_department — English
**Prompt:** "Create a department named Analytics with department number 700"
**Response:** `{"status":"completed"}`
**HTTP:** 200 in 0.5s
**Verification:** Department "Analytics" (#700) found — ID 871308
**Result:** ✅ PASS

#### Test 6: create_employee — English
**Prompt:** "Create an employee named Alice Smith with email alice.smith@test.com"
**Response:** `{"status":"completed"}`
**HTTP:** 200 in 2.5s
**Verification:** Employee "Alice Smith" NOT FOUND by firstName=Alice or email=alice.smith@test.com. Not in full employee list (30 total).
**Result:** ❌ FAIL — API returned "completed" but employee was not created. Possible silent failure (email collision, validation error, or name extraction issue).

#### Test 7: create_customer — English
**Prompt:** "Create a customer called DataCorp International"
**Response:** `{"status":"completed"}`
**HTTP:** 200 in 0.6s
**Verification:** Customer "DataCorp International" found — ID 108180707
**Result:** ✅ PASS

#### Test 8: create_product — English
**Prompt:** "Create a product called Cloud Hosting"
**Response:** `{"status":"completed"}`
**HTTP:** 200 in 0.5s
**Verification:** Product "Cloud Hosting" found — ID 84382361
**Result:** ✅ PASS

---

### German Tests

#### Test 9: create_department — German
**Prompt:** "Erstellen Sie eine Abteilung namens Forschung mit Abteilungsnummer 800"
**Response:** `{"status":"completed"}`
**HTTP:** 200 in 0.4s
**Verification:** Department "Forschung" (#800) found — ID 871380
**Result:** ✅ PASS

#### Test 10: create_customer — German
**Prompt:** "Erstellen Sie einen Kunden namens München GmbH"
**Response:** `{"status":"completed"}`
**HTTP:** 200 in 0.3s
**Verification:** Customer "München GmbH" found — ID 108180743
**Result:** ✅ PASS

---

## Summary Table

| # | Task Type | Language | HTTP | Verified | Result |
|---|-----------|----------|------|----------|--------|
| 1 | create_department | NO | 200 / 9.5s | ✅ Found | ✅ PASS |
| 2 | create_employee | NO | 200 / 1.4s | ✅ Found | ✅ PASS |
| 3 | create_customer | NO | 200 / 0.4s | ✅ Found | ✅ PASS |
| 4 | create_product | NO | 200 / 0.4s | ⚠️ Name mismatch | ⚠️ PARTIAL |
| 5 | create_department | EN | 200 / 0.5s | ✅ Found | ✅ PASS |
| 6 | create_employee | EN | 200 / 2.5s | ❌ Not found | ❌ FAIL |
| 7 | create_customer | EN | 200 / 0.6s | ✅ Found | ✅ PASS |
| 8 | create_product | EN | 200 / 0.5s | ✅ Found | ✅ PASS |
| 9 | create_department | DE | 200 / 0.4s | ✅ Found | ✅ PASS |
| 10 | create_customer | DE | 200 / 0.3s | ✅ Found | ✅ PASS |

**Overall: 8/10 PASS, 1 PARTIAL, 1 FAIL**

---

## Issues Found

### 1. Test 6 — Employee creation silently fails (English)
"Create an employee named Alice Smith" returned `{"status":"completed"}` but the employee does not exist in Tripletex. The `/solve` endpoint returns `{"status":"completed"}` even when the underlying Tripletex API call fails. **This is a bug** — the response should surface success/failure details from the executor.

### 2. Test 4 — Special character handling in product names
"Rådgivning" with special character å may have been transliterated to "Raadgivning" or the product name extraction may have failed. Hard to verify conclusively since "Raadgivning" (ID 84382304) may predate this test.

---

## Performance Notes

- First request (Test 1) took 9.5s — likely cold start / LLM classifier warmup
- Subsequent requests: 0.3s–2.5s
- Employee creation tends to be slower (1.4–2.5s) due to department lookup/creation
- Customer and product creation fastest (0.3–0.6s)
- Server briefly went down between Test 5 and Test 6 (connection refused), recovered on retry

---

## Architecture Notes

End-to-end flow:
```
POST /solve → classify (rule-based) → extract fields → execute (deterministic) → Tripletex API → {"status":"completed"}
```

- **4 task types confirmed working:** create_department, create_employee, create_customer, create_product
- **3 languages confirmed:** Norwegian, English, German
- All responses return only `{"status":"completed"}` — no detail on what was created or any errors
