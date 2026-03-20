# Tripletex API — Tested Endpoints: Product, Project, Travel Expense

> **Sandbox**: `https://kkpqfuj-amager.tripletex.dev/v2`
> **Auth**: Basic Auth, username `0`, password = session token
> **Tested**: 2026-03-20

---

## 1. POST /product — Create a Product

### Minimum Required Fields (CONFIRMED WORKING)

```json
{"name": "My Product"}
```

- **name** is the ONLY required field
- Name must be unique (duplicate → 422 "Produktnavnet er allerede registrert")

### Defaults Applied by Server

| Field | Default |
|---|---|
| vatType | `{"id": 6}` — "Ingen utgående avgift (utenfor mva-loven)", 0% |
| currency | `{"id": 1}` — NOK |
| priceExcludingVatCurrency | 0 |
| priceIncludingVatCurrency | 0 |
| costExcludingVatCurrency | 0 |
| number | "" (empty string, auto-managed) |

### Full Example with Optional Fields

```json
{
  "name": "Widget Pro",
  "number": "PROD-001",
  "description": "A test widget",
  "priceExcludingVatCurrency": 100,
  "vatType": {"id": 3},
  "currency": {"id": 1}
}
```

**NOTE**: vatType `{"id": 3}` (25% utgående) was REJECTED when used in product creation with error "Ugyldig mva-kode". Only vatType `{"id": 6}` (0%) was confirmed working for products. Other VAT types may require specific account setup.

### Response (201 Created)

```json
{
  "value": {
    "id": 84382020,
    "version": 0,
    "name": "API Test Product v3",
    "number": "",
    "displayName": "API Test Product v3",
    "description": "",
    "priceExcludingVatCurrency": 0,
    "priceIncludingVatCurrency": 0,
    "costExcludingVatCurrency": 0,
    "costPrice": 0,
    "isInactive": false,
    "productUnit": null,
    "vatType": {"id": 6},
    "currency": {"id": 1},
    "department": null,
    "account": null,
    "supplier": null,
    "isDeletable": false,
    "image": null
  }
}
```

### All Product Fields (from GET /product?fields=*)

| Field | Type | Notes |
|---|---|---|
| id | int | Auto-generated |
| name | string | **REQUIRED**, unique |
| number | string | Optional product number |
| displayNumber | string | Read-only |
| description | string | Optional |
| orderLineDescription | string | Optional |
| costExcludingVatCurrency | number | Default 0 |
| costPrice | number | Default 0 |
| priceExcludingVatCurrency | number | Default 0 |
| priceIncludingVatCurrency | number | Default 0 |
| isInactive | boolean | Default false |
| productUnit | ref | Optional |
| vatType | ref | Default id=6 |
| currency | ref | Default id=1 (NOK) |
| department | ref | Optional |
| account | ref | Optional ledger account |
| supplier | ref | Optional |
| image | ref | Optional |

---

## 2. GET /product — List Products

```
GET /product?count=5&fields=*
```

Returns standard paginated response:
```json
{
  "fullResultSize": 4,
  "from": 0,
  "count": 4,
  "values": [...]
}
```

---

## 3. POST /project — Create a Project

### Minimum Required Fields (CONFIRMED WORKING)

```json
{
  "name": "My Project",
  "projectManager": {"id": 18491802},
  "startDate": "2026-03-20"
}
```

All three fields are required:
- **name**: project name (string)
- **projectManager**: employee reference object `{"id": <employeeId>}` — NOT `projectManagerId`!
- **startDate**: ISO date string `YYYY-MM-DD`

### Error Messages When Fields Missing

| Missing Field | Error (Norwegian) |
|---|---|
| projectManager | "Feltet \"Prosjektleder\" må fylles ut." |
| startDate | "Feltet må fylles ut." |
| Using `projectManagerId` | "Feltet eksisterer ikke i objektet." |

### Defaults Applied by Server

| Field | Default |
|---|---|
| number | Auto-incremented (e.g., "3") |
| vatType | `{"id": 6}` — 0% |
| currency | `{"id": 1}` — NOK |
| isClosed | false |
| isInternal | false |
| isOffer | false |
| isFixedPrice | false |
| displayNameFormat | "NAME_STANDARD" |

