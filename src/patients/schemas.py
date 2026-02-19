"""JSON Schema definitions for patient registration endpoints."""

PATIENT_REGISTER_SCHEMA: dict = {
    "type": "object",
    "required": ["first_name", "last_name", "dob", "email", "phone"],
    "additionalProperties": False,
    "properties": {
        "first_name": {
            "type": "string",
            "minLength": 1,
            "maxLength": 100,
        },
        "last_name": {
            "type": "string",
            "minLength": 1,
            "maxLength": 100,
        },
        "dob": {
            "type": "string",
            "pattern": r"^\d{4}-\d{2}-\d{2}$",
            "description": "Date of birth in YYYY-MM-DD format",
        },
        "email": {
            "type": "string",
            "format": "email",
            "maxLength": 254,
        },
        "phone": {
            "type": "string",
            "pattern": r"^\+?[1-9]\d{7,14}$",
            "description": "E.164 phone number",
        },
    },
}
