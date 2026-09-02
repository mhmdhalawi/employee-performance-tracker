CREATE TABLE submissions (
    id TEXT PRIMARY KEY,
    received_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('pending', 'completed', 'failed')),
    request_sha256 TEXT NOT NULL,
    schema_fingerprint TEXT NOT NULL,
    table_count INTEGER NOT NULL CHECK (table_count > 0),
    row_count INTEGER NOT NULL CHECK (row_count > 0),
    request_json TEXT NOT NULL,
    error_message TEXT
);

CREATE INDEX submissions_received_at_idx
    ON submissions(received_at DESC);

CREATE INDEX submissions_request_sha256_idx
    ON submissions(request_sha256);

CREATE TABLE mapping_plans (
    schema_fingerprint TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    plan_json TEXT NOT NULL
);

CREATE TABLE analysis_runs (
    analysis_id TEXT PRIMARY KEY,
    submission_id TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    coverage_start TEXT,
    coverage_end TEXT,
    model TEXT NOT NULL,
    total_tokens INTEGER NOT NULL CHECK (total_tokens >= 0),
    model_requests INTEGER NOT NULL CHECK (model_requests >= 0),
    mapping_cache_hit INTEGER NOT NULL CHECK (mapping_cache_hit IN (0, 1)),
    response_json TEXT NOT NULL,
    FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE CASCADE
);

CREATE INDEX analysis_runs_created_at_idx
    ON analysis_runs(created_at DESC);
