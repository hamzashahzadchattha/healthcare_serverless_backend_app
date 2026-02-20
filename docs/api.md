# API Reference -- Healthcare Platform

Base URL: `https://<api-id>.execute-api.us-east-1.amazonaws.com`

All endpoints that modify or read patient data require a valid JWT in the
`Authorization: Bearer <token>` header. The registration endpoint is public.

All responses follow this envelope:

**Success:**
```json
{ "success": true, "data": { ... }, "meta": { ... } }
```

**Error:**
```json
{ "success": false, "error": { "code": "ERROR_CODE", "message": "Human-readable description" } }
```

---

## POST /patients/register

Creates a new patient account. Sensitive fields are hashed before storage.

**Auth:** None required

**Request body:**
| Field | Type | Required | Rules |
|---|---|---|---|
| `first_name` | string | Yes | 1-100 chars |
| `last_name` | string | Yes | 1-100 chars |
| `dob` | string | Yes | `YYYY-MM-DD`, must be past date |
| `email` | string | Yes | Valid email, max 254 chars |
| `phone` | string | Yes | E.164 format e.g. `+12025551234` |

**Success response** `201 Created`:
```json
{
  "success": true,
  "data": {
    "patient_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "active"
  }
}
```

**Error codes:**
| Code | HTTP | Condition |
|---|---|---|
| `VALIDATION_ERROR` | 400 | Missing field, invalid format, future DOB |
| `DUPLICATE_RECORD` | 409 | Email already registered |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

---

## GET /patients/{patient_id}/appointments/upcoming

Returns all upcoming scheduled appointments for a patient.

**Auth:** Bearer JWT required

**Path parameters:**
| Parameter | Type | Description |
|---|---|---|
| `patient_id` | UUID | Patient's unique identifier |

**Success response** `200 OK`:
```json
{
  "success": true,
  "data": {
    "appointments": [
      {
        "appointment_id": "uuid",
        "provider": {
          "provider_id": "uuid",
          "full_name": "Dr. Jane Smith",
          "specialty": "Cardiology"
        },
        "scheduled_at": "2025-08-15T14:30:00+00:00",
        "duration_minutes": 30,
        "appointment_type": "in_person",
        "status": "scheduled"
      }
    ],
    "total": 1
  }
}
```

**Error codes:**
| Code | HTTP | Condition |
|---|---|---|
| `VALIDATION_ERROR` | 400 | Invalid UUID format |
| `UNAUTHORIZED` | 401 | Missing or invalid JWT |
| `NOT_FOUND` | 404 | Patient does not exist |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

---

## POST /appointments/{appointment_id}/notes

Uploads a post-appointment clinical note. Only the provider assigned to the
appointment may add notes. Appointment must be in `completed` status.

**Auth:** Bearer JWT required

**Path parameters:**
| Parameter | Type | Description |
|---|---|---|
| `appointment_id` | UUID | Appointment's unique identifier |

**Request body:**
| Field | Type | Required | Rules |
|---|---|---|---|
| `provider_id` | UUID | Yes | Must match the appointment's provider |
| `note_text` | string | Yes | 1-10,000 characters |

**Success response** `201 Created`:
```json
{
  "success": true,
  "data": {
    "note_id": "uuid",
    "appointment_id": "uuid",
    "created_at": "2025-08-15T16:45:00+00:00"
  }
}
```

**Error codes:**
| Code | HTTP | Condition |
|---|---|---|
| `VALIDATION_ERROR` | 400 | Invalid input or appointment not completed |
| `UNAUTHORIZED` | 401 | Missing or invalid JWT |
| `FORBIDDEN` | 403 | Provider ID does not match appointment |
| `NOT_FOUND` | 404 | Appointment does not exist |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

---

## GET /patients/{patient_id}/prescriptions

Lists prescriptions for a patient with an optional status filter.

**Auth:** Bearer JWT required

**Path parameters:**
| Parameter | Type | Description |
|---|---|---|
| `patient_id` | UUID | Patient's unique identifier |

**Query parameters:**
| Parameter | Type | Default | Values |
|---|---|---|---|
| `filter` | string | `active` | `active`, `past`, `all` |

**Success response** `200 OK`:
```json
{
  "success": true,
  "data": {
    "prescriptions": [
      {
        "prescription_id": "uuid",
        "medication_name": "Metformin",
        "dosage": "500mg",
        "frequency": "twice daily",
        "start_date": "2025-01-01",
        "end_date": null,
        "status": "active",
        "prescribed_by": {
          "provider_id": "uuid",
          "full_name": "Dr. Jane Smith"
        }
      }
    ],
    "total": 1
  },
  "meta": { "filter": "active" }
}
```

**Error codes:**
| Code | HTTP | Condition |
|---|---|---|
| `VALIDATION_ERROR` | 400 | Invalid UUID or unknown filter value |
| `UNAUTHORIZED` | 401 | Missing or invalid JWT |
| `NOT_FOUND` | 404 | Patient does not exist |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

---

## GET /patients/{patient_id}/education-videos

Returns YouTube educational video recommendations based on the patient's
active medical conditions. Results are cached for 1 hour per condition.

**Auth:** Bearer JWT required

**Path parameters:**
| Parameter | Type | Description |
|---|---|---|
| `patient_id` | UUID | Patient's unique identifier |

**Success response** `200 OK`:
```json
{
  "success": true,
  "data": {
    "videos": [
      {
        "video_id": "dQw4w9WgXcQ",
        "title": "Understanding Type 2 Diabetes",
        "description": "A comprehensive overview of type 2 diabetes management...",
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "topic": "Type 2 Diabetes"
      }
    ],
    "total": 3
  }
}
```

**Error codes:**
| Code | HTTP | Condition |
|---|---|---|
| `VALIDATION_ERROR` | 400 | Invalid UUID format |
| `UNAUTHORIZED` | 401 | Missing or invalid JWT |
| `NOT_FOUND` | 404 | Patient does not exist |
| `EXTERNAL_SERVICE_ERROR` | 502 | YouTube API unavailable |
| `RATE_LIMIT_EXCEEDED` | 429 | YouTube API quota exhausted |
| `INTERNAL_ERROR` | 500 | Unexpected server error |
