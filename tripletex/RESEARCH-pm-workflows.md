# Project Manager Workflows — Tripletex API Research

> **Sandbox**: `https://kkpqfuj-amager.tripletex.dev/v2`
> **Auth**: Basic Auth, username `0`, password = session token
> **Tested**: 2026-03-21

---

## 1. User Persona

**Prosjektleder / Project Manager** — A role within a Norwegian SME using Tripletex for ERP/accounting.

### Typical responsibilities:
- Create and manage projects (with budgets, timelines, and teams)
- Assign team members as project participants
- Track time: employees log hours against project activities
- Bill clients: generate invoices from logged project hours
- Monitor project financials: budget vs. actual, P&L per project
- Close completed projects

### Language patterns (Norwegian prompts):
- "Opprett prosjekt [Navn]" — Create project
- "Legg til [Person] som prosjektleder" — Assign project manager
- "Registrer [X] timer på prosjekt [Navn]" — Log hours
- "Fakturer prosjekt [Navn]" — Invoice project
- "Lukk prosjekt [Navn]" — Close project
- "Vis timer på prosjekt [Navn]" — View project hours

### Relevant TaskTypes in our system:
| TaskType | Tier | Description |
|---|---|---|
| CREATE_PROJECT | T1 (×1) | Create a new project |
| UPDATE_PROJECT | T2 (×2) | Update project details |
| DELETE_PROJECT | T2 (×2) | Delete a project |
| PROJECT_WITH_CUSTOMER | T2 (×2) | Create project linked to customer |
| PROJECT_BILLING | T2 (×2) | Invoice a project |
| LOG_HOURS | T2 (×2) | Log timesheet entry on project |

---

## 2. API Endpoints (Full Details)

### 2.1 GET /project — List Projects

**Query parameters**: `name`, `number`, `id`, `projectManagerId`, `customerId`, `isClosed`, `from`, `count`, `fields`

**Sandbox state**: 7 projects exist (all with projectManager = employee 18491802)

**Full response fields** (from `fields=*`):
| Field | Type | Notes |
|---|---|---|
| id | int | Auto-generated |
| name | string | **REQUIRED** for POST |
| number | string | Auto-incremented if omitted |
| displayName | string | Read-only, format: "number name" |
| description | string | Optional |
| projectManager | ref | **REQUIRED** — `{"id": employeeId}` |
| startDate | string | **REQUIRED** — YYYY-MM-DD |
| endDate | string | Optional |
| customer | ref | Optional — `{"id": customerId}` |
| department | ref | Optional |
| mainProject | ref | Optional (for sub-projects) |
| projectCategory | ref | Optional (none configured on sandbox) |
| isClosed | boolean | Default false |
| isReadyForInvoicing | boolean | Default false |
| isInternal | boolean | Default false |
| isOffer | boolean | Default false |
| isFixedPrice | boolean | Default false |
| fixedprice | number | Default 0 |
| discountPercentage | number | Default 0 |
| vatType | ref | Default id=6 (0%) |
| currency | ref | Default id=1 (NOK) |
| participants | ref[] | Auto-created for projectManager |
| projectHourlyRates | ref[] | Auto-created with default rate |
| projectActivities | ref[] | Empty by default |
| orderLines | ref[] | Empty by default |
| invoicingPlan | ref[] | Empty by default |
| contact | ref | Optional |
| attention | ref | Optional |
| invoiceComment | string | Optional |
| reference | string | Optional |
| displayNameFormat | string | Default "NAME_STANDARD" |
| forParticipantsOnly | boolean | Default false |
| accessType | string | "WRITE" (read-only field) |
| markUpOrderLines | number | Default 0.0 |
| markUpFeesEarned | number | Default 0.0 |
| isPriceCeiling | boolean | Default false |
| priceCeilingAmount | number | Default 0.0 |
| contributionMarginPercent | number | Default 0.0 |
| invoiceDueDate | int | Default 0 |
| invoiceDueDateType | string | Default "DAYS" |
| hierarchyLevel | int | 0 for top-level |
| hierarchyNameAndNumber | string | Read-only |
| customerName | string | Read-only, empty if no customer |
| projectManagerNameAndNumber | string | Read-only |
| totalInvoicedOnAccountAmountAbsoluteCurrency | number | Read-only |
| accountingDimensionValues | ref[] | Empty by default |

