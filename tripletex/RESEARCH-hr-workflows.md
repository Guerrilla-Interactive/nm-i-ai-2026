# HR Manager Workflows — Tripletex API Research

**Date:** 2026-03-21
**Sandbox:** `https://kkpqfuj-amager.tripletex.dev/v2`
**Auth:** Basic Auth, username `0`, password (session token)

---

## 1. User Persona: HR Manager / Personalansvarlig

**Role:** HR Manager (Personalansvarlig) in a Norwegian SMB using Tripletex for ERP/accounting.

**Responsibilities:**
- Hire new employees and configure their system access
- Manage employee data (contact info, department assignments, bank details)
- Handle travel expense approvals and processing
- Run payroll (lønnskjøring) monthly
- Manage departments and organizational structure
- Handle employee lifecycle: onboarding → active → offboarding

**Languages:** Primarily Norwegian (bokmål), but prompts may come in English, Swedish, German, French, or Spanish.

**Key Norwegian terms:**
- Ansatt = Employee
- Avdeling = Department
- Reiseregning = Travel expense report
- Lønnskjøring = Payroll run
- Diett = Per diem
- Kilometergodtgjørelse = Mileage allowance
- Personalansvarlig = HR Manager

---

## 2. API Endpoints — Full Details

### 2.1 Employee (`/employee`)

**GET /employee** — List/search employees
- `fullResultSize`: 3 employees in sandbox (excluding contacts)
- **Working filters:** `firstName`, `email`, `includeContacts`, `count`, `from`, `fields`
- **NOT working:** `lastName`, `departmentId`, `id`, `name`, `employeeNumber`
- ⚠️ **CRITICAL:** Only `firstName` and `email` filter server-side. To find by last name, you must fetch all and filter client-side.

**GET /employee/{id}** — Single employee (works even for contacts)

**POST /employee** — Create employee
- **Required:** `firstName`, `lastName`, `email`, `userType`, `department.id`
- **Optional:** `phoneNumberMobile`, `phoneNumberHome`, `phoneNumberWork`, `phoneNumberMobileCountry`, `comments`, `address`, `dateOfBirth`, `nationalIdentityNumber`, `bankAccountNumber`
- ⚠️ **CRITICAL: `startDate` is NOT a valid field — causes 422 error!**
- ⚠️ `email` is **IMMUTABLE** after creation
- ⚠️ `userType` is **write-only** — always returns `null` in GET responses
- Valid `userType` values: `STANDARD`, `EXTENDED`, `NO_ACCESS`
- Invalid: `ADMINISTRATOR`, `ACCOUNTANT`, `AUDITOR`, `DEPARTMENT_MANAGER`, `READ_ONLY`, `NONE`

**PUT /employee/{id}** — Update employee
- Requires **near-complete body** (not just changed fields)
- **Required in body:** `id`, `version`, `firstName`, `lastName`, `email` (must match current), `dateOfBirth`
- **Can update:** phone numbers, comments, department, address, dateOfBirth, isContact
- **Cannot update:** email (422), allowInformationRegistration (silently ignored)
- Version mismatch → 409 Conflict

**DELETE /employee/{id}** — **403 Forbidden** (not available in sandbox)

### 2.2 Employee Employment (`/employee/employment`)

**GET /employee/employment** — Employment records
- `fullResultSize`: 0 (no employment records in sandbox currently)
- Linked to employee via `employee.id`
- Contains: `startDate`, `endDate`, `employmentType`, `division`

### 2.3 Employment Details (`/employee/employment/details`)

**GET /employee/employment/details** — Detailed employment info
- `fullResultSize`: 3
- Fields: `employment` (ref), `date`, `employmentType`, `employmentForm`, `remunerationType`, `workingHoursScheme`, `shiftDurationHours`, `occupationCode`, `percentageOfFullTimeEquivalent`, `annualSalary`, `hourlyWage`, `monthlySalary`, `payrollTaxMunicipalityId`
- Most fields default to `NOT_CHOSEN` or `0.0`
- `employmentType` values: `ORDINARY`, (others not observed)

### 2.4 Employment Types (`/employee/employment/employmentType`)

**GET /employee/employment/employmentType** — Reference data
- 4 types available:

| ID | Norwegian Name |
|---|---|
| 1 | Ordinært arbeidsforhold |
| 2 | Maritimt arbeidsforhold |
| 3 | Frilanser/oppdragstaker/honorar personer m.m. |
| 4 | Pensjon og andre ytelser uten arbeidsforhold |

