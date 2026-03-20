# Cloud Run Test Results

> Endpoint: `https://tripletex-agent-785696234845.europe-north1.run.app`
> LLM mode: `none` (rule-based classifier)
> Tested: 2026-03-20

## Health Check
```
GET /health → {"status":"ok","llm_mode":"none"} (HTTP 200)
```

## Test Results

| # | Prompt | HTTP | Time | Entity Created | Fields Correct |
|---|--------|------|------|----------------|----------------|
| A | `Opprett avdeling CRTest og avdelingsnummer 99` | 200 | 0.31s | **YES** — dept id=870068, name="CRTest", number="99" | name ✅ number ✅ |
| B | `Create customer CR Global Corp with email cr@global.com` | 200 | 0.30s | **YES** — cust id=108178163, name="CR Global Corp", email="cr@global.com" | name ✅ email ✅ |
| C | `Erstellen Kunden CR München GmbH` | 200 | 0.31s | **YES** — cust id=108178165, name="CR München GmbH" | name ✅ |
| D | `Opprett ansatt med fornavn CRTest og etternavn Worker, e-post crtest@test.no` | 200 | 0.85s | **YES** — emp id=18502194, first="CRTest", last="Worker", email="crtest@test.no" | first ✅ last ✅ email ✅ |
| E | `Opprett produkt CRWidget til 999 kr` | 200 | 0.31s | **YES** — prod id=84382317, name="CRWidget", price=999.0 | name ✅ price ✅ |
| F | `Créer département CRFinance numéro 88` | 200 | 0.29s | **YES** — dept id=870074, name="CRFinance", number="88" | name ✅ number ✅ |

## Summary

**6/6 tests passed.** All entities created correctly in the Tripletex sandbox.

### Performance
- Average response time: ~0.39s (fastest: 0.29s, slowest: 0.85s for employee)
- Employee creation slower due to extra API call to check for existing employee

### Observations
- Rule-based classifier (no LLM) handles Norwegian, English, German, and French correctly
- Name extraction is clean — "til 999 kr" correctly extracted as price, not included in name
- Department numbers correctly extracted from "avdelingsnummer N" and "numéro N"
- Email correctly extracted from "with email X" / "e-post X"

### Known Issues from Sandbox
- Earlier test left a product named "Frakttjeneste til 2500 kr" (price in name) — this was before the classifier prompt fix
- Earlier test left a department named "HR with number 30" (number in name) — same issue, now fixed

### Previous Local Test Issues (Now Fixed on Cloud Run)
All issues from local testing are resolved:
- ✅ Names no longer include price suffixes
- ✅ Department numbers correctly extracted
- ✅ Multilingual support working (DE, FR tested)