### 2.2 POST /project — Create Project

**Minimum payload** (confirmed working):
```json
{
  "name": "My Project",
  "projectManager": {"id": 18491802},
  "startDate": "2026-03-20"
}
```

**Critical**: Use `projectManager: {"id": X}` NOT `projectManagerId`. Using the wrong field gives: "Feltet eksisterer ikke i objektet."

**Optional fields for POST**:
```json
{
  "name": "Full Project",
  "projectManager": {"id": 18491802},
  "startDate": "2026-03-20",
  "endDate": "2026-12-31",
  "description": "A project description",
  "customer": {"id": 108168567},
  "department": {"id": 864717},
  "isFixedPrice": true,
  "fixedprice": 50000,
  "isInternal": false,
  "number": "P-001"
}
```

### 2.3 PUT /project/{id} — Update Project

Requires `version` field for optimistic locking. GET first with `fields=*` to get current version.

**Closable fields**:
- `isClosed: true` — close the project
- `endDate` — set end date
- `projectManager` — change manager

### 2.4 DELETE /project/{id}

Returns 204 No Content. Cannot delete projects with linked invoices/orders.

### 2.5 GET /project/category — Project Categories

**Sandbox**: Empty (0 categories configured). Categories are optional.

### 2.6 GET /project/hourlyRates — Hourly Rates

**Confirmed working**. Each project auto-gets one hourly rate record on creation.

| Field | Type | Notes |
|---|---|---|
| id | int | Auto-generated |
| project | ref | Parent project |
| startDate | string | Same as project start |
| showInProjectOrder | boolean | Default false |
| hourlyRateModel | string | `"TYPE_FIXED_HOURLY_RATE"` |
| projectSpecificRates | array | Empty by default |
| fixedRate | number | Default 0.0 |

**Hourly rate models**: `TYPE_FIXED_HOURLY_RATE`, `TYPE_PROJECT_SPECIFIC_HOURLY_RATE`, `TYPE_PREDEFINED_HOURLY_RATES`

### 2.7 GET /project/projectActivity — Project-Specific Activities

**Status**: Returns 405 (Method Not Allowed) on direct GET. Must be accessed through `project.projectActivities` relationship or by projectId filter.

### 2.8 GET /project/orderline — Project Order Lines

**Requires** `projectId` query parameter. Cannot list all.

### 2.9 GET /project/participant — Project Participants

**Status**: Returns 405 (Method Not Allowed) on direct list GET. Accessed via project's `participants` array.

### 2.10 GET /activity — Activities (Global)

**Sandbox**: 4 activities available:

| id | name | type | isProjectActivity | isChargeable |
|---|---|---|---|---|
| 5685468 | Administrasjon | GENERAL_ACTIVITY | false | false |
| 5685469 | Ferie | GENERAL_ACTIVITY | false | false |
| 5685470 | Prosjektadministrasjon | PROJECT_GENERAL_ACTIVITY | true | false |
| 5685471 | Fakturerbart arbeid | PROJECT_GENERAL_ACTIVITY | true | **true** |

**Key insight**: Only `isProjectActivity: true` activities can be used in project timesheet entries. `Fakturerbart arbeid` (Billable work) is the only chargeable activity on this sandbox.

**Activity fields**:
| Field | Type | Notes |
|---|---|---|
| id | int | Auto-generated |
| name | string | Display name |
| number | string | Optional |
| description | string | Optional |
| activityType | string | GENERAL_ACTIVITY or PROJECT_GENERAL_ACTIVITY |
| isProjectActivity | boolean | Must be true for project time entries |
| isGeneral | boolean | Available to all projects |
| isTask | boolean | Task-type activity |
| isDisabled | boolean | Inactive flag |
| isChargeable | boolean | Can be billed to customer |
| rate | number | Default hourly rate |
| costPercentage | number | Cost markup |

### 2.11 GET /timesheet/entry — Timesheet Entries

**Requires** `dateFrom` and `dateTo` query parameters.

**Sandbox**: 1 entry exists (2.5 hours on Administrasjon, no project).

