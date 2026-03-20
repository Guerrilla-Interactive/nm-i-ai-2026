# Executor Payload Test Results

**Date:** 2026-03-20
**Test file:** `app/test_executor_payloads.py`
**Result:** 16/16 PASSED, 0 FAILED

## Methodology

All 10 executor functions were tested by mocking `TripletexClient` methods with `AsyncMock`, then inspecting the exact payloads passed to each API call. No real API calls were made. The tests verify:

- Required fields are present
- Field names match Tripletex API expectations (camelCase)
- Data types are correct (int IDs, float amounts, string dates, `{"id": N}` refs)
- No invalid/unknown fields are included
- Edge cases (missing optional fields, None values, auto-generation)

## Test Results by Executor

### 1. `_exec_create_employee`
- **No `startDate` field** in the payload (confirmed absent -- Tripletex does not accept it on POST /employee)
- `userType` mapping works correctly:
  - `"administrator"` / `"ADMIN"` -> `"EXTENDED"`
  - `"RESTRICTED"` -> `"NO_ACCESS"`
  - Invalid values (e.g. `"SUPERUSER"`) -> fallback `"STANDARD"`
- `department` is always `{"id": int}` ref format
- `phone` maps to `phoneNumberMobile`
- Auto-generates email as `first.last@example.com` when not provided
- `_clean` removes all None optional fields

### 2. `_exec_create_customer`
- `organizationNumber` field name correct (not `org_number`)
- `org_number` alias works via fallback (`or _get(fields, "org_number")`)
- `isCustomer: True` always included (distinguishes from supplier in Tripletex entity model)
- Address mapped to `postalAddress` with sub-fields `addressLine1`, `postalCode`, `city`
- `phone` maps to `phoneNumber` (not `phoneNumberMobile` -- different from employee)
- Minimal payload (name only) produces `{"name": "...", "isCustomer": true}`
- No unknown/invalid fields

### 3. `_exec_create_product`
- VAT type resolved dynamically via `GET /ledger/vatType?typeOfVat=outgoing`
- Prefers "utgaende" (output) VAT types matching the target percentage
- No `vat_percentage` specified -> defaults to 25% (standard Norwegian VAT, id=3)
- 0% VAT resolves correctly to id=6
- `vatType` is `{"id": int}` ref format
- `price` maps to `priceExcludingVatCurrency` (float)
- No unknown fields in payload

### 4. `_exec_create_invoice`
- **Order-then-invoice flow:** POST /order -> PUT /order/{id}/:invoice
- Order payload includes `customer: {"id": int}`, `orderDate`, `deliveryDate`, `orderLines`, `invoiceComment`
- Order lines have: `count` (float), `unitPriceExcludingVatCurrency` (float), `description`
- `invoiceComment` correctly maps from `comment` field
- Bank account check (`GET /ledger/account?number=1920`) performed before invoice creation
- `invoice_order` called with correct order_id and `invoiceDate` param

### 5. `_exec_invoice_with_payment`
- Auto-calculates `paidAmount` from order lines when not explicitly provided
- Applies 1.25x VAT multiplier when prices are ex-VAT (unitPriceExcludingVatCurrency)
- Does NOT apply VAT multiplier when prices are inc-VAT (unitPriceIncludingVatCurrency)
- Example: 2 * 1000 ex-VAT -> paidAmount = 2500.0
- `paymentTypeId` and `paidAmount` passed as **strings** in invoice params (query params)
- `sendToCustomer` = `"false"` (string, not boolean -- used as query param)
- Explicit `paid_amount` takes precedence over auto-calculation

### 6. `_exec_project_with_customer`
- When customer not found (empty lookup), creates customer inline
- Customer payload includes `name` and `organizationNumber` from fields
- Project linked to customer via `customer: {"id": int}` ref
- `projectManager` is `{"id": int}` ref (NOT `projectManagerId`)
- `startDate` passed through from fields
- Falls back to finding first available employee as project manager

### 7. `_exec_create_travel_expense`
- Employee resolved via name lookup, ref format `{"id": int}`
- `travelDetails` sub-object contains: `departureDate`, `returnDate`, `departureFrom`, `destination`, `purpose`, `isDayTrip`, `isForeignTravel`
- Boolean fields like `isDayTrip: False` preserved (not cleaned as None)
- Cost lines created via separate POST /travelExpense/cost with:
  - `travelExpense: {"id": int}` ref linking to parent
  - `paymentType: {"id": int}` ref (looked up dynamically)
  - `amountCurrencyIncVat` (float)

### 8. `_exec_create_contact`
- Customer lookup by name, then ref in payload as `customer: {"id": int}`
- When customer not found, creates customer inline (handles fresh accounts)
- `customer_identifier` alias works for customer name lookup
- Contact payload: `firstName`, `lastName`, `email`, `phoneNumberMobile`, `customer` ref
- `phone` maps to `phoneNumberMobile`

### 9. `_exec_create_department`
- Minimal payload: only `name`, `departmentNumber`, `departmentManager`
- `departmentManager` uses `{"id": int}` ref format via `_ref()`
- None values excluded by `_clean` -- minimal case has only `{"name": "..."}`

### 10. `_exec_register_payment`
- Invoice lookup by `invoiceNumber` string via GET /invoice
- Direct `invoice_id` bypasses lookup
- Payment params: `paymentDate` (string), `paymentTypeId` (int), `paidAmount` (float)
- Payment type looked up dynamically via `GET /invoice/paymentType`
- `register_payment` called with `int(invoice_id)` and params dict

## Edge Cases Tested

| Case | Result |
|------|--------|
| Empty order lines | Returns empty list |
| Missing price on line | Defaults to `unitPriceExcludingVatCurrency: 0.0` |
| `count` alias for `quantity` | Works (float conversion) |
| `product_id` in order line | Creates `{"id": int}` ref |
| Discount on order line | `discount: float` |
| `unit_price_including_vat` | Maps to `unitPriceIncludingVatCurrency` (excludes ex-VAT field) |
| None optional fields | Excluded from payload by `_clean()` |
| `_ref(None)` | Returns `None` (excluded by `_clean`) |
| `_ref("10")` | Coerced to `{"id": 10}` (int) |

## Key Architectural Notes

1. **All entity references** use `{"id": int}` format (not flat ID fields)
2. **`_clean()` removes None** but keeps `False` and `0` -- important for boolean fields
3. **Invoice flow** always goes through orders: POST /order -> PUT /order/:invoice
4. **Bank account prerequisite** checked before every invoice creation
5. **VAT type resolution** defaults to 25% Norwegian standard rate
6. **Payment params** in invoice_order are query params (strings), while register_payment params use int/float
