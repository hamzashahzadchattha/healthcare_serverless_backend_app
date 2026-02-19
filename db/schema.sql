-- db/schema.sql
-- Healthcare Platform — PostgreSQL 15 schema
-- Run once: psql -h <rds-endpoint> -U healthcare_admin -d healthcare_dev -f db/schema.sql
-- gen_random_uuid() is a core built-in since PostgreSQL 13 — no extension required

-- ─────────────────────────────────────────────────────────────────────────── --
-- Trigger function: auto-update updated_at on every UPDATE
-- ─────────────────────────────────────────────────────────────────────────── --
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ─────────────────────────────────────────────────────────────────────────── --
-- patients
-- PII columns store bcrypt hashes. first_name and last_name are stored as
-- plaintext for display — they are NOT considered high-risk PII in this model.
-- DOB, email, and phone are hashed because they are used for identity proofing.
-- ─────────────────────────────────────────────────────────────────────────── --
CREATE TABLE IF NOT EXISTS patients (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    first_name      TEXT            NOT NULL,
    last_name       TEXT            NOT NULL,
    dob_hash        TEXT            NOT NULL,
    email_hash      TEXT            NOT NULL UNIQUE,
    email_sha256    TEXT            NOT NULL UNIQUE,
    phone_hash      TEXT            NOT NULL,
    status          TEXT            NOT NULL DEFAULT 'active'
                                    CHECK (status IN ('active', 'inactive', 'deceased')),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_patients_status ON patients (status);
CREATE INDEX idx_patients_email_sha256 ON patients (email_sha256);

CREATE TRIGGER patients_updated_at
    BEFORE UPDATE ON patients
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ─────────────────────────────────────────────────────────────────────────── --
-- providers
-- ─────────────────────────────────────────────────────────────────────────── --
CREATE TABLE IF NOT EXISTS providers (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    first_name      TEXT            NOT NULL,
    last_name       TEXT            NOT NULL,
    specialty       TEXT            NOT NULL,
    license_number  TEXT            NOT NULL UNIQUE,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE TRIGGER providers_updated_at
    BEFORE UPDATE ON providers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ─────────────────────────────────────────────────────────────────────────── --
-- appointments
-- ─────────────────────────────────────────────────────────────────────────── --
CREATE TABLE IF NOT EXISTS appointments (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id      UUID            NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    provider_id     UUID            NOT NULL REFERENCES providers(id) ON DELETE RESTRICT,
    scheduled_at    TIMESTAMPTZ     NOT NULL,
    duration_minutes INT            NOT NULL DEFAULT 30 CHECK (duration_minutes > 0),
    status          TEXT            NOT NULL DEFAULT 'scheduled'
                                    CHECK (status IN ('scheduled', 'completed', 'cancelled', 'no_show')),
    appointment_type TEXT           NOT NULL DEFAULT 'in_person'
                                    CHECK (appointment_type IN ('in_person', 'telehealth')),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_appointments_patient_upcoming
    ON appointments (patient_id, scheduled_at)
    WHERE status = 'scheduled';

CREATE TRIGGER appointments_updated_at
    BEFORE UPDATE ON appointments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ─────────────────────────────────────────────────────────────────────────── --
-- appointment_notes
-- Notes are clinical data — store them but never log their content
-- ─────────────────────────────────────────────────────────────────────────── --
CREATE TABLE IF NOT EXISTS appointment_notes (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    appointment_id  UUID            NOT NULL REFERENCES appointments(id) ON DELETE RESTRICT,
    provider_id     UUID            NOT NULL REFERENCES providers(id) ON DELETE RESTRICT,
    note_text       TEXT            NOT NULL,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_notes_appointment_id ON appointment_notes (appointment_id);

CREATE TRIGGER appointment_notes_updated_at
    BEFORE UPDATE ON appointment_notes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ─────────────────────────────────────────────────────────────────────────── --
-- prescriptions
-- ─────────────────────────────────────────────────────────────────────────── --
CREATE TABLE IF NOT EXISTS prescriptions (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id      UUID            NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    provider_id     UUID            NOT NULL REFERENCES providers(id) ON DELETE RESTRICT,
    medication_name TEXT            NOT NULL,
    dosage          TEXT            NOT NULL,
    frequency       TEXT            NOT NULL,
    start_date      DATE            NOT NULL,
    end_date        DATE,
    status          TEXT            NOT NULL DEFAULT 'active'
                                    CHECK (status IN ('active', 'completed', 'cancelled')),
    notes           TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_prescriptions_patient_status ON prescriptions (patient_id, status);

CREATE TRIGGER prescriptions_updated_at
    BEFORE UPDATE ON prescriptions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ─────────────────────────────────────────────────────────────────────────── --
-- patient_conditions
-- Medical conditions drive YouTube video recommendations
-- ─────────────────────────────────────────────────────────────────────────── --
CREATE TABLE IF NOT EXISTS patient_conditions (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id      UUID            NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    condition_name  TEXT            NOT NULL,
    icd10_code      TEXT,
    diagnosed_at    DATE            NOT NULL,
    status          TEXT            NOT NULL DEFAULT 'active'
                                    CHECK (status IN ('active', 'resolved', 'chronic')),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_conditions_patient_id ON patient_conditions (patient_id);

CREATE TRIGGER patient_conditions_updated_at
    BEFORE UPDATE ON patient_conditions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
