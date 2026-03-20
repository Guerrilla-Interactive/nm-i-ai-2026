# Tier 2 Classifier Test Results

**Date:** 2026-03-20
**LLM Mode:** rule-based (no GEMINI_MODEL or ANTHROPIC_API_KEY set)
**Total tests:** 39
**Type classification correct:** 34/39
**Fully passed (type + fields):** 28/39

## Summary by Task Type

| Task Type | Tests | Type OK | Fully Passed |
|-----------|-------|---------|--------------|
| `invoice_existing_customer` | 3 | 2/3 | 2/3 FAIL |
| `register_payment` | 4 | 3/4 | 3/4 FAIL |
| `create_credit_note` | 3 | 3/3 | 3/3 PASS |
| `invoice_with_payment` | 4 | 4/4 | 4/4 PASS |
| `create_travel_expense` | 4 | 4/4 | 2/4 PARTIAL |
| `delete_travel_expense` | 3 | 3/3 | 3/3 PASS |
| `project_with_customer` | 3 | 3/3 | 3/3 PASS |
| `project_billing` | 3 | 1/3 | 0/3 FAIL |
| `create_contact` | 3 | 3/3 | 0/3 PARTIAL |
| `find_customer` | 3 | 2/3 | 2/3 FAIL |
| `update_project` | 3 | 3/3 | 3/3 PASS |
| `delete_project` | 3 | 3/3 | 3/3 PASS |

## Critical Disambiguation Tests

- **invoice_with_payment - French (facture impayee) CRITICAL**: PASS (expected `invoice_with_payment`, got `invoice_with_payment`)
- **invoice_with_payment - German (unbezahlte Rechnung) CRITICAL**: PASS (expected `invoice_with_payment`, got `invoice_with_payment`)
- **register_payment - Norwegian disambiguation**: PASS (expected `register_payment`, got `register_payment`)
- **create_contact - Norwegian (kontaktperson) CRITICAL**: PASS (expected `create_contact`, got `create_contact`)

## Detailed Results

### INVOICE_EXISTING_CUSTOMER

**[PASS] invoice_existing_customer - Norwegian**
- Prompt: `Fakturer kunde Aker Solutions med 5 stk Konsulenttimer til 1200 kr`
- Expected type: `invoice_existing_customer` | Got: `invoice_existing_customer` (correct)
- Extracted fields: `{"price_excluding_vat": 1200.0, "customer_name": "Aker Solutions", "lines": [{"description": "Konsulenttimer", "quantity": 5, "unit_price": 1200.0}]}`

**[PASS] invoice_existing_customer - English**
- Prompt: `Create an invoice for existing customer Nordic Tech AS for 10 hours consulting at 1500 NOK`
- Expected type: `invoice_existing_customer` | Got: `invoice_existing_customer` (correct)
- Extracted fields: `{"price_excluding_vat": 1500.0, "customer_name": "Nordic Tech AS", "lines": [{"description": "consulting", "quantity": 10, "unit_price": 1500.0}]}`

**[FAIL] invoice_existing_customer - French**
- Prompt: `Facturer le client Dupont SARL pour 3 pcs Widget at 500 NOK`
- Expected type: `invoice_existing_customer` | Got: `unknown` (WRONG)
  - MISSING expected field 'customer_name'

### REGISTER_PAYMENT

**[PASS] register_payment - Norwegian**
- Prompt: `Registrer innbetaling på faktura 10042 med beløp 15000 kr, dato 15.03.2026`
- Expected type: `register_payment` | Got: `register_payment` (correct)
- Extracted fields: `{"price_excluding_vat": 15000.0, "invoice_id": "10042", "amount": 15000.0}`

**[PASS] register_payment - English**
- Prompt: `Register payment on invoice 20055 amount 8500 NOK`
- Expected type: `register_payment` | Got: `register_payment` (correct)
- Extracted fields: `{"price_excluding_vat": 8500.0, "invoice_id": "20055", "amount": 8500.0}`

