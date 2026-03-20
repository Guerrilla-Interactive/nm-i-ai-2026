# Tripletex Sandbox Audit

**Date:** 2026-03-20
**Sandbox:** kkpqfuj-amager.tripletex.dev
**Company ID:** 108167433

---

## Summary

| Entity Type     | Count | Status |
|-----------------|-------|--------|
| Employees       | 20    | OK     |
| Customers       | 30    | OK     |
| Products        | 16    | OK     |
| Departments     | 27    | OK     |
| Projects        | 12    | OK     |
| Orders          | 25    | OK     |
| Invoices        | 28    | OK     |
| Travel Expenses | 9     | OK     |
| Ledger Accounts | 21+   | OK (system-provided) |
| Company         | -     | Endpoint /company returns 405, /company/with/me returns 404 |

---

## Employees (20 total)

| ID       | Name                    | Email                          | Origin  |
|----------|-------------------------|--------------------------------|---------|
| 18491802 | Frikk a23fd25c          | frikk@guerrilla.no             | Pre-existing (admin) |
| 18492587 | Ola Nordmann            | ola@example.com                | Agent   |
| 18493396 | Delete MePlease         | deleteme@example.com           | Agent (test) |
| 18493534 | TypeTest STANDARD       | type_STANDARD@example.com      | Agent (test) |
| 18493536 | Ola Nordmann            | ola2@test.no                   | Agent   |
| 18493562 | TypeTest2 NO_ACCESS     | type2_NO_ACCESS@example.com    | Agent (test) |
| 18493564 | TypeTest2 EXTENDED      | type2_EXTENDED@example.com     | Agent (test) |
| 18494521 | Kari Hansen             | kari@test.no                   | Agent   |
| 18497054 | Kari Nordmann           | kari@example.com               | Agent   |
| 18497358 | Lars Berg               | lars@fjord.no                  | Agent   |
| 18497369 | named Emma              | emma@nordic.se                 | Agent   |
| 18499667 | Olaleotl Nordmannleotl  | leotl@example.com              | Agent (E2E test) |
| 18499842 | Olarluxc Nordmannrluxc  | rluxc@example.com              | Agent (E2E test) |
| 18499881 | Olaemkeh Nordmannemkeh  | emkeh@example.com              | Agent (E2E test) |
| 18501222 | Test Bruker             | test@bruker.no                 | Agent   |
| 18501601 | Arne Svendsen           | arne@test.no                   | Agent   |
| 18501684 | Test2 Bruker2           | test2@bruker.no                | Agent   |
| 18502194 | CRTest Worker           | crtest@test.no                 | Agent (CloudRun) |
| 18503378 | ECAnna ECLarsen         | ecanna@test.no                 | Agent (EC test) |
| 18503382 | ECAnna ECLarsen         | ecanna.eclarsen@example.com    | Agent (EC test) |

**Notes:** Only employee 18491802 (Frikk) is pre-existing (sandbox admin with employment record). All others were created by our agent during testing.

---

## Customers (30 total)

| ID        | # | Name                                              | Email              | Origin  |
|-----------|---|---------------------------------------------------|--------------------|---------|
| 108168219 | 10001 | Testbedrift AS                                | ny@testbedrift.no  | Agent   |
| 108168567 | 10002 | Test Customer AS                              |                    | Agent   |
| 108169123 | 10003 | Test Firma AS                                 |                    | Agent   |
| 108170200 | 10004 | Invoice Test Firma AS                         | test@faktura.no    | Agent   |
| 108170479 | 10005 | Direct Test Corp                              |                    | Agent   |
| 108170621 | 10006 | Nordmann Handel AS                            | kontakt@nordmann.no | Agent   |
| 108172892 | 10007 | Nordic Solutions AS with email info@nordic.no | info@nordic.no     | Agent   |
| 108173073 | 10008 | Fjord Shipping AS                             |                    | Agent   |
| 108173088 | 10009 | Nordic Solutions AB with email info@nordic.se | info@nordic.se     | Agent   |
| 108173101 | 10010 | Paris Conseil SAS                             |                    | Agent   |
| 108173205 | 10011 | CloudRun Test AS                              |                    | Agent (CloudRun) |
| 108175270 | 10012 | AcmeE2E0320010532 AS                          |                    | Agent (E2E test) |
| 108175399 | 10013 | Acmerxewn AS                                  |                    | Agent (E2E test) |
| 108175423 | 10014 | Test AS                                       |                    | Agent (E2E test) |
| 108175492 | 10015 | Acmeleotl AS                                  |                    | Agent (E2E test) |
| 108175669 | 10016 | Acmerluxc AS                                  |                    | Agent (E2E test) |
| 108175684 | 10017 | Testkunde AS                                  |                    | Agent (E2E test) |
| 108175717 | 10018 | Acmeemkeh AS                                  |                    | Agent (E2E test) |
| 108177476 | 10019 | LiveTest AS                                   | info@livetest.no   | Agent   |
| 108177534 | 10020 | NordTech AS                                   | info@nordtech.no   | Agent   |
| 108177536 | 10021 | EuroSoft AB                                   | info@eurosoft.se   | Agent   |
| 108177539 | 10022 | Berlin Tech GmbH                              |                    | Agent   |
| 108177542 | 10023 | Valencia Solutions SL                         |                    | Agent   |
| 108177624 | 10024 | TestFirma AS                                  | test@testfirma.no  | Agent   |
| 108177627 | 10025 | Global Corp                                   | info@global.com    | Agent   |
| 108177628 | 10026 | Hamburg GmbH                                  |                    | Agent   |
| 108177629 | 10027 | Madrid Tech SL                                |                    | Agent   |
| 108178163 | 10028 | CR Global Corp                                | cr@global.com      | Agent (CloudRun) |
| 108178165 | 10029 | CR Munchen GmbH                               |                    | Agent (CloudRun) |
| 108179370 | 10030 | EC Barcelona Tech SL                          | info@ecbarcelona.es | Agent (EC test) |

