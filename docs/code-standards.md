# Code Standards -- Healthcare Platform

This document is the authoritative standard for all Python code in this repository.
Every pull request is reviewed against these rules. No exceptions.

---

## 1. The Core Principle

**Code is written once and read many times.**
Optimise for the reader, not the writer.
When you finish writing a function, ask: "Would a senior engineer understand this
in 30 seconds without running it?" If the answer is no, rewrite it.

---

## 2. Comment Rules

### Write comments that explain WHY, never WHAT

The code shows what it does. The comment explains why the code does it that way
and not some other way.

**BAD -- describes what the code does (obvious from reading it):**
```python
# Loop through appointments and format each one
appointments = [_format_appointment(row) for row in appt_rows]

# Check if patient exists
patient_rows = db.execute_query(_CHECK_PATIENT_EXISTS, (patient_id,))
if not patient_rows:
    raise RecordNotFoundError("Patient not found")
```

**GOOD -- explains the non-obvious why:**
```python
# SHA-256 check before bcrypt to avoid paying the 200ms hashing cost on duplicate requests
existing = db.execute_query(_CHECK_EMAIL_UNIQUE, (email_sha256,))

# Pool is lazily initialised so Lambda cold start does not pay connection cost
# for invocations that are rejected at the validation layer before DB is needed
_pool: psycopg2.pool.ThreadedConnectionPool | None = None

# Retry once -- RDS resets connections after ~8 hours of idle time on free-tier
except psycopg2.OperationalError:
    _pool = None
```

### Comment placement
- Comments go on the line immediately **above** the code they describe, never inline
  unless the inline note is 3 words or fewer
- Inline comments (same line as code) are only acceptable for `# noqa` directives or
  short clarifications on constants: `_MAX_RESULTS = 5  # YouTube API page size cap`

### Comment formatting
- Start with a capital letter
- No period at the end
- Maximum one line -- if you need two lines, the code or the function is too complex
- Never start a comment with "This", "We", "It", or "I"

### What must NEVER have a comment
- Function signatures where the name and type hints are self-documenting
- Simple assignments: `count = len(rows)` -- no comment needed
- Control flow that matches English directly: `if not rows: raise RecordNotFoundError(...)`
- Import statements
- `return` statements on simple functions

---

## 3. Function Rules

### Size
- A function must do **one thing**. If you find yourself writing "and" when you describe
  what a function does, split it into two functions.
- Maximum 30 lines of code per function body (excluding blank lines and comments).
  If you exceed this, extract a helper with a meaningful name.

### Naming
- Functions are verbs or verb phrases: `validate_body`, `get_patient`, `build_dsn`
- Functions that return a boolean start with `is_` or `has_`: `is_valid_uuid`, `has_active_conditions`
- Private functions (module-internal) start with `_`: `_scrub_dict`, `_build_query`
- Never abbreviate unless the abbreviation is universally known (`db`, `id`, `url`)

### Return types
- Every function has a return type annotation, including `-> None`
- Functions return early to avoid deep nesting -- maximum 3 levels of indentation

**BAD -- deep nesting:**
```python
def handler(event, context):
    patient_id = event.get("pathParameters", {}).get("patient_id")
    if patient_id:
        rows = db.execute_query(...)
        if rows:
            data = rows[0]
            if data["status"] == "active":
                return response.success(data)
    return response.error(...)
```

**GOOD -- early returns flatten the structure:**
```python
def handler(event: dict, context: Any) -> dict:
    patient_id = validate_uuid_path_param(
        (event.get("pathParameters") or {}).get("patient_id"), "patient_id"
    )
    rows = db.execute_query(_SELECT_PATIENT, (patient_id,))
    if not rows:
        raise RecordNotFoundError("Patient not found")
    if rows[0]["status"] != "active":
        raise ValidationError("Patient account is not active")
    return response.success(rows[0])
```

---

## 4. Naming Conventions

