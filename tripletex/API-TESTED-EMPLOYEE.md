# Tripletex Employee API — Tested & Documented

**Date tested:** 2026-03-20
**Sandbox:** `https://kkpqfuj-amager.tripletex.dev/v2`
**Auth:** Basic Auth, username `0`, password (session token)

---

## 1. GET /employee — List & Search

### List all employees
```
GET /employee?fields=*&count=20
```
- Returns employees with `fullResultSize` count
- Default list **excludes** employees where `isContact=true`
- Use `includeContacts=true` to include contact-flagged employees

### Available search/filter parameters (tested)

| Parameter | Works? | Notes |
|---|---|---|
| `firstName=Test` | **YES** | Exact match filter |
| `email=ola@example.com` | **YES** | Exact match filter |
| `includeContacts=true` | **YES** | Includes employees with `isContact=true` |
| `hasSystemAccess=true` | Accepted but no filtering effect observed | Returns all non-contact employees |
| `lastName=Tester` | **NO** — returns 0 results | Not a supported filter parameter |
| `departmentId=865127` | **NO** — returns 0 results | Not a supported filter parameter |
| `id=18493126` | **NO** — returns 0 results | Not a supported filter parameter |
| `name=Test` | **NO** — returns all employees | Ignored/no effect |
| `employeeNumber=1` | **NO** — returns 0 results | Not a supported filter parameter |
| `count=N` | **YES** | Pagination |
| `from=N` | **YES** | Pagination offset |
| `fields=field1,field2` | **YES** | Field selection |

### Get single employee
```
GET /employee/{id}?fields=*
```
Returns full employee object even if `isContact=true`.

---

## 2. Employee Object — All Fields

```json
{
  "id": 18493126,
  "version": 3,                          // Required for PUT (optimistic locking)
  "url": "...tripletex.dev/v2/employee/18493126",
  "firstName": "Test",
  "lastName": "Tester",
  "displayName": "Test Tester",          // Read-only (auto-generated)
  "employeeNumber": "",
  "dateOfBirth": "1990-01-15",           // Format: "YYYY-MM-DD", nullable
  "email": "test.tester@example.com",    // IMMUTABLE after creation
  "phoneNumberMobileCountry": {"id": 161},  // Country reference (161 = Norway)
  "phoneNumberMobile": "99887766",
  "phoneNumberHome": "22334455",
  "phoneNumberWork": "55443322",
  "nationalIdentityNumber": "",
  "dnumber": "",
  "internationalId": {
    "intAmeldingType": null,
    "country": null,
    "number": ""
  },
  "bankAccountNumber": "",
  "iban": "",
  "bic": "",
  "creditorBankCountryId": 0,
  "usesAbroadPayment": false,
  "userType": null,                      // Always null in response (write-only on POST)
  "allowInformationRegistration": true,  // Read-only (cannot be changed via PUT)
  "isContact": false,                    // Can be changed via PUT
  "isProxy": false,
  "comments": "API test employee",
  "address": {"id": 405189061},          // Nested address object
  "department": {"id": 864717},          // Department reference
  "employments": [],                     // Read-only list
  "holidayAllowanceEarned": {
    "year": 0,
    "amount": 0.0,
    "basis": 0.0,
    "amountExtraHolidayWeek": 0.0
  },
  "employeeCategory": null,
  "isAuthProjectOverviewURL": true,
  "pictureId": 0,
  "companyId": 108167433,               // Read-only
  "vismaConnect2FAactive": false         // Read-only
}
```

---

## 3. POST /employee — Create

**Endpoint:** `POST /employee`
**Returns:** HTTP 201 with full employee object

### Minimum required fields
```json
{
  "firstName": "Test",
  "lastName": "Tester",
  "email": "test@example.com",
  "userType": "STANDARD",
  "department": {"id": 864717}
}
```

### Full creation body (all optional fields included)
```json
{
  "firstName": "Test",
  "lastName": "Tester",
  "email": "test.tester@example.com",
  "userType": "STANDARD",
  "phoneNumberMobileCountry": {"id": 161},
  "phoneNumberMobile": "99887766",
  "phoneNumberHome": "22334455",
  "phoneNumberWork": "55443322",
  "comments": "Created via API",
  "department": {"id": 864717},
  "address": {
    "addressLine1": "Testgata 1",
    "postalCode": "0150",
    "city": "Oslo",
    "country": {"id": 161}
  }
}
```

### userType values (tested)

