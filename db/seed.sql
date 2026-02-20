-- db/seed.sql
-- Healthcare Platform — Synthetic dev seed data
-- All data is fictional. PII hash values are bcrypt hashes of fake data.
-- Run after schema.sql: psql -h <rds-endpoint> -U healthcare_admin -d healthcare_dev -f db/seed.sql

-- Fixed UUIDs for deterministic references across tables
-- Providers
INSERT INTO providers (id, first_name, last_name, specialty, license_number) VALUES
    ('a1b2c3d4-0001-4000-8000-000000000001', 'Sarah', 'Smith', 'Internal Medicine', 'MD-2024-00101'),
    ('a1b2c3d4-0001-4000-8000-000000000002', 'James', 'Johnson', 'Cardiology', 'MD-2024-00202')
ON CONFLICT DO NOTHING;

-- Patients (hash values are bcrypt of synthetic data, not real PII)
-- Patient 1: "Jane Doe", DOB 1985-03-15, email jane.doe@example.com, phone +15551234567
-- Patient 2: "John Roe", DOB 1990-07-22, email john.roe@example.com, phone +15559876543
-- Patient 3: "Alice Test", DOB 1978-11-30, email alice.test@example.com, phone +15555550100
INSERT INTO patients (id, first_name, last_name, dob_hash, email_hash, email_sha256, phone_hash) VALUES
    ('b2c3d4e5-0001-4000-8000-000000000001', 'Jane', 'Doe',
     '$2b$12$LJ3m4ys1Hv7kXqZp9vMHNOqNx4yvGh1K2lQwE3rT5uI7oP0sA6bCe',
     '$2b$12$Kx9yRtG4hN2wA5sD8fJ7eO1mI3uQ6vB0cL4pZ9kW2jE5nH8rT0gMa',
     '86e0b9e56c17cc4d12387e1949b85053fbe73bc3ce5a1188713a9d300cc6133d',
     '$2b$12$Mn7oP0qR3sT5uV8wX1yZ2aB4cD6eF9gH0iJ2kL4mN6oP8qR0sT2u'),
    ('b2c3d4e5-0001-4000-8000-000000000002', 'John', 'Roe',
     '$2b$12$Qw3eR5tY7uI9oP1aS3dF5gH7jK9lZ1xC3vB5nM7qW9eR1tY3uI5o',
     '$2b$12$Az1sX3cD5fV7gB9hN1jM3kL5oP7qR9sT1uV3wX5yZ7aB9cD1eF3g',
     'b080fc583aa933c11e020921a81f8723b91e98f78ddf5d77a236d98d064f30aa',
     '$2b$12$Hy6jU8kI0oL2pM4nQ6rS8tU0vW2xY4zA6bC8dE0fG2hI4jK6lM8n'),
    ('b2c3d4e5-0001-4000-8000-000000000003', 'Alice', 'Test',
     '$2b$12$Wq1wE3rT5yU7iO9pA1sD3fG5hJ7kL9zX1cV3bN5mQ7wE9rT1yU3i',
     '$2b$12$Pl0oK9iJ8uH7yG6tF5rD4eS3wA2qZ1xC0vB9nM8lK7jH6gF5dS4a',
     'b106de6ba50cec6d415155690572a8c84b992ae2fc1bb71f2f9d0e8d0c1dc288',
     '$2b$12$Ty5rE4wQ3aS2dF1gH0jK9lP8oI7uY6tR5eW4qA3sD2fG1hJ0kL9p')
ON CONFLICT DO NOTHING;

-- Appointments (mix of past completed and future scheduled)
INSERT INTO appointments (id, patient_id, provider_id, scheduled_at, duration_minutes, status, appointment_type) VALUES
    ('c3d4e5f6-0001-4000-8000-000000000001',
     'b2c3d4e5-0001-4000-8000-000000000001',
     'a1b2c3d4-0001-4000-8000-000000000001',
     NOW() - INTERVAL '7 days', 30, 'completed', 'in_person'),
    ('c3d4e5f6-0001-4000-8000-000000000002',
     'b2c3d4e5-0001-4000-8000-000000000001',
     'a1b2c3d4-0001-4000-8000-000000000002',
     NOW() + INTERVAL '3 days', 45, 'scheduled', 'telehealth'),
    ('c3d4e5f6-0001-4000-8000-000000000003',
     'b2c3d4e5-0001-4000-8000-000000000002',
     'a1b2c3d4-0001-4000-8000-000000000001',
     NOW() + INTERVAL '5 days', 30, 'scheduled', 'in_person'),
    ('c3d4e5f6-0001-4000-8000-000000000004',
     'b2c3d4e5-0001-4000-8000-000000000002',
     'a1b2c3d4-0001-4000-8000-000000000002',
     NOW() - INTERVAL '14 days', 60, 'completed', 'in_person'),
    ('c3d4e5f6-0001-4000-8000-000000000005',
     'b2c3d4e5-0001-4000-8000-000000000003',
     'a1b2c3d4-0001-4000-8000-000000000001',
     NOW() + INTERVAL '10 days', 30, 'scheduled', 'telehealth')
ON CONFLICT DO NOTHING;