**Notes:** All 30 customers were created by our agent. No pre-existing customers in sandbox. Naming patterns show different test phases: manual tests, E2E automated (random suffixes like rxewn, leotl, rluxc, emkeh), CloudRun (CR prefix), and EC tests.

---

## Products (16 total)

| ID       | Name                        | Price (ex VAT) | Origin  |
|----------|-----------------------------|----------------|---------|
| 84382010 | Test Product                | 0              | Agent   |
| 84382015 | API Test Product Minimal    | 0              | Agent   |
| 84382020 | API Test Product v3         | 0              | Agent   |
| 84382021 | API Test Product v4         | 0              | Agent   |
| 84382025 | Widget with price 299 NOK   | 299            | Agent   |
| 84382051 | Konsulenttime til 1500 kr   | 1500           | Agent   |
| 84382156 | Frakttjeneste til 2500 kr   | 2500           | Agent   |
| 84382219 | WidgetE2E0320010532         | 199            | Agent (E2E test) |
| 84382225 | Widgetrxewn                 | 199            | Agent (E2E test) |
| 84382228 | Widgetleotl                 | 199            | Agent (E2E test) |
| 84382233 | Widgetrluxc                 | 199            | Agent (E2E test) |
| 84382235 | Widgetemkeh                 | 199            | Agent (E2E test) |
| 84382298 | Konsultasjon                | 2200           | Agent   |
| 84382304 | Raadgivning                 | 1800           | Agent   |
| 84382317 | CRWidget                    | 999            | Agent (CloudRun) |
| 84382337 | ECKonsulenttime             | 1500           | Agent (EC test) |

**Notes:** All 16 products created by agent. E2E test products use "Widget" + random suffix pattern at 199 NOK.

---

## Departments (27 total)

| ID     | Name            | Number | Origin  |
|--------|-----------------|--------|---------|
| 864717 | Avdeling        |        | Pre-existing (default) |
| 865127 | Hovedavdeling   | 1      | Agent   |
| 865587 | Salg            | 10     | Agent   |
| 865590 | Marketing       |        | Agent   |
| 866144 | IT              | 20     | Agent   |
| 866149 | HR with number 30 |      | Agent   |
| 867134 | Teknologi       | 50     | Agent   |
| 867497 | Marketing       |        | Agent (duplicate) |
| 867581 | Logistikk       | 60     | Agent   |
| 867595 | Vertrieb        |        | Agent   |
| 867596 | Finance         |        | Agent   |
| 868645 | Salg0320010532  |        | Agent (E2E test) |
| 868718 | Salgrxewn       |        | Agent (E2E test) |
| 868767 | Salgleotl       |        | Agent (E2E test) |
| 868850 | Salgrluxc       |        | Agent (E2E test) |
| 868868 | Salgemkeh       |        | Agent (E2E test) |
| 869735 | Kvalitet        | 40     | Agent   |
| 869758 | Testing         | 55     | Agent   |
| 869759 | QA              | 65     | Agent   |
| 869760 | Forschung       | 75     | Agent   |
| 869762 | RH              | 85     | Agent   |
| 869806 | Kvalitet        | 77     | Agent (duplicate) |
| 869807 | Innovation      | 78     | Agent   |
| 870068 | CRTest          | 99     | Agent (CloudRun) |
| 870074 | CRFinance       | 88     | Agent (CloudRun) |
| 870678 | ECKundeservice  |        | Agent (EC test) |
| 871268 | Logistikk       | 600    | Agent (duplicate) |