**[FAIL] register_payment - German**
- Prompt: `Registrieren Sie die Zahlung für Rechnung 30099, Betrag 12000 NOK`
- Expected type: `register_payment` | Got: `create_invoice` (WRONG)
- Extracted fields: `{"price_excluding_vat": 12000.0}`
  - MISSING expected field 'invoice_id'

**[PASS] register_payment - Norwegian disambiguation**
- Prompt: `Registrer innbetaling på faktura 12345 med beløp 5000 kr`
- Expected type: `register_payment` | Got: `register_payment` (correct)
- Extracted fields: `{"price_excluding_vat": 5000.0, "invoice_id": "12345", "amount": 5000.0}`

### CREATE_CREDIT_NOTE

**[PASS] create_credit_note - Norwegian**
- Prompt: `Opprett kreditnota for faktura 10055`
- Expected type: `create_credit_note` | Got: `create_credit_note` (correct)
- Extracted fields: `{"invoice_id": "10055"}`

**[PASS] create_credit_note - English**
- Prompt: `Create a credit note for invoice 20033`
- Expected type: `create_credit_note` | Got: `create_credit_note` (correct)
- Extracted fields: `{"invoice_id": "20033"}`

**[PASS] create_credit_note - German**
- Prompt: `Erstellen Sie eine Gutschrift für Rechnung 40077`
- Expected type: `create_credit_note` | Got: `create_credit_note` (correct)
- Extracted fields: `{"invoice_id": "40077"}`

### INVOICE_WITH_PAYMENT

**[PASS] invoice_with_payment - French (facture impayee) CRITICAL**
- Prompt: `Le client Colline SARL (org. nr. 850491941) a une facture impayée de 10550 NOK pour "Heures de conse...`
- Expected type: `invoice_with_payment` | Got: `invoice_with_payment` (correct)
- Extracted fields: `{"price_excluding_vat": 10550.0, "organization_number": "850491941", "customer_name": "Colline SARL (org", "amount": 10550.0}`

**[PASS] invoice_with_payment - German (unbezahlte Rechnung) CRITICAL**
- Prompt: `Der Kunde Müller GmbH (Org.Nr. 912345678) hat eine unbezahlte Rechnung über 5000 NOK für Beratung. Z...`
- Expected type: `invoice_with_payment` | Got: `invoice_with_payment` (correct)
- Extracted fields: `{"price_excluding_vat": 5000.0, "organization_number": "912345678", "customer_name": "Müller GmbH (Org", "amount": 5000.0}`

**[PASS] invoice_with_payment - English**
- Prompt: `Create an invoice for Acme Corp for 3 hours consulting at 1500 NOK/hr, already paid in full`
- Expected type: `invoice_with_payment` | Got: `invoice_with_payment` (correct)
- Extracted fields: `{"price_excluding_vat": 1500.0, "customer_name": "Acme Corp", "lines": [{"description": "consulting", "quantity": 3, "unit_price": 1500.0}], "amount": 1500.0}`

**[PASS] invoice_with_payment - Norwegian**
- Prompt: `Opprett faktura med betaling for kunde Berg AS, 2 stk Vedlikehold til 3000 kr, betalt i sin helhet`
- Expected type: `invoice_with_payment` | Got: `invoice_with_payment` (correct)
- Extracted fields: `{"price_excluding_vat": 3000.0, "customer_name": "Berg AS", "lines": [{"description": "Vedlikehold", "quantity": 2, "unit_price": 3000.0}], "amount": 3000.0}`

### CREATE_TRAVEL_EXPENSE

**[FAIL] create_travel_expense - Norwegian**
- Prompt: `Opprett reiseregning for ansatt Per Hansen, fra Bergen til Oslo 19. mars 2026, formål: kundemøte`
- Expected type: `create_travel_expense` | Got: `create_travel_expense` (correct)
- Extracted fields: `{"first_name": "Per", "last_name": "Hansen"}`
  - MISSING expected field 'employee_identifier'

