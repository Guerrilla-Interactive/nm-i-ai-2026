# Tier 3 & Edge Case Test Results

Run: 2026-03-20 04:41:08
Classifier mode: rule-based (no LLM)

## Summary

- Total tests: 49
- Passed: 41
- Failed: 8
- Pass rate: 83.7%

## Detailed Results

### T3 (12/15 passed)

| Test | Status | Task Type | Confidence | Details |
|------|--------|-----------|------------|---------|
| T3-1a: Bank reconciliation (Norwegian) | PASS | bank_reconciliation | 0.60 | account_number=1920, period=for mars 2026 |
| T3-1b: Bank reconciliation (English) | PASS | bank_reconciliation | 0.60 | account_number=1920, period=for March 2026 |
| T3-1c: Bank reconciliation variant | PASS | bank_reconciliation | 0.60 | period=januar 2026 |
| T3-2a: Error correction (Norwegian) | PASS | error_correction | 0.60 | price_excluding_vat=15000.0, voucher_identifier=4521 |
| T3-2b: Error correction (English) | PASS | error_correction | 0.60 | voucher_identifier=8899 |
| T3-2c: Error correction - reverse posting | FAIL | unknown | 0.00 | task_type: expected=error_correction, got=unknown; confidence>0: confidence=0.0; field:voucher_identifier: voucher_identifier: expected=1234, got=None |
| T3-2d: Error correction - rett feil | FAIL | unknown | 0.00 | task_type: expected=error_correction, got=unknown; confidence>0: confidence=0.0; field:voucher_identifier: voucher_identifier: expected=5678, got=None |
| T3-3a: Year-end closing (Norwegian) | PASS | year_end_closing | 0.60 | year=2025 |
| T3-3b: Year-end closing (English) | PASS | year_end_closing | 0.60 | year=2025 |
| T3-3c: Year-end closing - årsoppgjør | PASS | year_end_closing | 0.60 | year=2025 |
| T3-3d: Year-end closing - close year | PASS | year_end_closing | 0.60 | year=2024 |
| T3-4a: Enable module (Norwegian) | PASS | enable_module | 0.60 | module_name=Reiseregning |
| T3-4b: Enable module (English) | PASS | enable_module | 0.60 | module_name=Project Management |
| T3-4c: Enable module - slå på | PASS | enable_module | 0.60 | module_name=Fakturering |
| T3-4d: Enable module - activate | FAIL | create_invoice | 0.60 | task_type: expected=enable_module, got=create_invoice; field:module_name: module_name: got=None |

### EDGE (12/16 passed)

| Test | Status | Task Type | Confidence | Details |
|------|--------|-----------|------------|---------|
| EDGE-5: Batch departments | FAIL | unknown | 0.00 | task_type: expected=create_department, got=unknown; confidence>0: confidence=0.0; field:name: name: got=None |
| EDGE-6a: Spanish - create customer | PASS | create_customer | 0.60 | name=Empresa Nordica SA, email=info@nordica.es |
| EDGE-6b: Portuguese - create project | FAIL | create_customer | 0.60 | task_type: expected=create_project, got=create_customer |
| EDGE-6c: Spanish - create employee | PASS | create_employee | 0.60 | name=Carlos García, email=carlos@empresa.es |
| EDGE-7: Long multi-field prompt | FAIL | invoice_existing_customer | 0.60 | task_type: expected=create_customer, got=invoice_existing_customer |
| EDGE-8a: Norwegian special chars (æ, ø, å) | PASS | create_department | 0.60 | name=Økonomistyring |
| EDGE-8b: German special chars (ü, ö, ä) | PASS | create_customer | 0.60 | name=Müller & Söhne GmbH |
| EDGE-8c: French special chars (é, è) | PASS | create_department | 0.60 | name=Développement Stratégique |
| EDGE-9a: Ambiguous - invoice vs payment | PASS | invoice_with_payment | 0.60 | price_excluding_vat=5000.0, customer_name=Acme AS, amount=5000.0 |
| EDGE-9b: Ambiguous - project for customer | PASS | project_with_customer | 0.60 | name=Nettsideredesign, customer_name=DigitalByrå AS, start_date=2026-04-01 |
| EDGE-9c: Ambiguous - employee role vs create | PASS | set_employee_roles | 0.60 | user_type=EXTENDED, first_name=Per, last_name=Olsen |
| EDGE-10a: PDF attachment reference | PASS | bank_reconciliation | 0.60 | (no fields) |
| EDGE-10b: Image attachment | PASS | create_travel_expense | 0.60 | title=basert på vedlagt kvittering |
| EDGE-EXTRA-1: Enable module Reiseregning (not travel expense) | PASS | enable_module | 0.60 | module_name=Reiseregning i Tripletex |
| EDGE-EXTRA-2: feilretting keyword | FAIL | unknown | 0.00 | task_type: expected=error_correction, got=unknown; confidence>0: confidence=0.0 |
| EDGE-EXTRA-3: Year-end German (Jahresabschluss) | PASS | year_end_closing | 0.60 | year=2025 |

### FIELD (17/18 passed)