| Thing | Convention | Example |
|---|---|---|
| Module | `snake_case` | `list_prescriptions.py` |
| Class | `PascalCase` | `HealthcarePlatformError` |
| Function | `snake_case` | `validate_body` |
| Variable | `snake_case` | `patient_id` |
| Constant (module-level) | `UPPER_SNAKE_CASE` | `PHI_BLOCKED_KEYS` |
| Private function/var | `_snake_case` | `_scrub_dict` |
| SQL query constant | `UPPER_SNAKE_CASE` | `_SELECT_UPCOMING_APPOINTMENTS` |
| Type alias | `PascalCase` | `RowDict` |

---

## 5. SQL Query Standards

- All SQL queries are **named constants** at the top of the module -- never written inline
- All queries use `%s` parameterised placeholders -- string formatting into SQL is forbidden
- Query constant names are verb-first: `_INSERT_PATIENT`, `_SELECT_UPCOMING`, `_UPDATE_APPOINTMENT_TIMESTAMP`
- Multi-line queries use triple-quoted strings with each clause on its own line:

**BAD:**
```python
rows = db.execute_query(f"SELECT * FROM patients WHERE id = '{patient_id}'")
```

**GOOD:**
```python
_SELECT_PATIENT = """
    SELECT id, first_name, last_name, status
    FROM patients
    WHERE id = %s
      AND status = 'active'
"""
rows = db.execute_query(_SELECT_PATIENT, (patient_id,))
```

---

## 6. Error Handling Rules

- Every Lambda handler has exactly **one** `try/except HealthcarePlatformError` block
  and one `except Exception` fallback -- no other exception handling structure is permitted
- Never catch `Exception` in shared utilities -- let errors propagate up to the handler
  unless you are converting a library exception into a typed application exception
- Never silence exceptions with a bare `except: pass`
- The `except Exception` fallback at the handler level must: log at ERROR level, and
  return a generic 500 with no internal detail in the response body
- Never put PHI in exception messages -- exception messages may appear in stack traces

**BAD:**
```python
raise ValidationError(f"Email {email} is already registered")  # PHI in message
raise RecordNotFoundError(f"No patient found for {patient_id}")  # Redundant
```

**GOOD:**
```python
raise DuplicateRecordError("A patient with this email address is already registered")
raise RecordNotFoundError("Patient not found")
```

---

## 7. Import Order (enforced by flake8-isort)

```python
# 1. Standard library
import json
import os
import time
from datetime import date, datetime
from typing import Any

# 2. Third-party packages (blank line separator)
import bcrypt
import psycopg2

# 3. Internal modules (blank line separator)
from src.shared import db, response
from src.shared.exceptions import RecordNotFoundError, ValidationError
from src.shared.logger import get_logger
```

Never use wildcard imports (`from module import *`).
Never use relative imports outside of tests.

---

## 8. Type Hints

- Every function parameter and return value has a type hint -- no exceptions
- Use `X | None` syntax (Python 3.10+) instead of `Optional[X]`
- Use `dict[str, Any]` instead of `Dict[str, Any]` (built-in generics, Python 3.9+)
- Use `list[str]` instead of `List[str]`
- When a function accepts a Lambda event, annotate it as `dict[str, Any]`
- When a function accepts a Lambda context, annotate it as `Any` (the type is not importable)

---

## 9. Anti-Patterns -- Never Do These

### Never use `print()`
```python
# WRONG
print(f"Patient registered: {patient_id}")

# RIGHT
_logger.info("Patient registered", patient_id=patient_id)
```

### Never log PHI -- not even DEBUG
```python
# WRONG -- even in dev, even at DEBUG, even "temporarily"
_logger.debug("Validating email", email=body["email"])

# RIGHT -- log the operation, not the value
_logger.debug("Email validation passed")
```

### Never use mutable default arguments
```python
# WRONG
def get_secret(name: str, cache: dict = {}) -> dict:  # Shared across all calls

# RIGHT
def get_secret(name: str, cache: dict | None = None) -> dict:
    if cache is None:
        cache = {}
```

