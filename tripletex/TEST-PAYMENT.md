# INVOICE_WITH_PAYMENT Test Results

**Date**: 2026-03-20
**Classifier mode**: rule-based (no LLM)

## Summary: 3/6 passed

| # | Description | Task | Amount | Overall |
|---|-------------|------|--------|---------|
| 1 | Norwegian - single line, ex-VAT amount | FAIL | FAIL | FAIL |
| 2 | French - unpaid invoice, register payment | PASS | FAIL | FAIL |
| 3 | German - unpaid invoice, register payment | PASS | FAIL | FAIL |
| 4 | English - hours-based, paid in full | PASS | PASS | PASS |
| 5 | Norwegian - multi-quantity product, register payment | PASS | PASS | PASS |
| 6 | Edge case - short form, 'betalt' signals payment | PASS | PASS | PASS |

## Detailed Results

### Test 1: Norwegian - single line, ex-VAT amount

- **Expected task**: `invoice_with_payment`
- **Actual task**: `create_invoice` FAIL
- **Expected paid_amount**: 39125.0
- **Computed paid_amount**: 0.0 FAIL
- **Extracted fields**: `{'price_excluding_vat': 31300.0, 'organization_number': '909268265', 'customer_name': 'Brattli AS (org'}`
- **Order lines**: `[]`

### Test 2: French - unpaid invoice, register payment

- **Expected task**: `invoice_with_payment`
- **Actual task**: `invoice_with_payment` PASS
- **Expected paid_amount**: 13187.5
- **Computed paid_amount**: 0.0 FAIL
- **Extracted fields**: `{'price_excluding_vat': 10550.0, 'organization_number': '850491941', 'customer_name': 'Colline SARL (nº org', 'amount': 10550.0}`
- **Order lines**: `[]`

### Test 3: German - unpaid invoice, register payment

- **Expected task**: `invoice_with_payment`
- **Actual task**: `invoice_with_payment` PASS
- **Expected paid_amount**: 6250.0
- **Computed paid_amount**: 0.0 FAIL
- **Extracted fields**: `{'price_excluding_vat': 5000.0, 'customer_name': 'Müller GmbH hat eine unbezahlte Rechnung über 5000 NOK exkl', 'amount': 5000.0}`
- **Order lines**: `[]`

### Test 4: English - hours-based, paid in full

- **Expected task**: `invoice_with_payment`
- **Actual task**: `invoice_with_payment` PASS
- **Expected paid_amount**: 5625.0
- **Computed paid_amount**: 5625.0 PASS
- **Extracted fields**: `{'price_excluding_vat': 1500.0, 'customer_name': 'Acme Corp', 'lines': [{'description': 'consulting', 'quantity': 3, 'unit_price': 1500.0}], 'amount': 1500.0}`
- **Order lines**: `[{'description': 'consulting', 'count': 3.0, 'unitPriceExcludingVatCurrency': 1500.0}]`

### Test 5: Norwegian - multi-quantity product, register payment

- **Expected task**: `invoice_with_payment`
- **Actual task**: `invoice_with_payment` PASS
- **Expected paid_amount**: 1250.0
- **Computed paid_amount**: 1250.0 PASS
- **Extracted fields**: `{'price_excluding_vat': 200.0, 'customer_name': 'Fjord AS', 'lines': [{'description': 'Produkt A', 'quantity': 5, 'unit_price': 200.0}], 'amount': 200.0}`
- **Order lines**: `[{'description': 'Produkt A', 'count': 5.0, 'unitPriceExcludingVatCurrency': 200.0}]`

### Test 6: Edge case - short form, 'betalt' signals payment

- **Expected task**: `invoice_with_payment`
- **Actual task**: `invoice_with_payment` PASS
- **Expected paid_amount**: 3750.0
- **Computed paid_amount**: 3750.0 PASS
- **Extracted fields**: `{'price_excluding_vat': 1500.0, 'customer_name': 'Nordfjord AS', 'lines': [{'description': 'Konsulenttjeneste', 'quantity': 2, 'unit_price': 1500.0}], 'amount': 1500.0}`
- **Order lines**: `[{'description': 'Konsulenttjeneste', 'count': 2.0, 'unitPriceExcludingVatCurrency': 1500.0}]`

## Failure Analysis

### Test 1: Norwegian - single line, ex-VAT amount
- **Classification failure**: Got `create_invoice`, expected `invoice_with_payment`. The rule-based classifier may lack patterns for this language/phrasing.
- **Amount calculation failure**: Computed 0.0, expected 39125.0. 
  - Root cause: No order lines were extracted from the prompt. The line extraction regex did not match.

### Test 2: French - unpaid invoice, register payment
- **Amount calculation failure**: Computed 0.0, expected 13187.5. 
  - Root cause: No order lines were extracted from the prompt. The line extraction regex did not match.

### Test 3: German - unpaid invoice, register payment
- **Amount calculation failure**: Computed 0.0, expected 6250.0. 
  - Root cause: No order lines were extracted from the prompt. The line extraction regex did not match.

