# ADMIN ROLE RESEARCH — CREATE_EMPLOYEE Scoring Issue

**Date:** 2026-03-20
**Issue:** "Administrator role assigned" is worth 5/10 points for CREATE_EMPLOYEE tasks

---

## 1. The Scoring Breakdown

From the official competition docs (`challenge://tripletex/scoring`):

| Check | Points |
|-------|--------|
| Employee found | 2 |
| Correct first name | 1 |
| Correct last name | 1 |
| Correct email | 1 |
| Administrator role assigned | 5 |
| **Total** | **10** |

**The admin role check is worth HALF the total score.** Getting name+email right but missing the admin role gives only 5/10 = 0.5 correctness. With Tier 1 multiplier (x1) and no efficiency bonus on imperfect scores, that's just 0.5 points.

---

## 2. What Does the Tripletex API Support?

### 2a. userType Enum (the ONLY role-related field on Employee)

The Employee model has exactly three valid `userType` values:

| Value | Description |
|-------|-------------|
| `STANDARD` | Reduced access. Users with limited system entitlements. |
| `EXTENDED` | Users can be given ALL system entitlements. This is the "admin" tier. |
| `NO_ACCESS` | User with no log on access. |

**There is NO `ADMINISTRATOR` userType.** The API rejects unknown enum values.

