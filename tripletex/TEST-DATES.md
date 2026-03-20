# Date Parsing Test Results

**Test Date:** 2026-03-20
**LLM Mode:** none (rule-based fallback)
**Note:** No GEMINI_MODEL or ANTHROPIC_API_KEY set; all tests use rule-based classifier.

## 1. Full Pipeline Tests (classify function)

| Status | Field | Actual | Expected | Prompt (truncated) |
|--------|-------|--------|----------|--------------------|
| FAIL | `date_of_birth` | `NOT FOUND` | `1986-05-04` | Opprett ansatt born 4. May 1986 med namn Test Person, t... |
| FAIL | `date_of_birth` | `NOT FOUND` | `1990-03-15` | Opprett ansatt født 15. mars 1990 med namn Test Person,... |
| FAIL | `date_of_birth` | `NOT FOUND` | `1990-03-15` | Create employee Test Person born March 15, 1990, test@t... |
| FAIL | `date_of_birth` | `NOT FOUND` | `1990-03-15` | Erstellen Mitarbeiter Test Person geboren am 15. März 1... |
| FAIL | `date_of_birth` | `NOT FOUND` | `1990-03-15` | Créer employé Test Person né le 15 mars 1990, test@test... |
| PASS | `date_of_birth` | `1990-03-15` | `1990-03-15` | Opprett ansatt Test Person født 1990-03-15, test@test.n... |
| FAIL | `payment_date` | `NOT FOUND` | `2026-03-15` | Registrer innbetaling 5000 kr på faktura 10099, dato 15... |
| FAIL | `payment_date` | `NOT FOUND` | `2026-03-15` | Registrer innbetaling 5000 kr på faktura 10099, dato 20... |
| FAIL | `departure_date` | `NOT FOUND` | `2026-03-19` | Reiserekning for Per Hansen, dagsreise 19. mars 2026... |
| FAIL | `departure_date` | `NOT FOUND` | `2026-03-20` | Travel expense for John Smith, trip March 20-22, 2026... |
| FAIL | `date_of_birth` | `NOT FOUND` | `1986-05-04` | Opprett ansatt Test Person født 4. mai 1986, test@test.... |
| FAIL | `date_of_birth` | `NOT FOUND` | `1995-01-22` | Opprett ansatt Test Person født 22. januar 1995, test@t... |
| FAIL | `date_of_birth` | `NOT FOUND` | `1988-12-30` | Opprett ansatt Test Person født 30. desember 1988, test... |
| FAIL | `date_of_birth` | `NOT FOUND` | `1986-05-04` | Opprett ansatt Test Person født 4. May 1986, test@test.... |

**Result: 1 passed, 13 failed out of 14 tests**

## 2. Date Extraction Tests (classifier._extract_dates)

This tests the lower-level `_extract_dates` function from `classifier.py`,
which is used by the keyword-based classifier in `classifier.py` but NOT by
the rule-based classifier in `main.py`.

### Norwegian Month Names

| Status | Input | Parsed | Expected |
|--------|-------|--------|----------|
| PASS | `15. januar 2026` | `2026-01-15` | `2026-01-15` |
| PASS | `15. februar 2026` | `2026-02-15` | `2026-02-15` |
| PASS | `15. mars 2026` | `2026-03-15` | `2026-03-15` |
| PASS | `15. april 2026` | `2026-04-15` | `2026-04-15` |
| PASS | `15. mai 2026` | `2026-05-15` | `2026-05-15` |
| PASS | `15. juni 2026` | `2026-06-15` | `2026-06-15` |
| PASS | `15. juli 2026` | `2026-07-15` | `2026-07-15` |
| PASS | `15. august 2026` | `2026-08-15` | `2026-08-15` |
| PASS | `15. september 2026` | `2026-09-15` | `2026-09-15` |
| PASS | `15. oktober 2026` | `2026-10-15` | `2026-10-15` |
| PASS | `15. november 2026` | `2026-11-15` | `2026-11-15` |
| PASS | `15. desember 2026` | `2026-12-15` | `2026-12-15` |

**Norwegian: 12 passed, 0 failed out of 12**

### English Month Names

| Status | Input | Parsed | Expected |
|--------|-------|--------|----------|
| FAIL | `15. January 2026` | `NONE` | `2026-01-15` |
| FAIL | `15. February 2026` | `NONE` | `2026-02-15` |
| FAIL | `15. March 2026` | `NONE` | `2026-03-15` |
| PASS | `15. April 2026` | `2026-04-15` | `2026-04-15` |
| FAIL | `15. May 2026` | `NONE` | `2026-05-15` |
| FAIL | `15. June 2026` | `NONE` | `2026-06-15` |
| FAIL | `15. July 2026` | `NONE` | `2026-07-15` |
| PASS | `15. August 2026` | `2026-08-15` | `2026-08-15` |
| PASS | `15. September 2026` | `2026-09-15` | `2026-09-15` |
| FAIL | `15. October 2026` | `NONE` | `2026-10-15` |
| PASS | `15. November 2026` | `2026-11-15` | `2026-11-15` |
| FAIL | `15. December 2026` | `NONE` | `2026-12-15` |

**English: 4 passed, 8 failed out of 12**

### German Month Names