**Notes:** Department 864717 ("Avdeling") is the pre-existing default. All others agent-created. Some duplicates exist (Marketing x2, Kvalitet x2, Logistikk x2).

---

## Projects (12 total)

| ID        | # | Name                | Start Date  | Customer      | Origin  |
|-----------|---|---------------------|-------------|---------------|---------|
| 401950684 | 3 | API Test Project v2 | 2026-03-20  |               | Agent   |
| 401950691 | 99001 | API Test Project | 2026-03-20  |               | Agent   |
| 401950848 | 99015 | Fix Verify Project | 2026-03-20  |              | Agent   |
| 401950957 | 99016 | Havnelogistikk    | 2026-03-20  |               | Agent   |
| 401951089 | 99017 | Prosjektrxewn     | 2026-03-20  |               | Agent (E2E test) |
| 401951092 | 99018 | Prosjektleotl     | 2026-03-20  |               | Agent (E2E test) |
| 401951100 | 99019 | Prosjektrluxc     | 2026-03-20  |               | Agent (E2E test) |
| 401951104 | 99021 | Prosjektemkeh     | 2026-03-20  |               | Agent (E2E test) |
| 401951202 | 99023 | Digitalisering    | 2026-03-20  |               | Agent   |
| 401951298 | 99032 | Webshop           | 2026-03-20  | NordTech AS   | Agent   |
| 401951300 | 99034 | Mobile App        | 2026-04-01  | EuroSoft AB   | Agent   |
| 401951304 | 99035 | DataMigrasjon     | 2026-03-20  | TestFirma AS  | Agent   |

**Notes:** All 12 projects created by agent. All use employee 18491802 (Frikk) as project manager. E2E test projects follow "Prosjekt" + random suffix pattern.

---

## Orders (25 total)

| ID        | # | Customer              | Date       | Closed | Origin  |
|-----------|---|-----------------------|------------|--------|---------|
| 401950669 | 1 | Test Customer AS      | 2026-03-20 | Yes    | Agent   |
| 401950693 | 2 | Test Customer AS      | 2026-03-20 | Yes    | Agent   |
| 401950700 | 3 | Test Customer AS      | 2026-03-20 | Yes    | Agent   |
| 401950701 | 4 | Test Customer AS      | 2026-03-20 | Yes    | Agent   |
| 401950703 | 5 | Test Customer AS      | 2026-03-20 | Yes    | Agent   |
| 401950708 | 6 | Test Firma AS         | 2026-03-20 | Yes    | Agent   |
| 401950709 | 7 | Test Firma AS         | 2026-03-20 | Yes    | Agent   |
| 401950715 | 8 | Invoice Test Firma AS | 2026-03-20 | Yes    | Agent   |
| 401950718 | 9 | Invoice Test Firma AS | 2026-03-20 | Yes    | Agent   |
| 401950719 | 10 | Invoice Test Firma AS | 2026-03-20 | Yes   | Agent   |
| 401950720 | 11 | Invoice Test Firma AS | 2026-03-20 | Yes   | Agent   |
| 401950722 | 12 | Nordmann Handel AS    | 2026-03-20 | Yes   | Agent   |
| 401950853 | 13 | Test Firma AS         | 2026-03-20 | No    | Agent   |
| 401950862 | 14 | Test Firma AS         | 2026-03-20 | No    | Agent   |
| 401950863 | 15 | Test Firma AS         | 2026-03-20 | No    | Agent   |
| 401950864 | 16 | Test Firma AS         | 2026-03-20 | No    | Agent   |
| 401950865 | 17 | Test Firma AS         | 2026-03-20 | No    | Agent   |
| 401951091 | 18 | Acmerxewn AS          | 2026-03-20 | Yes   | Agent (E2E test) |
| 401951094 | 19 | Acmeleotl AS          | 2026-03-20 | Yes   | Agent (E2E test) |
| 401951103 | 20 | Acmerluxc AS          | 2026-03-20 | Yes   | Agent (E2E test) |
| 401951106 | 21 | Acmeemkeh AS          | 2026-03-20 | Yes   | Agent (E2E test) |
| 401951203 | 22 | Nordmann Handel AS    | 2026-03-20 | Yes   | Agent   |
| 401951296 | 23 | NordTech AS           | 2026-03-20 | Yes   | Agent   |
| 401951301 | 24 | EuroSoft AB           | 2026-03-20 | Yes   | Agent   |
| 401951305 | 25 | TestFirma AS          | 2026-03-20 | Yes   | Agent   |