| Field | Type | Notes |
|---|---|---|
| id | int | Auto-generated |
| employee | ref | **REQUIRED** |
| project | ref | Optional (null = general time) |
| activity | ref | **REQUIRED** |
| date | string | **REQUIRED** — YYYY-MM-DD |
| hours | number | **REQUIRED** — decimal hours |
| chargeableHours | number | Auto from activity.isChargeable |
| comment | string | Optional |
| locked | boolean | Read-only |
| chargeable | boolean | Read-only |
| invoice | ref | Set when invoiced |
| hourlyRate | number | From project/activity rate |
| hourlyCost | number | Computed |
| hourlyCostPercentage | number | From activity |
| projectChargeableHours | number | Computed |

**Response includes**: `sumAllHours` aggregate field.

### 2.12 POST /timesheet/entry — Create Timesheet Entry

**Minimum payload**:
```json
{
  "employee": {"id": 18491802},
  "activity": {"id": 5685471},
  "project": {"id": 401950684},
  "date": "2026-03-21",
  "hours": 7.5
}
```

**Notes**:
- `activity` must have `isProjectActivity: true` when `project` is specified
- `employee` must be a project participant (or `forParticipantsOnly: false` on project)
- `comment` is optional but often useful

### 2.13 GET /timesheet/settings — Timesheet Settings

**Sandbox settings**:
```json
{
  "timeClock": false,
  "timesheetCompleted": true,
  "flexBalance": true,
  "vacationBalance": true,
  "showDetailedTimeSheet": false,
  "requireCommentsOnRegisteredHoursAllProjects": false
}
```

### 2.14 GET /timesheet/timeClock — Time Clock

**Sandbox**: Empty (time clock is disabled in settings).

### 2.15 GET /order — Orders

Orders can optionally link to a project via `project` ref field. Sandbox has 3 orders, none project-linked.

**Key order fields for project context**:
| Field | Notes |
|---|---|
| project | Optional ref — links order to project |
| customer | Required ref |
| orderLines | Order line items |
| isClosed | True after invoicing |

### 2.16 GET /invoice — Invoices with Project Details

Invoices have `projectInvoiceDetails` array linking to `/invoice/details/{id}`:

```json
{
  "feeAmount": 0.0,
  "markupPercent": 0.0,
  "includeOrderLinesAndReinvoicing": true,
  "includeHours": false,
  "includeOnAccountBalance": false,
  "project": {"id": 401950669}
}
```

**Key**: `includeHours: true` would pull logged timesheet hours into the invoice.

---

## 3. Project Lifecycle (Step-by-Step API Calls)

### 3.1 Create Project

**Minimum (2 API calls)**:
1. `GET /employee?firstName=Frikk` → get projectManager ID
2. `POST /project` with `{name, projectManager: {id}, startDate}`

**With customer link (3 API calls)**:
1. `GET /employee?firstName=Frikk` → projectManager ID
2. `GET /customer?name=Firma AS` → customer ID
3. `POST /project` with `{name, projectManager: {id}, startDate, customer: {id}}`

### 3.2 Assign Project Manager (Update)

1. `GET /project?name=ProjectName` → get project ID + version
2. `PUT /project/{id}` with `{id, version, projectManager: {"id": newManagerId}}`

### 3.3 Add Project Participant

**No direct API** for adding participants. Participants auto-include the projectManager. Additional participants are managed via the project update payload or the Tripletex UI.

### 3.4 Create Project Activity

Activities are global (`GET /activity`). Project-specific activities link via `projectActivity` endpoint, but the sandbox uses general project activities (`isGeneral: true`).

### 3.5 Log Hours on Project

1. `GET /project?name=ProjectName` → project ID
2. `GET /activity` → find project activity ID (e.g., "Fakturerbart arbeid")
3. `GET /employee?firstName=Name` → employee ID
4. `POST /timesheet/entry` with `{employee: {id}, project: {id}, activity: {id}, date, hours}`

**Minimum 4 API calls** (can be reduced to 2 if IDs are cached).

### 3.6 Invoice Project (Project Billing)

**Option A: Order-based (standard flow)**:
1. `GET /project/{id}` → verify customer is linked
2. `POST /order` with `{customer: {id}, project: {id}, orderLines: [...]}`
3. `PUT /order/{id}/:invoice` → generate invoice from order

**Option B: Direct project billing** (via invoice details):
1. `GET /project?name=Name` → project ID + customer
2. `POST /order` with customer + project + order lines based on logged hours
3. `PUT /order/{id}/:invoice`