| Status | Input | Parsed | Expected |
|--------|-------|--------|----------|
| PASS | `15. Januar 2026` | `2026-01-15` | `2026-01-15` |
| PASS | `15. Februar 2026` | `2026-02-15` | `2026-02-15` |
| FAIL | `15. März 2026` | `NONE` | `2026-03-15` |
| PASS | `15. April 2026` | `2026-04-15` | `2026-04-15` |
| PASS | `15. Mai 2026` | `2026-05-15` | `2026-05-15` |
| PASS | `15. Juni 2026` | `2026-06-15` | `2026-06-15` |
| PASS | `15. Juli 2026` | `2026-07-15` | `2026-07-15` |
| PASS | `15. August 2026` | `2026-08-15` | `2026-08-15` |
| PASS | `15. September 2026` | `2026-09-15` | `2026-09-15` |
| PASS | `15. Oktober 2026` | `2026-10-15` | `2026-10-15` |
| PASS | `15. November 2026` | `2026-11-15` | `2026-11-15` |
| FAIL | `15. Dezember 2026` | `NONE` | `2026-12-15` |

**German: 10 passed, 2 failed out of 12**

### French Month Names

| Status | Input | Parsed | Expected |
|--------|-------|--------|----------|
| FAIL | `15. janvier 2026` | `NONE` | `2026-01-15` |
| FAIL | `15. février 2026` | `NONE` | `2026-02-15` |
| PASS | `15. mars 2026` | `2026-03-15` | `2026-03-15` |
| FAIL | `15. avril 2026` | `NONE` | `2026-04-15` |
| PASS | `15. mai 2026` | `2026-05-15` | `2026-05-15` |
| FAIL | `15. juin 2026` | `NONE` | `2026-06-15` |
| FAIL | `15. juillet 2026` | `NONE` | `2026-07-15` |
| FAIL | `15. août 2026` | `NONE` | `2026-08-15` |
| FAIL | `15. septembre 2026` | `NONE` | `2026-09-15` |
| FAIL | `15. octobre 2026` | `NONE` | `2026-10-15` |
| FAIL | `15. novembre 2026` | `NONE` | `2026-11-15` |
| FAIL | `15. décembre 2026` | `NONE` | `2026-12-15` |

**French: 2 passed, 10 failed out of 12**

### Numeric Date Formats

| Status | Input | Parsed | Expected |
|--------|-------|--------|----------|
| PASS | `15.03.2026` | `2026-03-15` | `2026-03-15` |
| PASS | `2026-03-15` | `2026-03-15` | `2026-03-15` |
| PASS | `15/03/2026` | `2026-03-15` | `2026-03-15` |
| PASS | `15-03-2026` | `2026-03-15` | `2026-03-15` |
| PASS | `1986-05-04` | `1986-05-04` | `1986-05-04` |
| PASS | `04.05.1986` | `1986-05-04` | `1986-05-04` |

**Numeric formats: 6 passed, 0 failed out of 6**

## 3. Summary

### Full Pipeline (classify)
- **1 passed, 13 failed** out of 14 tests

### Date Extraction (_extract_dates)
- **34 passed, 20 failed** out of 54 tests

## 4. Root Cause Analysis

### Problem 1: Rule-based classifier in `main.py` ignores textual dates

The `_extract_fields_rule_based()` function in `main.py` (line 442-445) only
extracts `date_of_birth` when the date is already in YYYY-MM-DD format:
```python
m = re.search(r"(?:født|born|date.?of.?birth|...)\s*:?\s*(\d{4}-\d{2}-\d{2})", text, re.I)
```
It does NOT call `classifier._extract_dates()` and does not handle textual
month names (e.g., '15. mars 1990') or DD.MM.YYYY numeric format for birth dates.

### Problem 2: Rule-based classifier does not extract `payment_date` or `departure_date`

The `_extract_fields_rule_based()` function has no extraction logic for
`payment_date` on register_payment tasks or `departure_date` on travel expense tasks.
These fields are only populated when using the `classifier.py` keyword path or LLM paths.

### Problem 3: `_extract_dates` in `classifier.py` only knows Norwegian months

The `_RE_DATE_TEXT_NB` regex in `classifier.py` (line 1009-1012) only matches
Norwegian month names. It does not recognize:
- English: January, February, March, May, June, July, October, December
- German: März, Dezember
- French: janvier, février, avril, juin, juillet, août, septembre, octobre, novembre, décembre

Some months coincidentally match because they are identical in Norwegian and the
other language (e.g., April, August, September, November for English/German).

### Problem 4: Dispatch inconsistency

When no LLM is available, `main.py:classify()` uses `_classify_rule_based()` from
`main.py`, NOT `_classify_with_keywords()` from `classifier.py`. The latter has
better date extraction via `_extract_dates()` and `_extract_fields_generic()`.
However, even `classifier.py`'s date extraction is incomplete for non-Norwegian months.

### Recommendations

1. **Add multilingual month names** to `_RE_DATE_TEXT_NB` / `_MONTH_NB` in `classifier.py`
   to cover English, German, and French month names.
2. **Use `_extract_dates()` from `classifier.py`** in `main.py`'s `_extract_fields_rule_based()`
   for extracting `date_of_birth`, `payment_date`, and `departure_date`.
3. **Add English-style date parsing** (e.g., 'March 15, 1990') to `_extract_dates()`.
4. **Consider unifying** the rule-based paths so `main.py` delegates to `classifier.py`'s
   `_classify_with_keywords()` instead of maintaining a separate `_classify_rule_based()`.