**[FAIL] create_travel_expense - English**
- Prompt: `Create a travel expense for employee Jane Smith, from London to Oslo departure 2026-04-01, return 20...`
- Expected type: `create_travel_expense` | Got: `create_travel_expense` (correct)
- Extracted fields: `{"first_name": "Jane", "last_name": "Smith"}`
  - MISSING expected field 'employee_identifier'

**[PASS] create_travel_expense - German**
- Prompt: `Erstellen Sie eine Reisekostenabrechnung für Mitarbeiter Hans Weber, von München nach Berlin`
- Expected type: `create_travel_expense` | Got: `create_travel_expense` (correct)
- Extracted fields: `{"title": "für Mitarbeiter Hans Weber"}`

**[PASS] create_travel_expense - French**
- Prompt: `Créer une note de frais de voyage pour employé Marie Dupont, de Paris à Oslo`
- Expected type: `create_travel_expense` | Got: `create_travel_expense` (correct)
- Extracted fields: `{"first_name": "Marie", "last_name": "Dupont", "title": "de voyage pour employé Marie Dupont"}`

### DELETE_TRAVEL_EXPENSE

**[PASS] delete_travel_expense - Norwegian**
- Prompt: `Slett reiseregning 11142218`
- Expected type: `delete_travel_expense` | Got: `delete_travel_expense` (correct)
- Extracted fields: `{"title": "11142218", "travel_expense_id": "11142218"}`

**[PASS] delete_travel_expense - English**
- Prompt: `Delete travel expense 11142145`
- Expected type: `delete_travel_expense` | Got: `delete_travel_expense` (correct)
- Extracted fields: `{"title": "11142145", "travel_expense_id": "11142145"}`

**[PASS] delete_travel_expense - Norwegian (fjern)**
- Prompt: `Fjern reiseregning 99887766`
- Expected type: `delete_travel_expense` | Got: `delete_travel_expense` (correct)
- Extracted fields: `{"title": "99887766", "travel_expense_id": "99887766"}`

### PROJECT_WITH_CUSTOMER

**[PASS] project_with_customer - Norwegian**
- Prompt: `Opprett prosjekt Nettside for kunde Digitalbyrå AS, start 2026-04-01, fast pris 50000 kr`
- Expected type: `project_with_customer` | Got: `project_with_customer` (correct)
- Extracted fields: `{"name": "Nettside", "price_excluding_vat": 50000.0, "customer_name": "Digitalbyrå AS", "start_date": "2026-04-01"}`

**[PASS] project_with_customer - English with details**
- Prompt: `Create project 'Website Redesign' for customer Acme Corp, org number 912345678, project manager Erik...`
- Expected type: `project_with_customer` | Got: `project_with_customer` (correct)
- Extracted fields: `{"name": "Website Redesign", "customer_name": "Acme Corp", "project_manager_name": "ik Olsen"}`

**[PASS] project_with_customer - French**
- Prompt: `Créer un projet Migration pour client Tech Solutions SA`
- Expected type: `project_with_customer` | Got: `project_with_customer` (correct)
- Extracted fields: `{"name": "Tech Solutions SA", "customer_name": "Tech Solutions SA"}`

### PROJECT_BILLING

**[FAIL] project_billing - Norwegian**
- Prompt: `Fakturer prosjekt Nettside med 20 timer utvikling til 1500 kr`
- Expected type: `project_billing` | Got: `project_billing` (correct)
- Extracted fields: `{"price_excluding_vat": 1500.0, "lines": [{"description": "utvikling", "quantity": 20, "unit_price": 1500.0}], "project_name": "Nettside"}`
  - MISSING expected field 'project_identifier'

**[FAIL] project_billing - English**
- Prompt: `Invoice project Website Redesign for 40 hours development at 1200 NOK`
- Expected type: `project_billing` | Got: `create_invoice` (WRONG)
- Extracted fields: `{"price_excluding_vat": 1200.0, "lines": [{"description": "development", "quantity": 40, "unit_price": 1200.0}]}`
  - MISSING expected field 'project_identifier'