**Current executor approach** (`_exec_project_billing`): Gets project, extracts customer, delegates to `_exec_create_invoice`. This is correct but skips the project-specific `includeHours` mechanism.

### 3.7 Close Project

1. `GET /project?name=ProjectName` → get ID + version
2. `PUT /project/{id}` with `{id, version, isClosed: true, endDate: "YYYY-MM-DD"}`

**2 API calls**.

---

## 4. Time Tracking Workflow

### 4.1 Core Concepts

- **Activity**: A type of work (e.g., "Administrasjon", "Fakturerbart arbeid"). Global or project-specific.
- **Timesheet Entry**: An employee's logged hours on a date, against an activity, optionally on a project.
- **Chargeable Hours**: Hours that can be billed to the customer. Determined by `activity.isChargeable`.
- **Locked Entries**: Cannot be modified (locked by period close or invoicing).

### 4.2 POST /timesheet/entry — Required Fields

```json
{
  "employee": {"id": 18491802},     // REQUIRED — who logged
  "activity": {"id": 5685471},      // REQUIRED — what type of work
  "project": {"id": 401950684},     // OPTIONAL — which project (null = general time)
  "date": "2026-03-21",             // REQUIRED — YYYY-MM-DD
  "hours": 7.5                      // REQUIRED — decimal hours
}
```

**Optional**:
- `comment`: Text description of work done
- No `chargeableHours` field on POST — computed from activity

### 4.3 Activity Selection Logic

For project time entries:
1. Try to match `activity_name` from prompt against existing activities
2. Prefer `isProjectActivity: true` activities
3. Prefer chargeable activities for billable work
4. Fallback: use "Fakturerbart arbeid" (id=5685471) for project work

For general (non-project) time:
1. Use "Administrasjon" (id=5685468) as default

### 4.4 Querying Timesheet Entries

```
GET /timesheet/entry?dateFrom=2026-03-01&dateTo=2026-03-31&employeeId=18491802&projectId=401950684
```

Returns entries with `sumAllHours` aggregate.

### 4.5 Time Clock (Not Used)

`timeClock: false` in settings. The `/timesheet/timeClock` endpoint is empty.

---

## 5. Project Billing Workflow

### 5.1 From Logged Hours to Invoice

The full project billing flow:

1. **Log hours** throughout the period (multiple `POST /timesheet/entry`)
2. **Verify project is ready**: `GET /project/{id}` — check `customer` is linked
3. **Create order with project reference**:
   ```json
   POST /order
   {
     "customer": {"id": customerFromProject},
     "project": {"id": projectId},
     "orderDate": "2026-03-31",
     "deliveryDate": "2026-03-31",
     "orderLines": [{
       "description": "Konsulentarbeid mars 2026",
       "count": 150,
       "unitPriceExcludingVat": 1200
     }]
   }
   ```
4. **Invoice the order**: `PUT /order/{id}/:invoice` (query params only, no body)

### 5.2 Invoice Details with Hours

When an invoice is created from a project order, Tripletex creates `projectInvoiceDetails` entries. These can include:
- `includeHours: true` — pulls logged chargeable hours
- `includeOrderLinesAndReinvoicing: true` — includes order lines
- `feeAmount` — additional fees/markup

### 5.3 Current Executor Implementation

`_exec_project_billing` (line 1697):
1. Finds project by name
2. Checks customer is linked
3. Delegates to `_exec_create_invoice`

**Gap**: Does not pull logged hours automatically. Uses generic invoice creation instead of project-specific billing with `includeHours`.

### 5.4 Fixed Price vs. Time & Materials

| Mode | Field | Billing |
|---|---|---|
| Fixed price | `isFixedPrice: true, fixedprice: 50000` | Invoice fixed amount |
| Time & Materials | `isFixedPrice: false` | Invoice based on logged hours × rate |

---

## 6. Prompt Patterns (Norwegian + English)

### 6.1 Project Creation

**Norwegian**:
- "Opprett prosjekt Nettside for kunde Firma AS"
- "Lag et nytt prosjekt kalt Havnelogistikk"
- "Opprett prosjekt Redesign med Kari som prosjektleder"
- "Nytt fastprisprosjekt Migrasjon, 150 000 kr"

