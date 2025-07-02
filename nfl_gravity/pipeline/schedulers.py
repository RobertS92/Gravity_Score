"""Scheduling components for automated pipeline execution."""

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Callable
from enum import Enum

from ..core.config import Config
from ..core.exceptions import NFLGravityError


class ScheduleFrequency(Enum):
    """Enumeration of supported schedule frequencies."""
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class SimpleScheduler:
    """Simple scheduler for running pipeline tasks."""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger("nfl_gravity.scheduler")
        
        self._scheduled_jobs = []
        self._running = False
        self._scheduler_thread = None
        self._stop_event = threading.Event()
    
    def schedule_pipeline(self, 
                         pipeline_func: Callable,
                         teams: List[str],
                         frequency: ScheduleFrequency,
                         start_time: Optional[datetime] = None,
                         job_name: str = "nfl_pipeline") -> str:
        """
        Schedule a pipeline execution.
        
        Args:
            pipeline_func: Function to execute (should be pipeline.run_full_pipeline)
            teams: List of teams to process
            frequency: How often to run the pipeline
            start_time: When to start (defaults to now)
            job_name: Name for the scheduled job
            
        Returns:
            Job ID for tracking
        """
        if start_time is None:
            start_time = datetime.now()
        
        job_id = f"{job_name}_{len(self._scheduled_jobs)}"
        
        job = {
            'id': job_id,
            'name': job_name,
            'pipeline_func': pipeline_func,
            'teams': teams,
            'frequency': frequency,
            'next_run': start_time,
            'last_run': None,
            'run_count': 0,
            'status': 'scheduled',
            'created_at': datetime.now()
        }
        
        self._scheduled_jobs.append(job)
        
        self.logger.info(f"Scheduled job {job_id} for {frequency.value} execution starting {start_time}")
        
        # Start scheduler if not running
        if not self._running:
            self.start()
        
        return job_id
    
    def start(self):
        """Start the scheduler."""
        if self._running:
            self.logger.warning("Scheduler is already running")
            return
        
        self._running = True
        self._stop_event.clear()
        self._scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._scheduler_thread.start()
        
        self.logger.info("Scheduler started")
    
    def stop(self):
        """Stop the scheduler."""
        if not self._running:
            return
        
        self._running = False
        self._stop_event.set()
        
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5)
        
        self.logger.info("Scheduler stopped")
    
    def _scheduler_loop(self):
        """Main scheduler loop."""
        while self._running and not self._stop_event.is_set():
            try:
                current_time = datetime.now()
                
                # Check each job
                for job in self._scheduled_jobs:
                    if job['status'] != 'scheduled':
                        continue
                    
                    if current_time >= job['next_run']:
                        self._execute_job(job)
                
                # Sleep for 60 seconds before next check
                self._stop_event.wait(60)
                
            except Exception as e:
                self.logger.error(f"Error in scheduler loop: {e}")
                time.sleep(60)  # Wait before retrying
    
    def _execute_job(self, job: Dict[str, Any]):
        """Execute a scheduled job."""
        job_id = job['id']
        
        try:
            self.logger.info(f"Executing scheduled job: {job_id}")
            
            job['status'] = 'running'
            job['last_run'] = datetime.now()
            
            # Execute the pipeline function
            result = job['pipeline_func'](
                teams=job['teams'],
                fast_mode=True  # Use fast mode for scheduled runs
            )
            
            job['run_count'] += 1
            job['status'] = 'scheduled'  # Reset to scheduled for next run
            job['last_result'] = result
            
            # Calculate next run time
            job['next_run'] = self._calculate_next_run(job)
            
            self.logger.info(f"Job {job_id} completed successfully. Next run: {job['next_run']}")
            
        except Exception as e:
            job['status'] = 'failed'
            job['last_error'] = str(e)
            
            self.logger.error(f"Job {job_id} failed: {e}")
            
            # For failed jobs, retry in 1 hour
            job['next_run'] = datetime.now() + timedelta(hours=1)
    
    def _calculate_next_run(self, job: Dict[str, Any]) -> datetime:
        """Calculate the next run time for a job."""
        frequency = job['frequency']
        last_run = job['last_run']
        
        if frequency == ScheduleFrequency.ONCE:
            # One-time jobs don't get rescheduled
            return datetime.max
        elif frequency == ScheduleFrequency.DAILY:
            return last_run + timedelta(days=1)
        elif frequency == ScheduleFrequency.WEEKLY:
            return last_run + timedelta(weeks=1)
        elif frequency == ScheduleFrequency.MONTHLY:
            # Approximate monthly scheduling (30 days)
            return last_run + timedelta(days=30)
        else:
            return datetime.max
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a scheduled job.
        
        Args:
            job_id: ID of the job
            
        Returns:
            Job status dictionary or None if not found
        """
        for job in self._scheduled_jobs:
            if job['id'] == job_id:
                return {
                    'id': job['id'],
                    'name': job['name'],
                    'status': job['status'],
                    'frequency': job['frequency'].value,
                    'next_run': job['next_run'].isoformat(),
                    'last_run': job['last_run'].isoformat() if job['last_run'] else None,
                    'run_count': job['run_count'],
                    'created_at': job['created_at'].isoformat()
                }
        
        return None
    
    def list_jobs(self) -> List[Dict[str, Any]]:
        """
        List all scheduled jobs.
        
        Returns:
            List of job status dictionaries
        """
        return [self.get_job_status(job['id']) for job in self._scheduled_jobs]
    
    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a scheduled job.
        
        Args:
            job_id: ID of the job to cancel
            
        Returns:
            True if job was cancelled, False if not found
        """
        for i, job in enumerate(self._scheduled_jobs):
            if job['id'] == job_id:
                del self._scheduled_jobs[i]
                self.logger.info(f"Cancelled job: {job_id}")
                return True
        
        return False
    
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._running
    
    def get_scheduler_status(self) -> Dict[str, Any]:
        """
        Get overall scheduler status.
        
        Returns:
            Dictionary with scheduler status
        """
        return {
            'running': self._running,
            'total_jobs': len(self._scheduled_jobs),
            'active_jobs': len([j for j in self._scheduled_jobs if j['status'] == 'scheduled']),
            'failed_jobs': len([j for j in self._scheduled_jobs if j['status'] == 'failed']),
            'next_job_run': min([j['next_run'] for j in self._scheduled_jobs if j['status'] == 'scheduled'], 
                               default=None)
        }