### 2.5 Salary Types (`/salary/type`)

**GET /salary/type** — 51 salary types available
- Key types for payroll:

| Number | Name | Taxable? | Vacation payable? |
|---|---|---|---|
| 2000 | Fastlønn | Yes | Yes |
| 2001 | Timelønn | Yes | Yes |
| 2002 | Bonus | Yes | Yes |
| 2003 | Faste tillegg | Yes | Yes |
| 2005 | Overtidsgodtgjørelse | Yes | Yes |
| 2015 | Feriepenger u/skattetrekk | No | — |
| 2016 | Feriepenger m/skattetrekk | Yes | — |
| 2028 | Trekk i lønn for ferie - fastlønn | — | — |
| 5001 | Kilometergodtgjørelse bil | — | — |
| 5002 | Kost | — | — |
| 6000 | Skattetrekk | — | — |
| 1000 | Gjeld til ansatte | No | No |
| 1001 | Forskudd på lønn | — | — |

### 2.6 Salary Transactions (`/salary/transaction`)

**GET /salary/transaction** — **403 Forbidden** (not accessible with current token)

### 2.7 Salary Payslips (`/salary/payslip`)

**GET /salary/payslip** — 0 results (empty, but accessible)

### 2.8 Salary Settings (`/salary/settings`)

**GET /salary/settings** — Returns:
```json
{
  "municipality": {"id": 262},
  "payrollTaxCalcMethod": "AA"
}
```
- Municipality 262 is the registered payroll tax municipality
- Method "AA" = standard calculation method

### 2.9 Travel Expenses (`/travelExpense`)

**GET /travelExpense** — Travel expense reports
- `fullResultSize`: 3 in sandbox
- Key fields: `employee` (ref), `department` (ref), `project` (ref), `title`, `date`, `amount`, `paymentAmount`, `state`, `number`
- States: `OPEN` (Åpent), `DELIVERED`, `APPROVED`, `REJECTED`, `COMPLETED`
- Actions available on OPEN: `DELIVER`, `COPY`, `DELETE`
- Contains nested arrays: `costs`, `perDiemCompensations`, `mileageAllowances`, `accommodationAllowances`
- Has `travelDetails` with departure/return dates, locations, purpose

### 2.10 Travel Expense Costs (`/travelExpense/cost`)

**GET /travelExpense/cost** — Individual cost line items
- Fields: `travelExpense` (ref), `vatType`, `currency`, `costCategory`, `paymentType`, `date`, `amountCurrencyIncVat`, `amountNOKInclVAT`, `isPaidByEmployee`, `rate`, `participants`
- Each cost references a `costCategory` and `paymentType`

### 2.11 Travel Expense Cost Categories (`/travelExpense/costCategory`)

**GET /travelExpense/costCategory** — 11 categories
- **Travel expenses** (`showOnTravelExpenses=true`):

| ID | Description |
|---|---|
| 33998584 | Bomavgift (toll) |
| 33998585 | Buss |
| 33998586 | Båt |
| 33998587 | Drivstoff |
| 33998588 | Drivstoff - leiebil |
| 33998589 | Drivstoff - selskapets transportmiddel |
| 33998590 | Ferge |
| 33998591 | Fly |
| 33998592 | Flybuss |
| 33998593 | Flytog |
| 33998594 | Hotell |
| 33998595 | Hurtigbåt |

- **Employee expenses** (`showOnEmployeeExpenses=true`): Bredbånd, Kontorrekvisita, Data/EDB-kostnad, Aviser, Møte/kurs, Annen kontorkostnad, Telefon, Porto

### 2.12 Travel Expense Payment Types (`/travelExpense/paymentType`)

**GET /travelExpense/paymentType** — 1 type available:

| ID | Description |
|---|---|
| 33998575 | Privat utlegg |

### 2.13 Per Diem Compensations (`/travelExpense/perDiemCompensation`)

**GET /travelExpense/perDiemCompensation** — Per diem entries
- Fields: `travelExpense` (ref), `rateType`, `rateCategory`, `countryCode`, `overnightAccommodation`, `location`, `count`, `rate`, `amount`
- `overnightAccommodation` values: `HOTEL`, `NONE`, (others)
- Deduction flags: `isDeductionForBreakfast`, `isDeductionForLunch`, `isDeductionForDinner`