**English**:
- "Create project Website for customer Firma AS"
- "New project Harbour Logistics starting 2026-04-01"
- "Create internal project Team Building"

**Fields to extract**: name, customer_name, project_manager_name, start_date, end_date, is_fixed_price, fixed_price, is_internal, description

### 6.2 Time Logging

**Norwegian**:
- "Registrer 7.5 timer på prosjekt Nettside, aktivitet Utvikling"
- "Logg 3 timer på Havnelogistikk i dag"
- "Før 8 timer prosjektarbeid for Kari på Nettside, 20. mars"
- "Registrer 2 timer administrasjon"

**English**:
- "Log 7.5 hours on project Website, activity Development"
- "Register 3 hours on Harbour Logistics today"
- "Book 8 hours for Kari on project Website, March 20"

**Fields to extract**: hours, project_name, activity_name, employee_identifier (first_name/last_name/email), date, comment

### 6.3 Project Billing

**Norwegian**:
- "Fakturer timer på prosjekt Nettside for mars 2026"
- "Opprett faktura fra prosjekt Havnelogistikk"
- "Fakturer prosjekt Redesign med fastpris 150 000"
- "Send faktura for prosjektarbeid på Nettside til Firma AS"

**English**:
- "Invoice project Website for March 2026"
- "Bill project Harbour Logistics"
- "Create invoice from project hours"

**Fields to extract**: project_identifier, invoice_date, period (month/year), lines (if manual)

### 6.4 Project Management

**Norwegian**:
- "Legg til Kari som prosjektleder på prosjekt Nettside"
- "Endre prosjektleder til Ola for Havnelogistikk"
- "Lukk prosjekt Nettside"
- "Oppdater sluttdato på prosjekt Redesign til 30. juni"
- "Vis timeregistreringer for prosjekt Nettside denne uken"

**English**:
- "Set Kari as project manager for Website project"
- "Close project Harbour Logistics"
- "Update end date on project Redesign to June 30"
- "Show timesheet entries for project Website this week"

### 6.5 Multi-language Patterns

| Language | "Create project" | "Log hours" | "Invoice project" |
|---|---|---|---|
| Norwegian | Opprett prosjekt | Registrer timer | Fakturer prosjekt |
| English | Create project | Log hours | Invoice project |
| Swedish | Skapa projekt | Registrera timmar | Fakturera projekt |
| Danish | Opret projekt | Registrer timer | Fakturer projekt |
| German | Projekt erstellen | Stunden erfassen | Projekt fakturieren |
| French | Créer un projet | Enregistrer des heures | Facturer le projet |
| Spanish | Crear proyecto | Registrar horas | Facturar proyecto |

---

## 7. Gap Analysis

### 7.1 What We Handle Well

| Scenario | Handler | Status |
|---|---|---|
| Create project | `_exec_create_project` | Working |
| Create project with customer | `_exec_project_with_customer` | Working |
| Update project | `_exec_update_project` | Working |
| Delete project | `_exec_delete_project` | Working |
| Log hours | `_exec_log_hours` | Working (creates project/employee if needed) |
| Project billing | `_exec_project_billing` | Basic (delegates to generic invoice) |

### 7.2 Gaps & Missing Capabilities

| Scenario | Current Status | Impact |
|---|---|---|
| **Invoice from logged hours** | Not implemented — PROJECT_BILLING doesn't pull timesheet data | High — PM workflow core feature |
| **View project hours** | No handler — read-only query | Medium — PM needs visibility |
| **Change project manager** | UPDATE_PROJECT handles this but may not extract well | Low — covered by generic update |
| **Add project participants** | No endpoint available (405 on GET /project/participant) | Low — auto-managed by Tripletex |
| **Project-specific activities** | GET /project/projectActivity returns 405 | Low — global activities work |
| **Hourly rate management** | No handler — rates auto-created at 0.0 | Medium — affects billing amounts |
| **Project budget tracking** | No handler — no budget API exposed | Medium |
| **Project period management** | `/project/period` returns 422 — format unclear | Low |
| **Sub-projects** | `mainProject` field exists but no handler | Low |
| **Project categories** | None configured on sandbox | Low |
| **Time clock** | Disabled in settings, no handler | Low |
| **Lock timesheet periods** | No handler | Low |

### 7.3 Specific Issues Found