| Test | Status | Task Type | Confidence | Details |
|------|--------|-----------|------------|---------|
| FIELD-11a: Date format DD. Month YYYY (Norwegian) | PASS | create_employee | 0.60 | name=Erik Blom, first_name=Erik, last_name=Blom |
| FIELD-11b: Date format DD/MM/YYYY | PASS | create_project | 0.60 | name=Alpha |
| FIELD-11c: Date format YYYY-MM-DD (ISO) | PASS | create_employee | 0.60 | first_name=John, last_name=Doe |
| FIELD-12a: Price 22550 NOK | PASS | create_product | 0.60 | name=Datenberatung, price_excluding_vat=22550.0 |
| FIELD-12b: Price 1500 kr | PASS | create_product | 0.60 | name=Konsulenttjeneste, price_excluding_vat=1500.0 |
| FIELD-12c: Price with currency symbol EUR | PASS | create_product | 0.60 | name=Export Service, price_excluding_vat=1500.0 |
| FIELD-13a: VAT 25% MVA | PASS | create_product | 0.60 | name=Tjeneste, price_excluding_vat=1000.0, vat_percentage=25 |
| FIELD-13b: VAT Steuersatz 25% | PASS | create_product | 0.60 | name=Beratung, vat_percentage=25 |
| FIELD-13c: VAT MwSt 25% | PASS | create_product | 0.60 | name=Analyse, price_excluding_vat=5000.0, vat_percentage=25 |
| FIELD-14a: Org number with 'org.nr' | PASS | create_customer | 0.60 | name=Test AS, organization_number=912345678 |
| FIELD-14b: Org number with 'organisasjonsnummer' | PASS | create_customer | 0.60 | name=Fjord AS, organization_number=987654321 |
| FIELD-14c: Org number with 'organization number' | PASS | create_customer | 0.60 | name=Nordic Ltd, organization_number=123456789 |
| FIELD-15a: Norwegian address | PASS | create_customer | 0.60 | name=Fjord AS, address_line1=Fjordveien 105, postal_code=3015 |
| FIELD-15b: Address with Storgata | PASS | create_customer | 0.60 | name=Nordlys AS, address_line1=Storgata 5, postal_code=0001 |
| FIELD-16a: Role - kontoadministrator | FAIL | set_employee_roles | 0.60 | task_type: expected=create_employee, got=set_employee_roles |
| FIELD-16b: Role - administrator | PASS | create_employee | 0.60 | first_name=Hans, last_name=Hansen, user_type=ADMINISTRATOR |
| FIELD-16c: Role - ingen tilgang | PASS | set_employee_roles | 0.60 | user_type=NO_ACCESS, first_name=Per, last_name=Olsen |
| FIELD-16d: Role - standard user | PASS | set_employee_roles | 0.60 | user_type=STANDARD, first_name=Kari, last_name=Nord |

## Failed Test Details

### T3-2c: Error correction - reverse posting
- **Prompt**: `Reverser bilag 1234 og opprett ny postering`
- **Expected type**: `error_correction`
- **Got type**: `unknown`
- **Confidence**: 0.0
- **Fields**: `{}`
- **Failed checks**:
  - task_type: expected=error_correction, got=unknown
  - confidence>0: confidence=0.0
  - field:voucher_identifier: voucher_identifier: expected=1234, got=None

### T3-2d: Error correction - rett feil
- **Prompt**: `Rett feil i postering 5678`
- **Expected type**: `error_correction`
- **Got type**: `unknown`
- **Confidence**: 0.0
- **Fields**: `{}`
- **Failed checks**:
  - task_type: expected=error_correction, got=unknown
  - confidence>0: confidence=0.0
  - field:voucher_identifier: voucher_identifier: expected=5678, got=None

### T3-4d: Enable module - activate
- **Prompt**: `Activate module Invoice Management`
- **Expected type**: `enable_module`
- **Got type**: `create_invoice`
- **Confidence**: 0.6
- **Fields**: `{}`
- **Failed checks**:
  - task_type: expected=enable_module, got=create_invoice
  - field:module_name: module_name: got=None

### EDGE-5: Batch departments
- **Prompt**: `Create three departments: Utvikling, Innkjøp, and Salg`
- **Expected type**: `create_department`
- **Got type**: `unknown`
- **Confidence**: 0.0
- **Fields**: `{}`
- **Failed checks**:
  - task_type: expected=create_department, got=unknown
  - confidence>0: confidence=0.0
  - field:name: name: got=None

### EDGE-6b: Portuguese - create project
- **Prompt**: `Criar um projeto chamado Desenvolvimento Web para o cliente TechCorp`
- **Expected type**: `create_project`
- **Got type**: `create_customer`
- **Confidence**: 0.6
- **Fields**: `{'name': 'Desenvolvimento Web para o cliente TechCorp'}`
- **Failed checks**:
  - task_type: expected=create_project, got=create_customer

### EDGE-7: Long multi-field prompt
- **Prompt**: `Opprett en ny kunde med navn Nordfjord Konsulentselskap AS, organisasjonsnummer 987654321, e-post kontakt@nordfjord.no, `
- **Expected type**: `create_customer`
- **Got type**: `invoice_existing_customer`
- **Confidence**: 0.6
- **Fields**: `{'name': 'Nordfjord Konsulentselskap AS', 'email': 'kontakt@nordfjord.no', 'phone': '+47 55 12 34 56', 'organization_number': '987654321', 'customer_name': 'Nordfjord Konsulentselskap AS'}`
- **Failed checks**:
  - task_type: expected=create_customer, got=invoice_existing_customer

### FIELD-16a: Role - kontoadministrator
- **Prompt**: `Opprett ansatt med navn Admin Bruker, e-post admin@test.no, rolle kontoadministrator`
- **Expected type**: `create_employee`
- **Got type**: `set_employee_roles`
- **Confidence**: 0.6
- **Fields**: `{'name': 'Admin Bruker', 'email': 'admin@test.no', 'user_type': 'ADMINISTRATOR'}`
- **Failed checks**:
  - task_type: expected=create_employee, got=set_employee_roles

### EDGE-EXTRA-2: feilretting keyword
- **Prompt**: `Feilretting i bilag 7890`
- **Expected type**: `error_correction`
- **Got type**: `unknown`
- **Confidence**: 0.0
- **Fields**: `{}`
- **Failed checks**:
  - task_type: expected=error_correction, got=unknown
  - confidence>0: confidence=0.0
