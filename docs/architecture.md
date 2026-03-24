# Architecture Diagram -- Healthcare Platform

## Request Flow

```mermaid
flowchart TD
    Client([Client App])
    APIGW[API Gateway\nHTTP API v2]

    subgraph VPC [Private VPC -- 10.0.0.0/16]
        subgraph Lambda [Lambda Functions -- Private Subnets]
            L1[patient-register\n256MB - 10s]
            L2[appointments-upcoming\n256MB - 15s - PC:1]
            L3[appointment-notes\n256MB - 15s - PC:1]
            L4[prescription-list\n256MB - 15s - PC:1]
            L5[education-videos\n512MB - 20s - PC:1]
        end

        PROXY[RDS Proxy\nPostgreSQL\nConnection Pool]
        RDS[(RDS PostgreSQL 16\ndb.t4g.micro\nPrivate Only)]
    end

    SM[AWS Secrets Manager\nDB Credentials\nYouTube API Key]
    CW[CloudWatch Logs\nStructured JSON\n30-day retention]
    YT[YouTube Data API v3\nExternal]
    ALARM[CloudWatch Alarms\nError Rate\nPHI Leak Detection]

    Client -->|HTTPS| APIGW
    APIGW --> L1
    APIGW --> L2
    APIGW --> L3
    APIGW --> L4
    APIGW --> L5

    L1 -->|psycopg2 SSL| PROXY
    L2 -->|psycopg2 SSL| PROXY
    L3 -->|psycopg2 SSL| PROXY
    L4 -->|psycopg2 SSL| PROXY
    L5 -->|psycopg2 SSL| PROXY
    PROXY -->|Multiplexed SSL| RDS

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

> PC:1 = Provisioned Concurrency 1 (1 warm container always running)

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
