# Tripletex AI Agent — Architecture Research

## Executive Summary

**Recommended architecture: Hybrid LLM-Parse + Deterministic Execute**

The efficiency bonus (up to 2× score) is the single biggest scoring lever. An agent that makes zero unnecessary API calls will dramatically outperform a "smart" agent that explores the API. The optimal strategy:

1. LLM parses natural language → identifies task type + extracts structured fields
2. Deterministic code executes the minimum API calls for that task type
3. LLM never touches the API directly — no ReAct loops, no exploration

This gives us: maximum correctness (structured extraction) × maximum efficiency (pre-mapped API sequences) = maximum score.

---

## 1. Architecture Comparison

### Option A: ReAct Agent (LLM calls APIs iteratively)
- LLM reasons → calls API → observes → reasons → calls API...
- **Pros:** Flexible, handles unknown task types
- **Cons:** Many API calls (kills efficiency bonus), slow (300s timeout risk), expensive, hallucination risk
- **Verdict: REJECTED** — efficiency bonus penalty is catastrophic

### Option B: Plan-then-Execute (LLM plans, executor runs)
- LLM generates a plan of API calls → executor runs them
- **Pros:** Better than ReAct, some efficiency gains
- **Cons:** LLM may plan unnecessary calls, still variable API count
- **Verdict: PARTIALLY USEFUL** — good for Tier 3 unknown tasks only

### Option C: Direct Prompt → Structured Output (LLM extracts fields)
- LLM receives task text → outputs structured JSON with task type + fields
- **Pros:** Single LLM call, deterministic downstream execution, maximum efficiency
- **Cons:** Requires pre-mapping all task types
- **Verdict: RECOMMENDED** — perfect for known task types (Tier 1-2)

### Option D: Hybrid (C for known tasks, B for unknown)
- Use Option C for all 30 known task types
- Fall back to Option B for truly novel Tier 3 tasks
- **Verdict: OPTIMAL** — covers all scenarios

---

## 2. The Efficiency Bonus Strategy (CRITICAL)

### Scoring Math
```
score = correctness × tier_multiplier × efficiency_bonus
      = correctness × tier × (1.0 + efficiency_factor)

Max possible: 1.0 × 3.0 × 2.0 = 6.0
```

### Key Insight: Pre-map ALL 30 Task Types

Each task type maps to a **deterministic API call sequence**. Examples:

| Task Type | Minimum API Calls | Sequence |
|-----------|-------------------|----------|
| Create employee | 1 | `POST /employee` |
| Create customer | 1 | `POST /customer` |
| Create product | 1 | `POST /product` |
| Create invoice | 2-3 | `POST /order` → `PUT /order/{id}/:invoice` |
| Create invoice with new customer | 3-4 | `POST /customer` → `POST /order` → invoice |
| Travel expense | 2-3 | `POST /travelExpense` → `POST /travelExpense/cost` |
| Create project | 1-2 | `POST /project` (may need customer ID first) |
| Department setup | 1 | `POST /department` |
| Payment | 1-2 | `POST /payment` or similar |
| Error correction | 1-2 | `PUT /entity/{id}` or reversal endpoint |

### Zero-LLM-API-Call Architecture
```
Task Text (NL) → [LLM: extract fields] → {task_type, fields} → [Deterministic Router] → [API Calls]
                      ↑                                              ↑
                 1 LLM call only                           Pre-mapped minimal sequence
                 (not counted?)                            (counted, but minimal)
```

The LLM should make ZERO Tripletex API calls. It only parses text. The code makes the minimum possible API calls.

### Avoiding 4xx Errors
The competition docs mention 4xx errors reduce the efficiency bonus. This means:
- Validate extracted fields BEFORE making API calls
- Use schema validation (required fields, data types, formats)
- Never "explore" the API — know exactly what to send
- Build field validation maps per task type

---

## 3. Multi-Language Handling

### 7 Languages
Norwegian (Bokmål), Nynorsk, English, Spanish, Portuguese, German, French

### Recommendation: Option B — Multilingual LLM Directly

**Why NOT translate first:**
- Extra LLM call = extra latency
- Translation can lose domain-specific terms (Norwegian accounting terminology)
- Modern LLMs handle all 7 languages natively

