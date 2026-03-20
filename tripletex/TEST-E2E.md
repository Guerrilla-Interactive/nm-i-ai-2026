# E2E Test Results — Tripletex Agent (All Tier 1)

> Tested: 2026-03-20 02:00 CET
> Endpoint: localhost:8080 (direct Python, rule-based mode)
> LLM mode: none (rule-based keyword classifier)
> Sandbox: kkpqfuj-amager.tripletex.dev

---

## Summary: 9/9 PASS — All entities verified field-by-field in sandbox

### Departments

| Test | Prompt | Classified | Fields | Sandbox name | Sandbox num | API Calls |
|------|--------|-----------|--------|-------------|-------------|-----------|
| T1-1 | Opprett avdeling E2E-Logistikk avdelingsnummer 41 | create_department | name=E2E-Logistikk, num=41 | E2E-Logistikk | 41 | 1 |
| T1-2 | Create department E2E-Research with number 71 | create_department | name=E2E-Research, num=71 | E2E-Research | 71 | 1 |

### Customers

| Test | Prompt | Classified | Fields | Sandbox name | Sandbox email | API Calls |
|------|--------|-----------|--------|-------------|--------------|-----------|
| T1-3 | Opprett kunde E2E-Fjord AS med e-post e2e@fjord.no | create_customer | name=E2E-Fjord AS, email=e2e@fjord.no | E2E-Fjord AS | e2e@fjord.no | 1 |
| T1-4 | Create customer E2E-Nordic AB with email e2e@nordic.se | create_customer | name=E2E-Nordic AB, email=e2e@nordic.se | E2E-Nordic AB | e2e@nordic.se | 1 |
| T1-5 | Erstellen Sie einen Kunden namens E2E-Hamburg GmbH | create_customer | name=E2E-Hamburg GmbH | E2E-Hamburg GmbH | (none) | 1 |
| T1-6 | Crear un cliente llamado E2E-Madrid SL | create_customer | name=E2E-Madrid SL | E2E-Madrid SL | (none) | 1 |

### Employee

| Test | Prompt | Classified | Fields | Sandbox first | Sandbox last | Sandbox email | API Calls |
|------|--------|-----------|--------|-------------|-------------|--------------|-----------|
| T1-7 | Opprett ansatt fornavn E2E-Lars etternavn Testberg e-post e2e@test.no | create_employee | first=E2E-Lars, last=Testberg, email=e2e@test.no | E2E-Lars | Testberg | e2e@test.no | 2 |

### Product

| Test | Prompt | Classified | Fields | Sandbox name | Sandbox price | API Calls |
|------|--------|-----------|--------|-------------|--------------|-----------|
| T1-8 | Opprett produkt E2E-Frakttjeneste til 2500 kr | create_product | name=E2E-Frakttjeneste, price=2500.0 | E2E-Frakttjeneste | 2500.0 | 1 |

### Project

| Test | Prompt | Classified | Fields | Sandbox name | Sandbox start | API Calls |
|------|--------|-----------|--------|-------------|--------------|-----------|
| T1-9 | Opprett prosjekt E2E-Digitalisering | create_project | name=E2E-Digitalisering | E2E-Digitalisering | 2026-03-20 | 2 |

---

## Field-by-Field Verification

Every extracted field matches exactly what was stored in the Tripletex sandbox:

- Department names: exact match, no noise
- Department numbers: correctly extracted and stored
- Customer names: exact match across Norwegian, English, German, Spanish
- Customer emails: correctly extracted to email field (not in name)
- Employee first/last names: correctly split
- Employee email: correctly extracted
- Product name: clean (no "til 2500 kr" in name)
- Product price: correctly extracted to price field
- Project name: exact match
- Project start date: defaults to today (2026-03-20) when not specified

## API Call Efficiency

| Entity Type | API Calls | Notes |
|------------|-----------|-------|
| Department | 1 | POST /department |
| Customer | 1 | POST /customer |
| Employee | 2 | GET /department (required) + POST /employee |
| Product | 1 | POST /product |
| Project | 2 | GET /employee (for project manager) + POST /project |
| **Total (9 tasks)** | **11** | **Zero 4xx errors** |

## No Bugs Found

All 9 Tier 1 task types work correctly in rule-based mode. Zero field mismatches, zero silent failures, zero 4xx errors.

## Entity IDs (for cross-referencing)

```
Departments: 872237 (E2E-Logistikk), 872238 (E2E-Research)
Customers: 108182471 (E2E-Fjord AS), 108182472 (E2E-Nordic AB), 108182474 (E2E-Hamburg GmbH), 108182476 (E2E-Madrid SL)
Employee: 18506419 (E2E-Lars Testberg)
Product: 84382406 (E2E-Frakttjeneste)
Project: 401951415 (E2E-Digitalisering)
```