### Never use global variables except for module-level singleton state
```python
# WRONG
patient_count = 0
def increment():
    global patient_count  # Don't do this
    patient_count += 1

# RIGHT -- singletons like the DB pool are the only acceptable use of module-level state
_pool: psycopg2.pool.ThreadedConnectionPool | None = None
```

### Never format SQL with f-strings or .format()
```python
# WRONG -- SQL injection vector
query = f"SELECT * FROM patients WHERE id = '{patient_id}'"

# RIGHT
db.execute_query("SELECT * FROM patients WHERE id = %s", (patient_id,))
```

### Never return raw dicts from Lambda handlers
```python
# WRONG
return {"statusCode": 200, "body": json.dumps({"data": result})}

# RIGHT
return response.success(data=result)
```

### Never hard-code secrets or credentials
```python
# WRONG
DB_PASSWORD = "mysecretpassword"
API_KEY = "AIzaSyAbCdEfGh..."

# RIGHT -- fetch from Secrets Manager at runtime
creds = secrets.get_secret(os.environ["DB_SECRET_NAME"])
```

### Never catch broad exceptions in shared utilities
```python
# WRONG -- swallows real errors silently
try:
    return db.execute_query(query, params)
except Exception:
    return []

# RIGHT -- let it propagate; the handler will catch and log it
return db.execute_query(query, params)
```

### Never log query parameters
```python
# WRONG -- params may contain PHI
_logger.debug("Executing query", query=query, params=params)

# RIGHT -- log the template, never the bound values
_logger.debug("Executing query", query_template=query)
```

---

## 10. File Structure Template

Every new Lambda handler module must follow this exact top-to-bottom structure:

```
1. Module docstring (one line)
2. Standard library imports
3. (blank line)
4. Third-party imports
5. (blank line)
6. Internal imports
7. (blank line)
8. Module-level logger
9. (blank line)
10. SQL query constants (UPPER_SNAKE_CASE)
11. (blank line)
12. JSON Schema constants (if any)
13. (blank line)
14. Private helper functions (prefixed with _)
15. (blank line)
16. Public handler() function
```

---

## 11. Logging Standards

### Field naming in log calls
All log fields use `snake_case`. Field names must be consistent across all functions
so CloudWatch Logs Insights queries work the same way everywhere.

**Reserved standard fields (managed by the logger -- do not pass these as kwargs):**
`timestamp`, `level`, `service`, `stage`, `function_name`, `request_id`, `logger`

**Standard optional fields (use these exact names when logging these concepts):**
| Field | Type | When to use |
|---|---|---|
| `patient_id` | `str` (UUID) | When the operation is patient-scoped |
| `appointment_id` | `str` (UUID) | When the operation is appointment-scoped |
| `note_id` | `str` (UUID) | When a note was created |
| `prescription_id` | `str` (UUID) | When the operation is prescription-scoped |
| `duration_ms` | `float` | Always -- handler and query timings |
| `error_code` | `str` | When logging a caught HealthcarePlatformError |
| `count` | `int` | Result set size |
| `filter` | `str` | Active query filter value |
| `query_template` | `str` | SQL template (never params) |
| `cache_key` | `str` | Cache key hash (never the raw topic) |
| `result_count` | `int` | External API result count |
| `http_status` | `int` | External API HTTP status codes |
| `topic` | `str` | YouTube search topic (condition name only -- not patient-linked) |

### What to log at each level
- `DEBUG`: internal decision points, cache hits/misses, query templates, pool events
- `INFO`: request received, record created/retrieved, response dispatched with count/duration
- `WARNING`: known error paths (validation fail, not found, duplicate, forbidden)
- `ERROR`: unexpected exceptions that were caught at the handler fallback
- `CRITICAL`: infrastructure failures (pool exhausted, Secrets Manager down)
