-- Gravity NIL Data Pipeline - PostgreSQL Schema
-- Production-grade schema with full auditability and provenance tracking

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- CORE ATHLETE TABLES
-- ============================================================================

CREATE TABLE athletes (
    athlete_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    canonical_name VARCHAR(255) NOT NULL,
    sport VARCHAR(50) NOT NULL,
    school VARCHAR(255),
    position VARCHAR(50),
    conference VARCHAR(100),
    jersey_number INTEGER,
    class_year VARCHAR(50), -- Freshman, Sophomore, Junior, Senior
    season_id VARCHAR(20), -- e.g., "2024-25"
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_athletes_name ON athletes(canonical_name);
CREATE INDEX idx_athletes_sport_school ON athletes(sport, school);
CREATE INDEX idx_athletes_season ON athletes(season_id);

-- ============================================================================
-- EVENT TRACKING (Time-series data)
-- ============================================================================

CREATE TABLE athlete_events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id UUID NOT NULL REFERENCES athletes(athlete_id),
    event_type VARCHAR(100) NOT NULL, -- 'social_post', 'news_mention', 'roster_change', 'nil_deal', etc.
    event_timestamp TIMESTAMP NOT NULL,
    source VARCHAR(100) NOT NULL,
    raw_data JSONB NOT NULL,
    processed BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_events_athlete ON athlete_events(athlete_id, event_timestamp DESC);
CREATE INDEX idx_events_type ON athlete_events(event_type);
CREATE INDEX idx_events_source ON athlete_events(source);
CREATE INDEX idx_events_processed ON athlete_events(processed) WHERE processed = false;

-- ============================================================================
-- RAW PAYLOAD STORAGE (Metadata for filesystem storage)
-- ============================================================================

CREATE TABLE raw_payloads (
    payload_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id UUID REFERENCES athletes(athlete_id),
    source VARCHAR(100) NOT NULL,
    payload_type VARCHAR(100) NOT NULL,
    file_path TEXT NOT NULL, -- Path to JSON file in filesystem/S3
    file_size_bytes INTEGER,
    checksum VARCHAR(64), -- SHA-256 hash for integrity
    fetched_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_payloads_athlete ON raw_payloads(athlete_id);
CREATE INDEX idx_payloads_source ON raw_payloads(source);
CREATE INDEX idx_payloads_fetched ON raw_payloads(fetched_at DESC);

-- ============================================================================
-- NIL DEALS
-- ============================================================================

CREATE TABLE nil_deals (
    deal_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id UUID NOT NULL REFERENCES athletes(athlete_id),
    brand VARCHAR(255) NOT NULL,
    deal_type VARCHAR(100), -- 'endorsement', 'appearance', 'content', 'licensing', etc.
    deal_value DECIMAL(12, 2),
    deal_currency VARCHAR(3) DEFAULT 'USD',
    deal_term_months INTEGER,
    is_national BOOLEAN DEFAULT false,
    is_local BOOLEAN DEFAULT false,
    start_date DATE,
    end_date DATE,
    announced_date DATE,
    source VARCHAR(100) NOT NULL,
    source_url TEXT,
    confidence_score FLOAT CHECK (confidence_score >= 0 AND confidence_score <= 1),
    is_verified BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_deals_athlete ON nil_deals(athlete_id);
CREATE INDEX idx_deals_brand ON nil_deals(brand);
CREATE INDEX idx_deals_value ON nil_deals(deal_value DESC);
CREATE INDEX idx_deals_source ON nil_deals(source);
CREATE INDEX idx_deals_confidence ON nil_deals(confidence_score DESC);

-- ============================================================================
-- NIL VALUATIONS (Point-in-time estimates)
-- ============================================================================

CREATE TABLE nil_valuations (
    valuation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id UUID NOT NULL REFERENCES athletes(athlete_id),
    valuation_amount DECIMAL(12, 2) NOT NULL,
    valuation_currency VARCHAR(3) DEFAULT 'USD',
    valuation_period VARCHAR(50), -- 'annual', 'monthly', 'total', etc.
    source VARCHAR(100) NOT NULL, -- 'on3', 'opendorse', 'inflcr', etc.
    ranking INTEGER, -- Source-specific ranking
    as_of_date DATE NOT NULL,
    confidence_score FLOAT CHECK (confidence_score >= 0 AND confidence_score <= 1),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_valuations_athlete ON nil_valuations(athlete_id, as_of_date DESC);
CREATE INDEX idx_valuations_source ON nil_valuations(source);
CREATE INDEX idx_valuations_amount ON nil_valuations(valuation_amount DESC);

-- ============================================================================
-- ENTITY RESOLUTION
-- ============================================================================

CREATE TABLE entity_matches (
    match_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id UUID REFERENCES athletes(athlete_id),
    event_id UUID REFERENCES athlete_events(event_id),
    match_type VARCHAR(50) NOT NULL, -- 'deterministic', 'probabilistic', 'manual'
    match_confidence FLOAT CHECK (match_confidence >= 0 AND match_confidence <= 1),
    match_explanation TEXT,
    match_attributes JSONB, -- Store matching attributes
    needs_review BOOLEAN DEFAULT false,
    reviewed_by VARCHAR(255),
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_matches_athlete ON entity_matches(athlete_id);
CREATE INDEX idx_matches_event ON entity_matches(event_id);
CREATE INDEX idx_matches_review ON entity_matches(needs_review) WHERE needs_review = true;
CREATE INDEX idx_matches_confidence ON entity_matches(match_confidence);

-- ============================================================================
-- DATA QUALITY METRICS (Field-level confidence)
-- ============================================================================

CREATE TABLE data_quality_metrics (
    metric_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id UUID NOT NULL REFERENCES athletes(athlete_id),
    field_category VARCHAR(100) NOT NULL, -- 'identity', 'brand', 'proof', 'proximity', 'velocity', 'risk'
    field_name VARCHAR(255) NOT NULL,
    field_value TEXT,
    source_reliability FLOAT,
    recency_score FLOAT,
    cross_source_agreement FLOAT,
    anomaly_score FLOAT,
    overall_confidence FLOAT CHECK (overall_confidence >= 0 AND overall_confidence <= 1),
    as_of_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_quality_athlete ON data_quality_metrics(athlete_id, as_of_date DESC);
CREATE INDEX idx_quality_field ON data_quality_metrics(field_category, field_name);
CREATE INDEX idx_quality_confidence ON data_quality_metrics(overall_confidence);

-- ============================================================================
-- PROVENANCE TRACKING (Source tracking for every field)
-- ============================================================================

CREATE TABLE provenance_map (
    provenance_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id UUID NOT NULL REFERENCES athletes(athlete_id),
    field_name VARCHAR(255) NOT NULL,
    field_value TEXT,
    sources JSONB NOT NULL, -- Array of: [{"source": "on3", "timestamp": "...", "reliability": 0.95}]
    confidence FLOAT CHECK (confidence >= 0 AND confidence <= 1),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    version INTEGER DEFAULT 1
);

CREATE INDEX idx_provenance_athlete ON provenance_map(athlete_id);
CREATE INDEX idx_provenance_field ON provenance_map(field_name);
CREATE INDEX idx_provenance_updated ON provenance_map(last_updated DESC);

-- ============================================================================
-- FEATURE STORE (Computed metrics)
-- ============================================================================

CREATE TABLE feature_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id UUID NOT NULL REFERENCES athletes(athlete_id),
    season_id VARCHAR(20) NOT NULL,
    as_of_date DATE NOT NULL,
    features JSONB NOT NULL, -- All computed metrics as JSON
    raw_metrics JSONB,
    derived_metrics JSONB,
    fraud_adjusted_metrics JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(athlete_id, season_id, as_of_date)
);

CREATE INDEX idx_features_athlete ON feature_snapshots(athlete_id, as_of_date DESC);
CREATE INDEX idx_features_season ON feature_snapshots(season_id);

-- ============================================================================
-- GRAVITY SCORES (Component scores: B, P, X, V, R)
-- ============================================================================

CREATE TABLE gravity_scores (
    score_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id UUID NOT NULL REFERENCES athletes(athlete_id),
    season_id VARCHAR(20) NOT NULL,
    as_of_date DATE NOT NULL,
    
    -- Raw component scores (0-100)
    brand_score FLOAT CHECK (brand_score >= 0 AND brand_score <= 100),
    proof_score FLOAT CHECK (proof_score >= 0 AND proof_score <= 100),
    proximity_score FLOAT CHECK (proximity_score >= 0 AND proximity_score <= 100),
    velocity_score FLOAT CHECK (velocity_score >= 0 AND velocity_score <= 100),
    risk_score FLOAT CHECK (risk_score >= 0 AND risk_score <= 100),
    
    -- Confidence scores (0-1)
    brand_confidence FLOAT CHECK (brand_confidence >= 0 AND brand_confidence <= 1),
    proof_confidence FLOAT CHECK (proof_confidence >= 0 AND proof_confidence <= 1),
    proximity_confidence FLOAT CHECK (proximity_confidence >= 0 AND proximity_confidence <= 1),
    velocity_confidence FLOAT CHECK (velocity_confidence >= 0 AND velocity_confidence <= 1),
    risk_confidence FLOAT CHECK (risk_confidence >= 0 AND risk_confidence <= 1),
    
    -- Aggregate Gravity scores
    gravity_raw FLOAT,
    gravity_conf FLOAT,
    average_confidence FLOAT,
    
    -- Explanations and evidence
    explanations JSONB,
    evidence JSONB,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(athlete_id, season_id, as_of_date)
);

CREATE INDEX idx_gravity_athlete ON gravity_scores(athlete_id, as_of_date DESC);
CREATE INDEX idx_gravity_season ON gravity_scores(season_id);
CREATE INDEX idx_gravity_score ON gravity_scores(gravity_conf DESC);

-- ============================================================================
-- UNDERWRITING RESULTS (Deal evaluations)
-- ============================================================================

CREATE TABLE underwriting_results (
    underwriting_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id UUID NOT NULL REFERENCES athletes(athlete_id),
    
    -- Deal proposal details
    proposed_price DECIMAL(12, 2) NOT NULL,
    proposed_term_months INTEGER,
    deal_structure JSONB, -- rights, deliverables, etc.
    
    -- Calculated values
    iacv_p25 DECIMAL(12, 2),
    iacv_p50 DECIMAL(12, 2),
    iacv_p75 DECIMAL(12, 2),
    dsuv DECIMAL(12, 2), -- Deal-Specific Underwritten Value
    radv DECIMAL(12, 2), -- Risk-Adjusted Deal Value
    
    -- Decision
    decision VARCHAR(50) NOT NULL, -- 'approve', 'counter', 'no-go'
    decision_rationale TEXT,
    counter_price DECIMAL(12, 2),
    
    -- Negotiation terms
    anchor_price DECIMAL(12, 2),
    target_price DECIMAL(12, 2),
    walk_away_price DECIMAL(12, 2),
    concession_ladder JSONB,
    recommended_clauses TEXT[],
    
    -- Metadata
    underwritten_by VARCHAR(255),
    underwritten_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP -- Underwriting validity period
);

CREATE INDEX idx_underwriting_athlete ON underwriting_results(athlete_id, underwritten_at DESC);
CREATE INDEX idx_underwriting_decision ON underwriting_results(decision);

-- ============================================================================
-- NEGOTIATION PACKS (Generated pack metadata)
-- ============================================================================

CREATE TABLE negotiation_packs (
    pack_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id UUID NOT NULL REFERENCES athletes(athlete_id),
    underwriting_id UUID REFERENCES underwriting_results(underwriting_id),
    
    -- Output files
    json_file_path TEXT,
    pdf_file_path TEXT,
    json_url TEXT,
    pdf_url TEXT,
    
    -- Pack metadata
    pack_version VARCHAR(20),
    generated_by VARCHAR(255),
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Status
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    error_message TEXT,
    
    -- Access control
    access_token VARCHAR(255) UNIQUE,
    expires_at TIMESTAMP,
    download_count INTEGER DEFAULT 0
);

CREATE INDEX idx_packs_athlete ON negotiation_packs(athlete_id);
CREATE INDEX idx_packs_status ON negotiation_packs(status);
CREATE INDEX idx_packs_generated ON negotiation_packs(generated_at DESC);
CREATE INDEX idx_packs_token ON negotiation_packs(access_token);

-- ============================================================================
-- ASYNC JOB TRACKING
-- ============================================================================

CREATE TABLE pack_jobs (
    job_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id UUID NOT NULL REFERENCES athletes(athlete_id),
    deal_proposal JSONB,
    
    -- Status tracking
    status VARCHAR(50) NOT NULL DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    progress INTEGER DEFAULT 0, -- 0-100
    error_message TEXT,
    
    -- Results
    pack_id UUID REFERENCES negotiation_packs(pack_id),
    json_url TEXT,
    pdf_url TEXT,
    
    -- Timing
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    
    -- Metadata
    requested_by VARCHAR(255),
    priority INTEGER DEFAULT 5 -- 1-10, lower = higher priority
);

CREATE INDEX idx_jobs_status ON pack_jobs(status, priority, created_at);
CREATE INDEX idx_jobs_athlete ON pack_jobs(athlete_id);
CREATE INDEX idx_jobs_created ON pack_jobs(created_at DESC);

-- ============================================================================
-- AUDIT LOG (Complete audit trail)
-- ============================================================================

CREATE TABLE audit_log (
    audit_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    table_name VARCHAR(100) NOT NULL,
    record_id UUID NOT NULL,
    operation VARCHAR(20) NOT NULL, -- 'INSERT', 'UPDATE', 'DELETE'
    old_values JSONB,
    new_values JSONB,
    changed_by VARCHAR(255),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address INET,
    user_agent TEXT
);

CREATE INDEX idx_audit_table ON audit_log(table_name, changed_at DESC);
CREATE INDEX idx_audit_record ON audit_log(record_id);
CREATE INDEX idx_audit_operation ON audit_log(operation);

-- ============================================================================
-- TRIGGER FUNCTIONS FOR AUDIT LOGGING
-- ============================================================================

CREATE OR REPLACE FUNCTION audit_trigger_func()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO audit_log (table_name, record_id, operation, new_values)
        VALUES (TG_TABLE_NAME, NEW.athlete_id, 'INSERT', row_to_json(NEW));
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO audit_log (table_name, record_id, operation, old_values, new_values)
        VALUES (TG_TABLE_NAME, NEW.athlete_id, 'UPDATE', row_to_json(OLD), row_to_json(NEW));
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO audit_log (table_name, record_id, operation, old_values)
        VALUES (TG_TABLE_NAME, OLD.athlete_id, 'DELETE', row_to_json(OLD));
        RETURN OLD;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Apply audit triggers to key tables
CREATE TRIGGER audit_athletes AFTER INSERT OR UPDATE OR DELETE ON athletes
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_func();

CREATE TRIGGER audit_nil_deals AFTER INSERT OR UPDATE OR DELETE ON nil_deals
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_func();

CREATE TRIGGER audit_underwriting AFTER INSERT OR UPDATE OR DELETE ON underwriting_results
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_func();

-- ============================================================================
-- UPDATE TIMESTAMP TRIGGERS
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_athletes_updated_at BEFORE UPDATE ON athletes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_nil_deals_updated_at BEFORE UPDATE ON nil_deals
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- MATERIALIZED VIEWS FOR PERFORMANCE
-- ============================================================================

-- Latest valuations per athlete
CREATE MATERIALIZED VIEW mv_latest_valuations AS
SELECT DISTINCT ON (athlete_id, source)
    athlete_id,
    source,
    valuation_amount,
    ranking,
    as_of_date,
    confidence_score
FROM nil_valuations
ORDER BY athlete_id, source, as_of_date DESC;

CREATE UNIQUE INDEX idx_mv_latest_val ON mv_latest_valuations(athlete_id, source);

-- Current Gravity scores per athlete
CREATE MATERIALIZED VIEW mv_current_gravity_scores AS
SELECT DISTINCT ON (athlete_id)
    athlete_id,
    gravity_conf,
    brand_score,
    proof_score,
    proximity_score,
    velocity_score,
    risk_score,
    average_confidence,
    as_of_date
FROM gravity_scores
ORDER BY athlete_id, as_of_date DESC;

CREATE UNIQUE INDEX idx_mv_current_gravity ON mv_current_gravity_scores(athlete_id);

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Refresh all materialized views
CREATE OR REPLACE FUNCTION refresh_all_materialized_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_latest_valuations;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_current_gravity_scores;
END;
$$ LANGUAGE plpgsql;

-- Get athlete summary
CREATE OR REPLACE FUNCTION get_athlete_summary(p_athlete_id UUID)
RETURNS TABLE (
    athlete_name VARCHAR,
    sport VARCHAR,
    school VARCHAR,
    latest_valuation DECIMAL,
    gravity_score FLOAT,
    deal_count BIGINT,
    total_deal_value DECIMAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        a.canonical_name,
        a.sport,
        a.school,
        COALESCE(v.valuation_amount, 0) as latest_valuation,
        COALESCE(g.gravity_conf, 0) as gravity_score,
        COUNT(DISTINCT d.deal_id) as deal_count,
        COALESCE(SUM(d.deal_value), 0) as total_deal_value
    FROM athletes a
    LEFT JOIN mv_latest_valuations v ON a.athlete_id = v.athlete_id AND v.source = 'on3'
    LEFT JOIN mv_current_gravity_scores g ON a.athlete_id = g.athlete_id
    LEFT JOIN nil_deals d ON a.athlete_id = d.athlete_id
    WHERE a.athlete_id = p_athlete_id
    GROUP BY a.canonical_name, a.sport, a.school, v.valuation_amount, g.gravity_conf;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- GRANTS (Adjust as needed for your security model)
-- ============================================================================

-- Grant read access to application user
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO gravity_app_user;
-- GRANT INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO gravity_app_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO gravity_app_user;

-- ============================================================================
-- INITIAL DATA / SEED DATA
-- ============================================================================

-- Source reliability weights (can be updated via application)
CREATE TABLE source_reliability_weights (
    source VARCHAR(100) PRIMARY KEY,
    reliability_weight FLOAT NOT NULL CHECK (reliability_weight >= 0 AND reliability_weight <= 1),
    tier INTEGER,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO source_reliability_weights (source, reliability_weight, tier, description) VALUES
    ('on3', 0.95, 1, 'Primary NIL platform with verified data'),
    ('opendorse', 0.90, 1, 'NIL marketplace with direct athlete connections'),
    ('inflcr', 0.85, 2, 'Social analytics and NIL platform'),
    ('teamworks', 0.80, 2, 'Team management platform with official data'),
    ('247sports', 0.75, 3, 'Recruiting and NIL coverage'),
    ('rivals', 0.75, 3, 'Recruiting and NIL rankings'),
    ('news', 0.60, 4, 'Public news sources'),
    ('social', 0.50, 5, 'Social media posts and announcements'),
    ('espn', 0.95, 1, 'Official sports statistics'),
    ('wikipedia', 0.70, 3, 'Public encyclopedia'),
    ('direct_api', 0.98, 1, 'Direct API integrations with official sources');

COMMENT ON DATABASE current_database() IS 'Gravity NIL Data Pipeline - Production Database Schema v1.0';