### Response (201 Created)

```json
{
  "value": {
    "id": 401950684,
    "version": 0,
    "name": "API Test Project v2",
    "number": "3",
    "displayName": "3 API Test Project v2",
    "description": "",
    "projectManager": {"id": 18491802},
    "department": null,
    "mainProject": null,
    "startDate": "2026-03-20",
    "endDate": null,
    "customer": null,
    "isClosed": false,
    "isReadyForInvoicing": false,
    "isInternal": false,
    "isOffer": false,
    "isFixedPrice": false,
    "projectCategory": null,
    "vatType": {"id": 6},
    "currency": {"id": 1},
    "discountPercentage": 0,
    "fixedprice": 0,
    "numberOfSubProjects": 0,
    "numberOfProjectParticipants": 1,
    "participants": [{"id": 15621554}],
    "projectHourlyRates": [{"id": 11067075}],
    "orderLines": [],
    "projectActivities": []
  }
}
```

### All Project Fields (from GET /project?fields=*)

| Field | Type | Notes |
|---|---|---|
| id | int | Auto-generated |
| name | string | **REQUIRED** |
| number | string | Auto-generated if omitted |
| projectManager | ref | **REQUIRED** — employee ref |
| startDate | string | **REQUIRED** — YYYY-MM-DD |
| endDate | string | Optional |
| description | string | Optional |
| customer | ref | Optional |
| department | ref | Optional |
| mainProject | ref | Optional (for sub-projects) |
| projectCategory | ref | Optional |
| isClosed | boolean | Default false |
| isInternal | boolean | Default false |
| isOffer | boolean | Default false |
| isFixedPrice | boolean | Default false |
| isReadyForInvoicing | boolean | Default false |
| vatType | ref | Default id=6 |
| currency | ref | Default id=1 (NOK) |
| discountPercentage | number | Default 0 |
| fixedprice | number | Default 0 |
| reference | string | Optional |
| externalAccountsNumber | string | Optional |
| displayNameFormat | string | Default "NAME_STANDARD" |
| deliveryAddress | ref | Optional |
| contact | ref | Optional |
| attention | ref | Optional |
| invoiceComment | string | Optional |

### GET /project/category — Project Categories

Returns **empty** on this sandbox (no categories configured):
```json
{"fullResultSize": 0, "values": []}
```

---

## 4. POST /travelExpense — Create a Travel Expense

### Minimum Required Fields (CONFIRMED WORKING)

```json
{
  "employee": {"id": 18491802},
  "title": "My Travel Expense"
}
```

- **employee**: employee reference object — REQUIRED
- **title**: string — REQUIRED (without it: "Kan ikke være null" on employee field)
- **date**: OPTIONAL — defaults to today's date

### Error Messages When Fields Missing

| Missing Field | Error |
|---|---|
| employee | "Kan ikke være null." (path: null.employee) |
| title only | Works! Date defaults to today |

### Defaults Applied by Server

| Field | Default |
|---|---|
| date | Today's date |
| department | Employee's department (auto-inherited) |
| paymentCurrency | `{"id": 1}` — NOK |
| state | "OPEN" |
| amount | 0 |
| isCompleted | false |
| isApproved | false |
| isChargeable | false |

### Response (201 Created)

```json
{
  "value": {
    "id": 11142106,
    "version": 2,
    "title": "API Test Expense",
    "number": 1,
    "numberAsString": "1-2026",
    "displayName": "1 - API Test Expense",
    "employee": {"id": 18491802},
    "department": {"id": 864717},
    "project": null,
    "date": "2026-03-20",
    "state": "OPEN",
    "stateName": "Åpent",
    "amount": 0,
    "paymentAmount": 0,
    "paymentCurrency": {"id": 1},
    "vatType": {"id": 0},
    "isCompleted": false,
    "isApproved": false,
    "isChargeable": false,
    "travelAdvance": 0,
    "costs": [],
    "perDiemCompensations": [],
    "mileageAllowances": [],
    "accommodationAllowances": [],
    "attachmentCount": 1,
    "actions": [
      {"rel": "DELIVER", "type": "PUT"},
      {"rel": "COPY", "type": "POST"},
      {"rel": "DELETE", "type": "DELETE"}
    ]
  }
}
```

