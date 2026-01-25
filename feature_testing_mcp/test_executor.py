"""Test executor for running feature tests"""

import subprocess
import logging
from pathlib import Path
from typing import Tuple, Optional, Dict, Any

from .exceptions import TestExecutionError
from .test_registry import TEST_REGISTRY, get_test_info, infer_test_from_keywords

logger = logging.getLogger(__name__)


class TestExecutor:
    """Executes tests for features"""
    
    def __init__(self, project_root: str):
        """
        Initialize test executor.
        
        Args:
            project_root: Path to project root directory
        """
        self.project_root = Path(project_root)
        if not self.project_root.exists():
            raise TestExecutionError(f"Project root does not exist: {project_root}")
    
    def run_test(
        self, 
        test_name: str, 
        timeout: Optional[int] = None
    ) -> Tuple[bool, str, Optional[Dict]]:
        """
        Execute a test by name.
        
        Args:
            test_name: Name of test from TEST_REGISTRY
            timeout: Optional timeout in seconds (uses registry default if not provided)
        
        Returns:
            Tuple of (success: bool, notes: str, result: Optional[Dict])
        """
        # Get test info from registry
        test_info = get_test_info(test_name)
        if not test_info:
            return False, f"Unknown test: {test_name}", None
        
        script = test_info['script']
        args = test_info.get('args', [])
        test_timeout = timeout or test_info.get('timeout', 180)
        
        logger.info(f"Running test: {test_name} (script: {script}, timeout: {test_timeout}s)")
        
        try:
            # Build command
            cmd = ['python3', script] + args
            
            # Execute test
            result = subprocess.run(
                cmd,
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=test_timeout
            )
            
            # Determine success based on return code
            success = result.returncode == 0
            
            # Build notes
            if success:
                notes = f"Test passed successfully"
            else:
                # Include stderr in notes for failed tests
                stderr_preview = result.stderr[:300] if result.stderr else "No error output"
                notes = f"Test failed with exit code {result.returncode}. Error: {stderr_preview}"
            
            # Build result dict
            test_result = {
                'return_code': result.returncode,
                'stdout_length': len(result.stdout),
                'stderr_length': len(result.stderr),
                'timeout': test_timeout,
                'script': script,
                'args': args
            }
            
            # Include stderr preview if failed
            if not success and result.stderr:
                test_result['stderr_preview'] = result.stderr[:500]
            
            logger.info(f"Test {test_name} {'passed' if success else 'failed'} (exit code: {result.returncode})")
            return success, notes, test_result
            
        except subprocess.TimeoutExpired:
            notes = f"Test timed out after {test_timeout} seconds"
            logger.warning(f"Test {test_name} timed out")
            return False, notes, {'timeout': test_timeout, 'timed_out': True}
        
        except FileNotFoundError:
            notes = f"Test script not found: {script}"
            logger.error(notes)
            return False, notes, {'script': script, 'error': 'Script not found'}
        
        except Exception as e:
            notes = f"Test execution error: {str(e)}"
            logger.error(f"Error executing test {test_name}: {e}", exc_info=True)
            return False, notes, {'error': str(e)}
    
    def run_inferred_test(
        self, 
        feature_name: str, 
        description: str = ""
    ) -> Tuple[bool, str, Optional[Dict]]:
        """
        Infer and run a test based on feature name and description.
        
        Args:
            feature_name: Name of the feature
            description: Description of the feature
        
        Returns:
            Tuple of (success: bool, notes: str, result: Optional[Dict])
        """
        # Try to infer test from keywords
        test_name = infer_test_from_keywords(feature_name, description)
        
        if test_name:
            logger.info(f"Inferred test '{test_name}' for feature '{feature_name}'")
            return self.run_test(test_name)
        else:
            # No matching test found
            notes = f"Could not infer test for feature '{feature_name}'. No matching keywords found."
            logger.warning(notes)
            return False, notes, {'inference_failed': True}
    
    def validate_test(self, test_name: str) -> Tuple[bool, str]:
        """
        Validate that a test exists and its script is available.
        
        Args:
            test_name: Name of test to validate
        
        Returns:
            Tuple of (valid: bool, message: str)
        """
        test_info = get_test_info(test_name)
        if not test_info:
            return False, f"Unknown test: {test_name}"
        
        script_path = self.project_root / test_info['script']
        if not script_path.exists():
            return False, f"Test script not found: {test_info['script']}"
        
        return True, f"Test '{test_name}' is valid"
    
    def list_available_tests(self) -> Dict[str, Dict[str, Any]]:
        """
        Get list of all available tests with their info.
        
        Returns:
            Dict mapping test names to test info
        """
        available = {}
        for test_name, test_info in TEST_REGISTRY.items():
            script_path = self.project_root / test_info['script']
            test_info_copy = test_info.copy()
            test_info_copy['available'] = script_path.exists()
            test_info_copy['script_path'] = str(script_path)
            available[test_name] = test_info_copy
        
        return available

