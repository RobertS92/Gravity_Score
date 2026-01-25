"""
SQLAlchemy ORM Models for Gravity NIL Data Pipeline
Production-grade models with full type safety and relationships
"""

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, TIMESTAMP, Date,
    ForeignKey, CheckConstraint, UniqueConstraint, ARRAY, DECIMAL, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

Base = declarative_base()


class Athlete(Base):
    """Canonical athlete records"""
    __tablename__ = 'athletes'
    
    athlete_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    canonical_name = Column(String(255), nullable=False)
    sport = Column(String(50), nullable=False)
    school = Column(String(255))
    position = Column(String(50))
    conference = Column(String(100))
    jersey_number = Column(Integer)
    class_year = Column(String(50))
    season_id = Column(String(20))
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    metadata = Column(JSONB, default={})
    
    # Relationships
    events = relationship("AthleteEvent", back_populates="athlete", cascade="all, delete-orphan")
    nil_deals = relationship("NILDeal", back_populates="athlete", cascade="all, delete-orphan")
    nil_valuations = relationship("NILValuation", back_populates="athlete", cascade="all, delete-orphan")
    gravity_scores = relationship("GravityScore", back_populates="athlete", cascade="all, delete-orphan")
    feature_snapshots = relationship("FeatureSnapshot", back_populates="athlete", cascade="all, delete-orphan")
    underwriting_results = relationship("UnderwritingResult", back_populates="athlete", cascade="all, delete-orphan")
    negotiation_packs = relationship("NegotiationPack", back_populates="athlete", cascade="all, delete-orphan")
    pack_jobs = relationship("PackJob", back_populates="athlete", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_athletes_name', 'canonical_name'),
        Index('idx_athletes_sport_school', 'sport', 'school'),
        Index('idx_athletes_season', 'season_id'),
    )


class AthleteEvent(Base):
    """Time-series events (social posts, news mentions, roster changes)"""
    __tablename__ = 'athlete_events'
    
    event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey('athletes.athlete_id'), nullable=False)
    event_type = Column(String(100), nullable=False)
    event_timestamp = Column(TIMESTAMP, nullable=False)
    source = Column(String(100), nullable=False)
    raw_data = Column(JSONB, nullable=False)
    processed = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    # Relationships
    athlete = relationship("Athlete", back_populates="events")
    
    __table_args__ = (
        Index('idx_events_athlete', 'athlete_id', 'event_timestamp'),
        Index('idx_events_type', 'event_type'),
        Index('idx_events_source', 'source'),
        Index('idx_events_processed', 'processed'),
    )


class RawPayload(Base):
    """Metadata for filesystem/S3 stored raw payloads"""
    __tablename__ = 'raw_payloads'
    
    payload_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey('athletes.athlete_id'))
    source = Column(String(100), nullable=False)
    payload_type = Column(String(100), nullable=False)
    file_path = Column(Text, nullable=False)
    file_size_bytes = Column(Integer)
    checksum = Column(String(64))  # SHA-256
    fetched_at = Column(TIMESTAMP, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    __table_args__ = (
        Index('idx_payloads_athlete', 'athlete_id'),
        Index('idx_payloads_source', 'source'),
        Index('idx_payloads_fetched', 'fetched_at'),
    )


class NILDeal(Base):
    """Individual NIL deals with source and confidence tracking"""
    __tablename__ = 'nil_deals'
    
    deal_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey('athletes.athlete_id'), nullable=False)
    brand = Column(String(255), nullable=False)
    deal_type = Column(String(100))
    deal_value = Column(DECIMAL(12, 2))
    deal_currency = Column(String(3), default='USD')
    deal_term_months = Column(Integer)
    is_national = Column(Boolean, default=False)
    is_local = Column(Boolean, default=False)
    start_date = Column(Date)
    end_date = Column(Date)
    announced_date = Column(Date)
    source = Column(String(100), nullable=False)
    source_url = Column(Text)
    confidence_score = Column(Float)
    is_verified = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # Relationships
    athlete = relationship("Athlete", back_populates="nil_deals")
    
    __table_args__ = (
        CheckConstraint('confidence_score >= 0 AND confidence_score <= 1', name='check_deal_confidence'),
        Index('idx_deals_athlete', 'athlete_id'),
        Index('idx_deals_brand', 'brand'),
        Index('idx_deals_value', 'deal_value'),
        Index('idx_deals_source', 'source'),
        Index('idx_deals_confidence', 'confidence_score'),
    )


