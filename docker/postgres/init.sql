-- Pipeline events sink table
CREATE TABLE IF NOT EXISTS events (
    id          BIGSERIAL PRIMARY KEY,
    event_id    VARCHAR(20)    NOT NULL,
    event_time  TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    sensor_id   VARCHAR(20),
    temperature DOUBLE PRECISION,
    pressure    DOUBLE PRECISION,
    status      VARCHAR(20),
    value       DOUBLE PRECISION,
    created_at  TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_events_event_time ON events (event_time DESC);
CREATE INDEX IF NOT EXISTS idx_events_sensor_id  ON events (sensor_id);

-- Incident log table (used by agents)
CREATE TABLE IF NOT EXISTS incidents (
    incident_id     VARCHAR(50)  PRIMARY KEY,
    service         VARCHAR(50),
    severity        VARCHAR(20),
    category        VARCHAR(50),
    root_cause      TEXT,
    impact          TEXT,
    solution        TEXT,
    solution_source VARCHAR(10),
    approval_status VARCHAR(20)  DEFAULT 'pending',
    remediation_status VARCHAR(20),
    validation_status  VARCHAR(20),
    escalated       BOOLEAN      DEFAULT FALSE,
    detected_at     TIMESTAMPTZ,
    resolved_at     TIMESTAMPTZ,
    report_path     VARCHAR(255),
    created_at      TIMESTAMPTZ  DEFAULT NOW()
);
