# Technical Explanation -- Healthcare Platform Backend

## Overview

The healthcare platform backend is a serverless, cloud-native system built on AWS.
It exposes five REST APIs over AWS API Gateway HTTP API (v2), backed by five AWS Lambda
functions written in Python 3.12, and persists data in Amazon RDS PostgreSQL 15.

All infrastructure is defined as code in a single `serverless.yml` file managed by the
Serverless Framework (serverless.com), enabling repeatable, stage-isolated deployments.

---

## API Design

**API 1 -- Patient Registration (POST /patients/register)**
Accepts patient demographics, validates the input against a JSON Schema, and stores only
non-reversible representations of sensitive fields. Date of birth, email, and phone are
hashed with bcrypt (12 rounds). Email additionally stores a SHA-256 digest to enable
a fast uniqueness check without the 200ms cost of bcrypt verification on every request.
The response contains only the new patient UUID and status -- no PII is echoed back.

**API 2 -- Upcoming Appointments (GET /patients/{patient_id}/appointments/upcoming)**
Joins the `appointments` and `providers` tables and returns scheduled future appointments
in ascending chronological order. Database credentials are fetched from AWS Secrets
Manager on the first warm invocation and cached in memory for subsequent calls.
Query execution time is measured and logged (template only -- no parameters are logged).

**API 3 -- Provider Notes (POST /appointments/{appointment_id}/notes)**
Allows a provider to upload a post-appointment clinical note. The handler verifies that
the appointment is in `completed` status and that the requesting provider matches the
appointment's provider before inserting. The note insert and the appointment's `updated_at`
update are executed in a single database transaction to guarantee consistency.
Note content is never logged under any circumstances.

**API 4 -- Prescription Listing (GET /patients/{patient_id}/prescriptions)**
Returns a patient's prescriptions filtered by status (`active`, `past`, or `all`).
The filter is applied at the SQL level rather than in application code to avoid fetching
unnecessary rows. Each prescription includes the prescribing provider's name for display.

**API 5 -- Education Videos (GET /patients/{patient_id}/education-videos)**
Fetches the patient's active conditions from the database, derives a search topic for each
condition (preferring ICD-10 codes for precision), and queries the YouTube Data API v3.
Results are cached in a module-level dict (keyed by SHA-256 of the topic) for one hour,
reducing YouTube API calls on repeated requests. The YouTube API key is stored in Secrets
Manager and never logged or exposed in responses.

---

## Error Handling Strategy

All errors are typed, subclassing `HealthcarePlatformError`. Each subclass carries an
HTTP status code and a machine-readable `error_code` string. Handlers contain one
`try/except HealthcarePlatformError` block that converts typed errors to structured HTTP
responses, and one `except Exception` fallback that logs at ERROR level and returns a
generic 500 without any internal detail. This prevents stack traces or internal system
information from reaching API consumers.

---

## Logging Strategy

All log output is structured JSON emitted to stdout. AWS Lambda automatically captures
stdout and forwards it to CloudWatch Logs. Every log line contains a flat set of
top-level fields: `timestamp`, `level`, `service`, `stage`, `function_name`,
`request_id`, and any operation-specific metadata.

PHI is protected by a two-layer scrubber that runs on every log call:
1. Key-based removal: any field with a key in the PHI blocklist is dropped entirely
2. Value-based redaction: any string value matching an email, phone, date, or SSN
   pattern is replaced with `[REDACTED]`

CloudWatch Metric Filters monitor log streams for ERROR/CRITICAL entries and for
`[REDACTED]` occurrences (indicating a PHI scrub triggered). CloudWatch Alarms fire
on threshold breaches, enabling operational and compliance alerting.

---

## Security Architecture

The RDS instance is in a private subnet with no public accessibility. Lambda functions
run in the same VPC and reach RDS over a private network connection using SSL. Secrets
Manager credentials are never stored as environment variables -- they are fetched at
runtime over the VPC internal network and cached for the container's lifetime.

Each Lambda function has its own IAM role granting only the permissions it needs:
CloudWatch log writes to its specific log group, Secrets Manager read access to the
specific secrets it uses, VPC networking, and X-Ray tracing. No role has wildcard
resource permissions except for the EC2 VPC networking actions which AWS requires.
