-- ============================================================
--  CaaS COE Compliance Module  --  PostgreSQL Schema
--  Database: caas_dashboard  |  Port: 5433
--  3-month rolling window, monthly range partitions
--  Best Practice: ISO 27001, CIS Benchmarks, VMware HCL
-- ============================================================

-- ── Extensions ───────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- fast text search

-- ============================================================
--  1. SCAN RUNS  (one row per compliance scan execution)
-- ============================================================
CREATE TABLE IF NOT EXISTS compliance_scans (
    id              BIGSERIAL PRIMARY KEY,
    scanned_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    scan_date       DATE        NOT NULL DEFAULT CURRENT_DATE,
    triggered_by    TEXT        NOT NULL DEFAULT 'scheduler',  -- scheduler | manual | <username>
    status          TEXT        NOT NULL DEFAULT 'running',    -- running | completed | failed
    total_assets    INT         DEFAULT 0,
    compliant       INT         DEFAULT 0,
    warning         INT         DEFAULT 0,
    non_compliant   INT         DEFAULT 0,
    duration_sec    NUMERIC(8,2),
    error_msg       TEXT,
    UNIQUE(scan_date, triggered_by)
);
CREATE INDEX IF NOT EXISTS idx_compliance_scans_date ON compliance_scans(scan_date DESC);

-- ============================================================
--  2. ASSETS REGISTRY  (deduplicated asset catalogue)
-- ============================================================
CREATE TABLE IF NOT EXISTS compliance_assets (
    id              BIGSERIAL PRIMARY KEY,
    asset_key       TEXT        NOT NULL UNIQUE,   -- md5(hostname+ip+type)
    hostname        TEXT        NOT NULL,
    ip_address      TEXT,
    os_name         TEXT,
    os_version      TEXT,
    os_family       TEXT,                          -- windows | linux | other
    asset_type      TEXT        NOT NULL DEFAULT 'vm',   -- vm | baremetal
    vcenter         TEXT,
    cluster         TEXT,
    hypervisor_host TEXT,
    datastore       TEXT,
    vm_id           TEXT,                          -- moref / CMDB CI id
    cpu_count       INT,
    memory_gb       NUMERIC(8,2),
    disk_gb         NUMERIC(10,2),
    power_state     TEXT,
    tools_version   TEXT,
    tools_status    TEXT,
    hw_version      TEXT,
    environment     TEXT,                          -- prod | nonprod | dev
    owner_team      TEXT,
    first_seen      DATE        NOT NULL DEFAULT CURRENT_DATE,
    last_seen       DATE        NOT NULL DEFAULT CURRENT_DATE,
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE
);
CREATE INDEX IF NOT EXISTS idx_compliance_assets_hostname ON compliance_assets(hostname);
CREATE INDEX IF NOT EXISTS idx_compliance_assets_vcenter  ON compliance_assets(vcenter);
CREATE INDEX IF NOT EXISTS idx_compliance_assets_type     ON compliance_assets(asset_type);
CREATE INDEX IF NOT EXISTS idx_compliance_assets_os       ON compliance_assets(os_family);

-- ============================================================
--  3. COMPLIANCE RESULTS  (daily score per asset)
--     Partitioned by month for 3-month retention
-- ============================================================
CREATE TABLE IF NOT EXISTS compliance_results (
    id              BIGSERIAL,
    scan_id         BIGINT      NOT NULL REFERENCES compliance_scans(id) ON DELETE CASCADE,
    asset_id        BIGINT      NOT NULL REFERENCES compliance_assets(id) ON DELETE CASCADE,
    scanned_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    score           INT         NOT NULL CHECK (score BETWEEN 0 AND 100),
    status          TEXT        NOT NULL,           -- compliant | warning | non_compliant
    -- individual rule results stored as JSONB for flexibility
    checks          JSONB       NOT NULL DEFAULT '[]',
    -- quick lookup columns (denormalized from checks for fast filtering)
    patch_age_days  INT,
    tools_ok        BOOLEAN,
    hw_version_ok   BOOLEAN,
    snapshot_ok     BOOLEAN,
    eol_os          BOOLEAN     DEFAULT FALSE,
    missing_patches INT         DEFAULT 0,
    PRIMARY KEY (id, scanned_at)
) PARTITION BY RANGE (scanned_at);

-- Monthly partitions — current 3 months + 1 future
DO $$
DECLARE
    m DATE;
    part_name TEXT;
    start_ts  TEXT;
    end_ts    TEXT;