**[FAIL] project_billing - Norwegian (prosjektfaktura)**
- Prompt: `Prosjektfaktura for prosjekt Alpha med 5 stk Konsulenttimer til 800 kr`
- Expected type: `project_billing` | Got: `unknown` (WRONG)

### CREATE_CONTACT

**[FAIL] create_contact - French (Creer un contact)**
- Prompt: `Créer un contact pour client Acme SA: Pierre Dupont, pierre@acme.fr`
- Expected type: `create_contact` | Got: `create_contact` (correct)
- Extracted fields: `{"email": "pierre@acme.fr", "customer_name": "Acme SA: Pierre Dupont", "name": "Acme SA: Pierre Dupont"}`
  - MISSING expected field 'first_name'
  - MISSING expected field 'last_name'

**[FAIL] create_contact - Norwegian (kontaktperson) CRITICAL**
- Prompt: `Opprett kontaktperson Erik Berg for kunde Aker Solutions, e-post erik@aker.no`
- Expected type: `create_contact` | Got: `create_contact` (correct)
- Extracted fields: `{"email": "erik@aker.no", "first_name": "Erik", "last_name": "Berg", "customer_name": "Aker Solutions", "name": "Aker Solutions"}`
  - MISSING expected field 'customer_identifier'

**[FAIL] create_contact - English**
- Prompt: `Add a contact person for customer Nordfjord AS: Jane Doe, jane@nordfjord.no, mobile 99887766`
- Expected type: `create_contact` | Got: `create_contact` (correct)
- Extracted fields: `{"email": "jane@nordfjord.no", "customer_name": "Nordfjord AS: Jane Doe", "name": "Nordfjord AS: Jane Doe"}`
  - MISSING expected field 'first_name'
  - MISSING expected field 'last_name'
  - MISSING expected field 'customer_identifier'

### FIND_CUSTOMER

**[PASS] find_customer - Norwegian (org nr)**
- Prompt: `Finn kunde med org.nr 912345678`
- Expected type: `find_customer` | Got: `find_customer` (correct)
- Extracted fields: `{"organization_number": "912345678"}`

**[PASS] find_customer - English**
- Prompt: `Find customer Nordic Tech AS`
- Expected type: `find_customer` | Got: `find_customer` (correct)
- Extracted fields: `{"name": "Nordic Tech AS"}`

**[FAIL] find_customer - German**
- Prompt: `Suche Kunde Schmidt GmbH`
- Expected type: `find_customer` | Got: `unknown` (WRONG)

### UPDATE_PROJECT

**[PASS] update_project - Norwegian**
- Prompt: `Oppdater prosjekt Nettside Redesign med ny sluttdato 2026-12-31`
- Expected type: `update_project` | Got: `update_project` (correct)
- Extracted fields: `{"name": "Nettside Redesign"}`

**[PASS] update_project - English**
- Prompt: `Update project Alpha with new description and end date 2026-06-30`
- Expected type: `update_project` | Got: `update_project` (correct)
- Extracted fields: `{"name": "Alpha"}`

**[PASS] update_project - French**
- Prompt: `Modifier projet Migration avec nouvelle date de fin`
- Expected type: `update_project` | Got: `update_project` (correct)
- Extracted fields: `{"name": "Migration"}`

### DELETE_PROJECT

**[PASS] delete_project - Norwegian**
- Prompt: `Slett prosjekt Gammelt Prosjekt`
- Expected type: `delete_project` | Got: `delete_project` (correct)
- Extracted fields: `{"name": "Gammelt Prosjekt"}`

**[PASS] delete_project - English**
- Prompt: `Delete project Legacy System`
- Expected type: `delete_project` | Got: `delete_project` (correct)
- Extracted fields: `{"name": "Legacy System"}`

**[PASS] delete_project - Spanish**
- Prompt: `Eliminar proyecto Sistema Antiguo`
- Expected type: `delete_project` | Got: `delete_project` (correct)
- Extracted fields: `{"name": "Sistema Antiguo"}`