| Value | Works? | Entitlements assigned |
|---|---|---|
| `STANDARD` | **YES** (201) | 4 entitlements (AUTH_HOURLIST, AUTH_TRAVELREPORT, AUTH_EMPLOYEE_INFO, AUTH_PROJECT_INFO) |
| `EXTENDED` | **YES** (201) | Same 4 entitlements |
| `NO_ACCESS` | **YES** (201) | 0 entitlements |
| `ADMINISTRATOR` | **NO** (422) | Invalid value |
| `ACCOUNTANT` | **NO** (422) | Invalid value |
| `AUDITOR` | **NO** (422) | Invalid value |
| `DEPARTMENT_MANAGER` | **NO** (422) | Invalid value |
| `READ_ONLY` | **NO** (422) | Invalid value |
| `NONE` | **NO** (422) | Invalid value |

**Important:** `userType` is required on POST (422 error: "Brukertype kan ikke være '0' eller tom") but always returns `null` in GET responses — it's write-only.

### Validation errors on POST
- Missing `userType` → 422: "Brukertype kan ikke være '0' eller tom."
- Missing `firstName`/`lastName` → required fields

---

## 4. PUT /employee/{id} — Update

**Endpoint:** `PUT /employee/{id}`
**Returns:** HTTP 200 with updated employee object

### Required fields for PUT
PUT requires a **near-complete body** — not just changed fields. Minimum:
- `id` — must match URL
- `version` — current version (optimistic locking, 409 if stale)
- `firstName`, `lastName` — required
- `email` — must be included and MUST match current value (immutable)
- `dateOfBirth` — required on PUT (even if null on creation)

### Successful PUT body example
```json
{
  "id": 18493126,
  "version": 2,
  "firstName": "Test",
  "lastName": "Tester",
  "email": "test.tester@example.com",
  "dateOfBirth": "1990-01-15",
  "phoneNumberMobileCountry": {"id": 161},
  "phoneNumberMobile": "11112222",
  "phoneNumberHome": "33334444",
  "phoneNumberWork": "55556666",
  "comments": "Updated via API",
  "department": {"id": 865127},
  "address": {
    "id": 405189061,
    "addressLine1": "Oppdatertgata 42",
    "postalCode": "0250",
    "city": "Oslo",
    "country": {"id": 161}
  }
}
```

### Fields that CAN be updated via PUT (tested)
- `phoneNumberMobile` ✅
- `phoneNumberHome` ✅
- `phoneNumberWork` ✅
- `phoneNumberMobileCountry` ✅
- `comments` ✅
- `department` ✅ (change department by ID)
- `address` ✅ (must include address `id` for existing, or creates new)
- `dateOfBirth` ✅
- `isContact` ✅

### Fields that CANNOT be updated via PUT
- `email` ❌ — 422: "email kan ikke endres."
- `allowInformationRegistration` ❌ — silently ignored (stays true)

### Validation errors on PUT
- Changed email → 422: "email kan ikke endres."
- Missing `dateOfBirth` → 422: "Feltet må fylles ut."
- Wrong `version` → 409: RevisionException
- Address without `id` → 422: "Adressen er registrert på en annen ansatt." (creates new address conflicting with existing)

### Version handling
- Every successful PUT increments `version` by 1
- Must send current `version` in PUT body
- Stale version returns **409 Conflict** (RevisionException)

---

## 5. DELETE /employee/{id}

**Endpoint:** `DELETE /employee/{id}`
**Result:** **403 Forbidden** — "You do not have permission to access this feature."

DELETE is **not available** with the current API token/permissions. Employees cannot be deleted via this sandbox token.

---

## 6. Employee Roles & Permissions (Entitlements)

### How roles work
Employee permissions are managed through the **entitlements** system, NOT through fields on the employee object.

### Entitlement endpoint
```
GET /employee/entitlement?employeeId={id}&fields=*
POST /employee/entitlement
DELETE /employee/entitlement/{id}  → 403 (not permitted)
```

### Available entitlements (observed)

| Name | entitlementId | Description |
|---|---|---|
| `AUTH_HOURLIST` | 46 | Access to hour lists |
| `AUTH_TRAVELREPORT` | 47 | Access to travel reports |
| `AUTH_EMPLOYEE_INFO` | 61 | Access to employee information |
| `AUTH_PROJECT_INFO` | 92 | Access to project information |

### Creating entitlements
```json
POST /employee/entitlement
{
  "employee": {"id": 18493562},
  "entitlementId": 46,
  "customer": {"id": 108167433}
}
```
Returns **201** with `{"value": {"url": ".../employee/entitlement/0"}}` (note: ID 0 in response).