### 2.14 Mileage Allowances (`/travelExpense/mileageAllowance`)

**GET /travelExpense/mileageAllowance** — 0 results in sandbox
- Fields include: `travelExpense`, `date`, `departureLocation`, `destination`, `km`, `rateTypeId`, `rate`, `amount`

### 2.15 Travel Expense Rate Categories (`/travelExpense/rateCategory`)

**GET /travelExpense/rateCategory** — Large dataset (10000+ limit hit)

**Per Diem categories** (type=`PER_DIEM`):
- Various rates for day trips (5-9h, 9-12h, 12h+) and overnight stays
- Domestic vs. foreign travel
- Categories have validity date ranges (`fromDate`, `toDate`)

**Mileage categories** (type=`MILEAGE_ALLOWANCE`):

| ID | Name |
|---|---|
| 80 | Bil - inntil 9000 km |
| 81 | Bil - over 9000 km |
| 82 | Bil - Tromsø-tillegg |
| 83 | Bil - tillegg skogs- og anleggsveier |
| 84 | Bruk av tilhenger eller utstyr/bagasje i bilen |
| 85 | Bil - passasjertillegg |
| 86 | Motorsykkel - fra og med 125 ccm |
| 87 | Motorsykkel - inntil 125 ccm |
| 88 | Snøskuter |
| 89 | Båt - fra og med 50 hk |

### 2.16 Departments (`/department`)

**GET /department** — 20+ departments in sandbox
- Fields: `id`, `version`, `name`, `departmentNumber`, `departmentManager` (ref, nullable), `isInactive`, `businessActivityTypeId`
- Key departments: Avdeling, Hovedavdeling (1), Salg (10), Marketing, IT (20), HR with number 30, Teknologi (50)

**POST /department** — Create department
- Required: `name`
- Optional: `departmentNumber`, `departmentManager` (ref)

**PUT /department/{id}** — Update department
- Requires `id`, `version`, `name`

**DELETE /department/{id}** — Delete department
- May fail with 422/409 if linked entities exist

---

## 3. Employee Lifecycle

### Step 1: Hire / Onboard (Opprett ansatt)

```
POST /employee
{
  "firstName": "Kari",
  "lastName": "Nordmann",
  "email": "kari@firma.no",
  "userType": "STANDARD",
  "department": {"id": <dept_id>},
  "phoneNumberMobile": "99887766",
  "phoneNumberMobileCountry": {"id": 161},
  "address": {
    "addressLine1": "Storgata 1",
    "postalCode": "0150",
    "city": "Oslo",
    "country": {"id": 161}
  }
}
```

**Gotchas:**
- ⚠️ Do NOT include `startDate` — causes 422
- ⚠️ `userType` is required but write-only
- ⚠️ `email` cannot be changed after creation
- Department must exist — look up by name first: `GET /department?name=<dept>`

### Step 2: Configure Employment (optional)

Employment details are managed through `/employee/employment` and `/employee/employment/details` but these are mostly pre-populated by the salary module. Directly creating employment records may not be needed for basic HR use.

### Step 3: Assign/Change Department

```
PUT /employee/{id}
{
  "id": <emp_id>,
  "version": <current_version>,
  "firstName": "Kari",
  "lastName": "Nordmann",
  "email": "kari@firma.no",    // MUST match current
  "dateOfBirth": "1990-01-15", // Required on PUT
  "department": {"id": <new_dept_id>}
}
```

**Gotchas:**
- Must include nearly complete body
- Must GET employee first to obtain `version` and current `email`
- `dateOfBirth` is required on PUT even if null on creation

### Step 4: Update Employee Info

Same as Step 3 — PUT with full body. Can update:
- Phone numbers (mobile, home, work)
- Address (must include address `id` for existing addresses)
- Comments
- Department assignment
- Date of birth
- isContact flag

### Step 5: Offboard / Terminate

- `DELETE /employee/{id}` → **403 Forbidden** (not possible in sandbox)
- Alternative: Set `isContact: true` to hide from active employee lists
- No direct termination API — employment end dates may be managed through `/employee/employment`

---

## 4. Payroll Workflow (Lønnskjøring)

### Current Implementation (Voucher-based)

The current `_exec_run_payroll` uses a **voucher-based approach** since direct salary transaction API returns 403:

1. **Find employee** via `_find_employee()` helper
2. **Parse period** — handles Norwegian month names (mars, juni, etc.), "MM/YYYY" patterns, date fields
3. **Calculate amounts** — base_salary + bonus (defaults to 30,000 if not specified)
4. **Create voucher** with salary postings:
   - Debit: Account 7700/7000/5900 (salary expense)
   - Credit: Account 2920/2780/2400 (skyldig lønn / salary payable)

### Salary API Limitations

| Endpoint | Status |
|---|---|
| `GET /salary/type` | ✅ Works — 51 types available |
| `GET /salary/payslip` | ✅ Works — but empty |
| `GET /salary/settings` | ✅ Works — municipality + calc method |
| `GET /salary/transaction` | ❌ 403 Forbidden |
| `POST /salary/transaction` | ❌ Likely 403 (not tested, read-only) |

### Ideal Payroll Flow (if salary module were accessible)

1. `GET /salary/type` — List salary types
2. `POST /salary/transaction` — Create transactions per employee:
   - Salary type 2000 (Fastlønn): amount = monthly salary
   - Salary type 2002 (Bonus): amount = bonus
   - Salary type 6000 (Skattetrekk): amount = tax deduction
3. `POST /salary/payslip` — Generate payslip
4. Approve/process payslip

### What "Kjør lønnskjøring for mars 2026" requires:

1. Find employee(s) by name/identifier
2. Determine period: March 2026 → payroll date 2026-03-31
3. Look up amounts: base salary, any bonus
4. Create voucher postings:
   - DR 7700 (Personnel costs) = total gross amount
   - CR 2920 (Skyldig lønn) = total gross amount
5. Return confirmation with voucher ID and amounts

---

## 5. Travel Expense Workflow (Reiseregning)

### Step 1: Create Travel Expense

```
POST /travelExpense
{
  "employee": {"id": <emp_id>},
  "title": "Oslo-Bergen tjenestereise",
  "date": "2026-03-20"
}
```

Returns: expense with `id`, `number`, `state: "OPEN"`

### Step 2: Add Cost Lines

```
POST /travelExpense/cost
{
  "travelExpense": {"id": <expense_id>},
  "paymentType": {"id": 33998575},          // Privat utlegg
  "costCategory": {"id": 33998591},          // Fly
  "amountCurrencyIncVat": 2500.00,
  "date": "2026-03-20"
}
```

Cost categories for travel: Bomavgift, Buss, Båt, Drivstoff, Ferge, Fly, Flybuss, Flytog, Hotell, Hurtigbåt

### Step 3: Add Per Diem Compensation (Diett)

```
POST /travelExpense/perDiemCompensation
{
  "travelExpense": {"id": <expense_id>},
  "location": "Bergen",
  "count": 2,                                // Number of days
  "overnightAccommodation": "HOTEL",
  "rate": 800.0
}
```

Deduction flags: `isDeductionForBreakfast`, `isDeductionForLunch`, `isDeductionForDinner`

### Step 4: Add Mileage Allowance (Kilometergodtgjørelse)

```
POST /travelExpense/mileageAllowance
{
  "travelExpense": {"id": <expense_id>},
  "date": "2026-03-20",
  "departureLocation": "Oslo",
  "destination": "Bergen",
  "km": 500.0,
  "rateTypeId": 80                           // Bil - inntil 9000 km
}
```

Mileage rate categories: Bil (80-85), Motorsykkel (86-87), Snøskuter (88), Båt (89)

### Step 5: Deliver / Approve

- Deliver: `PUT /travelExpense/:deliver` (action from state OPEN)
- Approve: `PUT /travelExpense/:approve` (after delivery)
- Complete: Creates voucher postings automatically

### State Machine

```
OPEN → DELIVERED → APPROVED → COMPLETED
  ↓        ↓
DELETE   REJECTED
```

---

## 6. Department Management

### Create Department

```
POST /department
{
  "name": "Salg",
  "departmentNumber": "10",
  "departmentManager": {"id": <employee_id>}  // Optional
}
```

### List Departments

```
GET /department?fields=*
```

Current sandbox departments (20+): Avdeling, Hovedavdeling (1), Salg (10), Marketing, IT (20), HR with number 30, Teknologi (50), Testing (55), QA (65), Forschung (75), RH (85), Finance, Vertrieb

### Update Department