**Why multilingual LLM works:**
- Gemini 2.0 Flash shows tight performance across languages (0.546 Chinese vs 0.550 English)
- Structured output works regardless of input language
- Accounting terms are similar across European languages (faktura/invoice/factura/Rechnung)

**Implementation:**
- Single prompt with multilingual examples
- Include key accounting terms in all 7 languages in the prompt
- Use structured output (JSON schema) to force consistent field names regardless of input language

### Language-Specific Field Mapping
Some fields may need language-aware parsing:
- Date formats: DD.MM.YYYY (Norwegian) vs MM/DD/YYYY (English) vs DD/MM/YYYY (others)
- Number formats: 1.000,50 (Norwegian/German) vs 1,000.50 (English)
- Currency: NOK assumed but task may specify

---

## 4. LLM Choice Analysis

### Gemini 2.0 Flash (PRIMARY RECOMMENDATION)
- **Free via GCP** (already provisioned) — no cost constraint
- **Fast:** ~0.5-1s for structured output extraction
- **Structured output:** Native JSON schema support via `response_mime_type: "application/json"`
- **Multilingual:** Strong across European languages
- **Pydantic integration:** Define task schemas in Python, pass to Gemini
- **Latency:** Well within 300s timeout (leaves 290s+ for API calls)

### Gemini 2.5 Flash (if available)
- Even better accuracy, especially on reasoning tasks
- Check if available in europe-north1

### Claude API (BACKUP)
- Superior at nuanced text understanding and structured extraction
- Tool use / function calling is very reliable
- **Cost:** Not free, adds complexity
- **When to use:** If Gemini fails on edge cases or Tier 3 tasks

### Recommendation
- **Primary:** Gemini 2.0 Flash (or 2.5 if available) for all task parsing
- **Fallback:** Claude Sonnet for Tier 3 complex tasks if Gemini struggles
- **Never:** GPT-4 (unnecessary cost/latency for this task)

---

## 5. Proposed Architecture

### Component Diagram
```
                    ┌──────────────────────────────────────┐
                    │          POST /solve                  │
                    │     (Cloud Run endpoint)              │
                    └──────────────┬───────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────────────┐
                    │       1. Task Classifier              │
                    │  (Gemini structured output)           │
                    │                                       │
                    │  Input: task text (any language)       │
                    │  Output: {                             │
                    │    task_type: enum(30 types),          │
                    │    fields: {extracted values},         │
                    │    confidence: float                   │
                    │  }                                     │
                    └──────────────┬───────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────────────┐
                    │       2. Field Validator               │
                    │  (Deterministic code)                  │
                    │                                       │
                    │  - Required fields present?            │
                    │  - Data types correct?                 │
                    │  - Date/number format normalized?      │
                    │  - Confidence threshold met?           │
                    └──────────────┬───────────────────────┘
                                   │
                          ┌────────┴────────┐
                          │                 │
                     confidence ≥ 0.8   confidence < 0.8
                          │                 │
                          ▼                 ▼
                    ┌────────────┐   ┌────────────────┐
                    │ 3a. Direct │   │ 3b. Fallback   │
                    │  Executor  │   │  (Re-prompt     │
                    │            │   │   or Plan+Exec) │
                    └─────┬──────┘   └───────┬────────┘
                          │                  │
                          ▼                  ▼
                    ┌──────────────────────────────────────┐
                    │       4. API Executor                  │
                    │  (Deterministic, pre-mapped)           │
                    │                                       │
                    │  task_type → [ordered API calls]       │
                    │  Each call: method, endpoint, payload  │
                    │  Sequential execution with ID passing  │
                    └──────────────┬───────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────────────┐
                    │       5. Response Builder              │
                    │  Return success/failure + metadata     │
                    └──────────────────────────────────────┘
```

### Data Flow Pseudocode

