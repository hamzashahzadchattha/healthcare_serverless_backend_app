# Healthcare Platform

HIPAA-aligned, cloud-native healthcare backend built on AWS with Serverless Framework v3.

## Architecture

```
Client (HTTPS) --> API Gateway HTTP API (v2) --> Lambda Functions --> RDS PostgreSQL 15
                                                      |
                                                      +--> Secrets Manager (via VPC Endpoint)
                                                      +--> YouTube Data API v3 (education videos)
                                                      +--> CloudWatch Logs + X-Ray Tracing
```

All Lambda functions and RDS run inside a shared VPC with private subnets. The database is never publicly accessible. Secrets Manager is reached through a VPC Interface Endpoint (no NAT Gateway required). Each Lambda function has its own IAM role scoped to the minimum permissions it needs.

## Tech Stack

| Component           | Technology                        |
|---------------------|-----------------------------------|
| Runtime             | Python 3.12                       |
| IaC                 | Serverless Framework v3           |
| Compute             | AWS Lambda                        |
| Database            | Amazon RDS PostgreSQL 15          |
| API                 | AWS API Gateway HTTP API (v2)     |
| Secrets             | AWS Secrets Manager               |
| Observability       | CloudWatch Logs + AWS X-Ray       |
| Auth                | JWT (external IdP via API Gateway)|

## Prerequisites

- Node.js 18+ and npm (for Serverless Framework)
- Python 3.12
- Docker (for building Lambda-compatible Python packages)
- AWS CLI configured with appropriate credentials
- PostgreSQL 15 client (`psql`) for database bootstrapping

## Local Setup

```bash
# 1. Install Serverless Framework and plugins
npm install -g serverless@3
npm install

# 2. Install Python dependencies
pip install -r requirements.txt -r requirements-dev.txt

# 3. Create your environment file
cp .env.example .env.dev
# Edit .env.dev with your JWT issuer URL and audience

# 4. Bootstrap the database (after first deploy)
psql -h <rds-endpoint> -U healthcare_admin -d healthcare_dev -f db/schema.sql
psql -h <rds-endpoint> -U healthcare_admin -d healthcare_dev -f db/seed.sql
```

Note: RDS is inside a private VPC. Connect via an EC2 bastion host or AWS SSM Session Manager port forwarding.

## Deploy

```bash
npx serverless deploy --stage dev
npx serverless deploy --stage prod
```

## Run Tests

```bash
pytest tests/unit/ -v
pytest tests/unit/ -v --cov=src --cov-report=term-missing
```

## Environment Variables

| Variable              | Purpose                                    | Secret? |
|-----------------------|--------------------------------------------|---------|
| `STAGE`               | Deployment stage (dev/prod)                | No      |
| `REGION`              | AWS region                                 | No      |
| `DB_SECRET_NAME`      | Secrets Manager key for RDS credentials    | No      |
| `YOUTUBE_SECRET_NAME` | Secrets Manager key for YouTube API key    | No      |
| `SERVICE_NAME`        | Service identifier for log correlation     | No      |
| `FUNCTION_NAME`       | Lambda function name for log correlation   | No      |
| `LOG_LEVEL`           | Logging threshold (DEBUG/INFO/WARNING)     | No      |
| `CACHE_TTL_SECONDS`   | TTL for YouTube video cache (default 3600) | No      |

All sensitive values (database password, YouTube API key) are stored in AWS Secrets Manager and fetched at runtime. They never appear in environment variables or logs.

## API Reference

| Method | Path                                           | Auth | Description                                |
|--------|-------------------------------------------------|------|--------------------------------------------|
| POST   | `/patients/register`                            | No   | Register a new patient with hashed PII     |
| GET    | `/patients/{patient_id}/appointments/upcoming`  | JWT  | List upcoming scheduled appointments       |
| POST   | `/appointments/{appointment_id}/notes`          | JWT  | Upload provider notes for a completed appt |
| GET    | `/patients/{patient_id}/prescriptions`          | JWT  | List prescriptions (filter: active/past/all)|
| GET    | `/patients/{patient_id}/education-videos`       | JWT  | Get condition-based YouTube video recs     |

## PHI & Logging Policy

The structured JSON logger enforces a blocklist of 20+ PHI-sensitive field names (`email`, `phone`, `dob`, `ssn`, `note_text`, `medication_name`, `dosage`, etc.). Any log call passing a blocked key has that key silently removed before the log entry is written to CloudWatch. Patient IDs are truncated to 8 characters in error-level logs. Clinical note content is never written to logs at any level. API error responses never include stack traces or internal details beyond a machine-readable error code and a safe message.

## Project Structure

```
├── serverless.yml          # All AWS infrastructure (single source of truth)
├── db/
│   ├── schema.sql          # PostgreSQL DDL (run manually after first deploy)
│   └── seed.sql            # Synthetic dev data
├── src/
│   ├── shared/             # Response builder, DB pool, logger, validation, secrets, exceptions
│   ├── patients/           # Patient registration
│   ├── appointments/       # Upcoming appointments + provider notes
│   ├── prescriptions/      # Prescription listing
│   └── education/          # YouTube education videos + caching
└── tests/
    ├── unit/               # Per-handler and per-module unit tests
    └── integration/        # Database connectivity tests
```

## Security

- All Lambda functions have dedicated IAM roles (least privilege)
- PII fields (DOB, email, phone) are bcrypt-hashed before database storage
- Email uniqueness is checked via SHA-256 digest (fast) separate from bcrypt (slow)
- RDS is encrypted at rest, never publicly accessible
- Secrets are stored in AWS Secrets Manager, never in environment variables
- Clinical note content is never written to logs
- VPC Endpoint for Secrets Manager eliminates internet-bound traffic from Lambda
- Security headers (nosniff, DENY framing, no-store cache) on every response