1. **`_exec_project_billing`** (line 1697): Gets project, verifies customer, then delegates to `_exec_create_invoice` with generic `fields`. Does NOT:
   - Pull logged timesheet hours
   - Calculate billable amount from hours × rate
   - Set `includeHours: true` in invoice details
   - Handle period-specific billing (e.g., "invoice March hours")

2. **`_exec_log_hours`** (line 1841): Works well but has these issues:
   - Creates employee if not found (risky — may create duplicates)
   - Creates project if not found (risky — may create duplicates)
   - Activity matching: falls back to first activity if no name match

3. **Hourly rates**: All projects auto-create with `fixedRate: 0.0`. The billing workflow produces $0 invoices unless order lines have explicit unit prices.

4. **No read-only query handlers**: "Show me hours on project X" or "What's the project status?" cannot be answered — we only have mutation handlers.

---

## 8. Recommendations

### 8.1 High Priority — Improve PROJECT_BILLING

Enhance `_exec_project_billing` to:
1. Query `GET /timesheet/entry?projectId={id}&dateFrom=...&dateTo=...` for logged hours
2. Calculate total chargeable hours × hourly rate
3. Create order with calculated amount as order line
4. Consider period-based billing (extract month/year from prompt)

### 8.2 Medium Priority — Set Hourly Rates on Project Creation

When creating a project, if a rate is specified:
1. Create project (auto-creates hourly rate at 0.0)
2. `GET /project/hourlyRates?projectId={id}` → get rate record ID + version
3. `PUT /project/hourlyRates/{id}` with `{fixedRate: 1200}`

### 8.3 Medium Priority — Improve LOG_HOURS Safety

- Don't auto-create employees — return error if not found
- Don't auto-create projects — return error if not found
- These create side effects that may not match user intent

### 8.4 Low Priority — Add Read-Only Handlers

Consider a QUERY task type or extending existing handlers to support:
- "Vis timer for prosjekt X" → query timesheet entries
- "Prosjektstatus for X" → get project with hours summary

### 8.5 Field Extraction Improvements

For `LOG_HOURS`, ensure classifier extracts:
- `hours` (decimal, e.g., 7.5 from "7,5 timer")
- `date` (specific date or "i dag" = today)
- `activity_name` (often "utvikling", "design", "møte")
- `comment` (free text after core fields)

For `PROJECT_BILLING`, add fields:
- `period_start` / `period_end` (for "mars 2026" → 2026-03-01 to 2026-03-31)
- `hourly_rate` (if not set on project)

### 8.6 API Call Efficiency

**Current state** — API calls per operation:
| Operation | Current Calls | Optimal |
|---|---|---|
| Create project | 2-3 | 2 (employee lookup + POST) |
| Log hours | 3-6 | 2 (if IDs known) |
| Project billing | 4-6 | 3 (project lookup + order + invoice) |
| Update project | 2 | 2 (GET + PUT) |

**Key optimization**: Cache employee ID (18491802) and activity IDs across calls within a single request. The executor could maintain a request-scoped cache.

---

## Appendix A: Sandbox Data Reference

### Employees
| id | name | email |
|---|---|---|
| 18491802 | Frikk a23fd25c | frikk@guerrilla.no |
| 18492587 | Ola Nordmann | ola@example.com |

### Projects (7 total)
| id | name | number | customer | isClosed |
|---|---|---|---|---|
| 401950684 | API Test Project v2 | 3 | none | false |
| 401950691 | API Test Project | 99001 | none | false |
| 401950848 | Fix Verify Project | 99015 | none | false |
| 401950957 | Havnelogistikk | — | none | false |
| 401951089 | Prosjektrxewn | — | none | false |
| 401951092 | Prosjektleotl | — | none | false |
| (7th) | — | — | — | — |

### Activities (4 total)
| id | name | type | forProject | chargeable |
|---|---|---|---|---|
| 5685468 | Administrasjon | GENERAL | no | no |
| 5685469 | Ferie | GENERAL | no | no |
| 5685470 | Prosjektadministrasjon | PROJECT_GENERAL | yes | no |
| 5685471 | Fakturerbart arbeid | PROJECT_GENERAL | yes | **yes** |

### Timesheet Settings
- Time clock: disabled
- Timesheet completion: enabled
- Flex balance: enabled
- Require comments: disabled