class NILValuation(Base):
    """Point-in-time NIL valuations from various sources"""
    __tablename__ = 'nil_valuations'
    
    valuation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey('athletes.athlete_id'), nullable=False)
    valuation_amount = Column(DECIMAL(12, 2), nullable=False)
    valuation_currency = Column(String(3), default='USD')
    valuation_period = Column(String(50))
    source = Column(String(100), nullable=False)
    ranking = Column(Integer)
    as_of_date = Column(Date, nullable=False)
    confidence_score = Column(Float)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    # Relationships
    athlete = relationship("Athlete", back_populates="nil_valuations")
    
    __table_args__ = (
        CheckConstraint('confidence_score >= 0 AND confidence_score <= 1', name='check_valuation_confidence'),
        Index('idx_valuations_athlete', 'athlete_id', 'as_of_date'),
        Index('idx_valuations_source', 'source'),
        Index('idx_valuations_amount', 'valuation_amount'),
    )


class EntityMatch(Base):
    """Entity resolution tracking"""
    __tablename__ = 'entity_matches'
    
    match_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey('athletes.athlete_id'))
    event_id = Column(UUID(as_uuid=True), ForeignKey('athlete_events.event_id'))
    match_type = Column(String(50), nullable=False)
    match_confidence = Column(Float)
    match_explanation = Column(Text)
    match_attributes = Column(JSONB)
    needs_review = Column(Boolean, default=False)
    reviewed_by = Column(String(255))
    reviewed_at = Column(TIMESTAMP)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    __table_args__ = (
        CheckConstraint('match_confidence >= 0 AND match_confidence <= 1', name='check_match_confidence'),
        Index('idx_matches_athlete', 'athlete_id'),
        Index('idx_matches_event', 'event_id'),
        Index('idx_matches_review', 'needs_review'),
        Index('idx_matches_confidence', 'match_confidence'),
    )


class DataQualityMetric(Base):
    """Field-level confidence scores"""
    __tablename__ = 'data_quality_metrics'
    
    metric_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey('athletes.athlete_id'), nullable=False)
    field_category = Column(String(100), nullable=False)
    field_name = Column(String(255), nullable=False)
    field_value = Column(Text)
    source_reliability = Column(Float)
    recency_score = Column(Float)
    cross_source_agreement = Column(Float)
    anomaly_score = Column(Float)
    overall_confidence = Column(Float)
    as_of_date = Column(Date, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    __table_args__ = (
        CheckConstraint('overall_confidence >= 0 AND overall_confidence <= 1', name='check_overall_confidence'),
        Index('idx_quality_athlete', 'athlete_id', 'as_of_date'),
        Index('idx_quality_field', 'field_category', 'field_name'),
        Index('idx_quality_confidence', 'overall_confidence'),
    )


class ProvenanceMap(Base):
    """Source tracking for every field value"""
    __tablename__ = 'provenance_map'
    
    provenance_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey('athletes.athlete_id'), nullable=False)
    field_name = Column(String(255), nullable=False)
    field_value = Column(Text)
    sources = Column(JSONB, nullable=False)  # Array of source objects
    confidence = Column(Float)
    last_updated = Column(TIMESTAMP, server_default=func.current_timestamp())
    version = Column(Integer, default=1)
    
    __table_args__ = (
        CheckConstraint('confidence >= 0 AND confidence <= 1', name='check_provenance_confidence'),
        Index('idx_provenance_athlete', 'athlete_id'),
        Index('idx_provenance_field', 'field_name'),
        Index('idx_provenance_updated', 'last_updated'),
    )


class FeatureSnapshot(Base):
    """Computed metrics and features"""
    __tablename__ = 'feature_snapshots'
    
    snapshot_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey('athletes.athlete_id'), nullable=False)
    season_id = Column(String(20), nullable=False)
    as_of_date = Column(Date, nullable=False)
    features = Column(JSONB, nullable=False)
    raw_metrics = Column(JSONB)
    derived_metrics = Column(JSONB)
    fraud_adjusted_metrics = Column(JSONB)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    # Relationships
    athlete = relationship("Athlete", back_populates="feature_snapshots")
    
    __table_args__ = (
        UniqueConstraint('athlete_id', 'season_id', 'as_of_date', name='uq_feature_snapshot'),
        Index('idx_features_athlete', 'athlete_id', 'as_of_date'),
        Index('idx_features_season', 'season_id'),
    )