```python
from pydantic import BaseModel
from enum import Enum

# === 1. Task Type Definitions ===

class TaskType(str, Enum):
    CREATE_EMPLOYEE = "create_employee"
    UPDATE_EMPLOYEE = "update_employee"
    CREATE_CUSTOMER = "create_customer"
    CREATE_PRODUCT = "create_product"
    CREATE_INVOICE = "create_invoice"
    CREATE_INVOICE_WITH_CUSTOMER = "create_invoice_with_customer"
    SEND_INVOICE = "send_invoice"
    REGISTER_PAYMENT = "register_payment"
    CREATE_TRAVEL_EXPENSE = "create_travel_expense"
    CREATE_PROJECT = "create_project"
    CREATE_DEPARTMENT = "create_department"
    ENABLE_MODULE = "enable_module"
    REVERSE_ENTRY = "reverse_entry"
    # ... all 30 types

class TaskClassification(BaseModel):
    task_type: TaskType
    confidence: float
    fields: dict  # Task-type-specific extracted fields

# === 2. LLM Extraction (single call) ===

async def classify_task(task_text: str) -> TaskClassification:
    """Single Gemini call to classify + extract fields."""
    response = await gemini.generate_content(
        contents=task_text,
        config={
            "response_mime_type": "application/json",
            "response_schema": TaskClassification.model_json_schema(),
            "system_instruction": SYSTEM_PROMPT,  # includes all 30 task types + examples
        }
    )
    return TaskClassification.model_validate_json(response.text)

# === 3. Pre-mapped API Sequences ===

TASK_SEQUENCES = {
    TaskType.CREATE_EMPLOYEE: [
        ApiCall("POST", "/employee", lambda f: {
            "firstName": f["first_name"],
            "lastName": f["last_name"],
            "email": f.get("email"),
            # ... map all fields
        })
    ],
    TaskType.CREATE_INVOICE: [
        # Step 1: Create order
        ApiCall("POST", "/order", lambda f: {
            "customer": {"id": f["customer_id"]},
            "orderDate": f["date"],
            "orderLines": [{"product": {"id": f["product_id"]}, "count": f["quantity"]}]
        }),
        # Step 2: Convert to invoice
        ApiCall("PUT", "/order/{prev_id}/:invoice", lambda f: {
            "invoiceDate": f["date"],
            "sendToCustomer": False,
        })
    ],
    # ... all 30 task types
}

# === 4. Executor ===

async def execute_task(classification: TaskClassification, api_client) -> dict:
    """Execute pre-mapped API calls with minimal calls."""
    sequence = TASK_SEQUENCES[classification.task_type]
    results = []
    prev_id = None

    for call in sequence:
        payload = call.build_payload(classification.fields, prev_id)

        # Validate before calling (avoid 4xx!)
        validate_payload(call.endpoint, payload)

        response = await api_client.request(
            call.method,
            call.endpoint.format(prev_id=prev_id),
            json=payload
        )
        prev_id = response.get("value", {}).get("id")
        results.append(response)

    return {"success": True, "results": results}

# === 5. Main Handler ===

async def solve(task_text: str) -> dict:
    # Step 1: LLM classifies + extracts (1 LLM call, 0 API calls)
    classification = await classify_task(task_text)

    # Step 2: Validate
    if classification.confidence < 0.5:
        # Fallback: re-prompt with more context or use plan-execute
        classification = await classify_task_with_examples(task_text)

    # Step 3: Execute deterministically (minimum API calls)
    result = await execute_task(classification, tripletex_client)

    return result
```

### System Prompt Design (Key Component)

```
You are an accounting task classifier for Tripletex ERP.

Given a task description in any of these languages: Norwegian (Bokmål),
Nynorsk, English, Spanish, Portuguese, German, French — identify the
task type and extract all relevant fields.

## Task Types and Required Fields:

### create_employee
Required: first_name, last_name
Optional: email, phone, department, start_date, employee_number

### create_customer
Required: name
Optional: email, phone, org_number, address, postal_code, city

### create_invoice
Required: customer_id OR customer_name, lines (product + quantity + price)
Optional: invoice_date, due_date, comment

[... all 30 types with field definitions ...]

## Field Formatting Rules:
- Dates: always output as YYYY-MM-DD
- Numbers: always output as plain numbers (no thousand separators)
- Currency amounts: always in NOK unless explicitly stated otherwise
- Names: preserve original casing
- Boolean values: true/false

## Examples:
[Include 2-3 examples per language for common task types]
```