### Deleting entitlements
```
DELETE /employee/entitlement/{id}
```
Returns **403** — not permitted with current token.

### Role-related fields on employee object

| Field | Type | Writable? | Notes |
|---|---|---|---|
| `userType` | string | POST only | Controls initial entitlements. STANDARD/EXTENDED → 4 entitlements. NO_ACCESS → 0. |
| `allowInformationRegistration` | boolean | Read-only | Cannot be changed via PUT |
| `isContact` | boolean | PUT ✅ | Marks employee as contact (excluded from default list) |
| `isProxy` | boolean | Not tested | |
| `isAuthProjectOverviewURL` | boolean | Read-only | |

---

## 7. Phone Number Format

### Structure
Phone numbers are plain strings on the employee object:
- `phoneNumberMobile`: `"99887766"` — digits only, no spaces or prefix
- `phoneNumberHome`: `"22334455"` — digits only
- `phoneNumberWork`: `"55443322"` — digits only

### Country code for mobile
`phoneNumberMobileCountry` is a **country reference object**:
```json
"phoneNumberMobileCountry": {"id": 161}
```
- Country ID 161 = Norway ("NO")
- It's the country entity ID, NOT the phone dialing code
- Default for new employees: `{"id": 161}` (Norway)
- Only applies to mobile number, not home/work

---

## 8. Address Fields

### Address on employee creation (nested, no ID needed)
```json
"address": {
  "addressLine1": "Testgata 1",
  "addressLine2": "",         // Optional
  "postalCode": "0150",
  "city": "Oslo",
  "country": {"id": 161}     // Country reference (161 = Norway)
}
```

### Address on employee update (must include existing address ID)
```json
"address": {
  "id": 405189061,            // REQUIRED for update — existing address ID
  "addressLine1": "Oppdatertgata 42",
  "postalCode": "0250",
  "city": "Oslo",
  "country": {"id": 161}
}
```

### Full address object (from GET /address/{id})
```json
{
  "id": 405189061,
  "version": 1,
  "addressLine1": "Oppdatertgata 42",
  "addressLine2": "",
  "postalCode": "0250",
  "city": "Oslo",
  "country": {"id": 161},
  "displayName": "Test Tester, Oppdatertgata 42, 0250 Oslo, Norge",
  "addressAsString": "Oppdatertgata 42, 0250 Oslo, Norge",
  "knr": 0, "gnr": 0, "bnr": 0, "fnr": 0, "snr": 0,
  "unitNumber": "",
  "name": "",
  "customerVendor": null
}
```

### Key address rules
- `country` is a reference: `{"id": 161}` for Norway
- `postalCode` and `city` are plain strings
- On PUT: **must include address `id`** or you get 422 ("Adressen er registrert på en annen ansatt")
- `addressLine2` is optional

---

## 9. Department Reference

### Departments in sandbox
| ID | Name | Number |
|---|---|---|
| 864717 | Avdeling | (empty) |
| 865127 | Hovedavdeling | 1 |

### Usage
```json
"department": {"id": 864717}
```
Can be changed via PUT — just set a different department ID.

---

## 10. Summary of HTTP Status Codes

| Operation | Status | Meaning |
|---|---|---|
| POST /employee | **201** | Created successfully |
| GET /employee | **200** | List returned |
| GET /employee/{id} | **200** | Single employee |
| PUT /employee/{id} | **200** | Updated successfully |
| PUT /employee/{id} | **409** | Version conflict (stale version) |
| PUT /employee/{id} | **422** | Validation error |
| DELETE /employee/{id} | **403** | Permission denied |
| POST /employee/entitlement | **201** | Entitlement created |
| DELETE /employee/entitlement/{id} | **403** | Permission denied |

---

## 11. Test Employees Created

| ID | firstName | lastName | email | userType | Notes |
|---|---|---|---|---|---|
| 18493126 | Test | Tester | test.tester@example.com | STANDARD | Updated, isContact=true |
| 18493396 | Delete | MePlease | deleteme@example.com | STANDARD | Created for DELETE test |
| 18493534 | TypeTest | STANDARD | type_STANDARD@example.com | STANDARD | userType test |
| 18493562 | TypeTest2 | NO_ACCESS | type2_NO_ACCESS@example.com | NO_ACCESS | 0 entitlements |
| 18493564 | TypeTest2 | EXTENDED | type2_EXTENDED@example.com | EXTENDED | Same entitlements as STANDARD |
