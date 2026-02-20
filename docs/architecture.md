# Architecture Diagram -- Healthcare Platform

## Request Flow

```mermaid
flowchart TD
    Client([Client App])
    APIGW[API Gateway\nHTTP API v2]
    JWT[JWT Authorizer\nCognito / Auth0]

    subgraph VPC [Private VPC -- 10.0.0.0/16]
        subgraph Lambda [Lambda Functions -- Private Subnets]
            L1[patient-register\n256MB - 10s]
            L2[appointments-upcoming\n256MB - 15s]
            L3[appointment-notes\n256MB - 15s]
            L4[prescription-list\n256MB - 15s]
            L5[education-videos\n512MB - 20s]
        end

        RDS[(RDS PostgreSQL 15\ndb.t3.micro\nFree Tier\nPrivate Only)]
    end

    SM[AWS Secrets Manager\nDB Credentials\nYouTube API Key]
    CW[CloudWatch Logs\nStructured JSON\n30-day retention]
    YT[YouTube Data API v3\nExternal]
    ALARM[CloudWatch Alarms\nError Rate\nPHI Leak Detection]

    Client -->|HTTPS| APIGW
    APIGW -->|JWT validation| JWT
    JWT -->|Verified| APIGW
    APIGW --> L1
    APIGW --> L2
    APIGW --> L3
    APIGW --> L4
    APIGW --> L5

    L1 -->|psycopg2 SSL| RDS
    L2 -->|psycopg2 SSL| RDS
    L3 -->|psycopg2 SSL| RDS
    L4 -->|psycopg2 SSL| RDS
    L5 -->|psycopg2 SSL| RDS

    L1 -->|GetSecretValue| SM
    L2 -->|GetSecretValue| SM
    L3 -->|GetSecretValue| SM
    L4 -->|GetSecretValue| SM
    L5 -->|GetSecretValue| SM

    L5 -->|search.list| YT

    L1 -->|Structured JSON| CW
    L2 -->|Structured JSON| CW
    L3 -->|Structured JSON| CW
    L4 -->|Structured JSON| CW
    L5 -->|Structured JSON| CW

    CW -->|Metric Filters| ALARM
```

## PHI Data Flow

```mermaid
flowchart LR
    Input([Raw Request\nfirst_name, last_name\ndob, email, phone])
    Validator[Request Validator\njsonschema]
    Hasher[bcrypt Hasher\nrounds=12]
    DB[(PostgreSQL\nStores hashes only\nNo plaintext PII)]
    Logger[PHI-Safe Logger\nKey + Value scrubbing]
    CW[CloudWatch\nNo PHI ever]
    Response([API Response\npatient_id + status only])

    Input --> Validator
    Validator -->|Valid schema| Hasher
    Hasher -->|dob_hash, email_hash\nemail_sha256, phone_hash| DB
    DB -->|id, status| Response
    Validator -->|Metadata only| Logger
    Logger -->|Flat JSON, PHI stripped| CW
```

## Security Layers

| Layer | Control |
|---|---|
| Network | RDS in private subnet -- no public access |
| Transport | SSL required on all RDS connections |
| Authentication | JWT on all routes except POST /patients/register |
| Authorisation | Per-function IAM roles -- least privilege |
| Secrets | All credentials in Secrets Manager -- never in env vars or code |
| Data at rest | RDS storage encryption enabled |
| Logging | PHI scrubbed by key name AND value pattern before CloudWatch |
| Monitoring | CloudWatch Alarms on error rate and PHI leak attempts |