BEGIN
    FOR i IN -3..1 LOOP
        m         := date_trunc('month', NOW()) + (i || ' months')::interval;
        part_name := 'compliance_results_' || to_char(m, 'YYYY_MM');
        start_ts  := to_char(m,                  'YYYY-MM-DD');
        end_ts    := to_char(m + interval '1 month', 'YYYY-MM-DD');
        IF NOT EXISTS (
            SELECT 1 FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relname = part_name AND n.nspname = 'public'
        ) THEN
            EXECUTE format(
                'CREATE TABLE %I PARTITION OF compliance_results FOR VALUES FROM (%L) TO (%L)',
                part_name, start_ts, end_ts
            );
            RAISE NOTICE 'Created partition %', part_name;
        END IF;
    END LOOP;
END $$;

CREATE INDEX IF NOT EXISTS idx_comp_results_asset   ON compliance_results(asset_id, scanned_at DESC);
CREATE INDEX IF NOT EXISTS idx_comp_results_scan    ON compliance_results(scan_id);
CREATE INDEX IF NOT EXISTS idx_comp_results_status  ON compliance_results(status, scanned_at DESC);
CREATE INDEX IF NOT EXISTS idx_comp_results_score   ON compliance_results(score, scanned_at DESC);

-- ============================================================
--  4. REMEDIATIONS  (task tracker per asset)
-- ============================================================
CREATE TABLE IF NOT EXISTS compliance_remediations (
    id              BIGSERIAL PRIMARY KEY,
    asset_id        BIGINT      NOT NULL REFERENCES compliance_assets(id) ON DELETE CASCADE,
    result_id       BIGINT,
    check_name      TEXT        NOT NULL,           -- which rule failed
    action          TEXT        NOT NULL,           -- description of remediation
    priority        TEXT        NOT NULL DEFAULT 'medium',  -- critical | high | medium | low
    status          TEXT        NOT NULL DEFAULT 'open',    -- open | in_progress | resolved | dismissed
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      TEXT        NOT NULL DEFAULT 'system',
    updated_at      TIMESTAMPTZ,
    resolved_at     TIMESTAMPTZ,
    resolved_by     TEXT,
    notes           TEXT
);
CREATE INDEX IF NOT EXISTS idx_comp_remediations_asset  ON compliance_remediations(asset_id);
CREATE INDEX IF NOT EXISTS idx_comp_remediations_status ON compliance_remediations(status, created_at DESC);

-- ============================================================
--  5. COMPLIANCE TREND DAILY SUMMARY  (pre-aggregated for charts)
-- ============================================================
CREATE TABLE IF NOT EXISTS compliance_trend (
    trend_date      DATE        PRIMARY KEY,
    total_assets    INT         DEFAULT 0,
    compliant       INT         DEFAULT 0,
    warning         INT         DEFAULT 0,
    non_compliant   INT         DEFAULT 0,
    avg_score       NUMERIC(5,2),
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
--  6. AUTO-ROTATE PARTITIONS  (function + scheduled call)
--     Call compliance_rotate_partitions() monthly
-- ============================================================
CREATE OR REPLACE FUNCTION compliance_rotate_partitions()
RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    future_m  DATE;
    old_m     DATE;
    new_part  TEXT;
    old_part  TEXT;
    s         TEXT;
    e         TEXT;
BEGIN
    -- Create next month's partition
    future_m  := date_trunc('month', NOW()) + interval '2 months';
    new_part  := 'compliance_results_' || to_char(future_m, 'YYYY_MM');
    s         := to_char(future_m, 'YYYY-MM-DD');
    e         := to_char(future_m + interval '1 month', 'YYYY-MM-DD');
    IF NOT EXISTS (
        SELECT 1 FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname = new_part
    ) THEN
        EXECUTE format(
            'CREATE TABLE %I PARTITION OF compliance_results FOR VALUES FROM (%L) TO (%L)',
            new_part, s, e
        );
        RAISE NOTICE 'Created future partition %', new_part;
    END IF;

    -- Drop partition older than 4 months (keep ~3 months of data)
    old_m    := date_trunc('month', NOW()) - interval '4 months';
    old_part := 'compliance_results_' || to_char(old_m, 'YYYY_MM');
    IF EXISTS (
        SELECT 1 FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname = old_part
    ) THEN
        EXECUTE format('DROP TABLE %I', old_part);
        RAISE NOTICE 'Dropped old partition %', old_part;
    END IF;
END $$;

-- Grant permissions to caas_app
GRANT SELECT, INSERT, UPDATE, DELETE ON compliance_scans        TO caas_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON compliance_assets       TO caas_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON compliance_results      TO caas_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON compliance_remediations TO caas_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON compliance_trend        TO caas_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public           TO caas_app;

\echo 'Compliance schema created successfully.'