class GravityScore(Base):
    """Component scores (B, P, X, V, R) with confidence"""
    __tablename__ = 'gravity_scores'
    
    score_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey('athletes.athlete_id'), nullable=False)
    season_id = Column(String(20), nullable=False)
    as_of_date = Column(Date, nullable=False)
    
    # Component scores (0-100)
    brand_score = Column(Float)
    proof_score = Column(Float)
    proximity_score = Column(Float)
    velocity_score = Column(Float)
    risk_score = Column(Float)
    
    # Confidence scores (0-1)
    brand_confidence = Column(Float)
    proof_confidence = Column(Float)
    proximity_confidence = Column(Float)
    velocity_confidence = Column(Float)
    risk_confidence = Column(Float)
    
    # Aggregate scores
    gravity_raw = Column(Float)
    gravity_conf = Column(Float)
    average_confidence = Column(Float)
    
    # Explanations and evidence
    explanations = Column(JSONB)
    evidence = Column(JSONB)
    
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    # Relationships
    athlete = relationship("Athlete", back_populates="gravity_scores")
    
    __table_args__ = (
        CheckConstraint('brand_score >= 0 AND brand_score <= 100', name='check_brand_score'),
        CheckConstraint('proof_score >= 0 AND proof_score <= 100', name='check_proof_score'),
        CheckConstraint('proximity_score >= 0 AND proximity_score <= 100', name='check_proximity_score'),
        CheckConstraint('velocity_score >= 0 AND velocity_score <= 100', name='check_velocity_score'),
        CheckConstraint('risk_score >= 0 AND risk_score <= 100', name='check_risk_score'),
        CheckConstraint('brand_confidence >= 0 AND brand_confidence <= 1', name='check_brand_confidence'),
        CheckConstraint('proof_confidence >= 0 AND proof_confidence <= 1', name='check_proof_confidence'),
        CheckConstraint('proximity_confidence >= 0 AND proximity_confidence <= 1', name='check_proximity_confidence'),
        CheckConstraint('velocity_confidence >= 0 AND velocity_confidence <= 1', name='check_velocity_confidence'),
        CheckConstraint('risk_confidence >= 0 AND risk_confidence <= 1', name='check_risk_confidence'),
        UniqueConstraint('athlete_id', 'season_id', 'as_of_date', name='uq_gravity_score'),
        Index('idx_gravity_athlete', 'athlete_id', 'as_of_date'),
        Index('idx_gravity_season', 'season_id'),
        Index('idx_gravity_score', 'gravity_conf'),
    )


class UnderwritingResult(Base):
    """Deal evaluation and underwriting decisions"""
    __tablename__ = 'underwriting_results'
    
    underwriting_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey('athletes.athlete_id'), nullable=False)
    
    # Deal proposal
    proposed_price = Column(DECIMAL(12, 2), nullable=False)
    proposed_term_months = Column(Integer)
    deal_structure = Column(JSONB)
    
    # Calculated values
    iacv_p25 = Column(DECIMAL(12, 2))
    iacv_p50 = Column(DECIMAL(12, 2))
    iacv_p75 = Column(DECIMAL(12, 2))
    dsuv = Column(DECIMAL(12, 2))
    radv = Column(DECIMAL(12, 2))
    
    # Decision
    decision = Column(String(50), nullable=False)
    decision_rationale = Column(Text)
    counter_price = Column(DECIMAL(12, 2))
    
    # Negotiation terms
    anchor_price = Column(DECIMAL(12, 2))
    target_price = Column(DECIMAL(12, 2))
    walk_away_price = Column(DECIMAL(12, 2))
    concession_ladder = Column(JSONB)
    recommended_clauses = Column(ARRAY(Text))
    
    # Metadata
    underwritten_by = Column(String(255))
    underwritten_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    expires_at = Column(TIMESTAMP)
    
    # Relationships
    athlete = relationship("Athlete", back_populates="underwriting_results")
    
    __table_args__ = (
        Index('idx_underwriting_athlete', 'athlete_id', 'underwritten_at'),
        Index('idx_underwriting_decision', 'decision'),
    )