### All Travel Expense Fields

| Field | Type | Notes |
|---|---|---|
| id | int | Auto-generated |
| title | string | **REQUIRED** |
| employee | ref | **REQUIRED** |
| date | string | Optional, defaults to today |
| project | ref | Optional |
| department | ref | Auto from employee |
| paymentCurrency | ref | Default NOK |
| vatType | ref | Default id=0 |
| state | string | OPEN, DELIVERED, APPROVED, etc. |
| amount | number | Computed from costs |
| paymentAmount | number | Computed |
| isCompleted | boolean | Default false |
| isApproved | boolean | Default false |
| isChargeable | boolean | Default false |
| isFixedInvoicedAmount | boolean | Default false |
| travelAdvance | number | Default 0 |
| fixedInvoicedAmount | number | Default 0 |
| costs | array | Cost line items |
| perDiemCompensations | array | Per diem entries |
| mileageAllowances | array | Mileage entries |
| accommodationAllowances | array | Accommodation entries |
| attachmentCount | int | Read-only |

---

## 5. POST /travelExpense/cost — Add Cost to Travel Expense

### Minimum Required Fields (CONFIRMED WORKING)

```json
{
  "travelExpense": {"id": 11142106},
  "paymentType": {"id": 33998575},
  "amountCurrencyIncVat": 150
}
```

- **travelExpense**: travel expense reference — REQUIRED
- **paymentType**: payment type reference — REQUIRED
- **amountCurrencyIncVat**: number — REQUIRED
- costCategory: OPTIONAL
- date: OPTIONAL
- currency: OPTIONAL (defaults to NOK)
- rate: OPTIONAL (defaults to 1)

### Error Messages When Fields Missing

| Missing Field | Error |
|---|---|
| amountCurrencyIncVat | "Kan ikke være null." |
| paymentType | "Kan ikke være null." |

### Full Example

```json
{
  "travelExpense": {"id": 11142106},
  "date": "2026-03-20",
  "costCategory": {"id": 33998576},
  "paymentType": {"id": 33998575},
  "currency": {"id": 1},
  "rate": 1,
  "amountCurrencyIncVat": 150
}
```

### Response (201 Created)

Minimal response (just URL):
```json
{"value": {"url": "kkpqfuj-amager.tripletex.dev/v2/travelExpense/cost/20249007"}}
```

### GET /travelExpense/cost/{id}?fields=* — Full Cost Object

```json
{
  "value": {
    "id": 20249007,
    "version": 1,
    "travelExpense": {"id": 11142106},
    "vatType": {"id": 1},
    "currency": {"id": 1},
    "costCategory": {"id": 33998576},
    "paymentType": {"id": 33998575},
    "category": "",
    "comments": "",
    "rate": 1.0,
    "amountCurrencyIncVat": 150.0,
    "amountNOKInclVAT": 150.0,
    "amountNOKInclVATLow": 0.0,
    "amountNOKInclVATMedium": 0.0,
    "amountNOKInclVATHigh": 30.0,
    "isPaidByEmployee": false,
    "isChargeable": false,
    "date": "2026-03-20",
    "participants": []
  }
}
```

---

## 6. DELETE /travelExpense/{id} — Delete a Travel Expense

```
DELETE /travelExpense/11142109
```

- Returns **204 No Content** on success
- No response body
- The expense must be in OPEN state (not delivered/approved)

---

## 7. GET /travelExpense — List Travel Expenses

```
GET /travelExpense?count=5&fields=*
```

Standard paginated response. Same structure as single GET but in `values` array.

---

## 8. Reference Endpoints

### GET /ledger/vatType — VAT Types

21 types available. Key ones:

| id | number | % | Name |
|---|---|---|---|
| 1 | 1 | 25% | Fradrag inngående avgift, høy sats |
| 3 | 3 | 25% | Utgående avgift, høy sats |
| 5 | 5 | 0% | Ingen utgående avgift (innenfor mva-loven) |
| 6 | 6 | 0% | Ingen utgående avgift (utenfor mva-loven) |
| 7 | 7 | 0% | Ingen avgiftsbehandling (inntekter) |
| 11 | 11 | 15% | Fradrag inngående avgift, middels sats |
| 12 | 13 | 12% | Fradrag inngående avgift, lav sats |
| 31 | 31 | 15% | Utgående avgift, middels sats |
| 32 | 33 | 12% | Utgående avgift, lav sats |

**Important**: Not all VAT types are valid for all contexts. Product creation only accepted id=6 in testing.

### GET /currency — Currencies

| id | code | description |
|---|---|---|
| 1 | NOK | Norge |
| 2 | SEK | Sverige |
| 3 | DKK | Danmark |
| 4 | USD | USA |
| 5 | EUR | EU |
| 6 | GBP | Storbritannia |
| 7 | CHF | Sveits |

### GET /country — Countries

Standard ISO country list. Examples:

| id | name | isoAlpha2 |
|---|---|---|
| 1 | Andorra | AD |
| 161 | Norge | NO |

### GET /travelExpense/costCategory — Cost Categories

21 categories. Key ones:

| id | description | vatType | showOnTravel | showOnEmployee |
|---|---|---|---|---|
| 33998576 | Bredbånd | id=1 (25%) | false | true |
| 33998577 | Kontorrekvisita | id=1 (25%) | false | true |
| 33998578 | Data/EDB-kostnad | id=1 (25%) | false | true |
| 33998579 | Aviser, tidsskrifter, bøker | id=0 | false | true |

### GET /travelExpense/paymentType — Payment Types

| id | description |
|---|---|
| 33998575 | Privat utlegg |

Only 1 payment type on this sandbox.

### GET /employee — Employees

| id | name | email |
|---|---|---|
| 18491802 | Frikk a23fd25c | frikk@guerrilla.no |
| 18492587 | Ola Nordmann | ola@example.com |

---

## 9. Dependencies Summary

```
Employee (must exist)
  └── Travel Expense (needs employee ref)
       └── Travel Expense Cost (needs travelExpense ref + paymentType ref)

Employee (must exist)
  └── Project (needs employee as projectManager)

Product (standalone, no dependencies)
```

## 10. Quick Reference — Minimum Payloads

### Product (just name)
```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"name":"My Product"}' \
  https://kkpqfuj-amager.tripletex.dev/v2/product
```

### Project (name + manager + start date)
```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"name":"My Project","projectManager":{"id":18491802},"startDate":"2026-03-20"}' \
  https://kkpqfuj-amager.tripletex.dev/v2/project
```

### Travel Expense (employee + title)
```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"employee":{"id":18491802},"title":"My Expense"}' \
  https://kkpqfuj-amager.tripletex.dev/v2/travelExpense
```

### Travel Expense Cost (expense ref + payment type + amount)
```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"travelExpense":{"id":EXPENSE_ID},"paymentType":{"id":33998575},"amountCurrencyIncVat":150}' \
  https://kkpqfuj-amager.tripletex.dev/v2/travelExpense/cost
```

### Delete Travel Expense
```bash
curl -X DELETE https://kkpqfuj-amager.tripletex.dev/v2/travelExpense/EXPENSE_ID
# Returns 204 No Content
```

---

## 11. Key Gotchas

1. **Reference fields use objects, not IDs**: Use `{"id": 123}` not just `123`. E.g., `"projectManager": {"id": 18491802}` not `"projectManagerId": 18491802`.
2. **Product names must be unique** — duplicate names return 422.
3. **VAT type id=3 (25% outgoing) is invalid for products** — only id=6 worked. May need account configuration.
4. **Project requires startDate** — unlike product/expense which have sensible defaults.
5. **Travel expense cost `count` field doesn't exist** — don't include it.
6. **Delete only works on OPEN expenses** — delivered/approved expenses cannot be deleted.
7. **Project number auto-increments** — you don't need to set it.
8. **Cost response is minimal** — only returns URL, need separate GET for full data.
