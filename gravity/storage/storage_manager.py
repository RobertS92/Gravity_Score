"""
Storage Manager for Gravity NIL Pipeline
Handles raw payload storage and PostgreSQL connection management
"""

import os
import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from contextlib import contextmanager
import uuid

from sqlalchemy import create_engine, pool
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

# Import models
try:
    from gravity.db.models import Base, RawPayload
except ImportError:
    from db.models import Base, RawPayload

logger = logging.getLogger(__name__)


class StorageManager:
    """
    Manages storage for raw payloads (filesystem/S3) and PostgreSQL connections
    """
    
    def __init__(
        self,
        postgres_url: Optional[str] = None,
        raw_payload_base_path: Optional[str] = None,
        use_s3: bool = False,
        s3_bucket: Optional[str] = None
    ):
        """
        Initialize storage manager
        
        Args:
            postgres_url: PostgreSQL connection string
            raw_payload_base_path: Base path for storing raw payloads
            use_s3: Whether to use S3 for raw storage (False = filesystem)
            s3_bucket: S3 bucket name if using S3
        """
        # PostgreSQL setup
        self.postgres_url = postgres_url or os.getenv(
            'POSTGRES_URL',
            'postgresql://localhost:5432/gravity_nil'
        )
        
        # Create engine with connection pooling
        self.engine = create_engine(
            self.postgres_url,
            poolclass=pool.QueuePool,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,  # Verify connections before using
            echo=False  # Set to True for SQL debugging
        )
        
        # Create session factory
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
        
        # Raw payload storage setup
        self.raw_payload_base_path = Path(raw_payload_base_path or os.getenv(
            'RAW_PAYLOAD_PATH',
            'data/raw_payloads'
        ))
        self.use_s3 = use_s3
        self.s3_bucket = s3_bucket or os.getenv('S3_BUCKET')
        
        if not use_s3:
            # Create base directory for filesystem storage
            self.raw_payload_base_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Raw payload storage initialized at: {self.raw_payload_base_path}")
        else:
            logger.info(f"Raw payload storage configured for S3 bucket: {self.s3_bucket}")
        
        logger.info(f"PostgreSQL connection initialized: {self.postgres_url.split('@')[1] if '@' in self.postgres_url else 'localhost'}")
    
    # ========================================================================
    # SESSION MANAGEMENT
    # ========================================================================
    
    @contextmanager
    def get_session(self) -> Session:
        """
        Get a database session with automatic cleanup
        
        Usage:
            with storage.get_session() as session:
                session.query(Athlete).all()
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Session error: {e}")
            raise
        finally:
            session.close()
    
    def execute_in_transaction(self, func, *args, **kwargs) -> Any:
        """
        Execute a function within a transaction
        Automatically handles commit/rollback
        
        Args:
            func: Function that takes session as first argument
            *args, **kwargs: Additional arguments to pass to func
        
        Returns:
            Result from func
        """
        with self.get_session() as session:
            return func(session, *args, **kwargs)
    
    # ========================================================================
    # RAW PAYLOAD STORAGE
    # ========================================================================
    
    def write_raw_payload(
        self,
        data: Dict[str, Any],
        source: str,
        payload_type: str,
        athlete_id: Optional[uuid.UUID] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Write raw payload to storage and record metadata in PostgreSQL
        
        Args:
            data: Raw payload data (will be JSON serialized)
            source: Data source (e.g., 'on3', 'opendorse')
            payload_type: Type of payload (e.g., 'valuation', 'deal', 'profile')
            athlete_id: Optional athlete UUID
            metadata: Optional additional metadata
        
        Returns:
            Dict with file_path, payload_id, checksum
        """
        # Generate file path
        date_str = datetime.now().strftime('%Y-%m-%d')
        payload_id = uuid.uuid4()
        
        if self.use_s3:
            file_path = f"s3://{self.s3_bucket}/{source}/{date_str}/{payload_id}.json"
            self._write_to_s3(file_path, data)
        else:
            # Filesystem storage
            dir_path = self.raw_payload_base_path / source / date_str
            dir_path.mkdir(parents=True, exist_ok=True)
            file_path = dir_path / f"{payload_id}.json"
            
            # Write JSON file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
            
            file_path = str(file_path)
        
        # Calculate checksum
        json_str = json.dumps(data, sort_keys=True, default=str)
        checksum = hashlib.sha256(json_str.encode()).hexdigest()
        
        # Record metadata in PostgreSQL
        try:
            with self.get_session() as session:
                payload_record = RawPayload(
                    payload_id=payload_id,
                    athlete_id=athlete_id,
                    source=source,
                    payload_type=payload_type,
                    file_path=file_path,
                    file_size_bytes=len(json_str),
                    checksum=checksum,
                    fetched_at=datetime.now()
                )
                session.add(payload_record)
                session.commit()
                
                logger.info(f"Raw payload written: {source}/{payload_type} -> {file_path}")
                
                return {
                    'payload_id': str(payload_id),
                    'file_path': file_path,
                    'checksum': checksum,
                    'size_bytes': len(json_str)
                }
        except SQLAlchemyError as e:
            logger.error(f"Failed to record payload metadata: {e}")
            # Still return file info even if DB write fails
            return {
                'payload_id': str(payload_id),
                'file_path': file_path,
                'checksum': checksum,
                'size_bytes': len(json_str),
                'warning': 'Metadata not recorded in database'
            }
    
    def read_raw_payload(self, payload_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """
        Read raw payload from storage
        
        Args:
            payload_id: UUID of payload
        
        Returns:
            Parsed JSON data or None if not found
        """
        try:
            with self.get_session() as session:
                payload_record = session.query(RawPayload).filter(
                    RawPayload.payload_id == payload_id
                ).first()
                
                if not payload_record:
                    logger.warning(f"Payload not found: {payload_id}")
                    return None
                
                file_path = payload_record.file_path
                
                if file_path.startswith('s3://'):
                    return self._read_from_s3(file_path)
                else:
                    # Filesystem read
                    with open(file_path, 'r', encoding='utf-8') as f:
                        return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read payload {payload_id}: {e}")
            return None
    
    def _write_to_s3(self, s3_path: str, data: Dict[str, Any]):
        """Write data to S3 (requires boto3)"""
        try:
            import boto3
            s3 = boto3.client('s3')
            
            # Parse S3 path
            parts = s3_path.replace('s3://', '').split('/', 1)
            bucket = parts[0]
            key = parts[1]
            
            json_str = json.dumps(data, indent=2, default=str)
            s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=json_str.encode('utf-8'),
                ContentType='application/json'
            )
        except ImportError:
            raise RuntimeError("boto3 not installed. Install with: pip install boto3")
        except Exception as e:
            logger.error(f"S3 write failed: {e}")
            raise
    
    def _read_from_s3(self, s3_path: str) -> Dict[str, Any]:
        """Read data from S3 (requires boto3)"""
        try:
            import boto3
            s3 = boto3.client('s3')
            
            # Parse S3 path
            parts = s3_path.replace('s3://', '').split('/', 1)
            bucket = parts[0]
            key = parts[1]
            
            response = s3.get_object(Bucket=bucket, Key=key)
            json_str = response['Body'].read().decode('utf-8')
            return json.loads(json_str)
        except ImportError:
            raise RuntimeError("boto3 not installed. Install with: pip install boto3")
        except Exception as e:
            logger.error(f"S3 read failed: {e}")
            raise
    
    # ========================================================================
    # AUDIT LOGGING
    # ========================================================================
    
    def write_audit_log(
        self,
        table_name: str,
        record_id: uuid.UUID,
        operation: str,
        old_values: Optional[Dict] = None,
        new_values: Optional[Dict] = None,
        changed_by: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """
        Write audit log entry
        
        Args:
            table_name: Name of table being modified
            record_id: UUID of record
            operation: 'INSERT', 'UPDATE', or 'DELETE'
            old_values: Previous values (for UPDATE/DELETE)
            new_values: New values (for INSERT/UPDATE)
            changed_by: User/system identifier
            ip_address: IP address of requester
            user_agent: User agent string
        """
        from gravity.db.models import AuditLog
        
        try:
            with self.get_session() as session:
                audit_entry = AuditLog(
                    table_name=table_name,
                    record_id=record_id,
                    operation=operation,
                    old_values=old_values,
                    new_values=new_values,
                    changed_by=changed_by,
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                session.add(audit_entry)
                session.commit()
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def init_database(self):
        """
        Initialize database schema (create all tables)
        WARNING: This should only be run in development or with migrations
        """
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database schema initialized")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    def drop_all_tables(self):
        """
        Drop all tables
        WARNING: This is destructive! Only use in development/testing
        """
        if os.getenv('ENVIRONMENT') == 'production':
            raise RuntimeError("Cannot drop tables in production!")
        
        try:
            Base.metadata.drop_all(bind=self.engine)
            logger.warning("All tables dropped")
        except Exception as e:
            logger.error(f"Failed to drop tables: {e}")
            raise
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check health of storage systems
        
        Returns:
            Dict with status of PostgreSQL and raw storage
        """
        status = {
            'postgres': False,
            'raw_storage': False,
            'details': {}
        }
        
        # Check PostgreSQL
        try:
            with self.get_session() as session:
                session.execute("SELECT 1")
            status['postgres'] = True
            status['details']['postgres'] = 'Connected'
        except Exception as e:
            status['details']['postgres'] = f'Error: {str(e)}'
        
        # Check raw storage
        try:
            if self.use_s3:
                # Check S3 access
                import boto3
                s3 = boto3.client('s3')
                s3.head_bucket(Bucket=self.s3_bucket)
                status['raw_storage'] = True
                status['details']['raw_storage'] = f'S3 bucket accessible: {self.s3_bucket}'
            else:
                # Check filesystem
                test_file = self.raw_payload_base_path / '.health_check'
                test_file.write_text('OK')
                test_file.unlink()
                status['raw_storage'] = True
                status['details']['raw_storage'] = f'Filesystem writable: {self.raw_payload_base_path}'
        except Exception as e:
            status['details']['raw_storage'] = f'Error: {str(e)}'
        
        return status
    
    def cleanup_old_payloads(self, days_old: int = 90) -> int:
        """
        Clean up raw payloads older than specified days
        
        Args:
            days_old: Delete payloads older than this many days
        
        Returns:
            Number of payloads deleted
        """
        from datetime import timedelta
        cutoff_date = datetime.now() - timedelta(days=days_old)
        
        try:
            with self.get_session() as session:
                old_payloads = session.query(RawPayload).filter(
                    RawPayload.fetched_at < cutoff_date
                ).all()
                
                deleted_count = 0
                for payload in old_payloads:
                    try:
                        # Delete file
                        if not payload.file_path.startswith('s3://'):
                            file_path = Path(payload.file_path)
                            if file_path.exists():
                                file_path.unlink()
                        
                        # Delete DB record
                        session.delete(payload)
                        deleted_count += 1
                    except Exception as e:
                        logger.error(f"Failed to delete payload {payload.payload_id}: {e}")
                
                session.commit()
                logger.info(f"Cleaned up {deleted_count} old payloads (>{days_old} days)")
                return deleted_count
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            return 0
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """
        Get storage statistics
        
        Returns:
            Dict with payload counts, sizes, etc.
        """
        try:
            with self.get_session() as session:
                from sqlalchemy import func
                
                stats = session.query(
                    func.count(RawPayload.payload_id).label('total_payloads'),
                    func.sum(RawPayload.file_size_bytes).label('total_size_bytes'),
                    func.min(RawPayload.fetched_at).label('oldest_payload'),
                    func.max(RawPayload.fetched_at).label('newest_payload')
                ).first()
                
                return {
                    'total_payloads': stats.total_payloads or 0,
                    'total_size_bytes': stats.total_size_bytes or 0,
                    'total_size_mb': round((stats.total_size_bytes or 0) / 1024 / 1024, 2),
                    'oldest_payload': stats.oldest_payload.isoformat() if stats.oldest_payload else None,
                    'newest_payload': stats.newest_payload.isoformat() if stats.newest_payload else None
                }
        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            return {}


# Singleton instance for easy access
_storage_manager_instance = None

def get_storage_manager() -> StorageManager:
    """Get or create singleton storage manager instance"""
    global _storage_manager_instance
    if _storage_manager_instance is None:
        _storage_manager_instance = StorageManager()
    return _storage_manager_instance
