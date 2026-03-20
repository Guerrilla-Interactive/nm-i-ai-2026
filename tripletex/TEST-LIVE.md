# Live Test Results — Tripletex Agent

> Tested: 2026-03-20
> Endpoint: ngrok (https://coralie-overaffected-mazie.ngrok-free.dev) → localhost
> LLM mode: claude (ANTHROPIC_API_KEY set)
> Sandbox: kkpqfuj-amager.tripletex.dev

---

## HTTP Response Results: 18/18 PASS

All tests returned HTTP 200 with `{"status":"completed"}`.

| Test ID | Prompt (abbreviated) | HTTP | Status |
|---------|---------------------|------|--------|
| T1-nb-dept | Opprett avdeling Logistikk #60 | 200 | ✅ |
| T1-nb-cust | Opprett kunde Fjord Shipping AS | 200 | ✅ |
| T1-nb-emp | Opprett ansatt Lars Berg, lars@fjord.no | 200 | ✅ |
| T1-nb-prod | Opprett produkt Frakttjeneste 2500 kr | 200 | ✅ |
| T1-nb-proj | Opprett prosjekt Havnelogistikk | 200 | ✅ |
| T1-en-dept | Create department Research #70 | 200 | ✅ |
| T1-en-cust | Create customer Nordic Solutions AB | 200 | ✅ |
| T1-en-emp | Create employee Emma Wilson | 200 | ✅ |
| T1-en-prod | Create product API Integration Service 3500 | 200 | ✅ |
| T1-de-cust | Erstellen Kunden München GmbH | 200 | ✅ |
| T1-de-dept | Erstellen Abteilung Vertrieb #80 | 200 | ✅ |
| T1-fr-dept | Créer département Finance #90 | 200 | ✅ |
| T1-fr-cust | Créer client Paris Conseil SAS | 200 | ✅ |
| T1-es-cust | Crear cliente Barcelona Tech SL | 200 | ✅ |
| T2-nb-inv | Faktura Fjord Shipping 3×Frakttjeneste | 200 | ✅ |
| T2-en-inv | Invoice Nordic Solutions 5×API Integration | 200 | ✅ |
| T2-nb-travel | Reiseregning Kundebesøk Bergen | 200 | ✅ |
| T2-nb-contact | Kontaktperson Per Olsen for Fjord Shipping | 200 | ✅ |

---

## Sandbox Verification — Entity Data Quality

### Departments (11 total)
```
864717: Avdeling (num=)
865127: Hovedavdeling (num=1)
865587: Salg (num=10)
865590: Marketing (num=)
866144: IT (num=20)
866149: HR with number 30 (num=)          ⚠️ BUG: name includes "with number 30"
867134: Teknologi (num=50)
867497: Marketing (num=)
867581: Logistikk (num=60)                ✅ correct
867595: Vertrieb (num=)                   ⚠️ missing departmentNumber 80
867596: Finance (num=)                    ⚠️ missing departmentNumber 90
```

**Issues found:**
- ⚠️ "HR with number 30" — LLM included "with number 30" in the name field
- ⚠️ "Research" department (T1-en-dept) not found — silently failed or created with wrong name
- ⚠️ Vertrieb, Finance missing department numbers — LLM didn't extract `departmentNumber`

### Customers (10 total)
```
108168219: Testbedrift AS                 (pre-existing)
108168567: Test Customer AS               (pre-existing)
108169123: Test Firma AS                  (pre-existing)
108170200: Invoice Test Firma AS          (pre-existing)
108170479: Direct Test Corp               (pre-existing)
108170621: Nordmann Handel AS             (pre-existing)
108172892: Nordic Solutions AS with email info@nordic.no  ⚠️ email in name
108173073: Fjord Shipping AS              ✅
108173088: Nordic Solutions AB with email info@nordic.se  ⚠️ email in name
108173101: Paris Conseil SAS              ✅
```

**Issues found:**
- ⚠️ "Nordic Solutions AB with email info@nordic.se" — LLM put "with email info@nordic.se" in the name field instead of the email field
- ⚠️ München GmbH not found — German customer may have silently failed
- ⚠️ Barcelona Tech SL not found — Spanish customer may have silently failed

### Employees (11 total)
```
18491802: Frikk a23fd25c                  (pre-existing)
18492587: Ola Nordmann                    (pre-existing)
18493396: Delete MePlease                 (pre-existing)
18493534: TypeTest STANDARD               (pre-existing)
18493536: Ola Nordmann                    (pre-existing)
18493562: TypeTest2 NO_ACCESS             (pre-existing)
18493564: TypeTest2 EXTENDED              (pre-existing)
18494521: Kari Hansen                     (pre-existing)
18497054: Kari Nordmann                   (pre-existing)
18497358: Lars Berg email=lars@fjord.no   ✅ correct
18497369: named Emma email=emma@nordic.se ⚠️ firstName="named", lastName="Emma"
```

**Issues found:**
- ⚠️ **P0 BUG:** "named Emma" — LLM returned `first_name: "named"` instead of `first_name: "Emma"`, `last_name: "Wilson"`. The word "named" was parsed as the first name.

### Products (7 total)
```
84382010-84382025: (pre-existing test products)
84382051: Konsulenttime til 1500 kr       ⚠️ name includes price text
84382156: Frakttjeneste til 2500 kr       ⚠️ name includes price text
```

**Issues found:**
- ⚠️ Product names include price suffix "til 1500 kr" / "til 2500 kr" — the LLM (Claude mode) is not stripping price text from names. The keyword classifier fixes this but the LLM path doesn't benefit from `_clean_name()`.

### Projects (5 total)
```
401950684-401950848: (pre-existing)
401950957: Havnelogistikk                 ✅ correct
```

### Invoices (16 total — includes pre-existing)
- Multiple invoices exist with various amounts
- T2 invoice tests produced HTTP 200 but hard to verify which new invoices were from this test batch

### Contacts (2 total)
```
18493126: Test Tester                     (pre-existing)
18494518: (no name) email=kontakt@nordmann.no  (from earlier test)
```

**Issue:** Per Olsen contact not visible — may have been created but API listing not working, or creation silently failed.

---

## Priority Bugs Found

### P0 — Incorrect data written to Tripletex

| Bug | Test | Expected | Got | Impact |
|-----|------|----------|-----|--------|
| Employee "named" as first name | T1-en-emp | first=Emma, last=Wilson | first=named, last=Emma | Scoring: wrong firstName, wrong lastName = lose points |
| Customer name includes "with email X" | T1-en-cust | name=Nordic Solutions AB, email=info@nordic.se | name="Nordic Solutions AB with email info@nordic.se" | Scoring: wrong name = lose points |
| Product name includes price text | T1-nb-prod | name=Frakttjeneste | name="Frakttjeneste til 2500 kr" | Scoring: wrong name = lose points |
| Department name includes "with number" | T1-en-dept (prev) | name=HR, number=30 | name="HR with number 30" | Scoring: wrong name = lose points |

### P1 — Entities not created (silent failure)

| Bug | Test | Expected | Sandbox | Impact |
|-----|------|----------|---------|--------|
| München GmbH missing | T1-de-cust | Customer created | Not found | Zero points for task |
| Barcelona Tech SL missing | T1-es-cust | Customer created | Not found | Zero points for task |
| Research dept missing | T1-en-dept | Department created | Not found | Zero points for task |
| Per Olsen contact missing | T2-nb-contact | Contact created | Not found | Zero points for task |

### P2 — Missing field extraction

| Bug | Test | Expected | Got | Impact |
|-----|------|----------|-----|--------|
| Dept numbers not extracted | T1-de-dept, T1-fr-dept | departmentNumber=80,90 | empty | Partial score loss |

---

## Root Cause Analysis

**All P0 bugs are in the Claude LLM classifier path** (not the keyword fallback):

1. **"named" as first name** — The Claude LLM is not stripping the English word "named" from names. The system prompt has examples showing correct extraction, but the LLM still includes it. Fix: add post-processing in `_normalize_fields()` to strip known prefixes from first_name/last_name.

2. **"with email X" in customer name** — The LLM parses "Nordic Solutions AB with email info@nordic.se" and includes everything in the name field. Fix: add post-processing to split "X with email Y" patterns.

3. **Product price in name** — Same pattern: LLM includes "til 1500 kr" in the product name. Fix: apply `_clean_name()` to LLM-extracted names too.

4. **Silent failures (P1)** — Likely Tripletex API 4xx errors that are caught and swallowed. The endpoint returns 200 even on failure (by design). Need to check server logs.

**Key insight:** The keyword classifier's `_clean_name()` function fixes most of these, but the LLM path bypasses it entirely. Either:
- Apply `_clean_name()` as post-processing on ALL classifier outputs (both LLM and keyword)
- Or improve the LLM system prompt with more explicit examples

---

## Recommendations

1. **Apply `_clean_name()` to ALL fields** after both LLM and keyword classification (in `_normalize_fields()`)
2. **Add "with email" / "med e-post" / "til X kr" stripping** to `_normalize_fields()`
3. **Add logging for Tripletex API errors** — currently errors are logged but hard to trace back to test cases
4. **Test Cloud Run deployment** separately after fixing bugs
5. **Focus on getting T1 tasks 100% correct** before optimizing T2 — each T1 task is worth up to 2.0 points with efficiency bonus