---

## 6. Error Handling Strategy

### Pre-call Validation (Prevent 4xx)
```python
FIELD_VALIDATORS = {
    "email": lambda v: re.match(r"^[^@]+@[^@]+\.[^@]+$", v),
    "date": lambda v: parse_date(v) is not None,
    "phone": lambda v: re.match(r"^[\d\s\+\-]+$", v),
    "org_number": lambda v: len(v) == 9 and v.isdigit(),
}
```

### Retry Strategy
1. **LLM misparse:** Re-prompt with the original text + "Previous extraction failed validation: {error}". Max 1 retry.
2. **API 4xx:** Do NOT retry blindly. Log error, check if field mapping is wrong. 4xx errors hurt the efficiency score.
3. **API 5xx:** Retry once with exponential backoff (server-side issue).
4. **Timeout risk:** Monitor elapsed time. If >240s elapsed, abort gracefully.

### Ambiguous Tasks
- If task type confidence < 0.5, try re-extraction with few-shot examples
- If still ambiguous, try the most likely interpretation (wrong answer > no answer, since best score is kept)
- Never make exploratory API calls to "figure out" what to do

---

## 7. Implementation Priority

### Phase 1: MVP (First 4 hours) — Target: Tier 1 Working
1. Cloud Run endpoint accepting POST /solve
2. Gemini structured output for 10 most common task types
3. Hardcoded API sequences for those 10 types
4. Basic field extraction (English + Norwegian)

### Phase 2: Coverage (Next 4 hours) — Target: All Tier 1 Perfect
5. All 30 task types mapped
6. All 7 languages tested
7. Field validation layer
8. Retry logic for LLM misparse

### Phase 3: Optimization (Next 4 hours) — Target: Max Efficiency Bonus
9. Minimize API calls per task (audit each sequence)
10. Cache lookups (e.g., GET customer by name → cache ID)
11. Batch operations where possible
12. Ensure zero 4xx errors

### Phase 4: Tier 2 & 3 (Remaining time)
13. Tier 2 task types (likely more complex multi-step)
14. Tier 3 task types (may need plan-execute fallback)
15. Edge case handling

---

## 8. Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| LLM | Gemini 2.0/2.5 Flash | Free, fast, native structured output |
| Architecture | Parse + Deterministic Execute | Maximizes efficiency bonus |
| Language handling | Direct multilingual (no translation) | Fewer calls, modern LLMs handle it |
| Framework | Python + FastAPI + httpx | Fast to develop, async, Cloud Run friendly |
| Task mapping | Static dict of API sequences | Deterministic, auditable, minimal calls |
| Validation | Pre-call field validation | Prevents 4xx errors (efficiency penalty) |
| Fallback | Re-prompt → plan-execute | Only for truly unknown task types |

---

## 9. Risk Analysis

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Gemini misparses task | Medium | High | Few-shot examples per type, retry once |
| Unknown Tier 3 task type | High | Medium | Plan-execute fallback |
| API sequence wrong | Medium | High | Test each sequence against sandbox |
| Date/number format errors | High | Medium | Robust parsing with locale awareness |
| Timeout (300s) | Low | High | Monitor elapsed time, abort at 240s |
| Gemini rate limits | Low | Medium | Batch requests, use Flash (high limits) |

---

## Sources
- [Tripletex API 2.0 Docs](https://tripletex.no/v2-docs/)
- [Tripletex API GitHub](https://github.com/Tripletex/tripletex-api2)
- [Tripletex Developer Portal](https://developer.tripletex.no/)
- [Gemini Structured Output Docs](https://ai.google.dev/gemini-api/docs/structured-output)
- [ReAct vs Plan-and-Execute Comparison](https://dev.to/jamesli/react-vs-plan-and-execute-a-practical-comparison-of-llm-agent-patterns-4gh9)
- [LLM Agent Architectures](https://apxml.com/courses/langchain-production-llm/chapter-2-sophisticated-agents-tools/agent-architectures)
- [Gemini 2.0 Flash Review](https://textcortex.com/post/gemini-2-0-flash-review)
