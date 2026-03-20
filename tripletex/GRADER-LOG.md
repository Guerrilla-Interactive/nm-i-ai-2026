# Tripletex Grader Request Log

**Generated:** 2026-03-20 04:10 CET
**Endpoint:** https://tripletex-agent-4nwfkerl6q-lz.a.run.app

## All Grader Requests

| # | Time (UTC) | Language | Prompt | Task Type | Conf | Status | API Calls | Errors | Time | Notes |
|---|-----------|----------|--------|-----------|------|--------|-----------|--------|------|-------|
| 1 | 02:16:58 | NO-nb | Lag faktura til kunde Nordfjord AS: 2 stk Konsulenttjeneste til 1500 kr | CREATE_INVOICE | 0.60 | SUCCESS | 4 | 0 | 1.0s | Rule-based classifier |
| 2 | 02:22:05 | NO-nn | Opprett prosjektet "Analyse Sjøbris" knytt til kunden Sjøbris AS (org.nr 883693329). Prosjektleiar er Steinar Berge (ste... | PROJECT_WITH_CUSTOMER | 0.60 | SUCCESS | 3 | 0 | 6.1s | Rule-based classifier |
| 3 | 02:29:09 | NO-nn | Opprett ein ny avdeling som heiter Marknadsføring | CREATE_DEPARTMENT | 0.98 | FAILED | 1 | 0 | 6.1s | DNS error: wrong base_url? |
| 4 | 02:31:19 | NO-nb | Opprett prosjektet "Test" knytt til kunden TestCorp AS... | PROJECT_WITH_CUSTOMER | 0.98 | FAILED | 1 | 2 | 7.7s | 401 — expired token |
| 5 | 02:32:55 | DE | Erstellen Sie das Produkt "Datenberatung" mit der Produktnummer 5524. Der Preis beträgt 22550 NOK ohne MwSt., mit dem St... | CREATE_PRODUCT | 0.98 | SUCCESS | 1 | 0 | 8.9s | Gemini. **Check 4 failed** (vatType=0% not 25%) |
| 6 | 02:39:40 | — | *(empty prompt)* | — | — | — | 0 | 0 | — | Missing credentials (health check?) |
| 7 | 02:40:26 | DE | Erstellen Sie den Kunden Grünfeld GmbH mit der Organisationsnummer 835026434. Die Adresse ist Fjordveien 105, 3015 Dramm... | CREATE_CUSTOMER | 0.98 | SUCCESS | 1 | 0 | 9.2s | Gemini |
| 8 | 02:42:14 | EN | Create three departments in Tripletex: "Utvikling", "Innkjøp", and "Salg". | UNKNOWN | 0.00 | FAILED | 0 | 0 | 8.6s | **0 SCORE** — Gemini returned list, both retries failed, keyword fallback → UNKNOWN |
| 9 | 02:46:05 | NO-nn | Opprett ein tilsett med namn Kari Nordmann, e-post kari@example.org | CREATE_EMPLOYEE | 0.98 | FAILED | 1 | 2 | 6.8s | 401 — expired sandbox token (our manual test) |
| 10 | 02:59:39 | EN | Create three departments in Tripletex: "Utvikling", "Innkjop", and "Salg". | BATCH (3x DEPT) | — | FAILED | 3 | 6 | 9.5s | Batch works now! 401 from fake token (our test) |
| 11-15 | 02:59-03:00 | mixed | *(our manual tests with fake tokens)* | various | 0.96-0.98 | FAILED | 1-2 | 2-3 | 4-6s | All 401 — fake token, classification correct |
| 16 | 03:02:42 | FR | Le client Colline SARL (nº org. 850491941) a une facture impayée de 10550 NOK hors TVA pour "Heures de conseil". Enregis... | REGISTER_PAYMENT | 0.75 | FAILED | 1 | 0 | 43.6s | **MISCLASSIFIED** — should be INVOICE_WITH_PAYMENT. Searched for invoice #850491941 (org nr, not invoice nr) |
| 17 | 03:06:45 | FR | *(same prompt, our retest)* | INVOICE_WITH_PAYMENT | 0.97 | FAILED | 1 | 2 | 12.3s | Fixed! 401 from fake token |

## Grader Prompt Patterns

### Languages Observed
- **Norwegian Nynorsk (nn):** Most common. Uses "ein", "heiter", "knytt til", "tilsett", "reiserekning"
- **Norwegian Bokmål (nb):** "Lag faktura", "Opprett prosjektet"
- **German (de):** "Erstellen Sie...", uses "MwSt" for VAT, "Organisationsnummer"
- **English (en):** "Create three departments..."
- **French (fr):** "Le client... facture impayée... Enregistrer le paiement"

### Task Types Observed from Grader
1. **CREATE_INVOICE** — "Lag faktura til kunde X: N stk Y til Z kr"
2. **PROJECT_WITH_CUSTOMER** — "Opprett prosjektet 'X' knytt til kunden Y AS (org.nr Z). Prosjektleiar er A B (email)"
3. **CREATE_DEPARTMENT** — "Opprett ein ny avdeling som heiter X" / Batch: "Create three departments: X, Y, Z"
4. **CREATE_PRODUCT** — "Erstellen Sie das Produkt X mit der Produktnummer N. Der Preis beträgt Y NOK ohne MwSt., mit dem Steuersatz Z%"
5. **CREATE_CUSTOMER** — "Erstellen Sie den Kunden X mit der Organisationsnummer Y. Die Adresse ist Z"
6. **INVOICE_WITH_PAYMENT** — "Le client X (nº org. Y) a une facture impayée de Z NOK hors TVA pour 'description'. Enregistrer le paiement"

### Key Patterns
- Grader includes **org numbers** in customer/invoice prompts
- Grader includes **addresses** (street, postal code, city)
- Grader includes **project manager name + email** in project prompts
- Grader sends **batch operations** (multiple entities in one prompt)
- Grader sends **multi-step tasks** (create customer + invoice + payment)
- Prompts are often **120+ chars** with multiple data fields
- **VAT rates** are specified explicitly in product prompts

## Failures & Root Causes

| Failure | Root Cause | Fix Applied |
|---------|-----------|-------------|
| Product Check 4 failed (vatType) | Hardcoded vatType=6 (0%), grader wanted 25% | Dynamic VAT lookup via /ledger/vatType |
| Batch departments → UNKNOWN | Gemini returned JSON list, `data.get()` crashed | List unwrapping in `_parse_response` + batch handler |
| French invoice → REGISTER_PAYMENT | Gemini confused "facture impayée" with existing invoice | Added disambiguation rules + few-shot examples |
| Invoice #orgNumber not found | Org number extracted as invoice identifier | Fixed: INVOICE_WITH_PAYMENT creates customer+invoice first |

## Scoring History

| Submission | Task | Score | Details |
|-----------|------|-------|---------|
| V6 | CREATE_PRODUCT | 5/7 (71%) | Check 4 failed (vatType) |
| V7 | CREATE_PRODUCT | 6/7 (86%) | Check 4 still failed |
| V8 | CREATE_PRODUCT | 7/7 (100%) | vatType fix deployed |
| V9 | INVOICE_WITH_PAYMENT | 2/7 (29%) | Misclassified as REGISTER_PAYMENT |

## Task Types NOT Yet Seen from Grader
- CREATE_EMPLOYEE (tested manually, not from grader with valid creds)
- UPDATE_EMPLOYEE / DELETE_EMPLOYEE
- SET_EMPLOYEE_ROLES
- UPDATE_CUSTOMER
- CREATE_TRAVEL_EXPENSE / DELETE_TRAVEL_EXPENSE
- CREATE_CONTACT
- FIND_CUSTOMER
- CREATE_CREDIT_NOTE
- REGISTER_PAYMENT (standalone)
- UPDATE_PROJECT / DELETE_PROJECT
- PROJECT_BILLING
- BANK_RECONCILIATION
- ERROR_CORRECTION
- YEAR_END_CLOSING
- ENABLE_MODULE
