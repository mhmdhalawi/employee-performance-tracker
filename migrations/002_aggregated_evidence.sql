ALTER TABLE submissions ADD COLUMN idempotency_key TEXT;

CREATE UNIQUE INDEX submissions_idempotency_key_idx
    ON submissions(idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE TABLE submission_plans (
    submission_id TEXT PRIMARY KEY,
    schema_fingerprint TEXT NOT NULL,
    plan_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE CASCADE
);

CREATE INDEX submission_plans_schema_fingerprint_idx
    ON submission_plans(schema_fingerprint);

CREATE TABLE canonical_records (
    record_type TEXT NOT NULL,
    record_id TEXT NOT NULL,
    employee_id TEXT NOT NULL,
    period_start TEXT,
    period_end TEXT,
    payload_json TEXT NOT NULL,
    source_version INTEGER,
    source_updated_at TEXT,
    source_submission_id TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (record_type, record_id),
    UNIQUE (record_type, record_id),
    FOREIGN KEY (source_submission_id) REFERENCES submissions(id)
);

CREATE INDEX canonical_records_employee_date_idx
    ON canonical_records(employee_id, period_start, period_end);

CREATE INDEX canonical_records_source_submission_idx
    ON canonical_records(source_submission_id);