**Notes:** All 25 orders created by agent. Most are closed (invoiced). Orders 13-17 remain open.

---

## Invoices (28 total)

| # | Date       | Customer              | Amount (NOK) | Credited | Origin  |
|---|------------|-----------------------|--------------|----------|---------|
| 1 | 2026-03-20 | Test Customer AS      | 400          | No       | Agent   |
| 2 | 2026-03-20 | Test Customer AS      | 0            | No       | Agent   |
| 3 | 2026-03-20 | Test Customer AS      | 400          | No       | Agent   |
| 4 | 2026-03-20 | Test Customer AS      | 400          | No       | Agent   |
| 5 | 2026-03-20 | Test Customer AS      | 400          | No       | Agent   |
| 6 | 2026-03-20 | Test Firma AS         | 400          | Yes      | Agent   |
| 7 | 2026-03-20 | Test Firma AS         | 400          | No       | Agent   |
| 8 | 2026-03-20 | Invoice Test Firma AS | 100          | No       | Agent   |
| 9 | 2026-03-20 | Invoice Test Firma AS | 100          | No       | Agent   |
| 10 | 2026-03-20 | Invoice Test Firma AS | 100         | No       | Agent   |
| 11 | 2026-03-20 | Invoice Test Firma AS | 100         | No       | Agent   |
| 12 | 2026-03-20 | Nordmann Handel AS    | 400         | No       | Agent   |
| 13 | 2026-03-20 | Test Firma AS         | -400        | Credit   | Agent   |
| 14-28 | 2026-03-20 | Various            | Various     | Various  | Agent (E2E/CloudRun/EC) |

**Notes:** All 28 invoices created by agent. Invoice #13 is a credit note (negative amount). Full invoicing pipeline works end-to-end.

---

## Travel Expenses (9 total)

| ID       | # | Title                | Employee       | Amount | State | Origin  |
|----------|---|----------------------|----------------|--------|-------|---------|
| 11142106 | 1 | API Test Expense     | Frikk a23fd25c | 400    | Open  | Agent   |
| 11142133 | 2 | Kundebesok Oslo      | Kari Hansen    | 0      | Open  | Agent   |
| 11142145 | 3 | Kundebesok Bergen    | Frikk a23fd25c | 0      | Open  | Agent   |
| 11142149 | 4 | Final Test Trip      | Frikk a23fd25c | 0      | Open  | Agent   |
| 11142162 | 5 | (untitled)           | Frikk a23fd25c | 0      | Open  | Agent   |
| 11142212 | 6 | Travel Expense       | Frikk a23fd25c | 0      | Open  | Agent   |
| 11142214 | 7 | Travel Expense       | Frikk a23fd25c | 0      | Open  | Agent   |
| 11142218 | 8 | Kundebesok Stavanger | Arne Svendsen  | 0      | Open  | Agent   |
| 11142220 | 9 | Kundebesok Stavanger | Arne Svendsen  | 0      | Open  | Agent   |

**Notes:** All 9 travel expenses created by agent. All in OPEN state (not delivered/approved). Only expense #1 has actual costs (400 NOK with 4 cost lines).

---

## Ledger Accounts (21+ total, first 20 shown)

Standard Norwegian chart of accounts (Norsk Standard Kontoplan). These are **system-provided**, not agent-created. Account numbers start from 1000.

---

## Key Observations

1. **Pre-existing entities:** Only 2 things existed before our agent:
   - Employee 18491802 (Frikk a23fd25c) - sandbox admin
   - Department 864717 (Avdeling) - default department
   - Ledger accounts (system-provided chart of accounts)

2. **Everything else was created by our agent.** All customers, products, projects, orders, invoices, and travel expenses.

3. **E2E test artifacts:** Multiple test runs left entities with random suffixes (rxewn, leotl, rluxc, emkeh, E2E0320010532). These follow a consistent naming pattern across entity types.

4. **Test phase naming patterns:**
   - Early manual tests: generic names (Test Product, Ola Nordmann)
   - E2E automated: random 5-char suffixes (Widgetrxewn, Prosjektleotl)
   - CloudRun tests: "CR" prefix (CRWidget, CRTest Worker)
   - EC tests: "EC" prefix (ECKonsulenttime, ECAnna ECLarsen)

5. **Working features:** Employee CRUD, Customer CRUD, Product CRUD, Department CRUD, Project CRUD, Order creation + closing, Invoice creation (including credit notes), Travel Expense creation with costs.

6. **Not tested / not working:**
   - Company endpoint returns 405/404 (different from standard GET)
   - No travel expenses in delivered/approved state
   - Most travel expenses have 0 amount (no cost lines)