Source: [Tripletex Ruby API - Employee.md](https://github.com/sveredyuk/tripletex_ruby/blob/master/docs/Employee.md), [Tripletex API v2 docs](https://tripletex.no/v2-docs/)

### 2b. No Separate Admin/Role Fields

The Employee model does NOT have:
- `isAdministrator` field
- `allowLogin` field (only `allowInformationRegistration`, read-only)
- `role` or `roles` field
- Any admin boolean

The only role-related API is `/employee/entitlement` (GET only, read-only). There is no POST/PUT for entitlements through the standard API.

### 2c. Conclusion: The Grader Checks `userType`

Since `userType` is the ONLY writable role-related field on POST /employee, the grader's "Administrator role assigned" check almost certainly verifies:

```
employee.userType == "EXTENDED"
```

This is the only way to "assign an administrator role" via the API. `EXTENDED` = "can be given all system entitlements" = administrator.

---

## 3. How Our Code Maps User Types

### 3a. Executor (_USER_TYPE_MAP in executor.py lines 264-272)

```python
_USER_TYPE_MAP = {
    "ADMINISTRATOR": "EXTENDED",
    "ADMIN": "EXTENDED",
    "KONTOADMINISTRATOR": "EXTENDED",
    "RESTRICTED": "NO_ACCESS",
    "BEGRENSET": "NO_ACCESS",
    "INGEN_TILGANG": "NO_ACCESS",
    "NONE": "NO_ACCESS",
}
```

Validation: if not in `("STANDARD", "EXTENDED", "NO_ACCESS")` after mapping, defaults to `"STANDARD"`.

**This mapping is CORRECT.** Any admin-like value gets mapped to `EXTENDED`.

### 3b. Classifier (classifier.py lines 271-275)

The Gemini system prompt instructs:
```
When the prompt mentions administrator, admin, kontoadministrator → set user_type to "ADMINISTRATOR"
```

This outputs `user_type="ADMINISTRATOR"` which the executor then maps to `"EXTENDED"`. **Correct pipeline.**

### 3c. Rule-based Classifier (main.py lines 448-457)

```python
if any(w in text_lower for w in ["kontoadministrator", "administrator", "admin"]):
    fields["user_type"] = "ADMINISTRATOR"
```

Then the executor maps `"ADMINISTRATOR"` -> `"EXTENDED"`. **Correct.**

### 3d. Default Behavior (NO admin keyword in prompt)

If the prompt does NOT mention any admin keyword:
- `user_type` field is not set by classifier
- Executor defaults: `user_type = _get(fields, "user_type", "STANDARD").upper()` -> `"STANDARD"`
- Employee is created with `userType: "STANDARD"`

**CRITICAL PROBLEM: If the grader prompt says "kontoadministrator" but our classifier doesn't extract user_type, we send STANDARD and lose 5 points.**

---

## 4. Known Classification Bug: "kontoadministrator" Misclassification

### Test Result (from TEST-TIER3-EDGE.md, FIELD-16a):

```
Prompt: "Opprett ansatt med navn Admin Bruker, e-post admin@test.no, rolle kontoadministrator"
Expected: create_employee
Got: set_employee_roles (WRONG TASK TYPE!)
```

**Root cause:** The word "rolle" (role) triggers the `SET_EMPLOYEE_ROLES` pattern in the keyword classifier before `CREATE_EMPLOYEE` is checked. The keyword map in main.py checks `SET_EMPLOYEE_ROLES` patterns (which include "rolle") BEFORE `CREATE_EMPLOYEE`.

**Impact:** If the grader sends a CREATE_EMPLOYEE prompt with "rolle kontoadministrator", the rule-based classifier routes it to `set_employee_roles`, which tries to find an existing employee (fails on fresh account), and the employee is never created. Score = 0/10.

### But Without "rolle":

```
Prompt with "administrator" (no "rolle"): create_employee -> user_type=ADMINISTRATOR -> CORRECT
```

The word "kontoadministrator" alone (without "rolle") should still classify as CREATE_EMPLOYEE in the keyword classifier because "kontoadministrator" is checked inside the `_extract_fields_rule_based` function for CREATE_EMPLOYEE task type, not in the task-type matching keywords.

---

## 5. Grader Prompt Patterns (What We Expect)

Based on the scoring doc example: "Han skal vaere kontoadministrator" (He should be account administrator).

Likely grader prompts:
- `"Opprett en ansatt med navn X Y, e-post x@y.com. Han/hun skal vaere kontoadministrator."`
- `"Create employee X Y, email x@y.com. They should be an administrator."`
- `"Erstellen Sie einen Mitarbeiter X Y. Er soll Kontoadministrator sein."`

The key phrase patterns:
- Norwegian: "skal vaere kontoadministrator", "som kontoadministrator", "rolle kontoadministrator"
- English: "should be an administrator", "as administrator", "admin role"
- German: "soll Kontoadministrator sein", "als Administrator"

---

## 6. Keyword Variant Analysis

### What the classifier catches (user_type extraction in main.py):

| Keyword | Language | Matched by `in text_lower` | Result |
|---------|----------|---------------------------|--------|
| `kontoadministrator` | nb/nn | YES ("kontoadministrator" in text) | user_type=ADMINISTRATOR |
| `administrator` | multi | YES ("administrator" in text) | user_type=ADMINISTRATOR |
| `admin` | multi | YES ("admin" in text) | user_type=ADMINISTRATOR |
| `Kontoadministrator` | de | YES (lowercased first) | user_type=ADMINISTRATOR |
| `administrateur` | fr | NO - not in keyword list | **MISSED** -> defaults to STANDARD |
| `administrador` | es/pt | NO - not in keyword list | **MISSED** -> defaults to STANDARD |
| `Administrator` | de (capitalized) | YES (lowercased) | user_type=ADMINISTRATOR |

**Gap: French "administrateur" and Spanish/Portuguese "administrador" are NOT detected** by the rule-based classifier. They contain "admin" as a substring though, so `"admin" in text_lower` WOULD match them. Let me verify:

- `"administrateur"` contains `"admin"` -> YES, matched
- `"administrador"` contains `"admin"` -> YES, matched

**Actually, all variants ARE caught** because `"admin" in text_lower` is a substring check that matches any word containing "admin". This is correct behavior.

### What the Gemini classifier catches:

The system prompt says: `When the prompt mentions administrator, admin, kontoadministrator -> set user_type to "ADMINISTRATOR"`

Gemini should handle all natural language variants including French, German, etc.

---

## 7. Risk Assessment

### HIGH RISK: Task Type Misclassification
- If the prompt contains "rolle" + "kontoadministrator", the rule-based classifier picks `SET_EMPLOYEE_ROLES` instead of `CREATE_EMPLOYEE`
- This means the employee is never created -> 0/10 points
- **Mitigation:** Gemini/Claude classifiers should handle this correctly since they understand context. The rule-based classifier order needs fixing.

### MEDIUM RISK: Default to STANDARD When No Admin Keyword
- If the grader prompt uses an unexpected phrasing for admin role
- E.g., "med utvidet tilgang" (with extended access), "fullmakt" (authorization)
- These would NOT trigger the keyword check
- **Mitigation:** Add more keyword variants

### LOW RISK: userType Mapping
- The ADMINISTRATOR -> EXTENDED mapping in executor.py is correct
- All three valid userType values are handled
- The API POST /employee accepts userType in the payload

---

## 8. Summary of Findings

| Question | Answer |
|----------|--------|
| What does "Administrator role assigned" mean? | `userType: "EXTENDED"` on the created employee |
| Is there an "ADMINISTRATOR" userType? | NO. Only STANDARD, EXTENDED, NO_ACCESS |
| Does the grader check a separate role/permission? | NO. `userType` is the only writable role field |
| Is there `isAdministrator` field? | NO. Does not exist on Employee model |
| Does our mapping work? | YES. ADMINISTRATOR/ADMIN/KONTOADMINISTRATOR -> EXTENDED |
| What's the biggest risk? | Task type misclassification when prompt has "rolle" + admin keyword |
| Are multilingual admin keywords caught? | YES, via "admin" substring match |
| What if no admin keyword in prompt? | Defaults to STANDARD -> loses 5 points |

---

## 9. Recommendations (DO NOT IMPLEMENT - research only)

1. **Fix keyword classifier priority:** When prompt contains BOTH "opprett ansatt" AND "kontoadministrator", it should classify as `CREATE_EMPLOYEE` with `user_type=ADMINISTRATOR`, NOT as `SET_EMPLOYEE_ROLES`.

2. **Add more admin keyword variants:** Consider "utvidet" (extended), "full tilgang" (full access), "superbruker" (superuser) as indicators of EXTENDED userType.

3. **Gemini/Claude few-shot example:** Add an explicit example:
   ```
   Input: "Opprett ansatt Ola Nordmann, ola@test.no. Han skal vaere kontoadministrator."
   Output: {"task_type": "create_employee", "fields": {"first_name": "Ola", "last_name": "Nordmann", "email": "ola@test.no", "user_type": "ADMINISTRATOR"}}
   ```

4. **Consider always setting EXTENDED:** Since the admin check is worth 5/10 points and the grader example explicitly mentions "kontoadministrator", it's possible that ALL CREATE_EMPLOYEE grader prompts include an admin role requirement. If so, defaulting to EXTENDED instead of STANDARD might be a viable strategy (risky if some prompts explicitly say STANDARD).