```
PUT /department/{id}
{
  "id": <dept_id>,
  "version": <version>,
  "name": "New Name",
  "departmentNumber": "99",
  "departmentManager": {"id": <emp_id>}
}
```

### Delete Department

```
DELETE /department/{id}
```
- May fail with 422 if employees are assigned to the department
- May fail with 409 if there's a conflict

### Assign Employee to Department

Done via `PUT /employee/{id}` with `"department": {"id": <dept_id>}`

---

## 7. Prompt Patterns

### Employee Management

| Norwegian Prompt | English Equivalent | TaskType | Key Fields |
|---|---|---|---|
| "Opprett ny ansatt: Kari Nordmann, epost kari@firma.no" | "Create new employee: Kari Nordmann, email kari@firma.no" | CREATE_EMPLOYEE | first_name=Kari, last_name=Nordmann, email=kari@firma.no |
| "Oppdater telefonnummer til ansatt Per Hansen til 99001122" | "Update employee Per Hansen's phone to 99001122" | UPDATE_EMPLOYEE | employee_identifier=Per Hansen, phone=99001122 |
| "Flytt ansatt Ola til avdeling Salg" | "Move employee Ola to Sales department" | UPDATE_EMPLOYEE | employee_identifier=Ola, department_name=Salg |
| "Slett ansatt med epost test@example.com" | "Delete employee with email test@example.com" | DELETE_EMPLOYEE | employee_identifier=test@example.com |
| "Gi Kari standard tilgang i systemet" | "Give Kari standard system access" | SET_EMPLOYEE_ROLES | employee_identifier=Kari, user_type=STANDARD |
| "Legg til ny ansatt Lars Berg i IT-avdelingen" | "Add new employee Lars Berg to IT department" | CREATE_EMPLOYEE | first_name=Lars, last_name=Berg, department_name=IT |

### Travel Expenses

| Norwegian Prompt | English Equivalent | TaskType | Key Fields |
|---|---|---|---|
| "Registrer reiseregning for Kari: Oslo-Bergen, 500km, 2 døgn diett" | "Register travel expense for Kari: Oslo-Bergen, 500km, 2 days per diem" | CREATE_TRAVEL_EXPENSE | employee_identifier=Kari, departure_from=Oslo, destination=Bergen, mileage_allowances=[{km:500}], per_diem_compensations=[{count:2}] |
| "Opprett reiseregning for Ola: fly Oslo-Tromsø, hotell 3 netter, 1500kr" | "Create travel expense for Ola: flight Oslo-Tromsø, hotel 3 nights, 1500kr" | CREATE_TRAVEL_EXPENSE | employee_identifier=Ola, costs=[{amount:1500, category:Fly}] |
| "Slett reiseregning nummer 1-2026" | "Delete travel expense number 1-2026" | DELETE_TRAVEL_EXPENSE | travel_expense_identifier=1-2026 |

### Payroll

| Norwegian Prompt | English Equivalent | TaskType | Key Fields |
|---|---|---|---|
| "Kjør lønnskjøring for mars 2026" | "Run payroll for March 2026" | RUN_PAYROLL | month=3, year=2026 |
| "Registrer lønn for Kari: 45000 kr i fastlønn + 5000 bonus" | "Register salary for Kari: 45000 fixed + 5000 bonus" | RUN_PAYROLL | employee_identifier=Kari, base_salary=45000, bonus=5000 |
| "Betal ut lønn til alle ansatte for april" | "Pay salary to all employees for April" | RUN_PAYROLL | month=4, year=2026 |

### Department Management

| Norwegian Prompt | English Equivalent | TaskType | Key Fields |
|---|---|---|---|
| "Opprett avdeling Salg med avdelingsnummer 10" | "Create department Sales with number 10" | CREATE_DEPARTMENT | name=Salg, department_number=10 |
| "Endre navn på avdeling Marketing til Markedsføring" | "Rename department Marketing to Markedsføring" | UPDATE_DEPARTMENT | department_identifier=Marketing, new_name=Markedsføring |
| "Slett avdeling Testing" | "Delete department Testing" | DELETE_DEPARTMENT | name=Testing |
| "Sett Ola som leder for IT-avdelingen" | "Set Ola as manager for IT department" | UPDATE_DEPARTMENT | department_identifier=IT, manager_name=Ola |

---

## 8. Gap Analysis

### Currently Supported ✅