-- Appointment notes (only for completed appointments)
INSERT INTO appointment_notes (id, appointment_id, provider_id, note_text) VALUES
    ('d4e5f6a7-0001-4000-8000-000000000001',
     'c3d4e5f6-0001-4000-8000-000000000001',
     'a1b2c3d4-0001-4000-8000-000000000001',
     'Patient presented with mild hypertension. Recommended dietary changes and follow-up in 3 months.'),
    ('d4e5f6a7-0001-4000-8000-000000000002',
     'c3d4e5f6-0001-4000-8000-000000000004',
     'a1b2c3d4-0001-4000-8000-000000000002',
     'Annual cardiac screening completed. ECG within normal limits. Cholesterol slightly elevated.'),
    ('d4e5f6a7-0001-4000-8000-000000000003',
     'c3d4e5f6-0001-4000-8000-000000000004',
     'a1b2c3d4-0001-4000-8000-000000000002',
     'Follow-up note: prescribed statin therapy pending lab results confirmation.')
ON CONFLICT DO NOTHING;

-- Prescriptions (mix of active and completed)
INSERT INTO prescriptions (id, patient_id, provider_id, medication_name, dosage, frequency, start_date, end_date, status, notes) VALUES
    ('e5f6a7b8-0001-4000-8000-000000000001',
     'b2c3d4e5-0001-4000-8000-000000000001',
     'a1b2c3d4-0001-4000-8000-000000000001',
     'Lisinopril', '10mg', 'Once daily', CURRENT_DATE - INTERVAL '30 days', NULL, 'active',
     'For mild hypertension management'),
    ('e5f6a7b8-0001-4000-8000-000000000002',
     'b2c3d4e5-0001-4000-8000-000000000001',
     'a1b2c3d4-0001-4000-8000-000000000001',
     'Amoxicillin', '500mg', 'Three times daily', CURRENT_DATE - INTERVAL '21 days',
     CURRENT_DATE - INTERVAL '11 days', 'completed',
     'For upper respiratory infection'),
    ('e5f6a7b8-0001-4000-8000-000000000003',
     'b2c3d4e5-0001-4000-8000-000000000002',
     'a1b2c3d4-0001-4000-8000-000000000002',
     'Atorvastatin', '20mg', 'Once daily at bedtime', CURRENT_DATE - INTERVAL '14 days', NULL, 'active',
     'For elevated LDL cholesterol'),
    ('e5f6a7b8-0001-4000-8000-000000000004',
     'b2c3d4e5-0001-4000-8000-000000000003',
     'a1b2c3d4-0001-4000-8000-000000000001',
     'Metformin', '500mg', 'Twice daily with meals', CURRENT_DATE - INTERVAL '60 days', NULL, 'active',
     'For type 2 diabetes management')
ON CONFLICT DO NOTHING;

-- Patient conditions (drive education video recommendations)
INSERT INTO patient_conditions (id, patient_id, condition_name, icd10_code, diagnosed_at, status) VALUES
    ('f6a7b8c9-0001-4000-8000-000000000001',
     'b2c3d4e5-0001-4000-8000-000000000001',
     'Essential Hypertension', 'I10', CURRENT_DATE - INTERVAL '30 days', 'chronic'),
    ('f6a7b8c9-0001-4000-8000-000000000002',
     'b2c3d4e5-0001-4000-8000-000000000002',
     'Hyperlipidemia', 'E78.5', CURRENT_DATE - INTERVAL '14 days', 'active'),
    ('f6a7b8c9-0001-4000-8000-000000000003',
     'b2c3d4e5-0001-4000-8000-000000000003',
     'Type 2 Diabetes Mellitus', 'E11.9', CURRENT_DATE - INTERVAL '60 days', 'chronic'),
    ('f6a7b8c9-0001-4000-8000-000000000004',
     'b2c3d4e5-0001-4000-8000-000000000001',
     'Upper Respiratory Infection', 'J06.9', CURRENT_DATE - INTERVAL '21 days', 'resolved')
ON CONFLICT  DO NOTHING;

-- Massive data seed for Patient 1 pagination testing
DO $$
DECLARE
    i INT;
BEGIN
    FOR i IN 1..100 LOOP
        INSERT INTO appointments (id, patient_id, provider_id, scheduled_at, duration_minutes, status, appointment_type)
        VALUES (
            gen_random_uuid(),
            'b2c3d4e5-0001-4000-8000-000000000001',
            'a1b2c3d4-0001-4000-8000-000000000001',
            NOW() + (i || ' days')::INTERVAL,
            30,
            'scheduled',
            'in_person'
        );
        
        INSERT INTO prescriptions (id, patient_id, provider_id, medication_name, dosage, frequency, start_date, status, notes)
        VALUES (
            gen_random_uuid(),
            'b2c3d4e5-0001-4000-8000-000000000001',
            'a1b2c3d4-0001-4000-8000-000000000001',
            'Medication Pagination Demo ' || i,
            '10mg',
            'Once daily',
            CURRENT_DATE - (i || ' days')::INTERVAL,
            'active',
            'Auto-generated for testing UI tables limit and offset pages'
        );
    END LOOP;
END $$;