class NegotiationPack(Base):
    """Generated pack metadata and outputs"""
    __tablename__ = 'negotiation_packs'
    
    pack_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey('athletes.athlete_id'), nullable=False)
    underwriting_id = Column(UUID(as_uuid=True), ForeignKey('underwriting_results.underwriting_id'))
    
    # Output files
    json_file_path = Column(Text)
    pdf_file_path = Column(Text)
    json_url = Column(Text)
    pdf_url = Column(Text)
    
    # Pack metadata
    pack_version = Column(String(20))
    generated_by = Column(String(255))
    generated_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    # Status
    status = Column(String(50), default='pending')
    error_message = Column(Text)
    
    # Access control
    access_token = Column(String(255), unique=True)
    expires_at = Column(TIMESTAMP)
    download_count = Column(Integer, default=0)
    
    # Relationships
    athlete = relationship("Athlete", back_populates="negotiation_packs")
    
    __table_args__ = (
        Index('idx_packs_athlete', 'athlete_id'),
        Index('idx_packs_status', 'status'),
        Index('idx_packs_generated', 'generated_at'),
        Index('idx_packs_token', 'access_token'),
    )


class PackJob(Base):
    """Async job tracking for pack generation"""
    __tablename__ = 'pack_jobs'
    
    job_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey('athletes.athlete_id'), nullable=False)
    deal_proposal = Column(JSONB)
    
    # Status tracking
    status = Column(String(50), nullable=False, default='pending')
    progress = Column(Integer, default=0)
    error_message = Column(Text)
    
    # Results
    pack_id = Column(UUID(as_uuid=True), ForeignKey('negotiation_packs.pack_id'))
    json_url = Column(Text)
    pdf_url = Column(Text)
    
    # Timing
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    started_at = Column(TIMESTAMP)
    completed_at = Column(TIMESTAMP)
    
    # Metadata
    requested_by = Column(String(255))
    priority = Column(Integer, default=5)
    
    # Relationships
    athlete = relationship("Athlete", back_populates="pack_jobs")
    
    __table_args__ = (
        Index('idx_jobs_status', 'status', 'priority', 'created_at'),
        Index('idx_jobs_athlete', 'athlete_id'),
        Index('idx_jobs_created', 'created_at'),
    )


class AuditLog(Base):
    """Complete audit trail for all operations"""
    __tablename__ = 'audit_log'
    
    audit_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    table_name = Column(String(100), nullable=False)
    record_id = Column(UUID(as_uuid=True), nullable=False)
    operation = Column(String(20), nullable=False)
    old_values = Column(JSONB)
    new_values = Column(JSONB)
    changed_by = Column(String(255))
    changed_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    ip_address = Column(INET)
    user_agent = Column(Text)
    
    __table_args__ = (
        Index('idx_audit_table', 'table_name', 'changed_at'),
        Index('idx_audit_record', 'record_id'),
        Index('idx_audit_operation', 'operation'),
    )


class SourceReliabilityWeight(Base):
    """Source reliability configuration"""
    __tablename__ = 'source_reliability_weights'
    
    source = Column(String(100), primary_key=True)
    reliability_weight = Column(Float, nullable=False)
    tier = Column(Integer)
    description = Column(Text)
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    __table_args__ = (
        CheckConstraint('reliability_weight >= 0 AND reliability_weight <= 1', name='check_reliability_weight'),
    )


class CrawlerExecution(Base):
    """Crawler execution tracking"""
    __tablename__ = 'crawler_executions'
    
    execution_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    crawler_name = Column(String(100), nullable=False)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey('athletes.athlete_id'))
    sport = Column(String(50))
    status = Column(String(50), nullable=False)
    started_at = Column(TIMESTAMP, nullable=False)
    completed_at = Column(TIMESTAMP)
    duration_seconds = Column(Integer)
    events_created = Column(Integer, default=0)
    errors = Column(JSONB)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())


class CrawlerConfig(Base):
    """Crawler configuration and scheduling"""
    __tablename__ = 'crawler_configs'
    
    config_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    crawler_name = Column(String(100), unique=True, nullable=False)
    is_enabled = Column(Boolean, default=True)
    schedule_interval = Column(String(50))
    schedule_time = Column(String(10))
    last_run_at = Column(TIMESTAMP)
    next_run_at = Column(TIMESTAMP)
    config = Column(JSONB, default={})
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp())


class ScoreRecalculation(Base):
    """Score recalculation tracking"""
    __tablename__ = 'score_recalculations'
    
    recalculation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey('athletes.athlete_id'), nullable=False)
    trigger_event_id = Column(UUID(as_uuid=True), ForeignKey('athlete_events.event_id'))
    trigger_event_type = Column(String(100))
    components_recalculated = Column(ARRAY(String))
    old_gravity_score = Column(Float)
    new_gravity_score = Column(Float)
    score_delta = Column(Float)
    recalculated_at = Column(TIMESTAMP, server_default=func.current_timestamp())