| Scenario | TaskType | Status |
|---|---|---|
| Create employee | CREATE_EMPLOYEE | ✅ Working |
| Update employee details | UPDATE_EMPLOYEE | ✅ Working |
| Delete employee | DELETE_EMPLOYEE | ⚠️ Returns 403 (API limitation) |
| Set employee roles | SET_EMPLOYEE_ROLES | ✅ Working |
| Create travel expense | CREATE_TRAVEL_EXPENSE | ✅ Working |
| Delete travel expense | DELETE_TRAVEL_EXPENSE | ✅ Working |
| Run payroll (voucher-based) | RUN_PAYROLL | ✅ Working (fallback) |
| Create department | CREATE_DEPARTMENT | ✅ Working |
| Update department | UPDATE_DEPARTMENT | ✅ Working |
| Delete department | DELETE_DEPARTMENT | ✅ Working |

### Gaps / Missing Capabilities ❌

| Scenario | Issue | Severity |
|---|---|---|
| **Employee search by last name** | API only supports firstName/email filters. Must fetch all + filter client-side | Medium |
| **Employee termination** | DELETE returns 403. No employment end-date API accessible | High |
| **Direct salary transactions** | /salary/transaction returns 403. Using voucher fallback | High |
| **Payslip generation** | No POST /salary/payslip tested. Endpoint exists but empty | Medium |
| **Travel expense approval workflow** | Deliver/approve actions exist but not implemented in executor | Medium |
| **Bulk payroll** | No support for running payroll for ALL employees at once | Low |
| **Employment contracts** | /employee/employment creation not implemented | Medium |
| **Employee categories** | `employeeCategory` field exists but no management | Low |
| **Holiday allowance** | `holidayAllowanceEarned` is read-only, no management API | Low |
| **National ID / D-number** | Fields exist but no validation or lookup | Low |
| **Bank account updates** | `bankAccountNumber` can be set on create but PUT behavior untested | Low |
| **Mileage tracking** | Rate categories exist (80-89) but 0 mileage records in sandbox | Medium |
| **Travel expense delivery** | `PUT /travelExpense/:deliver` not implemented | Medium |
| **Multi-employee payroll** | Current impl handles single employee at a time | Medium |

### API Permission Gaps

| Endpoint | Status | Impact |
|---|---|---|
| DELETE /employee/{id} | 403 | Cannot delete employees |
| GET /salary/transaction | 403 | Cannot view salary history |
| DELETE /employee/entitlement/{id} | 403 | Cannot remove permissions |

---

## 9. Recommendations

### Priority 1: Fix Employee Search (High Impact, Low Effort)

The `_find_employee` helper should:
1. Try `firstName` filter first
2. If not found, fetch all employees (`count=100`) and filter client-side by last name, full name, or email
3. Add fuzzy matching for Norwegian names (Ø/ö, Å/å, etc.)

### Priority 2: Travel Expense Deliver/Approve (High Impact, Medium Effort)

Add new task types or extend CREATE_TRAVEL_EXPENSE:
- `DELIVER_TRAVEL_EXPENSE` → `PUT /travelExpense/:deliver`
- `APPROVE_TRAVEL_EXPENSE` → `PUT /travelExpense/:approve`
- These complete the travel expense lifecycle

### Priority 3: Improve Payroll Robustness (Medium Impact, Medium Effort)

Current voucher-based fallback works but:
- Try salary transaction API first (may work with different modules enabled)
- Add description field to voucher with employee name and period
- Support multiple salary components (overtime, deductions)
- Add tax deduction line (skattetrekk)

### Priority 4: Employee Termination Workaround (Medium Impact, Low Effort)

Since DELETE returns 403:
- Set `isContact: true` to effectively deactivate
- Update `comments` with termination date/reason
- This is documented in API-TESTED-EMPLOYEE.md

### Priority 5: Department Manager Assignment (Low Impact, Low Effort)

The `departmentManager` field exists on departments but is nullable for all current departments. The UPDATE_DEPARTMENT executor should:
1. Find employee by name
2. Set `departmentManager: {"id": emp_id}` on department PUT

### Priority 6: Employment Details Configuration (Low Impact, High Effort)

Employment details (annual salary, FTE%, employment type) could be configured via:
- `POST /employee/employment` → Create employment record
- `POST /employee/employment/details` → Set salary, hours, occupation code
- This enables proper a-melding reporting
